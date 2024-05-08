import re
from collections.abc import Callable
from enum import Enum
from typing import Awaitable, ClassVar, Optional

from lsprotocol.types import (
    CodeActionKind,
    MessageType,
    Position,
    Range,
    TextEdit,
    WorkspaceEdit,
)
from pydantic import BaseModel, Field, ValidationError
from result import Err, Ok, Result

from . import language as lang
from . import workspace as wrk
from .logging import log


class ActionParams(BaseModel):
    """A base class for parameters that can be passed to a Grimoire action."""

    template_start_str: ClassVar[str] = "<|grimoire-params-start|>"
    template_end_str: ClassVar[str] = "<|grimoire-params-end|>"

    @classmethod
    def to_template_lines(cls) -> list[str]:
        """Generate a set of lines for the user to specify these parameters."""
        result = [cls.template_start_str]
        for k, v in cls.model_json_schema()["properties"].items():
            type_ = v.get("type")
            if k not in v.get("required", []):
                type_ += "?"
            desc = v.get("description", "")
            if desc:
                desc = f" - {desc}"
            default = v.get("default", "")
            result.append(f"{k}[{type_}{desc}]: {default}")
        result.append(cls.template_end_str + "\n")
        return result

    @classmethod
    def from_template_lines(cls, lines: list[str]) -> Result["ActionParams", str]:
        """Parse parameters from lines that describe the parameters."""
        arg_dict = {}
        for line in lines:
            key, tail = line.split("[", maxsplit=1)
            value = re.match(r".*\]: ?(.+)$", tail)
            if value:
                arg_dict[key] = value.group(1)
        try:
            return Ok(cls.model_validate(arg_dict))
        except ValidationError as e:
            return Err(str(e))

    @classmethod
    def extract_from_lines(
        cls, lines: list[str], language: lang.Language
    ) -> tuple[Result["ActionParams", str], list[str]]:
        """Extract the parameters from the beginning of `lines` and return the remaining lines."""
        i = 0
        param_lines = []
        for i, line in enumerate(lines):
            line = language.uncomment(line.strip()).strip()
            if i == 0:
                if line != cls.template_start_str:
                    return Err("Could not find parameters"), lines
                continue
            if line == cls.template_end_str:
                break
            param_lines.append(line)
        return cls.from_template_lines(param_lines), lines[i + 1 :]


class GrimoireActionType(Enum):
    """What to do with the resulting content of the code action."""

    replace = "replace"
    prepend = "prepend"
    append = "append"


class ActionOptions(BaseModel):
    id: str
    title: Optional[str] = None
    action: GrimoireActionType = GrimoireActionType.replace
    params: Optional[type[ActionParams]] = None
    command_kwargs: dict = Field(default_factory=dict)
    code_action_kwargs: dict = Field(default_factory=dict)
    log: bool = False

    def model_post_init(self, _):
        self.title = self.title or self.id
        self.code_action_kwargs.setdefault("title", self.title)
        self.command_kwargs.setdefault("title", self.title)
        self.code_action_kwargs.setdefault("kind", CodeActionKind.RefactorRewrite)


TransformFn = Callable[[str, Optional[ActionParams]], Awaitable[Result[str, str]]]


def wrap_transform(
    f: TransformFn,
    options: ActionOptions,
):
    """Creates a code action from a function that takes in a string and returns a string."""

    # NOTE: `ls` variable name cannot be changed. It is hard-coded in pygls
    async def wrapped(ls, args: tuple[str, int, int, int, int]):
        uri, start_line, start_col, end_line, end_col = args
        document = ls.workspace.get_document(uri)
        range_ = Range(Position(start_line, start_col), Position(end_line, end_col))
        lines = wrk.lines_from_range(document.lines, range_)
        original_indent = wrk.Indentation.from_lines(lines)
        n_param_lines = 0
        params = None

        if options.params:
            language = lang.from_extension(wrk.uri_to_path(uri).suffix)
            match options.params.extract_from_lines(lines, language):
                case (Ok(parsed_params), new_lines):
                    params = parsed_params
                    n_param_lines = len(lines) - len(new_lines)
                    lines = new_lines
                case (Err(e), new_lines):
                    ls.show_message(
                        f"Parameters required: {e}",
                        MessageType.Info,
                    )
                    # If the parameters are not valid, (re)insert the template lines
                    template_lines = original_indent.format(
                        [
                            language.comment(line)
                            for line in options.params.to_template_lines()
                        ]
                    )
                    n_param_lines = len(lines) - len(new_lines)
                    text_edit = TextEdit(
                        range=Range(
                            Position(start_line, start_col),
                            Position(start_line + n_param_lines, start_col),
                        ),
                        new_text="\n".join(template_lines),
                    )
                    ls.apply_edit(WorkspaceEdit(changes={uri: [text_edit]}))
                    return

        text = "".join(lines).strip()
        edits = []
        # Remove the parameters from the text if they were present
        if n_param_lines:
            edits.append(
                TextEdit(
                    range=Range(
                        Position(start_line, start_col),
                        Position(start_line + n_param_lines, start_col),
                    ),
                    new_text="",
                )
            )
            start_line += n_param_lines

        match await f(text, params):
            case Ok(result):
                # NOTE: rstrip is important to remove trailing whitespace which can mess up the indentation
                result = "\n".join(original_indent.format(result.rstrip().splitlines()))
                if options.log:
                    log("Result:")
                    log(result)

                match options.action:
                    case GrimoireActionType.replace:
                        range_ = Range(
                            Position(start_line, start_col),
                            Position(end_line, end_col),
                        )
                    case GrimoireActionType.append:
                        range_ = Range(
                            Position(end_line, end_col),
                            Position(end_line, end_col),
                        )
                    case GrimoireActionType.prepend:
                        range_ = Range(
                            Position(start_line, start_col),
                            Position(start_line, start_col),
                        )
                edits.append(
                    TextEdit(
                        range=range_,
                        new_text=result,
                    )
                )
                ls.apply_edit(WorkspaceEdit(changes={uri: edits}))
            case Err(e):
                if options.log:
                    log("!!!FAILED!!!\nResponse:")
                    log(e)
                ls.show_message(
                    "Model did not produce a valid result",
                    MessageType.Warning,
                )

    return wrapped
