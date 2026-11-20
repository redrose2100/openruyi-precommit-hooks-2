# check-spec-build-cmake

Enforce the requirements that the openRuyi packaging guidelines place on a
spec file whose build system is CMake.

## Original Requirement

Source: <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/BuildSystems/cmake>

The page states that a CMake package must declare the build-system field and
must depend on `cmake`:

> Specify `cmake` in the `BuildSystem` field, and declare `cmake` in
> `BuildRequires`.

The same dependency clause is repeated for the `%build` step, where the macros
are described as already handling the configure, build and install phases:

> Build system notes:
> - The `%cmake` macro handles the configure phase automatically; every `-D`
>   option belongs in `BuildOption(conf)`.
> - The `%cmake_build` macro handles the build phase automatically.
> - The `%cmake_install` macro handles the install phase automatically.
> - The `%ctest` macro runs the tests automatically; extra test arguments
>   belong in `BuildOption(check)`.

Two consequences of that wording are machine-checkable and are reported here:

1. Because `%ctest` "runs the tests automatically", an explicit `%check`
   section whose whole body is an argument-free `ctest` cannot add anything
   to the build.
2. Because the `-D` options "belong in `BuildOption(conf)`" and the macros
   "handle" each phase "automatically", a `BuildOption(conf)` flag that
   repeats a value the shipped macros already define is dead weight.

## Flags

| Flag | Default | Effect |
| --- | --- | --- |
| `--no-check-buildrequires` | check enabled | Skip C1, the `cmake` dependency check. |
| `--no-check-check-section` | check enabled | Skip C2, the redundant `%check` check. |
| `--no-check-build-option` | check enabled | Skip C3, the redundant `BuildOption(conf)` check. |

All three checks apply only to a spec that declares `BuildSystem: cmake`. A
spec that builds with another system, or that omits the field, is never
reported; the flags only narrow that set further.

## Checkpoints

| ID | Checkpoint | Strength |
| --- | --- | --- |
| C1 | A spec with `BuildSystem: cmake` declares `cmake` as a build dependency. | MUST |
| C2 | A spec with `BuildSystem: cmake` has no `%check` section that only re-runs `ctest`. | SHOULD |
| C3 | A spec with `BuildSystem: cmake` does not repeat a macro-defined value in `BuildOption(conf)`. | SHOULD |

### C1 — the `cmake` build dependency

```
demo.spec: BuildSystem: cmake (line 8) requires "cmake" in BuildRequires; missing "cmake"
```

- One finding per file, reported on the first `BuildSystem: cmake` line.
- The field name is matched case-insensitively and tolerates the
  `Buildsystem` spelling that occurs in the corpus.
- The field value is matched case-insensitively, so `CMake` counts.
- A dependency is satisfied by the whole name `cmake`, so `cmake >= 3.20` and
  `Cmake` count.
- `extra-cmake-modules` and `kf6-extra-cmake-modules` are different packages
  and do **not** satisfy the requirement.
- A dependency declared in any block counts. `BuildRequires` is a
  source-package level field, so RPM merges the declarations of every
  subpackage block into one build dependency set.
- A commented-out `BuildRequires` line is ignored.

### C2 — the redundant `%check` section

```
demo.spec: %check (line 14) runs "ctest" without arguments, which the %ctest macro already runs for BuildSystem: cmake; remove the redundant %check
```

- The finding is reported on the `%check` header line.
- Only a body that is exactly one non-comment line counts, and that line must
  be `ctest` or `%ctest` with no argument.
- A `ctest` that carries arguments is never reported. The page asks for those
  arguments to move into `BuildOption(check)`, which is a placement question
  owned by `check-spec-buildoption`, not a redundancy this rule may drop.
- A `ctest` that sits inside an `%if` guard is never reported. The body of a
  guarded section holds the conditional plus the statement, so removing the
  section would make the tests unconditional.
- An empty `%check` section is not reported.
- Comment lines inside the section are ignored, so a documented `ctest` is
  still recognised as a bare one.

### C3 — the redundant `BuildOption(conf)` flag

```
demo.spec: BuildOption(conf) (line 9) repeats "-DLIB_SUFFIX=64", which the cmake macros already define
```

- The finding is reported on the `BuildOption` line, once per repeated flag.
- Both the name **and** the value must match a value the macros already
  define. Overriding a default with another value is a deliberate choice and
  is never reported.
- The whole line is scanned, so a line that carries several `-D` flags is
  judged flag by flag.
- Only the `conf` stage is inspected. A flag of the `build`, `install` or
  `check` stage belongs to a different phase and is out of scope.
- A value may be written with a CMake type, as in
  `-DCMAKE_BUILD_TYPE:STRING=RelWithDebInfo`.

The values the macros already define:

| Flag | Value |
| --- | --- |
| `CMAKE_BUILD_TYPE` | `RelWithDebInfo` |
| `CMAKE_VERBOSE_MAKEFILE` | `ON` |
| `CMAKE_INSTALL_DO_STRIP` | `OFF` |
| `BUILD_SHARED_LIBS` | `ON` |
| `LIB_SUFFIX` | `64` |
| `CMAKE_INSTALL_PREFIX` | `%{_prefix}` |
| `CMAKE_INSTALL_LIBDIR` | `%{_lib}` |
| `CMAKE_INSTALL_FULL_LIBDIR` | `%{_libdir}` |
| `CMAKE_INSTALL_SBINDIR` | `bin` |
| `CMAKE_INSTALL_FULL_SBINDIR` | `%{_sbindir}` |
| `CMAKE_INSTALL_LIBEXECDIR` | `%{_libexecdir}` |
| `CMAKE_INSTALL_FULL_LIBEXECDIR` | `%{_libexecdir}` |
| `INCLUDE_INSTALL_DIR` | `%{_includedir}` |
| `LIB_INSTALL_DIR` | `%{_libdir}` |
| `SYSCONF_INSTALL_DIR` | `%{_sysconfdir}` |
| `SHARE_INSTALL_PREFIX` | `%{_datadir}` |

The table records the defaults of the packaging macros, not a preference of
this rule. A macro update that changes a default is a change to this table.

## Scope notes

Measured against the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`: 6341 spec files, of which 434
declare `BuildSystem: cmake`.

| Checkpoint | Findings | Files |
| --- | --- | --- |
| C1 | 112 | 112 |
| C2 | 0 | 0 |
| C3 | 43 | 43 |

C2 was narrowed after measuring the corpus, and the narrowing removes every
current finding. Twelve specs carry a `%check` that mentions `ctest`: six
invoke it with arguments, so the page asks to relocate the arguments rather
than to delete the section, and six invoke it bare but wrap it in an
`%if %{with test}` guard. Deleting a guarded run would make the tests
unconditional and change behaviour, so a guarded body does not count as a
bare body and is not reported. No spec in the corpus has a `%check` whose
whole body is an unguarded `ctest`, so the checkpoint currently reports
nothing. It stays in the rule because the construct it forbids is the one the
page describes, and a later spec can introduce it.

C3 was narrowed the same way. Fifty-five flags in `BuildOption(conf)` repeat a
macro-defined name: forty-three repeat the name **and** the value, and
twenty-one of those lines also override a default with a different value
(`-DBUILD_SHARED_LIBS:BOOL=OFF`, `-DCMAKE_BUILD_TYPE:STRING=None`,
`-DBUILD_SHARED_LIBS=1`). The rule reports the forty-three redundant flags and
leaves the twenty-one overrides alone.

Candidates that were considered and rejected:

- **A `%cmake` invocation without `BuildSystem: cmake`.** The page presents the
  field as the way to declare the build system, but it does not forbid calling
  the macros directly. The corpus has no such spec, so the checkpoint would
  have no evidence behind it.
- **`cmake --install` inside `%install`.** The page asks for the
  `%cmake_install` macro, which is a style preference for a step that the
  macros already cover. The corpus has no such spec either.

Out of scope on purpose:

- The `%build` and `%install` macro requirements are not checkable per file
  without deciding that a phase must be written a particular way, which the
  page does not require.
- Whether a `-D` flag is placed in the right stage is owned by
  `check-spec-buildoption`.
- Whether the `%check` arguments belong in `BuildOption(check)` is likewise
  owned by `check-spec-buildoption`.

## Examples

### Passing

```spec
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
URL:            https://example.org/demo
Source0:        https://example.org/demo-1.0.tar.gz
BuildSystem:    cmake
BuildRequires:  cmake

%description
A demo package.

%check
%ctest --output-on-failure
```

The dependency is declared, and the `%check` passes an argument, so it is not
a bare re-run of what the macro does.

### Failing

```spec
Name:           demo
Version:        1.0
Release:        1
Summary:        A demo package
License:        MIT
URL:            https://example.org/demo
Source0:        https://example.org/demo-1.0.tar.gz
BuildSystem:    cmake
BuildRequires:  extra-cmake-modules
BuildOption(conf):  -DCMAKE_BUILD_TYPE:STRING=RelWithDebInfo

%description
A demo package.

%check
ctest
```

Three findings: `extra-cmake-modules` is not `cmake`, the build type repeats
the macro default, and the `%check` body is a bare `ctest`.
