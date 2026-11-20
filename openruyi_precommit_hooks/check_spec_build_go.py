"""Enforce the requirements of the golang and golangmodules build systems.

The Golang supplement of the packaging guidelines describes the two
declarative build systems for Go packages and states the dependencies and
the macros they need.

Section "Dependencies":

> If you need to use the "golang" or "golangmodules" build system, then you
> need to add these BuildRequires.
>
>     BuildRequires:  go
>     BuildRequires:  go-rpm-macros

Section "Which macros are needed":

> At least "_name" and "go_import_path" should be defined in the header.
> The former is usually the name of the Go library, the latter is usually
> the import path of the Go library.

Three checkpoints are implemented, and each one is anchored in one of those
two clauses:

* C1 is MUST level ("you need to add these BuildRequires") and reproduces
  the two dependencies the page names, both of them.
* C2 reports a spec that never defines the ``_name`` macro, or defines it
  after the first section instead of in the header.
* C3 does the same for the ``go_import_path`` macro.

Everything else the page says is deliberately out of scope, because the
page phrases it as advice rather than as a requirement:

* The shared ``%prep`` option ``BuildOption(prep): -n %{_name}-%{version}``
  is offered with "may be used directly", so a spec without it is legal.
  Most of the corpus passes a commit identifier instead of the version.
* ``BuildOption(check)`` only documents how to pass extra arguments to the
  test run the macros already perform; a hand-written ``%check`` that runs
  a specific test is a supported way to call into the other build system.
* The page explicitly allows calling into the other build system, so a
  ``golangmodules`` spec may carry its own ``%install`` and ``%check``, and
  a spec built by another system may call ``%go_common``.

No network access and no ``rpm`` invocation is performed, so the rule works
on a bare checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. A trailing parenthesised argument
# such as the stage of "BuildOption(build):" belongs to the field name
# rather than to the value, so the group is matched and dropped.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)(?:\(([^)]*)\))?\s*:\s*(.*)$')

# A section header. Section arguments ("%prep -a", "%check -a") are
# ignored.
RE_SECTION = re.compile(r'^%([a-z]\w*)\b')

# The field that switches the requirement on, and the field that satisfies
# it. Both are matched loosely so a misspelling reported by the dedicated
# rules still contributes its value here.
RE_BUILD_SYSTEM = re.compile(r'^build-?system$', re.IGNORECASE)
RE_BUILD_REQUIRES = re.compile(r'^build-?requires?$', re.IGNORECASE)

# A macro definition. The name is the first word of the body, so a value
# that continues on the next line does not hide it.
RE_DEFINE = re.compile(r'^%(?:define|global)\s+(\w+)(?=\s|$)')

# The dependency operators. A token that is exactly an operator consumes
# the token after it, which is the version of the dependency to its left.
RE_OPERATOR = re.compile(r'^(?:<=|>=|=|<|>)$')

# The two keywords that join two dependency names into one clause.
_JOINERS = frozenset({'with', 'without'})

# The closed set of real RPM sections, mirroring check-spec-basic-fields.
# Anything else that starts with "%" is a macro invocation (%license,
# %doc, %systemd_post, %autochangelog, ...) and must never be mistaken
# for a section.
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

# The two build systems this rule covers, spelled as the page spells them,
# and the two dependencies the page names for them.
GO_SYSTEMS: frozenset[str] = frozenset({'golang', 'golangmodules'})
REQUIRED_PACKAGES: tuple[str, ...] = ('go', 'go-rpm-macros')

# The macros the page asks for, and the clause that asks for them.
NAME_MACRO = '_name'
IMPORT_PATH_MACRO = 'go_import_path'


class _Block(NamedTuple):
    """One field block: the fields it holds, in file order.

    ``fields`` is a list of ``(spelling, stage, value, 1-based line)``
    tuples, where ``stage`` is the parenthesised argument of a field name
    or the empty string when the name carries none.
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

    The first block is the main preamble, kept even when it holds no
    field. Every ``%package`` opens a fresh block, so a subpackage that
    declares a build system of its own is judged against its own
    dependencies. A block ends at the first known section, so a macro
    invocation such as ``%global debug_package %{nil}`` neither ends a
    block nor hides the fields that follow it.
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
    version, or two names joined by a comma, ``with`` or ``without``. A
    rich dependency in parentheses is skipped entirely: its name is the
    capability it tests, so ``go(github.com/foo/bar)`` names a Go module
    and is not the ``go`` package the page asks for.
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


def _system_lines(blocks: Sequence[_Block]) -> list[tuple[int, str]]:
    """Return the line and name of every Go ``BuildSystem`` field."""
    found: list[tuple[int, str]] = []
    for block in blocks:
        for name, _stage, value, line in block.fields:
            if RE_BUILD_SYSTEM.match(name) is None:
                continue
            system = value.strip().lower()
            if system in GO_SYSTEMS:
                found.append((line, system))
    return found


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


def _check_buildrequires(
    line: int, system: str, declared: set[str],
) -> list[str]:
    """C1: a Go spec declares both Go build dependencies."""
    wanted = '" and "'.join(REQUIRED_PACKAGES)
    return [
        f'BuildSystem: {system} (line {line}) requires "{wanted}" in '
        f'BuildRequires; missing "{name}"'
        for name in REQUIRED_PACKAGES
        if name not in declared
    ]


def _first_section_line(lines: Sequence[str]) -> int:
    """Return the 1-based line of the first section, or one past the end."""
    for index, line in enumerate(lines, 1):
        if _is_section(line) is not None:
            return index
    return len(lines) + 1


def _definition_line(lines: Sequence[str], macro: str) -> int | None:
    """Return the 1-based line that defines the macro, or None."""
    wanted = macro.lower()
    for index, line in enumerate(lines, 1):
        if line.startswith('#'):
            continue
        match = RE_DEFINE.match(line)
        if match is None:
            continue
        if match.group(1).lower() == wanted:
            return index
    return None


def _check_header_macro(
    line: int, system: str, macro: str,
    defined: int | None, header_end: int,
) -> list[str]:
    """C2/C3: a Go spec defines the macro in the header."""
    if defined is None:
        return [
            f'BuildSystem: {system} (line {line}) requires the "{macro}" '
            f'macro in the header; no %define or %global sets it',
        ]
    if defined >= header_end:
        return [
            f'BuildSystem: {system} (line {line}) requires the "{macro}" '
            f'macro in the header; line {defined} defines it after the '
            f'first section',
        ]
    return []


def _check_spec_build_go_ext(
    filename: str,
    *,
    check_buildrequires: bool = True,
    check_name_macro: bool = True,
    check_import_path_macro: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None
    if not (
        check_buildrequires
        or check_name_macro
        or check_import_path_macro
    ):
        return []

    blocks = _blocks_of(lines)
    system_lines = _system_lines(blocks)
    if not system_lines:
        return []

    system_line, system = system_lines[0]
    header_end = _first_section_line(lines)
    errors: list[str] = []
    if check_buildrequires:
        declared = _declared_everywhere(blocks)
        errors.extend(
            _check_buildrequires(system_line, system, declared),
        )
    if check_name_macro:
        errors.extend(
            _check_header_macro(
                system_line, system, NAME_MACRO,
                _definition_line(lines, NAME_MACRO), header_end,
            ),
        )
    if check_import_path_macro:
        errors.extend(
            _check_header_macro(
                system_line, system, IMPORT_PATH_MACRO,
                _definition_line(lines, IMPORT_PATH_MACRO), header_end,
            ),
        )

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_build_go(filename: str) -> list[str]:
    return _check_spec_build_go_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the requirements of a golang build system.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-buildrequires',
        action='store_true',
        help='do not report missing Go build dependencies',
    )
    parser.add_argument(
        '--no-check-name-macro',
        action='store_true',
        help='do not report a missing _name macro',
    )
    parser.add_argument(
        '--no-check-import-path-macro',
        action='store_true',
        help='do not report a missing go_import_path macro',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_build_go_ext(
            filename,
            check_buildrequires=not args.no_check_buildrequires,
            check_name_macro=not args.no_check_name_macro,
            check_import_path_macro=not args.no_check_import_path_macro,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret
