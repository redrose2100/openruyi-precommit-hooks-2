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

## Supported Hooks (9 in total)

| # | Hook ID | Description | Rule Doc |
| --- | --- | --- | --- |
| 1 | `check-spdx-header` | Validates that spec files start with SPDX copyright and license declarations (ISCAS + openRuyi Contributors + MulanPSL-2.0) | [rules/check-spdx-header.md](rules/check-spdx-header.md) |
| 2 | `check-spec-basic-fields` | Validates that spec files follow the openRuyi packaging guideline rules for the basic fields and sections | [rules/check-spec-basic-fields.md](rules/check-spec-basic-fields.md) |
| 3 | `check-spec-name` | Validates that the spec `Name` field follows the openRuyi packaging guideline naming rules, including the case its own `Source` URLs use | [rules/check-spec-name.md](rules/check-spec-name.md) |
| 4 | `check-spec-version` | Validates that the spec `Version` field follows the openRuyi packaging guideline versioning rules | [rules/check-spec-version.md](rules/check-spec-version.md) |
| 5 | `check-spec-release` | Validates that the spec `Release` field follows the openRuyi packaging guideline release rules: it must be present and use `%autorelease`, must not hard-code a distribution suffix, and the `%{dist}` macro must not be overridden | [rules/check-spec-release.md](rules/check-spec-release.md) |
| 6 | `check-spec-summary` | Validates that the spec `Summary` field follows the openRuyi packaging guideline summary rules: it must be present and non-empty, must not end with an English period, and should be English only | [rules/check-spec-summary.md](rules/check-spec-summary.md) |
| 7 | `check-spec-license` | Validates that the spec `License` field follows the openRuyi packaging guideline license rules: the value must be a valid SPDX license expression, every identifier must exist in the SPDX license list, and identifiers must use the canonical spelling | [rules/check-spec-license.md](rules/check-spec-license.md) |
| 8 | `check-spec-url` | Validates that the spec `URL` field follows the openRuyi packaging guideline URL rules: the spec must set `URL` to the package website or the project source URL, or write the comment `# URL: No URL link available`; the value must be an absolute URL and must not be built from macros; the field must be spelled `URL` | [rules/check-spec-url.md](rules/check-spec-url.md) |
| 9 | `check-spec-vcs` | Validates that the spec `VCS` field follows the openRuyi packaging guideline VCS rules: `VCS` may be omitted only when `URL` is already a source repository link, and is required otherwise, either as a cloneable address or as the comment `# VCS: No VCS link available`; the value must be cloneable and must not be built from macros; the field must be spelled `VCS` | [rules/check-spec-vcs.md](rules/check-spec-vcs.md) |

## Standalone CLI Usage

Each hook also provides a standalone command-line entry point, so it can be
run without pre-commit:

```console
$ check-spdx-header path/to/foo.spec
$ check-spec-basic-fields path/to/foo.spec
$ check-spec-name path/to/foo.spec
$ check-spec-version path/to/foo.spec
$ check-spec-release path/to/foo.spec
$ check-spec-summary path/to/foo.spec
$ check-spec-license path/to/foo.spec
$ check-spec-url path/to/foo.spec
$ check-spec-vcs path/to/foo.spec
```

An exit code of 1 means some files do not meet the requirements; 0 means
all files pass.

`check-spec-name` additionally exposes an opt-in `--verify-upstream` mode that
resolves the names no `Source` URL can settle by querying the host. It is not
registered as a hook because it makes network requests; see
[rules/check-spec-name.md](rules/check-spec-name.md) for the flags.

See each rule's document for detailed checking rules and examples:
[rules/](rules/)
