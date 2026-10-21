# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_basic_fields import _check_spec_basic_fields
from openruyi_precommit_hooks.check_spec_basic_fields import main

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


def test_valid_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_basic_fields(_write(tmp_path, 'ok.spec', VALID_SPEC)) == []


# --- checkpoint 1: required fields ------------------------------------------


@pytest.mark.parametrize(
    'missing',
    ['Name', 'Version', 'Release', 'Summary', 'License'],
)
def test_missing_required_field_is_reported(
    tmp_path: Path, missing: str,
) -> None:
    content = ''.join(
        f'{name}:           value\n'
        for name in ('Name', 'Version', 'Release', 'Summary', 'License')
        if name != missing
    )
    content += (
        '\n%description\nAn example package.\n'
        '\n%files\n%license LICENSE\n'
        '\n%changelog\n%autochangelog\n'
    )
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    expected = f'missing required field "{missing}"'
    assert sum(expected in err for err in errors) == 1, errors


def test_all_required_fields_present_reports_none(tmp_path: Path) -> None:
    errors = _check_spec_basic_fields(_write(tmp_path, 'ok.spec', VALID_SPEC))
    assert not any('missing required field' in err for err in errors)


# --- checkpoint 2: required sections ----------------------------------------


@pytest.mark.parametrize(
    'missing',
    ['%description', '%files', '%changelog'],
)
def test_missing_required_section_is_reported(
    tmp_path: Path, missing: str,
) -> None:
    parts = {
        '%description': '\n%description\nAn example package.\n',
        '%files': '\n%files\n%license LICENSE\n',
        '%changelog': '\n%changelog\n%autochangelog\n',
    }
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'Summary:        Example package\n'
        'License:        MulanPSL-2.0\n'
    )
    for name, text in parts.items():
        if name != missing:
            content += text
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    expected = f'missing required section "{missing}"'
    assert sum(expected in err for err in errors) == 1, errors


def test_missing_multiple_sections_are_all_reported(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'Summary:        Example package\n'
        'License:        MulanPSL-2.0\n'
        '\n'
        '%description\n'
        'An example package.\n'
    )
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    assert any('missing required section "%files"' in err for err in errors), errors
    assert any('missing required section "%changelog"' in err for err in errors), errors


# --- checkpoint 3: section order --------------------------------------------


@pytest.mark.parametrize(
    ('content', 'expected'),
    [
        pytest.param(
            """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%files
%license LICENSE

%description
An example package.

%changelog
%autochangelog
""",
            'must appear before "%files"',
            id='description-after-files',
        ),
        pytest.param(
            """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%changelog
%autochangelog

%files
%license LICENSE
""",
            'must appear before "%changelog"',
            id='files-after-changelog',
        ),
    ],
)
def test_section_order(tmp_path: Path, content: str, expected: str) -> None:
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    assert any(expected in err for err in errors), errors


# --- checkpoint 4: blank line between sections ------------------------------


@pytest.mark.parametrize(
    'content',
    [
        pytest.param(
            """\
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
""",
            id='files-then-changelog-adjacent',
        ),
        pytest.param(
            """\
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
""",
            id='description-then-files-adjacent',
        ),
        pytest.param(
            """\
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
%pre
echo hi
""",
            id='changelog-then-scriptlet-adjacent',
        ),
    ],
)
def test_missing_blank_line_between_sections(
    tmp_path: Path, content: str,
) -> None:
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    assert any('must be separated' in err for err in errors), errors


def test_sections_separated_by_blank_line_passes(tmp_path: Path) -> None:
    assert _check_spec_basic_fields(_write(tmp_path, 'ok.spec', VALID_SPEC)) == []


def test_same_name_adjacent_sections_are_allowed(tmp_path: Path) -> None:
    # Two %files blocks written back to back are legitimate.
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%package        devel
Summary:        Development files

%description    devel
Development files.

%files
%{_bindir}/foo
%files devel
%{_includedir}/foo.h

%changelog
%autochangelog
"""
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


def test_sections_in_mutually_exclusive_branches_need_no_blank_line(
    tmp_path: Path,
) -> None:
    # Reproduces SPECS/ceph/ceph.spec: the %package guarded by %else is a
    # mutually exclusive alternative to the %description above it, so the two
    # can never be adjacent in the expanded spec. The %else boundary is a
    # stronger separator than a blank line.
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%if %{with dashboard}
%package        dashboard
Summary:        Dashboard

%description    dashboard
desc one
%else
%package        plain
Summary:        Plain

%description    plain
desc two
%endif

%files
%license LICENSE

%changelog
%autochangelog
"""
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


def test_branch_boundary_does_not_hide_missing_blank_line(
    tmp_path: Path,
) -> None:
    # Inside a single branch the blank-line requirement still applies: both
    # sections live on the same conditional branch path.
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%if %{with docs}
%package        docs
Summary:        Docs
%description    docs
docs desc
%endif

%files
%license LICENSE

%changelog
%autochangelog
"""
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    assert any('must be separated' in err for err in errors), errors
    assert any('"%description"' in err for err in errors), errors


def test_macro_lines_are_not_treated_as_sections(tmp_path: Path) -> None:
    # %doc, %license and %autochangelog must not trigger the blank-line check.
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%files
%doc README
%license LICENSE

%changelog
%autochangelog
"""
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


def test_comment_directly_above_section_is_allowed(tmp_path: Path) -> None:
    # A comment directly above a header (with a blank line before the comment)
    # reads as part of that header.
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%install
make install

# no test suite
%check
:

%files
%license LICENSE

%changelog
%autochangelog
"""
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


def test_comment_does_not_hide_missing_blank_line(tmp_path: Path) -> None:
    # %find_lang is section body, so the comment above %check does not act
    # as a separator.
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%install
make install
%find_lang %{name}
# no test suite
%check
:

%files
%license LICENSE

%changelog
%autochangelog
"""
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    assert any('"%check"' in err for err in errors), errors


def test_conditional_directly_above_section_is_allowed(tmp_path: Path) -> None:
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%install
make install

%if %{with systemd}
%post
%systemd_post foo.service
%endif

%files
%license LICENSE

%changelog
%autochangelog
"""
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


def test_scriptlet_sections_do_not_break_parsing(tmp_path: Path) -> None:
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%install
install -d %{buildroot}

%files
%license LICENSE

%changelog
%autochangelog
"""
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


# --- checkpoint 5: changelog content ----------------------------------------


@pytest.mark.parametrize(
    'body',
    [
        pytest.param(
            '* Tue Jan 06 2026 Dev <dev@example.com> - 1.0-1\n- Initial\n',
            id='manual-changelog',
        ),
        pytest.param('', id='empty-changelog'),
    ],
)
def test_changelog_must_be_autochangelog(tmp_path: Path, body: str) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'Summary:        Example package\n'
        'License:        MulanPSL-2.0\n'
        '\n'
        '%description\n'
        'An example package.\n'
        '\n'
        '%files\n'
        '%license LICENSE\n'
        '\n'
        '%changelog\n'
        f'{body}'
    )
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    assert any('%autochangelog' in err for err in errors), errors


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('%autochangelog', id='bare'),
        pytest.param('%{?autochangelog}', id='legacy-conditional'),
    ],
)
def test_changelog_accepted_forms(tmp_path: Path, value: str) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'Summary:        Example package\n'
        'License:        MulanPSL-2.0\n'
        '\n'
        '%description\n'
        'An example package.\n'
        '\n'
        '%files\n'
        '%license LICENSE\n'
        '\n'
        '%changelog\n'
        f'{value}\n'
    )
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


# --- checkpoint 6: core field order -----------------------------------------


@pytest.mark.parametrize(
    'content',
    [
        pytest.param(
            """\
Name:           foo
Version:        1.0
Summary:        Example package
Release:        %autorelease
License:        MulanPSL-2.0

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
""",
            id='release-after-summary',
        ),
        pytest.param(
            """\
Name:           foo
Summary:        Example package
Version:        1.0
Release:        %autorelease
License:        MulanPSL-2.0

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
""",
            id='version-after-summary',
        ),
        pytest.param(
            """\
Summary:        Example package
Name:           foo
Version:        1.0
Release:        %autorelease
License:        MulanPSL-2.0

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
""",
            id='name-after-summary',
        ),
    ],
)
def test_core_field_order(tmp_path: Path, content: str) -> None:
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    assert any('must appear before' in err for err in errors), errors


def test_non_core_fields_are_not_order_checked(tmp_path: Path) -> None:
    # Requires before Provides is this repository's dominant style and is
    # deliberately not enforced by the rule.
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
Requires:       bar
Provides:       foo

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


def test_repeated_fields_do_not_trigger_order_errors(tmp_path: Path) -> None:
    # Regression: fields were once collected globally, so a second Provides:
    # appearing after Recommends: looked out of order.
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
Provides:       foo
Recommends:     bar
Provides:       foo-extra

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    assert not any('must appear before' in err for err in errors), errors


def test_subpackage_block_is_ordered_independently(tmp_path: Path) -> None:
    # A subpackage restarts the documented order and must not be compared
    # against the main block's later fields.
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
Requires:       bar

%description
An example package.

%package        devel
Version:        1.0
Name:           foo-devel

%description    devel
Development files.

%files devel
%{_includedir}/foo.h

%changelog
%autochangelog
"""
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    assert any('field block 1' in err for err in errors), errors


def test_subpackage_fields_are_collected(tmp_path: Path) -> None:
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%package        devel
Name:           foo-devel
Version:        1.0
Release:        %autorelease
Summary:        Development files
License:        MulanPSL-2.0

%description    devel
Development files.

%files devel
%{_includedir}/foo.h

%changelog
%autochangelog
"""
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


# --- checkpoint 7: Release value --------------------------------------------


@pytest.mark.parametrize(
    ('value', 'failed'),
    [
        pytest.param('%autorelease', False, id='bare'),
        pytest.param('%{autorelease}', False, id='braced'),
        pytest.param('1', True, id='hardcoded'),
        pytest.param(
            '%{patchset_release}.%{config_version}_%autorelease',
            True,
            id='composite',
        ),
    ],
)
def test_release_value(tmp_path: Path, value: str, failed: bool) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        f'Release:        {value}\n'
        'Summary:        Example package\n'
        'License:        MulanPSL-2.0\n'
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
    errors = _check_spec_basic_fields(_write(tmp_path, 'x.spec', content))
    got = any('should use "%autorelease"' in err for err in errors)
    assert got is failed, errors


# --- parsing details --------------------------------------------------------


def test_conditional_lines_are_skipped(tmp_path: Path) -> None:
    content = """\
Name:           foo
Version:        1.0
%if %{with extra}
Release:        %autorelease
%endif
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


def test_comment_lines_are_skipped(tmp_path: Path) -> None:
    content = """\
# a leading comment
Name:           foo
# a comment between fields
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
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


def test_numbered_and_parameterised_field_names(tmp_path: Path) -> None:
    content = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
Source0:        foo-1.0.tar.gz
Source1:        extra.tar.gz
Patch0:         fix.patch

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""
    assert _check_spec_basic_fields(_write(tmp_path, 'x.spec', content)) == []


def test_errors_are_prefixed_and_deduplicated(tmp_path: Path) -> None:
    content = (
        'Summary:        Example package\n'
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
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_basic_fields(path)
    assert errors, errors
    assert all(err.startswith(f'{path}: ') for err in errors), errors
    assert len(errors) == len(set(errors)), errors
    assert not any('%%' in err for err in errors), errors


# --- error handling ---------------------------------------------------------


def test_non_utf8_file(tmp_path: Path) -> None:
    path = tmp_path / 'bad.spec'
    path.write_bytes(b'Name: foo\n\xff\xfe\n')
    errors = _check_spec_basic_fields(str(path))
    assert errors == [f'{path}: file is not valid UTF-8']


def test_missing_file(tmp_path: Path) -> None:
    path = str(tmp_path / 'nope.spec')
    errors = _check_spec_basic_fields(path)
    assert len(errors) == 1
    assert errors[0].startswith(f'{path}: ')


# --- main -------------------------------------------------------------------


def test_main_returns_zero_for_valid_file(tmp_path: Path) -> None:
    assert main([_write(tmp_path, 'ok.spec', VALID_SPEC)]) == 0


def test_main_returns_one_for_invalid_file(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'Summary:        Example package\n'
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
    assert main([_write(tmp_path, 'bad.spec', content)]) == 1


def test_main_without_filenames_returns_zero() -> None:
    assert main([]) == 0
