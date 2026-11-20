# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check-spec-build-meson."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_build_meson import (
    _check_spec_build_meson,
)
from openruyi_precommit_hooks.check_spec_build_meson import (
    _check_spec_build_meson_ext,
)
from openruyi_precommit_hooks.check_spec_build_meson import main


CLEAN_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
URL:            https://example.org/demo
Source0:        https://example.org/demo-1.0.tar.gz
BuildSystem:    meson
BuildRequires:  meson
BuildOption(conf):  -Dman=enabled

%description
A demo package.
"""

NOT_MESON_SPEC = """\
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
BuildOption(conf):  -Dman=enabled

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
        for err in _check_spec_build_meson(_write(tmp_path, content))
    ]


def _single_error(tmp_path: Path, content: str) -> str:
    messages = _messages(tmp_path, content)
    assert len(messages) == 1, messages
    return messages[0]


# --------------------------------------------------------------------------
# Scope - only a meson spec is judged.
# --------------------------------------------------------------------------


def test_clean_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_build_meson(_write(tmp_path, CLEAN_SPEC)) == []


def test_non_meson_spec_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_meson(_write(tmp_path, NOT_MESON_SPEC)) == []


def test_spec_without_build_system_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_meson(
        _write(tmp_path, NO_BUILD_SYSTEM_SPEC),
    ) == []


def test_unreadable_file_reports_error(tmp_path: Path) -> None:
    missing = str(tmp_path / 'missing.spec')
    errors = _check_spec_build_meson(missing)
    assert len(errors) == 1
    assert errors[0].startswith(missing)


def test_utf8_error_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'demo.spec'
    path.write_bytes(b'Name: \xff\xfe\n')
    errors = _check_spec_build_meson(str(path))
    assert errors == [f'{path}: file is not valid UTF-8']


# --------------------------------------------------------------------------
# C1 - meson must be declared in BuildRequires.
# --------------------------------------------------------------------------


def test_c1_missing_dependency_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  meson\n', '')
    assert 'missing "meson"' in _single_error(tmp_path, content)


def test_c1_message_names_the_system_and_the_line(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  meson\n', '')
    message = _single_error(tmp_path, content)
    assert 'BuildSystem: meson (line 8)' in message
    assert 'requires "meson" in BuildRequires' in message


def test_c1_versioned_dependency_satisfies(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  meson',
        'BuildRequires:  meson >= 1.4.0',
    )
    assert _check_spec_build_meson(_write(tmp_path, content)) == []


def test_c1_commented_dependency_does_not_count(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  meson',
        '# BuildRequires:  meson',
    )
    assert 'missing "meson"' in _single_error(tmp_path, content)


def test_c1_subpackage_dependency_counts(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  meson\n', '') + """
%package devel
Summary:        Development files
BuildRequires:  meson
"""
    assert _check_spec_build_meson(_write(tmp_path, content)) == []


def test_c1_prefix_name_does_not_satisfy(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  meson',
        'BuildRequires:  meson-python',
    )
    assert 'missing "meson"' in _single_error(tmp_path, content)


def test_c1_rich_dependency_does_not_satisfy(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  meson',
        'BuildRequires:  pkgconfig(meson)',
    )
    assert 'missing "meson"' in _single_error(tmp_path, content)


# --------------------------------------------------------------------------
# C2 - a meson option must sit in BuildOption(conf).
# --------------------------------------------------------------------------


def test_c2_option_in_section_body_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  -Dman=enabled\n',
        '',
    ) + """
%check
%meson -Dman=enabled
"""
    message = _single_error(tmp_path, content)
    assert '%check (line' in message
    assert '"-Dman=enabled"' in message
    assert 'BuildOption(conf)' in message


def test_c2_and_c3_fire_on_the_same_build_section(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  -Dman=enabled\n',
        '',
    ) + """
%build
%meson -Dman=enabled
"""
    messages = _messages(tmp_path, content)
    assert len(messages) == 2
    assert any('carries the meson option' in msg for msg in messages)
    assert any('belong in %build -a' in msg for msg in messages)


def test_c2_option_in_conf_section_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  -Dman=enabled\n',
        '',
    ) + """
%conf
%meson -Dman=enabled
"""
    assert '%conf (line' in _single_error(tmp_path, content)


def test_c2_option_in_build_option_build_is_reported(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  -Dman=enabled',
        'BuildOption(build):  -Dman=enabled',
    )
    message = _single_error(tmp_path, content)
    assert 'BuildOption(build) (line 10)' in message


def test_c2_option_in_build_option_install_is_reported(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  -Dman=enabled',
        'BuildOption(install):  -Dwtmpdbd=enabled',
    )
    assert 'BuildOption(install) (line 10)' in _single_error(
        tmp_path, content,
    )


def test_c2_option_in_check_section_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  -Dman=enabled\n',
        '',
    ) + """
%check
%meson_test -Dman=enabled
"""
    assert '%check (line' in _single_error(tmp_path, content)


def test_c2_compiler_define_is_not_a_meson_option(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  -Dman=enabled\n',
        '',
    ) + """
%install -a
install -Dpm0644 %{SOURCE1} %{buildroot}%{_bindir}/demo
"""
    assert _check_spec_build_meson(_write(tmp_path, content)) == []


def test_c2_bare_define_without_value_is_not_a_meson_option(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  -Dman=enabled\n',
        '',
    ) + """
%check
gcc -DFOO -o demo demo.c
"""
    assert _check_spec_build_meson(_write(tmp_path, content)) == []


def test_c2_suffixed_section_is_not_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  -Dman=enabled\n',
        '',
    ) + """
%build -a
%meson_build -Dman=enabled
"""
    assert _check_spec_build_meson(_write(tmp_path, content)) == []


def test_c2_multiple_options_are_reported_on_their_own_lines(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  -Dman=enabled\n',
        '',
    ) + """
%check
%meson_test -Dman=enabled
%meson_test -Dcompat-symlink=true
"""
    messages = _messages(tmp_path, content)
    assert len(messages) == 2
    assert '\"-Dman=enabled\"' in messages[0]
    assert '\"-Dcompat-symlink=true\"' in messages[1]


# --------------------------------------------------------------------------
# C3 - a plain %build or %install must not carry a body.
# --------------------------------------------------------------------------


def test_c3_plain_build_with_a_body_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC + """
%build
%meson_build
"""
    message = _single_error(tmp_path, content)
    assert '%build (line' in message
    assert 'belong in %build -a' in message


def test_c3_plain_install_with_a_body_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC + """
%install
%meson_install
"""
    message = _single_error(tmp_path, content)
    assert '%install (line' in message
    assert 'belong in %install -a' in message


def test_c3_suffixed_section_passes(tmp_path: Path) -> None:
    content = CLEAN_SPEC + """
%build -a
%meson_build

%install -a
mkdir -p %{buildroot}%{_mandir}/man1
"""
    assert _check_spec_build_meson(_write(tmp_path, content)) == []


def test_c3_empty_section_passes(tmp_path: Path) -> None:
    content = CLEAN_SPEC + """
%build
"""
    assert _check_spec_build_meson(_write(tmp_path, content)) == []


def test_c3_comment_only_section_passes(tmp_path: Path) -> None:
    content = CLEAN_SPEC + """
%build
# nothing to do
"""
    assert _check_spec_build_meson(_write(tmp_path, content)) == []


def test_c3_install_a_only_passes(tmp_path: Path) -> None:
    content = CLEAN_SPEC + """
%install -a
mkdir -p %{buildroot}%{_mandir}/man1
"""
    assert _check_spec_build_meson(_write(tmp_path, content)) == []


def test_c3_prep_is_not_managed(tmp_path: Path) -> None:
    content = CLEAN_SPEC + """
%prep
%autosetup -p1
"""
    assert _check_spec_build_meson(_write(tmp_path, content)) == []


def test_c3_check_is_not_managed(tmp_path: Path) -> None:
    content = CLEAN_SPEC + """
%check
%meson_test
"""
    assert _check_spec_build_meson(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# Combined findings and de-duplication.
# --------------------------------------------------------------------------


def test_all_three_checkpoints_fire_together(tmp_path: Path) -> None:
    content = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildSystem:    meson

%build
%meson -Dman=enabled
"""
    messages = _messages(tmp_path, content)
    assert len(messages) == 3
    assert any('missing "meson"' in msg for msg in messages)
    assert any('carries the meson option' in msg for msg in messages)
    assert any('belong in %build -a' in msg for msg in messages)


# --------------------------------------------------------------------------
# Flags.
# --------------------------------------------------------------------------


def test_flag_disables_c1(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  meson\n', '')
    assert _check_spec_build_meson_ext(
        _write(tmp_path, content), check_buildrequires=False,
    ) == []


def test_flag_disables_c2(tmp_path: Path) -> None:
    content = CLEAN_SPEC + """
%check
%meson -Dman=enabled
"""
    assert _check_spec_build_meson_ext(
        _write(tmp_path, content), check_option_position=False,
    ) == []


def test_flag_disables_c3(tmp_path: Path) -> None:
    content = CLEAN_SPEC + """
%build
%meson_build
"""
    assert _check_spec_build_meson_ext(
        _write(tmp_path, content), check_plain_sections=False,
    ) == []


def test_all_flags_together_return_nothing(tmp_path: Path) -> None:
    content = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildSystem:    meson

%build
%meson -Dman=enabled
"""
    assert _check_spec_build_meson_ext(
        _write(tmp_path, content),
        check_buildrequires=False,
        check_option_position=False,
        check_plain_sections=False,
    ) == []


# --------------------------------------------------------------------------
# Command line entry point.
# --------------------------------------------------------------------------


def test_main_returns_zero_on_clean_spec(tmp_path: Path) -> None:
    assert main([_write(tmp_path, CLEAN_SPEC)]) == 0


def test_main_returns_one_on_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  meson\n', '')
    path = _write(tmp_path, content)
    assert main([path]) == 1
    out = capsys.readouterr().out
    assert f'{path}: ' in out
    assert 'missing "meson"' in out


def test_main_flag_disables_the_checkpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  meson\n', '')
    path = _write(tmp_path, content)
    assert main([path, '--no-check-buildrequires']) == 0
    assert capsys.readouterr().out == ''


def test_main_without_filenames_returns_zero() -> None:
    assert main([]) == 0
