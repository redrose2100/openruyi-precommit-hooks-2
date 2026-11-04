# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_version import _check_spec_version
from openruyi_precommit_hooks.check_spec_version import main

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


def _spec(version: str) -> str:
    return f'Name:           foo\nVersion:        {version}\n'


def _findings(tmp_path: Path, version: str) -> list[str]:
    path = _write(tmp_path, 'x.spec', _spec(version))
    return [err.split('x.spec: ', 1)[-1] for err in _check_spec_version(path)]


# --- baseline ---------------------------------------------------------------


def test_valid_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_version(_write(tmp_path, 'ok.spec', VALID_SPEC)) == []


def test_plain_semver_passes(tmp_path: Path) -> None:
    for version in ('1.0', '1.5.7', '2025.07', '1.0.0'):
        assert _findings(tmp_path, version) == [], version


def test_main_returns_zero_on_clean_file(tmp_path: Path) -> None:
    path = _write(tmp_path, 'ok.spec', VALID_SPEC)
    assert main([path]) == 0


def test_main_returns_one_on_violation(tmp_path: Path) -> None:
    path = _write(tmp_path, 'bad.spec', _spec('1.0-rc1'))
    assert main([path]) == 1


# --- V1: presence -----------------------------------------------------------


def test_missing_version_is_reported(tmp_path: Path) -> None:
    content = 'Name:           foo\nSummary:        Example package\n'
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_version(path)
    assert 'Version field is missing' in errors[0], errors


def test_empty_version_is_reported(tmp_path: Path) -> None:
    assert _findings(tmp_path, '') == ['Version field is empty (line 2)']


def test_whitespace_only_version_is_reported(tmp_path: Path) -> None:
    content = 'Name:           foo\nVersion:        \n'
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_version(path)
    assert 'Version field is empty (line 2)' in errors[0], errors


# --- V2: hyphen -------------------------------------------------------------


def test_hyphen_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, '7.1.1-44')
    assert len(findings) == 1, findings
    assert 'must not contain "-"' in findings[0], findings


# --- V3: underscore ---------------------------------------------------------


def test_underscore_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, '17_6')
    assert len(findings) == 1, findings
    assert 'must not contain "_"' in findings[0], findings


# --- V4: prerelease markers -------------------------------------------------


def test_prerelease_without_tilde_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, '3.5.0-rc1')
    assert any('must be preceded by "~"' in f for f in findings), findings


def test_prerelease_directly_after_digit_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, '1.0rc1')
    assert any('must be preceded by "~"' in f for f in findings), findings


def test_uppercase_prerelease_marker_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, '3.5.0~RC1')
    assert any('must be lowercase' in f for f in findings), findings


def test_tilde_lowercase_prerelease_passes(tmp_path: Path) -> None:
    for version in ('3.5.0~rc1', '1.0~beta1', '2.0~alpha', '1.0~rc'):
        assert _findings(tmp_path, version) == [], version


def test_marker_inside_a_word_is_not_reported(tmp_path: Path) -> None:
    # "alpha" inside "alphabet" must not be treated as a marker.
    findings = _findings(tmp_path, '1.0alphabet')
    assert not any('prerelease' in f for f in findings), findings


# --- V5: snapshot form ------------------------------------------------------


def test_snapshot_form_passes(tmp_path: Path) -> None:
    for version in (
        '0+git20250808.ee5b7e3',
        '1.2.3+svn20250101.1234567',
        '2.0+snap20250606.abcd1234',
        '0+git20250808.abcdef123',
        '2.44+git20260918.1f5026241027',
        '0+git20250808.' + 'e' * 40,
    ):
        assert _findings(tmp_path, version) == [], version


def test_snapshot_without_revision_dot_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, '0+git20250808ee5b7e3')
    assert any('snapshot' in f for f in findings), findings


def test_snapshot_with_overlong_revision_is_reported(tmp_path: Path) -> None:
    # Longer than any real hash: the revision is "usually" 7-10 characters
    # and never more than a full 40-character SHA-1.
    findings = _findings(tmp_path, '0+git20250808.' + 'e' * 41)
    assert any('snapshot' in f for f in findings), findings


def test_snapshot_with_bad_date_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, '0+git2025088.ee5b7e3')
    assert any('snapshot' in f for f in findings), findings


def test_plain_plus_suffix_is_reported(tmp_path: Path) -> None:
    # An upstream "+build5" suffix is not the documented snapshot form.
    findings = _findings(tmp_path, '1.2.3+build5')
    assert any('snapshot' in f for f in findings), findings


# --- V6: character set ------------------------------------------------------


def test_invalid_char_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, '1.0@beta')
    assert any('invalid character "@"' in f for f in findings), findings


def test_whitespace_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, '1.0 rc1')
    assert any('invalid character' in f for f in findings), findings


# --- macro-valued versions --------------------------------------------------


def test_macro_valued_version_skips_value_checks(tmp_path: Path) -> None:
    for version in ('%{version}', '%{upstream_version}', '1.0-%{suffix}'):
        assert _findings(tmp_path, version) == [], version


# --- combined violations ----------------------------------------------------


def test_multiple_violations_are_all_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, '1.0-rc1_beta')
    assert any('must not contain "-"' in f for f in findings), findings
    assert any('must not contain "_"' in f for f in findings), findings
    assert any('prerelease' in f for f in findings), findings
