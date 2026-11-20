# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check-spec-build-autotools."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_build_autotools import _check_spec_build_autotools
from openruyi_precommit_hooks.check_spec_build_autotools import _check_spec_build_autotools_ext
from openruyi_precommit_hooks.check_spec_build_autotools import main


CLEAN_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
URL:            https://example.org/demo
Source0:        https://example.org/demo-1.0.tar.gz
BuildArch:      noarch
BuildSystem:    autotools
BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  libtool
BuildRequires:  make

%description
A demo package.
"""

NOT_AUTOTOOLS_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildSystem:    cmake
BuildRequires:  cmake

%description
A demo package.
"""

NO_BUILD_SYSTEM_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildRequires:  gcc

%description
A demo package.
"""

DYNAMIC_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildSystem:    autotools
BuildRequires:  make

%package
%description
A demo package.

%generate_buildrequires
echo autoconf
"""


def _write(tmp_path: Path, content: str) -> str:
    path = tmp_path / 'demo.spec'
    path.write_text(content, encoding='utf-8')
    return str(path)


def _messages(tmp_path: Path, content: str) -> list[str]:
    return [
        err.split(': ', 1)[1]
        for err in _check_spec_build_autotools(_write(tmp_path, content))
    ]


def _single_error(tmp_path: Path, content: str) -> str:
    messages = _messages(tmp_path, content)
    assert len(messages) == 1, messages
    return messages[0]


# --------------------------------------------------------------------------
# C1 - the four tools are declared.
# --------------------------------------------------------------------------


def test_clean_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_build_autotools(_write(tmp_path, CLEAN_SPEC)) == []


def test_missing_one_tool_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  libtool\n', '')
    message = _single_error(tmp_path, spec)
    assert 'missing "libtool"' in message


def test_all_four_tools_missing_is_one_finding(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  autoconf\n'
        'BuildRequires:  automake\n'
        'BuildRequires:  libtool\n'
        'BuildRequires:  make\n',
        '',
    )
    message = _single_error(tmp_path, spec)
    assert 'autoconf' in message
    assert 'automake' in message
    assert 'libtool' in message
    assert 'make' in message


def test_missing_tools_are_listed_in_guideline_order(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  autoconf\n', '')
    spec = spec.replace('BuildRequires:  libtool\n', '')
    message = _single_error(tmp_path, spec)
    assert 'missing "autoconf" and "libtool"' in message


def test_gcc_alone_does_not_satisfy_the_requirement(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  autoconf\n'
        'BuildRequires:  automake\n'
        'BuildRequires:  libtool\n'
        'BuildRequires:  make\n',
        'BuildRequires:  gcc\n',
    )
    messages = _messages(tmp_path, spec)
    assert len(messages) == 1
    assert 'gcc' not in messages[0]


def test_declaring_gcc_is_not_required(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  make\n',
        'BuildRequires:  make\nBuildRequires:  gcc\n',
    )
    assert _check_spec_build_autotools(_write(tmp_path, spec)) == []


# --------------------------------------------------------------------------
# Name matching must be exact.
# --------------------------------------------------------------------------


def test_autoconf_archive_does_not_satisfy_autoconf(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  autoconf\n',
        'BuildRequires:  autoconf-archive\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'missing "autoconf"' in message


def test_autoconf_archive_alongside_autoconf_passes(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  autoconf\n',
        'BuildRequires:  autoconf\nBuildRequires:  autoconf-archive\n',
    )
    assert _check_spec_build_autotools(_write(tmp_path, spec)) == []


def test_dependency_name_is_case_insensitive(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  autoconf\n',
        'BuildRequires:  Autoconf\n',
    )
    assert _check_spec_build_autotools(_write(tmp_path, spec)) == []


def test_versioned_dependency_still_counts(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  libtool\n',
        'BuildRequires:  libtool >= 2.4\n',
    )
    assert _check_spec_build_autotools(_write(tmp_path, spec)) == []


def test_rich_dependency_is_ignored(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  libtool\n',
        'BuildRequires:  (libtool if gcc)\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'missing "libtool"' in message


def test_several_dependencies_on_one_line_are_all_seen(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  autoconf\n'
        'BuildRequires:  automake\n'
        'BuildRequires:  libtool\n'
        'BuildRequires:  make\n',
        'BuildRequires:  autoconf, automake, libtool, make\n',
    )
    assert _check_spec_build_autotools(_write(tmp_path, spec)) == []


# --------------------------------------------------------------------------
# When the rule is silent.
# --------------------------------------------------------------------------


def test_non_autotools_spec_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_autotools(
        _write(tmp_path, NOT_AUTOTOOLS_SPEC),
    ) == []


def test_spec_without_build_system_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_autotools(
        _write(tmp_path, NO_BUILD_SYSTEM_SPEC),
    ) == []


def test_dynamic_generator_spec_is_skipped(tmp_path: Path) -> None:
    assert _check_spec_build_autotools(
        _write(tmp_path, DYNAMIC_SPEC),
    ) == []


def test_dynamic_generator_can_be_checked_on_demand(
    tmp_path: Path,
) -> None:
    errors = _check_spec_build_autotools_ext(
        _write(tmp_path, DYNAMIC_SPEC),
        check_dynamic=True,
    )
    assert len(errors) == 1
    assert 'missing' in errors[0]


def test_value_case_is_accepted(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildSystem:    autotools',
        'BuildSystem:    Autotools',
    )
    assert _check_spec_build_autotools(_write(tmp_path, spec)) == []


def test_dependency_in_a_later_block_is_accepted(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  make\n',
        '\n%package        extra\nSummary:        Extra files\n'
        'BuildRequires:  make\n',
    )
    assert _check_spec_build_autotools(_write(tmp_path, spec)) == []


def test_commented_dependency_does_not_count(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  libtool\n',
        '# BuildRequires:  libtool\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'missing "libtool"' in message


def test_field_inside_a_macro_body_does_not_count(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  libtool\n',
        '%global deps %{expand:\n'
        'BuildRequires:  libtool\n'
        '}\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'missing "libtool"' in message


# --------------------------------------------------------------------------
# Boundary behaviour.
# --------------------------------------------------------------------------


def test_finding_names_the_system_line(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  libtool\n', '')
    message = _single_error(tmp_path, spec)
    assert 'line 9' in message


def test_missing_file_reports_once(tmp_path: Path) -> None:
    errors = _check_spec_build_autotools(str(tmp_path / 'absent.spec'))
    assert len(errors) == 1
    assert 'absent.spec' in errors[0]


def test_invalid_utf8_reports_once(tmp_path: Path) -> None:
    path = tmp_path / 'demo.spec'
    path.write_bytes(b'Name: demo\nSummary: \xff\xfe\n')
    errors = _check_spec_build_autotools(str(path))
    assert len(errors) == 1
    assert 'UTF-8' in errors[0]


def test_error_is_prefixed_with_the_filename(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  make\n', '')
    path = _write(tmp_path, spec)
    errors = _check_spec_build_autotools(path)
    assert errors[0].startswith(f'{path}: ')


# --------------------------------------------------------------------------
# Flags.
# --------------------------------------------------------------------------


def test_flag_disables_the_check(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  make\n', '')
    path = _write(tmp_path, spec)
    assert _check_spec_build_autotools_ext(
        path,
        check_buildrequires=False,
    ) == []


def test_disabled_check_returns_no_finding(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  make\n', '')
    path = _write(tmp_path, spec)
    assert _check_spec_build_autotools_ext(
        path,
        check_buildrequires=False,
    ) == []


# --------------------------------------------------------------------------
# CLI.
# --------------------------------------------------------------------------


def test_main_returns_zero_for_clean_spec(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, CLEAN_SPEC)
    assert main([path]) == 0
    assert capsys.readouterr().out == ''


def test_main_returns_one_and_prints_findings(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  make\n', '')
    path = _write(tmp_path, spec)
    assert main([path]) == 1
    out = capsys.readouterr().out
    assert 'missing "make"' in out
    assert path in out


def test_main_honours_disable_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  make\n', '')
    path = _write(tmp_path, spec)
    assert main([path, '--no-check-buildrequires']) == 0
    assert capsys.readouterr().out == ''


def test_main_honours_check_dynamic_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, DYNAMIC_SPEC)
    assert main([path]) == 0
    capsys.readouterr()
    assert main([path, '--check-dynamic']) == 1
    assert 'missing' in capsys.readouterr().out


def test_main_without_filenames_returns_zero() -> None:
    assert main([]) == 0
