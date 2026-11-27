# check-spec-programming-rust

Enforce the requirements that the Rust language packaging guideline states
for the three kinds of package the Rust ecosystem produces: crate
providers, Rust applications, and packages in other languages that embed
Rust.

## Original Requirement

Source:
<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/languages/Rust>

The page opens by dividing Rust packaging into three categories, which is
why this rule is split into a provider population and an ecosystem
population rather than into one flat checkpoint list:

> Rust packages in openRuyi usually fall into the following categories:
>
> - Rust crate provider packages.
> - Rust applications or command-line tools.
> - Packages in other languages that contain Rust extensions, such as
>   Python/Rust extension packages.

Section "Naming" states, verbatim:

> Rust crate provider packages must use the `rust-` prefix.

> A crate provider package name usually comes from the crate compatibility
> name. For example:
>
> ```specfile
> %global crate_name serde
> %global full_version 1.0.228
> %global pkgname serde-1
> Name:           rust-serde-1
> Version:        1.0.228
> ```

> Where:
>
> - `crate_name` is the original crate name from upstream `Cargo.toml`.
> - `full_version` is the full upstream crate version.
> - `pkgname` is the compatibility name that openRuyi uses for package
>   names, directory names, and `crate(...)` capabilities.

> RPM package names and `crate(...)` capabilities usually normalize
> underscores in crate names to hyphens. For example, when the upstream
> crate name is `os_str_bytes`, the provider package name usually uses
> `os-str-bytes`.

> Keep the crate provider directory name, spec file name, and `Name`
> consistent. For example:
>
> ```
> SPECS/rust-serde-1/rust-serde-1.spec
> ```
>
> corresponds to:
>
> ```specfile
> %global pkgname serde-1
> Name:           rust-serde-1
> ```

> If you must change `pkgname`, also update the directory name, spec file
> name, and related `crate(...)` dependency declarations. Explain the
> reason in the commit and PR.

Section "Compatibility Names" states, verbatim:

> Rust crate providers use compatibility names so that different
> incompatible versions can coexist in the repository.
>
> Use the following rules in most cases:
>
> - Group versions `1.x.y` and later by major version.
> - Group versions `0.y.z` where `y > 0` by minor version.
> - Group versions `0.0.z` by the full patch version.
>
> For example:
>
> ```
> serde 1.0.228       -> serde-1
> tokenizers 0.22.2   -> tokenizers-0.22
> foo 0.0.7           -> foo-0.0.7
> ```

> Do not introduce unnecessarily fine-grained compatibility names, such as
> `serde-1.0.15`, unless the crate has a clear compatibility issue.

Section "Build Systems" states, verbatim:

> Use the following build system for Rust crate provider packages:
>
> ```specfile
> BuildSystem:    rustcrates
> ```
>
> Use the following build system for Rust applications, command-line tools,
> or other packages that need to run Cargo build/test workflows:
>
> ```specfile
> BuildSystem:    rust
> ```
>
> Python packages with Rust extensions should usually continue to use a
> Python-related build system, for example:
>
> ```specfile
> BuildSystem:    pyproject
> ```

Section "Dependencies" states, verbatim:

> Declare Rust crate dependencies through `crate(...)` capabilities. For
> example:
>
> ```specfile
> BuildRequires:  crate(serde-1/default) >= 1.0.0
> BuildRequires:  crate(clap-4/derive) >= 4.5.0
> ```

> If the package needs a feature, explicitly declare the corresponding
> feature capability.

> Do not use ordinary RPM package names instead of `crate(...)`
> capabilities to declare Rust crate dependencies. `crate(...)`
> capabilities are the main interface for dependency resolution between
> Rust ecosystem packages.

Section "Rust Crate Provider Packages" states, verbatim:

> Rust crate provider packages install crate source code into the system
> and provide `crate(...)` capabilities for other Rust packages.

Section "Cargo.toml in the Provider Directory" states, verbatim:

> When TakoPack generates a crate provider package, it keeps a `Cargo.toml`
> file in the provider directory. For example:
>
> ```
> SPECS/rust-serde-1/Cargo.toml
> SPECS/rust-serde-1/rust-serde-1.spec
> ```

> This `Cargo.toml` is a copy of the crate metadata used for packaging. It
> records the crate name, version, dependencies, and feature information.
> It also provides important input for generating
> `BuildRequires: crate(...)`, feature subpackages, and related dependency
> relationships.

Section "Python/Rust Extension Packages" states, verbatim:

> Declare both Python and Rust build dependencies. For example:
>
> ```specfile
> BuildRequires:  rust
> BuildRequires:  rust-rpm-macros
> BuildRequires:  python3dist(maturin)
> BuildRequires:  crate(pyo3-0.27/default) >= 0.27.0
> BuildRequires:  crate(pyo3-0.27/extension-module) >= 0.27.0
> ```

## Flags

Every checkpoint can be switched off on its own, so a repository that
deliberately deviates from one clause keeps the other nine.

| Flag | Default | Effect |
| --- | --- | --- |
| `--no-check-provider-prefix` | on | Do not report a crate provider `Name` without the `rust-` prefix. |
| `--no-check-provider-consistency` | on | Do not report a provider whose directory name or spec file name disagrees with `Name`. |
| `--no-check-pkgname` | on | Do not report a `pkgname` macro that is not the part of `Name` after `rust-`. |
| `--no-check-compat-group` | on | Do not report a compatibility name that groups a version by the wrong key. |
| `--no-check-compat-granularity` | on | Do not report an unnecessarily fine-grained compatibility name. |
| `--no-check-crate-capability` | on | Do not report an ordinary package name used where a `crate(...)` capability belongs. |
| `--no-check-crate-version` | on | Do not report a `crate(...)` build dependency without a version constraint. |
| `--no-check-pyproject-toolchain` | on | Do not report a `pyproject` Rust extension that omits `rust` or `rust-rpm-macros`. |
| `--no-check-provider-capability` | on | Do not report a crate provider that provides no `crate(...)` capability. |
| `--no-check-provider-cargo-toml` | on | Do not report a provider directory that keeps no `Cargo.toml`. |

## Checkpoints

| ID | Checkpoint | Strength | Scope |
| --- | --- | --- | --- |
| C1 | A crate provider package carries the `rust-` prefix. | MUST | Spec with `BuildSystem: rustcrates`. |
| C2 | The provider directory name, the spec file name and `Name` agree. | MUST | Spec with `BuildSystem: rustcrates`. |
| C3 | `pkgname` is the part of `Name` after `rust-`. | MUST | Spec with `BuildSystem: rustcrates` that defines `pkgname`. |
| C4 | The compatibility name groups a version by the page's key. | SHOULD | Spec with `BuildSystem: rustcrates` that defines `crate_name` and a version. |
| C5 | The compatibility name is not unnecessarily fine-grained. | MUST | Spec with `BuildSystem: rustcrates` that defines `crate_name`, `full_version` and `pkgname`. |
| C6 | A crate dependency is declared as a `crate(...)` capability. | MUST | Any Rust ecosystem spec. |
| C7 | A `crate(...)` build dependency carries a version constraint. | SHOULD | Any Rust ecosystem spec. |
| C8 | A `pyproject` Rust extension declares both `rust` and `rust-rpm-macros`. | MUST | Spec with `BuildSystem: pyproject` and a `crate(...)` dependency. |
| C9 | A crate provider provides a `crate(...)` capability. | SHOULD | Spec with `BuildSystem: rustcrates` that defines `pkgname`. |
| C10 | The provider directory keeps a `Cargo.toml`. | SHOULD | Spec with `BuildSystem: rustcrates` that defines `crate_name` or `pkgname`. |

The four MUST ratings that the page supports with an imperative are C1
("must use the `rust-` prefix"), C2 ("Keep the crate provider directory
name, spec file name, and `Name` consistent"), C6 ("Do not use ordinary
RPM package names instead of `crate(...)` capabilities") and C8 ("Declare
both Python and Rust build dependencies").

C3 is a MUST because the page defines `pkgname` in one sentence that binds
it to the package name, the directory name and the capability name; a
`pkgname` that disagrees with `Name` breaks all three at once.

C5 is a MUST because the page phrases it as a prohibition ("Do not
introduce unnecessarily fine-grained compatibility names") with one
escape hatch.

C4, C7, C9 and C10 are SHOULD, and the wording is why:

* C4 is introduced with "Use the following rules in most cases", so an
  exception is expected and the checkpoint reports a deviation rather
  than an error.
* C7 rests on the two `BuildRequires` examples the page writes, each with
  a `>=` constraint; the page never states the constraint as a rule.
* C9 restates the sentence "provide `crate(...)` capabilities for other
  Rust packages", which describes the package rather than commands the
  packager.
* C10 restates "it keeps a `Cargo.toml` file in the provider directory",
  again a description of what the generator produces.

A repository that keeps an intentionally coarse or fine compatibility
name, or an unversioned dependency the build resolves another way, turns
the relevant flag off instead of rewording the finding.

## Scope

A spec is in scope for the seven provider checkpoints when it declares
`BuildSystem: rustcrates`. That is the declarative build system the page
assigns to a crate provider, and it is the only signal a spec-only linter
can read to tell a provider from a package that merely builds with Cargo.

C6, C7 and C8 are judged on the wider population of Rust ecosystem
packages, because the dependency clause is written for every package that
consumes crates. That population is decided by three signals the spec
text carries: a `rust` or `rustcrates` build system, a `crate(...)`
dependency, or a `rust`/`rust-rpm-macros` build dependency.

```
.spec files                                 6341
BuildSystem: rustcrates                     2354   <- C1, C2, C3, C4, C5, C9, C10
  on a prerelease version                     76   <- excluded from C4 and C5
BuildSystem: rust                             27   <- C6, C7
BuildSystem: pyproject                       891   <- C6, C7
  with a crate(...) dependency                23   <- C8 as well
Specs declaring crate(...) dependencies     2081   <- C6, C7
```

The counts are measured against the openRuyi corpus, not asserted.
`ceph` declares `BuildSystem: cmake` and never appears in the 2081 even
though it builds Rust code, because a spec that names neither a Rust build
system nor a `crate(...)` capability gives the linter nothing to anchor
on.

C4 and C5 need a version to compute a compatibility key, so they read the
`full_version` macro and fall back to the `Version:` field. A spec that
carries neither is skipped rather than guessed at.

### Prerelease versions

Seventy-six providers package a prerelease such as `0.6.0-rc.10` and name
themselves `rust-aead-0.6.0-rc.10`. The page defines the compatibility key
only for a released version, so C4 and C5 leave a prerelease alone: the
key function returns nothing when the version carries a `-`, and the two
checkpoints skip a spec whose key is unknown.

Without that rule the seventy-six prerelease providers would each be
reported twice, once for a key they cannot have and once for a granularity
the page never asked them to reduce. Reporting them would be a false
positive rather than a conforming finding.

## C1 - a crate provider package carries the rust- prefix

The checkpoint reads the main `Name:` field after expanding the macros of
the spec, so `Name: rust-%{pkgname}` and `Name: rust-serde-1` are both
accepted.

A name that still holds an unexpanded macro after expansion is skipped,
so a spec that composes its name from a macro the linter cannot resolve is
left alone rather than guessed at.

The finding names the spelling the page asks for, derived by prefixing the
current name:

```
Name: serde-1 (line 4) does not carry the "rust-" prefix; a Rust crate
provider package must be named "rust-serde-1"
```

The clause is spelled "must use the `rust-` prefix" and the example puts
the prefix immediately before the compatibility name, so the prefix is
required and not a style preference.

## C2 - the provider directory name, the spec file name and Name agree

The clause is anchored on the example path `SPECS/rust-serde-1/rust-serde-1.spec`,
which shows three names that are one name: the directory, the file and the
`Name` field.

Both halves are checked, because a spec can satisfy one and miss the other:

```
Name: rust-serde-1 (line 4) does not match the provider directory name
"rust-serde"; keep the crate provider directory name, spec file name and
Name consistent
```

```
Name: rust-serde-1 (line 4) does not match the spec file name
"rust-serde-2.spec"; keep the crate provider directory name, spec file
name and Name consistent
```

A provider that lives in a directory named after the crate only, or whose
spec file keeps the upstream crate version, is reported. The finding points
at the `Name` line rather than at the path, because the page asks the
packager to change whichever of the three is wrong, and the field is the
one a reviewer reads first.

## C3 - pkgname is the part of Name after rust

The page defines `pkgname` as "the compatibility name that openRuyi uses
for package names, directory names, and `crate(...)` capabilities", and its
example pairs `%global pkgname serde-1` with `Name: rust-serde-1`.

The checkpoint therefore derives the expected value by removing the
prefix, instead of comparing `pkgname` with `crate_name` or with the
directory: the prefix is the one part of the name the page fixes, so the
rest is the compatibility name by construction.

The value of the macro is expanded before it is judged, so an indirection
such as `%global pkgname %{crate_name}-1` is resolved and checked:

```
%global pkgname other-1 (line 1) does not match Name: rust-serde-1
(line 4); the compatibility name is the part of the package name after
"rust-", that is "serde-1"
```

## C4 - the compatibility name groups a version by the page's key

The page states three grouping rules, and the checkpoint computes the key
from them:

| Version | Rule | Key |
| --- | --- | --- |
| `1.0.228` | Group versions `1.x.y` and later by major version | `1` |
| `0.22.2` | Group versions `0.y.z` where `y > 0` by minor version | `0.22` |
| `0.0.7` | Group versions `0.0.z` by the full patch version | `0.0.7` |

A version whose major part is not a number, and a prerelease whose core
carries a `-`, produce no key and are skipped.

The checkpoint compares the trailing part of `pkgname` with the key. The
crate name itself may be spelled with `_` or `-`, so the suffix is looked
for after both spellings of the crate name, and the checkpoint accepts the
key itself as well as a name that extends the key to the right:

```
%global pkgname serde-1.0 (line 3) groups version 1.0.228 by "1.0";
the page asks to group a version 1.0.228 by "1", so the compatibility
name is "serde-1"
```

A provider that carries no suffix at all is reported separately, because
the compatibility name is the whole point of the package name:

```
%global pkgname serde (line 3) carries no compatibility name; a crate
provider groups version 1.0.228 by "1", so the compatibility name is
"serde-1"
```

## C5 - the compatibility name is not unnecessarily fine-grained

The clause is a prohibition with one escape hatch: "Do not introduce
unnecessarily fine-grained compatibility names, such as `serde-1.0.15`,
unless the crate has a clear compatibility issue".

The two knobs it reads are the key C4 computes and the suffix the name
carries. A suffix that extends the key to the right is finer than the
page asks for, and the escape hatch is not something a spec can declare,
so the finding asks for the key rather than for a note about the issue:

```
%global pkgname serde-1.0.228 (line 3) splits the compatibility key
"1" more finely as "1.0.228"; do not introduce an unnecessarily
fine-grained compatibility name unless the crate has a clear
compatibility issue
```

A spec that adopts a deliberately finer name because of a real
compatibility issue turns `--no-check-compat-granularity` off and records
the reason in the commit message, which is the workflow C2 already asks
for when `pkgname` deviates.

## C6 - a crate dependency is declared as a crate capability

The checkpoint reads `BuildRequires:` and `Requires:`, because the page
writes `crate(...)` under the heading "Dependencies" without restricting
it to the build. It does not read `Provides:`, because a `Provides`
capability is what a package advertises rather than what it consumes.

A dependency name is reduced to its own name before it is judged, so a
version operator and the version after it never look like a package name,
and a `crate(.../feature)` capability keeps its feature path.

The tool packages this rule never reports are the ones the page itself
names: `rust`, `rust-rpm-macros`, `cargo`, `cargo-c`, `rustfmt` and their
siblings. They are toolchain packages rather than crates, so they are
declared as ordinary RPM packages on purpose.

A dependency whose name still looks like a provider package, that is a
`rust-` prefixed name that ends with a version, is reported:

```
BuildRequires: rust-syn-2 >= 2.0.87 (line 109) names a crate provider
package instead of a crate(...) capability; declare the Rust crate
dependency as "crate(syn-2)"
```

The corpus shows why the checkpoint matters: `mesa` carries six
`rust-*` package dependencies next to a comment that reads
`# FIXME: use crate(xxx) when it's allowed by pre-commit hook`, so the
packager already knows the spelling is wrong and is waiting for a rule to
say so.

## C7 - a crate(...) build dependency carries a version constraint

The page writes every `crate(...)` dependency it shows with a `>=`
constraint, and the version is what makes the capability resolvable
against the compatibility names C4 produces.

Only `BuildRequires:` is read. A runtime `Requires: crate(...)` line is
not asked for a constraint, because the page's examples are all build
dependencies and a generated runtime dependency is derived from the build
metadata rather than written by hand.

An entry counts as constrained when an operator follows the name, so both
`>= 2.0.0` and `= 2.0.0` are accepted and only a bare name is reported:

```
BuildRequires: crate(regex-1/default) (line 40) declares a crate
capability without a version constraint; the page writes every
crate(...) dependency with one, such as "regex-1 >= 1.0.0"
```

## C8 - a pyproject Rust extension declares both build dependencies

The checkpoint applies only to a spec that names `BuildSystem: pyproject`
and also declares a `crate(...)` dependency. The first signal is what the
page asks a Python package with a Rust extension to keep, and the second
proves the extension really builds Rust code.

The clause is "Declare both Python and Rust build dependencies", and the
example that follows lists `rust` and `rust-rpm-macros`, so the checkpoint
reports whichever of the two is absent:

```
BuildSystem: pyproject (line 9) declares crate(...) dependencies but
not "rust-rpm-macros" in BuildRequires; a Python package with a Rust
extension must declare both "rust" and "rust-rpm-macros"
```

A `pyproject` package that ships no Rust code keeps its silence, because
the `crate(...)` condition never becomes true. That is why the checkpoint
does not duplicate `check-spec-build-rust`, which asks every `rust` and
`rustcrates` spec for `rust-rpm-macros`: the populations are disjoint.

## C9 - a crate provider provides a crate capability

The page describes a provider as a package that "install[s] crate source
code into the system and provide[s] `crate(...)` capabilities for other
Rust packages". The checkpoint asks for that capability on the provider
itself, keyed by the compatibility name the spec defines:

```
%global pkgname serde-1 (line 3) is not advertised; a crate provider
installs the crate sources and provides "crate(serde-1)" for other Rust
packages, so add it to Provides
```

A capability with a feature path is accepted, so
`Provides: crate(%{pkgname}/default)` and `Provides: crate(%{pkgname})`
both satisfy the clause. The page asks for the capability, not for one
particular spelling of it.

## C10 - the provider directory keeps a Cargo.toml

The page shows the two files that make up a provider, `Cargo.toml` and
`rust-serde-1.spec`, and explains that the metadata copy is what the
generated `crate(...)` dependencies are derived from.

The checkpoint therefore reads the directory the spec lives in and looks
for `Cargo.toml`. It is the second checkpoint, after C2, that touches the
filesystem, and both of them read nothing but the spec's own directory, so
a bare checkout is enough to run the rule.

```
(line 4) the provider directory holds no Cargo.toml; a crate provider
keeps a copy of the crate metadata there as the basis for the generated
crate(...) dependencies
```

The finding points at the `Name` line, because the missing file has no
line of its own and the name is where a reviewer starts reading.

## Boundary with check-spec-build-rust

`check-spec-build-rust` covers the build side of the same ecosystem, taken
from the separate page `BuildSystems/rust`. Four of its clauses are close
enough to be worth naming:

| Clause | Owner | Overlapping checkpoint here |
| --- | --- | --- |
| A `rustcrates` spec writes no plain `%install`. | `check-spec-build-rust` | none |
| A `rust` spec runs `%rust_setup_registry` in `%prep`. | `check-spec-build-rust` | none |
| A `rust` or `rustcrates` spec declares `rust-rpm-macros`. | `check-spec-build-rust` | none |
| A `rust` spec declares `rust`. | `check-spec-build-rust` | none |

The fourth row is the one that could look like a duplicate of C8, and it
is not: that clause judges a spec whose `BuildSystem` is `rust` or
`rustcrates`, while C8 judges a spec whose `BuildSystem` is `pyproject`
and which also declares a `crate(...)` dependency. No spec is in both
populations, so a repository that enables the two rules reports each spec
once.

The split is visible in what this rule leaves alone on purpose: `%build`,
`%install`, `%check` and the `rust-rpm-macros` dependency of a provider
belong to the build rule, and the provider half of this rule stops at the
name, the layout, the compatibility name and the capability.

## Scope notes

Measured against the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`:

| Metric | Count |
| --- | --- |
| `.spec` files scanned | 6341 |
| Specs with `BuildSystem: rustcrates` | 2354 |
| Providers on a prerelease version | 76 |
| Specs with `BuildSystem: rust` | 27 |
| Specs with `BuildSystem: pyproject` | 891 |
| `pyproject` specs with a `crate(...)` dependency | 23 |
| Specs declaring `crate(...)` dependencies | 2081 |
| Findings, default flags | 76 |
| Files with at least one finding | 6 |

Per checkpoint:

| ID | Findings | Notes |
| --- | --- | --- |
| C1 | 0 | All 2354 providers carry the prefix. |
| C2 | 0 | All 2354 providers keep the three names consistent. |
| C3 | 0 | Every `pkgname` matches the part of `Name` after `rust-`. |
| C4 | 0 | Every released provider uses the key the page asks for. |
| C5 | 0 | No released provider is finer than its key. |
| C6 | 6 | `mesa` declares six `rust-*` packages instead of `crate(...)`. |
| C7 | 69 | Four specs declare `crate(...)` build dependencies with no version. |
| C8 | 1 | `python-maturin` declares `rust` but not `rust-rpm-macros`. |
| C9 | 0 | Every provider advertises `crate(%{pkgname})`. |
| C10 | 0 | Every provider directory keeps a `Cargo.toml`. |

Six files carry seventy-six findings, because C7 is the checkpoint that
fires repeatedly inside one spec. The distribution is worth reading in
full:

- `python-tokenizers`: 49 findings, one per `crate(...)` line from line 35
  to line 86, all of the form `crate(ahash-0.8/default)`,
  `crate(compact-str-0.9/serde)`, `crate(dary-heap-0.3/serde)`. The spec
  declares its whole dependency graph without versions, so the list is
  long but the fix is mechanical.
- `python-tiktoken`: 10 findings, lines 35 to 44, again a bare list ending
  at `crate(aho-corasick-1)`.
- `clang-wrap`: 7 findings, lines 24 to 30, spelled `crate(serde-json-1)`,
  `crate(goblin-0.10)`, `crate(scroll-derive-0.13)`. This provider lives
  at `SPECS/clang-wrap/clang-wrap.spec`, outside the `rust/` prefix a grep
  would guess at, which is why the scan is a recursive walk over `SPECS`.
- `python-libcst`: 3 findings, lines 28, 31 and 33, the three proc-macro
  crates `proc-macro2-1`, `quote-1` and `syn-2`.
- `mesa`: 6 findings, one per `rust-*` package dependency at lines 108 to
  113, immediately after the comment
  `# FIXME: use crate(xxx) when it's allowed by pre-commit hook`.
- `python-maturin`: 1 finding, the missing `rust-rpm-macros` alongside
  `BuildRequires: rust` on line 93.

The nine zeroes are real rather than a sign of a checkpoint that never
runs: the seven provider checkpoints each build on a signal that 2354
specs carry, and 2354 specs answering all seven clauses correctly is the
result of TakoPack generating them.

### Rejected candidates

| Candidate | Corpus count | Why it is rejected |
| --- | --- | --- |
| A `rustcrates` spec declares `BuildArch: noarch`. | 2354 of 2354 | Every provider is architecture independent, so the finding would hit 100% of the population and says nothing. |
| `Source` must use `https://static.crates.io/crates/%{crate_name}/...`. | 2354 use a literal or macro form | The page explicitly says source fields "should follow the actual generated result", so the literal and macro spellings are both conforming. |
| `#!RemoteAsset` must sit above `Source`. | 2341 carry it | The field is part of the generated result, and the page leaves its consistency to the generator rather than to a rule. |
| A provider declares `rust-rpm-macros`. | owned elsewhere | `check-spec-build-rust` reports it for the same 2354 specs, so a second rule would double-report. |
| A provider writes no `%build` and no `%install`. | owned elsewhere | Same reason. |
| A `rust` spec runs `%rust_setup_registry`. | owned elsewhere | Same reason. |
| `BuildSystem` must be one of the three values the page names. | owned elsewhere | `check-spec-buildsystem` already validates the legal values. |
| The crate name must normalise `_` to `-`. | 176 providers spell it with `_` | The page words it with "usually", and a provider that spells the crate name and the package name with the same separator is complete either way. |
| A `%files` section must list `%{_datadir}/cargo/registry/...`. | 0 providers omit it | The clause is never violated in the corpus, so a checkpoint would be pure overhead. |
| A provider with a patched `Cargo.toml` keeps the patch, the metadata copy and the source tree consistent. | not decidable | The spec text records neither which dependency was generated nor which was hand-edited, so the rule cannot tell a deliberate patch from a stale copy. |
| Generated `Requires` and `Provides` must be regenerated rather than hand-edited. | not decidable | Same reason: the spec text has no marker for a generated line. |
| A dependency range crossing two compatibility keys is patched rather than rewritten. | not decidable | Requires reading the upstream `Cargo.toml` and the modified one, which is outside a spec-only linter. |
| A `rust` application provides `crate(...)`. | 27 specs, 0 provide it | Applications install binaries rather than crate sources, so asking a tool for a crate capability would report 27 correct specs. |
| A `pyproject` Rust extension keeps a `Cargo.toml` in the package directory. | 23 of 23 carry one | Worth a checkpoint in principle, but the corpus never violates it, and the clause is stated for the generator rather than for the packager. |
| A `pyproject` Rust extension runs `%rust_setup_registry` in `%prep`. | 0 omit it | Never violated, and the build rule owns the `%prep` shape. |
| A `crate(...)` dependency carries a feature path when one is needed. | not decidable | Which features the build needs comes from the source tree, not from the spec text. |
| Every `crate(...)` runtime dependency carries a version. | 39161 `Requires: crate(` lines | The page's examples are build dependencies only, so a runtime constraint is not the stated property; reporting it would drown the rule. |
| A provider keeps the upstream `LICENSE` file. | owned elsewhere | `check-spec-license` and the licence rules already cover the field. |
| A provider names its `crate(...)` capability `%{pkgname}` rather than a literal. | 2354 use the macro | Conforming but not required, and the two spellings are equivalent after expansion. |

## Examples

A crate provider that passes every checkpoint:

```specfile
%global crate_name serde
%global full_version 1.0.228
%global pkgname serde-1

Name:           rust-serde-1
Version:        1.0.228
Release:        %autorelease
Summary:        Serialization framework for Rust
License:        MIT OR Apache-2.0
URL:            https://crates.io/crates/%{crate_name}
Source:         https://static.crates.io/crates/%{crate_name}/%{full_version}/download
BuildArch:      noarch
BuildSystem:    rustcrates
BuildRequires:  rust-rpm-macros

Provides:       crate(%{pkgname}) = %{full_version}

%description
Serialization framework for Rust.

%files
%license LICENSE-MIT
%doc README.md
%{_datadir}/cargo/registry/%{crate_name}-%{full_version}/

%changelog
%autochangelog
```

That spec lives at `SPECS/rust-serde-1/rust-serde-1.spec`, with the
`Cargo.toml` the page asks for next to it.

A Rust application that passes every checkpoint:

```specfile
Name:           ripgrep
Version:        14.1.0
Release:        %autorelease
Summary:        Line-oriented search tool
License:        MIT
URL:            https://github.com/BurntSushi/ripgrep
Source:         https://github.com/BurntSushi/ripgrep/archive/%{version}.tar.gz
BuildSystem:    rust
BuildRequires:  rust
BuildRequires:  rust-rpm-macros
BuildRequires:  crate(grep-0.3/default) >= 0.3.0
BuildRequires:  crate(clap-4/derive) >= 4.5.0

%description
Line-oriented search tool.

%install
install -Dm0755 target/release/rg %{buildroot}%{_bindir}/rg

%files
%{_bindir}/rg

%changelog
%autochangelog
```

A provider that names itself without the prefix, groups a version wrongly
and keeps a compatibility name that is finer than the key:

```specfile
%global crate_name serde
%global full_version 1.0.228
%global pkgname serde-1.0

Name:           serde-1
Version:        1.0.228
Release:        %autorelease
BuildSystem:    rustcrates
BuildRequires:  rust-rpm-macros
```

That spec produces three findings: C1 for the name, C2 for the directory
and the file name once they follow the wrong name, and C4 for the key.
Switching any of them off with the matching flag leaves the others in
place.

A spec that mixes the two dependency spellings, which is the mistake the
corpus actually shows:

```specfile
Name:           mesa
BuildSystem:    meson
BuildRequires:  rust
BuildRequires:  rust-rpm-macros
# FIXME: use crate(xxx) when it's allowed by pre-commit hook
BuildRequires:  rust-syn-2 >= 2.0.87
```

That spec produces one C6 finding per `rust-*` line, because `mesa` builds
Rust through a `crate(...)` dependency that it declares with a package
name instead.
