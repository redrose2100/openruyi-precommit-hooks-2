from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_no_chinese import _check_no_chinese
from scripts.check_no_chinese import main

# Test data below uses \uXXXX escapes instead of literal CJK characters so
# that this test file itself complies with the check-no-chinese policy.
SHI_JIE = '\u4e16\u754c'  # shi jie
NI_HAO = '\u4f60\u597d'  # ni hao
ZHONG_WEN = '\u4e2d\u6587'  # zhong wen
DI_SAN_HANG = '\u7b2c\u4e09\u884c'  # di san hang
YOU_ZHONG_WEN = '\u6709\u4e2d\u6587'  # you zhong wen


def _write(tmp_path: Path, name: str, content: str | bytes) -> str:
    p = tmp_path / name
    if isinstance(content, bytes):
        p.write_bytes(content)
    else:
        p.write_text(content, encoding='utf-8')
    return str(p)


@pytest.mark.parametrize(
    ('content', 'filename'),
    [
        pytest.param(
            'hello world\nno chinese here\n', 'ok1.txt', id='ascii-only',
        ),
        pytest.param('', 'ok2.txt', id='empty-file'),
        pytest.param(
            'English only\nSome 123 numbers & symbols #@!\n',
            'ok3.txt',
            id='no-chinese-characters',
        ),
        pytest.param(
            'Chinese punctuation is allowed\u3002\n',
            'ok4.txt',
            id='chinese-punctuation-only',
        ),
        pytest.param(
            'trailing newline\n',
            'ok5.txt',
            id='trailing-newline',
        ),
    ],
)
def test_ok_no_chinese(tmp_path: Path, content: str, filename: str) -> None:
    errors = _check_no_chinese(_write(tmp_path, filename, content))
    assert errors == []


@pytest.mark.parametrize(
    ('content', 'filename', 'expected_lineno'),
    [
        pytest.param(
            f'hello {SHI_JIE}\n', 'bad1.txt', 1, id='chinese-in-line-1',
        ),
        pytest.param(
            f'{NI_HAO}{SHI_JIE}\n', 'bad2.txt', 1, id='chinese-only',
        ),
        pytest.param(
            f'line one\nline two {ZHONG_WEN}\nline three\n',
            'bad3.txt',
            2,
            id='chinese-in-line-2',
        ),
        pytest.param(
            f'first\nsecond\n{DI_SAN_HANG}\n',
            'bad4.txt',
            3,
            id='chinese-in-line-3',
        ),
        pytest.param(
            'mixed \u4e2d english \u6587 text\n',
            'bad5.txt',
            1,
            id='mixed-chinese-english',
        ),
    ],
)
def test_bad_no_chinese(
    tmp_path: Path, content: str, filename: str, expected_lineno: int,
) -> None:
    errors = _check_no_chinese(_write(tmp_path, filename, content))
    assert len(errors) == 1
    assert f'{filename}:{expected_lineno}' in errors[0]
    assert 'contains Chinese characters' in errors[0]


def test_bad_no_chinese_reports_multiple_lines(tmp_path: Path) -> None:
    content = f'{ZHONG_WEN} line 1\nascii line\n{ZHONG_WEN} line 3\n'
    errors = _check_no_chinese(_write(tmp_path, 'multi.txt', content))
    assert len(errors) == 2
    assert 'multi.txt:1' in errors[0]
    assert 'multi.txt:3' in errors[1]


def test_bad_utf8(tmp_path: Path) -> None:
    errors = _check_no_chinese(
        _write(tmp_path, 'bad-utf8.txt', b'\xff\xfe\x00'),
    )
    assert len(errors) == 1
    assert 'not valid UTF-8' in errors[0]


def test_main_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    ok = _write(tmp_path, 'ok.txt', 'no chinese\n')
    bad = _write(
        tmp_path, 'bad.txt', f'{YOU_ZHONG_WEN}\n',
    )
    retv = main([ok, bad])
    captured = capsys.readouterr()
    assert retv == 1
    assert 'bad.txt:1' in captured.out
    assert 'contains Chinese characters' in captured.out
    assert 'ok.txt' not in captured.out


def test_main_empty_input() -> None:
    assert main([]) == 0


def test_main_unreadable_file(tmp_path: Path) -> None:
    missing = tmp_path / 'missing.txt'
    assert main([str(missing)]) == 1
