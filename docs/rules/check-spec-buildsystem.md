# check-spec-buildsystem

## Original Requirement

The six checkpoints of this rule do **not** all come from the
`#buildsystem` section. That section only governs the field's value. The
three order and duplication checkpoints are derived from three other
places in the guidelines, and they rest on the weaker SHOULD strength
rather than the MUST / MUST NOT strength. Each is listed separately below
so the provenance is unambiguous.

### Source A — `#buildsystem` (value clauses, MUST level)

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

Clauses 1 to 4 use the MUST / MUST NOT wording, so S2 and S3 enforce the
hard requirements of this field.

### Source B — base field section relative order (SHOULD level)

Source: the base field section of the same page, specifically its
"relative order" list of base fields.

The base field section lists the relative order that fields should follow
when they are present:

> When the following fields are present they should appear in this
> relative order: Name, Version, Release, Summary, License, URL, VCS,
> Source, BuildArch, BuildSystem, Patch, BuildOption, BuildRequires, ...

and it defines what counts as one source declaration:

> The numbered forms Source, Source0 and Source1 are the same position, and
> the equivalent `%sourcelist` form also belongs to the source declaration
> block.

The wording is SHOULD, not MUST. From this list the rule derives:

- S5 — `BuildSystem` comes after the source declaration block, so it
  should indeed sit after the **last** `Source` / `SourceN` /
  `%sourcelist` of its block.
- The `BuildSystem` before `BuildRequires` half of S6.

### Source C — `BuildArch` section (SHOULD level)

Source: the optional `BuildArch` subsection of the base field section.

> The BuildArch field should appear between the last Source field and the
> BuildSystem field.

Also SHOULD. From this sentence the rule derives the `BuildSystem` after
`BuildArch` half of S6.

### Source D — supplement `BuildSystems` (advisory wording)

Source: <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/BuildSystems>

> In the simplest case the spec file only needs to contain one build
> system declaration field, for example `BuildSystem: autotools`.

The sentence says "only needs", which is advisory and does not spell out a
rule for duplicate declarations. S4 is therefore the weakest checkpoint of
the six, justified only by this sentence plus the general principle that
one field carries one value.

### Strength summary

| Checkpoint | Source | Guideline strength |
| --- | --- | --- |
| S2 value present | A clause 3 | MUST NOT |
| S3 value is a supported name | A clause 4 | MUST |
| S1 spelling | A section title and usage | implied, no explicit clause |
| S4 at most one declaration | D | advisory ("only needs") |
| S5 after the last source | B | SHOULD |
| S6 after `BuildArch`, before `BuildRequires` | B and C | SHOULD |

S1, S4, S5 and S6 are therefore stricter than a literal reading of the
guidelines. They stay enabled by default because a misspelled field name, a
duplicated declaration and a misplaced field are all concrete defects in
the spec that ships, and the corpus shows that every project writing the
field out of order was editing that block anyway, so the fixes are local.

A team that wants only the hard requirements can opt out of part of this:

| Flag | Disables |
| --- | --- |
| `--no-check-field-case` | S1 |
| `--no-check-value` | S2 and S3 |
| `--no-check-position` | S5 and S6 |

S4 has no opt-out flag, because a duplicated declaration is a data-integrity
problem rather than a style choice and it is the cheapest of the six checks
to satisfy.

## Checkpoints

| ID | Checkpoint | Source | Strength |
| --- | --- | --- | --- |
| S1 | The field is spelled `BuildSystem` | A (implied) | error |
| S2 | The value is present | A clause 3 | error |
| S3 | The value is one literal lowercase build system name | A clause 4 | error |
| S4 | A field block declares the field at most once | D | error |
| S5 | The field sits after the last source declaration of its block | B | error |
| S6 | The field sits after `BuildArch` and before `BuildRequires` | B and C | error |

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
