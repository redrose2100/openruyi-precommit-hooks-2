# check-spec-requires

Report the `Requires` field of an openRuyi spec file that does not match the
shape, the position or the main-package pin that the packaging guidelines
require.

## Original Requirement

### Source A: the Requires section

The packaging guidelines define `Requires` in six clauses:

1. A static `Requires` must be written one dependency package per line.
2. A `Requires` declaration should name a package that the software genuinely
   needs, rather than a package that merely happens to be installed alongside
   it.
3. The runtime dependency set should be complete: a program that fails at
   runtime without a package must declare that package.
4. When a dependency is only needed during a scriptlet phase, the field should
   carry the phase as a qualifier, as in `Requires(post):` or `Requires(pre):`,
   rather than inflating the runtime set.
5. A package that renames or splits its payload should record the transition
   through `Provides` and `Obsoletes`, so that an upgrade path survives.
6. A `Conflicts` declaration should be justified by a real incompatibility
   rather than used as a crude way to control the transaction.

### Source B: the SplitPackage sub-page

The sub-page adds the pinning rules that a subpackage has to follow when it
depends on its own main package. A subpackage should depend on the main package
with an exact version and release pin, and that pin should carry `%{?_isa}` so
that the subpackage is bound to the architecture of the main package it was
built against. The recommended spelling is:

```
Requires:       %{name}%{?_isa} = %{version}-%{release}
```

The sub-page also asks the packager to filter the runtime dependencies that an
automatic generator emits for a private `.so` file, because such a dependency
names a library that no other package should link against.

### Source C: the layout section and the base field order

The layout section states that `BuildRequires` and `Requires` must both use the
one-dependency-per-line form, which repeats clause 1. The base field section
lists the relative order of the optional fields as:

```
Name: Version: Release: Summary: License: URL: VCS: Source: BuildArch:
BuildSystem: Patch: BuildOption: BuildRequires: Provides: Conflicts:
Obsoletes: Recommends: Requires: Supplements: %description
```

so `Requires` sits after `Recommends` and before `Supplements`. The same
relative order applies inside each subpackage definition, and a subpackage only
needs the fields that apply to it.

The order list is a SHOULD-level statement: the section says that fields
present in a spec should appear in that relative order, and that a spec which
omits a conditional field does not need to reserve its place.

## Strength summary

| Check | Guideline strength | Note |
| --- | --- | --- |
| S1 spelling | MUST | the field name is what every other clause is written against |
| S2 non-empty value | MUST | an empty field declares no dependency |
| S3 one dependency per line | MUST | clause 1 and the layout section |
| S4 no repeated clause | stricter than the letter | a repeated clause adds no constraint |
| S5 field position | SHOULD | the base field order and the layout section |
| S6 inside the field block | SHOULD | follows S5 |
| S7 subpackage pins the main package | SHOULD | the SplitPackage sub-page |
| S8 the pin carries `%{?_isa}` | SHOULD | the SplitPackage sub-page |

## Flags

| Flag | Disables |
| --- | --- |
| `--no-check-field-case` | S1 |
| `--no-check-value` | S2 |
| `--no-check-one-per-line` | S3 |
| `--no-check-duplicate` | S4 |
| `--no-check-position` | S5 and S6 |
| `--no-check-main-pin` | S7 |
| `--no-check-main-isa` | S8 |

## Checkpoints

### S1: the field is spelled `Requires`

A field name that differs from `Requires` only in case, in the plural, or in a
hyphen is reported with the spelling that the spec used and with the expected
spelling. `BuildRequires` shares a suffix with the field but is anchored out of
the match, so a build dependency is never read as a runtime dependency.

### S2: the field declares at least one dependency

`Requires:` with no value is reported. An absent field is never a finding,
because a package may legitimately need nothing at runtime.

### S3: one field line declares exactly one dependency

A line that declares several dependencies is reported with the number of
dependencies that it declares. The count uses a dependency-clause tokenizer, so
the following all count as one dependency:

- `pkgconfig(zlib) >= 1.2.11` - a name, an operator and a version;
- `%{name}%{?_isa} = %{version}-%{release}` - the pinned main package;
- `%{name}%{?_isa} == %{version}-%{release}` - the same pin with the `==`
  operator that some specs use;
- `(python3dist(foo) if python3dist(bar))` - one rich dependency;
- `foo with bar` - two names joined into one clause by `with` / `without`.

`gawk tar` counts as two dependencies, which is the finding.

### S4: one field block declares each clause at most once

The comparison key is the scriptlet stage together with the whole normalized
clause. The stage belongs to the key because the two spellings are different
statements, and a spec that installs a package for the scriptlet phase only
writes both on purpose:

```
Requires:       coreutils
Requires(post): coreutils
```

The whole clause belongs to the key because one dependency bounded from both
sides is a version interval written as two lines:

```
Requires:       openssl-libs >= 3.0
Requires:       openssl-libs < 4.0
```

Only a clause that is literally repeated is reported, because such a line adds
no constraint at all. The comparison is per block, so the same dependency may
appear in the main package and in a subpackage.

A block that contains a conditional branch is exempt, because a field may
legitimately exist on one branch only.

### S5: the field sits between `Recommends` and `Supplements`

The field is reported when its first line precedes the last `Recommends` line of
the block, or when its last line follows the first `Supplements` line of the
block. The window opens on the first line of the field and closes on its last,
because the field is normally repeated once per dependency.

A boundary that the block never writes is not reported. The order table
constrains the relative position of two fields that are both present, so a spec
that writes neither is silent.

The window is the adjacent pair of the order table rather than its whole
left-hand side, and the reason is a measurement of the openRuyi repository.
The order table also places `Requires` after `Provides`, `Conflicts` and
`Obsoletes`, but 10151 of the 10962 blocks that write both `Requires` and
`Provides` - 2194 files - put `Requires` first, and 8309 of those open a
subpackage with `Summary` and then `Requires` before `Provides`. The repository
therefore departs from the documented order for that pair as a matter of
convention, and a per-file rule would fire on about a third of the corpus,
which is a repository-level migration decision rather than something a commit
hook should block on. The `Recommends` and `Supplements` pairs show the opposite
picture: 87 blocks write `Recommends` and 72 of them order it wrongly, and 18
blocks write `Supplements` and 2 of them order it wrongly. That is the outlier
shape a hook is meant to catch, so the rule reports those.

### S6: the field sits inside the header field block

A `Requires` line below the first body section belongs to no field block, so the
order table cannot describe it. A `Requires` inside a `%package` block is inside
a block and is not reported. The walk skips a multi-line macro definition whole,
and it also skips a here-document body, because both can contain field-shaped
lines that belong to the macro or to a generated file rather than to the spec:

```
%global bundled_requires %{expand:
Requires:       bundled(zlib)
}
```

```
cat > demo.pc << EOF
Requires:       zlib
EOF
```

### S7: a subpackage pins the main package to its version and release

A `Requires` line inside a `%package` block that names the main package is
reported unless the clause pins both the version and the release. The main
package name is read from the `Name` field, and the `%{name}` macro is
recognised as the main package as well. A subpackage name such as
`%{name}-devel` names a different package and is never reported.

The release is part of the pin because dropping it lets a rebuild pair a
subpackage with a runtime library from an earlier build, which is exactly the
mismatch the sub-page wants to avoid.

The main block is exempt, because the main package cannot depend on itself.

### S8: that pin names the architecture through `%{?_isa}`

A clause that pins the main package correctly but omits `%{?_isa}` is reported
with the recommended spelling. A clause that already fails S7 is skipped,
because a clause that pins nothing has to be rewritten anyway and reporting the
same line twice tells the packager nothing new.

A spec that declares `BuildArch: noarch` is exempt, because `%{?_isa}` expands
to nothing there and the suffix would be dead text rather than an architecture
constraint.

### Scope notes

Clauses 3 and 5 are out of scope. Clause 3 needs the package metadata or the
installed payload to know what the software needs at runtime, so the rule never
reports a missing runtime dependency. Clause 5 needs the history of a rename or
a split, so the rule never asks for a `Provides` or an `Obsoletes`.

Clause 6 asks for a judgement about whether a `Conflicts` is justified, which no
static rule can make.

The sub-page's advice to filter a `Provides` or a `Requires` that an automatic
generator emits for a private `.so` is out of scope as well, because it needs
the file list of the built package and the generator output.

The sibling fields `Provides`, `Conflicts`, `Obsoletes`, `Recommends` and
`Supplements` are only ever read as position boundaries, so the rule says
nothing about their own spelling, shape or duplicates.

The rule performs no network access and invokes no `rpm`, so it works on a bare
checkout.

## Examples

### A clean spec

```
Recommends:     demo-docs
Requires:       coreutils
Requires:       pkgconfig(openssl) >= 3.0
```

### S3: several dependencies on one line

```
Requires:       gawk tar
```

```
demo.spec: Requires (line 60) declares 2 dependencies; write one dependency per line
```

### S4: a repeated clause

```
Requires:       coreutils
Requires:       gawk
Requires:       coreutils
```

```
demo.spec: Requires "coreutils" (line 30) is already declared at line 20; remove the duplicate
```

### S5: written before `Recommends`

```
Requires:       ceph-common

Recommends:     kubernetes
```

```
demo.spec: Requires (line 20) must be written after Recommends (line 22); write the fields in the order Recommends -> Requires -> Supplements
```

### S6: written below the first section

```
%description
A demo package.
Requires:       zlib-devel
```

```
demo.spec: Requires (line 14) is written outside the header field block; write it before the first section
```

### S7: a subpackage that does not pin the main package

```
%package        devel
Summary:        Development files
Requires:       demo
```

```
demo.spec: Requires "demo" (line 13) does not pin the main package to its version and release; write "Requires: %{name}%{?_isa} = %{version}-%{release}"
```

### S8: a pin without the architecture suffix

```
Requires:       %{name} = %{version}-%{release}
```

```
demo.spec: Requires "%{name} = %{version}-%{release}" (line 67) does not constrain the architecture of the main package; write "Requires: %{name}%{?_isa} = %{version}-%{release}"
```
