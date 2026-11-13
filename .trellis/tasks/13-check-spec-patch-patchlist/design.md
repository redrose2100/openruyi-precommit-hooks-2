# Design: check-spec-patch-patchlist

## Module layout

The module reuses the skeleton of the twelfth rule,
`check_spec_buildsystem.py`, so both rules share the same helpers and the
same message style.

```
check_spec_patch_patchlist.py
|-- constants
|   |-- RE_FIELD / RE_SECTION / RE_CONDITIONAL
|   |-- RE_PATCH_FIELD / RE_PATCHLIST
|   |-- RE_PATCH_FILE
|   |-- RE_PATCH_ENTRY
|   `-- KNOWN_SECTIONS
|-- _PatchEntry(NamedTuple)
|-- reading and splitting: _read_lines / _is_section / _blocks_of
|-- patch discovery: _find_patch_fields / _patchlist_entries
|-- checks: _check_comment           (P1)
|           _check_prefix            (P2 + P3)
|           _check_patchlist_needed  (P4)
|           _check_patchlist_position(P5)
|           _check_patch_position    (P6)
`-- entry: _check_spec_patch_patchlist_ext / _check_spec_patch_patchlist / main
```

## Splitting strategy

Identical to `check_spec_buildsystem.py`:

- A line is a section header only when its name is in `KNOWN_SECTIONS`, so a
  macro invocation such as `%global debug_package %{nil}` neither ends a
  field block nor hides the fields written after it.
- The main preamble block is always kept, even when it holds no field, so
  that the patch declarations of the preamble are always analysed.
- Every `%package` opens a fresh block, so a subpackage may only declare its
  own patches. In practice patch declarations live in the preamble.

## Patch entry discovery

Two declaration forms are collected into a single list of `_PatchEntry`
records, each carrying the 1-based line number, the file name and a flag
telling whether it came from a field or from `%patchlist`.

- **Field form.** A field whose name matches `patch\d*` case-insensitively.
  The value is the patch file reference and may hold a macro, a bare file
  name or a path.
- **`%patchlist` form.** The body starts on the line after the macro. It
  ignores blank lines inside the list but a blank line terminates it,
  because the corpus shows the multi-line `%global _description %{expand:`
  macro written immediately after a `%patchlist`. The body also terminates
  at the first line starting with `%`. Inside the body, comment lines and
  any token that does not end in `.patch` or `.diff` are skipped, because
  the documented form is a comment line followed by a bare file name.

Building the patch file name for the range checks:

- A value with a macro reference is skipped by P2 and P3, since the name is
  only known at build time.
- A value with a path is reduced to its last component, because the four
  digit prefix belongs to the file name and not to a directory.
- A value that carries no `.patch` or `.diff` suffix anywhere is skipped,
  so a reference such as `Patch0: %{name}.diff.in` is not reported as a
  badly named patch.

## P1 comment above a patch declaration group

Provenance: SHOULD level, from the main guidelines clause 1 and repeated in
the supplement. The supplement example shows one comment followed by a bare
file name and repeats for the next group, which is what fixes the grouping
granularity.

Discrete checkpoints:

- Contiguous field declarations form one group; only the first line needs a
  comment directly above it.
- Contiguous `%patchlist` entries form one group; only the first entry needs
  a comment directly above it.
- A comment line is a line whose first non-space character is `#`.
- An entry whose group starts on the first line of the file is reported,
  because there is no comment above it.

Known limitation, documented in the rule doc: the guidelines allow a patch
to be considered self-explanatory, and this exemption is not evaluated
because it would need the patch payload. `--no-check-comment` turns the
whole checkpoint off.

## P2 and P3 patch file naming

Provenance: MUST level, from the main guidelines clause 2 and repeated
unchanged in the supplement.

- P2 reports a patch file name that does not start with four digits.
- P3 reports a patch file name whose four digit prefix is outside
  `0001`-`2999`.

They are separate checkpoints because they produce different findings and a
file can satisfy P2 while violating P3. Both are disabled by
`--no-check-naming`.

The rule does not verify that the prefix matches the actual patch type. That
would need the patch payload and its upstream history. A four digit number
inside the documented range is accepted whatever the patch really is.

## P4 more than three patches implies `%patchlist`

Provenance: advisory, from the main guidelines clause 3, where the wording
is "it is not appropriate" rather than a MUST. It stays enabled because the
corpus shows the threshold is respected almost everywhere: only 25 files
declare more than three patches without a list.

The count includes field declarations and `%patchlist` entries, but the
finding is only reported when the spec has no `%patchlist` at all. When a
`%patchlist` is present the threshold is already satisfied, so no finding is
produced even if the list is short.

## P5 `%patchlist` above the first `%description`

Provenance: MUST level, from the main guidelines clause 3 and repeated in
the supplement, which also links the rpm issue that explains why.

The comparison uses the first `%description` of the file, since that is the
main package description and the documented anchor.

## P6 `Patch` position

Provenance: SHOULD level, from the supplement placement sentence and from
the base field relative order list in the main guidelines.

- When the spec writes `BuildOption`, the first `Patch` must come before it.
- When the spec does not write `BuildOption`, the first `Patch` must come
  before the first `BuildRequires`.
- A spec that writes neither is silent, because the documented window is
  defined relative to those fields.

The first `Patch` is compared, because a spec that repeats the field one per
patch satisfies the clause as soon as the earliest one is inside the window.

## Corpus verification

Running on `e:\code\openRuyi\SPECS` yields 305 findings in 187 files:

| Checkpoint | Files | Occurrences |
| --- | --- | --- |
| P1 | 140 | 143 |
| P2 | 56 | 119 |
| P3 | 2 | 2 |
| P4 | 25 | 25 |
| P5 | 4 | 4 |
| P6 | 12 | 12 |

Representative genuine findings:

| File | Checkpoint | Evidence |
| --- | --- | --- |
| `cups/cups.spec` | P1 | ten `%patchlist` entries with no comment at all |
| `cdparanoia/cdparanoia.spec` | P2 | `cdparanoia-10.2-endian.patch` |
| `freetype/freetype.spec` | P2 | `freetype-2.3.0-enable-spr.patch` |
| `libunwind/libunwind.spec` | P3 | `3000-libunwind-no-dl-iterate-phdr.patch` |
| `rpm/rpm.spec` | P3 | `6464-auto-config-update.diff` |
| `audiofile/audiofile.spec` | P4 | eleven `PatchN` fields, no `%patchlist` |
| `openssl/openssl.spec` | P5 | `%patchlist` below `%description` |
| `aom/aom.spec` | P6 | first `Patch` after `BuildOption` |

Compliant files used as negative regression fixtures:

| File | Reason |
| --- | --- |
| `cdson/cdson.spec` | every `%patchlist` entry preceded by a commit link |
| `go/go.spec` | grouped comments above grouped `%patchlist` entries |
| `attr/attr.spec` | `Patch1: 0001-...`, index and prefix intentionally differ |

## Flags

| Flag | Disables |
| --- | --- |
| `--no-check-comment` | P1 |
| `--no-check-naming` | P2 and P3 |
| `--no-check-patchlist` | P4 and P5 |
| `--no-check-position` | P6 |
