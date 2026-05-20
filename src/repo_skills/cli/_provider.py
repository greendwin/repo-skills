from __future__ import annotations

import typer
from typer_di import TyperDI

from repo_skills.config import (
    BUILTIN_PROVIDER_NAME,
    PROVIDERS_REGISTRY_FILE,
    ProviderConfig,
    ProviderRegistry,
    default_config_dir,
)
from repo_skills.errors import AppError

from ._app import app
from ._utils import echo

provider_app = TyperDI(
    help="Manage skill providers.",
    no_args_is_help=True,
)
app.add_typer(provider_app, name="provider")


def _load_registry() -> ProviderRegistry:
    path = default_config_dir() / PROVIDERS_REGISTRY_FILE
    return ProviderRegistry.load(path)


def _save_registry(registry: ProviderRegistry) -> None:
    path = default_config_dir() / PROVIDERS_REGISTRY_FILE
    registry.save(path)


@provider_app.command(name="add", help="Register a new provider.")
def provider_add(
    name: str = typer.Argument(help="Provider name."),
    install_dir: str = typer.Option(
        ..., "--install-dir", help="Path to the provider's skills directory."
    ),
) -> None:
    registry = _load_registry()

    if name in registry.with_builtins().providers:
        raise AppError(f"Provider [cyan]{name}[/cyan] already exists.")

    registry.providers[name] = ProviderConfig(name=name, install_dir=install_dir)
    _save_registry(registry)

    echo(f"Added provider [green]{name}[/green].")


@provider_app.command(name="list", help="List all registered providers.")
def provider_list() -> None:
    registry = _load_registry().with_builtins()

    echo("[yellow]Providers:[/yellow]")
    width = max(len(n) for n in registry.providers)
    width = max(width, 16)
    for name, cfg in registry.providers.items():
        label = f"[green]{name:<{width}}[/green]"
        path = f"[dim white]{cfg.install_dir}[/dim white]"
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

    registry = _load_registry()

    if name not in registry.providers:
        raise AppError(f"Provider [cyan]{name}[/cyan] not found.")

    del registry.providers[name]
    _save_registry(registry)

    echo(f"Removed provider [green]{name}[/green].")
