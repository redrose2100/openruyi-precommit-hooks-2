# check-spec-buildrequires

Report the `BuildRequires` field of an openRuyi spec file that does not match
the shape, the position or the `pkgconfig(...)` spelling that the packaging
guidelines require.

## Original Requirement

### Source A: the BuildRequires section

The packaging guidelines define `BuildRequires` in seven clauses:

1. A spec must ensure that every build-time dependency is declared, through a
   static `BuildRequires` field, through the dynamic build dependency
   generator, or through both.
2. When the package uses the dynamic generator, the static field must still
   hold the dependencies needed to run the generator plus any other necessary
   build dependency that the generator cannot produce.
3. When the base build environment and the generated dependencies are enough,
   the static field may be omitted; a C program, for instance, usually does not
   declare `gcc`.
4. A static `BuildRequires` must be written one dependency package per line.
5. The openRuyi base build environment is the set of packages that the build
   configuration guarantees before the build starts, and the preinstall image
   is the authority for that set.
6. A spec must not omit a necessary build dependency just because that
   dependency happens to exist in the current build root.
7. When a dependency is discovered through `pkg-config`, `BuildRequires`
   should declare it as `pkgconfig(xxx)` rather than depend on `xxx-devel`
   directly.

### Source B: the PkgConfigBuildRequires sub-page

The sub-page elaborates clause 7. A declaration should name the pkg-config
module rather than the development package, so that the dependency tracks the
module across a package rename, and its example contrasts the recommended
`pkgconfig(openssl)` with the discouraged `openssl-devel`.

### Source C: the layout section and the base field order

The layout section states that `BuildRequires` and `Requires` must both use the
one-dependency-per-line form, which repeats clause 4 and extends it to the
runtime field. The base field section lists the relative order of the optional
fields as:

```
Name: Version: Release: Summary: License: URL: VCS: Source: BuildArch:
BuildSystem: Patch: BuildOption: BuildRequires: Provides: Conflicts:
Obsoletes: Recommends: Requires: Supplements: %description
```

so `BuildRequires` sits after `BuildSystem`, `Patch` and `BuildOption`, and
before `Provides`. The same relative order applies inside each subpackage
definition, and a subpackage only needs the fields that apply to it.

The order list is a SHOULD-level statement: the section says that fields
present in a spec should appear in that relative order, and that a spec which
omits a conditional field does not need to reserve its place.

### Strength summary

| Check | Guideline strength | Note |
| --- | --- | --- |
| R1 spelling | MUST | the field name is what every other clause is written against |
| R2 non-empty value | MUST | an empty field declares no dependency |
| R3 one dependency per line | MUST | clause 4 and the layout section |
| R4 no repeated clause | stricter than the letter | a repeated clause adds no constraint |
| R5 field position | SHOULD | the base field order and the layout section |
| R6 inside the field block | SHOULD | follows R5 |
| R7 pkgconfig module shape | SHOULD | the statically decidable part of clause 7 |

## Flags

| Flag | Disables |
| --- | --- |
| `--no-check-field-case` | R1 |
| `--no-check-value` | R2 |
| `--no-check-one-per-line` | R3 |
| `--no-check-duplicate` | R4 |
| `--no-check-position` | R5 and R6 |
| `--no-check-pkgconfig` | R7 |

## Checkpoints

### R1: the field is spelled `BuildRequires`

A field name that differs from `BuildRequires` only in case, in the plural, or
in a hyphen is reported with the spelling that the spec used and with the
expected spelling. A name that shares none of those shapes is indistinguishable
from a different field and is left alone.

### R2: the field declares at least one dependency

`BuildRequires:` with no value is reported. An absent field is never a finding,
because clause 3 makes the field optional.

### R3: one field line declares exactly one dependency

A line that declares several dependencies is reported with the number of
dependencies that it declares. The count uses a dependency-clause tokenizer, so
the following all count as one dependency:

- `pkgconfig(zlib) >= 1.2.11` - a name, an operator and a version;
- `crate(arc-swap-1/default) >= 1.9.1` - a name with a slash and a version;
- `(python3dist(foo) if python3dist(bar))` - one rich dependency;
- `foo with bar` - two names joined into one clause by `with` / `without`.

`libXaw-devel, libXmu-devel` counts as two dependencies, which is the finding.

### R4: one field block declares each dependency clause at most once

The comparison key is the whole normalized clause rather than the bare name.
One dependency bounded from both sides is a version interval and is written as
two lines, so comparing names would report every interval:

```
BuildRequires:  python3dist(dill) >= 0.3
BuildRequires:  python3dist(dill) < 0.4.2
```

Only a clause that is literally repeated is reported, because such a line adds
no constraint at all. The comparison is per block, so the same dependency may
appear in the main package and in a subpackage.

A block that contains a conditional branch is exempt, because a field may
legitimately exist on one branch only.

### R5: the field sits after the builders and before `Provides`

The field is reported when its first line precedes the last
`BuildSystem` or `BuildOption` line of the block, or when its last line follows
the first `Provides` line of the block. The window opens on the first line of
the field and closes on its last, because the field is normally repeated once
per dependency. `Patch` is not used as a boundary: the guidelines place it
before `BuildOption` and before `BuildRequires`, so it constrains neither.

A boundary that the block never writes is not reported. The order table
constrains the relative position of two fields that are both present, so a
spec that writes neither is silent.

### R6: the field sits inside the header field block

A `BuildRequires` line below the first body section belongs to no field block,
so the order table cannot describe it. A `BuildRequires` inside a `%package`
block is inside a block and is not reported. The walk skips a multi-line macro
definition whole, because such a body can contain field-shaped lines that belong
to the macro rather than to the spec:

```
%global bundled_provides %{expand:
BuildRequires:  bundled(zlib)
}
```

### R7: a `pkgconfig(...)` declaration names a bare module

Three shapes are reported:

- an empty module, as in `pkgconfig()`;
- a module with padding inside the parentheses, as in `pkgconfig( openssl )`;
- a module that ends with `-devel`, as in `pkgconfig(openssl-devel)`.

Case is not checked. A module name such as `pkgconfig(Qt6Core)` is a literal
module name and is left alone.

### Scope notes

Clauses 1, 2, 5 and 6 are out of scope. Each one needs information that a
single spec file does not carry: the preinstall image manifest, the build
configuration, the generator output or the contents of the current build root.
The rule never reports a missing dependency, because doing so would need that
information.

Clause 3 makes the field optional, so an absent field is never a finding.

Clause 7 as a whole asks whether the upstream build recipe uses `pkg-config`,
which needs the upstream sources. The rule therefore never asks a packager to
convert a stand-alone `-devel` declaration; it only checks the shape of a
`pkgconfig(...)` declaration that the spec already writes.

Two tempting checks are deliberately out of scope as well.

The first would report a `-devel` package that the same block already requires
through `pkgconfig(...)`. That would be wrong, because the two forms are not
interchangeable: `python3-devel` ships build macros and headers that
`pkgconfig(python3)` does not, and the repository contains specs that
legitimately declare both.

The second would report every `-devel` declaration whose name looks like a
pkg-config module. That would be wrong for the same reason, and it would also
need repository metadata to know which module each package ships.

The rule performs no network access and invokes no `rpm`, so it works on a bare
checkout.

## Examples

### A clean spec

```
BuildSystem:    autotools
BuildOption(build):  %{?_smp_mflags}
BuildRequires:  pkgconfig(openssl) >= 3.0
BuildRequires:  python3dist(pytest)
Provides:       demo-libs = %{version}-%{release}
```

### R3: several dependencies on one line

```
BuildRequires:  libXaw-devel, libXmu-devel
```

```
demo.spec: BuildRequires (line 93) declares 2 dependencies; write one dependency per line
```

### R4: a repeated clause

```
BuildRequires:  pkgconfig(libelf)
BuildRequires:  pkgconfig(zlib)
BuildRequires:  pkgconfig(libelf)
```

```
demo.spec: BuildRequires "pkgconfig(libelf)" (line 39) is already declared at line 23; remove the duplicate
```

### R5: written before `BuildOption`

```
BuildSystem:    autotools

BuildRequires:  pkgconfig(libmd)

BuildOption(conf):  --disable-static
```

```
demo.spec: BuildRequires (line 22) must be written after BuildOption (line 24); write the fields in the order BuildSystem -> BuildOption -> BuildRequires -> Provides
```

### R6: written below the first section

```
%description
A demo package.
BuildRequires:  zlib-devel
```

```
demo.spec: BuildRequires (line 12) is written outside the header field block; write it before the first section
```

### R7: a development package named as a module

```
BuildRequires:  pkgconfig(openssl-devel)
```

```
demo.spec: pkgconfig module "openssl-devel" (line 11) ends with "-devel"; write the pkg-config module name
```
