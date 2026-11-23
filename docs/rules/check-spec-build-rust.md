# check-spec-build-rust

Enforce the requirements that the packaging guidelines state for the `rust`
and `rustcrates` declarative build systems.

## Original Requirement

Source:
<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/BuildSystems/rust>

Section "Dependencies" states, verbatim:

> When using the `rust` or `rustcrates` build system, you usually need to
> add:
>
> ```specfile
> BuildRequires:  rust
> BuildRequires:  rust-rpm-macros
> ```

Section "Prep" states, verbatim, for `rust`:

> The prep stage of the `rust` build system unpacks the default sources and
> configures Cargo to use the system registry.
>
> Its core behaviour is equivalent to:
>
> ```specfile
> %autosetup -C -p1
> ...
> %rust_setup_registry
> ```
>
> If you need to add a few commands before or after the default prep stage,
> you can use the section extension mechanism of the declarative build
> system:
>
> ```specfile
> %prep -p
> echo "run before default Rust prep"
> ```
>
> ```specfile
> %prep -a
> echo "run after default Rust prep"
> ```
>
> If you fully override `%prep`, you need to keep the configuration that
> makes Cargo use the system registry, otherwise the subsequent Cargo build
> may not be able to use the crate dependencies the system provides.

Section "Install" states, verbatim, for `rustcrates`:

> The install stage of the `rustcrates` build system installs the crate
> sources.
>
> Its core behaviour is equivalent to:
>
> ```specfile
> %rust_install_crate
> ```
>
> That macro installs the current crate sources to the system location and
> generates `.cargo-checksum.json`.
>
> Therefore, Rust crate provider packages usually do not need to write
> `%install` by hand. If you really need to add operations before or after
> the default install logic, you can use `%install -p` or `%install -a`.

Section "Notes" states, verbatim:

> - `rust` is for Rust application packages, not for generating crate
>   provider packages.
> - `rustcrates` is for Rust crate provider packages, not for building Rust
>   applications.

That clause is the one part of the page this rule cannot implement: it
selects the build system from the nature of the upstream software, which a
spec-only linter cannot verify. The rule therefore starts from the declared
value and judges what the declaration implies.

## Flags

| Flag | Effect |
| --- | --- |
| `--no-check-crates-install` | Do not report a hand-written `%install` in a `rustcrates` spec (C1). |
| `--no-check-rust-prep` | Do not report a `%prep` override without the registry setup (C2). |
| `--no-check-macros-package` | Do not report the missing `rust-rpm-macros` (C3). |
| `--no-check-toolchain` | Do not report the missing `rust` toolchain (C4). |

## Checkpoints

| ID | Requirement | Strength |
| --- | --- | --- |
| C1 | A `rustcrates` spec must not write a plain `%install` section by hand; extra work belongs in `%install -p` or `%install -a`. | SHOULD |
| C2 | A `rust` spec that writes a plain `%prep` section must keep `%rust_setup_registry` in it, or extend the default prep with `%prep -p`/`%prep -a`. | SHOULD |
| C3 | A `rust` or `rustcrates` spec must declare `rust-rpm-macros` in `BuildRequires`. | MUST |
| C4 | A `rust` spec must declare `rust` in `BuildRequires`. | MUST |

C1 and C2 restate clauses the page words with "usually do not need" and
"you need to keep", so they describe the normal form the page asks for
rather than an absolute ban. C3 and C4 are worded with "usually need to
add", so a spec that satisfies the clause in another equivalent spelling is
accepted rather than reported.

C4 is scoped to `rust`. The page groups both dependencies under one
heading, but a `rustcrates` package installs crate sources instead of
compiling Cargo output, and none of the 2354 `rustcrates` specs in the
corpus declares the toolchain, while every `rust` spec declares it.

### C1

```
%install (line 23) is written by hand in a BuildSystem: rustcrates spec; the default install stage installs the crate sources and generates .cargo-checksum.json, so use %install -p or %install -a to add work around it
```

Deciding details:

- Only a plain `%install` header is judged. The page names `%install -p`
  and `%install -a` as the compliant way to run commands around the default
  install logic, so a suffixed section is accepted. Every subpackage shares
  the section, so one finding covers the whole spec.
- A section holding only comments or blank lines is not reported: it
  overrides nothing, so the default install logic still runs.
- The finding points at the `%install` header rather than at the first
  command, because the section as a whole is the problem.
- A spec that declares `rust` instead of `rustcrates` is not judged here:
  the page states that `rust` has no default install action, so an
  application package must write `%install` itself.

### C2

```
%prep (line 19) overrides the default prep of BuildSystem: rust without configuring the system crate registry; keep %rust_setup_registry in the section, or use %prep -p or %prep -a to extend the default prep
```

Deciding details:

- Only a plain `%prep` header is judged. `%prep -p` and `%prep -a` run
  around the default prep, so the registry configuration stays in place.
- The section must contain the literal macro `%rust_setup_registry`, which
  is the macro the page names in the equivalent core behaviour.
- A section holding only comments or blank lines is not reported.
- A `rustcrates` spec is not judged here: the page states that its prep
  stage only unpacks the sources and never configures the registry, so an
  override cannot break anything.

### C3

```
BuildSystem: rust (line 8) requires "rust-rpm-macros" in BuildRequires; missing "rust-rpm-macros"
```

Deciding details:

- The package is matched as a whole name. `rust-rpm-macros-extra` does not
  satisfy `rust-rpm-macros`.
- A version constraint is accepted: `BuildRequires: rust-rpm-macros >= 0.5`
  satisfies the requirement, because the version operator and its operand
  are dropped before the name is compared.
- A commented-out declaration does not count.
- A declaration in any `%package` block counts, because RPM merges the
  `BuildRequires` of every subpackage into one build dependency set.
- The finding points at the line of the `BuildSystem` declaration, not at a
  missing line, since there is nothing to point at in the spec.

### C4

```
BuildSystem: rust (line 8) requires "rust" in BuildRequires; missing "rust"
```

Deciding details:

- The toolchain is matched as a whole name, so `rust-toolset`,
  `rust-std-static` and `rust-analyzer` do not satisfy it.
- A version constraint is accepted.
- A declaration in any `%package` block counts.
- A `rustcrates` spec is not judged, for the reason stated above.

## Scope notes

Measured against the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`: 6341 specs in `SPECS`, of which
27 declare `BuildSystem: rust` and 2354 declare `BuildSystem: rustcrates`.
No spec declares both.

| Checkpoint | Findings | Affected files |
| --- | --- | --- |
| C1 | 68 | 68 |
| C2 | 0 | 0 |
| C3 | 0 | 0 |
| C4 | 0 | 0 |
| **Total** | **68** | **68** |

The 68 C1 findings cover 68 of the 2354 `rustcrates` specs. Those specs
hand-write `%install` to copy the crate tree, typically with `%__install -d`
and `%__cp -a .` into `%{_datadir}/cargo/registry/...`, which is exactly the
work `%rust_install_crate` performs. The single `rustcrates` spec that
extends the stage instead uses `%install -a` and is not reported.

C2 to C4 have zero findings. All three are implemented anyway: C2 is the
clause the page words with "you need to keep", and C3 and C4 are the
dependency pair the page states up front, so a rule that only fires on
future regressions is the point of a pre-commit hook.

### Rejected candidates

Every candidate below was measured on the same corpus and then rejected.

| Candidate | Findings | Why it was rejected |
| --- | --- | --- |
| A `rustcrates` spec must not write a plain `%build` section | 0 | The page says "do not override this stage", so the requirement is real. But the same paragraph explains that the stage generates the specpart files that hold the `%files` content of the feature subpackages, and a spec-only linter cannot tell an empty plain `%build` from one whose output is discarded, so the rule would either miss the violation or report a legal spec. |
| A `rustcrates` spec must declare `rust` in `BuildRequires` | 2354 of 2354 lack it | The page names both dependencies under one heading, but the corpus shows that crate provider packages are built without the toolchain, and the page states that `rust` is for application packages. Reporting the entire population is not a finding. |
| A `rust` spec must not write `%install` by hand | 0 | The page states that `rust` has no default install action and that the spec should write or extend `%install` according to the package, so writing it is compliance. |
| `%check` must not be empty for either build system | 5 `rust` specs hold only a comment | The page states that a `rust` test stage may be overridden or disabled according to package policy, and that a `rustcrates` package may override it for extra validation. An empty section is therefore one documented outcome, not a violation. The empty-section rule belongs to `check-spec-build-pyproject` because that page forbids the shortcut for its own system. |
| `BuildSystem` must be one of `rust` / `rustcrates` | - | The legal value set belongs to `check-spec-buildsystem`. |
| A `rustcrates` spec must use the `%global crate_name` / `full_version` / `pkgname` triple | 2310 of 2354 declare all three | The page calls the triple a typical example and says it is generally not edited by hand, which describes the output of the provider generator rather than a rule. The 44 specs that spell it differently generate the same compatibility names. |
| `full_version` must differ from `Version` | 0 | The page defines `full_version` as the complete upstream crate version, which means it may legitimately equal `Version` for a plain release. Requiring a difference would invent a constraint the page does not state. |
| A `rust` spec must also declare the `crate(...)` capability for its dependencies | 24 of 27 do | The page says "if the package depends on other Rust crates, it should declare the corresponding build dependency", which is conditional on the dependency graph. A spec that vendored its dependencies before the switch to the system registry is not wrong, and the rule cannot read `Cargo.lock`. |
| A `rustcrates` feature subpackage must be named `rust-<pkgname>+<feature>` | - | The naming contract lives in the Rust language packaging guide, not in this page. |
| A Python package with a Rust extension must declare `BuildSystem: pyproject` | - | The page words it as "usually should", and detecting a Rust extension needs the unpacked upstream tree. |
| The role separation between `rust` and `rustcrates` as declared | - | Enforcing it means knowing which role the upstream software has, which a spec-only linter cannot establish. |

Deliberately out of scope as well: the syntax and stages of
`BuildOption`, which belong to `check-spec-buildoption`; the `BuildSystem`
field value itself, which belongs to `check-spec-buildsystem`; every other
dependency question, which belongs to `check-spec-buildrequires`; and the
section extension mechanism `-p`/`-a` itself, which belongs to the rule that
covers each build system.

No network access and no `rpm` invocation is performed, so the rule works on
a bare checkout.

## Examples

Passing `rust` application:

```specfile
Name:           ripgrep
Version:        15.2.0
Release:        %autorelease
Summary:        Fast recursive text search tool
License:        Unlicense OR MIT
URL:            https://github.com/BurntSushi/ripgrep
Source:         https://static.crates.io/crates/ripgrep/15.2.0/download#/ripgrep-15.2.0.tar.gz
BuildSystem:    rust

BuildRequires:  rust
BuildRequires:  rust-rpm-macros
BuildRequires:  crate(regex-1/default) >= 1.9.5

%description
ripgrep recursively searches directories for regular expressions.

%install
install -Dpm0755 target/release/rg %{buildroot}%{_bindir}/rg

%files
%{_bindir}/rg
```

Passing `rustcrates` provider package:

```specfile
%global crate_name anes
%global full_version 0.1.6
%global pkgname anes-0.1

Name:           rust-%{pkgname}
Version:        0.1.6
Release:        %autorelease
Summary:        Rust crate "anes"
License:        MIT OR Apache-2.0
URL:            https://github.com/zrzka/anes-rs
Source:         https://static.crates.io/crates/%{crate_name}/%{full_version}/download#/%{name}-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    rustcrates

BuildRequires:  rust-rpm-macros

Provides:       crate(%{pkgname}) = %{version}

%description
Source code for the Anes Rust crate.

%files
%{_datadir}/cargo/registry/%{crate_name}-%{full_version}/
```

Passing, with the extended install stage instead of a hand-written section:

```specfile
BuildSystem:    rustcrates
BuildRequires:  rust-rpm-macros

%install -a
%__rm -f %{buildroot}%{_datadir}/cargo/registry/%{crate_name}-%{full_version}/*checksum.json
```

Failing:

```specfile
Name:           demo
Version:        1.0
Release:        %autorelease
Summary:        A demo package
License:        MIT
URL:            https://example.org/demo
BuildSystem:    rust

%description
A demo package.

%prep
%autosetup -C -p1

%install
install -Dpm0755 target/release/demo %{buildroot}%{_bindir}/demo

%files
%{_bindir}/demo
```

Three findings: the `rust` toolchain and the `rust-rpm-macros` dependency are
missing, and the `%prep` override drops the registry configuration.

```text
demo.spec: BuildSystem: rust (line 7) requires "rust-rpm-macros" in BuildRequires; missing "rust-rpm-macros"
demo.spec: %prep (line 12) overrides the default prep of BuildSystem: rust without configuring the system crate registry; keep %rust_setup_registry in the section, or use %prep -p or %prep -a to extend the default prep
demo.spec: BuildSystem: rust (line 7) requires "rust" in BuildRequires; missing "rust"
```
