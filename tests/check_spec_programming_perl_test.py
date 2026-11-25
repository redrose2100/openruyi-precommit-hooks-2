# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check-spec-programming-perl."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks import check_spec_programming_perl as rule

CHECK = rule._check_spec_programming_perl
CHECK_EXT = rule._check_spec_programming_perl_ext


CLEAN_SPEC = """\
Name:           perl-Archive-Zip
Version:        1.68
Release:        %autorelease
Summary:        Provide an interface to ZIP archive files
License:        GPL-1.0-or-later OR Artistic-1.0-Perl
URL:            https://metacpan.org/dist/Archive-Zip
#!RemoteAsset:  sha256:984e185d785baf6129c6e75f8eb44411745ac00bf6122fb1c8e822a3861ec650
Source0:        https://www.cpan.org/authors/id/P/PH/PHRED/Archive-Zip-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    perlmaker

BuildOption(build):  INSTALLDIRS=vendor

BuildRequires:  make
BuildRequires:  perl-rpm-packaging
BuildRequires:  perl-rpm-macros
BuildRequires:  perl-macros
BuildRequires:  perl >= 5.6.0
BuildRequires:  perl(Compress::Raw::Zlib) >= 2.017
BuildRequires:  perl(ExtUtils::MakeMaker)
BuildRequires:  perl(File::Spec) >= 0.80

Requires:       perl(Compress::Raw::Zlib) >= 2.017
Requires:       perl(File::Spec) >= 0.80

%description
The Archive::Zip module allows a Perl program to create, manipulate, read,
and write Zip archive files.

%files -f %{name}.files
%doc Changes README.md

%changelog
%autochangelog
"""

MACRO_NAME_SPEC = """\
%define tarname Locale-gettext

Name:           perl-%{tarname}
Version:        1.07
Release:        %autorelease
Summary:        A Perl module for Native Language Support
License:        LGPL-2.0-or-later
URL:            https://metacpan.org/release/Locale-gettext
Source0:        https://cpan.metacpan.org/authors/id/P/PV/PVANDRY/%{tarname}-%{version}.tar.gz
BuildSystem:    perlmaker

BuildRequires:  perl-rpm-packaging
BuildRequires:  perl-rpm-macros
BuildRequires:  perl-macros
BuildRequires:  perl(ExtUtils::MakeMaker)

%description
Native Language Support for Perl.

%files -f %{name}.files
%doc COPYING README
"""

PLUS_NAME_SPEC = """\
Name:           perl-Text-Tabs-Wrap
Version:        2020.0901
Release:        %autorelease
Summary:        Expand tabs and wrap lines
License:        GPL-1.0-or-later OR Artistic-1.0-Perl
URL:            https://metacpan.org/dist/Text-Tabs%2BWrap
Source0:        https://www.cpan.org/authors/id/M/MT/MTHURN/Text-Tabs%2BWrap-%{version}.tar.gz
BuildSystem:    perlmaker

BuildRequires:  perl-rpm-packaging
BuildRequires:  perl-rpm-macros
BuildRequires:  perl-macros
BuildRequires:  perl(ExtUtils::MakeMaker)

%description
Expand tabs and wrap lines.

%files -f %{name}.files
%doc Changes
"""

SUBPACKAGE_SPEC = """\
Name:           perl-Demo-Module
Version:        1.0
Release:        %autorelease
Summary:        A demo Perl module
License:        GPL-1.0-or-later OR Artistic-1.0-Perl
URL:            https://metacpan.org/dist/Demo-Module
Source0:        https://www.cpan.org/authors/id/D/DE/DEMO/Demo-Module-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    perlmaker
BuildRequires:  perl-rpm-packaging
BuildRequires:  perl-rpm-macros
BuildRequires:  perl-macros
BuildRequires:  perl(ExtUtils::MakeMaker)

%description
A demo Perl module.

%package     -n perl-Demo-Module-Extra
Summary:        The optional extra helpers
License:        GPL-1.0-or-later OR Artistic-1.0-Perl

%description -n perl-Demo-Module-Extra
The optional extra helpers.

%files -f %{name}.files
%doc Changes

%files -n perl-Demo-Module-Extra
%{perl_vendorlib}/Demo/Module/Extra.pm
"""

NON_CPAN_SPEC = """\
Name:           po4a
Version:        0.71
Release:        %autorelease
Summary:        Tools to translate documentation
License:        GPL-2.0-or-later
URL:            https://po4a.org/
Source0:        https://github.com/mquinson/po4a/releases/download/v%{version}/po4a-%{version}.tar.gz
BuildSystem:    perlbuild

BuildRequires:  perl-rpm-packaging
BuildRequires:  perl-rpm-macros
BuildRequires:  perl-macros
BuildRequires:  perl(ExtUtils::MakeMaker)

%description
Tools to translate documentation.

%files -f %{name}.files
%doc README.md
"""

OTHER_LANGUAGE_SPEC = """\
Name:           kubectl
Version:        1.31.0
Release:        %autorelease
Summary:        Command line tool for Kubernetes
License:        Apache-2.0
URL:            https://github.com/kubernetes/kubernetes
Source0:        https://github.com/kubernetes/kubernetes/archive/v%{version}.tar.gz
BuildSystem:    golang

BuildRequires:  go
BuildRequires:  go-rpm-macros

%description
The Kubernetes command line tool.

%build
make all

%files
%{_bindir}/kubectl
"""

NON_DECLARATIVE_SPEC = """\
Name:           perl-Legacy-Build
Version:        1.0
Release:        %autorelease
Summary:        A Perl module built by hand
License:        GPL-1.0-or-later OR Artistic-1.0-Perl
URL:            https://metacpan.org/dist/Legacy-Build
Source0:        https://www.cpan.org/authors/id/L/LE/LEGACY/Legacy-Build-%{version}.tar.gz

BuildRequires:  perl(ExtUtils::MakeMaker)
BuildRequires:  perl-devel

%description
A Perl module built by hand.

%prep
%setup -q

%build
%{__perl} Makefile.PL INSTALLDIRS=vendor
make

%install
make install DESTDIR=%{buildroot}

%files
%{perl_vendorlib}/Legacy/Build.pm
"""


def _write(tmp_path: Path, content: str, name: str = 'demo.spec') -> str:
    path = tmp_path / name
    path.write_text(content, encoding='utf-8')
    return str(path)


def _messages(tmp_path: Path, content: str) -> list[str]:
    return [
        err.split(': ', 1)[1]
        for err in CHECK(_write(tmp_path, content))
    ]


def _single_error(tmp_path: Path, content: str) -> str:
    messages = _messages(tmp_path, content)
    assert len(messages) == 1, messages
    return messages[0]


# --------------------------------------------------------------------------
# Scope - a spec that packages a Perl module is judged, anything else is not.
# --------------------------------------------------------------------------


def test_clean_spec_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, CLEAN_SPEC)) == []


def test_macro_spelled_name_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, MACRO_NAME_SPEC)) == []


def test_plus_in_distribution_name_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, PLUS_NAME_SPEC)) == []


def test_subpackage_spec_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, SUBPACKAGE_SPEC)) == []


def test_non_cpan_perl_project_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, NON_CPAN_SPEC)) == []


def test_other_language_spec_is_ignored(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, OTHER_LANGUAGE_SPEC)) == []


def test_non_declarative_build_is_still_judged(tmp_path: Path) -> None:
    content = NON_DECLARATIVE_SPEC.replace(
        'BuildRequires:  perl(ExtUtils::MakeMaker)',
        'BuildRequires:  perl(ExtUtils::MakeMaker)\n'
        'BuildRequires:  perl-File-Copy',
    )
    message = _single_error(tmp_path, content)
    assert 'perl(File::Copy)' in message


def test_unreadable_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'broken.spec'
    path.write_bytes(b'Name: \xff\xfe\n')
    errors = CHECK(str(path))
    assert len(errors) == 1
    assert 'not valid UTF-8' in errors[0]


# --------------------------------------------------------------------------
# C1 - the package name is derived from the CPAN distribution.
# --------------------------------------------------------------------------


def test_misspelled_name_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Name:           perl-Archive-Zip',
        'Name:           perl-Archive-Zipper',
    )
    message = _single_error(tmp_path, content)
    assert 'package naming rule' in message
    assert 'perl-Archive-Zip' in message


def test_name_without_perl_prefix_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Name:           perl-Archive-Zip',
        'Name:           Archive-Zip',
    )
    message = _single_error(tmp_path, content)
    assert 'package naming rule' in message


def test_name_is_not_judged_without_a_metacpan_distribution(
    tmp_path: Path,
) -> None:
    content = NON_CPAN_SPEC.replace('Name:           po4a', 'Name:           p04a')
    assert CHECK(_write(tmp_path, content)) == []


def test_version_suffix_of_a_release_url_is_not_a_name_finding(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'URL:            https://metacpan.org/dist/Archive-Zip',
        'URL:            https://metacpan.org/release/Archive-Zip-1.68',
    )
    message = _single_error(tmp_path, content)
    assert 'pins the distribution version' in message
    assert 'package naming rule' not in message


def test_subpackage_name_is_reported(tmp_path: Path) -> None:
    content = SUBPACKAGE_SPEC.replace(
        '%package     -n perl-Demo-Module-Extra',
        '%package     -n perl-Demo-Extra',
    )
    message = _single_error(tmp_path, content)
    assert 'package naming rule' in message
    assert 'perl-Demo-Module-Something' in message


def test_package_name_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Name:           perl-Archive-Zip',
        'Name:           perl-Archive-Zipper',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_package_name=False,
    ) == []


# --------------------------------------------------------------------------
# C2 - a CPAN package uses a non-versioned metacpan URL.
# --------------------------------------------------------------------------


def test_project_url_of_a_cpan_package_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'URL:            https://metacpan.org/dist/Archive-Zip',
        'URL:            https://archivezip.example.org/',
    )
    message = _single_error(tmp_path, content)
    assert 'is not a metacpan URL' in message


def test_versioned_metacpan_url_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'URL:            https://metacpan.org/dist/Archive-Zip',
        'URL:            https://metacpan.org/release/Archive-Zip-1.68',
    )
    message = _single_error(tmp_path, content)
    assert 'pins the distribution version' in message


def test_release_url_without_a_version_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'URL:            https://metacpan.org/dist/Archive-Zip',
        'URL:            https://metacpan.org/release/Archive-Zip',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_url_of_a_non_cpan_source_is_not_judged(tmp_path: Path) -> None:
    content = NON_CPAN_SPEC.replace(
        'URL:            https://po4a.org/',
        'URL:            https://example.org/anything',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_url_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'URL:            https://metacpan.org/dist/Archive-Zip',
        'URL:            https://archivezip.example.org/',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_url=False,
    ) == []


# --------------------------------------------------------------------------
# C3 - a declarative package declares the three shared macro packages.
# --------------------------------------------------------------------------


@pytest.mark.parametrize('package', rule.SHARED_PACKAGES)
def test_missing_shared_package_is_reported(
    tmp_path: Path, package: str,
) -> None:
    content = CLEAN_SPEC.replace(f'BuildRequires:  {package}\n', '')
    message = _single_error(tmp_path, content)
    assert 'missing' in message
    assert package in message


def test_versioned_shared_package_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  perl-macros\n',
        'BuildRequires:  perl-macros >= 1.0\n',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_non_declarative_build_does_not_need_shared_packages(
    tmp_path: Path,
) -> None:
    assert CHECK(_write(tmp_path, NON_DECLARATIVE_SPEC)) == []


def test_shared_package_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  perl-macros\n', '')
    assert CHECK_EXT(
        _write(tmp_path, content), check_shared_packages=False,
    ) == []


# --------------------------------------------------------------------------
# C4 - a build dependency on a module uses the perl(MODULE) form.
# --------------------------------------------------------------------------


def test_bare_build_dependency_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  perl(ExtUtils::MakeMaker)',
        'BuildRequires:  perl-ExtUtils-MakeMaker',
    )
    message = _single_error(tmp_path, content)
    assert 'perl(ExtUtils::MakeMaker)' in message


def test_core_perl_dependency_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  perl >= 5.6.0',
        'BuildRequires:  perl >= 5.6.0\nBuildRequires:  perl-devel',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_shared_macro_package_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  make\n',
        'BuildRequires:  make\nBuildRequires:  perl-libs\n',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_build_module_form_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  perl(ExtUtils::MakeMaker)',
        'BuildRequires:  perl-ExtUtils-MakeMaker',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_build_module_form=False,
    ) == []


# --------------------------------------------------------------------------
# C5 - Requires and Provides use the perl(MODULE) form.
# --------------------------------------------------------------------------


def test_bare_requires_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Requires:       perl(File::Spec) >= 0.80',
        'Requires:       perl-File-Spec >= 0.80',
    )
    message = _single_error(tmp_path, content)
    assert 'Requires' in message
    assert 'perl(File::Spec)' in message


def test_bare_provides_is_reported(tmp_path: Path) -> None:
    content = SUBPACKAGE_SPEC.replace(
        '%package     -n perl-Demo-Module-Extra\n',
        '%package     -n perl-Demo-Module-Extra\n'
        'Provides:       perl-Demo-Module-Extra = %{version}\n',
    )
    message = _single_error(tmp_path, content)
    assert 'Provides' in message
    assert 'perl(Demo::Module::Extra)' in message


def test_devel_requires_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Requires:       perl(File::Spec) >= 0.80',
        'Requires:       perl(File::Spec) >= 0.80\nRequires:       perl-devel',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_runtime_capability_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Requires:       perl(File::Spec) >= 0.80',
        'Requires:       perl-File-Spec >= 0.80',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_runtime_capability=False,
    ) == []


# --------------------------------------------------------------------------
# C6 - a declarative package does not hand-write its build stages.
# --------------------------------------------------------------------------


@pytest.mark.parametrize('stage', rule.DECLARATIVE_STAGES)
def test_hand_written_stage_is_reported(tmp_path: Path, stage: str) -> None:
    content = CLEAN_SPEC.replace(
        '%files -f %{name}.files',
        f'{stage}\nmake\n\n%files -f %{{name}}.files',
    )
    message = _single_error(tmp_path, content)
    assert f'{stage} (' in message
    assert 'hand-written stage' in message


def test_empty_stage_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%files -f %{name}.files',
        '%install\n\n%files -f %{name}.files',
    )
    message = _single_error(tmp_path, content)
    assert 'hand-written stage' in message


def test_macro_invocation_is_not_a_stage(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%files -f %{name}.files',
        '%files -f %{name}.files\n%license COPYING',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_non_declarative_stage_is_not_reported(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, NON_DECLARATIVE_SPEC)) == []


def test_declarative_stages_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%files -f %{name}.files',
        '%build\nmake\n\n%files -f %{name}.files',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_declarative_stages=False,
    ) == []


# --------------------------------------------------------------------------
# C7 - the main file list reads a generated file list.
# --------------------------------------------------------------------------


def test_hand_written_main_filelist_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%files -f %{name}.files',
        '%files\n%{perl_vendorlib}/Archive/Zip.pm',
    )
    message = _single_error(tmp_path, content)
    assert 'does not read a generated file list' in message


def test_other_generated_filelist_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%files -f %{name}.files',
        '%files -f %{name}-main.files',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_missing_filelist_section_is_not_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('%files -f %{name}.files\n', '')
    assert CHECK(_write(tmp_path, content)) == []


def test_generated_filelist_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%files -f %{name}.files',
        '%files\n%{perl_vendorlib}/Archive/Zip.pm',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_generated_filelist=False,
    ) == []


# --------------------------------------------------------------------------
# C8 - header files of a module stay in the module package.
# --------------------------------------------------------------------------


def test_header_in_a_devel_subpackage_is_reported(tmp_path: Path) -> None:
    content = SUBPACKAGE_SPEC.replace(
        '%package     -n perl-Demo-Module-Extra',
        '%package     -n perl-Demo-Module-devel',
    ).replace(
        '%{perl_vendorlib}/Demo/Module/Extra.pm',
        '%{_includedir}/Demo/Module.h',
    )
    message = _single_error(tmp_path, content)
    assert 'header file in a -devel subpackage' in message


def test_plain_header_path_is_reported(tmp_path: Path) -> None:
    content = SUBPACKAGE_SPEC.replace(
        '%package     -n perl-Demo-Module-Extra',
        '%package     -n perl-Demo-Module-devel',
    ).replace(
        '%{perl_vendorlib}/Demo/Module/Extra.pm',
        '/usr/share/Demo/Module.h',
    )
    message = _single_error(tmp_path, content)
    assert 'header file in a -devel subpackage' in message


def test_module_file_in_a_devel_subpackage_is_accepted(
    tmp_path: Path,
) -> None:
    content = SUBPACKAGE_SPEC.replace(
        '%package     -n perl-Demo-Module-Extra',
        '%package     -n perl-Demo-Module-devel',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_header_of_the_main_package_is_not_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%doc Changes README.md',
        '%doc Changes README.md\n%{_includedir}/Archive/Zip.h',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_devel_headers_checker_can_be_disabled(tmp_path: Path) -> None:
    content = SUBPACKAGE_SPEC.replace(
        '%package     -n perl-Demo-Module-Extra',
        '%package     -n perl-Demo-Module-devel',
    ).replace(
        '%{perl_vendorlib}/Demo/Module/Extra.pm',
        '%{_includedir}/Demo/Module.h',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_devel_headers=False,
    ) == []


# --------------------------------------------------------------------------
# Entry point - the command line returns 1 on a finding and 0 otherwise.
# --------------------------------------------------------------------------


def test_main_returns_zero_for_a_clean_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert rule.main([_write(tmp_path, CLEAN_SPEC)]) == 0
    assert capsys.readouterr().out == ''


def test_main_returns_one_and_prints_the_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  perl-macros\n', '')
    assert rule.main([_write(tmp_path, content)]) == 1
    assert 'missing perl-macros' in capsys.readouterr().out


def test_main_renders_the_help_text(capsys: pytest.CaptureFixture[str]) -> None:
    # A '%' in an argparse help string must be escaped as '%%', otherwise
    # print_help raises TypeError once the user asks for the usage text.
    with pytest.raises(SystemExit):
        rule.main(['--help'])
    out = capsys.readouterr().out
    assert '--no-check-generated-filelist' in out
    # The rendered help must show a literal '%', not the '%%' escape.
    assert 'section without -f' in out
    assert '%%files' not in out


def test_main_reports_nothing_for_an_ignored_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert rule.main([_write(tmp_path, OTHER_LANGUAGE_SPEC)]) == 0
    assert capsys.readouterr().out == ''


def test_main_disables_a_checkpoint(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  perl-macros\n', '')
    assert rule.main(
        ['--no-check-shared-packages', _write(tmp_path, content)],
    ) == 0
