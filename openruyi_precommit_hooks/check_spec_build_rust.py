"""Enforce the requirements of the rust and rustcrates build systems.

The Rust supplement of the packaging guidelines describes two declarative
build systems. ``rust`` builds Rust applications, command line tools and
anything that needs a Cargo build and test run; ``rustcrates`` builds Rust
crate provider packages, that is packages that install crate sources and
generate the crate feature subpackages.

Section "Dependencies" states, verbatim:

> When using the ``rust`` or ``rustcrates`` build system, you usually need
> to add:
>
>     BuildRequires:  rust
>     BuildRequires:  rust-rpm-macros

Section "Install" states, verbatim, for ``rustcrates``:

> The install stage of the ``rustcrates`` build system installs the crate
> sources. Its core behaviour is equivalent to:
>
>     %rust_install_crate
>
> That macro installs the current crate sources into the system location
> and generates ``.cargo-checksum.json``.
>
> Therefore, Rust crate provider packages usually do not need to write
> ``%install`` by hand. If you really need to add operations before or after
> the default install logic, you can use ``%install -p`` or ``%install -a``.

Section "Prep" states, verbatim, for ``rust``:

> The prep stage of the ``rust`` build system unpacks the default sources
> and configures Cargo to use the system registry. Its core behaviour is
> equivalent to:
>
>     %autosetup -C -p1
>     ...
>     %rust_setup_registry
>
> If you fully override ``%prep``, you need to keep the configuration that
> makes Cargo use the system registry, otherwise the later Cargo build may
> not be able to use the crate dependencies the system provides.

Four checkpoints are implemented, and each one is anchored in one of those
clauses:

* C1 reproduces the "usually do not need to write %install by hand"
  clause for ``rustcrates``. The page names ``%install -p`` and
  ``%install -a`` as the compliant way to add work around the default
  install logic, so a suffixed section is accepted and only a plain
  ``%install`` is reported.
* C2 reproduces the "keep the configuration that makes Cargo use the
  system registry" clause for ``rust``. Only a plain ``%prep`` section is
  judged, because a suffixed section runs around the default prep and
  therefore keeps the registry configuration in place.
* C3 reproduces the macro package the page names for both build systems in
  the same sentence.
* C4 reproduces the toolchain dependency the page names first in the same
  sentence, for ``rust`` only. The page lists both dependencies under one
  heading, but a ``rustcrates`` package installs crate sources rather than
  building them, so the corpus declares the toolchain in none of the 2354
  ``rustcrates`` specs while every ``rust`` spec declares it. Reporting the
  toolchain for ``rustcrates`` would therefore flag the entire corpus, so
  C4 is scoped to the build system that compiles Cargo output.

C3 and C4 are worded with "usually need to add", so they are enforced as a
normal form rather than as an absolute rule: a spec that satisfies the
clause in another spelling is accepted, and every dependency question
outside those two names belongs to ``check-spec-buildrequires``.

Deliberately out of scope: whether the value of ``BuildSystem`` is one of
the legal names (owned by ``check-spec-buildsystem``), the compatibility
macros ``%global crate_name``/``full_version``/``pkgname`` (the page calls
them a typical example that is generally not edited by hand, which is a
description of the tool output rather than a rule), the ``%check`` stage of
both systems (the page states that ``rustcrates`` has no default test
stage and that overriding it for extra validation is allowed, and it states
that a ``rust`` test stage may be overridden or disabled by package policy),
the expected default install action of ``rust`` (the page states that a
spec writes ``%install`` according to the package, so a spec without one is
not a violation this rule can prove), the absence of a plain ``%build``
section for ``rustcrates`` (the page forbids overriding the stage, and the
corpus never does it, but the same paragraph also explains that the stage
generates the specparts, which a spec-only linter cannot distinguish from
an empty plain section), and the section extension mechanism itself
(owned by the rule that covers each build system).

No network access and no ``rpm`` invocation is performed, so the rule works
on a bare checkout.
"""
from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from typing import NamedTuple


# Any top-level "Field: value" line. A trailing parenthesised argument such
# as the stage of "BuildOption(build):" belongs to the field name rather
# than to the value, so the group is matched and dropped.
RE_FIELD = re.compile(r'^([A-Za-z]\w*)(?:\(([^)]*)\))?\s*:\s*(.*)$')

# A section header, together with everything that follows the section name
# on the same line. For "%install" the remainder is empty; for "%install -a"
# it is "-a".
RE_SECTION = re.compile(r'^%([a-z]\w*)\b(.*)$')

# The field that switches the requirement on, and the field that satisfies
# it. Both are matched loosely so a misspelling reported by the dedicated
# rules still contributes its value here.
RE_BUILD_SYSTEM = re.compile(r'^build-?system$', re.IGNORECASE)
RE_BUILD_REQUIRES = re.compile(r'^build-?requires?$', re.IGNORECASE)

# The dependency operators. A token that is exactly an operator consumes the
# token after it, which is the version of the dependency to its left.
RE_OPERATOR = re.compile(r'^(?:<=|>=|=|<|>)$')

# The two keywords that join two dependency names into one clause.
_JOINERS = frozenset({'with', 'without'})

# The closed set of real RPM sections, mirroring check-spec-basic-fields.
# Anything else that starts with "%" is a macro invocation (%license, %doc,
# %systemd_post, %autochangelog, ...) and must never be mistaken for a
# section.
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

# The two build systems this rule covers. The names are spelled exactly as
# the page spells them.
RUST = 'rust'
RUSTCRATES = 'rustcrates'

# The dependency names the page asks for, matched as whole names so
# "rust-toolset" would not pass for "rust".
TOOLCHAIN_PACKAGE = 'rust'
MACROS_PACKAGE = 'rust-rpm-macros'

# The dependency spellings named in the messages.
TOOLCHAIN_SPELLING = 'rust'
MACROS_SPELLING = 'rust-rpm-macros'

# The section that C1 inspects and the section that C2 inspects.
INSTALL_SECTION = '%install'
PREP_SECTION = '%prep'


class _Block(NamedTuple):
    """One field block: the fields it holds, in file order.

    ``fields`` is a list of ``(spelling, stage, value, 1-based line)``
    tuples, where ``stage`` is the parenthesised argument of a field name or
    the empty string when the name carries none.
    """

    fields: list[tuple[str, str, str, int]]


class _Section(NamedTuple):
    """One section: its name, its suffix, its header line and its body.

    ``suffix`` is everything the header line carries after the section name,
    so a plain ``%install`` has an empty suffix while ``%install -a`` has
    ``-a``.
    """

    name: str
    suffix: str
    line: int
    body: list[tuple[int, str]]


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


def _section_of(line: str) -> tuple[str, str] | None:
    """Return ``(section name, suffix)`` for a known section header."""
    match = RE_SECTION.match(line)
    if match is None:
        return None
    name = '%' + match.group(1)
    if name not in KNOWN_SECTIONS:
        return None
    return name, match.group(2).strip()


def _macro_depth_after(line: str, depth: int) -> int:
    """Return the macro nesting depth after consuming one line."""
    depth += line.count('{') - line.count('}')
    return depth if depth > 0 else 0


def _blocks_of(lines: list[str]) -> list[_Block]:
    """Split the file into field blocks.

    The first block is the main preamble, kept even when it holds no field.
    Every ``%package`` opens a fresh block, so a subpackage that declares a
    build system of its own is judged against its own dependencies. A block
    ends at the first known section, so a macro invocation such as
    ``%global debug_package %{nil}`` neither ends a block nor hides the
    fields that follow it.
    """
    raw: list[list[tuple[str, str, str, int]]] = []
    fields: list[tuple[str, str, str, int]] = []
    macro_depth = 0

    for index, line in enumerate(lines, 1):
        if macro_depth > 0:
            macro_depth = _macro_depth_after(line, macro_depth)
            continue
        if _section_of(line) is not None:
            raw.append(fields)
            fields = []
            continue
        if line.startswith('#'):
            continue
        match = RE_FIELD.match(line)
        if match is None:
            continue
        name, stage, value = (
            match.group(1), match.group(2) or '', match.group(3),
        )
        fields.append((name, stage.strip(), value, index))
        macro_depth = _macro_depth_after(line, 0)

    raw.append(fields)
    blocks = [_Block(raw[0])]
    blocks.extend(_Block(item) for item in raw[1:] if item)
    return blocks


def _declared_names(value: str) -> set[str]:
    """Return the lowercase name of every dependency on one field line.

    A dependency is a name optionally followed by a version operator and a
    version, or one rich dependency in parentheses, or two names joined by
    a comma, ``with`` or ``without``. Only the names are returned, so a
    version number never looks like a dependency and ``rust-toolset`` stays
    distinct from ``rust``.
    """
    names: set[str] = set()
    skip = False
    depth = 0
    for token in value.split():
        opens = token.count('(')
        closes = token.count(')')
        if depth > 0 or opens or closes:
            depth = max(depth + opens - closes, 0)
            skip = False
            continue
        if skip:
            skip = False
            continue
        if RE_OPERATOR.match(token) is not None:
            skip = True
            continue
        if token.lower() in _JOINERS:
            skip = True
            continue
        names.add(token.rstrip(',').lower())
    return names


def _systems_of(blocks: Sequence[_Block]) -> dict[str, int]:
    """Return the first line of every ``BuildSystem`` value, lowercase.

    The value is split on whitespace so a field that names more than one
    system contributes each of them.
    """
    found: dict[str, int] = {}
    for block in blocks:
        for name, _stage, value, line in block.fields:
            if RE_BUILD_SYSTEM.match(name) is None:
                continue
            for token in value.split():
                found.setdefault(token.strip().lower(), line)
    return found


def _declared_everywhere(blocks: Sequence[_Block]) -> set[str]:
    """Return every dependency name declared in any build-requires field.

    ``BuildRequires`` is a source-package level field, so RPM merges the
    declarations of every subpackage block into one build dependency set.
    The requirement is therefore satisfied when the name appears anywhere
    in the file, which keeps a subpackage that carries the dependency from
    producing a false finding.
    """
    declared: set[str] = set()
    for block in blocks:
        for name, _stage, value, _line in block.fields:
            if RE_BUILD_REQUIRES.match(name) is not None:
                declared |= _declared_names(value)
    return declared


def _sections_of(lines: Sequence[str]) -> list[_Section]:
    """Return every known section, with its suffix and its body lines.

    A body line keeps its 1-based line number so a finding can point at the
    exact command. Comment lines are kept on purpose: C1 and C2 report a
    section that does something, and a section holding only a comment holds
    nothing that overrides the default stage.
    """
    found: list[_Section] = []
    current: _Section | None = None
    body: list[tuple[int, str]] = []

    for index, line in enumerate(lines, 1):
        header = _section_of(line)
        if header is not None:
            if current is not None:
                found.append(current._replace(body=body))
            current = _Section(header[0], header[1], index, [])
            body = []
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped:
            body.append((index, stripped))

    if current is not None:
        found.append(current._replace(body=body))
    return found


def _effective_lines(section: _Section) -> list[tuple[int, str]]:
    """Return the section's lines except comments and blank lines."""
    return [
        (line, text) for line, text in section.body
        if not text.startswith('#')
    ]


def _plain_sections(
    sections: Sequence[_Section], name: str,
) -> list[_Section]:
    """Return the sections of that name that carry no -p/-a suffix."""
    return [
        section for section in sections
        if section.name == name and section.suffix == ''
    ]


def _check_crates_install(
    systems: dict[str, int], sections: Sequence[_Section],
) -> list[str]:
    """C1: a rustcrates spec does not write %install by hand."""
    if systems.get(RUSTCRATES) is None:
        return []
    found: list[str] = []
    for section in _plain_sections(sections, INSTALL_SECTION):
        if not _effective_lines(section):
            continue
        found.append(
            f'%install (line {section.line}) is written by hand in a '
            f'BuildSystem: {RUSTCRATES} spec; the default install stage '
            f'installs the crate sources and generates '
            f'.cargo-checksum.json, so use %install -p or %install -a to '
            f'add work around it',
        )
    return found


def _check_rust_prep(
    systems: dict[str, int], sections: Sequence[_Section],
) -> list[str]:
    """C2: a rust spec that overrides %prep keeps the registry setup."""
    if systems.get(RUST) is None:
        return []
    found: list[str] = []
    for section in _plain_sections(sections, PREP_SECTION):
        effective = _effective_lines(section)
        if not effective:
            continue
        joined = '\n'.join(text for _line, text in effective)
        if '%rust_setup_registry' in joined:
            continue
        found.append(
            f'%prep (line {section.line}) overrides the default prep of '
            f'BuildSystem: {RUST} without configuring the system crate '
            f'registry; keep %rust_setup_registry in the section, or use '
            f'%prep -p or %prep -a to extend the default prep',
        )
    return found


def _check_macros_package(
    systems: dict[str, int], declared: set[str],
) -> list[str]:
    """C3: a rust or rustcrates spec declares the rust macro package."""
    if MACROS_PACKAGE in declared:
        return []
    line = systems.get(RUST, systems.get(RUSTCRATES, 0))
    system = RUST if systems.get(RUST) is not None else RUSTCRATES
    return [
        f'BuildSystem: {system} (line {line}) requires '
        f'"{MACROS_SPELLING}" in BuildRequires; '
        f'missing "{MACROS_SPELLING}"',
    ]


def _check_toolchain(
    systems: dict[str, int], declared: set[str],
) -> list[str]:
    """C4: a rust spec declares the rust toolchain dependency."""
    if systems.get(RUST) is None:
        return []
    if TOOLCHAIN_PACKAGE in declared:
        return []
    return [
        f'BuildSystem: {RUST} (line {systems[RUST]}) requires '
        f'"{TOOLCHAIN_SPELLING}" in BuildRequires; '
        f'missing "{TOOLCHAIN_SPELLING}"',
    ]


def _check_spec_build_rust_ext(
    filename: str,
    *,
    check_crates_install: bool = True,
    check_rust_prep: bool = True,
    check_macros_package: bool = True,
    check_toolchain: bool = True,
) -> list[str]:
    lines, error = _read_lines(filename)
    if error is not None:
        return [error]
    assert lines is not None
    if not (
        check_crates_install or check_rust_prep or check_macros_package or
        check_toolchain
    ):
        return []

    blocks = _blocks_of(lines)
    systems = _systems_of(blocks)
    if RUST not in systems and RUSTCRATES not in systems:
        return []

    errors: list[str] = []
    if check_crates_install or check_rust_prep:
        sections = _sections_of(lines)
        if check_crates_install:
            errors.extend(_check_crates_install(systems, sections))
        if check_rust_prep:
            errors.extend(_check_rust_prep(systems, sections))
    if check_macros_package or check_toolchain:
        declared = _declared_everywhere(blocks)
        if check_macros_package:
            errors.extend(_check_macros_package(systems, declared))
        if check_toolchain:
            errors.extend(_check_toolchain(systems, declared))

    return _dedup([f'{filename}: {err}' for err in errors])


def _check_spec_build_rust(filename: str) -> list[str]:
    return _check_spec_build_rust_ext(filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Check the requirements of the rust build systems.',
    )
    parser.add_argument(
        'filenames', nargs='*', help='spec files to check',
    )
    parser.add_argument(
        '--no-check-crates-install',
        action='store_true',
        help='do not report a hand-written %install in a rustcrates spec',
    )
    parser.add_argument(
        '--no-check-rust-prep',
        action='store_true',
        help='do not report a %prep override without the registry setup',
    )
    parser.add_argument(
        '--no-check-macros-package',
        action='store_true',
        help='do not report the rust macro package',
    )
    parser.add_argument(
        '--no-check-toolchain',
        action='store_true',
        help='do not report the rust toolchain dependency',
    )
    args = parser.parse_args(argv)

    ret = 0
    for filename in args.filenames:
        errors = _check_spec_build_rust_ext(
            filename,
            check_crates_install=not args.no_check_crates_install,
            check_rust_prep=not args.no_check_rust_prep,
            check_macros_package=not args.no_check_macros_package,
            check_toolchain=not args.no_check_toolchain,
        )
        if errors:
            ret = 1
            for err in errors:
                print(err)
    return ret
