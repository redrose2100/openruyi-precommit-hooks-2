# PRD: check-spec-buildsystem rule

## Background

The openRuyi packaging guidelines state four normative requirements on the
`BuildSystem` field in the `#buildsystem` section, and the `BuildSystems`
supplement adds requirements on `BuildOption`. The
`openruyi-precommit-hooks` project already ships eleven `check-spec-*`
rules, but none of them validates the `BuildSystem` field itself, so a
misspelled field name, a duplicated declaration or a misplaced field can
only be caught by manual review.

## Goal

Add a twelfth rule, `check-spec-buildsystem`, that statically checks `.spec`
files during the pre-commit stage and reports stable, reproducible
messages.

## Normative sources

From <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/#buildsystem>:

1. A spec that uses the RPM declarative build system mechanism must declare
   the build system it uses through `BuildSystem`.
2. A spec that does not use that mechanism may omit `BuildSystem`.
3. A spec must not add an empty `BuildSystem` field only to say that the
   declarative mechanism does not apply.
4. When `BuildSystem` is present its value must name a supported
   declarative build system.

From <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/BuildSystems>:

- `BuildOption(<stage>):` must be separated from its arguments by exactly
  two spaces.
- `BuildOption` sits between `BuildSystem` and `BuildRequires`.

From `#buildarch` and the base field order section:

- `BuildArch` sits between the last `Source` field and the `BuildSystem`
  field.

## Checkpoints

| ID | Checkpoint | Source |
| --- | --- | --- |
| S1 | The field is spelled `BuildSystem` | field naming |
| S2 | The value is present | clause 3 |
| S3 | The value is one literal lowercase build system name | clause 4 |
| S4 | A field block declares the field at most once | clause 1 |
| S5 | The field sits after the last source declaration of its block | field order |
| S6 | The field sits after `BuildArch` and before `BuildRequires` | field order |

## Explicitly out of scope

- Deciding whether a package should use a declarative build system at all,
  which needs payload knowledge.
- Deciding whether the chosen build system matches the upstream recipe.
- Verifying that the build system macros exist in the build root.
- The semantics of the stage tags `%prep -a` and `%conf -p`.
- The correctness of the `BuildOption` arguments.

## Corpus baseline

- Scope: every `.spec` under the `SPECS` tree of the `openRuyi` repository,
  6341 files
- Commit: `1bb886cf1dc0dd4932a312f6dfbcae10d924889d`
- Supported names observed in the `%buildsystem_<name>_*` macro packages:
  autotools, cmake, golang, golangmodules, linux, meson, muon,
  perlbuild, perlmaker, pyproject, rust, rustcrates, waf
- Expected findings: nine S1, one S4, one S5, two S6, thirteen in total

## Deliverables

- `openruyi_precommit_hooks/check_spec_buildsystem.py`
- `tests/check_spec_buildsystem_test.py`
- `docs/rules/check-spec-buildsystem.md`
- A twelfth hook block in `.pre-commit-hooks.yaml`
- A `setup.cfg` entry point, plus updates to `docs/user-guide.md` and
  `CHANGELOG.md`
