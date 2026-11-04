# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_release import _check_spec_release
from openruyi_precommit_hooks.check_spec_release import main

VALID_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

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


def _spec(release: str) -> str:
    return f'Name:           foo\nVersion:        1.0\nRelease:        {release}\n'


def _findings(tmp_path: Path, release: str) -> list[str]:
    path = _write(tmp_path, 'x.spec', _spec(release))
    return [err.split('x.spec: ', 1)[-1] for err in _check_spec_release(path)]


# --- baseline ---------------------------------------------------------------


def test_valid_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_release(_write(tmp_path, 'ok.spec', VALID_SPEC)) == []


def test_brace_autorelease_passes(tmp_path: Path) -> None:
    path = _write(tmp_path, 'ok.spec', _spec('%{autorelease}'))
    assert _check_spec_release(path) == []


def test_compound_macro_expression_passes(tmp_path: Path) -> None:
    # Used by the linux and linux-lts packages.
    path = _write(
        tmp_path,
        'ok.spec',
        _spec('%{patchset_release}.%{config_version}_%autorelease'),
    )
    assert _check_spec_release(path) == []


def test_main_returns_zero_on_clean_file(tmp_path: Path) -> None:
    path = _write(tmp_path, 'ok.spec', VALID_SPEC)
    assert main([path]) == 0


def test_main_returns_one_on_violation(tmp_path: Path) -> None:
    path = _write(tmp_path, 'bad.spec', _spec('3'))
    assert main([path]) == 1


def test_main_returns_zero_without_filenames() -> None:
    assert main([]) == 0


# --- R1: presence -----------------------------------------------------------


def test_missing_release_is_reported(tmp_path: Path) -> None:
    content = 'Name:           foo\nVersion:        1.0\nSummary:        Example package\n'
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_release(path)
    assert 'Release field is missing' in errors[0], errors


def test_empty_release_is_reported(tmp_path: Path) -> None:
    assert _findings(tmp_path, '') == ['Release field is empty (line 3)']


def test_whitespace_only_release_is_reported(tmp_path: Path) -> None:
    content = 'Name:           foo\nVersion:        1.0\nRelease:        \n'
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_release(path)
    assert 'Release field is empty (line 3)' in errors[0], errors


# --- R2: %autorelease -------------------------------------------------------


@pytest.mark.parametrize(
    ('release', 'reason'),
    [
        pytest.param('3', 'literal number', id='literal-number'),
        pytest.param('1%{?dist}', 'traditional Fedora form', id='traditional-fedora'),
        pytest.param('2.1', 'decimal', id='decimal'),
    ],
)
def test_non_autorelease_is_reported(
    tmp_path: Path,
    release: str,
    reason: str,
) -> None:
    findings = _findings(tmp_path, release)
    assert len(findings) == 1, findings
    assert 'should use %autorelease' in findings[0], findings


# --- R3: hard-coded distribution suffix ------------------------------------


@pytest.mark.parametrize(
    ('release', 'suffix'),
    [
        pytest.param('3.fc38', '.fc38', id='fedora'),
        pytest.param('1.el9', '.el9', id='rhel'),
        pytest.param('2.oe1', '.oe1', id='openeuler-short'),
        pytest.param('2.oe2403', '.oe2403', id='openeuler-ordinal'),
        pytest.param('1.openEuler1', '.openEuler1', id='openeuler-long'),
        pytest.param('2.FC38', '.FC38', id='upper-case'),
    ],
)
def test_hard_coded_dist_suffix_is_reported(
    tmp_path: Path,
    release: str,
    suffix: str,
) -> None:
    findings = _findings(tmp_path, release)
    assert len(findings) >= 1, findings
    assert any(suffix in finding for finding in findings), findings
    assert any('hard-code a distribution suffix' in finding for finding in findings), findings


def test_traditional_fedora_form_has_no_dist_suffix(tmp_path: Path) -> None:
    # "%{?dist}" is a macro reference, not a hard-coded suffix: R3 must stay
    # silent even though R2 fires.
    findings = _findings(tmp_path, '1%{?dist}')
    assert len(findings) == 1, findings
    assert 'should use %autorelease' in findings[0], findings


def test_hard_coded_suffix_also_fires_r2(tmp_path: Path) -> None:
    # "3.fc38" violates both R2 (not %autorelease) and R3 (hard-coded
    # suffix); the two messages are independent and neither hides the other.
    findings = _findings(tmp_path, '3.fc38')
    assert len(findings) == 2, findings
    assert any('should use %autorelease' in f for f in findings), findings
    assert any('hard-code a distribution suffix' in f for f in findings), findings


# --- R4: %{dist} override ---------------------------------------------------


def test_global_dist_override_is_reported(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        '%global dist .fc40\n'
        'Summary:        Example package\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_release(path)
    assert len(errors) == 1, errors
    assert '%{dist} macro is overridden on line 4' in errors[0], errors


def test_define_dist_override_is_reported(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        '%define dist .el9\n'
        'Release:        %autorelease\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_release(path)
    assert len(errors) == 1, errors
    assert '%{dist} macro is overridden on line 3' in errors[0], errors


def test_indented_dist_override_is_reported(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        '  %global dist .fc40\n'
        'Release:        %autorelease\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_release(path)
    assert len(errors) == 1, errors
    assert '%{dist} macro is overridden on line 3' in errors[0], errors


# --- file-level errors ------------------------------------------------------


def test_missing_file_is_reported(tmp_path: Path) -> None:
    path = str(tmp_path / 'nope.spec')
    errors = _check_spec_release(path)
    assert len(errors) == 1, errors
    assert 'nope.spec' in errors[0], errors
    assert 'No such file' in errors[0], errors


def test_non_utf8_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'bad.spec'
    path.write_bytes(b'Release: \xff\xfe\n')
    errors = _check_spec_release(str(path))
    assert len(errors) == 1, errors
    assert 'file is not valid UTF-8' in errors[0], errors


def test_empty_file_passes(tmp_path: Path) -> None:
    path = _write(tmp_path, 'empty.spec', '')
    errors = _check_spec_release(path)
    assert len(errors) == 1, errors
    assert 'Release field is missing' in errors[0], errors
