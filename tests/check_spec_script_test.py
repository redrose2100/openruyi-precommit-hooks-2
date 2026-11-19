# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_script import _check_spec_script
from openruyi_precommit_hooks.check_spec_script import (
    _check_spec_script_ext,
)
from openruyi_precommit_hooks.check_spec_script import main

# A spec whose scriptlets satisfy every checkpoint: the program is named by
# "-p", the shell bodies end with "exit 0" or a "|| :" fallback, no
# %pretrans is written and every transaction test is a range test.
CLEAN_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%post -p /sbin/ldconfig

%postun -p /sbin/ldconfig

%posttrans
%{_bindir}/fc-cache -s || :

%preun
if [ "$1" -ge 1 ]; then
    %{_bindir}/foo --remove-alternatives || :
fi

%post
if [ "$1" -gt 1 ]; then
    %{_bindir}/foo --upgrade || :
fi
exit 0

%files
%license LICENSE

%changelog
%autochangelog
"""

# A spec that writes no scriptlet at all. Everything stays silent.
NO_SCRIPTLET_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The corpus shape that a naive section detector breaks on: "%systemd_post"
# and "%sysusers_create_package" are macro calls inside the body, not
# section headers, so the body must not be cut short at them.
MACRO_BODY_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%post
%systemd_post foo.service

%preun
%systemd_preun foo.service

%postun
%systemd_postun_with_restart foo.service

%files
%license LICENSE

%changelog
%autochangelog
"""

# A scriptlet body that is a single argument free program call, the defect
# measured in bluez. The first checkpoint reports the header form, and it
# subsumes the status of the single statement, so exactly one finding is
# expected.
SINGLE_PROGRAM_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%post
/sbin/udevadm

%files
%license LICENSE

%changelog
%autochangelog
"""

# A program call that carries an argument. "-p" names the program that runs
# the body, so the argument would be lost and the form does not apply. The
# "|| :" fallback keeps the status clean, so only the header form is at
# stake here.
PROGRAM_WITH_ARGUMENT_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%post
/sbin/udevadm trigger --subsystem-match=usb || :

%files
%license LICENSE

%changelog
%autochangelog
"""

# A body that ends with a bare command, the defect clause 2 describes.
BARE_STATUS_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%post
%{_bindir}/fc-cache -fs

%files
%license LICENSE

%changelog
%autochangelog
"""

# The %pretrans the supplement advises against. The body forces success, so
# the section is the only thing at stake.
PRETRANS_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%pretrans
mkdir -p %{_localstatedir}/cache/foo || :

%files
%license LICENSE

%changelog
%autochangelog
"""

# An install side scriptlet that writes the erase handler, which never runs.
WRONG_SIDE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%post
if [ "$1" -eq 0 ]; then
    %{_bindir}/foo --clean || :
fi
exit 0

%files
%license LICENSE

%changelog
%autochangelog
"""

# The exact upgrade count that a parallel installable package breaks.
EXACT_COUNT_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%post
if [ "$1" = "2" ]; then
    %{_bindir}/foo --upgrade || :
fi
exit 0

%files
%license LICENSE

%changelog
%autochangelog
"""

# The exact upgrade count in an erase scriptlet, whose tabulated value is 1.
EXACT_UNINSTALL_COUNT_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%preun
if [ "$1" -eq 1 ]; then
    %{_bindir}/foo --upgrade-uninstall || :
fi
exit 0

%files
%license LICENSE

%changelog
%autochangelog
"""

# A trigger body is a scriptlet in name only: its arguments are package
# names rather than a transaction count, so it is a boundary that is never
# checked, and its body must never be read as part of the scriptlet above.
TRIGGER_BOUNDARY_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%transfiletriggerin -- /usr/share/fonts
%{_bindir}/fc-cache -s

%files
%license LICENSE

%changelog
%autochangelog
"""

# "%postuntrans" is a real section but sits outside the supplement table. It
# must still end the "%postun" body above it.
POSTUNTRANS_BOUNDARY_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%postun
%{_bindir}/fc-cache -s || :

%postuntrans
mkdir -p %{_localstatedir}/cache/foo

%files
%license LICENSE

%changelog
%autochangelog
"""

# A Lua scriptlet names its interpreter with "-p <lua>", so the body is Lua
# rather than shell and the shell checkpoints must leave it alone.
LUA_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%post -p <lua>
if posix.access("/usr/sbin/ldconfig", "x") then
  rpm.spawn({"/usr/sbin/ldconfig"})
end

%postun -p <lua>
rpm.spawn({"/usr/sbin/ldconfig"})

%files
%license LICENSE

%changelog
%autochangelog
"""

# A package qualified header. "-n" names the package rather than the
# program, so the body is still shell and is still checked.
PACKAGE_FLAG_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%post -n foo
%systemd_post foo.service

%preun -n foo
%systemd_preun foo.service

%files
%license LICENSE

%changelog
%autochangelog
"""


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    return str(path)


def _spec_with_body(name: str, body: str) -> str:
    return f"""\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

{name}
{body}

%files
%license LICENSE

%changelog
%autochangelog
"""


@pytest.mark.parametrize(
    'content',
    [
        pytest.param(CLEAN_SPEC, id='clean'),
        pytest.param(NO_SCRIPTLET_SPEC, id='no-scriptlet'),
        pytest.param(MACRO_BODY_SPEC, id='macro-body'),
        pytest.param(PROGRAM_WITH_ARGUMENT_SPEC, id='program-with-argument'),
        pytest.param(TRIGGER_BOUNDARY_SPEC, id='trigger-boundary'),
        pytest.param(POSTUNTRANS_BOUNDARY_SPEC, id='postuntrans-boundary'),
        pytest.param(LUA_SPEC, id='lua-scriptlet'),
        pytest.param(PACKAGE_FLAG_SPEC, id='package-name-flag'),
        pytest.param(
            _spec_with_body(
                '%post',
                '%{_bindir}/foo --install >/dev/null || :',
            ),
            id='output-redirect',
        ),
        pytest.param(
            _spec_with_body('%post', 'true'),
            id='last-statement-true',
        ),
        pytest.param(
            _spec_with_body('%post', ':'),
            id='last-statement-colon',
        ),
        pytest.param(
            _spec_with_body('%post', '%{_bindir}/foo --install || true'),
            id='fallback-true',
        ),
        pytest.param(
            _spec_with_body(
                '%post',
                'if [ "$1" -gt 1 ]; then\n'
                '    %{_bindir}/foo upgrade || :\n'
                'fi',
            ),
            id='ends-with-control-closer',
        ),
        pytest.param(
            _spec_with_body('%post', 'exit 0'),
            id='explicit-success-exit',
        ),
        pytest.param(
            _spec_with_body(
                '%post',
                '%{_bindir}/foo --install ||\n    exit 1',
            ),
            id='deliberate-failure-is-kept',
        ),
        pytest.param(
            _spec_with_body(
                '%preun',
                'if [ "$1" -ge 1 ]; then\n'
                '    %{_bindir}/foo remove || :\n'
                'fi',
            ),
            id='range-test-on-uninstall',
        ),
        pytest.param(
            _spec_with_body(
                '%post',
                'if [ "$1" -gt 1 ]; then\n'
                '    %{_bindir}/foo upgrade || :\n'
                'fi',
            ),
            id='install-side-range-test',
        ),
    ],
)
def test_passing_specs(tmp_path: Path, content: str) -> None:
    path = _write(tmp_path, 'foo.spec', content)
    assert _check_spec_script(path) == []


@pytest.mark.parametrize(
    ('content', 'expected'),
    [
        pytest.param(
            SINGLE_PROGRAM_SPEC,
            '%post (line 12) runs the single program "/sbin/udevadm" and '
            'gives it no argument; write "%post -p /sbin/udevadm" and '
            'leave the body empty',
            id='single-program',
        ),
        pytest.param(
            BARE_STATUS_SPEC,
            '%post (line 12) leaves the transaction status to '
            '"%{_bindir}/fc-cache -fs"; append "|| :" to the command or '
            'end the body with "exit 0"',
            id='bare-status',
        ),
        pytest.param(
            PRETRANS_SPEC,
            '%pretrans (line 12) runs before any package is installed and '
            'therefore cannot rely on a program it needs; use "%posttrans" '
            'instead',
            id='pretrans',
        ),
        pytest.param(
            WRONG_SIDE_SPEC,
            '%post (line 13) tests "$1" against "0"; an install side '
            'scriptlet never runs while a package is erased, so the branch '
            'is never taken; use "%postun" for the erase case',
            id='wrong-side',
        ),
        pytest.param(
            EXACT_COUNT_SPEC,
            '%post (line 13) tests "$1" with "=" against "2"; a parallel '
            'installable package reports a larger count, so write "-gt 1" '
            'instead',
            id='exact-install-count',
        ),
        pytest.param(
            EXACT_UNINSTALL_COUNT_SPEC,
            '%preun (line 13) tests "$1" with "-eq" against "1"; a parallel '
            'installable package reports a larger count, so write "-ge 1" '
            'instead',
            id='exact-uninstall-count',
        ),
    ],
)
def test_failing_specs(
    tmp_path: Path,
    content: str,
    expected: str,
) -> None:
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_script(path)
    assert len(errors) == 1
    assert errors[0] == f'{path}: {expected}'


def test_empty_pretrans_body_is_reported(tmp_path: Path) -> None:
    """The %pretrans rule is about the section, not about its body."""
    content = _spec_with_body('%pretrans', '')
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_script(path)
    assert len(errors) == 1
    assert '%pretrans' in errors[0]


def test_continued_command_reported_once(tmp_path: Path) -> None:
    """A backslash continuation is one statement, at its first line."""
    content = _spec_with_body(
        '%post',
        '%{_bindir}/xmlcatalog --noout \\\n'
        '    --add system foo \\\n'
        '    %{_sysconfdir}/xml/catalog',
    )
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_script(path)
    assert len(errors) == 1
    assert '(line 12)' in errors[0]
    assert '--add system foo' in errors[0]


def test_long_command_is_shortened(tmp_path: Path) -> None:
    """A thirty follower call must not be reproduced in full."""
    followers = ' '.join(
        f'--slave /usr/share/man/man1/{n}.1.gz {n}-man /usr/bin/{n}'
        for n in ('java', 'javac', 'jlink', 'jmod', 'jar', 'jarsigner')
    )
    content = _spec_with_body(
        '%post',
        f'alternatives --install /usr/bin/java java '
        f'/usr/lib/jvm/bin/java 17 {followers}',
    )
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_script(path)
    assert len(errors) == 1
    message = errors[0].removeprefix(f'{path}: ')
    assert '...' in message
    assert len(message) < 300


def test_macro_invocation_is_not_checked(tmp_path: Path) -> None:
    """A macro owns its own status handling, so its body is skipped."""
    content = _spec_with_body(
        '%post',
        '%sysusers_create_package foo %{SOURCE4}',
    )
    path = _write(tmp_path, 'foo.spec', content)
    assert _check_spec_script(path) == []


def test_macro_expansion_is_still_a_command(tmp_path: Path) -> None:
    """A "%{_bindir}/foo" path is a command, unlike a macro invocation."""
    content = _spec_with_body(
        '%post',
        '%{_bindir}/foo --install',
    )
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_script(path)
    assert len(errors) == 1
    assert 'transaction status' in errors[0]


def test_macro_is_not_a_section_boundary(tmp_path: Path) -> None:
    """A "%systemd_post" call must not cut the body of its scriptlet."""
    content = _spec_with_body(
        '%post',
        '%systemd_post foo.service\n'
        '/sbin/udevadm',
    )
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_script(path)
    assert len(errors) == 1
    assert '"/sbin/udevadm"' in errors[0]


def test_comment_and_blank_lines_are_ignored(tmp_path: Path) -> None:
    """The last statement is decided by code, not by a trailing comment."""
    content = _spec_with_body(
        '%post',
        '%{_bindir}/foo --install || :\n'
        '\n'
        '# a trailing comment',
    )
    path = _write(tmp_path, 'foo.spec', content)
    assert _check_spec_script(path) == []


def test_multiple_findings_in_one_spec(tmp_path: Path) -> None:
    """Each checkpoint reports independently."""
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    autotools

%description
An example package.

%pretrans
mkdir -p %{_localstatedir}/cache/foo

%post
/sbin/udevadm

%files
%license LICENSE

%changelog
%autochangelog
"""
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_script(path)
    assert len(errors) == 2
    assert any('%pretrans' in e for e in errors)
    assert any('single program' in e for e in errors)


def test_flags_disable_checkpoints(tmp_path: Path) -> None:
    single = _write(tmp_path, 'a.spec', SINGLE_PROGRAM_SPEC)
    assert _check_spec_script_ext(single, check_single_program=False) == []

    status = _write(tmp_path, 'b.spec', BARE_STATUS_SPEC)
    assert _check_spec_script_ext(status, check_exit_status=False) == []

    pretrans = _write(tmp_path, 'c.spec', PRETRANS_SPEC)
    assert _check_spec_script_ext(pretrans, check_pretrans=False) == []

    exact = _write(tmp_path, 'd.spec', EXACT_COUNT_SPEC)
    assert _check_spec_script_ext(exact, check_transaction_range=False) == []

    side = _write(tmp_path, 'e.spec', WRONG_SIDE_SPEC)
    assert _check_spec_script_ext(side, check_transaction_side=False) == []


def test_flags_keep_other_checkpoints(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', SINGLE_PROGRAM_SPEC)
    errors = _check_spec_script_ext(path, check_pretrans=False)
    assert len(errors) == 1
    assert 'single program' in errors[0]


def test_missing_file_reported() -> None:
    missing = str(Path('does') / 'not' / 'exist.spec')
    errors = _check_spec_script(missing)
    assert len(errors) == 1
    assert errors[0].startswith(missing)


def test_non_utf8_file_reported(tmp_path: Path) -> None:
    path = tmp_path / 'latin.spec'
    path.write_bytes(b'Name: foo\nSummary: caf\xe9\n')
    errors = _check_spec_script(str(path))
    assert errors == [f'{path}: file is not valid UTF-8']


def test_main_returns_zero_for_clean_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', CLEAN_SPEC)
    assert main([path]) == 0
    assert capsys.readouterr().out == ''


def test_main_returns_zero_without_filenames() -> None:
    assert main([]) == 0


def test_main_returns_one_for_failing_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', SINGLE_PROGRAM_SPEC)
    assert main([path]) == 1
    assert path in capsys.readouterr().out


def test_main_reports_every_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    first = _write(tmp_path, 'a.spec', SINGLE_PROGRAM_SPEC)
    second = _write(tmp_path, 'b.spec', BARE_STATUS_SPEC)
    assert main([first, second]) == 1
    out = capsys.readouterr().out
    assert first in out
    assert second in out


@pytest.mark.parametrize(
    'flag',
    [
        pytest.param('--no-check-single-program', id='single-program'),
        pytest.param('--no-check-exit-status', id='exit-status'),
        pytest.param('--no-check-pretrans', id='pretrans'),
        pytest.param('--no-check-transaction-range', id='range'),
        pytest.param('--no-check-transaction-side', id='side'),
    ],
)
def test_main_no_check_flags(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    flag: str,
) -> None:
    body = {
        '--no-check-single-program': SINGLE_PROGRAM_SPEC,
        '--no-check-exit-status': BARE_STATUS_SPEC,
        '--no-check-pretrans': PRETRANS_SPEC,
        '--no-check-transaction-range': EXACT_COUNT_SPEC,
        '--no-check-transaction-side': WRONG_SIDE_SPEC,
    }[flag]
    path = _write(tmp_path, 'foo.spec', body)
    assert main([flag, path]) == 0
    assert capsys.readouterr().err == ''
