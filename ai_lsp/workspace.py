from urllib.parse import unquote_plus, urlparse
import git
import itertools as it
import math
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from pydantic import BaseModel, computed_field

from ai_lsp.server import AILanguageServer

from . import language as lang
from .logging import log


class Indentation(BaseModel):
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

        log(lines)
        log(sizes)

        size = math.gcd(*sizes)
        if size == 1:
            size = min(s for s in sizes if s > 0)
        return Indentation(size=size, char=char, base_level=min(sizes) / size)

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


class Content(BaseModel):
    content: str
    language: lang.Language = lang.by_extension[".txt"]
    source_uri: Optional[str] = None

    @computed_field
    @property
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


def uri_to_path(uri: str) -> Path:
    """Returns the path corresponding to `uri`."""
    return Path(unquote_plus(urlparse(uri).path))


def get_other_files_context(server: AILanguageServer, current_uri: str) -> List[str]:
    """Returns a context string with the content of other files in the workspace."""
    root = server.workspace.root_path
    other_files = []
    if root:
        for p in visible_files(git.Repo(root), Path(root)):
            language = lang.from_extension(p.suffix.lstrip("."))
            uri = p.as_uri()
            if uri == current_uri:
                continue
            content = server.workspace.get_text_document(uri).lines
            if not content:
                continue
            other_files.append(language.path_comment(p.relative_to(root)))
            other_files.extend(content)
    return other_files
