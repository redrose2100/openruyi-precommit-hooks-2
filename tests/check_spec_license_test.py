# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks._spdx_ids import EXCEPTION_IDS
from openruyi_precommit_hooks._spdx_ids import LICENSE_IDS
from openruyi_precommit_hooks.check_spec_license import _check_spec_license
from openruyi_precommit_hooks.check_spec_license import _check_value
from openruyi_precommit_hooks.check_spec_license import main

VALID_SPEC = """\
# SPDX-FileCopyrightText: (C) 2026 openRuyi Project Contributors
# SPDX-License-Identifier: MulanPSL-2.0

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
"""


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding='utf-8')
    return str(path)


def _spec(license_value: str) -> str:
    return (
        'Name:           foo\n'
        'Version:        1.0\n'
        f'License:        {license_value}\n'
    )


def _findings(tmp_path: Path, license_value: str) -> list[str]:
    path = _write(tmp_path, 'x.spec', _spec(license_value))
    return [err.split('x.spec: ', 1)[-1] for err in _check_spec_license(path)]


# --- baseline ---------------------------------------------------------------


def test_valid_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_license(_write(tmp_path, 'ok.spec', VALID_SPEC)) == []


def test_main_returns_zero_on_clean_file(tmp_path: Path) -> None:
    path = _write(tmp_path, 'ok.spec', VALID_SPEC)
    assert main([path]) == 0


def test_main_returns_one_on_violation(tmp_path: Path) -> None:
    path = _write(tmp_path, 'bad.spec', _spec('BSD and MIT'))
    assert main([path]) == 1


def test_main_returns_zero_without_filenames() -> None:
    assert main([]) == 0


def test_license_with_alignment_padding_passes(tmp_path: Path) -> None:
    # The whole corpus aligns the tag value with spaces. A rule that inspected
    # raw whitespace would flag all 6341 specs, so the padding is stripped
    # before any checkpoint runs.
    assert _findings(tmp_path, 'MIT') == []
    assert _findings(tmp_path, 'MIT OR Apache-2.0') == []


def test_license_with_minimal_spacing_passes(tmp_path: Path) -> None:
    content = 'Name: foo\nVersion: 1.0\nLicense:MIT\n'
    path = _write(tmp_path, 'x.spec', content)
    assert _check_spec_license(path) == []


# --- valid expressions ------------------------------------------------------


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('MIT', id='single'),
        pytest.param('MIT OR Apache-2.0', id='or'),
        pytest.param('MIT AND Apache-2.0', id='and'),
        pytest.param('Apache-2.0 WITH LLVM-exception', id='with'),
        pytest.param('(GPL-2.0-or-later OR BSD-3-Clause) AND LGPL-2.1-or-later', id='nested'),
        pytest.param('LicenseRef-openRuyi-Public-Domain', id='license-ref'),
        pytest.param('MIT AND LicenseRef-ISO-8879', id='license-ref-and'),
        pytest.param('GPL-1.0-or-later OR Artistic-1.0-Perl', id='perl-module'),
        pytest.param('CC0-1.0', id='cc0'),
        pytest.param('Unlicense', id='unlicense'),
        pytest.param('MulanPSL-2.0', id='mulanpsl'),
        pytest.param('((MIT))', id='redundant-parens'),
    ],
)
def test_valid_expression_passes(tmp_path: Path, value: str) -> None:
    assert _findings(tmp_path, value) == [], value


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('Apache-2.0 AND (Apache-2.0 WITH LLVM-exception OR NCSA)', id='duplicate-leaf'),
        pytest.param('LGPL-2.1-or-later AND LGPL-2.1-or-later WITH GCC-exception-2.0', id='duplicate-with-exception'),
        pytest.param('MIT AND MIT AND MIT', id='triple-duplicate'),
    ],
)
def test_duplicate_terms_pass(tmp_path: Path, value: str) -> None:
    # A repeated identifier is legal: the WITH form reuses the same license
    # under a different exception. Token-level duplicate detection fires 74
    # times on the corpus and is almost entirely wrong, so it is not
    # implemented.
    assert _findings(tmp_path, value) == [], value


# --- C1: expression syntax --------------------------------------------------


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        pytest.param('BSD and MIT', '"and" must be upper case', id='lower-and'),
        pytest.param('MIT or Apache-2.0', '"or" must be upper case', id='lower-or'),
        pytest.param('GPL with additional restrictions', '"with" must be upper case', id='lower-with'),
        pytest.param('MIT, BSD-3-Clause', 'use AND / OR instead of ","', id='comma'),
        pytest.param('(MIT OR Apache-2.0', 'unbalanced "("', id='unbalanced-open'),
        pytest.param('MIT OR Apache-2.0)', 'unexpected ")"', id='unbalanced-close'),
        pytest.param('MIT AND', 'must be followed by a license identifier', id='dangling-and'),
        pytest.param('MIT OR', 'must be followed by a license identifier', id='dangling-or'),
        pytest.param('MIT AND Apache-2.0 WITH', 'must be followed by an SPDX exception identifier', id='dangling-with'),
        pytest.param('LGPL-2.1-or-later BSD-3-Clause', 'missing AND / OR before "BSD-3-Clause"', id='missing-operator'),
    ],
)
def test_syntax_error_is_reported(
    tmp_path: Path,
    value: str,
    expected: str,
) -> None:
    findings = _findings(tmp_path, value)
    assert len(findings) == 1, findings
    assert 'invalid SPDX license expression' in findings[0], findings
    assert expected in findings[0], findings


def test_comma_is_not_reported_as_unknown_identifier(tmp_path: Path) -> None:
    # The comma is a syntax problem with an actionable fix; both identifiers
    # around it are valid, so reporting them as unknown would be noise.
    findings = _findings(tmp_path, 'MIT, BSD-3-Clause')
    assert len(findings) == 1, findings
    assert 'unknown' not in findings[0], findings


def test_syntax_error_masks_identifier_errors(tmp_path: Path) -> None:
    # "(A OR B" is both unbalanced and full of unknown identifiers. Only the
    # syntax error is reported, because fixing it can change which identifiers
    # are even visible.
    findings = _findings(tmp_path, '(A OR B')
    assert len(findings) == 1, findings
    assert 'unbalanced "("' in findings[0], findings
    assert 'unknown' not in findings[0], findings


def test_stray_character_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, 'MIT & Apache-2.0')
    assert len(findings) == 1, findings
    assert 'invalid SPDX license expression' in findings[0], findings


# --- C2: unknown identifier -------------------------------------------------


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('FIXME', id='fixme'),
        pytest.param('BSD', id='bsd-bare'),
        pytest.param('MPL-2.0+', id='mpl-plus'),
        pytest.param('GFDL', id='gfdl'),
        pytest.param('CDDL', id='cddl'),
        pytest.param('GPLv3+', id='gplv3-plus'),
        pytest.param('Mulan-2.0', id='mulan-wrong'),
        pytest.param('Public-Domain', id='public-domain-hyphen'),
        pytest.param('OpenRuyi-Public-Domain', id='openruyi-public-domain'),
        pytest.param('ssh-keysign', id='not-a-license'),
    ],
)
def test_unknown_identifier_is_reported(tmp_path: Path, value: str) -> None:
    findings = _findings(tmp_path, value)
    assert any('unknown SPDX license identifier' in f for f in findings), findings


def test_deprecated_identifier_is_accepted(tmp_path: Path) -> None:
    # Deprecated ids stay in the vendored list and therefore stay valid.
    # Neither specification document asks for deprecation to be rejected, and
    # a keyword search over both returns zero hits for it.
    assert _findings(tmp_path, 'ssh-keyscan') == []
    assert _findings(tmp_path, 'BSD-2-Clause-FreeBSD') == []


def test_multi_word_value_is_reported_as_syntax_error(tmp_path: Path) -> None:
    # "Public Domain" is an informal string, not an expression. Two adjacent
    # operands with no connector is the honest description of the shape.
    findings = _findings(tmp_path, 'Public Domain')
    assert len(findings) == 1, findings
    assert 'missing AND / OR before "Domain"' in findings[0], findings


def test_known_exception_in_license_position_is_reported(tmp_path: Path) -> None:
    # Observed on the corpus (man-pages.spec): the "-exception" suffix makes
    # the mix-up obvious, so the message names the real problem instead of
    # claiming the identifier is unknown.
    findings = _findings(
        tmp_path,
        'MIT AND LGPL-3.0-linking-exception',
    )
    assert len(findings) == 1, findings
    assert 'is an SPDX exception identifier' in findings[0], findings
    assert 'must follow "WITH"' in findings[0], findings


def test_unknown_identifier_suggests_close_match(tmp_path: Path) -> None:
    findings = _findings(tmp_path, 'GPL-2.0-or-late')
    assert len(findings) == 1, findings
    assert 'did you mean "GPL-2.0-or-later"' in findings[0], findings


def test_unknown_identifier_without_close_match_has_no_hint(tmp_path: Path) -> None:
    findings = _findings(tmp_path, 'FIXME')
    assert len(findings) == 1, findings
    assert 'did you mean' not in findings[0], findings


def test_unknown_exception_identifier_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, 'Apache-2.0 WITH No-Such-Exception')
    assert len(findings) == 1, findings
    assert 'unknown SPDX exception identifier' in findings[0], findings


def test_exception_checked_against_exception_list_only(tmp_path: Path) -> None:
    # MIT is a license, not an exception, so it is invalid after WITH.
    findings = _findings(tmp_path, 'GPL-2.0-or-later WITH MIT')
    assert len(findings) == 1, findings
    assert 'is an SPDX license identifier, not an exception' in findings[0], (
        findings
    )


def test_license_checked_against_license_list_only(tmp_path: Path) -> None:
    # LLVM-exception is an exception, not a license.
    findings = _findings(tmp_path, 'LLVM-exception')
    assert len(findings) == 1, findings
    assert 'is an SPDX exception identifier' in findings[0], findings
    assert 'must follow "WITH"' in findings[0], findings


def test_license_ref_is_always_valid(tmp_path: Path) -> None:
    assert _findings(tmp_path, 'LicenseRef-Anything-Goes') == []


def test_license_ref_is_valid_after_with_refusal(tmp_path: Path) -> None:
    # LicenseRef-* is a valid expression leaf in every position.
    assert _findings(tmp_path, 'MIT AND LicenseRef-foo') == []


# --- C3: canonical case -----------------------------------------------------


@pytest.mark.parametrize(
    ('value', 'canonical'),
    [
        pytest.param('zlib', 'Zlib', id='zlib'),
        pytest.param('ZLIB', 'Zlib', id='zlib-upper'),
        pytest.param('BSD-2-clause', 'BSD-2-Clause', id='bsd-2-clause'),
        pytest.param('tu-berlin-2.0', 'TU-Berlin-2.0', id='tu-berlin'),
        pytest.param('gpl-2.0-or-later', 'GPL-2.0-or-later', id='gpl'),
        pytest.param('mit', 'MIT', id='mit'),
    ],
)
def test_case_error_suggests_canonical_spelling(
    tmp_path: Path,
    value: str,
    canonical: str,
) -> None:
    findings = _findings(tmp_path, value)
    assert len(findings) == 1, findings
    assert f'must be spelled "{canonical}"' in findings[0], findings
    assert 'case sensitive' in findings[0], findings


def test_case_error_takes_precedence_over_unknown(tmp_path: Path) -> None:
    findings = _findings(tmp_path, 'zlib')
    assert len(findings) == 1, findings
    assert 'unknown' not in findings[0], findings


def test_case_error_inside_expression_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, 'MIT AND zlib')
    assert len(findings) == 1, findings
    assert 'must be spelled "Zlib"' in findings[0], findings


def test_canonical_identifiers_pass(tmp_path: Path) -> None:
    for value in ('Zlib', 'BSD-2-Clause', 'TU-Berlin-2.0', 'GPL-2.0-or-later'):
        assert _findings(tmp_path, value) == [], value


# --- skipped values ---------------------------------------------------------


@pytest.mark.parametrize(
    'value',
    [
        pytest.param('%{license}', id='simple-macro'),
        pytest.param('%{?license}', id='conditional-macro'),
        pytest.param('%{license} AND MIT', id='macro-and'),
    ],
)
def test_macro_value_skips_every_check(tmp_path: Path, value: str) -> None:
    assert _findings(tmp_path, value) == [], value


def test_empty_license_value_is_not_reported(tmp_path: Path) -> None:
    # Presence and emptiness belong to check-spec-basic-fields; reporting them
    # here would double every finding.
    assert _findings(tmp_path, '') == []


def test_missing_license_field_is_not_reported(tmp_path: Path) -> None:
    content = 'Name:           foo\nVersion:        1.0\nRelease:        %autorelease\n'
    path = _write(tmp_path, 'x.spec', content)
    assert _check_spec_license(path) == []


def test_commented_license_line_is_ignored(tmp_path: Path) -> None:
    content = '# License: FIXME\nName: foo\nLicense: MIT\n'
    path = _write(tmp_path, 'x.spec', content)
    assert _check_spec_license(path) == []


# --- line reporting ---------------------------------------------------------


def test_line_number_is_reported(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', _spec('BSD and MIT'))
    assert '(line 3)' in _check_spec_license(path)[0]


def test_multiple_license_lines_are_all_checked(tmp_path: Path) -> None:
    # 69 specs in the corpus declare more than one License line (max 4).
    # Taking only the first would silently skip every subpackage license.
    content = (
        'Name:           foo\n'
        'License:        MIT\n'
        '%package -n foo-devel\n'
        'License:        BSD and MIT\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_license(path)
    assert len(errors) == 1, errors
    assert '(line 4)' in errors[0], errors


def test_subpackage_license_is_checked(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'License:        MIT\n'
        '%package -n foo-devel\n'
        'License:        FIXME\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_license(path)
    assert len(errors) == 1, errors
    assert 'unknown SPDX license identifier "FIXME"' in errors[0], errors


# --- file-level errors ------------------------------------------------------


def test_missing_file_is_reported(tmp_path: Path) -> None:
    path = str(tmp_path / 'nope.spec')
    errors = _check_spec_license(path)
    assert len(errors) == 1, errors
    assert 'nope.spec' in errors[0], errors
    assert 'No such file' in errors[0], errors


def test_non_utf8_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'bad.spec'
    path.write_bytes(b'License: \xff\xfe\n')
    errors = _check_spec_license(str(path))
    assert len(errors) == 1, errors
    assert 'file is not valid UTF-8' in errors[0], errors


def test_empty_file_passes(tmp_path: Path) -> None:
    assert _check_spec_license(_write(tmp_path, 'empty.spec', '')) == []


# --- vendored SPDX data -----------------------------------------------------


def test_spdx_data_is_populated() -> None:
    assert len(LICENSE_IDS) > 600, len(LICENSE_IDS)
    assert len(EXCEPTION_IDS) > 50, len(EXCEPTION_IDS)
    assert 'MIT' in LICENSE_IDS
    assert 'Apache-2.0' in LICENSE_IDS
    assert 'LLVM-exception' in EXCEPTION_IDS


def test_spdx_license_ids_have_no_whitespace() -> None:
    # A whitespace-bearing identifier could never be produced by the tokenizer,
    # which would make the lookup silently unreachable.
    assert all(' ' not in i for i in LICENSE_IDS)
    assert all(' ' not in i for i in EXCEPTION_IDS)
