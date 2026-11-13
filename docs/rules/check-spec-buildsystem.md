# check-spec-buildsystem

## Original Requirement

Source: <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/#buildsystem>

The packaging guidelines define the `BuildSystem` field in four clauses:

1. A spec that uses the RPM declarative build system mechanism must declare
   the build system it uses through `BuildSystem`.
2. A spec that does not use that mechanism may omit `BuildSystem`. Examples
   are a source-less meta-package, a data-only package, and a package that
   implements every build stage through explicit sections.
3. A spec must not add an empty `BuildSystem` field only to say that the
   declarative mechanism does not apply.
4. When `BuildSystem` is present its value must name a supported declarative
   build system. The usable names and their requirements are defined by the
   supplement `BuildSystems`.

Source: <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/BuildSystems>

- `BuildOption(<stage>):` must be separated from its arguments by exactly
  two spaces, and the stage name must be written out.
- `BuildOption` sits between `BuildSystem` and `BuildRequires`, and repeated
  options follow the RPM build order.

Source: `#buildarch` and the base field order section

- `BuildArch` sits between the last `Source` field and the `BuildSystem`
  field.

## Checkpoints

| ID | Checkpoint | Clause |
| --- | --- | --- |
| S1 | The field is spelled `BuildSystem` | field naming |
| S2 | The value is present | clause 3 |
| S3 | The value is one literal lowercase build system name | clause 4 |
| S4 | A field block declares the field at most once | clause 1 |
| S5 | The field sits after the last source declaration of its block | field order |
| S6 | The field sits after `BuildArch` and before `BuildRequires` | field order |

### Scope notes

- The field is conditional. A spec that omits `BuildSystem` entirely is
  never reported: clause 2 makes omission legal and the decision needs
  knowledge of the package payload.
- A spec that builds only through explicit `%prep`, `%build` and `%install`
  sections is a documented reason to omit the field, so the rule never asks
  for it to be added.
- The main spec states that it does not maintain the list of usable build
  system names. A hardcoded whitelist would therefore reject a build system
  added upstream, so S3 only checks the shape of the value. `waf` and
  `muon` are supported by the openRuyi macro packages without appearing in
  every supplement page, which confirms that shape checking is the durable
  rule.
- A macro reference in the value is reported rather than expanded. Unlike
  `BuildArch`, whose value is a parameterised token, this field names a
  fixed build system keyword, so an indirection cannot be resolved
  statically.
- Whether the chosen build system matches the upstream build recipe, and
  whether the `%buildsystem_<name>_*` macros exist in the build root, both
  need build-time information and are out of scope.
- The stage tags `%prep -a` and `%conf -p` are section annotations rather
  than fields, so they are not inspected. `BuildOption` syntax is owned by
  the supplement and is not duplicated here.
- A block that writes no source declaration is not reported for S5, and a
  block that writes neither `BuildArch` nor `BuildRequires` is not reported
  for S6: each clause constrains the relative position of two present
  fields.
- The first `BuildRequires` line closes the S6 window, because the field is
  commonly repeated once per dependency.
- A misspelled field still feeds S2 to S6, so one defect does not hide
  another.
- `%package` opens a fresh field block: a subpackage writes its own
  window and is not a duplicate of the main preamble.
- No network access and no `rpm` invocation is performed, so the rule works
  on a bare checkout.

## Examples

Passing spec:

```spec
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
Source0:        https://example.org/foo-%{version}.tar.gz
BuildArch:      noarch
BuildSystem:    autotools

BuildRequires:  gcc
```

Misspelled field:

```text
foo.spec: BuildSystem field (line 9) is spelled "Buildsystem"; write "BuildSystem"
```

Empty value:

```text
foo.spec: BuildSystem field (line 9) is empty
```

Value is not a single name:

```text
foo.spec: BuildSystem "autotools cmake" (line 9) is not a single bare build system name; write one lowercase token such as "autotools" or "cmake"
```

Value is a macro reference:

```text
foo.spec: BuildSystem "%{build_system}" (line 9) uses a macro reference; write one literal lowercase build system name such as "autotools" or "cmake"
```

Duplicate declaration:

```text
foo.spec: BuildSystem field block declares the field 2 times (lines 9, 12); keep one declaration
```

Position before the last source declaration:

```text
foo.spec: BuildSystem (line 7) must be written after the last source declaration (line 9)
```

Position before `BuildArch`:

```text
foo.spec: BuildSystem (line 8) must be written after BuildArch (line 9)
```

Position after `BuildRequires`:

```text
foo.spec: BuildSystem (line 11) must be written before BuildRequires (line 10)
```

## Corpus result

Scanning all 6341 spec files of the openRuyi `SPECS` tree at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d` yields 13 findings in 12 files.

| File | Checkpoint | Finding |
| --- | --- | --- |
| `dejagnu/dejagnu.spec` | S1 | line 23 is spelled `Buildsystem` |
| `ed/ed.spec` | S1 | line 17 is spelled `Buildsystem` |
| `go-github-rcrowley-go-metrics/go-github-rcrowley-go-metrics.spec` | S4 | lines 23 and 28 declare the field twice |
| `go-github-rcrowley-go-metrics/go-github-rcrowley-go-metrics.spec` | S6 | line 28 sits after `BuildRequires` at line 25 |
| `go-opentelemetry-contrib/go-opentelemetry-contrib.spec` | S5 | line 24 sits before the last source at line 34 |
| `grep/grep.spec` | S1 | line 19 is spelled `Buildsystem` |
| `libffi/libffi.spec` | S1 | line 17 is spelled `Buildsystem` |
| `libtool/libtool.spec` | S1 | line 17 is spelled `Buildsystem` |
| `lzip/lzip.spec` | S1 | line 17 is spelled `Buildsystem` |
| `mkosi/mkosi.spec` | S6 | line 23 sits after `BuildRequires` at line 19 |
| `mpfr/mpfr.spec` | S1 | line 19 is spelled `Buildsystem` |
| `pkgconf/pkgconf.spec` | S1 | line 39 is spelled `Buildsystem` |
| `zstd/zstd.spec` | S1 | line 19 is spelled `Buildsystem` |

No finding was produced for S2 or S3: every spec that writes the field also
gives it one in-range name.
