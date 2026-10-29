from __future__ import annotations

import argparse
import re
from collections.abc import Sequence


_RE_COPYRIGHT_ISCAS = re.compile(
    r'^#\s*SPDX-FileCopyrightText:\s*\(C\)\s*'
    r'\d{4}(?:\s*,\s*\d{4}|\s*-\s*\d{4})*\s+'
    r'Institute\s+of\s+Software,\s+Chinese\s+Academy\s+of\s+'
    r'Sciences\s+\(ISCAS\)\s*$',
)
_RE_COPYRIGHT_RUYI = re.compile(
    r'^#\s*SPDX-FileCopyrightText:\s*\(C\)\s*'
    r'\d{4}(?:\s*,\s*\d{4}|\s*-\s*\d{4})*\s+'
    r'openRuyi\s+Project\s+Contributors\s*$',
)
_RE_CONTRIBUTOR = re.compile(r'^#\s*SPDX-FileContributor:\s*.+\s*$')
_RE_BLANK_COMMENT = re.compile(r'^#\s*$')
_RE_LICENSE_ANY = re.compile(
    r'^#\s*SPDX-License-Identifier:\s*(\S+)\s*$',
)
_RE_SPDX_START = re.compile(r'^#\s*SPDX-')


def _header_block(lines: list[str]) -> tuple[list[str], str | None]:
    """Extract the leading SPDX header block.

    Returns (spdx_lines, error). spdx_lines is the leading comment block
    that belongs to the SPDX header; once the required
    SPDX-License-Identifier line is seen, the scan stops and any later
    content is ignored. Error describes why the file does not start with
    valid SPDX declarations, or is None when it does.
    """
    if not lines:
        return [], 'file is empty'
    first = lines[0].strip()
    if not first:
        return [], 'file must not start with a blank line'
    if not lines[0].lstrip().startswith('#'):
        return [], 'file does not start with a comment'
    if not _RE_SPDX_START.match(first):
        return [], (
            f'file must start with SPDX declarations, found "{first}"'
        )
    block: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.lstrip()
        if not stripped.startswith('#'):
            break
        block.append(raw.strip())
        if _RE_LICENSE_ANY.match(raw.strip()):
            break
        i += 1

    return block, None


def _classify(line: str) -> str:
    if _RE_COPYRIGHT_ISCAS.match(line):
        return 'iscas'
    if _RE_COPYRIGHT_RUYI.match(line):
        return 'ruyi'
    if _RE_CONTRIBUTOR.match(line):
        return 'contributor'
    if _RE_BLANK_COMMENT.match(line):
        return 'blank'
    if _RE_LICENSE_ANY.match(line):
        return 'license'
    return 'other'


def _dedup(errors: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for err in errors:
        if err not in seen:
            seen.add(err)
            out.append(err)
    return out


def _check_spdx_header(filename: str) -> list[str]:
    errors: list[str] = []
    try:
        with open(filename, encoding='utf-8') as f:
            lines = f.read().splitlines()
    except UnicodeDecodeError:
        return [f'{filename}: file is not valid UTF-8']
    except OSError as exc:
        return [f'{filename}: {exc}']

    block, error = _header_block(lines)
    if error is not None:
        return [f'{filename}: {error}']

    seq = [_classify(line) for line in block]

    if 'other' in seq:
        idx = seq.index('other')
        return [
            f'{filename}: header may only contain SPDX declarations, '
            f'found "{block[idx]}"',
        ]

    # Duplicate lines are not allowed: the ISCAS copyright, openRuyi
    # copyright and license identifier lines must each appear exactly once.
    for kind, label in (
        ('iscas', 'ISCAS copyright'),
        ('ruyi', 'openRuyi copyright'),
        ('license', 'SPDX-License-Identifier'),
    ):
        n = seq.count(kind)
        if n > 1:
            errors.append(
                f'{filename}: duplicate {label} line, expected it '
                'exactly once',
            )

    # Ordering: ISCAS copyright, openRuyi copyright, then zero or more
    # contributors, then exactly one blank "#", then the license line as
    # the final SPDX declaration.
    expected_order = ['iscas', 'ruyi', 'contributor', 'blank', 'license']
    kind_positions: dict[str, list[int]] = {}
    for i, c in enumerate(seq):
        kind_positions.setdefault(c, []).append(i)

    prev = -1
    for kind in expected_order:
        positions = kind_positions.get(kind, [])
        if not positions:
            continue
        first = positions[0]
        if first < prev:
            errors.append(
                f'{filename}: header lines are out of order, expected '
                'ISCAS copyright, openRuyi copyright, optional '
                'contributor lines, blank "#", then '
                'SPDX-License-Identifier',
            )
            break
        prev = positions[-1]

    has_iscas = 'iscas' in seq
    has_ruyi = 'ruyi' in seq

    if not has_iscas:
        errors.append(
            f'{filename}: missing required header line '
            '"# SPDX-FileCopyrightText: (C) <year> '
            'Institute of Software, Chinese Academy of '
            'Sciences (ISCAS)"',
        )
    if not has_ruyi:
        errors.append(
            f'{filename}: missing required header line '
            '"# SPDX-FileCopyrightText: (C) <year> '
            'openRuyi Project Contributors"',
        )

    license_value = None
    for i, c in enumerate(seq):
        if c == 'license':
            m = _RE_LICENSE_ANY.match(block[i])
            if m:
                license_value = m.group(1)
            break
    if license_value is None:
        errors.append(
            f'{filename}: missing required header line '
            '"# SPDX-License-Identifier: MulanPSL-2.0"',
        )
        return _dedup(errors)
    if license_value != 'MulanPSL-2.0':
        errors.append(
            f'{filename}: SPDX-License-Identifier must be the default '
            f'license "MulanPSL-2.0" (found "{license_value}")',
        )
        return _dedup(errors)

    # The SPDX license line terminates the header block, so `license` is
    # always the final item of `seq` here; nothing to check after it.
    return _dedup(errors)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        for err in _check_spdx_header(filename):
            print(err)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
