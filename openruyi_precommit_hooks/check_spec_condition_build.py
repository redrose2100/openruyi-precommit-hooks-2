"""Enforce the openRuyi conditional build clauses of a spec file.

The packaging guidelines keep the "Conditional build" part short and give it
two clauses:

1. When an optional build switch is needed, the spec should define it with
   ``%bcond``.
2. The spec should avoid ``%bcond_with`` and ``%bcond_without``.

The worked example writes ``%bcond bootstrap 0`` and ``%bcond bootstrap 1``
and then tests the switch with ``%if %{with bootstrap}`` and
``%if %{without bootstrap}``, so the documented form always carries an
explicit default value.

That yields two checkpoints, both SHOULD level, because the clause uses the
"should" wording and the example only shows the documented shape:

* C1 - ``%bcond_with`` and ``%bcond_without`` are replaced by ``%bcond``.
* C2 - a ``%bcond`` declaration carries an explicit default value.

C1 follows the clause directly. C2 follows the shape of the example:
``%bcond`` is a declaration form, so a bare name leaves the switch without
the default the clause shows, and a later ``%if %{with <name>}`` then has
nothing to test.

A hand rolled ``%define with_<name> 0|1`` switch is not reported: the clause
names ``%bcond`` and the two legacy macros, and it does not describe the
general purpose ``%define`` family, so reading it as a switch requirement
would be an inference the spec text does not support.

Deliberately out of scope, each because the clause does not reach it or
because the spec text alone cannot decide it:

* Whether a switch should exist at all, and which default is right for a
  given package, are design decisions about the software being packaged.
* A ``%bcond`` that no ``%if`` in the spec tests is not reported. The
  guideline never requires every declared switch to be referenced by its
  own spec, and a builder can still flip it from the command line with
  ``--with`` / ``--without``.
* A switch redefined inside an ``%if`` / ``%else`` pair is legitimate. Two
  declarations of the same name are allowed when each sits on a different
  branch, which is how a spec pins a switch per target, so declaration
  counting is not a checkpoint.
* ``%if %{with x}`` and ``%{?with x:...}`` are both correct ways to read a
  switch, and the guideline does not prefer one.
* How a spec consumes the resulting ``%{with ...}`` value, and whether the
  conditional block wraps the right number of lines, are structure questions
  owned by the section rules rather than by this clause.

A ``%bcond`` whose value is built from a macro, as in
``%bcond rpmwheels %{without bootstrap}``, is accepted without inspection:
the value cannot be judged before expansion and the indirection is a
deliberate way to derive one switch from another.

No network access and no ``rpm`` invocation is performed, so the rule works
on a bare checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence


# A "%bcond" declaration. The name is the first token and everything after
# it is the default value, which may be empty.
RE_BCOND = re.compile(r'^%bcond\s+(?P<name>\S+)(?P<rest>.*)$')

# The legacy switch declarations. "out" is captured so the message can
# suggest the matching "%bcond" default: "%bcond_with" defaults to off and
# "%bcond_without" defaults to on.
RE_LEGACY = re.compile(r'^%bcond_with(?P<out>out)?\s+(?P<name>\S+)')


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


def _directive(line: str) -> str:
    """Return the line without its indentation, or '' for a comment."""
    stripped = line.strip()
    if stripped.startswith('#'):
        return ''
    return stripped


def _check_legacy_form(lines: list[str]) -> list[str]:
    """C1: the spec avoids ``%bcond_with`` and ``%bcond_without``."""
    errors: list[str] = []
    for index, line in enumerate(lines):
        text = _directive(line)
        match = RE_LEGACY.match(text)
        if match is None:
            continue
        name = match.group('name')
        default = '1' if match.group('out') else '0'
        errors.append(
            f'"{text.split()[0]} {name}" (line {index + 1}) is the legacy '
            f'switch form; write "%bcond {name} {default}" instead',
        )
    return errors


def _check_default_value(lines: list[str]) -> list[str]:
    """C2: a ``%bcond`` declaration carries an explicit default value."""
    errors: list[str] = []
    for index, line in enumerate(lines):
        text = _directive(line)
        match = RE_BCOND.match(text)
        if match is None:
            continue
        if match.group('rest').strip():
            continue
        name = match.group('name')
        errors.append(
            f'"%bcond {name}" (line {index + 1}) declares no default value; '
            f'write "%bcond {name} 0" or "%bcond {name} 1"',
        )
    return errors


def _check_spec_condition_build_ext(
    filename: str,
    *,
    check_legacy_form: bool = True,
    check_default_value: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    errors: list[str] = []
    if check_legacy_form:
        errors.extend(_check_legacy_form(lines))
    if check_default_value:
        errors.extend(_check_default_value(lines))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_condition_build(filename: str) -> list[str]:
    return _check_spec_condition_build_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            'Check the conditional build clauses of openRuyi spec files.'
        ),
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-legacy-form',
        action='store_true',
        help='do not report the %bcond_with and %bcond_without forms',
    )
    parser.add_argument(
        '--no-check-default-value',
        action='store_true',
        help='do not report a %bcond declaration without a default value',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_condition_build_ext(
            filename,
            check_legacy_form=not args.no_check_legacy_form,
            check_default_value=not args.no_check_default_value,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret


if __name__ == '__main__':
    raise SystemExit(main())
