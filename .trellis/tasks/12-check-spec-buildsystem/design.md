# Design: check-spec-buildsystem

## Module layout

The module reuses the skeleton of the eleventh rule,
`check_spec_buildarch.py`, so that both rules share the same helpers and the
same message style.

```
check_spec_buildsystem.py
|-- constants
|   |-- RE_FIELD / RE_SECTION / RE_CONDITIONAL
|   |-- RE_SOURCELIST / RE_SOURCE_N
|   |-- RE_BUILD_SYSTEM_TOKEN
|   |-- RE_MACRO
|   `-- KNOWN_SECTIONS
|-- _Block(NamedTuple)
|-- reading and splitting: _read_lines / _is_section / _blocks_of
|-- field lookup: _find_build_system / _find_source_lines /
|                 _find_field_lines
|-- checks: _check_field_case     (S1)
|           _check_value          (S2 + S3)
|           _check_duplicate      (S4)
|           _check_after_source   (S5)
|           _check_position       (S6)
`-- entry: _check_spec_buildsystem_ext / _check_spec_buildsystem / main
```

## Splitting strategy

Identical to `check_spec_buildarch.py`:

- A line is a section header only when its name is in `KNOWN_SECTIONS`, so a
  macro invocation such as `%global debug_package %{nil}` neither ends a
  field block nor hides the fields written after it.
- The main preamble block is always kept, even when it holds no field, so
  that a "field is missing" style finding could be reported there and so
  that the subpackage block indices stay stable.
- An empty subpackage block is dropped, so an empty `%package` header is
  never reported twice.

## S1 field spelling

The lookup matches the name case-insensitively and returns the spelling the
packager used. A spelling that differs from `BuildSystem` is reported, which
covers `Buildsystem` and `BUILDSYSTEM` alike. A misspelled field still feeds
S2 to S6, because a wrong name does not make the value or the position
irrelevant.

## S2 and S3 value validity

- An empty value is reported, because clause 3 forbids an empty field.
- A value that holds a macro reference is reported rather than skipped.
  `BuildArch` accepts a macro because its value is a parameterised token,
  but this field names a fixed build system keyword, so an indirection
  cannot be resolved statically and the spec cannot be trusted to name a
  supported build system.
- A value that is not a single bare lowercase token is reported.
- A well formed token is accepted even when it is absent from the set of
  names documented today. The main spec states that it does not maintain
  the list of usable names, so a hardcoded whitelist would reject a build
  system added upstream. The openRuyi macro packages also ship `waf` and
  `muon`, which confirms that shape checking is the durable rule.

So S3 produces two distinct messages but counts as one checkpoint.

## S4 duplicate declaration

Provenance: advisory only, from the `BuildSystems` supplement sentence that
in the simplest case a spec "only needs to contain one build system
declaration field". No clause in `#buildsystem` mentions duplicates, so this
is the weakest of the six checkpoints.

Inside one field block, every occurrence of the field (matched
case-insensitively) is counted. More than one occurrence is reported with
all line numbers. In the openRuyi corpus,
`go-github-rcrowley-go-metrics.spec` declares the field twice inside one
block, which is a genuine mistake rather than a legitimate per-branch
declaration, so limiting the check to one block is correct. There is no
opt-out flag, because a duplicated declaration corrupts the spec data rather
than a style preference.

## S5 position after the last source declaration

Provenance: SHOULD level, from the base field relative-order list, which puts
`Source` before `BuildSystem` and defines `SourceN` and `%sourcelist` as the
same position as `Source`. Disabled by `--no-check-position`.

The check collects every `Source` / `SourceN` field line plus every
`%sourcelist` macro line of the block and takes the maximum. A field written
before that line is reported. A block that writes no source declaration is
silent, because the clause constrains the relative position of two present
fields.

## S6 position between BuildArch and BuildRequires

Provenance: SHOULD level, from two sentences. The base field relative-order
list gives the "before `BuildRequires`" half and the `BuildArch` section
sentence gives the "after `BuildArch`" half. Disabled by
`--no-check-position`.

Two independent sub-checks:

- When the block writes `BuildArch` and it comes after the field, the order
  is reported.
- When the block writes `BuildRequires` and its first line comes after the
  field, the order is reported. The first line is used because the field is
  commonly repeated once per dependency and the documented window closes on
  the first of them.

## Corpus verification

Running on `e:\code\openRuyi\SPECS` yields 13 findings in 12 files:

| Checkpoint | Count | Files |
| --- | --- | --- |
| S1 | 9 | dejagnu, ed, grep, libffi, libtool, lzip, mpfr, pkgconf, zstd |
| S4 | 1 | go-github-rcrowley-go-metrics |
| S5 | 1 | go-opentelemetry-contrib |
| S6 | 2 | go-github-rcrowley-go-metrics, mkosi |

## Compatibility

- Python 3.10 or newer, standard library only.
- Every message is pure ASCII English so that the `check-no-chinese` hook
  stays green.
- `--no-check-field-case`, `--no-check-value` and `--no-check-position`
  switch the three checkpoint groups off, matching the option style of the
  rest of the family.
