from __future__ import annotations

import argparse
import re
from collections.abc import Sequence

# CJK Unified Ideographs, CJK Extension A, and CJK Compatibility Ideographs
_RE_CHINESE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')


def _check_no_chinese(filename: str) -> list[str]:
    errors: list[str] = []
    try:
        with open(filename, encoding='utf-8') as f:
            lines = f.read().splitlines()
    except UnicodeDecodeError:
        return [f'{filename}: file is not valid UTF-8']
    except OSError as exc:
        return [f'{filename}: {exc}']

    for lineno, line in enumerate(lines, start=1):
        if _RE_CHINESE.search(line):
            errors.append(f'{filename}:{lineno}: contains Chinese characters')
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', nargs='*', help='files to check')
    args = parser.parse_args(argv)

    retv = 0
    for filename in args.filenames:
        for err in _check_no_chinese(filename):
            print(err)
            retv = 1
    return retv


if __name__ == '__main__':
    raise SystemExit(main())
