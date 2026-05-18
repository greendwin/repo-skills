from pytest_subtests import SubTests

from tests.helper import assert_invoke


def test_help_lists_all_commands() -> None:
    result = assert_invoke("--help")
    for cmd in ("install", "update", "uninstall", "source"):
        assert cmd in result.output


COMMANDS = ("install", "update", "uninstall", "source")


def test_each_subcommand_has_help(subtests: SubTests) -> None:
    for cmd in COMMANDS:
        with subtests.test(cmd=cmd):
            assert_invoke(cmd, "--help")
