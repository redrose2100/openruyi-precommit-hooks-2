# check-spec-release

> Rule ID: `check-spec-release`

## Original Requirement

Source: [openRuyi Packaging Specification · Release](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#release)
and [openRuyi Packaging Specification · Versioning](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/Versioning)
(`Release` field chapter).

The rule covers **only** the `Release` field of a spec, plus the `%{dist}`
macro override. `Version` and `Epoch` are deliberately out of scope.

### Release

- `Release` must be present and must not be empty.
- `Release` should use `%autorelease` so that the RPM build host assigns
  and bumps the release automatically. Both `%autorelease` and
  `%{autorelease}` count as compliant; a compound macro expression that
  embeds an `%autorelease` token (for example
  `%{patchset_release}.%{config_version}_%autorelease`) also counts.
- The value must not hard-code a distribution suffix such as `.fc38`,
  `.el9` or `.oe1`. `%{?dist}` is a macro reference, not a hard-coded
  suffix, so it never violates this clause.
- The `%{dist}` macro must not be overridden (`%global dist ...` or
  `%define dist ...`).

## Checkpoints

| # | Checkpoint | Requirement | Failure condition | Flag | Default |
| --- | --- | --- | --- | --- | --- |
| 1 | Presence | The spec must declare a non-empty `Release` | No `Release:` line, or the value is empty | — | on |
| 2 | `%autorelease` | The value should use `%autorelease` (`%autorelease` and `%{autorelease}` are both compliant) | The value contains no autorelease token — a literal number (`3`) or the traditional Fedora form (`1%{?dist}`) | — | on |
| 3 | Distribution suffix | The value must not hard-code a distribution suffix | The value matches `\.(fc|el|oe|openEuler)\d*` (case-insensitive) — `.fc38`, `.el9`, `.oe1`, `.oe2403`, `.openEuler1` | — | on |
| 4 | `%{dist}` override | The `%{dist}` macro must not be overridden | A `%global dist ...` or `%define dist ...` line appears anywhere in the file | — | on |

### Scope notes

Every clause below is a real part of the specification that this rule
deliberately does not enforce, or a decision about how the checkpoints above
behave.

- **Checkpoint 2 is a "should" rule, reported as a violation.** The
  guideline tells the packager to use `%autorelease` rather than managing a
  literal release number. A spec that writes `Release: 3` or
  `Release: 1%{?dist}` is reported with the fix suggested, because the
  maintainers' intent is that every package uses `%autorelease`. A scan of
  the openRuyi `SPECS` tree shows all 6290 specs already use
  `%autorelease`, `%{autorelease}` or a compound expression that embeds
  `%autorelease`; no spec triggers this checkpoint today.

- **Checkpoint 3 never fires on a macro reference.** `%{?dist}` expands to
  the build distribution at runtime, so it is not a hard-coded suffix. The
  checkpoint only matches literal suffix text (`.fc38`, `.el9`, `.oe1`,
  `.oe2403`, `.openEuler1`, ...). Combined with checkpoint 2,
  `Release: 1%{?dist}` yields exactly one message — checkpoint 2 — and
  `Release: 3.fc38` yields two independent messages, one per checkpoint.

- **Checkpoints 2 and 3 are plain text checks with no macro-value
  escape.** Unlike the `Version` rule, these two checkpoints match text
  directly (`%autorelease` token, hard-coded suffix string) and never need
  the macro-expanded value. A macro-valued release such as `1%{?dist}` is
  therefore correctly reported by checkpoint 2 instead of being skipped.

- **Checkpoint 4 tolerates leading whitespace.** `%global dist` and
  `%define dist` redefine the RPM distribution macro wherever they appear,
  and rpmbuild strips indentation when it reads the file, so an indented
  directive still counts as an override. A scan of the openRuyi `SPECS`
  tree found no `%{dist}` override today; the checkpoint is defensive.

- **Not enforced: bumping the release for every change.** The guideline
  says the release must be bumped for every change of the same version.
  Deciding that needs the previous revision of the file, which a per-file
  static hook does not have.

- **Not enforced: resetting the release to 1 when the version
  changes.** The guideline says the release starts at 1 again when the
  version changes. Deciding that needs the previous version, which a
  per-file static hook does not have.

- **Not enforced: the ordinal `%autorelease` expands to.** The actual
  release number is assigned by the build host and is unknowable from the
  spec alone.

- **`Version` and `Epoch` are out of scope.** The `Epoch` and `Version`
  clauses of the Versioning guideline are enforced by `check-spec-version`
  and no other rule in this repository handles `Epoch`; this rule is
  limited to `Release` and the `%{dist}` override.
