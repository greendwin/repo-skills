import click


@click.group()
def cli() -> None:
    """Manage Claude Code skills."""


@cli.command()
def install() -> None:
    """Install a skill from the repo."""


@cli.command()
def update() -> None:
    """Update installed skills from the repo."""


@cli.command()
def peek() -> None:
    """Show changes between repo and installed skills."""


@cli.command()
def merge() -> None:
    """Resolve conflicts between repo and installed skills."""


@cli.command(name="list")
def list_() -> None:
    """List available and installed skills."""


@cli.command()
def uninstall() -> None:
    """Uninstall a skill."""
