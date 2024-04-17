from pathlib import Path

path = Path("~/Projects/grimoire_ls/grimoire_ls.log").expanduser()
path.write_text("")


def log(x):
    if not isinstance(x, str):
        x = repr(x)
    with path.open("a") as f:
        f.write(f"{x}\n")
