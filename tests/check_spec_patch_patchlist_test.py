# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_patch_patchlist import (
    _check_spec_patch_patchlist,
)
from openruyi_precommit_hooks.check_spec_patch_patchlist import (
    _check_spec_patch_patchlist_ext,
)
from openruyi_precommit_hooks.check_spec_patch_patchlist import main

# A spec that satisfies every checkpoint: one commented patch above
# BuildRequires, a four digit prefix inside the documented range, and no
# %patchlist because a single patch stays under the threshold.
CLEAN_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo

Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
# Adjust the tests for the newer setuptools.
Patch0:         0001-adjusts-tests-for-setuptools.patch
BuildRequires:  gcc

%description
An example package.

%prep
%autosetup -p1

%files
%license LICENSE

%changelog
%autochangelog
"""

# A package with no patch at all. Every checkpoint is conditional on a
# patch being declared, so this spec must stay silent.
NO_PATCH_SPEC = """\
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

# %patchlist replaces the Patch field once the count exceeds three. The
# documented layout is one comment line per group of entries, and the whole
# block sits above %description.
CLEAN_PATCHLIST_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo

Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
BuildRequires:  gcc

%patchlist
# Import fixes from the upstream maintenance branch.
0001-import-upstream-maintenance-fixes.patch
0002-import-upstream-maintenance-fixes.patch
# Local change, not intended for upstream.
2001-disable-optional-feature.patch
2002-relax-test-timeout.patch

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The same layout with the list below %description, which P5 reports.
PATCHLIST_BELOW_DESCRIPTION_SPEC = """\
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

%patchlist
# Import fixes from the upstream maintenance branch.
0001-import-upstream-maintenance-fixes.patch
0002-import-upstream-maintenance-fixes.patch
# Local change, not intended for upstream.
2001-disable-optional-feature.patch
2002-relax-test-timeout.patch

%files
%license LICENSE

%changelog
%autochangelog
"""

# A four digit range that is outside the documented window. Both prefixes
# parse as four digits, so P2 accepts them and P3 has to reject them.
OUT_OF_RANGE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo

Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
# Backport a fix from the next upstream release.
Patch0:         3000-backport-fix.patch
# Local change, not intended for upstream.
Patch1:         6464-local-change.patch
BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A patch file name with no four digit prefix at all, which P2 reports.
NO_PREFIX_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo

Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
# Fix the endian detection.
Patch0:         foo-1.0-endian.patch
BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A single patch with nothing above it, which P1 reports.
NO_COMMENT_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Patch0:         0001-adjusts-tests-for-setuptools.patch

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

# Four Patch fields and no %patchlist, which exceeds the documented
# threshold of three.
TOO_MANY_PATCHES_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo

Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
# Import fixes from the upstream maintenance branch.
Patch0:         0001-import-upstream-maintenance-fixes.patch
Patch1:         0002-import-upstream-maintenance-fixes.patch
Patch2:         0003-import-upstream-maintenance-fixes.patch
# Local change, not intended for upstream.
Patch3:         2001-disable-optional-feature.patch
BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# The first Patch sits after BuildOption, so P6 reports it.
PATCH_AFTER_BUILD_OPTION_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo

Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
BuildOption(prep): -p0
# Fix the endian detection.
Patch0:         0001-fix-endian-detection.patch
BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# No BuildOption, and the first Patch sits after BuildRequires, so P6
# reports it against the second boundary.
PATCH_AFTER_BUILD_REQUIRES_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo

Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
BuildRequires:  gcc
# Fix the endian detection.
Patch0:         0001-fix-endian-detection.patch

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A patch value that is only resolvable at build time must not be reported
# as a badly named patch file.
MACRO_VALUE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo

Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
# Fix the endian detection.
Patch0:         %{name}-%{version}-endian.patch
BuildRequires:  gcc

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A %patchlist whose body is followed by a multi-line %global macro. The
# prose of the macro must not be read as patch file names.
PATCHLIST_THEN_GLOBAL_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo

Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
BuildRequires:  gcc

%patchlist
# Import fixes from the upstream maintenance branch.
0001-import-upstream-maintenance-fixes.patch
0002-import-upstream-maintenance-fixes.patch
# Local change, not intended for upstream.
2001-disable-optional-feature.patch
2002-relax-test-timeout.patch

%global _description %{expand:
The foo library provides an example implementation used by the prose of
this macro body, which must never be read as patch file names.
}

%description
%{_description}

%files
%license LICENSE

%changelog
%autochangelog
"""

# A path in front of the file name. The four digit prefix belongs to the
# file name, so the reference is compliant.
PATCH_WITH_PATH_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo

Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
# Sync the test data from the upstream repository.
Patch0:         patches/0001-sync-test-data.patch
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


def _spec_with_patch(value: str) -> str:
    return (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'Summary:        Example package\n'
        'License:        MulanPSL-2.0\n'
        'URL:            https://example.org/foo\n'
        '\n'
        'Source0:        https://example.org/foo-%{version}.tar.gz\n'
        'BuildSystem:    autotools\n'
        '# Describe the patch here.\n'
        f'Patch0:         {value}\n'
        'BuildRequires:  gcc\n'
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


@pytest.mark.parametrize(
    'content',
    [
        pytest.param(CLEAN_SPEC, id='single-commented-patch'),
        pytest.param(NO_PATCH_SPEC, id='no-patch'),
        pytest.param(CLEAN_PATCHLIST_SPEC, id='patchlist-above-description'),
        pytest.param(MACRO_VALUE_SPEC, id='macro-value'),
        pytest.param(PATCHLIST_THEN_GLOBAL_SPEC, id='patchlist-then-global'),
        pytest.param(PATCH_WITH_PATH_SPEC, id='patch-with-path'),
    ],
)
def test_passing_specs(
    tmp_path: Path,
    content: str,
) -> None:
    filename = _write(tmp_path, 'foo.spec', content)
    assert _check_spec_patch_patchlist(filename) == []


@pytest.mark.parametrize(
    ('content', 'expected'),
    [
        pytest.param(
            PATCHLIST_BELOW_DESCRIPTION_SPEC,
            '%patchlist (line 15) must be written above %description '
            '(line 12)',
            id='patchlist-below-description',
        ),
        pytest.param(
            OUT_OF_RANGE_SPEC,
            'patch file "3000-backport-fix.patch" (line 11) starts with a '
            'prefix outside 0001-2999',
            id='prefix-above-range',
        ),
        pytest.param(
            NO_PREFIX_SPEC,
            'patch file "foo-1.0-endian.patch" (line 11) does not start '
            'with four digits',
            id='no-prefix',
        ),
        pytest.param(
            NO_COMMENT_SPEC,
            'patch declaration (line 7) has no comment line above it',
            id='no-comment',
        ),
        pytest.param(
            TOO_MANY_PATCHES_SPEC,
            '4 patches are declared but the spec uses no %patchlist',
            id='too-many-patches',
        ),
        pytest.param(
            PATCH_AFTER_BUILD_OPTION_SPEC,
            'Patch (line 12) must be written above BuildOption (line 10)',
            id='patch-after-buildoption',
        ),
        pytest.param(
            PATCH_AFTER_BUILD_REQUIRES_SPEC,
            'Patch (line 12) must be written above BuildRequires (line 10)',
            id='patch-after-buildrequires',
        ),
    ],
)
def test_failing_specs(
    tmp_path: Path,
    content: str,
    expected: str,
) -> None:
    filename = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_patch_patchlist(filename)
    assert any(expected in err for err in errors), errors


def test_out_of_range_reports_every_bad_prefix(tmp_path: Path) -> None:
    filename = _write(tmp_path, 'foo.spec', OUT_OF_RANGE_SPEC)
    errors = _check_spec_patch_patchlist(filename)
    assert len(errors) == 2, errors
    assert '3000-backport-fix.patch' in errors[0]
    assert '6464-local-change.patch' in errors[1]


def test_out_of_range_does_not_report_missing_prefix(tmp_path: Path) -> None:
    """A four digit prefix outside the range is P3, never P2."""
    filename = _write(tmp_path, 'foo.spec', OUT_OF_RANGE_SPEC)
    errors = _check_spec_patch_patchlist(filename)
    assert not any('does not start with four digits' in err for err in errors)


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('0001-fix.patch', id='lower-bound'),
        pytest.param('0999-fix.patch', id='upper-same-version'),
        pytest.param('1000-backport.patch', id='lower-backport'),
        pytest.param('1999-backport.patch', id='upper-backport'),
        pytest.param('2000-local.patch', id='lower-local'),
        pytest.param('2999-local.patch', id='upper-local'),
        pytest.param('0001-fix.diff', id='diff-suffix'),
        pytest.param('0002-Fix-Upper-Case.PATCH', id='upper-case-suffix'),
    ],
)
def test_documented_prefixes_pass(tmp_path: Path, value: str) -> None:
    filename = _write(tmp_path, 'foo.spec', _spec_with_patch(value))
    assert _check_spec_patch_patchlist(filename) == []


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('0000-fix.patch', id='below-range'),
        pytest.param('3000-fix.patch', id='above-range'),
        pytest.param('9999-fix.patch', id='far-above-range'),
        pytest.param('fix-0001.patch', id='prefix-not-leading'),
        pytest.param('foo.patch', id='no-digits'),
    ],
)
def test_undocumented_prefixes_fail(tmp_path: Path, value: str) -> None:
    filename = _write(tmp_path, 'foo.spec', _spec_with_patch(value))
    assert _check_spec_patch_patchlist(filename) != []


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('%{name}.patch', id='macro-only'),
        pytest.param('%{name}-%{version}.patch', id='macro-with-suffix'),
        pytest.param('%{patch0}', id='macro-without-suffix'),
    ],
)
def test_macro_values_are_not_naming_findings(
    tmp_path: Path,
    value: str,
) -> None:
    filename = _write(tmp_path, 'foo.spec', _spec_with_patch(value))
    assert _check_spec_patch_patchlist(filename) == []


def test_non_patch_suffix_is_not_a_naming_finding(tmp_path: Path) -> None:
    """A reference that names no patch file is left to the build."""
    filename = _write(tmp_path, 'foo.spec', _spec_with_patch('%{name}.in'))
    errors = _check_spec_patch_patchlist(filename)
    assert not any('four digits' in err for err in errors)


def test_five_digit_prefix_is_read_as_its_first_four_digits(
    tmp_path: Path,
) -> None:
    """Only the first four digits are the type prefix, so this is compliant."""
    filename = _write(tmp_path, 'foo.spec', _spec_with_patch('12345-fix.patch'))
    assert _check_spec_patch_patchlist(filename) == []


def test_comment_group_only_needs_one_comment(tmp_path: Path) -> None:
    """One comment covers a contiguous run, as the supplement sample shows."""
    filename = _write(tmp_path, 'foo.spec', TOO_MANY_PATCHES_SPEC)
    errors = _check_spec_patch_patchlist(filename)
    assert len(errors) == 1, errors
    assert 'no %patchlist' in errors[0]


def test_patchlist_group_only_needs_one_comment(tmp_path: Path) -> None:
    filename = _write(
        tmp_path, 'foo.spec', CLEAN_PATCHLIST_SPEC,
    )
    assert _check_spec_patch_patchlist(filename) == []


def test_patchlist_entry_without_comment_is_reported(tmp_path: Path) -> None:
    content = CLEAN_PATCHLIST_SPEC.replace(
        '# Import fixes from the upstream maintenance branch.\n', '',
    )
    filename = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_patch_patchlist(filename)
    assert any(
        'no comment line above' in err and '(line 13)' in err
        for err in errors
    ), errors


def test_patchlist_body_stops_at_blank_line(tmp_path: Path) -> None:
    """The multi-line %global body after a list is prose, not patch names."""
    filename = _write(tmp_path, 'foo.spec', PATCHLIST_THEN_GLOBAL_SPEC)
    assert _check_spec_patch_patchlist(filename) == []


def test_patchlist_body_stops_at_directive(tmp_path: Path) -> None:
    content = CLEAN_PATCHLIST_SPEC.replace(
        '2002-relax-test-timeout.patch\n\n%description',
        '2002-relax-test-timeout.patch\n%define debug_package %{nil}\n'
        '%description',
    )
    filename = _write(tmp_path, 'foo.spec', content)
    assert _check_spec_patch_patchlist(filename) == []


def test_patchlist_threshold_counts_entries(tmp_path: Path) -> None:
    """A list is satisfied even when it holds more than three entries."""
    filename = _write(tmp_path, 'foo.spec', CLEAN_PATCHLIST_SPEC)
    assert _check_spec_patch_patchlist(filename) == []


def test_three_patches_do_not_need_patchlist(tmp_path: Path) -> None:
    content = TOO_MANY_PATCHES_SPEC.replace(
        '# Local change, not intended for upstream.\n'
        'Patch3:         2001-disable-optional-feature.patch\n', '',
    )
    filename = _write(tmp_path, 'foo.spec', content)
    errors = _check_spec_patch_patchlist(filename)
    assert not any('no %patchlist' in err for err in errors), errors


def test_patch_position_ignored_without_boundary(tmp_path: Path) -> None:
    """A spec with neither BuildOption nor BuildRequires is silent."""
    content = CLEAN_SPEC.replace('BuildRequires:  gcc\n', '')
    filename = _write(tmp_path, 'foo.spec', content)
    assert _check_spec_patch_patchlist(filename) == []


def test_patch_above_boundary_passes(tmp_path: Path) -> None:
    filename = _write(tmp_path, 'foo.spec', CLEAN_SPEC)
    assert _check_spec_patch_patchlist(filename) == []


def test_missing_file_is_reported(tmp_path: Path) -> None:
    missing = str(tmp_path / 'absent.spec')
    errors = _check_spec_patch_patchlist(missing)
    assert len(errors) == 1
    assert 'absent.spec' in errors[0]


def test_non_utf8_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'latin.spec'
    path.write_bytes(b'Name: foo\n# \xff\xfe\n')
    errors = _check_spec_patch_patchlist(str(path))
    assert len(errors) == 1
    assert 'not valid UTF-8' in errors[0]


def test_findings_are_prefixed_with_the_filename(tmp_path: Path) -> None:
    filename = _write(tmp_path, 'foo.spec', NO_PREFIX_SPEC)
    errors = _check_spec_patch_patchlist(filename)
    assert errors
    assert all(err.startswith(filename + ': ') for err in errors)


@pytest.mark.parametrize(
    ('flag', 'content', 'needle'),
    [
        pytest.param(
            'check_comment',
            NO_COMMENT_SPEC,
            'no comment line above',
            id='no-check-comment',
        ),
        pytest.param(
            'check_naming',
            NO_PREFIX_SPEC,
            'does not start with four digits',
            id='no-check-naming-p2',
        ),
        pytest.param(
            'check_naming',
            OUT_OF_RANGE_SPEC,
            'prefix outside',
            id='no-check-naming-p3',
        ),
        pytest.param(
            'check_patchlist',
            TOO_MANY_PATCHES_SPEC,
            'no %patchlist',
            id='no-check-patchlist-threshold',
        ),
        pytest.param(
            'check_patchlist',
            PATCHLIST_BELOW_DESCRIPTION_SPEC,
            'must be written above %description',
            id='no-check-patchlist-position',
        ),
        pytest.param(
            'check_position',
            PATCH_AFTER_BUILD_OPTION_SPEC,
            'must be written above BuildOption',
            id='no-check-position',
        ),
    ],
)
def test_flag_disables_checkpoint(
    tmp_path: Path,
    flag: str,
    content: str,
    needle: str,
) -> None:
    filename = _write(tmp_path, 'foo.spec', content)
    enabled = _check_spec_patch_patchlist_ext(filename)
    assert any(needle in err for err in enabled), enabled
    disabled = _check_spec_patch_patchlist_ext(filename, **{flag: False})
    assert not any(needle in err for err in disabled), disabled


def test_main_reports_findings_and_returns_one(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    filename = _write(tmp_path, 'foo.spec', NO_PREFIX_SPEC)
    assert main([filename]) == 1
    assert 'four digits' in capsys.readouterr().out


def test_main_clean_file_returns_zero(tmp_path: Path) -> None:
    filename = _write(tmp_path, 'foo.spec', CLEAN_SPEC)
    assert main([filename]) == 0


def test_main_flag_is_accepted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    filename = _write(tmp_path, 'foo.spec', NO_PREFIX_SPEC)
    assert main(['--no-check-naming', filename]) == 0
    assert capsys.readouterr().out == ''


def test_main_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(['--help'])
    assert exc.value.code == 0


# Corpus regression fixtures. The files below live in the read-only
# openRuyi clone and pin the behaviour that motivates the rule.
CORPUS = Path(r'E:\code\openRuyi\SPECS')
_corpus = pytest.mark.skipif(
    not CORPUS.is_dir(),
    reason='the read-only openRuyi clone is not available',
)


@_corpus
def test_corpus_cups_reports_the_uncommented_list() -> None:
    """Ten entries and no comment above any of them."""
    errors = _check_spec_patch_patchlist(str(CORPUS / 'cups' / 'cups.spec'))
    assert any('(line 66) has no comment line above' in err for err in errors)
    assert len(errors) == 1, errors


@_corpus
def test_corpus_cdson_is_clean() -> None:
    """Every entry carries a commit link above it."""
    errors = _check_spec_patch_patchlist(str(CORPUS / 'cdson' / 'cdson.spec'))
    assert errors == []


@_corpus
def test_corpus_cdparanoia_reports_the_missing_prefix() -> None:
    errors = _check_spec_patch_patchlist(
        str(CORPUS / 'cdparanoia' / 'cdparanoia.spec'),
    )
    assert any(
        'cdparanoia-10.2-endian.patch' in err
        and 'does not start with four digits' in err
        for err in errors
    ), errors


@_corpus
def test_corpus_attr_does_not_compare_index_with_prefix() -> None:
    """Patch1 with a 0001- file name is the kernel style, not a finding."""
    errors = _check_spec_patch_patchlist(str(CORPUS / 'attr' / 'attr.spec'))
    assert not any('0001' in err for err in errors), errors


@_corpus
def test_corpus_libunwind_reports_the_out_of_range_prefix() -> None:
    errors = _check_spec_patch_patchlist(
        str(CORPUS / 'libunwind' / 'libunwind.spec'),
    )
    assert any('prefix outside 0001-2999' in err for err in errors), errors


@_corpus
def test_corpus_amdsmi_prose_is_not_a_patch_name() -> None:
    """The %global body after the list must not be read as patch names."""
    errors = _check_spec_patch_patchlist(
        str(CORPUS / 'amdsmi' / 'amdsmi.spec'),
    )
    assert not any('The library' in err for err in errors), errors


@_corpus
def test_corpus_go_groups_comments() -> None:
    """A grouped comment above grouped entries satisfies P1."""
    errors = _check_spec_patch_patchlist(str(CORPUS / 'go' / 'go.spec'))
    assert not any('has no comment line above' in err for err in errors), errors


@_corpus
def test_corpus_aom_reports_the_misplaced_patch() -> None:
    errors = _check_spec_patch_patchlist(str(CORPUS / 'aom' / 'aom.spec'))
    assert any('must be written above BuildOption' in err for err in errors)
