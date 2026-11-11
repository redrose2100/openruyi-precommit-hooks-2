"""Check the ``Source`` field of spec files against the openRuyi guidelines.

Two documents define the rule:

* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines``
  (``#source`` section)
* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/SourceURL``
  (the SourceURL supplement it links to)

Checkpoints
-----------

S1. Two source declarations must not resolve to the same index. ``Source``
    and ``Source0`` both mean index ``0``, so using both is a clash.
S2. A declared ``Source`` or ``SourceN`` must not be empty.
S3. A source that resolves to an ``http`` or ``https`` URL must be
    immediately preceded by a ``#!RemoteAsset:`` comment.
S4. That ``#!RemoteAsset:`` comment must carry a ``sha256:`` checksum on
    the same line, because an HTTP source without one cannot be verified.
S5. A ``#!RemoteAsset:`` whose value is a version-control fetch such as
    ``git+https://...`` must be followed by ``#!CreateArchive``, because
    the archive does not exist upstream and must be produced at build time.
S6. ``#!CreateArchive`` must sit directly between ``#!RemoteAsset:`` and
    the ``Source`` line, with no other line in between.
S7. A ``#!RemoteAsset:`` comment must not be orphaned; it must annotate a
    ``Source`` line, possibly through an intervening ``#!CreateArchive``.
S8. The field is spelled ``Source`` or ``SourceN``; ``source`` and
    ``SourceX`` are reported.
S9. ``SourceN`` indices should start at ``0`` and increase by one, with no
    gap. This is the only "should" clause, so it has an off switch.
S10. A SourceForge download must use ``downloads.sourceforge.net``. The
    neighbouring ``download.sourceforge.net`` and ``prdownloads`` hosts,
    and the ``/projects/.../files/...`` browser URL, are all reported.
S11. A source that resolves to an ``http`` or ``https`` URL must end with a
    file name; a URL whose last path segment is empty names a directory,
    and rpm cannot derive a tarball from it.

S3 resolves a ``%{url}`` prefix against the ``URL`` field before deciding,
because reusing ``%{url}`` is the documented and preferred form. A value
that still holds an unexpanded macro, and a bare local file name, are not
network sources and are therefore exempt from S3, S4 and S11.

S4 accepts only the ``sha256:`` algorithm. The document allows a checksum,
``remoteassetify`` emits SHA-256, and a shortened or foreign digest gives
no verification value.

Field ordering, whether the downloaded content really is the upstream
source of this package, whether a local file name conveys its purpose,
reachability of the URL, and the exact byte size of the tarball are all
deliberately out of scope. The document asks for an adjacent comment on an
unclear local source name; that judgement needs a human reader, so it is
not automated here.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence

# One source declaration: (name as written, value, source index or None,
# 1-based line). The index is None for a name that only looks like a
# source field, such as "SourceX", which S8 reports but the index checks
# skip.
SourceDecl = tuple[str, str, 'int | None', int]


# Matches any top-level "Field: value" line. The name is captured verbatim
# so that S8 can see the spelling the packager used.
_RE_FIELD = re.compile(r'^([A-Za-z]\w*)\s*:\s*(.*)$')

# A section header. Section arguments ("%pre -n foo") are ignored. The
# closed whitelist keeps macro invocations such as "%global" and "%if"
# from ending the main field block.
_RE_SECTION = re.compile(r'^%([a-z]\w*)\b')

# The closed set of real RPM sections, mirroring check-spec-basic-fields.
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

# The comment that marks a source as fetched over the network.
_RE_REMOTE_ASSET = re.compile(r'^#!RemoteAsset\s*:?\s*(.*)$')

# The comment that asks the build system to build the archive itself.
_RE_CREATE_ARCHIVE = re.compile(r'^#!CreateArchive\s*$')

# A "%sourcelist" block header. Arguments are not allowed.
_RE_SOURCELIST = re.compile(r'^%sourcelist\b\s*(.*)$')

# An absolute URL: a scheme, "://", a host that stops at the first path,
# query, fragment or space character, then the rest of the value.
_RE_ABSOLUTE = re.compile(
    r'^([A-Za-z][A-Za-z0-9+.\-]*)://([^/?#\s]+)([^?#\s]*)',
)

# The documented checksum form, "sha256:" followed by 64 hex digits.
_RE_SHA256 = re.compile(r'^sha256\s*:\s*([0-9A-Fa-f]{64})$')

# A version-control fetch prefix, as used in a "#!RemoteAsset:" value that
# names a repository instead of a downloadable archive. Three shapes occur:
# "git+https://...", "git://..." and "git:https://...".
_RE_VCS_FETCH = re.compile(
    r'^(?:git|hg|svn|bzr|cvs)(?:\+|:)',
    re.IGNORECASE,
)

# A macro reference, "%{name}" or the conditional "%{?flag:text}". Removed
# before a query string is looked for, because the "?" of a conditional
# macro is not a URL query. Macros nest, as in "%{?rc:-%{rc}}", so the
# removal repeats until the text stops changing.
_RE_MACRO = re.compile(r'%\{[^{}]*\}')

# A reuse of the URL field as a prefix, which the document encourages.
_URL_PREFIX = '%{url}'

# The only SourceForge host that serves a direct file download.
SOURCEFORGE_HOST = 'downloads.sourceforge.net'


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


def _main_block_end(lines: list[str]) -> int:
    """Return how many leading lines belong to the main field block."""
    for index, line in enumerate(lines):
        match = _RE_SECTION.match(line)
        if match is None:
            continue
        if '%' + match.group(1) in KNOWN_SECTIONS:
            return index
    return len(lines)


def _find_source_fields(
    lines: list[str],
) -> list[tuple[str, str, int | None, int]]:
    """Return every source declaration as (name, value, index, line number).

    The index is ``0`` for a bare ``Source`` and ``N`` for ``SourceN``, so
    that S1 can spot a ``Source`` plus ``Source0`` clash. A name that only
    looks like a source field, such as ``SourceX`` or ``Sources``, gets
    ``None`` so that the index checks skip it while S8 still reports the
    spelling. Only the main field block is scanned: a ``Source`` written
    after ``%description`` is not a field.
    """
    end = _main_block_end(lines)
    found: list[tuple[str, str, int | None, int]] = []
    for offset in range(end):
        match = _RE_FIELD.match(lines[offset])
        if match is None:
            continue
        name = match.group(1)
        lowered = name.lower()
        if not lowered.startswith('source'):
            continue
        digits = lowered[len('source'):]
        if digits and re.fullmatch(r'\d+', digits) is None:
            number: int | None = None
        elif digits:
            number = int(digits)
        else:
            number = 0
        found.append((name, match.group(2).strip(), number, offset + 1))
    return found


def _find_url_field(lines: list[str]) -> str:
    """Return the value of the main ``URL`` field, or an empty string."""
    end = _main_block_end(lines)
    for offset in range(end):
        match = _RE_FIELD.match(lines[offset])
        if match is None:
            continue
        if match.group(1) == 'URL':
            return match.group(2).strip()
    return ''


def _find_comments(
    lines: list[str],
    pattern: re.Pattern[str],
) -> list[tuple[str, int, int]]:
    """Return (payload, 0-based offset, 1-based line) for each match.

    The payload is group 1 when the pattern captures one, so that
    ``#!CreateArchive`` - which has nothing to carry - yields an empty
    payload instead of an index error.
    """
    end = _main_block_end(lines)
    has_group = pattern.groups >= 1
    found: list[tuple[str, int, int]] = []
    for offset in range(end):
        match = pattern.match(lines[offset])
        if match is None:
            continue
        payload = match.group(1).strip() if has_group else ''
        found.append((payload, offset, offset + 1))
    return found


def _resolve_url(value: str, url_field: str) -> str:
    """Expand a leading ``%{url}`` against the ``URL`` field."""
    if not url_field or not value.startswith(_URL_PREFIX):
        return value
    return url_field.rstrip('/') + value[len(_URL_PREFIX):]


def _strip_macros(text: str) -> str:
    """Remove every macro reference, innermost first.

    ``%{?rc_ver:-%{rc_ver}}`` is a nested conditional, so one pass leaves
    the outer braces behind and the ``?`` of the conditional would look
    like a URL query. Repeating until the text stops changing removes the
    whole construct.
    """
    while True:
        stripped = _RE_MACRO.sub('', text)
        if stripped == text:
            return stripped
        text = stripped


def _network_scheme(value: str, url_field: str) -> str | None:
    """Return ``'http'``/``'https'`` for a network source, else ``None``.

    A value that names a directory or holds an unexpanded macro before the
    scheme is not a network source, and stays ``None`` so that the network
    checks stay silent instead of guessing.
    """
    resolved = _resolve_url(value, url_field)
    if _RE_VCS_FETCH.match(resolved) is not None:
        return None
    match = _RE_ABSOLUTE.match(resolved)
    if match is None:
        return None
    scheme = match.group(1).lower()
    if scheme in ('http', 'https'):
        return scheme
    return None


def _remote_before(
    lines: list[str],
    offset: int,
) -> tuple[str, int] | None:
    """Return the ``#!RemoteAsset:`` that annotates this ``Source`` line.

    Two accepted shapes, both immediate:

    ``#!RemoteAsset: ...`` then ``Source: ...``
    ``#!RemoteAsset: ...`` then ``#!CreateArchive`` then ``Source: ...``

    A blank line or any other comment in between breaks the chain, which
    is what S3 and S6 report.
    """
    if offset >= 1:
        match = _RE_REMOTE_ASSET.match(lines[offset - 1])
        if match is not None:
            return match.group(1).strip(), offset
    if offset >= 2 and _RE_CREATE_ARCHIVE.match(lines[offset - 1]):
        match = _RE_REMOTE_ASSET.match(lines[offset - 2])
        if match is not None:
            return match.group(1).strip(), offset - 1
    return None


def _check_duplicate_index(
    sources: list[SourceDecl],
) -> list[str]:
    """S1: two declarations must not resolve to the same index."""
    errors: list[str] = []
    seen: dict[int, str] = {}
    for name, _, number, line in sources:
        if number is None:
            continue
        first = seen.get(number)
        if first is None:
            seen[number] = name
            continue
        errors.append(
            f'"{name}" (line {line}) repeats source index {number}, '
            f'already declared as "{first}"; Source and Source0 both mean '
            'index 0, so keep only one',
        )
    return errors


def _check_empty(sources: list[SourceDecl]) -> list[str]:
    """S2: a declared source must not be empty."""
    errors: list[str] = []
    for name, value, _, line in sources:
        if value:
            continue
        errors.append(
            f'{name} field (line {line}) is empty; write the upstream URL, '
            'or delete the line when the package needs no source input',
        )
    return errors


def _check_remote_asset_present(
    lines: list[str],
    sources: list[SourceDecl],
    url_field: str,
) -> list[str]:
    """S3: an HTTP(S) source needs a ``#!RemoteAsset:`` right above it."""
    errors: list[str] = []
    for name, value, _, line in sources:
        if _network_scheme(value, url_field) is None:
            continue
        if _remote_before(lines, line - 1) is not None:
            continue
        errors.append(
            f'{name} (line {line}) is a network source but has no '
            '"#!RemoteAsset:" comment directly above it; add the comment '
            'with its sha256 checksum',
        )
    return errors


def _check_checksum(
    lines: list[str],
    sources: list[SourceDecl],
    url_field: str,
) -> list[str]:
    """S4: the ``#!RemoteAsset:`` of an HTTP(S) source needs a sha256."""
    errors: list[str] = []
    for name, value, _, line in sources:
        if _network_scheme(value, url_field) is None:
            continue
        remote = _remote_before(lines, line - 1)
        if remote is None:
            continue
        payload, remote_line = remote
        if _RE_SHA256.match(payload) is not None:
            continue
        if not payload:
            errors.append(
                f'"#!RemoteAsset:" (line {remote_line}) is empty; it must '
                'carry the checksum of the archive, as in '
                '"#!RemoteAsset:  sha256:<64 hex digits>"',
            )
            continue
        errors.append(
            f'"#!RemoteAsset: {payload}" (line {remote_line}) carries no '
            'sha256 checksum; an HTTP source must state it on the same '
            'line, as in "#!RemoteAsset:  sha256:<64 hex digits>"',
        )
    return errors


def _check_create_archive_required(
    lines: list[str],
    sources: list[SourceDecl],
) -> list[str]:
    """S5: a VCS fetch in ``#!RemoteAsset:`` needs ``#!CreateArchive``."""
    errors: list[str] = []
    for name, _, _, line in sources:
        remote = _remote_before(lines, line - 1)
        if remote is None:
            continue
        payload, remote_line = remote
        if _RE_VCS_FETCH.match(payload) is None:
            continue
        if _RE_CREATE_ARCHIVE.match(lines[line - 2]):
            continue
        errors.append(
            f'"#!RemoteAsset: {payload}" (line {remote_line}) fetches from '
            'a version-control repository, so "#!CreateArchive" must come '
            f'between it and {name} (line {line})',
        )
    return errors


def _check_create_archive_placement(
    lines: list[str],
    archives: list[tuple[str, int, int]],
    sources: list[SourceDecl],
) -> list[str]:
    """S6: ``#!CreateArchive`` sits between ``#!RemoteAsset:`` and Source."""
    errors: list[str] = []
    source_offsets = {line - 1 for _, _, _, line in sources}
    for _, offset, line in archives:
        if offset < 1 or _RE_REMOTE_ASSET.match(lines[offset - 1]) is None:
            errors.append(
                f'"#!CreateArchive" (line {line}) must come directly after '
                'the "#!RemoteAsset:" comment that names the repository',
            )
        if offset + 1 not in source_offsets:
            errors.append(
                f'"#!CreateArchive" (line {line}) must come directly before '
                'the Source line that names the archive it builds',
            )
    return errors


def _check_remote_asset_orphan(
    lines: list[str],
    remotes: list[tuple[str, int, int]],
    archives: list[tuple[str, int, int]],
    sources: list[SourceDecl],
) -> list[str]:
    """S7: a ``#!RemoteAsset:`` must annotate a ``Source`` line."""
    errors: list[str] = []
    source_offsets = {line - 1 for _, _, _, line in sources}
    archive_offsets = {offset for _, offset, _ in archives}
    for payload, offset, line in remotes:
        target = offset + 1
        if target in source_offsets:
            continue
        if target in archive_offsets and target + 1 in source_offsets:
            continue
        shown = payload if payload else '(empty)'
        errors.append(
            f'"#!RemoteAsset: {shown}" (line {line}) does not annotate a '
            'Source line; put it directly above the Source it describes',
        )
    return errors


def _check_field_case(
    sources: list[SourceDecl],
) -> list[str]:
    """S8: the field is spelled ``Source`` or ``SourceN``."""
    errors: list[str] = []
    for name, _, _, line in sources:
        if name == 'Source' or re.fullmatch(r'Source\d+', name) is not None:
            continue
        errors.append(
            f'source field (line {line}) is spelled "{name}"; write '
            '"Source" or "SourceN"',
        )
    return errors


def _check_index_sequence(
    sources: list[SourceDecl],
) -> list[str]:
    """S9: ``SourceN`` indices should start at 0 and increase by one."""
    known = [(name, line) for name, _, number, line in sources
             if number is not None]
    if not known:
        return []
    numbers = sorted({number for _, _, number, _ in sources
                      if number is not None})
    expected = list(range(numbers[-1] + 1))
    if numbers == expected:
        return []
    missing = [str(n) for n in expected if n not in numbers]
    if len(missing) > 6:
        detail = ', '.join(missing[:6]) + ', ...'
    else:
        detail = ', '.join(missing)
    return [
        f'source indices are not numbered from 0 without gaps; index {detail} '
        f'is missing (first declaration on line {known[0][1]})',
    ]


def _check_sourceforge(
    sources: list[SourceDecl],
    url_field: str,
) -> list[str]:
    """S10: a SourceForge download must use ``downloads.sourceforge.net``."""
    errors: list[str] = []
    for name, value, _, line in sources:
        if _network_scheme(value, url_field) is None:
            continue
        match = _RE_ABSOLUTE.match(_resolve_url(value, url_field))
        assert match is not None
        host = match.group(2).lower()
        if host == SOURCEFORGE_HOST:
            continue
        if host != 'sourceforge.net' and not host.endswith('.sourceforge.net'):
            continue
        errors.append(
            f'{name} (line {line}) uses the SourceForge host "{host}"; '
            f'write "{SOURCEFORGE_HOST}" instead, as in '
            f'"https://{SOURCEFORGE_HOST}/%{{name}}/%{{name}}-%{{version}}'
            '.tar.gz"',
        )
    return errors


def _check_file_name(
    sources: list[SourceDecl],
    url_field: str,
) -> list[str]:
    """S11: an HTTP(S) source URL must yield a file name for rpm.

    rpm takes the tarball name from the URL, so the URL must expose one.
    Two shapes hide it, and both need the documented URL fragment:

    * the path ends in a directory, as in ``https://example.org/foo/1.0/``;
    * the path is a script rather than a file, as in
      ``https://example.org/download.cgi?file=foo``.

    A conditional macro such as ``%{?rc:-rc}`` contributes a ``?`` that is
    not a query string, so macros are stripped before the query test.
    """
    errors: list[str] = []
    for name, value, _, line in sources:
        if _network_scheme(value, url_field) is None:
            continue
        plain = _strip_macros(_resolve_url(value, url_field))
        if '#' in plain:
            # The fragment already states the file name.
            continue
        if '?' in plain:
            problem = 'a query string and no URL fragment'
        else:
            match = _RE_ABSOLUTE.match(plain)
            assert match is not None
            segment = match.group(3)
            if segment.strip('/') and segment.rsplit('/', 1)[-1]:
                continue
            problem = 'a directory path'
        errors.append(
            f'{name} (line {line}) gives rpm {problem}, so the tarball name '
            'cannot be derived; state the file name in a URL fragment, as '
            'in "https://example.org/download.cgi#/foo-1.0.tar.gz"',
        )
    return errors


def _check_source_list(
    lines: list[str],
) -> list[str]:
    """S12: a ``%sourcelist`` block must be bare and must list a file."""
    errors: list[str] = []
    end = _main_block_end(lines)
    for offset in range(end):
        match = _RE_SOURCELIST.match(lines[offset])
        if match is None:
            continue
        if match.group(1).strip():
            errors.append(
                f'"%sourcelist" (line {offset + 1}) must be written alone on '
                'its line; list the files below it, one per line',
            )
        following = lines[offset + 1] if offset + 1 < end else ''
        if not following.strip() or following.lstrip().startswith('%'):
            errors.append(
                f'"%sourcelist" (line {offset + 1}) is not followed by any '
                'file; list the local source inputs below it, one per line',
            )
    return errors


def _check_spec_source_ext(
    filename: str,
    *,
    check_field_case: bool = True,
    check_index_sequence: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    sources = _find_source_fields(lines)
    url_field = _find_url_field(lines)
    remotes = _find_comments(lines, _RE_REMOTE_ASSET)
    archives = _find_comments(lines, _RE_CREATE_ARCHIVE)

    errors: list[str] = []
    errors.extend(_check_duplicate_index(sources))
    errors.extend(_check_empty(sources))
    errors.extend(_check_remote_asset_present(lines, sources, url_field))
    errors.extend(_check_checksum(lines, sources, url_field))
    errors.extend(_check_create_archive_required(lines, sources))
    errors.extend(_check_create_archive_placement(lines, archives, sources))
    errors.extend(
        _check_remote_asset_orphan(lines, remotes, archives, sources),
    )
    if check_field_case:
        errors.extend(_check_field_case(sources))
    if check_index_sequence:
        errors.extend(_check_index_sequence(sources))
    errors.extend(_check_sourceforge(sources, url_field))
    errors.extend(_check_file_name(sources, url_field))
    errors.extend(_check_source_list(lines))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_source(filename: str) -> list[str]:
    return _check_spec_source_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    parser.add_argument(
        '--no-check-field-case',
        dest='check_field_case',
        action='store_false',
        help='do not report a field spelled "source" or "SourceX"',
    )
    parser.add_argument(
        '--no-check-index-sequence',
        dest='check_index_sequence',
        action='store_false',
        help='do not report SourceN indices that skip a number',
    )
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        findings = _check_spec_source_ext(
            filename,
            check_field_case=args.check_field_case,
            check_index_sequence=args.check_index_sequence,
        )
        for finding in findings:
            print(finding)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
