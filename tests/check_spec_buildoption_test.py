# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_buildoption import (
    _check_spec_buildoption,
)
from openruyi_precommit_hooks.check_spec_buildoption import (
    _check_spec_buildoption_ext,
)
from openruyi_precommit_hooks.check_spec_buildoption import main

# A spec that satisfies every checkpoint: BuildSystem, then BuildOption,
# then BuildRequires, with the documented four stage run.
CLEAN_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools

BuildOption(conf):  --enable-foo
BuildOption(conf):  --disable-bar
BuildOption(build):  %{?_smp_mflags}
BuildOption(install):  DESTDIR=%{buildroot}
BuildOption(check):  --verbose

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A spec that never writes the field. The field is optional, so the rule is
# silent and never asks for a declaration.
NO_BUILDOPTION_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools

BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A subpackage writes its own BuildOption block, so a stage run that restarts
# inside the subpackage is not a defect.
SUBPACKAGE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools

BuildOption(conf):  --enable-foo

BuildRequires:  gcc

%description
An example package.

%package devel
Summary:        Development files
BuildSystem:    cmake

BuildOption(conf):  -DFOO=ON

BuildRequires:  cmake

%description devel
Development files.

%files
%license LICENSE

%changelog
%autochangelog
"""


def _write(tmp_path: Path, content: str) -> str:
    spec = tmp_path / 'foo.spec'
    spec.write_text(content, encoding='utf-8')
    return str(spec)


def test_clean_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_buildoption(_write(tmp_path, CLEAN_SPEC)) == []


def test_spec_without_buildoption_passes(tmp_path: Path) -> None:
    assert _check_spec_buildoption(_write(tmp_path, NO_BUILDOPTION_SPEC)) == []


def test_subpackage_restarts_the_stage_run(tmp_path: Path) -> None:
    assert _check_spec_buildoption(_write(tmp_path, SUBPACKAGE_SPEC)) == []


def test_missing_utf8_is_reported(tmp_path: Path) -> None:
    spec = tmp_path / 'bad.spec'
    spec.write_bytes(b'Name: foo\nBuildOption(conf):  --x\xff\n')
    errors = _check_spec_buildoption(str(spec))
    assert len(errors) == 1
    assert 'not valid UTF-8' in errors[0]


def test_missing_file_is_reported(tmp_path: Path) -> None:
    errors = _check_spec_buildoption(str(tmp_path / 'absent.spec'))
    assert len(errors) == 1
    assert 'absent.spec' in errors[0]


# -- B1 spelling ------------------------------------------------------------

@pytest.mark.parametrize(
    'line',
    [
        'Buildoption(conf):  --enable-foo',
        'BuildOPTION(conf):  --enable-foo',
        'BuildOptions(conf):  --enable-foo',
        'BuildOptionx(conf):  --enable-foo',
    ],
)
def test_b1_misspelled_field_is_reported(tmp_path: Path, line: str) -> None:
    content = CLEAN_SPEC.replace('BuildOption(conf):  --enable-foo', line)
    errors = _check_spec_buildoption(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'is spelled' in errors[0]
    assert 'write "BuildOption"' in errors[0]


def test_b1_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        'Buildoption(conf):  --enable-foo',
    )
    path = _write(tmp_path, content)
    assert _check_spec_buildoption_ext(path, check_field_case=False) == []


# -- B2 stage present -------------------------------------------------------

def test_b2_missing_stage_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        'BuildOption:  --enable-foo',
    )
    errors = _check_spec_buildoption(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'omits the stage' in errors[0]


def test_b2_empty_stage_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        'BuildOption():  --enable-foo',
    )
    errors = _check_spec_buildoption(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'has an empty stage' in errors[0]


def test_b2_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        'BuildOption:  --enable-foo',
    )
    path = _write(tmp_path, content)
    assert _check_spec_buildoption_ext(path, check_stage=False) == []


# -- B3 stage shape ---------------------------------------------------------

@pytest.mark.parametrize(
    'stage',
    ['Conf', 'CONF', 'conf build', 'conf-build', '%{stage}', '1conf'],
)
def test_b3_odd_stage_is_reported(tmp_path: Path, stage: str) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        f'BuildOption({stage}):  --enable-foo',
    )
    errors = _check_spec_buildoption(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'is not a single' in errors[0]


def test_b3_undocumented_stage_is_accepted(tmp_path: Path) -> None:
    # RPM ships stages the guidelines do not list, so the shape check must
    # not turn into a closed whitelist.
    content = CLEAN_SPEC.replace(
        'BuildOption(check):  --verbose',
        'BuildOption(generate_buildrequires):  -N',
    )
    assert _check_spec_buildoption(_write(tmp_path, content)) == []


# -- B4 and B5 spacing and argument -----------------------------------------

@pytest.mark.parametrize('gap', [' ', '   ', '    ', '\t', '\t\t'])
def test_b4_wrong_separator_is_reported(tmp_path: Path, gap: str) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        f'BuildOption(conf):{gap}--enable-foo',
    )
    errors = _check_spec_buildoption(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'instead of two spaces' in errors[0]


def test_b4_preserves_every_argument_of_a_line(tmp_path: Path) -> None:
    # One argument may legitimately be a flag plus its value, an assignment
    # or a command substitution, so a multi token line is not a finding.
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo\n'
        'BuildOption(conf):  --disable-bar',
        'BuildOption(conf):  -G Ninja\n'
        'BuildOption(conf):  CFLAGS="%{optflags} -fno-strict-aliasing"\n'
        'BuildOption(conf):  --with-gssapi=$(krb5-config --prefix)',
    )
    assert _check_spec_buildoption(_write(tmp_path, content)) == []


def test_b4_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        'BuildOption(conf): --enable-foo',
    )
    path = _write(tmp_path, content)
    assert _check_spec_buildoption_ext(path, check_spacing=False) == []


@pytest.mark.parametrize(
    'tail',
    ['', '  ', '    ', '\t'],
)
def test_b5_empty_argument_is_reported(tmp_path: Path, tail: str) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        f'BuildOption(conf):{tail}',
    )
    errors = _check_spec_buildoption(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'declares no argument' in errors[0]


# -- B6 position ------------------------------------------------------------

def test_b6_before_buildsystem_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildSystem:    autotools\n\nBuildOption(conf):  --enable-foo',
        'BuildOption(conf):  --enable-foo\nBuildSystem:    autotools',
    )
    errors = _check_spec_buildoption(_write(tmp_path, content))
    assert any('must be written after BuildSystem' in err for err in errors)


def test_b6_after_buildrequires_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(check):  --verbose\n\nBuildRequires:  gcc',
        'BuildRequires:  gcc\n\nBuildOption(check):  --verbose',
    )
    errors = _check_spec_buildoption(_write(tmp_path, content))
    assert any('must be written before BuildRequires' in err for err in errors)


def test_b6_inside_a_section_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%files\n%license LICENSE',
        '%files\n%license LICENSE\nBuildOption(install):  --x',
    )
    errors = _check_spec_buildoption(_write(tmp_path, content))
    assert any('outside the header field block' in err for err in errors)


def test_b6_repeated_buildrequires_closes_on_the_first(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  gcc',
        'BuildRequires:  gcc\nBuildRequires:  make',
    )
    content = content.replace(
        'BuildOption(check):  --verbose',
        'BuildOption(check):  --verbose',
    )
    assert _check_spec_buildoption(_write(tmp_path, content)) == []


def test_b6_silent_when_buildrequires_is_absent(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  gcc\n', '')
    assert _check_spec_buildoption(_write(tmp_path, content)) == []


def test_b6_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(check):  --verbose\n\nBuildRequires:  gcc',
        'BuildRequires:  gcc\n\nBuildOption(check):  --verbose',
    )
    path = _write(tmp_path, content)
    assert _check_spec_buildoption_ext(path, check_position=False) == []


# -- B7 stage order ---------------------------------------------------------

def test_b7_reversed_stages_are_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo\n'
        'BuildOption(conf):  --disable-bar\n'
        'BuildOption(build):  %{?_smp_mflags}\n'
        'BuildOption(install):  DESTDIR=%{buildroot}\n'
        'BuildOption(check):  --verbose',
        'BuildOption(check):  --verbose\n'
        'BuildOption(install):  DESTDIR=%{buildroot}\n'
        'BuildOption(build):  %{?_smp_mflags}\n'
        'BuildOption(conf):  --disable-bar',
    )
    errors = _check_spec_buildoption(_write(tmp_path, content))
    assert len(errors) == 3
    assert all('write the stages in the order' in err for err in errors)


def test_b7_prep_precedes_conf(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        'BuildOption(prep):  -p0\nBuildOption(conf):  --enable-foo',
    )
    assert _check_spec_buildoption(_write(tmp_path, content)) == []


def test_b7_conf_after_prep_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        'BuildOption(conf):  --enable-foo\nBuildOption(prep):  -p0',
    )
    errors = _check_spec_buildoption(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'BuildOption(prep)' in errors[0]


def test_b7_unnamed_stage_does_not_break_the_run(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(install):  DESTDIR=%{buildroot}',
        'BuildOption(generate_buildrequires):  -N\n'
        'BuildOption(install):  DESTDIR=%{buildroot}',
    )
    assert _check_spec_buildoption(_write(tmp_path, content)) == []


def test_b7_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        'BuildOption(check):  --verbose\nBuildOption(conf):  --enable-foo',
    )
    path = _write(tmp_path, content)
    assert _check_spec_buildoption_ext(path, check_order=False) == []


# -- CLI --------------------------------------------------------------------

def test_main_returns_zero_for_a_clean_spec(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([_write(tmp_path, CLEAN_SPEC)]) == 0
    assert capsys.readouterr().out == ''


def test_main_returns_one_and_prints_findings(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(conf):  --enable-foo',
        'BuildOption(conf): --enable-foo',
    )
    path = _write(tmp_path, content)
    assert main([path]) == 1
    out = capsys.readouterr().out
    assert path in out
    assert 'instead of two spaces' in out


def test_main_accepts_no_filenames() -> None:
    assert main([]) == 0
