"""Shared command-line support for SxPB tidying and linting."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import sys
import tempfile
from typing import Iterable

from pathspec import GitIgnoreSpec

from .formatter import SxpbFormatError, format_sxpb


IgnoreFilter = tuple[Path, GitIgnoreSpec]


@dataclass(frozen=True)
class CliArgs:
    paths: list[str]
    ignore_file: Path | None


@dataclass(frozen=True)
class FormattedFile:
    path: Path
    original: str
    formatted: str

    @property
    def changed(self) -> bool:
        return self.formatted != self.original


def parse_cli_args(*, prog: str, description: str, verb: str) -> CliArgs:
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument(
        "paths",
        nargs="*",
        help=(
            f"Files or directories to {verb}; defaults to the current directory; "
            "use - for stdin"
        ),
    )
    parser.add_argument(
        "--ignore-file",
        type=Path,
        metavar="FILE",
        help="Apply gitignore-style patterns from FILE",
    )
    args = parser.parse_args()
    return CliArgs(paths=args.paths or ["."], ignore_file=args.ignore_file)


def _load_ignore_filter(path: Path) -> IgnoreFilter:
    if not path.is_file():
        raise ValueError(f"Ignore file does not exist: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    return path.parent.absolute(), GitIgnoreSpec.from_lines(lines)


def _is_ignored(path: Path, ignore_filter: IgnoreFilter, *, directory: bool) -> bool:
    root, spec = ignore_filter
    try:
        relative = path.absolute().relative_to(root)
    except ValueError:
        return False

    match_path = relative.as_posix()
    if match_path == ".":
        return False
    if directory:
        match_path += "/"
    return spec.match_file(match_path)


def _files_in_directory(
    directory: Path, ignore_filter: IgnoreFilter | None
) -> Iterable[Path]:
    if ignore_filter is not None and _is_ignored(
        directory, ignore_filter, directory=True
    ):
        return

    for root, directory_names, file_names in os.walk(directory):
        root_path = Path(root)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if ignore_filter is None
            or not _is_ignored(root_path / name, ignore_filter, directory=True)
        )
        for name in sorted(file_names):
            candidate = root_path / name
            if name.endswith(".sxpb") and (
                ignore_filter is None
                or not _is_ignored(candidate, ignore_filter, directory=False)
            ):
                yield candidate


def _collect_paths(
    arguments: list[str], ignore_filter: IgnoreFilter | None
) -> tuple[bool, list[Path]]:
    if "-" in arguments:
        if len(arguments) != 1:
            raise ValueError("`-` for stdin cannot be combined with file paths")
        return True, []

    paths: list[Path] = []
    seen: set[Path] = set()
    for argument in arguments:
        path = Path(argument)
        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")
        candidates = (
            _files_in_directory(path, ignore_filter) if path.is_dir() else [path]
        )
        for candidate in candidates:
            if ignore_filter is not None and _is_ignored(
                candidate, ignore_filter, directory=False
            ):
                continue
            key = candidate.absolute()
            if key not in seen:
                seen.add(key)
                paths.append(candidate)
    return False, paths


def _collect_inputs(args: CliArgs) -> tuple[bool, list[Path]]:
    ignore_filter = (
        _load_ignore_filter(args.ignore_file) if args.ignore_file is not None else None
    )
    return _collect_paths(args.paths, ignore_filter)


def _format_files(paths: list[Path]) -> list[FormattedFile]:
    formatted_files: list[FormattedFile] = []
    for path in paths:
        original = path.read_bytes().decode("utf-8")
        formatted_files.append(
            FormattedFile(path=path, original=original, formatted=format_sxpb(original))
        )
    return formatted_files


def _atomic_write(path: Path, text: str) -> None:
    mode = path.stat().st_mode
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(text.encode("utf-8"))
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def run_tidy(args: CliArgs) -> int:
    try:
        use_stdin, paths = _collect_inputs(args)
        if use_stdin:
            sys.stdout.write(format_sxpb(sys.stdin.read()))
            return 0

        formatted_files = _format_files(paths)
        for result in formatted_files:
            if result.changed:
                _atomic_write(result.path, result.formatted)
                print(f"Tidied: {result.path}", file=sys.stderr)
        return 0
    except (OSError, UnicodeError, ValueError, SxpbFormatError) as error:
        print(f"sxpb-tidy: {error}", file=sys.stderr)
        return 2


def run_lint(args: CliArgs) -> int:
    try:
        use_stdin, paths = _collect_inputs(args)
        if use_stdin:
            original = sys.stdin.read()
            if format_sxpb(original) != original:
                print("Needs tidying: -", file=sys.stderr)
                return 1
            return 0

        changed_paths = [
            result.path for result in _format_files(paths) if result.changed
        ]
        for path in changed_paths:
            print(f"Needs tidying: {path}", file=sys.stderr)
        return 1 if changed_paths else 0
    except (OSError, UnicodeError, ValueError, SxpbFormatError) as error:
        print(f"sxpb-lint: {error}", file=sys.stderr)
        return 2
