# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_buildsystem import (
    _check_spec_buildsystem,
)
from openruyi_precommit_hooks.check_spec_buildsystem import (
    _check_spec_buildsystem_ext,
)
from openruyi_precommit_hooks.check_spec_buildsystem import main

# A spec that satisfies every checkpoint: one source declaration, then the
# documented position window Source -> BuildArch -> BuildSystem, then the
# build requirements.
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

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A package that builds entirely through explicit sections. The field is
# conditional, so omitting it is legal and is never a finding.
NO_BUILDSYSTEM_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildArch:      noarch

%description
An example package.

%prep
%autosetup

%build
:

%files
%license LICENSE

%changelog
%autochangelog
"""

# A data-only package: no source declaration, so the position window has no
# lower bound and the field must not be reported for it.
DATA_ONLY_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildArch:      noarch
BuildSystem:    autotools

%description
An example package built from no source input.

%files
%license LICENSE

%changelog
%autochangelog
"""

# An empty field, forbidden by the third clause. The field is present but
# says nothing.
EMPTY_VALUE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The field written with a lower case "s" in the second word, the defect
# measured in nine openRuyi specs.
MISSPELLED_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
Buildsystem:    autotools

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A misspelled field still feeds the value and position checks, so one
# defect does not hide another. Here the position is correct and the value
# is valid, so the spelling is the only finding.
MISSPELLED_ONLY_SPEC = MISSPELLED_SPEC

# The field written twice in one block, the defect measured in
# go-github-rcrowley-go-metrics.
DUPLICATE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    golangmodules

BuildRequires:  go
BuildSystem:    golangmodules

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The field written before the last source declaration. A source
# declaration only opens the position window; it must close before the
# field.
BEFORE_LAST_SOURCE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
BuildSystem:    rust
Source0:        https://example.org/foo-%{version}.tar.gz
Source1:        foo.conf
BuildArch:      noarch

BuildRequires:  rust

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
BuildSystem:    autotools
%sourcelist
foo.conf
bar.conf
BuildArch:      noarch

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The field written before BuildArch, which reverses the documented window.
BEFORE_BUILDARCH_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
BuildArch:      noarch

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The field written after the first BuildRequires, which closes the window.
AFTER_BUILDREQUIRES_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  gcc
BuildSystem:    autotools

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A value that is not a single bare token: a space separated pair.
TWO_VALUES_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    autotools cmake

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A value with a capital letter and a dash. The build system name is a
# fixed keyword, so the shape is reported.
ODD_VALUE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    Auto-tools

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The value is a macro reference. Unlike a parameterised field, this field
# names a fixed keyword, so the indirection is reported.
MACRO_VALUE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    %{build_system}

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A build system name that is not in the documented set is still a well
# formed token, so it passes: the main spec does not maintain the list of
# usable names.
UNLISTED_VALUE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    somefuturesystem

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A %define above the field region selects a build-time macro. It is not a
# field and does not move the field window.
DEFINE_BEFORE_FIELDS_SPEC = """\
%define _name foo
%if "%{_host_cpu}" == "riscv64"
%define extra_test_args -short
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

BuildRequires:  go

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A subpackage block restarts the field model: its own BuildSystem is a
# fresh declaration and is not a duplicate of the main one.
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

BuildRequires:  gcc

%description
An example package.

%package data
Summary:        Architecture independent data
BuildArch:      noarch
BuildSystem:    autotools

BuildRequires:  gcc

%description data
Data files.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A subpackage block whose BuildSystem is written before its own BuildArch,
# which is a defect of that block alone.
SUBPACKAGE_BEFORE_ARCH_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    autotools

BuildRequires:  gcc

%description
An example package.

%package data
Summary:        Architecture independent data
BuildSystem:    autotools
BuildArch:      noarch

BuildRequires:  gcc

%description data
Data files.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A macro invocation is not a section, so it must not end the field block
# and hide the BuildSystem written after it.
MACRO_BEFORE_FIELDS_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
%global debug_package %{nil}
BuildSystem:    autotools

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The field inside a comment is not a field.
COMMENTED_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
# BuildSystem:    autotools

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The four comments above are followed by a second spelling mistake: the
# field written in upper case.
UPPER_CASE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BUILDSYSTEM:    autotools

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding='utf-8')
    return str(path)


def _spec_with_value(value: str) -> str:
    separator = '    ' if value else ''
    return f"""\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{{version}}.tar.gz
BuildArch:      noarch
BuildSystem:{separator}{value}

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""


@pytest.mark.parametrize(
    'content',
    (
        pytest.param(CLEAN_SPEC, id='clean'),
        pytest.param(NO_BUILDSYSTEM_SPEC, id='field-omitted'),
        pytest.param(DATA_ONLY_SPEC, id='data-only'),
        pytest.param(UNLISTED_VALUE_SPEC, id='unlisted-name'),
        pytest.param(DEFINE_BEFORE_FIELDS_SPEC, id='define-above-fields'),
        pytest.param(SUBPACKAGE_SPEC, id='subpackage'),
        pytest.param(MACRO_BEFORE_FIELDS_SPEC, id='macro-above-fields'),
        pytest.param(COMMENTED_SPEC, id='commented-out'),
    ),
)
def test_passing_specs(tmp_path: Path, content: str) -> None:
    path = _write(tmp_path, 'foo.spec', content)
    assert _check_spec_buildsystem(path) == []


@pytest.mark.parametrize(
    ('content', 'expected'),
    (
        pytest.param(
            MISSPELLED_SPEC,
            'BuildSystem field (line 9) is spelled "Buildsystem"; '
            'write "BuildSystem"',
            id='misspelled-lowercase',
        ),
        pytest.param(
            UPPER_CASE_SPEC,
            'BuildSystem field (line 9) is spelled "BUILDSYSTEM"; '
            'write "BuildSystem"',
            id='misspelled-uppercase',
        ),
        pytest.param(
            EMPTY_VALUE_SPEC,
            'BuildSystem field (line 9) is empty',
            id='empty-value',
        ),
        pytest.param(
            TWO_VALUES_SPEC,
            'BuildSystem "autotools cmake" (line 9) is not a single bare '
            'build system name; write one lowercase token such as '
            '"autotools" or "cmake"',
            id='two-values',
        ),
        pytest.param(
            ODD_VALUE_SPEC,
            'BuildSystem "Auto-tools" (line 9) is not a single bare '
            'build system name; write one lowercase token such as '
            '"autotools" or "cmake"',
            id='odd-value',
        ),
        pytest.param(
            MACRO_VALUE_SPEC,
            'BuildSystem "%{build_system}" (line 9) uses a macro '
            'reference; write one literal lowercase build system name '
            'such as "autotools" or "cmake"',
            id='macro-value',
        ),
        pytest.param(
            BEFORE_LAST_SOURCE_SPEC,
            'BuildSystem (line 7) must be written after the last source '
            'declaration (line 9)',
            id='before-last-source',
        ),
        pytest.param(
            BEFORE_SOURCELIST_SPEC,
            'BuildSystem (line 7) must be written after the last source '
            'declaration (line 8)',
            id='before-sourcelist',
        ),
        pytest.param(
            BEFORE_BUILDARCH_SPEC,
            'BuildSystem (line 8) must be written after BuildArch '
            '(line 9)',
            id='before-buildarch',
        ),
        pytest.param(
            AFTER_BUILDREQUIRES_SPEC,
            'BuildSystem (line 11) must be written before BuildRequires '
            '(line 10)',
            id='after-buildrequires',
        ),
    ),
)
def test_failing_specs(
    tmp_path: Path,
    content: str,
    expected: str,
) -> None:
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_buildsystem(path)
    assert errors, 'expected at least one finding'
    assert any(expected in err for err in errors), errors


def test_duplicate_reported_once(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', DUPLICATE_SPEC)
    errors = _check_spec_buildsystem(path)
    assert any(
        'BuildSystem field block declares the field 2 times '
        '(lines 9, 12); keep one declaration' in err
        for err in errors
    ), errors


def test_duplicate_also_moves_position(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', DUPLICATE_SPEC)
    errors = _check_spec_buildsystem(path)
    assert any('must be written before BuildRequires' in err for err in errors)


@pytest.mark.parametrize(
    'value',
    (
        pytest.param('', id='empty'),
        pytest.param(' ', id='spaces'),
    ),
)
def test_blank_value_is_empty(tmp_path: Path, value: str) -> None:
    path = _write(tmp_path, 'foo.spec', _spec_with_value(value))
    errors = _check_spec_buildsystem(path)
    assert any('(line 9) is empty' in err for err in errors), errors


@pytest.mark.parametrize(
    'value',
    (
        pytest.param('autotools', id='autotools'),
        pytest.param('cmake', id='cmake'),
        pytest.param('meson', id='meson'),
        pytest.param('golang', id='golang'),
        pytest.param('golangmodules', id='golangmodules'),
        pytest.param('perlbuild', id='perlbuild'),
        pytest.param('perlmaker', id='perlmaker'),
        pytest.param('pyproject', id='pyproject'),
        pytest.param('rust', id='rust'),
        pytest.param('rustcrates', id='rustcrates'),
    ),
)
def test_documented_names_pass(tmp_path: Path, value: str) -> None:
    path = _write(tmp_path, 'foo.spec', _spec_with_value(value))
    assert _check_spec_buildsystem(path) == []


def test_two_findings_in_one_block(tmp_path: Path) -> None:
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:
BuildArch:      noarch

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""
    path = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_buildsystem(path)
    assert any('(line 8) is empty' in err for err in errors), errors
    assert any('must be written after BuildArch' in err for err in errors), errors


def test_flags_disable_checkpoints(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', MISSPELLED_SPEC)
    assert _check_spec_buildsystem_ext(
        path,
        check_field_case=False,
    ) == []


def test_flags_disable_value(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', EMPTY_VALUE_SPEC)
    assert _check_spec_buildsystem_ext(path, check_value=False) == []


def test_flags_disable_position(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', AFTER_BUILDREQUIRES_SPEC)
    assert _check_spec_buildsystem_ext(path, check_position=False) == []


def test_flags_keep_other_checkpoints(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', MISSPELLED_SPEC)
    errors = _check_spec_buildsystem_ext(path, check_value=False)
    assert errors


def test_missing_file_reported() -> None:
    errors = _check_spec_buildsystem('/nonexistent/foo.spec')
    assert len(errors) == 1
    assert '/nonexistent/foo.spec' in errors[0]


def test_non_utf8_file_reported(tmp_path: Path) -> None:
    path = tmp_path / 'foo.spec'
    path.write_bytes(b'Name: \xff\xfe\n')
    errors = _check_spec_buildsystem(str(path))
    assert len(errors) == 1
    assert 'not valid UTF-8' in errors[0]


def test_main_returns_zero_for_clean_spec(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', CLEAN_SPEC)
    assert main([path]) == 0
    assert capsys.readouterr().out == ''


def test_main_returns_zero_without_filenames(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    assert capsys.readouterr().out == ''


def test_main_returns_one_for_failing_spec(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', MISSPELLED_SPEC)
    assert main([path]) == 1
    assert 'write "BuildSystem"' in capsys.readouterr().out


def test_main_reports_every_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first = _write(tmp_path, 'a.spec', MISSPELLED_SPEC)
    second = _write(tmp_path, 'b.spec', EMPTY_VALUE_SPEC)
    assert main([first, second]) == 1
    out = capsys.readouterr().out
    assert 'a.spec' in out
    assert 'b.spec' in out


def test_main_no_check_flags(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', MISSPELLED_SPEC)
    assert main([path, '--no-check-field-case']) == 0
    assert capsys.readouterr().out == ''


def test_main_no_check_value_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', EMPTY_VALUE_SPEC)
    assert main([path, '--no-check-value']) == 0
    assert capsys.readouterr().out == ''


def test_main_no_check_position_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', AFTER_BUILDREQUIRES_SPEC)
    assert main([path, '--no-check-position']) == 0
    assert capsys.readouterr().out == ''


def test_subpackage_block_is_independent(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', SUBPACKAGE_SPEC)
    assert _check_spec_buildsystem(path) == []


def test_subpackage_position_reported(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', SUBPACKAGE_BEFORE_ARCH_SPEC)
    errors = _check_spec_buildsystem(path)
    assert len(errors) == 1, errors
    assert 'BuildSystem (line 18) must be written after BuildArch ' \
        '(line 19)' in errors[0], errors


def test_empty_subpackage_block_keeps_indices(tmp_path: Path) -> None:
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

BuildRequires:  gcc

%description
An example package.

%package docs
Summary:        Documentation

%description docs
Documentation.

%files
%license LICENSE

%changelog
%autochangelog
"""
    path = _write(tmp_path, 'foo.spec', content)
    assert _check_spec_buildsystem(path) == []


def test_corpus_regression_rcrowley(tmp_path: Path) -> None:
    content = """\
Name:           go-github-rcrowley-go-metrics
Version:        0+git20250401.65e299d
Release:        %autorelease
Summary:        Go port of Coda Hale's Metrics library
License:        BSD 2-Clause
URL:            https://github.com/rcrowley/go-metrics
Source0:        https://github.com/rcrowley/go-metrics/archive/%{commit_id}.tar.gz#/%{_name}-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    golangmodules

BuildRequires:  go
BuildRequires:  go(github.com/stathat/go)
BuildSystem:    golangmodules

%description
Go port of Coda Hale's Metrics library.

%files
%license LICENSE
"""
    path = _write(tmp_path, 'rcrowley.spec', content)
    errors = _check_spec_buildsystem(path)
    assert any('declares the field 2 times' in err for err in errors), errors


def test_corpus_regression_misspelling(tmp_path: Path) -> None:
    content = """\
Name:           grep
Version:        3.11
Release:        %autorelease
Summary:        Pattern matching utilities
License:        GPL-3.0-or-later
URL:            https://www.gnu.org/software/grep/
Source0:        https://ftp.gnu.org/gnu/grep/grep-%{version}.tar.xz
BuildArch:      noarch
Buildsystem:    autotools

BuildRequires:  pcre2-devel

%description
Pattern matching utilities.
"""
    path = _write(tmp_path, 'grep.spec', content)
    errors = _check_spec_buildsystem(path)
    assert len(errors) == 1, errors
    assert 'is spelled "Buildsystem"' in errors[0]


def test_corpus_regression_mkosi(tmp_path: Path) -> None:
    content = """\
Name:           mkosi
Version:        25
Release:        %autorelease
Summary:        Build bespoke OS images
License:        LGPL-2.1-or-later
URL:            https://github.com/systemd/mkosi
Source0:        https://github.com/systemd/mkosi/archive/v%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildSystem:    pyproject

%description
Build bespoke OS images.
"""
    path = _write(tmp_path, 'mkosi.spec', content)
    errors = _check_spec_buildsystem(path)
    assert len(errors) == 1, errors
    assert 'must be written before BuildRequires (line 10)' in errors[0]
