# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_url import _check_spec_url
from openruyi_precommit_hooks.check_spec_url import _check_spec_url_ext
from openruyi_precommit_hooks.check_spec_url import main

VALID_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding='utf-8', newline='\n')
    return str(path)


def _spec(field: str) -> str:
    return (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        f'{field}\n'
        '\n'
        '%description\n'
        'An example package.\n'
    )


def _findings(tmp_path: Path, field: str) -> list[str]:
    path = _write(tmp_path, 'x.spec', _spec(field))
    return [err.split('x.spec: ', 1)[-1] for err in _check_spec_url(path)]


# --- baseline ---------------------------------------------------------------


def test_valid_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_url(_write(tmp_path, 'ok.spec', VALID_SPEC)) == []


def test_main_returns_zero_on_clean_file(tmp_path: Path) -> None:
    path = _write(tmp_path, 'ok.spec', VALID_SPEC)
    assert main([path]) == 0


def test_main_returns_one_on_violation(tmp_path: Path) -> None:
    path = _write(tmp_path, 'bad.spec', _spec('Url:            https://example.org/foo'))
    assert main([path]) == 1


def test_main_returns_zero_without_filenames() -> None:
    assert main([]) == 0


# --- U1: presence -----------------------------------------------------------


def test_missing_url_is_reported(tmp_path: Path) -> None:
    errors = _findings(tmp_path, 'Summary:        Example package')
    assert any('URL field is missing' in err for err in errors), errors


def test_placeholder_satisfies_presence(tmp_path: Path) -> None:
    assert _findings(tmp_path, '# URL: No URL link available') == []


def test_placeholder_with_wrong_case_satisfies_presence(
    tmp_path: Path,
) -> None:
    assert _findings(tmp_path, '# url: No URL link available') == []


def test_url_in_subpackage_only_does_not_satisfy_presence(
    tmp_path: Path,
) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'Summary:        Example package\n'
        '\n'
        '%package devel\n'
        'URL:            https://example.org/foo\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_url(path)
    assert any('URL field is missing' in err for err in errors), errors


def test_url_after_a_macro_invocation_counts(tmp_path: Path) -> None:
    content = (
        '%global debug_package %{nil}\n'
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'Summary:        Example package\n'
        'URL:            https://example.org/foo\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    assert _check_spec_url(path) == []


# --- U2: non-empty value ----------------------------------------------------


def test_empty_url_is_reported(tmp_path: Path) -> None:
    assert _findings(tmp_path, 'URL:') == ['URL field (line 4) is empty']


# --- U3: absolute URL form --------------------------------------------------


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('FIXME', id='placeholder-word'),
        pytest.param('example.org/foo', id='no-scheme'),
        pytest.param('/usr/share/doc/foo', id='path'),
        pytest.param('https://localhost/foo', id='host-without-dot'),
        pytest.param('https://', id='scheme-only'),
        pytest.param('ftp:/example.org', id='single-slash'),
    ],
)
def test_non_absolute_url_is_reported(tmp_path: Path, value: str) -> None:
    errors = _findings(tmp_path, f'URL:            {value}')
    assert len(errors) == 1, errors
    assert 'is not an absolute URL' in errors[0], errors


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('https://example.org/foo', id='https'),
        pytest.param('http://example.org', id='http'),
        pytest.param('https://example.org', id='bare-host'),
        pytest.param('https://example.org/foo?a=1#b', id='query-fragment'),
        pytest.param('ftp://ftp.example.org/pub', id='ftp'),
        pytest.param('git+https://example.org/foo', id='plus-scheme'),
        pytest.param('https://sub.example.org', id='subdomain'),
    ],
)
def test_absolute_url_passes(tmp_path: Path, value: str) -> None:
    assert _findings(tmp_path, f'URL:            {value}') == []


# --- U4: no macro concatenation ---------------------------------------------


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('https://github.com/owner/%{name}', id='brace-ref'),
        pytest.param('https://pypi.org/project/%{srcname}/', id='global-ref'),
        pytest.param('https://github.com/o/%{upstream_name}', id='long-ref'),
        pytest.param('%{url}', id='bare-ref'),
        pytest.param('https://example.org/%foo', id='unbraced-ref'),
    ],
)
def test_macro_url_is_reported(tmp_path: Path, value: str) -> None:
    errors = _findings(tmp_path, f'URL:            {value}')
    assert len(errors) == 1, errors
    assert 'is built from a macro' in errors[0], errors


def test_macro_url_skips_the_absolute_check(tmp_path: Path) -> None:
    """U4 inverts the usual macro escape hatch: the macro is the defect."""
    errors = _findings(tmp_path, 'URL:            %{url}')
    assert len(errors) == 1, errors
    assert 'is not an absolute URL' not in errors[0], errors


def test_percent_escape_is_not_a_macro(tmp_path: Path) -> None:
    """URL encoding such as %2B must not be mistaken for a macro."""
    value = 'https://metacpan.org/release/Text-Tabs%2BWrap'
    assert _findings(tmp_path, f'URL:            {value}') == []


def test_percent_escape_with_a_real_macro_is_still_reported(
    tmp_path: Path,
) -> None:
    value = 'https://example.org/%2B/%{name}'
    errors = _findings(tmp_path, f'URL:            {value}')
    assert len(errors) == 1, errors
    assert 'is built from a macro' in errors[0], errors


# --- U5: placeholder wording ------------------------------------------------


@pytest.mark.parametrize(
    'text',
    [
        pytest.param('No URL link available.', id='trailing-period'),
        pytest.param('no url link available', id='lowercase'),
        pytest.param('No URL', id='short'),
        pytest.param('', id='empty'),
    ],
)
def test_wrong_placeholder_text_is_reported(
    tmp_path: Path,
    text: str,
) -> None:
    errors = _findings(tmp_path, f'# URL: {text}')
    assert len(errors) == 1, errors
    assert 'must read exactly' in errors[0], errors


def test_documented_placeholder_text_passes(tmp_path: Path) -> None:
    assert _findings(tmp_path, '# URL: No URL link available') == []


# --- U6: mutual exclusion ---------------------------------------------------


def test_field_and_placeholder_together_are_reported(
    tmp_path: Path,
) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'URL:            https://example.org/foo\n'
        '# URL: No URL link available\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_url(path)
    assert len(errors) == 1, errors
    assert 'must not both be present' in errors[0], errors


# --- U7: field name spelling ------------------------------------------------


@pytest.mark.parametrize(
    'name',
    [
        pytest.param('Url', id='title-case'),
        pytest.param('url', id='lower-case'),
        pytest.param('UrL', id='mixed-case'),
    ],
)
def test_misspelled_field_is_reported(tmp_path: Path, name: str) -> None:
    errors = _findings(tmp_path, f'{name}:            https://example.org/foo')
    assert len(errors) == 1, errors
    assert f'is spelled "{name}"' in errors[0], errors


def test_misspelled_field_still_validates_its_value(tmp_path: Path) -> None:
    """U7 must not steal the defect from U2-U4."""
    errors = _findings(tmp_path, 'Url:            FIXME')
    assert len(errors) == 2, errors
    assert any('is spelled "Url"' in err for err in errors), errors
    assert any('is not an absolute URL' in err for err in errors), errors


def test_misspelled_field_satisfies_presence(tmp_path: Path) -> None:
    """A wrong name does not also make the field missing."""
    errors = _findings(tmp_path, 'Url:            https://example.org/foo')
    assert len(errors) == 1, errors
    assert 'URL field is missing' not in errors[0], errors


def test_field_case_flag_turns_u7_off(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'x.spec',
        _spec('Url:            https://example.org/foo'),
    )
    assert _check_spec_url_ext(path, check_field_case=False) == []


def test_field_case_flag_keeps_the_other_checkpoints(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', _spec('Url:            FIXME'))
    errors = _check_spec_url_ext(path, check_field_case=False)
    assert len(errors) == 1, errors
    assert 'is not an absolute URL' in errors[0], errors


def test_main_accepts_the_field_case_flag(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'x.spec',
        _spec('Url:            https://example.org/foo'),
    )
    assert main(['--no-check-field-case', path]) == 0


# --- scope boundaries -------------------------------------------------------


def test_uppercase_field_passes(tmp_path: Path) -> None:
    assert _findings(tmp_path, 'URL:            https://example.org/foo') == []


def test_padding_after_the_colon_is_ignored(tmp_path: Path) -> None:
    assert _findings(tmp_path, 'URL:https://example.org/foo') == []


def test_commented_out_field_is_not_a_placeholder(tmp_path: Path) -> None:
    """A disabled field leaves the spec without a URL, so U1 fires.

    It is not the documented placeholder, so it must not be reported as
    wrong placeholder wording.
    """
    errors = _findings(tmp_path, '# URL:            https://example.org/foo')
    assert len(errors) == 1, errors
    assert 'URL field is missing' in errors[0], errors


def test_commented_out_url_does_not_conflict_with_the_field(
    tmp_path: Path,
) -> None:
    """A commented-out URL is a disabled field, not a placeholder."""
    content = (
        'Name:           foo\n'
        'URL:            https://example.org/foo\n'
        '# URL:            https://old.example.org/foo\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    assert _check_spec_url(path) == []


def test_subpackage_url_lines_are_checked(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'URL:            https://example.org/foo\n'
        '\n'
        '%package devel\n'
        'URL:            FIXME\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_url(path)
    assert len(errors) == 1, errors
    assert 'line 5' in errors[0], errors


def test_url_before_license_is_not_reported(tmp_path: Path) -> None:
    """Field ordering belongs to check-spec-basic-fields."""
    content = (
        'Name:           foo\n'
        'URL:            https://example.org/foo\n'
        'License:        MulanPSL-2.0\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    assert _check_spec_url(path) == []


def test_repeated_identical_findings_are_deduplicated(
    tmp_path: Path,
) -> None:
    content = (
        'Name:           foo\n'
        'URL:            FIXME\n'
        '%package devel\n'
        'URL:            FIXME\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_url(path)
    assert len(errors) == 2, errors


# --- infrastructure ---------------------------------------------------------


def test_missing_file_is_reported(tmp_path: Path) -> None:
    path = str(tmp_path / 'absent.spec')
    errors = _check_spec_url(path)
    assert len(errors) == 1, errors
    assert errors[0].startswith(path + ': '), errors


def test_non_utf8_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'latin.spec'
    path.write_bytes(b'Name: foo\nURL: http://ex.org/\xe9\n')
    errors = _check_spec_url(str(path))
    assert errors == [f'{path}: file is not valid UTF-8']


def test_empty_file_reports_the_missing_field(tmp_path: Path) -> None:
    path = _write(tmp_path, 'empty.spec', '')
    errors = _check_spec_url(path)
    assert len(errors) == 1, errors
    assert 'URL field is missing' in errors[0], errors
