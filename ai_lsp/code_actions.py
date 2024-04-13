from collections.abc import Callable
from typing import Awaitable, Optional, Tuple

from lsprotocol.types import (
    TEXT_DOCUMENT_CODE_ACTION,
    CodeAction,
    CodeActionKind,
    CodeActionParams,
    Command,
    MessageType,
    Position,
    Range,
    TextEdit,
    WorkspaceEdit,
)

from . import workspace as wrk
from .logging import log


def replace_content_wrapper(
    server,
    f: Callable[[str], Awaitable[Optional[str]]],
    id_: str,
    command_kwargs: Optional[dict] = None,
    code_action_kwargs: Optional[dict] = None,
):
    """Creates a code action from a function that takes in a string and returns a string that should replace it."""

    # NOTE: `ls` variable name cannot be changed. It is hard-coded in pygls
    async def wrapped(ls, args: Tuple[str, int, int, int, int]):
        uri, start_line, start_col, end_line, end_col = args
        document = ls.workspace.get_document(uri)
        range_ = Range(Position(start_line, start_col), Position(end_line, end_col))
        lines = wrk.lines_from_range(document.lines, range_)
        text = "".join(lines).strip()
        result = await f(text)

        if result:
            original_indent = wrk.Indentation.from_lines(lines)
            # NOTE: rstrip is important to remove trailing whitespace which can mess up the indentation
            result = "\n".join(original_indent.format(result.rstrip().splitlines()))
            log("Result:")
            log(result)
            text_edit = TextEdit(
                range=range_,
                new_text=result,
            )
            ls.apply_edit(WorkspaceEdit(changes={uri: [text_edit]}))
        else:
            log("|FAILED|\nResponse:")
            log(result)
            ls.show_message(
                "Model did not produce a valid result",
                MessageType.Warning,
            )

    # Register the wrapped function as a command
    server.command(id_)(wrapped)

    command_kwargs = command_kwargs or {}
    command_kwargs.setdefault("title", id_)
    code_action_kwargs = code_action_kwargs or {}
    code_action_kwargs.setdefault("kind", CodeActionKind.RefactorRewrite)

    async def code_action(params: CodeActionParams):
        uri = params.text_document.uri
        start = params.range.start
        end = params.range.end
        return [
            CodeAction(
                command=Command(
                    command=id_,
                    arguments=[
                        uri,
                        start.line,
                        start.character,
                        end.line,
                        end.character,
                    ],
                    **command_kwargs,
                ),
                **code_action_kwargs,
            )
        ]

    # Register a code action that triggers the command
    return server.feature(TEXT_DOCUMENT_CODE_ACTION)(code_action)
