# check-spec-license

> Rule ID: `check-spec-license`

## Original Requirement

Source: [openRuyi Packaging Specification · License](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#license)
and the *license identifier* clause of the same document, plus the
[license rules](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#license)
linked from the same page.

The rule covers **only** the value of the `License` field in a spec. Whether
the field exists at all is owned by `check-spec-basic-fields`; whether the
declared licenses actually match the source is out of scope for every static
check.

### License

- The `License` field must be present.
- The value must be a valid SPDX license expression.
- Every identifier in the expression must exist in the SPDX license list.
- Identifiers must use the canonical spelling from the SPDX license list.

The specification points at SPDX as the identifier source and requires the
value to be an expression rather than free text, so a value such as
`BSD and MIT` or `Public Domain` cannot satisfy it.

## Checkpoints

| # | Checkpoint | Requirement | Failure condition | Flag | Default |
| --- | --- | --- | --- | --- | --- |
| 1 | Expression syntax | The value must be a valid SPDX expression | The value cannot be parsed as an SPDX expression | — | on |
| 2 | Known identifiers | Every identifier must exist in the SPDX license list | An identifier is absent from the license and exception lists | — | on |
| 3 | Canonical case | Identifiers must use the canonical spelling | The identifier matches a known id case-insensitively but not exactly | — | on |

The three checkpoints run in a fixed order and a syntax failure stops the
other two, because identifier checks need a tree to walk. This is why a value
such as `Public Domain` is reported once, as a syntax problem, instead of
twice.

## What counts as a valid expression

The rule implements the SPDX expression grammar directly instead of matching
the text with regular expressions:

- A term is a license identifier, a `LicenseRef-...` identifier, or a
  parenthesised expression.
- Terms are joined by `AND` and `OR`, which must be upper case.
- A term may be followed by `WITH <exception>`, where `<exception>` must come
  from the SPDX exception list.

The parser reports these shapes:

| Shape | Message |
| --- | --- |
| `BSD and MIT` | `"and" must be upper case` |
| `MIT, BSD-3-Clause` | `use AND / OR instead of ","` |
| `MIT AND` | `operator "AND" / "OR" must be followed by a license identifier` |
| `(MIT OR BSD-3-Clause` | `unbalanced "("` |
| `LGPL-2.1-or-later BSD-3-Clause` | `missing AND / OR before "BSD-3-Clause"` |
| `MIT AND Apache-2.0 WITH` | `"WITH" must be followed by an SPDX exception identifier` |
| `GPL with additional restrictions` | `"with" must be upper case` |
| `MIT & BSD-3-Clause` | `unexpected character "&" at offset 4` |

## Scope notes

Every clause below is a real part of the specification that this rule
deliberately does not enforce, or a decision about how the checkpoints above
behave.

- **`LicenseRef-*` is always accepted.** The specification allows a package to
  declare a license the SPDX list does not cover through a `LicenseRef-`
  identifier, and the actual license text lives in the package. Any identifier
  starting with `LicenseRef-` therefore passes checkpoints 2 and 3. This is how
  `LicenseRef-openRuyi-Public-Domain` is accepted while the neighbouring
  `sprintf` is reported.

- **Deprecated identifiers are accepted.** The vendored list contains all 740
  identifiers of the SPDX list, deprecated ones included, because neither the
  packaging guideline nor the linked license document asks for deprecation to
  be rejected. `ssh-keyscan` and `BSD-2-Clause-FreeBSD` therefore pass.

- **Exception identifiers in license position are reported as such.**
  `LGPL-3.0-linking-exception` exists in the SPDX exception list, so calling it
  unknown would be wrong. The message states that it must follow `WITH`, which
  points at the fix without inventing an identifier.

- **A macro value is skipped.** `License: %{license}` expands at build time and
  carries no static information, so checkpoints 1-3 stay silent for any value
  containing `%`.

- **An empty value is not this rule's business.** `License:` with nothing after
  the colon is reported by `check-spec-basic-fields`, which owns field presence
  and emptiness for every core field. Reporting it twice would give the same
  defect two owners.

- **Every `License:` line is checked, subpackage blocks included.** RPM
  subpackages declare their own `License` inside `%package` blocks. 69 specs in
  the corpus carry more than one such line (maximum 4), and each is evaluated
  independently.

- **Whitespace around the value is stripped.** The corpus writes
  `License:        <value>` with alignment padding on all 6571 occurrences. The
  captured value is stripped before parsing, so padding never produces a
  finding.

- **Not enforced: whether the declared licenses match the source.** Deciding
  whether a package really is `MIT` requires reading the upstream license
  files and judging them. A static text check cannot do that.

- **Not enforced: `%license` usage.** The guideline asks packagers to mark
  license files with `%license`, but 3088 of 6341 corpus specs have a `License`
  field and no `%license`. The rule cannot distinguish an omission from a
  package whose source ships no license file, so it stays silent.

- **Not enforced: subpackage licenses covering the files they own.** Whether
  the subpackage `License` matches the files listed in the subpackage
  `%files` section needs a package build, not a text check.

- **Not enforced: `License:` comment lines.** A `# License: MIT` comment never
  matches, because the field must start at column 0.

- **Version of the vendored data.** `_spdx_ids.py` is generated from the SPDX
  license list at revision `8791eda` and carries 740 license identifiers and 86
  exception identifiers. The list is vendored because the hook must run
  offline with no third-party dependency. Regenerating it is a separate,
  deliberate act; see `docs/developer-guide.md`.

- **Other fields are out of scope.** `Name` is enforced by `check-spec-name`,
  `Version` by `check-spec-version`, `Release` and the `%{dist}` override by
  `check-spec-release`, `Summary` by `check-spec-summary`, and the basic field
  layout by `check-spec-basic-fields`; this rule is limited to `License`.

## Examples

Passing values:

```
License:        MIT
License:        Apache-2.0 WITH LLVM-exception
License:        (GPL-2.0-or-later OR BSD-3-Clause) AND LGPL-2.1-or-later
License:        MIT AND LicenseRef-openRuyi-Public-Domain
License:        Apache-2.0 AND (Apache-2.0 WITH LLVM-exception OR NCSA)
```

Failing values:

```
License:        BSD and MIT            # "and" must be upper case
License:        MIT, BSD-3-Clause      # use AND / OR instead of ","
License:        BSD 2-Clause           # missing AND / OR before "2-Clause"
License:        MPL-2.0+               # unknown, did you mean "MPL-2.0"?
License:        zlib                   # must be spelled "Zlib"
```

## Corpus result

Scanning `openRuyi` at `1bb886c` (6341 specs) produces 52 findings in 52
specs, split as 20 syntax, 22 unknown identifiers, 1 exception in license
position, and 9 case errors. The full list, the reconciliation against the
prototype baseline, and the false-positive audit are recorded in
`.trellis/tasks/11-09-check-spec-license/research/scan-result.md`.
