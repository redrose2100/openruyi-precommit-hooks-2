# check-spec-condition-build

> Rule ID: `check-spec-condition-build`

## Original Requirement

Source: [openRuyi Packaging Specification · 条件构建](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/#%E6%9D%A1%E4%BB%B6%E6%9E%84%E5%BB%BA)

The conditional build part of the main specification is short: it defines one
declaration form for optional build switches and states that the older pair
of switch macros should be avoided.

### 条件构建 (Conditional build)

- 当需要定义可选构建开关时，Spec 应当使用 `%bcond`。
  When an optional build switch is needed, the spec **should** define it with
  `%bcond`.
- Spec 应当尽量避免使用 `%bcond_with` 与 `%bcond_without`。
  The spec **should** avoid `%bcond_with` and `%bcond_without`.

The worked example in the specification writes the switch with an explicit
default and then reads it back:

```specfile
%bcond bootstrap 0
%bcond bootstrap 1

%if %{with bootstrap}
# ...
%endif
%if %{without bootstrap}
# ...
%endif
```

Two things follow from the wording and the example:

- The clause talks about *optional build switches*, so its subject is the
  declaration of a switch, not every `%if` in the file.
- The documented shape always carries a default value, and the switch is read
  back through `%{with ...}` / `%{without ...}`.

### Strength summary

Both clauses use 应当 (should), so every checkpoint in this rule is SHOULD
level: a finding is a request to normalise the declaration, not a build
breaker. `%bcond_with` and `%bcond_without` still work, and a hand written
`%define with_foo 1` switch still expands, so the rule reports style and
maintainability debt rather than a defect.

## Flags

| Flag | Effect |
| --- | --- |
| `--no-check-legacy-form` | Do not report `%bcond_with` / `%bcond_without`. |
| `--no-check-manual-switch` | Do not report a `%define` / `%global` style switch. |
| `--no-check-default-value` | Do not report a `%bcond` declared without a value. |

## Checkpoints

| # | Checkpoint | Requirement | Failure condition | Flag | Strength |
| --- | --- | --- | --- | --- | --- |
| C1 | Legacy switch form | An optional build switch is declared with `%bcond` | `%bcond_with foo`, `%bcond_without foo` | `--no-check-legacy-form` | SHOULD |
| C2 | Manual switch macro | An optional build switch is declared with `%bcond` | `%define with_foo 1`, `%global with_foo 0`, `%define _with_foo 1` | `--no-check-manual-switch` | SHOULD |
| C3 | Explicit default value | A `%bcond` declaration carries a default value | `%bcond foo` with nothing after the name | `--no-check-default-value` | SHOULD |

### C1 — Legacy switch form

`%bcond_with foo` declares a switch whose default is off, and
`%bcond_without foo` declares one whose default is on. Both are the form the
specification asks maintainers to move away from, so the message names the
`%bcond` replacement and keeps the original default:

```text
foo.spec: "%bcond_with openssl" (line 12) is the legacy switch form;
write "%bcond openssl 0" instead
```

The suggested default is `0` for `%bcond_with` and `1` for
`%bcond_without`, because that is the semantic each legacy macro already has.
Reporting the old form with a *different* default would silently flip the
package's build configuration.

### C2 — Manual switch macro

Before `%bcond` existed, a switch was written as a boolean macro and read back
with `%{?with_foo:...}`:

```specfile
%define with_mroonga 1
...
%if %{?with_mroonga}%{!?with_mroonga:0}
```

That is the same concept as `%bcond mroonga 1`, so clause 1 reaches it. Two
conditions must both hold before a line is reported, which is what keeps the
checkpoint from firing on ordinary macros:

1. The name carries a switch prefix: `with_`, `without_` or `_with_`.
2. The value is a boolean literal, `0` or `1`, and nothing else follows on the
   line.

`%define with_docdir /usr/share/doc/foo` fails the second condition and is an
ordinary macro. The reported switch name drops the prefix, so `with_mroonga`
becomes `%bcond mroonga`.

### C3 — Explicit default value

A `%bcond` with no value leaves the switch undefined, and a later
`%if %{with foo}` then has nothing to test. The declaration form shown in the
specification always carries the default, so the checkpoint asks for it:

```text
foo.spec: "%bcond bootstrap" (line 11) declares no default value;
write "%bcond bootstrap 0" or "%bcond bootstrap 1"
```

A value built from a macro is accepted without inspection. The reference
corpus contains `%bcond rpmwheels %{without bootstrap}`, which derives one
switch from another; the value cannot be judged before expansion, and
forbidding macros here would reject a legitimate indirection.

### Scope notes

Every item below is a real part of the specification that this rule
deliberately does not enforce, or a decision about how the checkpoints above
behave.

- **Whether a switch should exist at all is out of scope.** The clause
  describes how to declare an optional switch, not which options a package
  should expose. Which default is right for a given package is a design
  decision about the software being packaged.

- **A `%bcond` that no `%if` tests is not reported.** The guideline never
  requires every declared switch to be referenced by its own spec, and a
  builder can still flip it from the command line with `--with` /
  `--without`. Measured on the corpus, 21 switches across 15 specs are
  declared without a matching `%if %{with ...}`; they are left alone.

- **A switch redefined inside an `%if` / `%else` pair is legitimate.** Two
  declarations of the same name are allowed when each sits on a different
  branch, which is how a spec pins a switch per target. Measured on the
  corpus this shape appears 22 times across 16 specs, always inside a
  conditional, so declaration counting is not a checkpoint.

- **`%if %{with x}` and `%{?with x:...}` are both correct ways to read a
  switch.** The guideline does not prefer one, so neither form is reported.

- **A commented out line is never reported.** `# %bcond_with openssl` is
  documentation, so comment lines are stripped before matching. An indented
  declaration is still reported, because `%bcond` may legitimately sit inside
  an `%if` branch.

- **How a spec consumes the value, and how many lines a conditional block
  wraps, are structure questions.** They belong to the field and section
  rules rather than to this clause.

## Examples

### Reported

```specfile
%bcond_with openssl
```

```text
foo.spec: "%bcond_with openssl" (line 12) is the legacy switch form;
write "%bcond openssl 0" instead
```

```specfile
%define with_mroonga 1
```

```text
foo.spec: manual build switch "with_mroonga" (line 12) is defined with
%define; write "%bcond mroonga 1" instead
```

```specfile
%bcond bootstrap
```

```text
foo.spec: "%bcond bootstrap" (line 11) declares no default value;
write "%bcond bootstrap 0" or "%bcond bootstrap 1"
```

### Accepted

```specfile
%bcond bootstrap 0
%bcond docs 1
%bcond rpmwheels %{without bootstrap}

%if %{with bootstrap}
%endif
%if %{without docs}
%endif
```

```specfile
# A switch pinned per branch is legitimate.
%bcond bootstrap 0

%if %{with bootstrap}
%bcond race 0
%else
%bcond race 0
%bcond shared 0
%endif
```

```specfile
# An ordinary macro that starts with "with" is not a switch.
%define with_docdir /usr/share/doc/foo
```
