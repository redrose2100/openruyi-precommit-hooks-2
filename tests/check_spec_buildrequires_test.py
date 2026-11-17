# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check-spec-buildrequires."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_buildrequires import _check_spec_buildrequires
from openruyi_precommit_hooks.check_spec_buildrequires import _check_spec_buildrequires_ext
from openruyi_precommit_hooks.check_spec_buildrequires import main


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
BuildOption(build):  %{?_smp_mflags}
BuildRequires:  pkgconfig(openssl) >= 3.0
BuildRequires:  python3dist(pytest)
Provides:       demo-libs = %{version}-%{release}

%description
A demo package.
"""

NO_BUILDREQUIRES_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildSystem:    autotools

%description
A demo package.
"""

SUBPACKAGE_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildSystem:    autotools
BuildOption(install):  %{name} +auto
BuildRequires:  pkgconfig(openssl)

%description
A demo package.

%package        devel
Summary:        Development files
BuildSystem:    cmake
BuildOption(build):  -DCMAKE_BUILD_TYPE=Release
BuildRequires:  pkgconfig(zlib)
Provides:       demo-devel = %{version}

%description    devel
Development files.
"""


def _write(tmp_path: Path, content: str) -> str:
    path = tmp_path / 'demo.spec'
    path.write_text(content, encoding='utf-8')
    return str(path)


def _single_error(tmp_path: Path, content: str) -> str:
    errors = _check_spec_buildrequires(_write(tmp_path, content))
    assert len(errors) == 1, errors
    return errors[0].split(': ', 1)[1]


def test_clean_spec_has_no_findings(tmp_path: Path) -> None:
    assert _check_spec_buildrequires(_write(tmp_path, CLEAN_SPEC)) == []


def test_absent_field_is_not_a_finding(tmp_path: Path) -> None:
    assert _check_spec_buildrequires(
        _write(tmp_path, NO_BUILDREQUIRES_SPEC),
    ) == []


def test_subpackage_block_has_no_findings(tmp_path: Path) -> None:
    assert _check_spec_buildrequires(_write(tmp_path, SUBPACKAGE_SPEC)) == []


def test_missing_file_is_reported() -> None:
    errors = _check_spec_buildrequires('does-not-exist.spec')
    assert len(errors) == 1
    assert errors[0].startswith('does-not-exist.spec: ')


def test_non_utf8_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'latin.spec'
    path.write_bytes(b'Name: demo\n# \xff\n')
    errors = _check_spec_buildrequires(str(path))
    assert errors == [f'{path}: file is not valid UTF-8']


# --------------------------------------------------------------------------
# R1 - the field is spelled BuildRequires.
# --------------------------------------------------------------------------


def test_r1_misspelled_field(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequire:   python3dist(pytest)',
    )
    message = _single_error(tmp_path, spec)
    assert 'is spelled "BuildRequire"' in message
    assert 'write "BuildRequires"' in message


def test_r1_uppercase_field(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'buildrequires:  python3dist(pytest)',
    )
    message = _single_error(tmp_path, spec)
    assert 'is spelled "buildrequires"' in message


def test_r1_can_be_disabled(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequire:   python3dist(pytest)',
    )
    errors = _check_spec_buildrequires_ext(
        _write(tmp_path, spec),
        check_field_case=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# R2 - the field declares at least one dependency.
# --------------------------------------------------------------------------


def test_r2_empty_field(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:',
    )
    message = _single_error(tmp_path, spec)
    assert 'declares no dependency' in message
    assert 'one dependency per line' in message


def test_r2_can_be_disabled(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:',
    )
    errors = _check_spec_buildrequires_ext(
        _write(tmp_path, spec),
        check_value=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# R3 - one field line declares exactly one dependency.
# --------------------------------------------------------------------------


def test_r3_two_dependencies_on_one_line(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  gcc make',
    )
    message = _single_error(tmp_path, spec)
    assert 'declares 2 dependencies' in message
    assert 'one dependency per line' in message


def test_r3_comma_separated_dependencies(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  libXaw-devel, libXmu-devel',
    )
    message = _single_error(tmp_path, spec)
    assert 'declares 2 dependencies' in message


def test_r3_versioned_dependency_is_one_dependency(
    tmp_path: Path,
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  pkgconfig(zlib) >= 1.2.11',
    )
    assert _check_spec_buildrequires(_write(tmp_path, spec)) == []


def test_r3_rich_dependency_is_one_dependency(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  (python3dist(foo) if python3dist(bar))',
    )
    assert _check_spec_buildrequires(_write(tmp_path, spec)) == []


def test_r3_with_clause_is_one_dependency(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  foo with bar',
    )
    assert _check_spec_buildrequires(_write(tmp_path, spec)) == []


def test_r3_can_be_disabled(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  gcc make',
    )
    errors = _check_spec_buildrequires_ext(
        _write(tmp_path, spec),
        check_one_per_line=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# R4 - one field block declares each dependency at most once.
# --------------------------------------------------------------------------


def test_r4_duplicate_dependency(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  pkgconfig(openssl) >= 3.0\n'
        'BuildRequires:  python3dist(pytest)',
    )
    message = _single_error(tmp_path, spec)
    assert 'BuildRequires "pkgconfig(openssl) >= 3.0" (line 12)' in message
    assert 'is already declared at line 11' in message
    assert 'remove the duplicate' in message


def test_r4_version_interval_is_not_a_duplicate(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  python3dist(dill) >= 0.3\n'
        'BuildRequires:  python3dist(dill) < 0.4.2',
    )
    assert _check_spec_buildrequires(_write(tmp_path, spec)) == []


def test_r4_same_dependency_in_two_blocks_is_allowed(
    tmp_path: Path,
) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'BuildRequires:  pkgconfig(zlib)',
        'BuildRequires:  pkgconfig(openssl)',
    )
    assert _check_spec_buildrequires(_write(tmp_path, spec)) == []


def test_r4_conditional_block_is_exempt(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  python3dist(pytest)\n'
        '%if 0%{?fedora}\n'
        'BuildRequires:  python3dist(pytest)\n'
        '%endif',
    )
    assert _check_spec_buildrequires(_write(tmp_path, spec)) == []


def test_r4_can_be_disabled(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  pkgconfig(openssl) >= 3.0\n'
        'BuildRequires:  python3dist(pytest)',
    )
    errors = _check_spec_buildrequires_ext(
        _write(tmp_path, spec),
        check_duplicate=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# R5 - the field sits after the builders and before Provides.
# --------------------------------------------------------------------------


def test_r5_before_build_system(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildSystem:    autotools\n'
        'BuildOption(build):  %{?_smp_mflags}\n'
        'BuildRequires:  pkgconfig(openssl) >= 3.0',
        'BuildRequires:  pkgconfig(openssl) >= 3.0\n'
        'BuildSystem:    autotools\n'
        'BuildOption(build):  %{?_smp_mflags}',
    )
    errors = _check_spec_buildrequires(_write(tmp_path, spec))
    assert len(errors) == 2, errors
    assert 'must be written after BuildSystem (line 10)' in errors[0]
    assert 'must be written after BuildOption (line 11)' in errors[1]
    assert 'BuildSystem -> BuildOption -> BuildRequires' in errors[1]


def test_r5_before_build_option(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildOption(build):  %{?_smp_mflags}\n'
        'BuildRequires:  pkgconfig(openssl) >= 3.0',
        'BuildRequires:  pkgconfig(openssl) >= 3.0\n'
        'BuildOption(build):  %{?_smp_mflags}',
    )
    message = _single_error(tmp_path, spec)
    assert 'must be written after BuildOption (line 11)' in message


def test_r5_after_provides(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Provides:       demo-libs = %{version}-%{release}',
        'Provides:       demo-libs = %{version}-%{release}\n'
        'BuildRequires:  zlib-devel',
    )
    message = _single_error(tmp_path, spec)
    assert 'must be written before Provides (line 13)' in message
    assert 'Requires -> Provides' in message


def test_r5_absent_boundary_is_silent(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Provides:       demo-devel = %{version}\n',
        '',
    )
    assert _check_spec_buildrequires(_write(tmp_path, spec)) == []


def test_r5_can_be_disabled(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Provides:       demo-libs = %{version}-%{release}',
        'Provides:       demo-libs = %{version}-%{release}\n'
        'BuildRequires:  zlib-devel',
    )
    errors = _check_spec_buildrequires_ext(
        _write(tmp_path, spec),
        check_position=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# R6 - the field sits inside the header field block.
# --------------------------------------------------------------------------


def test_r6_after_first_section(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        '%description\nA demo package.\n',
        '%description\nA demo package.\nBuildRequires:  zlib-devel\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'is written outside the header field block' in message
    assert 'write it before the first section' in message


def test_r6_inside_macro_body_is_silent(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildSystem:    autotools\n',
        'BuildSystem:    autotools\n'
        '%global bundled_provides %{expand:\n'
        'BuildRequires:  bundled(zlib)\n'
        '}\n',
    )
    assert _check_spec_buildrequires(_write(tmp_path, spec)) == []


def test_r6_in_subpackage_block_is_silent(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        '%description\nA demo package.\n',
        '%description\nA demo package.\n'
        '%package        tools\n'
        'BuildRequires:  zlib-devel\n'
        '%description    tools\nTools.\n',
    )
    assert _check_spec_buildrequires(_write(tmp_path, spec)) == []


# --------------------------------------------------------------------------
# R7 - a pkgconfig(...) declaration names a bare module.
# --------------------------------------------------------------------------


def test_r7_empty_module(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  pkgconfig(openssl) >= 3.0',
        'BuildRequires:  pkgconfig()',
    )
    message = _single_error(tmp_path, spec)
    assert 'pkgconfig module (line 11) is empty' in message
    assert 'write "pkgconfig(<module>)"' in message


def test_r7_padded_module(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  pkgconfig(openssl) >= 3.0',
        'BuildRequires:  pkgconfig( openssl )',
    )
    message = _single_error(tmp_path, spec)
    assert 'carries extra spacing' in message


def test_r7_devel_module(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  pkgconfig(openssl) >= 3.0',
        'BuildRequires:  pkgconfig(openssl-devel)',
    )
    message = _single_error(tmp_path, spec)
    assert 'ends with "-devel"' in message
    assert 'write the pkg-config module name' in message


def test_r7_upper_case_module_is_allowed(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  pkgconfig(openssl) >= 3.0',
        'BuildRequires:  pkgconfig(Qt6Core)',
    )
    assert _check_spec_buildrequires(_write(tmp_path, spec)) == []


def test_r7_can_be_disabled(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  pkgconfig(openssl) >= 3.0',
        'BuildRequires:  pkgconfig(openssl-devel)',
    )
    errors = _check_spec_buildrequires_ext(
        _write(tmp_path, spec),
        check_pkgconfig=False,
    )
    assert errors == []


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
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  gcc make',
    )
    path = _write(tmp_path, spec)
    assert main([path]) == 1
    out = capsys.readouterr().out
    assert 'declares 2 dependencies' in out
    assert path in out


def test_main_honours_disable_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildRequires:  python3dist(pytest)',
        'BuildRequires:  gcc make',
    )
    path = _write(tmp_path, spec)
    assert main([path, '--no-check-one-per-line']) == 0
    assert capsys.readouterr().out == ''


def test_main_without_filenames_returns_zero() -> None:
    assert main([]) == 0
