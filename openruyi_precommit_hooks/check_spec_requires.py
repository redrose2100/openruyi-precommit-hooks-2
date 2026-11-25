"""Enforce the openRuyi Requires clauses of a spec file.

The packaging guidelines define the ``Requires`` group of fields in six
clauses:

1. ``Requires`` lists runtime dependencies, and those dependencies must be
   written one dependency package per line.
2. When a package needs no explicit runtime dependency, the spec may omit
   ``Requires``.
3. The absence of an explicit ``Requires`` does not exempt a package from
   declaring correct runtime dependencies; the automatic and the explicit
   mechanisms together must describe them.
4. ``Provides``, ``Recommends`` and ``Supplements`` may be used when the
   package needs to express the corresponding relationship.
5. A rename, a split or a migration must offer a seamless upgrade path
   through ``Provides`` and ``Obsoletes``.
6. ``Conflicts`` may be used for strict incompatibilities, with caution.

The layout section repeats clause 1 for both ``BuildRequires`` and
``Requires``, and the base field section places ``Requires`` after
``Recommends`` and before ``Supplements``. The ``SplitPackage`` sub-page
adds the only guidance that is specific to this field: a subpackage that
depends on the main package must pin it to the main package version, which
the page writes as ``%{name}%{?_isa} = %{version}-%{release}``, and it
recommends the ``%{?_isa}`` suffix so that a multilib resolver cannot pick
the wrong architecture.

The rule checks eight things, all of them statically:

* S1 - the field is spelled ``Requires``.
* S2 - the field declares at least one dependency.
* S3 - one field line declares exactly one dependency.
* S4 - one field block declares each ``Requires`` clause at most once.
* S5 - the field sits after ``Recommends`` and before ``Supplements``.
* S6 - the field sits inside the header field block.
* S7 - a subpackage pins the main package to the main package version.
* S8 - that pin names the architecture through ``%{?_isa}``.

S1 and S2 are the shape the field needs before any other clause can apply.
S3 is MUST clause 1. S4 compares the whole normalized clause together with
its scriptlet qualifier, so it reports a clause that is literally repeated
and stays silent when one dependency is bounded from both sides
(``foo >= 1`` next to ``foo < 2``), which is how RPM expresses a version
interval. The qualifier is part of the key because ``Requires: foo`` and
``Requires(post): foo`` are two different clauses and the repository relies
on that distinction to install a package for the scriptlet phase only; the
file format makes both spellings reach the same field name, so the rule
keeps them apart itself. A block that holds a conditional branch is exempt,
because a field may legitimately exist on one branch only. S5 rests on the
base field order section, which is SHOULD level. S6 follows S5: a field
written below the first section is outside the block that the order table
describes. S7 and S8 come from the sub-page's recommended rules, so both
are SHOULD level; S7 requires that the version and the release are both
named, because dropping the release lets a rebuild pair the subpackage with
a runtime library from an earlier build, which is exactly the mismatch the
sub-page wants to avoid.

Deliberately out of scope, each because the clause cannot be decided from
one file: clause 3 needs the package metadata or the installed payload, so
the rule never reports a missing runtime dependency; clause 5 needs the
history of a rename or a split, so the rule never asks for a ``Provides``
or an ``Obsoletes``; clause 6 asks for a judgement about whether a
``Conflicts`` is justified, which no static rule can make. The sub-page's
advice to filter a ``Provides`` or a ``Requires`` that an automatic
generator emits for a private ``.so`` is out of scope as well, because it
needs the file list of the built package and the generator output. The
sibling fields ``Provides``, ``Conflicts``, ``Obsoletes``, ``Recommends``
and ``Supplements`` are only ever read as position boundaries, so the rule
says nothing about their own spelling, shape or duplicates. S8 is skipped
for a spec that declares ``BuildArch: noarch``, because ``%{?_isa}``
expands to nothing there and the suffix would be dead text rather than an
architecture constraint. No network access and no ``rpm`` invocation is
performed, so the rule works on a bare checkout.

The position window is the adjacent pair of the order table rather than its
whole left-hand side, and the reason is a measurement rather than a
preference. The order table also places ``Requires`` after ``Provides``,
``Conflicts`` and ``Obsoletes``, but 10151 of the 10962 blocks that write
both ``Requires`` and ``Provides`` (2194 files) put ``Requires`` first:
8309 of them open a subpackage with ``Summary`` then ``Requires`` and only
then write ``Provides``. The repository therefore departs from the
documented order for that pair as a matter of convention, and a per-file
rule would fire on about a third of the corpus, which is a repository-level
migration decision rather than something a commit hook should block on.
The ``Recommends`` and ``Supplements`` pairs show the opposite picture - 87
blocks write ``Recommends`` and 72 of them order it wrongly, 18 write
``Supplements`` and 2 order it wrongly - which is the outlier shape a hook
is meant to catch, so the rule reports those. The same reasoning is why
S5 stays at SHOULD strength.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. The name is captured verbatim so that
# S1 can see the spelling the packager used. The parenthesised scriptlet
# stage of "Requires(post):" is captured on its own, because S4 has to tell
# "Requires: foo" apart from "Requires(post): foo" and both spellings share
# the field name once the stage is dropped.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)(?:\(([^)]*)\))?\s*:\s*(.*)$')

# A section header. Section arguments ("%pre -n foo", "%prep -a") are
# ignored. The closed whitelist below keeps macro invocations such as
# "%global" from ending a field block.
RE_SECTION = re.compile(r'^%([a-z]\w*)\b')

# A conditional branch or its terminator. A field may exist on one branch
# only, so a repeated dependency is legitimate here and S4 stays silent
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

# The field under check, matched loosely so that S1 can report a misspelling
# while S2 to S8 still see the value. The pattern accepts a missing plural
# and any case, which are the shapes that a typo of this field actually
# takes in practice, and it stays anchored so that "BuildRequires" is never
# read as this field.
RE_REQUIRES = re.compile(r'^requires?$', re.IGNORECASE)

# The start of a here-document. A spec that generates a file in a scriptlet
# writes its content through a here-document, and that content can hold
# lines that look exactly like a field of the spec, so the body is skipped
# whole. Both "<<EOF" and "<<-EOF" are matched, with or without quotes.
RE_HEREDOC = re.compile(r'<<-?\s*(["\']?)([A-Za-z_]\w*)\1')

# A dependency version operator. RPM accepts it glued to either neighbour,
# so a token that is exactly an operator joins the two tokens around it.
# "==" is accepted as well: RPM reads it as "=" and specs in the repository
# are written that way.
RE_OPERATOR = re.compile(r'^(?:<=|>=|==|=|<|>)$')

# The operators that constrain a dependency to one exact version.
_EXACT_OPERATORS = frozenset({'=', '=='})

# The operators that admit more than one version.
_RANGE_OPERATORS = frozenset({'<=', '>=', '<', '>'})

# The two keywords that join two dependency names into one clause.
_JOINERS = frozenset({'with', 'without'})

# The architecture suffix that the sub-page recommends.
RE_ISA_SUFFIX = re.compile(r'%\{\?_isa\}$')

# The macro names that carry the release part of a version pin.
_RELEASE_MACROS = ('%{release}', '%{?release}')

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

# The field under check and the two fields that bound its documented
# position window. The window is the adjacent pair from the order table
# rather than the whole left-hand side of it; the module docstring records
# why.
FIELD_NAME = 'Requires'
_AFTER_FIELDS = ('Recommends',)
_BEFORE_FIELDS = ('Supplements',)

# The documented relative order around Requires, quoted in the position
# message so that a reader can repair the spec without opening the
# guidelines.
ORDER_TEXT = 'Recommends -> Requires -> Supplements'

# The pin shape that the sub-page writes for a subpackage.
PIN_TEXT = f'{FIELD_NAME}: %{{name}}%{{?_isa}} = %{{version}}-%{{release}}'

# The value that makes a spec architecture independent.
_NOARCH = 'noarch'


class _Field(NamedTuple):
    """One field line: its spelling, its scriptlet stage and its value.

    ``qualifier`` is the empty string for a field written without a
    parenthesised stage, and the stage name otherwise. ``line`` is 1-based.
    """

    name: str
    qualifier: str
    value: str
    line: int


class _Block(NamedTuple):
    """One field block: where it starts, where it ends and what it holds.

    ``first_field`` and ``end`` are 0-based offsets into the file, ``end``
    being exclusive. ``first_field`` is ``None`` for a block that holds no
    field at all. ``conditional`` records whether the block holds a
    conditional branch.
    """

    first_field: int | None
    end: int
    conditional: bool
    fields: list[_Field]


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


def _heredoc_body(lines: list[str]) -> set[int]:
    """Return the 0-based indices of every line inside a here-document.

    The opening line is not part of the body, so a field written before the
    document still counts. An unterminated document swallows the rest of the
    file, which keeps the parse deterministic on a broken spec.
    """
    body: set[int] = set()
    index = 0
    while index < len(lines):
        match = RE_HEREDOC.search(lines[index])
        index += 1
        if match is None:
            continue
        marker = match.group(2)
        strip_tabs = '<<-' in match.group(0)
        while index < len(lines):
            line = lines[index]
            body.add(index)
            index += 1
            if (line.lstrip('\t') if strip_tabs else line).strip() == marker:
                break
    return body


def _blocks_of(lines: list[str]) -> list[_Block]:
    """Split the file into field blocks.

    The first block is the main preamble, kept even when it holds no field
    so that the subpackage blocks are distinguishable from it. Every
    ``%package`` opens a fresh block, because the documented relative field
    order also applies inside a subpackage definition. A block ends at the
    first known section other than ``%package``, so a macro invocation such
    as ``%global debug_package %{nil}`` neither ends a block nor hides the
    fields that follow it. A multi-line macro definition is skipped whole,
    because its body can carry field-shaped lines that belong to the macro
    rather than to the block. A here-document body is skipped for the same
    reason: a generated ``.pc`` file carries its own ``Requires:`` lines.
    """
    raw: list[tuple[int | None, int, bool, list[_Field]]] = []
    first_field: int | None = None
    fields: list[_Field] = []
    conditional = False
    ended = False
    macro_depth = 0
    heredoc = _heredoc_body(lines)

    for index, line in enumerate(lines):
        if index in heredoc:
            continue
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
        fields.append(
            _Field(
                match.group(1),
                match.group(2) or '',
                match.group(3).strip(),
                index + 1,
            ),
        )

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
    dependency, which is what S3 counts.
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


def _label(field: _Field) -> str:
    """Return how the finding names the field, including its stage."""
    if field.qualifier:
        return f'{FIELD_NAME}({field.qualifier})'
    return FIELD_NAME


def _find_requires(fields: list[_Field]) -> list[_Field]:
    """Return every field under check in one block."""
    return [f for f in fields if RE_REQUIRES.match(f.name) is not None]


def _field_lines(fields: list[_Field], name: str) -> list[int]:
    """Return the 1-based lines of every field with exactly this name."""
    return [f.line for f in fields if f.name == name]


def _main_name(blocks: list[_Block]) -> str | None:
    """Return the value of the spec's ``Name`` field, or None."""
    for field in blocks[0].fields:
        if field.name == 'Name' and field.value:
            return field.value
    return None


def _is_noarch(blocks: list[_Block]) -> bool:
    """Return whether any block declares ``BuildArch: noarch``."""
    for block in blocks:
        for field in block.fields:
            if field.name != 'BuildArch':
                continue
            if field.value.strip().lower() == _NOARCH:
                return True
    return False


def _check_field_case(requires: list[_Field]) -> list[str]:
    """S1: the field is spelled ``Requires``."""
    errors: list[str] = []
    for field in requires:
        if field.name == FIELD_NAME:
            continue
        errors.append(
            f'{_label(field)} field (line {field.line}) is spelled '
            f'"{field.name}"; write "{FIELD_NAME}"',
        )
    return errors


def _check_value(field: _Field) -> list[str]:
    """S2: the field declares at least one dependency."""
    if field.value:
        return []
    return [
        f'{_label(field)} (line {field.line}) declares no dependency; '
        'write one dependency per line',
    ]


def _check_one_per_line(field: _Field) -> list[str]:
    """S3: one field line declares exactly one dependency."""
    names = _dependency_names(field.value)
    if len(names) <= 1:
        return []
    return [
        f'{_label(field)} (line {field.line}) declares {len(names)} '
        'dependencies; write one dependency per line',
    ]


def _check_duplicate(requires: list[_Field]) -> list[str]:
    """S4: one field block declares each clause at most once.

    The comparison key is the scriptlet stage together with the whole
    normalized clause. The stage belongs to the key because
    ``Requires(post): foo`` adds ``foo`` to the scriptlet transaction only
    and is a different statement from ``Requires: foo``. The whole clause
    belongs to the key because one dependency bounded from both sides is a
    version interval written as two lines, so comparing bare names would
    report every interval as a duplicate.
    """
    errors: list[str] = []
    seen: dict[tuple[str, str], int] = {}
    for field in requires:
        clause = ' '.join(field.value.split())
        if not clause:
            continue
        key = (field.qualifier.lower(), clause)
        first = seen.get(key)
        if first is None:
            seen[key] = field.line
            continue
        errors.append(
            f'{_label(field)} "{clause}" (line {field.line}) is already '
            f'declared at line {first}; remove the duplicate',
        )
    return errors


def _check_position(block: _Block, requires: list[_Field]) -> list[str]:
    """S5: the field sits between ``Recommends`` and ``Supplements``.

    A boundary that the block never writes is not reported: the order table
    constrains the relative position of two present fields, so a spec that
    writes neither is silent. ``Requires`` is commonly repeated on one line
    per dependency, so the window opens on the first line of the field and
    closes on the last. The window is the adjacent pair of the order table,
    and the module docstring records the measurement behind that choice.
    """
    errors: list[str] = []
    first = requires[0].line
    last = requires[-1].line

    for name in _AFTER_FIELDS:
        lines = _field_lines(block.fields, name)
        if not lines:
            continue
        boundary = max(lines)
        if first < boundary:
            errors.append(
                f'{FIELD_NAME} (line {first}) must be written after {name} '
                f'(line {boundary}); write the fields in the order '
                f'{ORDER_TEXT}',
            )

    for name in _BEFORE_FIELDS:
        lines = _field_lines(block.fields, name)
        if not lines:
            continue
        boundary = min(lines)
        if last > boundary:
            errors.append(
                f'{FIELD_NAME} (line {last}) must be written before {name} '
                f'(line {boundary}); write the fields in the order '
                f'{ORDER_TEXT}',
            )
    return errors


def _check_outside_block(lines: list[str]) -> list[str]:
    """S6: the field sits inside the header field block.

    A field written below the first body section belongs to no field block,
    so the order table cannot describe it. The walk mirrors ``_blocks_of``,
    including its macro skip, so a field-shaped line inside a macro body is
    not mistaken for a field of the spec.
    """
    errors: list[str] = []
    inside_body = False
    macro_depth = 0
    heredoc = _heredoc_body(lines)

    for index, line in enumerate(lines):
        if index in heredoc:
            continue
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
        if RE_REQUIRES.match(match.group(1)) is None:
            continue
        errors.append(
            f'{FIELD_NAME} (line {index + 1}) is written outside the '
            'header field block; write it before the first section',
        )
    return errors


def _targets_main(value: str, main_name: str | None) -> bool:
    """Return whether the line requires the main package itself.

    Only the literal main name and the ``%{name}`` macro are recognised.
    A subpackage name such as ``%{name}-devel`` names a different package
    and is not a dependency on the main one, so it never matches.
    """
    for dependency in _dependency_names(value):
        name = RE_ISA_SUFFIX.sub('', dependency)
        if main_name is not None and name == main_name:
            return True
        if name == '%{name}':
            return True
    return False


def _is_exact_pin(value: str) -> bool:
    """Return whether the clause pins the exact version and release."""
    tokens = value.split()
    if not any(token in _EXACT_OPERATORS for token in tokens):
        return False
    if any(token in _RANGE_OPERATORS for token in tokens):
        return False
    return any(macro in value for macro in _RELEASE_MACROS)


def _check_main_pin(
    requires: list[_Field],
    main_name: str | None,
) -> list[str]:
    """S7: a subpackage pins the main package to its version and release."""
    errors: list[str] = []
    for field in requires:
        if not _targets_main(field.value, main_name):
            continue
        if _is_exact_pin(field.value):
            continue
        errors.append(
            f'{_label(field)} "{field.value}" (line {field.line}) does not '
            'pin the main package to its version and release; write '
            f'"{PIN_TEXT}"',
        )
    return errors


def _check_main_isa(
    requires: list[_Field],
    main_name: str | None,
) -> list[str]:
    """S8: the pin on the main package names the architecture.

    A clause that already fails S7 is skipped, because a clause that pins
    nothing has to be rewritten anyway and reporting the same line twice
    tells the packager nothing new.
    """
    errors: list[str] = []
    for field in requires:
        if not _targets_main(field.value, main_name):
            continue
        if not _is_exact_pin(field.value):
            continue
        if '%{?_isa}' in field.value:
            continue
        errors.append(
            f'{_label(field)} "{field.value}" (line {field.line}) does not '
            'constrain the architecture of the main package; write '
            f'"{PIN_TEXT}"',
        )
    return errors


def _check_spec_requires_ext(
    filename: str,
    *,
    check_field_case: bool = True,
    check_value: bool = True,
    check_one_per_line: bool = True,
    check_duplicate: bool = True,
    check_position: bool = True,
    check_main_pin: bool = True,
    check_main_isa: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    blocks = _blocks_of(lines)
    main_name = _main_name(blocks)
    noarch = _is_noarch(blocks)

    errors: list[str] = []
    for index, block in enumerate(blocks):
        requires = _find_requires(block.fields)
        if not requires:
            continue
        if check_field_case:
            errors.extend(_check_field_case(requires))
        if check_value:
            for field in requires:
                errors.extend(_check_value(field))
        if check_one_per_line:
            for field in requires:
                errors.extend(_check_one_per_line(field))
        if check_duplicate and not block.conditional:
            errors.extend(_check_duplicate(requires))
        if check_position:
            errors.extend(_check_position(block, requires))
        if index == 0:
            continue
        if check_main_pin:
            errors.extend(_check_main_pin(requires, main_name))
        if check_main_isa and not noarch:
            errors.extend(_check_main_isa(requires, main_name))

    if check_position:
        errors.extend(_check_outside_block(lines))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_requires(filename: str) -> list[str]:
    return _check_spec_requires_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the Requires field of openRuyi spec files.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-field-case',
        action='store_true',
        help='do not report a Requires field whose spelling differs',
    )
    parser.add_argument(
        '--no-check-value',
        action='store_true',
        help='do not report a Requires field that declares nothing',
    )
    parser.add_argument(
        '--no-check-one-per-line',
        action='store_true',
        help='do not report a field line that declares several dependencies',
    )
    parser.add_argument(
        '--no-check-duplicate',
        action='store_true',
        help='do not report a clause declared twice in one field block',
    )
    parser.add_argument(
        '--no-check-position',
        action='store_true',
        help='do not report a misplaced Requires field',
    )
    parser.add_argument(
        '--no-check-main-pin',
        action='store_true',
        help='do not report a subpackage that does not pin the main package',
    )
    parser.add_argument(
        '--no-check-main-isa',
        action='store_true',
        help='do not report a pin that omits the %%{?_isa} suffix',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_requires_ext(
            filename,
            check_field_case=not args.no_check_field_case,
            check_value=not args.no_check_value,
            check_one_per_line=not args.no_check_one_per_line,
            check_duplicate=not args.no_check_duplicate,
            check_position=not args.no_check_position,
            check_main_pin=not args.no_check_main_pin,
            check_main_isa=not args.no_check_main_isa,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret


if __name__ == '__main__':
    raise SystemExit(main())
