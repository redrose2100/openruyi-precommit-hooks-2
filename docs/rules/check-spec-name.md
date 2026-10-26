# check-spec-name

> Rule ID: `check-spec-name`

## Original Requirement

Source: [openRuyi Packaging Specification · Name](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#name)
and [openRuyi Packaging Specification · Naming](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/Naming)

The rule covers **only** the `Name` field of a spec. Subpackage names are read
solely to detect a collision with the main package name; no other field is
inspected.

### Name

- A spec **must** declare a `Name`.
- The name **should** be lowercase and **should** prefer the hyphen (`-`) over
  the underscore (`_`).

### Naming — general rules

- The name normally **should** follow the upstream project's official name.
- A name **must** use the hyphen (`-`) between its parts, with a few documented
  exceptions; upstream names that naturally contain an underscore, such as
  `nss_wrapper`, are one of them.
- Encoding an ABI (SONAME major) or an upstream major version into the name is
  not allowed. A digit that is part of the upstream official name (`libxml2`)
  is not such an encoding.

### Naming — name conflicts

- Conflicting package names are absolutely forbidden, **including names that
  differ only in case**.

### Naming — case sensitivity

- Case sensitivity is not mandatory, but case **should** only be used where
  necessary: if the upstream maintainer calls the application `RapidCopy`, the
  package name should be `RapidCopy`; otherwise the default is lowercase.
- Perl modules are the exception — CPAN groups and types should be
  capitalized.

## Checkpoints

| # | Checkpoint | Requirement | Failure condition | Flag | Default |
| --- | --- | --- | --- | --- | --- |
| 1 | Presence | The spec must declare a non-empty `Name` | No `Name:` line, or the value is empty | — | on |
| 2 | Character set | The value may only contain `A-Za-z0-9._+-` | Any other character, including whitespace | — | on |
| 3 | Delimiters | The value must not begin or end with a separator | The first or last character is `-`, `_` or `.` | — | on |
| 4 | Repeated separators | The value must not contain two separators in a row | `--`, `__`, `..`, `-_`, `_-`, `._`, `_.`, `-.` or `.-` appears | — | on |
| 5 | Name conflict | A subpackage must not reuse the main package name, compared case-insensitively | A resolved `%package` name equals the main name | — | on |
| 6 | Lowercase | The value should be lowercase unless the upstream name is capitalized | The value contains an uppercase letter and does not start with `perl-` | `--no-check-case` | on |
| 7 | Hyphen | The value should use `-` rather than `_` | The value contains `_` | `--check-separator` | off |
| 8 | Source-URL case | The value should be spelled the way the project's own download URL spells it | No `Source` URL spells the value as written, but at least one spells it with a different case | `--no-check-upstream-case` | on |

### Scope notes

Every clause below is a real part of the specification that this rule
deliberately does not enforce. The measured counts come from a scan of the
6149 spec files in the openRuyi `SPECS` tree.

- **Checkpoint 6 is on by default**, which is a decision rather than a reading
  of the text: the case-sensitivity section says explicitly that case
  sensitivity is not a mandatory requirement. It is enabled because the
  sentence that follows is a real requirement with a real failure mode —
  silently lowercasing a package whose upstream name is capitalized.
  The scan finds 425 uppercase main names; 390 of them begin with `perl-` and
  are excluded by checkpoint 6 itself, as the specification requires. The
  remaining **35** are not all of the same kind, and checkpoint 8 is what tells
  them apart: **31** are silenced because the project's own download URL spells
  them exactly, **2** would be silenced by checkpoint 6 but are **reported** by
  checkpoint 8 because their URL spells a different case, and **2** cannot be
  decided from the spec at all, so checkpoint 6 still reports them:

  | Group | Count | Names |
  | --- | --- | --- |
  | URL confirms the spelling, silent | 31 | `Catch2`, `ModemManager`, `NetworkManager`, `PackageKit`, `PackageKit-Qt`, `SDL3`, `libICE`, `libSM`, `libX11`, `libXScrnSaver`, `libXau`, `libXcomposite`, `libXcursor`, `libXdamage`, `libXdmcp`, `libXext`, `libXfixes`, `libXfont2`, `libXft`, `libXi`, `libXinerama`, `libXmu`, `libXpresent`, `libXrandr`, `libXrender`, `libXres`, `libXt`, `libXtst`, `libXv`, `libXxf86vm`, `unixODBC` |
  | URL contradicts the spelling | 2 | `Xwayland` (URL says `xwayland`), `Aflplusplus` (URL says `AFLplusplus`) |
  | No usable URL | 2 | `SDL2`, `python-Whoosh` |

  The two unresolved ones are unresolved for a different reason each, and each
  is a lowercasing of the first letter rather than the upstream form: `SDL2`
  sits on a repository named `SDL` whose `release-%{version}.tar.gz` artefact
  encodes no `SDL2` at all, and `python-Whoosh` writes `python-%{srcname}` with
  a `%{srcname}` that conflicts with the PyPI file name, so the two spellings
  cancel out. A packager should confirm each of them by hand, which is what
  `--verify-upstream` is for.

- **Checkpoint 8 is what makes checkpoint 6 usable.** It reads the same
  `Source` lines the `rpm` build reads, so the capitalization question is
  answered by evidence inside the spec instead of by a human. When a URL spells
  the value exactly, both checkpoints stay silent; when it spells another case,
  checkpoint 8 reports the mismatch and checkpoint 6 does **not** also fire,
  because the two messages would contradict each other. Checkpoint 8 is
  therefore bidirectional: it also catches a lowercase name against a
  capitalized artefact, which checkpoint 6 could never see. The scan finds 22
  such names —
  `cunit`, `docbook2x`, `fp16`, `freerdp`, `fxdiv`, `imagemagick`, `imath`,
  `judy`, `libidl`, `libraw`, `lmdb`, `lvm2`, `openblas`, `opencc`, `opensc`,
  `opensp`, `orbit2`, `safeint`, `scons`, `spirv-llvm-translator`, `wavpack`
  and `waybar` —
  each of which is a current defect in the tree rather than an accepted
  exception. `safeint` is a good illustration of why the `URL:` line has to be
  expanded before it is trusted: it declares
  `URL: https://github.com/dcleblanc/SafeInt` with a capitalized path and
  `Source0: %{url}/archive/%{version}/SafeInt-%{version}.tar.gz`, so the
  evidence only becomes visible once `%{url}` is bound.

- **Checkpoint 8 reads `Source\d*` and nothing else.** The `URL:` line is
  deliberately excluded as evidence: a forge normalises that path to lower
  case while the tarball keeps the real spelling, so `libXScrnSaver` declares
  `URL: https://gitlab.freedesktop.org/xorg/lib/libxscrnsaver` next to a
  correctly capitalized `Source0`. Trusting `URL:` would have reported several
  `libX*` specifications that are in fact correct. The `URL:` value is still
  *bound* so that a relative `Source0` such as
  `%{url}/releases/individual/lib/%{name}-%{version}.tar.xz` expands to a real
  URL before it is examined, which is what keeps `libXft` at its correct
  spelling.

- **Checkpoint 8 is not the network check.** It reads the spec and nothing
  else: it never opens a socket, so it stays usable as a pre-commit hook. The
  optional `--verify-upstream` mode described below adds a real network probe
  for the two unresolved names; it is a separate, opt-in command and is
  **not** registered as a hook.

  With checkpoints 1 to 8 at their defaults the scan reports **27** findings
  over the 6149-spec tree, down from 36 before checkpoint 8 existed: the 1
  checkpoint-4 finding, the 2 unresolved case findings and the 24
  checkpoint-8 findings. Passing `--no-check-upstream-case` reproduces the old
  behaviour exactly, all 36 of them.

- **Checkpoint 7 is off by default.** The scan finds 25 **resolved** main
  names containing `_`: `nss_wrapper`, `pam_wrapper`, `socket_wrapper`,
  `priv_wrapper`, `uid_wrapper`, `lm_sensors`, `wpa_supplicant`,
  `createrepo_c`, `libatomic_ops`, `sg3_utils`, `volume_key`, `magic_enum`,
  `fast_float`, `isa-l_crypto`, `libnetfilter_conntrack`,
  `libnetfilter_cthelper`, `libnetfilter_cttimeout`, `libnetfilter_queue`,
  `libnetfilter_log`, `libnetfilter_acct`, `perl-OLE-Storage_Lite`,
  `perl-PerlIO-utf8_strict`, `perl-Text-CSV_XS`, `python-annotated_types` and
  `python-mistral_common`. Every one is either an upstream name that
  naturally contains an underscore (an explicit exception in the separator
  section) or a CPAN/PyPI distribution name that does, so none is a hyphen
  that should have been written as an underscore. The check is therefore
  opt-in, and a repository that enables it should expect these.

  Names whose underscore only exists inside an unresolved macro —
  `python-%{pypi_name}`, `llvm%{maj_ver}`, `dotnet%{dotnet_major}` — are
  **not** reported, because checkpoint 7 is skipped for a macro-valued name.
  One of the 25 is an inconsistency with its own directory name and is worth
  reporting: `python-annotated_types` lives in `python-annotated-types`.
  `python-mistral_common` has the same name in both places, so only the
  separator convention itself is at issue there.

- **Checkpoints 6 and 8 interact with checkpoint 7.** `--check-separator` is
  orthogonal, so enabling it takes the default 27 to 52: the 25 underscore
  names plus the 27. Adding `--no-check-case` brings that to 50, because
  `SDL2` and `python-Whoosh` stop being reported by checkpoint 6 while the
  checkpoint-8 findings survive — a separator flag never silences a name whose
  download URL proves the spelling wrong.

- `+` is treated as an **ordinary character**, not a separator. `libsigc++` is
  a legitimate C++ library whose upstream name contains `++`, and the separator
  section only defines `-`, `_` and `.` as separators. A name such as
  `+foo` or `foo+` is consequently not reported by checkpoint 3.

- `go-github-sean--seed` is reported by checkpoint 4 on the current tree, and
  is an **accepted true positive**: the specification has no exception for a
  doubled hyphen, and the upstream repository name genuinely uses `--`. It is
  reported rather than allowlisted so that the exception stays visible.

- **Not enforced: encoding an ABI or version into the name.** The clause is a
  negative requirement over an unbounded set of plausible names. `libxml2` is
  correct because the digit is upstream's, while `libfoo2` would be wrong; the
  two are indistinguishable without an upstream name lookup, so any static
  check would be a guess.

- **Not enforced: `Provide`-based upstream aliases.** The `Provide` section
  says providing the original upstream name when it differs is optional, so
  there is nothing to fail on.

- **Not enforced: cross-file name conflicts.** The hook receives the staged
  files of one repository, but the checkpoint-5 comparison is deliberately
  limited to a single spec, where the main name and its own subpackages are
  both available. The scan reports zero **within-file** and zero **cross-file**
  case-insensitive collisions over the current tree, so the current corpus is
  already clean; a repo-wide conflict check still needs a separate tool, not a
  per-file hook.

- **Not enforced: doc subpackage, font package, perl and Python prefixes.**
  `%{name}-doc`, `fonts-[fontname]`, `perl-CPANDIST` and the `python-` prefix
  are naming rules for *sub*packages or for a narrow package class, and a spec
  is allowed to have no subpackage at all. They are out of the `Name` field
  scope.

- **Macro-valued names.** `%{name}` is expanded to the main name, and any
  `%global` / `%define` value is expanded when it is known. A value that still
  contains `%` after expansion could be anything, so checkpoints 2, 3, 4, 6 and
  7 are skipped for it and checkpoint 5 skips that entry. This is what keeps
  `python-%{pypi_name}` clean.

- The `Name` line is matched **per line**, never with a whole-file search: a
  non-`MULTILINE` pattern applied to the entire text matches nothing, and that
  mistake silently produced zero findings during the analysis for this rule.

## Usage

Add to `.pre-commit-config.yaml`:

```yaml
-   repo: https://github.com/openRuyi-Project/openruyi-precommit-hooks
    rev: v0.1.0   # use the latest tag
    hooks:
    -   id: check-spec-name
```

A repository that has accepted the upstream capitalization of some of its
packages can turn checkpoint 6 off. This is rarely needed now that checkpoint 8
reads the download URLs, because the names that are genuinely upstream
spellings are silenced on their own; `--no-check-case` is for a repository that
wants no case findings at all:

```yaml
    -   id: check-spec-name
        args: [--no-check-case]
```

A repository that wants the pre-checkpoint-8 behaviour back — every uppercase
name reported, no download URL consulted — can turn checkpoint 8 off, which
exactly reproduces the older result:

```yaml
    -   id: check-spec-name
        args: [--no-check-upstream-case]
```

A repository that has decided its names must use hyphens everywhere can turn
checkpoint 7 on:

```yaml
    -   id: check-spec-name
        args: [--check-separator]
```

It can also be used as a standalone command:

```console
$ check-spec-name path/to/foo.spec
```

An exit code of 1 means some files do not meet the requirements; 0 means all
files pass.

### Verifying the unresolved names online

Checkpoint 8 settles every name whose download URL embeds the artefact name.
The 2 names it cannot settle — `SDL2` and `python-Whoosh` on the current tree —
are exactly the ones where the URL points at an API endpoint or names no
artefact, so `--verify-upstream` asks the host itself:

```console
$ check-spec-name --verify-upstream path/to/foo.spec
$ check-spec-name --verify-upstream --upstream-workers 16 \
      --upstream-timeout 20 specs/*/*.spec
```

The mode probes two channels and stops at the first verdict:

1. The `Source` URL, requested with the exact bytes the spec writes. A `200`
   from a case-sensitive host proves the spelling, because a different case
   would be a different path and would have returned `404`; a `404` or a
   transport failure proves nothing and falls through to the second channel.
2. The package index that owns the host — the GitHub API for `github.com`, the
   GitLab API for any host containing `gitlab`, PyPI for `*.pythonhosted.org`
   and `pypi.org`, crates.io for `*.crates.io`. The lookup is made
   case-insensitively and compared case-sensitively, which is the only signal a
   case-insensitive host provides.

A confirmed name prints nothing. A mismatch is printed as an error. A name that
no channel could decide is **also** printed as an error rather than silently
dropped, because an unchecked name is not a passing one:

```
foo.spec: Name "Xwayland" (line 8) is not spelled the way upstream writes it (https://xorg.freedesktop.org/archive/individual/xserver/xwayland-24.1.11.tar.xz returns 200 and spells "xwayland")
foo.spec: Name "python-Whoosh" (line 9) could not be verified upstream (the spec declares no http Source URL)
```

GitHub rate-limits unauthenticated traffic to 60 requests per hour, while the
current tree alone holds 1581 GitHub URLs, so set `GITHUB_TOKEN` (or
`GH_TOKEN`) before a repository-wide run. The token is read from the
environment and sent as a bearer header to the GitHub API; no other host
receives it. `--upstream-workers` (default 8) bounds the thread pool and
`--upstream-timeout` (default 10 seconds) bounds each request.

This mode opens sockets, so it is deliberately **not** registered in
`.pre-commit-hooks.yaml` and must not be used as a pre-commit hook.

## Examples

### Pass ✅

```spec
Name:           foo
Version:        1.0
```

### Pass ✅ (upstream name with a plus, and a perl name)

```spec
Name:           libsigc++
Version:        2.12.0
```

```spec
Name:           perl-Scalar-List-Utils
Version:        1.63
```

### Pass ✅ (macro-valued name and a derived subpackage)

```spec
%global pypi_name example

Name:           python-%{pypi_name}
Version:        1.0

%package        devel
Summary:        Development files

%package -n %{name}-tools
Summary:        Tools
```

### Fail ❌ (missing name)

The expected output for this example is produced with the default flags.

```spec
Version:        1.0
```

```
foo.spec: Name field is missing
```

### Fail ❌ (invalid character)

```spec
Name:           foo bar
Version:        1.0
```

```
foo.spec: Name "foo bar" (line 1) contains an invalid character ' '
```

### Fail ❌ (trailing separator)

```spec
Name:           foo-
Version:        1.0
```

```
foo.spec: Name "foo-" (line 1) must not start or end with a separator
```

### Fail ❌ (repeated separator)

```spec
Name:           go-github-sean--seed
Version:        1.0
```

```
foo.spec: Name "go-github-sean--seed" (line 1) must not contain consecutive separators "--"
```

### Fail ❌ (duplicate name)

```spec
Name:           foo
Version:        1.0

%package -n foo
Summary:        Duplicate of the main package
```

```
foo.spec: duplicate package name "foo" (line 4), already used by the main package (line 1)
```

### Pass ✅ (name confirmed by the download URL)

`libX11` is capitalized, but the spec's own `Source0` spells it the same way,
so checkpoint 8 supplies the evidence checkpoint 6 was asking for and nothing
is reported. This is the shape of the 30 accepted `libX*`, `Catch2`,
`PackageKit`, `ModemManager`, `NetworkManager` and `SDL3` style names in the
openRuyi tree.

```spec
Name:           libX11
Version:        1.8.7
Source0:        https://www.x.org/pub/individual/lib/libX11-1.8.7.tar.xz
```

### Fail ❌ (name contradicts the download URL)

`Xwayland` is capitalized, but the `Source` URL it downloads from carries a
`xwayland-24.1.11.tar.xz` artefact. Checkpoint 8 reports the mismatch and
checkpoint 6 stays quiet, because the two findings would contradict each other.

```spec
Name:           Xwayland
Version:        24.1.11
Source0:        https://xorg.freedesktop.org/archive/individual/xserver/xwayland-24.1.11.tar.xz
```

```
foo.spec: Name "Xwayland" (line 1) is not spelled the way its Source URLs do; upstream writes "xwayland"
```

### Fail ❌ (name contradicts the download URL, other direction)

The check is bidirectional, so a lowercase name against a capitalized artefact
is reported too — the direct opposite of the `libX11` case above.

```spec
Name:           openblas
Version:        0.3.31
Source0:        https://github.com/OpenMathLib/OpenBLAS/archive/refs/tags/v0.3.31.tar.gz
```

```
foo.spec: Name "openblas" (line 1) is not spelled the way its Source URLs do; upstream writes "OpenBLAS"
```

### Fail ❌ (uppercase, default flags)

With no `Source` URL there is nothing for checkpoint 8 to compare against, so
the plain case rule stands. A repository that ships `libX11` without a
downloadable `Source` should either add one or run with `--no-check-case`.

```spec
Name:           libX11
Version:        1.8.7
```

```
foo.spec: Name "libX11" (line 1) contains uppercase characters; the default is lowercase unless the upstream project capitalizes its name
```

### Fail ❌ (underscore, with `--check-separator`)

```spec
Name:           nss_wrapper
Version:        1.1.15
```

```
foo.spec: Name "nss_wrapper" (line 1) contains "_"; the separator must be "-" unless the upstream name naturally contains an underscore
```
