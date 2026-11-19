# check-spec-subpackaging

Validate the subpackaging declarations of an openRuyi spec file.

## Original Requirement

### Source A — Packaging guidelines, `Subpackaging and Splitting Rules`

<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/#subpackaging-and-splitting-rules>

The section states five clauses, rendered here in English:

1. A spec **must** split by functional category, not by fine-grained module,
   plugin or file. The subpackage name **must** be `%{name}-<feature>`.
2. When development files exist, they **must** be split into
   `%{name}-devel`.
3. When the volume or the number of documentation files is large, the
   documentation **must** be split into `%{name}-doc`.
4. System shared libraries and their links **must** be placed in the package
   that the `SplitPackage` supplement describes.
5. When splitting changes the package name, a smooth upgrade path **must** be
   provided through `Obsoletes` and `Provides`.

### Source B — `SplitPackage` supplement

<https://www.openruyi.cn/zh-Hans/docs/guide/splitpackage/>

The supplement turns clause 4 into a division of `%{_libdir}` and adds the
rules for the content of each subpackage:

- The separator of a subpackage name **must** be `-`. The characters `_`,
  `+` and `.` are not allowed, except in special cases. A name shaped
  `%{name}-featureX-moduleY` should be avoided because it follows the code
  structure rather than the feature.
- Three classes live in `%{_libdir}`:

  | File | Class | Package |
  | --- | --- | --- |
  | `libfoo.so.3.2.0` | real file | runtime, **must not** be in `-devel` |
  | `libfoo.so.3` | SONAME link | runtime, **must not** be in `-devel` |
  | `libfoo.so` | unversioned link | **must** be in `-devel` |

- Development content is `*.h` headers, `pkgconfig/*.pc`, the CMake package
  configuration, and the unversioned `libfoo.so` link.
- A private or plugin library that is not in the linker search path and is
  loaded from a private directory does **not** belong in `-devel`; it stays
  with the main or the feature package, and the global `Provides` and
  `Requires` that RPM generates from it **must** be filtered.
- A runtime library should **not** be split into `%{name}-libs`. It stays in
  the main package, which declares
  `Provides:       %{name}-libs = %{version}-%{release}`, and each runtime
  library inside `%files` carries a `#` comment.
- A subpackage that depends on its base package **must** use the strict form
  `Requires:       %{name}%{?_isa} = %{version}-%{release}`.
- Language packs **must** be separate subpackages.

### Strength summary

| Clause | Wording | Level |
| --- | --- | --- |
| Name uses `-` | Supplement states it as a rule, with a carve out | MUST |
| Name is `%{name}-<feature>` | Clause 1 | MUST |
| Development files in `-devel` | Clause 2 and the supplement | MUST |
| Documentation in `-doc` | Clause 3, gated on a packager judgement | MUST |
| Runtime and SONAME libraries outside `-devel` | Clause 4 and the supplement | MUST |
| Unversioned link in `-devel` | Clause 4 and the supplement | MUST |
| Split by functional category | Clause 1 | MUST |
| Upgrade path across a rename | Clause 5 | MUST |
| `libs` subpackage avoided | Supplement, "should not" | SHOULD |
| Subpackage dependency pins the version | Supplement | MUST |

## Flags

| Flag | Disables |
| --- | --- |
| `--no-check-name` | P1, the separator of a subpackage name |
| `--no-check-dev-files` | P2, the package that holds the development content |
| `--no-check-versioned-library` | P3, the versioned library inside `-devel` |
| `--no-check-unversioned-link` | P4, the unversioned link outside `-devel` |
| `--no-check-dependency` | P5, the version pin of a subpackage `Requires` |

## Checkpoints

| ID | Checkpoint | Source | Strength |
| --- | --- | --- | --- |
| P1 | A subpackage name uses `-` as its separator. | A1, B | MUST |
| P2 | Development content is packaged in the `-devel` subpackage. | A2, B | MUST |
| P3 | A `-devel` subpackage carries no versioned shared library. | A4, B | MUST |
| P4 | The unversioned `lib*.so` link lives in the `-devel` subpackage. | A4, B | MUST |
| P5 | A subpackage that requires its base package pins the version. | B | MUST |

### Scope notes

- Clause 1's "split by functional category" and clause 3's "large
  documentation" are **not** enforced. Which category a file belongs to is a
  packager judgement that the spec does not record, and neither the volume
  nor the file count that make documentation "large" is defined. Both need
  the intent of the packager rather than the text of the spec.
- Clause 5's upgrade path is **not** enforced. Whether a rename needs
  `Obsoletes` and `Provides` depends on the history of the package, which the
  current spec does not carry.
- P1 reports `_` and `.` but never `+`, and only when the subpackage adds the
  character on top of the base package name. A Rust feature subpackage is
  spelled `%{name}+serde`, which the supplement carves out, and the openRuyi
  repository writes 8183 such names. A base package whose own name contains
  `_` or `.` is common (`libcom_err`, `cairomm1.0`), so its subpackages
  inherit the character legitimately. A name that carries a macro cannot be
  resolved without expanding it and is skipped.
- P2 recognises a header only below the include directory. A file that
  merely ends in `.h` is not counted, because a program may ship a header for
  its own run time (`%{_datadir}/dwarves/runtime/ctracer_relay.h`) and the
  clause is about the headers a compiler includes. A CMake package file is
  recognised by its `cmake` directory under a library or data directory,
  which is where a consumer's `find_package` looks; a `.cmake` file elsewhere
  (`%{_rpmmacrodir}/macros.cmake`) is not development content.
- P2 separates the two directions of the clause. When the spec declares a
  `-devel` subpackage, a development file elsewhere is in the wrong package.
  When it declares none, the finding says that the content exists and was
  never split out.
- P3 and P4 need a `-devel` subpackage to compare against. Without one, the
  finding belongs to P2, so P4 stays silent rather than reporting every
  unversioned link twice.
- P4 only reports a link directly below a library directory. A file one level
  deeper sits in a private plugin directory (`%{_libdir}/lighttpd/mod_authn_pam.so`),
  which the supplement places with the main or the feature package, so it is
  not a development file. A name that carries a macro
  (`%{_libdir}/libfoo-%{version}.so`) is skipped, because the file name
  embeds the version rather than being a linker link.
- P5 only reads a plain runtime `Requires`. A qualified form such as
  `Requires(post):` declares a scriptlet dependency and is not the clause
  under check. The pin accepts any release reference (`%{release}`,
  `%{nodejs_version}-%{release}`), because a spec that keeps a second version
  macro is still pinned `= %{version}`-equivalent. A requirement qualified by
  a rich dependency parenthesis (`foo(bar)`) is not read.
- The supplement's `libs` guidance is SHOULD level and stays advisory, and
  the `#` comment it asks for above each runtime library carries no machine
  readable meaning, so no checkpoint counts comments.
- Language packs are already produced by RPM through `%find_lang`, so their
  absence is not a defect of the spec.
- A `%files` header that names no package lists the files of the **main**
  package, which is why the main package writes a bare `%files`. It is not
  attached to the `%package` that happens to precede it, because a spec
  commonly writes `%files -f %{name}.lang` for the main package and
  `%files devel` for the subpackage in that order.
- Only a column zero section header is recognised, and only within the closed
  section whitelist, so a `%global` or a `%if` neither ends a block nor hides
  the `%files` entries that follow it. A comment and a `%exclude` line inside
  a `%files` block are dropped, because neither packages a file.
- No network access and no `rpm` invocation is performed, so the rule works
  on a bare checkout.

## Examples

Passing spec:

```text
%package devel
Summary:        Development files for foo
Requires:       %{name}%{?_isa} = %{version}-%{release}

%files
%license LICENSE
%{_libdir}/libfoo.so.1
%{_libdir}/libfoo.so.1.2.3

%files devel
%{_includedir}/foo.h
%{_libdir}/libfoo.so
%{_libdir}/pkgconfig/foo.pc
```

P1 — the subpackage name uses `_`:

```text
foo.spec: subpackage lighttpd-mod_authn_dbi (line 144) uses "_" in its name; separate the parts with "-" and write lighttpd-<feature>
foo.spec: subpackage cairomm1.0-extras (line 88) uses "." in its name; separate the parts with "-" and write cairomm1.0-<feature>
```

P2 — development content is in the wrong package, or was never split out:

```text
foo.spec: pkgconfig file %{_libdir}/pkgconfig/mm-glib.pc (line 111) is packaged in libmm-glib; move it to the ModemManager-devel subpackage
foo.spec: header file %{_includedir}/foo.h (line 41) is packaged in foo, but the spec declares no foo-devel subpackage to hold it
```

P3 — a versioned library is packaged in `-devel`:

```text
foo.spec: versioned shared library %{_libdir}/libfoo.so.1 (line 68) is packaged in foo-devel; keep the real file and the SONAME link in the runtime package
```

P4 — the unversioned link is outside `-devel`:

```text
foo.spec: unversioned library link %{_libdir}/libfoo.so (line 45) is packaged in foo; move the *.so link to the foo-devel subpackage
```

P5 — the subpackage does not pin its base package:

```text
foo.spec: Requires foo (line 56) in foo-scrub does not pin the base package; write "Requires:       foo%{?_isa} = %{version}-%{release}"
foo.spec: Requires foo = %{version} (line 49) in foo-devel does not pin the base package; write "Requires:       foo%{?_isa} = %{version}-%{release}"
```
