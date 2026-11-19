"""Enforce the openRuyi scriptlet clauses of a spec file.

The packaging guidelines describe the scriptlet section in the ``Scriptlet``
part of the main guidelines, and the ``Scriptlets`` supplement carries the
detail that the main text only summarises. Together they supply five
checkpoints:

* S1 - a scriptlet that runs one program without an argument uses ``-p``.
* S2 - a scriptlet does not leave the transaction status to a bare command.
* S3 - ``%pretrans`` is not used.
* S4 - a transaction argument is tested as a range, not as an exact count.
* S5 - an install side scriptlet does not test the erase state.

The strength of the underlying wording differs, so each checkpoint names its
source.

* S1 is SHOULD level. Clause 3 of the main guidelines writes that when a
  single program can be called directly, the scriptlet should use the ``-p``
  form to keep the shell logic small, and the supplement shows
  ``%post -p /usr/bin/ldconfig`` as the example. The form only works when
  the body carries no command line of its own, because ``-p`` names the
  program that runs the body, so only a body of exactly one argument free
  program invocation is reported.
* S2 is MUST level. Clause 2 writes that a scriptlet must end with a success
  status and that a non critical step must not abort the transaction. The
  supplement explains the mechanism: rpm does not pass ``-e`` to the shell,
  so the status of the last command decides the whole scriptlet, and ``|| :``
  is the idiom for forcing success. The checkpoint therefore reports a body
  whose last statement is a bare command, which silently inherits that
  command's status.
* S3 is SHOULD level. Clause 1 asks for idempotency, and the supplement's
  ``Order`` section states that ``%pretrans`` runs before any package is
  installed, that it therefore cannot depend on a program it needs, and that
  it should be avoided.
* S4 is SHOULD level. The supplement's ``$1`` table gives the count after
  the operation, and the note below it warns that a parallel installable
  package can shift the count, so ``if [ "$1" -gt 1 ]`` is preferred over
  testing ``== 2``. The same reasoning applies to the upgrade state of an
  erase scriptlet, whose tabulated count is one.
* S5 is MUST level. The ``$1`` table marks the erase state as not applicable
  to ``%pretrans``, ``%pre``, ``%post`` and ``%posttrans``, because those
  scriptlets never run while a package is being erased. A branch that tests
  for a count of zero inside them is never taken, so it is dead code rather
  than a working erase handler.

Deliberately out of scope, each because the clause is not statically
decidable from the spec alone. Clause 1 asks for idempotency, but whether a
program tolerates being run twice depends on what the program does, not on
the spec text. Clause 2 says a non critical step must not abort the
transaction, and the supplement says ``|| :`` must not be applied to a
command that genuinely must succeed, so a deliberate ``|| exit 1`` is left
alone: deciding whether a command is critical needs knowledge of the
program. A statement that is a macro *invocation* (``%systemd_post``) is not
inspected, because the macro owns its own exit status handling and the
reference corpus writes 552 of its 720 scriptlets that way; a statement that
uses a macro *expansion* as its program (``%{_bindir}/fc-cache -fs``) is
still a command the shell runs and is inspected. A body that uses
``-p`` is not inspected either, since the named program rather than the
shell then decides the status, and ``-p <lua>`` is legitimate. The
``%filetrigger*`` and ``%transfiletrigger*`` sections are treated as section
boundaries but are not checked, because their arguments carry a different
meaning from the ``$1`` of an ordinary scriptlet. ``%preuntrans`` and
``%postuntrans`` are boundaries for the same reason: the supplement's table
does not cover them. Whether a required program exists in the build root, and
whether the shell a scriptlet assumes is available, are build time questions.
No network access and no ``rpm`` invocation is performed, so the rule works
on a bare checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# A section header. Section arguments ("%post -n foo") are captured
# verbatim because the header form is one of the checkpoints. The closed
# whitelist below keeps a macro invocation such as "%systemd_post" from
# being mistaken for a section, which would cut every scriptlet body short.
RE_SECTION = re.compile(r'^%([a-z]\w*)\b')

# Conditional and macro directives. They are not commands, and a
# conditional can hold a command that only exists on one branch, so they are
# skipped rather than parsed.
RE_DIRECTIVE = re.compile(
    r'^%(?:if|ifarch|ifnarch|ifos|ifnos|else|elif|endif|end|global|'
    r'define|bcond|undefine|dnl)\b',
)

# The "-p" header flag, as a whole token. The leading whitespace keeps the
# "-p" inside a package name such as "e2fsprogs-scrub" from matching, and
# the "--" flag is not matched because "-p" must stand alone.
RE_P_FLAG = re.compile(r'(?:^|\s)-p(?:\s|$)')

# A program named by an absolute path, or by a macro followed by a path.
# A bare word is not enough: it may be a shell builtin or a function.
RE_PROGRAM = re.compile(r'^(?:/[^\s]+|%\{[^{}\s]+\}[^\s]*)$')

# A macro invocation that forms a whole statement, such as
# "%systemd_post foo.service". The lookahead separates it from a macro
# expansion such as "%{_bindir}/foo", which is a path and is still a
# command the shell runs.
RE_MACRO_CALL = re.compile(r'^%(?!\{)[A-Za-z_]\w*')

# A statement that closes a control structure. The status of the scriptlet
# then comes from inside the structure rather than from the closing token,
# so the statement is not treated as a bare command.
RE_CLOSER = re.compile(r'^(?:fi|done|esac|end|\})\s*;?$')

# A statement that opens or continues a control structure. A body that ends
# with one is a truncated fragment rather than a command, so it is skipped.
RE_OPENER = re.compile(
    r'^(?:if|then|else|elif|for|while|until|do|case|select|function)\b',
)

# An explicit success exit. It forces the status the clause asks for.
RE_EXIT_ZERO = re.compile(r'^exit\s+0\s*;?$')

# Any explicit exit. An "exit 1" that follows a "||" is the second half of a
# fallback the packager wrote on purpose, so it is not a bare command.
RE_EXIT_ANY = re.compile(r'^exit\s+\d+\s*;?$')

# A statement continued into the next one by a logical operator, which makes
# the next statement the chosen fallback rather than a bare command.
RE_CONTINUED = re.compile(r'(?:\|\||&&)\s*$')

# A "||" fallback. The status of "A || B" is the status of B, so the
# packager has already chosen what happens when A fails.
RE_FALLBACK = re.compile(r'\|\|')

# The transaction argument compared with a literal number. The quoting
# variants cover "[ $1 -eq 0 ]", '[ "$1" = 0 ]' and '[ "$1" == "0" ]'.
RE_ARGUMENT_COMPARE = re.compile(
    r'\$1["\']?\s*(?P<op>-eq|-ne|-gt|-ge|-lt|-le|==|!=|=)\s*'
    r'["\']?(?P<value>\d+)',
)

# A comparison that pins the argument to one exact count, which S4 reports
# when a parallel installable package can make the count larger.
EXACT_OPERATORS: frozenset[str] = frozenset({'-eq', '==', '='})

# The closed set of real RPM sections. A scriptlet body ends at the next
# entry, so the trigger family and the post transaction erase pair must be
# listed: leaving them out lets a trigger body or a "%postuntrans" body be
# read as part of the scriptlet above it.
KNOWN_SECTIONS: frozenset[str] = frozenset({
    '%package',
    '%description',
    '%prep',
    '%generate_buildrequires',
    '%conf',
    '%build',
    '%install',
    '%check',
    '%clean',
    '%files',
    '%changelog',
    '%sepolicy',
    '%pre',
    '%post',
    '%preun',
    '%postun',
    '%pretrans',
    '%posttrans',
    '%preuntrans',
    '%postuntrans',
    '%verifyscript',
    '%triggerprein',
    '%triggerin',
    '%triggerun',
    '%triggerpostun',
    '%filetriggerin',
    '%filetriggerun',
    '%filetriggerpostun',
    '%transfiletriggerin',
    '%transfiletriggerun',
    '%transfiletriggerpostun',
    '%end',
})

# The scriptlets the clause speaks about. The trigger family is excluded,
# because its arguments are package names rather than a transaction count.
SCRIPTLETS: frozenset[str] = frozenset({
    '%pre',
    '%post',
    '%preun',
    '%postun',
    '%pretrans',
    '%posttrans',
    '%verifyscript',
})

# The side of the transaction a scriptlet runs on. The supplement's table
# marks the erase state as not applicable to the install side.
INSTALL_SIDE: frozenset[str] = frozenset({
    '%pre',
    '%post',
    '%pretrans',
    '%posttrans',
})

UNINSTALL_SIDE: frozenset[str] = frozenset({'%preun', '%postun'})

# The count the supplement tabulates for the upgrade state of each side.
# A range test instead of this exact value keeps a parallel installable
# package working.
UPGRADE_COUNT: dict[str, str] = {
    '%pre': '2',
    '%post': '2',
    '%pretrans': '2',
    '%posttrans': '2',
    '%preun': '1',
    '%postun': '1',
}

# The range test that covers the tabulated count and every larger one.
UPGRADE_RANGE: dict[str, str] = {
    '%pre': '-gt 1',
    '%post': '-gt 1',
    '%pretrans': '-gt 1',
    '%posttrans': '-gt 1',
    '%preun': '-ge 1',
    '%postun': '-ge 1',
}

# The statement text is quoted inside the message, so a very long command
# such as an "alternatives --install" line with thirty followers is cut
# rather than reproduced in full.
STATEMENT_LIMIT = 120


class _Scriptlet(NamedTuple):
    """One scriptlet: its header line, its name, its flags and its body.

    ``line`` is the 1-based line of the header, ``flags`` is the header text
    after the section name, and ``body`` holds the joined statements as
    ``(1-based line, text)`` pairs.
    """

    line: int
    name: str
    flags: str
    body: list[tuple[int, str]]


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


def _shorten(text: str) -> str:
    """Cut a long command so that the message stays readable."""
    if len(text) <= STATEMENT_LIMIT:
        return text
    return text[:STATEMENT_LIMIT - 3] + '...'


def _has_p(flags: str) -> bool:
    """Return whether the header names a program with ``-p``."""
    return RE_P_FLAG.search(flags) is not None


def _marks(lines: list[str]) -> list[tuple[int, str, str]]:
    """Return the offset, name and flags of every known section header."""
    out: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        match = RE_SECTION.match(line)
        if match is None:
            continue
        name = '%' + match.group(1)
        if name not in KNOWN_SECTIONS:
            continue
        out.append((index, name, line[len(name):]))
    return out


def _statements(
    lines: list[str],
    start: int,
    stop: int,
) -> list[tuple[int, str]]:
    """Return the joined statements of one scriptlet body.

    ``start`` and ``stop`` are 0-based offsets, ``stop`` being exclusive.
    Blank lines, comments and conditional directives are dropped because
    they are not commands. A trailing backslash joins the next physical
    line, so a continued command is reported once, at the line where it
    begins.
    """
    out: list[tuple[int, str]] = []
    buffer = ''
    first = 0
    for offset in range(start, stop):
        text = lines[offset].strip()
        if not text or text.startswith('#'):
            continue
        if RE_DIRECTIVE.match(text) is not None:
            continue
        if not buffer:
            first = offset + 1
        if text.endswith('\\'):
            buffer += text[:-1] + ' '
            continue
        out.append((first, buffer + text))
        buffer = ''
    if buffer:
        out.append((first, buffer.rstrip()))
    return out


def _scriptlets(lines: list[str]) -> list[_Scriptlet]:
    """Return every scriptlet of the file, with its body already joined."""
    marks = _marks(lines)
    out: list[_Scriptlet] = []
    for pos, (index, name, flags) in enumerate(marks):
        if name not in SCRIPTLETS:
            continue
        stop = marks[pos + 1][0] if pos + 1 < len(marks) else len(lines)
        out.append(
            _Scriptlet(
                index + 1,
                name,
                flags,
                _statements(lines, index + 1, stop),
            ),
        )
    return out


def _check_single_program(item: _Scriptlet) -> list[str]:
    """S1: a single argument free program call uses the ``-p`` form."""
    if _has_p(item.flags) or len(item.body) != 1:
        return []
    _line, text = item.body[0]
    if RE_MACRO_CALL.match(text) is not None:
        return []
    tokens = text.split()
    if len(tokens) != 1:
        return []
    program = tokens[0]
    if RE_PROGRAM.match(program) is None:
        return []
    return [
        f'{item.name} (line {item.line}) runs the single program '
        f'"{program}" and gives it no argument; write '
        f'"{item.name} -p {program}" and leave the body empty',
    ]


def _bare_last_statement(item: _Scriptlet) -> tuple[int, str] | None:
    """Return the last statement when it decides the status on its own."""
    if _has_p(item.flags) or not item.body:
        return None
    # The third checkpoint reports the whole section, so reporting the
    # status of its body as well would only repeat the same advice.
    if item.name == '%pretrans':
        return None
    line, text = item.body[-1]
    text = text.strip().rstrip(';').strip()
    if RE_MACRO_CALL.match(text) is not None:
        return None
    if RE_CLOSER.match(text) is not None:
        return None
    if RE_OPENER.match(text) is not None:
        return None
    if text == '{':
        return None
    if RE_FALLBACK.search(text) is not None:
        return None
    if RE_EXIT_ZERO.match(text) is not None:
        return None
    if text in (':', 'true'):
        return None
    # The first checkpoint already tells the author to move this program
    # into the header, which removes the statement and the status with it.
    if len(item.body) == 1 and _check_single_program(item):
        return None
    # "cmd || exit 1" is a deliberate failure branch: the packager chose the
    # status, and the supplement only forbids forcing success on a command
    # that genuinely must succeed.
    if RE_EXIT_ANY.match(text) is not None and len(item.body) > 1:
        if RE_CONTINUED.search(item.body[-2][1]) is not None:
            return None
    return line, text


def _check_exit_status(item: _Scriptlet) -> list[str]:
    """S2: the scriptlet does not leave its status to a bare command."""
    last = _bare_last_statement(item)
    if last is None:
        return []
    _line, text = last
    return [
        f'{item.name} (line {item.line}) leaves the transaction status to '
        f'"{_shorten(text)}"; append "|| :" to the command or end the body '
        'with "exit 0"',
    ]


def _check_pretrans(item: _Scriptlet) -> list[str]:
    """S3: ``%pretrans`` runs before any package is installed."""
    if item.name != '%pretrans':
        return []
    return [
        f'{item.name} (line {item.line}) runs before any package is '
        'installed and therefore cannot rely on a program it needs; use '
        '"%posttrans" instead',
    ]


def _iter_comparisons(
    item: _Scriptlet,
) -> list[tuple[int, str, str]]:
    """Return every exact transaction argument test of the body.

    Each entry is ``(1-based line, operator, value)``. A statement that is
    a macro invocation is skipped, because the macro receives the argument
    rather than the shell.
    """
    out: list[tuple[int, str, str]] = []
    if _has_p(item.flags):
        return out
    for line, text in item.body:
        if RE_MACRO_CALL.match(text) is not None:
            continue
        match = RE_ARGUMENT_COMPARE.search(text)
        if match is None:
            continue
        operator = match.group('op')
        if operator not in EXACT_OPERATORS:
            continue
        out.append((line, operator, match.group('value')))
    return out


def _check_transaction_range(item: _Scriptlet) -> list[str]:
    """S4: the upgrade state is tested as a range, not as one count."""
    expected = UPGRADE_COUNT.get(item.name)
    if expected is None:
        return []
    suggestion = UPGRADE_RANGE[item.name]
    errors: list[str] = []
    for line, operator, value in _iter_comparisons(item):
        if value != expected:
            continue
        errors.append(
            f'{item.name} (line {line}) tests "$1" with "{operator}" '
            f'against "{value}"; a parallel installable package reports a '
            f'larger count, so write "{suggestion}" instead',
        )
    return errors


def _check_transaction_side(item: _Scriptlet) -> list[str]:
    """S5: an install side scriptlet never sees the erase count."""
    if item.name not in INSTALL_SIDE:
        return []
    errors: list[str] = []
    for line, _operator, value in _iter_comparisons(item):
        if value != '0':
            continue
        errors.append(
            f'{item.name} (line {line}) tests "$1" against "0"; an install '
            'side scriptlet never runs while a package is erased, so the '
            'branch is never taken; use "%postun" for the erase case',
        )
    return errors


def _check_spec_script_ext(
    filename: str,
    *,
    check_single_program: bool = True,
    check_exit_status: bool = True,
    check_pretrans: bool = True,
    check_transaction_range: bool = True,
    check_transaction_side: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    errors: list[str] = []
    for item in _scriptlets(lines):
        if check_single_program:
            errors.extend(_check_single_program(item))
        if check_exit_status:
            errors.extend(_check_exit_status(item))
        if check_pretrans:
            errors.extend(_check_pretrans(item))
        if check_transaction_range:
            errors.extend(_check_transaction_range(item))
        if check_transaction_side:
            errors.extend(_check_transaction_side(item))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_script(filename: str) -> list[str]:
    return _check_spec_script_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the scriptlets of openRuyi spec files.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-single-program',
        action='store_true',
        help='do not report a single program call without "-p"',
    )
    parser.add_argument(
        '--no-check-exit-status',
        action='store_true',
        help='do not report a scriptlet that leaves its status to a command',
    )
    parser.add_argument(
        '--no-check-pretrans',
        action='store_true',
        help='do not report the use of %pretrans',
    )
    parser.add_argument(
        '--no-check-transaction-range',
        action='store_true',
        help='do not report an exact test of the transaction argument',
    )
    parser.add_argument(
        '--no-check-transaction-side',
        action='store_true',
        help='do not report an erase test inside an install side scriptlet',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_script_ext(
            filename,
            check_single_program=not args.no_check_single_program,
            check_exit_status=not args.no_check_exit_status,
            check_pretrans=not args.no_check_pretrans,
            check_transaction_range=not args.no_check_transaction_range,
            check_transaction_side=not args.no_check_transaction_side,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret


if __name__ == '__main__':
    raise SystemExit(main())
