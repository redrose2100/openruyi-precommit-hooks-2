"""Enforce the requirements of the Perl language packaging guideline.

The Perl page of the packaging guidelines states, in Chinese, the rules an
openRuyi packager follows when packaging a CPAN module. The clauses this
rule reproduces are, translated into English:

> A Perl module package is named ``perl-CPANDIST``, where ``CPANDIST`` is
> the name of the CPAN distribution that is packaged. In the rare case that
> one distribution is split into smaller subpackages because of its
> dependencies, the extra subpackages are named ``perl-CPANDIST-Something``.

> For a CPAN based package, the ``URL`` field uses a non-versioned
> ``metacpan.org`` URL.

> A package that uses a declarative Perl build system normally declares
> ``perl-rpm-packaging``, ``perl-rpm-macros`` and ``perl-macros``.

> When a Perl module is needed at build time, write it in the
> ``perl(MODULE)`` form. This also applies to the core modules Perl itself
> ships.

> Write ``Requires`` and ``Provides`` in the ``perl(MODULE)`` form rather
> than depending on a package name.

> Most packages do not need a custom ``%build``, ``%install`` or
> ``%check`` section. Only when the upstream build script needs extra
> arguments is ``BuildOption(...)`` used.

> With a declarative Perl build system, prefer
> ``%files -f %{name}.files``.

> When a Perl module contains ``.h`` files, those files must not be moved
> into a ``-devel`` subpackage merely because they are headers.

Eight checkpoints are implemented, each anchored in one of those clauses:

* C1 reproduces the package naming derivation.
* C2 reproduces the non-versioned metacpan URL clause.
* C3 reproduces the three declarative build dependencies.
* C4 reproduces the ``perl(MODULE)`` build dependency form.
* C5 reproduces the ``perl(MODULE)`` runtime and provide form.
* C6 reproduces the ban on hand-written build stages.
* C7 reproduces the generated file list preference.
* C8 reproduces the ``.h`` file clause.

Everything else the page says is deliberately out of scope, because it is
either a workflow instruction, an editorial preference, or a judgement that
needs the upstream source tree. The rejected candidates are enumerated in
``docs/rules/check-spec-programming-perl.md``.

No network access and no ``rpm`` invocation is performed, so the rule works
on a bare checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Iterable
from collections.abc import Sequence
from typing import NamedTuple
from urllib.parse import unquote


# Any top-level "Field: value" line. A trailing parenthesised argument such
# as the qualifier of "Requires(post):" belongs to the field name rather
# than to the value, so the group is matched and dropped.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)(?:\(([^)]*)\))?\s*:\s*(.*)$')

# A section header, together with everything that follows the section name
# on the same line. For "%files" the remainder is empty; for "%files -f
# %{name}.files" it is "-f %{name}.files".
RE_SECTION = re.compile(r'^%([a-z]\w*)\b(.*)$')

# A macro definition. The body is kept whole, because a value may continue
# on the following lines or hold a "%{shrink: ...}" block.
RE_DEFINE = re.compile(r'^%(?:define|global)\s+(\w+)\s*(.*)$')

# The field that switches the declarative requirements on, and the fields
# this rule reads. All are matched loosely, so a field that a dedicated
# rule reports separately still contributes its value here.
RE_NAME = re.compile(r'^name$', re.IGNORECASE)
RE_URL = re.compile(r'^url$', re.IGNORECASE)
RE_BUILD_SYSTEM = re.compile(r'^build-?system$', re.IGNORECASE)
RE_BUILD_REQUIRES = re.compile(r'^build-?requires?$', re.IGNORECASE)
RE_REQUIRES = re.compile(r'^requires?$', re.IGNORECASE)
RE_PROVIDES = re.compile(r'^provides$', re.IGNORECASE)
RE_SOURCE = re.compile(r'^source\d*$', re.IGNORECASE)

# The dependency operators. A token that is exactly an operator consumes the
# token after it, which is the version of the dependency to its left.
RE_OPERATOR = re.compile(r'^(?:<=|>=|=|<|>)$')

# The two keywords that join two dependency names into one clause.
_JOINERS = frozenset({'with', 'without'})

# The closed set of real RPM sections, mirroring check-spec-basic-fields.
# Anything else that starts with "%" is a macro invocation (%license, %doc,
# %perl_gen_filelist, %autochangelog, ...) and must never be mistaken for a
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

# The two declarative build systems this rule covers. The names are spelled
# exactly as the page spells them.
PERLBUILD = 'perlbuild'
PERLMAKER = 'perlmaker'
PERL_SYSTEMS: frozenset[str] = frozenset({PERLBUILD, PERLMAKER})

# The three macro packages the page asks a declarative Perl package for.
# Their order is the order of the page.
SHARED_PACKAGES: tuple[str, ...] = (
    'perl-rpm-packaging',
    'perl-rpm-macros',
    'perl-macros',
)

# The plain package names that legitimately appear as a Perl dependency
# instead of a "perl(MODULE)" capability. The page names the macro packages
# itself, and a package that links to libperl.so needs perl-devel. The core
# Perl packages carry no module capability of their own, so they are listed
# as well.
TOOLCHAIN_PACKAGES: frozenset[str] = frozenset({
    'perl-rpm-packaging',
    'perl-rpm-macros',
    'perl-macros',
    'perl-devel',
    'perl-libs',
    'perl-doc',
})

# The prefix every Perl module package name carries.
PERL_PREFIX = 'perl-'

# The metacpan path that names a CPAN distribution, either as the canonical
# "/dist/" form or as the older "/release/" form. The capture is the
# distribution name as it is spelled in the URL.
RE_METACPAN_DIST = re.compile(
    r'metacpan\.org/(?:dist|release)/([^/?#\s]+)', re.IGNORECASE,
)

# A source entry that fetches a tarball from CPAN. That is the only reliable
# signal a spec-only linter has for "this package is based on CPAN".
RE_CPAN_SOURCE = re.compile(
    r'(?:cpan\.metacpan\.org|www\.cpan\.org)'
    r'/authors/id/', re.IGNORECASE,
)

# A version number inside a metacpan path. The page asks for a non-versioned
# URL, so a distribution directory that carries one is a finding.
RE_VERSION_IN_PATH = re.compile(r'\d+\.\d+')

# The generated file list the declarative build systems write during the
# installation stage.
RE_GENERATED_FILELIST = re.compile(r'%\{name\}\.files', re.IGNORECASE)

# The build stages a declarative Perl package does not hand-write.
DECLARATIVE_STAGES: tuple[str, ...] = ('%build', '%install', '%check')

# How many passes a macro expansion may take. A macro value may name another
# macro of the same package, so a handful of passes is enough for every
# spelling the corpus uses.
_EXPANSIONS = 10


class _Macro(NamedTuple):
    """One macro definition: its whole value and the line it starts on."""

    value: str
    line: int


class _Package(NamedTuple):
    """One package: its header, the fields and the %files entries.

    The first package is the main package. Its ``header`` is the empty
    string and its ``line`` is zero, because no line opens it.
    """

    header: str
    line: int
    fields: list[tuple[str, str, str, int]]
    files: list[tuple[int, str]]


class _Analysis(NamedTuple):
    """Everything the checkpoints read out of one spec."""

    macros: dict[str, _Macro]
    packages: list[_Package]
    systems: dict[str, int]
    sections: list[tuple[str, str, int]]


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

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in macros or name in pending:
            return match.group(0)
        return _expand_text(
            macros[name].value, macros, depth + 1, pending | {name},
        )

    current = re.sub(r'%\{(\w+)\}', replace, text)
    return re.sub(r'%(\w+)', replace, current)


def _packages_of(lines: Sequence[str]) -> tuple[
    list[_Package],
    list[tuple[str, str, int]],
]:
    """Split the file into packages, and record every section header.

    Every ``%package`` header opens a fresh package, so a subpackage is
    judged against its own declarations. A ``%files`` section belongs to the
    package its name selects: a bare ``%files`` belongs to the main package
    even when a subpackage header precedes it, and ``%files -n <name>``
    belongs to that subpackage. A macro definition block is skipped whole,
    so the fields it holds are never read as spec fields.

    The packages are returned in the order the file declares them, so the
    main package is always the first one. The section list holds
    ``(section name, suffix, 1-based line)`` for every section header, which
    is what C6 reads.
    """
    packages = [_Package('', 0, [], [])]
    current = packages[0]
    owner = packages[0]
    macro_depth = 0
    section = ''
    sections: list[tuple[str, str, int]] = []

    for index, line in enumerate(lines, 1):
        if macro_depth > 0:
            macro_depth = _macro_depth_after(line, macro_depth)
            continue
        header = _section_of(line)
        if header is not None:
            section = header[0]
            sections.append((header[0], header[1], index))
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
        current.fields.append(
            (match.group(1), match.group(2) or '', match.group(3), index),
        )
        macro_depth = _macro_depth_after(line, 0)

    return packages, sections


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
        if _declared_package_name(package.header) == name:
            return package
    return packages[-1]


def _declared_package_name(header: str) -> str:
    """Return the name a ``%package`` header declares, or the empty string."""
    match = re.match(
        r'^%package\s+(?:-n\s+)?(\S+)\s*$', header, re.IGNORECASE,
    )
    if match is None:
        return ''
    return match.group(1)


def _systems_of(packages: Sequence[_Package]) -> dict[str, int]:
    """Return the first line of every declarative Perl build system."""
    found: dict[str, int] = {}
    for package in packages:
        for name, _stage, value, line in package.fields:
            if RE_BUILD_SYSTEM.match(name) is None:
                continue
            for token in value.split():
                found.setdefault(token.strip().lower(), line)
    return found


def _analyse(lines: Sequence[str]) -> _Analysis:
    macros = _definitions(lines)
    packages, sections = _packages_of(lines)
    return _Analysis(macros, packages, _systems_of(packages), sections)


def _single_field(
    package: _Package, pattern: re.Pattern[str],
) -> tuple[str, int] | None:
    """Return ``(value, line)`` of the first field the pattern selects."""
    for name, _stage, value, line in package.fields:
        if pattern.match(name) is not None:
            return value.strip(), line
    return None


def _dependency_names(value: str) -> set[str]:
    """Return the name of every dependency on one field line.

    A dependency is a name optionally followed by a version operator and a
    version, or one rich dependency in parentheses, or two names joined by
    a comma, ``with`` or ``without``. Only the names are returned, so a
    version number never looks like a dependency and ``perl-rpm-macros``
    stays distinct from ``perl``. The spelling of the spec is kept, because
    a finding quotes the name back to the packager.
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
        names.add(token)
    return names


def _build_dependencies(packages: Sequence[_Package]) -> set[str]:
    """Return every plain dependency name declared in BuildRequires.

    ``BuildRequires`` is a source-package level field, so RPM merges the
    declarations of every package block into one build dependency set.
    The names are lowercased so the comparison ignores case.
    """
    declared: set[str] = set()
    for package in packages:
        for name, _stage, value, _line in package.fields:
            if RE_BUILD_REQUIRES.match(name) is not None:
                declared |= {
                    item.lower()
                    for item in _dependency_names(value)
                }
    return declared


def _bare_perl_dependencies(value: str) -> list[str]:
    """Return the plain ``perl-*`` package names on one dependency line."""
    items = [
        name for name in _dependency_names(value)
        if name.lower().startswith(PERL_PREFIX) and
        name.lower() not in TOOLCHAIN_PACKAGES
    ]
    return sorted(items, key=str.lower)


def _module_spelling(package: str) -> str:
    """Return the ``perl(MODULE)`` spelling of one plain package name."""
    module = package[len(PERL_PREFIX):].replace('-', '::')
    return f'perl({module})'


def _metacpan_dist(url: str) -> str:
    """Return the CPAN distribution a metacpan URL names, or ''."""
    match = RE_METACPAN_DIST.search(url)
    if match is None:
        return ''
    return unquote(match.group(1))


def _strip_version_suffix(dist: str) -> str:
    """Return a metacpan path segment with its trailing version removed.

    The older ``/release/DIST-VERSION`` path carries the version inside the
    segment, while ``/dist/DIST`` does not. A trailing ``-1.23`` or
    ``-1.23_45`` is therefore removed before the distribution name is
    compared, so C1 does not report a name that C2 already reports as a
    versioned URL.
    """
    return re.sub(r'-\d+\.\d+(?:_\d+)?$', '', dist)


def _normalise_name(text: str) -> str:
    """Return the comparison spelling of one distribution or package name.

    CPAN distribution names are spelled with ``-`` while the URL may encode
    a ``+`` and the canonical form uses ``-`` as well, so both characters
    are folded together. The comparison is case insensitive because a
    distribution name and its RPM package name may differ in case only.
    """
    return re.sub(r'[+_]', '-', text).lower()


def _is_cpan_source(
    packages: Sequence[_Package],
    macros: dict[str, _Macro],
) -> bool:
    """Return whether any source entry fetches a tarball from CPAN."""
    for package in packages:
        for name, _stage, value, _line in package.fields:
            if RE_SOURCE.match(name) is None:
                continue
            if RE_CPAN_SOURCE.search(_expand(value, macros)) is not None:
                return True
    return False


def _is_perl_package(
    packages: Sequence[_Package],
    macros: dict[str, _Macro],
) -> bool:
    """Return whether this spec packages a Perl module.

    A spec qualifies when it declares a declarative Perl build system, or
    when its package name starts with ``perl-``. The second condition keeps
    a spec that was written without the build system in scope, which is
    exactly the shape the automation section of the page warns about.
    """
    name = _primary_name(packages, macros)
    return name.startswith(PERL_PREFIX)


def _primary_name(
    packages: Sequence[_Package],
    macros: dict[str, _Macro],
) -> str:
    """Return the macro-expanded name of the main package, or ''."""
    found = _single_field(packages[0], RE_NAME)
    if found is None:
        return ''
    return _expand(found[0], macros)


def _check_package_name(
    analysis: _Analysis,
) -> list[str]:
    """C1: the package name is derived from the CPAN distribution.

    Only a spec whose ``URL`` names a metacpan distribution is judged,
    because that URL is the only place a spec-only linter can read the
    CPAN distribution name from. A spec that installs a CPAN tarball from
    a project site instead is out of scope, which is why ``po4a`` is left
    alone even though it declares ``perlbuild``.
    """
    found: list[str] = []
    dist = ''
    dist_line = 0
    url = _single_field(analysis.packages[0], RE_URL)
    if url is not None:
        value = _expand(url[0], analysis.macros)
        dist = _metacpan_dist(value)
        dist_line = url[1]
    if not dist:
        return found

    expected = PERL_PREFIX + _strip_version_suffix(dist)
    name_field = _single_field(analysis.packages[0], RE_NAME)
    name = _primary_name(analysis.packages, analysis.macros)
    if name_field is not None and name and '%' not in name:
        if _normalise_name(name) != _normalise_name(expected):
            found.append(
                f'Name: {name} (line {name_field[1]}) does not follow the '
                f'package naming rule; the URL (line {dist_line}) names the '
                f'CPAN distribution "{dist}", so name the package '
                f'"{expected}"',
            )

    for package in analysis.packages[1:]:
        declared = _declared_package_name(package.header)
        if not declared:
            continue
        actual = _expand(declared, analysis.macros)
        if '%' in actual:
            continue
        normal = _normalise_name(actual)
        base = _normalise_name(expected)
        if normal == base or normal.startswith(base + '-'):
            continue
        found.append(
            f'%package {declared} (line {package.line}) does not follow '
            f'the package naming rule; a subpackage of the CPAN '
            f'distribution "{dist}" is named "{expected}-Something"',
        )
    return found


def _check_url(analysis: _Analysis) -> list[str]:
    """C2: a CPAN package uses a non-versioned metacpan URL.

    The page scopes the clause to CPAN based packages, so only a spec whose
    source entry fetches a tarball from CPAN is judged. That leaves a Perl
    project that merely builds with ``perlbuild``, such as ``po4a``, alone.
    """
    found: list[str] = []
    if not _is_cpan_source(analysis.packages, analysis.macros):
        return found
    url = _single_field(analysis.packages[0], RE_URL)
    if url is None:
        return found
    value = _expand(url[0], analysis.macros)
    if not value or '%' in value:
        return found
    if 'metacpan.org' not in value.lower():
        found.append(
            f'URL: {url[0]} (line {url[1]}) is not a metacpan URL; the page '
            f'asks a CPAN based package for its non-versioned metacpan.org '
            f'address',
        )
        return found
    dist = _metacpan_dist(value)
    if dist and RE_VERSION_IN_PATH.search(dist) is not None:
        found.append(
            f'URL: {url[0]} (line {url[1]}) pins the distribution version; '
            f'the page asks for a non-versioned metacpan URL',
        )
    return found


def _check_shared_packages(
    systems: dict[str, int], declared: set[str],
) -> list[str]:
    """C3: a declarative Perl package declares the three macro packages."""
    missing = [pkg for pkg in SHARED_PACKAGES if pkg not in declared]
    if not missing:
        return []
    system, line = next(iter(systems.items()))
    return [
        f'BuildSystem: {system} (line {line}) requires the shared Perl '
        f'build dependencies in BuildRequires; '
        f'missing {", ".join(missing)}',
    ]


def _check_build_module_form(packages: Sequence[_Package]) -> list[str]:
    """C4: a build dependency on a Perl module uses perl(MODULE).

    A plain ``perl-Something`` name is the package name of a module, and the
    page asks for the capability instead, because the package name may be
    renamed while the capability stays stable. The macro packages the page
    names, the ``perl-devel`` package and the core Perl packages carry no
    such capability, so they are exempt.
    """
    found: list[str] = []
    for package in packages:
        for name, _stage, value, line in package.fields:
            if RE_BUILD_REQUIRES.match(name) is None:
                continue
            for item in _bare_perl_dependencies(value):
                found.append(
                    f'BuildRequires (line {line}) names the package '
                    f'"{item}"; the page asks for the module capability '
                    f'"{_module_spelling(item)}"',
                )
    return found


def _check_runtime_capability(packages: Sequence[_Package]) -> list[str]:
    """C5: Requires and Provides use the perl(MODULE) form.

    The page words this as "should" and explains why: the package that
    provides the module satisfies the capability, while a rename of the
    package would break a plain name dependency. The same exemptions as C4
    apply, so a ``Requires: perl-devel`` is left alone.
    """
    found: list[str] = []
    for package in packages:
        for name, _stage, value, line in package.fields:
            if (
                RE_REQUIRES.match(name) is None and
                RE_PROVIDES.match(name) is None
            ):
                continue
            for item in _bare_perl_dependencies(value):
                found.append(
                    f'{name} (line {line}) names the package "{item}"; the '
                    f'page asks Requires and Provides to use the module '
                    f'capability "{_module_spelling(item)}"',
                )
    return found


def _check_declarative_stages(
    systems: dict[str, int], sections: Sequence[tuple[str, str, int]],
) -> list[str]:
    """C6: a declarative Perl package does not hand-write its stages.

    The page states that most packages need no custom ``%build``,
    ``%install`` or ``%check`` section and that extra upstream arguments
    belong in ``BuildOption(...)``. A section with an empty body is
    reported as well, because an empty stage still shows that the packager
    overrode the declarative behaviour.
    """
    system, system_line = next(iter(systems.items()))
    found: list[str] = []
    for name, _suffix, line in sections:
        if name not in DECLARATIVE_STAGES:
            continue
        found.append(
            f'{name} (line {line}) is a hand-written stage in a '
            f'BuildSystem: {system} (line {system_line}) spec; the page '
            f'states these stages are normally not needed, and extra '
            f'upstream arguments belong in BuildOption(...)',
        )
    return found


def _check_generated_filelist(
    systems: dict[str, int], sections: Sequence[tuple[str, str, int]],
) -> list[str]:
    """C7: the main file list reads a generated file list.

    Only the main package is judged. ``%perl_gen_filelist`` writes a single
    ``%{name}.files`` for the source package, so a subpackage list is
    written by hand on purpose. A spec with no ``%files`` section at all is
    out of scope, because its absence is reported by
    ``check-spec-basic-fields``. A ``-f`` option is accepted in any spelling,
    because the page states the preference rather than the file name.
    """
    main = next(
        (
            item for item in sections
            if item[0] == '%files' and not re.search(r'-n\s+\S', item[1])
        ),
        None,
    )
    if main is None:
        return []
    if re.search(r'(?:^|\s)-f\s*\S', main[1]) is not None:
        return []
    system, system_line = next(iter(systems.items()))
    return [
        f'%files (line {main[2]}) does not read a generated file list; a '
        f'BuildSystem: {system} (line {system_line}) package is expected to '
        f'use %files -f %{{name}}.files',
    ]


def _check_devel_headers(analysis: _Analysis) -> list[str]:
    """C8: header files of a module stay in the module package.

    The page states that a ``.h`` file of a Perl module is not moved into a
    ``-devel`` subpackage merely because it is a header. Only a subpackage
    whose name ends in ``-devel`` is judged, because that is the pattern the
    page names.
    """
    found: list[str] = []
    for package in analysis.packages[1:]:
        declared = _declared_package_name(package.header)
        if not declared:
            continue
        if not _expand(declared, analysis.macros).lower().endswith('-devel'):
            continue
        for line, entry in package.files:
            tokens = entry.split()
            if not tokens:
                continue
            path = tokens[-1].lower()
            if not (path.endswith('.h') or '%{_includedir}' in path):
                continue
            found.append(
                f'%files -n {declared} entry "{tokens[-1]}" (line {line}) '
                f'is a header file in a -devel subpackage; the page states a '
                f'.h file of a Perl module is not moved into a -devel '
                f'subpackage merely because it is a header',
            )
    return found


def _check_spec_programming_perl_ext(
    filename: str,
    *,
    check_package_name: bool = True,
    check_url: bool = True,
    check_shared_packages: bool = True,
    check_build_module_form: bool = True,
    check_runtime_capability: bool = True,
    check_declarative_stages: bool = True,
    check_generated_filelist: bool = True,
    check_devel_headers: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None
    if not (
        check_package_name or check_url or check_shared_packages or
        check_build_module_form or check_runtime_capability or
        check_declarative_stages or check_generated_filelist or
        check_devel_headers
    ):
        return []

    analysis = _analyse(lines)
    declarative = {
        system: line for system, line in analysis.systems.items()
        if system in PERL_SYSTEMS
    }
    if not declarative and not _is_perl_package(
        analysis.packages, analysis.macros,
    ):
        return []

    errors: list[str] = []
    if check_package_name:
        errors.extend(_check_package_name(analysis))
    if check_url:
        errors.extend(_check_url(analysis))
    if declarative:
        declared = _build_dependencies(analysis.packages)
        if check_shared_packages:
            errors.extend(_check_shared_packages(declarative, declared))
        if check_declarative_stages:
            errors.extend(
                _check_declarative_stages(declarative, analysis.sections),
            )
        if check_generated_filelist:
            errors.extend(
                _check_generated_filelist(declarative, analysis.sections),
            )
    if check_devel_headers:
        errors.extend(_check_devel_headers(analysis))
    if check_build_module_form:
        errors.extend(_check_build_module_form(analysis.packages))
    if check_runtime_capability:
        errors.extend(_check_runtime_capability(analysis.packages))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_programming_perl(filename: str) -> list[str]:
    return _check_spec_programming_perl_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the requirements of the Perl language guideline.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-package-name',
        action='store_true',
        help='do not report a package name not derived from the CPAN '
             'distribution',
    )
    parser.add_argument(
        '--no-check-url',
        action='store_true',
        help='do not report a non-metacpan or versioned metacpan URL',
    )
    parser.add_argument(
        '--no-check-shared-packages',
        action='store_true',
        help='do not report the missing shared Perl macro packages',
    )
    parser.add_argument(
        '--no-check-build-module-form',
        action='store_true',
        help='do not report a plain perl-* name in BuildRequires',
    )
    parser.add_argument(
        '--no-check-runtime-capability',
        action='store_true',
        help='do not report a plain perl-* name in Requires or Provides',
    )
    parser.add_argument(
        '--no-check-declarative-stages',
        action='store_true',
        help='do not report a hand-written build stage',
    )
    parser.add_argument(
        '--no-check-generated-filelist',
        action='store_true',
        help='do not report a %%files section without -f %%{name}.files',
    )
    parser.add_argument(
        '--no-check-devel-headers',
        action='store_true',
        help='do not report a header file moved into a -devel subpackage',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_programming_perl_ext(
            filename,
            check_package_name=not args.no_check_package_name,
            check_url=not args.no_check_url,
            check_shared_packages=not args.no_check_shared_packages,
            check_build_module_form=not args.no_check_build_module_form,
            check_runtime_capability=not args.no_check_runtime_capability,
            check_declarative_stages=not args.no_check_declarative_stages,
            check_generated_filelist=not args.no_check_generated_filelist,
            check_devel_headers=not args.no_check_devel_headers,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret
