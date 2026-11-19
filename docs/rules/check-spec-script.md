# check-spec-script

Validate the scriptlets of an openRuyi spec file.

## Original Requirement

### Source A — Packaging guidelines, `Scriptlet`

<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/#%E8%84%9A%E6%9C%AC%E6%AE%B5>

The section states three clauses, rendered here in English. It also points to
the `Scriptlets` supplement for the full rule set and the recommended
template, so both sources are treated as one requirement.

1. A scriptlet **must** be idempotent and **must** handle the install, upgrade
   and uninstall cases correctly, distinguishing them by the transaction
   argument such as `$1`.
2. A scriptlet **must** end with a success status. It **must not** abort the
   transaction because a non critical step failed.
3. When a single program can be called directly, the scriptlet **should** use
   the `-p` form, which keeps the shell logic small.

### Source B — `Scriptlets` supplement

<https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines/Scriptlets>

The supplement supplies the detail that the main text only summarises.

- `-p` names the program that runs the scriptlet, so the whole section can be
  a direct program call. The example is the canonical one:

  ```text
  %post -p /usr/bin/ldconfig
  ```

- `$1` is the number of packages of the same name that remain **after** the
  operation. The supplement tabulates it per scriptlet:

  | Scriptlet | Install | Upgrade | Uninstall |
  | --- | --- | --- | --- |
  | `%pretrans` | `$1 == 1` | `$1 == 2` | N/A |
  | `%pre` | `$1 == 1` | `$1 == 2` | N/A |
  | `%post` | `$1 == 1` | `$1 == 2` | N/A |
  | `%preun` | N/A | `$1 == 1` | `$1 == 0` |
  | `%postun` | N/A | `$1 == 1` | `$1 == 0` |
  | `%posttrans` | `$1 == 1` | `$1 == 2` | N/A |

- Because a parallel installable package can make the count larger than the
  tabulated value, `if [ "$1" -gt 1 ]` is preferred over testing `== 2`.
- Every scriptlet should leave the exit status at `0`. RPM does not pass `-e`
  to the shell, so the status of the **last** command decides the status of
  the whole scriptlet. `|| :` is the idiom for forcing success on a command
  that is not critical, and it must not be applied to a command that
  genuinely must succeed.
- A non zero exit can break an install, an upgrade or an erase, and can leave
  a duplicate rpmdb entry and orphaned files behind.
- `%pretrans` runs before any package is installed, so it cannot have a
  dependency. The supplement states that it should be avoided.
- A scriptlet may assume `bash`.

### Strength summary

| Clause | Wording | Level |
| --- | --- | --- |
| Scriptlet is idempotent | Clause 1 | MUST |
| Install, upgrade and uninstall are distinguished | Clause 1, B table | MUST |
| Scriptlet ends with a success status | Clause 2, B | MUST |
| A non critical step does not abort the transaction | Clause 2, B | MUST |
| Single program call uses `-p` | Clause 3, B | SHOULD |
| Upgrade state is tested as a range | B, "prefer `-gt 1`" | SHOULD |
| Erase state is not tested on the install side | B table, "N/A" | MUST |
| `%pretrans` is avoided | B, `Order` section | SHOULD |

## Flags

| Flag | Disables |
| --- | --- |
| `--no-check-single-program` | S1, the `-p` form of a single program call |
| `--no-check-exit-status` | S2, the success status of the last statement |
| `--no-check-pretrans` | S3, the use of `%pretrans` |
| `--no-check-transaction-range` | S4, the range test of the argument |
| `--no-check-transaction-side` | S5, the erase test on the install side |

## Checkpoints

| ID | Checkpoint | Source | Strength |
| --- | --- | --- | --- |
| S1 | A scriptlet that runs one argument free program uses `-p`. | A3, B | SHOULD |
| S2 | A scriptlet does not leave the transaction status to a bare command. | A2, B | MUST |
| S3 | `%pretrans` is not used. | A1, B | SHOULD |
| S4 | A transaction argument is tested as a range, not as one exact count. | B | SHOULD |
| S5 | An install side scriptlet does not test the erase state. | B | MUST |

### Scope notes

- Clause 1's idempotency is **not** enforced. Whether a program tolerates
  being run twice depends on what the program does, which the spec does not
  record.
- Clause 2's "must not abort the transaction" is enforced through the last
  statement, not by judging the importance of a command. A deliberate
  `|| exit 1` is left alone, because the supplement says `|| :` must not be
  applied to a command that genuinely must succeed, and telling a critical
  command from a decorative one needs knowledge of the program.
- S1 only reports a body of exactly one token that is a program named by an
  absolute path or by a macro followed by a path. A body that carries an
  argument is **not** reported, because `-p` names the program that runs the
  body and the argument would be lost. A bare word is **not** reported
  either, because it may be a shell builtin, a function or a macro.
- A statement that is a macro **invocation** (`%systemd_post foo.service`) is
  not inspected by S1, S2, S4 or S5. The macro owns its own status handling,
  and the reference corpus writes 552 of its 720 scriptlets that way. A
  statement that uses a macro **expansion** as its program
  (`%{_bindir}/fc-cache -fs`) is still a command the shell runs, so it is
  inspected; the two forms are told apart by whether the `%` is followed by
  `{`.
- A body that uses `-p` is not inspected by S1 or S2, because the named
  program rather than the shell then decides the status. `-p <lua>` is
  legitimate and is skipped with the rest.
- S2 accepts five ways of forcing a success status: a `||` fallback, a
  trailing `exit 0`, a trailing `:` or `true`, and a body whose last
  statement closes a control structure (`fi`, `done`, `esac`, `}`), because
  the status then comes from inside the structure. An `exit 1` reached
  through a `||` or `&&` on the statement above is also accepted, since the
  packager chose that failure branch on purpose.
- S2 stays silent on `%pretrans` and on a body of exactly one argument free
  program call. In both cases the finding would only repeat the advice that
  S3 or S1 already gives, and moving the program into the header removes the
  statement and its status together.
- S4 and S5 only read an exact comparison (`-eq`, `==`, `=`) against a
  literal number, and skip a statement that is a macro invocation. A range
  comparison is never reported, and a value that does not match the state the
  supplement tabulates for that scriptlet is left to S5 or ignored.
- The `%filetrigger*` and `%transfiletrigger*` sections are treated as
  section boundaries but are never checked: their arguments are package
  names rather than a transaction count. `%preuntrans` and `%postuntrans` are
  boundaries for the same reason, because the supplement table does not
  cover them.
- The section whitelist is deliberately wider than the one the sibling rules
  use. A trigger header or a `%postuntrans` header that is missing from it
  would not end the scriptlet above, so the body of the scriptlet would
  absorb the next section and S2 would report a statement that belongs
  elsewhere.
- A `-n <name>` header flag names the package, not the program, so the body
  is still shell and is still checked. Only `-p` switches the body to another
  language.
- Whether a required program exists in the build root, and whether the shell
  a scriptlet assumes is available, are build time questions and are **not**
  checked.
- No network access and no `rpm` invocation is performed, so the rule works
  on a bare checkout.

## Examples

Passing spec:

```text
%post -p /sbin/ldconfig

%postun -p /sbin/ldconfig

%posttrans
%{_bindir}/fc-cache -s || :

%preun
if [ "$1" -ge 1 ]; then
    %{_bindir}/foo --remove-alternatives || :
fi

%post
if [ "$1" -gt 1 ]; then
    %{_bindir}/foo --upgrade || :
fi
exit 0
```

S1 — a single program call without `-p`:

```text
foo.spec: %post (line 166) runs the single program "/sbin/udevadm" and gives it no argument; write "%post -p /sbin/udevadm" and leave the body empty
```

S2 — the last statement decides the status:

```text
foo.spec: %post (line 81) leaves the transaction status to "%{_bindir}/fc-cache -fs"; append "|| :" to the command or end the body with "exit 0"
```

S3 — `%pretrans` is used:

```text
foo.spec: %pretrans (line 75) runs before any package is installed and therefore cannot rely on a program it needs; use "%posttrans" instead
```

S4 — the upgrade state is pinned to one exact count:

```text
foo.spec: %post (line 13) tests "$1" with "=" against "2"; a parallel installable package reports a larger count, so write "-gt 1" instead
```

S5 — the erase branch sits in an install side scriptlet:

```text
foo.spec: %post (line 13) tests "$1" against "0"; an install side scriptlet never runs while a package is erased, so the branch is never taken; use "%postun" for the erase case
```
