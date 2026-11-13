"""Enforce the openRuyi patch clauses of a spec file.

The packaging guidelines describe the patch policy in two places: the
``Patch and %patchlist (optional)`` section of the main guidelines and the
dedicated ``Patch`` supplement page. Together they supply five checkpoints:

* P1 - every declaration group has one comment line above it.
* P2 - every patch file name starts with four digits.
* P3 - that four digit prefix lies in ``0001``-``2999``.
* P4 - more than three patches imply ``%patchlist``.
* P5 - ``%patchlist`` sits above ``%description``.
* P6 - ``Patch`` sits above ``BuildOption``, or above ``BuildRequires``.

The strength of the underlying wording differs, so each checkpoint names its
source:

* P1 is SHOULD level. The main guidelines say that every referenced patch
  should have one comment line above it, and the supplement repeats it.
  Neither page makes it a hard requirement, and both allow a patch that
  explains itself.
* P2 and P3 are MUST level. The naming policy says every patch file should
  start with four digits and then fixes the meaning of the three ranges.
  The supplement repeats the ranges unchanged, so this is the strongest
  checkpoint of the rule.
* P4 is advisory. The main guidelines say that more than three patches makes
  the single ``Patch`` field inappropriate, which is advice rather than a
  prohibition.
* P5 is MUST level. The same sentence says that a ``%patchlist`` must be
  placed above ``%description``, and the supplement repeats it.
* P6 is SHOULD level. The supplement says the field should be written above
  ``BuildOption`` if present or above ``BuildRequires``, and the base field
  relative order list of the main guidelines puts ``Patch`` between
  ``BuildSystem`` and ``BuildOption``.

Deliberately out of scope, each because the clause does not reach it or
because the judgement is not static: whether a patch is actually applied
during ``%prep``; the correct strip level, which is ``-p1`` by default;
whether ``BuildOption(prep)`` or a hand-written ``%prep`` is justified;
whether a patch is truly upstream, backported or package specific, which
would need the patch payload and its upstream history; whether a submission
comment carries a real pull request link; and whether a patch is stale
against the current upstream version. The name of a patch file is only
compared against the documented shape, never against its real purpose.

The "a patch that explains itself needs no comment" escape hatch of P1 is
also out of scope, because deciding it needs the patch payload. A team that
wants to honour that exemption in its own reviews can disable the whole
checkpoint with ``--no-check-comment``.

No network access and no ``rpm`` invocation is performed, so the rule works
on a bare checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. The name is captured verbatim so that
# a subpackage field and a stub field can both be recognised.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)\s*:\s*(.*)$')

# A patch field: "Patch", "Patch0", "Patch1", ... The match is case
# insensitive and anchored, so a stray "Patches" is not a patch field.
RE_PATCH_FIELD = re.compile(r'^patch\d*$', re.IGNORECASE)

# A "%patchlist" block header. It is a macro rather than a field, so it can
# only be found by scanning the file's lines.
RE_PATCHLIST = re.compile(r'^%patchlist\b')

# A patch file reference. The suffix has to be at the end of the token, so
# an unrelated ".patch" inside a URL is not enough.
RE_PATCH_FILE = re.compile(r'\.(?:patch|diff)$', re.IGNORECASE)

# The four digit type prefix of a patch file name.
RE_PREFIX = re.compile(r'^(\d{4})')

# A macro reference. A value that holds one cannot be resolved on a bare
# checkout, so it is skipped rather than guessed.
RE_MACRO = re.compile(r'%\{[^{}]*\}')

# The two fields that close the documented position window of "Patch". The
# "BuildOption" field may carry an argument, as in "BuildOption(prep): -p0".
RE_BUILD_OPTION = re.compile(r'^BuildOption\s*[:(]')
RE_BUILD_REQUIRES = re.compile(r'^BuildRequires\s*:')

# The section that the "%patchlist" block has to precede.
RE_DESCRIPTION = re.compile(r'^%description\b')

# The documented range of a patch file type prefix.
PREFIX_MIN = 1
PREFIX_MAX = 2999

# The documented threshold: more declarations than this call for a list.
PATCHLIST_THRESHOLD = 3


class _PatchEntry(NamedTuple):
    """One patch declaration.

    ``line`` is 1-based. ``name`` is the patch file name when the
    declaration can be resolved on a bare checkout, and ``None`` when it
    holds a macro reference or does not look like a patch file reference.
    """

    line: int
    name: str | None


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


def _patch_file_name(token: str) -> str | None:
    """Return the patch file name of a declaration, or None.

    A token holding a macro reference is None, because the name is only
    known at build time. A token without a ``.patch`` or ``.diff`` suffix
    is None, because neither naming checkpoint should fire on a reference
    that does not name a patch file. A path is reduced to its last
    component, since the four digit prefix belongs to the file name and not
    to a directory in front of it.
    """
    if not token or RE_MACRO.search(token) is not None:
        return None
    first = token.split()[0]
    if RE_PATCH_FILE.search(first) is None:
        return None
    return first.rsplit('/', 1)[-1]


def _patch_fields(lines: list[str]) -> list[tuple[int, str]]:
    """Return (line, value) for every ``Patch`` or ``PatchN`` field."""
    found: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = RE_FIELD.match(line)
        if match is None:
            continue
        if RE_PATCH_FIELD.match(match.group(1)) is None:
            continue
        found.append((index + 1, match.group(2).strip()))
    return found


def _patchlist_lines(lines: list[str]) -> list[int]:
    """Return the 1-based lines that start a ``%patchlist`` block."""
    return [
        index + 1
        for index, line in enumerate(lines)
        if RE_PATCHLIST.match(line) is not None
    ]


def _patchlist_entries(
    lines: list[str],
    macro_line: int,
) -> list[tuple[int, str]]:
    """Return (line, token) for the entries of one ``%patchlist`` block.

    The body ends at the first blank line or at the first line that starts
    with ``%``. Both guards are needed by the corpus, which routinely
    writes a multi-line ``%global _description %{expand:`` macro directly
    after a ``%patchlist``; without them the prose of that macro is read as
    patch file names. Comment lines are skipped, since the documented form
    is a comment line followed by a bare file name.
    """
    found: list[tuple[int, str]] = []
    index = macro_line
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            break
        if line.lstrip().startswith('%'):
            break
        stripped = line.strip()
        if not stripped.startswith('#'):
            found.append((index + 1, stripped))
        index += 1
    return found


def _runs_of(lines: Sequence[int]) -> list[list[int]]:
    """Group consecutive line numbers into runs.

    The documented layout is one comment followed by a block of patch file
    names, so a run is the unit that carries one comment. A run that is
    short of a comment is reported once, which is why the grouping
    granularity has to match the sample in the guidelines.
    """
    runs: list[list[int]] = []
    current: list[int] = []
    for line in lines:
        if current and line == current[-1] + 1:
            current.append(line)
        else:
            if current:
                runs.append(current)
            current = [line]
    if current:
        runs.append(current)
    return runs


def _check_comment(lines: list[str], runs: list[list[int]]) -> list[str]:
    """P1: every declaration group has one comment line above it."""
    errors: list[str] = []
    for run in runs:
        line = run[0]
        if line > 1 and lines[line - 2].lstrip().startswith('#'):
            continue
        errors.append(
            f'patch declaration (line {line}) has no comment line above '
            f'it; add one line describing the patch or giving the upstream '
            f'link',
        )
    return errors


def _check_prefix(name: str, line: int) -> list[str]:
    """P2 and P3: the file name carries a documented four digit prefix."""
    ranges = (
        '0001-0999 for a patch from the same upstream version, '
        '1000-1999 for a CVE fix or a backport from another upstream '
        'version, 2000-2999 for an openRuyi specific patch'
    )
    match = RE_PREFIX.match(name)
    if match is None:
        return [
            f'patch file "{name}" (line {line}) does not start with four '
            f'digits; prefix it with {ranges}',
        ]
    if PREFIX_MIN <= int(match.group(1)) <= PREFIX_MAX:
        return []
    return [
        f'patch file "{name}" (line {line}) starts with a prefix outside '
        f'{PREFIX_MIN:04d}-{PREFIX_MAX:04d}; use {ranges}',
    ]


def _check_patchlist_needed(
    entries: list[_PatchEntry],
    patchlists: list[int],
) -> list[str]:
    """P4: more than three patches imply a ``%patchlist`` block."""
    if patchlists or len(entries) <= PATCHLIST_THRESHOLD:
        return []
    return [
        f'{len(entries)} patches are declared but the spec uses no '
        f'%patchlist; use %patchlist above %description instead of more '
        f'than {PATCHLIST_THRESHOLD} Patch fields',
    ]


def _check_patchlist_position(
    lines: list[str],
    patchlists: list[int],
) -> list[str]:
    """P5: the block sits above the first ``%description``."""
    descriptions = [
        index + 1
        for index, line in enumerate(lines)
        if RE_DESCRIPTION.match(line) is not None
    ]
    if not descriptions:
        return []
    first = min(descriptions)
    return [
        f'%patchlist (line {line}) must be written above %description '
        f'(line {first})'
        for line in patchlists
        if line > first
    ]


def _first_line(lines: list[str], pattern: re.Pattern[str]) -> int | None:
    """Return the 1-based line of the first match, or None."""
    for index, line in enumerate(lines):
        if pattern.match(line) is not None:
            return index + 1
    return None


def _check_patch_position(
    lines: list[str],
    fields: list[tuple[int, str]],
) -> list[str]:
    """P6: the first ``Patch`` sits above its documented boundary.

    The window closes on ``BuildOption`` when the spec writes one, and on
    ``BuildRequires`` otherwise. A spec that writes neither is silent,
    because the clause constrains the position relative to those fields.
    The first ``Patch`` is compared, since a spec that repeats the field
    once per patch satisfies the clause as soon as the earliest one is
    inside the window.
    """
    if not fields:
        return []
    first = min(line for line, _value in fields)
    anchor = _first_line(lines, RE_BUILD_OPTION)
    label = 'BuildOption'
    if anchor is None:
        anchor = _first_line(lines, RE_BUILD_REQUIRES)
        label = 'BuildRequires'
    if anchor is None or first < anchor:
        return []
    return [
        f'Patch (line {first}) must be written above {label} '
        f'(line {anchor})',
    ]


def _check_spec_patch_patchlist_ext(
    filename: str,
    *,
    check_comment: bool = True,
    check_naming: bool = True,
    check_patchlist: bool = True,
    check_position: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    fields = _patch_fields(lines)
    patchlists = _patchlist_lines(lines)

    list_entries: list[list[tuple[int, str]]] = [
        _patchlist_entries(lines, line) for line in patchlists
    ]

    errors: list[str] = []
    if check_comment:
        runs = _runs_of([line for line, _value in fields])
        for entries in list_entries:
            runs.extend(_runs_of([line for line, _token in entries]))
        errors.extend(_check_comment(lines, runs))

    if check_naming:
        declared = [(line, _patch_file_name(value)) for line, value in fields]
        for entries in list_entries:
            declared.extend(
                (line, _patch_file_name(token)) for line, token in entries
            )
        for line, name in declared:
            if name is not None:
                errors.extend(_check_prefix(name, line))

    resolved = [_PatchEntry(line, _patch_file_name(value))
                for line, value in fields]
    for entries in list_entries:
        resolved.extend(
            _PatchEntry(line, _patch_file_name(token))
            for line, token in entries
        )

    if check_patchlist:
        errors.extend(
            _check_patchlist_needed(
                [entry for entry in resolved if entry.name is not None],
                patchlists,
            ),
        )
        errors.extend(_check_patchlist_position(lines, patchlists))

    if check_position:
        errors.extend(_check_patch_position(lines, fields))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_patch_patchlist(filename: str) -> list[str]:
    return _check_spec_patch_patchlist_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the patch declarations of openRuyi spec files.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-comment',
        action='store_true',
        help='do not report a patch declaration without a comment above it',
    )
    parser.add_argument(
        '--no-check-naming',
        action='store_true',
        help='do not report a patch file name prefix outside 0001-2999',
    )
    parser.add_argument(
        '--no-check-patchlist',
        action='store_true',
        help='do not report a missing or a misplaced %%patchlist',
    )
    parser.add_argument(
        '--no-check-position',
        action='store_true',
        help='do not report a Patch field below BuildOption or '
             'BuildRequires',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_patch_patchlist_ext(
            filename,
            check_comment=not args.no_check_comment,
            check_naming=not args.no_check_naming,
            check_patchlist=not args.no_check_patchlist,
            check_position=not args.no_check_position,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret


if __name__ == '__main__':
    raise SystemExit(main())
