"""Enforce the openRuyi BuildSystem clauses of a spec file.

The packaging guidelines define the ``BuildSystem`` field in four clauses:

1. A spec that uses the RPM declarative build system mechanism must declare
   the build system it uses through ``BuildSystem``.
2. A spec that does not use that mechanism may omit ``BuildSystem``.
3. A spec must not add an empty ``BuildSystem`` field only to say that the
   declarative mechanism does not apply.
4. When ``BuildSystem`` is present its value must name a supported
   declarative build system.

The rule checks six things, all of them statically:

* S1 - the field is spelled ``BuildSystem``.
* S2 - the value is present.
* S3 - the value is one bare lowercase build system name.
* S4 - a field block declares the field at most once.
* S5 - the field sits after the last source declaration of its block.
* S6 - the field sits after ``BuildArch`` and before ``BuildRequires``.

Deliberately out of scope, each because the clause does not reach it or
because the judgement is not static: the field is conditional, so a missing
``BuildSystem`` is never a finding and a spec that builds entirely through
explicit sections is legitimate; the main spec states that it does not
maintain the list of usable build system names, so a hardcoded whitelist
would reject a build system added upstream and only the shape of the value
is checked; whether the chosen build system matches the upstream build
recipe needs payload knowledge; whether the build system macros exist in the
build root needs the build environment; and the stage tags ``%prep -a`` and
``%conf -p`` are section annotations rather than fields. No network access
and no ``rpm`` invocation is performed, so the rule works on a bare
checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. The name is captured verbatim so that
# S1 can see the spelling the packager used.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)\s*:\s*(.*)$')

# A section header. Section arguments ("%pre -n foo", "%prep -a") are
# ignored. The closed whitelist below keeps macro invocations such as
# "%global" and "%if" from ending a field block.
RE_SECTION = re.compile(r'^%([a-z]\w*)\b')

# Conditional and macro directives. They never carry a field, and a
# conditional can hold a field that only exists on one branch, so they are
# skipped rather than parsed.
RE_CONDITIONAL = re.compile(
    r'^%(?:if|ifarch|ifnarch|ifos|ifnos|else|elif|endif|end|global|'
    r'define|bcond|undefine|dnl)\b',
)

# A "%sourcelist" block header. It is the equivalent of a source
# declaration, but it is a macro rather than a field, so it can only be
# found by scanning the block's lines.
RE_SOURCELIST = re.compile(r'^%sourcelist\b')

# A source declaration name: "Source" or "SourceN". The match is case
# insensitive and the name is captured from the field regex, so a stray
# "Sources" is not a source declaration.
RE_SOURCE_N = re.compile(r'^source\d*$', re.IGNORECASE)

# One bare lowercase build system name: "autotools", "cmake", "meson",
# "golangmodules", "rustcrates", "perlmaker".
RE_BUILD_SYSTEM_TOKEN = re.compile(r'^[a-z][a-z0-9_]*$')

# A macro reference. The value of this field is a fixed keyword rather than
# a parameterised argument, so a macro reference is reported instead of
# being expanded.
RE_MACRO = re.compile(r'%\{[^{}]*\}')

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
FIELD_NAME = 'BuildSystem'
BUILD_ARCH_FIELD = 'BuildArch'
BUILD_REQUIRES_FIELD = 'BuildRequires'


class _Block(NamedTuple):
    """One field block: its first field line, its end and its fields.

    ``first_field`` and ``end`` are 0-based offsets into the file, ``end``
    being exclusive. ``first_field`` is ``None`` for a block that holds no
    field at all. Each field is ``(spelling, value, 1-based line)``.
    """

    first_field: int | None
    end: int
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


def _blocks_of(lines: list[str]) -> list[_Block]:
    """Split the file into field blocks.

    The first block is the main preamble, kept even when it holds no field
    so that the subpackage block numbers stay meaningful. Every
    ``%package`` opens a fresh block, because the documented relative field
    order also applies inside a subpackage definition. A block ends at the
    first known section, so a macro invocation such as
    ``%global debug_package %{nil}`` neither ends a block nor hides the
    fields that follow it.
    """
    raw: list[tuple[int | None, int, list[tuple[str, str, int]]]] = []
    first_field: int | None = None
    fields: list[tuple[str, str, int]] = []
    ended = False

    for index, line in enumerate(lines):
        section = _is_section(line)
        if section is not None:
            if section == _BLOCK_SECTION:
                raw.append((first_field, index, fields))
                first_field = None
                fields = []
                ended = False
                continue
            if not ended:
                raw.append((first_field, index, fields))
                first_field = None
                fields = []
                ended = True
            continue
        if ended:
            continue
        if RE_CONDITIONAL.match(line) or line.lstrip().startswith('#'):
            continue
        match = RE_FIELD.match(line)
        if match is None:
            continue
        if first_field is None:
            first_field = index
        fields.append((match.group(1), match.group(2).strip(), index + 1))

    if not ended:
        raw.append((first_field, len(lines), fields))

    # Keep the main preamble even when empty; drop empty subpackage blocks
    # so that the block indices stay contiguous.
    blocks = [_Block(*raw[0])] if raw else [_Block(None, len(lines), [])]
    blocks.extend(_Block(*item) for item in raw[1:] if item[2])
    return blocks


def _find_build_system(
    fields: list[tuple[str, str, int]],
) -> list[tuple[str, str, int]]:
    """Return every ``BuildSystem`` field as (spelling, value, line).

    The name is matched in any case so that S1 can report a misspelling,
    and so that a misspelled field still feeds S2 to S6: a wrong name does
    not make the value or the position irrelevant.
    """
    return [
        (name, value, line)
        for name, value, line in fields
        if name.lower() == FIELD_NAME.lower()
    ]


def _find_source_lines(block: _Block, lines: list[str]) -> list[int]:
    """Return the 1-based lines of every source declaration in the block.

    A source declaration is a ``Source`` or ``SourceN`` field, or a
    ``%sourcelist`` macro. Numbered forms share the position of a bare
    ``Source``, so the caller only needs the last line of the returned
    list.
    """
    found = [
        line for name, _value, line in block.fields if RE_SOURCE_N.match(name)
    ]
    if block.first_field is None:
        return found
    for offset in range(block.first_field, block.end):
        if RE_SOURCELIST.match(lines[offset]) is not None:
            found.append(offset + 1)
    return found


def _find_field_lines(
    fields: list[tuple[str, str, int]],
    name: str,
) -> list[int]:
    """Return the 1-based lines of every field with exactly this name."""
    return [line for field, _value, line in fields if field == name]


def _check_field_case(
    systems: list[tuple[str, str, int]],
) -> list[str]:
    """S1: the field is spelled ``BuildSystem``."""
    errors: list[str] = []
    for name, _value, line in systems:
        if name == FIELD_NAME:
            continue
        errors.append(
            f'BuildSystem field (line {line}) is spelled "{name}"; '
            f'write "{FIELD_NAME}"',
        )
    return errors


def _check_value(value: str, line: int) -> list[str]:
    """S2 and S3: the value is present and is one build system name.

    The value names a fixed keyword rather than a parameterised argument,
    so a macro reference is reported instead of being expanded.
    """
    if not value:
        return [f'BuildSystem field (line {line}) is empty']
    if RE_MACRO.search(value) is not None:
        return [
            f'BuildSystem "{value}" (line {line}) uses a macro reference; '
            'write one literal lowercase build system name such as '
            '"autotools" or "cmake"',
        ]
    if RE_BUILD_SYSTEM_TOKEN.match(value) is not None:
        return []
    return [
        f'BuildSystem "{value}" (line {line}) is not a single bare build '
        'system name; write one lowercase token such as "autotools" or '
        '"cmake"',
    ]


def _check_duplicate(
    systems: list[tuple[str, str, int]],
) -> list[str]:
    """S4: one field block declares the field at most once."""
    if len(systems) <= 1:
        return []
    lines = ', '.join(str(line) for _name, _value, line in systems)
    return [
        'BuildSystem field block declares the field '
        f'{len(systems)} times (lines {lines}); keep one declaration',
    ]


def _check_after_source(
    systems: list[tuple[str, str, int]],
    sources: list[int],
) -> list[str]:
    """S5: the field sits after the last source declaration its block writes.

    The check stays silent when the block declares no source declaration:
    the field order table constrains the relative position of two present
    fields, so a data-only package must not be reported for a boundary it
    never writes.
    """
    if not sources:
        return []
    last = max(sources)
    errors: list[str] = []
    for _name, _value, line in systems:
        if line > last:
            continue
        errors.append(
            f'BuildSystem (line {line}) must be written after the last '
            f'source declaration (line {last})',
        )
    return errors


def _check_position(
    block: _Block,
    systems: list[tuple[str, str, int]],
) -> list[str]:
    """S6: the field sits after ``BuildArch`` and before ``BuildRequires``.

    A boundary that the block never writes is not reported, for the reason
    given in S5. The comparison uses the first ``BuildRequires`` line,
    because the field is commonly repeated on one line per dependency and
    the documented window closes on the first of them.
    """
    errors: list[str] = []
    arch = _find_field_lines(block.fields, BUILD_ARCH_FIELD)
    if arch:
        first_arch = min(arch)
        for _name, _value, line in systems:
            if line > first_arch:
                continue
            errors.append(
                f'BuildSystem (line {line}) must be written after '
                f'BuildArch (line {first_arch})',
            )
    requires = _find_field_lines(block.fields, BUILD_REQUIRES_FIELD)
    if requires:
        first_requires = min(requires)
        for _name, _value, line in systems:
            if line < first_requires:
                continue
            errors.append(
                f'BuildSystem (line {line}) must be written before '
                f'BuildRequires (line {first_requires})',
            )
    return errors


def _check_spec_buildsystem_ext(
    filename: str,
    *,
    check_field_case: bool = True,
    check_value: bool = True,
    check_position: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    errors: list[str] = []
    for block in _blocks_of(lines):
        systems = _find_build_system(block.fields)
        if not systems:
            continue
        if check_field_case:
            errors.extend(_check_field_case(systems))
        if check_value:
            for _name, value, line in systems:
                errors.extend(_check_value(value, line))
        errors.extend(_check_duplicate(systems))
        if check_position:
            errors.extend(
                _check_after_source(
                    systems,
                    _find_source_lines(block, lines),
                ),
            )
            errors.extend(_check_position(block, systems))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_buildsystem(filename: str) -> list[str]:
    return _check_spec_buildsystem_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the BuildSystem field of openRuyi spec files.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-field-case',
        action='store_true',
        help='do not report a BuildSystem field whose spelling differs',
    )
    parser.add_argument(
        '--no-check-value',
        action='store_true',
        help='do not report an empty or malformed BuildSystem value',
    )
    parser.add_argument(
        '--no-check-position',
        action='store_true',
        help='do not report a misplaced BuildSystem field',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_buildsystem_ext(
            filename,
            check_field_case=not args.no_check_field_case,
            check_value=not args.no_check_value,
            check_position=not args.no_check_position,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret


if __name__ == '__main__':
    raise SystemExit(main())
