# check-spec-programming-golang

Enforce the requirements that the Go language packaging guideline states for
a Go library or application package.

## Original Requirement

Source:
<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/languages/Golang>

Section "Dependencies" states, verbatim:

> The following two build dependencies are indispensable:
>
> ```specfile
> BuildRequires:  go
> BuildRequires:  go-rpm-macros
> ```

> When writing a Go library dependency, you must use the prescribed virtual
> dependency, whose format is `go(<import path>)`.

Section "Provides" states, verbatim:

> The library package itself must explicitly write out the import path and
> version it provides in the RPM spec.

Section "Files" states, verbatim:

> All files must be installed to `/usr/share/gocode/src`, which corresponds
> to `$GOPATH/src`.

Section "Naming" states, verbatim:

> Every Go library has its own import path ... we replace all of its slashes
> with hyphens, and use a canonical identifier in place of the host name to
> name the package.

> For large repository-level packages that contain several modules, the
> name should be generated from the normalised VCS repository root path.

> The name of such a package should match the upstream project, for
> example `ollama`. Naming it `go-ollama` is wrong. Likewise, the generated
> binary subpackage name must not contain the `go-` prefix.

Section "Versioning" states, verbatim:

> Because the import path is the same, the two must be declared mutually
> exclusive in the RPM spec.

Section "Testing" states, verbatim:

> We recommend not adding several libraries to one test include macro; when
> the tests of a library fail, keep the library under test and exclude the
> libraries whose tests fail.

That clause is worded as a recommendation, which is why C9 is the one
SHOULD-level checkpoint of this rule.

## Flags

| Flag | Effect |
| --- | --- |
| `--no-check-toolchain` | Do not report the missing `go` toolchain (C1). |
| `--no-check-macros-package` | Do not report the missing `go-rpm-macros` package (C2). |
| `--no-check-virtual-dependency` | Do not report a bare import path in `BuildRequires` (C3). |
| `--no-check-capability-version` | Do not report a `go()` capability without a version (C4). |
| `--no-check-files-location` | Do not report library files installed outside the Go source tree (C5). |
| `--no-check-package-name` | Do not report a library name not derived from the import path (C6). |
| `--no-check-binary-name` | Do not report a `go-` prefixed binary package name (C7). |
| `--no-check-test-include` | Do not report a test include macro that names several libraries (C9). |
| `--no-check-shared-import-path` | Do not report a shared import path without `Conflicts:` (C10). |

## Checkpoints

| ID | Requirement | Strength |
| --- | --- | --- |
| C1 | A spec that declares a Go build system must declare `go` in `BuildRequires`. | MUST |
| C2 | A spec that declares a Go build system must declare `go-rpm-macros` in `BuildRequires`. | MUST |
| C3 | A Go library build dependency must use the virtual dependency form `go(<import path>)`. | MUST |
| C4 | A `go(<import path>)` capability must state its version. | MUST |
| C5 | Every file of a Go library must be installed under `/usr/share/gocode/src`. | MUST |
| C6 | A Go library package name must be derived from its import path. | MUST |
| C7 | A binary package name must not carry the `go-` prefix. | MUST |
| C9 | One test include macro must not name several libraries. | SHOULD |
| C10 | A spec that shares an import path with another package must declare it mutually exclusive. | MUST |

C1 and C2 are the pair the page calls "indispensable". C3, C4, C5, C6 and
C7 are each worded with "must" or with a direct declaration of what the
spec has to write. C9 is worded with "we recommend", so it is SHOULD. C10
follows from "the two must be declared mutually exclusive".

### C1

```
BuildSystem: golangmodules (line 12) requires "go" in BuildRequires; missing "go"
```

Deciding details:

- The package is matched as a whole name, so `golang`, `golang-bin` and
  `go-toolset` do not satisfy `go`.
- A version constraint is accepted: `BuildRequires: go >= 1.20` satisfies
  the requirement, because the version operator and its operand are dropped
  before the name is compared.
- A commented-out declaration does not count.
- A declaration in any `%package` block counts, because RPM merges the
  `BuildRequires` of every subpackage into one build dependency set.
- The finding points at the line of the `BuildSystem` declaration, not at a
  missing line, since there is nothing to point at in the spec.

### C2

```
BuildSystem: golangmodules (line 12) requires "go-rpm-macros" in BuildRequires; missing "go-rpm-macros"
```

Deciding details:

- The package is matched as a whole name. `go-rpm-macros-extra` does not
  satisfy `go-rpm-macros`.
- A version constraint is accepted.
- The deciding details of C1 apply unchanged.

### C3

```
BuildRequires (line 18) names the bare import path "github.com/stretchr/testify"; write it as the virtual dependency "go(github.com/stretchr/testify)"
```

Deciding details:

- Only a `BuildRequires` item that already contains a `/` is judged. A
  plain package name such as `git` or `gcc` carries no import path, so the
  clause does not apply to it.
- The item is accepted once it starts with `go(`, both with and without a
  version constraint that follows the closing parenthesis.
- The token is read up to its first whitespace, so a trailing relational
  operator does not shift the reported name.

### C4

```
Provides: go(github.com/jpillora/backoff) (line 22) does not state a version; write "go(github.com/jpillora/backoff) = %{version}"
```

Deciding details:

- A `Provides` field may join several capabilities with commas, so each
  item is judged on its own.
- A version is stated when the remainder after the closing parenthesis
  starts with `=` and holds an operand. `>=`, `<` and a bare `=` are not
  accepted, because the page asks for the version the package provides
  rather than for a range.
- The import path is macro expanded before it is printed, so the reported
  form is the one the reader sees in the built spec.

### C5

```
%files entry "%{_datadir}/chroma/v2" (line 74) installs outside the Go source tree; the page requires every file of a Go library under /usr/share/gocode/src, which corresponds to $GOPATH/src
```

Deciding details:

- Only the library subpackages are judged, meaning every `%package` block
  other than the main one. The main package of a `golangmodules` spec ships
  the same Go sources but also the built executable, and a `golang` spec
  ships the executable alone, so the page does not govern the `%files` block
  of the main package.
- A subpackage is judged only when it provides a `go()` capability, because
  that capability is what makes it a library.
- Four roots are accepted: `/usr/share/gocode/src`,
  `%{_datadir}/gocode/src`, `%{go_sys_gopath}` and `%{gopath}`. A macro is
  expanded before the comparison, so a spec that spells the root with a
  macro is accepted as well.
- A `%files` entry is read past its directives. `%dir`, `%config`,
  `%attr`, `%defattr`, `%verify` and `%lang` only modify the path that
  follows them, so the entry is judged by that path.
- An entry that names no path, such as `%doc README.md` or
  `%license LICENSE`, and an entry that starts with `%exclude`, is skipped:
  the page governs where a library installs, not what documentation or
  licensing a subpackage ships.

### C6

```
Name: go-github-jpillora-backhof (line 3) is not derived from the import path "github.com/jpillora/backoff"; name the package "go-github-jpillora-backoff" (replace every slash with a hyphen and the host with the canonical identifier)
```

Deciding details:

- Only a `golangmodules` spec is judged. Its main package provides the
  module the repository root names, so the derivation is well defined. A
  `golang` spec names an application after the upstream project instead,
  which C7 governs.
- The import path is read from the `go_import_path` macro when it is
  defined and covers a provided capability, and from the first `go()`
  capability otherwise.
- The name is macro expanded and then reduced to its canonical spelling,
  so case and punctuation differences do not matter.
- Three forms are accepted. The name may be the derived candidate itself,
  it may add an `-vN` or `-vN-M` suffix for the Go module major version, or
  it may extend the candidate with the path segments the candidate leaves
  over. That last form is what makes a repository-level package name legal
  while a misspelled segment is still reported.
- A candidate is derived for a repository root as well as for the full
  path, so a large repository-level package that is named after its
  repository root is accepted.
- A path whose host the page does not tabulate yields no candidate and is
  left alone. The tabulated hosts are `github.com`, `git.sr.ht`,
  `gitlab.com`, `bitbucket.org` and `codeberg.org`, and the canonical
  identifier of each is the one the page lists.

### C7

```
Name: go-kubectl (line 3) carries the "go-" prefix in a BuildSystem: golang spec; the binary package name follows the upstream project, so drop the "go-" prefix
```

Deciding details:

- Only a `golang` spec is judged. A `golangmodules` library is expected to
  carry the `go-` prefix, which C6 governs.
- Every package of the spec is judged, including each subpackage, because
  the page bans the prefix for the generated binary subpackage names as
  well as for the main binary package.
- A package that provides a `go()` capability is exempt: it is a library,
  so the prefix is the correct one for it.
- A name that starts with a macro is expanded before it is judged, and a
  name that still contains `%` is skipped, because its final spelling is
  not known to a spec-only linter.
- The exception the page states for a project that is genuinely called
  `go-something` cannot be told apart from a wrong name by a linter, so the
  flag `--no-check-binary-name` exists for a spec that hits it.

### C9

```
go_test_include (line 16) names 2 libraries (github.com/jpillora/backoff, github.com/spf13/afero) in one test include; keep the library under test and exclude the libraries whose tests fail
```

Deciding details:

- Only the `go_test_include` and `go_test_include_glob` macros are judged,
  because those are the two macros the page names for a test include.
- The macro value is expanded fully, so a `%{shrink:}` block that spells
  the same library several times counts as one library.
- A library is identified by its repository root rather than by its full
  path, because the page counts libraries, not packages. A repository root
  takes three segments for a hosting site and two for a vanity import path,
  so a spec that lists several packages of one repository is accepted.
- The other test macros the page documents, `go_test_exclude`,
  `go_test_exclude_glob`, `go_test_ignore_failure` and the four
  `go_test_*_option` macros, are not judged.

### C10

```
Provides: go(github.com/planetscale/vtprotobuf) (line 39) shares its import path with go-github-planetscale-vtprotobuf-v0.4.spec; the page requires the packages that share an import path to be mutually exclusive, so declare "Conflicts: go(github.com/planetscale/vtprotobuf)"
```

Deciding details:

- One spec cannot show the presence of the other one, so this checkpoint
  reads an index built from every file the run covers. The index is built
  once per run and is never built for a single file, which means the
  checkpoint is silent when the rule is called on one spec alone.
- The clause covers two packages that provide the same import path, for
  example the legacy and the latest release of one library. The page words
  it as "the two must be declared mutually exclusive", so the finding asks
  for a `Conflicts:` field naming the same capability.
- A capability that is spelled with a macro is skipped, because only a
  literal path can be matched against a sibling spec.
- A `Conflicts:` item is accepted both in the `go(<import path>)` form and
  as a plain package name, because RPM treats both as a conflict.

## Scope notes

Measured against the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`: 6341 specs in `SPECS`, of which
1240 declare a Go build system, 1215 as `BuildSystem: golangmodules` and 25
as `BuildSystem: golang`.

| Checkpoint | Findings | Affected files |
| --- | --- | --- |
| C1 | 0 | 0 |
| C2 | 0 | 0 |
| C3 | 0 | 0 |
| C4 | 4 | 4 |
| C5 | 0 | 0 |
| C6 | 3 | 3 |
| C7 | 1 | 1 |
| C9 | 0 | 0 |
| C10 | 1 | 1 |
| **Total** | **9** | **9** |

C4 is the largest group. The four specs spell the capability as
`go(...)` without a version, which is the one clause the page states as
"must explicitly write out the import path and version". C6 reports three
specs whose name drifts from the import path, and C7 reports one `golang`
spec that names its binary package with the `go-` prefix. C10 reports one
of the two vtprotobuf version slots as missing its `Conflicts:` field.

C1, C2, C3, C5 and C9 have zero findings. All of them are implemented
anyway: C1 to C3 are the dependency rules the page states up front, C5 is
its install location clause and C9 is its only recommendation, so a rule
that fires on future regressions is the point of a pre-commit hook. C5
judged 1004 library `%files` blocks and found none misplaced, and C9
examined 22 test include definitions.

### Boundary with check-spec-build-go

`check-spec-build-go` enforces the Go page of the BuildSystems chapter. Two
of its checkpoints overlap with this rule, because both pages name the same
dependency pair:

| Overlap | This rule | check-spec-build-go |
| --- | --- | --- |
| `BuildRequires: go` and `BuildRequires: go-rpm-macros` | C1 and C2 report each one separately | reports the pair once |
| The `_name` and `go_import_path` header macros | not checked | reports a missing macro and a macro defined after the first section |

A spec that satisfies both pages is reported by neither rule. A spec that
misses the pair is reported by both, in the form each page words it. To
avoid the double report, disable C1 and C2 with `--no-check-toolchain` and
`--no-check-macros-package` in a run that already applies
`check-spec-build-go`.

### Rejected candidates

Every candidate below was measured on the same corpus and then rejected.

| Candidate | Findings | Why it was rejected |
| --- | --- | --- |
| `go_test_*` comment requirements (C8) | 10 of 310 units | The page words the clause with "should", counts a unit as a library rather than a spec, and the 10 hits are specs whose comments describe a different unit. The rule cannot count the test units it never sees. |
| A spec that uses the Go build system must not put its `Source` at the module URL instead of the repository URL | - | Both spellings are legal upstream addresses and the page gives the repository form as an example, not as a requirement. |
| A `Requires:` field must mirror every `go()` build dependency | 122 of 806 lack it, 291 name fewer `Requires` than `BuildRequires` | The page never states that a runtime requirement mirrors a build requirement. The counts show that the corpus deliberately declares only the runtime closure. |
| `go_import_path` must carry a comment naming the upstream project | 1272 hits | The comment is an editorial aid the page shows in an example, not a constraint, and reporting the whole population is not a finding. |
| `%go_common` and `%__go` must be used instead of the plain binaries | - | The page documents the macros but never requires them, and a spec that calls `go build` directly is legal. |
| A large package must use `Version` and one unified capability version | - | The page explains the version slots but leaves the split to the packager, and a spec-only linter cannot read the upstream module graph. |
| The legacy/latest version slot assignment must follow a fixed rule | - | The page describes the slots, and which release becomes the latest is a repository policy decision. |
| `go2spec` must be used to generate the spec | - | The page presents the generator as a convenience, and a hand-written spec that satisfies the checkpoints is correct. |
| `go_test_exclude`, `go_test_exclude_glob` and `go_test_ignore_failure` must not appear | 80+ legitimate uses | The page documents all three as the escape hatch for a failing dependency, so their presence is compliance rather than a violation. |
| A migration must keep a compatibility symlink for the old path | - | The page describes the symlink as a temporary measure, and its absence is not an error. |
| The VCS repository-level packaging boundary | - | Enforcing it means knowing how the upstream repository is laid out, which a spec-only linter cannot establish. |
| A `BuildSystem` value must be one of `golang` / `golangmodules` | - | The legal value set belongs to `check-spec-buildsystem`. |

Deliberately out of scope as well: the `%prep`, `%build`, `%install` and
`%check` stages of the Go build systems, which belong to
`check-spec-build-go`; the `BuildSystem` field value itself, which belongs
to `check-spec-buildsystem`; and every other dependency question, which
belongs to `check-spec-buildrequires`.

No network access and no `rpm` invocation is performed, so the rule works on
a bare checkout.

## Examples

Passing `golangmodules` library:

```specfile
%define go_import_path  github.com/jpillora/backoff

Name:           go-github-jpillora-backoff
Version:        1.0.0
Release:        %autorelease
Summary:        Backoff algorithm for Go
License:        MIT
URL:            https://github.com/jpillora/backoff
Source:         %{url}/archive/v%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    golangmodules

BuildRequires:  go
BuildRequires:  go-rpm-macros
BuildRequires:  go(github.com/stretchr/testify)

Provides:       go(%{go_import_path}) = %{version}

%description
Exponential backoff algorithm in Go.

%files
%{go_sys_gopath}/%{go_import_path}
```

Passing `golang` application, whose binary package follows the upstream
project:

```specfile
%define _name kubectl

Name:           kubectl
Version:        1.31.0
Release:        %autorelease
Summary:        Command line tool for Kubernetes
License:        Apache-2.0
URL:            https://github.com/kubernetes/kubernetes
Source:         %{url}/archive/v%{version}.tar.gz
BuildSystem:    golang

BuildRequires:  go
BuildRequires:  go-rpm-macros

%description
The Kubernetes command line tool.

%install
install -Dpm0755 _output/bin/kubectl %{buildroot}%{_bindir}/%{_name}

%files
%{_bindir}/%{_name}
```

Passing, with two version slots declared mutually exclusive:

```specfile
Name:           go-github-planetscale-vtprotobuf
BuildSystem:    golangmodules
BuildRequires:  go
BuildRequires:  go-rpm-macros

Provides:       go(github.com/planetscale/vtprotobuf) = %{version}
Conflicts:      go(github.com/planetscale/vtprotobuf)
```
