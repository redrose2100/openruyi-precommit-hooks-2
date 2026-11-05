"""Check the ``Summary`` field of spec files against the openRuyi guidelines.

The rule is limited to the ``Summary`` field, traceable to a single
document:

* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines``
  (``#summary`` section and the *layout and readability* clause that
  requires American English)

Checkpoints
-----------

S1. ``Summary`` is present and non-empty.
S2. The value must not end with an English period ``.``.
S3. The value should be English only (American English); any non-ASCII
    character violates this checkpoint.
S4. The value should stay a brief description; a value longer than 300
    characters is flagged as a heuristic.

A macro-valued summary such as ``Summary: %{summary}`` cannot be judged
statically, so S2-S4 are skipped for it; S1 still fires when the field is
missing or empty. Subpackage ``Summary`` lines (inside ``%package``
blocks) are covered by every checkpoint, exactly like the main package
field.

Everything that is not statically decidable is deliberately out of scope:
judging whether a summary is "brief" below the heuristic bound, and
judging whether an ASCII summary is grammatical American English.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence


# Matches a top-level "Summary: value" line, including an empty value. Applied
# per line, never to the whole file: a non-MULTILINE search over the full text
# matches nothing.
_RE_SUMMARY = re.compile(r'^Summary\s*:\s*(.*)$')

# A non-ASCII character: anything above U+007F. A summary that contains one
# is not English-only (S3). ASCII punctuation is untouched by this check.
_RE_NON_ASCII = re.compile(r'[^\x00-\x7F]')

# Heuristic upper bound for a "brief" summary (S4). The guideline does not
# give a number; 300 characters is a deliberately loose bound so that only
# clearly oversized summaries are flagged. A scan of the openRuyi SPECS
# tree (6290 specs) found that ordinary one-line descriptions run up to
# roughly 200 characters, so the bound sits well above that.
_MAX_SUMMARY_LENGTH = 300


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


def _find_summaries(lines: list[str]) -> list[tuple[str, int]]:
    """Return every ``Summary:`` value and its 1-based line number.

    Comment lines, ``%global``/``%define`` lines and RPM conditional lines
    can never match because none of them start with ``Summary`` followed by
    a colon at column 0. The main package field and every subpackage field
    block are covered alike. A declared but valueless ``Summary:`` yields
    an empty string, which is distinct from a missing field.
    """
    return [
        (match.group(1).strip(), index)
        for index, line in enumerate(lines, start=1)
        for match in [_RE_SUMMARY.match(line)]
        if match is not None
    ]


def _check_present(summaries: list[tuple[str, int]]) -> list[str]:
    """S1: the spec must declare a non-empty ``Summary``."""
    errors: list[str] = []
    if not summaries:
        return ['Summary field is missing']
    for value, line in summaries:
        if not value:
            errors.append(f'Summary field is empty (line {line})')
    return errors


def _check_no_period(value: str, line: int) -> list[str]:
    """S2: the value must not end with an English period ``.``."""
    if value.endswith('.'):
        return [
            f'Summary "{value}" (line {line}) must not end with a '
            'period "."',
        ]
    return []


def _check_english(value: str, line: int) -> list[str]:
    """S3: the value should be English only (American English)."""
    if _RE_NON_ASCII.search(value):
        return [
            f'Summary "{value}" (line {line}) contains non-ASCII '
            'characters; write a brief English summary',
        ]
    return []


def _check_brief(value: str, line: int) -> list[str]:
    """S4: the value should stay brief (heuristic length bound)."""
    if len(value) > _MAX_SUMMARY_LENGTH:
        return [
            f'Summary "{value[:40]}..." (line {line}) is {len(value)} '
            f'characters; keep it under {_MAX_SUMMARY_LENGTH} (heuristic)',
        ]
    return []


def _is_macro_value(value: str) -> bool:
    """True when the value still holds an unresolved ``%`` reference.

    ``%{?foo}``, ``%{foo}`` and bare ``%foo`` all expand at build time, so
    the visible text is not the final value. The empty string contains no
    ``%`` and is handled by S1 instead.
    """
    return '%' in value


def _check_spec_summary(filename: str) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    summaries = _find_summaries(lines)

    errors: list[str] = []
    errors.extend(_check_present(summaries))

    for value, line in summaries:
        if not value:
            continue  # S1 already reported the empty value
        if _is_macro_value(value):
            continue  # macro value: cannot statically judge S2-S4
        errors.extend(_check_no_period(value, line))
        errors.extend(_check_english(value, line))
        errors.extend(_check_brief(value, line))

    return _dedup([f'{filename}: {err}' for err in errors])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        for err in _check_spec_summary(filename):
            print(err)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
