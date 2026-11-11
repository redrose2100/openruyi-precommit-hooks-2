# check-spec-source

> Rule ID: `check-spec-source`

## Original Requirement

Source: [openRuyi Packaging Specification · Source](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#source)

The rule covers the source input declarations of a spec: the `Source` field,
the numbered `SourceN` fields and the `%sourcelist` block. Every other field
is out of scope.

The linked supplement [SourceURL](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/sourceurl) is part of the requirement as well; it
defines the `#!RemoteAsset:` / `#!CreateArchive` comment protocol that tells
the build system where the archive comes from and how to verify it.

### Source

- The `Source` field points at the upstream source input of the package.
- A source fetched over the network must be annotated with a
  `#!RemoteAsset:` comment on the line directly above it.
- The generated archive must be verifiable, so the comment carries the
  checksum of the archive.
- A source that is fetched from a version-control repository is not an
  archive yet, so the build system has to create it: the comment needs a
  `#!CreateArchive` line between itself and the `Source` line.
- Several sources are numbered `Source0`, `Source1`, ... starting at 0.
- A set of plain file names may be listed under a `%sourcelist` block.

## Checkpoints

| # | Checkpoint | Requirement | Failure condition | Flag | Default |
| --- | --- | --- | --- | --- | --- |
| 1 | Unique index | Two declarations must not resolve to the same index | `Source` and `Source0`, or `Source1` twice | — | on |
| 2 | Non-empty value | Every source declaration must carry a value | `Source:` with nothing after the colon | — | on |
| 3 | RemoteAsset presence | A network source needs the comment directly above it | An `http`/`https` source with no `#!RemoteAsset:` between it and the previous field, comment or blank line | — | on |
| 4 | Checksum | The `#!RemoteAsset:` of a network source must carry a 64-digit `sha256:` | The comment is bare, or carries another algorithm, or a malformed digest | — | on |
| 5 | CreateArchive required | A VCS fetch needs `#!CreateArchive` | A `#!RemoteAsset:` whose value starts with `git+`, `git:`, `hg`, `svn`, `bzr` or `cvs`, and no `#!CreateArchive` in between | — | on |
| 6 | CreateArchive placement | `#!CreateArchive` sits between the comment and the source | `#!CreateArchive` with no `#!RemoteAsset:` above it, or with a blank line or field before the `Source` line | — | on |
| 7 | No orphan comment | Every `#!RemoteAsset:` must annotate a `Source` | A `#!RemoteAsset:` followed by a non-source field, a patch or nothing | — | on |
| 8 | Field name spelling | The field is spelled `Source` or `SourceN` | The field name is `source`, `SOURCE`, `Sources`, `SourceX`, ... | `--no-check-field-case` | on |
| 9 | Index sequence | `SourceN` indices run from 0 without gaps | `Source0` next to `Source2`, or a block starting at `Source1` | `--no-check-index-sequence` | on |
| 10 | SourceForge host | A SourceForge download uses the documented host | The URL host is `sourceforge.net`, `download.sourceforge.net` or `prdownloads.sourceforge.net` | — | on |
| 11 | Derivable name | `rpm` must be able to derive the tarball name from the URL | The path ends with `/`, or the URL has a query string and no `#/name` fragment | — | on |
| 12 | `%sourcelist` shape | The block stands alone and lists at least one file | `%sourcelist foo.conf` on one line, or a block with no entry before the next section | — | on |

### Scope notes

Every clause below is a real part of the specification that this rule
deliberately does not enforce, or a decision about how the checkpoints above
behave.

- **Local sources are exempt from checkpoints 3 to 5.** A bare file name such
  as `foo.conf` or `%{name}-%{version}.tar.gz` is not fetched over the
  network, so it needs neither a `#!RemoteAsset:` comment nor a checksum. The
  486 corpus specs in this shape are silent by design.

- **Only `http` and `https` count as network sources.** `ftp://` appears 24
  times in the corpus, and the document names `http`/`https` only. Reporting
  `ftp` would be inventing a requirement.

- **"Directly above" allows exactly one intervening line.** The two accepted
  shapes are `#!RemoteAsset:` / `Source` and `#!RemoteAsset:` /
  `#!CreateArchive` / `Source`. A blank line or any other field breaks the
  adjacency, because the generator reads the comment block positionally.

- **An empty `#!RemoteAsset:` is reported by checkpoint 4, not 3.** The
  comment is present but says nothing, which is a checksum defect: the corpus
  has 557 of these, the single largest real defect class.

- **`#!RemoteAsset:` also annotates `Patch` and `Icon` lines.** Checkpoint 7
  therefore only reports a comment that is followed by something that is
  neither a source declaration nor another annotation target.

- **Field order stays out of scope.** Whether the sources come before or
  after `BuildSystem` is `check-spec-basic-fields`'s business; this rule only
  looks at the source declarations themselves.

- **URL reachability stays out of scope.** The hook is offline and never
  performs a request, so a well-formed URL to a host that does not exist
  passes.

- **The document's "add a comment when the name is unclear" clause is not
  automated.** Deciding whether a local file name is self-explanatory needs a
  human reader. 486 corpus specs carry a bare local name with no adjacent
  comment; they stay silent on purpose.

- **`%{url}` is expanded before the network test.** 202 corpus specs write
  `Source0: %{url}/archive/v%{version}.tar.gz`, which the document prefers.
  The prefix is resolved against the `URL` field first, so the source is
  correctly recognised as a network source.

- **Macros are stripped iteratively.** RPM macros nest, as in
  `%{?rc:-%{rc}}`; one substitution pass would leave a `?` behind and report a
  phantom query string on `llvm22` and `llvm23`.

## Examples

### Network source without a checksum (checkpoint 4)

```spec
#!RemoteAsset
Source0:        https://example.org/foo-1.0.tar.gz
```

```
x.spec: "#!RemoteAsset:" (line 5) is empty; it must carry the checksum of
the archive, as in "#!RemoteAsset:  sha256:<64 hex digits>"
```

### Corrected

```spec
#!RemoteAsset:  sha256:0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c4b5a69788796a5b4c3d2e1f0
Source0:        https://example.org/foo-1.0.tar.gz
```

### VCS fetch without CreateArchive (checkpoint 5)

```spec
#!RemoteAsset:  git+https://git.example.org/foo.git#v%{version}
Source0:        foo-%{version}.tar.gz
```

```
x.spec: "#!RemoteAsset: git+https://git.example.org/foo.git#v%{version}"
(line 5) fetches from a version-control repository, so "#!CreateArchive"
must come between it and Source0 (line 6)
```

### Corrected

```spec
#!RemoteAsset:  git+https://git.example.org/foo.git#v%{version}
#!CreateArchive
Source0:        foo-%{version}.tar.gz
```

### Index gap (checkpoint 9)

```spec
Source0:        foo-1.0.tar.gz
Source2:        foo-extra-1.0.tar.gz
```

```
x.spec: source indices are not numbered from 0 without gaps; index 1 is
missing (first declaration on line 5)
```

### SourceForge host (checkpoint 10)

```spec
Source0:        https://download.sourceforge.net/foo/foo-1.0.tar.gz
```

```
x.spec: Source0 (line 5) uses the SourceForge host "download.sourceforge.net";
write "downloads.sourceforge.net" instead, which is the host the project
publishes, as in
"https://downloads.sourceforge.net/foo/foo-1.0.tar.gz"
```

### Query string with no fragment (checkpoint 11)

```spec
Source0:        https://example.org/download.cgi?file=foo
```

```
x.spec: Source0 (line 5) gives rpm a query string and no URL fragment, so
the tarball name cannot be derived; state the file name in a URL fragment,
as in "https://example.org/download.cgi#/foo-1.0.tar.gz"
```

### Corrected

```spec
Source0:        https://example.org/download.cgi?file=foo#/foo-1.0.tar.gz
```

### `%sourcelist` (checkpoint 12)

```spec
%sourcelist foo.conf
bar.conf
```

```
x.spec: "%sourcelist" (line 5) must be written alone on its line; list the
file names on the following lines
```

## Corpus result

Running the rule over the 6341 specs of
`openRuyi-Project/openRuyi` at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d` reports **590 findings in 485
specs**.

| Checkpoint | Findings | Affected shape |
| --- | --- | --- |
| 4 Checksum (empty comment) | 557 | `#!RemoteAsset` written bare |
| 9 Index sequence | 19 | `Source1` removed after a `.sig` file was dropped |
| 10 SourceForge host | 11 | `download.sourceforge.net`, `prdownloads.…` |
| 1 Unique index | 1 | `libffcall` declares `Source0` twice |
| 5 CreateArchive required | 1 | `ovmf` omits it for a `git+` fetch |
| 11 Derivable name | 1 | `findutils` uses a query string with no fragment |

Checkpoints 2, 3, 6, 7, 8 and 12 report nothing on the corpus: the packagers
write clean local sources, spell the field correctly and use `%sourcelist`
properly. The 571 difference against
`--no-check-field-case --no-check-index-sequence` is the 19 index findings,
which are also the only stylistic class.
