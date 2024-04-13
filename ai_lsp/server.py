import re
from typing import Tuple

from lsprotocol.types import (
    TEXT_DOCUMENT_CODE_ACTION,
    TEXT_DOCUMENT_COMPLETION,
    CodeAction,
    CodeActionKind,
    CodeActionOptions,
    CodeActionParams,
    Command,
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionListItemDefaultsType,
    CompletionListItemDefaultsTypeEditRangeType1,
    CompletionOptions,
    CompletionParams,
    MessageType,
    Position,
    Range,
    TextEdit,
    WorkspaceEdit,
)
from openai import AsyncOpenAI
from pygls.server import LanguageServer

from . import workspace as wrk, language as lang
from .logging import log


class AILanguageServer(LanguageServer):
    CMD_SIMPLIFY = "simplify"


server = AILanguageServer("ai-lsp", "v0.1")

completion_client = AsyncOpenAI(api_key="sk-blah", base_url="http://localhost:7777/v1")
chat_client = AsyncOpenAI(api_key="sk-blah", base_url="http://localhost:7778/v1")


def get_completion_context(params: CompletionParams) -> Tuple[str, str, str]:
    document = server.workspace.get_document(params.text_document.uri)

    other_files = wrk.get_other_files_context(server, params.text_document.uri)
    # If there are other files in the workspace, add a comment to delimit the current file
    if other_files:
        path = wrk.uri_to_path(params.text_document.uri)
        language = lang.from_extension(path.suffix.lstrip("."))
        other_files.append(
            language.path_comment(
                path.relative_to(server.workspace.root_path or path.parent)
            )
        )

    # Split the current line at the cursor position
    lines = document.lines
    line_no = params.position.line
    col = params.position.character
    cur_line = lines[line_no]
    before_cursor = "".join(lines[:line_no] + [cur_line[:col]])
    after_cursor = "".join([cur_line[col:]] + lines[line_no + 1 :])
    return "".join(other_files), before_cursor, after_cursor


@server.feature(
    TEXT_DOCUMENT_COMPLETION,
    CompletionOptions(trigger_characters=[" ", "\n"]),
)
async def completions(params: CompletionParams):
    other_files, before, after = get_completion_context(params)
    prompt = (
        f"""{other_files}<｜fim▁begin｜>{before}<｜fim▁hole｜>{after}<｜fim▁end｜>"""
    )
    log("Prompt")
    log(prompt)
    response = await completion_client.completions.create(
        top_p=0.9,
        best_of=3,
        seed=1234,
        max_tokens=200,
        model="deepseek-coder-base",
        prompt=prompt,
    )
    completion = response.choices[0].text
    return CompletionList(
        is_incomplete=False,
        items=[
            CompletionItem(
                label=completion,
                text_edit_text=completion,
                kind=CompletionItemKind.Text,
            ),
        ],
        item_defaults=CompletionListItemDefaultsType(
            edit_range=CompletionListItemDefaultsTypeEditRangeType1(
                Range(params.position, params.position),
                Range(params.position, params.position),
            )
        ),
    )


@server.command(AILanguageServer.CMD_SIMPLIFY)
async def simplify(
    ls: AILanguageServer,
    args: Tuple[str, int, int, int, int],
):
    uri, start_line, start_col, end_line, end_col = args
    document = ls.workspace.get_document(uri)
    text = document.lines[start_line : end_line + 1]
    if text:
        text[0] = text[0][start_col:]
        text[-1] = text[-1][: end_col + 1]
    text = "".join(text).strip()

    prompt = f"""<｜begin▁of▁sentence｜>You are a state of the art AI programming assistant.
    ### Instruction:
    Simplify the code as much as possible while preserving the original functionality.
    ```
    {text}
    ```
    ### Response:
    ```
    """
    log("Prompt:")
    log(prompt)
    log("")
    response = await chat_client.completions.create(
        model="deepseek-coder-instruct",
        prompt=prompt,
        best_of=3,
        top_p=0.9,
        seed=1234,
        max_tokens=1000,
        stop=["```", "<|EOT|>"],
    )
    completion = ""
    if response.choices:
        completion = response.choices[0].text
    if "```" in completion:
        match = re.search(r"(.*?)```", completion)
        if match:
            completion = match.group(1)

    if completion:
        original_indent = wrk.Indentation.from_lines(text.splitlines())
        # NOTE: rstrip is important to remove trailing whitespace which can mess up the indentation
        completion = "\n".join(original_indent.format(completion.rstrip().splitlines()))
        log("Completion:")
        log(completion)
        text_edit = TextEdit(
            range=Range(Position(start_line, start_col), Position(end_line, end_col)),
            new_text=completion,
        )
        ls.apply_edit(WorkspaceEdit(changes={uri: [text_edit]}))
    else:
        log("|FAILED|\nResponse:")
        log(completion)
        ls.show_message("Could not simplify the code", MessageType.Warning)


@server.feature(
    TEXT_DOCUMENT_CODE_ACTION,
    CodeActionOptions(code_action_kinds=[CodeActionKind.QuickFix]),
)
async def code_actions(params: CodeActionParams):
    items = []
    uri = params.text_document.uri
    start = params.range.start
    end = params.range.end
    items.append(
        CodeAction(
            title="Simplify this code",
            kind=CodeActionKind.RefactorRewrite,
            command=Command(
                title="Simplify",
                command=AILanguageServer.CMD_SIMPLIFY,
                arguments=[uri, start.line, start.character, end.line, end.character],
            ),
        )
    )
    return items


if __name__ == "__main__":
    try:
        server.start_io()
    except Exception as e:
        log(e)
        raise e
