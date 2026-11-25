# check-spec-programming-perl

Enforce the requirements that the Perl language packaging guideline states
for a package that ships a CPAN style Perl module.

## Original Requirement

Source:
<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/languages/Perl>

Section "Package Naming" states, verbatim:

> Name Perl module packages in the form of `perl-CPANDIST`, where `CPANDIST`
> is the name of the CPAN distribution being packaged.

> In rare cases, if a CPAN distribution must be split into smaller
> subpackages because of dependency relationships or similar reasons, name
> the additional subpackages `perl-CPANDIST-Something`.

Section "URL Tag" states, verbatim:

> For CPAN-based packages, the `URL` tag should use a non-versioned
> `metacpan.org` URL.

The section then gives the exact shape it asks for:

> For example, when packaging the `Net::XMPP` module:
>
> ```specfile
> URL:            https://metacpan.org/release/Net-XMPP
> ```

That example is worth reading twice, because it shows that a `/release/`
URL is accepted as long as it carries no version. C2 therefore judges only
the presence of a version in the path, not the choice between `/dist/` and
`/release/`.

Section "Build Dependencies" states, verbatim:

> A typical Perl module package using the declarative build systems starts
> with:
>
> ```specfile
> BuildRequires:  perl-rpm-packaging
> BuildRequires:  perl-rpm-macros
> BuildRequires:  perl-macros
> ```

> If your package requires specific Perl modules at build time, use the
> `perl(MODULE)` form. This rule also applies to core modules that Perl
> itself ships with, because upstream developers may move modules into or
> out of the base Perl package over time.

Section "Requires and Provides Tags" states, verbatim:

> When writing `Requires` and `Provides`, use the `perl(MODULE)` form rather
> than depending directly on package names.

> For example, a package requiring the Perl module `Archive::Zip` should not
> explicitly require the package name `perl-Archive-Zip`. Instead, it should
> require:
>
> ```specfile
> Requires:       perl(Archive::Zip)
> ```

Section "Choosing a Build System" and "Minimal Spec Structure" state,
verbatim:

> When writing a spec file manually, first check which upstream build script
> is used, then choose the corresponding build system instead of writing
> `%build`, `%install`, and `%check` logic from scratch.

> In most packages, you do not need to define custom `%build`, `%install`, or
> `%check` sections. Use `BuildOption(...)` entries only when the upstream
> build script needs extra arguments.

Section "File Listings" states, verbatim:

> Prefer the generated file list when using the declarative build systems.
> Manual file entries are mainly useful when custom install logic is
> required.

Section "`.h` Files in Module Packages" states, verbatim:

> If a Perl module includes `.h` files, do not split them into a `-devel`
> subpackage only because of those header files.

## Flags

Every checkpoint can be switched off on its own, so a repository that
deliberately deviates from one clause can keep the rest.

| Flag | Default | Effect |
| --- | --- | --- |
| `--no-check-package-name` | on | Do not report a package name that is not derived from the CPAN distribution. |
| `--no-check-url` | on | Do not report a non-metacpan or versioned metacpan `URL`. |
| `--no-check-shared-packages` | on | Do not report a missing shared Perl macro package. |
| `--no-check-build-module-form` | on | Do not report a plain `perl-*` name in `BuildRequires`. |
| `--no-check-runtime-capability` | on | Do not report a plain `perl-*` name in `Requires` or `Provides`. |
| `--no-check-declarative-stages` | on | Do not report a hand-written `%build`, `%install` or `%check`. |
| `--no-check-generated-filelist` | on | Do not report a `%files` section without `-f`. |
| `--no-check-devel-headers` | on | Do not report a header file moved into a `-devel` subpackage. |

## Checkpoints

| ID | Checkpoint | Strength | Scope |
| --- | --- | --- | --- |
| C1 | The package name is derived from the CPAN distribution. | MUST | Spec whose `URL` names a metacpan distribution. |
| C2 | A CPAN package uses a non-versioned metacpan `URL`. | MUST | Spec whose source entry fetches a tarball from CPAN. |
| C3 | A declarative package declares the three shared macro packages. | SHOULD | Spec with `BuildSystem: perlbuild` or `perlmaker`. |
| C4 | A build dependency on a module uses the `perl(MODULE)` form. | MUST | Any spec in scope. |
| C5 | `Requires` and `Provides` use the `perl(MODULE)` form. | SHOULD | Any spec in scope. |
| C6 | A declarative package does not hand-write build stages. | SHOULD | Spec with `BuildSystem: perlbuild` or `perlmaker`. |
| C7 | The main file list reads a generated file list. | SHOULD | Spec with `BuildSystem: perlbuild` or `perlmaker`. |
| C8 | Header files stay in the module package. | MUST | Any spec in scope. |

The strength column follows the wording of the page. A clause that gives a
direct naming rule ("Name Perl module packages in the form of ...", "use
the `perl(MODULE)` form rather than depending directly on package names")
or a direct prohibition ("do not split them into a `-devel` subpackage")
is treated as MUST. A clause worded as an expectation ("A typical Perl
module package using the declarative build systems starts with ...", "In
most packages, you do not need to define custom `%build` ... sections",
"Prefer the generated file list") or as "should use" is treated as SHOULD,
which is why C3, C5, C6 and C7 are the ones a downstream repository is most
likely to switch off.

## Scope

A spec is judged when it declares a declarative Perl build system
(`BuildSystem: perlbuild` or `BuildSystem: perlmaker`) **or** when its
expanded `Name` starts with `perl-`. The second condition exists because
the automation section of the page states that the `-x` output of
`cpan2spec` should be converted to a declarative build system, so a
`perl-` named spec without one is exactly the shape that still needs
judging. A spec of any other language is ignored, which keeps the rule
silent on the thousands of non-Perl specs in the corpus.

## C1 - the package name is derived from the CPAN distribution

The CPAN distribution name is read from the `URL`, because that is the only
place a spec-only linter can read it from without resolving the source
tarball. The check therefore applies to a spec whose `URL` contains a
`metacpan.org/dist/<dist>` or `metacpan.org/release/<dist>` path, and to a
spec whose subpackage header names a package that does not descend from
that distribution.

Example finding:

```text
demo.spec: Name: perl-Archive-Zipper (line 1) does not follow the package
naming rule; the URL (line 6) names the CPAN distribution "Archive-Zip",
so name the package "perl-Archive-Zip"
```

Example finding for a subpackage:

```text
demo.spec: %package perl-Demo-Extra (line 18) does not follow the package
naming rule; a subpackage of the CPAN distribution "Demo-Module" is named
"perl-Demo-Module-Something"
```

Deciding details:

- The comparison folds `+` and `_` into `-` and ignores case, because the
  CPAN distribution `Text-Tabs+Wrap` is packaged as `perl-Text-Tabs-Wrap`
  while its metacpan URL keeps the `%2B`.
- A `Name` that still contains a macro after expansion is skipped. The
  corpus holds `perl-Locale-gettext`, whose `Name: perl-%{tarname}` expands
  to a name that does match its distribution, and a linter must not report
  a spelling it cannot resolve.
- A `/release/DIST-VERSION` URL carries the version inside the path, so a
  trailing `-1.23` is removed before the name is compared. Without that
  step the same spec would be reported by both C1 and C2.
- A `Name` that carries no metacpan distribution is skipped rather than
  guessed. `po4a` declares `BuildSystem: perlbuild` and is a Perl project,
  but it is not a CPAN module package.

## C2 - a CPAN package uses a non-versioned metacpan URL

The page scopes this clause to CPAN based packages, so the check is gated
on a source entry that fetches a tarball from `cpan.metacpan.org` or
`www.cpan.org` under `/authors/id/`. That gate is what keeps `po4a`, which
builds from a GitHub release tarball, out of scope.

Example finding:

```text
demo.spec: URL: http://www.template-toolkit.org (line 12) is not a
metacpan URL; the page asks a CPAN based package for its non-versioned
metacpan.org address
```

Example finding for a pinned version:

```text
demo.spec: URL: https://metacpan.org/release/Archive-Zip-1.68 (line 6)
pins the distribution version; the page asks for a non-versioned
metacpan URL
```

Deciding details:

- Both `/dist/` and `/release/` are accepted, because the page's own
  example uses `/release/Net-XMPP`.
- Only the path segment that names the distribution is searched for a
  version. A version in a query string, in a fragment, or in the host name
  is not a finding.
- A `URL` that is still a macro after expansion is skipped, because the
  linter cannot expand an unknown macro into a host name.

## C3 - a declarative package declares the three shared macro packages

The page lists the three packages as the build dependencies a declarative
package usually needs, and the minimal spec structure repeats all three.
The check reads the merged `BuildRequires` set of every package block,
because RPM treats `BuildRequires` as a source-package level field.

Example finding:

```text
demo.spec: BuildSystem: perlmaker (line 10) requires the shared Perl build
dependencies in BuildRequires; missing perl-macros
```

Deciding details:

- Only the macro-expanded `BuildSystem` value is read. A spec whose
  `BuildSystem` is `cmake` is out of scope even when it packages Perl.
- A versioned dependency such as `perl-macros >= 1.0` satisfies the
  requirement, because the name is what the page asks for.
- A `perl-macros-extra` does not satisfy `perl-macros`, because the two are
  different packages.

## C4 - a build dependency on a module uses the perl(MODULE) form

The page asks for the `perl(MODULE)` form and states that it also applies
to the core modules Perl itself ships, so no module is exempt on the ground
that it is already part of the interpreter.

Example finding:

```text
demo.spec: BuildRequires (line 20) names the package
"perl-ExtUtils-MakeMaker"; the page asks for the module capability
"perl(ExtUtils::MakeMaker)"
```

Deciding details:

- The reported name keeps the spelling of the spec, and the suggested
  capability is derived by replacing `perl-` with `perl(` and every `-`
  with `::`. The spelling of the module in CPAN metadata is not guessed.
- The three shared macro packages, `perl-devel`, `perl-libs` and `perl-doc`
  are exempt, because they are packages and not module capabilities. The
  page names the macro packages itself, and `perl-devel` provides the Perl
  headers.
- The plain `perl` dependency with a version operator is exempt, because
  `perl >= 5.6.0` names the interpreter rather than a module.
- A rich dependency in parentheses is skipped, because it names no plain
  package at the top level.

## C5 - Requires and Provides use the perl(MODULE) form

The page words this clause as "use the `perl(MODULE)` form rather than
depending directly on package names" and explains why: the
package that provides the module satisfies the capability, while a plain
name dependency breaks when the package is renamed. The same exemptions as
C4 apply.

Example finding:

```text
demo.spec: Requires (line 24) names the package "perl-File-Spec"; the page
asks Requires and Provides to use the module capability "perl(File::Spec)"
```

Deciding details:

- Both fields are read, including their script qualifiers, so
  `Requires(post):` is reported in the same way as `Requires:`.
- A dependency that names the interpreter, such as `Requires: perl >= 5.10`,
  or a toolchain package such as `Requires: perl-devel`, is exempt.
- A `-devel` subpackage may still carry a plain `perl-` name in `Provides`
  when the name is the package's own name, because the capability of a
  module is provided by its own package. The finding quotes the capability
  the page would ask for, and the packager decides whether the subpackage
  really is a module package.

## C6 - a declarative package does not hand-write build stages

The page states that most packages need no custom stage and that extra
upstream arguments belong in `BuildOption(...)`, and adds that a packager
checks the upstream build script rather than writing the stages from
scratch.

Example finding:

```text
demo.spec: %check (line 55) is a hand-written stage in a BuildSystem:
perlmaker (line 17) spec; the page states these stages are normally not
needed, and extra upstream arguments belong in BuildOption(...)
```

Deciding details:

- A section header is recognised only when its name is one of the real RPM
  sections, so a macro invocation such as `%license`, `%doc` or
  `%perl_gen_filelist` is never read as a stage. That is the same closed
  section list `check-spec-basic-fields` uses.
- The section argument is part of the header, so `%build -p` and
  `%install -a` are recognised as stages. The corpus uses those spellings
  when the stage must run with a patched `%setup`, and they are still
  hand-written stages.
- An empty stage is reported as well, because an empty section still
  overrides the declarative behaviour.
- A spec without a Perl build system is out of scope, because the page
  scopes the clause to declarative packages. A hand-written
  `%build`/`%install`/`%check` in such a spec is the state the automation
  section asks the packager to convert.

## C7 - the main file list reads a generated file list

The page states that a declarative package installs through
`%perl_gen_filelist` and can therefore use the generated list, and words
the clause as a preference with `-f %{name}.files`.

Example finding:

```text
demo.spec: %files (line 34) does not read a generated file list; a
BuildSystem: perlmaker (line 10) package is expected to use
%files -f %{name}.files
```

Deciding details:

- Only the main `%files` section is judged. `%files -n <subpackage>` is a
  subpackage list, and `%perl_gen_filelist` writes one `%{name}.files` for
  the source package only.
- Any `-f <file>` option is accepted, not just `-f %{name}.files`,
  because the page states a preference rather than a file name.
- A spec with no `%files` section is not reported, because the missing
  section is already reported by `check-spec-basic-fields`.

## C8 - header files stay in the module package

The page states that a `.h` file of a Perl module is not moved into a
`-devel` subpackage merely because it is a header.

Example finding:

```text
demo.spec: %files -n perl-Demo-Module-devel entry
"%{_includedir}/Demo/Module.h" (line 26) is a header file in a -devel
subpackage; the page states a .h file of a Perl module is not moved into a
-devel subpackage merely because it is a header
```

Deciding details:

- Only a subpackage whose expanded name ends in `-devel` is judged, because
  that is the pattern the page names. A header listed by the main package
  is left alone.
- An entry is a header when its last token ends in `.h` or names
  `%{_includedir}`. A directory entry such as
  `%{_includedir}/Demo/` is not reported, because the header list is what
  the page talks about.
- A `%exclude` entry that names a header is reported like any other entry,
  because the subpackage still owns the header entry.

## Boundary with check-spec-build-perl

`check-spec-build-perl` already covers three clauses of the same page, and
two of them overlap this rule:

| Clause | Owner | Overlapping checkpoint here |
| --- | --- | --- |
| The shared Perl macro packages are declared. | `check-spec-build-perl` | C3 |
| A declarative package declares `perl(Module::Build)` or `perl(ExtUtils::MakeMaker)`. | `check-spec-build-perl` | none |
| The main file list reads `-f %{name}.files`. | `check-spec-build-perl` | C7 |

The overlap is deliberate: `check-spec-build-perl` is the narrower rule
that a build-system-only repository enables, and this rule repeats the two
clauses so a repository can enable a single Perl rule and still get them.
A repository that enables both should switch off the narrower rule for
those clauses, so a spec is reported once:

```yaml
- repo: https://github.com/openRuyi-Project/openruyi-precommit-hooks
  rev: <pinned>
  hooks:
    - id: check-spec-build-perl
      args: ['--no-check-shared-packages', '--no-check-files-list']
    - id: check-spec-programming-perl
```

The third part of the split is the missing module capability:
`check-spec-build-perl` asks for `perl(Module::Build)` or
`perl(ExtUtils::MakeMaker)` according to the declared build system, while
C4 asks that an existing plain module dependency be written in the
capability form, so the two report different sentences for different
findings.

## Scope notes

Measured against the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`:

| Metric | Count |
| --- | --- |
| `.spec` files scanned | 6341 |
| Perl family specs (`BuildSystem: perlbuild` or `perlmaker`) | 403 |
| Specs judged by the rule | 407 |
| Findings, default flags | 10 |
| Files with at least one finding | 10 |

Per checkpoint:

| ID | Findings | Notes |
| --- | --- | --- |
| C1 | 0 | Both candidate shapes have a legitimate name. |
| C2 | 1 | `perl-Template-Toolkit` points at its project site. |
| C3 | 0 | Every declarative spec declares all three packages. |
| C4 | 0 | No bare `perl-*` name appears in `BuildRequires`. |
| C5 | 0 | No bare `perl-*` name appears in `Requires` or `Provides`. |
| C6 | 9 | Nine hand-written stages across eight specs. |
| C7 | 0 | Every main `%files` section reads a generated list. |
| C8 | 0 | No Perl spec in the corpus declares a subpackage. |

The four judged-but-clean specs are `perl-libintl-perl` and
`perl-Locale-gettext`, which build with autotools, and `perl-rpm-macros` and
`perl-rpm-packaging`, which are toolchain packages. They carry a `perl-`
name but no declarative Perl build system, and the rule leaves them alone
because they declare no Perl module dependency in a plain form.

C6 is the only checkpoint with findings, and the nine findings come from
eight specs:

- `perl-Alien-cmake3` writes `%build -p`, because the patched `%setup`
  needs the `-p` argument to reach `cmake`.
- `po4a` writes `%build -p` to patch a hard-coded online DocBook stylesheet
  URL.
- `perl-SGMLSpm` writes `%install -a` to install a `sgmlspl` symlink.
- `perl-Encode` and `perl-IO-Compress` write `%install` because they need
  `%perl_make_install`, `%perl_process_packlist` and `%perl_gen_filelist`
  with extra arguments.
- `perl-CHI`, `perl-DBD-CSV`, `perl-File-Find-Rule-Perl` and `perl-HTML-Tree`
  write `%check` to exclude a known failing upstream test and then run
  `make test`.

Each of those specs is a legitimate deviation that the page words as a
preference, which is why C6 is a SHOULD checkpoint and why it can be
switched off with `--no-check-declarative-stages`.

### Rejected candidates

| Candidate | Corpus count | Why it is rejected |
| --- | --- | --- |
| `License` must be exactly `GPL-1.0-or-later OR Artistic-1.0-Perl`. | 62 | The page words the expression as "This is usually expressed with" and asks the packager to check the upstream metadata, so 59 of the 62 deviations are a different but correct licence for that module. |
| A `perl-` named package must declare a Perl build system. | 4 | All four exceptions are legitimate: two autotools modules and two toolchain packages. |
| A module package must carry `BuildArch: noarch`. | 0 | The field is correct only for a pure Perl module; an XS module is architecture dependent, and the decision needs the source tree. |
| An XS module must declare `perl-devel`. | 38 by regex | The evidence for an XS module is the presence of a `.xs` file, which is not in the spec, so the regex reports ordinary modules. |
| Every declarative spec must invoke `%perl_gen_filelist`. | 401 | The page states the macro is part of the default installation stage, so a declarative spec correctly omits it. |
| A package must declare `%doc`. | 403 present | The clause has no failure mode a linter can observe: the corpus already declares documentation in every spec. |
| The spec must be generated by `cpan2spec`. | not observable | The workflow is an instruction for the packager, not a property of the file. |
| `%perl_requires` must be used when the package requires the Perl version. | 0 | The condition "when the package requires the current Perl version" is not decidable from the spec text. |

## Examples

A declarative Perl module spec that passes every checkpoint:

```specfile
Name:           perl-Archive-Zip
Version:        1.68
Release:        %autorelease
Summary:        Provide an interface to ZIP archive files
License:        GPL-1.0-or-later OR Artistic-1.0-Perl
URL:            https://metacpan.org/dist/Archive-Zip
Source0:        https://www.cpan.org/authors/id/P/PH/PHRED/Archive-Zip-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    perlmaker

BuildOption(build):  INSTALLDIRS=vendor

BuildRequires:  make
BuildRequires:  perl-rpm-packaging
BuildRequires:  perl-rpm-macros
BuildRequires:  perl-macros
BuildRequires:  perl >= 5.6.0
BuildRequires:  perl(ExtUtils::MakeMaker)

Requires:       perl(Compress::Raw::Zlib) >= 2.017

%description
The Archive::Zip module allows a Perl program to create, manipulate, read,
and write Zip archive files.

%files -f %{name}.files
%doc Changes README.md

%changelog
%autochangelog
```

A spec that declares a declarative build system but hand-writes a stage:

```specfile
BuildSystem:    perlmaker
BuildRequires:  perl-rpm-packaging
BuildRequires:  perl-rpm-macros
BuildRequires:  perl-macros
BuildRequires:  perl(ExtUtils::MakeMaker)

%check
make test

%files -f %{name}.files
%doc Changes
```

That spec produces one finding for C6 and none for C3 or C7.
