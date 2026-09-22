# check-spdx-basic-fields

> Rule ID: `check-spdx-basic-fields`

## Original Requirement

Source: [openRuyi Packaging Guidelines · 基础字段与段落](https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#基础字段与段落)

> Spec 必须包含以下字段与段落，且应当按如下顺序出现:
>
> ```spec
> Name:
> Version:
> Release:
> Summary:
> License:
>
> %description
> %files
> %changelog
> ```

Additionally:

- Sections must be separated by blank lines.
- When present, optional fields must respect the specified relative order.

## Checkpoints

| # | Checkpoint | Requirement | Failure condition |
| --- | --- | --- | --- |
| 1 | Required fields | `Name:`, `Version:`, `Release:`, `Summary:`, `License:` must all be present | Any required field is missing |
| 2 | Required sections | `%description`, `%files`, `%changelog` must all be present | Any required section is missing |
| 3 | Field ordering | When optional fields are present, they must follow the specified relative order: `Name → Version → Release → Summary → License → URL → VCS → Source → BuildArch → BuildSystem → Patch → BuildOption → BuildRequires → Provides → Conflicts → Obsoletes → Recommends → Requires → Supplements` | A field appears before another field that should precede it |
| 4 | Section separation | Adjacent sections must be separated by a blank line | Two consecutive sections have no blank line between them |

### Required vs Conditional Fields

The following fields are **required** (must always be present):

| Field | Description |
| --- | --- |
| `Name` | Package name |
| `Version` | Package version |
| `Release` | Release number (should use `%autorelease`) |
| `Summary` | Short package description |
| `License` | SPDX license expression |

All other fields (URL, VCS, Source, BuildArch, BuildSystem, etc.) are
**conditional** — they may be omitted when not applicable. The hook only
enforces their relative order *when they are present*.

### Section Separation

Each **real RPM spec section** must be separated from the next by at least one
blank line. Recognised sections are limited to actual RPM scriptlet headers:

`%prep`, `%conf`, `%build`, `%install`, `%check`, `%clean`,
`%pre`, `%post`, `%preun`, `%postun`, `%pretrans`, `%posttrans`,
`%triggerprein`, `%triggerin`, `%triggerun`, `%triggerpostun`,
`%verifyscript`, `%files`, `%changelog`, `%description`, `%package`,
`%generate_buildrequires`.

Lines that start with `%` but are **not** sections — such as macros
(`%global`, `%define`, `%bcond`), conditionals (`%if`, `%else`, `%endif`,
`%ifarch`), file directives (`%license`, `%doc`, `%dir`, `%attr`,
`%config`, `%ghost`), build helpers (`%setup`, `%configure`, `%make_build`,
`%make_install`), and auxiliary tools (`%systemd_post`, `%tmpfiles_create`,
`%sysusers_create_package`) — are ignored for section-separation purposes.

For example:

```spec
%description
A package description.

%files
/usr/bin/foo

%changelog
%autochangelog
```

The blank lines between `%description` and `%files`, and between `%files`
and `%changelog`, are mandatory.

## Usage

Add to `.pre-commit-config.yaml`:

```yaml
-   repo: https://github.com/openRuyi-Project/openruyi-precommit-hooks
    rev: v0.1.0
    hooks:
    -   id: check-spdx-basic-fields
```

Or run as a standalone command:

```console
$ check-spdx-basic-fields path/to/package.spec
```