from __future__ import annotations

import typer
from typer_di import TyperDI

from repo_skills.config.deprecated import (
    BUILTIN_PROVIDER_NAME,
    ProviderConfig,
    load_provider_registry,
    save_provider_registry,
)
from repo_skills.errors import AppError
from repo_skills.utils import fmt_data, fmt_ident

from ._app import app
from ._utils import echo

provider_app = TyperDI(
    help="Manage skill providers.",
    no_args_is_help=True,
)
app.add_typer(provider_app, name="provider")


@provider_app.command(name="add", help="Register a new provider.")
def provider_add(
    name: str = typer.Argument(help="Provider name."),
    install_dir: str = typer.Option(
        ..., "--install-dir", help="Path to the provider's skills directory."
    ),
) -> None:
    registry = load_provider_registry(with_builtins=False)

    if name in load_provider_registry().providers:
        raise AppError(f"Provider {fmt_ident(name)} already exists.")

    registry.providers[name] = ProviderConfig(name=name, install_dir=install_dir)
    save_provider_registry(registry)

    echo(f"Added provider {fmt_ident(name)}.")


@provider_app.command(name="list", help="List all registered providers.")
def provider_list() -> None:
    registry = load_provider_registry()

    echo("[yellow]Providers:[/yellow]")
    width = max(len(n) for n in registry.providers)
    width = max(width, 16)
    for name, cfg in registry.providers.items():
        label = fmt_ident(f"{name:<{width}}")
        path = fmt_data(str(cfg.install_dir))
        if name == BUILTIN_PROVIDER_NAME:
            echo(f"* {label}  {path}  [dim](built-in)[/dim]")
        else:
            echo(f"* {label}  {path}")


@provider_app.command(name="remove", help="Remove a provider.")
def provider_remove(
    name: str = typer.Argument(help="Name of the provider to remove."),
) -> None:
    if name == BUILTIN_PROVIDER_NAME:
        raise AppError("Cannot remove the built-in provider.")

    registry = load_provider_registry(with_builtins=False)

    registry.require(name)
    del registry.providers[name]
    save_provider_registry(registry)

    echo(f"Removed provider {fmt_ident(name)}.")
