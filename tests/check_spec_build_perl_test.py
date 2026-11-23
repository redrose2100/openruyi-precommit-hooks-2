# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check-spec-build-perl."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_build_perl import (
    _check_spec_build_perl,
)
from openruyi_precommit_hooks.check_spec_build_perl import (
    _check_spec_build_perl_ext,
)
from openruyi_precommit_hooks.check_spec_build_perl import main


CLEAN_PERLMAKER_SPEC = """\
Name:           perl-Demo
Version:        1.0
Release:        1
Summary:        A demo Perl module
License:        MIT
URL:            https://metacpan.org/dist/Demo
Source0:        https://www.cpan.org/authors/id/D/DE/DEMO/Demo-1.0.tar.gz
BuildSystem:    perlmaker
BuildRequires:  perl-rpm-packaging
BuildRequires:  perl-rpm-macros
BuildRequires:  perl-macros
BuildRequires:  perl(ExtUtils::MakeMaker)

%description
A demo Perl module.

%files -f %{name}.files
%doc Changes README
"""

CLEAN_PERLBUILD_SPEC = """\
Name:           perl-Demo
Version:        1.0
Release:        1
Summary:        A demo Perl module
License:        MIT
URL:            https://metacpan.org/dist/Demo
Source0:        https://www.cpan.org/authors/id/D/DE/DEMO/Demo-1.0.tar.gz
BuildSystem:    perlbuild
BuildRequires:  perl-rpm-packaging
BuildRequires:  perl-rpm-macros
BuildRequires:  perl-macros
BuildRequires:  perl(Module::Build)

%description
A demo Perl module.

%files -f %{name}.files
%doc Changes README
"""

NOT_PERL_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildSystem:    cmake
BuildRequires:  cmake

%description
A demo package.

%files
%{_bindir}/demo
"""

NO_BUILD_SYSTEM_SPEC = """\
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildRequires:  perl-macros

%description
A demo package.
"""


def _write(tmp_path: Path, content: str) -> str:
    path = tmp_path / 'demo.spec'
    path.write_text(content, encoding='utf-8')
    return str(path)


def _messages(tmp_path: Path, content: str) -> list[str]:
    return [
        err.split(': ', 1)[1]
        for err in _check_spec_build_perl(_write(tmp_path, content))
    ]


def _single_error(tmp_path: Path, content: str) -> str:
    messages = _messages(tmp_path, content)
    assert len(messages) == 1, messages
    return messages[0]


# --------------------------------------------------------------------------
# Scope - only a spec that declares a Perl build system is judged.
# --------------------------------------------------------------------------


def test_clean_perlmaker_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_build_perl(
        _write(tmp_path, CLEAN_PERLMAKER_SPEC),
    ) == []


def test_clean_perlbuild_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_build_perl(
        _write(tmp_path, CLEAN_PERLBUILD_SPEC),
    ) == []


def test_non_perl_spec_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_perl(_write(tmp_path, NOT_PERL_SPEC)) == []


def test_spec_without_build_system_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_perl(
        _write(tmp_path, NO_BUILD_SYSTEM_SPEC),
    ) == []


def test_unreadable_file_reports_error(tmp_path: Path) -> None:
    missing = str(tmp_path / 'missing.spec')
    errors = _check_spec_build_perl(missing)
    assert len(errors) == 1
    assert errors[0].startswith(missing)


def test_utf8_error_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'demo.spec'
    path.write_bytes(b'BuildSystem: perlmaker\n\xff\xfe\n')
    errors = _check_spec_build_perl(str(path))
    assert errors == [f'{path}: file is not valid UTF-8']


def test_build_system_is_matched_case_insensitively(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        'BuildSystem:    perlmaker', 'BuildSystem:    PerlMaker',
    )
    assert _check_spec_build_perl(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# C1 - the three shared Perl macro packages.
# --------------------------------------------------------------------------


def test_c1_missing_packaging_package_is_reported(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        'BuildRequires:  perl-rpm-packaging\n', '',
    )
    assert 'missing perl-rpm-packaging' in _single_error(tmp_path, content)


def test_c1_missing_macros_package_is_reported(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace('BuildRequires:  perl-macros\n', '')
    assert 'missing perl-macros' in _single_error(tmp_path, content)


def test_c1_missing_rpm_macros_package_is_reported(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        'BuildRequires:  perl-rpm-macros\n', '',
    )
    assert 'missing perl-rpm-macros' in _single_error(tmp_path, content)


def test_c1_message_names_the_system_and_line(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace('BuildRequires:  perl-macros\n', '')
    message = _single_error(tmp_path, content)
    assert 'BuildSystem: perlmaker (line 8)' in message
    assert 'requires the shared Perl build dependencies' in message


def test_c1_all_missing_packages_are_listed(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC
    for pkg in ('perl-rpm-packaging', 'perl-rpm-macros', 'perl-macros'):
        content = content.replace(f'BuildRequires:  {pkg}\n', '')
    message = _single_error(tmp_path, content)
    assert 'missing perl-rpm-packaging, perl-rpm-macros, perl-macros' in (
        message
    )


def test_c1_report_is_a_single_line_for_all_three(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC
    for pkg in ('perl-rpm-packaging', 'perl-rpm-macros', 'perl-macros'):
        content = content.replace(f'BuildRequires:  {pkg}\n', '')
    assert len(_messages(tmp_path, content)) == 1


def test_c1_comma_list_satisfies_the_requirement(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        'BuildRequires:  perl-rpm-packaging\n'
        'BuildRequires:  perl-rpm-macros\n'
        'BuildRequires:  perl-macros',
        'BuildRequires:  perl-rpm-packaging, perl-rpm-macros, perl-macros',
    )
    assert _check_spec_build_perl(_write(tmp_path, content)) == []


def test_c1_versioned_package_satisfies(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        'BuildRequires:  perl-macros',
        'BuildRequires:  perl-macros >= 1.0',
    )
    assert _check_spec_build_perl(_write(tmp_path, content)) == []


def test_c1_comment_does_not_satisfy_the_requirement(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        'BuildRequires:  perl-macros\n',
        '# BuildRequires:  perl-macros\n',
    )
    assert 'missing perl-macros' in _single_error(tmp_path, content)


def test_c1_subpackage_declaration_counts(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        'BuildRequires:  perl-macros\n', '',
    ).replace(
        '%files -f %{name}.files',
        '%package doc\n'
        'Summary:        Documentation\n'
        'BuildRequires:  perl-macros\n'
        '\n'
        '%description doc\n'
        'Documentation.\n'
        '\n'
        '%files -f %{name}.files',
    )
    assert _check_spec_build_perl(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# C2 - the module capability each build system implies.
# --------------------------------------------------------------------------


def test_c2_perlbuild_missing_module_is_reported(tmp_path: Path) -> None:
    content = CLEAN_PERLBUILD_SPEC.replace(
        'BuildRequires:  perl(Module::Build)\n', '',
    )
    assert 'missing "perl(Module::Build)"' in _single_error(tmp_path, content)


def test_c2_perlmaker_missing_module_is_reported(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        'BuildRequires:  perl(ExtUtils::MakeMaker)\n', '',
    )
    assert 'missing "perl(ExtUtils::MakeMaker)"' in _single_error(
        tmp_path, content,
    )


def test_c2_perlbuild_rejects_the_perlmaker_module(tmp_path: Path) -> None:
    content = CLEAN_PERLBUILD_SPEC.replace(
        'perl(Module::Build)', 'perl(ExtUtils::MakeMaker)',
    )
    assert 'missing "perl(Module::Build)"' in _single_error(tmp_path, content)


def test_c2_perlmaker_rejects_the_perlbuild_module(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        'perl(ExtUtils::MakeMaker)', 'perl(Module::Build)',
    )
    assert 'missing "perl(ExtUtils::MakeMaker)"' in _single_error(
        tmp_path, content,
    )


def test_c2_message_names_the_system(tmp_path: Path) -> None:
    content = CLEAN_PERLBUILD_SPEC.replace(
        'BuildRequires:  perl(Module::Build)\n', '',
    )
    message = _single_error(tmp_path, content)
    assert message.startswith('BuildSystem: perlbuild (line 8)')
    assert 'requires "perl(Module::Build)"' in message


def test_c2_versioned_module_satisfies(tmp_path: Path) -> None:
    content = CLEAN_PERLBUILD_SPEC.replace(
        'BuildRequires:  perl(Module::Build)',
        'BuildRequires:  perl(Module::Build) >= 0.42',
    )
    assert _check_spec_build_perl(_write(tmp_path, content)) == []


def test_c2_capability_spelling_is_case_insensitive(tmp_path: Path) -> None:
    content = CLEAN_PERLBUILD_SPEC.replace(
        'perl(Module::Build)', 'perl(module::build)',
    )
    assert _check_spec_build_perl(_write(tmp_path, content)) == []


def test_c2_commented_module_does_not_count(tmp_path: Path) -> None:
    content = CLEAN_PERLBUILD_SPEC.replace(
        'BuildRequires:  perl(Module::Build)\n',
        '# BuildRequires:  perl(Module::Build)\n',
    )
    assert 'missing "perl(Module::Build)"' in _single_error(tmp_path, content)


def test_c2_both_systems_are_reported_separately(tmp_path: Path) -> None:
    content = CLEAN_PERLBUILD_SPEC.replace(
        'BuildSystem:    perlbuild',
        'BuildSystem:    perlbuild\nBuildSystem:    perlmaker',
    ).replace('BuildRequires:  perl(Module::Build)\n', '')
    messages = _messages(tmp_path, content)
    assert len(messages) == 2, messages
    assert any('perl(Module::Build)' in m for m in messages)
    assert any('perl(ExtUtils::MakeMaker)' in m for m in messages)


# --------------------------------------------------------------------------
# C5 - the %files section reads the generated file list.
# --------------------------------------------------------------------------


def test_c5_manual_file_list_is_reported(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        '%files -f %{name}.files',
        '%files\n%{perl_vendorarch}/auto/*\n%{perl_vendorarch}/Demo*',
    )
    assert 'does not read a generated file list' in _single_error(
        tmp_path, content,
    )


def test_c5_message_names_the_files_section_and_line(
    tmp_path: Path,
) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace('%files -f %{name}.files', '%files')
    message = _single_error(tmp_path, content)
    assert message.startswith('%files (line 17)')
    assert '%files -f %{name}.files' in message


def test_c5_other_file_list_name_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        '%files -f %{name}.files', '%files -f modules.files',
    )
    assert _check_spec_build_perl(_write(tmp_path, content)) == []


def test_c5_separate_f_flag_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        '%files -f %{name}.files', '%files -f %{name}.files -f extra.files',
    )
    assert _check_spec_build_perl(_write(tmp_path, content)) == []


def test_c5_files_body_alone_does_not_satisfy(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        '%files -f %{name}.files',
        '%files\n%{_bindir}/demo',
    )
    assert 'does not read a generated file list' in _single_error(
        tmp_path, content,
    )


def test_c5_spec_without_files_section_is_not_reported(
    tmp_path: Path,
) -> None:
    content = CLEAN_PERLMAKER_SPEC.split('%files')[0]
    assert _check_spec_build_perl(_write(tmp_path, content)) == []


def test_c5_subpackage_file_list_is_not_reported(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        '%files -f %{name}.files',
        '%package doc\n'
        'Summary:        Documentation\n'
        '\n'
        '%description doc\n'
        'Documentation.\n'
        '\n'
        '%files -f %{name}.files\n'
        '%doc README\n'
        '\n'
        '%files doc\n'
        '%{_docdir}/perl-Demo/README',
    )
    assert _check_spec_build_perl(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# The checkpoints combine.
# --------------------------------------------------------------------------


def test_all_three_checkpoints_can_fire_together(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC
    for pkg in ('perl-rpm-packaging', 'perl-rpm-macros', 'perl-macros'):
        content = content.replace(f'BuildRequires:  {pkg}\n', '')
    content = content.replace('BuildRequires:  perl(ExtUtils::MakeMaker)\n', '')
    content = content.replace('%files -f %{name}.files', '%files')
    assert len(_messages(tmp_path, content)) == 3


def test_repeated_findings_are_reported_once(tmp_path: Path) -> None:
    content = CLEAN_PERLMAKER_SPEC.replace(
        'BuildSystem:    perlmaker',
        'BuildSystem:    perlmaker\nBuildSystem:    perlmaker',
    )
    assert _check_spec_build_perl(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# Flags.
# --------------------------------------------------------------------------


def _broken_spec() -> str:
    content = CLEAN_PERLMAKER_SPEC
    for pkg in ('perl-rpm-packaging', 'perl-rpm-macros', 'perl-macros'):
        content = content.replace(f'BuildRequires:  {pkg}\n', '')
    content = content.replace('BuildRequires:  perl(ExtUtils::MakeMaker)\n', '')
    return content.replace('%files -f %{name}.files', '%files')


def test_flag_disables_c1(tmp_path: Path) -> None:
    errors = _check_spec_build_perl_ext(
        _write(tmp_path, _broken_spec()), check_shared_packages=False,
    )
    assert errors
    assert not any('shared Perl build dependencies' in err for err in errors)


def test_flag_disables_c2(tmp_path: Path) -> None:
    errors = _check_spec_build_perl_ext(
        _write(tmp_path, _broken_spec()), check_module=False,
    )
    assert errors
    assert not any('ExtUtils::MakeMaker' in err for err in errors)


def test_flag_disables_c5(tmp_path: Path) -> None:
    errors = _check_spec_build_perl_ext(
        _write(tmp_path, _broken_spec()), check_files_list=False,
    )
    assert errors
    assert not any('generated file list' in err for err in errors)


def test_all_flags_disabled_report_nothing(tmp_path: Path) -> None:
    assert _check_spec_build_perl_ext(
        _write(tmp_path, _broken_spec()),
        check_shared_packages=False,
        check_module=False,
        check_files_list=False,
    ) == []


# --------------------------------------------------------------------------
# main().
# --------------------------------------------------------------------------


def test_main_returns_zero_for_a_clean_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([_write(tmp_path, CLEAN_PERLMAKER_SPEC)]) == 0
    assert capsys.readouterr().out == ''


def test_main_returns_one_and_prints_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, _broken_spec())
    assert main([path]) == 1
    out = capsys.readouterr().out
    assert out.startswith(path)
    assert 'missing "perl(ExtUtils::MakeMaker)"' in out


def test_main_flag_disables_a_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, CLEAN_PERLMAKER_SPEC.replace(
        'BuildRequires:  perl(ExtUtils::MakeMaker)\n', '',
    ))
    assert main(['--no-check-module', path]) == 0
    assert capsys.readouterr().out == ''


def test_main_without_filenames_returns_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    assert capsys.readouterr().out == ''
