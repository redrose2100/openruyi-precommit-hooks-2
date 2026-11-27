"""Enforce the requirements of the Python language packaging guideline.

The Python page of the openRuyi packaging guidelines describes how a
package that ships Python modules is named and how it declares its source,
its modules and its runtime capabilities.

Section "Naming" states, verbatim:

> Packages for Python libraries must use the `python-` prefix.

> For the package name (`DISTNAME`), use the name the upstream project uses
> on PyPI. You must add the following macro at the top of the spec file:
>
>     %global srcname DISTNAME

> In short, the `srcname` macro represents the project's name on PyPI. The
> name must also follow the normalized name rules in PEP 503: use lowercase
> letters, and replace `_` and `.` with `-`. For example, if the upstream
> project name is `aiohttp_socks`, use `aiohttp-socks` as the package name
> and `srcname`.

Section "Provides: python3-DISTNAME" states, verbatim:

> Since openRuyi does not split `python3` into a separate subpackage, but
> instead provides it directly from the main package, if the package is
> architecture-independent, you should add the following entries to the
> spec file:
>
>     Provides:       python3-DISTNAME = %{version}-%{release}
>     %python_provide python3-DISTNAME

> If the package is architecture-dependent, you should add the following
> entries to the spec file instead:
>
>     Provides:       python3-%{srcname}%{?_isa} = %{version}-%{release}

> Here, you can replace `DISTNAME` with the previously defined macro, which
> is typically `%{srcname}`.

Section "Dependencies" states, verbatim:

> Packages should not declare an explicit runtime dependency on `python3`,
> because the following dependencies are added automatically in the
> corresponding cases:
>
> - When you install files into `%{python3_sitelib}` or
>   `%{python3_sitearch}`, the build system automatically generates a
>   dependency on `python(abi) = 3.X`.
> - If the package contains executable Python scripts, the build system
>   automatically generates a dependency on `/usr/bin/python3`.

Five checkpoints are implemented, and each one is anchored in one of those
clauses:

* C1 reproduces the naming prefix for a package that ships modules.
* C2 reproduces the ``srcname`` macro the page says must be written.
* C3 reproduces the PEP 503 normalisation the page asks ``srcname`` to
  follow.
* C4 reproduces the ``python3-`` capability the page asks the main package
  to provide.
* C5 reproduces the clause that forbids an explicit runtime dependency on
  ``python3``.

A spec is in scope when it declares ``BuildSystem: pyproject``, because that
is the declarative build system the page describes and it is the only
signal a spec-only linter can read to tell a Python library package from a
C or C++ package that merely ships Python bindings. ``ceph`` builds with
``BuildSystem: cmake`` and ``bind`` with ``BuildSystem: autotools``, so
neither is judged even though both install Python modules.

C1 and C4 are judged only on the library subset that installs modules into
``%{python3_sitelib}`` or ``%{python3_sitearch}``, so a command line tool
built with pyproject is not asked for a ``python-`` name or a ``python3-``
capability. C2 and C3 are judged on the specs that carry a ``python-`` name
or a ``srcname`` macro respectively, which is the population the clause
names.

Deliberately out of scope: the ``pkgconfig(python3)`` and
``pyproject-rpm-macros`` build dependencies (owned by
``check-spec-build-pyproject``), the ``BuildOption(install)`` module name
(also owned there), ``%{pyproject_files}`` in ``%files`` (owned there as
well), whether the upstream source really publishes to PyPI (the page
allows using another source when PyPI has no download, and a spec-only
linter cannot inspect the index), and the ``pypi_name`` macro (the page
asks for it only when the download name differs from the project name,
which the linter cannot decide).

No network access and no ``rpm`` invocation is performed, so the rule works
on a bare checkout.
"""
from __future__ import annotations

import argparse
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
RE_BUILD_SYSTEM = re.compile(r'^build-?system$', re.IGNORECASE)
RE_PROVIDES = re.compile(r'^provides?$', re.IGNORECASE)
RE_REQUIRES = re.compile(r'^requires?$', re.IGNORECASE)

# The explicit macro invocation that provides the python3- capability.
RE_PYTHON_PROVIDE = re.compile(r'^%python_provide\b', re.MULTILINE)

# The two directories a Python module package installs into. Their presence
# is the only reliable signal a spec-only linter has for "this spec ships a
# Python module".
RE_PYTHON_SITE = re.compile(r'%\{python3_(?:sitelib|sitearch)\}')

# The dependency operators. A token that is exactly an operator consumes the
# token after it, which is the version of the dependency to its left.
RE_OPERATOR = re.compile(r'^(?:<=|>=|=|<|>)$')

# The two keywords that join two dependency names into one clause.
_JOINERS = frozenset({'with', 'without'})

# The closed set of real RPM sections, mirroring check-spec-basic-fields.
# Anything else that starts with "%" is a macro invocation (%license, %doc,
# %python_provide, %autochangelog, ...) and must never be mistaken for a
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

# The build system this rule covers, spelled as the page spells it.
PYPROJECT = 'pyproject'

# The prefix a Python library package name carries.
PYTHON_PREFIX = 'python-'

# The capability prefix the main package provides.
PYTHON3_PREFIX = 'python3-'

# The name of the macro the page asks for, and the normalised spelling of a
# PEP 503 project name.
SRCNAME = 'srcname'
RE_PEP503 = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')

# How many passes a macro expansion may take.
_EXPANSIONS = 10

# The character pair the page asks srcname to replace, and the replacement.
_PEP503_REPLACEMENTS = (('_', '-'), ('.', '-'))


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
    checkpoint looks for a directory macro that a comment never makes
    meaningful, and it is deliberately not expanded: a spec is free to
    redefine ``python3_sitelib`` for itself, and the spelling the packager
    wrote is the one the finding should quote.
    """
    macros = _definitions(lines)
    text = '\n'.join(
        line for line in lines if not line.lstrip().startswith('#')
    )
    return _Analysis(macros, _blocks_of(lines), text)


def _first_field(
    analysis: _Analysis, pattern: re.Pattern[str],
) -> tuple[str, int] | None:
    """Return ``(value, line)`` of the first field the pattern selects."""
    for block in analysis.blocks:
        for name, _stage, value, line in block.fields:
            if pattern.match(name) is not None:
                return value.strip(), line
    return None


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


def _primary_name(analysis: _Analysis) -> tuple[str, int] | None:
    """Return ``(expanded name, line)`` of the main package, or None."""
    found = _first_field(analysis, RE_NAME)
    if found is None:
        return None
    return _expand(found[0], analysis.macros), found[1]


def _ships_modules(analysis: _Analysis) -> bool:
    """Return whether the spec installs into the Python module directory."""
    return RE_PYTHON_SITE.search(analysis.text) is not None


def _dependency_names(value: str) -> set[str]:
    """Return the name of every dependency on one field line.

    A dependency is a name optionally followed by a version operator and a
    version, or one rich dependency in parentheses, or two names joined by
    a comma, ``with`` or ``without``. Only the names are returned, so a
    version number never looks like a dependency and ``python3-devel`` stays
    distinct from ``python3``.
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


def _bare_python3(value: str) -> bool:
    """Return whether one dependency line names a bare ``python3``."""
    return 'python3' in {
        name.lower() for name in _dependency_names(value)
    }


def _provides_python3(analysis: _Analysis) -> bool:
    """Return whether the spec provides any ``python3-`` capability."""
    for value, _line in _fields_matching(analysis, RE_PROVIDES):
        for name in _dependency_names(_expand(value, analysis.macros)):
            if name.lower().startswith(PYTHON3_PREFIX):
                return True
    if RE_PYTHON_PROVIDE.search(analysis.text) is not None:
        return True
    return False


def _pep503_name(text: str) -> str:
    """Return the PEP 503 normalised spelling of one project name."""
    normal = text.strip().strip('\'"').lower()
    for old, new in _PEP503_REPLACEMENTS:
        normal = normal.replace(old, new)
    return re.sub(r'-{2,}', '-', normal)


def _is_normalised(text: str) -> bool:
    """Return whether ``text`` already follows the PEP 503 name rules."""
    return RE_PEP503.fullmatch(text) is not None


def _check_package_name(analysis: _Analysis) -> list[str]:
    """C1: a package that ships modules carries the python- prefix."""
    found: list[str] = []
    name = _primary_name(analysis)
    if name is None:
        return found
    value, line = name
    if not value or '%' in value:
        return found
    if value.lower().startswith(PYTHON_PREFIX):
        return found
    suggested = PYTHON_PREFIX + _pep503_name(value)
    found.append(
        f'Name: {value} (line {line}) does not carry the python- prefix; '
        f'a Python library package must be named "{suggested}"',
    )
    return found


def _check_srcname(analysis: _Analysis) -> list[str]:
    """C2: a python- named package defines the srcname macro."""
    found: list[str] = []
    name = _primary_name(analysis)
    if name is None:
        return found
    value, line = name
    if not value.lower().startswith(PYTHON_PREFIX):
        return found
    if SRCNAME in analysis.macros:
        return found
    found.append(
        f'Name: {value} (line {line}) is a Python library package without '
        f'a {SRCNAME} macro; add "%global {SRCNAME} DISTNAME" at the top of '
        f'the spec',
    )
    return found


def _check_srcname_normalised(analysis: _Analysis) -> list[str]:
    """C3: the srcname macro carries a PEP 503 normalised name."""
    found: list[str] = []
    macro = analysis.macros.get(SRCNAME)
    if macro is None:
        return found
    value = _expand(macro.value.strip().strip('\'"'), analysis.macros)
    if not value or '%' in value:
        return found
    if _is_normalised(value):
        return found
    found.append(
        f'%global {SRCNAME} {value} (line {macro.line}) is not PEP 503 '
        f'normalised; use lowercase letters and replace "_" and "." with '
        f'"-", for example "{_pep503_name(value)}"',
    )
    return found


def _capability_hint(analysis: _Analysis) -> str:
    """Return the capability name C4 suggests, in the spec's own spelling."""
    if SRCNAME in analysis.macros:
        return f'{PYTHON3_PREFIX}%{{{SRCNAME}}}'
    name = _primary_name(analysis)
    if name is None or not name[0]:
        return f'{PYTHON3_PREFIX}DISTNAME'
    base = name[0]
    if base.lower().startswith(PYTHON_PREFIX):
        base = base[len(PYTHON_PREFIX):]
    return PYTHON3_PREFIX + _pep503_name(base)


def _check_python3_provides(
    analysis: _Analysis, system_line: int,
) -> list[str]:
    """C4: a package that ships modules provides a python3- capability."""
    if _provides_python3(analysis):
        return []
    capability = _capability_hint(analysis)
    return [
        f'BuildSystem: {PYPROJECT} (line {system_line}) installs Python '
        f'modules but provides no "{PYTHON3_PREFIX}" capability; add '
        f'"Provides: {capability} = %{{version}}-%{{release}}" or '
        f'"%python_provide {capability}"',
    ]


def _check_python3_requires(analysis: _Analysis) -> list[str]:
    """C5: a package does not declare an explicit dependency on python3."""
    found: list[str] = []
    for value, line in _fields_matching(analysis, RE_REQUIRES):
        expanded = _expand(value, analysis.macros)
        if not _bare_python3(expanded):
            continue
        found.append(
            f'Requires: {value} (line {line}) declares an explicit runtime '
            f'dependency on python3; a package that installs into '
            f'%{{python3_sitelib}} or %{{python3_sitearch}} already depends '
            f'on "python(abi)" automatically',
        )
    return found


def _check_spec_programming_python_ext(
    filename: str,
    *,
    check_package_name: bool = True,
    check_srcname: bool = True,
    check_srcname_normalised: bool = True,
    check_python3_provides: bool = True,
    check_python3_requires: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None
    if not (
        check_package_name or check_srcname or check_srcname_normalised or
        check_python3_provides or check_python3_requires
    ):
        return []

    analysis = _analyse(lines)
    systems = {
        system: line for system, line in _systems(analysis).items()
        if system == PYPROJECT
    }
    if not systems:
        return []

    system_line = next(iter(systems.values()))
    ships = _ships_modules(analysis)

    errors: list[str] = []
    if check_package_name and ships:
        errors.extend(_check_package_name(analysis))
    if check_srcname:
        errors.extend(_check_srcname(analysis))
    if check_srcname_normalised:
        errors.extend(_check_srcname_normalised(analysis))
    if check_python3_provides and ships:
        errors.extend(_check_python3_provides(analysis, system_line))
    if check_python3_requires:
        errors.extend(_check_python3_requires(analysis))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_programming_python(filename: str) -> list[str]:
    return _check_spec_programming_python_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the requirements of the Python language '
                    'guideline.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-package-name',
        action='store_true',
        help='do not report a Python library package name without the '
             'python- prefix',
    )
    parser.add_argument(
        '--no-check-srcname',
        action='store_true',
        help='do not report a missing srcname macro',
    )
    parser.add_argument(
        '--no-check-srcname-normalised',
        action='store_true',
        help='do not report a srcname macro that is not PEP 503 normalised',
    )
    parser.add_argument(
        '--no-check-python3-provides',
        action='store_true',
        help='do not report a missing python3- capability',
    )
    parser.add_argument(
        '--no-check-python3-requires',
        action='store_true',
        help='do not report an explicit runtime dependency on python3',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_programming_python_ext(
            filename,
            check_package_name=not args.no_check_package_name,
            check_srcname=not args.no_check_srcname,
            check_srcname_normalised=not args.no_check_srcname_normalised,
            check_python3_provides=not args.no_check_python3_provides,
            check_python3_requires=not args.no_check_python3_requires,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret
