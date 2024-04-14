import re
from lsprotocol.types import (
    CompletionItem,
    CompletionItemKind,
    CompletionOptions,
    CompletionParams,
)
from typing import Optional
from openai import AsyncOpenAI
from ai_lsp.server import AILanguageServer
from ai_lsp.logging import log
from ai_lsp import completion as cmp

server = AILanguageServer("ai-lsp", "v0.1")
chat_client = AsyncOpenAI(api_key="sk-blah", base_url="http://localhost:7778/v1")
completion_client = AsyncOpenAI(api_key="sk-blah", base_url="http://localhost:7777/v1")


@server.completion(CompletionOptions(trigger_characters=[" ", "\n"]))
async def completions(params: CompletionParams):
    before, after, workspace = cmp.get_context(
        server, params, include_workspace_context=False
    )
    prompt = f"""{workspace}<｜fim▁begin｜>{before}<｜fim▁hole｜>{after}<｜fim▁end｜>"""
    log("Prompt")
    log(prompt)
    response = await completion_client.completions.create(
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

    return completion or None
