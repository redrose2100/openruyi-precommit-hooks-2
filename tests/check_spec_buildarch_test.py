# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_buildarch import _check_spec_buildarch
from openruyi_precommit_hooks.check_spec_buildarch import (
    _check_spec_buildarch_ext,
)
from openruyi_precommit_hooks.check_spec_buildarch import main

# A spec that satisfies every checkpoint: one source declaration, then the
# documented position window Source -> BuildArch -> BuildSystem.
CLEAN_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    autotools

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A package that writes no BuildArch at all. The field is conditional, so
# this is not a defect.
NO_BUILDARCH_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A data-only package: no source declaration and no BuildSystem, so the
# position clause cannot be decided and must stay silent.
NO_BOUNDARY_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildArch:      noarch

%description
An example package built from no source input.

%files
%license LICENSE

%changelog
%autochangelog
"""

# BuildArch written before the only source declaration, the defect measured
# in nine openRuyi specs.
BEFORE_SOURCE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildArch:      noarch
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# BuildArch written after the last numbered source declaration.
BEFORE_SOURCE_N_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
Source1:        foo.conf
BuildSystem:    autotools

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The source declaration is a %sourcelist macro rather than a field, so the
# last source line can only be found by scanning the block's lines.
BEFORE_SOURCELIST_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildArch:      noarch
BuildSystem:    autotools
%sourcelist https://example.org/a.tar.gz https://example.org/b.tar.gz

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# BuildArch written after BuildSystem, the other boundary of clause 2.
AFTER_BUILD_SYSTEM_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
BuildArch:      noarch

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A misspelled field still feeds the value and position checks, so one
# defect does not hide another. The position here is correct, so the
# spelling is the only defect.
MISSPELLED_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BUildArch:      noarch
BuildSystem:    autotools

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A noarch block whose build option makes the installed path follow the
# build host, the defect measured in hwdata.
NOARCH_ARCH_PATH_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    autotools
BuildOption(install):  libdir=%{_libdir}

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The conditional isa form expands to nothing on a noarch build, so this
# idiom is correct and must never be reported.
NOARCH_ISA_PROVIDES_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    autotools
Provides:       %{name}%{?_isa} = %{version}-%{release}

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A %files path may legitimately follow the library directory even when the
# payload is noarch, so the %files body is never read.
NOARCH_FILES_LIBDIR_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    cmake

%description
An example package.

%files
%{_libdir}/cmake/foo

%changelog
%autochangelog
"""

# A %define above the field region selects a build-time macro. It is not a
# field and does not contradict the architecture the block declares.
DEFINE_BEFORE_FIELDS_SPEC = """\
%define _name foo
%if "%{_host_cpu}" == "riscv64"
%define go_test_exclude_glob %{_name}/bench
%endif

Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    golangmodules

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A subpackage block restarts the field model: its own BuildArch is a fresh
# declaration and is not a duplicate of the main one.
SUBPACKAGE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    autotools

%description
An example package.

%package devel
Summary:        Development files

%description devel
Development files.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A %package block that carries its own BuildArch after its own Source.
SUBPACKAGE_BUILDARCH_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools

%description
An example package.

%package data
Summary:        Architecture independent data
Source1:        foo-data.tar.gz
BuildArch:      noarch

%description data
Architecture independent data.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A %package block whose BuildArch is written before its own Source, which
# is a defect of that block alone.
SUBPACKAGE_BUILDARCH_BEFORE_SOURCE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools

%description
An example package.

%package data
Summary:        Architecture independent data
BuildArch:      noarch
Source1:        foo-data.tar.gz

%description data
Architecture independent data.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A macro invocation is not a section, so it must not end the field block
# and hide the BuildArch written after it.
MACRO_NOT_SECTION_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
%global debug_package %{nil}
BuildArch:      noarch
BuildSystem:    autotools

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# BuildArch inside a comment is not a field.
COMMENTED_BUILDARCH_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
# BuildArch:    x86_64
BuildSystem:    autotools

%description
An example package.

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


def _spec_with_value(value: str) -> str:
    return f"""\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{{version}}.tar.gz
BuildArch:      {value}
BuildSystem:    autotools

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""


def _spec_with_duplicate_buildarch() -> str:
    return """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildArch:      x86_64
BuildSystem:    autotools

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""


@pytest.mark.parametrize(
    'content',
    [
        pytest.param(CLEAN_SPEC, id='clean'),
        pytest.param(NO_BUILDARCH_SPEC, id='field-absent'),
        pytest.param(NO_BOUNDARY_SPEC, id='no-source-no-buildsystem'),
        pytest.param(NOARCH_ISA_PROVIDES_SPEC, id='noarch-conditional-isa'),
        pytest.param(NOARCH_FILES_LIBDIR_SPEC, id='noarch-files-libdir'),
        pytest.param(DEFINE_BEFORE_FIELDS_SPEC, id='define-before-fields'),
        pytest.param(SUBPACKAGE_SPEC, id='subpackage-without-buildarch'),
        pytest.param(
            SUBPACKAGE_BUILDARCH_SPEC,
            id='subpackage-buildarch-after-source',
        ),
        pytest.param(MACRO_NOT_SECTION_SPEC, id='macro-is-not-section'),
        pytest.param(COMMENTED_BUILDARCH_SPEC, id='commented-field'),
        pytest.param(_spec_with_value('noarch'), id='value-noarch'),
        pytest.param(_spec_with_value('x86_64'), id='value-x86_64'),
        pytest.param(_spec_with_value('aarch64'), id='value-aarch64'),
        pytest.param(_spec_with_value('riscv64'), id='value-riscv64'),
        pytest.param(_spec_with_value('loongarch64'), id='value-loongarch64'),
        pytest.param(_spec_with_value('armv7hl'), id='value-armv7hl'),
        pytest.param(
            _spec_with_value('%{buildarch}'),
            id='value-macro',
        ),
        pytest.param(
            _spec_with_value('%{?go_arch}%{!?go_arch:noarch}'),
            id='value-conditional-macro',
        ),
    ],
)
def test_passing_specs(tmp_path: Path, content: str) -> None:
    path = _write(tmp_path, 'foo.spec', content)
    assert _check_spec_buildarch(path) == []


@pytest.mark.parametrize(
    ('content', 'expected'),
    [
        pytest.param(
            BEFORE_SOURCE_SPEC,
            'BuildArch (line 7) must be written after the last source '
            'declaration (line 8)',
            id='before-source',
        ),
        pytest.param(
            BEFORE_SOURCE_N_SPEC,
            'BuildArch (line 8) must be written after the last source '
            'declaration (line 9)',
            id='before-source-n',
        ),
        pytest.param(
            BEFORE_SOURCELIST_SPEC,
            'BuildArch (line 7) must be written after the last source '
            'declaration (line 9)',
            id='before-sourcelist',
        ),
        pytest.param(
            AFTER_BUILD_SYSTEM_SPEC,
            'BuildArch (line 9) must be written before BuildSystem '
            '(line 8)',
            id='after-buildsystem',
        ),
        pytest.param(
            MISSPELLED_SPEC,
            'BuildArch field (line 8) is spelled "BUildArch"; '
            'write "BuildArch"',
            id='misspelled-uppercase',
        ),
        pytest.param(
            NOARCH_ARCH_PATH_SPEC,
            'BuildArch "noarch" (line 8) declares an architecture '
            'independent package, but line 10 uses "%{_libdir}"',
            id='noarch-arch-path',
        ),
        pytest.param(
            SUBPACKAGE_BUILDARCH_BEFORE_SOURCE_SPEC,
            'BuildArch (line 15) must be written after the last source '
            'declaration (line 16)',
            id='subpackage-before-source',
        ),
        pytest.param(
            _spec_with_duplicate_buildarch(),
            'BuildArch field block declares the field 2 times '
            '(lines 8, 9); keep one declaration',
            id='duplicate',
        ),
        pytest.param(
            _spec_with_value(''),
            'BuildArch field (line 8) is empty',
            id='empty',
        ),
        pytest.param(
            _spec_with_value('x86_64 aarch64'),
            'BuildArch "x86_64 aarch64" (line 8) is not a bare architecture '
            'token; write one lowercase architecture name such as "noarch" '
            'or "x86_64"',
            id='value-two-architectures',
        ),
        pytest.param(
            _spec_with_value('Noarch'),
            'BuildArch "Noarch" (line 8) is not a bare architecture token; '
            'write one lowercase architecture name such as "noarch" or '
            '"x86_64"',
            id='value-capitalized',
        ),
        pytest.param(
            _spec_with_value('noarch, x86_64'),
            'BuildArch "noarch, x86_64" (line 8) is not a bare architecture '
            'token; write one lowercase architecture name such as "noarch" '
            'or "x86_64"',
            id='value-comma-list',
        ),
    ],
)
def test_failing_specs(
    tmp_path: Path,
    content: str,
    expected: str,
) -> None:
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_buildarch(path)
    assert len(errors) == 1
    assert errors[0] == f'{path}: {expected}'


def test_noarch_architecture_option_reported(tmp_path: Path) -> None:
    """A noarch block must not key an install path off the build host."""
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    autotools
BuildOption(install):  libdir=%{_libdir}

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_buildarch(path)
    assert len(errors) == 1
    assert '"%{_libdir}"' in errors[0]


@pytest.mark.parametrize(
    'macro',
    [
        pytest.param('%{_libdir}', id='libdir'),
        pytest.param('%{_lib}', id='lib'),
        pytest.param('%{_lib64}', id='lib64'),
        pytest.param('%{_arch}', id='arch'),
        pytest.param('%{_target_cpu}', id='target-cpu'),
        pytest.param('%{_host_cpu}', id='host-cpu'),
        pytest.param('%{_target_platform}', id='target-platform'),
    ],
)
def test_noarch_architecture_macros(tmp_path: Path, macro: str) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'Summary:        Example package\n'
        'License:        MulanPSL-2.0\n'
        'URL:            https://example.org/foo\n'
        'Source0:        https://example.org/foo-%{version}.tar.gz\n'
        'BuildArch:      noarch\n'
        'BuildSystem:    autotools\n'
        f'Provides:       foo-{macro}-x = 1\n'
        '\n'
        '%description\n'
        'An example package.\n'
        '\n'
        '%files\n'
        '%license LICENSE\n'
        '\n'
        '%changelog\n'
        '%autochangelog\n'
    )
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_buildarch(path)
    assert len(errors) == 1
    assert macro in errors[0]


def test_two_findings_in_one_block(tmp_path: Path) -> None:
    """A block can break the position rule on both sides at once."""
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
BuildArch:      noarch
Source1:        foo.conf

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_buildarch(path)
    assert len(errors) == 2
    assert any('after the last source declaration' in e for e in errors)
    assert any('before BuildSystem' in e for e in errors)


def test_flags_disable_checkpoints(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', MISSPELLED_SPEC)
    assert _check_spec_buildarch_ext(path, check_field_case=False) == []

    noarch = _write(tmp_path, 'bar.spec', NOARCH_ARCH_PATH_SPEC)
    assert _check_spec_buildarch_ext(noarch, check_noarch=False) == []


def test_flags_keep_other_checkpoints(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', MISSPELLED_SPEC)
    errors = _check_spec_buildarch_ext(path, check_noarch=False)
    assert len(errors) == 1
    assert 'is spelled' in errors[0]


def test_missing_file_reported() -> None:
    missing = str(Path('does') / 'not' / 'exist.spec')
    errors = _check_spec_buildarch(missing)
    assert len(errors) == 1
    assert errors[0].startswith(missing)


def test_non_utf8_file_reported(tmp_path: Path) -> None:
    path = tmp_path / 'latin.spec'
    path.write_bytes(b'Name: foo\nSummary: caf\xe9\n')
    errors = _check_spec_buildarch(str(path))
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
    path = _write(tmp_path, 'foo.spec', BEFORE_SOURCE_SPEC)
    assert main([path]) == 1
    assert path in capsys.readouterr().out


def test_main_reports_every_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    first = _write(tmp_path, 'a.spec', BEFORE_SOURCE_SPEC)
    second = _write(tmp_path, 'b.spec', MISSPELLED_SPEC)
    assert main([first, second]) == 1
    out = capsys.readouterr().out
    assert first in out
    assert second in out


def test_main_no_check_flags(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', MISSPELLED_SPEC)
    assert main(['--no-check-field-case', path]) == 0
    captured = capsys.readouterr()
    assert captured.err == ''

    noarch = _write(tmp_path, 'bar.spec', NOARCH_ARCH_PATH_SPEC)
    assert main(['--no-check-noarch', noarch]) == 0


def test_subpackage_block_is_independent(tmp_path: Path) -> None:
    """A subpackage BuildArch is a fresh declaration, not a duplicate."""
    path = _write(tmp_path, 'foo.spec', SUBPACKAGE_BUILDARCH_SPEC)
    assert _check_spec_buildarch(path) == []


def test_empty_subpackage_block_keeps_indices(tmp_path: Path) -> None:
    """An empty %package block must not shift the following block."""
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    autotools

%description
An example package.

%package empty

%description empty
Nothing.

%package data
Summary:        Data files
Source1:        foo-data.tar.gz
BuildArch:      noarch

%description data
Data files.

%files
%license LICENSE

%changelog
%autochangelog
"""
    path = _write(tmp_path, 'foo.spec', content)
    assert _check_spec_buildarch(path) == []


def test_corpus_regression_calico(tmp_path: Path) -> None:
    """The real defect: BuildArch before a numbered source declaration."""
    content = """\
Name:           calico
Version:        3.32.0
Release:        %autorelease
Summary:        Calico manifests
License:        Apache-2.0
URL:            https://github.com/projectcalico/calico
BuildArch:      noarch
#!RemoteAsset:  sha256:55defb4135a7f04942ff596848b4decc5eeed67d0d97f81b57df5395f41354c9
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        calico-v%{version}-crds.yaml.in
Source2:        calico-v%{version}-openruyi-riscv64.yaml.in
Source3:        README.openruyi

Recommends:     kubernetes

%description
Calico.

%files
%license LICENSE

%changelog
%autochangelog
"""
    path = _write(tmp_path, 'calico.spec', content)
    errors = _check_spec_buildarch(path)
    assert len(errors) == 1
    assert 'line 7' in errors[0]
    assert 'last source declaration (line 12)' in errors[0]


def test_corpus_regression_hwdata(tmp_path: Path) -> None:
    """The real defect: a noarch block keyed off the library directory."""
    content = """\
Name:           hwdata
Version:        0.407
Release:        %autorelease
Summary:        Hardware identification data
License:        GPL-2.0-or-later
URL:            https://github.com/vcrhonek/hwdata
Source0:        https://github.com/vcrhonek/hwdata/archive/v%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    autotools

BuildOption(install):  libdir=%{_libdir}

BuildRequires:  make

%description
hwdata.

%files
%license COPYING

%changelog
%autochangelog
"""
    path = _write(tmp_path, 'hwdata.spec', content)
    errors = _check_spec_buildarch(path)
    assert len(errors) == 1
    assert '"%{_libdir}"' in errors[0]


def test_corpus_regression_misspelling(tmp_path: Path) -> None:
    """The real defect: the field is spelled BUildArch."""
    content = _spec_with_value('noarch').replace(
        'BuildArch:      noarch',
        'BUildArch:      noarch',
    )
    path = _write(tmp_path, 'chart.spec', content)
    errors = _check_spec_buildarch(path)
    assert len(errors) == 1
    assert 'is spelled "BUildArch"' in errors[0]
