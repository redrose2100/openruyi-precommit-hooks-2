"""Check the ``VCS`` field of spec files against the openRuyi guidelines.

The rule is limited to the ``VCS`` field, traceable to a single document:

* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines``
  (``#vcs`` section)

The four clauses are chained, not independent. Clause 2 gates clauses 1
and 3, which gives the decision the packager must make::

    URL is a source repository link  -> VCS may be omitted
    otherwise, VCS is declared       -> the value must be usable
    otherwise                        -> write the documented placeholder
    otherwise                        -> violation: VCS is required

Checkpoints
-----------

V1. When ``URL`` is not a source repository link, the spec must either
    declare ``VCS`` or write the documented placeholder comment
    ``# VCS: No VCS link available``. A spec whose ``URL`` is already a
    repository link is exempt, which is clause 2.
V2. The placeholder text must be exactly the documented sentence, and the
    ``# VCS:`` prefix must be preserved. A comment whose text is itself a
    URL is a commented-out field, not a placeholder, and is ignored.
V3. A placeholder comment and a real ``VCS`` field must not coexist.
V4. A declared ``VCS`` must not be empty.
V5. The value must not be assembled from macros such as ``%{name}``.
V6. The value must be a cloneable address: a ``git:``, ``git+``, ``hg:``,
    ``svn:`` or ``bzr:`` prefixed link, an absolute ``scheme://host`` URL,
    or an scp-like ``user@host:path``.

V5 inverts the usual macro escape hatch. Every other rule treats a
macro-valued field as unjudgeable and stays silent; here the macro itself
is the defect, so a macro value reports V5 and skips V6. Percent escapes
such as ``%2B`` are URL encoding, not macros, and are stripped before the
``%`` test.

V1 needs a decision on whether ``URL`` names a source repository. That is
the only heuristic here, and it is deliberately conservative: see
``_is_repo_link``. Documentation and package-index sites such as
``metacpan.org`` and ``crates.io`` are not repositories, so ``VCS`` is
required for them; ``--no-check-doc-site`` exempts them.

Field ordering, whether ``URL`` really is the upstream repository, whether
``VCS`` and ``URL`` name the same project, reachability of the clone URL,
and a wrapped continuation line are all deliberately out of scope.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence


# The placeholder a spec writes when no usable source repository link
# exists. The "# VCS:" prefix is part of the documented form.
PLACEHOLDER_TEXT = 'No VCS link available'

# Matches any top-level "Field: value" line, including an empty value. The
# name is captured verbatim so that V7 can see the spelling the packager
# used. Applied per line, never to the whole file.
_RE_FIELD = re.compile(r'^([A-Za-z]\w*)\s*:\s*(.*)$')

# Matches the documented placeholder comment. The name is matched in any
# case because V1 accepts the VCS field in any case as well, and a comment
# is not a field, so the spelling rule of V7 does not apply to it.
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

# An absolute URL: a scheme, "://", a host that stops at the first path,
# query, fragment or space character, then the rest of the value. The host
# and the path are both captured, because repository detection and the
# cloneable check need them.
_RE_ABSOLUTE = re.compile(
    r'^[A-Za-z][A-Za-z0-9+.\-]*://([^/?#\s]+)([^?#\s]*)',
)

# The version-control schemes that may prefix a clone URL, optionally with
# the "+" suffix of a pip-style direct reference ("git+https://...").
_RE_CLONE_SCHEME = re.compile(
    r'^(?:git|git\+|hg|hg\+|svn|svn\+|bzr|bzr\+|cvs):',
    re.IGNORECASE,
)

# An scp-like address, "user@host:path", as accepted by git clone.
_RE_SCP_LIKE = re.compile(r'^[^@\s/:]+@[^:\s/]+:\S+$')

# A percent escape such as "%2B" or "%20". URL encoding, not a macro.
_RE_PCT_ESCAPE = re.compile(r'%[0-9A-Fa-f]{2}')

# Text that reads as an actual URL rather than prose. A commented-out field
# ("# VCS: git:https://example.org/foo.git") is a disabled field, not the
# documented placeholder, so V2 must not report it. A "git:" prefix is a
# clone scheme rather than a URL scheme, so it needs its own alternative.
_RE_LOOKS_LIKE_URL = re.compile(
    r'^(?:[A-Za-z][A-Za-z0-9+.\-]*://|%|(?:git|git\+|hg|hg\+|svn|svn\+'
    r'|bzr|bzr\+|cvs):)',
)

# Forge hosts, mapped to the minimum number of path segments that identify
# a single repository. "https://github.com/foo" is a user page, not a repo;
# "https://github.com/foo/bar" is a repo.
FORGE_MIN_DEPTH: dict[str, int] = {
    'bitbucket.org': 2,
    'codeberg.org': 2,
    'github.com': 2,
    'git.kernel.org': 3,
    'git.sr.ht': 2,
    'gitlab.com': 2,
    'hg.sr.ht': 1,
    'invent.kde.org': 2,
    'pagure.io': 1,
    'salsa.debian.org': 2,
    'sourceware.org': 1,
    'src.fedoraproject.org': 2,
}

# A host that announces itself as a source host. Any such host with a
# non-empty path is treated as a repository.
_RE_SOURCE_HOST = re.compile(
    r'^(?:git|gitlab|gitea|gogs|forgejo|hg|svn|cvs|bzr|code|repo|cgit)\.'
    r'|(?:^|\.)googlesource\.com$'
    r'|(?:^|\.)sr\.ht$',
)

# Documentation and package-index hosts. These describe a package rather
# than host its source, so they are not repository links.
_RE_DOC_SITE = re.compile(
    r'\.github\.io$'
    r'|\.gitlab\.io$'
    r'|\.readthedocs\.io$'
    r'|^(?:crates\.io|docs\.rs|lib\.rs|metacpan\.org|pypi\.org'
    r'|pypi\.python\.org)$',
)


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


def _split_url(value: str) -> tuple[str, str] | None:
    """Return (lowercased host, path) for an absolute URL, else ``None``."""
    match = _RE_ABSOLUTE.match(value)
    if match is None:
        return None
    return match.group(1).lower(), match.group(2) or ''


def _path_segments(path: str) -> list[str]:
    return [part for part in path.strip('/').split('/') if part]


def _is_repo_link(value: str) -> bool:
    """True when a ``URL`` value names a source code repository.

    This decides clause 2, and therefore whether V1 applies at all. It is
    deliberately conservative: a value is a repository link only when it
    ends in ``.git``, or the host is a known forge with enough path depth,
    or the host announces itself as a source host and has a non-empty path.
    Everything else - a plain project website, a documentation site, a bare
    host - is not, which is what makes ``VCS`` required there.
    """
    parts = _split_url(value)
    if parts is None:
        return False
    host, path = parts
    if path.rstrip('/').endswith('.git'):
        return True
    depth = FORGE_MIN_DEPTH.get(host)
    if depth is not None:
        return len(_path_segments(path)) >= depth
    if _RE_SOURCE_HOST.search(host) is not None:
        return bool(_path_segments(path))
    return False


def _is_doc_site(value: str) -> bool:
    """True when a ``URL`` value points at a documentation or index site."""
    parts = _split_url(value)
    if parts is None:
        return False
    return _RE_DOC_SITE.search(parts[0]) is not None


def _find_fields(lines: list[str]) -> list[tuple[str, str, int]]:
    """Return every ``VCS`` field as (spelling, value, 1-based line).

    The name is matched in any case so that V7 can report a misspelled
    field, and so that a misspelled field still feeds V4-V6: a wrong name
    does not make the value irrelevant. Comment lines, ``%global`` and
    ``%define`` lines and RPM conditional lines can never match, because
    the field must start at column 0. Both the main package field and the
    ``VCS`` lines inside ``%package`` blocks are returned.
    """
    found: list[tuple[str, str, int]] = []
    for index, line in enumerate(lines, start=1):
        match = _RE_FIELD.match(line)
        if match is None:
            continue
        if match.group(1).lower() != 'vcs':
            continue
        found.append((match.group(1), match.group(2).strip(), index))
    return found


def _find_url_fields(lines: list[str]) -> list[tuple[str, int]]:
    """Return every ``URL`` field as (value, 1-based line)."""
    found: list[tuple[str, int]] = []
    for index, line in enumerate(lines, start=1):
        match = _RE_FIELD.match(line)
        if match is None:
            continue
        if match.group(1).lower() != 'url':
            continue
        found.append((match.group(2).strip(), index))
    return found


def _find_placeholders(lines: list[str]) -> list[tuple[str, int]]:
    """Return every ``# VCS:`` placeholder as (text, 1-based line).

    A comment whose text is itself a URL or a macro is a commented-out
    field rather than the documented placeholder, so it is ignored here:
    it neither satisfies V1 nor triggers V2 or V3.
    """
    found: list[tuple[str, int]] = []
    for index, line in enumerate(lines, start=1):
        match = _RE_PLACEHOLDER.match(line)
        if match is None:
            continue
        if match.group(1).lower() != 'vcs':
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
    does not end the block, so a ``VCS`` written after it is still counted.
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
    V5 forbids in this field.
    """
    return '%' in _RE_PCT_ESCAPE.sub('', value)


def _check_presence(
    vcs: list[tuple[str, str, int]],
    placeholders: list[tuple[str, int]],
    urls: list[tuple[str, int]],
    end: int,
    *,
    check_doc_site: bool,
) -> list[str]:
    """V1: ``VCS`` is required when ``URL`` is not a repository link."""
    if any(line <= end for _, _, line in vcs):
        return []
    if any(line <= end for _, line in placeholders):
        return []
    if not urls:
        # A missing URL is check-spec-url's finding; one defect must not
        # have two owners, and without a URL the VCS requirement cannot be
        # decided at all.
        return []
    value = urls[0][0]
    if not value:
        # An empty URL is check-spec-url's U2 finding, and it says nothing
        # about the VCS requirement.
        return []
    if _has_macro(value):
        # A macro-built URL cannot be judged before expansion, and it is
        # already check-spec-url's U4 finding, so V1 stays silent here.
        return []
    if _is_repo_link(value):
        return []
    if not check_doc_site and _is_doc_site(value):
        return []
    return [
        'VCS field is missing; the URL is not a source repository link, '
        'so set VCS to a cloneable source repository link, or write the '
        f'comment "# VCS: {PLACEHOLDER_TEXT}"',
    ]


def _check_mutual_exclusion(
    vcs: list[tuple[str, str, int]],
    placeholders: list[tuple[str, int]],
) -> list[str]:
    """V3: the placeholder and a real field must not coexist."""
    if not vcs or not placeholders:
        return []
    return [
        f'VCS field (line {vcs[0][2]}) and the placeholder comment '
        f'(line {placeholders[0][1]}) must not both be present; keep the '
        'field, or delete it and keep the comment',
    ]


def _check_placeholder_text(
    placeholders: list[tuple[str, int]],
) -> list[str]:
    """V2: the placeholder text must be the documented sentence."""
    errors: list[str] = []
    for text, line in placeholders:
        if text == PLACEHOLDER_TEXT:
            continue
        errors.append(
            f'placeholder comment (line {line}) must read exactly '
            f'"# VCS: {PLACEHOLDER_TEXT}"',
        )
    return errors


def _check_field_case(vcs: list[tuple[str, str, int]]) -> list[str]:
    """V7: the field is spelled ``VCS``."""
    errors: list[str] = []
    for name, _, line in vcs:
        if name == 'VCS':
            continue
        errors.append(
            f'VCS field (line {line}) is spelled "{name}"; write "VCS"',
        )
    return errors


def _check_cloneable(value: str, line: int) -> list[str]:
    """V6: the value must be an address usable to clone the source.

    Three accepted shapes, tried in order:

    * an scp-like ``user@host:path``, as ``git clone`` accepts;
    * a plain absolute URL, which covers the ``git://``, ``https://``,
      ``ssh://`` and ``svn://`` transports directly;
    * the same URL behind a version-control prefix, as in
      ``git:https://...`` or ``git+https://...``.
    """
    if _RE_SCP_LIKE.match(value) is not None:
        return []
    for candidate in (value, _RE_CLONE_SCHEME.sub('', value)):
        parts = _split_url(candidate)
        if parts is not None and '.' in parts[0]:
            return []
    return [
        f'VCS "{value}" (line {line}) is not a cloneable address; write '
        'the source repository clone URL, for example '
        '"git:https://git.example.org/project.git"',
    ]


def _check_value(value: str, line: int) -> list[str]:
    """V4, V5 and V6 for one ``VCS`` value."""
    if not value:
        return [f'VCS field (line {line}) is empty']
    if _has_macro(value):
        return [
            f'VCS "{value}" (line {line}) is built from a macro; write '
            'the expanded clone URL',
        ]
    return _check_cloneable(value, line)


def _check_spec_vcs_ext(
    filename: str,
    *,
    check_field_case: bool = True,
    check_doc_site: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    vcs = _find_fields(lines)
    placeholders = _find_placeholders(lines)
    urls = _find_url_fields(lines)
    end = _main_block_end(lines)

    errors: list[str] = []
    errors.extend(
        _check_presence(
            vcs,
            placeholders,
            urls,
            end,
            check_doc_site=check_doc_site,
        ),
    )
    errors.extend(_check_mutual_exclusion(vcs, placeholders))
    errors.extend(_check_placeholder_text(placeholders))
    if check_field_case:
        errors.extend(_check_field_case(vcs))
    for _, value, line in vcs:
        errors.extend(_check_value(value, line))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_vcs(filename: str) -> list[str]:
    return _check_spec_vcs_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    parser.add_argument(
        '--no-check-field-case',
        dest='check_field_case',
        action='store_false',
        help='do not report a field spelled "VCs" or "vcs"',
    )
    parser.add_argument(
        '--no-check-doc-site',
        dest='check_doc_site',
        action='store_false',
        help='do not require VCS when the URL is a documentation or '
        'package-index site',
    )
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        findings = _check_spec_vcs_ext(
            filename,
            check_field_case=args.check_field_case,
            check_doc_site=args.check_doc_site,
        )
        for finding in findings:
            print(finding)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
