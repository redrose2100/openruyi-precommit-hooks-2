# check-spec-build-go

Enforce the requirements that the packaging guidelines state for the
`golang` and `golangmodules` build systems.

## Original Requirement

Source:
<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/BuildSystems/golang>

Section "Dependencies" states, verbatim:

> If you need to use the `golang` or `golangmodules` build system, then you
> need to add these `BuildRequires`.
>
> ```specfile
> BuildRequires:  go
> BuildRequires:  go-rpm-macros
> ```

Section "Which macros are needed" states, verbatim:

> At least `_name` and `go_import_path` should be defined in the header. The
> former is usually the name of the Go library, the latter is usually the
> import path of the Go library.

The two clauses above are the only normative statements on the page. Every
other sentence is advice, an example, or a pointer at the macro files:
`%prep` is offered with "may be used directly", test arguments are shown as
an optional `BuildOption(check)` tweak, and calling into the other build
system is described as explicitly allowed.

## Flags

| Flag | Effect |
| --- | --- |
| `--no-check-buildrequires` | Do not report a missing `go` or `go-rpm-macros` build dependency (C1). |
| `--no-check-name-macro` | Do not report a missing or misplaced `_name` macro (C2). |
| `--no-check-import-path-macro` | Do not report a missing or misplaced `go_import_path` macro (C3). |

## Checkpoints

| ID | Requirement | Strength |
| --- | --- | --- |
| C1 | A spec that declares `BuildSystem: golang` or `BuildSystem: golangmodules` must declare both `go` and `go-rpm-macros` in `BuildRequires`. | MUST |
| C2 | The same spec must define the `_name` macro with `%define` or `%global`, in the header. | MUST |
| C3 | The same spec must define the `go_import_path` macro with `%define` or `%global`, in the header. | MUST |

### C1

Both dependencies are required, and each missing one is reported on its own
line:

```
BuildSystem: golangmodules (line 11) requires "go" and "go-rpm-macros" in BuildRequires; missing "go"
BuildSystem: golangmodules (line 11) requires "go" and "go-rpm-macros" in BuildRequires; missing "go-rpm-macros"
```

Deciding details:

- A version constraint is accepted. `BuildRequires: go >= 1.26.8` satisfies
  the requirement, because the version operator and its operand are dropped
  before the name is compared.
- The name is matched as a whole name. `go-rpm-macros`, `go-md2man` and
  `golang` are distinct packages: `go-rpm-macros` satisfies the second
  requirement, while `go-md2man` satisfies neither.
- A rich dependency is skipped. `go(github.com/example/demo)` names a Go
  module capability, not the `go` package the page asks for, so it does not
  satisfy C1.
- A commented-out declaration does not count.
- A declaration in any `%package` block counts, because RPM merges the
  `BuildRequires` of every subpackage into one build dependency set.
- A spec that never declares a Go build system is not judged at all.

### C2

```
BuildSystem: golang (line 11) requires the "_name" macro in the header; no %define or %global sets it
BuildSystem: golang (line 11) requires the "_name" macro in the header; line 41 defines it after the first section
```

Deciding details:

- Either `%define` or `%global` is accepted, and the separator between the
  macro name and its value may be spaces or a tab.
- A commented-out definition does not count.
- "Header" means before the first section. A definition that only appears
  after `%prep`, `%build`, `%install`, `%check`, `%files` and so on is
  reported, because the macros the build system expands read `_name` while
  the header is processed.
- The value is not compared with anything. The page says `_name` is usually
  the Go library name, which is regularly different from `Name:`: the corpus
  has 1213 such specs on purpose, so comparing them would be a false
  positive generator.

### C3

```
BuildSystem: golangmodules (line 11) requires the "go_import_path" macro in the header; no %define or %global sets it
```

Deciding details:

- The name must match exactly. A differently named macro such as
  `api_import_path`, `client_import_path` or `go_compat_import_path` does not
  satisfy the requirement.
- The value is not validated. The corpus has no `go_import_path` with a URL
  scheme, a trailing slash or an empty value, so there is nothing to report
  and no ground to reject a value shape the page does not forbid.

## Scope notes

Measured against the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`: 6341 specs in `SPECS`, of which
1240 declare `golang` or `golangmodules`.

| Checkpoint | Findings | Affected files |
| --- | --- | --- |
| C1 | 0 | 0 |
| C2 | 1 | 1 |
| C3 | 2 | 2 |
| **Total** | **3** | **2** |

The single C2 finding and one of the two C3 findings are the same spec,
`SPECS/kata-containers/kata-containers.spec`: it declares
`BuildSystem: golang` but defines no macro at all and drives a hand-written
`make` instead of the Go macros. The other C3 finding is
`SPECS/moby/moby.spec`, which defines `_name` and then uses
`api_import_path` and `client_import_path` instead of a single
`go_import_path`.

C1 has zero findings because every one of the 1240 specs already declares
both dependencies. It is implemented anyway: it is the one clause of the
page that is phrased as a requirement, and a rule that only fires on future
regressions is the point of a pre-commit hook.

### Rejected candidates

Every candidate below was measured on the same corpus and then rejected.

| Candidate | Findings | Why it was rejected |
| --- | --- | --- |
| A `%check` whose whole body is `%{go_common}` | 0 | Zero findings, and the page only says the macros already contain `%check`; it never forbids a hand-written section. |
| `BuildOption(check)` together with a hand-written `%check` that runs `go test` | 17 `BuildOption(check)` plus `%check` pairs, 6 of which run `go test` | Manual review showed every one of the six runs a **specific** target (`-run '^TestFS$'`, `-run '^$'`, `go test -c -o /dev/null`), which is not a duplicate of the default run. Reporting them would be a false positive. |
| A `golangmodules` spec that carries its own `%install` or `%check` | 80 `%install`, 116 `%check` | The page explicitly allows calling into the other build system, so these sections are legal. |
| A spec that calls `%go_common` without `BuildSystem: golang` | 3 (`etcd`, `fzf`, `ollama`) | Those three build with no declared system, `autotools` and `cmake` respectively; the page names this cross-system call as supported. |
| A spec without `BuildOption(prep): -n %{_name}-%{version}` | 995 | The page offers it as optional ("may be used directly"), and 64 specs legitimately pass `%{commit_id}` instead of `%{version}`. |
| A dependency spelled `golang` or `golang-rpm-macros` | 0 | Zero findings. |
| A `go_import_path` with a URL scheme, a trailing slash or an empty value | 0 | Zero findings. |
| `_name` must equal `Name:` | 1213 | The page says `_name` is the Go **library** name, which is legitimately different from the package name, so every one of the 1213 would be a false positive. |
| A `golang` spec must have a `%build` section | 8 of 25 | The build system supplies `%build` itself, so a missing section is not a violation. |

Deliberately out of scope as well: every dependency question beyond the two
names above, which belongs to `check-spec-buildrequires`, and the placement
of test arguments, which belongs to `check-spec-buildoption`.

No network access and no `rpm` invocation is performed, so the rule works on
a bare checkout.

## Examples

Passing:

```specfile
%define _name           buildx
%define go_import_path  github.com/docker/buildx

Name:           buildx
Version:        0.38.0
Release:        %autorelease
Summary:        Docker CLI plugin for extended build capabilities
License:        Apache-2.0
URL:            https://github.com/docker/buildx
Source0:        https://github.com/docker/buildx/archive/refs/tags/v%{version}.tar.gz
BuildSystem:    golang
BuildRequires:  go >= 1.26.8
BuildRequires:  go-rpm-macros

%description
Docker CLI plugin for extended build capabilities with BuildKit.
```

Failing:

```specfile
Name:           kata-containers
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
BuildSystem:    golang
BuildRequires:  git
BuildRequires:  make

%build
make -C src
```

```
demo.spec: BuildSystem: golang (line 6) requires "go" and "go-rpm-macros" in BuildRequires; missing "go"
demo.spec: BuildSystem: golang (line 6) requires "go" and "go-rpm-macros" in BuildRequires; missing "go-rpm-macros"
demo.spec: BuildSystem: golang (line 6) requires the "_name" macro in the header; no %define or %global sets it
demo.spec: BuildSystem: golang (line 6) requires the "go_import_path" macro in the header; no %define or %global sets it
```
