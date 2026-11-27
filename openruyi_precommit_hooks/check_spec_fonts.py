"""Check the requirements of the font packaging guideline.

The page
<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/FontPackagingGuidelines>
is written in Chinese. The quotations below are translations of the clauses
this rule reads.

Section "Package naming" states:

> Every font package is named fonts-fontname, where fontname is the
> canonical name of the font. The name may follow the Family or the
> Typographic Family entry of the OpenType name table, but the upstream
> project name wins when the two disagree.
>
> An abbreviation the upstream project has long used, or one that has
> already become a de-facto standard in the Linux ecosystem, is allowed as
> long as it does not collide with another font project, so WenQuanYi may
> be abbreviated to wqy and packaged as fonts-wqy.

Section "Licence" states:

> Always remember: packaging a proprietary font that may not be
> redistributed is forbidden. When a font is introduced, prefer a family
> under a licence such as the OFL or the GPL.

Section "Build" states:

> When upstream ships a source package, the font files should be built from
> source. When the font files cannot be built from source, the font archive
> upstream publishes may be used directly.
>
> When the fonts published in one upstream archive do not belong to the
> same font family, they must be split into separate font packages.

Section "Installation location" states:

> A system font belongs under the %{_datadir}/fonts directory and is
> classified by container:
>
> - OpenType TT (*.ttf/*.ttc) belongs in %{_datadir}/fonts/truetype.
> - OpenType CFF/CFF2 (*.otf/*.otc) belongs in %{_datadir}/fonts/opentype.
>
> fontconfig scans the paths below it recursively and maintains a cache, so
> the layering does not affect discovery.

Section "Bitmap fonts" states:

> Bitmap fonts are handled in two ways, and the second way should not be
> packaged unless it is necessary:
>
> - The OpenType bitmap format (*.otb) that modern fontconfig and Xft use
>   belongs in %{_datadir}/fonts/misc. X11 bitmap files (*.pcf)/(*.bdf)
>   that are genuinely needed alongside it may be placed in the same
>   directory.
> - The legacy Core X11 fonts (XLFD) bitmap format (*.pcf) must be
>   compressed with gzip first and then installed by resolution into
>   %{_datadir}/fonts/X11/100dpi/ or %{_datadir}/fonts/X11/75dpi/, with a
>   low-resolution or monospaced font going to
>   %{_datadir}/fonts/X11/misc/. When the format is *.bdf, it must be
>   converted to *.pcf.
>
> The legacy fonts should not be depended on by default and should not be
> preinstalled.

Section "Type 1" states:

> Type 1 (*.pfa/*.pfb) is a legacy format. FreeType still supports it, but
> many modern applications are dropping it, so when upstream also publishes
> an OpenType TT or CFF/CFF2 font the OpenType version should be packaged
> first. When the format does have to be packaged, it belongs in
> %{_datadir}/fonts/type1. A metrics file (*.afm) shipped with the font
> must be packaged into the directory as well.

Section "Exceptions" states:

> The Linux console font (*.psf) and the Web font (*.woff/*.woff2) must
> not be installed in a directory fontconfig can find. The latter is called
> out by the WOFF specification, which says a WOFF file should not be
> treated as a desktop-installable format.
>
> - The console font (*.psf) belongs in %{_datadir}/consolefonts.
> - The Web font (*.woff) belongs in %{_datadir}/webfonts.

Section "Subpackage split and naming" states:

> When more than one font format exists, the main package acts as a
> metapackage and ships no font file itself. The recommended split is:
>
> - fonts-fontname-vf for the variable fonts, usually a *.ttf or *.otf VF.
>   The metapackage may declare Requires: fonts-fontname-vf.
> - fonts-fontname-static for the static fonts, usually a non-VF *.ttf or
>   *.otf.
>
> Upstream sometimes publishes only a collection file (*.ttc/*.otc), in
> which case the subpackage may be named fonts-fontname-ttc or
> fonts-fontname-otc.

Section "Macros" states:

> The fonts-rpm-macros package provides the RPM macros that spell the font
> directories described above and install a font file into them. Using
> them requires the build dependency:
>
>     BuildRequires:  fonts-rpm-macros
>
> The current macros cover OpenType TT (*.ttf/*.ttc) and OpenType
> CFF/CFF2 (*.otf). The remaining formats, such as *.otc, *.otb, *.pcf,
> *.pfb, *.psf and *.woff, must still be installed by hand along the paths
> given in the installation location section.

Section "Directory macros" states:

> %install and %files should use the following macros rather than a
> hardcoded path:
>
> - %{_fontdir} for %{_datadir}/fonts, the top level of a system font.
> - %{_font_truetypedir} for %{_fontdir}/truetype.
> - %{_font_opentypedir} for %{_fontdir}/opentype.
> - %{_font_fontconfigdir} for %{_datadir}/fontconfig/conf.avail.

Section "%install_font" states:

> %install_font <src> [subdir] installs a single font file and picks the
> destination by extension: *.ttf and *.ttc go to %{_font_truetypedir} and
> *.otf goes to %{_font_opentypedir}. Any other extension fails the build.

Section "%install_fonts" states:

> %install_fonts <glob> [subdir] hands every file matched by <glob> to
> %install_font. A glob that matches nothing is skipped, so a match rule
> can be reserved for a format a version happens not to publish.

Section "%font_files" states:

> %font_files <subdir> [ext...] generates the %files entries for a font
> installed under <subdir>. For each extension it generates the %dir entry
> of the owning type directory and the glob entry of the font file.
>
> List the extensions the package actually installs. When the extension is
> omitted the macro falls back to ttf, otf and ttc, and rpmbuild fails when
> any of the three globs matches nothing.

Twelve checkpoints are implemented, and each one is anchored in one of
those clauses:

* C1 reproduces "Every font package is named fonts-fontname".
* C2 reproduces "packaging a proprietary font that may not be
  redistributed is forbidden".
* C3 reproduces "A system font belongs under the %{_datadir}/fonts
  directory and is classified by container".
* C4 reproduces "The Linux console font (*.psf) and the Web font
  (*.woff/*.woff2) must not be installed in a directory fontconfig can
  find".
* C5 reproduces the extension-to-container table of the installation
  location, bitmap font and Type 1 sections.
* C6 reproduces "When the format is *.bdf, it must be converted to *.pcf".
* C7 reproduces "The legacy Core X11 fonts (XLFD) bitmap format (*.pcf)
  must be compressed with gzip first".
* C8 reproduces the "BuildRequires:  fonts-rpm-macros" dependency the
  macros section requires.
* C9 reproduces "%install and %files should use the following macros
  rather than a hardcoded path" on the %install side.
* C10 reproduces the same clause on the %files side, because a spec can
  honour one half and miss the other.
* C11 reproduces "Any other extension fails the build".
* C12 reproduces "List the extensions the package actually installs".

C1, C2, C8, C11 and C12 are judged on the whole spec. C3, C4, C5, C6, C7,
C9 and C10 are judged on the lines of %install and %files that name a font
file, because a path only matters where a file is placed.

The population is narrow on purpose. A spec is in scope when its main Name
carries the fonts- prefix, when it installs or packs a font file into a font
directory, or when it calls one of the font macros. That keeps a browser, a
boot loader or a console tool that happens to carry a private font under
%{_libdir} out of the population: a font vendored by an application is an
application asset, not a system font.

Deliberately out of scope:

* "When a font is introduced, prefer a family under a licence such as the
  OFL or the GPL" is a preference, not a prohibition; C2 only reports the
  licences the page forbids outright.
* "When the fonts published in one upstream archive do not belong to the
  same font family, they must be split into separate font packages" cannot
  be decided from the spec text, which records neither the family metadata
  of the files nor the contents of the archive.
* "When more than one font format exists, the main package acts as a
  metapackage and ships no font file itself" and the subpackage suffixes
  it recommends are written as a recommendation; the corpus honours them
  everywhere, so a checkpoint would carry no signal.
* "The metapackage may declare Requires: fonts-fontname-vf" is phrased with
  "may", so a metapackage without the dependency is conforming.
* "The legacy fonts should not be depended on by default and should not be
  preinstalled" is a repository-wide policy over a package set rather than
  a property of one spec.
* Whether a font is built from source or taken from an upstream archive is
  decided by the choice of Source, which check-spec-source already reads.

No network access and no rpm invocation is performed. The rule reads the
spec text, the paths the spec spells, and the %install/%files section the
paths appear in.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Iterable
from collections.abc import Sequence
from typing import NamedTuple

FONT_PREFIX = 'fonts-'
MACROS_PACKAGE = 'fonts-rpm-macros'

# The formats the page names, in the spelling a file extension uses. The
# order is the one the page lists them in, so a finding reads naturally.
FONT_EXTENSIONS = (
    'ttf', 'ttc', 'otf', 'otc', 'otb', 'pcf', 'bdf', 'pfa', 'pfb', 'afm',
    'psf', 'woff', 'woff2',
)

RE_FONT_FILE = re.compile(
    r'\.(' + '|'.join(FONT_EXTENSIONS) + r')(?![A-Za-z0-9/])',
    re.IGNORECASE,
)

# The containers of the installation location, bitmap font and Type 1
# sections, keyed by the directory the page names under %{_datadir}/fonts.
CONTAINER: dict[str, frozenset[str]] = {
    'truetype': frozenset({'ttf', 'ttc'}),
    'opentype': frozenset({'otf', 'otc'}),
    'misc': frozenset({'otb', 'pcf', 'bdf'}),
    'type1': frozenset({'pfa', 'pfb', 'afm'}),
    'X11/100dpi': frozenset({'pcf'}),
    'X11/75dpi': frozenset({'pcf'}),
    'X11/misc': frozenset({'pcf'}),
}

# The two directories under %{_datadir} that hold a format fontconfig must
# not find.
SIDE: dict[str, frozenset[str]] = {
    'consolefonts': frozenset({'psf'}),
    'webfonts': frozenset({'woff', 'woff2'}),
}

# Where the page sends a format that cannot live in a regular container.
EXCEPTION_DIR = {
    'psf': 'consolefonts',
    'woff': 'webfonts',
    'woff2': 'webfonts',
}

# The macro the page offers for each directory it documents with one.
DIR_MACRO = {
    'truetype': '%{_font_truetypedir}',
    'opentype': '%{_font_opentypedir}',
    'fontconfig/conf.avail': '%{_font_fontconfigdir}',
}

_DIR_MACRO_ROOTS = (
    ('%{_font_fontconfigdir}', 'fontconfig/conf.avail'),
    ('%{_font_truetypedir}', 'truetype'),
    ('%{_font_opentypedir}', 'opentype'),
    ('%{_fontdir}', 'fonts'),
)

# Any path under the share directory. A font file is classified by the
# directory it lands in, so a path outside the documented ones has to be
# readable as well.
RE_SHARE_PATH = re.compile(
    r'/usr/(?:local/)?share/[A-Za-z0-9._*?%{}-]+'
    r'(?:/[A-Za-z0-9._*?%{}-]+)*',
)

RE_DATADIR_PATH = re.compile(
    r'%\{_datadir\}/[A-Za-z0-9._*?%{}-]+'
    r'(?:/[A-Za-z0-9._*?%{}-]+)*',
)

RE_DIR_MACRO_PATH = re.compile(
    r'%\{_(?:font_fontconfigdir|font_truetypedir|font_opentypedir|fontdir)\}'
    r'(?:/[A-Za-z0-9._*?%{}-]+)*',
)

# The macros that install a font file or generate its %files entries.
RE_FONT_MACRO = re.compile(
    r'%(install_fonts_auto|install_fonts|install_font|font_files)\b',
)

RE_FONT_MACRO_CALL = re.compile(
    r'%(install_fonts_auto|install_fonts|install_font|font_files)\b(.*)$',
)

# The extensions the install macros can place.
MACRO_EXTENSIONS = frozenset({'ttf', 'ttc', 'otf'})

# The words that start a new section. A %license, %doc, %dir or %attr line
# inside %files calls a macro rather than opening a section, so a section is
# only opened by a word from this list.
SECTION_WORDS: frozenset[str] = frozenset({
    'package', 'description', 'prep', 'generate_buildrequires', 'conf',
    'build', 'install', 'check', 'files', 'changelog', 'clean', 'pre',
    'post', 'preun', 'postun', 'triggerpostun', 'trigger', 'triggerin',
    'triggerun', 'verifyscript', 'transfiletriggerin', 'filetrigger',
})

RE_SECTION = re.compile(r'^%(\w+)(?:\s+(.*))?$')
RE_DEFINE = re.compile(r'^%(?:define|global)\s+(\w+)(?:\s+(.*))?$')
RE_NAME = re.compile(r'^Name:\s*(.*)$', re.IGNORECASE | re.MULTILINE)
RE_LICENSE = re.compile(
    r'^License:\s*(.*)$', re.IGNORECASE | re.MULTILINE,
)
RE_BUILD_REQUIRES = re.compile(
    r'^BuildRequires:\s*(.*)$', re.IGNORECASE | re.MULTILINE,
)
RE_MACRO_REF = re.compile(r'%\{(\w+)\}')

# Licence fragments that mark a font as undistributable.
PROPRIETARY = (
    'proprietary', 'freeware', 'shareware', 'non-free', 'nonfree',
    'redistributable', 'commercial',
)

_EXPANSIONS = 10


class _Macro(NamedTuple):
    value: str
    line: int


class _Section(NamedTuple):
    kind: str
    arg: str
    body: list[tuple[int, str]]


class _Spec(NamedTuple):
    name: str
    name_line: int
    macros: dict[str, _Macro]
    sections: list[_Section]
    licences: list[tuple[str, int]]
    build_requires: set[str]
    text: str


class _Hit(NamedTuple):
    line: int
    text: str
    ext: str
    root: str


class _Path(NamedTuple):
    line: int
    text: str
    root: str
    expected: str


class _Call(NamedTuple):
    macro: str
    line: int
    text: str
    rest: str


class _Layout(NamedTuple):
    outside: list[_Hit]
    misplaced: list[_Hit]
    mismatched: list[_Hit]
    bitmap: list[_Hit]
    unpacked: list[_Hit]
    install_macro: list[_Path]
    files_macro: list[_Path]


def _dedup(errors: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for err in errors:
        seen.setdefault(err, None)
    return list(seen)


def _read_lines(filename: str) -> tuple[list[str] | None, str | None]:
    try:
        with open(filename, encoding='utf-8') as handle:
            return handle.read().splitlines(), None
    except UnicodeDecodeError:
        return None, f'{filename}: file is not valid UTF-8'
    except OSError as exc:
        return None, f'{filename}: {exc}'


def _definitions(lines: Sequence[str]) -> dict[str, _Macro]:
    """Return the first definition of every %define and %global macro."""
    macros: dict[str, _Macro] = {}
    index = 0
    while index < len(lines):
        match = RE_DEFINE.match(lines[index])
        if match is None:
            index += 1
            continue
        value = (match.group(2) or '').strip()
        line = index + 1
        while value.endswith('\\') and index + 1 < len(lines):
            index += 1
            value = value[:-1].rstrip() + ' ' + lines[index].strip()
        if match.group(1) not in macros:
            macros[match.group(1)] = _Macro(value, line)
        index += 1
    return macros


def _substitute(match: re.Match[str], macros: dict[str, _Macro]) -> str:
    macro = macros.get(match.group(1))
    return match.group(0) if macro is None else macro.value


def _expand(text: str, macros: dict[str, _Macro]) -> str:
    """Expand %{name} references through the macros of the spec."""
    result = text
    for _pass in range(_EXPANSIONS):
        expanded = RE_MACRO_REF.sub(
            lambda match: _substitute(match, macros), result,
        )
        if expanded == result:
            return result
        result = expanded
    return result


def _sections(lines: Sequence[str]) -> list[_Section]:
    """Split a spec into the sections a %word line opens."""
    sections: list[_Section] = []
    kind = ''
    arg = ''
    body: list[tuple[int, str]] = []
    for index, text in enumerate(lines, start=1):
        match = RE_SECTION.match(text)
        if match is not None and match.group(1) in SECTION_WORDS:
            if kind:
                sections.append(_Section(kind, arg, body))
            kind = match.group(1)
            arg = (match.group(2) or '').strip()
            body = []
            continue
        if kind:
            body.append((index, text))
    if kind:
        sections.append(_Section(kind, arg, body))
    return sections


def _owner(arg: str, name: str) -> str:
    """Return the package a %files section belongs to."""
    parts = arg.split()
    if parts[:1] == ['-n'] and len(parts) > 1:
        return parts[1]
    if not parts or parts[0].startswith('-'):
        return name
    return f'{name}-{parts[0]}'


def _segments(text: str) -> list[str]:
    return [segment for segment in text.split('/') if segment]


def _classify(base: str, tail: list[str]) -> tuple[str, list[str]]:
    """Return the container of a path below the fonts directory."""
    if base != 'fonts' or not tail:
        return base, tail
    if tail[0] in CONTAINER:
        return tail[0], tail[1:]
    if tail[0] == 'X11' and len(tail) > 1:
        key = f'X11/{tail[1]}'
        if key in CONTAINER:
            return key, tail[2:]
    return base, tail


def _location(token: str) -> tuple[str, list[str]]:
    """Return ``(directory key, remaining segments)`` of one path token.

    The key is a container of the page, one of the two side directories, the
    name of some other directory under %{_datadir}, or ``fonts`` when the
    token names the top level itself.
    """
    for macro, root in _DIR_MACRO_ROOTS:
        if token.startswith(macro):
            return _classify(root, _segments(token[len(macro):]))
    text = token
    for prefix in ('%{buildroot}', '%{_datadir}', '/usr/local/share',
                   '/usr/share'):
        text = text.replace(prefix, '', 1)
    segments = _segments(text)
    if not segments:
        return '', []
    head, tail = segments[0], segments[1:]
    if head == 'fonts':
        return _classify('fonts', tail)
    if head == 'fontconfig':
        if tail[:1] == ['conf.avail']:
            return 'fontconfig/conf.avail', tail[1:]
        return 'fontconfig', tail
    return head, tail


def _path_tokens(text: str) -> list[str]:
    """Return every font directory path the line spells out."""
    tokens = [match.group(0) for match in RE_SHARE_PATH.finditer(text)]
    tokens += [match.group(0) for match in RE_DATADIR_PATH.finditer(text)]
    tokens += [match.group(0) for match in RE_DIR_MACRO_PATH.finditer(text)]
    return tokens


def _ships_font(text: str) -> bool:
    """Return whether one line of %install or %files places a font file."""
    if text.lstrip().startswith('#'):
        return False
    if RE_FONT_MACRO.search(text):
        return True
    if RE_FONT_FILE.search(text) is None:
        return False
    return bool(_path_tokens(text))


def _in_scope(spec: _Spec) -> bool:
    """Return whether the spec packages a system font."""
    if spec.name.lower().startswith(FONT_PREFIX):
        return True
    if RE_FONT_MACRO.search(spec.text):
        return True
    return any(
        _ships_font(text)
        for section in spec.sections
        if section.kind in ('install', 'files')
        for _line, text in section.body
    )


def _build_requirement_names(lines: Sequence[str]) -> set[str]:
    names: set[str] = set()
    for text in lines:
        match = RE_BUILD_REQUIRES.match(text)
        if match is None:
            continue
        for entry in match.group(1).split(','):
            parts = entry.split()
            if parts:
                names.add(parts[0].lower())
    return names


def _spec_of(lines: Sequence[str]) -> _Spec:
    text = '\n'.join(lines)
    macros = _definitions(lines)
    name = ''
    name_line = 0
    for index, line in enumerate(lines, start=1):
        match = RE_NAME.match(line)
        if match is not None:
            name = _expand(match.group(1).strip(), macros)
            name_line = index
            break
    licences = [
        (match.group(1).strip(), text.count('\n', 0, match.start()) + 1)
        for match in RE_LICENSE.finditer(text)
    ]
    return _Spec(
        name=name,
        name_line=name_line,
        macros=macros,
        sections=_sections(lines),
        licences=licences,
        build_requires=_build_requirement_names(lines),
        text=text,
    )


def _font_shipping_packages(spec: _Spec) -> list[tuple[str, int]]:
    """Return ``(package, line)`` for every package that ships a font."""
    found: list[tuple[str, int]] = []
    for section in spec.sections:
        if section.kind != 'files':
            continue
        package = _owner(section.arg, spec.name)
        for line, text in section.body:
            if text.lstrip().startswith('#'):
                continue
            if RE_FONT_FILE.search(text) is None:
                if RE_FONT_MACRO.search(text) is None:
                    continue
            found.append((package, line))
            break
    return found


def _macro_calls(spec: _Spec) -> list[_Call]:
    """Return every font macro call of the %install and %files sections."""
    calls: list[_Call] = []
    for section in spec.sections:
        if section.kind not in ('install', 'files'):
            continue
        for line, text in section.body:
            match = RE_FONT_MACRO_CALL.match(text.lstrip())
            if match is None:
                continue
            calls.append(
                _Call(match.group(1), line, text.strip(), match.group(2)),
            )
    return calls


def _layout(spec: _Spec) -> _Layout:
    """Collect the findings that read a path against the directory table."""
    outside: list[_Hit] = []
    misplaced: list[_Hit] = []
    mismatched: list[_Hit] = []
    bitmap: list[_Hit] = []
    unpacked: list[_Hit] = []
    install_macro: list[_Path] = []
    files_macro: list[_Path] = []

    for section in spec.sections:
        if section.kind not in ('install', 'files'):
            continue
        for line, text in section.body:
            if text.lstrip().startswith('#'):
                continue
            if RE_FONT_MACRO.search(text):
                continue
            extensions = [
                ext.lower() for ext in RE_FONT_FILE.findall(text)
            ]
            for token in _path_tokens(text):
                root = _location(token)[0]
                if root.startswith('fontconfig'):
                    continue
                if root not in CONTAINER and root not in SIDE:
                    if not extensions:
                        continue
                    outside.append(
                        _Hit(line, text, '', root or 'fonts'),
                    )
                    continue
                if root == 'fonts' and extensions:
                    outside.append(_Hit(line, text, '', 'fonts'))
                    continue
                if not extensions:
                    continue
                expected = DIR_MACRO.get(root)
                if (
                    expected is not None and expected not in text
                    and '%{_fontdir}' not in text
                ):
                    path = _Path(line, text, root, expected)
                    if section.kind == 'install':
                        install_macro.append(path)
                    else:
                        files_macro.append(path)
                for ext in extensions:
                    if root in SIDE:
                        if ext not in SIDE[root]:
                            misplaced.append(_Hit(line, text, ext, root))
                        continue
                    if ext not in CONTAINER[root]:
                        if ext in EXCEPTION_DIR:
                            misplaced.append(_Hit(line, text, ext, root))
                        else:
                            mismatched.append(_Hit(line, text, ext, root))
                    if ext == 'bdf':
                        bitmap.append(_Hit(line, text, ext, root))
                    if ext == 'pcf' and '.gz' not in text:
                        unpacked.append(_Hit(line, text, ext, root))

    return _Layout(
        outside=outside,
        misplaced=misplaced,
        mismatched=mismatched,
        bitmap=bitmap,
        unpacked=unpacked,
        install_macro=install_macro,
        files_macro=files_macro,
    )


def _check_name_prefix(spec: _Spec) -> list[str]:
    """C1: a package that ships a font file is named with the fonts- prefix."""
    found: list[str] = []
    for package, line in _font_shipping_packages(spec):
        if package.lower().startswith(FONT_PREFIX):
            continue
        found.append(
            f'package "{package}" (line {line}) ships a font file but its '
            f'name does not carry the "{FONT_PREFIX}" prefix; a font '
            f'package must be named "fonts-<fontname>"',
        )
    return found


def _check_licence(spec: _Spec) -> list[str]:
    """C2: the licence must allow redistribution."""
    found: list[str] = []
    for value, line in spec.licences:
        lowered = value.lower()
        for token in PROPRIETARY:
            if token not in lowered:
                continue
            found.append(
                f'License: {value} (line {line}) names a licence that does '
                f'not allow redistribution; packaging a proprietary font '
                f'that may not be redistributed is forbidden, so prefer a '
                f'family under the OFL or the GPL',
            )
            break
    return found


def _check_install_dir(layout: _Layout) -> list[str]:
    """C3: a font file lands in a directory the page documents."""
    found: list[str] = []
    for hit in layout.outside:
        where = (
            '%{_datadir}/fonts' if hit.root == 'fonts'
            else f'%{{_datadir}}/{hit.root}'
        )
        found.append(
            f'{hit.text} (line {hit.line}) installs a font file into '
            f'"{where}"; a system font belongs under '
            f'%{{_datadir}}/fonts in a container such as truetype, '
            f'opentype, misc, type1 or X11/misc, or in consolefonts or '
            f'webfonts when it is a console or Web font',
        )
    return found


def _spell_extensions(extensions: Iterable[str]) -> str:
    """Return the given formats spelled in the order the page lists them."""
    wanted = set(extensions)
    return ', '.join(
        f'"*.{ext}"' for ext in FONT_EXTENSIONS if ext in wanted
    )


def _exception_reason(hit: _Hit) -> str:
    target = EXCEPTION_DIR.get(hit.ext)
    if target is None:
        allowed = _spell_extensions(SIDE[hit.root])
        return (
            f'%{{_datadir}}/{hit.root} only holds {allowed}, and neither '
            f'the console font directory nor the Web font directory is a '
            f'directory fontconfig scans'
        )
    return (
        f'the page sends "*.{hit.ext}" to %{{_datadir}}/{target} so that '
        f'fontconfig never finds it'
    )


def _check_exception_dir(layout: _Layout) -> list[str]:
    """C4: a console or Web font goes to its own directory."""
    found: list[str] = []
    for hit in layout.misplaced:
        found.append(
            f'{hit.text} (line {hit.line}) installs "*.{hit.ext}" into '
            f'"%{{_datadir}}/{hit.root}"; {_exception_reason(hit)}',
        )
    return found


def _check_extension(layout: _Layout) -> list[str]:
    """C5: the extension matches the container it is installed into."""
    found: list[str] = []
    for hit in layout.mismatched:
        allowed = _spell_extensions(CONTAINER[hit.root])
        found.append(
            f'{hit.text} (line {hit.line}) installs "*.{hit.ext}" into '
            f'"%{{_datadir}}/fonts/{hit.root}", which holds {allowed}; '
            f'the page classifies "*.{hit.ext}" under another container',
        )
    return found


def _check_bdf(layout: _Layout) -> list[str]:
    """C6: a bitmap font is converted from *.bdf to *.pcf."""
    found: list[str] = []
    for hit in layout.bitmap:
        found.append(
            f'{hit.text} (line {hit.line}) packages a "*.bdf" bitmap font; '
            f'a *.bdf file must be converted to *.pcf before it is '
            f'packaged',
        )
    return found


def _check_pcf_gzip(layout: _Layout) -> list[str]:
    """C7: a *.pcf bitmap font is gzipped."""
    found: list[str] = []
    for hit in layout.unpacked:
        found.append(
            f'{hit.text} (line {hit.line}) installs a "*.pcf" bitmap font '
            f'that is not compressed; a *.pcf file must be compressed with '
            f'gzip first, so the path ends in "*.pcf.gz"',
        )
    return found


def _check_macro_requires(spec: _Spec) -> list[str]:
    """C8: a spec that uses the font macros declares the macro package."""
    calls = _macro_calls(spec)
    if not calls:
        return []
    if MACROS_PACKAGE in spec.build_requires:
        return []
    first = calls[0]
    return [
        f'{first.text} (line {first.line}) calls "%{first.macro}" but the '
        f'spec declares no "BuildRequires:  {MACROS_PACKAGE}"; a spec that '
        f'uses the font install macros must add that build dependency',
    ]


def _check_install_macro(layout: _Layout) -> list[str]:
    """C9: %install reaches a font directory through the macro."""
    found: list[str] = []
    for path in layout.install_macro:
        found.append(
            f'{path.text} (line {path.line}) spells the "{path.root}" '
            f'directory out instead of using "{path.expected}"; %install '
            f'must use the font directory macros the page lists rather '
            f'than a hardcoded path',
        )
    return found


def _check_files_macro(layout: _Layout) -> list[str]:
    """C10: %files reaches a font directory through the macro."""
    found: list[str] = []
    for path in layout.files_macro:
        found.append(
            f'{path.text} (line {path.line}) spells the "{path.root}" '
            f'directory out instead of using "{path.expected}"; %files '
            f'must use the font directory macros the page lists rather '
            f'than a hardcoded path',
        )
    return found


def _trailing_extension(name: str) -> str | None:
    """Return the extension of a file name or glob, or None."""
    stem = name.rsplit('/', 1)[-1]
    if '.' not in stem:
        return None
    ext = stem.rsplit('.', 1)[1]
    if not ext.isalnum() or len(ext) > 5:
        return None
    return ext.lower()


def _check_install_font_ext(spec: _Spec) -> list[str]:
    """C11: the install macros only place the formats they support."""
    found: list[str] = []
    for call in _macro_calls(spec):
        if call.macro == 'install_fonts_auto':
            continue
        parts = call.rest.split()
        if not parts:
            continue
        ext = _trailing_extension(parts[0])
        if ext is None or ext in MACRO_EXTENSIONS:
            continue
        found.append(
            f'{call.text} (line {call.line}) passes "*.{ext}" to '
            f'%{call.macro}; %{call.macro} places "*.ttf" and "*.ttc" in '
            f'the truetype directory and "*.otf" in the opentype '
            f'directory, and any other extension fails the build',
        )
    return found


def _check_font_files_ext(spec: _Spec) -> list[str]:
    """C12: %font_files lists the extensions the package installs."""
    found: list[str] = []
    for call in _macro_calls(spec):
        if call.macro != 'font_files':
            continue
        if call.rest.split()[1:]:
            continue
        found.append(
            f'{call.text} (line {call.line}) lists no extension; '
            f'%font_files falls back to "ttf", "otf" and "ttc" when the '
            f'extension is omitted, and rpmbuild fails when any of the '
            f'three globs matches nothing, so list the extensions the '
            f'package actually installs',
        )
    return found


def _check_spec_fonts_ext(
    filename: str,
    *,
    check_name_prefix: bool = True,
    check_licence: bool = True,
    check_install_dir: bool = True,
    check_exception_dir: bool = True,
    check_extension: bool = True,
    check_bdf: bool = True,
    check_pcf_gzip: bool = True,
    check_macro_requires: bool = True,
    check_install_macro: bool = True,
    check_files_macro: bool = True,
    check_install_font_ext: bool = True,
    check_font_files_ext: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None
    if not (
        check_name_prefix or check_licence or check_install_dir or
        check_exception_dir or check_extension or check_bdf or
        check_pcf_gzip or check_macro_requires or check_install_macro or
        check_files_macro or check_install_font_ext or check_font_files_ext
    ):
        return []

    spec = _spec_of(lines)
    if not _in_scope(spec):
        return []
    layout = _layout(spec)

    errors: list[str] = []
    if check_name_prefix:
        errors.extend(_check_name_prefix(spec))
    if check_licence:
        errors.extend(_check_licence(spec))
    if check_install_dir:
        errors.extend(_check_install_dir(layout))
    if check_exception_dir:
        errors.extend(_check_exception_dir(layout))
    if check_extension:
        errors.extend(_check_extension(layout))
    if check_bdf:
        errors.extend(_check_bdf(layout))
    if check_pcf_gzip:
        errors.extend(_check_pcf_gzip(layout))
    if check_macro_requires:
        errors.extend(_check_macro_requires(spec))
    if check_install_macro:
        errors.extend(_check_install_macro(layout))
    if check_files_macro:
        errors.extend(_check_files_macro(layout))
    if check_install_font_ext:
        errors.extend(_check_install_font_ext(spec))
    if check_font_files_ext:
        errors.extend(_check_font_files_ext(spec))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_fonts(filename: str) -> list[str]:
    return _check_spec_fonts_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the requirements of the font packaging '
                    'guideline.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-name-prefix',
        action='store_true',
        help='do not report a package that ships a font file without the '
             'fonts- prefix',
    )
    parser.add_argument(
        '--no-check-licence',
        action='store_true',
        help='do not report a licence that forbids redistribution',
    )
    parser.add_argument(
        '--no-check-install-dir',
        action='store_true',
        help='do not report a font file installed outside the documented '
             'font directories',
    )
    parser.add_argument(
        '--no-check-exception-dir',
        action='store_true',
        help='do not report a console or Web font installed outside '
             'consolefonts or webfonts',
    )
    parser.add_argument(
        '--no-check-extension',
        action='store_true',
        help='do not report an extension that does not match its container',
    )
    parser.add_argument(
        '--no-check-bdf',
        action='store_true',
        help='do not report a *.bdf bitmap font that was not converted to '
             '*.pcf',
    )
    parser.add_argument(
        '--no-check-pcf-gzip',
        action='store_true',
        help='do not report a *.pcf bitmap font that is not compressed',
    )
    parser.add_argument(
        '--no-check-macro-requires',
        action='store_true',
        help='do not report a spec that uses a font macro without the '
             'fonts-rpm-macros build dependency',
    )
    parser.add_argument(
        '--no-check-install-macro',
        action='store_true',
        help='do not report a %install line that spells a font directory '
             'out instead of using its macro',
    )
    parser.add_argument(
        '--no-check-files-macro',
        action='store_true',
        help='do not report a %files line that spells a font directory '
             'out instead of using its macro',
    )
    parser.add_argument(
        '--no-check-install-font-ext',
        action='store_true',
        help='do not report a %install_font or %install_fonts call with an '
             'unsupported extension',
    )
    parser.add_argument(
        '--no-check-font-files-ext',
        action='store_true',
        help='do not report a %font_files call that lists no extension',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_fonts_ext(
            filename,
            check_name_prefix=not args.no_check_name_prefix,
            check_licence=not args.no_check_licence,
            check_install_dir=not args.no_check_install_dir,
            check_exception_dir=not args.no_check_exception_dir,
            check_extension=not args.no_check_extension,
            check_bdf=not args.no_check_bdf,
            check_pcf_gzip=not args.no_check_pcf_gzip,
            check_macro_requires=not args.no_check_macro_requires,
            check_install_macro=not args.no_check_install_macro,
            check_files_macro=not args.no_check_files_macro,
            check_install_font_ext=not args.no_check_install_font_ext,
            check_font_files_ext=not args.no_check_font_files_ext,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret
