# openruyi-precommit-hooks

Some out-of-the-box hooks for [pre-commit](https://pre-commit.com).

This project provides out-of-the-box git hooks for openruyi-related
repositories, managed via the [pre-commit](https://pre-commit.com)
framework.

## Quick Start

Add this repository to your `.pre-commit-config.yaml`:

```yaml
-   repo: https://github.com/openRuyi-Project/openruyi-precommit-hooks
    rev: v0.1.0  # replace with the version you want to use
    hooks:
    -   id: check-spdx-header
```

Then run:

```console
$ pre-commit install
```

## User Guide

For hook users: installation, usage, and the list of supported hooks:

- [User Guide](docs/user-guide.md)
- [Rules](docs/rules/) (detailed checking rules and examples for each rule)

## Developer Guide

For contributors: development, testing, and commit conventions:

- [Developer Guide](docs/developer-guide.md)

## License

[LICENSE](LICENSE)
