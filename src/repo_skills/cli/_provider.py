from __future__ import annotations

import typer
from cli_error import CliError
from typer_di import TyperDI

from repo_skills.config import (
    load_provider_registry,
    save_provider_registry,
)
from repo_skills.console import reporter

from ._app import app

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
    provider_registry = load_provider_registry()

    if provider_registry.is_registered(name):
        raise CliError("Provider [id]{name}[/id] already exists.", name=name)

    provider_registry.register(name, install_dir)
    save_provider_registry(provider_registry)

    reporter.print("Added provider [id]{name}[/id].", name=name)


@provider_app.command(name="list", help="List all registered providers.")
def provider_list() -> None:
    registry = load_provider_registry()

    reporter.print("[yellow]Providers:[/yellow]")
    width = max(len(p.name) for p in registry.providers)
    width = max(width, 16)
    for provider in registry.providers:
        reporter.print(
            "* [id]{label}[/id]  [data]{path}[/data]",
            label=f"{provider.name:<{width}}",
            path=str(provider.install_path),
        )


@provider_app.command(name="remove", help="Remove a provider.")
def provider_remove(
    name: str = typer.Argument(help="Name of the provider to remove."),
) -> None:
    registry = load_provider_registry()

    registry.require(name)
    registry.unregister(name)
    save_provider_registry(registry)

    reporter.print("Removed provider [id]{name}[/id].", name=name)
