"""Enforce the openRuyi subpackaging clauses of a spec file.

The packaging guidelines describe subpackaging in the ``Subpackaging and
Splitting Rules`` section of the main guidelines, and the
``SplitPackage`` supplement adds the file placement rules that the section
only summarises. Together they supply five checkpoints:

* P1 - a subpackage name uses ``-`` as its separator.
* P2 - development content is packaged in the ``-devel`` subpackage.
* P3 - a ``-devel`` subpackage carries no versioned shared library.
* P4 - the unversioned ``lib*.so`` link lives in the ``-devel``
  subpackage.
* P5 - a subpackage that requires its base package pins the version.

The strength of the underlying wording differs, so each checkpoint names
its source:

* P1 is MUST level. The supplement writes that the ``-`` is the separator
  of a subpackage name and that ``_``, ``+`` and ``.`` are not allowed,
  with an explicit carve out for special cases. Two of those three
  characters are reported here and ``+`` is not, because a Rust feature
  subpackage is spelled ``%{name}+serde`` and the repository writes 8183
  of them, so ``+`` is the carve out rather than a defect.
* P2 is MUST level. Clause 2 of the main guidelines says that development
  files must be split into ``%{name}-devel`` when they exist, and the
  supplement lists the content of that subpackage.
* P3 is MUST level. The supplement divides ``%{_libdir}`` into three
  classes and says that the real file ``libfoo.so.3.2.0`` and the SONAME
  link ``libfoo.so.3`` must not be in ``-devel``.
* P4 is MUST level. The same division says that the unversioned link
  ``libfoo.so`` must be in ``-devel``, because it is the link the linker
  needs and nothing at run time.
* P5 is MUST level. The supplement's ``Subpackage dependency`` note says
  that a subpackage depending on its base package must use the strict
  ``%{name}%{?_isa} = %{version}-%{release}`` form.

Deliberately out of scope, each because the clause is not statically
decidable from the spec alone. Clause 1 says to split by functional
category rather than by module or plugin, but which category a file belongs
to is a packager judgement and the spec does not record it. Clause 3 says
to split documentation once its volume or file count is large, and neither
threshold is defined. Clause 5 says to keep upgrades working across a
rename with ``Obsoletes`` and ``Provides``, which needs the history of the
package rather than its current text. The supplement's ``libs`` guidance
says a runtime library should stay in the main package and be announced
with ``Provides:       %{name}-libs = ...``, which is SHOULD level and
optional in practice. The supplement also asks for a ``#`` comment above
each runtime library inside ``%files``; a comment carries no machine
readable meaning and its absence says nothing about the package, so no
checkpoint counts comments. Plugin libraries are not covered by P4: a
``.so`` below a private directory of the library directory is loaded by
its own program rather than by the linker, and the supplement says that
such a file belongs to the main or the feature package. Language packs
must be separate subpackages, but RPM already generates them through the
``%find_lang`` mechanism, so their absence is not a defect of the spec.
No network access and no ``rpm`` invocation is performed, so the rule
works on a bare checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# A "%package" header. The argument text is captured verbatim because the
# name may be a suffix ("%package devel"), an explicit name introduced by
# "-n" ("%package -n foo"), or a mix of flags ("%package -f devel").
RE_PACKAGE = re.compile(r'^%package\b(?P<rest>.*)$')

# A "%files" header. Its arguments follow the same shape, plus "-f" for a
# file list that names no package of its own.
RE_FILES = re.compile(r'^%files\b(?P<rest>.*)$')

# The main package name. Only the header field block is searched, so a
# "Name:" line quoted inside "%description" is never read.
RE_NAME_FIELD = re.compile(r'^Name\s*:\s*(?P<value>\S+)')

# A runtime "Requires" line. A qualified form such as "Requires(pre):" is
# not matched, because the strict dependency clause is about the runtime
# dependency and a scriptlet qualifier is a different declaration.
RE_REQUIRES = re.compile(r'^Requires\s*:\s*(?P<value>.*)$')

# A section header. Section arguments ("%files -f %{name}.lang") are
# ignored. The closed whitelist below keeps macro invocations such as
# "%global" and "%if" from ending a block.
RE_SECTION = re.compile(r'^%([a-z]\w*)\b')

# A macro reference inside a name. A name that carries one cannot be
# resolved without expanding it, so the name checkpoints skip it.
RE_MACRO = re.compile(r'%\{[^}]*\}')

# A version pin: an equality comparator followed by a release reference.
# The reference is not tied to "%{version}", because a spec that keeps a
# second version macro ("%{nodejs_version}-%{release}") is still pinned.
RE_PINNED = re.compile(r'=[^,]*%\{\??release\}')

# A comparator in front of the required name, stripped before comparing.
RE_COMPARATOR = re.compile(r'[<>=].*$')

# Development content. A header is anything below the include directory; a
# file that merely ends in ".h" is not counted, because a program may ship
# a header for its own run time ("%{_datadir}/foo/relay.h") and the
# guideline is about the headers a compiler includes. The include directory
# itself is excluded, because a directory-only entry creates the directory
# rather than packaging a header, while a subdirectory such as
# "%{_includedir}/foo/" is kept because it holds the headers. A pkgconfig
# file is a ".pc" file; a directory such as
# "%{_datadir}/pkgconfig/personality.d" is configuration of the tool rather
# than a development file. A CMake package file lives below the "cmake"
# directory of a library or data directory, which is where a consumer's
# "find_package" looks; a ".cmake" file elsewhere
# ("%{_rpmmacrodir}/macros.cmake") is not.
RE_INCLUDE_DIRECTORY = re.compile(r'^(?:%\{_includedir\}|/usr/include)(?:/|$)')
RE_PKGCONFIG = re.compile(r'\.pc$')
RE_CMAKE = re.compile(
    r'(?:%\{_lib(?:dir|64dir|32dir)\}|%\{_datadir\}'
    r'|/usr/lib(?:64|32)?|/usr/share)/cmake/',
)

# The library directories that the guidelines name, in the forms a spec
# actually writes: the macro spelling and the expanded path.
LIBRARY_DIRECTORY = r'(?:%\{_lib(?:dir|64dir|32dir)\}|/usr/lib(?:64|32)?)'

# The unversioned link: exactly one component below a library directory.
# A file one level deeper sits in a private plugin directory, which the
# supplement places with the main or the feature package.
RE_UNVERSIONED_LINK = re.compile(
    r'^' + LIBRARY_DIRECTORY + r'/(?P<base>[^/\s]+\.so)$',
)

# A versioned shared library or a SONAME link.
RE_VERSIONED_LIBRARY = re.compile(r'\.so\.\d')

# The closed set of real RPM sections, mirroring check-spec-basic-fields.
KNOWN_SECTIONS: frozenset[str] = frozenset({
    '%description',
    '%package',
    '%prep',
    '%conf',
    '%build',
    '%install',
    '%check',
    '%clean',
    '%files',
    '%changelog',
    '%pre',
    '%post',
    '%preun',
    '%postun',
    '%pretrans',
    '%posttrans',
    '%triggerprein',
    '%triggerin',
    '%triggerun',
    '%triggerpostun',
    '%verifyscript',
    '%generate_buildrequires',
})

# The section that opens a new subpackage block.
_BLOCK_SECTION = '%package'

# The subpackage that holds development content.
DEV_SUFFIX = 'devel'

# The flag whose argument is an explicit package name, and the flag whose
# argument is a file list rather than a name.
_NAME_FLAG = '-n'
_FILELIST_FLAG = '-f'


class _PackageBlock(NamedTuple):
    """One ``%package`` header and the block it opens.

    ``offset`` is a 0-based offset into the file and ``line`` is 1-based.
    ``mode`` is ``"n"`` when the name is written in full after ``-n``,
    ``"suffix"`` when the argument is a suffix of the main package name,
    and ``"main"`` when the header names no package of its own.
    ``value`` is the raw text of that name or suffix.
    """

    offset: int
    line: int
    mode: str
    value: str | None
    span: tuple[int, int]


class _FilesBlock(NamedTuple):
    """One ``%files`` header and the entries it lists.

    ``entries`` holds ``(line, token)`` pairs, where ``line`` is 1-based and
    ``token`` is one path or glob of the block. Directives and comments are
    already removed.
    """

    line: int
    mode: str
    value: str | None
    entries: list[tuple[int, str]]


def _dedup(errors: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for err in errors:
        if err not in seen:
            seen.add(err)
            out.append(err)
    return out


def _read_lines(filename: str) -> tuple[list[str] | None, str | None]:
    """Return the spec's lines, or (None, error) when it cannot be read."""
    try:
        with open(filename, encoding='utf-8') as f:
            return f.read().splitlines(), None
    except UnicodeDecodeError:
        return None, f'{filename}: file is not valid UTF-8'
    except OSError as exc:
        return None, f'{filename}: {exc}'


def _is_section(line: str) -> str | None:
    """Return the known section name on this line, or None."""
    match = RE_SECTION.match(line)
    if match is None:
        return None
    section = '%' + match.group(1)
    if section in KNOWN_SECTIONS:
        return section
    return None


def _marks(lines: list[str]) -> list[tuple[int, str]]:
    """Return the offset and name of every known section header."""
    out: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        section = _is_section(line)
        if section is not None:
            out.append((index, section))
    return out


def _head(rest: str) -> tuple[str, str | None]:
    """Split a ``%package`` or ``%files`` argument list.

    Returns ``("n", name)`` for an explicit name introduced by ``-n``,
    ``("suffix", suffix)`` for a bare suffix, and ``("main", None)`` when
    the line carries no name of its own, which is how the main package
    writes its own headers. A flag that takes a value swallows the token
    behind it, so ``%files -f %{name}.lang`` is not read as a package
    called ``%{name}.lang``.
    """
    tokens = rest.split()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == _NAME_FLAG and index + 1 < len(tokens):
            return 'n', tokens[index + 1]
        if token == _FILELIST_FLAG:
            index += 2
            continue
        if token.startswith('-'):
            index += 1
            continue
        return 'suffix', token
    return 'main', None


def _resolve(
    main: str | None,
    mode: str,
    value: str | None,
) -> str | None:
    """Return the package name this header declares, as written.

    A bare header belongs to the main package. A suffix is joined to the
    main name, so ``%package devel`` becomes ``foo-devel`` and can be
    compared against a ``-n`` spelling. The result may still carry macros.
    """
    if mode == 'main':
        return main
    if value is None:
        return None
    if mode == 'n':
        return value
    if main is None:
        return value
    return f'{main}-{value}'


def _main_name(
    lines: list[str],
    marks: list[tuple[int, str]],
) -> str | None:
    """Return the main package name, or None when the spec declares none."""
    limit = marks[0][0] if marks else len(lines)
    for index in range(limit):
        match = RE_NAME_FIELD.match(lines[index])
        if match is not None:
            return match.group('value')
    return None


def _package_blocks(
    lines: list[str],
    marks: list[tuple[int, str]],
) -> list[_PackageBlock]:
    """Return every ``%package`` block, as 0-based half-open spans."""
    blocks: list[_PackageBlock] = []
    for position, (index, section) in enumerate(marks):
        if section != _BLOCK_SECTION:
            continue
        match = RE_PACKAGE.match(lines[index])
        if match is None:
            continue
        mode, value = _head(match.group('rest'))
        if position + 1 < len(marks):
            end = marks[position + 1][0]
        else:
            end = len(lines)
        blocks.append(
            _PackageBlock(
                offset=index,
                line=index + 1,
                mode=mode,
                value=value,
                span=(index, end),
            ),
        )
    return blocks


def _entries_of(
    lines: list[str],
    start: int,
    end: int,
) -> list[tuple[int, str]]:
    """Return the ``(line, token)`` pairs of one section body.

    A comment is dropped, because the supplement asks packagers to annotate
    a runtime library with one and a commented path must never be read as
    a packaged file. A ``%exclude`` line is dropped as well, because it
    removes a path from the package rather than adding it. A directive such
    as ``%doc``, ``%license`` or ``%attr(...)`` is not a path and is
    dropped, while a macro that expands to a path (``%{_libdir}``) is kept.
    """
    out: list[tuple[int, str]] = []
    for index in range(start, end):
        text = lines[index].strip()
        if not text or text.startswith('#'):
            continue
        if text.startswith('%exclude'):
            continue
        for token in text.split():
            if token.startswith('%') and not token.startswith(('%{', '%!')):
                continue
            out.append((index + 1, token))
    return out


def _files_blocks(
    lines: list[str],
    marks: list[tuple[int, str]],
) -> list[_FilesBlock]:
    """Return every ``%files`` block with the package it belongs to.

    A ``%files`` header that names no package of its own lists the files of
    the main package, which is why the main package writes a bare
    ``%files``. It is not attached to the ``%package`` that happens to
    precede it, because a spec commonly writes ``%files devel`` and then
    the bare ``%files`` of the main package in that order.
    """
    blocks: list[_FilesBlock] = []
    for position, (index, section) in enumerate(marks):
        if section != '%files':
            continue
        match = RE_FILES.match(lines[index])
        if match is None:
            continue
        mode, value = _head(match.group('rest'))
        if position + 1 < len(marks):
            end = marks[position + 1][0]
        else:
            end = len(lines)
        blocks.append(
            _FilesBlock(
                line=index + 1,
                mode=mode,
                value=value,
                entries=_entries_of(lines, index + 1, end),
            ),
        )
    return blocks


def _is_dev(mode: str, value: str | None) -> bool:
    """True when this name is the development subpackage.

    A Rust feature subpackage is spelled ``%package +serde``, so a leading
    ``+`` in a suffix is not a development package. A ``+`` anywhere else
    is ordinary text of the name, as in ``uuid-c++-devel``, which is the
    development subpackage of ``uuid-c++``.
    """
    if mode == 'main' or value is None:
        return False
    if mode == 'suffix' and value.startswith('+'):
        return False
    return value == DEV_SUFFIX or value.endswith('-' + DEV_SUFFIX)


def _is_opaque(name: str | None, main: str | None) -> bool:
    """True when the name hides its role behind a macro.

    ``%files -n %{devname}`` names a development subpackage, but the
    spelling hides it behind a ``%global``. Without expanding the macro the
    block cannot be classified, and guessing would report a header that is
    already in the right package. A name that simply repeats the main
    package is not opaque, because the main package is known already.
    """
    if name is None or name == main:
        return False
    return RE_MACRO.search(name) is not None


def _dev_kind(token: str) -> str | None:
    """Return the kind of development content this token names, or None."""
    if token in ('%{_includedir}', '/usr/include'):
        return None
    if RE_INCLUDE_DIRECTORY.match(token) is not None:
        return 'header file'
    if RE_PKGCONFIG.search(token) is not None:
        return 'pkgconfig file'
    if RE_CMAKE.search(token) is not None:
        return 'CMake package file'
    return None


def _check_name(
    main: str | None,
    blocks: list[_PackageBlock],
) -> list[str]:
    """P1: a subpackage name uses ``-`` as its separator.

    A name that carries a macro cannot be resolved without expanding it, so
    it is skipped. A ``+`` marks a Rust feature subpackage, which the
    supplement carves out. Only a ``_`` or a ``.`` that the subpackage adds
    on top of the main name is reported, so a base package whose own name
    contains ``_`` or ``.`` does not turn every one of its subpackages into
    a finding: ``socket_wrapper`` keeps its underscore in
    ``libsocket_wrapper_noop``, because the character comes from the
    upstream project name rather than from the subpackage separator.
    """
    errors: list[str] = []
    for block in blocks:
        name = _resolve(main, block.mode, block.value)
        if name is None:
            continue
        if '+' in name or RE_MACRO.search(name) is not None:
            continue
        tail = name
        if main is not None and name.startswith(main):
            tail = name[len(main):]
        bad = [
            char
            for char in '_.'
            if char in tail and (main is None or char not in main)
        ]
        if not bad:
            continue
        quoted = '" "'.join(bad)
        errors.append(
            f'subpackage {name} (line {block.line}) uses "{quoted}" in its '
            f'name; separate the parts with "-" and write '
            f'{main or "%{name}"}-<feature>',
        )
    return errors


def _check_dev_files(
    main: str | None,
    blocks: list[_FilesBlock],
    dev_name: str | None,
    undecidable: bool = False,
) -> list[str]:
    """P2: development content is packaged in the ``-devel`` subpackage.

    The two arms of the clause are reported with different messages. When
    the spec declares a ``-devel`` subpackage, a development file anywhere
    else is in the wrong package. When it declares none, the clause is
    violated in the other direction: the development files exist and were
    never split out. The second arm is withheld while ``undecidable`` is
    set, because a package name written through a macro may hide the
    ``-devel`` subpackage itself and the spec has not been shown to lack
    one.
    """
    base = main or '%{name}'
    errors: list[str] = []
    for block in blocks:
        if _is_dev(block.mode, block.value):
            continue
        owner = _resolve(main, block.mode, block.value) or base
        if _is_opaque(owner, main):
            continue
        for line, token in block.entries:
            kind = _dev_kind(token)
            if kind is None:
                continue
            if dev_name is None:
                if undecidable:
                    continue
                errors.append(
                    f'{kind} {token} (line {line}) is packaged in {owner}, '
                    f'but the spec declares no {base}-{DEV_SUFFIX} '
                    'subpackage to hold it',
                )
            else:
                errors.append(
                    f'{kind} {token} (line {line}) is packaged in {owner}; '
                    f'move it to the {dev_name} subpackage',
                )
    return errors


def _check_versioned_library(
    main: str | None,
    blocks: list[_FilesBlock],
) -> list[str]:
    """P3: a ``-devel`` subpackage carries no versioned shared library.

    The supplement splits ``%{_libdir}`` into a real file, a SONAME link
    and an unversioned link, and puts the first two in the runtime package.
    Both forms carry a numeric suffix after ``.so``, so one pattern finds
    them.
    """
    errors: list[str] = []
    for block in blocks:
        if not _is_dev(block.mode, block.value):
            continue
        owner = _resolve(main, block.mode, block.value) or f'{DEV_SUFFIX}'
        for line, token in block.entries:
            if RE_VERSIONED_LIBRARY.search(token) is None:
                continue
            errors.append(
                f'versioned shared library {token} (line {line}) is '
                f'packaged in {owner}; keep the real file and the SONAME '
                'link in the runtime package',
            )
    return errors


def _check_unversioned_link(
    main: str | None,
    blocks: list[_FilesBlock],
    dev_name: str | None,
) -> list[str]:
    """P4: the unversioned ``lib*.so`` link lives in ``-devel``.

    Only a link directly below a library directory is reported: a file one
    level deeper sits in a private plugin directory, which the supplement
    places with the main or the feature package. A name that carries a
    macro is skipped, because ``%{_libdir}/libfoo-%{version}.so`` is a real
    library whose file name embeds the version rather than a linker link. A
    glob is skipped too, because ``%{_libdir}/lib*.so`` may expand to real
    libraries whose names never carried a version at all. The checkpoint
    needs a ``-devel`` subpackage to point at; without one the finding
    belongs to P2.
    """
    if dev_name is None:
        return []
    base = main or '%{name}'
    errors: list[str] = []
    for block in blocks:
        if _is_dev(block.mode, block.value):
            continue
        owner = _resolve(main, block.mode, block.value) or base
        for line, token in block.entries:
            match = RE_UNVERSIONED_LINK.match(token)
            if match is None:
                continue
            leaf = match.group('base')
            if '*' in leaf or RE_MACRO.search(leaf) is not None:
                continue
            errors.append(
                f'unversioned library link {token} (line {line}) is '
                f'packaged in {owner}; move the *.so link to the '
                f'{dev_name} subpackage',
            )
    return errors


def _check_dependency(
    lines: list[str],
    main: str | None,
    blocks: list[_PackageBlock],
) -> list[str]:
    """P5: a subpackage that requires its base package pins the version.

    A subpackage that names its base package without the exact version
    breaks the split when the two are upgraded out of step, which is what
    the supplement's strict form prevents. Only a plain runtime
    ``Requires`` is read; a qualifier such as ``Requires(pre)`` declares a
    scriptlet dependency and is not the clause under check. The comparison
    is made against the raw name of the base package, so a spec that spells
    it through a macro is checked too.
    """
    if main is None:
        return []
    errors: list[str] = []
    base_names = {main, '%{name}'}
    for block in blocks:
        owner = _resolve(main, block.mode, block.value)
        if owner is None:
            continue
        start, end = block.span
        for index in range(start, end):
            match = RE_REQUIRES.match(lines[index])
            if match is None:
                continue
            value = match.group('value').strip()
            if not value:
                continue
            head = RE_COMPARATOR.sub('', value.split()[0])
            if head not in base_names:
                continue
            if RE_PINNED.search(value) is not None:
                continue
            errors.append(
                f'Requires {value} (line {index + 1}) in {owner} does not '
                f'pin the base package; write "Requires:       '
                f'{main}%{{?_isa}} = %{{version}}-%{{release}}"',
            )
    return errors


def _check_spec_subpackaging_ext(
    filename: str,
    *,
    check_name: bool = True,
    check_dev_files: bool = True,
    check_versioned_library: bool = True,
    check_unversioned_link: bool = True,
    check_dependency: bool = True,
) -> list[str]:
    """Run the checkpoints of this rule against one spec file.

    Every checkpoint is on by default. The keyword arguments exist for the
    command line flags, which let a team relax one clause without dropping
    the rest.
    """
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None

    marks = _marks(lines)
    packages = _package_blocks(lines, marks)
    if not packages:
        return []

    main = _main_name(lines, marks)
    files = _files_blocks(lines, marks)

    dev_name: str | None = None
    undecidable = False
    for block in packages:
        if _is_dev(block.mode, block.value):
            dev_name = _resolve(main, block.mode, block.value)
            break
        if _is_opaque(_resolve(main, block.mode, block.value), main):
            undecidable = True

    errors: list[str] = []
    if check_name:
        errors.extend(_check_name(main, packages))
    if check_dev_files:
        errors.extend(_check_dev_files(main, files, dev_name, undecidable))
    if check_versioned_library:
        errors.extend(_check_versioned_library(main, files))
    if check_unversioned_link:
        errors.extend(_check_unversioned_link(main, files, dev_name))
    if check_dependency:
        errors.extend(_check_dependency(lines, main, packages))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_subpackaging(filename: str) -> list[str]:
    """Run every checkpoint of this rule against one spec file."""
    return _check_spec_subpackaging_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            'Check the openRuyi subpackaging clauses of a spec file: the '
            'name separator of a subpackage, the package that holds the '
            'development content, the package that holds each class of '
            'shared library, and the version pin of a subpackage that '
            'requires its base package.'
        ),
    )
    parser.add_argument('filenames', nargs='*', help='spec files to check')
    parser.add_argument(
        '--no-check-name',
        action='store_true',
        help='skip the separator check on subpackage names',
    )
    parser.add_argument(
        '--no-check-dev-files',
        action='store_true',
        help='skip the placement check on development files',
    )
    parser.add_argument(
        '--no-check-versioned-library',
        action='store_true',
        help='skip the check that keeps versioned libraries out of -devel',
    )
    parser.add_argument(
        '--no-check-unversioned-link',
        action='store_true',
        help='skip the check that puts the unversioned *.so link in -devel',
    )
    parser.add_argument(
        '--no-check-dependency',
        action='store_true',
        help='skip the version pin check on a subpackage Requires',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_subpackaging_ext(
            filename,
            check_name=not args.no_check_name,
            check_dev_files=not args.no_check_dev_files,
            check_versioned_library=not args.no_check_versioned_library,
            check_unversioned_link=not args.no_check_unversioned_link,
            check_dependency=not args.no_check_dependency,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret


if __name__ == '__main__':
    raise SystemExit(main())
