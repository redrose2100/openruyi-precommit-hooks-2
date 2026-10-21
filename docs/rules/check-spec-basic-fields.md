# check-spec-basic-fields

> Rule ID: `check-spec-basic-fields`

## Original Requirement

Source: [openRuyi Packaging Specification · Basic Fields and Sections](https://www.openruyi.cn/en/docs/guide/packaging-guidelines#basic-fields-and-sections)
and [openRuyi Packaging Specification · Minimal Skeleton Example](https://www.openruyi.cn/en/docs/guide/packaging-guidelines#minimal-skeleton-example)

The rule covers **only** those two sections of the packaging guidelines.

### Basic fields and sections

- A spec **must** contain the fields `Name` `Version` `Release` `Summary`
  `License`, and the sections `%description` `%files` `%changelog`.
- A missing **conditional** field (`URL` `VCS` `Source` `BuildArch`
  `BuildSystem` `Patch` `BuildOption` `BuildRequires` `Provides` `Conflicts`
  `Obsoletes` `Recommends` `Requires` `Supplements`, and the conditional
  sections) is **not** a violation.
- When those fields are present they **should** appear in the documented
  relative order: `Name` → `Version` → `Release` → `Summary` → `License` →
  `URL` → `VCS` → `Source` → `BuildArch` → `BuildSystem` → `Patch` →
  `BuildOption` → `BuildRequires` → `Provides` → `Conflicts` → `Obsoletes` →
  `Recommends` → `Requires` → `Supplements`, with the `%description` section
  last. Only the **relative** order is required — a field that is omitted
  leaves no gap. `Source` / `Source0` / `Source1` share the same position.
- The same relative order applies inside each `%package` block, evaluated
  independently; a subpackage only needs the fields that apply to it.
- Sections **must** be separated by a blank line.
- `%changelog` content **must** be `%autochangelog`.
- `Release` **should** use `%autorelease`.

### Minimal skeleton example

The minimal skeleton consists of the five required fields followed by the
three required sections, each section separated by a blank line, with
`%autorelease` as the release value and `%autochangelog` as the changelog
body.

## Checkpoints

| # | Checkpoint | Requirement | Failure condition |
| --- | --- | --- | --- |
| 1 | Required fields | The spec must contain `Name`, `Version`, `Release`, `Summary`, `License` | Any of the five is absent from every field block |
| 2 | Required sections | The spec must contain `%description`, `%files`, `%changelog` | Any of the three is absent |
| 3 | Section order | `%description` before `%files` before `%changelog` (relative order) | A later section appears before an earlier one |
| 4 | Section separation | Adjacent, **differently named** sections must be separated by a blank line | No blank line separates two distinct section headers, ignoring comment lines and RPM conditionals |
| 5 | Changelog content | The first non-blank line of `%changelog` must be `%autochangelog` (the legacy form `%{?autochangelog}` is equivalent and accepted) | The body is a manual changelog, is empty, or starts with anything else |
| 6 | Core field order | Inside each field block, the core fields that are present must keep the order `Name` → `Version` → `Release` → `Summary` → `License` | Two present core fields are inverted |
| 7 | Autorelease | `Release` should be `%autorelease` (the brace form `%{autorelease}` is accepted) | `Release` has some other value |

### Scope notes

- Check 6 uses the **core five** fields only. Enforcing the complete
  19-field order is out of scope: the repository overwhelmingly writes
  `Requires` before `Provides`, which is a style migration rather than a
  per-file defect.
- Fields are collected per block. The main preamble and every `%package`
  block are evaluated separately, and only the **first** occurrence of a
  repeated field (for example several `BuildRequires:` lines) is considered.
  This is what keeps repeated and subpackage fields from being reported.
- `%license`, `%doc`, `%systemd_post`, `%autochangelog`, `%find_lang` and
  similar macro invocations are never treated as sections, so they do not
  trigger the blank-line check.
- Comment lines and RPM conditionals (`%if` `%ifarch` `%ifnarch` `%ifos`
  `%ifnos` `%else` `%elif` `%endif`) are skipped when collecting fields, and
  are also ignored by the blank-line check. A comment placed directly above
  a section header reads as part of that header, so

  ```spec
  %install
  make install
  # no test suite
  %check
  ```

  is accepted, while

  ```spec
  %install
  make install
  %check
  ```

  is not.
- Consecutive sections with the **same** name are never reported: it is
  normal for several subpackages to emit a `%files` block in sequence.

## Usage

Add to `.pre-commit-config.yaml`:

```yaml
-   repo: https://github.com/openRuyi-Project/openruyi-precommit-hooks
    rev: v0.1.0   # use the latest tag
    hooks:
    -   id: check-spec-basic-fields
```

It can also be used as a standalone command:

```console
$ check-spec-basic-fields path/to/foo.spec
```

An exit code of 1 means some files do not meet the requirements; 0 means
all files pass.

## Examples

### Pass ✅

```spec
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
```

### Pass ✅ (repeated fields and a subpackage block)

Repeated fields collapse to their first occurrence, and each `%package`
block is ordered independently:

```spec
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
BuildRequires:  gcc
BuildRequires:  make
Provides:       foo

%description
An example package.

%package        devel
Summary:        Development files
License:        MulanPSL-2.0

%description    devel
Development files for foo.

%files devel
%{_includedir}/foo.h

%changelog
%autochangelog
```

### Fail ❌ (missing required field)

```spec
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
```

```
foo.spec: missing required field "License"
```

### Fail ❌ (missing required section)

```spec
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%changelog
%autochangelog
```

```
foo.spec: missing required section "%files"
```

### Fail ❌ (sections out of order)

```spec
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%files
%license LICENSE

%description
An example package.

%changelog
%autochangelog
```

```
foo.spec: section "%description" (line 10) must appear before "%files" (line 7)
```

### Fail ❌ (sections not separated by a blank line)

```spec
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%files
%license LICENSE
%changelog
%autochangelog
```

```
foo.spec: section "%changelog" (line 12) must be separated from "%files" (line 10) by a blank line
```

### Fail ❌ (changelog is not `%autochangelog`)

```spec
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%files
%license LICENSE

%changelog
* Tue Jan 06 2026 Your Name <you@example.com> - 1.0-1
- Initial package
```

```
foo.spec: %changelog (line 13) must contain "%autochangelog", found "* Tue Jan 06 2026 Your Name <you@example.com> - 1.0-1"
```

### Fail ❌ (core fields out of order)

```spec
Name:           foo
Version:        1.0
Summary:        Example package
Release:        %autorelease
License:        MulanPSL-2.0

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
```

```
foo.spec: field "Release" (line 4) must appear before "Summary" (line 3) in the main block
```

### Fail ❌ (Release is not `%autorelease`)

```spec
Name:           foo
Version:        1.0
Release:        1
Summary:        Example package
License:        MulanPSL-2.0

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
```

```
foo.spec: Release (line 3) should use "%autorelease", found "1"
```
