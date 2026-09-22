"""Check that SPEC files have the required basic fields and sections.

Validates SPEC files against the openRuyi Packaging Specification,
section "基础字段与段落" (Basic Fields and Sections).

Reference:
https://www.openruyi.cn/zh-Hans/docs/guide/packaging-guidelines#基础字段与段落
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Required fields that MUST be present in the preamble
# ---------------------------------------------------------------------------
_REQUIRED_FIELDS = ['Name', 'Version', 'Release', 'Summary', 'License']

# ---------------------------------------------------------------------------
# Required sections that MUST be present
# ---------------------------------------------------------------------------
_REQUIRED_SECTIONS = ['%description', '%files', '%changelog']

# ---------------------------------------------------------------------------
# Field order for relative ordering check (as defined in the spec)
# ---------------------------------------------------------------------------
_FIELD_ORDER = [
    'Name', 'Version', 'Release', 'Summary', 'License',
    'URL', 'VCS', 'Source', 'BuildArch', 'BuildSystem',
    'Patch', 'BuildOption', 'BuildRequires',
    'Provides', 'Conflicts', 'Obsoletes',
    'Recommends', 'Requires', 'Supplements',
]

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
# Matches a field line like "Name: foo", "BuildOption(conf): bar",
# "Source0: url", etc.
_RE_FIELD = re.compile(
    r'^([A-Za-z]\w*(?:\([^)]*\))?|Source\d+):\s*',
)

# ---------------------------------------------------------------------------
# Known RPM spec scriptlet / section headers
# Only these are treated as section boundaries.  Other %-prefixed lines
# (macros like %global/%define, conditionals like %if/%else/%endif,
# file-level directives like %license/%doc/%dir/%attr/%config/%ghost,
# build helpers like %setup/%configure/%make_build, auxiliary tools like
# %systemd_post/%tmpfiles_create) are *not* sections.
# ---------------------------------------------------------------------------
_KNOWN_SECTIONS: frozenset[str] = frozenset({
    # main scriptlets
    '%prep', '%conf', '%build', '%install', '%check', '%clean',
    # install-time scriptlets
    '%pre', '%post', '%preun', '%postun',
    '%pretrans', '%posttrans',
    # trigger scriptlets
    '%triggerprein', '%triggerin', '%triggerun', '%triggerpostun',
    # verifyscript
    '%verifyscript',
    # structural
    '%files', '%changelog', '%description', '%package',
    # dynamic buildrequires (RPM ≥ 4.15)
    '%generate_buildrequires',
})

# Matches a known section header.
# Section headers can have optional arguments, e.g.
# "%files subpkg", "%package -n name", "%description -n subpkg".
_RE_KNOWN_SECTION = re.compile(r'^(%\w+)\b')



# SPDX header detection
_RE_SPDX = re.compile(r'^#\s*SPDX-')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_field(name: str) -> str:
    """Normalize a field name for ordering purposes.

    ``Source0``, ``Source1`` etc. → ``Source``.
    ``BuildOption(conf)`` → ``BuildOption``.
    """
    if re.match(r'^Source\d+$', name):
        return 'Source'
    paren = name.find('(')
    if paren != -1:
        return name[:paren]
    return name


def _parse_spec(lines: list[str]) -> tuple[
    list[tuple[str, str, int]],   # (normalized_name, raw_name, lineno)
    list[tuple[str, int, int]],   # (section_name, start_lineno, end_lineno)
    str | None,                   # error message or None
]:
    """Parse a SPEC file into preamble fields and sections.

    Returns (fields, sections, error).
    """
    fields: list[tuple[str, str, int]] = []
    sections: list[tuple[str, int, int]] = []

    n = len(lines)
    i = 0

    # ---- skip SPDX header comment block ----
    if i < n:
        stripped = lines[i].strip()
        if stripped and _RE_SPDX.match(stripped):
            while i < n and lines[i].strip().startswith('#'):
                i += 1

    # ---- skip blank lines after SPDX header ----
    while i < n and lines[i].strip() == '':
        i += 1

    # ---- parse preamble fields (everything before the first %section) ----
    while i < n:
        line = lines[i]
        m = _RE_FIELD.match(line)
        if m:
            raw_name = m.group(1)
            normalized = _normalize_field(raw_name)
            fields.append((normalized, raw_name, i + 1))
            i += 1
            # handle continuation lines (backslash or indented)
            while i < n and (
                lines[i].rstrip().endswith('\\')
                or (lines[i].startswith(' ') and lines[i].strip())
            ):
                i += 1
        elif _RE_KNOWN_SECTION.match(line):
            maybe_sec = _RE_KNOWN_SECTION.match(line).group(1)
            if maybe_sec in _KNOWN_SECTIONS:
                break
            else:
                i += 1
        elif line.strip() == '':
            i += 1
        elif line.strip().startswith('#'):
            i += 1
        else:
            # non-field, non-comment, non-blank, non-section line
            # in preamble — treat as unrecognised content
            i += 1

    # ---- parse sections ----
    while i < n:
        line = lines[i]
        m = _RE_KNOWN_SECTION.match(line)
        if m and m.group(1) in _KNOWN_SECTIONS:
            sec_name = m.group(1)
            sec_start = i + 1  # 1-based
            i += 1
            while i < n:
                m2 = _RE_KNOWN_SECTION.match(lines[i])
                if m2 and m2.group(1) in _KNOWN_SECTIONS:
                    break
                i += 1
            sections.append((sec_name, sec_start, i))  # end is exclusive
        else:
            i += 1

    return fields, sections, None


def _check_basic_fields(filename: str) -> list[str]:
    """Check a single SPEC file for basic field/section compliance."""
    errors: list[str] = []

    try:
        with open(filename, encoding='utf-8') as f:
            lines = f.read().splitlines()
    except UnicodeDecodeError:
        return [f'{filename}: file is not valid UTF-8']
    except OSError as exc:
        return [f'{filename}: {exc}']

    if not lines:
        return [f'{filename}: file is empty']

    fields, sections, _parse_err = _parse_spec(lines)

    field_names = {f[0] for f in fields}
    section_names = {s[0] for s in sections}

    # ---- 1. Required fields ----
    for req in _REQUIRED_FIELDS:
        if req not in field_names:
            errors.append(
                f'{filename}: missing required field "{req}:"',
            )

    # ---- 2. Required sections ----
    for req in _REQUIRED_SECTIONS:
        if req not in section_names:
            errors.append(
                f'{filename}: missing required section "{req}"',
            )

    # ---- 3. Field ordering ----
    # Collect normalized field names that are in _FIELD_ORDER, in order
    ordered_fields = [fn for fn, _, _ in fields if fn in _FIELD_ORDER]
    if len(ordered_fields) >= 2:
        max_seen = -1
        out_of_order: list[str] = []
        for fn in ordered_fields:
            pos = _FIELD_ORDER.index(fn)
            if pos < max_seen:
                out_of_order.append(fn)
            max_seen = max(max_seen, pos)
        if out_of_order:
            errors.append(
                f'{filename}: field order is incorrect; '
                f'field(s) out of position: {", ".join(out_of_order)}',
            )

    # ---- 4. Sections must be separated by blank lines ----
    # Skip backwards over comment lines.  If an RPM conditional macro
    # (%if / %else / %endif / ...) appears between sections, the
    # macro block itself provides structural separation — no error.
    _RE_RPM_COND = re.compile(r'^%(?:if|ifarch|ifnarch|ifos|ifnos|else|elif|endif)\b')
    for idx in range(len(sections) - 1):
        _this_name, _this_start, this_end = sections[idx]
        next_name, next_start, _next_end = sections[idx + 1]
        if next_start > 1:
            i = next_start - 2  # 0-based index of line just before section
            saw_cond = False
            while i >= 0:
                stripped = lines[i].strip()
                if stripped.startswith('#'):
                    i -= 1
                    continue
                if _RE_RPM_COND.match(stripped):
                    saw_cond = True
                    i -= 1
                    continue
                break  # non-skippable line reached
            # Conditional macros provide separation; otherwise need blank line
            if not saw_cond and (i < 0 or lines[i].strip() != ''):
                errors.append(
                    f'{filename}: sections "{_this_name}" and '
                    f'"{next_name}" must be separated by a blank line',
                )

    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        for err in _check_basic_fields(filename):
            print(err)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())