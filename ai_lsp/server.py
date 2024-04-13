import importlib.util
import os
from pathlib import Path
from typing import List, Optional

import git
from pygls.server import LanguageServer

from . import code_actions
from . import language as lang
from . import workspace as wrk


class AILanguageServer(LanguageServer):
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

    def get_other_files_context(self, current_uri: str) -> List[str]:
        """Returns a context string with the content of other files in the workspace."""
        root = self.workspace.root_path
        other_files = []
        if root:
            for p in wrk.visible_files(git.Repo(root), Path(root)):
                language = lang.from_extension(p.suffix.lstrip("."))
                uri = p.as_uri()
                if uri == current_uri:
                    continue
                content = self.workspace.get_text_document(uri).lines
                if not content:
                    continue
                other_files.append(language.path_comment(p.relative_to(root)))
                other_files.extend(content)
        return other_files

    @classmethod
    def from_config(cls) -> "AILanguageServer":
        path = (
            Path(
                os.environ.get(
                    "XDG_CONFIG_HOME", os.path.join(os.environ["HOME"], ".config")
                )
            )
            / "ai_lsp/init.py"
        )
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


# completion_client = AsyncOpenAI(api_key="sk-blah", base_url="http://localhost:7777/v1")


# def get_completion_context(params: CompletionParams) -> Tuple[str, str, str]:
#     document = server.workspace.get_document(params.text_document.uri)
#
#     other_files = wrk.get_other_files_context(server, params.text_document.uri)
#     # If there are other files in the workspace, add a comment to delimit the current file
#     if other_files:
#         path = wrk.uri_to_path(params.text_document.uri)
#         language = lang.from_extension(path.suffix.lstrip("."))
#         other_files.append(
#             language.path_comment(
#                 path.relative_to(server.workspace.root_path or path.parent)
#             )
#         )
#
#     # Split the current line at the cursor position
#     lines = document.lines
#     line_no = params.position.line
#     col = params.position.character
#     cur_line = lines[line_no]
#     before_cursor = "".join(lines[:line_no] + [cur_line[:col]])
#     after_cursor = "".join([cur_line[col:]] + lines[line_no + 1 :])
#     return "".join(other_files), before_cursor, after_cursor


# @server.feature(
#     TEXT_DOCUMENT_COMPLETION,
#     CompletionOptions(trigger_characters=[" ", "\n"]),
# )
# async def completions(params: CompletionParams):
#     other_files, before, after = get_completion_context(params)
#     prompt = (
#         f"""{other_files}<｜fim▁begin｜>{before}<｜fim▁hole｜>{after}<｜fim▁end｜>"""
#     )
#     log("Prompt")
#     log(prompt)
#     response = await completion_client.completions.create(
#         top_p=0.9,
#         best_of=3,
#         seed=1234,
#         max_tokens=200,
#         model="deepseek-coder-base",
#         prompt=prompt,
#     )
#     completion = response.choices[0].text
#     return CompletionList(
#         is_incomplete=False,
#         items=[
#             CompletionItem(
#                 label=completion,
#                 text_edit_text=completion,
#                 kind=CompletionItemKind.Text,
#             ),
#         ],
#         item_defaults=CompletionListItemDefaultsType(
#             edit_range=CompletionListItemDefaultsTypeEditRangeType1(
#                 Range(params.position, params.position),
#                 Range(params.position, params.position),
#             )
#         ),
#     )
#
