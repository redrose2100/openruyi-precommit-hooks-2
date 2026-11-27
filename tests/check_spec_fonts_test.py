"""Tests for check-spec-fonts."""
from __future__ import annotations

from pathlib import Path

from openruyi_precommit_hooks import check_spec_fonts as rule

CHECK = rule._check_spec_fonts
CHECK_EXT = rule._check_spec_fonts_ext

FLAGS = (
    'check_name_prefix',
    'check_licence',
    'check_install_dir',
    'check_exception_dir',
    'check_extension',
    'check_bdf',
    'check_pcf_gzip',
    'check_macro_requires',
    'check_install_macro',
    'check_files_macro',
    'check_install_font_ext',
    'check_font_files_ext',
)

HEADER = """\
Name:           {name}
Version:        1.0.0
Release:        %autorelease
Summary:        A font family
License:        {licence}
URL:            https://example.org/
Source0:        https://example.org/demo-%{{version}}.zip
BuildArch:      noarch
{build_requires}
%description
A font family.
"""

CLEAN_MACROS = HEADER.format(
    name='fonts-demo',
    licence='OFL-1.1',
    build_requires='BuildRequires:  fonts-rpm-macros\n',
) + """\

%install
%install_fonts *.ttf demo
%install_fonts *.otf demo

%files
%license LICENSE
%font_files demo ttf
%font_files demo otf

%changelog
%autochangelog
"""

# The same package without the macro package: %install spells the directory
# out by hand, which keeps the spec in scope through the path it names.
CLEAN_PATHS = HEADER.format(
    name='fonts-demo',
    licence='OFL-1.1',
    build_requires='',
) + """\

%install
mkdir -p %{buildroot}%{_font_truetypedir}/demo
install -m 0644 *.ttf %{buildroot}%{_font_truetypedir}/demo

%files
%license LICENSE
%dir %{_font_truetypedir}/demo
%{_font_truetypedir}/demo/*.ttf

%changelog
%autochangelog
"""


def _write(
    tmp_path: Path, content: str, name: str = 'demo.spec',
) -> str:
    folder = tmp_path / 'demo'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(content, encoding='utf-8')
    return str(path)


def _messages(tmp_path: Path, content: str) -> list[str]:
    return [
        err.split(': ', 1)[1] for err in CHECK(_write(tmp_path, content))
    ]


def _isolated(tmp_path: Path, content: str, flag: str) -> list[str]:
    """Run one checkpoint alone and return its messages."""
    options: dict[str, bool] = {option: False for option in FLAGS}
    options[flag] = True
    return [
        err.split(': ', 1)[1]
        for err in CHECK_EXT(_write(tmp_path, content), **options)
    ]


def _body(install: str = '', files: str = '') -> str:
    """Return a spec with the given %install and %files bodies."""
    return HEADER.format(
        name='fonts-demo',
        licence='OFL-1.1',
        build_requires='',
    ) + f"""\

%install
{install}

%files
{files}

%changelog
%autochangelog
"""


# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------


def test_clean_macro_spec_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, CLEAN_MACROS)) == []


def test_clean_path_spec_passes(tmp_path: Path) -> None:
    assert CHECK(_write(tmp_path, CLEAN_PATHS)) == []


def test_application_with_a_private_font_is_ignored(tmp_path: Path) -> None:
    content = """\
Name:           firefox
Version:        130.0
Release:        %autorelease
Summary:        Web browser
License:        MPL-2.0
URL:            https://www.mozilla.org/
Source0:        https://example.org/firefox-%{version}.tar.gz

%description
Web browser.

%install
install -D -m 0644 browser/fonts/TwemojiMozilla.ttf \\
    %{buildroot}%{_libdir}/firefox/fonts/TwemojiMozilla.ttf

%files
%{_libdir}/firefox/fonts/TwemojiMozilla.ttf
"""
    assert CHECK(_write(tmp_path, content, 'firefox.spec')) == []


def test_macro_package_itself_passes(tmp_path: Path) -> None:
    content = """\
Name:           fonts-rpm-macros
Version:        20260625
Release:        %autorelease
Summary:        RPM macros for font packages
License:        MIT
Source0:        macros.fonts
BuildArch:      noarch

%description
RPM macros for font packages.

%install
install -D -m0644 %{SOURCE0} %{buildroot}%{_rpmconfigdir}/macros.d/macros.fonts

%files
%{_rpmconfigdir}/macros.d/macros.fonts
"""
    assert CHECK(_write(tmp_path, content)) == []


# --------------------------------------------------------------------------
# C1
# --------------------------------------------------------------------------


C1_CONTENT = HEADER.format(
    name='demo-font',
    licence='OFL-1.1',
    build_requires='BuildRequires:  fonts-rpm-macros\n',
) + """\

%install
%install_fonts *.ttf demo

%files
%license LICENSE
%font_files demo ttf
"""


def test_c1_reports_a_package_without_the_prefix(tmp_path: Path) -> None:
    messages = _isolated(tmp_path, C1_CONTENT, 'check_name_prefix')
    assert len(messages) == 1
    assert 'does not carry the "fonts-" prefix' in messages[0]


def test_c1_accepts_the_prefix(tmp_path: Path) -> None:
    content = C1_CONTENT.replace('Name:           demo-font',
                                 'Name:           fonts-demo-font')
    assert _isolated(tmp_path, content, 'check_name_prefix') == []


def test_c1_reports_a_prefixed_subpackage_only_when_it_lacks_it(
    tmp_path: Path,
) -> None:
    content = HEADER.format(
        name='fonts-demo',
        licence='OFL-1.1',
        build_requires='',
    ) + """\

%install
install -m 0644 *.ttf %{buildroot}%{_font_truetypedir}/demo

%files -n demo-fonts
%{_font_truetypedir}/demo/*.ttf
"""
    messages = _isolated(tmp_path, content, 'check_name_prefix')
    assert len(messages) == 1
    assert '"demo-fonts"' in messages[0]


# --------------------------------------------------------------------------
# C2
# --------------------------------------------------------------------------


def test_c2_reports_a_proprietary_licence(tmp_path: Path) -> None:
    content = CLEAN_MACROS.replace('License:        OFL-1.1',
                                   'License:        Proprietary')
    messages = _isolated(tmp_path, content, 'check_licence')
    assert len(messages) == 1
    assert 'does not allow redistribution' in messages[0]


def test_c2_reports_a_non_free_licence(tmp_path: Path) -> None:
    content = CLEAN_MACROS.replace('License:        OFL-1.1',
                                   'License:        LicenseRef-Non-Free')
    messages = _isolated(tmp_path, content, 'check_licence')
    assert len(messages) == 1
    assert 'does not allow redistribution' in messages[0]


def test_c2_accepts_the_ofl(tmp_path: Path) -> None:
    assert _isolated(tmp_path, CLEAN_MACROS, 'check_licence') == []


def test_c2_accepts_a_font_under_the_gpl(tmp_path: Path) -> None:
    content = CLEAN_MACROS.replace('License:        OFL-1.1',
                                   'License:        GPL-3.0-or-later')
    assert _isolated(tmp_path, content, 'check_licence') == []


# --------------------------------------------------------------------------
# C3
# --------------------------------------------------------------------------


def test_c3_reports_a_font_at_the_top_level(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.ttf '
        '%{buildroot}%{_datadir}/fonts/demo.ttf'
    ))
    messages = _isolated(tmp_path, content, 'check_install_dir')
    assert len(messages) == 1
    assert 'installs a font file into "%{_datadir}/fonts"' in messages[0]


def test_c3_reports_a_font_outside_the_share_directory(
    tmp_path: Path,
) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.ttf '
        '%{buildroot}%{_datadir}/demo/demo.ttf'
    ))
    messages = _isolated(tmp_path, content, 'check_install_dir')
    assert len(messages) == 1
    assert 'installs a font file into "%{_datadir}/demo"' in messages[0]


def test_c3_accepts_a_documented_container(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.ttf '
        '%{buildroot}%{_font_truetypedir}/demo/demo.ttf'
    ))
    assert _isolated(tmp_path, content, 'check_install_dir') == []


def test_c3_accepts_a_web_font(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.woff2 '
        '%{buildroot}%{_datadir}/webfonts/demo/demo.woff2'
    ))
    assert _isolated(tmp_path, content, 'check_install_dir') == []


def test_c3_ignores_a_fontconfig_configuration(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.conf '
        '%{buildroot}%{_datadir}/fontconfig/conf.avail/demo.conf'
    ))
    assert _isolated(tmp_path, content, 'check_install_dir') == []


# --------------------------------------------------------------------------
# C4
# --------------------------------------------------------------------------


def test_c4_reports_a_console_font_under_a_container(
    tmp_path: Path,
) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.psf '
        '%{buildroot}%{_font_truetypedir}/demo/demo.psf'
    ))
    messages = _isolated(tmp_path, content, 'check_exception_dir')
    assert len(messages) == 1
    assert '"*.psf" to %{_datadir}/consolefonts' in messages[0]


def test_c4_reports_a_web_font_under_a_container(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.woff2 '
        '%{buildroot}%{_font_opentypedir}/demo/demo.woff2'
    ))
    messages = _isolated(tmp_path, content, 'check_exception_dir')
    assert len(messages) == 1
    assert '%{_datadir}/webfonts' in messages[0]


def test_c4_reports_a_font_in_the_console_font_directory(
    tmp_path: Path,
) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.ttf '
        '%{buildroot}%{_datadir}/consolefonts/demo.ttf'
    ))
    messages = _isolated(tmp_path, content, 'check_exception_dir')
    assert len(messages) == 1
    assert 'fontconfig' in messages[0]


def test_c4_accepts_a_console_font(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.psf '
        '%{buildroot}%{_datadir}/consolefonts/demo.psf'
    ))
    assert _isolated(tmp_path, content, 'check_exception_dir') == []


def test_c4_accepts_a_web_font(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.woff2 '
        '%{buildroot}%{_datadir}/webfonts/demo/demo.woff2'
    ))
    assert _isolated(tmp_path, content, 'check_exception_dir') == []


# --------------------------------------------------------------------------
# C5
# --------------------------------------------------------------------------


def test_c5_reports_a_truetype_font_in_the_opentype_directory(
    tmp_path: Path,
) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.ttf '
        '%{buildroot}%{_font_opentypedir}/demo/demo.ttf'
    ))
    messages = _isolated(tmp_path, content, 'check_extension')
    assert len(messages) == 1
    assert '"*.otf", "*.otc"' in messages[0]


def test_c5_reports_an_opentype_font_in_the_truetype_directory(
    tmp_path: Path,
) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.otf '
        '%{buildroot}%{_font_truetypedir}/demo/demo.otf'
    ))
    messages = _isolated(tmp_path, content, 'check_extension')
    assert len(messages) == 1
    assert '"*.ttf", "*.ttc"' in messages[0]


def test_c5_reports_a_type1_font_in_the_bitmap_directory(
    tmp_path: Path,
) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.pfb '
        '%{buildroot}%{_datadir}/fonts/misc/demo.pfb'
    ))
    messages = _isolated(tmp_path, content, 'check_extension')
    assert len(messages) == 1
    assert '"*.otb", "*.pcf", "*.bdf"' in messages[0]


def test_c5_accepts_a_collection_in_the_opentype_directory(
    tmp_path: Path,
) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.otc '
        '%{buildroot}%{_font_opentypedir}/demo/demo.otc'
    ))
    assert _isolated(tmp_path, content, 'check_extension') == []


def test_c5_accepts_a_bitmap_font_in_the_x11_directory(
    tmp_path: Path,
) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.pcf.gz '
        '%{buildroot}%{_datadir}/fonts/X11/misc/demo.pcf.gz'
    ))
    assert _isolated(tmp_path, content, 'check_extension') == []


# --------------------------------------------------------------------------
# C6
# --------------------------------------------------------------------------


def test_c6_reports_a_bdf_bitmap_font(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.bdf '
        '%{buildroot}%{_datadir}/fonts/misc/demo.bdf'
    ))
    messages = _isolated(tmp_path, content, 'check_bdf')
    assert len(messages) == 1
    assert 'must be converted to *.pcf' in messages[0]


def test_c6_accepts_a_pcf_bitmap_font(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.pcf.gz '
        '%{buildroot}/usr/share/fonts/misc/demo.pcf.gz'
    ))
    assert _isolated(tmp_path, content, 'check_bdf') == []


# --------------------------------------------------------------------------
# C7
# --------------------------------------------------------------------------


def test_c7_reports_an_uncompressed_pcf(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.pcf '
        '%{buildroot}%{_datadir}/fonts/misc/demo.pcf'
    ))
    messages = _isolated(tmp_path, content, 'check_pcf_gzip')
    assert len(messages) == 1
    assert 'must be compressed with gzip first' in messages[0]


def test_c7_accepts_a_compressed_pcf(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.pcf.gz '
        '%{buildroot}%{_datadir}/fonts/misc/demo.pcf.gz'
    ))
    assert _isolated(tmp_path, content, 'check_pcf_gzip') == []


# --------------------------------------------------------------------------
# C8
# --------------------------------------------------------------------------


def test_c8_reports_a_macro_without_the_macro_package(
    tmp_path: Path,
) -> None:
    content = HEADER.format(
        name='fonts-demo',
        licence='OFL-1.1',
        build_requires='BuildRequires:  unzip\n',
    ) + """\

%install
%install_fonts *.ttf demo

%files
%font_files demo ttf
"""
    messages = _isolated(tmp_path, content, 'check_macro_requires')
    assert len(messages) == 1
    assert 'BuildRequires:  fonts-rpm-macros' in messages[0]


def test_c8_accepts_the_macro_package(tmp_path: Path) -> None:
    assert _isolated(tmp_path, CLEAN_MACROS, 'check_macro_requires') == []


def test_c8_ignores_a_spec_without_a_macro(tmp_path: Path) -> None:
    assert _isolated(tmp_path, CLEAN_PATHS, 'check_macro_requires') == []


# --------------------------------------------------------------------------
# C9
# --------------------------------------------------------------------------


def test_c9_reports_a_hardcoded_install_path(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.ttf '
        '%{buildroot}%{_datadir}/fonts/truetype/demo/demo.ttf'
    ))
    messages = _isolated(tmp_path, content, 'check_install_macro')
    assert len(messages) == 1
    assert '"%{_font_truetypedir}"' in messages[0]


def test_c9_reports_a_hardcoded_opentype_path(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.otf '
        '%{buildroot}/usr/share/fonts/opentype/demo/demo.otf'
    ))
    messages = _isolated(tmp_path, content, 'check_install_macro')
    assert len(messages) == 1
    assert '"%{_font_opentypedir}"' in messages[0]


def test_c9_accepts_the_directory_macros(tmp_path: Path) -> None:
    assert _isolated(tmp_path, CLEAN_PATHS, 'check_install_macro') == []


def test_c9_accepts_the_fontdir_macro(tmp_path: Path) -> None:
    content = _body(install=(
        'install -D -m 0644 demo.ttf '
        '%{buildroot}%{_fontdir}/truetype/demo/demo.ttf'
    ))
    assert _isolated(tmp_path, content, 'check_install_macro') == []


def test_c9_ignores_a_directory_with_no_font_file(tmp_path: Path) -> None:
    content = _body(install=(
        'mkdir -p %{buildroot}%{_datadir}/fonts/truetype/demo'
    ))
    assert _isolated(tmp_path, content, 'check_install_macro') == []


# --------------------------------------------------------------------------
# C10
# --------------------------------------------------------------------------


def test_c10_reports_a_hardcoded_files_path(tmp_path: Path) -> None:
    content = _body(files=(
        '%{_datadir}/fonts/truetype/demo/*.ttf'
    ))
    messages = _isolated(tmp_path, content, 'check_files_macro')
    assert len(messages) == 1
    assert '%files must use the font directory macros' in messages[0]


def test_c10_reports_every_hardcoded_files_path(tmp_path: Path) -> None:
    content = _body(files=(
        '%{_datadir}/fonts/truetype/demo/*.ttf\n'
        '%{_datadir}/fonts/opentype/demo/*.otf'
    ))
    messages = _isolated(tmp_path, content, 'check_files_macro')
    assert len(messages) == 2


def test_c10_tolerates_license_doc_and_dir_macros(tmp_path: Path) -> None:
    content = _body(files=(
        '%license LICENSE\n'
        '%doc README.md\n'
        '%dir %{_datadir}/fonts/truetype/demo\n'
        '%{_datadir}/fonts/truetype/demo/*.ttf'
    ))
    messages = _isolated(tmp_path, content, 'check_files_macro')
    assert len(messages) == 1
    assert '*.ttf' in messages[0]


def test_c10_accepts_the_directory_macros(tmp_path: Path) -> None:
    assert _isolated(tmp_path, CLEAN_PATHS, 'check_files_macro') == []


def test_c10_ignores_a_fontconfig_files_entry(tmp_path: Path) -> None:
    content = _body(files=(
        '%{_datadir}/fontconfig/conf.avail/demo.conf'
    ))
    assert _isolated(tmp_path, content, 'check_files_macro') == []


# --------------------------------------------------------------------------
# C11
# --------------------------------------------------------------------------


def test_c11_reports_a_web_font_in_the_install_macros(
    tmp_path: Path,
) -> None:
    content = HEADER.format(
        name='fonts-demo',
        licence='OFL-1.1',
        build_requires='BuildRequires:  fonts-rpm-macros\n',
    ) + """\

%install
%install_fonts *.woff2 demo

%files
%font_files demo ttf
"""
    messages = _isolated(tmp_path, content, 'check_install_font_ext')
    assert len(messages) == 1
    assert 'any other extension fails the build' in messages[0]


def test_c11_reports_a_bitmap_font_in_install_font(tmp_path: Path) -> None:
    content = HEADER.format(
        name='fonts-demo',
        licence='OFL-1.1',
        build_requires='BuildRequires:  fonts-rpm-macros\n',
    ) + """\

%install
%install_font demo.otb demo

%files
%font_files demo ttf
"""
    messages = _isolated(tmp_path, content, 'check_install_font_ext')
    assert len(messages) == 1
    assert '"*.otb"' in messages[0]


def test_c11_accepts_the_supported_extensions(tmp_path: Path) -> None:
    assert _isolated(tmp_path, CLEAN_MACROS, 'check_install_font_ext') == []


def test_c11_ignores_the_auto_macro(tmp_path: Path) -> None:
    content = HEADER.format(
        name='fonts-demo',
        licence='OFL-1.1',
        build_requires='BuildRequires:  fonts-rpm-macros\n',
    ) + """\

%install
%install_fonts_auto demo

%files
%font_files demo ttf
"""
    assert _isolated(tmp_path, content, 'check_install_font_ext') == []


# --------------------------------------------------------------------------
# C12
# --------------------------------------------------------------------------


def test_c12_reports_a_font_files_call_without_extensions(
    tmp_path: Path,
) -> None:
    content = CLEAN_MACROS.replace(
        '%font_files demo ttf\n%font_files demo otf',
        '%font_files demo',
    )
    messages = _isolated(tmp_path, content, 'check_font_files_ext')
    assert len(messages) == 1
    assert 'lists no extension' in messages[0]


def test_c12_reports_each_call_without_extensions(tmp_path: Path) -> None:
    content = CLEAN_MACROS.replace(
        '%font_files demo ttf\n%font_files demo otf',
        '%font_files demo\n%font_files demo',
    )
    messages = _isolated(tmp_path, content, 'check_font_files_ext')
    assert len(messages) == 2
    assert all('lists no extension' in message for message in messages)


def test_c12_accepts_an_explicit_extension_list(tmp_path: Path) -> None:
    assert _isolated(tmp_path, CLEAN_MACROS, 'check_font_files_ext') == []


# --------------------------------------------------------------------------
# Flags
# --------------------------------------------------------------------------


def test_every_flag_can_be_switched_off(tmp_path: Path) -> None:
    content = _body(
        install=(
            'install -D -m 0644 demo.bdf '
            '%{buildroot}%{_datadir}/fonts/truetype/demo.bdf'
        ),
        files='%{_datadir}/fonts/truetype/demo/*.bdf',
    )
    options = {flag: False for flag in FLAGS}
    assert CHECK_EXT(_write(tmp_path, content), **options) == []


def test_the_default_run_covers_every_checkpoint(tmp_path: Path) -> None:
    content = HEADER.format(
        name='demo-font',
        licence='Proprietary',
        build_requires='',
    ) + """\

%install
install -D -m 0644 demo.bdf %{buildroot}%{_datadir}/fonts/truetype/demo.bdf
%install_fonts *.woff2 demo

%files
%{_datadir}/fonts/truetype/demo/*.bdf
%font_files demo
"""
    errors = CHECK(_write(tmp_path, content))
    assert len(errors) == 11
