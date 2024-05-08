import importlib.util
import os
from functools import wraps
from pathlib import Path
from typing import Awaitable, Callable, List, Optional
from uuid import uuid4

from lsprotocol.types import (
    TEXT_DOCUMENT_CODE_ACTION,
    TEXT_DOCUMENT_COMPLETION,
    CodeAction,
    CodeActionParams,
    Command,
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
from result import Err, Ok, Result

from . import code_actions
from .code_actions import ActionOptions
from .progress import ProgressOptions


class GrimoireServer(LanguageServer):
    default_progress_options: ProgressOptions
    code_actions: list[ActionOptions]

    def __init__(
        self,
        name: str = "grimoire-ls",
        version: str = "v0.1",
        default_progress_options: ProgressOptions = ProgressOptions(),
        **kwargs,
    ):
        self.code_actions = []
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

    def code_action(
        self,
        options: ActionOptions,
        progress: Optional[ProgressOptions] = None,
    ):
        """Creates a code action from a user-defined function."""
        progress_ = progress or self.default_progress_options

        def decorator(f):
            progress = progress_  # Ugly hack to make pyright happy
            if progress.task_name is None:
                progress = progress.with_attrs(task_name=f.__name__)
            f = self.with_progress(progress)(f)

            # Register the function as an LSP command
            f = code_actions.wrap_transform(f, options)
            self.command(options.id)(f)
            self.code_actions.append(options)
            return f

        return decorator

    def _register_code_actions(self):
        @self.feature(TEXT_DOCUMENT_CODE_ACTION)
        async def _(params: CodeActionParams):
            uri = params.text_document.uri
            start = params.range.start
            end = params.range.end
            return [
                CodeAction(
                    command=Command(
                        command=action_opts.id,
                        arguments=[
                            uri,
                            start.line,
                            start.character,
                            end.line,
                            end.character,
                        ],
                        **action_opts.command_kwargs,
                    ),
                    **action_opts.code_action_kwargs,
                )
                for action_opts in self.code_actions
            ]

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
        server._register_code_actions()
        return server
