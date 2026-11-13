"""Check the ``License`` field of spec files against the openRuyi guidelines.

The rule is limited to statements that are decidable from the spec file alone.
Two documents define them:

* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines``
  (``#license`` section, rules 1 and 2)
* ``https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/Licenses``
  (*The License tag* section, "use the appropriate SPDX license expression")

Checkpoints
-----------

C1. The value must be a syntactically valid SPDX license expression:
    balanced parentheses, no dangling ``AND`` / ``OR``, ``WITH`` followed
    by an exception identifier, upper-case connectors, and no comma used
    as a separator.
C2. Every identifier must exist in the SPDX license list, or in the SPDX
    exception list when it follows ``WITH``. ``LicenseRef-*`` identifiers
    are always accepted.
C3. An identifier that differs from an SPDX identifier only by case is
    reported together with the canonical spelling.

Presence and emptiness are *not* covered: ``check-spec-basic-fields``
already owns them, and reporting them twice would double every finding.

Deliberately out of scope, because neither document requires it or because
it cannot be decided without more than the spec file:

* Whether the enumerated licenses are factually correct (needs the source
  tarball).
* Whether ``%license`` appears in ``%files`` (needs the source tree; a
  package whose source ships no license file legitimately has none).
* Whether a subpackage license matches the main package (needs RPM
  artefacts).
* The Perl module special case (needs module detection).
* Deprecated SPDX identifiers and extra whitespace inside the value: no
  specification document mentions either. The formatting clause in fact
  asks packagers to align tag values *with* spaces, which points the other
  way for whitespace.
"""
from __future__ import annotations

import argparse
import difflib
import re
from collections.abc import Sequence

from openruyi_precommit_hooks._spdx_ids import EXCEPTION_IDS
from openruyi_precommit_hooks._spdx_ids import LICENSE_IDS
from openruyi_precommit_hooks._spdx_ids import LICENSE_REFS_PREFIX
from openruyi_precommit_hooks._spdx_ids import (
    LOWER_EXCEPTION_TO_CANONICAL,
)
from openruyi_precommit_hooks._spdx_ids import LOWER_LICENSE_TO_CANONICAL


# Matches a top-level "License: value" line, including an empty value. Applied
# per line, never to the whole file. The captured value keeps the alignment
# padding used across the whole corpus, so every consumer strips it first; a
# rule that inspected raw whitespace would flag all 6341 specs.
_RE_LICENSE = re.compile(r'^License\s*:\s*(.*)$')

# Token kinds, in match priority order. ``AND`` / ``OR`` / ``WITH`` are listed
# before the lower-case forms and before the generic identifier so a connector
# is never mistaken for an identifier, and ``LicenseRef-`` is listed before the
# generic identifier so a valid reference is never looked up in the lists.
_TOKEN_RE = re.compile(
    r'(?P<lparen>\()'
    r'|(?P<rparen>\))'
    r'|(?P<ws>\s+)'
    r'|(?P<op>AND|OR|WITH)'
    r'|(?P<lower_op>and|or|with)'
    r'|(?P<comma>,)'
    r'|(?P<ref>LicenseRef-[A-Za-z0-9.\-]+)'
    r'|(?P<id>[A-Za-z0-9.+\-]+)',
)

# Connectors that must appear between two operands, and the one that
# introduces an exception rather than a new operand.
_OPERATORS = ('AND', 'OR')
_WITH = 'WITH'

# Minimum difflib similarity for suggesting a spelling. Same threshold and same
# helper shape as check_spec_header, where it separates a one-character typo
# from an unrelated token.
_SPELLING_MATCH_THRESHOLD = 0.9


class _ParseError(Exception):
    """A syntax error found while parsing one expression."""


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


def _is_macro_value(value: str) -> bool:
    """True when the value still holds an unresolved ``%`` reference.

    ``%{license}`` expands at build time, so the visible text is not the
    final value and no checkpoint can judge it.
    """
    return '%' in value


def _tokenize(value: str) -> list[tuple[str, str]]:
    """Split an expression into ``(kind, text)`` pairs, dropping blanks.

    Raises ``_ParseError`` for a character no token accepts, so the message
    can name the offending character and its offset.
    """
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(value):
        match = _TOKEN_RE.match(value, pos)
        if match is None:
            raise _ParseError(
                f'unexpected character "{value[pos]}" at offset {pos}',
            )
        kind = match.lastgroup
        assert kind is not None
        if kind != 'ws':
            tokens.append((kind, match.group()))
        pos = match.end()
    return tokens


def _spelling_hint(identifier: str, candidates: frozenset[str]) -> str:
    """Return a ``did you mean`` suffix, or an empty string."""
    matches = difflib.get_close_matches(
        identifier,
        sorted(candidates),
        n=1,
        cutoff=_SPELLING_MATCH_THRESHOLD,
    )
    if not matches:
        return ''
    return f', did you mean "{matches[0]}"?'


def _lookup_license(identifier: str) -> str | None:
    """Return an error for a license identifier, or None when it is valid.

    C3 is evaluated before C2: an identifier that folds onto exactly one
    canonical spelling is a spelling error, not an unknown identifier, and the
    message can name the fix. The lower-case table only holds unambiguous
    keys, so a hit always implies a single suggestion.
    """
    if identifier.startswith(LICENSE_REFS_PREFIX):
        return None
    if identifier in LICENSE_IDS:
        return None
    if identifier in EXCEPTION_IDS:
        return (
            f'"{identifier}" is an SPDX exception identifier; it must '
            'follow "WITH"'
        )
    canonical = LOWER_LICENSE_TO_CANONICAL.get(identifier.lower())
    if canonical is not None and canonical != identifier:
        return (
            f'"{identifier}" must be spelled "{canonical}" '
            '(SPDX identifiers are case sensitive)'
        )
    hint = _spelling_hint(identifier, LICENSE_IDS)
    return f'unknown SPDX license identifier "{identifier}"{hint}'


def _lookup_exception(identifier: str) -> str | None:
    """Return an error for an exception id, or None when it is valid."""
    if identifier in EXCEPTION_IDS:
        return None
    if identifier in LICENSE_IDS:
        return (
            f'"{identifier}" is an SPDX license identifier, not an '
            'exception; "WITH" needs an exception identifier'
        )
    canonical = LOWER_EXCEPTION_TO_CANONICAL.get(identifier.lower())
    if canonical is not None and canonical != identifier:
        return (
            f'"{identifier}" must be spelled "{canonical}" '
            '(SPDX identifiers are case sensitive)'
        )
    hint = _spelling_hint(identifier, EXCEPTION_IDS)
    return f'unknown SPDX exception identifier "{identifier}"{hint}'


class _Parser:
    """Recursive-descent parser for the SPDX expression grammar.

    ::

        expression := term ( ("AND" | "OR") term )*
        term       := factor [ "WITH" exception ]
        factor     := identifier | license-ref | "(" expression ")"

    A real parser is needed because a regular expression cannot tell
    ``(A OR B) AND C`` from ``(A OR B AND C``, nor ``A AND B`` from ``A AND``.
    """

    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self._tokens = tokens
        self._pos = 0
        self.errors: list[str] = []

    # -- token helpers ----------------------------------------------------

    def _peek(self) -> tuple[str, str] | None:
        if self._pos >= len(self._tokens):
            return None
        return self._tokens[self._pos]

    def _advance(self) -> tuple[str, str]:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _fail(self, message: str) -> None:
        raise _ParseError(message)

    # -- grammar ----------------------------------------------------------

    def parse(self) -> tuple[list[str], str | None]:
        """Return ``(identifier errors, syntax error or None)``.

        A syntax error makes the identifier findings unreliable, because the
        bad token can hide or duplicate operands. The caller reports the
        syntax error alone, so a single fix is always the right next step.
        """
        if not self._tokens:
            return self.errors, None
        try:
            self._parse_expression()
            remaining = self._peek()
            if remaining is not None:
                self._fail(
                    f'unexpected "{remaining[1]}"',
                )
        except _ParseError as exc:
            return self.errors, str(exc)
        return self.errors, None

    def _parse_expression(self) -> None:
        self._parse_term()
        while True:
            token = self._peek()
            if token is None:
                return
            kind, text = token
            if kind == 'op' and text in _OPERATORS:
                self._advance()
                self._parse_term()
                continue
            if kind == 'lower_op':
                self._fail(f'"{text}" must be upper case')
            if kind == 'comma':
                self._fail('use AND / OR instead of ","')
            if kind == 'id' or kind == 'ref' or kind == 'lparen':
                self._fail(
                    f'missing AND / OR before "{text}"',
                )
            if kind == 'rparen':
                return
            self._fail(f'unexpected "{text}"')

    def _parse_term(self) -> None:
        self._parse_factor()
        token = self._peek()
        if token is None:
            return
        kind, text = token
        if kind == 'op' and text == _WITH:
            self._advance()
            self._parse_exception()
            return
        if kind == 'lower_op' and text == 'with':
            self._fail('"with" must be upper case')

    def _parse_exception(self) -> None:
        token = self._peek()
        if token is None:
            self._fail(
                '"WITH" must be followed by an SPDX exception identifier',
            )
        assert token is not None
        kind, text = token
        if kind != 'id':
            self._fail(
                f'"WITH" must be followed by an SPDX exception identifier, '
                f'found "{text}"',
            )
        self._advance()
        error = _lookup_exception(text)
        if error is not None:
            self.errors.append(error)

    def _parse_factor(self) -> None:
        token = self._peek()
        if token is None:
            self._fail(
                'operator "AND" / "OR" must be followed by a license '
                'identifier',
            )
        assert token is not None
        kind, text = token
        if kind == 'lparen':
            self._advance()
            self._parse_expression()
            closing = self._peek()
            if closing is None:
                self._fail('unbalanced "("')
            assert closing is not None
            if closing[0] != 'rparen':
                self._fail(f'expected ")" but found "{closing[1]}"')
            self._advance()
            return
        if kind == 'ref':
            self._advance()
            return
        if kind == 'id':
            self._advance()
            error = _lookup_license(text)
            if error is not None:
                self.errors.append(error)
            return
        if kind in ('op', 'lower_op'):
            self._fail(
                f'operator "{text}" must be followed by a license identifier',
            )
        if kind == 'rparen':
            self._fail('unexpected ")"')
        if kind == 'comma':
            self._fail('use AND / OR instead of ","')
        self._fail(f'unexpected "{text}"')


def _check_value(value: str) -> list[str]:
    """Run C1-C3 over one expression and return the findings.

    A syntax error masks the identifier checks: fixing the expression can
    change which identifiers are even visible, so reporting both in one run
    would produce findings that disappear on their own after the first fix.
    """
    try:
        tokens = _tokenize(value)
    except _ParseError as exc:
        return [f'invalid SPDX license expression: {exc}']
    identifier_errors, syntax_error = _Parser(tokens).parse()
    if syntax_error is not None:
        return [f'invalid SPDX license expression: {syntax_error}']
    return identifier_errors


def _check_spec_license(filename: str) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    errors: list[str] = []
    for index, line in enumerate(lines, start=1):
        match = _RE_LICENSE.match(line)
        if match is None:
            continue
        value = match.group(1).strip()
        if not value or _is_macro_value(value):
            continue
        for finding in _check_value(value):
            errors.append(f'{finding} (line {index})')

    return _dedup([f'{filename}: {err}' for err in errors])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        for err in _check_spec_license(filename):
            print(err)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
