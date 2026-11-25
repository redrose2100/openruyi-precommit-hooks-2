"""Enforce the openRuyi BuildRequires needs of the autotools build system.

The ``autotools`` supplement of the packaging guidelines states the
dependency a spec takes on when it declares ``BuildSystem: autotools``:

> If you want to use the autotools build system, you need to add these
> BuildRequires, because gcc is preinstalled in the build environment and
> does not have to be declared explicitly.

followed by four ``BuildRequires`` lines naming ``autoconf``, ``automake``,
``libtool`` and ``make``.

The rule checks one thing, and it is static: when a field block declares
``BuildSystem: autotools``, the same block declares ``BuildRequires`` for
``autoconf``, ``automake``, ``libtool`` and ``make``. The requirement is
MUST level in the guideline text ("you need to add"), and it is the only
clause of that page that enumerates its subject, so the rule reproduces the
list verbatim instead of guessing which tool a project happens to use.

Two exemptions keep the rule honest, and neither one is a style choice:

* ``gcc`` is excluded because the guideline excludes it in the same
  sentence that states the requirement.
* A spec that uses ``%generate_buildrequires`` is skipped, because the
  dynamic dependency generator can supply a build dependency that no static
  field records, so the four names may legitimately be absent from the
  header. The guideline does not forbid a static declaration there, it just
  makes the static field unable to answer the question.

The four names are matched as whole dependency names, never as prefixes.
``autoconf-archive`` is a different package and must not satisfy the
``autoconf`` requirement; the corpus contains six such declarations.

Deliberately out of scope: whether a tool is needed beyond the four named
ones, which would duplicate the ``BuildRequires`` rule; whether the package
really builds with autotools, which needs the upstream payload; and the
``%conf`` / ``autoreconf`` advice, which the guideline words as a
recommendation rather than as a requirement. No network access and no
``rpm`` invocation is performed, so the rule works on a bare checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. A trailing parenthesised argument such
# as the stage of "BuildOption(build):" belongs to the field name rather
# than to the value, so the group is matched and dropped.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)(?:\([^)]*\))?\s*:\s*(.*)$')

# A section header. Section arguments ("%prep -a", "%conf -p") are ignored.
RE_SECTION = re.compile(r'^%([a-z]\w*)\b')

# A conditional branch or its terminator. A field can exist on one branch
# only, so the block keeps scanning across it.
RE_CONDITIONAL = re.compile(
    r'^%(?:if|ifarch|ifnarch|ifos|ifnos|else|elif|endif)\b',
)

# A macro definition or a directive that never carries a field of the spec.
RE_DIRECTIVE = re.compile(
    r'^%(?:end|global|define|bcond|undefine|dnl)\b',
)

# The field that switches the requirement on, and the field that satisfies
# it. Both are matched loosely so a misspelling reported by the dedicated
# rules still contributes its value here.
RE_BUILD_SYSTEM = re.compile(r'^build-?system$', re.IGNORECASE)
RE_BUILD_REQUIRES = re.compile(r'^build-?requires?$', re.IGNORECASE)

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

# The section that opens a new field block.
_BLOCK_SECTION = '%package'

# The section whose presence makes the static BuildRequires field unable to
# answer the question.
DYNAMIC_SECTION = '%generate_buildrequires'

# The build system this rule covers.
AUTOTOOLS = 'autotools'

# The four tools the supplement names, in the order the supplement lists
# them so that the message reads like the guideline.
REQUIRED_TOOLS: tuple[str, ...] = (
    'autoconf',
    'automake',
    'libtool',
    'make',
)


class _Block(NamedTuple):
    """One field block: where it starts and which fields it holds.

    ``fields`` is a list of ``(spelling, value, 1-based line)`` tuples.
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

    # Keep the main preamble even when empty; drop empty subpackage blocks.
    if raw:
        blocks = [_Block(*raw[0])]
    else:
        blocks = [_Block(None, len(lines), False, [])]
    blocks.extend(_Block(*item) for item in raw[1:] if item[3])
    return blocks


def _declared_names(value: str) -> set[str]:
    """Return the lowercase name of every dependency on one field line.

    A dependency is a name optionally followed by a version operator and a
    version, or one rich dependency in parentheses, or two names joined by
    a comma, ``with`` or ``without``. Only the names are returned, so a
    version number never looks like a dependency and ``autoconf-archive``
    stays distinct from ``autoconf``.
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


def _quote_list(names: Sequence[str]) -> str:
    """Return the names as an English list: "a", "b" and "c"."""
    quoted = [f'"{name}"' for name in names]
    if len(quoted) == 1:
        return quoted[0]
    return ', '.join(quoted[:-1]) + ' and ' + quoted[-1]


def _system_lines(
    blocks: Sequence[_Block],
) -> list[int]:
    """Return the lines of every ``BuildSystem: autotools`` field."""
    return [
        line
        for block in blocks
        for name, value, line in block.fields
        if RE_BUILD_SYSTEM.match(name) is not None and
        value.lower() == AUTOTOOLS
    ]


def _declared_everywhere(blocks: Sequence[_Block]) -> set[str]:
    """Return every dependency name declared in any field block.

    ``BuildRequires`` is a source-package level field, so RPM merges the
    declarations of every subpackage block into one build dependency set.
    The requirement is therefore satisfied when the name appears anywhere
    in the file, which keeps a subpackage that carries the dependency from
    producing a false finding.
    """
    declared: set[str] = set()
    for block in blocks:
        for name, value, _line in block.fields:
            if RE_BUILD_REQUIRES.match(name) is not None:
                declared |= _declared_names(value)
    return declared


def _check_buildrequires(line: int, declared: set[str]) -> list[str]:
    """C1: an autotools spec declares the four tools as BuildRequires."""
    missing = [tool for tool in REQUIRED_TOOLS if tool not in declared]
    if not missing:
        return []
    return [
        f'BuildSystem: {AUTOTOOLS} (line {line}) requires '
        f'{_quote_list(REQUIRED_TOOLS)} in BuildRequires; '
        f'missing {_quote_list(missing)}',
    ]


def _uses_dynamic_generator(lines: list[str]) -> bool:
    """Return whether the spec runs the dynamic dependency generator."""
    return any(_is_section(line) == DYNAMIC_SECTION for line in lines)


def _check_spec_build_autotools_ext(
    filename: str,
    *,
    check_buildrequires: bool = True,
    check_dynamic: bool = False,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None
    if not check_buildrequires:
        return []
    if not check_dynamic and _uses_dynamic_generator(lines):
        return []

    blocks = _blocks_of(lines)
    system_lines = _system_lines(blocks)
    if not system_lines:
        return []

    declared = _declared_everywhere(blocks)
    errors: list[str] = []
    for line in system_lines:
        errors.extend(_check_buildrequires(line, declared))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_build_autotools(filename: str) -> list[str]:
    return _check_spec_build_autotools_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the BuildRequires of an autotools build system.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-buildrequires',
        action='store_true',
        help='do not report a missing autotools build dependency',
    )
    parser.add_argument(
        '--check-dynamic',
        action='store_true',
        help=(
            'report a missing autotools build dependency even when the '
            'spec uses %%generate_buildrequires'
        ),
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_build_autotools_ext(
            filename,
            check_buildrequires=not args.no_check_buildrequires,
            check_dynamic=args.check_dynamic,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret


if __name__ == '__main__':
    raise SystemExit(main())
