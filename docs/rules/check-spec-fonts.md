# check-spec-fonts

Enforce the requirements that the font packaging guideline states for a
package that ships a system font: how it is named, which licence it may
carry, which directory each format belongs in, and which macro the
`%install` and `%files` sections must use instead of a hardcoded path.

## Original Requirement

Source:
<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/FontPackagingGuidelines>

The page is written in Chinese. The quotations below are translations of
the clauses this rule reads.

Section "Package naming" states, verbatim:

> Every font package is named `fonts-fontname`, where `fontname` is the
> canonical name of the font. The name may follow the `Family` or the
> `Typographic Family` entry of the OpenType name table, but the upstream
> project name wins when the two disagree.
>
> An abbreviation the upstream project has long used, or one that has
> already become a de-facto standard in the Linux ecosystem, is allowed as
> long as it does not collide with another font project, so WenQuanYi may
> be abbreviated to `wqy` and packaged as `fonts-wqy`.

Section "Licence" states, verbatim:

> Always remember: packaging a proprietary font that may not be
> redistributed is forbidden. When a font is introduced, prefer a family
> under a licence such as the OFL or the GPL.

Section "Installation location" states, verbatim:

> A system font belongs under the `%{_datadir}/fonts` directory and is
> classified by container:
>
> - OpenType TT (`*.ttf`/`*.ttc`) belongs in `%{_datadir}/fonts/truetype`.
> - OpenType CFF/CFF2 (`*.otf`/`*.otc`) belongs in
>   `%{_datadir}/fonts/opentype`.
>
> fontconfig scans the paths below it recursively and maintains a cache,
> so the layering does not affect discovery.

Section "Bitmap fonts" states, verbatim:

> Bitmap fonts are handled in two ways, and the second way should not be
> packaged unless it is necessary:
>
> - The OpenType bitmap format (`*.otb`) that modern fontconfig and Xft
>   use belongs in `%{_datadir}/fonts/misc`. X11 bitmap files
>   (`*.pcf`)/(`*.bdf`) that are genuinely needed alongside it may be
>   placed in the same directory.
> - The legacy Core X11 fonts (XLFD) bitmap format (`*.pcf`) must be
>   compressed with gzip first and then installed by resolution into
>   `%{_datadir}/fonts/X11/100dpi/` or `%{_datadir}/fonts/X11/75dpi/`,
>   with a low-resolution or monospaced font going to
>   `%{_datadir}/fonts/X11/misc/`. When the format is `*.bdf`, it must be
>   converted to `*.pcf`.
>
> The legacy fonts should not be depended on by default and should not be
> preinstalled.

Section "Type 1" states, verbatim:

> Type 1 (`*.pfa`/`*.pfb`) is a legacy format. FreeType still supports it,
> but many modern applications are dropping it, so when upstream also
> publishes an OpenType TT or CFF/CFF2 font the OpenType version should be
> packaged first. When the format does have to be packaged, it belongs in
> `%{_datadir}/fonts/type1`. A metrics file (`*.afm`) shipped with the
> font must be packaged into the directory as well.

Section "Exceptions" states, verbatim:

> The Linux console font (`*.psf`) and the Web font
> (`*.woff`/`*.woff2`) must not be installed in a directory fontconfig can
> find. The latter is called out by the WOFF specification, which says a
> WOFF file should not be treated as a desktop-installable format.
>
> - The console font (`*.psf`) belongs in `%{_datadir}/consolefonts`.
> - The Web font (`*.woff`) belongs in `%{_datadir}/webfonts`.

Section "Directory macros" states, verbatim:

> `%install` and `%files` should use the following macros rather than a
> hardcoded path:
>
> - `%{_fontdir}` for `%{_datadir}/fonts`, the top level of a system font.
> - `%{_font_truetypedir}` for `%{_fontdir}/truetype`.
> - `%{_font_opentypedir}` for `%{_fontdir}/opentype`.
> - `%{_font_fontconfigdir}` for `%{_datadir}/fontconfig/conf.avail`.

Section "Macros" states, verbatim:

> The `fonts-rpm-macros` package provides the RPM macros that spell the
> font directories described above and install a font file into them.
> Using them requires the build dependency:
>
> ```specfile
> BuildRequires:  fonts-rpm-macros
> ```
>
> The current macros cover OpenType TT (`*.ttf`/`*.ttc`) and OpenType
> CFF/CFF2 (`*.otf`). The remaining formats, such as `*.otc`, `*.otb`,
> `*.pcf`, `*.pfb`, `*.psf` and `*.woff`, must still be installed by hand
> along the paths given in the installation location section.

Section "`%install_font`" states, verbatim:

> `%install_font <src> [subdir]` installs a single font file and picks the
> destination by extension: `*.ttf` and `*.ttc` go to
> `%{_font_truetypedir}` and `*.otf` goes to `%{_font_opentypedir}`. Any
> other extension fails the build.

Section "`%install_fonts`" states, verbatim:

> `%install_fonts <glob> [subdir]` hands every file matched by `<glob>` to
> `%install_font`. A glob that matches nothing is skipped, so a match rule
> can be reserved for a format a version happens not to publish.

Section "`%font_files`" states, verbatim:

> `%font_files <subdir> [ext...]` generates the `%files` entries for a
> font installed under `<subdir>`. For each extension it generates the
> `%dir` entry of the owning type directory and the glob entry of the font
> file.
>
> List the extensions the package actually installs. When the extension is
> omitted the macro falls back to `ttf`, `otf` and `ttc`, and rpmbuild
> fails when any of the three globs matches nothing.

## Flags

Every checkpoint can be switched off on its own, so a repository that
deliberately deviates from one clause keeps the other eleven.

| Flag | Default | Effect |
| --- | --- | --- |
| `--no-check-name-prefix` | on | Do not report a package that ships a font file without the `fonts-` prefix. |
| `--no-check-licence` | on | Do not report a licence that forbids redistribution. |
| `--no-check-install-dir` | on | Do not report a font file placed outside the directories the page documents. |
| `--no-check-exception-dir` | on | Do not report a console or Web font placed in a directory fontconfig scans. |
| `--no-check-extension` | on | Do not report an extension that does not match its container. |
| `--no-check-bdf` | on | Do not report a packaged `*.bdf` bitmap font. |
| `--no-check-pcf-gzip` | on | Do not report an uncompressed `*.pcf` bitmap font. |
| `--no-check-macro-requires` | on | Do not report a font macro call without `BuildRequires: fonts-rpm-macros`. |
| `--no-check-install-macro` | on | Do not report a hardcoded font directory in `%install`. |
| `--no-check-files-macro` | on | Do not report a hardcoded font directory in `%files`. |
| `--no-check-install-font-ext` | on | Do not report an extension the install macros cannot place. |
| `--no-check-font-files-ext` | on | Do not report a `%font_files` call that lists no extension. |

## Checkpoints

| ID | Checkpoint | Strength | Scope |
| --- | --- | --- | --- |
| C1 | A package that ships a font file is named with the `fonts-` prefix. | MUST | Font spec, judged on `%files`. |
| C2 | The licence allows redistribution. | MUST | Font spec, judged on the whole spec. |
| C3 | A font file is installed into a directory the page documents. | MUST | Font spec, judged on `%install` and `%files`. |
| C4 | A console or Web font goes into its own directory. | MUST | Font spec, judged on `%install` and `%files`. |
| C5 | The extension matches the container it is installed into. | MUST | Font spec, judged on `%install` and `%files`. |
| C6 | A `*.bdf` bitmap font is converted to `*.pcf` first. | MUST | Font spec, judged on `%install` and `%files`. |
| C7 | A `*.pcf` bitmap font is compressed with gzip. | MUST | Font spec, judged on `%install` and `%files`. |
| C8 | A spec that calls the font macros declares `fonts-rpm-macros`. | MUST | Font spec, judged on the whole spec. |
| C9 | `%install` reaches a font directory through the macro. | SHOULD | Font spec, judged on `%install`. |
| C10 | `%files` reaches a font directory through the macro. | SHOULD | Font spec, judged on `%files`. |
| C11 | The install macros only receive the extensions they support. | MUST | Font spec, judged on `%install` and `%files`. |
| C12 | `%font_files` lists the extensions the package installs. | MUST | Font spec, judged on `%install` and `%files`. |

Ten of the twelve checkpoints are MUST, and the page is why: every one of
them is spelled with an imperative rather than a preference.

* C1 rests on "Every font package is named `fonts-fontname`", the only
  sentence of the naming section written as a rule.
* C2 rests on "packaging a proprietary font that may not be redistributed
  is forbidden".
* C3 rests on "A system font belongs under the `%{_datadir}/fonts`
  directory and is classified by container".
* C4 rests on "must not be installed in a directory fontconfig can find".
* C5 rests on the three extension tables, each phrased as "belongs in".
* C6 rests on "When the format is `*.bdf`, it must be converted to
  `*.pcf`".
* C7 rests on "`*.pcf` must be compressed with gzip first".
* C8 rests on "Using them requires the build dependency".
* C11 rests on "Any other extension fails the build", which is a
  statement about the macro rather than a style choice.
* C12 rests on "List the extensions the package actually installs" plus
  the failure the omitted form provokes at build time.

C9 and C10 are SHOULD, and the wording is why: the directory macros are
introduced with "`%install` and `%files` should use the following macros
rather than a hardcoded path". The page states a recommendation, so the
finding reports a deviation rather than an error. A repository that
packages a font directory the macro table does not cover, or that spells
one out on purpose, turns the relevant flag off instead of rewording the
spec.

C9 and C10 are separate checkpoints rather than one because a spec can
honour one half of the clause and miss the other, and the corpus does
exactly that: ten specs spell the directory out in both sections, which
would collapse into one finding each under a combined checkpoint, and the
`%files` half would then be invisible next to the `%install` half.

## Scope

A spec is in scope for the twelve checkpoints when at least one of three
signals holds:

1. the main `Name:` field carries the `fonts-` prefix;
2. an `%install` or `%files` line installs or packs a font file into a
   font directory;
3. the spec calls one of `%install_font`, `%install_fonts`,
   `%install_fonts_auto` or `%font_files`.

The population is narrow on purpose. A browser, a boot loader or a console
tool that happens to carry a private font under `%{_libdir}` is an
application with an application asset, not a system font, and the page is
about system fonts. Without that bound, `firefox`, `grub` and
`console-setup` would each land in the population and every finding they
produced would be a false positive.

```
.spec files                                          6341
Font specs                                            14   <- the whole population
  Name carries the fonts- prefix                      13
  installs a font file without the prefix              1   <- unifont
C3, C4, C5, C6, C7, C9, C10 judged on %install/%files
C1, C2, C8, C11, C12 judged on the whole spec
```

The counts are measured against the openRuyi corpus, not asserted.

A line is read for a font file only when the `%install` or `%files` body
names a font extension and also spells a path this rule can classify.
Both halves are needed: an extension without a path is an upstream file
name the packager never places anywhere, and a path without an extension
is a directory the rule cannot tie to a format.

## C1 - a package that ships a font file carries the fonts- prefix

The checkpoint reads every `%files` section and takes the package owner
from the section header, so a subpackage declared as `%files vf` is judged
as `fonts-name-vf` and a section declared as `%files -n fonts-name-static`
is judged as `fonts-name-static`. The owner counts as a font package when
the section lists a font file or calls a font macro.

The finding names the prefix the page asks for:

```
package "demo-font" (line 19) ships a font file but its name does not
carry the "fonts-" prefix; a font package must be named "fonts-<fontname>"
```

The clause is spelled "Every font package is named `fonts-fontname`", with
no exception, so a font package without the prefix is a finding. The page
does allow an abbreviation of the font name — `fonts-wqy` for WenQuanYi —
but the abbreviation shortens `fontname`, never the prefix, so the prefix
itself stays required.

## C2 - the licence allows redistribution

The checkpoint reads every `License:` field, expands the macros of the
spec, and lowers the value before matching a short list of markers that
name a licence forbidding redistribution: `proprietary`, `commercial`,
`non-free`, `nonshared`, `limited`, `restricted` and `eula`.

```
License: Proprietary (line 5) names a licence that does not allow
redistribution; packaging a proprietary font that may not be redistributed
is forbidden, so prefer a family under the OFL or the GPL
```

The list is short on purpose. A `License` field is free text that may
combine several identifiers with `AND`, `OR` or `WITH`, and a rule that
tried to decide whether every combination permits redistribution would
need a licence database rather than a spec linter. Matching the seven
markers the corpus uses catches the prohibited case without guessing at
the permitted ones.

`check-spec-license` owns the field itself — whether `License` is
non-empty, whether it uses a valid SPDX expression, whether `%license`
lists the licence file. C2 only answers the second question the page asks
about the same field, which is whether the named licence may be
redistributed at all.

The preference in the same section — "prefer a family under a licence
such as the OFL or the GPL" — is not a checkpoint, because the page words
it as a preference and a font under the MIT licence is conforming.

## C3 - a font file is installed into a documented directory

The checkpoint classifies every path an `%install` or `%files` line
spells, after expanding `%{_fontdir}`, `%{_font_truetypedir}`,
`%{_font_opentypedir}` and `%{_font_fontconfigdir}` to the paths the page
lists. A path is reported when it lies under `%{_datadir}` or
`/usr/share` and is not one of:

* `%{_datadir}/fonts/<container>` for a container the page names
  (`truetype`, `opentype`, `misc`, `type1`, `X11/100dpi`, `X11/75dpi`,
  `X11/misc`);
* `%{_datadir}/consolefonts` or `%{_datadir}/webfonts`;
* `%{_datadir}/fontconfig`, which holds configuration rather than fonts.

Paths under `%{_datadir}/fonts` itself are reported too, because the page
says a system font "belongs under the `%{_datadir}/fonts` directory and is
classified by container": a font file loose at the top level is not
classified.

```
install -D -m 0644 demo.ttf %{buildroot}%{_datadir}/demo/demo.ttf (line 14)
installs a font file into "%{_datadir}/demo"; a system font belongs under
%{_datadir}/fonts in a container such as truetype, opentype, misc, type1
or X11/misc, or in consolefonts or webfonts when it is a console or Web
font
```

A path a `%files` section lists is judged by the same table as the
`%install` line that places it. The page writes the table for the
installation location, and the two sections name the same file from the
two ends of the build, so a spec that installs correctly and packs from
another directory is reported once, on the `%files` line.

The `fontconfig` exclusion is what keeps the rule quiet about the
configuration snippets a font package ships next to the font: the page
names `%{_font_fontconfigdir}` as `%{_datadir}/fontconfig/conf.avail` in
the same macro table, so a path there is documented rather than stray.

## C4 - a console or Web font goes into its own directory

The checkpoint reports a `*.psf`, `*.woff` or `*.woff2` file that lands
in a container of the scan paths — `truetype`, `opentype`, `misc`,
`type1`, `X11/100dpi`, `X11/75dpi`, `X11/misc` — rather than in the
directory the page gives it.

```
install -D -m 0644 demo.woff %{buildroot}%{_datadir}/fonts/truetype/demo.woff
(line 14) installs "*.woff" into "%{_datadir}/fonts/truetype"; the page
sends "*.woff" to %{_datadir}/webfonts so that fontconfig never finds it
```

The clause is "must not be installed in a directory fontconfig can find",
and it is the WOFF specification the page cites that makes it a MUST:
a WOFF file is a Web asset, so a desktop font cache that indexed it would
offer a format no desktop application uses.

The console font is reported the same way, with the reason spelled as the
directory the page gives it:

```
install -D -m 0644 demo.psf %{buildroot}%{_datadir}/fonts/misc/demo.psf
(line 14) installs "*.psf" into "%{_datadir}/fonts/misc"; the page sends
"*.psf" to %{_datadir}/consolefonts so that fontconfig never finds it
```

A format that has no exception directory — `*.ttf` in `webfonts`, for
instance — is also reported, with the allowed set named instead of a
destination. That case is reachable in both directions: a Web font
directory holding a desktop font would be indexed by nothing, and the page
wording "fontconfig never finds it" is a statement about the directory
rather than about one format.

## C5 - the extension matches the container

The checkpoint reads the container of the path and the extension of the
file, and reports the pair when the page classifies the extension under a
different container. The table is the one the installation location,
bitmap font and Type 1 sections give:

| Extension | Documented directory |
| --- | --- |
| `*.ttf`, `*.ttc` | `%{_datadir}/fonts/truetype` |
| `*.otf`, `*.otc` | `%{_datadir}/fonts/opentype` |
| `*.otb`, `*.pcf`, `*.bdf` | `%{_datadir}/fonts/misc` |
| `*.pfa`, `*.pfb`, `*.afm` | `%{_datadir}/fonts/type1` |
| `*.pcf` | `%{_datadir}/fonts/X11/100dpi`, `X11/75dpi`, `X11/misc` |

```
install -D -m 0644 demo.otf %{buildroot}%{_font_truetypedir}/demo/demo.otf
(line 14) installs "*.otf" into "%{_datadir}/fonts/truetype", which holds
"*.ttf", "*.ttc"; the page classifies "*.otf" under another container
```

The page says fontconfig scans the tree recursively and caches it, so a
file in the wrong container is still discovered — but the container name
is what a package manager, a downstream consumer and a directory listing
read to learn the format, so a mismatch is a finding even when the font
still works.

`*.pcf` is deliberately in four sets, because the page offers it as an
X11 bitmap format by resolution and as a companion of `*.otb` under
`misc`. A `*.pcf` in any of the four containers is conforming; a `*.pcf`
in `truetype` or `type1` is not.

## C6 - a *.bdf bitmap font is converted to *.pcf

The checkpoint reports any `*.bdf` file that an `%install` or `%files`
line places or packs.

```
install -D -m 0644 demo.bdf %{buildroot}%{_datadir}/fonts/misc/demo.bdf
(line 14) packages a "*.bdf" bitmap font; a *.bdf file must be converted
to *.pcf before it is packaged
```

The clause is "When the format is `*.bdf`, it must be converted to
`*.pcf`", inside the paragraph that calls the legacy Core X11 path
unnecessary unless it is genuinely needed. The page never names a
directory for a `*.bdf` file, which is the point: the format has no
destination because it is an intermediate the build converts away.

## C7 - a *.pcf bitmap font is compressed with gzip

The checkpoint reports a `*.pcf` file whose path does not end in
`*.pcf.gz`.

```
install -D -m 0644 demo.pcf %{buildroot}%{_datadir}/fonts/X11/misc/demo.pcf
(line 14) installs a "*.pcf" bitmap font that is not compressed; a *.pcf
file must be compressed with gzip first, so the path ends in "*.pcf.gz"
```

The clause is "must be compressed with gzip first and then installed by
resolution", so the compression is a property of the installed file rather
than of the source archive. The 600-odd bitmap font packages of the
corpus all ship `*.pcf.gz`, which is why the count is zero.

## C8 - a spec that calls the font macros declares fonts-rpm-macros

The checkpoint reports the first font macro call of a spec that declares
no `BuildRequires:  fonts-rpm-macros`.

```
%install_fonts *.woff2 demo (line 16) calls "%install_fonts" but the spec
declares no "BuildRequires:  fonts-rpm-macros"; a spec that uses the font
install macros must add that build dependency
```

The macros live in that package, so a spec that calls one without the
dependency fails to build with an undefined macro rather than with a wrong
layout. The clause is "Using them requires the build dependency", written
immediately after the dependency line, so the checkpoint is a MUST.

One finding per spec rather than one per call, because the dependency is a
property of the spec: a spec with six macro calls and no dependency has
one cause and one fix. The first call is named so the finding points at a
line the reader can open.

`check-spec-build-rust` reports the missing `rust-rpm-macros` for the same
reason and for a different population, and the two rules never judge the
same spec: a font spec is not a Rust provider, and a Rust provider is not
a font spec.

## C9 - %install reaches a font directory through the macro

The checkpoint reports the `%install` line of a font spec that spells out
`%{_datadir}/fonts/truetype`, `%{_datadir}/fonts/opentype` or
`%{_datadir}/fontconfig/conf.avail` instead of using
`%{_font_truetypedir}`, `%{_font_opentypedir}` or
`%{_font_fontconfigdir}`.

```
install -m 0644 -p *.ttf %{buildroot}%{_datadir}/fonts/truetype/firacode-nerd/
(line 30) spells the "truetype" directory out instead of using
"%{_font_truetypedir}"; %install must use the font directory macros the
page lists rather than a hardcoded path
```

The page gives three directory macros — `truetype`, `opentype` and
`fontconfig` — so the checkpoint reports exactly those three. A line that
writes `%{_fontdir}/truetype` is accepted as well, because the page defines
`%{_font_truetypedir}` as `%{_fontdir}/truetype` and the expansion is the
same path; a line that writes `%{_fontdir}` alone is accepted for the
top-level directory the page documents.

The `misc`, `type1`, `X11` and `consolefonts` directories have no macro
and the page says so — "The remaining formats must still be installed by
hand along the paths given in the installation location section" — so a
spec that spells them out is conforming and is not reported.

## C10 - %files reaches a font directory through the macro

The same clause as C9, judged on the `%files` side.

```
%{_datadir}/fonts/truetype/*.ttf (line 51) spells the "truetype" directory
out instead of using "%{_font_truetypedir}"; %files must use the font
directory macros the page lists rather than a hardcoded path
```

The two checkpoints are separate because the sections are separate: ten
specs of the corpus spell the directory out in `%install` and again in
`%files`, and a fix applied to one section does not touch the other. A
repository that keeps `%files` written by hand for a reason turns the
`--no-check-files-macro` flag off and keeps C9 on.

## C11 - the install macros only receive supported extensions

The checkpoint reads the first argument of `%install_font` and
`%install_fonts` and reports an extension outside `ttf`, `ttc` and `otf`.
The trailing-extension autodetecting form `%install_fonts_auto` is
skipped, because the page describes it as choosing the extension by
itself.

```
%install_fonts *.woff2 demo (line 16) passes "*.woff2" to %install_fonts;
%install_fonts places "*.ttf" and "*.ttc" in the truetype directory and
"*.otf" in the opentype directory, and any other extension fails the
build
```

The clause is "Any other extension fails the build", and the macros
section repeats the boundary from the other side when it says the current
macros cover `*.ttf`, `*.ttc` and `*.otf` while "the remaining formats
must still be installed by hand". A `*.woff2` handed to the macro is not a
style problem; rpmbuild stops.

A glob the rule cannot read an extension from — `*.fonts.tar.xz`, an
unexpanded macro, a directory — is skipped rather than guessed at.

## C12 - %font_files lists the extensions the package installs

The checkpoint reads the arguments of `%font_files` and reports a call
that names a subdirectory and no extension.

```
%font_files demo (line 20) lists no extension; %font_files falls back to
"ttf", "otf" and "ttc" when the extension is omitted, and rpmbuild fails
when any of the three globs matches nothing, so list the extensions the
package actually installs
```

The clause is "List the extensions the package actually installs", and the
reason it is a MUST is the failure the page spells out in the same
paragraph: the three fallback globs are all expanded, and a font that
publishes only `*.ttf` makes the `*.otf` and `*.ttc` globs match nothing.
A collection file is the common case — `fonts-noto-sans-cjk` ships `*.ttc`
and calls `%font_files NotoSansCJK ttc` — which is exactly the case the
fallback breaks.

## Scope notes

Measured against the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`:

| Metric | Count |
| --- | --- |
| `.spec` files scanned | 6341 |
| Font specs in scope | 14 |
| Findings, default flags | 27 |
| Files with at least one finding | 10 |

Per checkpoint:

| ID | Findings | Notes |
| --- | --- | --- |
| C1 | 0 | Every package that ships a font is named `fonts-*`, including `unifont`. |
| C2 | 0 | Every font spec carries an open licence, mostly `OFL-1.1` and `GPL-*`. |
| C3 | 0 | Every font file lands in a container the page documents. |
| C4 | 0 | No console or Web font is installed into a scan path. |
| C5 | 0 | Every extension matches its container. |
| C6 | 0 | No spec packages a `*.bdf` file. |
| C7 | 0 | Every `*.pcf` in the corpus is already `*.pcf.gz`. |
| C8 | 0 | All three specs that call the macros declare `fonts-rpm-macros`. |
| C9 | 16 | Ten specs spell the `truetype`, `opentype` or `fontconfig` directory out in `%install`. |
| C10 | 11 | The same ten specs repeat the path in `%files`; `fonts-noto-sans-cjk` and `unifont` each carry more than one `%install` line. |
| C11 | 0 | The macros only receive `*.ttf`, `*.ttc` and `*.otf`. |
| C12 | 0 | Every `%font_files` call lists its extensions. |

Ten files carry twenty-seven findings, and the distribution is worth
reading in full:

- `fonts-codenewroman-nerd`, `fonts-firacode-nerd`,
  `fonts-iosevka-nerd`, `fonts-jetbrainsmono-nerd`: one finding in
  `%install` and one in `%files` each, all on the `truetype` directory
  spelled out as `%{_datadir}/fonts/truetype/...`.
- `fonts-dejavu`, `fonts-hack`, `fonts-noto-color-emoji`,
  `fonts-noto-serif-cjk`: the same pair, on `truetype`.
- `fonts-noto-sans-cjk`: five findings, three in `%install` (lines 58,
  59 and 63, the two `opentype` copies and the `truetype` copy) and one in
  `%files` (line 74).
- `unifont`: six findings, five in `%install` (lines 70, 74, 76, 78 and
  80, one `truetype` and four `opentype` copies) and two in `%files`
  (lines 97 and 98).

The four specs that use the macros — `fonts-fontawesome`, `fonts-noto`,
`fonts-sarasa-gothic` and `fonts-rpm-macros` — carry no finding, which is
the intended shape: the macros carry the directory so the packager never
writes it.

The eight zeroes are real rather than a sign of a checkpoint that never
runs. Each is anchored on a table the corpus honours: the fourteen in-scope
specs are hand-written and reviewed, so a wrong container, a stray licence
or a `*.bdf` in the tree would have been caught before the package landed.
The two checkpoints that do fire are the two whose clause is a SHOULD, and
that is the expected shape of a recommendation in a corpus written by
hand.

### Rejected candidates

| Candidate | Corpus count | Why it is rejected |
| --- | --- | --- |
| The main package of a multi-format font ships no font file. | 14 specs, 0 violate | The clause is "the main package acts as a metapackage", written as a recommendation, and the corpus already conforms. |
| A subpackage is named `-vf` or `-static` rather than `-ttc` or `-otc`. | 3 subpackages | The page offers `-ttc` and `-otc` for a collection, so all four suffixes are documented. |
| The metapackage declares `Requires: fonts-fontname-vf`. | 0 metapackages | The page writes "may declare", so a metapackage without the dependency is conforming. |
| A font package is `BuildArch: noarch`. | 14 of 14 | Every font spec is architecture independent, so the finding would hit 100% of the population. |
| A font package declares `%{_fontdir}` in `%files` rather than the container macro. | 4 use `%{_fontdir}` | The page defines `%{_fontdir}` as the top level and a `%files` glob under it is the documented form for a directory the macro table does not cover. |
| Every spec that ships a font calls `%font_files` rather than listing the paths. | 10 do not | The macros cover `*.ttf`, `*.ttc` and `*.otf` only, and the page says the other formats must be installed by hand. |
| The font package keeps the upstream `LICENSE` file through `%license`. | owned elsewhere | `check-spec-license` already reads the `%license` list of every spec. |
| The font package declares a `Provides: font(...)` capability. | 0 specs | Neither the page nor the corpus mentions the capability, so the rule would invent a requirement. |
| A font archive is unpacked from its own `Source` rather than vendored. | not decidable | The spec records the source URL, not whether the archive content matches it. |
| The fonts of one upstream archive that belong to different families are split into separate packages. | not decidable | Requires reading the name table of the shipped font files, which a spec-only linter cannot do. |
| The legacy Core X11 fonts are not depended on by default. | repository policy | The clause governs a repository-wide package set rather than a property of one spec. |
| A `*.afm` metrics file is packaged next to its `*.pfb`. | 0 specs ship Type 1 | A true clause, but the corpus has no Type 1 font at all, so a checkpoint would carry no signal. |
| `Source0` points at the upstream font release rather than at a mirror. | owned elsewhere | `check-spec-source` reads the source fields of every spec. |

## Examples

A font package that passes every checkpoint, built from source and packed
through the macros:

```specfile
Name:           fonts-firacode
Version:        6.2
Release:        %autorelease
Summary:        Monospaced font with programming ligatures
License:        OFL-1.1
URL:            https://github.com/tonsky/FiraCode
Source0:        https://github.com/tonsky/FiraCode/archive/%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  fonts-rpm-macros

%description
Monospaced font with programming ligatures.

%prep
%autosetup -n FiraCode-%{version}

%install
%install_fonts distr/ttf/*.ttf firacode

%files
%license LICENSE
%doc README.md
%font_files firacode ttf

%changelog
%autochangelog
```

The same font packaged from a handwritten `%install`, with every directory
reached through the macro the page lists:

```specfile
Name:           fonts-dejavu
Version:        2.37
Release:        %autorelease
Summary:        Unicode font family based on Bitstream Vera
License:        Bitstream-Vera AND Public-Domain
URL:            https://dejavu-fonts.github.io/
Source0:        https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_%{version}/dejavu-fonts-ttf-%{version}.tar.bz2
BuildArch:      noarch

%description
Unicode font family based on Bitstream Vera.

%prep
%autosetup -n dejavu-fonts-ttf-%{version}

%install
install -D -m 0644 build/*.ttf %{buildroot}%{_font_truetypedir}/

%files
%license LICENSE
%doc README.md
%{_font_truetypedir}/*.ttf

%changelog
%autochangelog
```

A Web font, which belongs in `%{_datadir}/webfonts` and has no macro:

```specfile
Name:           fonts-noto-color-emoji
Version:        2.047
Release:        %autorelease
Summary:        Color emoji font from the Noto family
License:        OFL-1.1
URL:            https://fonts.google.com/noto
Source0:        https://github.com/googlefonts/noto-emoji/archive/v%{version}.tar.gz
BuildArch:      noarch

%description
Color emoji font from the Noto family.

%install
install -D -m 0644 fonts/NotoColorEmoji.ttf \
    %{buildroot}%{_font_truetypedir}/NotoColorEmoji.ttf
install -D -m 0644 fonts/NotoColorEmoji.woff2 \
    %{buildroot}%{_datadir}/webfonts/NotoColorEmoji.woff2

%files
%license LICENSE
%{_font_truetypedir}/NotoColorEmoji.ttf
%{_datadir}/webfonts/NotoColorEmoji.woff2

%changelog
%autochangelog
```
