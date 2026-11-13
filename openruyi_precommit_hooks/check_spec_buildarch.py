"""Enforce the openRuyi BuildArch clauses of a spec file.

The packaging guidelines define the ``BuildArch`` field in three clauses:

1. ``BuildArch`` declares the target architecture.
2. The field must be written between the last ``Source`` field and the
   ``BuildSystem`` field.
3. When the value is ``noarch`` the package is independent of the CPU
   architecture.

The rule checks seven things, all of them statically:

* B1 - the field is spelled ``BuildArch``.
* B2 - the value is present.
* B3 - the value is one bare lowercase architecture token.
* B4 - a field block declares the field at most once.
* B5 - the field sits after the last source declaration of its block.
* B6 - the field sits before ``BuildSystem`` of its block.
* B7 - a ``noarch`` block does not make the build depend on the host
  architecture.

Deliberately out of scope, each because the clause does not reach it or
because another rule already owns it: the field is conditional, so a missing
``BuildArch`` is never a finding; the order of the five core fields and of
every other field is owned by ``check-spec-basic-fields``, whose field order
table already places ``BuildArch`` between ``Source`` and ``BuildSystem``;
whether ``noarch`` is the right choice for a package needs payload knowledge;
``ExclusiveArch`` and ``ExclusiveOS`` are different fields; and a
``%ifarch`` inside ``%prep``, ``%build``, ``%check`` or ``%files`` is
legitimate in a ``noarch`` subpackage of a multi-architecture spec. No
network access and no ``rpm`` invocation is performed, so the rule works on a
bare checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. The name is captured verbatim so that
# B1 can see the spelling the packager used.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)\s*:\s*(.*)$')

# A section header. Section arguments ("%pre -n foo") are ignored. The
# closed whitelist below keeps macro invocations such as "%global" and
# "%if" from ending a field block.
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

# One bare lowercase architecture token: "noarch", "x86_64", "aarch64",
# "riscv64", "loongarch64", "armv7hl".
RE_ARCH_TOKEN = re.compile(r'^[a-z][a-z0-9_]*$')

# A macro reference. A value that still holds one cannot be judged before
# expansion, so B3 leaves it alone.
RE_MACRO = re.compile(r'%\{[^{}]*\}')

# Failures that make a package depend on the build architecture. The
# conditional isa form is absent on purpose: "%{?_isa}" expands to nothing
# on a noarch build, so "Provides: %{name}%{?_isa}" is correct there.
RE_ARCH_PATH = re.compile(
    r'%\{_libdir\}|%\{_lib64\}|%\{_lib\}|%\{_arch\}|%\{_target_cpu\}|'
    r'%\{_host_cpu\}|%\{_target_platform\}',
)

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

# The field under check, the value that means "architecture independent",
# and the field that closes the documented position window.
FIELD_NAME = 'BuildArch'
NOARCH = 'noarch'
BUILD_SYSTEM_FIELD = 'BuildSystem'


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


def _find_buildarch(
    fields: list[tuple[str, str, int]],
) -> list[tuple[str, str, int]]:
    """Return every ``BuildArch`` field as (spelling, value, line).

    The name is matched in any case so that B1 can report a misspelling,
    and so that a misspelled field still feeds B2 to B6: a wrong name does
    not make the value irrelevant.
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


def _find_build_system_lines(block: _Block) -> list[int]:
    """Return the 1-based lines of every ``BuildSystem`` field in the block."""
    return [
        line
        for name, _value, line in block.fields
        if name == BUILD_SYSTEM_FIELD
    ]


def _check_field_case(
    buildarch: list[tuple[str, str, int]],
) -> list[str]:
    """B1: the field is spelled ``BuildArch``."""
    errors: list[str] = []
    for name, _value, line in buildarch:
        if name == FIELD_NAME:
            continue
        errors.append(
            f'BuildArch field (line {line}) is spelled "{name}"; '
            f'write "{FIELD_NAME}"',
        )
    return errors


def _check_value(value: str, line: int) -> list[str]:
    """B2 and B3: the value is present and is one architecture token.

    A value built from a macro is accepted without inspection: it cannot
    be judged before expansion, and forbidding macros here would reject a
    legitimate indirection.
    """
    if not value:
        return [f'BuildArch field (line {line}) is empty']
    if RE_MACRO.search(value) is not None:
        return []
    if RE_ARCH_TOKEN.match(value) is not None:
        return []
    return [
        f'BuildArch "{value}" (line {line}) is not a bare architecture '
        'token; write one lowercase architecture name such as "noarch" '
        'or "x86_64"',
    ]


def _check_duplicate(
    buildarch: list[tuple[str, str, int]],
) -> list[str]:
    """B4: one field block declares the field at most once."""
    if len(buildarch) <= 1:
        return []
    lines = ', '.join(str(line) for _name, _value, line in buildarch)
    return [
        'BuildArch field block declares the field '
        f'{len(buildarch)} times (lines {lines}); keep one declaration',
    ]


def _check_after_source(
    buildarch: list[tuple[str, str, int]],
    sources: list[int],
) -> list[str]:
    """B5: the field sits after the last source declaration of its block.

    The check stays silent when the block declares no source declaration:
    the clause constrains the relative position of two present fields, so
    a data-only package must not be reported for a boundary it never
    writes.
    """
    if not sources:
        return []
    last = max(sources)
    errors: list[str] = []
    for _name, _value, line in buildarch:
        if line > last:
            continue
        errors.append(
            f'BuildArch (line {line}) must be written after the last '
            f'source declaration (line {last})',
        )
    return errors


def _check_before_build_system(
    buildarch: list[tuple[str, str, int]],
    systems: list[int],
) -> list[str]:
    """B6: the field sits before ``BuildSystem`` of its block.

    As with B5, a block that writes no ``BuildSystem`` is not reported.
    """
    if not systems:
        return []
    first = min(systems)
    errors: list[str] = []
    for _name, _value, line in buildarch:
        if line < first:
            continue
        errors.append(
            'BuildArch (line '
            f'{line}) must be written before BuildSystem (line {first})',
        )
    return errors


def _check_noarch(block: _Block, lines: list[str]) -> list[str]:
    """B7: a ``noarch`` block must not depend on the build architecture.

    The window starts at the block's first field line, not at the block
    itself: a ``%define`` or ``%if`` placed above the fields selects a
    build-time macro before the field region starts, and it does not
    contradict the architecture the block declares. The ``%files`` body is
    never read, because a ``%files`` path belongs to the package that owns
    it rather than to the field block that declared the architecture.
    """
    if block.first_field is None:
        return []
    values = [
        value for _name, value, _line in _find_buildarch(block.fields)
    ]
    if NOARCH not in values:
        return []
    noarch_line = next(
        line
        for _name, value, line in _find_buildarch(block.fields)
        if value == NOARCH
    )
    errors: list[str] = []
    for offset in range(block.first_field, block.end):
        match = RE_ARCH_PATH.search(lines[offset])
        if match is None:
            continue
        errors.append(
            f'BuildArch "{NOARCH}" (line {noarch_line}) declares an '
            'architecture independent package, but line '
            f'{offset + 1} uses "{match.group(0)}"',
        )
    return errors


def _check_spec_buildarch_ext(
    filename: str,
    *,
    check_field_case: bool = True,
    check_noarch: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    errors: list[str] = []
    for block in _blocks_of(lines):
        buildarch = _find_buildarch(block.fields)
        if not buildarch:
            continue
        if check_field_case:
            errors.extend(_check_field_case(buildarch))
        for _name, value, line in buildarch:
            errors.extend(_check_value(value, line))
        errors.extend(_check_duplicate(buildarch))
        errors.extend(
            _check_after_source(
                buildarch,
                _find_source_lines(block, lines),
            ),
        )
        errors.extend(
            _check_before_build_system(
                buildarch,
                _find_build_system_lines(block),
            ),
        )
        if check_noarch:
            errors.extend(_check_noarch(block, lines))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_buildarch(filename: str) -> list[str]:
    return _check_spec_buildarch_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the BuildArch field of openRuyi spec files.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-field-case',
        action='store_true',
        help='do not report a BuildArch field whose spelling differs',
    )
    parser.add_argument(
        '--no-check-noarch',
        action='store_true',
        help='do not report architecture use inside a noarch block',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_buildarch_ext(
            filename,
            check_field_case=not args.no_check_field_case,
            check_noarch=not args.no_check_noarch,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret


if __name__ == '__main__':
    raise SystemExit(main())
