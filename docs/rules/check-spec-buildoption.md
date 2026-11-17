# check-spec-buildoption

Validate the `BuildOption` declarations of an openRuyi spec file.

## Original Requirement

### Source A — Packaging guidelines, `BuildOption (optional)`

<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/>

The `BuildOption (optional)` subsection of the main guidelines defines the
field in five clauses, rendered here in English:

1. When extra arguments are needed for a specific build stage, a spec may use
   the `BuildOption(<stage>):` field.
2. The field and its argument **must** be separated by two spaces.
3. Multiple arguments **must** be declared on separate lines.
4. When the field is used, it **should** sit between `BuildSystem` and
   `BuildRequires`.
5. The writing order **should** follow the RPM build process, i.e. `%build`,
   then `%install`, then `%check`.

### Source B — `BuildSystems` supplement, passing extra arguments

<https://www.openruyi.cn/zh-Hans/docs/guide/buildsystems/>

The supplement fixes the syntax, states that the tag may appear any number of
 times for one section, notes that the stage name is syntactically omissible
but that packagers are required to write it, and repeats that the colon and
the option string are separated by two spaces. It also carries the canonical
sample, which repeats one stage and mixes a single flag with a bare word list:

```text
BuildOption(conf):  --enable-zsh-secure-free
BuildOption(conf):  --enable-gdbm
BuildOption(build):  all info html
BuildOption(install):  install.info
BuildOption(install):  fndir=%{_datadir}/%{name}/functions
BuildOption(install):  runhelpdir=%{_datadir}/%{name}/help
```

### Source C — `Patch and %patchlist` supplement

<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/#patch-and-patchlist>

The Patch section documents `BuildOption(prep)` as the way to override the
strip level (`-p0`), and states that when a spec carries `BuildOption`, the
patch list should sit between `BuildSystem` and `BuildOption`. `prep`
therefore runs before `conf`, which the stage ranking reflects.

### Strength summary

| Clause | Wording | Level |
| --- | --- | --- |
| Field name | Section title and every sample line | Implied |
| Stage present | The supplement requires the stage to be written | MUST |
| Stage shape | `<stage>` placeholder of the syntax line | Implied |
| Two-space separator | Clause 2 uses a must-level verb | MUST |
| Argument present | Clause 3 requires every argument to be declared | MUST |
| Position window | Clause 4 uses a should-level verb | SHOULD |
| Stage order | Clause 5 uses a should-level verb | SHOULD |

## Flags

| Flag | Disables |
| --- | --- |
| `--no-check-field-case` | B1, the spelling of the field name |
| `--no-check-stage` | B2 and B3, the presence and shape of the stage |
| `--no-check-spacing` | B4 and B5, the separator and the argument |
| `--no-check-position` | B6, the position window |
| `--no-check-order` | B7, the stage order |

## Checkpoints

| ID | Checkpoint | Source | Strength |
| --- | --- | --- | --- |
| B1 | The field is spelled `BuildOption`. | A title, A/B samples | Implied |
| B2 | The stage argument is present. | A1, B | MUST |
| B3 | The stage is one bare lowercase token. | A1 syntax | Implied |
| B4 | Exactly two spaces separate the colon from the argument. | A2, B | MUST |
| B5 | The argument is not empty. | A3 | MUST |
| B6 | The field sits in a header field block, after `BuildSystem` and before `BuildRequires`. | A4, C | SHOULD |
| B7 | The stages are written in the RPM build process order. | A5, C | SHOULD |

### Scope notes

- Clause 3 ("multiple arguments on separate lines") is **not** enforced. A
  single argument is routinely written as a flag plus its value (`-G Ninja`),
  as an assignment (`CFLAGS="%{optflags} -fno-strict-aliasing"`), or as a
  command substitution (`--with-gssapi=$(krb5-config --prefix)`), and the
  official sample writes `BuildOption(build):  all info html`. Splitting a
  line into arguments therefore needs the option grammar of the individual
  build system, so the rule never counts arguments per line.
- The stage set is open. B3 checks the shape of the stage rather than a
  closed whitelist, and B7 only ranks the documented stages, so a newer RPM
  stage such as `generate_buildrequires` is never a finding.
- Duplicate declarations are legal. The supplement says that the field may
  appear any number of times for one stage, so repetition is not reported.
- B6 compares against the **first** `BuildSystem` and the **first**
  `BuildRequires` of the block, because `BuildRequires` is commonly repeated
  once per dependency. A boundary the block never writes is not reported.
- Each `%package` block is inspected on its own, because a subpackage repeats
  its own `BuildSystem`, `BuildRequires` and `BuildOption` window.
- Only a column zero field is recognised, mirroring the sibling rules, so an
  indented mention inside a `%description` body is not a field.
- Whether an option is valid for its stage, whether it duplicates another
  option, whether it needs shell quoting, and whether it belongs to the
  declared `BuildSystem` all need the build recipe or the build environment,
  so none of them is checked. No network access and no `rpm` invocation is
  performed.

## Examples

Passing spec:

```text
BuildSystem:    autotools

BuildOption(prep):  -p0
BuildOption(conf):  --enable-foo
BuildOption(conf):  --disable-bar
BuildOption(build):  %{?_smp_mflags}
BuildOption(install):  DESTDIR=%{buildroot}
BuildOption(check):  --verbose

BuildRequires:  gcc
```

B1 — the field is misspelled:

```text
foo.spec: BuildOption field (line 10) is spelled "Buildoption"; write "BuildOption"
```

B2 — the stage is missing or empty:

```text
foo.spec: BuildOption (line 10) omits the stage; write "BuildOption(<stage>):" with one of prep -> conf -> build -> install -> check
foo.spec: BuildOption (line 10) has an empty stage; write "BuildOption(<stage>):" with one of prep -> conf -> build -> install -> check
```

B3 — the stage is not one bare lowercase token:

```text
foo.spec: BuildOption stage "Conf" (line 10) is not a single bare lowercase stage name; write one token such as "conf" or "install"
```

B4 — the separator is not exactly two spaces:

```text
foo.spec: BuildOption(conf) (line 10) is separated from its argument by 1 space(s) instead of two spaces
foo.spec: BuildOption(conf) (line 10) is separated from its argument by a tab instead of two spaces
```

B5 — the argument is empty:

```text
foo.spec: BuildOption(conf) (line 10) declares no argument; write the option string after two spaces
```

B6 — the field is outside the documented window:

```text
foo.spec: BuildOption(conf) (line 10) must be written after BuildSystem (line 14)
foo.spec: BuildOption(check) (line 20) must be written before BuildRequires (line 9)
foo.spec: BuildOption(install) (line 41) is written outside the header field block; write it before the first section
```

B7 — the stages are out of order:

```text
foo.spec: BuildOption(conf) (line 14) is written after BuildOption(build) (line 10); write the stages in the order prep -> conf -> build -> install -> check
```
