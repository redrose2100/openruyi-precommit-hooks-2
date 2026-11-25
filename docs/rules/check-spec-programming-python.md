# check-spec-programming-python

Enforce the requirements that the Python language packaging guideline
states for a package that ships a Python module.

## Original Requirement

Source:
<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/languages/Python>

Section "Naming" states, verbatim:

> Packages for Python libraries must use the `python-` prefix.

> For the package name (`DISTNAME`), use the name the upstream project uses
> on PyPI. You must add the following macro at the top of the spec file:
>
> ```specfile
> %global srcname DISTNAME
> ```

> In short, the `srcname` macro represents the project's name on PyPI. The
> name must also follow the normalized name rules in
> [PEP 503](https://peps.python.org/pep-0503/): use lowercase letters, and
> replace `_` and `.` with `-`. For example, if the upstream project name is
> `aiohttp_socks`, use `aiohttp-socks` as the package name and `srcname`.

The page then shows the shape it asks for, which is worth reading twice
because the prefix and the macro appear together in one name:

> ```specfile
> %global srcname aiohttp-socks
>
> Name:           python-%{srcname}
> ```

That example is why C1 and C2 are separate checkpoints: a spec may carry
the prefix without the macro, and the page asks for both.

Section "Provides: python3-DISTNAME" states, verbatim:

> Since openRuyi does not split `python3` into a separate subpackage, but
> instead provides it directly from the main package, if the package is
> architecture-independent, you should add the following entries to the
> spec file:
>
> ```specfile
> Provides:       python3-DISTNAME = %{version}-%{release}
> %python_provide python3-DISTNAME
> ```

> If the package is architecture-dependent, you should add the following
> entries to the spec file instead:
>
> ```specfile
> Provides:       python3-%{srcname}%{?_isa} = %{version}-%{release}
> ```

> Here, you can replace `DISTNAME` with the previously defined macro, which
> is typically `%{srcname}`.

The `%{?_isa}` suffix is architecture dependent, so C4 accepts either
spelling: a `Provides:` line without a suffix and a
`%python_provide` invocation both satisfy the clause.

Section "Dependencies" states, verbatim:

> Packages should not declare an explicit runtime dependency on `python3`,
> because the following dependencies are added automatically in the
> corresponding cases:
>
> - When you install files into `%{python3_sitelib}` or
>   `%{python3_sitearch}`, the build system automatically generates a
>   dependency on `python(abi) = 3.X`.
> - If the package contains executable Python scripts, the build system
>   automatically generates a dependency on `/usr/bin/python3`.

## Flags

Every checkpoint can be switched off on its own, so a repository that
deliberately deviates from one clause can keep the rest.

| Flag | Default | Effect |
| --- | --- | --- |
| `--no-check-package-name` | on | Do not report a Python library package name without the `python-` prefix. |
| `--no-check-srcname` | on | Do not report a missing `srcname` macro. |
| `--no-check-srcname-normalised` | on | Do not report a `srcname` macro that is not PEP 503 normalised. |
| `--no-check-python3-provides` | on | Do not report a missing `python3-` capability. |
| `--no-check-python3-requires` | on | Do not report an explicit runtime dependency on `python3`. |

## Checkpoints

| ID | Checkpoint | Strength | Scope |
| --- | --- | --- | --- |
| C1 | A package that ships modules carries the `python-` prefix. | MUST | Spec with `BuildSystem: pyproject` that installs into the module directory. |
| C2 | A `python-` named package defines the `srcname` macro. | MUST | Spec with `BuildSystem: pyproject` whose `Name` starts with `python-`. |
| C3 | The `srcname` macro carries a PEP 503 normalised name. | MUST | Spec with `BuildSystem: pyproject` that defines `srcname`. |
| C4 | A package that ships modules provides a `python3-` capability. | MUST | Spec with `BuildSystem: pyproject` that installs into the module directory. |
| C5 | A package does not declare an explicit dependency on `python3`. | MUST | Spec with `BuildSystem: pyproject`. |

All five clauses are worded as a requirement ("must use", "use the name the
upstream project uses on PyPI", "must also follow the normalized name
rules", "you should add the following entries" and "should not declare an
explicit runtime dependency"), so all five are MUST. A repository that keeps
an intentionally unprefixed package or an upstream-original `srcname`
spelling switches the relevant flag off rather than reword the finding.

## Scope

A spec is judged when it declares `BuildSystem: pyproject`, because that
is the declarative build system the page describes and it is the only
signal a spec-only linter can read to tell a Python library package from a
C or C++ package that merely ships Python bindings.

The narrower population of "a package that ships modules" is decided by
the presence of `%{python3_sitelib}` or `%{python3_sitearch}` in the spec
text, which is where the runtime-dependency clause says the modules are
installed. C1 and C4 are judged only on that population, so a command line
tool built with pyproject keeps its name and its capability to itself.

```
BuildSystem: pyproject                    891 specs
  installs into the module directory       52 specs   <- C1, C4
  otherwise                                 ...         <- C2, C3, C5 only
```

The count is measured against the openRuyi corpus, not asserted: `ceph`
declares `BuildSystem: cmake` and `bind` declares `BuildSystem: autotools`,
so both are absent from the 891 even though both install Python modules.

## C1 - a package that ships modules carries the python- prefix

The checkpoint reads the main `Name:` field after expanding the macros of
the spec, so `Name: python-%{srcname}` and `Name: python-aiohttp-socks`
are both accepted.

The finding names the spelling the page asks for, derived by lowercasing
the current name and replacing `_` and `.` with `-`:

```
Name:           dblatex
```

produces

```
Name: dblatex (line 1) does not carry the python- prefix; a Python
library package must be named "python-dblatex"
```

A name that still holds an unexpanded macro after expansion is skipped, so
a spec that composes its name from a macro the linter cannot resolve is
left alone rather than guessed at.

## C2 - a python- named package defines the srcname macro

The clause is anchored on the name: the page says the prefix and the macro
belong together, so only a spec whose expanded `Name` starts with `python-`
is asked for the macro. A tool package without the prefix is not asked, and
a spec that never declares `python-` in its name keeps its silence here.

The finding points at the name line rather than at the top of the file,
because that is where the packager reads the prefix and looks for the
macro that should define it:

```
Name: python-msgspec (line 9) is a Python library package without a
srcname macro; add "%global srcname DISTNAME" at the top of the spec
```

## C3 - the srcname macro carries a PEP 503 normalised name

The value of the macro is expanded before it is judged, so an indirection
such as `%global srcname %{upstream_name}` is resolved and checked.

The accepted spelling is exactly the one the page states: lowercase
letters, digits, and single `-` separators. The pattern is
`^[a-z0-9]+(-[a-z0-9]+)*$`, which is the PEP 503 normalisation of a
project name.

Quoting is stripped before the check, so `%global srcname "PyYAML"` is
judged on `PyYAML` and still reported.

The finding quotes the normalised spelling so the packager can paste it:

```
%global srcname ruamel.yaml (line 9) is not PEP 503 normalised; use
lowercase letters and replace "_" and "." with "-", for example
"ruamel-yaml"
```

This checkpoint is deliberately blunt about upstream case. `Cython`, `PyYAML`
and `Whoosh` are the names PyPI publishes, but the page asks `srcname` to
follow PEP 503 rather than the project's own capitalisation, and a name
with a capital letter is not reachable through the normalised index path
anyway.

## C4 - a package that ships modules provides a python3- capability

The capability counts as declared when either spelling the page shows is
present:

* a `Provides:` field whose dependency name starts with `python3-`, or
* a `%python_provide` macro invoking a `python3-` capability.

Both are accepted because the page presents them as a pair, and a spec that
keeps only one of the two still advertises the capability.

The finding names the capability in the spec's own spelling: `%{srcname}`
when the macro is defined, otherwise the normalised name the spec itself
suggests. A subpackage that declares the capability satisfies the clause as
well, because the clause is about the package advertising it, not about
which block carries the line.

The `python3` subpackage question is settled by the page itself: openRuyi
does not split `python3` into subpackages and provides the capability from
the main package instead. The rule does not insist on the main block, so a
spec that already ships a `python3-` subpackage is not lectured.

## C5 - a package does not declare an explicit dependency on python3

Only `Requires:` fields are read. `BuildRequires:` is a different field
with a different meaning, and the page's clause is about runtime.

A dependency line is reduced to its names, so a version operator and the
version after it never look like a dependency, and a rich dependency in
parentheses is dropped entirely. The remaining names are compared with
`python3` exactly, which keeps these spellings silent:

* `python3-devel` and `python3-libs`, which are distinct packages,
* `python3dist(requests)`, which is a capability rather than the
  interpreter,
* `python(abi) = 3.11`, which is the automatic dependency the page
  describes.

The finding repeats the reason the page gives, so a packager understands
why the line is redundant:

```
Requires: python3 >= 3.9 (line 15) declares an explicit runtime
dependency on python3; a package that installs into
%{python3_sitelib} or %{python3_sitearch} already depends on
"python(abi)" automatically
```

## Boundary with check-spec-build-pyproject

`check-spec-build-pyproject` already covers the build side of the same
page family, and three of its clauses are close to this rule:

| Clause | Owner | Overlapping checkpoint here |
| --- | --- | --- |
| The spec declares `pyproject-rpm-macros`. | `check-spec-build-pyproject` | none |
| The spec declares `pkgconfig(python3)` or `python3-devel`. | `check-spec-build-pyproject` | none |
| `BuildOption(install)` names the modules to save. | `check-spec-build-pyproject` | none |
| `%files` reads `%{pyproject_files}`. | `check-spec-build-pyproject` | none |

There is no overlap on purpose. The build rule owns what the build needs;
this rule owns what the resulting package is named, what it advertises and
what it must not depend on. A repository that enables both sees each spec
reported once, without any flag juggling.

The split is visible in the clauses this rule deliberately leaves alone:
`pkgconfig(python3)` is a build dependency, `BuildOption(install)` is a
build option, and `%{pyproject_files}` is a file list. All three belong to
the build rule, and repeating them here would report one problem twice.

## Scope notes

Measured against the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`:

| Metric | Count |
| --- | --- |
| `.spec` files scanned | 6341 |
| Specs with `BuildSystem: pyproject` | 891 |
| Specs that install into the module directory | 52 |
| Findings, default flags | 58 |
| Files with at least one finding | 55 |

Per checkpoint:

| ID | Findings | Notes |
| --- | --- | --- |
| C1 | 3 | `dblatex`, `rpmlint`, `setools`. |
| C2 | 4 | Four library specs carry the prefix but no macro. |
| C3 | 47 | Mostly upstream original capitalisation and `_` separators. |
| C4 | 2 | `dblatex` and `rpmlint` provide no capability. |
| C5 | 2 | `dblatex` declares `Requires: python3`. |

Fifty-five files carry fifty-eight findings, because `dblatex` is reported
by C1, C4 and C5, `rpmlint` by C1 and C4, and `mkosi` only by C5. `mkosi`
is a tool, so it keeps its name and needs no capability, but it still
declares `Requires: python3`, which the runtime clause forbids.

C2 is worth reading in full, because all four findings are the same
omission:

- `python-linux-procfs`, `python-msgspec`,
  `python-sphinxcontrib-devhelp` and `python-systemd` carry the prefix and
  spell the upstream name in `Source`, but never introduce `srcname`, so
  the `Source` line cannot be written in terms of the macro the page asks
  for.

C3 is the checkpoint with the widest spread, and the forty-seven findings
fall into two groups:

- Thirty-one use `_` or `.` where the page asks for `-`: `gi_docgen`,
  `annotated_types`, `boolean.py`, `curl_cffi`, `discord.py`,
  `en_core_web_sm`, `flit_scm`, `hatch_fancy_pypi_readme`,
  `hatch_nodejs_version`, `hatch_vcs`, `hf_xet`, `huggingface_hub`,
  `ipython_pygments_lexers`, `language_data`, `libarchive_c`,
  `mistral_common`, `prompt_toolkit`, `pyproject_hooks`,
  `pytest_asyncio`, `pytest_env`, `pytest_freezer`, `python_discovery`,
  `requests_file`, `rpmautospec_core`, `ruamel.yaml`,
  `ruamel.yaml.clib`, `semantic_version`, `service_identity`,
  `setuptools_scm`, `spacy_legacy` and `spacy_loggers`.
- Sixteen keep the upstream capitalisation: `Beaker`,
  `BingImageCreator`, `CherryPy`, `CppHeaderParser`, `Cython`, `IPython`,
  `LAC`, `PyQt-builder`, `PyQt6-sip`, `PySocks`, `PyYAML`, `Tempita`,
  `Whoosh`, and two more spelled entirely in lowercase.

Both groups are the deviation the page names, so both are reported. Each
finding quotes the normalised spelling, so the fix is a single substitution
in each spec.

### Rejected candidates

| Candidate | Corpus count | Why it is rejected |
| --- | --- | --- |
| `srcname` must be defined in every spec with `BuildSystem: pyproject`. | 839 without one | Most are command line tools, and the page scopes the macro to a library package name. Asking a tool for it would report 839 correct specs. |
| `pypi_name` must be defined when the download name differs. | 3 defined but unused | The page makes the macro conditional on the upstream project publishing under a different name, which a spec-only linter cannot decide. |
| `Source` must use `%{pypi_source %{srcname}}`. | 631 use `%{srcname}` directly | The page allows a project site or a GitHub tag as a source, and `%{pypi_source}` is one convenience form rather than a requirement. |
| The spec must call `%pyproject_save_files` explicitly. | 900 files use `%{pyproject_files}`, 19 call the macro | The declarative build system generates the file list, so the explicit call is not the observable property. |
| `%files` must reference `%{pyproject_files}`. | 5 | Real, and worth a checkpoint, but it belongs to `check-spec-build-pyproject` and was not selected for this rule. |
| `BuildRequires` must include `pyproject-rpm-macros`. | owned elsewhere | `check-spec-build-pyproject` already reports it, so a second rule would double-report. |
| `BuildRequires` must include `pkgconfig(python3)` or `python3-devel`. | owned elsewhere | Same reason. |
| `BuildOption(install)` must name the module. | owned elsewhere | Same reason. |
| `%generate_buildrequires` must invoke `%pyproject_buildrequires`. | 12 | The page does not state the clause, and a spec may generate its requirements by hand for a legitimate reason. |
| The package must be built with `%pyproject_wheel` and `%pyproject_install`. | 891 | The declarative build system runs both stages, so a spec correctly omits them and the finding would hit every judged spec. |
| A `python-` package must carry `BuildArch: noarch`. | 0 observable | The field is correct only when no extension module is built, which the spec text does not show. |
| `Provides` must carry `%{?_isa}` for an architecture dependent package. | not decidable | Whether the package is architecture dependent needs the build output, not the spec text. |
| Every module must be reachable through `python3dist(...)`. | not stated | The page never asks for it, and the automatic provider generation already supplies it. |

## Examples

A spec that passes every checkpoint:

```specfile
%global srcname requests

Name:           python-%{srcname}
Version:        2.32.3
Release:        %autorelease
Summary:        Python HTTP for Humans
License:        Apache-2.0
URL:            https://requests.readthedocs.io/
Source0:        %{pypi_source %{srcname}}
BuildArch:      noarch
BuildSystem:    pyproject

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3dist(pytest)

Provides:       python3-%{srcname} = %{version}-%{release}
%python_provide python3-%{srcname}

%description
Python HTTP for Humans.

%prep
%autosetup -p1 -n %{srcname}-%{version}

%generate_buildrequires
%pyproject_buildrequires -t

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files %{srcname}

%files -f %{pyproject_files}
%{python3_sitelib}/requests

%changelog
%autochangelog
```

A spec that names the library without the prefix, ships its modules and
declares the interpreter as a runtime dependency:

```specfile
Name:           dblatex
BuildSystem:    pyproject

Requires:       python3

%description
DocBook to LaTeX transform.

%install
%pyproject_install
%pyproject_save_files dblatex

%files
%{python3_sitelib}/dblatex
```

That spec produces three findings: C1 for the name, C4 for the missing
capability, and C5 for the `Requires:` line. Switching any of them off with
the matching flag leaves the other two in place.

A spec that normalises the macro but keeps a tool's name:

```specfile
%global srcname aiohttp-socks

Name:           python-%{srcname}
BuildSystem:    pyproject

Provides:       python3-%{srcname} = %{version}-%{release}
%python_provide python3-%{srcname}

%files -f %{pyproject_files}
%{python3_sitelib}/aiohttp_socks
```

That spec produces no finding at all, because the prefix, the macro, the
normalisation and the capability are all present.
