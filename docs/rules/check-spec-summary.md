# check-spec-summary

> Rule ID: `check-spec-summary`

## Original Requirement

Source: [openRuyi Packaging Specification · Summary](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#summary)
and the *layout and readability* clause of the same document (the
clause that requires American English for descriptive text).

The rule covers **only** the `Summary` field of a spec, including the
`Summary` lines inside `%package` subpackage blocks. `Name`, `Version`,
`Release`, `License` and every other field are out of scope.

### Summary

- `Summary` must be present and must not be empty.
- `Summary` must be a brief description of what the package does.
- `Summary` should contain only the necessary English introduction.
- `Summary` must not end with an English period `.`.

The readability clause adds that descriptive text in a spec (including
`Summary`, comments and `%description`) should be written in American
English unless a supplementary specification for the package type says
otherwise.

## Checkpoints

| # | Checkpoint | Requirement | Failure condition | Flag | Default |
| --- | --- | --- | --- | --- | --- |
| 1 | Presence | The spec must declare a non-empty `Summary` | No `Summary:` line, or the value is empty | — | on |
| 2 | Trailing period | The value must not end with an English period `.` | The value ends with `.` (after stripping trailing whitespace) | — | on |
| 3 | English only | The value should be English only (American English) | The value contains a non-ASCII character (anything above U+007F) | — | on |

### Scope notes

Every clause below is a real part of the specification that this rule
deliberately does not enforce, or a decision about how the checkpoints above
behave.

- **Checkpoint 3 is a "should" rule, reported as a violation.** The
  guideline requires the summary to be a necessary English introduction and
  the readability clause requires American English. A value that contains
  any non-ASCII character cannot be English only, so it is reported with
  the fix suggested. ASCII text — including punctuation, digits and
  abbreviations such as `e.g.` — is never flagged by this checkpoint.

- **A macro-valued summary skips checkpoints 2-3.** `Summary:
  %{summary}`, `Summary: %{?summary}` and bare `%foo` all expand at build
  time, so the visible text is not the final value. The checkpoints that
  judge the text cannot decide statically and stay silent; checkpoint 1
  still fires when the field is missing or empty. This mirrors the
  `check-spec-version` macro escape hatch.

- **Every `Summary:` line is checked, subpackage blocks included.** RPM
  subpackages declare their own `Summary` inside `%package` blocks, and
  the guideline's field rules apply to subpackage definitions as well. The
  rule therefore finds every top-level `Summary:` line in the file, not
  just the main package one. A commented-out `# Summary: ...` line never
  matches, because the field must start with `Summary` at column 0.

- **Trailing whitespace is stripped before checkpoint 2.** A value such as
  `Example package. ` (with a trailing space) is reported as ending with a
  period, because the visible value after trimming is the text a reader
  sees.

- **Not enforced: whether an ASCII summary is grammatical American
  English.** Deciding that a value is a complete, grammatical sentence or
  uses British spellings (`colour` vs `color`) needs a language model, not
  a static text check. The rule only rejects characters and shapes that are
  statically decidable.

- **Not enforced: how "brief" a summary is.** The guideline asks for a
  brief description but gives no numeric bound; judging that needs a
  semantic decision this hook deliberately leaves to the packager.

- **Other fields are out of scope.** `Name` is enforced by
  `check-spec-name`, `Version` by `check-spec-version`, `Release` and the
  `%{dist}` override by `check-spec-release`, and the basic field layout by
  `check-spec-basic-fields`; this rule is limited to `Summary`.
