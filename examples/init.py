import re
from lsprotocol.types import (
    TEXT_DOCUMENT_DID_SAVE,
    CompletionItem,
    CompletionItemKind,
    CompletionOptions,
    CompletionParams,
    Diagnostic,
    DiagnosticSeverity,
    DidOpenTextDocumentParams,
    Position,
    Range,
)
from typing import Optional
from openai import OpenAI
from ai_lsp.server import AILanguageServer
from ai_lsp.logging import log
from ai_lsp import completion as cmp
from pydantic import BaseModel, Field
import instructor

server = AILanguageServer("ai-lsp", "v0.1")
oai_client = OpenAI(api_key="sk-blah", base_url="http://localhost:7777/v1")
instr_client = instructor.from_openai(oai_client)


@server.completion(CompletionOptions(trigger_characters=[" ", "\n"]))
async def completions(params: CompletionParams):
    before, after, workspace = cmp.get_context(
        server, params, include_workspace_context=False
    )
    prompt = f"""{workspace}<｜fim▁begin｜>{before}<｜fim▁hole｜>{after}<｜fim▁end｜>"""
    log("Prompt")
    log(prompt)
    response = oai_client.completions.create(
        top_p=0.9,
        best_of=3,
        seed=1234,
        max_tokens=200,
        model="deepseek-coder-base",
        prompt=prompt,
        stop=["\n\n", "<|EOT|>"],
    )
    if not response.choices:
        return []
    completion = response.choices[0].text
    log("Completion:")
    log(completion)
    return [
        CompletionItem(
            label=completion,
            text_edit_text=completion,
            kind=CompletionItemKind.Text,
        ),
    ]


class Improvement(BaseModel):
    start_line: int = Field(
        description="The first line number related to the suggestion"
    )
    end_line: int = Field(
        description="The last line number related to the suggestion (inclusive; same as start_line for single-line suggestions)"
    )
    suggestion: str = Field(
        description="A brief description of the suggested change (does not include the line numbers)"
    )


@server.feature(TEXT_DOCUMENT_DID_SAVE)
async def style_improvements(
    ls: AILanguageServer, params: DidOpenTextDocumentParams
) -> Optional[str]:
    code = "\n".join(ls.workspace.get_document(params.text_document.uri).lines)
    prompt = f"""<｜begin▁of▁sentence｜>You are a state of the art AI programming assistant.
    ### Instruction:
    Suggest stylistic improvements to this code.
    ```python
    {code}
    ```
    Only suggest things that improve the readability or maintainability of the code.
    DO suggest better names (only if needed), point out where there is a more idiomatic equivalent.
    DO suggest docstrings and type hints where appropriate.
    Do NOT suggest changes that would alter the functionality of the code.
    Do NOT suggest adding comments.
    Be conservative: only suggest a change if the improvement is significant, and make sure your suggestions are appropriate for this programming language.
    Respond with a short list of improvements. For each improvement provide a brief one sentence explanation of the suggested change, and state the line numbers where the change should be applied.
    At the end of the list on a new line write "<end suggestions>"
    If you have no suggestions, respond with "<end suggestions>"
    ### Response:
    """
    response = oai_client.completions.create(
        model="deepseek-coder-instruct",
        prompt=prompt,
        best_of=3,
        top_p=0.9,
        seed=1234,
        max_tokens=1000,
        stop=["<end suggestions>", "<|EOT|>"],
    )
    if not response.choices:
        raise ValueError("No suggestions were returned.")

    suggestions = response.choices[0].text

    prompt = f"Extract the suggestions and line numbers:\n{suggestions}"
    improvements = instr_client.chat.completions.create_iterable(
        model="hermes-2-pro",
        messages=[{"role": "user", "content": prompt}],
        response_model=Improvement,
    )
    diagnostics = []
    for imp in improvements:
        diagnostics.append(
            Diagnostic(
                range=Range(
                    start=Position(imp.start_line, 0),
                    end=Position(imp.end_line, 0),
                ),
                message=imp.suggestion,
                severity=DiagnosticSeverity.Hint,
            )
        )
    log("Completed diagnostics!")
    ls.publish_diagnostics(params.text_document.uri, diagnostics)


@server.code_action_replace("simplify", "Simplify this code")
async def simplify(text: str) -> Optional[str]:
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
    response = oai_client.completions.create(
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

    return completion or None
