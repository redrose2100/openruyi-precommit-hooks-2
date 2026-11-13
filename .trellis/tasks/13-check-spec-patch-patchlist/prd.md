# PRD: check-spec-patch-patchlist rule

## Background

The openRuyi packaging guidelines describe the patch policy in two pages:
the `Patch and %patchlist (optional)` section of the main guidelines and
the dedicated `Patch` supplement page. Together they state where patch
declarations go, how patch files must be named, when `%patchlist` must
replace the single `Patch` field, and that every referenced patch needs an
explanatory comment above it.

The `openruyi-precommit-hooks` project already ships twelve `check-spec-*`
rules, but none of them looks at `Patch`, `PatchN` or `%patchlist`, so every
deviation is only caught by manual review.

## Goal

Add a thirteenth rule, `check-spec-patch-patchlist`, that statically checks
`.spec` files during the pre-commit stage and reports stable, reproducible
messages, then scan the whole openRuyi corpus and publish the findings as a
Feishu document.

## Normative sources

The five checkpoints come from three places with three different strength
levels. They are kept apart so the provenance of each one is unambiguous.

### Source A — main guidelines, `#patch-and-patchlist-optional`

Source: <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#patch-and-patchlist-%E5%8F%AF%E9%80%89>

Clause 1, comment above every patch (SHOULD level, the wording is
"should have"):

> Every patch referenced in a spec file should have one line of comment
> above it. That line may state what the patch does or may be the upstream
> link.

Clause 2, patch file naming (MUST level, the wording is "should start with
four digits", presented as a hard naming policy):

> Every patch file should start with four digits, and those four digits
> represent the patch type: 0001-0999 for patches from the same version of
> upstream, 1000-1999 for CVE fixes and backports from other upstream
> versions, 2000-2999 for openRuyi-specific patches, patches not yet
> submitted upstream, and submitted-but-not-yet-accepted patches.

Clause 3, `%patchlist` (advisory for the threshold, MUST for the position):

> If there are more than 3 patches it is not appropriate to use the `Patch`
> field, and `%patchlist` may be defined directly. If `%patchlist` is
> defined, the list must be placed above `%description`.

### Source B — supplement `Patch` page

Source: <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/Patch>

- The comment-above clause is repeated with the same SHOULD wording, and
  adds that a patch submitted upstream should carry a submission comment,
  for example a pull request link, and that a patch is not renamed merely
  because its upstream status changed.
- The four-digit ranges are repeated unchanged.
- Single `Patch` field placement: "The `Patch` field should be written
  above the `BuildOption` field if present, or above the `BuildRequires`
  field."
- `%patchlist` threshold and position are repeated unchanged.
- Applying patches: the default strip level is `-p1`; `BuildOption(prep)`
  is only used when the default prep stage cannot work, for example `-p0`;
  a hand-written `%prep` that applies patches manually is only used when
  the declarative fields cannot express the need, and the reason must be
  commented.

### Source C — base field relative order, SHOULD level

Source: the base field section of the main guidelines.

> When the following fields are present they should appear in this relative
> order, which includes Source, then BuildArch, then BuildSystem, then
> Patch, then BuildOption, then BuildRequires.

This is the second basis for the position checkpoint, and it also gives the
"after `BuildSystem`" half of it.

## Checkpoints

| ID | Checkpoint | Source | Strength |
| --- | --- | --- | --- |
| P1 | Every patch declaration group has a comment line above it | A clause 1, B | SHOULD |
| P2 | Every patch file name starts with four digits | A clause 2, B | MUST |
| P3 | Every patch file name uses a prefix in `0001`-`2999` | A clause 2, B | MUST |
| P4 | More than three patches implies `%patchlist` | A clause 3 | advisory |
| P5 | `%patchlist` sits above the first `%description` | A clause 3, B | MUST |
| P6 | `Patch` sits above `BuildOption` or `BuildRequires` | B, C | SHOULD |

## Design decisions forced by the corpus

- **Comment grouping.** The supplment example shows one comment followed by
  several patch entries, so P1 is evaluated per contiguous run of patch
  declarations: only the first entry of a run needs the comment. Measuring
  every single entry instead would report 147 files, while grouping reports
  140 and matches the documented example.
- **Patch file shape.** Only tokens ending in `.patch` or `.diff` count as
  patch declarations. A `%patchlist` body also ends at the first blank line
  or the first line starting with `%`. Without these two guards the parser
  swallows the multi-line `%global _description %{expand:` macro that often
  follows a `%patchlist`, and reports ordinary English words as patch file
  names.
- **Excluded: patch index versus file name digits.** `Patch1: 0001-x.patch`
  is intentional in the kernel style and appears throughout the corpus, so
  comparing the `PatchN` index with the file name prefix is not a
  checkpoint.
- **Excluded: the "already explained inside the patch" escape hatch.** The
  patch files live next to the spec in the repository, but deciding whether
  a patch explains itself needs semantic judgement, so the rule cannot
  apply that exemption. It is documented as a known limitation and P1 can
  be disabled.

## Explicitly out of scope

- Whether a patch is actually applied during `%prep`.
- The correct strip level `-p1` versus `-p0`.
- Whether `BuildOption(prep)` or a hand-written `%prep` is justified.
- Whether a patch is truly upstream, backported or openRuyi-specific, which
  would require reading the patch payload and its upstream history.
- Whether a patch submission comment contains a real pull request link.
- Whether a patch is stale relative to the current upstream version.

## Corpus baseline

- Scope: every `.spec` under `SPECS` of the openRuyi repository, 6341 files
- Commit: `1bb886cf1dc0dd4932a312f6dfbcae10d924889d`
- Files that declare at least one patch: 645
- Files that use `%patchlist`: 51, with 371 entries in total
- Expected findings: P1 140 files / 143 occurrences, P2 56 files / 119
  occurrences, P3 2 files, P4 25 files, P5 4 files, P6 12 files

## Deliverables

- `openruyi_precommit_hooks/check_spec_patch_patchlist.py`
- `tests/check_spec_patch_patchlist_test.py`
- `docs/rules/check-spec-patch-patchlist.md`
- A thirteenth hook block in `.pre-commit-hooks.yaml`
- A `setup.cfg` entry point, plus updates to `docs/user-guide.md` and
  `CHANGELOG.md`
- A Feishu report at <https://openruyi.feishu.cn/wiki/Oyu4wZBoJioQYjk0EUec3ySHnqc>
  with the overview, the per-checkpoint distribution and the full finding
  list, whose file column links into the openRuyi repository
