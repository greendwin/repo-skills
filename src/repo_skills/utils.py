import os
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

_T = TypeVar("_T", bound=BaseModel)


def fmt_ident(text: str) -> str:
    return f"[green]{text}[/green]"


def fmt_path(path: Path | str) -> str:
    return f"[dim]{path}[/dim]"


def fmt_data(text: str) -> str:
    return f"[cyan]{text}[/cyan]"


def fmt_command(text: str) -> str:
    return f"[blue]{text}[/blue]"


def fmt_message(
    message: str,
    *,
    hint: str = "",
    props: dict[str, str] | None = None,
) -> str:
    r = message
    if props:
        for k, v in props.items():
            if k:
                r += f"\n  {k}: {v}"
            else:
                # support little hack for data without key
                r += f"\n{v.rstrip()}"
    if hint:
        r += f"\n\n{hint}"
    return r


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_config(cls: type[_T], path: Path) -> _T | None:
    if not os.path.exists(path):
        return None

    return cls.model_validate_json(read_text(path))


def save_config(cfg: BaseModel, path: Path) -> None:
    write_text(path, cfg.model_dump_json(indent=2))
