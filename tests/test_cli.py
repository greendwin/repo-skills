from pytest_subtests import SubTests

from skill_cli.main import cli
from tests.helper import assert_invoke


def test_help_lists_all_commands() -> None:
    result = assert_invoke(cli, ["--help"])
    for cmd in ("install", "update", "peek", "merge", "list", "uninstall"):
        assert cmd in result.output


COMMANDS = ("install", "update", "peek", "merge", "list", "uninstall")


def test_each_subcommand_has_help(subtests: SubTests) -> None:
    for cmd in COMMANDS:
        with subtests.test(cmd=cmd):
            assert_invoke(cli, [cmd, "--help"])
