# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check_basic_fields hook."""

from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spdx_basic_fields import _check_basic_fields
from openruyi_precommit_hooks.check_spdx_basic_fields import main


def _write(tmp_path: Path, name: str, content: str) -> str:
    p = tmp_path / name
    p.write_text(content, encoding='utf-8')
    return str(p)


# ---------------------------------------------------------------------------
# Minimal valid SPEC
# ---------------------------------------------------------------------------
MINIMAL_SPEC = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        A test package
License:        MIT

%description
A test package for unit tests.

%files
/usr/bin/foo

%changelog
%autochangelog
"""


# ---------------------------------------------------------------------------
# Tests for _check_basic_fields
# ---------------------------------------------------------------------------

def test_valid_minimal_spec(tmp_path: Path) -> None:
    errors = _check_basic_fields(_write(tmp_path, 'ok.spec', MINIMAL_SPEC))
    assert errors == []


def test_missing_name(tmp_path: Path) -> None:
    spec = MINIMAL_SPEC.replace('Name:           foo\n', '')
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert any('missing required field "Name:"' in e for e in errors)


def test_missing_version(tmp_path: Path) -> None:
    spec = MINIMAL_SPEC.replace('Version:        1.0\n', '')
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert any('missing required field "Version:"' in e for e in errors)


def test_missing_release(tmp_path: Path) -> None:
    spec = MINIMAL_SPEC.replace('Release:        %autorelease\n', '')
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert any('missing required field "Release:"' in e for e in errors)


def test_missing_summary(tmp_path: Path) -> None:
    spec = MINIMAL_SPEC.replace('Summary:        A test package\n', '')
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert any('missing required field "Summary:"' in e for e in errors)


def test_missing_license_field(tmp_path: Path) -> None:
    spec = MINIMAL_SPEC.replace('License:        MIT\n', '')
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert any('missing required field "License:"' in e for e in errors)


def test_missing_description_section(tmp_path: Path) -> None:
    spec = MINIMAL_SPEC.replace(
        '%description\nA test package for unit tests.\n\n', '')
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert any('missing required section "%description"' in e for e in errors)


def test_missing_files_section(tmp_path: Path) -> None:
    spec = MINIMAL_SPEC.replace('%files\n/usr/bin/foo\n\n', '')
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert any('missing required section "%files"' in e for e in errors)


def test_missing_changelog_section(tmp_path: Path) -> None:
    spec = MINIMAL_SPEC.replace('%changelog\n%autochangelog\n', '')
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert any('missing required section "%changelog"' in e for e in errors)


def test_changelog_without_autochangelog_is_ok(tmp_path: Path) -> None:
    """%changelog with hand-written content (without %autochangelog) is ok.
    The '基础字段与段落' section only requires %changelog to be present,
    not its content format."""
    spec = MINIMAL_SPEC.replace(
        '%changelog\n%autochangelog\n',
        '%changelog\n* Mon Sep 15 2025 Developer <dev@example.com> - 1.0-1\n- First release\n\n',
    )
    errors = _check_basic_fields(_write(tmp_path, 'ok.spec', spec))
    assert errors == []


def test_field_out_of_order(tmp_path: Path) -> None:
    """Version before Name is out of order."""
    spec = MINIMAL_SPEC.replace(
        'Name:           foo\nVersion:        1.0\n',
        'Version:        1.0\nName:           foo\n',
    )
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert any('field order is incorrect' in e for e in errors)


def test_field_order_with_url_and_source(tmp_path: Path) -> None:
    """Valid spec with URL and Source in correct order."""
    spec = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           bar
Version:        2.0
Release:        %autorelease
Summary:        Another test package
License:        Apache-2.0
URL:            https://example.org
VCS:            git:https://git.example.org/bar.git
Source:         https://example.org/bar-%{version}.tar.gz

%description
Another test package.

%files
/usr/bin/bar

%changelog
%autochangelog
"""
    errors = _check_basic_fields(_write(tmp_path, 'ok.spec', spec))
    assert errors == []


def test_source_before_vcs_is_out_of_order(tmp_path: Path) -> None:
    """Source before VCS violates the required relative order."""
    spec_bad = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           bar
Version:        2.0
Release:        %autorelease
Summary:        Bad order package
License:        MIT
Source:         https://example.org/bar-%{version}.tar.gz
VCS:            git:https://git.example.org/bar.git
URL:            https://example.org

%description
Bad order package.

%files
/usr/bin/bar

%changelog
%autochangelog
"""
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec_bad))
    assert any('field order is incorrect' in e for e in errors)


def test_sections_not_separated_by_blank_line(tmp_path: Path) -> None:
    """%description and %files must be separated by a blank line."""
    spec = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Test
License:        MIT

%description
A test package.
%files
/usr/bin/foo

%changelog
%autochangelog
"""
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert any('must be separated by a blank line' in e for e in errors)


def test_comment_between_blank_line_and_section_is_ok(tmp_path: Path) -> None:
    """Comment after a blank line before next section is allowed.

    e.g.  %install blocks ...

          # TODO: We purposely disable tests for now
          %check
    """
    spec = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Test
License:        MIT

%description
A test package.

# We skip tests for now
%files
/usr/bin/foo

%changelog
%autochangelog
"""
    errors = _check_basic_fields(_write(tmp_path, 'good.spec', spec))
    assert not any('must be separated by a blank line' in e for e in errors)


def test_comment_without_blank_line_still_errors(tmp_path: Path) -> None:
    """Comment directly before section without blank line → error."""
    spec = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Test
License:        MIT

%description
A test package.
# This comment is not preceded by a blank line
%files
/usr/bin/foo

%changelog
%autochangelog
"""
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert any('must be separated by a blank line' in e for e in errors)


def test_empty_file(tmp_path: Path) -> None:
    errors = _check_basic_fields(_write(tmp_path, 'empty.spec', ''))
    assert any('file is empty' in e for e in errors)


def test_file_with_only_spdx_header(tmp_path: Path) -> None:
    """File with SPDX header only and no fields/sections."""
    spec = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0
"""
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    assert len(errors) >= 5  # missing all 5 required fields


def test_spec_with_full_field_set(tmp_path: Path) -> None:
    """Spec with all possible fields in correct order."""
    spec = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           full
Version:        3.0
Release:        %autorelease
Summary:        Full field spec
License:        GPL-3.0-only
URL:            https://full.example.org
VCS:            git:https://git.example.org/full.git
Source:         https://full.example.org/full-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    autotools
BuildRequires:  gcc
Provides:       something
Conflicts:      something-else
Obsoletes:      old-thing
Recommends:     recommended-pkg
Requires:       required-pkg
Supplements:    supplementary-pkg

%description
Full field spec for testing.

%files
/usr/bin/full

%changelog
%autochangelog
"""
    errors = _check_basic_fields(_write(tmp_path, 'ok.spec', spec))
    assert errors == []


# ---------------------------------------------------------------------------
# Tests for main()
# ---------------------------------------------------------------------------

def test_main_valid_spec(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    retv = main([_write(tmp_path, 'ok.spec', MINIMAL_SPEC)])
    captured = capsys.readouterr()
    assert retv == 0
    assert captured.out == ''


def test_main_bad_spec(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec = MINIMAL_SPEC.replace('Name:           foo\n', '')
    retv = main([_write(tmp_path, 'bad.spec', spec)])
    captured = capsys.readouterr()
    assert retv == 1
    assert 'missing required field "Name:"' in captured.out


def test_main_empty_input() -> None:
    assert main([]) == 0


def test_main_unreadable_file(tmp_path: Path) -> None:
    retv = main([str(tmp_path / 'missing.spec')])
    assert retv == 1


def test_main_bad_utf8(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / 'bad-utf8.spec'
    p.write_bytes(b'Name: foo\xff\xfe\n')
    retv = main([str(p)])
    captured = capsys.readouterr()
    assert retv == 1
    assert 'not valid UTF-8' in captured.out


# ---------------------------------------------------------------------------
# Tests for correct section detection (non-section macros are ignored)
# ---------------------------------------------------------------------------

def test_non_section_macros_not_treated_as_sections(tmp_path: Path) -> None:
    """%global, %define, %bcond, %license, %doc, %dir, etc. are not sections."""
    spec = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

%global commit abc123
%global shortcommit %(c=%{commit}; echo ${c:0:7})

Name:           db
Version:        6.2.32
Release:        %autorelease
Summary:        A database library
License:        BSD-3-Clause

%description
A database library.

%prep
%setup -q

%build
%configure
%make_build

%install
%make_install

%files
%license LICENSE
%doc README
%dir %{_datadir}/db

%changelog
%autochangelog
"""
    errors = _check_basic_fields(_write(tmp_path, 'ok.spec', spec))
    assert errors == []


def test_conditional_macros_not_sections(tmp_path: Path) -> None:
    """%if / %else / %endif / %ifarch are not treated as sections."""
    spec = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

%if 0%{?fedora}
%bcond tests 1
%else
%bcond tests 0
%endif

Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Test
License:        MIT

%description
Test package.

%build
%make_build

%install
%make_install

%ifarch x86_64

%files
/usr/bin/foo64
%endif

%changelog
%autochangelog
"""
    errors = _check_basic_fields(_write(tmp_path, 'ok.spec', spec))
    # Only real sections trigger separation checks.
    # %ifarch wrapping %files means %install→%files has no blank line
    # between their "section" boundaries (because %ifarch is inline).
    # This is an acceptable detection for now.
    assert all(
        'missing required' not in e
        and 'field order' not in e
        for e in errors
    )


def test_only_real_sections_trigger_separation_check(tmp_path: Path) -> None:
    """Only real RPM scriptlet sections need blank line separation."""
    spec = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Test
License:        MIT

%description
Test package.
%prep
%setup -q

%build
%configure

%install
%make_install

%files
%license LICENSE
%doc README

%changelog
%autochangelog
"""
    errors = _check_basic_fields(_write(tmp_path, 'bad.spec', spec))
    # %description→%prep not separated → error
    # All other sections separated → ok
    # %license/%doc are NOT sections, no separation errors for those
    assert any('must be separated by a blank line' in e for e in errors)
    assert len(errors) == 1  # only the %description→%prep gap


def test_main_all_bad_prints_each(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = [
        _write(tmp_path, 'x1.spec', ''),
        _write(tmp_path, 'x2.spec', ''),
    ]
    retv = main(paths)
    captured = capsys.readouterr()
    assert retv == 1
    assert 'x1.spec' in captured.out
    assert 'x2.spec' in captured.out