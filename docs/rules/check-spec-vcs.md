# check-spec-vcs

> Rule ID: `check-spec-vcs`

## Original Requirement

Source: [openRuyi Packaging Specification · VCS](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#vcs)

The rule covers **only** the `VCS` field of a spec, including the `VCS`
lines inside `%package` subpackage blocks. Every other field is out of
scope.

### VCS

- When the `URL` field already points at the source code repository, `VCS`
  may be omitted.
- When the `URL` field is not a source repository link, `VCS` must not be
  omitted.
- When `VCS` cannot be omitted but no usable source repository link exists,
  the comment `# VCS: No VCS link available` must be written at the position
  of the `VCS` field, and the `# VCS:` prefix must be preserved.
- When a usable git repository does exist, the `VCS` value must be an
  address that can be used for `git clone`.

The `URL` section of the same document requires `URL` to be the official
website when one exists, which in practice is the common reason `VCS` is
required. That field is enforced by `check-spec-url`, not here.

## Checkpoints

| # | Checkpoint | Requirement | Failure condition | Flag | Default |
| --- | --- | --- | --- | --- | --- |
| 1 | Conditional presence | `VCS` may be omitted only when `URL` is a source repository link; otherwise the field or the documented placeholder must be written | The main field block has neither a `VCS` field nor a `# VCS:` placeholder, and `URL` is not a repository link | `--no-check-doc-site` | on |
| 2 | Placeholder wording | The placeholder text must be exactly the documented sentence | A `# VCS:` comment whose text is not `No VCS link available` | — | on |
| 3 | Mutual exclusion | A placeholder and a real field must not coexist | The spec has both a `VCS` field and a `# VCS:` placeholder | — | on |
| 4 | Non-empty value | A declared `VCS` must carry a value | `VCS:` with nothing after the colon | — | on |
| 5 | No macro concatenation | The value must not be built from macros | After removing `%XX` percent escapes, the value still contains `%` | — | on |
| 6 | Cloneable address | The value must be an address usable to clone the source | The value is neither an absolute URL nor an scp-like `user@host:path` | — | on |
| 7 | Field name spelling | The field is spelled `VCS`, as everywhere in the specification | The field name is `VCs`, `Vcs`, `vcs`, ... | `--no-check-field-case` | on |

### Scope notes

Every clause below is a real part of the specification that this rule
deliberately does not enforce, or a decision about how the checkpoints above
behave.

- **Checkpoint 1 is a decision chain, not a presence test.** The rule asks,
  in order: is `VCS` declared? is the placeholder written? is there a `URL`
  at all? is the `URL` value usable? Only when every answer is "no" does it
  report. This is what makes the field optional for
  `https://github.com/owner/project` and required for
  `https://www.kernel.org/`.

- **When `URL` is missing or empty, checkpoint 1 stays silent.** A missing
  `URL` is `check-spec-url`'s finding, and without a `URL` the `VCS`
  requirement cannot be decided at all. One defect must not have two owners.

- **When `URL` is built from a macro, checkpoint 1 stays silent.** An
  unexpanded value cannot be classified as a repository link or not, and it
  is already `check-spec-url`'s finding. This affects exactly four corpus
  specs: `pocketfft`, `psutils`, `python-azure-storage-blob` and `xnnpack`.

- **What counts as a repository link.** A `URL` value is a repository link
  when it ends in `.git`, or the host is a known forge with enough path
  depth, or the host announces itself as a source host and the path is not
  empty. Known forges and their minimum path depth:

  | Host | Depth | Host | Depth |
  | --- | --- | --- | --- |
  | `github.com` | 2 | `salsa.debian.org` | 2 |
  | `gitlab.com` | 2 | `invent.kde.org` | 2 |
  | `codeberg.org` | 2 | `src.fedoraproject.org` | 2 |
  | `bitbucket.org` | 2 | `git.sr.ht` | 2 |
  | `pagure.io` | 1 | `hg.sr.ht` | 1 |
  | `sourceware.org` | 1 | `git.kernel.org` | 3 |

  A host whose name starts with `git`, `gitlab`, `gitea`, `gogs`, `forgejo`,
  `hg`, `svn`, `cvs`, `bzr`, `code`, `repo` or `cgit`, or that ends in
  `googlesource.com` or `sr.ht`, is a source host and needs a non-empty
  path. Everything else - a project website, a bare host, a documentation
  site - is not a repository link, which is what makes `VCS` required.

- **Documentation and package-index sites are not repository links.**
  `*.github.io`, `*.gitlab.io`, `*.readthedocs.io`, `crates.io`, `docs.rs`,
  `lib.rs`, `metacpan.org`, `pypi.org` and `pypi.python.org` describe a
  package rather than host its source. They therefore require `VCS`, which
  is where 538 of the 800 corpus findings come from. A repository that
  accepts that reading can pass `--no-check-doc-site` to treat those hosts
  as sufficient; checkpoint 1 then drops from 800 to 262 findings.

- **Checkpoint 6 accepts three shapes.** An scp-like `user@host:path` as
  `git clone` accepts it; a plain absolute URL, which covers `git://`,
  `https://`, `ssh://` and `svn://` directly; and the same URL behind a
  version-control prefix, as in `git:https://...` or `git+https://...`. The
  last shape is the one the specification's own example uses, and the plain
  form is what 1002 corpus values use, so both must pass.

- **Checkpoint 5 inverts the usual macro escape hatch.** Every other rule in
  this repository treats a macro-valued field as unjudgeable and stays
  silent. Here the specification requires an address usable for `git clone`,
  which an unexpanded macro is not, so a macro-valued `VCS` reports
  checkpoint 5 and **skips checkpoint 6**. One defect produces one finding.

- **Percent escapes are not macros.** `%2B` and friends are URL encoding.
  The rule strips `%[0-9A-Fa-f]{2}` before testing for a remaining `%`.

- **Checkpoint 7 does not steal a defect from checkpoints 4-6.** A `VCs:`
  field still has its value validated, because a wrong field name does not
  make the value irrelevant. A `VCs:` field also satisfies checkpoint 1, so
  the spec is not additionally reported as missing the field.

- **Checkpoint 1 is scoped to the main field block.** The block ends at the
  first recognised section header, so a `VCS` that lives only in a
  `%package` subpackage does not satisfy the main package requirement. A
  `%global` or `%define` line is a macro invocation, not a section, and does
  not end the block.

- **Every `VCS` line is checked, subpackage blocks included.** Checkpoints
  2-7 apply to every `VCS` line in the file, not just the main package one.

- **A commented-out field is not the placeholder.** `# VCS: git:https://...`
  and `# VCS: %{vcs}` are disabled fields. They do not satisfy checkpoint 1,
  do not trigger checkpoint 2, and never conflict with a real field under
  checkpoint 3. Only a commented `# VCS:` line whose text is prose is
  treated as the documented placeholder.

- **A commented-out field never feeds the value checkpoints.** The field must
  start at column 0, so `# VCS: FIXME` is invisible to checkpoints 4-6.

- **Repeated findings are de-duplicated.** A spec with several identical
  `VCS` values reports one finding, not one per line, following the
  repository-wide `_dedup` contract.

- **Not enforced: field ordering.** `check-spec-basic-fields` owns field
  order and its `FIELD_ORDER` already contains `VCS`.

- **Not enforced: whether the `VCS` host matches the `URL` host.** A spec
  can legitimately combine an official website `URL` with a forge `VCS`, and
  a mirror can legitimately differ from the `URL` host.

- **Not enforced: whether the repository still exists.** Deciding whether a
  repository is "usable" needs the network, which a pre-commit hook must not
  require.

- **Other fields are out of scope.** `URL` is enforced by
  `check-spec-url`, `Name` by `check-spec-name`, `Version` by
  `check-spec-version`, `Release` by `check-spec-release`, `Summary` by
  `check-spec-summary`, `License` by `check-spec-license`, and the basic
  field layout by `check-spec-basic-fields`; this rule is limited to `VCS`.

## Examples

Passing specs:

```
URL:            https://github.com/owner/project          # VCS may be omitted

URL:            https://www.example.org/
VCS:            git:https://git.example.org/project.git

URL:            https://www.example.org/
# VCS: No VCS link available
```

Passing `VCS` values:

```
VCS:            git:https://git.example.org/project.git
VCS:            git://git.example.org/project.git
VCS:            https://github.com/owner/project
VCS:            git+https://git.example.org/project.git
VCS:            hg:https://hg.example.org/project
VCS:            svn:https://svn.example.org/project/trunk
VCS:            git@github.com:owner/project.git
```

Failing specs:

```
URL:            https://www.kernel.org/       # no VCS and not a repo link
URL:            https://pypi.org/project/foo  # package index, not a repo
```

Failing values:

```
VCS:                              # empty value
VCS:            upstream          # not a cloneable address
VCS:            example.org/foo   # no scheme
VCS:            git:https://git.example.org/%{name}.git   # macro-built
VCs:            git:https://git.example.org/foo.git       # wrong spelling
# VCS: no vcs link                 # wrong placeholder wording
```

## Corpus result

Scanning `openRuyi` at `1bb886c` (6341 specs) produces 815 findings in 815
specs, with no spec hit twice: 800 conditional-presence, 14 placeholder
wording, 1 field-name spelling, and nothing for checkpoints 3, 4, 5 and 6.
With `--no-check-doc-site`, checkpoint 1 drops from 800 to 262.

The 800 checkpoint-1 findings cluster on a few non-repository hosts:
`metacpan.org` 403, `gtk-rs.org` 50, `pypi.org` 35, `lib.rs` 19,
`sequoia-pgp.org` 18, `rust-random.github.io` 14, `tokio.rs` 13,
`rust-lang.github.io` 13, `crates.io` 11 and `icu4x.unicode.org` 9.
