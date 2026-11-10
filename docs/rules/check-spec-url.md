# check-spec-url

> Rule ID: `check-spec-url`

## Original Requirement

Source: [openRuyi Packaging Specification · URL](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#url)

The rule covers **only** the `URL` field of a spec, including the `URL`
lines inside `%package` subpackage blocks. Every other field is out of
scope.

### URL

- When the upstream project has an official website, `URL` must be the
  package's official website link.
- When the upstream project has no official website but a public source
  repository, `URL` must be a meaningful project address, usually the
  source repository URL.
- When no meaningful upstream URL exists, `URL` may be omitted, but the
  comment `# URL: No URL link available` must be written at the position of
  the `URL` field, and the `# URL:` prefix must be preserved.
- The `URL` field must not be assembled with macros such as `%{name}`.

The `VCS` section of the same document adds that `VCS` may be omitted when
`URL` already points at the source repository. That branch belongs to a
future `VCS` rule, not to this one.

## Checkpoints

| # | Checkpoint | Requirement | Failure condition | Flag | Default |
| --- | --- | --- | --- | --- | --- |
| 1 | Presence | The main field block must declare `URL`, or write the documented placeholder comment | Neither a `URL` field nor a `# URL:` placeholder appears before the first section | — | on |
| 2 | Non-empty value | A declared `URL` must carry a value | `URL:` with nothing after the colon | — | on |
| 3 | Absolute URL form | The value must be a meaningful address, i.e. an absolute `scheme://host` URL | The value has no scheme, or its host has no dot (`FIXME`) | — | on |
| 4 | No macro concatenation | The value must not be built from macros | After removing `%XX` percent escapes, the value still contains `%` | — | on |
| 5 | Placeholder wording | The placeholder text must be exactly the documented sentence | A `# URL:` comment whose text is not `No URL link available` | — | on |
| 6 | Mutual exclusion | A placeholder and a real field must not coexist | The spec has both a `URL` field and a `# URL:` placeholder | — | on |
| 7 | Field name spelling | The field is spelled `URL`, as everywhere in the specification | The field name is `Url`, `url`, ... | `--no-check-field-case` | on |

### Scope notes

Every clause below is a real part of the specification that this rule
deliberately does not enforce, or a decision about how the checkpoints above
behave.

- **Checkpoint 4 inverts the usual macro escape hatch.** Every other rule in
  this repository treats a macro-valued field as unjudgeable and stays
  silent. Here the macro itself is the defect, so a macro-valued `URL`
  reports checkpoint 4 and **skips checkpoint 3**: judging the host of an
  unexpanded value is meaningless. One defect produces one finding.

- **Percent escapes are not macros.** `%2B`, `%20` and friends are URL
  encoding. The rule strips `%[0-9A-Fa-f]{2}` before testing for a
  remaining `%`, so
  `https://metacpan.org/release/Text-Tabs%2BWrap` passes.

- **Checkpoint 7 is enforced by default.** The specification spells the field
  `URL` everywhere, and the corpus shows `URL` 6346 times against `Url` 3
  times. `--no-check-field-case` turns the checkpoint off for a repository
  that has accepted the variants.

- **Checkpoint 7 does not steal a defect from checkpoints 2-4.** A `Url:`
  field still has its value validated, because a wrong field name does not
  make the value irrelevant. A `Url:` field also satisfies checkpoint 1, so
  the spec is not additionally reported as missing the field.

- **Checkpoint 1 is scoped to the main field block.** The block ends at the
  first recognised section header, so a `URL` that lives only in a
  `%package` subpackage does not satisfy the main package requirement.
  A `%global` or `%define` line is a macro invocation, not a section, and
  does not end the block.

- **Every `URL` line is checked, subpackage blocks included.** Checkpoints
  2-7 apply to every `URL` line in the file, not just the main package one.

- **A commented-out field is not the placeholder.** `# URL: https://old...`
  and `# URL: %{url}` are disabled fields. They do not satisfy checkpoint 1,
  do not trigger checkpoint 5, and never conflict with a real field under
  checkpoint 6. Only a commented `# URL:` line whose text is prose is
  treated as the documented placeholder.

- **A commented-out field never feeds the value checkpoints.** The field must
  start at column 0, so `# URL: FIXME` is invisible to checkpoints 2-4.

- **Repeated findings are de-duplicated.** A spec with several identical
  `URL` values reports one finding, not one per line, following the
  repository-wide `_dedup` contract.

- **Not enforced: field ordering.** `check-spec-basic-fields` owns field
  order and its `FIELD_ORDER` already contains `URL`. 6 corpus specs place
  `URL` before `License`; reporting that here would give one defect two
  owners.

- **Not enforced: whether the value is the official website.** Checkpoint 3
  only proves the value is a well-formed absolute URL. Deciding that a URL
  is the upstream's official site, or a "meaningful" project address, needs
  human judgement.

- **Not enforced: whether the URL is a source repository URL**, which is what
  decides whether `VCS` may be omitted. That is the `VCS` branch.

- **Not enforced: reachability.** Verifying that the host answers needs the
  network, which a pre-commit hook must not require.

- **Not enforced: `https` over `http`.** The specification does not require a
  secure scheme, and 192 corpus specs use `http`.

- **Not enforced: continuation lines.** A `URL` value wrapped onto a second
  line does not occur in this corpus, and judging it would need the field
  block rather than a single line.

- **Other fields are out of scope.** `Name` is enforced by
  `check-spec-name`, `Version` by `check-spec-version`, `Release` by
  `check-spec-release`, `Summary` by `check-spec-summary`, `License` by
  `check-spec-license`, and the basic field layout by
  `check-spec-basic-fields`; this rule is limited to `URL`.

## Examples

Passing values:

```
URL:            https://www.example.org/
URL:            https://github.com/owner/project
URL:            http://example.org/project
URL:            https://metacpan.org/release/Text-Tabs%2BWrap
# URL: No URL link available
```

Failing values:

```
URL:                             # empty value
URL:            FIXME             # not an absolute URL
URL:            example.org/foo   # no scheme
URL:            https://github.com/owner/%{name}   # built from a macro
Url:            https://example.org/foo            # wrong field spelling
# URL: no url link                 # wrong placeholder wording
```

## Corpus result

Scanning `openRuyi` at `1bb886c` (6341 specs) produces 23 findings in 23
specs, split as 12 missing fields, 4 non-absolute values, 4 macro-built
values and 3 misspelled field names. Checkpoints 2, 5 and 6 report nothing
on this corpus.
