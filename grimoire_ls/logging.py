import os
from pathlib import Path

path = Path(
    os.environ.get(
        "GRIMOIRE_LS_LOG", Path(".").expanduser().resolve() / "grimoire-ls.log"
    )
)


def log(x):
    """Log an object to the log file specified by the `GRIMOIRE_LS_LOG` environment variable.
    If the variable is not set, the log file will be created in the current working directory."""
    if not isinstance(x, str):
        x = repr(x)
    with path.open("a") as f:
        f.write(f"{x}\n")
