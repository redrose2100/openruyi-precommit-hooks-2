# User Guide

This document is for users of this repository's hooks. It explains how to
install and use the hooks, and lists the currently supported hooks.

## Installing pre-commit

All hooks in this repository are used through the
[pre-commit](https://pre-commit.com) framework. If pre-commit is not yet
installed in your project, install it first:

```console
$ pip install pre-commit
```

## Using the Hooks

Add this repository to the `.pre-commit-config.yaml` at the root of your
project:

```yaml
-   repo: https://github.com/openRuyi-Project/openruyi-precommit-hooks
    rev: v0.1.0  # replace with the version you want to use
    hooks:
    -   id: check-spdx-header
```

Then install the git hooks and run the checks:

```console
$ pre-commit install
$ pre-commit run --all-files
```

After that, pre-commit automatically runs the configured hooks on staged
files every time you run `git commit`. You can also run a single hook:

```console
$ pre-commit run check-spdx-header --all-files
```

## Supported Hooks (1 in total)

| # | Hook ID | Description | Rule Doc |
| --- | --- | --- | --- |
| 1 | `check-spdx-header` | Validates that spec files start with SPDX copyright and license declarations (ISCAS + openRuyi Contributors + MulanPSL-2.0) | [rules/check-spdx-header.md](rules/check-spdx-header.md) |

## Standalone CLI Usage

Each hook also provides a standalone command-line entry point, so it can be
run without pre-commit:

```console
$ check-spdx-header path/to/foo.spec
```

An exit code of 1 means some files do not meet the requirements; 0 means
all files pass.

See each rule's document for detailed checking rules and examples:
[rules/](rules/)
