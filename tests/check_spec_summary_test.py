# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_summary import _check_spec_summary
from openruyi_precommit_hooks.check_spec_summary import main

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


def _spec(summary: str) -> str:
    return f'Name:           foo\nVersion:        1.0\nSummary:        {summary}\n'


def _findings(tmp_path: Path, summary: str) -> list[str]:
    path = _write(tmp_path, 'x.spec', _spec(summary))
    return [err.split('x.spec: ', 1)[-1] for err in _check_spec_summary(path)]


# --- baseline ---------------------------------------------------------------


def test_valid_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_summary(_write(tmp_path, 'ok.spec', VALID_SPEC)) == []


def test_main_returns_zero_on_clean_file(tmp_path: Path) -> None:
    path = _write(tmp_path, 'ok.spec', VALID_SPEC)
    assert main([path]) == 0


def test_main_returns_one_on_violation(tmp_path: Path) -> None:
    path = _write(tmp_path, 'bad.spec', _spec('Example package.'))
    assert main([path]) == 1


def test_main_returns_zero_without_filenames() -> None:
    assert main([]) == 0


# --- S1: presence -----------------------------------------------------------


def test_missing_summary_is_reported(tmp_path: Path) -> None:
    content = 'Name:           foo\nVersion:        1.0\nRelease:        %autorelease\n'
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_summary(path)
    assert 'Summary field is missing' in errors[0], errors


def test_empty_summary_is_reported(tmp_path: Path) -> None:
    assert _findings(tmp_path, '') == ['Summary field is empty (line 3)']


def test_whitespace_only_summary_is_reported(tmp_path: Path) -> None:
    content = 'Name:           foo\nVersion:        1.0\nSummary:        \n'
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_summary(path)
    assert 'Summary field is empty (line 3)' in errors[0], errors


# --- S2: no trailing period -------------------------------------------------


@pytest.mark.parametrize(
    ('summary', 'reason'),
    [
        pytest.param('Example package.', 'single period', id='single-period'),
        pytest.param('Example package..', 'double period', id='double-period'),
        pytest.param('Example package. ', 'period before trailing space', id='period-before-space'),
        pytest.param('Example package. \t', 'period before tab', id='period-before-tab'),
    ],
)
def test_trailing_period_is_reported(
    tmp_path: Path,
    summary: str,
    reason: str,
) -> None:
    findings = _findings(tmp_path, summary)
    assert len(findings) == 1, findings
    assert 'must not end with a period' in findings[0], findings


def test_internal_period_passes(tmp_path: Path) -> None:
    # "e.g." is a legitimate abbreviation inside the value; only a trailing
    # period is forbidden.
    assert _findings(tmp_path, 'e.g. an example package') == []


# --- S3: English only -------------------------------------------------------


@pytest.mark.parametrize(
    ('summary', 'reason'),
    [
        pytest.param('\u793a\u4f8b\u8f6f\u4ef6\u5305', 'simplified chinese', id='chinese'),
        pytest.param('Example パッケージ', 'japanese kana', id='japanese'),
        pytest.param('Пример пакета', 'cyrillic', id='cyrillic'),
        pytest.param('Exemple de démo', 'accented latin', id='accented-latin'),
    ],
)
def test_non_ascii_summary_is_reported(
    tmp_path: Path,
    summary: str,
    reason: str,
) -> None:
    findings = _findings(tmp_path, summary)
    assert len(findings) == 1, findings
    assert 'contains non-ASCII characters' in findings[0], findings


def test_ascii_punctuation_passes(tmp_path: Path) -> None:
    # Punctuation and symbols are part of ASCII; S3 only rejects characters
    # above U+007F.
    assert _findings(tmp_path, 'C/C++ bindings for libfoo (beta!)') == []


# --- S4: brief description (heuristic) -------------------------------------


def test_long_summary_is_reported(tmp_path: Path) -> None:
    long_summary = 'A very long description ' + ('word ' * 80)
    findings = _findings(tmp_path, long_summary)
    assert len(findings) == 1, findings
    assert 'characters; keep it under 300 (heuristic)' in findings[0], findings


def test_brief_summary_passes(tmp_path: Path) -> None:
    assert _findings(tmp_path, 'An example package for demonstration purposes') == []


# --- macro escape -----------------------------------------------------------


def test_macro_valued_summary_skips_content_checks(tmp_path: Path) -> None:
    # S2-S4 are statically undecidable for a macro value; only S1 applies.
    assert _findings(tmp_path, '%{summary}') == []


def test_conditional_macro_valued_summary_skips_content_checks(tmp_path: Path) -> None:
    assert _findings(tmp_path, '%{?summary}') == []


# --- subpackage Summary -----------------------------------------------------


def test_subpackage_summary_is_checked(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Summary:        Example package\n'
        '%package -n foo-devel\n'
        'Summary:        \u5f00\u53d1\u5de5\u5177\u5305.\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = [err.split('x.spec: ', 1)[-1] for err in _check_spec_summary(path)]
    assert len(errors) == 2, errors
    assert any('contains non-ASCII characters' in e for e in errors), errors
    assert any('must not end with a period' in e for e in errors), errors


def test_multiple_summaries_are_all_checked(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Summary:        Example package\n'
        '%package -n foo-libs\n'
        'Summary:        Runtime libraries.\n'
        '%package -n foo-devel\n'
        'Summary:        Development files\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = [err.split('x.spec: ', 1)[-1] for err in _check_spec_summary(path)]
    assert len(errors) == 1, errors
    assert 'must not end with a period' in errors[0], errors


def test_comment_summary_line_is_ignored(tmp_path: Path) -> None:
    # A commented-out "# Summary: ..." line must not count as the field.
    content = (
        '# Summary: commented out\n'
        'Name:           foo\n'
        'Version:        1.0\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_summary(path)
    assert 'Summary field is missing' in errors[0], errors


def test_summary_value_with_trailing_space_is_checked(tmp_path: Path) -> None:
    # Trailing whitespace is stripped before S2, so "foo. " is reported as
    # ending with a period.
    content = 'Name:           foo\nVersion:        1.0\nSummary:        Example package. \n'
    path = _write(tmp_path, 'x.spec', content)
    errors = [err.split('x.spec: ', 1)[-1] for err in _check_spec_summary(path)]
    assert len(errors) == 1, errors
    assert 'must not end with a period' in errors[0], errors


# --- file-level errors ------------------------------------------------------


def test_missing_file_is_reported(tmp_path: Path) -> None:
    path = str(tmp_path / 'nope.spec')
    errors = _check_spec_summary(path)
    assert len(errors) == 1, errors
    assert 'nope.spec' in errors[0], errors
    assert 'No such file' in errors[0], errors


def test_non_utf8_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'bad.spec'
    path.write_bytes(b'Summary: \xff\xfe\n')
    errors = _check_spec_summary(str(path))
    assert len(errors) == 1, errors
    assert 'file is not valid UTF-8' in errors[0], errors


def test_empty_file_reports_missing_summary(tmp_path: Path) -> None:
    path = _write(tmp_path, 'empty.spec', '')
    errors = _check_spec_summary(path)
    assert len(errors) == 1, errors
    assert 'Summary field is missing' in errors[0], errors
