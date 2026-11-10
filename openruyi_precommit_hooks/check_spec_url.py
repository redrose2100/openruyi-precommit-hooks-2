"""Check the ``URL`` field of spec files against the openRuyi guidelines.

The rule is limited to the ``URL`` field, traceable to a single document:

* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines``
  (``#url`` section)

Checkpoints
-----------

U1. A spec must declare ``URL`` in the main field block, or write the
    documented placeholder comment ``# URL: No URL link available``.
U2. A declared ``URL`` must not be empty.
U3. The value must be an absolute URL, i.e. ``scheme://host`` with a
    dotted host, because it must be a meaningful package address.
U4. The value must not be assembled from macros such as ``%{name}``.
U5. The placeholder text must be exactly the documented sentence, and the
    ``# URL:`` prefix must be preserved. A comment whose text is itself a
    URL is a commented-out field, not a placeholder, and is ignored.
U6. A placeholder comment and a real ``URL`` field must not coexist.
U7. The field is spelled ``URL``; ``Url`` and ``url`` are reported.

U4 inverts the usual macro escape hatch. Every other rule treats a
macro-valued field as unjudgeable and stays silent; here the macro itself
is the defect, so a macro value reports U4 and skips U3. Percent escapes
such as ``%2B`` are URL encoding, not macros, and are stripped before the
``%`` test.

Field ordering, the "official website" and "meaningful address"
judgements, whether ``URL`` is a source repository URL (and therefore
whether ``VCS`` may be omitted), reachability, and whether ``https`` is
required are all deliberately out of scope.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence


# The placeholder a spec writes when no meaningful upstream URL exists. The
# "# URL:" prefix is part of the documented form and must be preserved.
PLACEHOLDER_TEXT = 'No URL link available'

# Matches any top-level "Field: value" line, including an empty value. The
# name is captured verbatim so that U7 can see the spelling the packager
# used. Applied per line, never to the whole file.
_RE_FIELD = re.compile(r'^([A-Za-z]\w*)\s*:\s*(.*)$')

# Matches the documented placeholder comment. The name is matched in any
# case because U1 accepts the URL field in any case as well, and a comment
# is not a field, so the spelling rule of U7 does not apply to it.
_RE_PLACEHOLDER = re.compile(r'^\s*#\s*([A-Za-z]\w*)\s*:\s*(.*)$')

# A section header. Section arguments ("%pre -n foo") are ignored, the name
# token decides. The closed whitelist keeps macro invocations such as
# "%global", "%define" and "%if" from ending the main field block.
_RE_SECTION = re.compile(r'^%([a-z]\w*)\b')

# The closed set of real RPM sections, mirroring check-spec-basic-fields.
# Anything else that starts with "%" is a macro invocation.
KNOWN_SECTIONS: frozenset[str] = frozenset({
    '%description',
    '%package',
    '%prep',
    '%conf',
    '%build',
    '%install',
    '%check',
    '%clean',
    '%files',
    '%changelog',
    '%pre',
    '%post',
    '%preun',
    '%postun',
    '%pretrans',
    '%posttrans',
    '%triggerprein',
    '%triggerin',
    '%triggerun',
    '%triggerpostun',
    '%verifyscript',
    '%generate_buildrequires',
})

# An absolute URL: a scheme, "://", then a host that stops at the first
# path, query, fragment or space character. The host must be followed by one
# of those or by the end of the value.
_RE_ABSOLUTE = re.compile(
    r'^[A-Za-z][A-Za-z0-9+.\-]*://([^/?#\s]+)(?:[/?#]|$)',
)

# A percent escape such as "%2B" or "%20". URL encoding, not a macro.
_RE_PCT_ESCAPE = re.compile(r'%[0-9A-Fa-f]{2}')

# Text that reads as an actual URL rather than prose. A commented-out field
# ("# URL: https://example.org/foo") is a disabled field, not the documented
# placeholder, so U5 must not report it.
_RE_LOOKS_LIKE_URL = re.compile(r'^[A-Za-z][A-Za-z0-9+.\-]*://|^%')


def _dedup(errors: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for err in errors:
        if err not in seen:
            seen.add(err)
            out.append(err)
    return out


def _read_lines(filename: str) -> tuple[list[str] | None, str | None]:
    """Return the spec's lines, or (None, error) when it cannot be read."""
    try:
        with open(filename, encoding='utf-8') as f:
            return f.read().splitlines(), None
    except UnicodeDecodeError:
        return None, f'{filename}: file is not valid UTF-8'
    except OSError as exc:
        return None, f'{filename}: {exc}'


def _find_urls(lines: list[str]) -> list[tuple[str, str, int]]:
    """Return every ``URL`` field as (spelling, value, 1-based line).

    The name is matched in any case so that U7 can report a misspelled
    field, and so that a misspelled field still feeds U2-U4: a wrong name
    does not make the value irrelevant. Comment lines, ``%global`` and
    ``%define`` lines and RPM conditional lines can never match, because
    the field must start at column 0. Both the main package field and the
    ``URL`` lines inside ``%package`` blocks are returned.
    """
    found: list[tuple[str, str, int]] = []
    for index, line in enumerate(lines, start=1):
        match = _RE_FIELD.match(line)
        if match is None:
            continue
        if match.group(1).lower() != 'url':
            continue
        found.append((match.group(1), match.group(2).strip(), index))
    return found


def _find_placeholders(lines: list[str]) -> list[tuple[str, int]]:
    """Return every ``# URL:`` placeholder as (text, 1-based line).

    A comment whose text is itself a URL or a macro is a commented-out
    field rather than the documented placeholder, so it is ignored here:
    it neither satisfies U1 nor triggers U5 or U6.
    """
    found: list[tuple[str, int]] = []
    for index, line in enumerate(lines, start=1):
        match = _RE_PLACEHOLDER.match(line)
        if match is None:
            continue
        if match.group(1).lower() != 'url':
            continue
        text = match.group(2).strip()
        if _RE_LOOKS_LIKE_URL.match(text):
            continue
        found.append((text, index))
    return found


def _main_block_end(lines: list[str]) -> int:
    """Return how many leading lines belong to the main field block.

    The main block ends at the first recognised section header. A macro
    invocation such as ``%global debug_package %{nil}`` is not a section and
    does not end the block, so a ``URL`` written after it is still counted.
    """
    for index, line in enumerate(lines):
        match = _RE_SECTION.match(line)
        if match is None:
            continue
        if '%' + match.group(1) in KNOWN_SECTIONS:
            return index
    return len(lines)


def _has_macro(value: str) -> bool:
    """True when the value still holds an unexpanded macro reference.

    Percent escapes are stripped first: ``Text-Tabs%2BWrap`` is URL
    encoding, not a macro. Any remaining ``%`` is a macro reference, which
    U4 forbids in this field.
    """
    return '%' in _RE_PCT_ESCAPE.sub('', value)


def _check_presence(
    urls: list[tuple[str, str, int]],
    placeholders: list[tuple[str, int]],
    end: int,
) -> list[str]:
    """U1: the main block must declare ``URL`` or the placeholder."""
    if any(line <= end for _, _, line in urls):
        return []
    if any(line <= end for _, line in placeholders):
        return []
    return [
        'URL field is missing; set URL to the package website or the '
        'project source URL, or write the comment '
        f'"# URL: {PLACEHOLDER_TEXT}"',
    ]


def _check_mutual_exclusion(
    urls: list[tuple[str, str, int]],
    placeholders: list[tuple[str, int]],
) -> list[str]:
    """U6: the placeholder and a real field must not coexist."""
    if not urls or not placeholders:
        return []
    return [
        f'URL field (line {urls[0][2]}) and the placeholder comment '
        f'(line {placeholders[0][1]}) must not both be present; keep the '
        'field, or delete it and keep the comment',
    ]


def _check_placeholder_text(
    placeholders: list[tuple[str, int]],
) -> list[str]:
    """U5: the placeholder text must be the documented sentence."""
    errors: list[str] = []
    for text, line in placeholders:
        if text == PLACEHOLDER_TEXT:
            continue
        errors.append(
            f'placeholder comment (line {line}) must read exactly '
            f'"# URL: {PLACEHOLDER_TEXT}"',
        )
    return errors


def _check_field_case(urls: list[tuple[str, str, int]]) -> list[str]:
    """U7: the field is spelled ``URL``."""
    errors: list[str] = []
    for name, _, line in urls:
        if name == 'URL':
            continue
        errors.append(
            f'URL field (line {line}) is spelled "{name}"; write "URL"',
        )
    return errors


def _check_absolute(value: str, line: int) -> list[str]:
    """U3: the value must be an absolute URL with a dotted host."""
    match = _RE_ABSOLUTE.match(value)
    if match is not None and '.' in match.group(1):
        return []
    return [
        f'URL "{value}" (line {line}) is not an absolute URL; write the '
        'full address, for example "https://example.org/project"',
    ]


def _check_value(value: str, line: int) -> list[str]:
    """U2, U3 and U4 for one ``URL`` value."""
    if not value:
        return [f'URL field (line {line}) is empty']
    if _has_macro(value):
        return [
            f'URL "{value}" (line {line}) is built from a macro; write the '
            'expanded URL',
        ]
    return _check_absolute(value, line)


def _check_spec_url_ext(
    filename: str,
    *,
    check_field_case: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    urls = _find_urls(lines)
    placeholders = _find_placeholders(lines)
    end = _main_block_end(lines)

    errors: list[str] = []
    errors.extend(_check_presence(urls, placeholders, end))
    errors.extend(_check_mutual_exclusion(urls, placeholders))
    errors.extend(_check_placeholder_text(placeholders))
    if check_field_case:
        errors.extend(_check_field_case(urls))
    for _, value, line in urls:
        errors.extend(_check_value(value, line))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_url(filename: str) -> list[str]:
    return _check_spec_url_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    parser.add_argument(
        '--no-check-field-case',
        dest='check_field_case',
        action='store_false',
        help='do not report a field spelled "Url" or "url"',
    )
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        findings = _check_spec_url_ext(
            filename,
            check_field_case=args.check_field_case,
        )
        for finding in findings:
            print(finding)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
