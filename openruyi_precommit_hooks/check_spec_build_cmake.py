"""Enforce the build requirements and options of the cmake build system.

The ``cmake`` supplement of the packaging guidelines describes how a spec
opts into the declarative cmake build system, and it states both the
dependency that the choice implies and the options the shipped macros
already supply.

Section "依赖" (Dependencies):

> If you want to use the cmake build system, you need to add these
> BuildRequires, because gcc is preinstalled in the build environment and
> does not have to be declared explicitly.
>
>     BuildRequires:  cmake

Section "构建系统说明" (Build system notes) lists the values that the
macros in ``/usr/lib/rpm/macros.d/macros.cmake`` already define, and the
worked example of the page removes the redundant settings from the spec:

    -DCMAKE_BUILD_TYPE:STRING=RelWithDebInfo
    -DCMAKE_VERBOSE_MAKEFILE:BOOL=ON
    -DCMAKE_INSTALL_DO_STRIP:BOOL=OFF
    -DCMAKE_INSTALL_PREFIX:PATH=%{_prefix}
    -DCMAKE_INSTALL_SBINDIR:PATH=bin
    -DINCLUDE_INSTALL_DIR:PATH=%{_includedir}
    -DLIB_INSTALL_DIR:PATH=%{_libdir}
    -DSYSCONF_INSTALL_DIR:PATH=%{_sysconfdir}
    -DSHARE_INSTALL_PREFIX:PATH=%{_datadir}
    -DLIB_SUFFIX=64

The same page states that ``%check`` already runs ``%ctest`` and that the
extra arguments belong in ``BuildOption(check)``.

Three checkpoints are implemented, and each one is anchored in an explicit
clause of the page:

* C1 is MUST level ("you need to add these BuildRequires") and reproduces
  the single dependency the page names.
* C2 follows from the statement that ``%check`` already runs ``%ctest``:
  an explicit ``%check`` whose whole body re-runs ``ctest`` without any
  argument adds nothing, so it is a redundant section. A ``ctest`` that
  carries arguments is **not** reported, because the page keeps those
  arguments and only asks for them to move into ``BuildOption(check)``.
* C3 reports a ``BuildOption(conf)`` flag whose name **and** value are the
  value the macros already define, which is exactly what the worked
  example deletes. A flag that overrides a default with a different value
  is a deliberate choice and is not reported.

The package name is matched as a whole name, never as a prefix.
``extra-cmake-modules`` and ``kf6-extra-cmake-modules`` are different
packages that provide the CMake modules a project uses; neither one is
``cmake`` itself.

Deliberately out of scope: whether a spec that calls ``%cmake`` must
declare ``BuildSystem: cmake`` (the page only recommends the field, and no
spec in the corpus omits it), whether ``cmake --install`` belongs in
``%install`` (no spec in the corpus does it), and every other dependency
question, which belongs to ``check-spec-buildrequires``. No network access
and no ``rpm`` invocation is performed, so the rule works on a bare
checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. A trailing parenthesised argument such
# as the stage of "BuildOption(build):" belongs to the field name rather
# than to the value, so the group is matched and dropped.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)(?:\(([^)]*)\))?\s*:\s*(.*)$')

# A section header. Section arguments ("%prep -a", "%conf -p") are ignored.
RE_SECTION = re.compile(r'^%([a-z]\w*)\b')

# The field that switches the requirement on, and the field that satisfies
# it. Both are matched loosely so a misspelling reported by the dedicated
# rules still contributes its value here.
RE_BUILD_SYSTEM = re.compile(r'^build-?system$', re.IGNORECASE)
RE_BUILD_REQUIRES = re.compile(r'^build-?requires?$', re.IGNORECASE)
RE_BUILD_OPTION = re.compile(r'^build-?option$', re.IGNORECASE)

# The dependency operators. A token that is exactly an operator consumes the
# token after it, which is the version of the dependency to its left.
RE_OPERATOR = re.compile(r'^(?:<=|>=|=|<|>)$')

# A "ctest" invocation, with or without the "%" macro prefix. The captured
# remainder decides whether the invocation carries an argument.
RE_CTEST = re.compile(r'^\s*%?ctest\b(.*)$')

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

# The section whose body C2 inspects, and the stage whose BuildOption lines
# C3 inspects.
CHECK_SECTION = '%check'
CONF_STAGE = 'conf'

# The build system this rule covers, and the dependency the page names for
# it. The name is spelled exactly as the page spells it.
CMAKE = 'cmake'
REQUIRED_PACKAGE = 'cmake'

# The value a field of "BuildOption(conf)" assigns before the comparison.
RE_DEFINE = re.compile(
    r'^-D(?P<name>[A-Za-z_][A-Za-z0-9_]*)'
    r'(?::(?P<type>[A-Za-z]+))?'
    r'=(?P<value>.*)$',
)

# The exact defaults the shipped macros already define, transcribed from the
# "构建系统说明" bullet list and from the flags the worked example deletes.
# A flag is redundant only when both the name and the value match one of
# these pairs.
PRESET_VALUES: dict[str, tuple[str, ...]] = {
    'CMAKE_BUILD_TYPE': ('RelWithDebInfo',),
    'CMAKE_VERBOSE_MAKEFILE': ('ON',),
    'CMAKE_INSTALL_DO_STRIP': ('OFF',),
    'BUILD_SHARED_LIBS': ('ON',),
    'LIB_SUFFIX': ('64',),
    'CMAKE_INSTALL_PREFIX': ('%{_prefix}', '%_prefix'),
    'CMAKE_INSTALL_LIBDIR': ('%{_lib}', '%_lib'),
    'CMAKE_INSTALL_FULL_LIBDIR': ('%{_libdir}', '%_libdir'),
    'CMAKE_INSTALL_SBINDIR': ('bin',),
    'CMAKE_INSTALL_FULL_SBINDIR': ('%{_sbindir}', '%_sbindir'),
    'CMAKE_INSTALL_LIBEXECDIR': ('%{_libexecdir}', '%_libexecdir'),
    'CMAKE_INSTALL_FULL_LIBEXECDIR': ('%{_libexecdir}', '%_libexecdir'),
    'INCLUDE_INSTALL_DIR': ('%{_includedir}', '%_includedir'),
    'LIB_INSTALL_DIR': ('%{_libdir}', '%_libdir'),
    'SYSCONF_INSTALL_DIR': ('%{_sysconfdir}', '%_sysconfdir'),
    'SHARE_INSTALL_PREFIX': ('%{_datadir}', '%_datadir'),
}


class _Block(NamedTuple):
    """One field block: the fields it holds, in file order.

    ``fields`` is a list of ``(spelling, stage, value, 1-based line)``
    tuples, where ``stage`` is the parenthesised argument of a field name or
    the empty string when the name carries none.
    """

    fields: list[tuple[str, str, str, int]]


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


def _is_section(line: str) -> str | None:
    """Return the known section name on this line, or None."""
    match = RE_SECTION.match(line)
    if match is None:
        return None
    section = '%' + match.group(1)
    if section in KNOWN_SECTIONS:
        return section
    return None


def _macro_depth_after(line: str, depth: int) -> int:
    """Return the macro nesting depth after consuming one line."""
    depth += line.count('{') - line.count('}')
    return depth if depth > 0 else 0


def _blocks_of(lines: list[str]) -> list[_Block]:
    """Split the file into field blocks.

    The first block is the main preamble, kept even when it holds no field.
    Every ``%package`` opens a fresh block, so a subpackage that declares a
    build system of its own is judged against its own dependencies. A block
    ends at the first known section, so a macro invocation such as
    ``%global debug_package %{nil}`` neither ends a block nor hides the
    fields that follow it.
    """
    raw: list[list[tuple[str, str, str, int]]] = []
    fields: list[tuple[str, str, str, int]] = []
    macro_depth = 0

    for index, line in enumerate(lines, 1):
        if macro_depth > 0:
            macro_depth = _macro_depth_after(line, macro_depth)
            continue
        section = _is_section(line)
        if section is not None:
            raw.append(fields)
            fields = []
            continue
        if line.startswith('#'):
            continue
        match = RE_FIELD.match(line)
        if match is None:
            continue
        name, stage, value = (
            match.group(1), match.group(2) or '', match.group(3)
        )
        fields.append((name, stage.strip(), value, index))
        macro_depth = _macro_depth_after(line, 0)

    raw.append(fields)
    blocks = [_Block(raw[0])]
    blocks.extend(_Block(item) for item in raw[1:] if item)
    return blocks


def _declared_names(value: str) -> set[str]:
    """Return the lowercase name of every dependency on one field line.

    A dependency is a name optionally followed by a version operator and a
    version, or one rich dependency in parentheses, or two names joined by
    a comma, ``with`` or ``without``. Only the names are returned, so a
    version number never looks like a dependency and
    ``extra-cmake-modules`` stays distinct from ``cmake``.
    """
    names: set[str] = set()
    skip = False
    depth = 0
    for token in value.split():
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
        names.add(token.rstrip(',').lower())
    return names


def _system_lines(blocks: Sequence[_Block]) -> list[int]:
    """Return the lines of every ``BuildSystem: cmake`` field."""
    return [
        line
        for block in blocks
        for name, _stage, value, line in block.fields
        if RE_BUILD_SYSTEM.match(name) is not None
        and value.strip().lower() == CMAKE
    ]


def _declared_everywhere(blocks: Sequence[_Block]) -> set[str]:
    """Return every dependency name declared in any build-requires field.

    ``BuildRequires`` is a source-package level field, so RPM merges the
    declarations of every subpackage block into one build dependency set.
    The requirement is therefore satisfied when the name appears anywhere
    in the file, which keeps a subpackage that carries the dependency from
    producing a false finding.
    """
    declared: set[str] = set()
    for block in blocks:
        for name, _stage, value, _line in block.fields:
            if RE_BUILD_REQUIRES.match(name) is not None:
                declared |= _declared_names(value)
    return declared


def _check_buildrequires(line: int, declared: set[str]) -> list[str]:
    """C1: a cmake spec declares cmake as a BuildRequires."""
    if REQUIRED_PACKAGE in declared:
        return []
    return [
        f'BuildSystem: {CMAKE} (line {line}) requires '
        f'"{REQUIRED_PACKAGE}" in BuildRequires; '
        f'missing "{REQUIRED_PACKAGE}"',
    ]


def _ctest_without_arguments(lines: Sequence[str]) -> list[int]:
    """C2: return the lines of a ``%check`` that only re-runs ``ctest``.

    An explicit ``%check`` whose body is a single ``ctest`` invocation with
    no argument reproduces what the ``%ctest`` macro already runs, so the
    section carries nothing of its own. A ``ctest`` that passes arguments
    keeps them: the page only asks for those arguments to move into
    ``BuildOption(check)``, which is a placement question owned by
    ``check-spec-buildoption``, not a redundancy that this rule may drop.
    """
    found: list[int] = []
    header: int | None = None
    body: list[str] = []
    for index, line in enumerate(lines, 1):
        section = _is_section(line)
        if section is not None:
            if header is not None and _is_bare_ctest(body):
                found.append(header)
            header = index if section == CHECK_SECTION else None
            body = []
            continue
        if header is not None:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                body.append(line)
    if header is not None and _is_bare_ctest(body):
        found.append(header)
    return found


def _is_bare_ctest(body: Sequence[str]) -> bool:
    """Return whether the body is exactly one argument-free ``ctest``."""
    if len(body) != 1:
        return False
    match = RE_CTEST.match(body[0])
    if match is None:
        return False
    return not match.group(1).strip()


def _redundant_flags(blocks: Sequence[_Block]) -> list[tuple[str, int]]:
    """C3: return the flags of ``BuildOption(conf)`` that repeat a default.

    Only a flag whose name **and** value equal one of the defaults the
    shipped macros already define is returned. A flag that overrides a
    default with another value is a deliberate choice and is never returned.
    """
    found: list[tuple[str, int]] = []
    for block in blocks:
        for name, stage, value, line in block.fields:
            if RE_BUILD_OPTION.match(name) is None:
                continue
            if stage.lower() != CONF_STAGE:
                continue
            for token in value.split():
                match = RE_DEFINE.match(token)
                if match is None:
                    continue
                key = match.group('name')
                presets = PRESET_VALUES.get(key)
                if presets is None:
                    continue
                if match.group('value').strip().strip('"') in presets:
                    found.append((token, line))
    return found


def _check_spec_build_cmake_ext(
    filename: str,
    *,
    check_buildrequires: bool = True,
    check_check_section: bool = True,
    check_build_option: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None
    if not (
        check_buildrequires or check_check_section or check_build_option
    ):
        return []

    blocks = _blocks_of(lines)
    system_lines = _system_lines(blocks)
    if not system_lines:
        return []

    errors: list[str] = []
    if check_buildrequires:
        declared = _declared_everywhere(blocks)
        errors.extend(_check_buildrequires(system_lines[0], declared))
    if check_check_section:
        for line in _ctest_without_arguments(lines):
            errors.append(
                f'%check (line {line}) runs "ctest" without arguments, '
                f'which the %ctest macro already runs for '
                f'BuildSystem: {CMAKE}; remove the redundant %check',
            )
    if check_build_option:
        for token, line in _redundant_flags(blocks):
            errors.append(
                f'BuildOption({CONF_STAGE}) (line {line}) repeats '
                f'"{token}", which the cmake macros already define',
            )

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_build_cmake(filename: str) -> list[str]:
    return _check_spec_build_cmake_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the requirements of a cmake build system.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-buildrequires',
        action='store_true',
        help='do not report a missing cmake build dependency',
    )
    parser.add_argument(
        '--no-check-check-section',
        action='store_true',
        help='do not report an explicit %%check that re-runs %%ctest',
    )
    parser.add_argument(
        '--no-check-build-option',
        action='store_true',
        help='do not report a BuildOption(conf) that repeats a default',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_build_cmake_ext(
            filename,
            check_buildrequires=not args.no_check_buildrequires,
            check_check_section=not args.no_check_check_section,
            check_build_option=not args.no_check_build_option,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret
