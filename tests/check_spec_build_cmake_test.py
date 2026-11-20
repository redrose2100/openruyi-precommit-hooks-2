# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check-spec-build-cmake."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_build_cmake import _check_spec_build_cmake
from openruyi_precommit_hooks.check_spec_build_cmake import _check_spec_build_cmake_ext
from openruyi_precommit_hooks.check_spec_build_cmake import main


CLEAN_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
URL:            https://example.org/demo
Source0:        https://example.org/demo-1.0.tar.gz
BuildSystem:    cmake
BuildRequires:  cmake

%description
A demo package.
"""

NOT_CMAKE_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildSystem:    autotools
BuildRequires:  autoconf

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
        for err in _check_spec_build_cmake(_write(tmp_path, content))
    ]


def _single_error(tmp_path: Path, content: str) -> str:
    messages = _messages(tmp_path, content)
    assert len(messages) == 1, messages
    return messages[0]


# --------------------------------------------------------------------------
# Scope - only a cmake spec is judged.
# --------------------------------------------------------------------------


def test_clean_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_build_cmake(_write(tmp_path, CLEAN_SPEC)) == []


def test_not_a_cmake_spec_is_ignored(tmp_path: Path) -> None:
    spec = NOT_CMAKE_SPEC + '\n%check\nctest\n'
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_spec_without_build_system_is_ignored(tmp_path: Path) -> None:
    spec = NO_BUILD_SYSTEM_SPEC + '\n%check\nctest\n'
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_missing_file_reports_an_error(tmp_path: Path) -> None:
    errors = _check_spec_build_cmake(str(tmp_path / 'absent.spec'))
    assert len(errors) == 1
    assert 'absent.spec' in errors[0]


# --------------------------------------------------------------------------
# C1 - cmake is declared as a BuildRequires.
# --------------------------------------------------------------------------


def test_missing_cmake_dependency_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  cmake\n', '')
    message = _single_error(tmp_path, spec)
    assert 'requires "cmake" in BuildRequires' in message
    assert 'missing "cmake"' in message


def test_extra_cmake_modules_do_not_satisfy_the_requirement(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  extra-cmake-modules\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'missing "cmake"' in message


def test_kf6_extra_cmake_modules_do_not_satisfy_the_requirement(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  kf6-extra-cmake-modules\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'missing "cmake"' in message


def test_versioned_cmake_dependency_is_accepted(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  cmake >= 3.20\n',
    )
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_uppercase_cmake_dependency_is_accepted(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  cmake\n', 'BuildRequires:  Cmake\n')
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_rich_dependency_does_not_satisfy_the_requirement(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  (cmake if gcc)\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'missing "cmake"' in message


def test_commented_dependency_does_not_satisfy_the_requirement(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        '# BuildRequires:  cmake\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'missing "cmake"' in message


def test_dependency_in_a_subpackage_block_counts(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        '\n%package devel\nSummary:        Development files\n'
        'BuildRequires:  cmake\n',
    )
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_build_system_inside_a_subpackage_is_judged(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildSystem:    cmake\n', '')
    spec = spec.replace(
        '\n%description\n',
        '\n%package devel\nSummary:        Development files\n'
        'BuildSystem:    cmake\n\n%description\n',
    )
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_build_system_in_a_subpackage_still_needs_the_dependency(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  cmake\n', '')
    spec = spec.replace(
        '\n%description\n',
        '\n%package devel\nSummary:        Development files\n'
        'BuildSystem:    cmake\n\n%description\n',
    )
    messages = _messages(tmp_path, spec)
    assert len(messages) == 1, messages
    assert all('missing "cmake"' in message for message in messages)


def test_case_of_the_build_system_value_is_ignored(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildSystem:    cmake', 'BuildSystem:    CMake')
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_misspelt_build_system_field_still_matches(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildSystem:    cmake', 'Buildsystem:    cmake')
    spec = spec.replace('BuildRequires:  cmake\n', '')
    message = _single_error(tmp_path, spec)
    assert 'missing "cmake"' in message


# --------------------------------------------------------------------------
# C2 - an explicit %check that only re-runs ctest.
# --------------------------------------------------------------------------


def test_bare_check_section_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC + '\n%check\nctest\n'
    message = _single_error(tmp_path, spec)
    assert '%check' in message
    assert 'without arguments' in message


def test_bare_pct_ctest_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC + '\n%check\n%ctest\n'
    message = _single_error(tmp_path, spec)
    assert 'without arguments' in message


def test_check_section_with_arguments_is_not_reported(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC + '\n%check\n%ctest --parallel 1\n'
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_check_section_with_output_on_failure_is_not_reported(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC + '\n%check\nctest --output-on-failure\n'
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_check_section_with_several_statements_is_not_reported(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC + '\n%check\ncd tests\nctest\n'
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_empty_check_section_is_not_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC + '\n%check\n'
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_commented_ctest_does_not_make_the_body_bare(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC + '\n%check\n# upstream run\nctest\n'
    message = _single_error(tmp_path, spec)
    assert 'without arguments' in message


def test_ctest_outside_a_check_section_is_not_reported(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC + '\n%install\nctest\n'
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_guarded_ctest_is_not_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC + '\n%check\n%if %{with test}\n%ctest\n%endif\n'
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_check_section_reports_its_own_line(tmp_path: Path) -> None:
    spec = CLEAN_SPEC + '\n%check\nctest\n'
    message = _single_error(tmp_path, spec)
    assert '%check (line 14)' in message


# --------------------------------------------------------------------------
# C3 - BuildOption(conf) repeating a value the macros define.
# --------------------------------------------------------------------------


def test_redundant_build_type_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  cmake\n'
        'BuildOption(conf):  -DCMAKE_BUILD_TYPE:STRING=RelWithDebInfo\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'CMAKE_BUILD_TYPE' in message
    assert 'already define' in message


def test_redundant_prefix_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  cmake\n'
        'BuildOption(conf):  -DCMAKE_INSTALL_PREFIX=%{_prefix}\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'CMAKE_INSTALL_PREFIX' in message


def test_redundant_lib_suffix_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  cmake\nBuildOption(conf):  -DLIB_SUFFIX=64\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'LIB_SUFFIX' in message


def test_overriding_a_default_is_not_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  cmake\n'
        'BuildOption(conf):  -DBUILD_SHARED_LIBS:BOOL=OFF\n',
    )
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_unknown_flag_is_not_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  cmake\n'
        'BuildOption(conf):  -DENABLE_CCACHE=1\n',
    )
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_flag_of_another_stage_is_not_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  cmake\n'
        'BuildOption(build):  -DCMAKE_BUILD_TYPE:STRING=RelWithDebInfo\n',
    )
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_flag_without_a_stage_is_not_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  cmake\n'
        'BuildOption:  -DCMAKE_BUILD_TYPE=RelWithDebInfo\n',
    )
    assert _check_spec_build_cmake(_write(tmp_path, spec)) == []


def test_shared_libs_on_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  cmake\nBuildOption(conf):  -DBUILD_SHARED_LIBS=ON\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'BUILD_SHARED_LIBS' in message


def test_only_the_matching_value_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  cmake\n'
        'BuildOption(conf):  -DCMAKE_BUILD_TYPE=Debug '
        '-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'CMAKE_VERBOSE_MAKEFILE' in message
    assert 'CMAKE_BUILD_TYPE' not in message


# --------------------------------------------------------------------------
# Flags.
# --------------------------------------------------------------------------


def test_all_checks_are_reported_together(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  cmake\n', '')
    spec = spec.replace(
        'BuildSystem:    cmake\n',
        'BuildSystem:    cmake\n'
        'BuildOption(conf):  -DLIB_SUFFIX=64\n',
    )
    spec += '\n%check\nctest\n'
    messages = _messages(tmp_path, spec)
    assert len(messages) == 3


def test_no_check_buildrequires_switches_c1_off(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  cmake\n', '')
    assert _check_spec_build_cmake_ext(
        _write(tmp_path, spec), check_buildrequires=False,
    ) == []


def test_no_check_check_section_switches_c2_off(tmp_path: Path) -> None:
    spec = CLEAN_SPEC + '\n%check\nctest\n'
    assert _check_spec_build_cmake_ext(
        _write(tmp_path, spec), check_check_section=False,
    ) == []


def test_no_check_build_option_switches_c3_off(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  cmake\n',
        'BuildRequires:  cmake\nBuildOption(conf):  -DLIB_SUFFIX=64\n',
    )
    assert _check_spec_build_cmake_ext(
        _write(tmp_path, spec), check_build_option=False,
    ) == []


def test_switching_every_check_off_reports_nothing(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('BuildRequires:  cmake\n', '')
    spec += '\n%check\nctest\n'
    assert _check_spec_build_cmake_ext(
        _write(tmp_path, spec),
        check_buildrequires=False,
        check_check_section=False,
        check_build_option=False,
    ) == []


# --------------------------------------------------------------------------
# Command line.
# --------------------------------------------------------------------------


def test_main_reports_a_finding_on_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, CLEAN_SPEC + '\n%check\nctest\n')
    assert main([path]) == 1
    out = capsys.readouterr().out
    assert 'without arguments' in out


def test_main_returns_zero_for_a_clean_spec(tmp_path: Path) -> None:
    assert main([_write(tmp_path, CLEAN_SPEC)]) == 0


def test_main_accepts_the_switches(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, CLEAN_SPEC + '\n%check\nctest\n')
    code = main([
        '--no-check-check-section',
        '--no-check-build-option',
        '--no-check-buildrequires',
        path,
    ])
    assert code == 0
    assert capsys.readouterr().out == ''
