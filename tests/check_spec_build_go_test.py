# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check-spec-build-go."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_build_go import _check_spec_build_go
from openruyi_precommit_hooks.check_spec_build_go import _check_spec_build_go_ext
from openruyi_precommit_hooks.check_spec_build_go import main


CLEAN_SPEC = """\
%define _name           demo
%define go_import_path  github.com/example/demo

Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
URL:            https://example.org/demo
Source0:        https://example.org/demo-1.0.tar.gz
BuildSystem:    golangmodules
BuildRequires:  go
BuildRequires:  go-rpm-macros

%description
A demo package.
"""

GOLANG_SPEC = CLEAN_SPEC.replace('golangmodules', 'golang')

NOT_GO_SPEC = """\
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


def _write(tmp_path: Path, content: str) -> str:
    path = tmp_path / 'demo.spec'
    path.write_text(content, encoding='utf-8')
    return str(path)


def _messages(tmp_path: Path, content: str) -> list[str]:
    return [
        err.split(': ', 1)[1]
        for err in _check_spec_build_go(_write(tmp_path, content))
    ]


def _single_error(tmp_path: Path, content: str) -> str:
    messages = _messages(tmp_path, content)
    assert len(messages) == 1, messages
    return messages[0]


# --------------------------------------------------------------------------
# Scope - only a Go spec is judged.
# --------------------------------------------------------------------------


def test_clean_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_build_go(_write(tmp_path, CLEAN_SPEC)) == []


def test_golang_system_is_checked(tmp_path: Path) -> None:
    assert _check_spec_build_go(_write(tmp_path, GOLANG_SPEC)) == []


def test_non_go_spec_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_go(_write(tmp_path, NOT_GO_SPEC)) == []


def test_spec_without_build_system_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_go(
        _write(tmp_path, NO_BUILD_SYSTEM_SPEC),
    ) == []


def test_unreadable_file_reports_error(tmp_path: Path) -> None:
    missing = str(tmp_path / 'missing.spec')
    errors = _check_spec_build_go(missing)
    assert len(errors) == 1
    assert errors[0].startswith(missing)


def test_utf8_error_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'demo.spec'
    path.write_bytes(b'Name: \xff\xfe\n')
    errors = _check_spec_build_go(str(path))
    assert errors == [f'{path}: file is not valid UTF-8']


# --------------------------------------------------------------------------
# C1 - both Go build dependencies must be declared.
# --------------------------------------------------------------------------


def test_missing_go_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  go\n', '')
    message = _single_error(tmp_path, content)
    assert 'requires "go" and "go-rpm-macros" in BuildRequires' in message
    assert 'missing "go"' in message


def test_missing_go_rpm_macros_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  go-rpm-macros\n', '')
    message = _single_error(tmp_path, content)
    assert 'missing "go-rpm-macros"' in message


def test_missing_both_dependencies_is_two_findings(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  go\n', '')
    content = content.replace('BuildRequires:  go-rpm-macros\n', '')
    messages = _messages(tmp_path, content)
    assert len(messages) == 2
    assert any('missing "go"' in m for m in messages)
    assert any('missing "go-rpm-macros"' in m for m in messages)


def test_versioned_dependency_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  go\n', 'BuildRequires:  go >= 1.26.8\n')
    assert _check_spec_build_go(_write(tmp_path, content)) == []


def test_rich_dependency_does_not_satisfy_go(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  go\n',
        'BuildRequires:  go(github.com/example/demo)\n',
    )
    message = _single_error(tmp_path, content)
    assert 'missing "go"' in message


def test_commented_dependency_does_not_count(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  go\n',
        '# BuildRequires:  go\n',
    )
    message = _single_error(tmp_path, content)
    assert 'missing "go"' in message


def test_dependency_in_subpackage_counts(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  go\n', '')
    content += """
%package doc
Summary:        Documentation
BuildRequires:  go
BuildRequires:  go-rpm-macros

%description doc
Documentation.
"""
    assert _check_spec_build_go(_write(tmp_path, content)) == []


def test_go_buildsystem_is_recognised(tmp_path: Path) -> None:
    content = GOLANG_SPEC.replace('BuildRequires:  go-rpm-macros\n', '')
    message = _single_error(tmp_path, content)
    assert message.startswith('BuildSystem: golang (line 11)')


def test_buildsystem_is_case_insensitive(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildSystem:    golangmodules',
        'Buildsystem:    GolangModules',
    )
    assert _check_spec_build_go(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# C2 - the _name macro must be defined in the header.
# --------------------------------------------------------------------------


def test_missing_name_macro_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('%define _name           demo\n', '')
    message = _single_error(tmp_path, content)
    assert 'requires the "_name" macro in the header' in message
    assert 'no %define or %global sets it' in message


def test_global_name_macro_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('%define _name', '%global _name')
    assert _check_spec_build_go(_write(tmp_path, content)) == []


def test_name_macro_after_first_section_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%define _name           demo\n', '',
    ).replace(
        '%description\nA demo package.\n',
        '%description\nA demo package.\n\n%build\n%define _name demo\n',
    )
    messages = _messages(tmp_path, content)
    assert len(messages) == 1
    assert 'defines it after the first section' in messages[0]


def test_name_macro_with_tab_separator_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%define _name           demo',
        '%define\t_name\tdemo',
    )
    assert _check_spec_build_go(_write(tmp_path, content)) == []


def test_commented_name_macro_does_not_count(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%define _name           demo\n',
        '# %define _name           demo\n',
    )
    message = _single_error(tmp_path, content)
    assert 'no %define or %global sets it' in message


# --------------------------------------------------------------------------
# C3 - the go_import_path macro must be defined in the header.
# --------------------------------------------------------------------------


def test_missing_import_path_macro_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%define go_import_path  github.com/example/demo\n', '',
    )
    message = _single_error(tmp_path, content)
    assert 'requires the "go_import_path" macro in the header' in message


def test_similarly_named_macro_does_not_satisfy(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%define go_import_path  github.com/example/demo\n',
        '%define api_import_path  github.com/example/demo/api\n',
    )
    message = _single_error(tmp_path, content)
    assert 'requires the "go_import_path" macro in the header' in message


def test_import_path_after_first_section_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%define go_import_path  github.com/example/demo\n', '',
    ).replace(
        '%description\nA demo package.\n',
        '%description\nA demo package.\n\n%prep\n'
        '%define go_import_path github.com/example/demo\n',
    )
    messages = _messages(tmp_path, content)
    assert len(messages) == 1
    assert 'defines it after the first section' in messages[0]


# --------------------------------------------------------------------------
# Combinations.
# --------------------------------------------------------------------------


def test_all_three_findings_at_once(tmp_path: Path) -> None:
    content = """\
Name:           kata-containers
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildSystem:    golang
BuildRequires:  git
BuildRequires:  make

%build
make -C src
"""
    messages = _messages(tmp_path, content)
    assert len(messages) == 4
    assert any('missing "go"' in m for m in messages)
    assert any('missing "go-rpm-macros"' in m for m in messages)
    assert any('"_name"' in m for m in messages)
    assert any('"go_import_path"' in m for m in messages)


def test_findings_of_one_spec_are_prefixed(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        CLEAN_SPEC.replace('BuildRequires:  go\n', ''),
    )
    errors = _check_spec_build_go(path)
    assert all(err.startswith(f'{path}: ') for err in errors)


# --------------------------------------------------------------------------
# Flags.
# --------------------------------------------------------------------------


def test_no_check_buildrequires_skips_c1(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  go\n', '')
    path = _write(tmp_path, content)
    assert _check_spec_build_go_ext(path, check_buildrequires=False) == []


def test_no_check_name_macro_skips_c2(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('%define _name           demo\n', '')
    path = _write(tmp_path, content)
    assert _check_spec_build_go_ext(path, check_name_macro=False) == []


def test_no_check_import_path_macro_skips_c3(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%define go_import_path  github.com/example/demo\n', '',
    )
    path = _write(tmp_path, content)
    assert _check_spec_build_go_ext(
        path, check_import_path_macro=False,
    ) == []


def test_all_checks_disabled_returns_nothing(tmp_path: Path) -> None:
    content = """\
Name:           demo
BuildSystem:    golang

%description
A demo package.
"""
    path = _write(tmp_path, content)
    assert _check_spec_build_go_ext(
        path,
        check_buildrequires=False,
        check_name_macro=False,
        check_import_path_macro=False,
    ) == []


# --------------------------------------------------------------------------
# Command line.
# --------------------------------------------------------------------------


def test_main_returns_zero_for_clean_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, CLEAN_SPEC)
    assert main([path]) == 0
    assert capsys.readouterr().out == ''


def test_main_returns_one_for_failing_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, CLEAN_SPEC.replace('BuildRequires:  go\n', ''))
    assert main([path]) == 1
    assert 'missing "go"' in capsys.readouterr().out


def test_main_without_arguments_returns_zero() -> None:
    assert main([]) == 0


def test_main_honours_no_check_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, CLEAN_SPEC.replace('BuildRequires:  go\n', ''))
    assert main([path, '--no-check-buildrequires']) == 0
    assert capsys.readouterr().out == ''
