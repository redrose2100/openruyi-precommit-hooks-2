# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check-spec-programming-golang."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks import check_spec_programming_golang as rule

CHECK = rule._check_spec_programming_golang
CHECK_EXT = rule._check_spec_programming_golang_ext


CLEAN_LIBRARY_SPEC = """\
%define go_import_path  github.com/jpillora/backoff

Name:           go-github-jpillora-backoff
Version:        1.0.0
Release:        %autorelease
Summary:        Backoff algorithm for Go
License:        MIT
URL:            https://github.com/jpillora/backoff
Source:         %{url}/archive/v%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    golangmodules

BuildRequires:  go
BuildRequires:  go-rpm-macros
BuildRequires:  go(github.com/stretchr/testify)

Provides:       go(%{go_import_path}) = %{version}

%description
Exponential backoff algorithm in Go.

%files
%{go_sys_gopath}/%{go_import_path}
"""

CLEAN_BINARY_SPEC = """\
%define _name kubectl

Name:           kubectl
Version:        1.31.0
Release:        %autorelease
Summary:        Command line tool for Kubernetes
License:        Apache-2.0
URL:            https://github.com/kubernetes/kubernetes
Source:         %{url}/archive/v%{version}.tar.gz
BuildSystem:    golang

BuildRequires:  go
BuildRequires:  go-rpm-macros

%description
The Kubernetes command line tool.

%install
install -Dpm0755 _output/bin/kubectl %{buildroot}%{_bindir}/%{_name}

%files
%{_bindir}/%{_name}
"""

LIBRARY_WITH_SUBPACKAGE_SPEC = """\
%define _name chroma
%define go_import_path github.com/alecthomas/chroma

Name:           chroma
Version:        2.12.0
Release:        %autorelease
Summary:        Syntax highlighter
License:        MIT
URL:            https://github.com/alecthomas/chroma
Source:         %{url}/archive/v%{version}.tar.gz
BuildSystem:    golang

BuildRequires:  go
BuildRequires:  go-rpm-macros

%description
A general purpose syntax highlighter in pure Go.

%package     -n go-github-alecthomas-chroma-v2
Summary:        Go library github.com/alecthomas/chroma/v2
License:        MIT
BuildArch:      noarch

Provides:       go(github.com/alecthomas/chroma/v2) = %{version}

%description -n go-github-alecthomas-chroma-v2
The Chroma Go library.

%install
install -Dpm0755 %{_name} %{buildroot}%{_bindir}/%{_name}

%files
%{_bindir}/%{_name}

%files -n go-github-alecthomas-chroma-v2
%{go_sys_gopath}/%{go_import_path}/v2
"""

OTHER_BUILD_SYSTEM_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildSystem:    cmake
BuildRequires:  cmake

%description
A demo package.

%files
%{_bindir}/demo
"""


def _write(tmp_path: Path, content: str, name: str = 'demo.spec') -> str:
    path = tmp_path / name
    path.write_text(content, encoding='utf-8')
    return str(path)


def _messages(tmp_path: Path, content: str) -> list[str]:
    return [
        err.split(': ', 1)[1]
        for err in CHECK(_write(tmp_path, content))
    ]


def _single_error(tmp_path: Path, content: str) -> str:
    messages = _messages(tmp_path, content)
    assert len(messages) == 1, messages
    return messages[0]


# --------------------------------------------------------------------------
# Scope - only a spec that declares a Go build system is judged.
# --------------------------------------------------------------------------


def test_clean_library_spec_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, CLEAN_LIBRARY_SPEC)) == []


def test_clean_binary_spec_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, CLEAN_BINARY_SPEC)) == []


def test_library_with_subpackage_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, LIBRARY_WITH_SUBPACKAGE_SPEC)) == []


def test_other_build_system_is_ignored(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, OTHER_BUILD_SYSTEM_SPEC)) == []


# --------------------------------------------------------------------------
# C1 - the go toolchain is declared.
# --------------------------------------------------------------------------


def test_missing_toolchain_is_reported(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go\n', '',
    )
    message = _single_error(tmp_path, content)
    assert 'missing "go"' in message


def test_versioned_toolchain_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go\n', 'BuildRequires:  go >= 1.20\n',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_toolchain_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go\n', '',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_toolchain=False,
    ) == []


# --------------------------------------------------------------------------
# C2 - the go-rpm-macros package is declared.
# --------------------------------------------------------------------------


def test_missing_macros_package_is_reported(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go-rpm-macros\n', '',
    )
    message = _single_error(tmp_path, content)
    assert 'missing "go-rpm-macros"' in message


def test_macros_package_extra_does_not_satisfy(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go-rpm-macros\n',
        'BuildRequires:  go-rpm-macros-extra\n',
    )
    message = _single_error(tmp_path, content)
    assert 'missing "go-rpm-macros"' in message


def test_macros_package_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go-rpm-macros\n', '',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_macros_package=False,
    ) == []


# --------------------------------------------------------------------------
# C3 - a Go library dependency uses the go(<import path>) form.
# --------------------------------------------------------------------------


def test_bare_import_path_is_reported(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go(github.com/stretchr/testify)',
        'BuildRequires:  github.com/stretchr/testify',
    )
    message = _single_error(tmp_path, content)
    assert 'github.com/stretchr/testify' in message


def test_virtual_dependency_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go(github.com/stretchr/testify)',
        'BuildRequires:  go(github.com/stretchr/testify) >= 1.9.0',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_virtual_dependency_checker_can_be_disabled(
    tmp_path: Path,
) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go(github.com/stretchr/testify)',
        'BuildRequires:  github.com/stretchr/testify',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_virtual_dependency=False,
    ) == []


# --------------------------------------------------------------------------
# C4 - a capability states the imported path and its version.
# --------------------------------------------------------------------------


def test_capability_without_version_is_reported(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'Provides:       go(%{go_import_path}) = %{version}',
        'Provides:       go(%{go_import_path})',
    )
    message = _single_error(tmp_path, content)
    assert 'does not state a version' in message


def test_capability_with_version_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'Provides:       go(%{go_import_path}) = %{version}',
        'Provides:       go(%{go_import_path}) = %{version}-%{release}',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_capability_version_checker_can_be_disabled(
    tmp_path: Path,
) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'Provides:       go(%{go_import_path}) = %{version}',
        'Provides:       go(%{go_import_path})',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_capability_version=False,
    ) == []


# --------------------------------------------------------------------------
# C5 - a library installs its files under the Go source tree.
# --------------------------------------------------------------------------


def test_library_file_outside_gopath_is_reported(tmp_path: Path) -> None:
    content = LIBRARY_WITH_SUBPACKAGE_SPEC.replace(
        '%files -n go-github-alecthomas-chroma-v2\n'
        '%{go_sys_gopath}/%{go_import_path}/v2\n',
        '%files -n go-github-alecthomas-chroma-v2\n'
        '%{_datadir}/%{_name}/v2\n',
    )
    message = _single_error(tmp_path, content)
    assert 'installs outside the Go source tree' in message


def test_datadir_gocode_root_is_accepted(tmp_path: Path) -> None:
    content = LIBRARY_WITH_SUBPACKAGE_SPEC.replace(
        '%files -n go-github-alecthomas-chroma-v2\n'
        '%{go_sys_gopath}/%{go_import_path}/v2\n',
        '%files -n go-github-alecthomas-chroma-v2\n'
        '%{_datadir}/gocode/src/%{go_import_path}/v2\n',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_binary_entry_of_the_main_package_is_not_reported(
    tmp_path: Path,
) -> None:
    assert CHECK(_write(tmp_path, LIBRARY_WITH_SUBPACKAGE_SPEC)) == []


def test_files_location_checker_can_be_disabled(tmp_path: Path) -> None:
    content = LIBRARY_WITH_SUBPACKAGE_SPEC.replace(
        '%files -n go-github-alecthomas-chroma-v2\n'
        '%{go_sys_gopath}/%{go_import_path}/v2\n',
        '%files -n go-github-alecthomas-chroma-v2\n'
        '%{_datadir}/%{_name}/v2\n',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_files_location=False,
    ) == []


# --------------------------------------------------------------------------
# C6 - the package name is derived from the import path.
# --------------------------------------------------------------------------


def test_misspelled_name_is_reported(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'Name:           go-github-jpillora-backoff',
        'Name:           go-github-jpillora-backhof',
    )
    message = _single_error(tmp_path, content)
    assert 'is not derived from the import path' in message


def test_host_identifier_is_part_of_the_name(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'Name:           go-github-jpillora-backoff',
        'Name:           go-jpillora-backoff',
    )
    message = _single_error(tmp_path, content)
    assert 'go-github-jpillora-backoff' in message


def test_major_version_suffix_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'Name:           go-github-jpillora-backoff',
        'Name:           go-github-jpillora-backoff-v2',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_go_library_path_is_named_by_its_vanity_host(
    tmp_path: Path,
) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        '%define go_import_path  github.com/jpillora/backoff',
        '%define go_import_path  golang.org/x/oauth2',
    ).replace(
        'Name:           go-github-jpillora-backoff',
        'Name:           go-golang-x-oauth2',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_unlisted_host_is_skipped(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        '%define go_import_path  github.com/jpillora/backoff',
        '%define go_import_path  gopkg.in/yaml.v3',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_package_name_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'Name:           go-github-jpillora-backoff',
        'Name:           go-github-jpillora-backhof',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_package_name=False,
    ) == []


# --------------------------------------------------------------------------
# C7 - a binary package name does not carry the go- prefix.
# --------------------------------------------------------------------------


def test_binary_name_with_go_prefix_is_reported(tmp_path: Path) -> None:
    content = CLEAN_BINARY_SPEC.replace(
        'Name:           kubectl', 'Name:           go-kubectl',
    )
    message = _single_error(tmp_path, content)
    assert 'drop the "go-" prefix' in message


def test_binary_named_after_the_project_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, CLEAN_BINARY_SPEC)) == []


def test_library_subpackage_with_go_prefix_is_not_reported(
    tmp_path: Path,
) -> None:
    assert CHECK(_write(tmp_path, LIBRARY_WITH_SUBPACKAGE_SPEC)) == []


def test_binary_name_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_BINARY_SPEC.replace(
        'Name:           kubectl', 'Name:           go-kubectl',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_binary_name=False,
    ) == []


# --------------------------------------------------------------------------
# C9 - a test include macro names a single library.
# --------------------------------------------------------------------------


def test_test_include_with_several_libraries_is_reported(
    tmp_path: Path,
) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go(github.com/stretchr/testify)\n',
        'BuildRequires:  go(github.com/stretchr/testify)\n\n'
        '%define go_test_include %{shrink:\n'
        '    %{go_import_path}\n'
        '    github.com/spf13/afero\n'
        '}\n',
    )
    message = _single_error(tmp_path, content)
    assert 'names 2 libraries' in message


def test_test_include_of_one_library_passes(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go(github.com/stretchr/testify)\n',
        'BuildRequires:  go(github.com/stretchr/testify)\n\n'
        '%define go_test_include %{shrink:\n'
        '    %{go_import_path}\n'
        '    %{go_import_path}/internal\n'
        '}\n',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_test_include_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'BuildRequires:  go(github.com/stretchr/testify)\n',
        'BuildRequires:  go(github.com/stretchr/testify)\n\n'
        '%define go_test_include %{shrink:\n'
        '    %{go_import_path}\n'
        '    github.com/spf13/afero\n'
        '}\n',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_test_include=False,
    ) == []


# --------------------------------------------------------------------------
# C10 - a spec that shares an import path with another declares it.
# --------------------------------------------------------------------------


def test_shared_import_path_without_conflicts_is_reported(
    tmp_path: Path,
) -> None:
    first = _write(tmp_path, LIBRARY_WITH_SUBPACKAGE_SPEC, 'first.spec')
    second = _write(tmp_path, LIBRARY_WITH_SUBPACKAGE_SPEC, 'second.spec')
    capabilities = rule._capability_index([first, second])
    errors = CHECK_EXT(
        first, check_toolchain=False, check_macros_package=False,
        check_virtual_dependency=False, check_capability_version=False,
        check_files_location=False, check_package_name=False,
        check_binary_name=False, check_test_include=False,
        check_shared_import_path=False, capabilities=capabilities,
    )
    assert errors == []
    errors = CHECK_EXT(
        first, check_toolchain=False, check_macros_package=False,
        check_virtual_dependency=False, check_capability_version=False,
        check_files_location=False, check_package_name=False,
        check_binary_name=False, check_test_include=False,
        capabilities=capabilities,
    )
    assert len(errors) == 1, errors
    assert 'declare "Conflicts: go(github.com/alecthomas/chroma/v2)"' in \
        errors[0]


def test_shared_import_path_with_conflicts_passes(tmp_path: Path) -> None:
    content = LIBRARY_WITH_SUBPACKAGE_SPEC.replace(
        'Provides:       go(github.com/alecthomas/chroma/v2) = %{version}',
        'Provides:       go(github.com/alecthomas/chroma/v2) = %{version}\n'
        'Conflicts:      go(github.com/alecthomas/chroma/v2)',
    )
    first = _write(tmp_path, content, 'first.spec')
    second = _write(tmp_path, content, 'second.spec')
    capabilities = rule._capability_index([first, second])
    errors = CHECK_EXT(
        first,
        check_toolchain=False,
        check_macros_package=False,
        check_virtual_dependency=False,
        check_capability_version=False,
        check_files_location=False,
        check_package_name=False,
        check_binary_name=False,
        check_test_include=False,
        capabilities=capabilities,
    )
    assert errors == []


def test_shared_import_path_is_not_reported_without_an_index(
    tmp_path: Path,
) -> None:
    assert CHECK(_write(tmp_path, LIBRARY_WITH_SUBPACKAGE_SPEC)) == []


# --------------------------------------------------------------------------
# Command line entry point.
# --------------------------------------------------------------------------


def test_main_returns_zero_for_a_clean_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, CLEAN_LIBRARY_SPEC)
    assert rule.main([path]) == 0
    assert capsys.readouterr().out == ''


def test_main_reports_a_violation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    content = CLEAN_LIBRARY_SPEC.replace(
        'Name:           go-github-jpillora-backoff',
        'Name:           go-github-jpillora-backhof',
    )
    path = _write(tmp_path, content)
    assert rule.main([path]) == 1
    assert 'is not derived from the import path' in \
        capsys.readouterr().out


def test_main_reports_nothing_for_an_ignored_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, OTHER_BUILD_SYSTEM_SPEC)
    assert rule.main([path]) == 0
    assert capsys.readouterr().out == ''
