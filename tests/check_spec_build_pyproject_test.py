# flake8: noqa: E501  -- spec file contents are reproduced verbatim
"""Tests for check-spec-build-pyproject."""
from __future__ import annotations

from pathlib import Path

from openruyi_precommit_hooks.check_spec_build_pyproject import (
    _check_spec_build_pyproject,
)
from openruyi_precommit_hooks.check_spec_build_pyproject import (
    _check_spec_build_pyproject_ext,
)
from openruyi_precommit_hooks.check_spec_build_pyproject import main


CLEAN_SPEC = """\
Name:           python-example
Version:        1.0
Release:        %autorelease
Summary:        An example module
License:        MIT
URL:            https://example.org/example
Source0:        https://example.org/example/example-1.0.tar.gz
BuildArch:      noarch
BuildSystem:    pyproject
BuildOption(install):  -l example
BuildRequires:  pyproject-rpm-macros
BuildRequires:  pkgconfig(python3)
BuildRequires:  python3dist(setuptools)

%description
An example module.

%generate_buildrequires
%pyproject_buildrequires

%check
# No module named 'marray'
BuildOption(check):  -e 'example.tests*'

%files -f %{pyproject_files}
"""

CLEAN_PYTHON_DEVEL_SPEC = """\
Name:           python-example
Version:        1.0
Release:        %autorelease
Summary:        An example module
License:        MIT
URL:            https://example.org/example
Source0:        https://example.org/example/example-1.0.tar.gz
BuildSystem:    pyproject
BuildOption(install):  %{srcname}
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel

%description
An example module.

%files -f %{pyproject_files}
%{_bindir}/example
"""

CLEAN_PKGCONFIG_PYTHON_SPEC = """\
Name:           python-example
Version:        1.0
Release:        %autorelease
Summary:        An example module
License:        MIT
URL:            https://example.org/example
Source0:        https://example.org/example/example-1.0.tar.gz
BuildSystem:    pyproject
BuildOption(install):  -l example +auto
BuildRequires:  pyproject-rpm-macros
BuildRequires:  pkgconfig(python)

%description
An example module.

%files -f %{pyproject_files}
"""

NOT_PYPROJECT_SPEC = """\
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
BuildRequires:  pyproject-rpm-macros

%description
A demo package.

%files
%{_bindir}/demo
"""


def _write(tmp_path: Path, content: str, name: str = 'demo.spec') -> str:
    path = tmp_path / name
    path.write_text(content, encoding='utf-8')
    return str(path)


def _messages(tmp_path: Path, content: str) -> list[str]:
    return [
        err.split(': ', 1)[1]
        for err in _check_spec_build_pyproject(_write(tmp_path, content))
    ]


def _single_error(tmp_path: Path, content: str) -> str:
    messages = _messages(tmp_path, content)
    assert len(messages) == 1, messages
    return messages[0]


# --------------------------------------------------------------------------
# Scope - only a spec that declares the pyproject build system is judged.
# --------------------------------------------------------------------------


def test_clean_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_build_pyproject(_write(tmp_path, CLEAN_SPEC)) == []


def test_python3_devel_satisfies_python_devel(tmp_path: Path) -> None:
    assert _check_spec_build_pyproject(
        _write(tmp_path, CLEAN_PYTHON_DEVEL_SPEC),
    ) == []


def test_pkgconfig_python_satisfies_python_devel(tmp_path: Path) -> None:
    assert _check_spec_build_pyproject(
        _write(tmp_path, CLEAN_PKGCONFIG_PYTHON_SPEC),
    ) == []


def test_other_build_system_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_pyproject(
        _write(tmp_path, NOT_PYPROJECT_SPEC),
    ) == []


def test_spec_without_build_system_is_ignored(tmp_path: Path) -> None:
    assert _check_spec_build_pyproject(
        _write(tmp_path, NO_BUILD_SYSTEM_SPEC),
    ) == []


# --------------------------------------------------------------------------
# C1 - the pyproject macro package.
# --------------------------------------------------------------------------


def test_missing_macros_package_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildRequires:  pyproject-rpm-macros\n', '')
    message = _single_error(tmp_path, content)
    assert 'requires "pyproject-rpm-macros" in BuildRequires' in message
    assert 'line 9' in message


def test_macros_package_with_version_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  pyproject-rpm-macros',
        'BuildRequires:  pyproject-rpm-macros >= 1.0',
    )
    assert _check_spec_build_pyproject(_write(tmp_path, content)) == []


def test_macros_package_in_comma_list_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  pyproject-rpm-macros',
        'BuildRequires:  pyproject-rpm-macros, python3dist(pip)',
    )
    assert _check_spec_build_pyproject(_write(tmp_path, content)) == []


def test_commented_out_macros_package_does_not_count(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  pyproject-rpm-macros',
        '# BuildRequires:  pyproject-rpm-macros',
    )
    message = _single_error(tmp_path, content)
    assert 'pyproject-rpm-macros' in message


def test_macros_package_in_subpackage_counts(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  pyproject-rpm-macros\n',
        '',
    ).replace(
        '%description\n',
        '%package sub\nSummary: A subpackage\n'
        'BuildRequires:  pyproject-rpm-macros\n\n%description\n',
    )
    assert _check_spec_build_pyproject(_write(tmp_path, content)) == []


def test_macros_package_with_similar_name_does_not_count(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  pyproject-rpm-macros',
        'BuildRequires:  python3-pyproject-rpm-macros',
    )
    message = _single_error(tmp_path, content)
    assert 'pyproject-rpm-macros' in message


# --------------------------------------------------------------------------
# C2 - the Python development dependency.
# --------------------------------------------------------------------------


def test_missing_python_devel_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  pkgconfig(python3)\n',
        '',
    )
    message = _single_error(tmp_path, content)
    assert 'Python development dependency' in message
    assert 'pkgconfig(python3)' in message
    assert 'missing pkgconfig(python3), pkgconfig(python)' in message


def test_python3_devel_similar_name_does_not_count(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  pkgconfig(python3)',
        'BuildRequires:  python3-devel-extra',
    )
    message = _single_error(tmp_path, content)
    assert 'Python development dependency' in message


def test_python310_devel_does_not_count(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildRequires:  pkgconfig(python3)',
        'BuildRequires:  python3.10-devel',
    )
    message = _single_error(tmp_path, content)
    assert 'Python development dependency' in message


# --------------------------------------------------------------------------
# C3 - the module name passed to the install stage.
# --------------------------------------------------------------------------


def test_missing_install_option_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('BuildOption(install):  -l example\n', '')
    message = _single_error(tmp_path, content)
    assert 'requires the module name to install' in message


def test_explicit_save_files_satisfies_install_option(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(install):  -l example\n',
        '',
    ).replace(
        '%check\n',
        '%install\n%pyproject_install\n'
        '%pyproject_save_files example\n\n%check\n',
    )
    assert _check_spec_build_pyproject(_write(tmp_path, content)) == []


def test_install_option_only_flags_does_not_satisfy_c3(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(install):  -l example',
        'BuildOption(install):  -l',
    )
    message = _single_error(tmp_path, content)
    assert 'carries only options' in message
    assert 'line 10' in message


# --------------------------------------------------------------------------
# C4 - BuildOption(install) must name a module.
# --------------------------------------------------------------------------


def test_install_option_with_auto_only_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(install):  -l example',
        'BuildOption(install):  +auto',
    )
    message = _single_error(tmp_path, content)
    assert 'carries only options' in message


def test_install_option_with_module_and_flags_is_accepted(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(install):  -l example',
        'BuildOption(install):  -l example +auto',
    )
    assert _check_spec_build_pyproject(_write(tmp_path, content)) == []


def test_install_option_with_macro_module_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'BuildOption(install):  -l example',
        'BuildOption(install):  -l %{srcname}',
    )
    assert _check_spec_build_pyproject(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# C5 - an empty %check.
# --------------------------------------------------------------------------


def test_empty_check_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        "%check\n# No module named 'marray'\n"
        "BuildOption(check):  -e 'example.tests*'\n",
        '%check\n',
    )
    message = _single_error(tmp_path, content)
    assert '%check (line 21) is empty' in message


def test_check_with_only_a_comment_is_accepted(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        "%check\n# No module named 'marray'\n"
        "BuildOption(check):  -e 'example.tests*'\n",
        '%check\n# skip tests as some deps we do not have yet.\n',
    )
    assert _check_spec_build_pyproject(_write(tmp_path, content)) == []


def test_check_with_a_command_passes(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        "%check\n# No module named 'marray'\n"
        "BuildOption(check):  -e 'example.tests*'\n",
        '%check -a\n%pytest\n',
    )
    assert _check_spec_build_pyproject(_write(tmp_path, content)) == []


def test_missing_check_section_is_not_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        "%check\n# No module named 'marray'\n"
        "BuildOption(check):  -e 'example.tests*'\n",
        '',
    )
    assert _check_spec_build_pyproject(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# C6 - BuildOption(check) must state a reason.
# --------------------------------------------------------------------------


def test_check_option_without_reason_is_reported(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        "# No module named 'marray'\n",
        '',
    )
    message = _single_error(tmp_path, content)
    assert 'does not state the reason for excluding modules' in message
    assert 'line 22' in message


def test_reason_may_be_separated_by_a_blank_line(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        "# No module named 'marray'\n",
        "\n# No module named 'marray'\n\n",
    )
    assert _check_spec_build_pyproject(_write(tmp_path, content)) == []


def test_only_the_first_check_option_needs_a_reason(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        "BuildOption(check):  -e 'example.tests*'\n",
        "BuildOption(check):  -e 'example.tests*'\n"
        "BuildOption(check):  -e 'example.tools*'\n",
    )
    assert _check_spec_build_pyproject(_write(tmp_path, content)) == []


def test_second_check_group_also_needs_a_reason(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        "BuildOption(check):  -e 'example.tests*'\n",
        "BuildOption(check):  -e 'example.tests*'\n"
        "%build\n"
        "BuildOption(check):  -e 'example.tools*'\n",
    )
    message = _single_error(tmp_path, content)
    assert 'does not state the reason for excluding modules' in message


# --------------------------------------------------------------------------
# Several findings on one spec, and flag handling.
# --------------------------------------------------------------------------


def test_every_checkpoint_reports_on_one_broken_spec(tmp_path: Path) -> None:
    content = '''\
Name:           python-broken
Version:        1.0
Release:        %autorelease
Summary:        A broken module
License:        MIT
URL:            https://example.org/broken
Source0:        https://example.org/broken/broken-1.0.tar.gz
BuildSystem:    pyproject
BuildRequires:  python3dist(setuptools)

%description
A broken module.

%check

%files
'''
    messages = _messages(tmp_path, content)
    assert len(messages) == 4, messages
    assert any('pyproject-rpm-macros' in m for m in messages)
    assert any('Python development dependency' in m for m in messages)
    assert any('module name to install' in m for m in messages)
    assert any('%check (line 14) is empty' in m for m in messages)


def test_ext_flags_disable_each_checkpoint(tmp_path: Path) -> None:
    content = '''\
Name:           python-broken
Version:        1.0
Release:        %autorelease
Summary:        A broken module
License:        MIT
URL:            https://example.org/broken
Source0:        https://example.org/broken/broken-1.0.tar.gz
BuildSystem:    pyproject
BuildRequires:  python3dist(setuptools)

%description
A broken module.

%check

%files
'''
    path = _write(tmp_path, content)
    assert _check_spec_build_pyproject_ext(
        path,
        check_macros_package=False,
        check_python_devel=False,
        check_install_option=False,
        check_install_option_module=False,
        check_check_section=False,
        check_check_reason=False,
    ) == []


def test_ext_flag_keeps_the_others(tmp_path: Path) -> None:
    content = '''\
Name:           python-broken
Version:        1.0
Release:        %autorelease
Summary:        A broken module
License:        MIT
URL:            https://example.org/broken
Source0:        https://example.org/broken/broken-1.0.tar.gz
BuildSystem:    pyproject
BuildRequires:  pyproject-rpm-macros
BuildRequires:  pkgconfig(python3)
BuildOption(install):  -l broken

%description
A broken module.

%check

%files
'''
    path = _write(tmp_path, content)
    errors = _check_spec_build_pyproject_ext(
        path, check_check_reason=False,
    )
    assert len(errors) == 1
    assert '%check' in errors[0]


def test_main_reports_and_sets_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write(tmp_path, NO_BUILD_SYSTEM_SPEC)
    assert main([path]) == 0
    assert main(['--no-check-macros-package', path]) == 0
    assert main([]) == 0


def test_main_prints_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    content = '''\
Name:           python-broken
Version:        1.0
Release:        %autorelease
Summary:        A broken module
License:        MIT
URL:            https://example.org/broken
Source0:        https://example.org/broken/broken-1.0.tar.gz
BuildSystem:    pyproject

%description
A broken module.

%files
'''
    path = _write(tmp_path, content)
    assert main([path]) == 1
    out = capsys.readouterr().out
    assert 'pyproject-rpm-macros' in out


def test_utf8_error_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'bad.spec'
    path.write_bytes(b'\xff\xfe\x00BuildSystem: pyproject\n')
    errors = _check_spec_build_pyproject(str(path))
    assert len(errors) == 1
    assert 'file is not valid UTF-8' in errors[0]


def test_dedup_keeps_one_finding_per_message(tmp_path: Path) -> None:
    content = '''\
Name:           python-broken
Version:        1.0
Release:        %autorelease
Summary:        A broken module
License:        MIT
URL:            https://example.org/broken
Source0:        https://example.org/broken/broken-1.0.tar.gz
BuildSystem:    pyproject
BuildSystem:    pyproject

%description
A broken module.

%files
'''
    messages = _messages(tmp_path, content)
    assert len(messages) == len(set(messages))
