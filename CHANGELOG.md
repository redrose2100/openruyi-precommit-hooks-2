# CHANGELOG

### Changed

- Renamed the SPDX header rule from `check-spdx-header` to
  `check-spec-header` so every rule ID uses the `check-spec-*` prefix. The
  module moved to `openruyi_precommit_hooks/check_spec_header.py` (helper
  `_check_spec_header`), the rule doc to `docs/rules/check-spec-header.md`,
  and the test to `tests/check_spec_header_test.py`. The old hook ID is no
  longer registered, so existing `.pre-commit-config.yaml` files must update
  `id: check-spdx-header` to `id: check-spec-header`.

### Fixed

- `check-spec-basic-fields`: no longer reports `missing required section
  "%files"` for kernel specs (`linux-lts-kmhv2`, `linux-lts`) that delegate
  `%files`, the subpackages, their `%description`s and the scriptlets to the
  `%linux_package_implementation` macro (defined in
  `SPECS/openruyi-linux-build/macros.linux`). A known section-providing
  macro counts as present at its invocation line for the required-sections
  and section-order checks, needs no blank line between the sections it
  emits, and its own line is skipped by the backward separator scan. The
  macro table is a closed set — an unknown `%foo` line still cannot satisfy
  a required section.

### Added

- Fourth rule hook `check-spec-version`: validates the `Version` field
  against the "Version" section and the "Versioning" chapter of the openRuyi
  packaging guidelines — the field must be present and non-empty, the value
  must not contain `-` or `_`, must not contain characters outside
  `[A-Za-z0-9.+~]`, and the snapshot form (lowercase SCM tag + date +
  revision) is recognised, with a macro-valued version escaping the content
  checks.
- Fifth rule hook `check-spec-release`: validates the `Release` field and the
  `%{dist}` macro override against the openRuyi packaging guidelines — the
  field must be present and non-empty, should use `%autorelease`, must not
  hard-code a distribution suffix such as `.fc38` or `.el9`, and the `%{dist}`
  macro must not be overridden with `%global dist` / `%define dist`.
- Sixth rule hook `check-spec-summary`: validates the `Summary` field against
  the openRuyi packaging guidelines — the field must be present and non-empty,
  must not end with an English period, and should be English only (American
  English; any non-ASCII character is reported). Subpackage
  `Summary` lines inside `%package` blocks are checked as well, and a
  macro-valued summary skips the content checkpoints.
- Seventh rule hook `check-spec-license`: validates the `License` field
  against the "License" section of the openRuyi packaging guidelines and the
  linked license document. The value must parse as an SPDX license
  expression (checked with a real parser, not a regular expression), every
  identifier must exist in the SPDX license list, and identifiers must use
  the canonical spelling. `LicenseRef-*` identifiers and macro values are
  accepted, deprecated identifiers are accepted, and subpackage `License`
  lines are checked as well. The SPDX data is vendored in
  `openruyi_precommit_hooks/_spdx_ids.py` so the hook keeps working offline.
- Eighth rule hook `check-spec-url`: validates the `URL` field against the
  "URL" section of the openRuyi packaging guidelines — the spec must set
  `URL` to the package website or the project source URL, or write the
  comment `# URL: No URL link available` with the `# URL:` prefix preserved;
  the value must not be empty, must be an absolute `scheme://host` URL, and
  must not be assembled from macros such as `%{name}` (percent escapes such
  as `%2B` are URL encoding, not macros, and pass). The field must be spelled
  `URL`; `--no-check-field-case` turns that checkpoint off. Subpackage `URL`
  lines are checked as well, and field ordering stays with
  `check-spec-basic-fields`.
- Ninth rule hook `check-spec-vcs`: validates the `VCS` field against the
  "VCS" section of the openRuyi packaging guidelines — `VCS` may be omitted
  only when `URL` already points at the source repository, and is required
  otherwise, either as a cloneable address or as the comment
  `# VCS: No VCS link available` with the `# VCS:` prefix preserved. The
  value must not be empty, must not be assembled from macros such as
  `%{name}` (percent escapes are URL encoding and pass), and must be
  cloneable, accepting an absolute URL (`git://`, `https://`, `ssh://`,
  `svn://`), the same URL behind a version-control prefix (`git:https://...`),
  or an scp-like `user@host:path`. Documentation and package-index hosts
  (`*.github.io`, `*.readthedocs.io`, `crates.io`, `metacpan.org`,
  `pypi.org`, ...) count as non-repository URLs; `--no-check-doc-site`
  accepts them without `VCS`. The field must be spelled `VCS`;
  `--no-check-field-case` turns that checkpoint off. Subpackage `VCS` lines
  are checked as well, and `VCS` stays silent when `URL` is missing, empty or
  macro-built, because `check-spec-url` already owns those defects.
- Tenth rule hook `check-spec-source`: validates `Source`, `SourceN` and
  `%sourcelist` against the "Source" section of the openRuyi packaging
  guidelines and the linked "SourceURL" supplement. A source fetched over
  `http`/`https` needs an adjacent `#!RemoteAsset:` comment, that comment must
  carry a 64-digit `sha256:` checksum, and a VCS fetch (`git+`, `git:`,
  `svn:`, ...) additionally needs `#!CreateArchive` between the comment and
  the `Source` line; `#!CreateArchive` must never travel alone. Two
  declarations must not resolve to the same index (`Source` and `Source0` are
  both index 0), a value must not be empty, `#!RemoteAsset:` must not be
  orphaned, `SourceN` indices must run from 0 without gaps, SourceForge URLs
  must use `downloads.sourceforge.net`, the tarball name must be derivable
  from the URL (a trailing `/` or a query string with no `#/name` fragment is
  reported), and the field must be spelled `Source` or `SourceN`.
  `%sourcelist` must stand alone on its line and be followed by at least one
  file name. `--no-check-field-case` and `--no-check-index-sequence` turn the
  two stylistic checkpoints off. Local source names and overall field order
  stay out of scope, and `#!RemoteAsset`/`#!CreateArchive` comments that
  annotate `Patch` or `Icon` lines belong to their own fields.
- Eleventh rule hook `check-spec-buildarch`: validates the optional
  `BuildArch` field against the "BuildArch (optional)" clause of the openRuyi
  packaging guidelines. The field must be spelled `BuildArch`, must not be
  empty, must carry a single bare lower-case architecture token such as
  `noarch` or `x86_64` (a macro value escapes the value checks), must be
  declared at most once per package block, must be written after the last
  `Source` / `SourceN` / `%sourcelist` of its block and before `BuildSystem`,
  and a `noarch` block must not key an installed path off the build host via
  `%{_libdir}`, `%{_lib}`, `%{_lib64}`, `%{_arch}`, `%{_target_cpu}`,
  `%{_host_cpu}` or `%{_target_platform}`.
- Twelfth rule hook `check-spec-buildsystem`: validates the optional
  `BuildSystem` field against the "BuildSystem" clause of the openRuyi
  packaging guidelines. The field must be spelled `BuildSystem`, must not be
  empty, must carry a single literal lower-case build system name such as
  `autotools`, `cmake` or `rustcrates` (a macro value is reported because the
  field names a fixed keyword), must be declared at most once per package
  block, must be written after the last `Source` / `SourceN` /
  `%sourcelist` of its block, and must sit after `BuildArch` and before
  `BuildRequires`. The main spec does not maintain the list of usable build
  system names, so only the shape of the value is checked.
  `--no-check-field-case` and `--no-check-noarch` turn the two stylistic
  checkpoints off. A spec that writes no `BuildArch` is never reported,
  because the field is optional; the position checkpoints stay silent when
  the block has no source declaration or no `BuildSystem`; a `%package`
  subpackage block restarts the field model; and the `%{?_isa}` conditional
  form never counts as architecture evidence because it expands to nothing on
  a `noarch` build.
- Project scaffolding: `setup.cfg` / `setup.py` packaging configuration,
  `.pre-commit-hooks.yaml` public hooks manifest, `.pre-commit-config.yaml`
  bootstrap configuration.
- Test infrastructure: `tests/`, plus `tox.ini`, `requirements-dev.txt`,
  GitHub Actions CI.
- First rule hook `check-spec-header`: validates that spec files start with
  SPDX copyright and license declarations (ISCAS + openRuyi Project
  Contributors + `SPDX-License-Identifier: MulanPSL-2.0`); the contributor
  line is optional; the `SPDX-License-Identifier` line terminates the header
  block, so trailing blank `#` lines and plain comments that follow it are
  outside the checked header and are accepted; duplicate copyright/license
  lines and contributors in invalid positions are rejected.
- Second rule hook `check-spec-basic-fields`: validates that spec files follow
  the "Basic Fields and Sections" and "Minimal Skeleton Example" sections of
  the openRuyi packaging guidelines — the five required fields and the three
  required sections must be present, sections must be ordered and separated by
  a blank line, `%changelog` must contain `%autochangelog`, `Release` should
  use `%autorelease`, and the core fields should keep their documented order
  inside each field block. Sections living in mutually exclusive conditional
  branches are treated as already separated by the branch boundary and do not
  need a blank line.
- Third rule hook `check-spec-name`: validates the `Name` field against the
  "Name" section and the "Naming" chapter of the openRuyi packaging
  guidelines — the field must be present and non-empty, may only use
  `[A-Za-z0-9._+-]`, must not start or end with a separator, must not contain
  repeated separators, and must not be reused by a subpackage of the same spec
  (compared case-insensitively). The lowercase preference is enforced by
  default with `perl-*` exempted, and can be disabled with `--no-check-case`;
  the hyphen-over-underscore preference is opt-in via `--check-separator`.
  A capitalized name is additionally judged against the case its own
  `Source\d*` URLs use, so the names that are genuinely upstream spellings are
  silenced by evidence instead of by a blanket `--no-check-case`, and a
  lowercase name against a capitalized artefact is caught as well; the
  `URL:` line is excluded as evidence because a forge normalizes its path
  while the tarball keeps the real spelling. This check is purely offline and
  can be disabled with `--no-check-upstream-case`, which reproduces the
  earlier output exactly. For the names no `Source` URL can settle, the
  abstract rule module exposes an opt-in `--verify-upstream` command that
  probes the URL itself and then the owning package index (GitHub, GitLab,
  PyPI, crates.io); it is deliberately not registered as a hook because it
  opens sockets, and it reports an undecided name as an error rather than
  dropping it.
- Repository-internal check `check-no-chinese`: fails if any checked file
  contains Chinese characters; reports the file path and line number. It is
  registered as a local hook in `.pre-commit-config.yaml` and run by CI on
  all files (`pre-commit run check-no-chinese --all-files`), but is not
  published as a public hook.
- Commit message check: integrated `conventional-pre-commit` (v4.4.0) as a
  commit-msg hook with `--strict` mode to enforce Conventional Commits,
  consistent with the README "Commit Convention" section.
- Rule documentation `docs/rules/`, user guide `docs/user-guide.md`, and
  README Hooks list.
