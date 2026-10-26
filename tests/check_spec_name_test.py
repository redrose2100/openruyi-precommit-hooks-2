# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

import openruyi_precommit_hooks.check_spec_name as rule
from openruyi_precommit_hooks.check_spec_name import _check_spec_name
from openruyi_precommit_hooks.check_spec_name import _check_spec_name_ext
from openruyi_precommit_hooks.check_spec_name import main

DOC_PATH = (
    Path(__file__).resolve().parents[1] / 'docs' / 'rules' / 'check-spec-name.md'
)
HOOK_PATH = Path(__file__).resolve().parents[1] / '.pre-commit-hooks.yaml'

VALID_SPEC = """\
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
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(content)
    return str(path)


def _spec(name: str) -> str:
    return f'Name:           {name}\nVersion:        1.0\n'


def _findings(tmp_path: Path, name: str) -> list[str]:
    path = _write(tmp_path, 'x.spec', _spec(name))
    return [err.split('x.spec: ', 1)[-1] for err in _check_spec_name(path)]


# --- baseline ---------------------------------------------------------------


def test_valid_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_name(_write(tmp_path, 'ok.spec', VALID_SPEC)) == []


def test_canonical_entry_point_matches_extended(tmp_path: Path) -> None:
    path = _write(tmp_path, 'ok.spec', VALID_SPEC)
    assert _check_spec_name(path) == _check_spec_name_ext(path)


# --- N1: presence -----------------------------------------------------------


def test_missing_name_is_reported(tmp_path: Path) -> None:
    content = 'Version:        1.0\nSummary:        Example package\n'
    assert _findings_from(tmp_path, content) == ['Name field is missing']


def test_empty_name_is_reported(tmp_path: Path) -> None:
    assert _findings(tmp_path, '') == ['Name field is empty (line 1)']


def test_whitespace_only_name_is_reported(tmp_path: Path) -> None:
    content = 'Name:           \nVersion:        1.0\n'
    assert _findings_from(tmp_path, content) == [
        'Name field is empty (line 1)',
    ]


def test_name_on_later_line_reports_that_line(tmp_path: Path) -> None:
    content = (
        '# a comment\n'
        '\n'
        '%global commit abc123\n'
        '\n'
        'Name:           foo-bar-\n'
    )
    assert _findings_from(tmp_path, content) == [
        'Name "foo-bar-" (line 5) must not start or end with a separator',
    ]


def _findings_from(tmp_path: Path, content: str) -> list[str]:
    path = _write(tmp_path, 'x.spec', content)
    return [err.split('x.spec: ', 1)[-1] for err in _check_spec_name(path)]


# --- N2: legal characters ---------------------------------------------------


@pytest.mark.parametrize(
    'value',
    [
        'foo bar',
        'foo/bar',
        'foo@bar',
        'foo:bar',
        'foo"bar',
        'foo#bar',
    ],
    ids=['space', 'slash', 'at', 'colon', 'quote', 'hash'],
)
def test_invalid_character_is_reported(tmp_path: Path, value: str) -> None:
    errors = _findings(tmp_path, value)
    assert len(errors) == 1, errors
    assert 'contains an invalid character' in errors[0], errors


@pytest.mark.parametrize(
    'value',
    ['foo', 'foo-bar', 'foo_bar', 'foo.bar', 'foo+bar', 'libsigc++', 'a1.b2-c3'],
    ids=['plain', 'dash', 'underscore', 'dot', 'plus', 'libsigc', 'mixed'],
)
def test_legal_value_has_no_character_finding(
    tmp_path: Path, value: str,
) -> None:
    assert not any(
        'invalid character' in err for err in _findings(tmp_path, value)
    )


# --- N3: leading and trailing separators ------------------------------------


@pytest.mark.parametrize(
    'value',
    ['-foo', '_foo', '.foo', 'foo-', 'foo_', 'foo.'],
)
def test_leading_or_trailing_separator_is_reported(
    tmp_path: Path, value: str,
) -> None:
    assert _findings(tmp_path, value) == [
        f'Name "{value}" (line 1) must not start or end with a separator',
    ]


def test_libsigcxx_plus_is_not_a_separator(tmp_path: Path) -> None:
    assert _findings(tmp_path, 'libsigc++') == []


def test_leading_plus_is_not_a_separator(tmp_path: Path) -> None:
    assert _findings(tmp_path, '+foo') == []


# --- N4: consecutive separators ---------------------------------------------


@pytest.mark.parametrize(
    'value',
    [
        'foo--bar',
        'foo__bar',
        'foo..bar',
        'foo-_bar',
        'foo_-bar',
        'foo._bar',
        'foo_.bar',
        'foo-.bar',
        'foo.-bar',
    ],
    ids=[
        'dash-dash',
        'underscore-underscore',
        'dot-dot',
        'dash-underscore',
        'underscore-dash',
        'dot-underscore',
        'underscore-dot',
        'dash-dot',
        'dot-dash',
    ],
)
def test_consecutive_separator_is_reported(
    tmp_path: Path, value: str,
) -> None:
    errors = _findings(tmp_path, value)
    assert len(errors) == 1, errors
    assert 'must not contain consecutive separators' in errors[0], errors


def test_doubled_separator_real_case_reports_exactly_one(
    tmp_path: Path,
) -> None:
    errors = _findings(tmp_path, 'go-github-sean--seed')
    assert errors == [
        'Name "go-github-sean--seed" (line 1) must not contain '
        'consecutive separators "--"',
    ]


# --- N5: duplicate names ----------------------------------------------------


def test_subpackage_reusing_main_name_is_reported(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        '\n'
        '%package -n foo\n'
        'Summary:        sub\n'
    )
    assert _findings_from(tmp_path, content) == [
        'duplicate package name "foo" (line 3), already used by the main '
        'package (line 1)',
    ]


def test_subpackage_duplicate_is_case_insensitive(tmp_path: Path) -> None:
    content = (
        'Name:           Foo\n'
        '\n'
        '%package -n FOO\n'
        'Summary:        sub\n'
    )
    errors = _findings_from(tmp_path, content)
    assert any('duplicate package name' in err for err in errors), errors


def test_derived_subpackage_name_is_not_a_duplicate(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        '\n'
        '%package devel\n'
        'Summary:        sub\n'
        '\n'
        '%package -n %{name}-tools\n'
        'Summary:        sub\n'
    )
    assert _findings_from(tmp_path, content) == []


def test_macro_defined_subpackage_collision_is_reported(
    tmp_path: Path,
) -> None:
    content = (
        '%global sub foo\n'
        '\n'
        'Name:           foo\n'
        '\n'
        '%package -n %{sub}\n'
        'Summary:        sub\n'
    )
    errors = _findings_from(tmp_path, content)
    assert any('duplicate package name' in err for err in errors), errors


# --- N6: case, on by default ------------------------------------------------


@pytest.mark.parametrize(
    'value',
    ['libX11', 'SDL3', 'Catch2', 'ModemManager', 'NetworkManager'],
    ids=['libX11', 'SDL3', 'Catch2', 'ModemManager', 'NetworkManager'],
)
def test_uppercase_name_is_reported_by_default(
    tmp_path: Path, value: str,
) -> None:
    errors = _findings(tmp_path, value)
    assert len(errors) == 1, errors
    assert 'contains uppercase characters' in errors[0], errors


def test_lowercase_name_is_not_reported_by_default(tmp_path: Path) -> None:
    assert _findings(tmp_path, 'foo-bar') == []


@pytest.mark.parametrize(
    'value',
    ['perl-Git', 'perl-PPIx-Utils', 'perl-Scalar-List-Utils'],
    ids=['perl-Git', 'perl-PPIx-Utils', 'perl-Scalar-List-Utils'],
)
def test_perl_names_are_exempt_from_the_case_check(
    tmp_path: Path, value: str,
) -> None:
    assert _findings(tmp_path, value) == []


def test_no_check_case_clears_the_case_finding(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', _spec('libX11'))
    assert _check_spec_name_ext(path, check_case=False) == []


def test_no_check_case_keeps_the_other_findings(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', _spec('LibX11--bad'))
    errors = _check_spec_name_ext(path, check_case=False)
    assert len(errors) == 1, errors
    assert any('consecutive separators' in err for err in errors), errors
    assert not any('uppercase' in err for err in errors), errors


# --- N7: separator, opt-in --------------------------------------------------


@pytest.mark.parametrize(
    'value',
    ['nss_wrapper', 'pam_wrapper', 'lm_sensors', 'sg3_utils'],
)
def test_underscore_is_clean_by_default(tmp_path: Path, value: str) -> None:
    assert _findings(tmp_path, value) == []


@pytest.mark.parametrize(
    'value',
    ['nss_wrapper', 'pam_wrapper', 'lm_sensors', 'sg3_utils'],
)
def test_underscore_is_reported_with_check_separator(
    tmp_path: Path, value: str,
) -> None:
    path = _write(tmp_path, 'x.spec', _spec(value))
    errors = _check_spec_name_ext(path, check_separator=True)
    assert len(errors) == 1, errors
    assert 'contains "_"' in errors[0], errors


def test_check_separator_does_not_affect_dashed_names(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', _spec('nss-wrapper'))
    assert _check_spec_name_ext(path, check_separator=True) == []


# --- N8: the case used by the Source URLs -----------------------------------


OPENBLAS_SPEC = (
    'Name:           openblas\n'
    'Version:        0.3.31\n'
    'Source0:        https://github.com/OpenMathLib/OpenBLAS/releases/'
    'download/v%{version}/OpenBLAS-%{version}.tar.gz\n'
)


def test_source_url_confirming_the_spelling_keeps_the_rule_silent(
    tmp_path: Path,
) -> None:
    content = (
        'Name:           libX11\n'
        'Version:        1.8.13\n'
        'Source0:        https://xorg.freedesktop.org/releases/individual/'
        'lib/%{name}-%{version}.tar.xz\n'
    )
    assert _findings_from(tmp_path, content) == []


def test_source_url_in_the_reverse_direction_is_reported(
    tmp_path: Path,
) -> None:
    """A lowercase name against a capitalized artefact is a finding too."""
    errors = _findings_from(tmp_path, OPENBLAS_SPEC)
    assert len(errors) == 1, errors
    assert 'Source URLs' in errors[0], errors
    assert '"OpenBLAS"' in errors[0], errors


def test_mismatch_replaces_the_case_finding(tmp_path: Path) -> None:
    """N8 and N6 must not both fire: their advice contradicts."""
    content = (
        'Name:           Xwayland\n'
        'Version:        24.1.11\n'
        'Source0:        https://xorg.freedesktop.org/archive/individual/'
        'xserver/xwayland-%{version}.tar.xz\n'
    )
    errors = _findings_from(tmp_path, content)
    assert len(errors) == 1, errors
    assert '"xwayland"' in errors[0], errors
    assert 'uppercase' not in errors[0], errors


def test_github_owner_and_repository_are_evidence(tmp_path: Path) -> None:
    """The repository segment spells the project when the tarball is an API."""
    content = (
        '%global srcname Aflplusplus\n'
        'Name:           %{srcname}\n'
        'Version:        5.02c\n'
        'Source0:        https://github.com/AFLplusplus/AFLplusplus/archive/'
        'refs/tags/v%{version}.tar.gz\n'
    )
    errors = _findings_from(tmp_path, content)
    assert len(errors) == 1, errors
    assert '"AFLplusplus"' in errors[0], errors


def test_url_fragment_names_the_artefact(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Source0:        https://example.com/api/archive/deadbeef.tar.gz'
        '#/Foo-1.0.tar.gz\n'
    )
    errors = _findings_from(tmp_path, content)
    assert len(errors) == 1, errors
    assert '"Foo"' in errors[0], errors


def test_url_tag_alone_is_never_evidence(tmp_path: Path) -> None:
    """A forge lowercases the URL path while the tarball keeps the case."""
    content = (
        'Name:           libXScrnSaver\n'
        'Version:        1.2.5\n'
        'URL:            https://gitlab.freedesktop.org/xorg/lib/'
        'libxscrnsaver\n'
        'Source0:        https://xorg.freedesktop.org/releases/individual/'
        'lib/libXScrnSaver-%{version}.tar.xz\n'
    )
    assert _findings_from(tmp_path, content) == []


def test_a_lowercase_url_does_not_silence_the_case_finding(
    tmp_path: Path,
) -> None:
    """With no Source line there is no evidence, so N6 stands."""
    content = (
        'Name:           libXScrnSaver\n'
        'Version:        1.2.5\n'
        'URL:            https://gitlab.freedesktop.org/xorg/lib/'
        'libxscrnsaver\n'
    )
    errors = _findings_from(tmp_path, content)
    assert len(errors) == 1, errors
    assert 'uppercase' in errors[0], errors


def test_inconclusive_source_leaves_the_case_finding(tmp_path: Path) -> None:
    """The GitHub owner/repo spells ``SDL``, not ``SDL2``."""
    content = (
        'Name:           SDL2\n'
        'Version:        2.32.10\n'
        'Source:         https://github.com/libsdl-org/SDL/archive/refs/tags/'
        'release-%{version}.tar.gz\n'
    )
    errors = _findings_from(tmp_path, content)
    assert len(errors) == 1, errors
    assert 'uppercase' in errors[0], errors


def test_url_tag_is_bound_so_a_relative_source_expands(
    tmp_path: Path,
) -> None:
    content = (
        'Name:           libXft\n'
        'Version:        2.3.8\n'
        'URL:            https://xorg.freedesktop.org\n'
        'Source0:        %{url}/releases/individual/lib/%{name}-%{version}'
        '.tar.xz\n'
    )
    assert _findings_from(tmp_path, content) == []


def test_archive_suffix_and_version_are_stripped(tmp_path: Path) -> None:
    """``LMDB_0.9.36.tgz`` reduces to ``LMDB``, not to ``LMDB_0.9.36``."""
    content = (
        'Name:           lmdb\n'
        'Version:        0.9.36\n'
        'Source0:        https://git.openldap.org/openldap/-/archive/'
        'LMDB_%{version}/openldap-LMDB_%{version}.tar.gz\n'
    )
    errors = _findings_from(tmp_path, content)
    assert len(errors) == 1, errors
    assert '"LMDB"' in errors[0], errors


def test_dot_separated_artefact_is_evidence(tmp_path: Path) -> None:
    content = (
        'Name:           lvm2\n'
        'Version:        2.03.35\n'
        'Source0:        https://sourceware.org/pub/lvm2/releases/LVM2.%{version}'
        '.tgz\n'
    )
    errors = _findings_from(tmp_path, content)
    assert len(errors) == 1, errors
    assert '"LVM2"' in errors[0], errors


def test_no_check_upstream_case_restores_the_case_finding(
    tmp_path: Path,
) -> None:
    content = (
        'Name:           Xwayland\n'
        'Version:        24.1.11\n'
        'Source0:        https://xorg.freedesktop.org/archive/individual/'
        'xserver/xwayland-%{version}.tar.xz\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    errors = _check_spec_name_ext(path, check_upstream_case=False)
    assert len(errors) == 1, errors
    assert 'uppercase' in errors[0], errors


def test_no_check_upstream_case_clears_a_reverse_mismatch(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, 'x.spec', OPENBLAS_SPEC)
    assert _check_spec_name_ext(path, check_upstream_case=False) == []


@pytest.mark.parametrize(
    'segment,version,expected',
    [
        ('OpenBLAS-0.3.31.tar.gz', '0.3.31', 'OpenBLAS'),
        ('libIDL-0.8.14.tar.bz2', '0.8.14', 'libIDL'),
        ('SCons-4.10.1.tar.gz', '4.10.1', 'SCons'),
        ('LVM2.2.03.35.tgz', '2.03.35', 'LVM2'),
        ('LMDB_0.9.36.tar.gz', '0.9.36', 'LMDB'),
        ('release-2.32.10.tar.gz', '2.32.10', 'release'),
        ('hello.c', '1.0', 'hello.c'),
    ],
)
def test_strip_artefact_suffix(
    segment: str, version: str, expected: str,
) -> None:
    assert rule._strip_artefact_suffix(segment, version) == expected


def test_strip_artefact_suffix_swaps_a_dashed_version() -> None:
    """``2.1-3`` is written ``2.1_3`` in the artefact name."""
    assert rule._strip_artefact_suffix(
        'CUnit-2.1_3.tar.bz2', '2.1-3',
    ) == 'CUnit'


def test_strip_artefact_suffix_without_a_version_keeps_the_name() -> None:
    assert rule._strip_artefact_suffix('v5.02c.tar.gz', '') == 'v5.02c'


def test_source_that_is_not_http_carries_no_evidence() -> None:
    lines = [
        'Name:           foo',
        'Version:        1.0',
        'Source0:        foo-%{version}.tar.gz',
        'Source1:        https://example.com/%{name}-%{version}.tar.gz',
    ]
    assert rule._expand_sources(
        lines, {}, 'foo', '1.0', {'version': '1.0'},
    ) == ['https://example.com/foo-1.0.tar.gz']


def test_unresolved_macro_in_a_source_is_dropped() -> None:
    lines = ['Version:        1.0', 'Source0:        %{unknown}/foo.tar.gz']
    assert rule._expand_sources(lines, {}, 'foo', '1.0', {}) == []


# --- Layer 2: opt-in upstream verification ----------------------------------


class _Answers:
    """Stub the two network primitives with a fixed url -> answer table."""

    def __init__(
        self,
        statuses: dict[str, int | None] | None = None,
        indexes: dict[str, str | None] | None = None,
    ) -> None:
        self.statuses = statuses or {}
        self.indexes = indexes or {}
        self.status_calls: list[str] = []
        self.index_calls: list[str] = []

    def status(self, url: str, timeout: float = 10.0) -> int | None:
        self.status_calls.append(url)
        return self.statuses.get(url)

    def field(
        self,
        url: str,
        field: str,
        token: str | None,
        timeout: float = 10.0,
    ) -> str | None:
        self.index_calls.append(url)
        return self.indexes.get(url)


def _install(monkeypatch: pytest.MonkeyPatch, answers: _Answers) -> None:
    monkeypatch.setattr(rule, '_http_status', answers.status)
    monkeypatch.setattr(rule, '_json_field', answers.field)


def test_verify_upstream_confirms_from_a_served_source_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = 'https://xorg.freedesktop.org/archive/libX11-1.8.13.tar.xz'
    answers = _Answers(statuses={url: 200})
    _install(monkeypatch, answers)
    verdict, detail = rule._verify_upstream(
        'libX11', [url], version='1.8.13',
    )
    assert verdict == rule._CONFIRMED
    assert url in detail


def test_verify_upstream_reports_a_conflicting_spelling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = 'https://xorg.freedesktop.org/archive/xwayland-24.1.11.tar.xz'
    answers = _Answers(statuses={url: 200})
    _install(monkeypatch, answers)
    verdict, detail = rule._verify_upstream(
        'Xwayland', [url], version='24.1.11',
    )
    assert verdict == rule._MISMATCH
    assert 'xwayland' in detail


def test_verify_upstream_uses_the_index_when_the_url_is_opaque(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A GitHub archive URL names no artefact, so the API decides."""
    url = 'https://github.com/OpenMathLib/OpenBLAS/releases/download/v1/x.tar.gz'
    api = 'https://api.github.com/repos/OpenMathLib/OpenBLAS'
    answers = _Answers(
        statuses={url: 200},
        indexes={api: 'OpenMathLib/OpenBLAS'},
    )
    _install(monkeypatch, answers)
    verdict, detail = rule._verify_upstream('openblas', [url])
    assert verdict == rule._MISMATCH
    assert 'OpenBLAS' in detail


def test_verify_upstream_confirms_a_canonical_index_spelling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = 'https://github.com/catchorg/Catch2/archive/v1.tar.gz'
    api = 'https://api.github.com/repos/catchorg/Catch2'
    answers = _Answers(statuses={url: 200}, indexes={api: 'catchorg/Catch2'})
    _install(monkeypatch, answers)
    verdict, _ = rule._verify_upstream('Catch2', [url])
    assert verdict == rule._CONFIRMED


def test_verify_upstream_is_undetermined_without_a_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, _Answers())
    verdict, detail = rule._verify_upstream('python-Whoosh', [])
    assert verdict == rule._UNDETERMINED
    assert 'no http Source URL' in detail


def test_verify_upstream_is_undetermined_but_specific_when_served(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 200 whose URLs spell nothing comparable is still a reportable miss."""
    url = 'https://github.com/libsdl-org/SDL/archive/release-2.tar.gz'
    answers = _Answers(statuses={url: 200})
    _install(monkeypatch, answers)
    verdict, detail = rule._verify_upstream('SDL2', [url], version='2')
    assert verdict == rule._UNDETERMINED
    assert 'github.com' in detail
    assert 'no comparable project name' in detail


def test_verify_upstream_names_the_unreachable_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = 'https://downloads.example.org/foo-1.0.tar.gz'
    _install(monkeypatch, _Answers(statuses={url: None}))
    verdict, detail = rule._verify_upstream('foo', [url])
    assert verdict == rule._UNDETERMINED
    assert 'downloads.example.org' in detail


def test_verify_upstream_prefers_the_source_url_over_the_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The index is never consulted once the download URL has spoken."""
    url = 'https://example.org/xwayland-24.1.11.tar.xz'
    answers = _Answers(statuses={url: 200})
    _install(monkeypatch, answers)
    rule._verify_upstream('Xwayland', [url], version='24.1.11')
    assert answers.index_calls == []


def test_verify_file_reports_a_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = (
        'Name:           waybar\n'
        'Version:        0.15.0\n'
        'Source0:        https://example.org/Waybar-%{version}.tar.gz\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    url = 'https://example.org/Waybar-0.15.0.tar.gz'
    monkeypatch.setattr(
        rule,
        '_http_status',
        lambda candidate, timeout=1.0: 200 if candidate == url else None,
    )
    findings = rule._verify_file(path, 1.0)
    assert len(findings) == 1, findings
    assert 'is not spelled the way upstream writes it' in findings[0], findings


def test_verify_file_silences_a_confirmed_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = (
        'Name:           Catch2\n'
        'Version:        3.14.0\n'
        'Source0:        https://example.org/Catch2-%{version}.tar.gz\n'
    )
    path = _write(tmp_path, 'x.spec', content)
    url = 'https://example.org/Catch2-3.14.0.tar.gz'
    monkeypatch.setattr(
        rule,
        '_http_status',
        lambda candidate, timeout=1.0: 200 if candidate == url else None,
    )
    assert rule._verify_file(path, 1.0) == []


def test_verify_file_without_a_name_field_is_silent(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', 'Version:        1.0\n')
    assert rule._verify_file(path, 1.0) == []


@pytest.mark.parametrize(
    'url,answer,expected,expected_call',
    [
        (
            'https://github.com/o/r/archive/v1.tar.gz',
            'o/r',
            'r',
            'https://api.github.com/repos/o/r',
        ),
        (
            'https://gitlab.freedesktop.org/xorg/lib/x-1.tar.xz',
            'xorg/lib',
            'lib',
            'https://gitlab.freedesktop.org/api/v4/projects/xorg%2Flib',
        ),
        (
            'https://files.pythonhosted.org/packages/source/w/W/W-2.tar.gz',
            'Whoosh',
            'Whoosh',
            'https://pypi.org/pypi/W/json',
        ),
        (
            'https://static.crates.io/crates/foo/foo-0.1.crate',
            'serde',
            'serde',
            'https://crates.io/api/v1/crates/W',
        ),
    ],
    ids=['github', 'gitlab', 'pypi', 'crates'],
)
def test_index_spelling_per_host_family(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    answer: str,
    expected: str,
    expected_call: str,
) -> None:
    """Each host family is asked through its own canonical endpoint."""
    calls: list[str] = []

    def field(
        candidate: str,
        name: str,
        token: str | None,
        timeout: float = 1.0,
    ) -> str | None:
        calls.append(candidate)
        return answer

    monkeypatch.setattr(rule, '_json_field', field)
    assert rule._index_spelling(url, '', 'W', 1.0) == expected
    assert calls == [expected_call], calls


@pytest.mark.parametrize(
    'url,answer,expected',
    [
        ('https://github.com/o/r/archive/v1.tar.gz', 'other/pair', 'pair'),
        ('https://crates.io/crates/foo', None, None),
    ],
    ids=['github-repo-segment', 'no-answer'],
)
def test_index_spelling_unwraps_the_index_answer(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    answer: str | None,
    expected: str | None,
) -> None:
    """An owner/repo answer is unwrapped; a missing answer stays missing."""
    calls: list[str] = []

    def field(
        candidate: str,
        name: str,
        token: str | None,
        timeout: float = 1.0,
    ) -> str | None:
        calls.append(candidate)
        return answer

    monkeypatch.setattr(rule, '_json_field', field)
    assert rule._index_spelling(url, '', 'r', 1.0) == expected
    assert len(calls) == 1, calls


def test_index_spelling_ignores_unknown_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = _Answers()
    _install(monkeypatch, answers)
    url = 'https://downloads.example.org/foo/foo-1.0.tar.gz'
    assert rule._index_spelling(url, '', 'foo', 1.0) is None
    assert answers.index_calls == []


def test_upstream_tokens_strips_the_distribution_prefix() -> None:
    assert rule._upstream_tokens('python-Whoosh') == ['python-Whoosh', 'Whoosh']
    assert rule._upstream_tokens('perl-Git') == ['perl-Git', 'Git']
    assert rule._upstream_tokens('libX11') == ['libX11']
    assert rule._upstream_tokens('python-') == ['python-']


def test_http_status_reports_404_and_swallows_transport_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import urllib.error

    def raiser(code: int) -> object:
        def factory(*args: object, **kwargs: object) -> object:
            raise urllib.error.HTTPError(
                'u', code, 'e', {}, None,  # type: ignore[arg-type]
            )

        return factory

    monkeypatch.setattr(rule.urllib.request, 'urlopen', raiser(404))
    assert rule._http_status('https://example.org/x') == 404
    monkeypatch.setattr(rule.urllib.request, 'urlopen', raiser(500))
    assert rule._http_status('https://example.org/x') is None

    def broken(*args: object, **kwargs: object) -> object:
        raise urllib.error.URLError('no dns')

    monkeypatch.setattr(rule.urllib.request, 'urlopen', broken)
    assert rule._http_status('https://example.org/x') is None


def test_http_status_returns_200(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Reply:
        status = 200

        def __enter__(self) -> _Reply:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def opener(*args: object, **kwargs: object) -> _Reply:
        return _Reply()

    monkeypatch.setattr(rule.urllib.request, 'urlopen', opener)
    assert rule._http_status('https://example.org/x') == 200


def test_json_field_walks_a_dotted_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Reply:
        def __enter__(self) -> _Reply:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"a": {"b": "c"}, "n": 7}'

    monkeypatch.setattr(
        rule.urllib.request,
        'urlopen',
        lambda *args, **kwargs: _Reply(),
    )
    assert rule._json_field('https://x/y', 'a.b', None, 1.0) == 'c'
    assert rule._json_field('https://x/y', 'a.z', None, 1.0) is None
    assert rule._json_field('https://x/y', 'n', None, 1.0) is None
    assert rule._json_field('https://x/y', 'a.b.c', None, 1.0) is None


def test_verify_upstream_is_not_registered_as_a_hook() -> None:
    """Layer 2 opens sockets, so it must never run inside the hook."""
    text = HOOK_PATH.read_text(encoding='utf-8')
    assert 'verify-upstream' not in text
    assert '- id: check-spec-name' in text


def test_main_accepts_no_check_upstream_case(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', OPENBLAS_SPEC)
    assert main([path]) == 1
    assert main(['--no-check-upstream-case', path]) == 0


def test_main_parses_the_verification_flags() -> None:
    assert main(['--verify-upstream', '--upstream-workers', '2',
                 '--upstream-timeout', '0.5']) == 0


# --- macro-valued names -----------------------------------------------------


def test_full_macro_name_skips_value_checks(tmp_path: Path) -> None:
    assert _findings(tmp_path, '%{pypi_name}') == []


def test_trailing_macro_name_skips_value_checks(tmp_path: Path) -> None:
    assert _findings(tmp_path, '%{name}_SUFFIX') == []


def test_braced_less_percent_skips_value_checks(tmp_path: Path) -> None:
    """A bare ``%`` may be a legacy macro reference, so the value is skipped."""
    assert _findings(tmp_path, 'foo%bar') == []


def test_embedded_macro_is_resolved_for_later_checks(tmp_path: Path) -> None:
    content = (
        '%global maj_ver 18\n'
        '\n'
        'Name:           llvm%{maj_ver}\n'
        '\n'
        '%package -n llvm%{maj_ver}-devel\n'
        'Summary:        sub\n'
    )
    assert _findings_from(tmp_path, content) == []


# --- line-by-line parsing regression ----------------------------------------


def test_whole_file_search_would_have_missed_this(tmp_path: Path) -> None:
    """A non-MULTILINE search over the whole text never matches."""
    content = (
        'Summary:        Example package\n'
        'Version:        1.0\n'
        'Name:           foo bar\n'
    )
    errors = _findings_from(tmp_path, content)
    assert len(errors) == 1, errors
    assert 'line 3' in errors[0], errors


def test_comment_lines_are_not_treated_as_the_name_field(
    tmp_path: Path,
) -> None:
    content = (
        '# Name:           comment-only\n'
        'Name:           foo\n'
    )
    assert _findings_from(tmp_path, content) == []


# --- error handling ---------------------------------------------------------


def test_non_utf8_file(tmp_path: Path) -> None:
    path = tmp_path / 'bad.spec'
    path.write_bytes(b'Name: foo\n\xff\xfe\n')
    errors = _check_spec_name(str(path))
    assert errors == [f'{path}: file is not valid UTF-8']


def test_missing_file(tmp_path: Path) -> None:
    path = str(tmp_path / 'nope.spec')
    errors = _check_spec_name(path)
    assert len(errors) == 1
    assert errors[0].startswith(f'{path}: ')


def test_errors_are_prefixed_and_deduplicated(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', 'Version:        1.0\n')
    errors = _check_spec_name(path)
    assert errors, errors
    assert all(err.startswith(f'{path}: ') for err in errors), errors
    assert len(errors) == len(set(errors)), errors


def test_reporting_order_is_stable(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', _spec('Foo--bar_'))
    first = _check_spec_name(path)
    second = _check_spec_name(path)
    assert first == second
    assert [err.split('x.spec: ', 1)[-1][:8] for err in first] == [
        err.split('x.spec: ', 1)[-1][:8] for err in second
    ]


# --- main -------------------------------------------------------------------


def test_main_returns_zero_for_valid_file(tmp_path: Path) -> None:
    assert main([_write(tmp_path, 'ok.spec', VALID_SPEC)]) == 0


def test_main_returns_one_for_invalid_file(tmp_path: Path) -> None:
    assert main([_write(tmp_path, 'bad.spec', _spec('libX11'))]) == 1


def test_main_without_filenames_returns_zero() -> None:
    assert main([]) == 0


def test_main_accepts_no_check_case(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', _spec('libX11'))
    assert main([path]) == 1
    assert main(['--no-check-case', path]) == 0


def test_main_accepts_check_separator(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', _spec('nss_wrapper'))
    assert main([path]) == 0
    assert main(['--check-separator', path]) == 1


# --- documentation examples -------------------------------------------------


def _doc_examples() -> list[tuple[str, str, bool, bool, bool, list[str]]]:
    """Yield (heading, spec, case, separator, upstream, expected) pairs."""
    lines = DOC_PATH.read_text(encoding='utf-8').splitlines()
    examples: list[tuple[str, str, bool, bool, bool, list[str]]] = []
    heading = ''
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith('### '):
            heading = line[4:].strip()
        if line.strip() != '```spec':
            index += 1
            continue
        body: list[str] = []
        index += 1
        while lines[index].strip() != '```':
            body.append(lines[index])
            index += 1
        expected: list[str] = []
        following = index + 1
        while (
            following < len(lines)
            and not lines[following].strip().startswith('```')
            and not lines[following].startswith('#')
        ):
            following += 1
        if following < len(lines) and lines[following].strip() == '```':
            following += 1
            while lines[following].strip() != '```':
                expected.append(lines[following])
                following += 1
            index = following
        examples.append(
            (
                heading,
                '\n'.join(body) + '\n',
                '--no-check-case' not in heading,
                '--check-separator' in heading,
                '--no-check-upstream-case' not in heading,
                expected,
            ),
        )
        index += 1
    return examples


DOC_EXAMPLES = _doc_examples()


def test_documentation_has_examples() -> None:
    assert len(DOC_EXAMPLES) >= 8, len(DOC_EXAMPLES)
    passing = [case for case in DOC_EXAMPLES if not case[5]]
    failing = [case for case in DOC_EXAMPLES if case[5]]
    assert len(passing) >= 3, len(passing)
    assert len(failing) >= 5, len(failing)


@pytest.mark.parametrize(
    'heading,spec,check_case,check_separator,check_upstream_case,expected',
    DOC_EXAMPLES,
    ids=[case[0] for case in DOC_EXAMPLES],
)
def test_documentation_example(
    tmp_path: Path,
    heading: str,
    spec: str,
    check_case: bool,
    check_separator: bool,
    check_upstream_case: bool,
    expected: list[str],
) -> None:
    path = _write(tmp_path, 'foo.spec', spec)
    errors = _check_spec_name_ext(
        path,
        check_case=check_case,
        check_separator=check_separator,
        check_upstream_case=check_upstream_case,
    )
    actual = [err.replace(path, 'foo.spec') for err in errors]
    assert actual == expected, heading
