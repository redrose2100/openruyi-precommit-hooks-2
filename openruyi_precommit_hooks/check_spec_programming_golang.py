"""Enforce the requirements of the Go language packaging guideline.

The Go language page of the packaging guidelines describes how a Go library
or application is packaged. The page states, verbatim:

> The following two build dependencies are indispensable:
>
>     BuildRequires:  go
>     BuildRequires:  go-rpm-macros

> When writing a Go library dependency, you must use the prescribed virtual
> dependency, whose format is ``go(<import path>)``.

> The library package itself must explicitly write out the import path and
> version it provides in the RPM spec.

> All files must be installed to ``/usr/share/gocode/src``, which
> corresponds to ``$GOPATH/src``.

> Every Go library has its own import path ... we replace all of its slashes
> with hyphens, and use a canonical identifier in place of the host name to
> name the package.

> For large repository-level packages that contain several modules, the
> name should be generated from the normalised VCS repository root path.

> The name of such a package should match the upstream project, for example
> ``ollama``. Naming it ``go-ollama`` is wrong. Likewise, the generated
> binary subpackage name must not contain the ``go-`` prefix.

> Because the import path is the same, the two must be declared mutually
> exclusive in the RPM spec.

Nine checkpoints are implemented, each anchored in one of those clauses:

* C1 and C2 reproduce the two dependencies the page calls indispensable.
* C3 reproduces the virtual dependency format.
* C4 reproduces the "explicitly write out the import path and version"
  clause.
* C5 reproduces the install location clause.
* C6 reproduces the package naming derivation.
* C7 reproduces the ban on the ``go-`` prefix for binary packages.
* C9 reproduces the clause that recommends against adding several libraries
  to one test include macro.
* C10 reproduces the mutual exclusion clause.

Everything else the page says is deliberately out of scope, because it is
either a workflow instruction, an editorial preference, or a judgement a
spec-only linter cannot make. The rejected candidates are enumerated in
``docs/rules/check-spec-programming-golang.md``.

No network access and no ``rpm`` invocation is performed, so the rule works
on a bare checkout.
"""
from __future__ import annotations

import argparse
import os
import re
from collections.abc import Iterable, Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. A trailing parenthesised argument such
# as the stage of "BuildOption(build):" belongs to the field name rather
# than to the value, so the group is matched and dropped.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)(?:\(([^)]*)\))?\s*:\s*(.*)$')

# A section header, together with everything that follows the section name
# on the same line. For "%files" the remainder is empty; for "%files -f
# devel.files" it is "-f devel.files".
RE_SECTION = re.compile(r'^%([a-z]\w*)\b(.*)$')

# A macro definition. The body is kept whole, because a value may continue
# on the following lines or hold a "%{shrink: ...}" block.
RE_DEFINE = re.compile(r'^%(?:define|global)\s+(\w+)\s*(.*)$')

# The field that switches the requirements on, and the fields that satisfy
# them. Both are matched loosely so a misspelling reported by the dedicated
# rules still contributes its value here.
RE_BUILD_SYSTEM = re.compile(r'^build-?system$', re.IGNORECASE)
RE_BUILD_REQUIRES = re.compile(r'^build-?requires?$', re.IGNORECASE)
RE_PROVIDES = re.compile(r'^provides$', re.IGNORECASE)
RE_CONFLICTS = re.compile(r'^conflicts$', re.IGNORECASE)

# One "go(<import path>)" capability, together with the remainder of the
# item, which holds the version relationship when one is written.
RE_GO_CAPABILITY = re.compile(r'^go\(\s*([^)]*?)\s*\)\s*(.*)$')

# The dependency operators. A token that is exactly an operator consumes the
# token after it, which is the version of the dependency to its left.
RE_OPERATOR = re.compile(r'^(?:<=|>=|=|<|>)$')

# The two keywords that join two dependency names into one clause.
_JOINERS = frozenset({'with', 'without'})

# The closed set of real RPM sections, mirroring check-spec-basic-fields.
# Anything else that starts with "%" is a macro invocation (%license, %doc,
# %systemd_post, %autochangelog, ...) and must never be mistaken for a
# section.
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

# The two build systems this rule covers, spelled as the page spells them.
GO_SYSTEMS: frozenset[str] = frozenset({'golang', 'golangmodules'})

# The build system that compiles Go programs. C7 only applies to it, because
# a golangmodules spec names library packages and its subpackages provide
# capabilities rather than binaries.
GOLANG = 'golang'

# The underlying build system that packages Go module sources.
GOLANGMODULES = 'golangmodules'

# The two dependencies the page calls indispensable.
TOOLCHAIN_PACKAGE = 'go'
MACROS_PACKAGE = 'go-rpm-macros'

# The canonical host identifiers the page tabulates. The table maps
# "golang.org/x/oauth2" to "go-golang-x-oauth2", "google.golang.org/
# protobuf" to "go-google-protobuf", "github.com/jpillora/backoff" to
# "go-github-jpillora-backoff" and "git.sr.ht/~sbinet/cmpimg" to
# "go-sourcehut-sbinet-cmpimg", so each host has exactly one accepted
# identifier.
HOST_IDENTIFIERS: dict[str, str] = {
    'github.com': 'github',
    'golang.org': 'golang',
    'google.golang.org': 'google',
    'git.sr.ht': 'sourcehut',
}

# The hosting sites that put an owner, and then a repository, after the
# host. A path on one of them therefore names its repository with three
# segments, while a vanity import path names its module with two.
FORGE_HOSTS: frozenset[str] = frozenset({
    'github.com',
    'git.sr.ht',
    'gitlab.com',
    'bitbucket.org',
    'codeberg.org',
})

# The install roots the page accepts. The page names
# "/usr/share/gocode/src" and states that it corresponds to "$GOPATH/src".
# The macro spellings cover the same location and are named by the
# go-rpm-macros package.
GOPATH_ROOTS: tuple[str, ...] = (
    '/usr/share/gocode/src',
    '%{_datadir}/gocode/src',
    '%{go_sys_gopath}',
    '%{gopath}',
)

# The file list directives that modify the path that follows them rather
# than naming content of their own. Every other directive (%doc,
# %license, %exclude, %ghost, %artifact, %readme, %autochangelog, ...)
# names documentation, a licence file or an exclusion, so an entry that
# carries one is not a library file to judge.
_TEXT_DIRECTIVES: frozenset[str] = frozenset({
    '%dir', '%config', '%attr', '%defattr', '%verify', '%lang',
})

# How many passes a macro expansion may take. A macro value may name another
# macro of the same package, so a handful of passes is enough for every
# spelling the corpus uses.
_EXPANSIONS = 10

# The leading token of a %files entry, when that token is a directive. The
# name is a lowercase word, which tells "%is" apart from a macro reference
# such as "%go_import_path".
RE_ENTRY_DIRECTIVE = re.compile(r'^(%[a-z]+)\b')

# The test include macros the page talks about.
_TEST_INCLUDE_MACROS = frozenset({'go_test_include', 'go_test_include_glob'})


class _Macro(NamedTuple):
    """One macro definition: its whole value and the line it starts on."""

    value: str
    line: int


class _Package(NamedTuple):
    """One package section: its header, the fields and the %files entries.

    The first package is the main package. Its ``header`` is the empty
    string and its ``line`` is zero, because no line opens it.
    """

    header: str
    line: int
    fields: list[tuple[str, str, int]]
    files: list[tuple[int, str]]


class _Analysis(NamedTuple):
    """Everything the checkpoints read out of one spec."""

    macros: dict[str, _Macro]
    packages: list[_Package]
    systems: dict[str, int]


class _Capabilities(NamedTuple):
    """The import paths every spec of one run provides and conflicts with."""

    provided: dict[str, set[str]]
    conflicted: dict[str, set[str]]


def _dedup(errors: Iterable[str]) -> list[str]:
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


def _macro_depth_after(line: str, depth: int) -> int:
    """Return the macro nesting depth after consuming one line."""
    depth += line.count('{') - line.count('}')
    return depth if depth > 0 else 0


def _section_of(line: str) -> tuple[str, str] | None:
    """Return ``(section name, suffix)`` for a known section header."""
    match = RE_SECTION.match(line)
    if match is None:
        return None
    name = '%' + match.group(1)
    if name not in KNOWN_SECTIONS:
        return None
    return name, match.group(2).strip()


def _definitions(lines: Sequence[str]) -> dict[str, _Macro]:
    """Return every macro definition, with its whole value and its line.

    A value may continue with a trailing backslash or with a ``%{shrink:``
    block that closes on a later line, so both continuations are joined
    before the value is stored. The first definition of a name wins, which
    mirrors how the file reads from top to bottom.
    """
    macros: dict[str, _Macro] = {}
    name = ''
    start = 0
    buffer = ''
    for index, line in enumerate(lines, 1):
        text = line.strip()
        if not name:
            match = RE_DEFINE.match(text)
            if match is None:
                continue
            name = match.group(1)
            start = index
            text = match.group(2).strip()
        joined = f'{buffer} {text}'.strip() if buffer else text
        continued = joined.endswith('\\')
        if continued:
            buffer = joined[:-1]
            continue
        if _macro_depth_after(joined, 0) > 0:
            buffer = joined
            continue
        macros.setdefault(name, _Macro(joined.strip(), start))
        name = ''
        buffer = ''
    if name:
        macros.setdefault(name, _Macro(buffer.strip(), start))
    return macros


def _expand(text: str, macros: dict[str, _Macro]) -> str:
    """Expand the macro spellings of one text as far as the table allows.

    Every occurrence of a macro is replaced, but a macro that is already
    being expanded higher up is left alone. That guard terminates the
    expansion even when a spec defines two macros in terms of each other,
    and it keeps the result bounded by the depth limit.
    """
    return _expand_text(text, macros, 0, frozenset())


def _expand_text(
    text: str,
    macros: dict[str, _Macro],
    depth: int,
    pending: frozenset[str],
) -> str:
    """Expand one text, refusing to re-enter a macro that is in progress."""
    if depth >= _EXPANSIONS:
        return text

    def replace(match: 're.Match[str]') -> str:
        name = match.group(1)
        if name not in macros or name in pending:
            return match.group(0)
        return _expand_text(
            macros[name].value, macros, depth + 1, pending | {name},
        )

    current = re.sub(r'%\{(\w+)\}', replace, text)
    return re.sub(r'%(\w+)', replace, current)


def _packages_of(lines: Sequence[str]) -> list[_Package]:
    """Split the file into packages, each with its fields and %files entries.

    Every ``%package`` header opens a fresh package, so a subpackage is
    judged against its own declarations. A ``%files`` section belongs to the
    package its name selects: a bare ``%files`` belongs to the main package
    even when a subpackage header precedes it, and ``%files -n <name>``
    belongs to that subpackage. A macro definition block is skipped whole,
    so the fields it holds are never read as spec fields.

    The packages are returned in the order the file declares them, so the
    main package is always the first one.
    """
    packages = [_Package('', 0, [], [])]
    current = packages[0]
    owner = packages[0]
    macro_depth = 0
    section = ''

    for index, line in enumerate(lines, 1):
        if macro_depth > 0:
            macro_depth = _macro_depth_after(line, macro_depth)
            continue
        header = _section_of(line)
        if header is not None:
            section = header[0]
            if section == '%package':
                current = _Package(line.strip(), index, [], [])
                packages.append(current)
            elif section == '%files':
                owner = _files_owner(header[1], packages)
            continue
        if line.lstrip().startswith('#'):
            continue
        stripped = line.strip()
        if section == '%files' and stripped:
            owner.files.append((index, stripped))
            continue
        match = RE_FIELD.match(line)
        if match is None:
            continue
        current.fields.append((match.group(1), match.group(3), index))
        macro_depth = _macro_depth_after(line, 0)

    return packages


def _files_owner(suffix: str, packages: Sequence[_Package]) -> _Package:
    """Return the package whose files a ``%files`` section installs."""
    options = suffix.split()
    name = ''
    index = 0
    while index < len(options):
        option = options[index].lower()
        if option == '-n' and index + 1 < len(options):
            name = options[index + 1]
            index += 2
            continue
        if option == '-f' and index + 1 < len(options):
            index += 2
            continue
        break
    if not name:
        return packages[0]
    for package in packages[1:]:
        declared = re.match(
            r'^%package\s+(?:-n\s+)?(\S+)\s*$', package.header,
            re.IGNORECASE,
        )
        if declared is not None and declared.group(1) == name:
            return package
    return packages[-1]


def _systems_of(packages: Sequence[_Package]) -> dict[str, int]:
    """Return the first line of every ``BuildSystem`` value, lowercase."""
    found: dict[str, int] = {}
    for package in packages:
        for name, value, line in package.fields:
            if RE_BUILD_SYSTEM.match(name) is None:
                continue
            for token in value.split():
                found.setdefault(token.strip().lower(), line)
    return found


def _go_system_of(systems: dict[str, int]) -> tuple[str, int]:
    """Return the Go build system this spec declares, and its line."""
    for system in (GOLANGMODULES, GOLANG):
        if system in systems:
            return system, systems[system]
    raise ValueError('the spec does not declare a Go build system')


def _analyse(lines: Sequence[str]) -> _Analysis:
    macros = _definitions(lines)
    packages = _packages_of(lines)
    return _Analysis(macros, packages, _systems_of(packages))


def _dependency_names(value: str) -> set[str]:
    """Return the lowercase name of every dependency on one field line.

    A dependency is a name optionally followed by a version operator and a
    version, or one rich dependency in parentheses, or two names joined by
    a comma, ``with`` or ``without``. Only the names are returned, so a
    version number never looks like a dependency and ``go-rpm-macros-extra``
    stays distinct from ``go-rpm-macros``.
    """
    names: set[str] = set()
    skip = False
    depth = 0
    for token in value.replace(',', ' ').split():
        opens = token.count('(')
        closes = token.count(')')
        if depth > 0 or opens or closes:
            depth = max(depth + opens - closes, 0)
            skip = False
            continue
        if skip:
            skip = False
            continue
        if RE_OPERATOR.match(token) is not None:
            skip = True
            continue
        if token.lower() in _JOINERS:
            skip = True
            continue
        names.add(token.lower())
    return names


def _declared_names(packages: Sequence[_Package]) -> set[str]:
    """Return every dependency name declared in any build-requires field."""
    declared: set[str] = set()
    for package in packages:
        for name, value, _line in package.fields:
            if RE_BUILD_REQUIRES.match(name) is not None:
                declared |= _dependency_names(value)
    return declared


def _go_capabilities(
    package: _Package, macros: dict[str, _Macro],
) -> list[tuple[str, int, str]]:
    """Return ``(import path, line, item)`` for every go() capability.

    A ``Provides`` field may join several capabilities with commas, so each
    item is judged on its own. The import path is macro expanded, because
    most specs spell it with ``%{go_import_path}``.
    """
    found: list[tuple[str, int, str]] = []
    for name, value, line in package.fields:
        if RE_PROVIDES.match(name) is None:
            continue
        for item in value.split(','):
            item = item.strip()
            match = RE_GO_CAPABILITY.match(item)
            if match is None:
                continue
            found.append((_expand(match.group(1), macros), line, item))
    return found


def _conflicts_capabilities(
    packages: Sequence[_Package], macros: dict[str, _Macro],
) -> set[str]:
    """Return every import path a ``Conflicts`` field names."""
    found: set[str] = set()
    for package in packages:
        for name, value, _line in package.fields:
            if RE_CONFLICTS.match(name) is None:
                continue
            for item in value.split(','):
                match = RE_GO_CAPABILITY.match(item.strip())
                if match is not None:
                    found.add(_expand(match.group(1), macros))
                    continue
                token = item.strip().split()
                if token:
                    found.add(_expand(token[0], macros))
    return found


def _slug(text: str) -> str:
    """Return the canonical identifier spelling of one path segment."""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def _derived_names(
    import_path: str,
) -> list[tuple[str, list[str]]] | None:
    """Return the candidate package names of one import path, longest first.

    The page replaces every slash with a hyphen, substitutes the canonical
    identifier for the host name, and takes the repository root for a large
    repository-level package. Every candidate is therefore a leading part of
    the full path, so a repository-level package is accepted through the
    shorter candidate while a misspelled segment is still reported.

    Each candidate is returned together with the path segments it leaves
    over, because those segments explain a longer package name.

    A path whose host the page does not tabulate has no canonical
    identifier, so it yields no candidate and is left alone.
    """
    segments = [item for item in import_path.split('/') if item]
    if not segments or segments[0] not in HOST_IDENTIFIERS:
        return None
    rest = [item.lstrip('~') for item in segments[1:]]
    if not rest:
        return None
    prefix = ['go', HOST_IDENTIFIERS[segments[0]]]
    return [
        (_slug('-'.join(prefix + rest[:count])), rest[count:])
        for count in range(len(rest), 0, -1)
    ]


def _matches_derived(
    actual: str, candidates: Sequence[tuple[str, list[str]]],
) -> bool:
    """Return whether the actual name is one accepted form of a candidate.

    Three forms are accepted. The name may be the candidate itself, it may
    add an ``-vN`` or ``-vN-M`` suffix for the Go module major version, or
    it may extend the candidate with the path segments the candidate leaves
    over, as in ``go-google-api-support`` for ``google.golang.org/api``.
    """
    for candidate, tail in candidates:
        if actual == candidate:
            return True
        if re.fullmatch(re.escape(candidate) + r'-v\d+(-\d+)?', actual):
            return True
        if not actual.startswith(candidate + '-'):
            continue
        remainder = actual[len(candidate) + 1:]
        if all(_slug(item) in remainder for item in tail):
            return True
    return False


def _check_toolchain(
    system: str, line: int, declared: set[str],
) -> list[str]:
    """C1: a Go spec declares the go toolchain."""
    if TOOLCHAIN_PACKAGE in declared:
        return []
    return [
        f'BuildSystem: {system} (line {line}) requires '
        f'"{TOOLCHAIN_PACKAGE}" in BuildRequires; '
        f'missing "{TOOLCHAIN_PACKAGE}"',
    ]


def _check_macros_package(
    system: str, line: int, declared: set[str],
) -> list[str]:
    """C2: a Go spec declares the go-rpm-macros package."""
    if MACROS_PACKAGE in declared:
        return []
    return [
        f'BuildSystem: {system} (line {line}) requires '
        f'"{MACROS_PACKAGE}" in BuildRequires; '
        f'missing "{MACROS_PACKAGE}"',
    ]


def _check_virtual_dependency(packages: Sequence[_Package]) -> list[str]:
    """C3: a Go library dependency uses the go(<import path>) form."""
    found: list[str] = []
    for package in packages:
        for name, value, line in package.fields:
            if RE_BUILD_REQUIRES.match(name) is None:
                continue
            for item in value.split(','):
                item = item.strip()
                if not item or item.startswith('go('):
                    continue
                token = item.split()[0]
                if '/' not in token:
                    continue
                found.append(
                    f'BuildRequires (line {line}) names the bare import path '
                    f'"{token}"; write it as the virtual dependency '
                    f'"go({token})"',
                )
    return found


def _check_capability_version(packages: Sequence[_Package]) -> list[str]:
    """C4: a go() capability states its version explicitly."""
    found: list[str] = []
    for package in packages:
        for name, value, line in package.fields:
            if RE_PROVIDES.match(name) is None:
                continue
            for item in value.split(','):
                match = RE_GO_CAPABILITY.match(item.strip())
                if match is None:
                    continue
                rest = match.group(2).strip()
                if rest.startswith('=') and rest[1:].strip():
                    continue
                found.append(
                    f'Provides: {match.group(0).strip()} (line {line}) does '
                    f'not state a version; write '
                    f'"go({match.group(1)}) = %{{version}}"',
                )
    return found


def _entry_path(entry: str) -> str | None:
    """Return the path an entry installs, or None when it installs none.

    A directive only modifies the path that follows it, so it is stripped
    together with its parenthesised argument, as in
    ``%attr(0644,root,root) /usr/share/gocode/src/...``. A token that is
    not one of those directives makes an entry name documentation or an
    exclusion rather than an installed library file, so it is skipped.
    """
    text = entry
    while text:
        match = RE_ENTRY_DIRECTIVE.match(text)
        if match is None:
            break
        directive = match.group(1).lower()
        if directive not in _TEXT_DIRECTIVES:
            return None
        text = text[match.end():].lstrip()
        if text.startswith('('):
            close = text.find(')')
            if close < 0:
                return None
            text = text[close + 1:].lstrip()
    return text or None


def _check_files_location(
    packages: Sequence[_Package], macros: dict[str, _Macro],
) -> list[str]:
    """C5: a library installs its files under the Go source tree.

    Only a subpackage that provides a ``go(...)`` capability is judged,
    because that subpackage is the library on its own. The main package of
    a ``golangmodules`` spec ships the same Go sources but also the built
    executable, and a ``golang`` spec ships the executable alone, so the
    page does not govern the ``%files`` block of the main package.
    """
    found: list[str] = []
    for package in packages[1:]:
        if not _go_capabilities(package, macros):
            continue
        for line, entry in package.files:
            path = _entry_path(entry)
            if path is None:
                continue
            if any(
                path.startswith(root) or _expand(path, macros).startswith(root)
                for root in GOPATH_ROOTS
            ):
                continue
            found.append(
                f'%files entry "{path}" (line {line}) installs outside the '
                f'Go source tree; the page requires every file of a Go '
                f'library under /usr/share/gocode/src, which corresponds '
                f'to $GOPATH/src',
            )
    return found


def _check_package_name(
    systems: dict[str, int], packages: Sequence[_Package],
    macros: dict[str, _Macro],
) -> list[str]:
    """C6: the package name is derived from the import path.

    Only a ``golangmodules`` spec is judged. Its main package provides the
    module the repository root names, so the derivation is well defined. A
    ``golang`` spec names an application after the upstream project instead,
    which the page states separately.
    """
    if systems.get(GOLANGMODULES) is None:
        return []
    main = packages[0]
    capabilities = _go_capabilities(main, macros)
    if not capabilities:
        return []

    name = ''
    name_line = 0
    for field, value, line in main.fields:
        if field.lower() == 'name':
            name = _expand(value.strip(), macros)
            name_line = line
            break
    if not name or '%' in name:
        return []

    import_path = ''
    if 'go_import_path' in macros:
        import_path = _expand(macros['go_import_path'].value, macros)
    base = capabilities[0][0]
    if import_path and any(
        path == import_path or path.startswith(import_path + '/') or
        import_path.startswith(path + '/')
        for path, _line, _item in capabilities
    ):
        base = import_path

    candidates = _derived_names(base)
    if candidates is None:
        return []

    actual = _slug(name)
    if _matches_derived(actual, candidates):
        return []
    return [
        f'Name: {name} (line {name_line}) is not derived from the import '
        f'path "{base}"; name the package "{candidates[0][0]}" '
        f'(replace every slash with a hyphen and the host with the '
        f'canonical identifier)',
    ]


def _check_binary_name(
    systems: dict[str, int], packages: Sequence[_Package],
    macros: dict[str, _Macro],
) -> list[str]:
    """C7: a binary package name does not carry the go- prefix."""
    if systems.get(GOLANG) is None:
        return []
    found: list[str] = []
    for package in packages:
        name = ''
        name_line = 0
        for field, value, line in package.fields:
            if field.lower() == 'name':
                name = _expand(value.strip(), macros)
                name_line = line
                break
        if not name:
            match = re.match(r'^%package\s+(?:-n\s+)?(\S+)$', package.header,
                             re.IGNORECASE)
            if match is None:
                continue
            name = _expand(match.group(1), macros)
            name_line = package.line
        if not name.startswith('go-'):
            continue
        if _go_capabilities(package, macros):
            continue
        found.append(
            f'Name: {name} (line {name_line}) carries the "go-" prefix in a '
            f'BuildSystem: {GOLANG} spec; the binary package name follows '
            f'the upstream project, so drop the "go-" prefix',
        )
    return found


def _library_root(import_path: str) -> str:
    """Return the repository root of one import path.

    A Go repository keeps every package of one module under a common root,
    so the segments that name the repository are the root while the ones
    that follow name packages inside it. A hosting site puts the owner
    before the repository, so its root takes three segments, while a vanity
    import path names the module right after the host and takes two. The
    page counts a library, not a package, which is why a repository-level
    spec may list every package it ships without listing several libraries.
    """
    segments = [item for item in import_path.split('/') if item]
    width = 3 if segments and segments[0].lower() in FORGE_HOSTS else 2
    if len(segments) <= width:
        return '/'.join(segments)
    return '/'.join(segments[:width])


def _check_test_include(macros: dict[str, _Macro]) -> list[str]:
    """C9: a test include macro names a single library."""
    found: list[str] = []
    for name, macro in sorted(macros.items()):
        if name not in _TEST_INCLUDE_MACROS:
            continue
        value = _expand(macro.value, macros)
        items = [item for item in value.split() if '/' in item]
        roots = {_library_root(item) for item in items}
        if len(roots) <= 1:
            continue
        found.append(
            f'{name} (line {macro.line}) names {len(roots)} libraries '
            f'({", ".join(sorted(roots))}) in one test include; keep the '
            f'library under test and exclude the libraries whose tests fail',
        )
    return found


def _check_shared_import_path(
    filename: str,
    analysis: _Analysis,
    capabilities: _Capabilities,
) -> list[str]:
    """C10: a spec that shares an import path with another declares it.

    The clause covers two packages that provide the same import path, for
    example the legacy and the latest release of one library. One spec
    cannot show the presence of the other one, so this checkpoint reads the
    index built from every file the run covers. A capability that is spelled
    with a macro is skipped, because only a literal path can be matched
    against a sibling spec.
    """
    found: list[str] = []
    for package in analysis.packages:
        for path, line, _item in _go_capabilities(package, analysis.macros):
            if '%' in path:
                continue
            others = capabilities.provided.get(path, set()) - {filename}
            if not others:
                continue
            if path in capabilities.conflicted.get(filename, set()):
                continue
            siblings = ', '.join(sorted(os.path.basename(other)
                                        for other in others))
            found.append(
                f'Provides: go({path}) (line {line}) shares its import path '
                f'with {siblings}; the page requires the packages that '
                f'share an import path to be mutually exclusive, so declare '
                f'"Conflicts: go({path})"',
            )
    return found


def _capability_index(filenames: Iterable[str]) -> _Capabilities:
    """Return the import paths each file provides and conflicts with."""
    provided: dict[str, set[str]] = {}
    conflicted: dict[str, set[str]] = {}

    for filename in filenames:
        lines, error = _read_lines(filename)
        if lines is None or error is not None:
            continue
        analysis = _analyse(lines)
        if not any(key in analysis.systems for key in GO_SYSTEMS):
            continue
        conflicted[filename] = _conflicts_capabilities(
            analysis.packages, analysis.macros,
        )
        for package in analysis.packages:
            for path, _line, _item in _go_capabilities(
                package, analysis.macros,
            ):
                if '%' in path:
                    continue
                provided.setdefault(path, set()).add(filename)
    return _Capabilities(provided, conflicted)


def _check_spec_programming_golang_ext(
    filename: str,
    *,
    check_toolchain: bool = True,
    check_macros_package: bool = True,
    check_virtual_dependency: bool = True,
    check_capability_version: bool = True,
    check_files_location: bool = True,
    check_package_name: bool = True,
    check_binary_name: bool = True,
    check_test_include: bool = True,
    check_shared_import_path: bool = True,
    capabilities: _Capabilities | None = None,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None
    if not (
        check_toolchain or check_macros_package or check_virtual_dependency or
        check_capability_version or check_files_location or
        check_package_name or check_binary_name or check_test_include or
        check_shared_import_path
    ):
        return []

    analysis = _analyse(lines)
    if not any(key in analysis.systems for key in GO_SYSTEMS):
        return []

    errors: list[str] = []
    if check_toolchain or check_macros_package:
        declared = _declared_names(analysis.packages)
        system, line = _go_system_of(analysis.systems)
        if check_toolchain:
            errors.extend(_check_toolchain(system, line, declared))
        if check_macros_package:
            errors.extend(_check_macros_package(system, line, declared))
    if check_virtual_dependency:
        errors.extend(_check_virtual_dependency(analysis.packages))
    if check_capability_version:
        errors.extend(_check_capability_version(analysis.packages))
    if check_files_location:
        errors.extend(
            _check_files_location(analysis.packages, analysis.macros))
    if check_package_name:
        errors.extend(
            _check_package_name(
                analysis.systems, analysis.packages, analysis.macros))
    if check_binary_name:
        errors.extend(
            _check_binary_name(
                analysis.systems, analysis.packages, analysis.macros))
    if check_test_include:
        errors.extend(_check_test_include(analysis.macros))
    if check_shared_import_path and capabilities is not None:
        errors.extend(
            _check_shared_import_path(filename, analysis, capabilities))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_programming_golang(filename: str) -> list[str]:
    return _check_spec_programming_golang_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the requirements of the Go language guideline.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-toolchain',
        action='store_true',
        help='do not report the missing go toolchain',
    )
    parser.add_argument(
        '--no-check-macros-package',
        action='store_true',
        help='do not report the missing go-rpm-macros package',
    )
    parser.add_argument(
        '--no-check-virtual-dependency',
        action='store_true',
        help='do not report a bare import path in BuildRequires',
    )
    parser.add_argument(
        '--no-check-capability-version',
        action='store_true',
        help='do not report a go() capability without a version',
    )
    parser.add_argument(
        '--no-check-files-location',
        action='store_true',
        help='do not report library files installed outside the Go tree',
    )
    parser.add_argument(
        '--no-check-package-name',
        action='store_true',
        help='do not report a package name not derived from the import path',
    )
    parser.add_argument(
        '--no-check-binary-name',
        action='store_true',
        help='do not report a "go-" prefixed binary package name',
    )
    parser.add_argument(
        '--no-check-test-include',
        action='store_true',
        help='do not report a test include macro with several libraries',
    )
    parser.add_argument(
        '--no-check-shared-import-path',
        action='store_true',
        help='do not report a shared import path without Conflicts',
    )
    args = parser.parse_args(argv)

    # The shared import path checkpoint compares the files of one run, so the
    # index is built once and never on a single file.
    capabilities: _Capabilities | None = None
    if not args.no_check_shared_import_path and len(args.filenames) > 1:
        capabilities = _capability_index(args.filenames)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_programming_golang_ext(
            filename,
            check_toolchain=not args.no_check_toolchain,
            check_macros_package=not args.no_check_macros_package,
            check_virtual_dependency=not args.no_check_virtual_dependency,
            check_capability_version=not args.no_check_capability_version,
            check_files_location=not args.no_check_files_location,
            check_package_name=not args.no_check_package_name,
            check_binary_name=not args.no_check_binary_name,
            check_test_include=not args.no_check_test_include,
            check_shared_import_path=not args.no_check_shared_import_path,
            capabilities=capabilities,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret
