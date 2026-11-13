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

The six checkpoints do not all come from `#buildsystem`. That section covers
only the value of the field and uses the MUST / MUST NOT wording. Three
further places in the guidelines supply the order and duplication
checkpoints, and they use weaker wording. Each source is listed separately.

### Source A — `#buildsystem`, MUST level

From <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/#buildsystem>:

1. A spec that uses the RPM declarative build system mechanism must declare
   the build system it uses through `BuildSystem`.
2. A spec that does not use that mechanism may omit `BuildSystem`.
3. A spec must not add an empty `BuildSystem` field only to say that the
   declarative mechanism does not apply.
4. When `BuildSystem` is present its value must name a supported
   declarative build system.

### Source B — base field section, SHOULD level

> When the following fields are present they should appear in this relative
> order: Name, Version, Release, Summary, License, URL, VCS, Source,
> BuildArch, BuildSystem, Patch, BuildOption, BuildRequires, ...

> The numbered forms Source, Source0 and Source1 are the same position, and
> the equivalent `%sourcelist` form also belongs to the source declaration
> block.

This gives S5 and the "before `BuildRequires`" half of S6.

### Source C — `BuildArch` section, SHOULD level

> The BuildArch field should appear between the last Source field and the
> BuildSystem field.

This gives the "after `BuildArch`" half of S6.

### Source D — supplement `BuildSystems`, advisory

> In the simplest case the spec file only needs to contain one build system
> declaration field.

This is the only basis for S4. It is advisory rather than normative, so S4
is the weakest checkpoint.

## Checkpoints

| ID | Checkpoint | Source | Strength |
| --- | --- | --- | --- |
| S1 | The field is spelled `BuildSystem` | A (implied) | error |
| S2 | The value is present | A clause 3 | error |
| S3 | The value is one literal lowercase build system name | A clause 4 | error |
| S4 | A field block declares the field at most once | D | error |
| S5 | The field sits after the last source declaration of its block | B | error |
| S6 | The field sits after `BuildArch` and before `BuildRequires` | B and C | error |

## Known deviation from the letter of the guidelines

S1, S4, S5 and S6 are stricter than a literal reading, because the guideline
wording is SHOULD or advisory while the hook reports them as errors.
The decision was taken deliberately and is documented in
`docs/rules/check-spec-buildsystem.md`: the findings are concrete defects in
the spec that ships, they need no build-time knowledge, and the corpus shows
the offending blocks were being edited anyway, so the fix is local.
`--no-check-field-case` and `--no-check-position` let a team opt out of S1,
S5 and S6. S4 has no opt-out flag.

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
