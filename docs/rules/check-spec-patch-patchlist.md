# check-spec-patch-patchlist

## Original Requirement

The patch policy is documented in two places, not one. The main guidelines
have a `Patch and %patchlist (optional)` section, and a dedicated `Patch`
supplement page repeats most of it and adds the placement sentence. The six
checkpoints of this rule come from those two pages and from the base field
relative order list, and they rest on three different strength levels.
Each source is listed separately below so the provenance of every
checkpoint is unambiguous.

### Source A — main guidelines, `Patch and %patchlist` (optional section)

Source: <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#patch-and-patchlist-%E5%8F%AF%E9%80%89>

**Clause 1 — a comment above every patch.** The wording is SHOULD level
("should have"):

> Every patch referenced in a spec file should have one line of comment
> above it. That line may state what the patch does, or it may be the
> upstream link.

**Clause 2 — the four digit file name prefix.** The wording presents this
as the naming policy, so the rule treats it as MUST level:

> Every patch file should start with four digits, and those four digits
> represent the patch type: `0001`-`0999` for patches taken from the same
> upstream version, `1000`-`1999` for CVE fixes and backports from other
> upstream versions, `2000`-`2999` for patches specific to openRuyi,
> patches not yet submitted upstream, and patches submitted but not yet
> accepted upstream.

**Clause 3 — `%patchlist`.** This single sentence carries two different
strengths: the threshold is advisory wording ("it is not appropriate"),
while the position is a hard requirement ("must be placed"):

> If there are more than 3 patches, it is not appropriate to use the
> `Patch` field, and `%patchlist` may be defined directly. If `%patchlist`
> is defined, the list must be placed above `%description`.

### Source B — supplement `Patch` page

Source: <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/Patch>

- The comment clause is repeated with the same SHOULD wording, and adds
  that a patch submitted upstream should carry a submission comment, for
  example a pull request link, and that a patch is not renamed merely
  because its upstream status changed. That addition is **not** a
  checkpoint of this rule; see the scope notes.
- The four digit ranges are repeated unchanged, so P2 and P3 rest on two
  independent statements of the same policy.
- The supplement is the source of the placement sentence:

  > The `Patch` field should be written above the `BuildOption` field if
  > there is one, or above the `BuildRequires` field.

- The `%patchlist` threshold and position are repeated unchanged.
- Applying patches: the default strip level is `-p1`; `BuildOption(prep)`
  is only used when the default prep stage cannot serve, for example `-p0`;
  a hand-written `%prep` that applies patches manually is only used when
  the declarative fields cannot express the need, and the reason must be
  commented.

### Source C — base field relative order (SHOULD level)

Source: the base field section of the main guidelines page.

> When the following fields are present they should appear in this relative
> order, which includes Source, then BuildArch, then BuildSystem, then
> Patch, then BuildOption, then BuildRequires.

This is the second basis for P6 and the reason the window closes on
`BuildOption` when the spec writes one and on `BuildRequires` otherwise.

### Strength summary

| Checkpoint | Source | Guideline strength |
| --- | --- | --- |
| P2 file name starts with four digits | A clause 2, B | MUST |
| P3 prefix lies in `0001`-`2999` | A clause 2, B | MUST |
| P5 `%patchlist` above `%description` | A clause 3, B | MUST |
| P1 comment above every group | A clause 1, B | SHOULD |
| P6 `Patch` above `BuildOption` / `BuildRequires` | B, C | SHOULD |
| P4 more than three patches imply a list | A clause 3 | advisory |

The rule reports every checkpoint as an error by default. The two advisory
ones (P4 and P1) are the ones a team is most likely to disagree with, so
each has its own opt-out flag:

| Flag | Disables |
| --- | --- |
| `--no-check-comment` | P1 |
| `--no-check-naming` | P2 and P3 |
| `--no-check-patchlist` | P4 and P5 |
| `--no-check-position` | P6 |

## Checkpoints

| ID | Checkpoint | Source | Strength |
| --- | --- | --- | --- |
| P1 | Every patch declaration group has a comment line above it | A clause 1, B | error |
| P2 | Every patch file name starts with four digits | A clause 2, B | error |
| P3 | That four digit prefix lies in `0001`-`2999` | A clause 2, B | error |
| P4 | More than three patches imply a `%patchlist` | A clause 3 | error |
| P5 | `%patchlist` sits above the first `%description` | A clause 3, B | error |
| P6 | `Patch` sits above `BuildOption`, or above `BuildRequires` | B, C | error |

### P1 comment above every declaration group

The unit is a **group**, not a single entry. The supplement sample shows one
comment line followed by a bare file name, and repeats that pattern for the
next group, so a run of adjacent declarations is satisfied by one comment
directly above its first line. Measuring every entry instead would report
147 files on the corpus, while grouping reports 140 and matches the
documented layout.

Two independent runs are checked: contiguous `Patch` / `PatchN` fields, and
contiguous `%patchlist` entries. A group at the top of the file is reported,
because there is no line above it to carry the comment.

**Known limitation.** Clause 1 allows a patch that already explains itself
to skip the comment. Deciding that needs the patch payload and its intent,
so the rule cannot apply the exemption and reports the group anyway. A team
that reviews patches by hand can disable the whole checkpoint with
`--no-check-comment` rather than fight the finding.

### P2 and P3 patch file naming

The two checkpoints are separate because they produce different findings
and a file can satisfy P2 while violating P3: `3000-fix.patch` does start
with four digits, yet its prefix is outside the documented window.

The range boundaries are inclusive: `0001`, `0999`, `1000`, `1999`, `2000`
and `2999` all pass; `0000` and `3000` fail. Only the **first four digits**
are read, so `12345-fix.patch` is compliant and is not treated as a five
digit prefix.

What is skipped, and why:

- A value holding a macro reference, such as `Patch0: %{name}-fix.patch`,
  is skipped because the name only exists at build time.
- A value that does not end in `.patch` or `.diff` is skipped, because it
  does not reference a patch file at all. `Patch0: %{name}.in` is therefore
  silent rather than a naming finding.
- A path in front of the file name is stripped, because the four digit
  prefix belongs to the file name and not to a directory. `Patch0:
  patches/0001-sync-data.patch` is compliant.

The rule does **not** verify that the prefix matches the actual patch type.
Telling a same-version upstream patch from a backport needs the patch
payload and its upstream history.

### P4 more than three patches imply a list

The threshold sentence is advisory, but the corpus honours it almost
everywhere: only 25 files declare more than three patches without a list.
The count includes both `Patch` fields and `%patchlist` entries, and the
finding is reported only when the spec has no `%patchlist` at all. When a
list is present the threshold is already satisfied, so a short list is never
reported.

The comparison is strictly greater than three, so exactly three `Patch`
fields are compliant.

### P5 `%patchlist` above `%description`

The comparison uses the first `%description` in the file, which is the main
package description and the anchor the clause names.

### P6 `Patch` position

The window closes on `BuildOption` when the spec writes one, and on
`BuildRequires` otherwise. A spec that writes neither is silent, because
the clause constrains the position of two present fields.

The **first** `Patch` is compared, because a spec that repeats the field
once per patch satisfies the clause as soon as the earliest one is inside
the window. `BuildOption(prep): -p0` also counts as a `BuildOption`, since
it carries the same field name with a stage argument.

## Scope notes

These are deliberately **not** checkpoints, each because the clause does not
reach it or the judgement is not static:

- Whether a patch is actually applied during `%prep`.
- The correct strip level, `-p1` by default.
- Whether `BuildOption(prep)` or a hand-written `%prep` is justified.
- Whether a patch is truly upstream, a backport or openRuyi specific.
- Whether a submission comment above a patch carries a real pull request
  link. The comment content is not inspected, only its presence.
- Whether a patch is stale against the current upstream version.
- **The `PatchN` index does not have to match the file name prefix.**
  `Patch1: 0001-foo.patch` is intentional in the kernel style and appears
  throughout the corpus, for example in `attr.spec`. Comparing the two would
  produce findings that the guidelines never ask for.

A spec that declares no patch is never reported: every checkpoint is
conditional on a patch being declared.

## Corpus baseline

Scanning 6341 specs of the openRuyi repository at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d` yields 305 findings in 187
files:

| Checkpoint | Files | Occurrences |
| --- | --- | --- |
| P1 | 140 | 143 |
| P2 | 56 | 119 |
| P3 | 2 | 2 |
| P4 | 25 | 25 |
| P5 | 4 | 4 |
| P6 | 12 | 12 |

## Examples

A compliant spec:

```specfile
Source0:        https://example.org/foo-%{version}.tar.gz
BuildSystem:    autotools
# Adjust the tests for the newer setuptools.
Patch0:         0001-adjusts-tests-for-setuptools.patch
BuildRequires:  gcc

%description
An example package.
```

A compliant list, placed above `%description`:

```specfile
%patchlist
# Import fixes from the upstream maintenance branch.
0001-import-upstream-maintenance-fixes.patch
0002-import-upstream-maintenance-fixes.patch
# Local change, not intended for upstream.
2001-disable-optional-feature.patch

%description
An example package.
```

Findings look like this:

```text
foo.spec: patch declaration (line 7) has no comment line above it; add one line describing the patch or giving the upstream link
foo.spec: patch file "foo-1.0-endian.patch" (line 11) does not start with four digits; prefix it with 0001-0999 for a patch from the same upstream version, 1000-1999 for a CVE fix or a backport from another upstream version, 2000-2999 for an openRuyi specific patch
foo.spec: patch file "3000-fix.patch" (line 11) starts with a prefix outside 0001-2999; use 0001-0999 for a patch from the same upstream version, 1000-1999 for a CVE fix or a backport from another upstream version, 2000-2999 for an openRuyi specific patch
foo.spec: 4 patches are declared but the spec uses no %patchlist; use %patchlist above %description instead of more than 3 Patch fields
foo.spec: %patchlist (line 15) must be written above %description (line 12)
foo.spec: Patch (line 12) must be written above BuildOption (line 10)
foo.spec: Patch (line 12) must be written above BuildRequires (line 10)
```

## Flags

| Flag | Disables | Checkpoint strength |
| --- | --- | --- |
| `--no-check-comment` | P1 | SHOULD |
| `--no-check-naming` | P2 and P3 | MUST |
| `--no-check-patchlist` | P4 and P5 | advisory and MUST |
| `--no-check-position` | P6 | SHOULD |

`--no-check-patchlist` deliberately covers two checkpoints of different
strength, because both are governed by the same clause 3 sentence and a
team that wants to keep the hard position rule has no reason to lose it.
