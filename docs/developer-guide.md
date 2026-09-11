# Developer Guide

This document is for contributors to this repository. It covers the project
structure, development workflow, testing, and commit conventions.

## Project Structure

```
openruyi-precommit-hooks/
├── openruyi_precommit_hooks/     # hook implementation source
│   ├── __init__.py
│   └── check_spdx_header.py      # check-spdx-header hook
├── scripts/                      # repo-internal checks (not published)
│   └── check_no_chinese.py
├── tests/                        # pytest tests
│   ├── __init__.py
│   └── check_spdx_header_test.py
├── docs/
│   ├── user-guide.md            # user guide (how to use hooks & the list)
│   ├── rules/                   # rule docs (detailed checking rules)
│   │   └── check-spdx-header.md
│   └── developer-guide.md       # this document
├── setup.cfg                     # packaging config (console_scripts entries)
├── setup.py
├── .pre-commit-hooks.yaml        # public hooks manifest
├── .pre-commit-config.yaml       # bootstrap config (this repo's pre-commit)
├── tox.ini                       # tox config
├── requirements-dev.txt          # development dependencies
└── .github/workflows/ci.yml      # GitHub Actions CI
```

## Development Environment

```console
$ pip install -r requirements-dev.txt
$ pip install -e .
$ pre-commit install --hook-type pre-commit --hook-type commit-msg
```

## Adding a New Hook

1. Create `your_hook.py` under `openruyi_precommit_hooks/`, implementing
   `main(argv=None) -> int`; return non-zero to indicate a failed check.
2. Register a command-line entry in `[options.entry_points] console_scripts`
   of `setup.cfg`.
3. Declare the new hook metadata in `.pre-commit-hooks.yaml`.
4. Add corresponding tests under `tests/`, with test resources placed in
   `testing/resources/`.
5. Update the hooks list in `docs/user-guide.md` (increment the total count
   in the "Supported Hooks" heading by 1 for each new hook), and update
   `CHANGELOG.md`.

## Testing

```console
$ python -m pytest tests
```

CI runs the tests on Ubuntu (Python 3.10–3.13) and Windows (Python 3.13),
and performs code style checks via `pre-commit run --all-files`.

## Commit Conventions

This repository follows the
[Conventional Commits](https://www.conventionalcommits.org/v1.0.0/)
specification, with the format:

```
<type>(<scope>): <description>
```

This convention is enforced by `conventional-pre-commit` (a commit-msg hook,
`--strict` mode).

Common `type` values (full list, see the Angular Commit Convention):

| type | Purpose |
|------|---------|
| `feat` | New feature (e.g. a new hook / new capability) |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Formatting changes that do not affect logic (spaces, semicolons, indentation, etc.) |
| `refactor` | Refactoring without changing external behavior |
| `perf` | Performance improvement |
| `test` | Adding or modifying tests |
