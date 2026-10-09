# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spdx_header import _check_spdx_header
from openruyi_precommit_hooks.check_spdx_header import main

VALID_SPEC = """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
"""


def _write(tmp_path: Path, name: str, content: str) -> str:
    p = tmp_path / name
    p.write_text(content, encoding='utf-8')
    return str(p)


@pytest.mark.parametrize(
    ('content', 'filename'),
    [
        pytest.param(
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
# SPDX-FileContributor: Your Name <your.email@example.com>
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            'good1.spec',
            id='with-contributor',
        ),
        pytest.param(
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
# SPDX-FileContributor: Your Name <your.email@example.com>
# SPDX-FileContributor: Another Dev <another@example.com>
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            'good4.spec',
            id='with-multiple-contributors',
        ),
        pytest.param(
            """\
# SPDX-FileCopyrightText: (C) 2025, 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2025, 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            'good2.spec',
            id='without-contributor-multi-year',
        ),
        pytest.param(
            """\
# SPDX-FileCopyrightText: (C) 2025-2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2025-2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            'good3.spec',
            id='year-range',
        ),
        pytest.param(
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
# SPDX-FileContributor: user1 <user1@example.com>
# SPDX-FileContributor: user2 <user2@example.com>
#
# SPDX-License-Identifier: MulanPSL-2.0
#

Name:           foo
Version:        1.0
""",
            'good5.spec',
            id='trailing-blank-hash',
        ),
        pytest.param(
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
# SPDX-FileContributor: user1 <user1@example.com>
# SPDX-FileContributor: user2 <user2@example.com>
#
# SPDX-License-Identifier: MulanPSL-2.0
#
#
#

Name:           foo
Version:        1.0
""",
            'good6.spec',
            id='multiple-trailing-blank-hash',
        ),
    ],
)
def test_ok_header(tmp_path: Path, content: str, filename: str) -> None:
    errors = _check_spdx_header(_write(tmp_path, filename, content))
    assert errors == []


@pytest.mark.parametrize(
    ('content', 'expected'),
    [
        pytest.param(
            # missing ISCAS copyright line
            """\
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            ['missing required header line', 'Institute of Software'],
            id='missing-iscas',
        ),
        pytest.param(
            # missing openRuyi copyright line
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            ['missing required header line', 'openRuyi Project Contributors'],
            id='missing-ruyi',
        ),
        pytest.param(
            # missing SPDX-License-Identifier line, and nothing else is
            # wrong, so the diagnostic list must match exactly
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#

Name:           foo
Version:        1.0
""",
            'missing required header line "# SPDX-License-Identifier: MulanPSL-2.0"',
            id='missing-license',
        ),
        pytest.param(
            # wrong license
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: Apache-2.0

Name:           foo
Version:        1.0
""",
            [
                'must be the default license "MulanPSL-2.0"',
                'found "Apache-2.0"',
                # the line exists, so it must not be reported missing too
                '!missing required header line',
            ],
            id='wrong-license-with-blank-separator',
        ),
        pytest.param(
            # wrong license value; exact list, so a spurious extra
            # diagnostic (e.g. "missing required header line") also fails
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MIT

Name:           foo
Version:        1.0
""",
            'SPDX-License-Identifier must be the default license "MulanPSL-2.0" (found "MIT")',
            id='wrong-license',
        ),
        pytest.param(
            # no blank "#" line between copyright and license
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            ['missing required blank "#" comment line'],
            id='missing-blank',
        ),
        pytest.param(
            # two blank "#" lines
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            ['there must be exactly one blank "#" comment line'],
            id='too-many-blank',
        ),
        pytest.param(
            """\
Name:           foo
Version:        1.0
""",
            ['file does not start with a comment'],
            id='no-comments-at-start',
        ),
        pytest.param(
            '',
            ['file is empty'],
            id='empty-file',
        ),
        pytest.param(
            # a non-SPDX leading comment is the only problem, so its
            # diagnostic must match exactly and must not be re-wrapped as
            # a malformed header line
            """\
# generated by openruyi-tooling
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            'file must start with SPDX declarations, found "# generated by openruyi-tooling"',
            id='plain-comment-before-spdx-block',
        ),
        pytest.param(
            """
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            ['file must not start with a blank line'],
            id='leading-blank-line',
        ),
        pytest.param(
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# generated by openruyi-tooling
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            [
                'header may only contain SPDX declarations',
                '# generated by openruyi-tooling',
            ],
            id='non-spdx-comment-in-block',
        ),
        pytest.param(
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
# some unrelated comment
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            [
                'header may only contain SPDX declarations',
                '# some unrelated comment',
            ],
            id='non-spdx-comment-between-copyright-and-license',
        ),
        pytest.param(
            # duplicate ISCAS copyright line
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            ['duplicate ISCAS copyright line'],
            id='duplicate-iscas-copyright',
        ),
        pytest.param(
            # duplicate openRuyi copyright line
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            ['duplicate openRuyi copyright line'],
            id='duplicate-ruyi-copyright',
        ),
        pytest.param(
            # duplicate SPDX-License-Identifier line
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            ['duplicate SPDX-License-Identifier line'],
            id='duplicate-license-line',
        ),
        pytest.param(
            # contributor before copyright
            """\
# SPDX-FileContributor: Your Name <your.email@example.com>
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            ['header lines are out of order'],
            id='contributor-before-copyright',
        ),
        pytest.param(
            # contributor between the two copyright lines
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileContributor: Your Name <your.email@example.com>
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            ['header lines are out of order'],
            id='contributor-between-copyrights',
        ),
        pytest.param(
            # contributor between the blank line and the license
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-FileContributor: Your Name <your.email@example.com>
# SPDX-License-Identifier: MulanPSL-2.0

Name:           foo
Version:        1.0
""",
            ['header lines are out of order'],
            id='contributor-between-blank-and-license',
        ),
        pytest.param(
            # contributor after the license
            """\
# SPDX-FileCopyrightText: (C) 2026 Institute of Software, Chinese Academy of Sciences (ISCAS)
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
#
# SPDX-License-Identifier: MulanPSL-2.0
# SPDX-FileContributor: Your Name <your.email@example.com>

Name:           foo
Version:        1.0
""",
            ['header lines are out of order'],
            id='contributor-after-license',
        ),
    ],
)
def test_bad_header(
    tmp_path: Path, content: str, expected: str | list[str],
) -> None:
    """Check that bad headers produce the expected diagnostics.

    ``expected`` is either the single message the file must produce
    (compared against the full list, so any extra or missing diagnostic
    fails), or a list of substrings to assert against the joined error
    output; an entry prefixed with ``!`` must NOT appear.
    """
    path = _write(tmp_path, 'bad.spec', content)
    errors = _check_spdx_header(path)
    if isinstance(expected, str):
        assert errors == [f'{path}: {expected}']
        return
    assert errors != []
    joined = '\n'.join(errors)
    for item in expected:
        if item.startswith('!'):
            assert item[1:] not in joined
        else:
            assert item in joined


def test_main_exit_code_and_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """main() should return non-zero and print every error for bad files."""
    paths = [
        _write(tmp_path, 'ok.spec', VALID_SPEC),
        _write(
            tmp_path, 'bad1.spec',
            VALID_SPEC.replace(
                '# SPDX-FileCopyrightText: (C) 2026 Institute of Software, '
                'Chinese Academy of Sciences (ISCAS)\n',
                '',
            ),
        ),
        _write(
            tmp_path, 'bad2.spec',
            VALID_SPEC.replace(
                '# SPDX-FileCopyrightText: (C) 2026 openRuyi Project '
                'Contributors\n',
                '',
            ),
        ),
    ]
    retv = main(paths)
    captured = capsys.readouterr()
    assert retv == 1
    assert 'bad1.spec' in captured.out
    assert 'bad2.spec' in captured.out
    assert 'ok.spec' not in captured.out


def test_main_empty_input() -> None:
    assert main([]) == 0


def test_main_valid_spec_returns_zero_no_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """main() should return 0 and print nothing for a valid spec file."""
    content = VALID_SPEC
    retv = main([_write(tmp_path, 'ok.spec', content)])
    captured = capsys.readouterr()
    assert retv == 0
    assert captured.out == ''


def test_main_unreadable_file(tmp_path: Path) -> None:
    missing = tmp_path / 'missing.spec'
    retv = main([str(missing)])
    assert retv == 1


def test_main_bad_utf8(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / 'bad-utf8.spec'
    p.write_bytes(b'# SPDX-FileCopyrightText: (C) 2026 \xff\xfe\n')
    retv = main([str(p)])
    captured = capsys.readouterr()
    assert retv == 1
    assert 'not valid UTF-8' in captured.out


def test_main_all_bad_prints_each(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Each bad file should produce at least one output line."""
    paths = [
        _write(tmp_path, 'x1.spec', 'Name: a\n'),
        _write(tmp_path, 'x2.spec', 'Name: b\n'),
    ]
    retv = main(paths)
    captured = capsys.readouterr()
    assert retv == 1
    assert 'x1.spec' in captured.out
    assert 'x2.spec' in captured.out
