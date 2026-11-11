# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_source import _check_spec_source
from openruyi_precommit_hooks.check_spec_source import _check_spec_source_ext
from openruyi_precommit_hooks.check_spec_source import main

# The SHA-256 used by every "valid" example. The value is arbitrary; only
# its shape matters to the rule.
SHA = 'a' * 64

# A spec that satisfies every checkpoint: one network source, annotated by
# a RemoteAsset comment that carries a sha256, numbered from 0.
CLEAN_SPEC = f"""\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
VCS:            git:https://git.example.org/foo.git
#!RemoteAsset:  sha256:{SHA}
Source0:        https://example.org/foo-%{{version}}.tar.gz

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A spec with no source input at all, which the document allows.
NO_SOURCE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
VCS:            git:https://git.example.org/foo.git

%description
An example package, built from no source input.

%files
%license LICENSE

%changelog
%autochangelog
"""


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding='utf-8', newline='\n')
    return str(path)


def _spec(*fields: str, url: str = 'https://example.org/foo') -> str:
    return (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        f'URL:            {url}\n'
        + ''.join(f'{field}\n' for field in fields)
        + '\n'
        '%description\n'
        'An example package.\n'
    )


def _findings(tmp_path: Path, content: str) -> list[str]:
    path = _write(tmp_path, 'x.spec', content)
    return [err.split('x.spec: ', 1)[-1] for err in _check_spec_source(path)]


def _findings_ext(
    tmp_path: Path,
    content: str,
    **kwargs: bool,
) -> list[str]:
    path = _write(tmp_path, 'x.spec', content)
    return [
        err.split('x.spec: ', 1)[-1]
        for err in _check_spec_source_ext(path, **kwargs)
    ]


# --- baseline ---------------------------------------------------------------


def test_clean_spec_reports_nothing(tmp_path: Path) -> None:
    assert _findings(tmp_path, CLEAN_SPEC) == []


def test_spec_without_source_reports_nothing(tmp_path: Path) -> None:
    assert _findings(tmp_path, NO_SOURCE_SPEC) == []


def test_bare_source_is_accepted(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source:         https://example.org/foo-1.0.tar.gz',
    )
    assert _findings(tmp_path, content) == []


def test_two_numbered_sources_are_accepted(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://example.org/foo-1.0.tar.gz',
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source1:        https://example.org/foo-1.0-extra.tar.gz',
    )
    assert _findings(tmp_path, content) == []


def test_local_file_source_is_accepted(tmp_path: Path) -> None:
    content = _spec('Source0:        foo.conf')
    assert _findings(tmp_path, content) == []


def test_macro_only_source_name_is_accepted(tmp_path: Path) -> None:
    content = _spec('Source0:        %{name}-%{version}.tar.gz')
    assert _findings(tmp_path, content) == []


# --- S1: duplicate index ----------------------------------------------------


def test_source_and_source0_clash(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source:         https://example.org/foo-1.0.tar.gz',
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://example.org/foo-1.0-extra.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'repeats source index 0' in findings[0]
    assert 'Source and Source0 both mean index 0' in findings[0]


def test_duplicate_numbered_index(tmp_path: Path) -> None:
    content = _spec(
        'Source0:        foo-1.0.tar.gz',
        'Source1:        foo-2.0.tar.gz',
        'Source1:        foo-3.0.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'repeats source index 1' in findings[0]


def test_distinct_indices_do_not_clash(tmp_path: Path) -> None:
    content = _spec(
        'Source0:        foo-1.0.tar.gz',
        'Source1:        foo-1.0-extra.tar.gz',
    )
    assert _findings(tmp_path, content) == []


# --- S2: empty value --------------------------------------------------------


def test_empty_source_value(tmp_path: Path) -> None:
    content = _spec('Source:')
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'Source field (line 5) is empty' in findings[0]


def test_empty_numbered_source_value(tmp_path: Path) -> None:
    content = _spec('Source2:        ')
    findings = _findings(tmp_path, content)
    assert any('Source2 field' in finding and 'is empty' in finding
               for finding in findings)


# --- S3: RemoteAsset presence ----------------------------------------------


def test_network_source_without_remote_asset(tmp_path: Path) -> None:
    content = _spec('Source0:        https://example.org/foo-1.0.tar.gz')
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'is a network source but has no "#!RemoteAsset:"' in findings[0]


def test_remote_asset_separated_by_blank_line(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        '',
        'Source0:        https://example.org/foo-1.0.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert any('is a network source but has no' in finding
               for finding in findings)


def test_remote_asset_after_source_does_not_count(tmp_path: Path) -> None:
    content = _spec(
        'Source0:        https://example.org/foo-1.0.tar.gz',
        f'#!RemoteAsset:  sha256:{SHA}',
    )
    findings = _findings(tmp_path, content)
    assert any('is a network source but has no' in finding
               for finding in findings)


def test_ftp_source_needs_no_remote_asset(tmp_path: Path) -> None:
    content = _spec('Source0:        ftp://example.org/foo-1.0.tar.gz')
    assert _findings(tmp_path, content) == []


def test_url_prefix_is_resolved_before_the_network_test(
    tmp_path: Path,
) -> None:
    content = _spec('Source0:        %{url}/archive/v%{version}.tar.gz')
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'is a network source but has no' in findings[0]


def test_url_prefix_with_remote_asset_is_clean(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        %{url}/archive/v%{version}.tar.gz',
    )
    assert _findings(tmp_path, content) == []


# --- S4: checksum -----------------------------------------------------------


def test_bare_remote_asset_is_reported_as_empty(tmp_path: Path) -> None:
    content = _spec(
        '#!RemoteAsset',
        'Source0:        https://example.org/foo-1.0.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'is empty' in findings[0]
    assert 'sha256' in findings[0]


def test_remote_asset_with_short_checksum(tmp_path: Path) -> None:
    content = _spec(
        '#!RemoteAsset:  sha256:abc123',
        'Source0:        https://example.org/foo-1.0.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'carries no sha256 checksum' in findings[0]


def test_remote_asset_with_sha1_checksum(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha1:{"b" * 40}',
        'Source0:        https://example.org/foo-1.0.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'carries no sha256 checksum' in findings[0]


def test_remote_asset_with_uppercase_checksum(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA.upper()}',
        'Source0:        https://example.org/foo-1.0.tar.gz',
    )
    assert _findings(tmp_path, content) == []


def test_remote_asset_with_spaced_checksum(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:  {SHA}',
        'Source0:        https://example.org/foo-1.0.tar.gz',
    )
    assert _findings(tmp_path, content) == []


def test_local_source_with_remote_asset_is_still_checked(
    tmp_path: Path,
) -> None:
    content = _spec(
        '#!RemoteAsset',
        'Source0:        foo.conf',
    )
    findings = _findings(tmp_path, content)
    # A local file needs no checksum, so the network checks stay silent,
    # but the comment is not orphaned either: it annotates the Source.
    assert findings == []


# --- S5: CreateArchive required --------------------------------------------


def test_git_remote_asset_without_create_archive(tmp_path: Path) -> None:
    content = _spec(
        '#!RemoteAsset:  git+https://example.org/foo.git#v%{version}',
        'Source0:        foo-%{version}.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'so "#!CreateArchive" must come' in findings[0]


def test_git_remote_asset_with_create_archive_is_clean(
    tmp_path: Path,
) -> None:
    content = _spec(
        '#!RemoteAsset:  git+https://example.org/foo.git#v%{version}',
        '#!CreateArchive',
        'Source0:        foo-%{version}.tar.gz',
    )
    assert _findings(tmp_path, content) == []


def test_git_protocol_remote_asset_without_create_archive(
    tmp_path: Path,
) -> None:
    content = _spec(
        '#!RemoteAsset:  git://example.org/foo.git#v%{version}',
        'Source0:        foo-%{version}.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert any('so "#!CreateArchive" must come' in finding
               for finding in findings)


def test_svn_remote_asset_without_create_archive(tmp_path: Path) -> None:
    content = _spec(
        '#!RemoteAsset:  svn://example.org/foo/trunk',
        'Source0:        foo-%{version}.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert any('so "#!CreateArchive" must come' in finding
               for finding in findings)


def test_https_remote_asset_needs_no_create_archive(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://example.org/foo-1.0.tar.gz',
    )
    assert _findings(tmp_path, content) == []


# --- S6: CreateArchive placement -------------------------------------------


def test_create_archive_without_remote_asset(tmp_path: Path) -> None:
    content = _spec(
        '#!CreateArchive',
        'Source0:        foo-%{version}.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert any('must come directly after the "#!RemoteAsset:"' in finding
               for finding in findings)


def test_create_archive_without_source(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        '#!CreateArchive',
        'BuildSystem:    cmake',
    )
    findings = _findings(tmp_path, content)
    assert any('must come directly before the Source line' in finding
               for finding in findings)


def test_create_archive_with_blank_line_before_source(
    tmp_path: Path,
) -> None:
    content = _spec(
        '#!RemoteAsset:  git+https://example.org/foo.git#v%{version}',
        '#!CreateArchive',
        '',
        'Source0:        foo-%{version}.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert any('must come directly before the Source line' in finding
               for finding in findings)


# --- S7: orphan RemoteAsset -------------------------------------------------


def test_orphan_remote_asset(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'BuildSystem:    cmake',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'does not annotate a Source line' in findings[0]


def test_remote_asset_before_patch_is_orphan(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Patch0:         foo-fix.patch',
    )
    findings = _findings(tmp_path, content)
    assert any('does not annotate a Source line' in finding
               for finding in findings)


def test_remote_asset_above_create_archive_is_not_orphan(
    tmp_path: Path,
) -> None:
    content = _spec(
        '#!RemoteAsset:  git+https://example.org/foo.git#v%{version}',
        '#!CreateArchive',
        'Source0:        foo-%{version}.tar.gz',
    )
    assert _findings(tmp_path, content) == []


# --- S8: field case ---------------------------------------------------------


@pytest.mark.parametrize('name', ['source', 'SOURCE', 'SourceX', 'Sources'])
def test_misspelled_source_field(tmp_path: Path, name: str) -> None:
    content = _spec(f'{name}:        foo-1.0.tar.gz')
    findings = _findings(tmp_path, content)
    assert any('is spelled' in finding for finding in findings)


@pytest.mark.parametrize('name', ['Source', 'Source0', 'Source1', 'Source42'])
def test_correctly_spelled_source_field(
    tmp_path: Path,
    name: str,
) -> None:
    content = _spec(f'{name}:        foo-1.0.tar.gz')
    findings = _findings(tmp_path, content)
    assert not any('is spelled' in finding for finding in findings)


def test_case_check_can_be_disabled(tmp_path: Path) -> None:
    content = _spec('source:         foo-1.0.tar.gz')
    findings = _findings_ext(tmp_path, content, check_field_case=False)
    assert not any('is spelled' in finding for finding in findings)


# --- S9: index sequence -----------------------------------------------------


def test_index_gap_after_zero(tmp_path: Path) -> None:
    content = _spec(
        'Source0:        foo.tar.gz',
        'Source2:        bar.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'are not numbered from 0' in findings[0]
    assert 'index 1 is missing' in findings[0]


def test_index_starting_at_one(tmp_path: Path) -> None:
    content = _spec('Source1:        foo.tar.gz')
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'index 0 is missing' in findings[0]


def test_index_gap_is_truncated_in_the_message(tmp_path: Path) -> None:
    content = _spec(
        'Source0:        a.tar.gz',
        'Source10:       b.tar.gz',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert ', ...' in findings[0]


def test_contiguous_indices_report_nothing(tmp_path: Path) -> None:
    content = _spec(
        'Source0:        a.tar.gz',
        'Source1:        b.tar.gz',
        'Source2:        c.tar.gz',
    )
    assert _findings(tmp_path, content) == []


def test_bare_source_counts_as_index_zero(tmp_path: Path) -> None:
    content = _spec(
        'Source:         a.tar.gz',
        'Source1:        b.tar.gz',
    )
    assert _findings(tmp_path, content) == []


def test_index_sequence_can_be_disabled(tmp_path: Path) -> None:
    content = _spec(
        'Source0:        a.tar.gz',
        'Source2:        b.tar.gz',
    )
    findings = _findings_ext(tmp_path, content, check_index_sequence=False)
    assert findings == []


# --- S10: SourceForge -------------------------------------------------------


@pytest.mark.parametrize(
    'url',
    [
        'https://download.sourceforge.net/foo/foo-1.0.tar.gz',
        'http://prdownloads.sourceforge.net/foo/foo-1.0.tar.gz',
        'https://sourceforge.net/projects/foo/files/1.0/foo-1.0.tar.gz',
    ],
)
def test_sourceforge_wrong_host(tmp_path: Path, url: str) -> None:
    content = _spec(f'#!RemoteAsset:  sha256:{SHA}', f'Source0:        {url}')
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'uses the SourceForge host' in findings[0]
    assert 'downloads.sourceforge.net' in findings[0]


def test_sourceforge_correct_host(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://downloads.sourceforge.net/foo/foo-1.0.tar.gz',
    )
    assert _findings(tmp_path, content) == []


def test_sourceforge_host_match_is_not_a_substring_match(
    tmp_path: Path,
) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://downloads.sourceforge.net.example.org/foo.tar.gz',
    )
    assert _findings(tmp_path, content) == []


# --- S11: derivable tarball name -------------------------------------------


def test_source_ending_in_directory(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://example.org/foo/1.0/',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'a directory path' in findings[0]


def test_source_with_query_string_and_no_fragment(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://example.org/download.cgi?file=foo',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'a query string and no URL fragment' in findings[0]


def test_source_with_query_string_and_fragment(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://example.org/download.cgi?file=foo#/foo.tar.gz',
    )
    assert _findings(tmp_path, content) == []


def test_conditional_macro_question_mark_is_not_a_query(
    tmp_path: Path,
) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://example.org/foo-%{version}%{?rc:-rc%{rc}}.tar.gz',
    )
    assert _findings(tmp_path, content) == []


def test_plain_file_name_is_accepted(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://example.org/foo-1.0.tar.gz',
    )
    assert _findings(tmp_path, content) == []


# --- S12: %sourcelist ------------------------------------------------------


def test_sourcelist_block_is_accepted(tmp_path: Path) -> None:
    content = _spec(
        '%sourcelist',
        'foo.conf',
        'bar.conf',
    )
    assert _findings(tmp_path, content) == []


def test_sourcelist_with_argument(tmp_path: Path) -> None:
    content = _spec(
        '%sourcelist foo.conf',
        'bar.conf',
    )
    findings = _findings(tmp_path, content)
    assert any('must be written alone on its line' in finding
               for finding in findings)


def test_sourcelist_without_entries(tmp_path: Path) -> None:
    content = _spec('%sourcelist')
    findings = _findings(tmp_path, content)
    assert any('is not followed by any file' in finding
               for finding in findings)


def test_sourcelist_before_a_section(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'URL:            https://example.org/foo\n'
        '%sourcelist\n'
        '\n'
        '%description\n'
        'An example package.\n'
    )
    findings = _findings(tmp_path, content)
    assert any('is not followed by any file' in finding
               for finding in findings)


# --- scope boundaries ------------------------------------------------------


def test_source_after_description_is_out_of_scope(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        'URL:            https://example.org/foo\n'
        '\n'
        '%description\n'
        'Source0:        https://example.org/foo-1.0.tar.gz\n'
    )
    assert _findings(tmp_path, content) == []


def test_local_name_without_comment_is_out_of_scope(tmp_path: Path) -> None:
    content = _spec('Source0:        foo.conf')
    assert _findings(tmp_path, content) == []


def test_reachability_is_out_of_scope(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://does-not-exist.invalid/foo-1.0.tar.gz',
    )
    assert _findings(tmp_path, content) == []


def test_field_order_is_out_of_scope(tmp_path: Path) -> None:
    content = _spec(
        f'#!RemoteAsset:  sha256:{SHA}',
        'Source0:        https://example.org/foo-1.0.tar.gz',
        'BuildSystem:    cmake',
        'BuildArch:      noarch',
    )
    assert _findings(tmp_path, content) == []


# --- infrastructure --------------------------------------------------------


def test_invalid_utf8(tmp_path: Path) -> None:
    path = tmp_path / 'bad.spec'
    path.write_bytes(b'Name: foo\xff\xfe\n')
    findings = _check_spec_source(str(path))
    assert len(findings) == 1
    assert 'file is not valid UTF-8' in findings[0]


def test_missing_file(tmp_path: Path) -> None:
    findings = _check_spec_source(str(tmp_path / 'nope.spec'))
    assert len(findings) == 1


def test_main_exit_code_zero_for_clean_spec(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', CLEAN_SPEC)
    assert main([path]) == 0


def test_main_exit_code_one_for_findings(tmp_path: Path) -> None:
    path = _write(tmp_path, 'x.spec', _spec('Source0:'))
    assert main([path]) == 1


def test_main_without_filenames() -> None:
    assert main([]) == 0


def test_dedup_keeps_one_finding_per_message(tmp_path: Path) -> None:
    content = _spec('Source:', 'Source:')
    findings = _findings(tmp_path, content)
    # Two declarations report S1 for the clash and S2 for each empty
    # value; identical messages are collapsed.
    assert len(findings) == len(set(findings))
