"""Check the ``Version`` field of spec files against the openRuyi guidelines.

The rule is limited to the ``Version`` field and to the version rules that
apply to it, traceable to two documents:

* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines``
  (``#version`` section)
* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/``
  ``Versioning``

Checkpoints
-----------

V1. ``Version`` is present and non-empty.
V2. The value must not contain ``-``: the guideline replaces a hyphen with
    a dot (``7.1.1-44`` -> ``7.1.1.44``).
V3. The value must not contain ``_``: the guideline replaces an underscore
    with a dot (``17_6`` -> ``17.6``).
V4. A prerelease marker (``alpha``, ``beta`` or ``rc``, case-insensitive)
    must be preceded by ``~`` and written in lower case (``3.5.0-rc1`` ->
    ``3.5.0~rc1``).
V5. A value containing ``+`` must follow the snapshot form
    ``<base>+<scm><YYYYMMDD>.<revision>`` (``0+git20250808.ee5b7e3``).
    The base is the last released version (``0`` when the upstream has
    never released one), the SCM tag is a short identifier such as ``git``,
    ``svn``, ``hg`` or ``snap``, the date is ``YYYYMMDD``, and the revision
    is the short commit identifier, usually its first 7 to 10 characters
    (up to a full 40-character SHA-1).
V6. The value may only contain ``[A-Za-z0-9.+~]``.

Macro-valued versions (values that still hold an unresolved ``%{...}``
reference) skip every value-based checkpoint; a missing or empty field is
still reported (V1).

Everything that is not statically decidable is deliberately out of scope:
component ordering across releases, leading-zero preservation, and
free-form patch-level suffixes such as ``post`` (``0.5.0-post1``).
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence


# Matches a top-level "Version: value" line, including an empty value. Applied
# per line, never to the whole file: a non-MULTILINE search over the full text
# matches nothing.
_RE_VERSION = re.compile(r'^Version\s*:\s*(.*)$')

# Prerelease markers the guideline names explicitly. The set is closed: the
# user decided not to extend it to "pre" or "dev". The lookarounds keep
# "alpha" inside "alphabet" or "rc" inside "arc" from matching, while "rc1"
# (marker followed by a digit) still matches.
_RE_PRERELEASE = re.compile(
    r'(?<![A-Za-z])(alpha|beta|rc)(?![A-Za-z])',
    re.IGNORECASE,
)

# Snapshot form "<scm><YYYYMMDD>.<revision>": a lowercase SCM tag, an
# 8-digit date, a dot, and a revision identifier. The guideline says the
# revision is "usually" the first 7 to 10 characters of the commit hash,
# so the length is a guideline, not a hard limit: 12-character hashes (the
# modern GitHub default) and the full 40-character SHA-1 both occur in the
# openRuyi tree. The bounds below accept any short-to-full hash.
_RE_SNAPSHOT = re.compile(r'^[a-z]+[0-9]{8}\.[0-9A-Za-z]{7,40}$')

# Characters that may appear in a version, as defined by the guideline's
# normalisation rules. "+" is the snapshot separator, "~" the prerelease
# marker, and "." the component separator. "-" and "_" are excluded here:
# they are each reported by their own checkpoint (V2 and V3), so V6 only
# fires for the characters none of the other checkpoints covers.
_RE_INVALID_CHAR = re.compile(r'[^A-Za-z0-9.+~\-_]')


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


def _find_version(
    lines: list[str],
) -> tuple[str | None, int | None]:
    """Return the first ``Version:`` value and its 1-based line number.

    Comment lines, ``%global``/``%define`` lines and RPM conditional lines
    can never match because none of them start with ``Version`` followed by a
    colon at column 0. A declared but valueless ``Version:`` yields an empty
    string, which is distinct from a missing field.
    """
    for index, line in enumerate(lines, start=1):
        match = _RE_VERSION.match(line)
        if match is not None:
            return match.group(1).strip(), index
    return None, None


def _is_macro_valued(value: str) -> bool:
    """True when a value still holds an unresolved macro reference.

    Such a value could expand to anything, so every value-based checkpoint is
    skipped for it.
    """
    return '%' in value


def _check_present(value: str | None, line: int | None) -> list[str]:
    """V1: the spec must declare a non-empty ``Version``."""
    if value is None:
        return ['Version field is missing']
    if not value:
        return [f'Version field is empty (line {line})']
    return []


def _check_hyphen(value: str, line: int) -> list[str]:
    """V2: no ``-``; the guideline replaces it with a dot."""
    if '-' not in value:
        return []
    return [
        f'Version "{value}" (line {line}) must not contain "-"; replace it '
        'with "." (7.1.1-44 -> 7.1.1.44)',
    ]


def _check_underscore(value: str, line: int) -> list[str]:
    """V3: no ``_``; the guideline replaces it with a dot."""
    if '_' not in value:
        return []
    return [
        f'Version "{value}" (line {line}) must not contain "_"; replace it '
        'with "." (17_6 -> 17.6)',
    ]


def _check_prerelease(value: str, line: int) -> list[str]:
    """V4: a prerelease marker must be preceded by ``~`` and be lowercase.

    A marker directly after a digit (``1.0rc1``) or after another separator
    (``3.5.0-rc1``) is a violation, as is an uppercase marker such as
    ``3.5.0~RC1``. Each matching marker is reported on its own, so a value
    with several malformed markers yields several messages.
    """
    errors: list[str] = []
    for match in _RE_PRERELEASE.finditer(value):
        marker = match.group(1)
        previous = value[match.start() - 1] if match.start() > 0 else ''
        if previous != '~':
            errors.append(
                f'Version "{value}" (line {line}): prerelease marker '
                f'"{marker}" must be preceded by "~" '
                '(3.5.0-rc1 -> 3.5.0~rc1)',
            )
        elif marker != marker.lower():
            errors.append(
                f'Version "{value}" (line {line}): prerelease marker '
                f'"{marker}" must be lowercase (3.5.0~RC1 -> 3.5.0~rc1)',
            )
    return errors


def _check_snapshot(value: str, line: int) -> list[str]:
    """V5: a value containing ``+`` must follow the snapshot form.

    The form is ``<base>+<scm><YYYYMMDD>.<revision>`` where the base is the
    last released version (``0`` when the upstream has never released one),
    the SCM tag is a short lowercase identifier such as ``git`` or ``snap``,
    the date is ``YYYYMMDD``, and the revision is the short commit
    identifier, usually its first 7 to 10 characters.
    """
    if '+' not in value:
        return []
    parts = value.split('+')
    if len(parts) > 2:
        return [
            f'Version "{value}" (line {line}) contains more than one "+"; '
            'the snapshot form is "<base>+<scm><YYYYMMDD>.<revision>"',
        ]
    base, snapshot = parts
    errors: list[str] = []
    if not base:
        errors.append(
            f'Version "{value}" (line {line}) has an empty base before "+"; '
            'the snapshot form is "<base>+<scm><YYYYMMDD>.<revision>"',
        )
    if not _RE_SNAPSHOT.match(snapshot):
        errors.append(
            f'Version "{value}" (line {line}) does not match the snapshot '
            'form "<base>+<scm><YYYYMMDD>.<revision>" '
            '(0+git20250808.ee5b7e3)',
        )
    return errors


def _check_chars(value: str, line: int) -> list[str]:
    """V6: only ``[A-Za-z0-9.+~]`` is allowed, beyond ``-``/``_``.

    ``-`` and ``_`` are deliberately not invalid characters here: they are
    each covered by their own checkpoint (V2 and V3), and reporting them
    again would duplicate messages.
    """
    match = _RE_INVALID_CHAR.search(value)
    if match is None:
        return []
    char = match.group(0)
    shown = repr(char) if char.isspace() else f'"{char}"'
    return [
        f'Version "{value}" (line {line}) contains invalid character {shown}',
    ]


def _check_spec_version(filename: str) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    value, line = _find_version(lines)

    errors: list[str] = []
    errors.extend(_check_present(value, line))
    if value is None or not value or line is None:
        return _dedup(errors)

    if not _is_macro_valued(value):
        errors.extend(_check_hyphen(value, line))
        errors.extend(_check_underscore(value, line))
        errors.extend(_check_prerelease(value, line))
        errors.extend(_check_snapshot(value, line))
        errors.extend(_check_chars(value, line))

    return _dedup([f'{filename}: {err}' for err in errors])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        for err in _check_spec_version(filename):
            print(err)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
