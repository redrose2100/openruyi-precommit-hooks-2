"""Check spec files against the openRuyi packaging guidelines.

The rule is limited to the "Basic Fields and Sections" and "Minimal
Skeleton Example" sections of the openRuyi Packaging Specification:

* the fields ``Name`` ``Version`` ``Release`` ``Summary`` ``License`` and
  the sections ``%description`` ``%files`` ``%changelog`` must be present
* those sections must appear in that relative order
* sections must be separated by a blank line
* ``%changelog`` must contain ``%autochangelog``
* ``Release`` should use ``%autorelease``
* inside each field block the five core fields should appear in the
  documented order

A missing conditional field or conditional section is not a violation.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence


# Fields every spec must contain, in the documented relative order.
CORE_FIELD_ORDER: tuple[str, ...] = (
    'Name',
    'Version',
    'Release',
    'Summary',
    'License',
)

# The documented relative order of all optional fields (informational).
FIELD_ORDER: tuple[str, ...] = (
    'Name',
    'Version',
    'Release',
    'Summary',
    'License',
    'URL',
    'VCS',
    'Source',
    'BuildArch',
    'BuildSystem',
    'Patch',
    'BuildOption',
    'BuildRequires',
    'Provides',
    'Conflicts',
    'Obsoletes',
    'Recommends',
    'Requires',
    'Supplements',
)

# Sections that must exist and be ordered.
REQUIRED_SECTIONS: tuple[str, ...] = (
    '%description',
    '%files',
    '%changelog',
)

# The closed set of RPM sections. Anything else that starts with "%" is a
# macro invocation (%license, %doc, %systemd_post, %autochangelog, ...)
# and must never be mistaken for a section.
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

# Sections that begin a new field block. Only %package does; every other
# section ends the field-collection phase of the file.
_BLOCK_SECTION = '%package'

# The three mandatory sections define the documented relative order.
_ORDERED_SECTIONS: tuple[str, ...] = REQUIRED_SECTIONS

_RE_FIELD = re.compile(r'^([A-Za-z]\w*)\s*:')
_RE_SECTION = re.compile(r'^%([a-z]\w*)\b')
_RE_CONDITIONAL = re.compile(
    r'^%(?:if|ifarch|ifnarch|ifos|ifnos|else|elif|endif|end|global|'
    r'define|bcond|undefine|dnl)\b',
)
_RE_SOURCE_N = re.compile(r'^Source(\d+)$')
_RE_PATCH_N = re.compile(r'^Patch(\d+)$')
_RE_BUILD_OPTION = re.compile(r'^BuildOption\(')
_RE_RELEASE_AUTO = re.compile(r'^%(?:autorelease|\{autorelease\})$')
_RE_CHANGELOG_AUTO = re.compile(
    r'^%(?:autochangelog|\{autochangelog\}|\{\?autochangelog\})$',
)


def _dedup(errors: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for err in errors:
        if err not in seen:
            seen.add(err)
            out.append(err)
    return out


def _normalize_field(name: str) -> str:
    """Map numbered and parameterised field names to one canonical name."""
    if _RE_SOURCE_N.match(name):
        return 'Source'
    if _RE_PATCH_N.match(name):
        return 'Patch'
    if _RE_BUILD_OPTION.match(name):
        return 'BuildOption'
    return name


def _is_section(line: str) -> str | None:
    """Return the known section name on this line, or None."""
    match = _RE_SECTION.match(line)
    if match is None:
        return None
    section = '%' + match.group(1)
    if section in KNOWN_SECTIONS:
        return section
    return None


def _blocks_of(
    lines: list[str],
) -> tuple[list[dict[str, int]], list[tuple[str, int]]]:
    """Split the file into field blocks and collect its sections.

    Returns ``(blocks, sections)`` where ``blocks`` is a list of
    ``{field: first_line_index}`` mappings (the main preamble first, then
    one per ``%package``) and ``sections`` is a list of
    ``(section_name, line_index)`` pairs in file order.

    ``blocks[0]`` is always the main preamble, even when it contains no
    fields; empty ``%package`` blocks are dropped so that the subpackage
    block numbers stay contiguous.
    """
    blocks: list[dict[str, int]] = []
    sections: list[tuple[str, int]] = []
    current: dict[str, int] = {}
    ended = False

    for index, line in enumerate(lines):
        section = _is_section(line)
        if section is not None:
            sections.append((section, index))
            if section == _BLOCK_SECTION:
                # A %package section opens a fresh field block.
                blocks.append(current)
                current = {}
                ended = False
                continue
            if not ended:
                blocks.append(current)
                current = {}
                ended = True
            continue
        if ended:
            continue
        if _RE_CONDITIONAL.match(line) or line.lstrip().startswith('#'):
            continue
        match = _RE_FIELD.match(line)
        if match is not None:
            name = _normalize_field(match.group(1))
            current.setdefault(name, index)

    blocks.append(current)
    # Keep the main preamble (blocks[0]) even when empty so that its index
    # and the subpackage block numbers stay meaningful.
    return [blocks[0]] + [block for block in blocks[1:] if block], sections


def _all_fields(blocks: list[dict[str, int]]) -> set[str]:
    names: set[str] = set()
    for block in blocks:
        names.update(block)
    return names


def _check_missing_fields(blocks: list[dict[str, int]]) -> list[str]:
    present = _all_fields(blocks)
    return [
        f'missing required field "{name}"'
        for name in CORE_FIELD_ORDER
        if name not in present
    ]


def _check_missing_sections(
    sections: list[tuple[str, int]],
) -> list[str]:
    present = {name for name, _ in sections}
    return [
        f'missing required section "{name}"'
        for name in REQUIRED_SECTIONS
        if name not in present
    ]


def _check_section_order(
    sections: list[tuple[str, int]],
) -> list[str]:
    first: dict[str, int] = {}
    for name, index in sections:
        first.setdefault(name, index)
    for previous, following in zip(
        _ORDERED_SECTIONS, _ORDERED_SECTIONS[1:],
    ):
        if previous in first and following in first:
            if first[previous] > first[following]:
                return [
                    f'section "{previous}" (line {first[previous] + 1}) '
                    f'must appear before "{following}" '
                    f'(line {first[following] + 1})',
                ]
    return []


def _has_blank_separator(
    lines: list[str], prev_line: int, line: int,
) -> bool:
    """Report whether a blank line separates the two section headers.

    Comment lines and conditional directives are skipped: a comment placed
    directly above a section reads as part of that section's header, which
    is the dominant style in the repository.
    """
    for index in range(line - 1, prev_line, -1):
        text = lines[index]
        if not text.strip():
            return True
        if _RE_CONDITIONAL.match(text) or text.lstrip().startswith('#'):
            continue
        return False
    return False


def _check_section_blank_lines(
    lines: list[str], sections: list[tuple[str, int]],
) -> list[str]:
    """Adjacent differently named sections need a blank line between them."""
    errors: list[str] = []
    for (prev_name, prev_line), (name, line) in zip(
        sections, sections[1:],
    ):
        if name == prev_name:
            # Consecutive blocks of the same section are normal, e.g. the
            # %files sections of several subpackages.
            continue
        if _has_blank_separator(lines, prev_line, line):
            continue
        errors.append(
            f'section "{name}" (line {line + 1}) must be separated '
            f'from "{prev_name}" (line {prev_line + 1}) by a blank line',
        )
    return errors


def _check_changelog(
    lines: list[str], sections: list[tuple[str, int]],
) -> list[str]:
    index = None
    for name, line_index in sections:
        if name == '%changelog':
            index = line_index
            break
    if index is None:
        return []
    for line in lines[index + 1:]:
        if not line.strip():
            continue
        if _RE_CHANGELOG_AUTO.match(line.strip()):
            return []
        return [
            f'%changelog (line {index + 1}) must contain '
            f'"%autochangelog", found "{line.strip()}"',
        ]
    return ['%changelog must contain "%autochangelog"']


def _check_field_order(blocks: list[dict[str, int]]) -> list[str]:
    """Core fields must keep their relative order inside each block."""
    order = {name: i for i, name in enumerate(CORE_FIELD_ORDER)}
    errors: list[str] = []
    for block_index, block in enumerate(blocks):
        present = [name for name in block if name in order]
        present.sort(key=lambda name: block[name])
        for previous, following in zip(present, present[1:]):
            if order[previous] > order[following]:
                if block_index == 0:
                    where = 'main block'
                else:
                    where = f'field block {block_index}'
                errors.append(
                    f'field "{following}" (line {block[following] + 1}) '
                    f'must appear before "{previous}" '
                    f'(line {block[previous] + 1}) in the {where}',
                )
    return errors


def _check_release(
    blocks: list[dict[str, int]], lines: list[str],
) -> list[str]:
    if not blocks:
        return []
    index = blocks[0].get('Release')
    if index is None:
        return []
    value = lines[index].split(':', 1)[1].strip()
    if _RE_RELEASE_AUTO.match(value):
        return []
    return [
        f'Release (line {index + 1}) should use "%autorelease", '
        f'found "{value}"',
    ]


def _check_spec_basic_fields(filename: str) -> list[str]:
    try:
        with open(filename, encoding='utf-8') as f:
            lines = f.read().splitlines()
    except UnicodeDecodeError:
        return [f'{filename}: file is not valid UTF-8']
    except OSError as exc:
        return [f'{filename}: {exc}']

    blocks, sections = _blocks_of(lines)

    errors: list[str] = []
    errors.extend(_check_missing_fields(blocks))
    errors.extend(_check_missing_sections(sections))
    errors.extend(_check_section_order(sections))
    errors.extend(_check_section_blank_lines(lines, sections))
    errors.extend(_check_changelog(lines, sections))
    errors.extend(_check_field_order(blocks))
    errors.extend(_check_release(blocks, lines))

    return _dedup([f'{filename}: {err}' for err in errors])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        for err in _check_spec_basic_fields(filename):
            print(err)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
