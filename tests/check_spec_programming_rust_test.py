"""Tests for check-spec-programming-rust."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks import check_spec_programming_rust as rule

CHECK = rule._check_spec_programming_rust
CHECK_EXT = rule._check_spec_programming_rust_ext


CLEAN_PROVIDER = """\
%global crate_name serde
%global full_version 1.0.228
%global pkgname serde-1

Name:           rust-serde-1
Version:        1.0.228
Release:        %autorelease
Summary:        Serialization framework for Rust
License:        MIT OR Apache-2.0
URL:            https://crates.io/crates/%{crate_name}
Source:         https://static.crates.io/crates/%{crate_name}/%{full_version}/
BuildArch:      noarch
BuildSystem:    rustcrates
BuildRequires:  rust-rpm-macros

Provides:       crate(%{pkgname}) = %{full_version}

%description
Serialization framework for Rust.

%files
%license LICENSE-MIT
%doc README.md
%{_datadir}/cargo/registry/%{crate_name}-%{full_version}/

%changelog
%autochangelog
"""

CLEAN_APP = """\
Name:           ripgrep
Version:        14.1.0
Release:        %autorelease
Summary:        Line-oriented search tool
License:        MIT
URL:            https://github.com/BurntSushi/ripgrep
Source:         https://github.com/BurntSushi/ripgrep/archive/%{version}.tar.gz
BuildSystem:    rust
BuildRequires:  rust
BuildRequires:  rust-rpm-macros
BuildRequires:  crate(grep-0.3/default) >= 0.3.0
BuildRequires:  crate(clap-4/derive) >= 4.5.0

%description
Line-oriented search tool.

%install
install -Dm0755 target/release/rg %{buildroot}%{_bindir}/rg

%files
%{_bindir}/rg

%changelog
%autochangelog
"""

CLEAN_PYPROJECT = """\
Name:           python-pydantic-core
Version:        2.27.1
Release:        %autorelease
Summary:        Core validation logic for pydantic
License:        MIT
URL:            https://github.com/pydantic/pydantic-core
Source:         https://example.org/pydantic-core-%{version}.tar.gz
BuildSystem:    pyproject
BuildRequires:  rust
BuildRequires:  rust-rpm-macros
BuildRequires:  python3dist(maturin)
BuildRequires:  crate(pyo3-0.22/default) >= 0.22.0

%description
Core validation logic for pydantic.

%files
%{python3_sitearch}/pydantic_core

%changelog
%autochangelog
"""

CMAKE_SPEC = """\
Name:           ceph
Version:        19.2.0
Release:        %autorelease
Summary:        Distributed object store
License:        LGPL-2.1-only
URL:            https://ceph.io/
Source0:        https://download.ceph.com/tarballs/ceph-%{version}.tar.gz
BuildSystem:    cmake
BuildRequires:  cmake
Requires:       python3

%description
Distributed object store.

%files
%{_bindir}/ceph
"""


def _write(
    tmp_path: Path, content: str, name: str = 'demo.spec',
    directory: str | None = None,
    cargo_toml: str | None = None,
) -> str:
    folder = tmp_path / (directory or 'demo')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(content, encoding='utf-8')
    if cargo_toml is not None:
        (folder / 'Cargo.toml').write_text(cargo_toml, encoding='utf-8')
    return str(path)


def _messages(
    tmp_path: Path, content: str, *,
    name: str = 'demo.spec',
    directory: str | None = None,
    cargo_toml: str | None = None,
) -> list[str]:
    path = _write(
        tmp_path, content, name=name, directory=directory,
        cargo_toml=cargo_toml,
    )
    return [err.split(': ', 1)[1] for err in CHECK(path)]


FLAGS = (
    'check_provider_prefix',
    'check_provider_consistency',
    'check_pkgname',
    'check_compat_group',
    'check_compat_granularity',
    'check_crate_capability',
    'check_crate_version',
    'check_pyproject_toolchain',
    'check_provider_capability',
    'check_provider_cargo_toml',
)


def _isolated(
    tmp_path: Path, content: str, flag: str, *,
    name: str = 'demo.spec',
    directory: str | None = None,
    cargo_toml: str | None = None,
) -> list[str]:
    """Run one checkpoint alone and return its messages."""
    options: dict[str, bool] = {option: False for option in FLAGS}
    options[flag] = True
    path = _write(
        tmp_path, content, name=name, directory=directory,
        cargo_toml=cargo_toml,
    )
    return [err.split(': ', 1)[1] for err in CHECK_EXT(path, **options)]


# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------


def test_clean_provider_passes(tmp_path: Path) -> None:
    assert CHECK(
        _write(
            tmp_path, CLEAN_PROVIDER, name='rust-serde-1.spec',
            directory='rust-serde-1', cargo_toml='[package]\nname = "serde"\n',
        ),
    ) == []


def test_clean_application_passes(tmp_path: Path) -> None:
    assert CHECK(
        _write(
            tmp_path, CLEAN_APP, name='ripgrep.spec',
            directory='ripgrep',
        ),
    ) == []


def test_clean_pyproject_extension_passes(tmp_path: Path) -> None:
    assert CHECK(
        _write(tmp_path, CLEAN_PYPROJECT, name='python-pydantic-core.spec'),
    ) == []


def test_other_build_system_is_ignored(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, CMAKE_SPEC)) == []


def test_non_rust_spec_is_ignored(tmp_path: Path) -> None:
    spec = """\
Name:           curl
Version:        8.9.0
Release:        %autorelease
BuildSystem:    autotools
BuildRequires:  gcc
Requires:       openssl-libs
"""
    assert CHECK(_write(tmp_path, spec)) == []


def test_unreadable_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'demo' / 'broken.spec'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'\xff\xfe\x00b\x00a\x00d')
    assert CHECK(str(path)) == [f'{path}: file is not valid UTF-8']


# --------------------------------------------------------------------------
# C1 - a crate provider package carries the rust- prefix.
# --------------------------------------------------------------------------


def test_provider_without_prefix_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_PROVIDER.replace(
        'Name:           rust-serde-1',
        'Name:           serde-1',
    )
    message = _isolated(
        tmp_path, spec, 'check_provider_prefix',
        name='serde-1.spec', directory='serde-1', cargo_toml='',
    )[0]
    assert 'does not carry the "rust-" prefix' in message


def test_provider_with_prefix_is_accepted(tmp_path: Path) -> None:
    assert _isolated(
        tmp_path, CLEAN_PROVIDER, 'check_provider_prefix',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    ) == []


def test_provider_name_built_from_macro_is_skipped(tmp_path: Path) -> None:
    spec = CLEAN_PROVIDER.replace(
        'Name:           rust-serde-1',
        'Name:           %{provider_name}',
    )
    assert _isolated(
        tmp_path, spec, 'check_provider_prefix',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    ) == []


# --------------------------------------------------------------------------
# C2 - the directory name, the spec file name and Name agree.
# --------------------------------------------------------------------------


def test_provider_directory_mismatch_is_reported(tmp_path: Path) -> None:
    message = _isolated(
        tmp_path, CLEAN_PROVIDER, 'check_provider_consistency',
        name='rust-serde-1.spec', directory='rust-serde', cargo_toml='',
    )[0]
    assert 'does not match the provider directory name "rust-serde"' in message


def test_provider_spec_file_mismatch_is_reported(tmp_path: Path) -> None:
    message = _isolated(
        tmp_path, CLEAN_PROVIDER, 'check_provider_consistency',
        name='rust-serde-2.spec', directory='rust-serde-1', cargo_toml='',
    )[0]
    assert 'does not match the spec file name "rust-serde-2.spec"' in message


def test_provider_consistent_layout_is_accepted(tmp_path: Path) -> None:
    assert _isolated(
        tmp_path, CLEAN_PROVIDER, 'check_provider_consistency',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    ) == []


# --------------------------------------------------------------------------
# C3 - pkgname is the package name without the rust- prefix.
# --------------------------------------------------------------------------


def test_pkgname_mismatch_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_PROVIDER.replace(
        '%global pkgname serde-1',
        '%global pkgname other-1',
    )
    message = _isolated(
        tmp_path, spec, 'check_pkgname',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    )[0]
    assert 'does not match' in message
    assert '"serde-1"' in message


def test_pkgname_defined_with_macro_is_accepted(tmp_path: Path) -> None:
    spec = CLEAN_PROVIDER.replace(
        '%global pkgname serde-1',
        '%global pkgname %{crate_name}-1',
    )
    assert _isolated(
        tmp_path, spec, 'check_pkgname',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    ) == []


# --------------------------------------------------------------------------
# C4 - the compatibility name groups a version by the page's rules.
# --------------------------------------------------------------------------


def test_wrong_group_for_stable_major_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_PROVIDER.replace(
        '%global pkgname serde-1',
        '%global pkgname serde-2',
    )
    message = _isolated(
        tmp_path, spec, 'check_compat_group',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    )[0]
    assert 'so the compatibility name is "serde-1"' in message


@pytest.mark.parametrize(
    ('crate', 'version', 'key'),
    [
        ('serde', '1.0.228', '1'),
        ('tokenizers', '0.22.2', '0.22'),
        ('foo', '0.0.7', '0.0.7'),
        ('bar', '0.0.12', '0.0.12'),
        ('baz', '2.0.0', '2'),
    ],
)
def test_compat_key_follows_the_grouping_rules(
    crate: str, version: str, key: str,
) -> None:
    assert rule._compat_key(version) == key


@pytest.mark.parametrize(
    ('version', 'key'),
    [
        ('0.6.0-rc.10', None),
        ('1.0.0-alpha.1', None),
        ('1.0.0', '1'),
        ('1.0.0+build.5', '1'),
        ('', None),
        ('not-a-version', None),
    ],
)
def test_compat_key_skips_prerelease_and_garbage(
    version: str, key: str | None,
) -> None:
    assert rule._compat_key(version) == key


def test_prerelease_provider_is_not_grouped(tmp_path: Path) -> None:
    spec = (
        CLEAN_PROVIDER
        .replace(
            '%global full_version 1.0.228',
            '%global full_version 0.6.0-rc.10',
        )
        .replace(
            '%global pkgname serde-1',
            '%global pkgname serde-0.6.0-rc.10',
        )
        .replace(
            'Name:           rust-serde-1',
            'Name:           rust-serde-0.6.0-rc.10',
        )
        .replace('Version:        1.0.228', 'Version:        0.6.0')
    )
    assert _isolated(
        tmp_path, spec, 'check_compat_group',
        name='rust-serde-0.6.0-rc.10.spec',
        directory='rust-serde-0.6.0-rc.10', cargo_toml='',
    ) == []


def test_missing_compatibility_suffix_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_PROVIDER.replace(
        '%global pkgname serde-1',
        '%global pkgname serde',
    )
    message = _isolated(
        tmp_path, spec, 'check_compat_group',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    )[0]
    assert 'carries no compatibility name' in message


# --------------------------------------------------------------------------
# C5 - the compatibility name is not unnecessarily fine-grained.
# --------------------------------------------------------------------------


def test_overly_fine_compatibility_name_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_PROVIDER.replace(
        '%global pkgname serde-1',
        '%global pkgname serde-1.0.228',
    )
    message = _isolated(
        tmp_path, spec, 'check_compat_granularity',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    )[0]
    assert 'unnecessarily fine-grained' in message


def test_exact_key_is_not_reported_as_fine(tmp_path: Path) -> None:
    assert _isolated(
        tmp_path, CLEAN_PROVIDER, 'check_compat_granularity',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    ) == []


# --------------------------------------------------------------------------
# C6 - a crate dependency is declared as a crate(...) capability.
# ---------------------------------------------------------------------------


def test_provider_package_name_in_buildrequires_is_reported(
    tmp_path: Path,
) -> None:
    spec = """\
Name:           mesa
Version:        25.0.0
Release:        %autorelease
Summary:        Mesa 3D graphics library
License:        MIT
URL:            https://mesa3d.org/
Source:         https://mesa3d.org/files/mesa-%{version}.tar.gz
BuildSystem:    meson
BuildRequires:  rust
BuildRequires:  rust-syn-2 >= 2.0.87
BuildRequires:  rust-rpm-macros

%description
Mesa 3D graphics library.
"""
    message = _isolated(
        tmp_path, spec, 'check_crate_capability',
        name='mesa.spec', directory='mesa',
    )[0]
    assert 'rust-syn-2' in message
    assert 'crate(syn-2)' in message


def test_tool_packages_are_not_crate_dependencies(tmp_path: Path) -> None:
    spec = """\
Name:           example
BuildSystem:    rust
BuildRequires:  rust
BuildRequires:  rust-rpm-macros
"""
    assert _isolated(
        tmp_path, spec, 'check_crate_capability',
        name='example.spec', directory='example',
    ) == []


def test_crate_capability_is_accepted(tmp_path: Path) -> None:
    assert _isolated(
        tmp_path, CLEAN_APP, 'check_crate_capability',
        name='ripgrep.spec', directory='ripgrep',
    ) == []


# --------------------------------------------------------------------------
# C7 - a crate(...) build dependency carries a version constraint.
# --------------------------------------------------------------------------


def test_crate_without_version_is_reported(tmp_path: Path) -> None:
    spec = """\
Name:           clang-wrap
BuildSystem:    rust
BuildRequires:  rust
BuildRequires:  rust-rpm-macros
BuildRequires:  crate(regex-1/default)
"""
    message = _isolated(
        tmp_path, spec, 'check_crate_version',
        name='clang-wrap.spec', directory='clang-wrap',
    )[0]
    assert 'without a version constraint' in message


def test_crate_with_version_is_accepted(tmp_path: Path) -> None:
    assert _isolated(
        tmp_path, CLEAN_APP, 'check_crate_version',
        name='ripgrep.spec', directory='ripgrep',
    ) == []


def test_runtime_crate_dependency_is_not_versioned_by_this_rule(
    tmp_path: Path,
) -> None:
    spec = """\
Name:           example
BuildSystem:    rust
BuildRequires:  rust
Requires:       crate(regex-1/default)
"""
    assert _isolated(
        tmp_path, spec, 'check_crate_version',
        name='example.spec', directory='example',
    ) == []


# --------------------------------------------------------------------------
# C8 - a pyproject Rust extension declares both Rust build dependencies.
# --------------------------------------------------------------------------


def test_pyproject_extension_without_macro_package_is_reported(
    tmp_path: Path,
) -> None:
    spec = CLEAN_PYPROJECT.replace('BuildRequires:  rust-rpm-macros\n', '')
    message = _isolated(
        tmp_path, spec, 'check_pyproject_toolchain',
        name='python-pydantic-core.spec', directory='python-pydantic-core',
    )[0]
    missing = message.split(';')[0]
    assert '"rust-rpm-macros"' in missing
    assert '"rust"' not in missing


def test_pyproject_extension_without_rust_is_reported(tmp_path: Path) -> None:
    spec = CLEAN_PYPROJECT.replace('BuildRequires:  rust\n', '')
    message = _isolated(
        tmp_path, spec, 'check_pyproject_toolchain',
        name='python-pydantic-core.spec', directory='python-pydantic-core',
    )[0]
    missing = message.split(';')[0]
    assert '"rust"' in missing
    assert '"rust-rpm-macros"' not in missing


def test_pyproject_extension_with_both_is_accepted(tmp_path: Path) -> None:
    assert _isolated(
        tmp_path, CLEAN_PYPROJECT, 'check_pyproject_toolchain',
        name='python-pydantic-core.spec', directory='python-pydantic-core',
    ) == []


def test_pyproject_without_crate_dependency_is_ignored(tmp_path: Path) -> None:
    spec = """\
Name:           python-msgspec
BuildSystem:    pyproject
BuildRequires:  python3-devel
"""
    assert _isolated(
        tmp_path, spec, 'check_pyproject_toolchain',
        name='python-msgspec.spec', directory='python-msgspec',
    ) == []


# --------------------------------------------------------------------------
# C9 - a crate provider provides a crate(...) capability.
# --------------------------------------------------------------------------


def test_provider_without_capability_is_reported(tmp_path: Path) -> None:
    spec = '\n'.join(
        line for line in CLEAN_PROVIDER.splitlines()
        if not line.startswith('Provides:')
    )
    message = _isolated(
        tmp_path, spec, 'check_provider_capability',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    )[0]
    assert 'crate(serde-1)' in message


def test_provider_with_capability_is_accepted(tmp_path: Path) -> None:
    assert _isolated(
        tmp_path, CLEAN_PROVIDER, 'check_provider_capability',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    ) == []


def test_capability_with_feature_path_is_accepted(tmp_path: Path) -> None:
    spec = CLEAN_PROVIDER.replace(
        'Provides:       crate(%{pkgname}) = %{full_version}',
        'Provides:       crate(%{pkgname}/default) = %{full_version}',
    )
    assert _isolated(
        tmp_path, spec, 'check_provider_capability',
        name='rust-serde-1.spec', directory='rust-serde-1', cargo_toml='',
    ) == []


# --------------------------------------------------------------------------
# C10 - the provider directory keeps the upstream Cargo.toml.
# --------------------------------------------------------------------------


def test_provider_without_cargo_toml_is_reported(tmp_path: Path) -> None:
    message = _isolated(
        tmp_path, CLEAN_PROVIDER, 'check_provider_cargo_toml',
        name='rust-serde-1.spec', directory='rust-serde-1',
    )[0]
    assert 'holds no Cargo.toml' in message


def test_provider_with_cargo_toml_is_accepted(tmp_path: Path) -> None:
    assert _isolated(
        tmp_path, CLEAN_PROVIDER, 'check_provider_cargo_toml',
        name='rust-serde-1.spec', directory='rust-serde-1',
        cargo_toml='[package]\nname = "serde"\n',
    ) == []


# --------------------------------------------------------------------------
# Flags
# --------------------------------------------------------------------------


def test_every_flag_can_be_switched_off(tmp_path: Path) -> None:
    spec = CLEAN_PROVIDER.replace(
        'Name:           rust-serde-1',
        'Name:           serde-1',
    )
    path = _write(
        tmp_path, spec, name='serde-1.spec', directory='serde-1',
    )
    assert CHECK_EXT(path, **{name: False for name in FLAGS}) == []


def test_one_flag_off_keeps_the_others(tmp_path: Path) -> None:
    spec = CLEAN_PROVIDER.replace(
        'Name:           rust-serde-1',
        'Name:           serde-1',
    )
    options = {name: True for name in FLAGS}
    options['check_crate_version'] = False
    path = _write(
        tmp_path, spec, name='serde-1.spec', directory='serde-1',
        cargo_toml='',
    )
    messages = [err.split(': ', 1)[1] for err in CHECK_EXT(path, **options)]
    assert len(messages) == 1
    assert 'rust-' in messages[0]


def test_plain_entry_point_uses_every_checkpoint(tmp_path: Path) -> None:
    spec = CLEAN_PROVIDER.replace(
        'Name:           rust-serde-1',
        'Name:           serde-1',
    )
    path = _write(
        tmp_path, spec, name='serde-1.spec', directory='serde-1',
        cargo_toml='',
    )
    assert CHECK(path) == CHECK_EXT(path)


def test_main_reports_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    spec = CLEAN_PROVIDER.replace(
        'Name:           rust-serde-1',
        'Name:           serde-1',
    )
    path = _write(
        tmp_path, spec, name='serde-1.spec', directory='serde-1',
        cargo_toml='',
    )
    assert rule.main([path]) == 1
    assert 'rust-' in capsys.readouterr().out


def test_main_returns_zero_for_a_clean_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(
        tmp_path, CLEAN_PROVIDER, name='rust-serde-1.spec',
        directory='rust-serde-1', cargo_toml='',
    )
    assert rule.main([path]) == 0
    assert capsys.readouterr().out == ''


def test_main_honours_a_disabled_checkpoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    spec = CLEAN_PROVIDER.replace(
        'Name:           rust-serde-1',
        'Name:           serde-1',
    )
    path = _write(
        tmp_path, spec, name='serde-1.spec', directory='serde-1',
        cargo_toml='',
    )
    assert rule.main(['--no-check-provider-prefix', path]) == 0
    assert capsys.readouterr().out == ''
