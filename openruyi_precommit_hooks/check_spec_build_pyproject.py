"""Enforce the requirements of the pyproject declarative build system.

The ``pyproject`` supplement of the packaging guidelines describes how a
spec opts into the declarative build system that drives PEP 517 and PEP 518
builds, and it states the dependencies, the options and the test behaviour
that the choice implies.

Section "Dependencies" states, verbatim:

> If you need to use the pyproject build system, then you typically need to
> add at least these BuildRequires:
>
>     BuildRequires:  pyproject-rpm-macros
>     BuildRequires:  pkgconfig(python3)

Section "Example" states, verbatim:

> Note that when using the pyproject declarative build system you must pass
> the corresponding module name to BuildOption(install). Because that option
> is passed as an argument to %pyproject_save_files, adding the -l argument
> by default is usually recommended.

Section "Testing" states, verbatim:

> The pyproject declarative build system runs a smoke test by default,
> namely an import check of the installed modules. Generally speaking, you
> should not simply empty %check to skip the tests.
>
> If you need to exclude some modules during this process, you can pass
> arguments to %pyproject_check_import through BuildOption(check), and write
> the reason for the exclusion above it.

Six checkpoints are implemented, and each one is anchored in one of those
clauses:

* C1 reproduces the macro package the page names for every pyproject spec.
* C2 reproduces the Python development dependency the page names next to it.
  The page writes ``pkgconfig(python3)``; the equivalent spellings
  ``pkgconfig(python)`` and ``python3-devel`` are accepted, because the
  corpus uses all three and they express the same build-time requirement.
* C3 reproduces the module name that ``BuildOption(install)`` must carry.
  An explicit ``%pyproject_save_files`` invocation delivers the same module
  name to the same macro, so a spec that writes it is accepted.
* C4 reports a ``BuildOption(install)`` that carries only options, which is
  the way a spec loses the module name while still looking configured.
* C5 reproduces the "do not simply empty %check" clause. A ``%check`` that
  holds a comment explaining why the tests are skipped is *not* reported:
  the page asks for that reason to be written, so writing it complies.
* C6 reproduces the "write the reason above it" clause for
  ``BuildOption(check)``. Only the first option of a group is judged, since
  the page asks for one reason above the group rather than one per line.

C1 and C2 are worded with "typically need at least", so they are enforced
as a normal form rather than as an absolute rule: a spec that satisfies the
clause in another spelling is accepted, and every dependency question
outside those two names belongs to ``check-spec-buildrequires``.

Deliberately out of scope: whether the upstream source tree carries a
``pyproject.toml`` and follows PEP 517 (the page chooses the build system
from the source tree, which a spec-only linter cannot inspect), the presence
of ``%generate_buildrequires``/``%pyproject_buildrequires`` (the page shows
them as the mechanism rather than as a requirement, and spec in the corpus
run explicit phases instead), the ``-l`` argument of ``BuildOption(install)``
(the page calls it a recommendation and allows dropping it when the build
reports ``No License-File``), the presence of ``%license`` (the page states
that it is usually unnecessary, which is a hint rather than a rule), and the
syntax of ``BuildOption`` itself (owned by ``check-spec-buildoption``).

No network access and no ``rpm`` invocation is performed, so the rule works
on a bare checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. A trailing parenthesised argument such
# as the stage of "BuildOption(install):" belongs to the field name rather
# than to the value, so the group is matched and dropped.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)(?:\(([^)]*)\))?\s*:\s*(.*)$')

# A section header, together with everything that follows the section name
# on the same line. For "%check" the remainder is empty; for "%check -a" it
# is "-a".
RE_SECTION = re.compile(r'^%([a-z]\w*)\b(.*)$')

# The field that switches the requirement on, and the fields that satisfy
# it. All of them are matched loosely so a misspelling reported by the
# dedicated rules still contributes its value here.
RE_BUILD_SYSTEM = re.compile(r'^build-?system$', re.IGNORECASE)
RE_BUILD_REQUIRES = re.compile(r'^build-?requires?$', re.IGNORECASE)
RE_BUILD_OPTION = re.compile(r'^build-?option$', re.IGNORECASE)

# A pkgconfig capability such as "pkgconfig(python3)". The capability is a
# rich dependency, so the generic dependency splitter drops it; matching it
# separately keeps the capability name intact.
RE_PKGCONFIG_CAPABILITY = re.compile(
    r'\b(?:pkgconfig|pkg-config)\(\s*([^)]*)\s*\)', re.IGNORECASE,
)

# The explicit macro invocation that hands the module name to
# %pyproject_save_files when the spec does not use BuildOption(install).
RE_SAVE_FILES = re.compile(r'^%pyproject_save_files\b', re.MULTILINE)

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

# The build system this rule covers. The name is spelled exactly as the
# page spells it.
PYPROJECT = 'pyproject'

# The macro package the page names first, matched as a whole name so
# "python3-pyproject-rpm-macros" would not pass for "pyproject-rpm-macros".
MACROS_PACKAGE = 'pyproject-rpm-macros'

# The Python development dependency, in every spelling the page and the
# corpus use. The first group is matched as a pkgconfig capability, the
# second as a plain package name.
PYTHON_DEVEL_CAPABILITIES: tuple[str, ...] = ('python3', 'python')
PYTHON_DEVEL_PACKAGES: tuple[str, ...] = ('python3-devel',)

# The spellings named in the C2 message, in the order of the page.
PYTHON_DEVEL_SPELLING = 'pkgconfig(python3), pkgconfig(python), python3-devel'

# The stages whose BuildOption lines are inspected, and the section whose
# body C5 inspects.
INSTALL_STAGE = 'install'
CHECK_STAGE = 'check'
CHECK_SECTION = '%check'


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
            match.group(1), match.group(2) or '', match.group(3),
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
    version number never looks like a dependency and ``python3-devel`` stays
    distinct from ``python3``.
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


def _capability_names(value: str) -> set[str]:
    """Return the lowercase name of every ``pkgconfig(...)`` capability."""
    return {
        match.group(1).strip().lower()
        for match in RE_PKGCONFIG_CAPABILITY.finditer(value)
    }


def _system_lines(blocks: Sequence[_Block]) -> list[int]:
    """Return the lines of every ``BuildSystem: pyproject`` field."""
    return [
        line
        for block in blocks
        for name, _stage, value, line in block.fields
        if RE_BUILD_SYSTEM.match(name) is not None and
        PYPROJECT in {token.lower() for token in value.split()}
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


def _capabilities_everywhere(blocks: Sequence[_Block]) -> set[str]:
    """Return every ``pkgconfig(...)`` capability declared as a requirement."""
    declared: set[str] = set()
    for block in blocks:
        for name, _stage, value, _line in block.fields:
            if RE_BUILD_REQUIRES.match(name) is not None:
                declared |= _capability_names(value)
    return declared


def _install_options(blocks: Sequence[_Block]) -> list[tuple[str, int]]:
    """Return ``(value, line)`` for every ``BuildOption(install)`` field."""
    return [
        (value, line)
        for block in blocks
        for name, stage, value, line in block.fields
        if RE_BUILD_OPTION.match(name) is not None and
        stage.lower() == INSTALL_STAGE
    ]


def _module_names(value: str) -> list[str]:
    """Return the module names of a ``BuildOption(install)`` value.

    Every leading-dash token is an option rather than a module, and
    ``+auto`` asks the macros to discover the modules. Whatever is left is
    a module name, including the ``%{srcname}`` spelling many specs use.
    """
    return [
        token for token in value.split()
        if not token.startswith(('-', '+'))
    ]


def _previous_nonblank(lines: Sequence[str], index: int) -> int | None:
    """Return the index of the previous non-blank line, or None."""
    cursor = index - 1
    while cursor >= 0:
        if lines[cursor].strip():
            return cursor
        cursor -= 1
    return None


def _check_bodies(lines: Sequence[str]) -> list[tuple[int, list[str]]]:
    """Return ``(header line, non-blank body lines)`` for each ``%check``.

    Comment lines are kept in the body on purpose: C5 only reports a
    section that holds nothing at all, and a comment that explains the skip
    is what the page asks the packager to write.
    """
    found: list[tuple[int, list[str]]] = []
    body: list[str] | None = None
    header = 0

    for index, line in enumerate(lines, 1):
        section = _is_section(line)
        if section is not None:
            if body is not None:
                found.append((header, body))
            if section == CHECK_SECTION:
                header, body = index, []
            else:
                header, body = 0, None
            continue
        if body is None:
            continue
        stripped = line.strip()
        if stripped:
            body.append(stripped)

    if body is not None:
        found.append((header, body))
    return found


def _reason_lines(lines: Sequence[str]) -> list[int]:
    """C6: return the lines of a ``BuildOption(check)`` without a reason.

    Only the first option of a group is judged. A consecutive
    ``BuildOption(check)`` block carries one reason above its first line,
    which is how every spec in the corpus satisfies the clause.
    """
    found: list[int] = []
    for index, line in enumerate(lines):
        match = RE_FIELD.match(line)
        if match is None:
            continue
        name = match.group(1)
        stage = (match.group(2) or '').strip().lower()
        if RE_BUILD_OPTION.match(name) is None or stage != CHECK_STAGE:
            continue
        previous = _previous_nonblank(lines, index)
        if previous is None:
            found.append(index + 1)
            continue
        above = lines[previous].lstrip()
        if above.startswith('#'):
            continue
        above_field = RE_FIELD.match(above)
        if (
            above_field is not None and
            RE_BUILD_OPTION.match(above_field.group(1)) is not None and
            (above_field.group(2) or '').strip().lower() == CHECK_STAGE
        ):
            continue
        found.append(index + 1)
    return found


def _check_macros_package(line: int, declared: set[str]) -> list[str]:
    """C1: a pyproject spec declares the pyproject macro package."""
    if MACROS_PACKAGE in declared:
        return []
    return [
        f'BuildSystem: {PYPROJECT} (line {line}) requires '
        f'"{MACROS_PACKAGE}" in BuildRequires; '
        f'missing "{MACROS_PACKAGE}"',
    ]


def _check_python_devel(
    line: int, declared: set[str], capabilities: set[str],
) -> list[str]:
    """C2: a pyproject spec declares a Python development dependency."""
    if any(name in capabilities for name in PYTHON_DEVEL_CAPABILITIES):
        return []
    if any(name in declared for name in PYTHON_DEVEL_PACKAGES):
        return []
    return [
        f'BuildSystem: {PYPROJECT} (line {line}) requires a Python '
        f'development dependency in BuildRequires; missing '
        f'{PYTHON_DEVEL_SPELLING}',
    ]


def _check_install_option(
    line: int, options: Sequence[tuple[str, int]], save_files: bool,
) -> list[str]:
    """C3: a pyproject spec passes the module name to the install stage."""
    if options or save_files:
        return []
    return [
        f'BuildSystem: {PYPROJECT} (line {line}) requires the module name '
        f'to install; neither BuildOption(install) nor '
        f'%pyproject_save_files is written',
    ]


def _check_install_option_module(
    options: Sequence[tuple[str, int]],
) -> list[int]:
    """C4: a ``BuildOption(install)`` carries at least one module name."""
    return [
        line for value, line in options if not _module_names(value)
    ]


def _check_spec_build_pyproject_ext(
    filename: str,
    *,
    check_macros_package: bool = True,
    check_python_devel: bool = True,
    check_install_option: bool = True,
    check_install_option_module: bool = True,
    check_check_section: bool = True,
    check_check_reason: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None
    if not (
        check_macros_package or check_python_devel or check_install_option or
        check_install_option_module or check_check_section or
        check_check_reason
    ):
        return []

    blocks = _blocks_of(lines)
    system_lines = _system_lines(blocks)
    if not system_lines:
        return []

    errors: list[str] = []
    if check_macros_package or check_python_devel:
        declared = _declared_everywhere(blocks)
        capabilities = _capabilities_everywhere(blocks)
        if check_macros_package:
            errors.extend(
                _check_macros_package(system_lines[0], declared),
            )
        if check_python_devel:
            errors.extend(
                _check_python_devel(
                    system_lines[0], declared, capabilities,
                ),
            )
    if check_install_option or check_install_option_module:
        options = _install_options(blocks)
        save_files = RE_SAVE_FILES.search('\n'.join(lines)) is not None
        if check_install_option:
            errors.extend(
                _check_install_option(system_lines[0], options, save_files),
            )
        if check_install_option_module:
            for line in _check_install_option_module(options):
                errors.append(
                    f'BuildOption(install) (line {line}) carries only '
                    f'options; the module name to install is missing',
                )
    if check_check_section:
        for line, body in _check_bodies(lines):
            if not body:
                errors.append(
                    f'%check (line {line}) is empty; a pyproject build '
                    f'runs a smoke test by default, so an empty %check '
                    f'skips the tests without a stated reason',
                )
    if check_check_reason:
        for line in _reason_lines(lines):
            errors.append(
                f'BuildOption(check) (line {line}) does not state the '
                f'reason for excluding modules; a comment line above it '
                f'is expected',
            )

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_build_pyproject(filename: str) -> list[str]:
    return _check_spec_build_pyproject_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the requirements of the pyproject build system.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-macros-package',
        action='store_true',
        help='do not report the pyproject macro package',
    )
    parser.add_argument(
        '--no-check-python-devel',
        action='store_true',
        help='do not report the Python development dependency',
    )
    parser.add_argument(
        '--no-check-install-option',
        action='store_true',
        help='do not report a missing BuildOption(install)',
    )
    parser.add_argument(
        '--no-check-install-option-module',
        action='store_true',
        help='do not report a BuildOption(install) without a module name',
    )
    parser.add_argument(
        '--no-check-check-section',
        action='store_true',
        help='do not report an empty %check section',
    )
    parser.add_argument(
        '--no-check-check-reason',
        action='store_true',
        help='do not report a BuildOption(check) without a reason',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_build_pyproject_ext(
            filename,
            check_macros_package=not args.no_check_macros_package,
            check_python_devel=not args.no_check_python_devel,
            check_install_option=not args.no_check_install_option,
            check_install_option_module=(
                not args.no_check_install_option_module
            ),
            check_check_section=not args.no_check_check_section,
            check_check_reason=not args.no_check_check_reason,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret
