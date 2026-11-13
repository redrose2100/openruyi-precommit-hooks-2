# check-spec-buildarch

> Rule ID: `check-spec-buildarch`

## Original Requirement

Source: [openRuyi Packaging Specification · BuildArch (optional)](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/#buildarch-optional)

The `BuildArch` field is optional: it is written only by a package that is
built for one architecture regardless of the build host, most commonly
`noarch`. The requirement therefore covers three things — where the field is
placed, how it is spelled and valued, and whether the rest of the block
contradicts the architecture it declares. Every other field is out of scope.

### BuildArch

- The field is written in the preamble of the package block that owns it, so
  a `%package` subpackage may carry its own declaration.
- It is written after the last source declaration of that block, so that the
  build system knows what input it is describing.
- It is written before `BuildSystem`, so that the chosen build system is
  configured for the declared architecture.
- The value is a single bare architecture name, written in lower case, such
  as `noarch`, `x86_64` or `aarch64`. A macro may be used when the
  architecture is decided at build time.
- When the value is `noarch`, the block must not derive an installed path from
  the build host's architecture.

## Checkpoints

| # | Checkpoint | Requirement | Failure condition | Flag | Default |
| --- | --- | --- | --- | --- | --- |
| 1 | Field name spelling | The field is spelled `BuildArch` | `BUildArch`, `Buildarch`, `buildarch`, `BuildArchs`, ... | `--no-check-field-case` | on |
| 2 | Non-empty value | Every declaration must carry a value | `BuildArch:` with nothing after the colon | — | on |
| 3 | Bare architecture token | The value is one lower-case architecture name or a macro | `x86_64 aarch64`, `Noarch`, `noarch, x86_64`, `noarch/x86_64` | — | on |
| 4 | One declaration per block | A package block declares the field once | Two `BuildArch` lines in the same block | — | on |
| 5 | After the last source | The field is written after the last `Source`/`SourceN`/`%sourcelist` of its block | `BuildArch` above a source declaration | — | on |
| 6 | Before `BuildSystem` | The field is written before `BuildSystem` | `BuildArch` below `BuildSystem` | — | on |
| 7 | Noarch contradiction | A `noarch` block must not key an installed path off the build host | A `%{_libdir}`, `%{_lib}`, `%{_lib64}`, `%{_arch}`, `%{_target_cpu}`, `%{_host_cpu}` or `%{_target_platform}` occurrence in the field region | `--no-check-noarch` | on |

### Scope notes

Every clause below is a real part of the specification that this rule
deliberately does not enforce, or a decision about how the checkpoints above
behave.

- **The field is optional, so writing no `BuildArch` is never a finding.**
  6204 of the 6341 corpus specs omit it; the rule stays silent for all of
  them.

- **Checkpoints 5 and 6 are silent when the boundary does not exist.** A
  data-only package has no source declaration and no `BuildSystem`, so the
  position clause cannot be decided. 44 corpus specs carry `BuildArch` with no
  source at all and remain silent.

- **A subpackage block restarts the field model.** A `%package` section opens
  a new block, so its own `BuildArch` is a fresh declaration rather than a
  duplicate, and its position is judged against its own source declarations.
  137 corpus blocks carry `BuildArch`; none of them declares it twice.

- **`%sourcelist` is treated as a source declaration.** It is a macro, not a
  field, so it never appears in the field list; the block's lines are scanned
  for it separately and folded into the "last source declaration" position.

- **A macro value is accepted without inspection.** `%{buildarch}` and
  `%{?go_arch}%{!?go_arch:noarch}` are resolved by the build system, so the
  rule cannot know the architecture and does not guess. This is the same
  policy `check-spec-url` applies to macro-valued URLs.

- **Checkpoint 7 reads the field region only, not the whole block.** The
  region runs from the block's first field to the next section. An earlier
  measurement over every line of the block reported 30 findings in 22 specs,
  but collapsed to 0 because a `%if "%{_host_cpu}" == "riscv64"` guard above
  the first field is a legitimate build-time switch. Narrowing the region to
  the fields left 11 findings in 11 specs, which is the shipped behaviour.

- **`%{?_isa}` never counts as architecture evidence.** The conditional form
  expands to nothing on a `noarch` build, so
  `Provides: %{name}%{?_isa} = %{version}-%{release}` is the standard idiom
  and must stay silent. Including it produced 15 findings in 12 specs of
  which 4 were this idiom.

- **`%files` bodies are out of scope.** A `%files` path such as
  `%{_libdir}/cmake/cereal` belongs to the owning package, not to the field
  region, and 4 corpus specs use it legitimately. Checkpoint 7 never looks at
  `%files`.

- **Section detection uses a closed whitelist.** A bare `^%([a-z]\w*)\b`
  pattern also matches `%global`, `%autosetup` and `%python_provide`, which
  would truncate the field region early and hide real declarations. Only the
  22 known section names end a field region.

- **Whether a non-`noarch` value is a real RPM architecture stays out of
  scope.** The rule checks the shape of the token, not a list of valid
  architectures, because the supported set grows with each RPM release.

## Examples

### Field written before its source (checkpoint 5)

```spec
Source0:        https://example.org/foo-1.0.tar.gz
BuildArch:      noarch
Source1:        foo.conf
```

```
x.spec: BuildArch (line 5) must be written after the last source
declaration (line 6)
```

### Corrected

```spec
Source0:        https://example.org/foo-1.0.tar.gz
Source1:        foo.conf
BuildArch:      noarch
```

### Field written after `BuildSystem` (checkpoint 6)

```spec
BuildSystem:    autotools
BuildArch:      noarch
```

```
x.spec: BuildArch (line 5) must be written before BuildSystem (line 4)
```

### Corrected

```spec
BuildArch:      noarch
BuildSystem:    autotools
```

### `noarch` keyed off the library directory (checkpoint 7)

```spec
BuildArch:      noarch
BuildSystem:    autotools
BuildOption(install):  libdir=%{_libdir}
```

```
x.spec: BuildArch "noarch" (line 4) declares an architecture independent
package, but line 6 uses "%{_libdir}"
```

### Corrected

```spec
BuildArch:      noarch
BuildSystem:    autotools
```

### Not a finding: the conditional isa idiom

```spec
BuildArch:      noarch
Provides:       %{name}%{?_isa} = %{version}-%{release}
```

`%{?_isa}` expands to nothing on a `noarch` build, so this shape is correct.

### Not a finding: a `%files` library path

```spec
BuildArch:      noarch
BuildSystem:    cmake

%files
%{_libdir}/cmake/foo
```

The `%files` body is not part of the field region.

### Multiple values (checkpoint 3)

```spec
BuildArch:      noarch, x86_64
```

```
x.spec: BuildArch "noarch, x86_64" (line 4) is not a bare architecture
token; write one lowercase architecture name such as "noarch" or "x86_64"
```

### Misspelled field (checkpoint 1)

```spec
BUildArch:      noarch
```

```
x.spec: BuildArch field (line 4) is spelled "BUildArch"; write "BuildArch"
```

## Corpus result

Running the rule over the 6341 specs of
`openRuyi-Project/openRuyi` at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d` reports **11 findings in 11
specs**.

| Checkpoint | Findings | Affected shape |
| --- | --- | --- |
| 5 After the last source | 9 | `BuildArch` written above the `SourceN` list |
| 1 Field name spelling | 1 | `go-github-wcharczuk-go-chart` writes `BUildArch` |
| 7 Noarch contradiction | 1 | `hwdata` sets `libdir=%{_libdir}` in a `noarch` block |

Checkpoints 2, 3, 4 and 6 report nothing on the corpus: the packagers write
one well-formed value, spell the field correctly in all but one spec, and
always place it above `BuildSystem`. All 11 findings are also reported with
`--no-check-field-case --no-check-noarch`, so no finding is stylistic.

The nine position findings, with the field line and the last source line:

| Spec | `BuildArch` | Last source |
| --- | --- | --- |
| `SPECS/calico/calico.spec` | 13 | 19 |
| `SPECS/go-opentelemetry-contrib/go-opentelemetry-contrib.spec` | 23 | 34 |
| `SPECS/openruyi-config-linux-dnf/openruyi-config-linux-dnf.spec` | 13 | 19 |
| `SPECS/openruyi-desktop-setup-kde/openruyi-desktop-setup-kde.spec` | 12 | 16 |
| `SPECS/openruyi-desktop-setup-labwc/openruyi-desktop-setup-labwc.spec` | 12 | 15 |
| `SPECS/openruyi-linux-build/openruyi-linux-build.spec` | 13 | 49 |
| `SPECS/openruyi-systemd-default-preset/openruyi-systemd-default-preset.spec` | 12 | 17 |
| `SPECS/rpm-config-openruyi/rpm-config-openruyi.spec` | 18 | 27 |
| `SPECS/u-boot-menu-ng/u-boot-menu-ng.spec` | 12 | 16 |
