from typing import Tuple

from lsprotocol.types import CompletionParams
from ai_lsp.server import AILanguageServer
from . import workspace as wrk
from . import language as lang


def get_context(
    server: AILanguageServer,
    params: CompletionParams,
    include_workspace_context: bool = False,
) -> Tuple[str, str, str]:
    """Returns the content of current file before and after the cursor position.
    If `include_workspace_context` is `True`, the third return value will be the
    content of all other files in the workspace, delimited by comments with their
    file name (if `False`, it will be an empty string)"""
    uri = params.text_document.uri

    # Split the current line at the cursor position
    document = server.workspace.get_document(uri)
    lines = document.lines
    line_no = params.position.line
    col = params.position.character
    cur_line = lines[line_no]
    before_middle = "".join(lines[:line_no] + [cur_line[:col]])
    after_middle = "".join([cur_line[col:]] + lines[line_no + 1 :])

    path = wrk.uri_to_path(uri)
    workspace_context = []
    if include_workspace_context:
        for p, content in wrk.workspace_file_contents(server).items():
            if p != path:
                language = lang.from_extension(p.suffix.lstrip("."))
                workspace_context.append(
                    language.path_comment(
                        p.relative_to(server.workspace.root_path or p.parent)
                    )
                )
                workspace_context.extend(content)

    if workspace_context:
        #  Add a comment to delimit the current file
        language = lang.from_extension(path.suffix.lstrip("."))
        workspace_context.append(
            language.path_comment(
                path.relative_to(server.workspace.root_path or path.parent)
            )
        )

    return before_middle, after_middle, "".join(workspace_context)
