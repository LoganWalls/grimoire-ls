from dataclasses import dataclass
from functools import lru_cache
import itertools as it
import math
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional
from urllib.parse import unquote_plus, urlparse

import git
from lsprotocol.types import Range

from . import language as lang
from .logging import log


@dataclass
class Indentation:
    size: int
    char: str
    base_level: int = 0

    @classmethod
    def from_lines(cls, lines: List[str]) -> "Indentation":
        """Infers the indentation from lines."""
        if not lines:
            return Indentation(size=2, char=" ", base_level=0)

        char = " "
        sizes = []
        for line in lines:
            level = 0
            for c in it.takewhile(str.isspace, line):
                if c != char:
                    char = c
                level += 1
            sizes.append(level)

        size = math.gcd(*sizes)
        if size == 1:
            size = min(s for s in sizes if s > 0)
        return cls(size=size, char=char, base_level=min(sizes) // size)

    def format(self, lines: List[str]) -> List[str]:
        """Aligns the lines to the current indentation."""
        if not lines:
            return lines

        stripped_lines = [line.lstrip() for line in lines]
        line_levels = [
            len(line) - len(stripped_line)
            for line, stripped_line in zip(lines, stripped_lines)
        ]
        levels = sorted(set(line_levels))
        log(line_levels)
        log(levels)
        log(f"Base level: {self.base_level}")
        return [
            f"{self.char * self.size * (levels.index(line_level) + self.base_level)}{line}"
            for line, line_level in zip(stripped_lines, line_levels)
        ]


@dataclass
class Content:
    content: str
    language: lang.Language = lang.by_extension["txt"]
    source_uri: Optional[str] = None

    @lru_cache
    def indentation(self) -> Indentation:
        return Indentation.from_lines(self.content.splitlines())


def filter_paths(
    repo: git.Repo,
    paths: Iterable[Path],
    ignored_extensions: Optional[List[str]] = None,
) -> List[Path]:
    ignored_extensions = ignored_extensions or [
        ".lock",
        ".git",
        ".log",
        ".env",
        ".envrc",
    ]
    paths, paths2 = it.tee(paths)
    ignored = repo.ignored(*map(str, paths2))
    return [
        p
        for p in paths
        if str(p) not in ignored
        and not any(p.name.endswith(e) for e in ignored_extensions)
    ]


def visible_files(repo: git.Repo, path: Path) -> Iterator[Path]:
    """Yields files in a directory, respecting .gitignore and excluding hidden files."""
    subdirs = []
    for p in filter_paths(repo, path.iterdir()):
        if p.is_file():
            yield p
        else:
            subdirs.append(p)
    for d in subdirs:
        for p in visible_files(repo, d):
            yield p


def workspace_file_contents(server) -> Dict[Path, List[str]]:
    """Returns a dictionary mapping from each path in the workspace to its content.
    Excludes empty files & hidden files, and respects .gitignore."""
    root = server.workspace.root_path
    files = {}
    if root:
        for p in visible_files(git.Repo(root), Path(root)):
            uri = p.as_uri()
            content = server.workspace.get_text_document(uri).lines
            if content:
                files[p] = content
    return files


def uri_to_path(uri: str) -> Path:
    """Returns the path corresponding to `uri`."""
    return Path(unquote_plus(urlparse(uri).path))


def lines_from_range(
    lines: List[str],
    range_: Range,
) -> List[str]:
    lines = lines[range_.start.line : range_.end.line + 1]
    if lines:
        lines[0] = lines[0][range_.start.character :]
        lines[-1] = lines[-1][: range_.end.character + 1]
    return lines
