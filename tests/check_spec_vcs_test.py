# flake8: noqa: E501  -- spec file contents are reproduced verbatim
from __future__ import annotations

from pathlib import Path

import pytest

from openruyi_precommit_hooks.check_spec_vcs import _check_spec_vcs
from openruyi_precommit_hooks.check_spec_vcs import _check_spec_vcs_ext
from openruyi_precommit_hooks.check_spec_vcs import main

# A URL that is not a repository link, so VCS is required.
WEBSITE_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://example.org/foo
VCS:            git:https://git.example.org/foo.git

%description
An example package.

%files
%license LICENSE

%changelog
%autochangelog
"""

# A URL that is itself a repository link, so VCS may be omitted.
REPO_URL_SPEC = """\
Name:           foo
Version:        1.0
Release:        %autorelease
Summary:        Example package
License:        MulanPSL-2.0
URL:            https://github.com/example/foo

%description
An example package.

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
        f'URL:            {url}\n' +
        ''.join(f'{field}\n' for field in fields) +
        '\n'
        '%description\n'
        'An example package.\n'
    )


def _findings(tmp_path: Path, content: str) -> list[str]:
    path = _write(tmp_path, 'x.spec', content)
    return [err.split('x.spec: ', 1)[-1] for err in _check_spec_vcs(path)]


def _findings_ext(
    tmp_path: Path,
    content: str,
    **kwargs: bool,
) -> list[str]:
    path = _write(tmp_path, 'x.spec', content)
    return [
        err.split('x.spec: ', 1)[-1]
        for err in _check_spec_vcs_ext(path, **kwargs)
    ]


# --- baseline ---------------------------------------------------------------


def test_valid_spec_passes(tmp_path: Path) -> None:
    assert _check_spec_vcs(_write(tmp_path, 'ok.spec', WEBSITE_SPEC)) == []


def test_repo_url_spec_without_vcs_passes(tmp_path: Path) -> None:
    assert _check_spec_vcs(_write(tmp_path, 'ok.spec', REPO_URL_SPEC)) == []


def test_main_returns_zero_on_clean_file(tmp_path: Path) -> None:
    path = _write(tmp_path, 'ok.spec', WEBSITE_SPEC)
    assert main([path]) == 0


def test_main_returns_one_on_violation(tmp_path: Path) -> None:
    path = _write(tmp_path, 'bad.spec', _spec())
    assert main([path]) == 1


def test_main_returns_zero_without_filenames() -> None:
    assert main([]) == 0


# --- V1: conditional presence -----------------------------------------------


def test_missing_vcs_is_reported_when_url_is_a_website(
    tmp_path: Path,
) -> None:
    findings = _findings(tmp_path, _spec())
    assert len(findings) == 1
    assert 'VCS field is missing' in findings[0]


@pytest.mark.parametrize(
    'url',
    [
        'https://github.com/example/foo',
        'https://gitlab.com/example/foo',
        'https://gitlab.gnome.org/GNOME/foo',
        'https://invent.kde.org/example/foo',
        'https://salsa.debian.org/example/foo',
        'https://git.kernel.org/pub/scm/foo/bar.git',
        'https://git.savannah.gnu.org/git/foo.git',
        'http://git.savannah.gnu.org/cgit/foo.git',
        'https://codeberg.org/example/foo',
        'https://bitbucket.org/example/foo',
        'https://sourceware.org/git/foo.git',
        'https://chromium.googlesource.com/foo',
        'https://git.sr.ht/~user/foo',
        'https://pagure.io/foo',
        'https://example.org/foo.git',
        'https://example.org/foo.git/',
    ],
)
def test_repository_url_makes_vcs_optional(
    tmp_path: Path,
    url: str,
) -> None:
    assert _findings(tmp_path, _spec(url=url)) == []


@pytest.mark.parametrize(
    'url',
    [
        'https://example.org/foo',
        'https://www.kernel.org/',
        'https://github.com/example',
        'https://gitlab.com/example',
        'https://git.example.org',
        'https://metacpan.org/dist/Foo',
        'https://pypi.org/project/foo',
        'https://crates.io/crates/foo',
        'https://lib.rs/foo',
        'https://docs.rs/foo',
        'https://example.github.io',
        'https://example.readthedocs.io',
    ],
)
def test_non_repository_url_requires_vcs(
    tmp_path: Path,
    url: str,
) -> None:
    findings = _findings(tmp_path, _spec(url=url))
    assert len(findings) == 1
    assert 'VCS field is missing' in findings[0]


def test_documented_placeholder_satisfies_presence(
    tmp_path: Path,
) -> None:
    content = _spec('# VCS: No VCS link available')
    assert _findings(tmp_path, content) == []


def test_placeholder_with_wrong_case_satisfies_presence(
    tmp_path: Path,
) -> None:
    content = _spec('# vcs: No VCS link available')
    assert _findings(tmp_path, content) == []


def test_missing_url_suppresses_v1(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'Release:        %autorelease\n'
        '\n'
        '%description\n'
        'An example package.\n'
    )
    assert _findings(tmp_path, content) == []


def test_empty_url_suppresses_v1(tmp_path: Path) -> None:
    content = _spec(url='')
    assert _findings(tmp_path, content) == []


@pytest.mark.parametrize(
    'url',
    [
        'https://github.com/mreineck/%{name}',
        'https://pypi.org/project/%{srcname}/',
        'https://example.org/%{upstream_name}/foo',
    ],
)
def test_macro_url_suppresses_v1(tmp_path: Path, url: str) -> None:
    assert _findings(tmp_path, _spec(url=url)) == []


def test_vcs_in_subpackage_only_does_not_satisfy_presence(
    tmp_path: Path,
) -> None:
    content = _spec() + (
        '\n'
        '%package -n foo-extra\n'
        'VCS:            git:https://git.example.org/extra.git\n'
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'VCS field is missing' in findings[0]


def test_vcs_after_a_macro_invocation_counts(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'URL:            https://example.org/foo\n'
        '%global debug_package %{nil}\n'
        'VCS:            git:https://git.example.org/foo.git\n'
        '\n'
        '%description\n'
        'An example package.\n'
    )
    assert _findings(tmp_path, content) == []


def test_doc_site_flag_turns_the_doc_site_branch_off(
    tmp_path: Path,
) -> None:
    content = _spec(url='https://metacpan.org/dist/Foo')
    assert _findings_ext(tmp_path, content, check_doc_site=False) == []


def test_doc_site_flag_keeps_the_website_branch(
    tmp_path: Path,
) -> None:
    content = _spec(url='https://example.org/foo')
    findings = _findings_ext(tmp_path, content, check_doc_site=False)
    assert len(findings) == 1
    assert 'VCS field is missing' in findings[0]


def test_main_accepts_the_doc_site_flag(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'doc.spec',
        _spec(url='https://pypi.org/project/foo'),
    )
    assert main([path]) == 1
    assert main(['--no-check-doc-site', path]) == 0


# --- V2: placeholder wording ------------------------------------------------


@pytest.mark.parametrize(
    'text',
    [
        'No reliable VCS link available',
        'No git repo found.',
        'Upstream git dead',
        'This package does not have a VCS link',
        'TODO: Add cvs link here',
        '',
    ],
)
def test_wrong_placeholder_text_is_reported(
    tmp_path: Path,
    text: str,
) -> None:
    findings = _findings(tmp_path, _spec(f'# VCS: {text}'))
    assert len(findings) == 1
    assert 'placeholder comment' in findings[0]


def test_documented_placeholder_text_passes(tmp_path: Path) -> None:
    content = _spec('# VCS: No VCS link available')
    assert _findings(tmp_path, content) == []


# --- V3: mutual exclusion ---------------------------------------------------


def test_field_and_placeholder_together_are_reported(
    tmp_path: Path,
) -> None:
    content = _spec(
        'VCS:            git:https://git.example.org/foo.git',
        '# VCS: No VCS link available',
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'must not both be present' in findings[0]


# --- V4: non-empty value ----------------------------------------------------


def test_empty_vcs_is_reported(tmp_path: Path) -> None:
    findings = _findings(tmp_path, _spec('VCS:'))
    assert len(findings) == 1
    assert 'is empty' in findings[0]


# --- V5: no macro concatenation ---------------------------------------------


@pytest.mark.parametrize(
    'value',
    [
        'git:https://git.example.org/%{name}.git',
        'https://git.example.org/%{srcname}.git',
        'git:http://git.example.org/%{upstream_name}/foo.git',
    ],
)
def test_macro_vcs_is_reported(tmp_path: Path, value: str) -> None:
    findings = _findings(tmp_path, _spec(f'VCS:            {value}'))
    assert len(findings) == 1
    assert 'built from a macro' in findings[0]


def test_macro_vcs_skips_the_cloneable_check(tmp_path: Path) -> None:
    findings = _findings(
        tmp_path,
        _spec('VCS:            %{vcs_url}'),
    )
    assert len(findings) == 1
    assert 'built from a macro' in findings[0]
    assert 'cloneable' not in findings[0]


def test_percent_escape_is_not_a_macro(tmp_path: Path) -> None:
    content = _spec('VCS:            git:https://git.example.org/a%2Bb.git')
    assert _findings(tmp_path, content) == []


def test_percent_escape_with_a_real_macro_is_still_reported(
    tmp_path: Path,
) -> None:
    findings = _findings(
        tmp_path,
        _spec('VCS:            git:https://git.example.org/a%2B%{name}.git'),
    )
    assert len(findings) == 1
    assert 'built from a macro' in findings[0]


# --- V6: cloneable address --------------------------------------------------


@pytest.mark.parametrize(
    'value',
    [
        'git:https://git.example.org/foo.git',
        'git:http://git.example.org/foo',
        'git://git.example.org/foo.git',
        'https://git.example.org/foo.git',
        'https://github.com/example/foo',
        'git+https://git.example.org/foo.git',
        'hg:https://hg.example.org/foo',
        'svn:https://svn.example.org/foo/trunk',
        'ssh://git@git.example.org/foo.git',
        'git@github.com:example/foo.git',
        'git:https://git.example.org/foo/',
    ],
)
def test_cloneable_value_passes(tmp_path: Path, value: str) -> None:
    content = _spec(f'VCS:            {value}')
    assert _findings(tmp_path, content) == []


@pytest.mark.parametrize(
    'value',
    [
        'see the website',
        'upstream',
        'example.org/foo',
        '/usr/src/foo',
        'git:',
        '@@@',
    ],
)
def test_non_cloneable_value_is_reported(
    tmp_path: Path,
    value: str,
) -> None:
    findings = _findings(tmp_path, _spec(f'VCS:            {value}'))
    assert len(findings) == 1
    assert 'is not a cloneable address' in findings[0]


# --- V7: field name spelling ------------------------------------------------


@pytest.mark.parametrize('name', ['VCs', 'Vcs', 'vcs'])
def test_misspelled_field_is_reported(
    tmp_path: Path,
    name: str,
) -> None:
    content = _spec(f'{name}:            git:https://git.example.org/foo.git')
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'is spelled' in findings[0]


def test_misspelled_field_still_validates_its_value(
    tmp_path: Path,
) -> None:
    findings = _findings(tmp_path, _spec('VCs:            not a url'))
    assert len(findings) == 2
    assert any('is spelled' in err for err in findings)
    assert any('is not a cloneable address' in err for err in findings)


def test_misspelled_field_satisfies_presence(tmp_path: Path) -> None:
    content = _spec('VCs:            git:https://git.example.org/foo.git')
    findings = _findings(tmp_path, content)
    assert all('VCS field is missing' not in err for err in findings)


def test_field_case_flag_turns_v7_off(tmp_path: Path) -> None:
    content = _spec('VCs:            git:https://git.example.org/foo.git')
    assert _findings_ext(tmp_path, content, check_field_case=False) == []


def test_field_case_flag_keeps_the_other_checkpoints(
    tmp_path: Path,
) -> None:
    findings = _findings_ext(
        tmp_path,
        _spec('VCs:            not a url'),
        check_field_case=False,
    )
    assert len(findings) == 1
    assert 'is not a cloneable address' in findings[0]


def test_main_accepts_the_field_case_flag(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'vcs.spec',
        _spec('VCs:            git:https://git.example.org/foo.git'),
    )
    assert main([path]) == 1
    assert main(['--no-check-field-case', path]) == 0


# --- scope boundaries -------------------------------------------------------


def test_padding_after_the_colon_is_ignored(tmp_path: Path) -> None:
    content = _spec('VCS:                                            git:https://git.example.org/foo.git')
    assert _findings(tmp_path, content) == []


def test_commented_out_field_is_not_a_placeholder(
    tmp_path: Path,
) -> None:
    content = _spec('# VCS: git:https://git.example.org/foo.git')
    findings = _findings(tmp_path, content)
    assert len(findings) == 1
    assert 'VCS field is missing' in findings[0]


def test_commented_out_vcs_does_not_conflict_with_the_field(
    tmp_path: Path,
) -> None:
    content = _spec(
        'VCS:            git:https://git.example.org/foo.git',
        '# VCS: git:https://git.example.org/old.git',
    )
    assert _findings(tmp_path, content) == []


def test_subpackage_vcs_lines_are_checked(tmp_path: Path) -> None:
    content = _spec() + (
        '\n'
        '%package -n foo-extra\n'
        'VCS:            not a url\n'
    )
    findings = _findings(tmp_path, content)
    assert len(findings) == 2
    assert any('VCS field is missing' in err for err in findings)
    assert any('is not a cloneable address' in err for err in findings)


def test_vcs_before_url_is_not_reported(tmp_path: Path) -> None:
    content = (
        'Name:           foo\n'
        'Version:        1.0\n'
        'VCS:            git:https://git.example.org/foo.git\n'
        'URL:            https://example.org/foo\n'
        '\n'
        '%description\n'
        'An example package.\n'
    )
    assert _findings(tmp_path, content) == []


def test_repeated_identical_findings_are_deduplicated(
    tmp_path: Path,
) -> None:
    content = _spec('VCS:', 'VCS:')
    findings = _findings(tmp_path, content)
    assert findings == ['VCS field (line 5) is empty', 'VCS field (line 6) is empty']


# --- infrastructure ---------------------------------------------------------

def test_missing_file_is_reported(tmp_path: Path) -> None:
    findings = _check_spec_vcs(str(tmp_path / 'absent.spec'))
    assert len(findings) == 1
    assert 'absent.spec' in findings[0]


def test_non_utf8_file_is_reported(tmp_path: Path) -> None:
    path = tmp_path / 'bad.spec'
    path.write_bytes(b'Name: \xff\xfe\n')
    findings = _check_spec_vcs(str(path))
    assert findings == [f'{path}: file is not valid UTF-8']


def test_empty_file_passes(tmp_path: Path) -> None:
    assert _check_spec_vcs(_write(tmp_path, 'empty.spec', '')) == []
