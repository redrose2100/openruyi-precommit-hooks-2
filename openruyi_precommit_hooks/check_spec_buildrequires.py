"""Enforce the openRuyi BuildRequires clauses of a spec file.

The packaging guidelines define the ``BuildRequires`` field in seven
clauses:

1. Every build-time dependency must be declared, either statically through
   ``BuildRequires``, through the dynamic build dependency generator, or
   through both.
2. When the dynamic generator is used, the static field must still hold the
   dependencies needed to run the generator plus any dependency the
   generator cannot produce.
3. When the base build environment plus the generated dependencies are
   enough, the static field may be omitted; for instance a plain C program
   usually does not declare ``gcc``.
4. Static ``BuildRequires`` must be written one dependency per line.
5. The base build environment is whatever the build configuration provides
   before the build starts, and the preinstall image is its authority.
6. A spec must not drop a dependency just because the current build root
   happens to contain it.
7. A dependency discovered through ``pkg-config`` should be declared as
   ``pkgconfig(xxx)`` rather than as ``xxx-devel``.

The ``PkgConfigBuildRequires`` sub-page elaborates clause 7: the declaration
should name the pkg-config module so that the dependency survives a package
rename, and its example contrasts ``pkgconfig(openssl)`` with the discouraged
``openssl-devel``. The layout section repeats clause 4 for both
``BuildRequires`` and ``Requires``, and the base field section places
``BuildRequires`` after ``BuildOption`` and before ``Provides``.

The rule checks seven things, all of them statically:

* R1 - the field is spelled ``BuildRequires``.
* R2 - the field declares at least one dependency.
* R3 - one field line declares exactly one dependency.
* R4 - one field block declares each dependency clause at most once.
* R5 - the field sits after ``BuildSystem`` and ``BuildOption``, and before
  ``Provides``.
* R6 - the field sits inside the header field block.
* R7 - a ``pkgconfig(...)`` declaration names a bare module.

R3 is MUST clause 4. R1 and R2 are the shape the field needs before any
other clause can apply, and the sub-page's example spells the field that
way. R4 compares the whole normalized clause, so it reports a clause that is
literally repeated and stays silent when one dependency is bounded from both
sides (``foo >= 1`` next to ``foo < 2``), which is how RPM expresses a
version interval; a repeated clause adds no constraint at all, so the check
is a statement about redundant spec data rather than about style. A block
that holds a conditional branch is exempt, because a field may legitimately
exist on one branch only. R5 rests on the base field order section and on
the layout section, both of which are SHOULD level. R6 follows R5: a field
written below the first section is outside the block that the order table
describes. R7 is the statically decidable part of clause 7: the module
argument of ``pkgconfig(...)`` is a literal name, so an empty, padded, or
``-devel``-suffixed module is reported without needing to know anything about
the upstream recipe.

Deliberately out of scope, each because the clause cannot be decided from one
file: clauses 1, 2, 5 and 6 need the build root, the preinstall image manifest
or the generator output, so the rule never reports a missing dependency;
clause 3 makes the field optional, so an absent field is never a finding;
clause 7 as a whole asks whether the upstream build recipe uses
``pkg-config``, which needs the upstream sources, so the rule never asks a
packager to convert a ``-devel`` declaration that stands alone. Two
tempting checks are also left out. Reporting a ``-devel`` package that a
block already requires through ``pkgconfig(...)`` would be wrong, because the
two forms are not interchangeable: ``python3-devel`` ships build macros and
headers that ``pkgconfig(python3)`` does not, and the repository has specs
that legitimately declare both. Reporting every ``-devel`` declaration whose
name looks like a pkg-config module would be wrong too, for the same reason
plus the need for repository metadata to know which module the package
ships. No network access and no ``rpm`` invocation is performed, so the rule
works on a bare checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. The name is captured verbatim so that
# R1 can see the spelling the packager used. A trailing parenthesised
# argument such as the stage of "BuildOption(build):" belongs to the field
# name rather than to the value, and RPM uses the same shape for
# "Requires(post):", so the group is matched and dropped.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)(?:\([^)]*\))?\s*:\s*(.*)$')

# A section header. Section arguments ("%pre -n foo", "%prep -a") are
# ignored. The closed whitelist below keeps macro invocations such as
# "%global" from ending a field block.
RE_SECTION = re.compile(r'^%([a-z]\w*)\b')

# A conditional branch or its terminator. A field may exist on one branch
# only, so a repeated dependency is legitimate here and R4 stays silent
# inside such a block.
RE_CONDITIONAL = re.compile(
    r'^%(?:if|ifarch|ifnarch|ifos|ifnos|else|elif|endif)\b',
)

# A macro definition or a directive that never carries a field of the spec.
# A definition can span several lines ("%global foo %{expand:" ... "}"), so
# the brace balance of the opening line decides how far the skip reaches.
RE_DIRECTIVE = re.compile(
    r'^%(?:end|global|define|bcond|undefine|dnl)\b',
)

# The field under check, matched loosely so that R1 can report a misspelling
# while R2 to R7 still see the value. The pattern accepts a missing plural, a
# hyphenated spelling and any case, which are the shapes that a typo of this
# field actually takes in practice; a name that shares no such shape is
# indistinguishable from a different field and is left alone.
RE_BUILD_REQUIRES = re.compile(r'^build-?requires?$', re.IGNORECASE)

# A dependency version operator. RPM accepts it glued to either neighbour,
# so a token that is exactly an operator joins the two tokens around it.
RE_OPERATOR = re.compile(r'^(?:<=|>=|=|<|>)$')

# The two keywords that join two dependency names into one clause.
_JOINERS = frozenset({'with', 'without'})

# A "pkgconfig(module)" declaration. The module is captured verbatim so
# that R7 can judge its shape. The syntax has no nested parentheses, so the
# capture runs from the first "(" to the last ")".
RE_PKGCONFIG = re.compile(r'^pkgconfig\((.*)\)$', re.IGNORECASE)

# The suffix of an RPM development subpackage.
_DEVEL_SUFFIX = '-devel'

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

# The section that opens a new field block.
_BLOCK_SECTION = '%package'

# The field under check and the three fields that bound its documented
# position window.
FIELD_NAME = 'BuildRequires'
BUILD_SYSTEM_FIELD = 'BuildSystem'
BUILD_OPTION_FIELD = 'BuildOption'
PROVIDES_FIELD = 'Provides'

# The documented relative order of the fields around BuildRequires, quoted
# in the position message so that a reader can repair the spec without
# opening the guidelines.
ORDER_TEXT = (
    f'{BUILD_SYSTEM_FIELD} -> {BUILD_OPTION_FIELD} -> '
    f'{FIELD_NAME} -> {PROVIDES_FIELD}'
)


class _Block(NamedTuple):
    """One field block: where it starts, where it ends and what it holds.

    ``first_field`` and ``end`` are 0-based offsets into the file, ``end``
    being exclusive. ``first_field`` is ``None`` for a block that holds no
    field at all. ``conditional`` records whether the block holds a
    conditional branch. Each field is ``(spelling, value, 1-based line)``.
    """

    first_field: int | None
    end: int
    conditional: bool
    fields: list[tuple[str, str, int]]


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
    """Return the macro nesting depth after consuming one line.

    Inside a definition the depth follows the brace balance of the body.
    On the opening line of a definition it starts at whatever the line
    leaves unclosed, so ``%global foo bar`` opens nothing and
    ``%global foo %{expand:`` opens a block that the following lines close.
    """
    depth += line.count('{') - line.count('}')
    return depth if depth > 0 else 0


def _blocks_of(lines: list[str]) -> list[_Block]:
    """Split the file into field blocks.

    The first block is the main preamble, kept even when it holds no field
    so that the subpackage block numbers stay meaningful. Every ``%package``
    opens a fresh block, because the documented relative field order also
    applies inside a subpackage definition. A block ends at the first known
    section, so a macro invocation such as ``%global debug_package %{nil}``
    neither ends a block nor hides the fields that follow it. A multi-line
    macro definition is skipped whole, because its body can carry
    field-shaped lines that belong to the macro rather than to the block.
    """
    raw: list[tuple[int | None, int, bool, list[tuple[str, str, int]]]] = []
    first_field: int | None = None
    fields: list[tuple[str, str, int]] = []
    conditional = False
    ended = False
    macro_depth = 0

    for index, line in enumerate(lines):
        if macro_depth > 0:
            macro_depth = _macro_depth_after(line, macro_depth)
            continue
        if RE_DIRECTIVE.match(line) is not None:
            macro_depth = _macro_depth_after(line, 0)
            continue
        section = _is_section(line)
        if section is not None:
            if section == _BLOCK_SECTION:
                raw.append((first_field, index, conditional, fields))
                first_field = None
                fields = []
                conditional = False
                ended = False
                continue
            if not ended:
                raw.append((first_field, index, conditional, fields))
                first_field = None
                fields = []
                conditional = False
                ended = True
            continue
        if RE_CONDITIONAL.match(line) is not None:
            conditional = True
            continue
        if ended:
            continue
        if line.lstrip().startswith('#'):
            continue
        match = RE_FIELD.match(line)
        if match is None:
            continue
        if first_field is None:
            first_field = index
        fields.append((match.group(1), match.group(2).strip(), index + 1))

    if not ended:
        raw.append((first_field, len(lines), conditional, fields))

    # Keep the main preamble even when empty; drop empty subpackage blocks
    # so that the block indices stay contiguous.
    if raw:
        blocks = [_Block(*raw[0])]
    else:
        blocks = [_Block(None, len(lines), False, [])]
    blocks.extend(_Block(*item) for item in raw[1:] if item[3])
    return blocks


def _dependency_names(value: str) -> list[str]:
    """Return the name of every dependency clause on one field line.

    A clause is a name optionally followed by a version operator and a
    version, or one rich dependency in parentheses, or two names joined by
    ``with`` / ``without``. The returned list therefore has one entry per
    dependency, which is what R3 and R4 count.
    """
    names: list[str] = []
    rich: list[str] = []
    skip_next = False
    for token in value.split():
        if rich:
            rich.append(token)
            if sum(t.count('(') - t.count(')') for t in rich) <= 0:
                names.append(' '.join(rich))
                rich = []
            continue
        if token.count('(') > token.count(')'):
            rich = [token]
            continue
        if RE_OPERATOR.match(token) is not None:
            skip_next = True
            continue
        if token.lower() in _JOINERS:
            skip_next = True
            continue
        if skip_next:
            skip_next = False
            continue
        names.append(token)
    if rich:
        names.append(' '.join(rich))
    return names


def _find_build_requires(
    fields: list[tuple[str, str, int]],
) -> list[tuple[str, str, int]]:
    """Return every ``BuildRequires`` field as (spelling, value, line)."""
    return [
        (name, value, line)
        for name, value, line in fields
        if RE_BUILD_REQUIRES.match(name) is not None
    ]


def _find_field_lines(
    fields: list[tuple[str, str, int]],
    name: str,
) -> list[int]:
    """Return the 1-based lines of every field with exactly this name."""
    return [line for field, _value, line in fields if field == name]


def _check_field_case(
    requires: list[tuple[str, str, int]],
) -> list[str]:
    """R1: the field is spelled ``BuildRequires``."""
    errors: list[str] = []
    for name, _value, line in requires:
        if name == FIELD_NAME:
            continue
        errors.append(
            f'BuildRequires field (line {line}) is spelled "{name}"; '
            f'write "{FIELD_NAME}"',
        )
    return errors


def _check_value(value: str, line: int) -> list[str]:
    """R2: the field declares at least one dependency."""
    if value:
        return []
    return [
        f'BuildRequires (line {line}) declares no dependency; write one '
        'dependency per line',
    ]


def _check_one_per_line(value: str, line: int) -> list[str]:
    """R3: one field line declares exactly one dependency."""
    names = _dependency_names(value)
    if len(names) <= 1:
        return []
    return [
        f'BuildRequires (line {line}) declares {len(names)} dependencies; '
        'write one dependency per line',
    ]


def _check_duplicate(
    requires: list[tuple[str, str, int]],
) -> list[str]:
    """R4: one field block declares each dependency clause at most once.

    The comparison key is the whole normalized clause, not the bare name.
    One dependency bounded from both sides is a version interval and is
    written as two lines, so comparing names would report every interval as
    a duplicate. Only a clause that is literally repeated is reported.
    """
    errors: list[str] = []
    seen: dict[str, int] = {}
    for _name, value, line in requires:
        clause = ' '.join(value.split())
        if not clause:
            continue
        first = seen.get(clause)
        if first is None:
            seen[clause] = line
            continue
        errors.append(
            f'BuildRequires "{clause}" (line {line}) is already declared at '
            f'line {first}; remove the duplicate',
        )
    return errors


def _check_position(
    block: _Block,
    requires: list[tuple[str, str, int]],
) -> list[str]:
    """R5: the field sits between the builders and ``Provides``.

    A boundary that the block never writes is not reported: the order table
    constrains the relative position of two present fields, so a spec that
    writes neither is silent. ``BuildRequires`` is commonly repeated on one
    line per dependency, so the window opens on the first line of the field
    and closes on the last.
    """
    errors: list[str] = []
    first = requires[0][2]
    last = requires[-1][2]

    for field in (BUILD_SYSTEM_FIELD, BUILD_OPTION_FIELD):
        lines = _find_field_lines(block.fields, field)
        if not lines:
            continue
        boundary = max(lines)
        if first < boundary:
            errors.append(
                f'BuildRequires (line {first}) must be written after '
                f'{field} (line {boundary}); write the fields in the order '
                f'{ORDER_TEXT}',
            )

    provides = _find_field_lines(block.fields, PROVIDES_FIELD)
    if provides:
        boundary = min(provides)
        if last > boundary:
            errors.append(
                f'BuildRequires (line {last}) must be written before '
                f'Provides (line {boundary}); write the fields in the order '
                f'{ORDER_TEXT}',
            )
    return errors


def _check_outside_block(lines: list[str]) -> list[str]:
    """R6: the field sits inside the header field block.

    A field written below the first body section belongs to no field block,
    so the order table cannot describe it. The walk mirrors ``_blocks_of``,
    including its macro skip, so a field-shaped line inside a macro body is
    not mistaken for a field of the spec.
    """
    errors: list[str] = []
    inside_body = False
    macro_depth = 0

    for index, line in enumerate(lines):
        if macro_depth > 0:
            macro_depth = _macro_depth_after(line, macro_depth)
            continue
        if RE_DIRECTIVE.match(line) is not None:
            macro_depth = _macro_depth_after(line, 0)
            continue
        section = _is_section(line)
        if section is not None:
            inside_body = section != _BLOCK_SECTION
            continue
        if not inside_body:
            continue
        match = RE_FIELD.match(line)
        if match is None:
            continue
        if RE_BUILD_REQUIRES.match(match.group(1)) is None:
            continue
        errors.append(
            f'BuildRequires (line {index + 1}) is written outside the '
            'header field block; write it before the first section',
        )
    return errors


def _check_pkgconfig_shape(
    requires: list[tuple[str, str, int]],
) -> list[str]:
    """R7: a ``pkgconfig(...)`` declaration names a bare module."""
    errors: list[str] = []
    for _name, value, line in requires:
        for dependency in _dependency_names(value):
            match = RE_PKGCONFIG.match(dependency)
            if match is None:
                continue
            module = match.group(1)
            if not module:
                errors.append(
                    f'pkgconfig module (line {line}) is empty; write '
                    '"pkgconfig(<module>)"',
                )
                continue
            if ' ' in module or module != module.strip():
                errors.append(
                    f'pkgconfig module "{module}" (line {line}) carries '
                    'extra spacing; write "pkgconfig(<module>)" and put a '
                    'version constraint after it',
                )
                continue
            if module.lower().endswith(_DEVEL_SUFFIX):
                errors.append(
                    f'pkgconfig module "{module}" (line {line}) ends with '
                    f'"{_DEVEL_SUFFIX}"; write the pkg-config module name',
                )
    return errors


def _check_spec_buildrequires_ext(
    filename: str,
    *,
    check_field_case: bool = True,
    check_value: bool = True,
    check_one_per_line: bool = True,
    check_duplicate: bool = True,
    check_position: bool = True,
    check_pkgconfig: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    errors: list[str] = []
    for block in _blocks_of(lines):
        requires = _find_build_requires(block.fields)
        if not requires:
            continue
        if check_field_case:
            errors.extend(_check_field_case(requires))
        if check_value:
            for _name, value, line in requires:
                errors.extend(_check_value(value, line))
        if check_one_per_line:
            for _name, value, line in requires:
                errors.extend(_check_one_per_line(value, line))
        if check_duplicate and not block.conditional:
            errors.extend(_check_duplicate(requires))
        if check_position:
            errors.extend(_check_position(block, requires))
        if check_pkgconfig:
            errors.extend(_check_pkgconfig_shape(requires))
    if check_position:
        errors.extend(_check_outside_block(lines))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_buildrequires(filename: str) -> list[str]:
    return _check_spec_buildrequires_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the BuildRequires field of openRuyi spec files.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-field-case',
        action='store_true',
        help='do not report a BuildRequires field whose spelling differs',
    )
    parser.add_argument(
        '--no-check-value',
        action='store_true',
        help='do not report a BuildRequires field that declares nothing',
    )
    parser.add_argument(
        '--no-check-one-per-line',
        action='store_true',
        help='do not report a field line that declares several dependencies',
    )
    parser.add_argument(
        '--no-check-duplicate',
        action='store_true',
        help='do not report a dependency declared twice in one field block',
    )
    parser.add_argument(
        '--no-check-position',
        action='store_true',
        help='do not report a misplaced BuildRequires field',
    )
    parser.add_argument(
        '--no-check-pkgconfig',
        action='store_true',
        help='do not report a malformed pkgconfig declaration',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_buildrequires_ext(
            filename,
            check_field_case=not args.no_check_field_case,
            check_value=not args.no_check_value,
            check_one_per_line=not args.no_check_one_per_line,
            check_duplicate=not args.no_check_duplicate,
            check_position=not args.no_check_position,
            check_pkgconfig=not args.no_check_pkgconfig,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret


if __name__ == '__main__':
    raise SystemExit(main())
