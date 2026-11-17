# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check-spec-requires."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_requires import _check_spec_requires
from openruyi_precommit_hooks.check_spec_requires import _check_spec_requires_ext
from openruyi_precommit_hooks.check_spec_requires import main


CLEAN_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
URL:            https://example.org/demo
Source0:        https://example.org/demo-1.0.tar.gz
BuildArch:      noarch
Recommends:     demo-docs
Requires:       coreutils
Requires:       pkgconfig(openssl) >= 3.0

%description
A demo package.
"""

NO_REQUIRES_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT

%description
A demo package.
"""

SUBPACKAGE_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
Requires:       coreutils

%description
A demo package.

%package        devel
Summary:        Development files
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
Development files.
"""


def _write(tmp_path: Path, content: str) -> str:
    path = tmp_path / 'demo.spec'
    path.write_text(content, encoding='utf-8')
    return str(path)


def _single_error(tmp_path: Path, content: str) -> str:
    errors = _check_spec_requires(_write(tmp_path, content))
    assert len(errors) == 1, errors
    return errors[0].split(': ', 1)[1]


def test_clean_spec_has_no_findings(tmp_path: Path) -> None:
    assert _check_spec_requires(_write(tmp_path, CLEAN_SPEC)) == []


def test_absent_field_is_not_a_finding(tmp_path: Path) -> None:
    assert _check_spec_requires(
        _write(tmp_path, NO_REQUIRES_SPEC),
    ) == []


def test_pinned_subpackage_has_no_findings(tmp_path: Path) -> None:
    assert _check_spec_requires(_write(tmp_path, SUBPACKAGE_SPEC)) == []


def test_missing_file_is_reported() -> None:
    errors = _check_spec_requires('does-not-exist.spec')
    assert len(errors) == 1
    assert errors[0].startswith('does-not-exist.spec: ')


def test_non_utf8_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'latin.spec'
    path.write_bytes(b'Name: demo\n# \xff\n')
    errors = _check_spec_requires(str(path))
    assert errors == [f'{path}: file is not valid UTF-8']


# --------------------------------------------------------------------------
# S1 - the field is spelled Requires.
# --------------------------------------------------------------------------


def test_s1_misspelled_field(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('Requires:       coreutils', 'Require:        coreutils')
    message = _single_error(tmp_path, spec)
    assert 'is spelled "Require"' in message
    assert 'write "Requires"' in message


def test_s1_uppercase_field(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('Requires:       coreutils', 'requires:       coreutils')
    message = _single_error(tmp_path, spec)
    assert 'is spelled "requires"' in message


def test_s1_does_not_read_buildrequires(tmp_path: Path) -> None:
    spec = NO_REQUIRES_SPEC.replace(
        'License:        MIT',
        'License:        MIT\nBuildRequires:  zlib-devel',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s1_can_be_disabled(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('Requires:       coreutils', 'Require:        coreutils')
    errors = _check_spec_requires_ext(
        _write(tmp_path, spec),
        check_field_case=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# S2 - the field declares at least one dependency.
# --------------------------------------------------------------------------


def test_s2_empty_field(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('Requires:       coreutils', 'Requires:')
    message = _single_error(tmp_path, spec)
    assert 'declares no dependency' in message
    assert 'one dependency per line' in message


def test_s2_can_be_disabled(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('Requires:       coreutils', 'Requires:')
    errors = _check_spec_requires_ext(
        _write(tmp_path, spec),
        check_value=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# S3 - one field line declares exactly one dependency.
# --------------------------------------------------------------------------


def test_s3_two_dependencies_on_one_line(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('Requires:       coreutils', 'Requires:       gawk tar')
    message = _single_error(tmp_path, spec)
    assert 'declares 2 dependencies' in message
    assert 'one dependency per line' in message


def test_s3_comma_separated_dependencies(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Requires:       coreutils',
        'Requires:       gawk, tar',
    )
    message = _single_error(tmp_path, spec)
    assert 'declares 2 dependencies' in message


def test_s3_versioned_dependency_is_one_dependency(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Requires:       pkgconfig(openssl) >= 3.0',
        'Requires:       openssl-libs >= 3.0',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s3_rich_dependency_is_one_dependency(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Requires:       pkgconfig(openssl) >= 3.0',
        'Requires:       (python3dist(foo) if python3dist(bar))',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s3_with_clause_is_one_dependency(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Requires:       pkgconfig(openssl) >= 3.0',
        'Requires:       foo with bar',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s3_double_equals_operator_is_one_dependency(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Requires:       pkgconfig(openssl) >= 3.0',
        'Requires:       %{name}%{?_isa} == %{version}-%{release}',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s3_can_be_disabled(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace('Requires:       coreutils', 'Requires:       gawk tar')
    errors = _check_spec_requires_ext(
        _write(tmp_path, spec),
        check_one_per_line=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# S4 - one field block declares each clause at most once.
# --------------------------------------------------------------------------


def test_s4_duplicate_clause(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Requires:       coreutils',
        'Requires:       coreutils\nRequires:       coreutils',
    )
    message = _single_error(tmp_path, spec)
    assert 'Requires "coreutils" (line 11)' in message
    assert 'is already declared at line 10' in message
    assert 'remove the duplicate' in message


def test_s4_version_interval_is_not_a_duplicate(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Requires:       coreutils',
        'Requires:       openssl-libs >= 3.0\nRequires:       openssl-libs < 4.0',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s4_scriptlet_qualifier_is_a_different_clause(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Requires:       coreutils',
        'Requires:       coreutils\nRequires(post):  coreutils',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s4_same_clause_in_two_blocks_is_allowed(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       coreutils',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s4_conditional_block_is_exempt(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Requires:       coreutils',
        'Requires:       coreutils\n'
        '%if 0%{?openruyi}\n'
        'Requires:       coreutils\n'
        '%endif',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s4_can_be_disabled(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Requires:       coreutils',
        'Requires:       coreutils\nRequires:       coreutils',
    )
    errors = _check_spec_requires_ext(
        _write(tmp_path, spec),
        check_duplicate=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# S5 - the field sits between Recommends and Supplements.
# --------------------------------------------------------------------------


def test_s5_before_recommends(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Recommends:     demo-docs\n'
        'Requires:       coreutils\n',
        'Requires:       coreutils\n'
        'Recommends:     demo-docs\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'must be written after Recommends (line 10)' in message
    assert 'Recommends -> Requires -> Supplements' in message


def test_s5_after_supplements(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Recommends:     demo-docs\n'
        'Requires:       coreutils\n',
        'Supplements:    demo-extras\n'
        'Requires:       coreutils\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'must be written before Supplements (line 9)' in message
    assert 'Recommends -> Requires -> Supplements' in message


def test_s5_after_provides_is_silent(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildArch:      noarch',
        'BuildArch:      noarch\nProvides:       demo-libs = %{version}-%{release}',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s5_absent_boundary_is_silent(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       coreutils',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s5_can_be_disabled(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'Recommends:     demo-docs\n'
        'Requires:       coreutils\n',
        'Requires:       coreutils\n'
        'Recommends:     demo-docs\n',
    )
    errors = _check_spec_requires_ext(
        _write(tmp_path, spec),
        check_position=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# S6 - the field sits inside the header field block.
# --------------------------------------------------------------------------


def test_s6_after_first_section(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        '%description\nA demo package.\n',
        '%description\nA demo package.\nRequires:       zlib-devel\n',
    )
    message = _single_error(tmp_path, spec)
    assert 'is written outside the header field block' in message
    assert 'write it before the first section' in message


def test_s6_inside_macro_body_is_silent(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        'BuildArch:      noarch\n',
        'BuildArch:      noarch\n'
        '%global bundled_tool %{expand:\n'
        'Requires:       bundled(zlib)\n'
        '}\n',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s6_inside_heredoc_is_silent(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        '%description\nA demo package.\n',
        '%description\n'
        'A demo package.\n'
        '%prep\n'
        'cat > demo.pc << EOF\n'
        'Requires:       zlib\n'
        'EOF\n',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s6_in_subpackage_block_is_silent(tmp_path: Path) -> None:
    spec = CLEAN_SPEC.replace(
        '%description\nA demo package.\n',
        '%description\nA demo package.\n'
        '%package        tools\n'
        'Requires:       zlib-devel\n'
        '%description    tools\nTools.\n',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


# --------------------------------------------------------------------------
# S7 - a subpackage pins the main package to its version and release.
# --------------------------------------------------------------------------


def test_s7_unpinned_dependency_on_main(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       demo',
    )
    message = _single_error(tmp_path, spec)
    assert 'Requires "demo" (line 13) does not pin the main package' in message
    assert 'Requires: %{name}%{?_isa} = %{version}-%{release}' in message


def test_s7_version_without_release(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       demo = %{version}',
    )
    message = _single_error(tmp_path, spec)
    assert 'does not pin the main package to its version and release' in message


def test_s7_dependency_on_other_package_is_silent(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       %{name}-tools = %{version}',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s7_main_block_is_exempt(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Requires:       coreutils',
        'Requires:       demo',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s7_can_be_disabled(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       demo',
    )
    errors = _check_spec_requires_ext(
        _write(tmp_path, spec),
        check_main_pin=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# S8 - that pin names the architecture through %{?_isa}.
# --------------------------------------------------------------------------


def test_s8_pin_without_isa(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       %{name} = %{version}-%{release}',
    )
    message = _single_error(tmp_path, spec)
    assert 'does not constrain the architecture of the main package' in message
    assert '%{name}%{?_isa} = %{version}-%{release}' in message


def test_s8_literal_name_without_isa(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       demo = %{version}-%{release}',
    )
    message = _single_error(tmp_path, spec)
    assert 'does not constrain the architecture' in message


def test_s8_is_not_reported_twice_with_s7(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       demo',
    )
    errors = _check_spec_requires(_write(tmp_path, spec))
    assert len(errors) == 1, errors
    assert 'does not pin the main package' in errors[0]


def test_s8_noarch_spec_is_exempt(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'License:        MIT',
        'License:        MIT\nBuildArch:      noarch',
    ).replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       %{name} = %{version}-%{release}',
    )
    assert _check_spec_requires(_write(tmp_path, spec)) == []


def test_s8_can_be_disabled(tmp_path: Path) -> None:
    spec = SUBPACKAGE_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       %{name} = %{version}-%{release}',
    )
    errors = _check_spec_requires_ext(
        _write(tmp_path, spec),
        check_main_isa=False,
    )
    assert errors == []


# --------------------------------------------------------------------------
# CLI.
# --------------------------------------------------------------------------


def test_main_returns_zero_for_clean_spec(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, CLEAN_SPEC)
    assert main([path]) == 0
    assert capsys.readouterr().out == ''


def test_main_returns_one_and_prints_findings(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = CLEAN_SPEC.replace('Requires:       coreutils', 'Requires:       gawk tar')
    path = _write(tmp_path, spec)
    assert main([path]) == 1
    out = capsys.readouterr().out
    assert 'declares 2 dependencies' in out
    assert path in out


def test_main_honours_disable_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = CLEAN_SPEC.replace('Requires:       coreutils', 'Requires:       gawk tar')
    path = _write(tmp_path, spec)
    assert main([path, '--no-check-one-per-line']) == 0
    assert capsys.readouterr().out == ''


def test_main_without_filenames_returns_zero() -> None:
    assert main([]) == 0
