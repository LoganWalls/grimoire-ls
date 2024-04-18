from functools import wraps
import importlib.util
import os
from uuid import uuid4
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional
from result import Err, Ok, Result

from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    CompletionItem,
    CompletionList,
    CompletionListItemDefaultsType,
    CompletionListItemDefaultsTypeEditRangeType1,
    CompletionOptions,
    CompletionParams,
    Range,
    WorkDoneProgressBegin,
    WorkDoneProgressEnd,
)
from pygls.server import LanguageServer

from . import code_actions
from .progress import ProgressOptions


class GrimoireServer(LanguageServer):
    progress_tokens: Dict[str, str]
    default_progress_options: ProgressOptions

    def __init__(
        self,
        name: str = "grimoire-ls",
        version: str = "v0.1",
        default_progress_options: ProgressOptions = ProgressOptions(),
        **kwargs,
    ):
        self.default_progress_options = default_progress_options
        super().__init__(name, version, **kwargs)

    def with_progress(self, options: Optional[ProgressOptions] = None):
        """This decorator will report the status of the request (pending, completed, failed) to the client"""
        options_ = options or self.default_progress_options

        def decorator(
            f: Callable[..., Awaitable[Result[..., str]]],
        ) -> Callable[..., Awaitable[Result[..., str]]]:
            options = options_  # Ugly hack to make pyright happy
            if not options.enabled:
                return f

            @wraps(f)
            async def wrapped(*args, **kwargs):
                token = str(uuid4())
                await self.progress.create_async(token)
                self.progress.begin(
                    token,
                    WorkDoneProgressBegin(
                        title=options.task_name or "Grimoire Task",
                        cancellable=False,
                    ),
                )
                result = await f(*args, **kwargs)
                match result:
                    case Ok(_):
                        self.progress.end(
                            token, WorkDoneProgressEnd(message=options.success_message)
                        )
                    case Err(e):
                        self.progress.end(
                            token,
                            WorkDoneProgressEnd(message=options.failure_message or e),
                        )

                return result

            return wrapped

        return decorator

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
        progress: Optional[ProgressOptions] = None,
    ):
        """Creates a completion handler from a user-defined function"""
        progress_ = progress or self.default_progress_options

        def decorator(
            f: Callable[
                [CompletionParams], Awaitable[Result[List[CompletionItem], str]]
            ],
        ):
            progress = progress_  # Ugly hack to make pyright happy
            if progress.task_name is None:
                progress = progress.with_attrs(task_name=f.__name__)

            async def wrapped(params: CompletionParams):
                g = self.with_progress(progress)(f)
                items = []
                match await g(params):
                    case Ok(v):
                        items = v

                return CompletionList(
                    is_incomplete=False,
                    items=items,
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
