# CHANGELOG

### Added

- Project scaffolding: `setup.cfg` / `setup.py` packaging configuration,
  `.pre-commit-hooks.yaml` public hooks manifest, `.pre-commit-config.yaml`
  bootstrap configuration.
- Test infrastructure: `tests/`, plus `tox.ini`, `requirements-dev.txt`,
  GitHub Actions CI.
- First rule hook `check-spdx-header`: validates that spec files start with
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
