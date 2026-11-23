# check-spec-build-pyproject

Enforce the requirements that the packaging guidelines state for the
`pyproject` declarative build system.

## Original Requirement

Source:
<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/BuildSystems/pyproject>

Section "Dependencies" states, verbatim:

> If you need to use the `pyproject` build system, then you typically need
> to add at least these `BuildRequires`:
>
> ```specfile
> BuildRequires:  pyproject-rpm-macros
> BuildRequires:  pkgconfig(python3)
> ```

Section "Automatic dependency generation" states, verbatim:

> By writing the following in a spec file that uses the `pyproject`
> declarative build system, you let the build system add the build
> dependencies automatically according to PEP 517 and PEP 518.
>
> ```specfile
> %generate_buildrequires
> %pyproject_buildrequires
> ```
>
> If the automatically generated build dependencies are insufficient, or
> the package also needs non-Python dependencies or system library
> dependencies, you should keep adding `BuildRequires` as needed.

Section "Example" states, verbatim:

> Note that when using the `pyproject` declarative build system you must
> pass the corresponding module name to `BuildOption(install)`. Because
> that option is passed as an argument to `%pyproject_save_files`, adding
> the `-l` argument by default is usually recommended.

Section "Testing" states, verbatim:

> The `pyproject` declarative build system runs a smoke test by default,
> namely an import check of the installed modules. Generally speaking, you
> should not simply empty `%check` to skip the tests.
>
> If you need to exclude some modules during this process, you can pass
> arguments to `%pyproject_check_import` through `BuildOption(check)`, and
> write the reason for the exclusion above it. For example:
>
> ```specfile
> BuildSystem:  pyproject
>
> BuildOption(install):  example_pkg
> # No module named 'marray'
> BuildOption(check):  -e 'example_pkg.tests*'
> ```

Section "Scope" states, verbatim:

> The `pyproject` declarative build system applies to the following
> scenarios:
>
> - the upstream source root contains `pyproject.toml`
> - the build process follows the PEP 517 interface

That clause is the one part of the page this rule cannot implement: it
selects the build system by inspecting the upstream tarball, which a
spec-only linter never sees. The rule therefore starts from the declared
value and judges what the declaration implies.

## Flags

| Flag | Effect |
| --- | --- |
| `--no-check-macros-package` | Do not report the missing `pyproject-rpm-macros` (C1). |
| `--no-check-python-devel` | Do not report the missing Python development dependency (C2). |
| `--no-check-install-option` | Do not report a spec that passes no module name to the install stage (C3). |
| `--no-check-install-option-module` | Do not report a `BuildOption(install)` that carries only options (C4). |
| `--no-check-check-section` | Do not report an empty `%check` (C5). |
| `--no-check-check-reason` | Do not report a `BuildOption(check)` without a stated reason (C6). |

## Checkpoints

| ID | Requirement | Strength |
| --- | --- | --- |
| C1 | A spec that declares `BuildSystem: pyproject` must declare `pyproject-rpm-macros` in `BuildRequires`. | MUST |
| C2 | A pyproject spec must declare a Python development dependency: `pkgconfig(python3)`, `pkgconfig(python)` or `python3-devel`. | MUST |
| C3 | A pyproject spec must pass the module name to the install stage, either through `BuildOption(install)` or through an explicit `%pyproject_save_files`. | MUST |
| C4 | The value of `BuildOption(install)` must carry at least one module name, not only options. | MUST |
| C5 | A `%check` section must not be empty: it needs either a command or a comment that states why the tests are skipped. | MUST |
| C6 | The first `BuildOption(check)` of a group must have a comment line above it stating the reason for the exclusion. | MUST |

C1 and C2 are worded with "typically need at least", so a spec that
satisfies the clause in another equivalent spelling is accepted rather than
reported. C3 to C6 reproduce clauses the page words with "must" or with
"should not ... without writing the reason", so they describe the normal
form the page asks for.

### C1

```
BuildSystem: pyproject (line 9) requires "pyproject-rpm-macros" in BuildRequires; missing "pyproject-rpm-macros"
```

Deciding details:

- The package is matched as a whole name. `python3-pyproject-rpm-macros`
  does not satisfy `pyproject-rpm-macros`.
- A version constraint is accepted: `BuildRequires: pyproject-rpm-macros >=
  2.0` satisfies the requirement, because the version operator and its
  operand are dropped before the name is compared.
- A comma-separated list satisfies the requirement.
- A commented-out declaration does not count.
- A declaration in any `%package` block counts, because RPM merges the
  `BuildRequires` of every subpackage into one build dependency set.
- A spec that declares another build system, or none at all, is not judged.

### C2

```
BuildSystem: pyproject (line 9) requires a Python development dependency in BuildRequires; missing pkgconfig(python3), pkgconfig(python), python3-devel
```

Deciding details:

- Three spellings are accepted, because they express the same build-time
  requirement and the corpus uses all three: `pkgconfig(python3)`,
  `pkgconfig(python)` and `python3-devel`.
- The capability is matched in its rich-dependency form, so the generic
  dependency splitter does not truncate `pkgconfig(python3)` at
  `pkgconfig(`.
- A near miss does not count: `python3-devel-extra` and `python3.10-devel`
  are different packages.
- `python3dist(...)` declarations do not satisfy this checkpoint. The page
  names a development dependency, not a Python module dependency,
  and those belong to `check-spec-buildrequires`.
- A declaration in any `%package` block counts.

### C3

```
BuildSystem: pyproject (line 9) requires the module name to install; neither BuildOption(install) nor %pyproject_save_files is written
```

Deciding details:

- The page asks for the module name, not for the specific field that
  carries it. An explicit `%pyproject_save_files example` delivers the same
  argument to the same macro, so a spec that writes it is accepted.
- A spec that writes both is accepted as well.
- A `BuildOption(install)` that exists but is empty is reported by C4
  instead, so one spec produces one finding for this concern.
- A spec that never installs anything still needs the option: the macro
  cannot guess the module names.

### C4

```
BuildOption(install) (line 10) carries only options; the module name to install is missing
```

Deciding details:

- Every token that starts with `-` is an option, and `+auto` asks the
  macros to discover the modules. Only the remaining tokens count as
  module names.
- `%{srcname}` is a module name, so `BuildOption(install): -l %{srcname}`
  is accepted.
- `BuildOption(install): -l` and `BuildOption(install): +auto` are
  reported, because neither one names a module.
- `BuildOption(install): -l example +auto` is accepted, because the module
  name is present even though discovery is requested as well.

### C5

```
%check (line 21) is empty; a pyproject build runs a smoke test by default, so an empty %check skips the tests without a stated reason
```

Deciding details:

- A comment inside the section makes the section acceptable: the page asks
  the packager to write why the tests are skipped, so writing it complies.
  `%check` holding only `# skip tests as some deps we do not have yet.`
  passes.
- A command inside the section passes, including `%pytest`, `%tox` and
  `%pyproject_check_import`.
- A `BuildOption(check)` line alone does not make the section non-empty:
  the option is metadata rather than a command, so a `%check` holding only
  `BuildOption(check): -e 'pkg.tests*'` is still reported.
- A spec with no `%check` section at all is not reported. The page does not
  require the section, and `check-spec-script` owns its presence.

### C6

```
BuildOption(check) (line 22) does not state the reason for excluding modules; a comment line above it is expected
```

Deciding details:

- The comment may sit directly above the option or be separated from it by
  blank lines; both are accepted.
- Only the first option of a consecutive group is judged. The page asks for
  one reason above the group, so `BuildOption(check)` followed by another
  `BuildOption(check)` needs one comment, not two.
- A second group, separated from the first by any unrelated line, needs its
  own comment.
- A comment that sits above the group but also documents something else is
  accepted: only the presence of a comment is checked, not its wording.

## Scope notes

Measured against the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`: 6341 specs in `SPECS`, of which
891 declare `BuildSystem: pyproject`.

| Checkpoint | Findings | Affected files |
| --- | --- | --- |
| C1 | 5 | 5 |
| C2 | 1 | 1 |
| C3 | 0 | 0 |
| C4 | 0 | 0 |
| C5 | 15 | 15 |
| C6 | 68 | 68 |
| **Total** | **89** | **89** |

C3 and C4 have zero findings. Both are implemented anyway: C3 is the exact
clause the page words with "must", and C4 is the failure mode that hides
behind it, so a rule that only fires on future regressions is the point of
a pre-commit hook.

### Rejected candidates

Every candidate below was measured on the same corpus and then rejected.

| Candidate | Findings | Why it was rejected |
| --- | --- | --- |
| `BuildOption(install)` must carry `-l` | 186 of 891 lack it | The page calls it a recommendation ("adding the `-l` argument by default is usually recommended") and tells the packager to remove it when the build reports `No License-File`. A recommendation cannot be a finding. |
| `%license LICENSE` must not be written when `-l` is used | - | The page says the manual entry is "usually unnecessary" and names the case where it is still needed. Forbidding it would contradict the page's own exception. |
| `%generate_buildrequires` and `%pyproject_buildrequires` must be present | 24 of 891 lack the section, 26 use no `%pyproject_*` macro at all | The page presents the pair as the way to enable automatic generation, not as a requirement. The specs without it run explicit phases, which is a legitimate path the page also documents. |
| `%files` must be exactly `%files -f %{pyproject_files}` | 0 (886 of 891 use that literal; the remaining 5 use no `-f` at all) | Pinning the literal would reject a legal generator with another file name. The requirement that survived from this candidate is "the main `%files` reads a generated list with `-f`", which is part of `check-spec-build-files` scope rather than of this rule. |
| A `%check` that holds only a comment must be reported | 16 of 891 | The page asks the packager to write the reason for skipping, so a comment is compliance rather than a violation. |
| Every `BuildOption(check)` line needs its own comment | 231 of 453 lines lack one | The corpus writes one comment per group; requiring one per line would report 163 additional false findings. |
| `%check -a` plus `%pytest`, or `%tox`, must be written | - | The page introduces both as "if you need to add pytest tests", which is conditional advice. |
| `BuildOption(generate_buildrequires)` must carry `-t` | - | The page gives `-t` as an example and allows passing the test dependencies by hand when they cannot be generated. |
| A pyproject spec must not keep `%build` or `%install` sections | 85 of 891 keep at least one | The page says those stages "can be left to the build system" and also documents `%install -a` for extra cleanup, so keeping a section is legal. |
| A pyproject spec must also declare `python-rpm-macros` | - | The page never names that package. |
| The upstream source must contain `pyproject.toml` and follow PEP 517 | - | Needs the unpacked upstream source tree, which a spec-only linter cannot inspect. The page also hedges that a project carrying `pyproject.toml` is "not necessarily" suitable. |

Deliberately out of scope as well: the syntax of `BuildOption`, which
belongs to `check-spec-buildoption`; the `BuildSystem` field value itself,
which belongs to `check-spec-buildsystem`; every other dependency question,
which belongs to `check-spec-buildrequires`; and the presence of `%check`,
which belongs to `check-spec-script`.

No network access and no `rpm` invocation is performed, so the rule works on
a bare checkout.

## Examples

Passing:

```specfile
Name:           python-example
Version:        1.0
Release:        %autorelease
Summary:        An example module
License:        MIT
URL:            https://example.org/example
Source0:        https://example.org/example/example-1.0.tar.gz
BuildArch:      noarch
BuildSystem:    pyproject
BuildOption(install):  -l example
BuildRequires:  pyproject-rpm-macros
BuildRequires:  pkgconfig(python3)
BuildRequires:  python3dist(setuptools)

%description
An example module.

%generate_buildrequires
%pyproject_buildrequires

%check
# No module named 'marray'
BuildOption(check):  -e 'example.tests*'

%files -f %{pyproject_files}
```

Passing, with the equivalent Python dependency spelling and an explicit
install stage:

```specfile
Name:           python-example
Version:        1.0
Release:        %autorelease
Summary:        An example module
License:        MIT
URL:            https://example.org/example
Source0:        https://example.org/example/example-1.0.tar.gz
BuildSystem:    pyproject
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel

%description
An example module.

%install
%pyproject_install
%pyproject_save_files example

%files -f %{pyproject_files}
%{_bindir}/example
```

Failing:

```specfile
Name:           python-demo
Version:        1.0
Release:        1
Summary:        A demo module
License:        MIT
URL:            https://example.org/demo
Source0:        https://example.org/demo/demo-1.0.tar.gz
BuildSystem:    pyproject
BuildRequires:  python3dist(setuptools)

%description
A demo module.

%check

%files
```

```
demo.spec: BuildSystem: pyproject (line 8) requires "pyproject-rpm-macros" in BuildRequires; missing "pyproject-rpm-macros"
demo.spec: BuildSystem: pyproject (line 8) requires a Python development dependency in BuildRequires; missing pkgconfig(python3), pkgconfig(python), python3-devel
demo.spec: BuildSystem: pyproject (line 8) requires the module name to install; neither BuildOption(install) nor %pyproject_save_files is written
demo.spec: %check (line 14) is empty; a pyproject build runs a smoke test by default, so an empty %check skips the tests without a stated reason
```
