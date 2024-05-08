from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    name: str
    extensions: tuple[str, ...]
    comment_prefix: str
    comment_suffix: str = ""

    @lru_cache
    def uncomment(
        self,
        content: str,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> str:
        if prefix is None:
            prefix = self.comment_prefix
        if suffix is None:
            suffix = self.comment_suffix
        return content.removeprefix(prefix).removesuffix(suffix)

    @lru_cache
    def comment(
        self,
        content: str | Path,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
    ) -> str:
        if prefix is None:
            prefix = self.comment_prefix
        if suffix is None:
            suffix = self.comment_suffix
        return f"{prefix}{content}{suffix}"


all_languages: List[Language] = [
    Language(name="C", extensions=("c",), comment_prefix="// "),
    Language(name="C++", extensions=("cpp",), comment_prefix="// "),
    Language(
        name="CSS",
        extensions=("css",),
        comment_prefix="/* ",
        comment_suffix=" */",
    ),
    Language(name="Elixir", extensions=("ex",), comment_prefix="# "),
    Language(name="Erlang", extensions=("erl",), comment_prefix="% "),
    Language(name="Go", extensions=("go",), comment_prefix="// "),
    Language(
        name="HTML",
        extensions=("html",),
        comment_prefix="<!-- ",
        comment_suffix=" -->",
    ),
    Language(name="Java", extensions=("java",), comment_prefix="// "),
    Language(name="JavaScript", extensions=("js",), comment_prefix="// "),
    Language(name="JSON", extensions=("json",), comment_prefix=""),
    Language(name="Julia", extensions=("jl",), comment_prefix="# "),
    Language(name="Lua", extensions=("lua",), comment_prefix="-- "),
    Language(
        name="Markdown",
        extensions=("md",),
        comment_prefix="<!-- ",
        comment_suffix=" -->",
    ),
    Language(name="Plaintext", extensions=("txt",), comment_prefix=""),
    Language(name="Python", extensions=("py",), comment_prefix="# "),
    Language(name="Ruby", extensions=("rb",), comment_prefix="# "),
    Language(name="Rust", extensions=("rs",), comment_prefix="// "),
    Language(name="SQL", extensions=("sql",), comment_prefix="-- "),
    Language(name="Shell", extensions=("sh",), comment_prefix="# "),
    Language(name="TypeScript", extensions=("ts",), comment_prefix="// "),
]

by_extension: Dict[str, Language] = {
    ext: lang for lang in all_languages for ext in lang.extensions
}


def from_extension(ext: str) -> Language:
    return by_extension.get(ext.lstrip("."), by_extension["txt"])


def register(language: Language):
    all_languages.append(language)
    for ext in language.extensions:
        by_extension[ext] = language
