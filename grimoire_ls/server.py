import importlib.util
import os
from pathlib import Path
from typing import Awaitable, Callable, List, Optional

from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    CompletionItem,
    CompletionList,
    CompletionListItemDefaultsType,
    CompletionListItemDefaultsTypeEditRangeType1,
    CompletionOptions,
    CompletionParams,
    Range,
)
from pygls.server import LanguageServer

from . import code_actions


class GrimoireServer(LanguageServer):
    def __init__(self, name: str = "grimoire-ls", version: str = "v0.1", **kwargs):
        super().__init__(name, version, **kwargs)

    def code_action_replace(
        self,
        id_: str,
        title: str,
        command_kwargs: Optional[dict] = None,
        code_action_kwargs: Optional[dict] = None,
    ):
        """Creates a code action from a function that takes in a string and returns a string that should replace it."""
        code_action_kwargs = command_kwargs or {}
        code_action_kwargs.setdefault("title", title)

        def decorator(f):
            return code_actions.replace_content_wrapper(
                self,
                f,
                id_,
                command_kwargs,
                code_action_kwargs,
            )

        return decorator

    def completion(
        self,
        options: CompletionOptions,
    ):
        """Creates a completion handler from a function that takes in a `CompletionParams` and returns a list of `CompletionItem`."""

        def decorator(f: Callable[[CompletionParams], Awaitable[List[CompletionItem]]]):
            async def wrapped(params: CompletionParams):
                return CompletionList(
                    is_incomplete=False,
                    items=await f(params),
                    item_defaults=CompletionListItemDefaultsType(
                        edit_range=CompletionListItemDefaultsTypeEditRangeType1(
                            Range(params.position, params.position),
                            Range(params.position, params.position),
                        )
                    ),
                )

            return self.feature(TEXT_DOCUMENT_COMPLETION, options)(wrapped)

        return decorator

    @classmethod
    def from_config(cls) -> "GrimoireServer":
        # First try to load the config from the environment variable
        path = os.environ.get("GRIMOIRE_LS_HOME")
        if path is None:
            # Default to the XDG config directory
            path = (
                Path(
                    os.environ.get(
                        "XDG_CONFIG_HOME", os.path.join(os.environ["HOME"], ".config")
                    )
                )
                / "grimoire-ls"
            )

        path = Path(path).expanduser().resolve() / "init.py"
        spec = importlib.util.spec_from_file_location("config", path)
        if spec is None:
            raise Exception(f"Could not load config from {path}")
        if spec.loader is None:
            raise Exception(f"Spec loader is None for {spec}")
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        server = config.server
        if not isinstance(server, cls):
            raise Exception(f"Expected `server` to be type {cls}, got {type(server)}")
        return server