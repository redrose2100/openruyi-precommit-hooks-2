# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check-spec-build-rust."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_build_rust import (
    _check_spec_build_rust,
)
from openruyi_precommit_hooks.check_spec_build_rust import (
    _check_spec_build_rust_ext,
)
from openruyi_precommit_hooks.check_spec_build_rust import main


CLEAN_RUST_SPEC = """\
Name:           ripgrep
Version:        15.2.0
Release:        %autorelease
Summary:        Fast recursive text search tool
License:        Unlicense OR MIT
URL:            https://github.com/BurntSushi/ripgrep
Source:         https://static.crates.io/crates/ripgrep/15.2.0/download#/ripgrep-15.2.0.tar.gz
BuildSystem:    rust

BuildRequires:  rust
BuildRequires:  rust-rpm-macros
BuildRequires:  crate(regex-1/default) >= 1.9.5

%description
ripgrep recursively searches directories for regular expressions.

%install
install -Dpm0755 target/release/rg %{buildroot}%{_bindir}/rg

%files
%{_bindir}/rg
"""

CLEAN_CRATES_SPEC = """\
%global crate_name anes
%global full_version 0.1.6
%global pkgname anes-0.1

Name:           rust-%{pkgname}
Version:        0.1.6
Release:        %autorelease
Summary:        Rust crate "anes"
License:        MIT OR Apache-2.0
URL:            https://github.com/zrzka/anes-rs
Source:         https://static.crates.io/crates/%{crate_name}/%{full_version}/download#/%{name}-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    rustcrates

BuildRequires:  rust-rpm-macros

Provides:       crate(%{pkgname}) = %{version}

%description
Source code for the Anes Rust crate.

%files
%{_datadir}/cargo/registry/%{crate_name}-%{full_version}/
"""

CRATES_EXTENDED_INSTALL_SPEC = """\
%global crate_name anes
%global full_version 0.1.6
%global pkgname anes-0.1

Name:           rust-%{pkgname}
Version:        0.1.6
Release:        %autorelease
Summary:        Rust crate "anes"
License:        MIT OR Apache-2.0
URL:            https://github.com/zrzka/anes-rs
Source:         https://static.crates.io/crates/%{crate_name}/%{full_version}/download#/%{name}-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    rustcrates

BuildRequires:  rust-rpm-macros

%description
Source code for the Anes Rust crate.

%install -a
%__rm -f %{buildroot}%{_datadir}/cargo/registry/%{crate_name}-%{full_version}/*checksum.json

%files
%{_datadir}/cargo/registry/%{crate_name}-%{full_version}/
"""

RUST_EXTENDED_PREP_SPEC = """\
Name:           ripgrep
Version:        15.2.0
Release:        %autorelease
Summary:        Fast recursive text search tool
License:        Unlicense OR MIT
URL:            https://github.com/BurntSushi/ripgrep
Source:         https://static.crates.io/crates/ripgrep/15.2.0/download#/ripgrep-15.2.0.tar.gz
BuildSystem:    rust

BuildRequires:  rust
BuildRequires:  rust-rpm-macros

%description
ripgrep recursively searches directories for regular expressions.

%prep -a
rm -rf vendor

%install
install -Dpm0755 target/release/rg %{buildroot}%{_bindir}/rg

%files
%{_bindir}/rg
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

NO_BUILD_SYSTEM_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildRequires:  rust

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
        for err in _check_spec_build_rust(_write(tmp_path, content))
    ]


def _single_error(tmp_path: Path, content: str) -> str:
    messages = _messages(tmp_path, content)
    assert len(messages) == 1, messages
    return messages[0]


# --------------------------------------------------------------------------
# Scope - only a spec that declares one of the rust build systems is judged.
# --------------------------------------------------------------------------


def test_clean_rust_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_build_rust(_write(tmp_path, CLEAN_RUST_SPEC)) == []


def test_clean_crates_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_build_rust(_write(tmp_path, CLEAN_CRATES_SPEC)) == []


def test_other_build_system_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_rust(
        _write(tmp_path, OTHER_BUILD_SYSTEM_SPEC),
    ) == []


def test_spec_without_build_system_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_rust(
        _write(tmp_path, NO_BUILD_SYSTEM_SPEC),
    ) == []


# --------------------------------------------------------------------------
# C1 - a rustcrates spec does not write %install by hand.
# --------------------------------------------------------------------------


def test_plain_install_in_crates_spec_is_reported(tmp_path: Path) -> None:
    content = CLEAN_CRATES_SPEC.replace(
        '%files\n',
        '%install\n'
        '%__install -d %{buildroot}%{_datadir}/cargo/registry/%{crate_name}-%{full_version}\n'
        '%__cp -a . %{buildroot}%{_datadir}/cargo/registry/%{crate_name}-%{full_version}/\n'
        '\n%files\n',
    )
    message = _single_error(tmp_path, content)
    assert 'is written by hand in a BuildSystem: rustcrates spec' in message
    assert 'line 22' in message
    assert '%install -p or %install -a' in message


def test_extended_install_in_crates_spec_is_accepted(tmp_path: Path) -> None:
    assert _check_spec_build_rust(
        _write(tmp_path, CRATES_EXTENDED_INSTALL_SPEC),
    ) == []


def test_empty_install_in_crates_spec_is_not_reported(tmp_path: Path) -> None:
    content = CLEAN_CRATES_SPEC.replace('%files\n', '%install\n\n%files\n')
    assert _check_spec_build_rust(_write(tmp_path, content)) == []


def test_comment_only_install_in_crates_spec_is_not_reported(
    tmp_path: Path,
) -> None:
    content = CLEAN_CRATES_SPEC.replace(
        '%files\n',
        '%install\n# the default stage already installs the crate\n\n%files\n',
    )
    assert _check_spec_build_rust(_write(tmp_path, content)) == []


def test_plain_install_in_rust_spec_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_RUST_SPEC.replace(
        '%install\ninstall -Dpm0755 target/release/rg %{buildroot}%{_bindir}/rg\n',
        '%install -a\ninstall -Dpm0755 target/release/rg %{buildroot}%{_bindir}/rg\n',
    )
    assert _check_spec_build_rust(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# C2 - a rust %prep override keeps the system registry setup.
# --------------------------------------------------------------------------


def test_prep_override_without_registry_is_reported(tmp_path: Path) -> None:
    content = CLEAN_RUST_SPEC.replace(
        '%install\n',
        '%prep\n%autosetup -C -p1\n\n%install\n',
    )
    message = _single_error(tmp_path, content)
    assert 'overrides the default prep of BuildSystem: rust' in message
    assert '%rust_setup_registry' in message
    assert 'line 17' in message


def test_prep_override_with_registry_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_RUST_SPEC.replace(
        '%install\n',
        '%prep\n%autosetup -C -p1\n%rust_setup_registry\n\n%install\n',
    )
    assert _check_spec_build_rust(_write(tmp_path, content)) == []


def test_extended_prep_in_rust_spec_is_accepted(tmp_path: Path) -> None:
    assert _check_spec_build_rust(
        _write(tmp_path, RUST_EXTENDED_PREP_SPEC),
    ) == []


def test_prep_override_in_crates_spec_is_not_reported(tmp_path: Path) -> None:
    content = CLEAN_CRATES_SPEC.replace(
        '%description\n',
        '%prep\n%autosetup -C -p1\n\n%description\n',
    )
    assert _check_spec_build_rust(_write(tmp_path, content)) == []


def test_empty_prep_in_rust_spec_is_not_reported(tmp_path: Path) -> None:
    content = CLEAN_RUST_SPEC.replace('%install\n', '%prep\n\n%install\n')
    assert _check_spec_build_rust(_write(tmp_path, content)) == []


def test_comment_only_prep_in_rust_spec_is_not_reported(
    tmp_path: Path,
) -> None:
    content = CLEAN_RUST_SPEC.replace(
        '%install\n',
        '%prep\n# the default prep is enough here\n\n%install\n',
    )
    assert _check_spec_build_rust(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# C3 - the rust macro package.
# --------------------------------------------------------------------------


def test_missing_macros_package_in_rust_spec_is_reported(
    tmp_path: Path,
) -> None:
    content = CLEAN_RUST_SPEC.replace('BuildRequires:  rust-rpm-macros\n', '')
    message = _single_error(tmp_path, content)
    assert 'requires "rust-rpm-macros" in BuildRequires' in message
    assert 'line 8' in message


def test_missing_macros_package_in_crates_spec_is_reported(
    tmp_path: Path,
) -> None:
    content = CLEAN_CRATES_SPEC.replace(
        'BuildRequires:  rust-rpm-macros\n',
        '',
    )
    message = _single_error(tmp_path, content)
    assert 'requires "rust-rpm-macros" in BuildRequires' in message


def test_macros_package_with_version_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_RUST_SPEC.replace(
        'BuildRequires:  rust-rpm-macros',
        'BuildRequires:  rust-rpm-macros >= 0.5',
    )
    assert _check_spec_build_rust(_write(tmp_path, content)) == []


def test_macros_package_with_similar_name_does_not_count(
    tmp_path: Path,
) -> None:
    content = CLEAN_RUST_SPEC.replace(
        'BuildRequires:  rust-rpm-macros',
        'BuildRequires:  rust-rpm-macros-extra',
    )
    message = _single_error(tmp_path, content)
    assert 'rust-rpm-macros' in message


def test_commented_out_macros_package_does_not_count(
    tmp_path: Path,
) -> None:
    content = CLEAN_RUST_SPEC.replace(
        'BuildRequires:  rust-rpm-macros',
        '# BuildRequires:  rust-rpm-macros',
    )
    message = _single_error(tmp_path, content)
    assert 'rust-rpm-macros' in message


def test_macros_package_in_subpackage_counts(tmp_path: Path) -> None:
    content = CLEAN_RUST_SPEC.replace(
        'BuildRequires:  rust-rpm-macros\n',
        '',
    ).replace(
        '%description\n',
        '%package cli\nSummary: A cli\n'
        'BuildRequires:  rust-rpm-macros\n\n%description\n',
    )
    assert _check_spec_build_rust(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# C4 - the rust toolchain dependency.
# --------------------------------------------------------------------------


def test_missing_toolchain_is_reported(tmp_path: Path) -> None:
    content = CLEAN_RUST_SPEC.replace('BuildRequires:  rust\n', '')
    message = _single_error(tmp_path, content)
    assert 'requires "rust" in BuildRequires' in message
    assert 'missing "rust"' in message


def test_toolchain_with_version_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_RUST_SPEC.replace(
        'BuildRequires:  rust\n',
        'BuildRequires:  rust >= 1.85\n',
    )
    assert _check_spec_build_rust(_write(tmp_path, content)) == []


def test_toolchain_with_similar_name_does_not_count(
    tmp_path: Path,
) -> None:
    content = CLEAN_RUST_SPEC.replace(
        'BuildRequires:  rust\n',
        'BuildRequires:  rust-toolset\n',
    )
    message = _single_error(tmp_path, content)
    assert 'missing "rust"' in message


def test_toolchain_is_not_required_for_crates_spec(tmp_path: Path) -> None:
    assert _check_spec_build_rust(_write(tmp_path, CLEAN_CRATES_SPEC)) == []


# --------------------------------------------------------------------------
# Several findings on one spec, and flag handling.
# --------------------------------------------------------------------------


BROKEN_SPEC = """\
Name:           demo
Version:        1.0
Release:        %autorelease
Summary:        A demo package
License:        MIT
URL:            https://example.org/demo
BuildSystem:    rust

%description
A demo package.

%prep
%autosetup -C -p1

%install
install -Dpm0755 target/release/demo %{buildroot}%{_bindir}/demo

%files
%{_bindir}/demo
"""


def test_every_checkpoint_reports_on_one_broken_spec(
    tmp_path: Path,
) -> None:
    messages = _messages(tmp_path, BROKEN_SPEC)
    assert len(messages) == 3, messages
    assert any('rust-rpm-macros' in m for m in messages)
    assert any('missing "rust"' in m for m in messages)
    assert any('%rust_setup_registry' in m for m in messages)


def test_ext_flags_disable_each_checkpoint(tmp_path: Path) -> None:
    path = _write(tmp_path, BROKEN_SPEC)
    assert _check_spec_build_rust_ext(
        path,
        check_crates_install=False,
        check_rust_prep=False,
        check_macros_package=False,
        check_toolchain=False,
    ) == []


def test_ext_flag_keeps_the_others(tmp_path: Path) -> None:
    path = _write(tmp_path, BROKEN_SPEC)
    errors = _check_spec_build_rust_ext(path, check_toolchain=False)
    assert len(errors) == 2
    assert all(
        'rust-rpm-macros' in err or '%rust_setup_registry' in err
        for err in errors
    )


def test_main_reports_and_sets_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, NO_BUILD_SYSTEM_SPEC)
    assert main([path]) == 0
    assert main(['--no-check-toolchain', path]) == 0
    assert main([]) == 0


def test_main_prints_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, BROKEN_SPEC)
    assert main([path]) == 1
    out = capsys.readouterr().out
    assert 'rust-rpm-macros' in out


def test_main_flag_disables_a_checkpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, BROKEN_SPEC)
    assert main(['--no-check-macros-package', path]) == 1
    out = capsys.readouterr().out
    assert 'rust-rpm-macros' not in out
    assert '%rust_setup_registry' in out


def test_utf8_error_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'bad.spec'
    path.write_bytes(b'\xff\xfe\x00BuildSystem: rust\n')
    errors = _check_spec_build_rust(str(path))
    assert len(errors) == 1
    assert 'file is not valid UTF-8' in errors[0]


def test_dedup_keeps_one_finding_per_message(tmp_path: Path) -> None:
    content = CLEAN_RUST_SPEC.replace(
        'BuildSystem:    rust\n',
        'BuildSystem:    rust\nBuildSystem:    rust\n',
    )
    messages = _messages(tmp_path, content)
    assert len(messages) == len(set(messages))
