# check-spec-build-autotools

## Original Requirement

Source: <https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/BuildSystems/autotools>

The `autotools` supplement of the packaging guidelines states the build
dependency that a spec takes on when it selects this build system.

Section "依赖" (Dependencies):

> If you want to use the autotools build system, you need to add these
> BuildRequires, because gcc is preinstalled in the build environment and
> does not have to be declared explicitly.

The section then lists the four dependencies it requires:

```
BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  libtool
BuildRequires:  make
```

The clause uses "need to add", which is MUST level, and it is the only
clause of this page that enumerates its subject explicitly. The rule
therefore reproduces the four names verbatim instead of inferring which
tool a given project happens to use.

Two further sentences of the same page were considered and are **not**
implemented, because neither is machine-decidable or normative:

- "If the packaged source has no `configure` script, do not use this
  command [`autoreconf -fiv`]." This is a MUST NOT, but deciding it needs
  the contents of the source tarball, which a spec file does not carry.
- "We recommend running `autoreconf -fiv` before the configuration part
  (`%conf`)." This is a recommendation (SHOULD at best) and, in the corpus,
  254 of the 682 autotools specs do not do it, so enforcing it would flag
  more than a third of the tree on advisory wording alone.

## Flags

| Flag | Effect |
| --- | --- |
| `--no-check-buildrequires` | disables C1 entirely |
| `--check-dynamic` | reports C1 even when the spec uses `%generate_buildrequires` |

## Checkpoints

| ID | Checkpoint | Strength |
| --- | --- | --- |
| C1 | A spec whose header declares `BuildSystem: autotools` also declares `autoconf`, `automake`, `libtool` and `make` as `BuildRequires` | MUST |

### C1 — autotools build dependencies

When any field block of a spec declares `BuildSystem: autotools`, the spec
must declare all four tools named by the guideline as `BuildRequires`.

The finding names the `BuildSystem` line and the missing tools, in the
order the guideline lists them:

```
demo.spec: BuildSystem: autotools (line 9) requires "autoconf",
"automake", "libtool" and "make" in BuildRequires; missing "libtool"
```

Details that decide the outcome:

- **`gcc` is exempt.** The guideline excludes it in the same sentence that
  states the requirement, because the build environment preinstalls it.
  Declaring it is allowed but never required.
- **Names match exactly.** `autoconf-archive` is a different package and
  does not satisfy `autoconf`. The corpus contains six declarations of
  `autoconf-archive`, so a prefix match would produce false negatives.
- **Matching is case-insensitive** and ignores a version constraint:
  `Autoconf` and `libtool >= 2.4` both count.
- **Any block counts.** `BuildRequires` is a source-package level field and
  RPM merges the declarations of every subpackage block, so a dependency
  written in a `%package` block counts for the top-level spec.
- **Rich dependencies do not count.** A form such as
  `(libtool if gcc)` is conditional at install time and is not a plain
  declaration of the tool.
- **Commented lines and macro bodies do not count.** A `# BuildRequires:`
  line, or a `BuildRequires` inside a multi-line `%global ... %{expand:`
  body, is not a field of the spec.

## Scope notes

Skipped by default: a spec that runs `%generate_buildrequires`. The dynamic
dependency generator can supply a build dependency that no static field
records, so the four names may legitimately be absent from the header. The
guideline does not forbid a static declaration there; the static field is
merely unable to answer the question. `--check-dynamic` turns the check back
on for teams that want it.

Out of scope:

- **Whether the four tools are enough.** The rule never asks for a
  dependency beyond the four named ones; `check-spec-buildrequires` owns the
  remaining dependency questions.
- **Whether the package really builds with autotools.** That needs the
  upstream payload. The rule trusts the declared `BuildSystem` value.
- **The `%conf` / `autoreconf` advice**, for the reason given under
  Original Requirement.
- **Redundant `BuildOption(conf)` flags.** The page states as a fact that
  `%conf` already passes `--disable-silent-rules`, `--disable-rpath` and
  `--docdir=%{_docdir}/%{name}`, but it never forbids repeating them. The
  corpus repeats one of the three in 77 places across 73 files; deriving a
  rule from a statement of fact would be inference, not enforcement.
- **`-n %{name}-%{version}` inside `BuildOption(prep)`.** The page mentions
  the omission while walking through an example rather than as a rule, and
  only 2 specs in the corpus do it.

Measured on the openRuyi corpus at commit
`1bb886cf1dc0dd4932a312f6dfbcae10d924889d`: 6341 specs in total, 682 of
them declaring `BuildSystem: autotools`, and 474 of those omitting at least
one of the four tools (after excluding the 5 specs that use
`%generate_buildrequires`). Per tool: `libtool` 383, `autoconf` 361,
`automake` 354, `make` 225.

No network access and no `rpm` invocation is performed, so the rule works on
a bare checkout.

## Examples

### Passing

```
BuildSystem:    autotools
BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  libtool
BuildRequires:  make
```

### Failing

```
BuildSystem:    autotools
BuildRequires:  autoconf
BuildRequires:  automake
```

```
demo.spec: BuildSystem: autotools (line 9) requires "autoconf",
"automake", "libtool" and "make" in BuildRequires; missing "libtool" and
"make"
```

### Accepted variations

```
BuildRequires:  autoconf >= 2.69
BuildRequires:  Autoconf, Automake, Libtool, Make
BuildRequires:  autoconf-archive
```

The first two lines satisfy the requirement; `autoconf-archive` does not
satisfy `autoconf` and must be accompanied by an `autoconf` declaration.
