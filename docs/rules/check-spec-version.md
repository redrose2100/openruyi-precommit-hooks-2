# check-spec-version

> Rule ID: `check-spec-version`

## Original Requirement

Source: [openRuyi Packaging Specification · Version](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#version)
and [openRuyi Packaging Specification · Versioning](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/Versioning)

The rule covers **only** the `Version` field of a spec. `Epoch` and `Release`
are deliberately out of scope.

### Version

- `Version` must reflect the upstream version.
- A version that consists only of half-width dots may use the upstream
  version verbatim (`1.5.7` -> `1.5.7`).
- A version with a prerelease marker (`alpha`, `beta`, `rc`) must be written
  with the marker lower-cased and preceded by `~` (`3.5.0-rc1` ->
  `3.5.0~rc1`).
- A version containing `-` must replace the hyphen with a dot
  (`7.1.1-44` -> `7.1.1.44`).
- A version containing `_` must replace the underscore with a dot
  (`17_6` -> `17.6`).
- A dotted date may be used verbatim (`2025.07` -> `2025.07`).
- A VCS-commit-hash version is written as `0+<scm><YYYYMMDD>.<hash7>`
  (`ee5b7e3...` -> `0+git20250808.ee5b7e3`).

### Versioning — Version field

- The tilde (`~`) is the mechanism for prerelease versions: it makes the
  component sort before (lower than) the same component without a tilde.
- The dot (`.`) is the mechanism for upstream patch-level versions; upstream
  separators such as `-` or `_` may need to be replaced with a dot or
  removed.
- A snapshot from an upstream that never released a version starts with `0`
  and must append `+<scm><date>.<revision>`. The SCM tag is a short
  identifier such as `git`, `svn`, `hg` or `snap`; the date is `YYYYMMDD`;
  the revision identifies the exact VCS position, usually the first 7 to 10
  characters of the commit hash.
- A snapshot after the last released version starts with that version and
  appends the same `+<scm><date>.<revision>` field.
- When the upstream breaks its version scheme and no transformation can
  produce a correctly ordering `Version`, the only remedy is `Epoch` — which
  is outside this rule.

## Checkpoints

| # | Checkpoint | Requirement | Failure condition | Flag | Default |
| --- | --- | --- | --- | --- | --- |
| 1 | Presence | The spec must declare a non-empty `Version` | No `Version:` line, or the value is empty | — | on |
| 2 | Hyphen | The value must not contain `-` | `-` appears (`7.1.1-44`) | — | on |
| 3 | Underscore | The value must not contain `_` | `_` appears (`17_6`) | — | on |
| 4 | Prerelease marker | A prerelease marker (`alpha`/`beta`/`rc`) must be preceded by `~` and lower-cased | The marker is not preceded by `~`, or it contains an uppercase letter | — | on |
| 5 | Snapshot form | A value containing `+` must follow `<base>+<scm><YYYYMMDD>.<revision>` | More than one `+`, an empty base, or a snapshot field that is not `<scm><YYYYMMDD>.<revision>` (the revision is usually 7-10 characters and never more than a full 40-character SHA-1) | — | on |
| 6 | Character set | The value may only contain `A-Za-z0-9.+~` | Any other character, including whitespace (`-`/`_` are reported by checkpoints 2 and 3, not here) | — | on |

### Scope notes

Every clause below is a real part of the specification that this rule
deliberately does not enforce, or a decision about how the checkpoints above
behave.

- **Checkpoint 5 is on by default.** A value containing `+` that is not the
  documented snapshot form — for example an upstream `1.2.3+build5` suffix —
  is reported. This is a decision rather than a reading of the text: the
  guideline names `+` only as the snapshot separator, so a non-conforming
  `+` has no documented meaning and the packager should rewrite the version
  so that it sorts correctly. A scan of the openRuyi `SPECS` tree gives the
  actual false-positive surface, which is reported per rule class so that a
  human can confirm each finding.

- **The prerelease-marker set is closed.** Only `alpha`, `beta` and `rc` are
  checked, because the guideline names exactly those three. `pre` and `dev`
  are not markers this rule understands; a value such as `1.0~dev` passes
  checkpoint 4 (and checkpoint 6, because `~` is allowed). A marker that is
  part of a longer word — `1.0alphabet`, `1.0arc` — is not a marker either:
  the marker match requires word boundaries on both sides, while `1.0rc1`
  (marker followed by a digit) still matches.

- **Checkpoint 3 reports every underscore.** The guideline says the
  underscore must be replaced with a dot, so `17_6` is a violation whether
  or not the upstream name naturally contains an underscore. There is no
  opt-out flag. A macro-valued version such as `%{upstream_version}` is
  skipped (see below), so a packager who keeps the underscore in a macro is
  not reported here.

- **Macro-valued versions skip every value-based checkpoint.** A `Version`
  whose value still holds an unresolved `%{...}` reference — `%{version}`,
  `%{upstream_version}` — could expand to anything, so checkpoints 2 to 6
  are skipped for it. Checkpoint 1 still applies: a missing or empty
  `Version` is reported.

- **Multiple violations are all reported.** A value such as `1.0-rc1_beta`
  yields one message per violated checkpoint (hyphen, underscore,
  prerelease marker), and a value with several malformed prerelease markers
  yields one message per marker. Messages are deduplicated, so the same
  violation is never printed twice.

- **Not enforced: component ordering across releases.** The guideline says
  a component value must never decrease unless a component to its left has
  increased. Deciding that needs the previous release, which a per-file
  static hook does not have.

- **Not enforced: leading-zero preservation.** The guideline says not to
  remove leading zeros, but the original upstream spelling is unknowable
  from the spec alone, so there is nothing to compare against.

- **Not enforced: patch-level suffixes such as `post`.** `0.5.0-post1` is a
  real example in the guideline, but `post` is a free-form marker and the
  set of such markers is open, so no static check is attempted.

- **`Epoch` and `Release` are out of scope.** The `Epoch` and `Release`
  clauses of the Versioning guideline are enforced by neither this rule nor
  any other rule in this repository; this rule is limited to `Version`.
