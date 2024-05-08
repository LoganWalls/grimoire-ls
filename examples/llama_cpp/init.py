"""This example uses the OpenAI API client to access local models running with Llama.cpp"""

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
from result import Err, Ok, Result
from grimoire_ls.code_actions import ActionOptions, ActionParams
from grimoire_ls.server import GrimoireServer
from grimoire_ls.logging import log
from grimoire_ls import completion as cmp
from pydantic import BaseModel, Field
import instructor

server = GrimoireServer()
# Note that the `api_key` is a dummy value (it is not required) for local models,
# the `base_url` points to the local Llama.cpp server instead of the OpenAI API.
oai_client = OpenAI(api_key="sk-blah", base_url="http://localhost:7777/v1")
instr_client = instructor.from_openai(oai_client)


@server.completion(CompletionOptions(trigger_characters=[" ", "\n"]))
async def completions(params: CompletionParams) -> Result[list[CompletionItem], str]:
    """Uses a fill-in-the-middle completion prompt to provide LLM-generated code completions."""

    # Use this helper to get the content of the current file before and after the cursor
    # Optionally, you can include the entire workspace content if you think the model
    # might benefit from more context (this will result in slower completions, though).
    before, after, workspace = cmp.get_context(
        server, params, include_workspace_context=False
    )

    # Prompts are model-specific, so make sure to adapt the prompt to the model you are using
    # Also note that not all models were trained to do fill-in-the-middle completions, so take
    # that into account when choosing a model, or consider using only the `before` context.
    prompt = f"""{workspace}<｜fim▁begin｜>{before}<｜fim▁hole｜>{after}<｜fim▁end｜>"""

    # The log function will write to an external log file for debugging
    # You can control the location of the file with the `GRIMOIRE_LS_LOG` environment variable
    log("Prompt")
    log(prompt)
    response = oai_client.completions.create(
        top_p=0.9,
        best_of=3,
        seed=1234,
        # This corresponds to the model alias defined in the `llama-cpp-server-config.json` file
        model="deepseek-coder-base",
        prompt=prompt,
        # You can adjust `max_tokens` and the `stop` sequences to allow shorter or longer completions
        max_tokens=200,
        stop=[
            "\n\n",
            "<|EOT|>",
        ],
    )
    if not response.choices:
        # Note that we are using the `Err` and `Ok` types from the `result` library
        return Err("Could not generate completions.")
    completion = response.choices[0].text
    log("Completion:")
    log(completion)

    # Note that we are using the `Err` and `Ok` types from the `result` library
    return Ok(
        [
            CompletionItem(
                label=completion,
                text_edit_text=completion,
                kind=CompletionItemKind.Text,
            ),
        ]
    )


# Used with with `instructor` to extract structured outputs from the language model.
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


# This is expensive, so it's disabled by default
# Uncomment to enable the style suggestions on save
# @server.feature(TEXT_DOCUMENT_DID_SAVE)
async def style_improvements(
    ls: GrimoireServer, params: DidOpenTextDocumentParams
) -> Optional[str]:
    """Provide style suggestions for the code as diagnostics.
    This example combines two different models. It uses a code model `deepseek-coder-instruct` to
    make suggestions about improvements. However, the code model is not designed to provide structured
    outputs. So, we use the `hermes-pro-2` combined with the `instructor` library to convert the first
    model's output into structured objects that we can return as diagnostics.
    """

    # Get the content of the current file
    code = "\n".join(ls.workspace.get_document(params.text_document.uri).lines)

    # Again, make sure to adapt the prompt to the model you are using
    prompt = f"""<｜begin▁of▁sentence｜>You are a state of the art AI programming assistant.
    ### Instruction:
    Suggest stylistic improvements to this code.
    ```
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
        model="hermes-2-pro",  # Note that the moodel name is different from the one used in the previous call
        messages=[{"role": "user", "content": prompt}],
        response_model=Improvement,  # This specifies the expected output structure
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
    ls.publish_diagnostics(params.text_document.uri, diagnostics)


@server.code_action(ActionOptions(id="simplify", title="Simplify this code"))
async def simplify(text: str, _) -> Result[str, str]:
    """A code action that uses a language model to simplify the code."""

    prompt = f"""<｜begin▁of▁sentence｜>You are a state of the art AI programming assistant.
    ### Instruction:
    Simplify the code as much as possible while preserving the original functionality.
    ```
    {text}
    ```
    ### Response:
    ```
    """
    response = oai_client.completions.create(
        model="deepseek-coder-instruct",
        prompt=prompt,
        best_of=3,
        top_p=0.9,
        seed=1234,
        temperature=0.1,
        max_tokens=1000,
        # Notice that the prompt includes the start of a code block and
        # `stop` includes the closing triple backticks so we can ensure
        # that the model will only generate code, and not other text.
        stop=["```", "<|EOT|>"],
    )
    result = ""
    if response.choices:
        result = response.choices[0].text
    if "```" in result:
        match = re.search(r"(.*?)```", result)
        if match:
            result = match.group(1)
    if not result:
        return Err("Could not simplify the code.")

    return Ok(result)


# This class defines the parameters for the action
class CustomInstructionParams(ActionParams):
    instruction: str
    best_of: int = 3
    top_p: float = 0.9
    seed: int = 1234
    temperature: float = 0.1
    max_tokens: int = 1000


@server.code_action(
    ActionOptions(
        id="custom_instruction",
        title="Custom instruction",
        params=CustomInstructionParams,
        log=True,
    )
)
async def custom_instruction(
    text: str, params: CustomInstructionParams
) -> Result[str, str]:
    """A code action that uses a language model to simplify the code."""

    # NOTE: using a """ f-string broke python indentation for this example
    # So we use a " string split into multiple lines instead
    prompt = (
        "<｜begin▁of▁sentence｜>You are a state of the art AI programming assistant.\n"
        "### Instruction:\n"
        f"{params.instruction}\n"
        f"```\n{text}\n```"
        "### Response:\n```\n"
    )
    log(prompt)
    response = oai_client.completions.create(
        model="deepseek-coder-instruct",
        prompt=prompt,
        best_of=params.best_of,
        top_p=params.top_p,
        seed=1234,
        temperature=params.temperature,
        max_tokens=params.max_tokens,
        stop=["```", "<|EOT|>"],
    )
    result = ""
    if response.choices:
        result = response.choices[0].text
    if "```" in result:
        match = re.search(r"(.*?)```", result)
        if match:
            result = match.group(1)
    if not result:
        log("Failed result:\n")
        return Err("Could not execute instruction.")

    return Ok(result)
