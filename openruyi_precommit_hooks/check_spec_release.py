"""Check the ``Release`` field of spec files against the openRuyi guidelines.

The rule is limited to the ``Release`` field and to the distribution
``%{dist}`` macro override, traceable to two documents:

* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines``
  (``#release`` section)
* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/``
  ``Versioning`` (``Release`` field chapter)

Checkpoints
-----------

R1. ``Release`` is present and non-empty.
R2. The value should use ``%autorelease``. Both ``%autorelease`` and
    ``%{autorelease}`` count as compliant; a compound macro expression such
    as ``%{patchset_release}.%{config_version}_%autorelease`` (used by the
    linux and linux-lts packages) also counts because it embeds an
    ``%autorelease`` token. A literal release number (``Release: 3``) or the
    traditional Fedora form (``Release: 1%{?dist}``) is reported and the
    fix is suggested.
R3. The value must not hard-code a distribution suffix (``.fc38``,
    ``.el9``, ``.oe1``, ``.openEuler1`` and the like). ``%{?dist}`` is a
    macro reference, not a hard-coded suffix, so it never triggers this
    checkpoint.
R4. The spec must not override the ``%{dist}`` macro (``%global dist
    ...`` / ``%define dist ...``). The scan covers every line, not only the
    ``Release`` field, because the override can appear anywhere in the file.

Unlike the ``Version`` rule, R2 and R3 are plain text checks and need no
macro-value escape hatch: R2 looks for an autorelease token and R3 for a
hard-coded suffix string, neither of which depends on macro expansion. A
macro-valued release such as ``1%{?dist}`` is therefore correctly reported
by R2, while ``%{?dist}`` itself never trips R3.

Everything that is not statically decidable is deliberately out of scope:
bumping the release for every change of the same version, resetting the
release to 1 when the version changes, and the ordinal that
``%autorelease`` expands to at build time.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence


# Matches a top-level "Release: value" line, including an empty value. Applied
# per line, never to the whole file: a non-MULTILINE search over the full text
# matches nothing.
_RE_RELEASE = re.compile(r'^Release\s*:\s*(.*)$')

# An autorelease token: "%autorelease" or "%{autorelease}". The leading "%"
# and the optional braces make a compound expression such as
# "%{patchset_release}.%{config_version}_%autorelease" match through its
# embedded "%autorelease" token.
_RE_AUTORELEASE = re.compile(r'%\{?autorelease\}?')

# A hard-coded distribution suffix: ".fc38", ".el9", ".oe1", ".oe2403",
# ".openEuler1" and the like. The leading dot keeps "gcc" or "foo" from
# matching. "oe\\d{4}" is a subset of "oe\\d*", so the latter covers the
# openEuler ordinal form as well.
_RE_DIST_SUFFIX = re.compile(r'\.(?:fc|el|oe|openEuler)\d*', re.IGNORECASE)

# A top-level "%global dist ..." or "%define dist ..." override of the RPM
# distribution macro. Leading whitespace is tolerated: rpmbuild strips it
# when it reads the file, so an indented directive still redefines the
# macro. The "\\b" after "dist" keeps "distribution" from matching.
_RE_DIST_OVERRIDE = re.compile(r'^\s*%\s*(?:global|define)\s+dist\b')


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


def _find_release(
    lines: list[str],
) -> tuple[str | None, int | None]:
    """Return the first ``Release:`` value and its 1-based line number.

    Comment lines, ``%global``/``%define`` lines and RPM conditional lines
    can never match because none of them start with ``Release`` followed by
    a colon at column 0. A declared but valueless ``Release:`` yields an
    empty string, which is distinct from a missing field.
    """
    for index, line in enumerate(lines, start=1):
        match = _RE_RELEASE.match(line)
        if match is not None:
            return match.group(1).strip(), index
    return None, None


def _find_dist_overrides(lines: list[str]) -> list[int]:
    """Return the 1-based line numbers of ``%{dist}`` macro overrides.

    ``%global dist`` and ``%define dist`` redefine the RPM distribution
    macro. RPM treats both directives as defining the macro for the rest of
    the spec, so either spelling is a violation. Leading whitespace is
    tolerated because rpmbuild strips it when it reads the file.
    """
    return [
        index
        for index, line in enumerate(lines, start=1)
        if _RE_DIST_OVERRIDE.match(line)
    ]


def _check_present(value: str | None, line: int | None) -> list[str]:
    """R1: the spec must declare a non-empty ``Release``."""
    if value is None:
        return ['Release field is missing']
    if not value:
        return [f'Release field is empty (line {line})']
    return []


def _check_autorelease(value: str, line: int) -> list[str]:
    """R2: the value should use ``%autorelease``."""
    if _RE_AUTORELEASE.search(value):
        return []
    return [
        f'Release "{value}" (line {line}) should use %autorelease '
        '(3 -> %autorelease)',
    ]


def _check_dist_suffix(value: str, line: int) -> list[str]:
    """R3: no hard-coded distribution suffix such as ``.fc38``."""
    match = _RE_DIST_SUFFIX.search(value)
    if match is None:
        return []
    return [
        f'Release "{value}" (line {line}) must not hard-code a '
        f'distribution suffix ("{match.group(0)}"); use %autorelease',
    ]


def _check_spec_release(filename: str) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    value, line = _find_release(lines)

    errors: list[str] = []
    errors.extend(_check_present(value, line))
    if value is None or not value or line is None:
        return _dedup(errors)

    errors.extend(_check_autorelease(value, line))
    errors.extend(_check_dist_suffix(value, line))

    for override_line in _find_dist_overrides(lines):
        errors.append(
            f'%{{dist}} macro is overridden on line {override_line}; '
            'use %autorelease instead of redefining the %{dist} macro',
        )

    return _dedup([f'{filename}: {err}' for err in errors])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        for err in _check_spec_release(filename):
            print(err)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
