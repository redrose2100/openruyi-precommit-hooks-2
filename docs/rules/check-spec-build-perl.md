# check-spec-build-perl

Enforce the requirements that the packaging guidelines state for the two
Perl declarative build systems, `perlbuild` and `perlmaker`.

## Original Requirement

Source:
<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/BuildSystems/perl>

Section "Dependencies" states, verbatim:

> If you need to use a Perl declarative build system, you typically need to
> add the following `BuildRequires`:
>
> ```specfile
> BuildRequires:  perl-rpm-packaging
> BuildRequires:  perl-rpm-macros
> BuildRequires:  perl-macros
> ```
>
> You should also add the Perl module dependencies that your upstream build
> script needs, for example: `perl(Module::Build)`,
> `perl(ExtUtils::MakeMaker)`. Among them: when using `perlbuild`, you
> typically need `perl(Module::Build)`. When using `perlmaker`, you
> typically need `perl(ExtUtils::MakeMaker)`.

Section "File list" states, verbatim:

> Perl packages typically use an automatically generated file list:
>
> ```specfile
> %files -f %{name}.files
> %doc Changes README
> ```
>
> `%perl_gen_filelist` generates `%{name}.files` during the installation
> phase. Therefore, when using `perlbuild` or `perlmaker`, you typically do
> not need to list all Perl module files by hand.

Section "Choosing the build system" states, verbatim:

> If the upstream source tree uses `Build.PL`, you should use `perlbuild`.
> If the upstream source tree uses `Makefile.PL`, you should use
> `perlmaker`.

That last clause is the only one this rule cannot implement: it selects the
build system by inspecting the upstream tarball, which a spec-only linter
never sees. The rule therefore starts from the declared value and judges
what the declaration implies.

## Flags

| Flag | Effect |
| --- | --- |
| `--no-check-shared-packages` | Do not report the shared Perl build dependencies (C1). |
| `--no-check-module` | Do not report the module the build system implies (C2). |
| `--no-check-files-list` | Do not report a `%files` section without `-f` (C3). |

## Checkpoints

| ID | Requirement | Strength |
| --- | --- | --- |
| C1 | A spec that declares `BuildSystem: perlbuild` or `perlmaker` should declare `perl-rpm-packaging`, `perl-rpm-macros` and `perl-macros` in `BuildRequires`. | SHOULD |
| C2 | A `perlbuild` spec should declare `perl(Module::Build)`; a `perlmaker` spec should declare `perl(ExtUtils::MakeMaker)`. | SHOULD |
| C3 | The main `%files` section of a Perl spec should read the generated file list with `-f`. | SHOULD |

Every clause on the page is worded with "typically", "should" or "in most
cases" rather than with "must", so all three checkpoints are enforced as
regression guards: a compliant spec is never reported, and a new violation
means the spec was most likely copied from a non-Perl template. A packager
with a real reason to deviate can switch the individual checkpoint off with
the flag above.

### C1

```
BuildSystem: perlmaker (line 8) requires the shared Perl build dependencies in BuildRequires; missing perl-macros
BuildSystem: perlbuild (line 9) requires the shared Perl build dependencies in BuildRequires; missing perl-rpm-packaging, perl-rpm-macros, perl-macros
```

Deciding details:

- All three packages are checked separately, and every missing one is named
  in a single message, so one spec produces one finding rather than three.
- A comma-separated list satisfies the requirement:
  `BuildRequires: perl-rpm-packaging, perl-rpm-macros, perl-macros` is
  accepted.
- A version constraint is accepted. `BuildRequires: perl-macros >= 1.0`
  satisfies the requirement, because the version operator and its operand
  are dropped before the name is compared.
- `perl-macros` and `perl-rpm-macros` are distinct names. Declaring one of
  them does not satisfy the other.
- A commented-out declaration does not count.
- A declaration in any `%package` block counts, because RPM merges the
  `BuildRequires` of every subpackage into one build dependency set.
- A spec that declares neither `perlbuild` nor `perlmaker` is not judged at
  all, even when it calls Perl macros.

### C2

```
BuildSystem: perlbuild (line 8) requires "perl(Module::Build)" in BuildRequires; missing "perl(Module::Build)"
BuildSystem: perlmaker (line 8) requires "perl(ExtUtils::MakeMaker)" in BuildRequires; missing "perl(ExtUtils::MakeMaker)"
```

Deciding details:

- The capability is matched in its rich-dependency form
  `perl(Module::Build)`. The generic dependency splitter ignores
  parenthesised names, so the capability is scanned separately; that keeps
  the colon-separated module name intact instead of truncating it at
  `perl(Module`.
- The comparison is case-insensitive, so `perl(module::build)` satisfies
  `perlbuild`.
- The two systems are not interchangeable. A `perlbuild` spec that declares
  only `perl(ExtUtils::MakeMaker)` is still reported, and the mirror case is
  reported as well.
- A version constraint is accepted:
  `BuildRequires: perl(Module::Build) >= 0.42` satisfies the requirement.
- A commented-out declaration does not count.
- A spec that declares both systems is checked twice, once per system, and
  each finding names its own system.

### C3

```
%files (line 17) does not read a generated file list; a Perl package is expected to use %files -f %{name}.files
```

Deciding details:

- Only the first `%files` section is judged. That is the section of the main
  package and the one `%perl_gen_filelist` fills, because the macro
  generates a single `%{name}.files` per source package. A subpackage list
  is written by hand on purpose and is left alone.
- The argument of `-f` is not fixed to `%{name}.files`. Any file name is
  accepted, so `%files -f modules.files` passes; the requirement is that the
  list comes from a generated file rather than from the section body.
- Globs written in the section body do not satisfy the requirement. A spec
  that lists `%{perl_vendorarch}/Demo*` by hand is reported.
- A spec with no `%files` section at all is not reported here. The section
  is mandatory for any package and its absence is already owned by
  `check-spec-basic-fields`.

## Scope notes

Measured against the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`: 6341 specs in `SPECS`, of which
403 declare a Perl declarative build system (355 `perlmaker`, 48
`perlbuild`).

| Checkpoint | Findings | Affected files |
| --- | --- | --- |
| C1 | 0 | 0 |
| C2 | 0 | 0 |
| C3 | 0 | 0 |
| **Total** | **0** | **0** |

All three checkpoints have zero findings because the 403 Perl specs in the
corpus already comply: every one declares the three shared macro packages,
every `perlbuild` spec declares `perl(Module::Build)`, every `perlmaker` spec
declares `perl(ExtUtils::MakeMaker)`, and all 403 read the generated file
list with `%files -f %{name}.files`. They are implemented anyway: each one
restates a clause the page presents as the normal form, and a rule that only
fires on future regressions is the point of a pre-commit hook.

### Rejected candidates

Every candidate below was measured on the same corpus and then rejected.

| Candidate | Findings | Why it was rejected |
| --- | --- | --- |
| The declared build system must match `Build.PL` / `Makefile.PL` in the tarball | - | Needs the unpacked upstream source tree, which a spec-only linter cannot inspect. |
| No hand-written `%build`, `%install` or `%check` section at all | 9 files have one | The page allows overriding the default phases and passing extra arguments. Every one of the 9 uses the section for a real purpose: `export ALIEN_INSTALL_TYPE=system`, rewriting a docbook URL, or deleting a failing test. Blanket rejection would be a false-positive generator. |
| A plain `%build`/`%install`/`%check` body must not repeat the bare default command | 1 (`perl-CHI`) | Only one spec repeats the default (`%check` holding just `make test`). The page phrases the rule as "in most cases you do not need", so a spec that keeps the section is not deviating from a requirement. |
| `BuildOption(build)` must carry `INSTALLDIRS=vendor` for `perlmaker` | 0 (355 of 355 comply) | The page gives the value as an example ("for example"), not as a requirement. Zero findings today, but pinning one string would break the `--installdirs=vendor` spelling the 48 `perlbuild` specs use. |
| `BuildOption(build)` must carry `--installdirs=vendor` for `perlbuild` | 0 (48 of 48 comply) | Same reason; the page lists it as a sample argument. |
| `BuildOption(install)` must carry `--create_packlist=0` | 0 (48 of 48 comply) | Same reason; the page shows it in the sample instead of stating it. |
| `BuildOption(check)` must not appear | 0 | The page explicitly allows it: "you can pass it through `BuildOption(check)` where appropriate". |
| `BuildOption(prep)` must not appear | 3 files use it | The page does not forbid it, and the three uses (`-n Mouse-v%{version}` and two similar) are legitimate `cpan2spec` output. |
| A Perl spec must declare `perl(Test::More)` | 305 of 403 do | The page says to add test modules "according to the actual situation". A package with no test suite needs none. |
| A Perl spec must declare `%doc Changes README` | 403 of 403 have a `%doc` line, spellings differ | The capitalization and the suffix vary (`CHANGES`, `README.md`), and the page allows extra or substitute documentation, so a machine check would misfire on legal files. |
| A Perl spec must call `%perl_process_packlist` or `%perl_gen_filelist` | - | Both run inside the core macros; a spec that uses `perlbuild`/`perlmaker` never writes them, so the check would measure nothing. |
| A spec that calls Perl macros must declare a Perl build system | 2 (`perl-libintl-perl`, `perl-Locale-gettext`, both `autotools`) | Both are C extensions built with autotools. The page does not require the Perl build systems for every package that happens to involve Perl. |
| A Perl spec must have a `%build` and an `%install` section | 2 and 3 of 403 have one | The declarative systems exist to remove exactly those sections; requiring them would invert the guideline. |

Deliberately out of scope as well: the syntax of `BuildOption`, which belongs
to `check-spec-buildoption`; the `BuildSystem` field value itself, which
belongs to `check-spec-buildsystem`; every dependency question beyond the
four names above, which belongs to `check-spec-buildrequires`; and the
presence of a `%check` section, which belongs to `check-spec-script`.

No network access and no `rpm` invocation is performed, so the rule works on
a bare checkout.

## Examples

Passing, `perlmaker`:

```specfile
Name:           perl-Config-IniFiles
Version:        3.000003
Release:        %autorelease
Summary:        Module for reading .ini-style configuration files
License:        GPL-1.0-or-later OR Artistic-1.0-Perl
URL:            https://metacpan.org/dist/Config-IniFiles
Source0:        https://www.cpan.org/authors/id/S/SH/SHLOMIF/Config-IniFiles-%{version}.tar.gz
BuildSystem:    perlmaker
BuildOption(build):  INSTALLDIRS=vendor
BuildRequires:  perl-rpm-packaging
BuildRequires:  perl-rpm-macros
BuildRequires:  perl-macros
BuildRequires:  perl(ExtUtils::MakeMaker)

%description
Config::IniFiles provides a way to have readable configuration files.

%files -f %{name}.files
%doc Changes README
```

Passing, `perlbuild`:

```specfile
Name:           perl-Alien-Build
Version:        2.83
Release:        %autorelease
Summary:        Build external dependencies for use in CPAN
License:        Apache-2.0
URL:            https://metacpan.org/dist/Alien-Build
Source0:        https://www.cpan.org/authors/id/P/PL/PLICEASE/Alien-Build-%{version}.tar.gz
BuildSystem:    perlbuild
BuildOption(build):  --installdirs=vendor optimize="%{optflags}"
BuildOption(install):  --destdir=%{buildroot} --create_packlist=0
BuildRequires:  perl-rpm-packaging
BuildRequires:  perl-rpm-macros
BuildRequires:  perl-macros
BuildRequires:  perl(Module::Build)

%description
Alien::Build provides tools for building external dependencies.

%files -f %{name}.files
%doc Changes README
```

Failing:

```specfile
Name:           perl-Demo
Version:        1.0
Release:        1
Summary:        A demo Perl module
License:        MIT
BuildSystem:    perlmaker
BuildRequires:  perl(Module::Build)

%description
A demo Perl module.

%files
%{perl_vendorarch}/Demo*
```

```
demo.spec: BuildSystem: perlmaker (line 7) requires the shared Perl build dependencies in BuildRequires; missing perl-rpm-packaging, perl-rpm-macros, perl-macros
demo.spec: BuildSystem: perlmaker (line 7) requires "perl(ExtUtils::MakeMaker)" in BuildRequires; missing "perl(ExtUtils::MakeMaker)"
demo.spec: %files (line 12) does not read a generated file list; a Perl package is expected to use %files -f %{name}.files
```
