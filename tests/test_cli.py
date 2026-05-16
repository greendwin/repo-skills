from click.testing import CliRunner

from skill_cli.main import cli


def test_help_lists_all_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for cmd in ("install", "update", "peek", "merge", "list", "uninstall"):
        assert cmd in result.output


COMMANDS = ("install", "update", "peek", "merge", "list", "uninstall")


def test_each_subcommand_has_help(subtests) -> None:  # type: ignore[no-untyped-def]
    runner = CliRunner()
    for cmd in COMMANDS:
        with subtests.test(cmd=cmd):
            result = runner.invoke(cli, [cmd, "--help"])
            assert result.exit_code == 0
