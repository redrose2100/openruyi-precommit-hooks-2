# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_condition_build import (
    _check_spec_condition_build,
)
from openruyi_precommit_hooks.check_spec_condition_build import (
    _check_spec_condition_build_ext,
)
from openruyi_precommit_hooks.check_spec_condition_build import main

# The documented shape: "%bcond" with an explicit default, read back with
# "%if %{with ...}" and "%if %{without ...}".
CLEAN_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%bcond bootstrap 0
%bcond docs 1

%description
An example package.

%build
%if %{with bootstrap}
echo bootstrap
%endif
%if %{without docs}
echo no docs
%endif

%files

%changelog
%autochangelog
"""

# A spec with no optional switch at all must stay silent: the clauses only
# describe how a switch is written, not whether one must exist.
NO_SWITCH_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%files

%changelog
%autochangelog
"""

LEGACY_WITH_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%bcond_with openssl

%description
An example package.

%files

%changelog
%autochangelog
"""

LEGACY_WITHOUT_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%bcond_without pkgconfig_compat

%description
An example package.

%files

%changelog
%autochangelog
"""

MANUAL_SWITCH_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%define with_mroonga 1
%define with_rocksdb 0

%description
An example package.

%files

%changelog
%autochangelog
"""

NO_DEFAULT_SPEC = """\\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%bcond bootstrap

%description
An example package.

%files

%changelog
%autochangelog
"""

# A default built from a macro cannot be judged before expansion, so the
# declaration is accepted as written.
MACRO_DEFAULT_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%bcond bootstrap 0
%bcond rpmwheels %{without bootstrap}

%description
An example package.

%files

%changelog
%autochangelog
"""

# The corpus shape that made the "dead switch" idea a non-checkpoint: a
# switch declared once per branch of an %if is legitimate.
BRANCHED_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%bcond bootstrap 0

%if %{with bootstrap}
%bcond race 0
%else
%bcond race 0
%bcond shared 0
%endif

%description
An example package.

%files

%changelog
%autochangelog
"""

# A commented out declaration is documentation, not a declaration.
COMMENTED_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

# %bcond_with openssl
#  %define with_mroonga 1
# %bcond bootstrap

%description
An example package.

%files

%changelog
%autochangelog
"""

# An indented declaration still counts, because %bcond may sit inside an
# %if branch.
INDENTED_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%ifarch x86_64
  %bcond_with sse42
%endif

%description
An example package.

%files

%changelog
%autochangelog
"""


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding='utf-8')
    return str(path)


def _spec_with_body(name: str, body: str) -> str:
    return (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'Summary:        Example package\n'
        'License:        MulanPSL-2.0\n'
        '\n'
        f'{body}\n'
        '\n'
        '%description\n'
        'An example package.\n'
        '\n'
        '%files\n'
        '\n'
        '%changelog\n'
        '%autochangelog\n'
    )


def test_clean_spec_is_accepted(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', CLEAN_SPEC)
    assert _check_spec_condition_build(path) == []


def test_no_switch_spec_is_accepted(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', NO_SWITCH_SPEC)
    assert _check_spec_condition_build(path) == []


def test_legacy_with_is_reported(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', LEGACY_WITH_SPEC)
    errors = _check_spec_condition_build(path)
    assert len(errors) == 1
    assert errors[0].startswith(f'{path}: ')
    assert '%bcond_with openssl' in errors[0]
    assert 'line 7' in errors[0]
    assert '%bcond openssl 0' in errors[0]


def test_legacy_without_suggests_default_one(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', LEGACY_WITHOUT_SPEC)
    errors = _check_spec_condition_build(path)
    assert len(errors) == 1
    assert '%bcond_without pkgconfig_compat' in errors[0]
    assert '%bcond pkgconfig_compat 1' in errors[0]


def test_manual_switch_is_not_reported(tmp_path: Path) -> None:
    # The clause names %bcond and the two legacy macros, not the general
    # purpose %define family.
    path = _write(tmp_path, 'foo.spec', MANUAL_SWITCH_SPEC)
    assert _check_spec_condition_build(path) == []


def test_missing_default_value_is_reported(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', NO_DEFAULT_SPEC)
    errors = _check_spec_condition_build(path)
    assert len(errors) == 1
    assert '%bcond bootstrap' in errors[0]
    assert 'no default value' in errors[0]


def test_macro_default_value_is_accepted(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', MACRO_DEFAULT_SPEC)
    assert _check_spec_condition_build(path) == []


def test_branched_declaration_is_accepted(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', BRANCHED_SPEC)
    assert _check_spec_condition_build(path) == []


def test_commented_lines_are_ignored(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', COMMENTED_SPEC)
    assert _check_spec_condition_build(path) == []


def test_indented_declaration_is_reported(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', INDENTED_SPEC)
    errors = _check_spec_condition_build(path)
    assert len(errors) == 1
    assert '%bcond_with sse42' in errors[0]


def test_multiple_findings_in_one_spec(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'foo.spec',
        _spec_with_body(
            'x',
            '%bcond_with openssl\n'
            '%define with_mroonga 1\n'
            '%bcond bootstrap\n',
        ),
    )
    errors = _check_spec_condition_build(path)
    assert len(errors) == 2


def test_all_flags_disabled_keeps_findings_silent(tmp_path: Path) -> None:
    path = _write(tmp_path, 'foo.spec', LEGACY_WITH_SPEC)
    errors = _check_spec_condition_build_ext(
        path,
        check_legacy_form=False,
        check_default_value=False,
    )
    assert errors == []


def test_disable_only_legacy_form(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'foo.spec',
        _spec_with_body('x', '%bcond_with openssl\n%bcond bootstrap\n'),
    )
    errors = _check_spec_condition_build_ext(path, check_legacy_form=False)
    assert len(errors) == 1
    assert 'no default value' in errors[0]


def test_disable_only_default_value(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'foo.spec',
        _spec_with_body('x', '%bcond_with openssl\n%bcond bootstrap\n'),
    )
    errors = _check_spec_condition_build_ext(path, check_default_value=False)
    assert len(errors) == 1
    assert '%bcond_with openssl' in errors[0]


def test_missing_file_is_reported() -> None:
    errors = _check_spec_condition_build('does-not-exist.spec')
    assert len(errors) == 1
    assert errors[0].startswith('does-not-exist.spec: ')


def test_non_utf8_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'bad.spec'
    path.write_bytes(b'Name: foo\n\xff\xfe\n')
    errors = _check_spec_condition_build(str(path))
    assert len(errors) == 1
    assert 'not valid UTF-8' in errors[0]


def test_main_returns_zero_for_clean_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', CLEAN_SPEC)
    assert main([path]) == 0
    assert capsys.readouterr().out == ''


def test_main_returns_one_and_prints_for_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', LEGACY_WITH_SPEC)
    assert main([path]) == 1
    out = capsys.readouterr().out
    assert '%bcond_with openssl' in out


def test_main_honours_no_check_flags(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', LEGACY_WITH_SPEC)
    assert main(['--no-check-legacy-form', path]) == 0
    assert capsys.readouterr().out == ''


def test_main_without_filenames_is_clean(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    assert capsys.readouterr().out == ''


def test_empty_spec_is_accepted(tmp_path: Path) -> None:
    path = _write(tmp_path, 'empty.spec', '')
    assert _check_spec_condition_build(path) == []


def test_bcond_name_case_is_kept_verbatim(tmp_path: Path) -> None:
    path = _write(
        tmp_path, 'foo.spec', _spec_with_body('x', '%bcond_with OpenSSL'),
    )
    errors = _check_spec_condition_build(path)
    assert len(errors) == 1
    assert '%bcond OpenSSL 0' in errors[0]
