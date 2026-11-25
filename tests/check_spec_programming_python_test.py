"""Tests for check-spec-programming-python."""
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks import check_spec_programming_python as rule

CHECK = rule._check_spec_programming_python
CHECK_EXT = rule._check_spec_programming_python_ext


CLEAN_SPEC = """\
%global srcname requests

Name:           python-%{srcname}
Version:        2.32.3
Release:        %autorelease
Summary:        Python HTTP for Humans
License:        Apache-2.0
URL:            https://requests.readthedocs.io/
Source0:        %{pypi_source %{srcname}}
BuildArch:      noarch
BuildSystem:    pyproject

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3dist(pytest)

Provides:       python3-%{srcname} = %{version}-%{release}
%python_provide python3-%{srcname}

%description
Python HTTP for Humans.

%prep
%autosetup -p1 -n %{srcname}-%{version}

%generate_buildrequires
%pyproject_buildrequires -t

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files %{srcname}

%files -f %{pyproject_files}
%{python3_sitelib}/requests
%doc README.md

%changelog
%autochangelog
"""

TOOL_SPEC = """\
Name:           mkosi
Version:        22
Release:        %autorelease
Summary:        Build Bespoke OS Images
License:        LGPL-2.1-or-later
URL:            https://github.com/systemd/mkosi
Source0:        https://github.com/systemd/mkosi/archive/v%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    pyproject

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel

%description
Build Bespoke OS Images.

%prep
%autosetup

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files mkosi

%files -f %{pyproject_files}
%{_bindir}/mkosi

%changelog
%autochangelog
"""

UNPREFIXED_SPEC = """\
Name:           dblatex
Version:        0.3.12
Release:        %autorelease
Summary:        DocBook to LaTeX transform
License:        GPL-2.0-or-later
URL:            https://dblatex.sourceforge.net/
Source0:        https://downloads.sourceforge.net/dblatex/dblatex-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    pyproject

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel

%description
DocBook to LaTeX transform.

%prep
%autosetup

%install
%pyproject_install
%pyproject_save_files dblatex

%files -f %{pyproject_files}
%{_bindir}/dblatex
%{python3_sitelib}/dblatex

%changelog
%autochangelog
"""

CMAKE_SPEC = """\
Name:           ceph
Version:        19.2.0
Release:        %autorelease
Summary:        Distributed object store
License:        LGPL-2.1-only
URL:            https://ceph.io/
Source0:        https://download.ceph.com/tarballs/ceph-%{version}.tar.gz
BuildSystem:    cmake

BuildRequires:  cmake
BuildRequires:  python3-devel
Requires:       python3

%description
Distributed object store.

%files
%{python3_sitelib}/ceph
"""

GOLANG_SPEC = """\
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
Requires:       python3

%description
The Kubernetes command line tool.

%build
make all

%files
%{_bindir}/kubectl
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
# Scope - only a spec that declares BuildSystem: pyproject is judged.
# --------------------------------------------------------------------------


def test_clean_spec_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, CLEAN_SPEC)) == []


def test_cmake_package_with_python_bindings_is_ignored(tmp_path: Path) -> None:
    # ceph installs into %{python3_sitelib} but builds with cmake, so it is
    # a C++ package that merely ships Python bindings.
    assert CHECK(_write(tmp_path, CMAKE_SPEC)) == []


def test_other_language_spec_is_ignored(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, GOLANG_SPEC)) == []


def test_unreadable_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'broken.spec'
    path.write_bytes(b'Name: \xff\xfe\n')
    errors = CHECK(str(path))
    assert len(errors) == 1
    assert 'not valid UTF-8' in errors[0]


def test_missing_file_is_reported(tmp_path: Path) -> None:
    errors = CHECK(str(tmp_path / 'absent.spec'))
    assert len(errors) == 1
    assert 'absent.spec' in errors[0]


# --------------------------------------------------------------------------
# C1 - a package that ships modules carries the python- prefix.
# --------------------------------------------------------------------------


def test_unprefixed_library_name_is_reported(tmp_path: Path) -> None:
    messages = _messages(tmp_path, UNPREFIXED_SPEC)
    assert any('does not carry the python- prefix' in item for item in messages)
    assert any('python-dblatex' in item for item in messages)


def test_unprefixed_library_also_lacks_the_capability(tmp_path: Path) -> None:
    messages = _messages(tmp_path, UNPREFIXED_SPEC)
    assert any('provides no "python3-" capability' in item
               for item in messages)


def test_unprefixed_tool_name_is_not_reported(tmp_path: Path) -> None:
    # mkosi ships a program rather than a module, so the naming clause and
    # the capability clause do not apply to it.
    assert CHECK(_write(tmp_path, TOOL_SPEC)) == []


def test_prefixed_name_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, CLEAN_SPEC)) == []


def test_prefixed_name_without_a_macro_passes(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Name:           python-%{srcname}', 'Name:           python-requests',
    ).replace('%global srcname requests\n', '')
    messages = _messages(tmp_path, content)
    assert all('python- prefix' not in item for item in messages), messages


def test_name_checker_can_be_disabled(tmp_path: Path) -> None:
    assert CHECK_EXT(
        _write(tmp_path, UNPREFIXED_SPEC),
        check_package_name=False,
        check_python3_provides=False,
    ) == []


# --------------------------------------------------------------------------
# C2 - a python- named package defines the srcname macro.
# --------------------------------------------------------------------------


def test_missing_srcname_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('%global srcname requests\n', '')
    messages = _messages(tmp_path, content)
    assert any('without a srcname macro' in item for item in messages), (
        messages
    )


def test_srcname_checker_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('%global srcname requests\n', '')
    errors = CHECK_EXT(
        _write(tmp_path, content), check_srcname=False,
    )
    assert all('srcname macro' not in err for err in errors)


def test_unprefixed_name_is_not_asked_for_srcname(tmp_path: Path) -> None:
    # The page asks for srcname on a library package, so an unprefixed tool
    # keeps its silence here even though it ships modules.
    content = UNPREFIXED_SPEC.replace(
        'Name:           dblatex', 'Name:           dblatex',
    )
    errors = CHECK_EXT(
        _write(tmp_path, content),
        check_package_name=False,
        check_python3_provides=False,
    )
    assert all('srcname' not in err for err in errors)


# --------------------------------------------------------------------------
# C3 - the srcname macro carries a PEP 503 normalised name.
# --------------------------------------------------------------------------


@pytest.mark.parametrize('spelling', [
    'PyYAML',
    'ruamel.yaml',
    'boolean.py',
    'aiohttp_socks',
    'Browser-Use',
])
def test_non_normalised_srcname_is_reported(
    tmp_path: Path, spelling: str,
) -> None:
    content = CLEAN_SPEC.replace(
        '%global srcname requests', f'%global srcname {spelling}',
    )
    messages = [
        item for item in _messages(tmp_path, content)
        if 'PEP 503' in item
    ]
    assert len(messages) == 1, messages
    assert 'not PEP 503 normalised' in messages[0]


@pytest.mark.parametrize('spelling', [
    'requests',
    'aiohttp-socks',
    'annotated-types',
    'ruamel-yaml',
    'python-dateutil-2',
])
def test_normalised_srcname_passes(tmp_path: Path, spelling: str) -> None:
    content = CLEAN_SPEC.replace(
        '%global srcname requests', f'%global srcname {spelling}',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_quoted_srcname_is_still_judged(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%global srcname requests', '%global srcname "PyYAML"',
    )
    messages = [
        item for item in _messages(tmp_path, content)
        if 'PEP 503' in item
    ]
    assert len(messages) == 1, messages


def test_srcname_macro_line_number_is_quoted(tmp_path: Path) -> None:
    message = _single_error(
        tmp_path,
        CLEAN_SPEC.replace(
            '%global srcname requests', '%global srcname PyYAML',
        ),
    )
    assert '(line 1)' in message


def test_srcname_normalisation_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%global srcname requests', '%global srcname PyYAML',
    )
    errors = CHECK_EXT(
        _write(tmp_path, content), check_srcname_normalised=False,
    )
    assert all('PEP 503' not in err for err in errors)


def test_undefined_srcname_spelling_is_handled(tmp_path: Path) -> None:
    # The macro is absent, so C3 stays silent and C2 reports instead.
    content = CLEAN_SPEC.replace('%global srcname requests\n', '')
    assert any(
        'srcname macro' in item for item in _messages(tmp_path, content)
    )


# --------------------------------------------------------------------------
# C4 - a package that ships modules provides a python3- capability.
# --------------------------------------------------------------------------


def test_missing_python3_provide_is_reported(tmp_path: Path) -> None:
    # The unprefixed fixture omits the runtime clause on purpose, so the
    # capability finding is the one being pinned here.
    content = UNPREFIXED_SPEC
    messages = _messages(tmp_path, content)
    assert any('provides no "python3-" capability' in item
               for item in messages), messages
    assert all('explicit runtime dependency' not in item
               for item in messages), messages


def test_missing_capability_is_reported(tmp_path: Path) -> None:
    content = TOOL_SPEC.replace(
        '%files -f %{pyproject_files}',
        '%files -f %{pyproject_files}\n%{python3_sitelib}/mkosi',
    )
    messages = _messages(tmp_path, content)
    assert any('provides no "python3-" capability' in item
               for item in messages), messages
    assert any('python3-mkosi' in item for item in messages), messages


def test_python_provide_macro_alone_is_enough(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Provides:       python3-%{srcname} = %{version}-%{release}\n',
        '',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_provides_field_alone_is_enough(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('%python_provide python3-%{srcname}\n', '')
    assert CHECK(_write(tmp_path, content)) == []


def test_tool_without_a_capability_is_not_reported(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, TOOL_SPEC)) == []


def test_capability_is_not_required_for_cmake_specs(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, CMAKE_SPEC)) == []


def test_python3_provides_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Provides:       python3-%{srcname} = %{version}-%{release}\n',
        '',
    ).replace('%python_provide python3-%{srcname}\n', '')
    assert CHECK_EXT(
        _write(tmp_path, content), check_python3_provides=False,
    ) == []


def test_capability_from_a_subpackage_is_accepted(tmp_path: Path) -> None:
    # The page asks the main package for the capability, but a spec that
    # moves it into a subpackage still declares it, so the clause is met
    # and the rule stays silent instead of arguing about the placement.
    content = CLEAN_SPEC.replace(
        'Provides:       python3-%{srcname} = %{version}-%{release}\n',
        '',
    ).replace('%python_provide python3-%{srcname}\n', '')
    content += (
        '\n%package -n python3-%{srcname}-extra\n'
        'Summary:        Extra files\n'
        'Provides:       python3-%{srcname}-extra\n'
    )
    assert CHECK(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# C5 - a package does not declare an explicit dependency on python3.
# --------------------------------------------------------------------------


def test_bare_python3_requires_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%description\n',
        'Requires:       python3 >= 3.9\n\n%description\n',
    )
    message = _single_error(tmp_path, content)
    assert 'explicit runtime dependency on python3' in message
    assert '(line ' in message


def test_bare_python3_field_is_reported_even_for_a_tool(
    tmp_path: Path,
) -> None:
    # mkosi ships a program, so C1 and C4 stay silent, but the clause about
    # an explicit runtime dependency applies to it all the same.
    content = TOOL_SPEC.replace(
        '%description\n', 'Requires:       python3\n\n%description\n',
    )
    message = _single_error(tmp_path, content)
    assert 'explicit runtime dependency on python3' in message


def test_python3_with_a_version_is_reported(tmp_path: Path) -> None:
    content = TOOL_SPEC.replace(
        '%description\n', 'Requires:       python3 >= 3.9\n\n%description\n',
    )
    message = _single_error(tmp_path, content)
    assert 'explicit runtime dependency on python3' in message


@pytest.mark.parametrize('field', [
    'Requires:       python3-devel',
    'Requires:       python3dist(requests)',
    'Requires:       python3dist(requests) >= 2.0',
    'Requires:       python(abi) = 3.11',
    'Requires:       python3-libs',
])
def test_other_dependency_spellings_pass(tmp_path: Path, field: str) -> None:
    content = TOOL_SPEC.replace(
        '%description\n', f'{field}\n\n%description\n',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_rich_dependency_with_python3_passes(tmp_path: Path) -> None:
    content = TOOL_SPEC.replace(
        '%description\n',
        'Requires:       (python3 >= 3.9 with python3-devel)\n\n%description\n',
    )
    assert CHECK(_write(tmp_path, content)) == []


def test_runtime_requires_can_be_disabled(tmp_path: Path) -> None:
    content = TOOL_SPEC.replace(
        '%description\n', 'Requires:       python3\n\n%description\n',
    )
    assert CHECK_EXT(
        _write(tmp_path, content), check_python3_requires=False,
    ) == []


def test_build_requires_on_python3_is_not_the_runtime_clause(
    tmp_path: Path,
) -> None:
    content = TOOL_SPEC.replace(
        'BuildRequires:  python3-devel',
        'BuildRequires:  python3-devel\nBuildRequires:  python3 >= 3.9',
    )
    assert CHECK(_write(tmp_path, content)) == []


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
    assert rule.main([_write(tmp_path, UNPREFIXED_SPEC)]) == 1
    out = capsys.readouterr().out
    assert 'python- prefix' in out
    assert 'provides no "python3-" capability' in out


def test_main_renders_the_help_text(capsys: pytest.CaptureFixture[str]) -> None:
    # A '%' in an argparse help string must be escaped as '%%', otherwise
    # print_help raises TypeError once the user asks for the usage text.
    with pytest.raises(SystemExit):
        rule.main(['--help'])
    out = capsys.readouterr().out
    assert '--no-check-python3-provides' in out
    assert '--no-check-python3-requires' in out
    assert '%%' not in out


def test_main_reports_nothing_for_an_ignored_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert rule.main([_write(tmp_path, CMAKE_SPEC)]) == 0
    assert capsys.readouterr().out == ''


def test_main_disables_a_checkpoint(tmp_path: Path) -> None:
    content = TOOL_SPEC.replace(
        '%description\n', 'Requires:       python3\n\n%description\n',
    )
    assert rule.main(
        ['--no-check-python3-requires', _write(tmp_path, content)],
    ) == 0


def test_main_disables_two_checkpoints(tmp_path: Path) -> None:
    assert rule.main([
        '--no-check-package-name',
        '--no-check-python3-provides',
        _write(tmp_path, UNPREFIXED_SPEC),
    ]) == 0
