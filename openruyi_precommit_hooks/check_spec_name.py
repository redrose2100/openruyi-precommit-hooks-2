"""Check the ``Name`` field of spec files against the openRuyi guidelines.

The rule is limited to the ``Name`` field and to the naming rules that apply
to it, traceable to two documents:

* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#name``
* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/Naming``

Checkpoints
-----------

N1. ``Name`` is present and non-empty.
N2. The value only uses ``[A-Za-z0-9._+-]`` (no whitespace, no other
    punctuation). Macro-valued names are skipped.
N3. The value does not start or end with a separator. ``+`` is an ordinary
    character: ``libsigc++`` is a legitimate C++ library name.
N4. The value does not contain consecutive separators (``--``, ``__``, ``..``,
    and the mixed pairs).
N5. The main package name is not reused by a subpackage of the same spec, with
    a case-insensitive comparison. The guideline states that conflicting names
    are absolutely forbidden, "including names that differ only in case".
N6. The value does not contain uppercase characters, unless it starts with
    ``perl-``. The guideline's case-sensitivity section says the default is
    lowercase and that a lowercase name is wrong only when upstream capitalizes
    its own name (``RapidCopy``). It also carves out perl: CPAN groups and types
    must keep their uppercase spelling. N6 is on by default and reports the
    upstream names whose capitalization the packager must preserve;
    ``--no-check-case`` turns it off for a repository that has accepted them.
    N8 silences N6 when the project's own download URL proves the spelling.
N7. The value does not contain ``_``. Off by default via
    ``--check-separator``, because the guideline's separator section lists
    underscore-bearing upstream names (``nss_wrapper`` and friends) as explicit
    exceptions and every underscore name in the corpus is such a case.
N8. A capitalized value is spelled the way the project's own download URL
    spells it. A ``Source`` URL names the released artefact, so it is upstream
    proof for N6: when the artefact spells the name exactly, both checkpoints
    stay silent, and when it differs, N8 reports the mismatch instead of N6.
    Only the ``Source\\d*`` lines are read; the ``URL`` line is excluded because
    a forge normalises that path to lower case while the tarball keeps the real
    spelling. N8 is bidirectional: it catches ``Name: openblas`` against an
    ``OpenBLAS-0.3.31.tar.gz`` artefact, which N6 could never see, as well as
    ``Name: Xwayland`` against ``xwayland-24.1.11.tar.xz``.
    ``--no-check-upstream-case`` disables N8 and restores the evidence-free N6
    result.

N8 reads the spec and nothing else: it never opens a socket.

Everything that is not statically decidable is deliberately out of scope:
encoding an ABI/SONAME major or an upstream major version into the name,
``Provides``-based upstream aliases, cross-file name conflicts (this hook runs
per file), doc-subpackage and font-package naming, and the perl/Python prefix
rules.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence


# Matches a top-level "Name: value" line, including an empty value. Applied
# per line, never to the whole file: a non-MULTILINE search over the full text
# matches nothing.
_RE_NAME = re.compile(r'^Name\s*:\s*(.*)$')

# Matches "%global name value" / "%define name value" so that macro-valued
# package names can be resolved for the duplicate check.
_RE_MACRO_DEF = re.compile(r'^%(?:global|define)\s+(\w+)(?:\(\))?\s+(\S+)')

# Matches "%{name}" style macro references.
_RE_MACRO_REF = re.compile(r'%\{(\w+)\}')

# Matches a "%package" header and captures the subpackage token. The "-n"
# argument form is handled separately so the token after it is used verbatim.
_RE_PACKAGE = re.compile(r'^%package\s+(.*)$')

# Characters that may appear in a package name. "+" is included on purpose:
# libsigc++ is a real package whose upstream name contains it.
_RE_INVALID_CHAR = re.compile(r'[^A-Za-z0-9._+-]')

# Separators as defined by the guideline. "+" is intentionally absent.
_SEPARATORS: tuple[str, ...] = ('-', '_', '.')

# Consecutive-separator pairs the guideline's delimiter rule forbids.
_BAD_SEQUENCES: tuple[str, ...] = (
    '--', '__', '..', '-_', '_-', '._', '_.', '-.', '.-',
)

# Uppercase in a perl module name is required by the guideline, so N6 skips
# names carrying this prefix.
_PERL_PREFIX = 'perl-'

# Matches a "Source", "Source0" or "Source12" line and captures the value.
# Only Source lines count as upstream evidence: the URL line is a project page
# that forges normalise to lower case, while the tarball keeps the real
# spelling. Using "URL" here produced false findings for libXScrnSaver,
# libXcursor and libXinerama, whose URL is a lower-case GitLab path.
_RE_SOURCE = re.compile(r'^Source\d*\s*:\s*(\S+)\s*$')

# Matches a top-level "Version: value" line, used to strip a trailing version
# from an artefact name before it is compared.
_RE_VERSION = re.compile(r'^Version\s*:\s*(.*)$')

# Matches a top-level "URL: value" line. The value is never used as evidence
# itself; it is only bound so that a Source written as
# "%{url}/releases/..." can expand the same way RPM expands it.
_RE_URL = re.compile(r'^URL\s*:\s*(.*)$')

# Archive suffixes removed from an artefact name. Longest first so that
# ".tar.gz" is stripped before ".tar".
_ARCHIVE_SUFFIXES: tuple[str, ...] = tuple(
    sorted(
        (
            '.tar.bz2', '.tar.gz', '.tar.lz', '.tar.lzma', '.tar.xz',
            '.tar.zst', '.tbz2', '.tgz', '.txz', '.tzst', '.crate',
            '.gem', '.jar', '.tar', '.whl', '.zip',
        ),
        key=len,
        reverse=True,
    ),
)

# Host whose download URL is a repository path rather than an artefact name,
# so its owner and repository segments are evidence as well.
_GITHUB_HOST = 'github.com'


# --- offline upstream evidence (N8 and N9) ---------------------------------


def _read_lines(filename: str) -> tuple[list[str] | None, str | None]:
    """Return the spec's lines, or (None, error) when it cannot be read."""
    try:
        with open(filename, encoding='utf-8') as f:
            return f.read().splitlines(), None
    except UnicodeDecodeError:
        return None, f'{filename}: file is not valid UTF-8'
    except OSError as exc:
        return None, f'{filename}: {exc}'


def _find_name(lines: list[str]) -> tuple[str | None, int | None]:
    """Return the main package name and its 1-based line number.

    The first matching line wins. Comment lines, ``%global``/``%define`` lines
    and RPM conditional lines can never match because none of them start with
    ``Name`` followed by a colon at column 0. A declared but valueless
    ``Name:`` yields an empty string, which is distinct from a missing field.
    """
    for index, line in enumerate(lines, start=1):
        match = _RE_NAME.match(line)
        if match is not None:
            return match.group(1).strip(), index
    return None, None


def _collect_macros(lines: list[str]) -> dict[str, str]:
    """Collect ``%global`` / ``%define`` values for later resolution."""
    macros: dict[str, str] = {}
    for line in lines:
        match = _RE_MACRO_DEF.match(line)
        if match is not None:
            macros.setdefault(match.group(1), match.group(2))
    return macros


def _resolve(value: str, name: str, macros: dict[str, str]) -> str:
    """Expand ``%{name}`` and any known ``%global``/``%define`` reference.

    ``%{name}`` is expanded literally and never through ``macros``: a
    pathological ``%global name name-%{name}`` would otherwise send the
    recursion guard down an irrelevant axis.
    """
    cyclic = _cyclic_macro_refs(macros)
    value = value.replace('%{name}', name)
    return _RE_MACRO_REF.sub(
        lambda match: (
            match.group(0)
            if match.group(1) in cyclic
            else macros.get(match.group(1), match.group(0))
        ),
        value,
    )


def _cyclic_macro_refs(macros: dict[str, str]) -> set[str]:
    """Return macros that vanish while expanding, so they expand to nothing.

    ``%global prefix prefix-%{prefix}`` expands forever. Such a macro is
    dropped like the RPM interpreter does rather than expanded once, which
    would leave a stray ``%{prefix}`` and hide a real name behind the
    unresolved-macro guard.
    """
    cyclic: set[str] = set()
    for key, value in macros.items():
        if key in _RE_MACRO_REF.findall(value):
            cyclic.add(key)
    changed = True
    while changed:
        changed = False
        for key, value in macros.items():
            if key in cyclic:
                continue
            if any(ref in cyclic for ref in _RE_MACRO_REF.findall(value)):
                cyclic.add(key)
                changed = True
    return cyclic


def _is_macro_valued(value: str) -> bool:
    """True when a value still holds an unresolved macro reference.

    Such a value could expand to anything, so every value-based checkpoint is
    skipped for it.
    """
    return '%' in value


def _subpackage_names(
    lines: list[str],
    name: str,
    macros: dict[str, str],
) -> list[tuple[str, int]]:
    """Return (resolved subpackage name, 1-based line) for each ``%package``.

    ``%package devel`` means ``<name>-devel``. ``%package -n foo`` means
    ``foo``. Names that stay macro-valued after resolution are skipped.
    """
    found: list[tuple[str, int]] = []
    for index, line in enumerate(lines, start=1):
        match = _RE_PACKAGE.match(line)
        if match is None:
            continue
        argument = match.group(1).strip()
        if argument.startswith('-n'):
            rest = argument[2:].strip()
            token = rest.split()[0] if rest else ''
            candidate = _resolve(token, name, macros)
        else:
            token = argument.split()[0] if argument else ''
            candidate = f'{name}-{_resolve(token, name, macros)}'
        if not candidate or _is_macro_valued(candidate):
            continue
        found.append((candidate, index))
    return found


def _check_present(value: str | None, line: int | None) -> list[str]:
    """N1: the spec must declare a non-empty ``Name``."""
    if value is None:
        return ['Name field is missing']
    if not value:
        return [f'Name field is empty (line {line})']
    return []


def _check_chars(value: str, line: int) -> list[str]:
    """N2: only ``[A-Za-z0-9._+-]`` is allowed."""
    match = _RE_INVALID_CHAR.search(value)
    if match is None:
        return []
    char = match.group(0)
    shown = repr(char) if char.isspace() else f'"{char}"'
    return [
        f'Name "{value}" (line {line}) contains an invalid character {shown}',
    ]


def _check_delimiter(value: str, line: int) -> list[str]:
    """N3: no leading or trailing separator."""
    if value[0] in _SEPARATORS or value[-1] in _SEPARATORS:
        return [
            f'Name "{value}" (line {line}) must not start or end '
            'with a separator',
        ]
    return []


def _check_sequences(value: str, line: int) -> list[str]:
    """N4: no consecutive separators."""
    errors: list[str] = []
    for sequence in _BAD_SEQUENCES:
        if sequence in value:
            errors.append(
                f'Name "{value}" (line {line}) must not contain '
                f'consecutive separators "{sequence}"',
            )
    return errors


def _check_duplicate(
    value: str,
    line: int,
    subpackages: list[tuple[str, int]],
) -> list[str]:
    """N5: a subpackage must not reuse the main package name."""
    lowered = value.lower()
    for subpackage, sub_line in subpackages:
        if subpackage.lower() == lowered:
            return [
                f'duplicate package name "{subpackage}" (line {sub_line}), '
                f'already used by the main package (line {line})',
            ]
    return []


def _check_case(value: str, line: int) -> list[str]:
    """N6: prefer lowercase unless upstream capitalizes its own name."""
    if value.startswith(_PERL_PREFIX):
        return []
    if not any(char.isupper() for char in value):
        return []
    return [
        f'Name "{value}" (line {line}) contains uppercase characters; the '
        'default is lowercase unless the upstream project capitalizes its '
        'name',
    ]


def _check_underscore(value: str, line: int) -> list[str]:
    """N7: prefer ``-`` over ``_`` unless the upstream name uses ``_``."""
    if '_' not in value:
        return []
    return [
        f'Name "{value}" (line {line}) contains "_"; the separator must be '
        '"-" unless the upstream name naturally contains an underscore',
    ]


def _find_version(lines: list[str]) -> str | None:
    """Return the first ``Version:`` value, or None when it is absent."""
    for line in lines:
        match = _RE_VERSION.match(line)
        if match is not None:
            return match.group(1).strip()
    return None


def _find_url(lines: list[str]) -> str | None:
    """Return the first ``URL:`` value, or None when it is absent."""
    for line in lines:
        match = _RE_URL.match(line)
        if match is not None:
            return match.group(1).strip()
    return None


def _builtin_tags(lines: list[str], name: str) -> dict[str, str]:
    """Return the RPM builtins a ``Source`` value may reference.

    ``%{name}``, ``%{version}`` and ``%{url}`` are builtins fed by the ``Name``,
    ``Version`` and ``URL`` tags rather than by ``%global``, so a Source such as
    ``%{url}/releases/individual/lib/%{name}-%{version}.tar.xz`` only expands
    when they are bound here. ``%{url}`` is bound for expansion only; the
    ``URL`` tag itself is never read as evidence, because a forge normalises
    that path to lower case while the tarball keeps the real spelling.
    """
    builtins: dict[str, str] = {}
    version = _find_version(lines)
    if version:
        builtins['version'] = version
    url = _find_url(lines)
    if url:
        builtins['url'] = url
    return builtins


def _upstream_answer(
    filename: str,
) -> tuple[str, int, list[str], str] | str:
    """Return ``(name, line, sources, version)``, or the error to report."""
    lines, error = _read_lines(filename)
    if error is not None:
        return error
    assert lines is not None
    value, line = _find_name(lines)
    if value is None or not value or line is None:
        return ''
    macros = _collect_macros(lines)
    resolved = _resolve(value, value, macros)
    if _is_macro_valued(resolved):
        return ''
    version = _resolve(_find_version(lines) or '', resolved, macros)
    sources = _expand_sources(
        lines,
        macros,
        resolved,
        version,
        _builtin_tags(lines, resolved),
    )
    return resolved, line, sources, version


def _strip_artefact_suffix(segment: str, version: str) -> str:
    """Reduce an artefact file name to the project name it encodes.

    ``OpenBLAS-0.3.31.tar.gz`` becomes ``OpenBLAS`` and
    ``libIDL-0.8.14.tar.bz2`` becomes ``libIDL``. A query string and a known
    archive suffix are removed, then a trailing ``-<version>`` or
    ``_<version>``.
    """
    segment = segment.split('?', 1)[0].split('#', 1)[0]
    lowered = segment.lower()
    for suffix in _ARCHIVE_SUFFIXES:
        if lowered.endswith(suffix):
            segment = segment[: -len(suffix)]
            break
    if not version:
        return segment
    for separator in ('-', '_', '.'):
        tail = f'{separator}{version}'
        if segment.endswith(tail):
            return segment[: -len(tail)]
        swapped = f'{separator}{version.replace("-", "_")}'
        if swapped != tail and segment.endswith(swapped):
            return segment[: -len(swapped)]
    return segment


def _expand_sources(
    lines: list[str],
    macros: dict[str, str],
    name: str,
    version: str,
    builtins: dict[str, str] | None = None,
) -> list[str]:
    """Return every ``Source`` value that expands to an absolute http URL.

    A value that is not an http URL (a local file, a mailto, an unresolved
    macro) carries no upstream spelling and is dropped.
    """
    bindings = {**(builtins or {}), **macros}
    bindings.setdefault('version', version)
    urls: list[str] = []
    for line in lines:
        match = _RE_SOURCE.match(line)
        if match is None:
            continue
        url = _resolve(match.group(1), name, bindings)
        if _is_macro_valued(url):
            continue
        if url.lower().startswith(('http://', 'https://')):
            urls.append(url)
    return urls


def _url_evidence(url: str, version: str) -> list[str]:
    """Return the project names a single download URL spells out.

    A ``Source`` URL yields up to three candidates: the path of a ``#/``
    fragment (the real file name when the download URL is an API endpoint),
    the last path segment, and, on GitHub, the owner and repository segments.
    """
    split = urllib.parse.urlsplit(url)
    segments = [part for part in split.path.split('/') if part]
    evidence = [part for part in split.fragment.split('/') if part]
    if segments:
        evidence.append(segments[-1])
    host = split.netloc.lower()
    if host == _GITHUB_HOST or host.endswith(f'.{_GITHUB_HOST}'):
        evidence.extend(segments[:2])
    return [
        stripped
        for stripped in (
            _strip_artefact_suffix(segment, version)
            for segment in evidence
        )
        if stripped
    ]


def _source_evidence(
    lines: list[str],
    macros: dict[str, str],
    name: str,
    version: str,
    builtins: dict[str, str],
) -> list[str]:
    """Return the project names the spec's own download URLs spell out."""
    return [
        candidate
        for url in _expand_sources(lines, macros, name, version, builtins)
        for candidate in _url_evidence(url, version)
    ]


def _with_version(macros: dict[str, str], version: str) -> dict[str, str]:
    """Return ``macros`` with ``%{version}`` bound to the ``Version`` field.

    ``%{version}`` is an RPM builtin fed by the ``Version`` tag, not a
    ``%global``, so it has to be bound here for a URL such as
    ``.../%{name}-%{version}.tar.xz`` to expand at all.
    """
    if not version or 'version' in macros:
        return macros
    return {**macros, 'version': version}


def _upstream_spellings(name: str, evidence: list[str]) -> set[str]:
    """Return every spelling of ``name`` that the evidence contains.

    Matching is case-insensitive and bounded by non-alphanumeric characters, so
    ``libX11`` is found in ``libX11-1.8.7`` and in ``libx11.tar.xz``, but
    ``libX1`` is not found in ``libX11``. The returned set keeps the case of
    the evidence, which is the whole point: it tells apart a spelling that
    agrees with the value from one that only agrees ignoring case.
    """
    boundary = re.escape(name)
    found: set[str] = set()
    for candidate in evidence:
        found.update(
            re.findall(
                rf'(?<![A-Za-z0-9]){boundary}(?![A-Za-z0-9])',
                candidate,
                re.IGNORECASE,
            ),
        )
    return found


def _check_upstream_case(
    name: str,
    line: int,
    spellings: set[str],
) -> list[str]:
    """N8: the value matches a download URL only if case is ignored.

    Reaching here means no ``Source`` URL spells the name as written, but at
    least one spells it the same way with a different case. The packager has to
    decide which of the two is intended, so it is reported in either direction:
    ``Xwayland`` against a ``xwayland`` artefact, and ``openblas`` against an
    ``OpenBLAS`` one. It replaces N6 rather than adding to it, because the N6
    text asks the packager to follow the upstream spelling, which is the very
    thing this finding already contradicts.
    """
    shown = ', '.join(f'"{spelling}"' for spelling in sorted(spellings))
    return [
        f'Name "{name}" (line {line}) is not spelled the way its Source URLs '
        f'do; upstream writes {shown}',
    ]


def _upstream_case_evidence(
    lines: list[str],
    macros: dict[str, str],
    name: str,
) -> list[str]:
    """Collect the download-URL evidence once for N6 and N8.

    N6 needs the evidence to stay silent about a spelling upstream proves, and
    N8 needs it to report a spelling upstream contradicts, so a run with both
    enabled extracts it a single time.
    """
    version = _resolve(_find_version(lines) or '', name, macros)
    return _source_evidence(
        lines,
        macros,
        name,
        version,
        _builtin_tags(lines, name),
    )


def _check_spec_name_ext(
    filename: str,
    *,
    check_case: bool = True,
    check_separator: bool = False,
    check_upstream_case: bool = True,
) -> list[str]:
    """Run every checkpoint and return the findings for ``filename``."""
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    value, line = _find_name(lines)
    errors = _check_present(value, line)
    if value is None or not value or line is None:
        return _dedup([f'{filename}: {msg}' for msg in errors])

    macros = _collect_macros(lines)
    resolved = _resolve(value, value, macros)

    messages = list(errors)
    if not _is_macro_valued(resolved):
        messages.extend(_check_chars(resolved, line))
        messages.extend(_check_delimiter(resolved, line))
        messages.extend(_check_sequences(resolved, line))
        messages.extend(
            _check_duplicate(
                resolved,
                line,
                _subpackage_names(lines, resolved, macros),
            ),
        )
        evidence: list[str] = []
        if check_upstream_case:
            evidence = _upstream_case_evidence(lines, macros, resolved)
        spellings = _upstream_spellings(resolved, evidence)
        confirmed = resolved in spellings
        reported = False
        if check_upstream_case and spellings and not confirmed:
            messages.extend(_check_upstream_case(resolved, line, spellings))
            reported = True
        if check_case and not confirmed and not reported:
            messages.extend(_check_case(resolved, line))
        if check_separator:
            messages.extend(_check_underscore(resolved, line))

    return _dedup([f'{filename}: {msg}' for msg in messages])


def _check_spec_name(filename: str) -> list[str]:
    """Canonical rule entry point required by the hook rule guidelines."""
    return _check_spec_name_ext(filename)


def _dedup(errors: list[str]) -> list[str]:
    """Drop repeated findings while preserving their order."""
    seen: set[str] = set()
    out: list[str] = []
    for err in errors:
        if err not in seen:
            seen.add(err)
            out.append(err)
    return out


# --- opt-in online verification (never part of the hook) --------------------

_HTTP_TIMEOUT = 10.0
_USER_AGENT = 'openruyi-precommit-hooks check-spec-name'

# Returned by _verify_upstream. "undetermined" is reported rather than
# ignored: a spelling that could not be checked is a result the caller asked
# for, not a pass.
_CONFIRMED = 'confirmed'
_MISMATCH = 'mismatch'
_UNDETERMINED = 'undetermined'


def _http_status(url: str, timeout: float = _HTTP_TIMEOUT) -> int | None:
    """Return the HTTP status for ``url``, or None when it is undecidable.

    HEAD is tried first because only the status matters; 403 and 405 mean the
    host refuses HEAD, so GET is retried and the body discarded. A connection
    error, a DNS failure, a rate limit or a 5xx all yield None so that the
    caller reports them as undetermined instead of as a case mismatch.
    """
    for method in ('HEAD', 'GET'):
        request = urllib.request.Request(url, method=method)
        request.add_header('User-Agent', _USER_AGENT)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as reply:
                return int(reply.status)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return 404
            if exc.code in (403, 405) and method == 'HEAD':
                continue
            return None
        except (urllib.error.URLError, OSError, ValueError):
            return None
    return None


def _json_field(
    url: str,
    field: str,
    token: str | None,
    timeout: float = _HTTP_TIMEOUT,
) -> str | None:
    """Return a dotted ``field`` from a JSON response, or None on failure."""
    request = urllib.request.Request(url)
    request.add_header('User-Agent', _USER_AGENT)
    request.add_header('Accept', 'application/json')
    if token:
        request.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            payload: object = json.loads(reply.read().decode('utf-8', 'replace'))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    for part in field.split('.'):
        if not isinstance(payload, dict):
            return None
        payload = payload.get(part)
    return payload if isinstance(payload, str) else None


def _index_spelling(
    url: str,
    token: str,
    token_override: str,
    timeout: float = _HTTP_TIMEOUT,
) -> str | None:
    """Ask the host's package index how it spells the project.

    The lookup is deliberately performed with a case-insensitive query and
    compared against the case-sensitive answer: that difference is the only
    signal a case-insensitive host provides.
    """
    split = urllib.parse.urlsplit(url)
    host = split.netloc.lower()
    segments = [part for part in split.path.split('/') if part]
    if host == _GITHUB_HOST or host.endswith(f'.{_GITHUB_HOST}'):
        if len(segments) < 2:
            return None
        full_name = _json_field(
            f'https://api.github.com/repos/{segments[0]}/{segments[1]}',
            'full_name',
            token,
            timeout,
        )
        return full_name.rsplit('/', 1)[-1] if full_name else None
    if 'gitlab' in host:
        if len(segments) < 2:
            return None
        path = urllib.parse.quote(f'{segments[0]}/{segments[1]}', safe='')
        project = _json_field(
            f'https://{host}/api/v4/projects/{path}',
            'path_with_namespace',
            token,
            timeout,
        )
        return project.rsplit('/', 1)[-1] if project else None
    if host == 'pypi.org' or host.endswith('.pythonhosted.org'):
        return _json_field(
            f'https://pypi.org/pypi/{token_override}/json',
            'info.name',
            token,
            timeout,
        )
    if host == 'crates.io' or host.endswith('.crates.io'):
        return _json_field(
            f'https://crates.io/api/v1/crates/{token_override}',
            'crate.name',
            token,
            timeout,
        )
    return None


def _upstream_tokens(name: str) -> list[str]:
    """Return the spellings a package index may hold for ``name``.

    A distribution name carries a type prefix that the index does not know, so
    ``python-Whoosh`` is looked up as ``Whoosh`` and ``perl-Git`` as ``Git``.
    """
    tokens = [name]
    for prefix in ('python-', 'perl-'):
        if name.startswith(prefix) and len(name) > len(prefix):
            tokens.append(name[len(prefix):])
    return tokens


def _verify_upstream(
    name: str,
    sources: list[str],
    *,
    timeout: float = _HTTP_TIMEOUT,
    version: str = '',
) -> tuple[str, str]:
    """Probe upstream for the way it spells ``name``.

    Two independent channels are used. The download URL proves the spelling
    when the host is case-sensitive, because the request is made with the exact
    bytes the spec writes: a 200 means those bytes are what the host serves, so
    the spelling the URL uses is authoritative, while a 404 or a transport
    failure proves nothing and is left to the second channel. A package index
    then supplies the canonical spelling for the hosts that are not
    case-sensitive, answering a case-insensitive query with the case it stores.
    """
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    served: list[str] = []
    unreachable: list[str] = []
    for url in sources:
        host = urllib.parse.urlsplit(url).netloc
        if _http_status(url, timeout) == 200:
            spellings = _upstream_spellings(name, _url_evidence(url, version))
            if name in spellings:
                return _CONFIRMED, f'Source URL returned 200: {url}'
            if spellings:
                shown = ', '.join(f'"{item}"' for item in sorted(spellings))
                return _MISMATCH, f'{url} returns 200 and spells {shown}'
            served.append(host)
        else:
            unreachable.append(host)
        for candidate in _upstream_tokens(name):
            spelled = _index_spelling(url, token, candidate, timeout)
            if spelled is None:
                continue
            if spelled == candidate:
                return _CONFIRMED, f'{host} spells it "{spelled}"'
            if spelled.lower() == candidate.lower():
                return _MISMATCH, f'{host} spells it "{spelled}"'
    if not sources:
        return _UNDETERMINED, 'the spec declares no http Source URL'
    if served:
        return _UNDETERMINED, (
            f'{", ".join(sorted(set(served)))} served every Source URL but '
            'spells no comparable project name'
        )
    return _UNDETERMINED, (
        f'unreachable: {", ".join(sorted(set(unreachable)))}'
    )


def _verify_file(filename: str, timeout: float) -> list[str]:
    """Return the upstream-verification findings for one spec file."""
    answer = _upstream_answer(filename)
    if isinstance(answer, str):
        return [answer] if answer else []
    resolved, line, sources, version = answer
    verdict, detail = _verify_upstream(
        resolved,
        sources,
        timeout=timeout,
        version=version,
    )
    if verdict == _CONFIRMED:
        return []
    if verdict == _MISMATCH:
        return [
            f'{filename}: Name "{resolved}" (line {line}) is not spelled the '
            f'way upstream writes it ({detail})',
        ]
    return [
        f'{filename}: Name "{resolved}" (line {line}) could not be verified '
        f'upstream ({detail})',
    ]


def _run_upstream_verification(
    filenames: list[str],
    workers: int,
    timeout: float,
) -> int:
    """Verify every file, in order, and return the exit code.

    Results are printed in the order the files were given, so the output of a
    parallel run is identical to a sequential one.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        reports = list(
            pool.map(lambda name: _verify_file(name, timeout), filenames),
        )
    retv = 0
    for findings in reports:
        for finding in findings:
            print(finding)
            retv = 1
    return retv


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    parser.add_argument(
        '--no-check-case',
        dest='check_case',
        action='store_false',
        help='do not report uppercase package names',
    )
    parser.add_argument(
        '--no-check-upstream-case',
        dest='check_upstream_case',
        action='store_false',
        help=(
            'ignore the case used by the Source URLs, so a capitalized name '
            'is judged by the case rule alone'
        ),
    )
    parser.add_argument(
        '--check-separator',
        dest='check_separator',
        action='store_true',
        help='also report "_" in package names',
    )
    parser.add_argument(
        '--verify-upstream',
        action='store_true',
        help=(
            'probe the Source URLs and the upstream package indexes for the '
            'spelling of the name; requires network access and must not be '
            'used as a pre-commit hook'
        ),
    )
    parser.add_argument(
        '--upstream-workers',
        type=int,
        default=8,
        metavar='N',
        help='parallel requests used by --verify-upstream (default: 8)',
    )
    parser.add_argument(
        '--upstream-timeout',
        type=float,
        default=_HTTP_TIMEOUT,
        metavar='SECONDS',
        help=f'socket timeout used by --verify-upstream (default: {_HTTP_TIMEOUT:g})',
    )
    args = parser.parse_args(argv)

    if args.verify_upstream:
        return _run_upstream_verification(
            list(args.filenames),
            max(1, args.upstream_workers),
            args.upstream_timeout,
        )

    retv = 0
    for filename in args.filenames:
        for err in _check_spec_name_ext(
            filename,
            check_case=args.check_case,
            check_separator=args.check_separator,
            check_upstream_case=args.check_upstream_case,
        ):
            print(err)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
