# check-spec-build-meson

Enforce the requirements that the packaging guidelines state for the
`meson` declarative build system.

## Original Requirement

Source:
<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/BuildSystems/meson>

Section "Dependencies" states, verbatim:

> To use the `meson` build system, add the following `BuildRequires`:
>
> ```specfile
> BuildRequires:  meson
> ```

Section "Example" rewrites a hand-written `%build` into the declarative
form. The original section is:

```specfile
%build
%meson -Dman=enabled -Dcompat-symlink=true -Dwtmpdbd=enabled
%meson_build
```

and the page states, verbatim:

> After switching to the declarative `meson` build system, because the build
> process now features a dedicated configuration phase (`%conf`), you must
> move the option arguments to the corresponding section and write them as
> follows:

```specfile
BuildOption(conf): -Dman=enabled
BuildOption(conf): -Dcompat-symlink=true
BuildOption(conf): -Dwtmpdbd=enabled
```

The same example continues, verbatim:

> Since `%meson_build` does not take any additional arguments here, your
> configuration requires no `BuildOption(build)` entries, and you do not
> need a separate `%build` section.

and, for the install phase:

> Likewise, since `%meson_install` does not take any additional arguments in
> the current installation scenario, you do not need to add
> `BuildOption(install)`. Instead, move any commands that follow the
> `%meson_install` macro to the `%install -a` section as needed.

Those three clauses are the only normative statements on the page. The
opening sentence that recommends `BuildSystem: meson` when a project uses
meson is phrased as a recommendation ("we recommend"), so a spec that does
not declare the field is not reported.

## Flags

| Flag | Effect |
| --- | --- |
| `--no-check-buildrequires` | Do not report a missing `meson` build dependency (C1). |
| `--no-check-option-position` | Do not report a meson option outside `BuildOption(conf)` (C2). |
| `--no-check-plain-sections` | Do not report a `%build` or `%install` section that carries a body (C3). |

## Checkpoints

| ID | Requirement | Strength |
| --- | --- | --- |
| C1 | A spec that declares `BuildSystem: meson` must declare `meson` in `BuildRequires`. | MUST |
| C2 | The same spec must write every meson `-Dname=value` option in `BuildOption(conf)`, never in another `BuildOption` stage or inline in a section body. | MUST |
| C3 | The same spec must not keep a plain `%build` or `%install` section that carries statements of its own; the extra commands belong in `%build -a` or `%install -a`. | MUST |

### C1

```
BuildSystem: meson (line 8) requires "meson" in BuildRequires; missing "meson"
```

Deciding details:

- A version constraint is accepted. `BuildRequires: meson >= 1.4.0`
  satisfies the requirement, because the version operator and its operand
  are dropped before the name is compared.
- The name is matched as a whole name. `meson-python` is a different package
  and does not satisfy C1.
- A rich dependency is skipped. `pkgconfig(meson)` names a capability, not
  the `meson` package the page asks for.
- A commented-out declaration does not count.
- A declaration in any `%package` block counts, because RPM merges the
  `BuildRequires` of every subpackage into one build dependency set.
- A spec that never declares `BuildSystem: meson` is not judged at all.

### C2

```
%conf (line 21) carries the meson option "-Dman=enabled"; meson option arguments belong in BuildOption(conf) for BuildSystem: meson
BuildOption(build) (line 10) carries the meson option "-Dman=enabled"; meson option arguments belong in BuildOption(conf) for BuildSystem: meson
```

Deciding details:

- An option is recognized as `-D` followed by a name, an equals sign and a
  value. A flag such as `install -Dpm0644 %{SOURCE1}` or a bare compiler
  define such as `gcc -DFOO` is not a meson option and is never reported.
- Both shapes are reported: a `BuildOption(<stage>)` field whose stage is
  not `conf`, and a `-D` option written inline in any section body.
- A section that carries a suffix is skipped. `%build -a` and
  `%install -a` exist precisely to hold the commands a packager appends
  after the build system has run, so an option there is the packager's own
  business and a false positive would be the only outcome.
- Only the first option on a line is reported, so a line that repeats the
  same mistake is not counted twice.

### C3

```
%build (line 15) has a body of its own; BuildSystem: meson supplies %build itself, so the extra commands belong in %build -a
%install (line 22) has a body of its own; BuildSystem: meson supplies %install itself, so the extra commands belong in %install -a
```

Deciding details:

- Only `%build` and `%install` are managed. `%prep`, `%check` and every
  other section are the packager's own, and the page says nothing about
  them.
- A section that carries a suffix (`%build -a`, `%install -a`) is never
  reported; that form is exactly what the page recommends.
- A section whose body is empty or holds nothing but comments declares
  nothing of its own and is not reported.
- `%check` is not managed even when it calls `%meson_test`: the page does
  not mention the test phase, and 9 specs in the corpus run it on purpose.

## Scope notes

Measured against the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`: 6341 specs in `SPECS`, of which
186 declare `BuildSystem: meson`.

| Checkpoint | Findings | Affected files |
| --- | --- | --- |
| C1 | 0 | 0 |
| C2 | 0 | 0 |
| C3 | 0 | 0 |
| **Total** | **0** | **0** |

All three checkpoints have zero findings because the 186 meson specs in the
corpus already comply: every one of them declares `BuildRequires: meson`,
785 `BuildOption(conf)` lines carry the `-D` options correctly, and no
meson spec keeps a plain `%build` or `%install` with a body. They are
implemented anyway: each one restates a clause the page phrases as a
requirement, and a rule that only fires on future regressions is the point
of a pre-commit hook.

### Rejected candidates

Every candidate below was measured on the same corpus and then rejected.

| Candidate | Findings | Why it was rejected |
| --- | --- | --- |
| A spec that calls `%meson` must declare `BuildSystem: meson` | 1 (`python-dbus-python`) | The page only recommends the field, and that one spec declares `pyproject` on purpose: only that system generates the `python3dist(dbus-python)` capability it needs, and the header comment says so. It still declares `BuildRequires: meson`, so it is not a dependency problem either. |
| A `BuildOption(conf)` line must carry a `-D` option | 14 | The page never says the configuration stage must hold an option; a stage that adjusts something else is legal. |
| `BuildOption(build)` or `BuildOption(install)` must not appear at all | 0 | The page describes the sample where `%meson_build` and `%meson_install` take no extra argument. It does not forbid the fields, and passing a real argument to those macros is the documented way to extend them. |
| A meson spec must have a `%check` section | 13 of 186 have one | The page does not mention tests, so requiring the section would invent a rule. |
| A meson spec must call `%meson_test` | 9 of 186 do | Same reason; the phase is optional. |
| A meson spec must use `%install -a` | 78 of 186 do | The page uses `%install -a` in its sample because that sample has trailing commands. A spec with nothing to append needs no such section. |
| The hand-written `%meson_build` must be removed | 1 (`kea`) | That one call sits inside `%build -a` and passes `doc` to build the documentation target, which is the extension mechanism the page keeps. |
| The hand-written `%meson_install` must be removed | 0 | Zero findings, and the page does not forbid it. |
| Option arguments in `%build -a` are misplaced too | 0 | The `-a` form exists to hold appended commands, so a `-D` there belongs to the packager's own step. |
| `BuildOption(<stage>)` syntax, spacing, stage name and ordering | - | Owned by `check-spec-buildoption`, which already enforces the two-space separator, one argument per line, the mandatory stage name and the write order. Duplicating it here would report the same defect twice. |

Deliberately out of scope as well: every dependency question beyond the
single name above, which belongs to `check-spec-buildrequires`, and the
`BuildSystem` field value itself, which belongs to `check-spec-buildsystem`.

No network access and no `rpm` invocation is performed, so the rule works on
a bare checkout.

## Examples

Passing:

```specfile
Name:           wtmpdb
Version:        0.13.0
Release:        %autorelease
Summary:        Y2038 safe wtmp implementation
License:        LGPL-2.1-or-later
URL:            https://github.com/thom311/wtmpdb
Source0:        https://github.com/thom311/wtmpdb/releases/download/%{version}/wtmpdb-%{version}.tar.xz
BuildSystem:    meson
BuildRequires:  meson
BuildOption(conf):  -Dman=enabled
BuildOption(conf):  -Dcompat-symlink=true
BuildOption(conf):  -Dwtmpdbd=enabled

%description
Y2038 safe wtmp implementation.

%install -a
mkdir -p %{buildroot}%{_mandir}/man1
ln -sf ../man8/wtmpdb.8 %{buildroot}%{_mandir}/man1/last.1
```

Failing:

```specfile
Name:           wtmpdb
Version:        0.13.0
Release:        1
Summary:        Y2038 safe wtmp implementation
License:        LGPL-2.1-or-later
BuildSystem:    meson

%build
%meson -Dman=enabled
%meson_build

%install
%meson_install
```

```
demo.spec: BuildSystem: meson (line 6) requires "meson" in BuildRequires; missing "meson"
demo.spec: %build (line 15) carries the meson option "-Dman=enabled"; meson option arguments belong in BuildOption(conf) for BuildSystem: meson
demo.spec: %build (line 15) has a body of its own; BuildSystem: meson supplies %build itself, so the extra commands belong in %build -a
demo.spec: %install (line 19) has a body of its own; BuildSystem: meson supplies %install itself, so the extra commands belong in %install -a
```
