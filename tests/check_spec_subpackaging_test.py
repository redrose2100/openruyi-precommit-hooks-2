# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_subpackaging import (
    _check_spec_subpackaging,
)
from openruyi_precommit_hooks.check_spec_subpackaging import (
    _check_spec_subpackaging_ext,
)
from openruyi_precommit_hooks.check_spec_subpackaging import main

# A spec that satisfies every checkpoint: the subpackage names use "-", the
# development content sits in "-devel", the versioned library stays in the
# runtime package, the unversioned link sits in "-devel", and the
# subpackage pins its base package.
CLEAN_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools

%description
An example package.

%package devel
Summary:        Development files for foo
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
Development files for foo.

%files
%license LICENSE
%{_libdir}/libfoo.so.1
%{_libdir}/libfoo.so.1.2.3

%files devel
%{_includedir}/foo.h
%{_libdir}/libfoo.so
%{_libdir}/pkgconfig/foo.pc

%changelog
%autochangelog
"""

# A spec that declares no subpackage at all. Every checkpoint needs a
# subpackage to compare against, so the rule is silent.
NO_SUBPACKAGE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools

%description
An example package.

%files
%license LICENSE
%{_bindir}/foo

%changelog
%autochangelog
"""

# A Rust feature subpackage. The supplement carves the "+" spelling out, so
# the name checkpoint must stay silent even though the name has no "-".
RUST_FEATURE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    cargo

%description
An example package.

%package -n %{name}+serde
Summary:        Serde support for foo

%description -n %{name}+serde
Serde support for foo.

%files -n %{name}+serde
%license LICENSE
%{_libdir}/libfoo_serde.so

%changelog
%autochangelog
"""

# The main package writes a bare "%files" after the "%files devel" block,
# which is the documented order. The bare block belongs to the main package
# and must not be read as a second development block.
BARE_FILES_AFTER_DEVEL_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools

%package devel
Summary:        Development files for foo

%description devel
Development files for foo.

%files -f %{name}.lang
%license LICENSE
%{_libdir}/libfoo.so.1

%files devel
%{_includedir}/foo.h
%{_libdir}/libfoo.so

%changelog
%autochangelog
"""

# A private plugin library below a directory of the library directory. The
# supplement places it with the main package, so the unversioned link
# checkpoint must not report it.
PRIVATE_PLUGIN_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools

%package devel
Summary:        Development files for foo

%description devel
Development files for foo.

%files
%license LICENSE
%{_libdir}/foo/plugin_auth.so

%files devel
%{_includedir}/foo.h

%changelog
%autochangelog
"""


def _write(tmp_path: Path, content: str) -> str:
    spec = tmp_path / 'foo.spec'
    spec.write_text(content, encoding='utf-8')
    return str(spec)


def test_clean_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_subpackaging(_write(tmp_path, CLEAN_SPEC)) == []


def test_spec_without_subpackage_passes(tmp_path: Path) -> None:
    assert _check_spec_subpackaging(
        _write(tmp_path, NO_SUBPACKAGE_SPEC),
    ) == []


def test_rust_feature_subpackage_passes(tmp_path: Path) -> None:
    assert _check_spec_subpackaging(
        _write(tmp_path, RUST_FEATURE_SPEC),
    ) == []


def test_bare_files_after_devel_belongs_to_the_main_package(
    tmp_path: Path,
) -> None:
    assert _check_spec_subpackaging(
        _write(tmp_path, BARE_FILES_AFTER_DEVEL_SPEC),
    ) == []


def test_private_plugin_library_passes(tmp_path: Path) -> None:
    assert _check_spec_subpackaging(
        _write(tmp_path, PRIVATE_PLUGIN_SPEC),
    ) == []


def test_missing_utf8_is_reported(tmp_path: Path) -> None:
    spec = tmp_path / 'bad.spec'
    spec.write_bytes(b'Name: foo\n%package devel\xff\n')
    errors = _check_spec_subpackaging(str(spec))
    assert len(errors) == 1
    assert 'not valid UTF-8' in errors[0]


def test_missing_file_is_reported(tmp_path: Path) -> None:
    errors = _check_spec_subpackaging(str(tmp_path / 'absent.spec'))
    assert len(errors) == 1
    assert 'absent.spec' in errors[0]


# -- P1 name separator -------------------------------------------------------

@pytest.mark.parametrize(
    'declaration',
    [
        '%package -n foo_libs',
        '%package -n foo-extras_v2',
        '%package -n foo.extras',
        '%package lib_foo',
    ],
)
def test_p1_odd_separator_is_reported(
    tmp_path: Path,
    declaration: str,
) -> None:
    content = CLEAN_SPEC.replace('%package devel', declaration, 1)
    errors = _check_spec_subpackaging(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'uses "' in errors[0]
    assert 'separate the parts with "-"' in errors[0]


def test_p1_separator_of_the_base_name_is_not_reported(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'Name:           foo',
        'Name:           foo_bar',
    ).replace('lib_foo', 'lib_foo')
    errors = _check_spec_subpackaging(_write(tmp_path, content))
    assert errors == []


def test_p1_macro_name_is_skipped(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%package devel',
        '%package -n %{name}_extras',
        1,
    )
    errors = _check_spec_subpackaging(_write(tmp_path, content))
    assert errors == []


def test_p1_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('%package devel', '%package lib_foo', 1)
    path = _write(tmp_path, content)
    assert _check_spec_subpackaging_ext(path, check_name=False) == []


# -- P2 development content --------------------------------------------------

@pytest.mark.parametrize(
    'entry',
    [
        '%{_includedir}/foo.h',
        '/usr/include/foo/foo.h',
        '%{_libdir}/pkgconfig/foo.pc',
        '%{_libdir}/cmake/foo/foo-config.cmake',
        '%{_datadir}/cmake/foo/foo.macros',
    ],
)
def test_p2_development_content_outside_devel_is_reported(
    tmp_path: Path,
    entry: str,
) -> None:
    content = CLEAN_SPEC.replace(
        '%{_bindir}/foo',
        entry,
    ).replace(
        '%{_libdir}/libfoo.so.1',
        entry,
        1,
    )
    errors = _check_spec_subpackaging(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'move it to the foo-devel subpackage' in errors[0]


def test_p2_content_without_a_devel_subpackage_is_reported(
    tmp_path: Path,
) -> None:
    content = NO_SUBPACKAGE_SPEC.replace(
        '%{_bindir}/foo',
        '%{_includedir}/foo.h',
    )
    errors = _check_spec_subpackaging(_write(tmp_path, content))
    assert errors == []


def test_p2_reports_missing_devel_when_another_subpackage_exists(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        '%package devel',
        '%package tools',
        1,
    ).replace(
        '%files devel',
        '%files tools',
        1,
    ).replace(
        '%{_includedir}/foo.h',
        '%{_bindir}/foo-tool',
        1,
    ).replace(
        '%{_libdir}/libfoo.so\n',
        '',
        1,
    ).replace(
        '%{_libdir}/pkgconfig/foo.pc',
        '',
        1,
    ).replace(
        '%{_libdir}/libfoo.so.1',
        '%{_includedir}/foo.h',
        1,
    )
    errors = _check_spec_subpackaging(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'declares no foo-devel subpackage' in errors[0]


def test_p2_ignores_a_commented_path(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%{_libdir}/libfoo.so.1',
        '# %{_includedir}/foo.h\n%{_libdir}/libfoo.so.1',
        1,
    )
    assert _check_spec_subpackaging(_write(tmp_path, content)) == []


def test_p2_ignores_an_excluded_path(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%{_libdir}/libfoo.so.1',
        '%exclude %{_includedir}/foo.h\n%{_libdir}/libfoo.so.1',
        1,
    )
    assert _check_spec_subpackaging(_write(tmp_path, content)) == []


def test_p2_ignores_a_runtime_header(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%{_libdir}/libfoo.so.1',
        '%{_datadir}/foo/relay.h\n%{_libdir}/libfoo.so.1',
        1,
    )
    assert _check_spec_subpackaging(_write(tmp_path, content)) == []


def test_p2_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%{_libdir}/libfoo.so.1',
        '%{_includedir}/foo.h\n%{_libdir}/libfoo.so.1',
        1,
    )
    path = _write(tmp_path, content)
    assert _check_spec_subpackaging_ext(path, check_dev_files=False) == []


# -- P3 versioned library inside devel ---------------------------------------

@pytest.mark.parametrize(
    'entry',
    [
        '%{_libdir}/libfoo.so.1',
        '%{_libdir}/libfoo.so.1.2.3',
        '/usr/lib64/libfoo.so.2',
        '%{_libdir}/libfoo.so.1*',
    ],
)
def test_p3_versioned_library_in_devel_is_reported(
    tmp_path: Path,
    entry: str,
) -> None:
    content = CLEAN_SPEC.replace(
        '%{_libdir}/libfoo.so\n',
        entry + '\n',
        1,
    )
    errors = _check_spec_subpackaging(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'versioned shared library' in errors[0]
    assert 'keep the real file and the SONAME link' in errors[0]


def test_p3_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%{_libdir}/libfoo.so\n',
        '%{_libdir}/libfoo.so.1\n',
        1,
    )
    path = _write(tmp_path, content)
    assert _check_spec_subpackaging_ext(
        path,
        check_versioned_library=False,
    ) == []


# -- P4 unversioned link -----------------------------------------------------

@pytest.mark.parametrize(
    'entry',
    [
        '%{_libdir}/libfoo.so',
        '/usr/lib64/libbar.so',
        '%{_libdir}/libfoo-2.so',
    ],
)
def test_p4_unversioned_link_outside_devel_is_reported(
    tmp_path: Path,
    entry: str,
) -> None:
    content = CLEAN_SPEC.replace(
        '%{_libdir}/libfoo.so.1\n%{_libdir}/libfoo.so.1.2.3',
        entry + '\n%{_libdir}/libfoo.so.1.2.3',
        1,
    )
    errors = _check_spec_subpackaging(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'unversioned library link' in errors[0]
    assert 'move the *.so link to the foo-devel subpackage' in errors[0]


def test_p4_is_silent_without_a_devel_subpackage(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%package devel',
        '%package tools',
        1,
    ).replace(
        '%files devel',
        '%files tools',
        1,
    ).replace(
        '%{_includedir}/foo.h\n',
        '',
        1,
    ).replace(
        '%{_libdir}/libfoo.so\n',
        '',
        1,
    ).replace(
        '%{_libdir}/pkgconfig/foo.pc',
        '',
        1,
    )
    errors = _check_spec_subpackaging(_write(tmp_path, content))
    assert errors == []


def test_p4_skips_a_version_in_the_file_name(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%{_libdir}/libfoo.so.1\n',
        '%{_libdir}/libfoo-%{version}.so\n',
        1,
    )
    assert _check_spec_subpackaging(_write(tmp_path, content)) == []


def test_p4_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        '%{_libdir}/libfoo.so.1\n%{_libdir}/libfoo.so.1.2.3',
        '%{_libdir}/libfoo.so\n%{_libdir}/libfoo.so.1.2.3',
        1,
    )
    path = _write(tmp_path, content)
    assert _check_spec_subpackaging_ext(
        path,
        check_unversioned_link=False,
    ) == []


# -- P5 dependency pin -------------------------------------------------------

@pytest.mark.parametrize(
    'declaration',
    [
        'Requires:       foo',
        'Requires:       foo = %{version}',
        'Requires:       foo >= %{version}',
        'Requires:       %{name} >= %{version}',
    ],
)
def test_p5_unpinned_requirement_is_reported(
    tmp_path: Path,
    declaration: str,
) -> None:
    content = CLEAN_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        declaration,
        1,
    )
    errors = _check_spec_subpackaging(_write(tmp_path, content))
    assert len(errors) == 1
    assert 'does not pin the base package' in errors[0]
    assert 'Requires:       foo%{?_isa} = %{version}-%{release}' in errors[0]


def test_p5_accepts_a_release_from_another_macro(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       foo%{?_isa} = %{nodejs_version}-%{release}',
        1,
    )
    assert _check_spec_subpackaging(_write(tmp_path, content)) == []


def test_p5_ignores_a_qualified_requirement(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires(post): foo',
        1,
    )
    assert _check_spec_subpackaging(_write(tmp_path, content)) == []


def test_p5_ignores_a_requirement_on_another_package(
    tmp_path: Path,
) -> None:
    content = CLEAN_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       bar',
        1,
    )
    assert _check_spec_subpackaging(_write(tmp_path, content)) == []


def test_p5_can_be_disabled(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Requires:       %{name}%{?_isa} = %{version}-%{release}',
        'Requires:       foo',
        1,
    )
    path = _write(tmp_path, content)
    assert _check_spec_subpackaging_ext(path, check_dependency=False) == []


# -- finding shape and command line ------------------------------------------

def test_findings_are_prefixed_with_the_filename(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace('%package devel', '%package lib_foo', 1)
    path = _write(tmp_path, content)
    errors = _check_spec_subpackaging(path)
    assert errors
    assert all(err.startswith(path + ': ') for err in errors)


def test_section_body_is_never_read_as_a_field(tmp_path: Path) -> None:
    content = CLEAN_SPEC.replace(
        'Development files for foo.\n',
        'Development files for foo.\n\nRequires:       foo\n'
        'Name:           foo_bar\n',
        1,
    )
    assert _check_spec_subpackaging(_write(tmp_path, content)) == []


def test_main_returns_zero_for_a_clean_spec(
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
    content = CLEAN_SPEC.replace('%package devel', '%package lib_foo', 1)
    path = _write(tmp_path, content)
    assert main([path]) == 1
    out = capsys.readouterr().out
    assert 'lib_foo' in out
    assert path in out


def test_main_accepts_no_filenames() -> None:
    assert main([]) == 0
