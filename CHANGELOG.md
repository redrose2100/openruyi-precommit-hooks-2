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
  line is optional; exactly one blank `#` comment line must separate the
  copyright lines and the license line.
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
