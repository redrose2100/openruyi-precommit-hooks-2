"""Enforce the openRuyi BuildOption clauses of a spec file.

The packaging guidelines define ``BuildOption`` in two places: the
``BuildOption (optional)`` section of the main guidelines and the
``Passing extra arguments`` subsection of the ``BuildSystems`` supplement.
Together they supply seven checkpoints:

* B1 - the field is spelled ``BuildOption``.
* B2 - the stage argument is present.
* B3 - the stage is one bare lowercase token.
* B4 - exactly two spaces separate the colon from the argument.
* B5 - the argument is present.
* B6 - the field sits in a header field block, after ``BuildSystem`` and
  before ``BuildRequires``.
* B7 - the stages follow the order of the RPM build process.

The strength of the underlying wording differs, so each checkpoint names
its source:

* B1 rests on the section title and on every sample line of both pages,
  which spell the field as one word. No clause says so explicitly, the
  same way that ``BuildSystem`` and ``BuildArch`` have no spelling clause.
* B2 is strong. The main guidelines write the field as
  ``BuildOption(<stage>):`` in clause 1, and the supplement adds that the
  stage name is syntactically omissible but that packagers are required to
  write it out.
* B3 rests on the ``<stage>`` placeholder of the syntax line. A stage is a
  section name, so the value cannot be an expression.
* B4 and B5 are MUST level. Clause 2 says that the colon and the argument
  must be separated by two spaces, and clause 3 requires every argument to
  be declared, so a missing tail is a defect rather than a style choice.
* B6 is SHOULD level. Clause 4 says that the field should sit between
  ``BuildSystem`` and ``BuildRequires``, and the base field relative order
  list of the same page repeats that window.
* B7 is SHOULD level. Clause 5 says that the writing order should follow
  the RPM build process, and its sample lists ``%build``, then
  ``%install``, then ``%check``. The ``Patch`` supplement documents
  ``BuildOption(prep)``, which runs before ``%conf``, so the rule ranks
  ``prep`` ahead of ``conf``.

Deliberately out of scope, each because the clause does not reach it or
because the judgement is not static. Clause 3 says that multiple arguments
must be declared on separate lines, but one argument is routinely written
as a flag plus its value (``-G Ninja``), as an assignment
(``CFLAGS="%{optflags} -fno-strict-aliasing"``), or as a command
substitution (``--with-gssapi=$(krb5-config --prefix)``), and the official
sample of the supplement itself writes ``BuildOption(build):  all info
html``, so splitting a line into arguments needs the option grammar of the
individual build system. The rule therefore never counts arguments per line
and never asks for one token per line. Whether an option is valid for its
stage, whether it duplicates another option, whether the argument needs
shell quoting, and whether the option belongs to the declared
``BuildSystem`` all need the build recipe or the build environment. The
stage set is open: the guidelines document ``conf``, ``build``,
``install`` and ``check``, the ``Patch`` supplement documents ``prep``, and
RPM adds stages such as ``generate_buildrequires``, so B3 checks the shape
of the stage and B7 only ranks the documented stages instead of rejecting
an unknown one. Duplicate declarations are legal: the supplement says that
the field may appear any number of times for one stage. No network access
and no ``rpm`` invocation is performed, so the rule works on a bare
checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# A "BuildOption" line, optionally carrying a parenthesised stage. The name
# is matched in any case so that B1 can report a misspelling, and the text
# after the colon is captured verbatim so that B4 can inspect the exact
# separator in front of the argument. Only a column zero field is matched,
# mirroring the sibling rules: an indented mention inside a section body or
# a prose line of "%description" is not a field.
RE_BUILD_OPTION = re.compile(
    r'^(?P<name>BuildOption\w*)'
    r'(?:\((?P<stage>[^)]*)\))?'
    r':(?P<rest>.*)$',
    re.IGNORECASE,
)

# Any top-level "Field: value" line. A "BuildOption(<stage>):" line does not
# match, because its name is followed by a parenthesis rather than a colon,
# so the two patterns never compete for the same line.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)\s*:\s*(.*)$')

# A section header. Section arguments ("%prep -a", "%conf -p") are ignored.
# The closed whitelist below keeps macro invocations such as "%global" and
# "%if" from ending a field block.
RE_SECTION = re.compile(r'^%([a-z]\w*)\b')

# The whitespace run in front of the argument.
RE_SEPARATOR = re.compile(r'[ \t]*')

# One bare lowercase stage token: "conf", "build", "install", "check",
# "prep", "generate_buildrequires".
RE_STAGE_TOKEN = re.compile(r'^[a-z][a-z0-9_]*$')

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

# The field under check, and the two fields that bound its documented
# position window.
FIELD_NAME = 'BuildOption'
BUILD_SYSTEM_FIELD = 'BuildSystem'
BUILD_REQUIRES_FIELD = 'BuildRequires'

# The documented separator between the colon and the argument.
EXPECTED_SEPARATOR = '  '

# The documented rank of each documented build stage, in the order of the
# RPM build process. "prep" runs before "conf" and is documented by the
# Patch supplement as the stage of a strip level override. A stage outside
# this table is shape checked by B3 but is not ranked by B7, because the
# guidelines only fix the order of the stages they name.
STAGE_RANK: dict[str, int] = {
    'prep': 0,
    'conf': 1,
    'build': 2,
    'install': 3,
    'check': 4,
}

# The ranked stages in their documented order, for the finding messages.
STAGE_ORDER_TEXT = ' -> '.join(STAGE_RANK)


class _Option(NamedTuple):
    """One ``BuildOption`` line.

    ``offset`` is a 0-based offset into the file and ``line`` is 1-based.
    ``stage`` is ``None`` when the parenthesis is missing. ``separator`` is
    the exact whitespace run in front of the argument and ``value`` is the
    argument with its surrounding whitespace removed.
    """

    offset: int
    line: int
    spelling: str
    stage: str | None
    separator: str
    value: str


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


def _blocks_of(lines: list[str]) -> list[tuple[int, int]]:
    """Split the file into field block ranges, as 0-based half-open spans.

    The main preamble is always the first block, even when it holds no
    field, so that a spec without a subpackage still has one block. Every
    ``%package`` opens a fresh block, because a subpackage carries its own
    ``BuildSystem``, ``BuildRequires`` and ``BuildOption`` window. A block
    ends at the next known section, so a macro invocation such as
    ``%global debug_package %{nil}`` neither ends a block nor hides the
    fields that follow it.
    """
    marks: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        section = _is_section(line)
        if section is not None:
            marks.append((index, section))

    blocks = [(0, marks[0][0] if marks else len(lines))]
    for position, (index, section) in enumerate(marks):
        if section != _BLOCK_SECTION:
            continue
        if position + 1 < len(marks):
            end = marks[position + 1][0]
        else:
            end = len(lines)
        blocks.append((index, end))
    return blocks


def _block_at(
    blocks: list[tuple[int, int]],
    index: int,
) -> tuple[int, int] | None:
    """Return the block span that holds this line, or None."""
    for start, end in blocks:
        if start <= index < end:
            return start, end
    return None


def _options_of(lines: list[str]) -> list[_Option]:
    """Return every ``BuildOption`` line of the file, in file order."""
    found: list[_Option] = []
    for offset, line in enumerate(lines):
        match = RE_BUILD_OPTION.match(line)
        if match is None:
            continue
        rest = match.group('rest')
        separator = RE_SEPARATOR.match(rest)
        found.append(
            _Option(
                offset=offset,
                line=offset + 1,
                spelling=match.group('name'),
                stage=match.group('stage'),
                separator=separator.group(0) if separator else '',
                value=rest.strip(),
            ),
        )
    return found


def _check_spelling(option: _Option) -> list[str]:
    """B1: the field is spelled ``BuildOption``."""
    if option.spelling == FIELD_NAME:
        return []
    return [
        f'BuildOption field (line {option.line}) is spelled '
        f'"{option.spelling}"; write "{FIELD_NAME}"',
    ]


def _check_stage(option: _Option) -> list[str]:
    """B2 and B3: the stage is present and is one bare lowercase token."""
    if option.stage is None:
        return [
            f'BuildOption (line {option.line}) omits the stage; write '
            f'"BuildOption(<stage>):" with one of {STAGE_ORDER_TEXT}',
        ]
    stage = option.stage.strip()
    if not stage:
        return [
            f'BuildOption (line {option.line}) has an empty stage; write '
            f'"BuildOption(<stage>):" with one of {STAGE_ORDER_TEXT}',
        ]
    if RE_STAGE_TOKEN.match(stage) is not None:
        return []
    return [
        f'BuildOption stage "{stage}" (line {option.line}) is not a single '
        'bare lowercase stage name; write one token such as "conf" or '
        '"install"',
    ]


def _check_spacing(option: _Option) -> list[str]:
    """B4 and B5: exactly two spaces, then a non-empty argument."""
    if not option.value:
        return [
            f'BuildOption({option.stage}) (line {option.line}) declares no '
            'argument; write the option string after two spaces',
        ]
    if option.separator == EXPECTED_SEPARATOR:
        return []
    kind = 'a tab' if '\t' in option.separator else (
        f'{len(option.separator)} space(s)'
    )
    return [
        f'BuildOption({option.stage}) (line {option.line}) is separated '
        f'from its argument by {kind} instead of two spaces',
    ]


def _first_field_line(
    lines: list[str],
    span: tuple[int, int],
    name: str,
) -> int | None:
    """Return the 1-based line of the first field with this name, or None."""
    start, end = span
    for offset in range(start, end):
        match = RE_FIELD.match(lines[offset])
        if match is None:
            continue
        if match.group(1) == name:
            return offset + 1
    return None


def _check_position(
    lines: list[str],
    blocks: list[tuple[int, int]],
    option: _Option,
) -> list[str]:
    """B6: the field sits in a header block, after BuildSystem, before
    BuildRequires.

    A field written after a section has started, for example directly above
    ``%files``, belongs to no field block and is reported as misplaced. The
    window closes on the first ``BuildSystem`` and the first
    ``BuildRequires`` of the block, because ``BuildRequires`` is commonly
    repeated once per dependency and the documented window closes on the
    first of them. A boundary that the block never writes is not reported:
    the clause constrains the position relative to two present fields.
    """
    span = _block_at(blocks, option.offset)
    if span is None:
        return [
            f'BuildOption({option.stage}) (line {option.line}) is written '
            'outside the header field block; write it before the first '
            'section',
        ]

    errors: list[str] = []
    system = _first_field_line(lines, span, BUILD_SYSTEM_FIELD)
    if system is not None and option.line < system:
        errors.append(
            f'BuildOption({option.stage}) (line {option.line}) must be '
            f'written after BuildSystem (line {system})',
        )
    requires = _first_field_line(lines, span, BUILD_REQUIRES_FIELD)
    if requires is not None and option.line > requires:
        errors.append(
            f'BuildOption({option.stage}) (line {option.line}) must be '
            f'written before BuildRequires (line {requires})',
        )
    return errors


def _check_stage_order(
    blocks: list[tuple[int, int]],
    options: list[_Option],
) -> list[str]:
    """B7: the stages follow the order of the RPM build process.

    Each field block is inspected on its own, because a subpackage repeats
    its own option block. Only the documented stages are ranked; a stage
    outside the table neither resets the comparison nor is reported, so a
    newer RPM stage is never a finding here. A run of one stage followed by
    a run of a later stage is the documented layout, so the message names
    the previous ranked declaration, which is the one the reader has to move
    or reorder.
    """
    errors: list[str] = []
    for start, end in blocks:
        previous: _Option | None = None
        for option in options:
            if not start <= option.offset < end:
                continue
            stage = (option.stage or '').strip()
            rank = STAGE_RANK.get(stage)
            if rank is None:
                continue
            if previous is not None:
                before = STAGE_RANK[(previous.stage or '').strip()]
                if rank < before:
                    errors.append(
                        f'BuildOption({stage}) (line {option.line}) is '
                        f'written after BuildOption({previous.stage}) '
                        f'(line {previous.line}); write the stages in the '
                        f'order {STAGE_ORDER_TEXT}',
                    )
            previous = option
    return errors


def _check_spec_buildoption_ext(
    filename: str,
    *,
    check_field_case: bool = True,
    check_stage: bool = True,
    check_spacing: bool = True,
    check_position: bool = True,
    check_order: bool = True,
) -> list[str]:
    """Run the checkpoints of this rule against one spec file.

    Every checkpoint is on by default. The keyword arguments exist for the
    command line flags, which let a team relax the SHOULD level checkpoints
    without dropping the MUST level ones.
    """
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    options = _options_of(lines)
    if not options:
        return []

    blocks = _blocks_of(lines)

    errors: list[str] = []
    for option in options:
        if check_field_case:
            errors.extend(_check_spelling(option))
        if check_stage:
            errors.extend(_check_stage(option))
        if check_spacing:
            errors.extend(_check_spacing(option))
        if check_position:
            errors.extend(_check_position(lines, blocks, option))

    if check_order:
        errors.extend(_check_stage_order(blocks, options))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_buildoption(filename: str) -> list[str]:
    return _check_spec_buildoption_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the BuildOption declarations of openRuyi spec '
                    'files.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-field-case',
        action='store_true',
        help='do not report a field spelled other than BuildOption',
    )
    parser.add_argument(
        '--no-check-stage',
        action='store_true',
        help='do not report a missing stage or a stage that is not one '
             'bare lowercase token',
    )
    parser.add_argument(
        '--no-check-spacing',
        action='store_true',
        help='do not report an empty argument or a separator other than '
             'two spaces',
    )
    parser.add_argument(
        '--no-check-position',
        action='store_true',
        help='do not report a field written outside the BuildSystem to '
             'BuildRequires window',
    )
    parser.add_argument(
        '--no-check-order',
        action='store_true',
        help='do not report stages written out of the RPM build process '
             'order',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_buildoption_ext(
            filename,
            check_field_case=not args.no_check_field_case,
            check_stage=not args.no_check_stage,
            check_spacing=not args.no_check_spacing,
            check_position=not args.no_check_position,
            check_order=not args.no_check_order,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret


if __name__ == '__main__':
    raise SystemExit(main())
