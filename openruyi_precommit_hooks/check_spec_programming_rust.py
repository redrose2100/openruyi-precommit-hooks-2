"""Enforce the requirements of the Rust packaging guideline.

The Rust page of the openRuyi packaging guidelines describes the three
kinds of package the Rust ecosystem produces and the naming, dependency
and layout rules each of them follows.

Section "Naming" states, verbatim:

> Rust crate provider packages must use the `rust-` prefix.

> A crate provider package name usually comes from the crate compatibility
> name. For example:
>
>     %global crate_name serde
>     %global full_version 1.0.228
>     %global pkgname serde-1
>     Name:           rust-serde-1
>     Version:        1.0.228

> RPM package names and `crate(...)` capabilities usually normalize
> underscores in crate names to hyphens.

> Keep the crate provider directory name, spec file name, and `Name`
> consistent. For example:
>
>     SPECS/rust-serde-1/rust-serde-1.spec

Section "Compatibility Names" states, verbatim:

> Rust crate providers use compatibility names so that different
> incompatible versions can coexist in the repository.
>
> Use the following rules in most cases:
>
> - Group versions `1.x.y` and later by major version.
> - Group versions `0.y.z` where `y > 0` by minor version.
> - Group versions `0.0.z` by the full patch version.
>
> For example:
>
>     serde 1.0.228       -> serde-1
>     tokenizers 0.22.2   -> tokenizers-0.22
>     foo 0.0.7           -> foo-0.0.7

> Do not introduce unnecessarily fine-grained compatibility names, such as
> `serde-1.0.15`, unless the crate has a clear compatibility issue.

Section "Dependencies" states, verbatim:

> Declare Rust crate dependencies through `crate(...)` capabilities. For
> example:
>
>     BuildRequires:  crate(serde-1/default) >= 1.0.0
>     BuildRequires:  crate(clap-4/derive) >= 4.5.0

> Do not use ordinary RPM package names instead of `crate(...)`
> capabilities to declare Rust crate dependencies.

> `crate(...)` capabilities are the main interface for dependency
> resolution between Rust ecosystem packages.

Section "Rust Crate Provider Packages" states, verbatim:

> Rust crate provider packages install crate source code into the system
> and provide `crate(...)` capabilities for other Rust packages.

Section "Cargo.toml in the Provider Directory" states, verbatim:

> When TakoPack generates a crate provider package, it keeps a
> `Cargo.toml` file in the provider directory. For example:
>
>     SPECS/rust-serde-1/Cargo.toml
>     SPECS/rust-serde-1/rust-serde-1.spec

Section "Python/Rust Extension Packages" states, verbatim:

> Declare both Python and Rust build dependencies. For example:
>
>     BuildRequires:  rust
>     BuildRequires:  rust-rpm-macros
>     BuildRequires:  python3dist(maturin)
>     BuildRequires:  crate(pyo3-0.27/default) >= 0.27.0

Ten checkpoints are implemented, and each one is anchored in one of those
clauses:

* C1 reproduces the ``rust-`` prefix a crate provider must carry.
* C2 reproduces the requirement that the directory name, the spec file
  name and the ``Name`` field agree.
* C3 reproduces the ``pkgname`` compatibility name the page ties to the
  package name, the directory name and the ``crate(...)`` capabilities.
* C4 reproduces the three grouping rules of the compatibility name.
* C5 reproduces the clause that forbids an unnecessarily fine-grained
  compatibility name.
* C6 reproduces the clause that forbids naming a crate provider package
  instead of a ``crate(...)`` capability.
* C7 reproduces the version constraint the page shows on every
  ``crate(...)`` dependency it writes.
* C8 reproduces the pair of build dependencies the page asks a Python
  package with a Rust extension to declare.
* C9 reproduces the capability a crate provider is described as
  providing.
* C10 reproduces the ``Cargo.toml`` the page says the provider directory
  keeps.

A spec is in scope for the provider checkpoints when it declares
``BuildSystem: rustcrates``, which is the declarative build system the
page assigns to a crate provider and the only signal a spec-only linter
can read to tell a provider from a package that merely builds with Cargo.
C6 and C7 are judged on the wider population of Rust ecosystem packages,
because the dependency clause is written for every package that consumes
crates, not only for a provider. That population is decided by three
signals the spec text carries: a ``rust`` or ``rustcrates`` build system,
a ``crate(...)`` dependency, or a ``rust``/``rust-rpm-macros`` build
dependency.

Deliberately out of scope: the ``%build``, ``%install`` and ``%check``
stages and the ``rust-rpm-macros`` dependency of ``rustcrates`` (owned by
``check-spec-build-rust``), the legal values of ``BuildSystem`` (owned by
``check-spec-buildsystem``), the source URL, ``#!RemoteAsset`` and
checksum consistency (owned by ``check-spec-source``), the runtime
dependency form of the ordinary fields (owned by ``check-spec-requires``
and ``check-spec-buildrequires``), the underscore normalisation of a crate
name (the page words it with "usually", and a provider that spells the
crate name and the package name with the same separator is complete
either way, so the two spellings are both accepted here), whether the
upstream source really publishes to crates.io (a spec-only linter cannot
inspect the index), and the patch/regeneration workflow the page
describes for a dependency range that crosses a compatibility key (the
spec text does not record which dependency came from the generated
metadata and which was hand-edited).

No network access and no ``rpm`` invocation is performed, so the rule
works on a bare checkout. C2 and C10 are the only checkpoints that read
the filesystem rather than the spec text, and both of them read nothing
but the directory the spec lives in.
"""
from __future__ import annotations

import argparse
import os
import re
from collections.abc import Iterable
from collections.abc import Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. A trailing parenthesised argument such
# as the stage of "BuildOption(install):" belongs to the field name rather
# than to the value, so the group is matched and dropped.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)(?:\(([^)]*)\))?\s*:\s*(.*)$')

# A section header, together with everything that follows the section name
# on the same line.
RE_SECTION = re.compile(r'^%([a-z]\w*)\b(.*)$')

# A macro definition at the top of the spec.
RE_DEFINE = re.compile(r'^%(?:define|global)\s+(\w+)\s+(.*)$')

# The fields the checkpoints read.
RE_NAME = re.compile(r'^name$', re.IGNORECASE)
RE_VERSION = re.compile(r'^version$', re.IGNORECASE)
RE_BUILD_SYSTEM = re.compile(r'^build-?system$', re.IGNORECASE)
RE_BUILD_REQUIRES = re.compile(r'^build-?requires?$', re.IGNORECASE)
RE_REQUIRES = re.compile(r'^requires?$', re.IGNORECASE)
RE_PROVIDES = re.compile(r'^provides?$', re.IGNORECASE)

# The closed set of real RPM sections, mirroring check-spec-basic-fields.
# Anything else that starts with "%" is a macro invocation (%license, %doc,
# %autochangelog, ...) and must never be mistaken for a section.
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

# The build systems this rule covers, spelled as the page spells them.
RUSTCRATES = 'rustcrates'
RUST = 'rust'
PYPROJECT = 'pyproject'

# The prefix a crate provider package name carries.
RUST_PREFIX = 'rust-'

# The macros the page defines for a crate provider.
CRATE_NAME = 'crate_name'
FULL_VERSION = 'full_version'
PKGNAME = 'pkgname'

# The build dependencies a Python package with a Rust extension declares.
TOOLCHAIN = 'rust'
MACROS = 'rust-rpm-macros'

# The name of the metadata file a provider directory keeps.
CARGO_TOML = 'Cargo.toml'

# The capability a crate provider advertises.
CRATE_CAPABILITY = 'crate('

# The dependency operators. A token that is exactly an operator consumes the
# token after it, which is the version of the dependency to its left.
RE_OPERATOR = re.compile(r'^(?:<=|>=|=|<|>)$')

# The two keywords that join two dependency names into one clause.
_JOINERS = frozenset({'with', 'without'})

# An ordinary RPM package name that names a crate provider, that is the
# rust- prefix followed by a crate compatibility name. A name without a
# trailing numeric group is a tool or a macro package rather than a
# provider, so "rust", "rust-src", "rust-rpm-macros" and "rust-gdb" never
# match.
RE_PROVIDER_PACKAGE = re.compile(
    r'^rust-[a-z0-9][a-z0-9_.+-]*-[0-9]+(?:\.[0-9]+)*$',
)

# The tool and macro packages whose names start with the rust- prefix and
# therefore look like a provider to a naive pattern.
TOOL_PACKAGES: frozenset[str] = frozenset({
    'rust',
    'rust-bin',
    'rust-cargo',
    'rust-doc',
    'rust-gdb',
    'rust-lldb',
    'rust-rpm-macros',
    'rust-src',
    'rust-std-static',
    'rust-toolset',
    'rustfmt',
    'cargo',
    'cargo-c',
})

# How many passes a macro expansion may take.
_EXPANSIONS = 10


class _Macro(NamedTuple):
    """One macro definition: its whole value and the line it starts on."""

    value: str
    line: int


class _Block(NamedTuple):
    """One field block: the fields it holds, in file order.

    ``fields`` is a list of ``(spelling, stage, value, 1-based line)``
    tuples, where ``stage`` is the parenthesised argument of a field name or
    the empty string when the name carries none.
    """

    fields: list[tuple[str, str, str, int]]


class _Analysis(NamedTuple):
    """Everything the checkpoints read out of one spec."""

    macros: dict[str, _Macro]
    blocks: list[_Block]
    text: str


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


def _section_of(line: str) -> str | None:
    """Return the known section name on this line, or None."""
    match = RE_SECTION.match(line)
    if match is None:
        return None
    name = '%' + match.group(1)
    if name not in KNOWN_SECTIONS:
        return None
    return name


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
    """Expand the macro spellings of one text as far as the table allows."""
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


def _blocks_of(lines: Sequence[str]) -> list[_Block]:
    """Split the file into field blocks.

    The first block is the main preamble, kept even when it holds no field.
    Every ``%package`` opens a fresh block, so a subpackage is judged
    against its own declarations. A block ends at the first known section,
    so a macro invocation such as ``%global debug_package %{nil}`` neither
    ends a block nor hides the fields that follow it.
    """
    raw: list[list[tuple[str, str, str, int]]] = []
    fields: list[tuple[str, str, str, int]] = []
    macro_depth = 0

    for index, line in enumerate(lines, 1):
        if macro_depth > 0:
            macro_depth = _macro_depth_after(line, macro_depth)
            continue
        if _section_of(line) is not None:
            raw.append(fields)
            fields = []
            continue
        if line.startswith('#'):
            continue
        match = RE_FIELD.match(line)
        if match is None:
            continue
        name, stage, value = (
            match.group(1), match.group(2) or '', match.group(3),
        )
        fields.append((name, stage.strip(), value, index))
        macro_depth = _macro_depth_after(line, 0)

    raw.append(fields)
    blocks = [_Block(raw[0])]
    blocks.extend(_Block(item) for item in raw[1:] if item)
    return blocks


def _analyse(lines: Sequence[str]) -> _Analysis:
    """Read the macros, the field blocks and the text of a spec.

    The text keeps every line except a full-line comment, because a
    checkpoint looks for a field or a capability that a comment never
    declares.
    """
    macros = _definitions(lines)
    text = '\n'.join(
        line for line in lines if not line.lstrip().startswith('#')
    )
    return _Analysis(macros, _blocks_of(lines), text)


def _fields_matching(
    analysis: _Analysis, pattern: re.Pattern[str],
) -> list[tuple[str, int]]:
    """Return ``(value, line)`` of every field the pattern selects."""
    found: list[tuple[str, int]] = []
    for block in analysis.blocks:
        for name, _stage, value, line in block.fields:
            if pattern.match(name) is not None:
                found.append((value.strip(), line))
    return found


def _systems(analysis: _Analysis) -> dict[str, int]:
    """Return the first line of every declared build system."""
    found: dict[str, int] = {}
    for block in analysis.blocks:
        for name, _stage, value, line in block.fields:
            if RE_BUILD_SYSTEM.match(name) is None:
                continue
            for token in value.split():
                found.setdefault(token.strip().lower(), line)
    return found


def _entries(value: str) -> list[str]:
    """Return the comma separated dependency entries of one field line.

    A comma inside parentheses belongs to a rich dependency rather than to
    an entry separator, so it never splits an entry.
    """
    entries: list[str] = []
    buffer = ''
    depth = 0
    for char in value:
        if char == '(':
            depth += 1
        elif char == ')':
            depth = max(depth - 1, 0)
        if char == ',' and depth == 0:
            if buffer.strip():
                entries.append(buffer.strip())
            buffer = ''
            continue
        buffer += char
    if buffer.strip():
        entries.append(buffer.strip())
    return entries


def _entry_name(entry: str) -> str:
    """Return the dependency name of one entry, or the empty string."""
    tokens = [
        token for token in entry.split()
        if not RE_OPERATOR.match(token)
    ]
    if not tokens:
        return ''
    token = tokens[0]
    if token.startswith(CRATE_CAPABILITY):
        # A capability keeps its closing parenthesis and may carry a
        # feature subpath after a slash, so both forms are named alike.
        return token.split(')')[0] + ')'
    return token.lower()


def _entry_version(entry: str) -> str:
    """Return the version constraint of one entry, or the empty string."""
    tokens = entry.split()
    for index, token in enumerate(tokens):
        if RE_OPERATOR.match(token) is not None and index + 1 < len(tokens):
            return f'{token} {tokens[index + 1]}'
    return ''


def _declared(analysis: _Analysis, pattern: re.Pattern[str]) -> set[str]:
    """Return the lowercase name of every dependency of a field."""
    names: set[str] = set()
    for value, _line in _fields_matching(analysis, pattern):
        for entry in _entries(_expand(value, analysis.macros)):
            name = _entry_name(entry)
            if name:
                names.add(name)
    return names


def _primary_name(analysis: _Analysis) -> tuple[str, int] | None:
    """Return ``(expanded name, line)`` of the main package, or None."""
    found = next(iter(_fields_matching(analysis, RE_NAME)), None)
    if found is None:
        return None
    return _expand(found[0], analysis.macros), found[1]


def _macro_value(analysis: _Analysis, name: str) -> tuple[str, int] | None:
    """Return ``(expanded value, line)`` of one macro, or None."""
    macro = analysis.macros.get(name)
    if macro is None:
        return None
    value = _expand(macro.value.strip().strip('\'"'), analysis.macros)
    if not value or '%' in value:
        return None
    return value, macro.line


def _is_rust_ecosystem(analysis: _Analysis, systems: dict[str, int]) -> bool:
    """Return whether the spec takes part in the Rust ecosystem.

    A provider and an application declare it through the build system. A
    package in another language does not, but it still consumes crates when
    it names one through a capability or through the toolchain dependency.
    """
    if RUST in systems or RUSTCRATES in systems:
        return True
    requires = _declared(analysis, RE_BUILD_REQUIRES)
    if TOOLCHAIN in requires or MACROS in requires:
        return True
    return any(
        name.startswith(CRATE_CAPABILITY)
        for name in _declared(analysis, RE_BUILD_REQUIRES) |
        _declared(analysis, RE_REQUIRES)
    )


def _compat_key(version: str) -> str | None:
    """Return the compatibility key the page asks for, or None.

    The core version is the part before a build metadata suffix. A
    prerelease version carries a dash in its core, and the page never
    states how to group one, so it is left alone rather than guessed at.
    """
    core = version.split('+')[0].strip()
    if not core or '-' in core:
        return None
    parts = core.split('.')
    if not parts or not parts[0].isdigit():
        return None
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    if major != 0:
        return str(major)
    if minor != 0:
        return f'0.{minor}'
    return f'0.0.{patch}'


def _compat_suffix(pkgname: str, crate: str) -> str:
    """Return the part of a compatibility name that follows the crate name."""
    for spelling in (crate, crate.replace('_', '-')):
        if pkgname.startswith(spelling + '-'):
            return pkgname[len(spelling) + 1:]
    return ''


def _is_finer(suffix: str, key: str) -> bool:
    """Return whether a suffix splits one compatibility key more finely."""
    if not suffix or not key:
        return False
    return suffix == key or suffix.startswith(key + '.')


def _check_provider_prefix(analysis: _Analysis) -> list[str]:
    """C1: a crate provider package carries the rust- prefix."""
    name = _primary_name(analysis)
    if name is None:
        return []
    value, line = name
    if not value or '%' in value:
        return []
    if value.lower().startswith(RUST_PREFIX):
        return []
    return [
        f'Name: {value} (line {line}) does not carry the "{RUST_PREFIX}" '
        f'prefix; a Rust crate provider package must be named '
        f'"{RUST_PREFIX}{value}"',
    ]


def _check_provider_consistency(
    filename: str, analysis: _Analysis,
) -> list[str]:
    """C2: the directory name, the spec file name and Name agree."""
    name = _primary_name(analysis)
    if name is None:
        return []
    value, line = name
    if not value or '%' in value:
        return []
    directory = os.path.basename(os.path.dirname(os.path.abspath(filename)))
    basename = os.path.basename(filename)
    found: list[str] = []
    if directory and directory != value:
        found.append(
            f'Name: {value} (line {line}) does not match the provider '
            f'directory name "{directory}"; keep the crate provider '
            f'directory name, spec file name and Name consistent',
        )
    if basename != f'{value}.spec':
        found.append(
            f'Name: {value} (line {line}) does not match the spec file '
            f'name "{basename}"; keep the crate provider directory name, '
            f'spec file name and Name consistent',
        )
    return found


def _check_pkgname(analysis: _Analysis) -> list[str]:
    """C3: the pkgname macro is the Name without the rust- prefix."""
    name = _primary_name(analysis)
    pkgname = _macro_value(analysis, PKGNAME)
    if name is None or pkgname is None:
        return []
    value, line = name
    if not value.lower().startswith(RUST_PREFIX):
        return []
    expected = value[len(RUST_PREFIX):]
    if pkgname[0] == expected:
        return []
    return [
        f'%global {PKGNAME} {pkgname[0]} (line {pkgname[1]}) does not match '
        f'Name: {value} (line {line}); the compatibility name is the part '
        f'of the package name after "{RUST_PREFIX}", that is "{expected}"',
    ]


def _check_compat_group(analysis: _Analysis) -> list[str]:
    """C4: the compatibility name groups versions by the page's rules."""
    crate = _macro_value(analysis, CRATE_NAME)
    if crate is None:
        return []
    version = _macro_value(analysis, FULL_VERSION)
    if version is None:
        found = next(
            iter(_fields_matching(analysis, RE_VERSION)), None,
        )
        if found is not None:
            version = (_expand(found[0], analysis.macros), found[1])
    if version is None:
        return []
    key = _compat_key(version[0])
    if key is None:
        return []
    pkgname = _macro_value(analysis, PKGNAME)
    if pkgname is None:
        name = _primary_name(analysis)
        if name is None or not name[0].lower().startswith(RUST_PREFIX):
            return []
        pkgname = (name[0][len(RUST_PREFIX):], name[1])
    suffix = _compat_suffix(pkgname[0], crate[0])
    if suffix and _is_finer(suffix, key):
        return []
    if not suffix:
        return [
            f'%global {PKGNAME} {pkgname[0]} (line {pkgname[1]}) carries no '
            f'compatibility name; a crate provider groups version '
            f'{version[0]} by "{key}", so the compatibility name is '
            f'"{crate[0]}-{key}"',
        ]
    return [
        f'%global {PKGNAME} {pkgname[0]} (line {pkgname[1]}) groups '
        f'version {version[0]} by "{suffix}"; the page asks to group a '
        f'version {version[0]} by "{key}", so the compatibility name is '
        f'"{crate[0]}-{key}"',
    ]


def _check_compat_granularity(analysis: _Analysis) -> list[str]:
    """C5: the compatibility name is not unnecessarily fine-grained."""
    crate = _macro_value(analysis, CRATE_NAME)
    if crate is None:
        return []
    version = _macro_value(analysis, FULL_VERSION)
    if version is None:
        return []
    key = _compat_key(version[0])
    if key is None:
        return []
    pkgname = _macro_value(analysis, PKGNAME)
    if pkgname is None:
        return []
    suffix = _compat_suffix(pkgname[0], crate[0])
    if not _is_finer(suffix, key) or suffix == key:
        return []
    return [
        f'%global {PKGNAME} {pkgname[0]} (line {pkgname[1]}) splits the '
        f'compatibility key "{key}" more finely as "{suffix}"; do not '
        f'introduce an unnecessarily fine-grained compatibility name '
        f'unless the crate has a clear compatibility issue',
    ]


def _check_crate_capability(
    analysis: _Analysis, systems: dict[str, int],
) -> list[str]:
    """C6: a crate dependency is declared as a crate(...) capability."""
    if not _is_rust_ecosystem(analysis, systems):
        return []
    found: list[str] = []
    for pattern in (RE_BUILD_REQUIRES, RE_REQUIRES):
        for value, line in _fields_matching(analysis, pattern):
            expanded = _expand(value, analysis.macros)
            for entry in _entries(expanded):
                name = _entry_name(entry)
                if name.lower() in TOOL_PACKAGES:
                    continue
                if RE_PROVIDER_PACKAGE.match(name) is None:
                    continue
                crate = name[len(RUST_PREFIX):]
                found.append(
                    f'{name} (line {line}) names a crate provider package '
                    f'instead of a crate(...) capability; declare the '
                    f'Rust crate dependency as "{CRATE_CAPABILITY}{crate})"',
                )
    return found


def _check_crate_version(
    analysis: _Analysis, systems: dict[str, int],
) -> list[str]:
    """C7: a crate(...) build dependency carries a version constraint."""
    if not _is_rust_ecosystem(analysis, systems):
        return []
    found: list[str] = []
    for value, line in _fields_matching(analysis, RE_BUILD_REQUIRES):
        expanded = _expand(value, analysis.macros)
        for entry in _entries(expanded):
            if not entry.startswith(CRATE_CAPABILITY):
                continue
            if _entry_version(entry):
                continue
            name = _entry_name(entry)
            found.append(
                f'BuildRequires: {entry.strip()} (line {line}) declares a '
                f'crate capability without a version constraint; the page '
                f'writes every crate(...) dependency with one, such as '
                f'"{name} >= 1.0.0"',
            )
    return found


def _check_pyproject_toolchain(
    analysis: _Analysis, systems: dict[str, int],
) -> list[str]:
    """C8: a pyproject Rust extension declares the Rust build dependencies."""
    if PYPROJECT not in systems:
        return []
    requires = _declared(analysis, RE_BUILD_REQUIRES)
    if not any(name.startswith(CRATE_CAPABILITY) for name in requires):
        return []
    missing = [name for name in (TOOLCHAIN, MACROS) if name not in requires]
    if not missing:
        return []
    return [
        f'BuildSystem: {PYPROJECT} (line {systems[PYPROJECT]}) declares '
        f'crate(...) dependencies but not ' +
        ' or '.join(f'"{name}"' for name in missing) +
        f' in BuildRequires; a Python package with a Rust extension must '
        f'declare both "{TOOLCHAIN}" and "{MACROS}"',
    ]


def _check_provider_capability(analysis: _Analysis) -> list[str]:
    """C9: a crate provider provides a crate(...) capability."""
    pkgname = _macro_value(analysis, PKGNAME)
    if pkgname is None:
        return []
    for value, _line in _fields_matching(analysis, RE_PROVIDES):
        for entry in _entries(_expand(value, analysis.macros)):
            name = _entry_name(entry)
            if not name.startswith(CRATE_CAPABILITY):
                continue
            ability = name[len(CRATE_CAPABILITY):].rstrip(')')
            ability = ability.split('/')[0]
            if ability == pkgname[0]:
                return []
    return [
        f'%global {PKGNAME} {pkgname[0]} (line {pkgname[1]}) is not '
        f'advertised; a crate provider installs the crate sources and '
        f'provides "{CRATE_CAPABILITY}{pkgname[0]})" for other Rust '
        f'packages, so add it to Provides',
    ]


def _check_provider_cargo_toml(
    filename: str, analysis: _Analysis,
) -> list[str]:
    """C10: the provider directory keeps the upstream Cargo.toml."""
    crate = _macro_value(analysis, CRATE_NAME)
    if crate is None and PKGNAME not in analysis.macros:
        return []
    directory = os.path.dirname(os.path.abspath(filename))
    if os.path.exists(os.path.join(directory, CARGO_TOML)):
        return []
    pkgname = _macro_value(analysis, PKGNAME)
    marker = pkgname[1] if pkgname is not None else crate[1] if crate else 1
    return [
        f'(line {marker}) the provider directory holds no {CARGO_TOML}; a '
        f'crate provider keeps a copy of the crate metadata there as the '
        f'basis for the generated crate(...) dependencies',
    ]


def _check_spec_programming_rust_ext(
    filename: str,
    *,
    check_provider_prefix: bool = True,
    check_provider_consistency: bool = True,
    check_pkgname: bool = True,
    check_compat_group: bool = True,
    check_compat_granularity: bool = True,
    check_crate_capability: bool = True,
    check_crate_version: bool = True,
    check_pyproject_toolchain: bool = True,
    check_provider_capability: bool = True,
    check_provider_cargo_toml: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None
    if not (
        check_provider_prefix or check_provider_consistency or
        check_pkgname or check_compat_group or check_compat_granularity or
        check_crate_capability or check_crate_version or
        check_pyproject_toolchain or check_provider_capability or
        check_provider_cargo_toml
    ):
        return []

    analysis = _analyse(lines)
    systems = _systems(analysis)
    provider = RUSTCRATES in systems
    ecosystem = _is_rust_ecosystem(analysis, systems)
    if not provider and not ecosystem:
        return []

    errors: list[str] = []
    if provider:
        if check_provider_prefix:
            errors.extend(_check_provider_prefix(analysis))
        if check_provider_consistency:
            errors.extend(_check_provider_consistency(filename, analysis))
        if check_pkgname:
            errors.extend(_check_pkgname(analysis))
        if check_compat_group:
            errors.extend(_check_compat_group(analysis))
        if check_compat_granularity:
            errors.extend(_check_compat_granularity(analysis))
        if check_provider_capability:
            errors.extend(_check_provider_capability(analysis))
        if check_provider_cargo_toml:
            errors.extend(_check_provider_cargo_toml(filename, analysis))
    if check_crate_capability:
        errors.extend(_check_crate_capability(analysis, systems))
    if check_crate_version:
        errors.extend(_check_crate_version(analysis, systems))
    if check_pyproject_toolchain:
        errors.extend(_check_pyproject_toolchain(analysis, systems))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_programming_rust(filename: str) -> list[str]:
    return _check_spec_programming_rust_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the requirements of the Rust language '
                    'guideline.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-provider-prefix',
        action='store_true',
        help='do not report a crate provider name without the rust- prefix',
    )
    parser.add_argument(
        '--no-check-provider-consistency',
        action='store_true',
        help='do not report a provider directory or spec file name that '
             'does not match Name',
    )
    parser.add_argument(
        '--no-check-pkgname',
        action='store_true',
        help='do not report a pkgname macro that does not match Name',
    )
    parser.add_argument(
        '--no-check-compat-group',
        action='store_true',
        help='do not report a compatibility name that groups a version '
             'by the wrong key',
    )
    parser.add_argument(
        '--no-check-compat-granularity',
        action='store_true',
        help='do not report an unnecessarily fine-grained compatibility '
             'name',
    )
    parser.add_argument(
        '--no-check-crate-capability',
        action='store_true',
        help='do not report a crate dependency declared as an ordinary '
             'package name',
    )
    parser.add_argument(
        '--no-check-crate-version',
        action='store_true',
        help='do not report a crate(...) build dependency without a '
             'version constraint',
    )
    parser.add_argument(
        '--no-check-pyproject-toolchain',
        action='store_true',
        help='do not report a pyproject Rust extension without the rust '
             'and rust-rpm-macros build dependencies',
    )
    parser.add_argument(
        '--no-check-provider-capability',
        action='store_true',
        help='do not report a crate provider that advertises no '
             'crate(...) capability',
    )
    parser.add_argument(
        '--no-check-provider-cargo-toml',
        action='store_true',
        help='do not report a provider directory without a Cargo.toml',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_programming_rust_ext(
            filename,
            check_provider_prefix=not args.no_check_provider_prefix,
            check_provider_consistency=not args.no_check_provider_consistency,
            check_pkgname=not args.no_check_pkgname,
            check_compat_group=not args.no_check_compat_group,
            check_compat_granularity=not args.no_check_compat_granularity,
            check_crate_capability=not args.no_check_crate_capability,
            check_crate_version=not args.no_check_crate_version,
            check_pyproject_toolchain=not args.no_check_pyproject_toolchain,
            check_provider_capability=not args.no_check_provider_capability,
            check_provider_cargo_toml=not args.no_check_provider_cargo_toml,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret
