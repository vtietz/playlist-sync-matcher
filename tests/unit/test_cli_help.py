"""Tests for CLI help system and workflow examples."""

from click.testing import CliRunner
from psm.cli import cli


def test_cli_help_contains_workflow_examples():
    """Test that main CLI help contains workflow examples."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0

    # Check for workflow examples section
    assert "TYPICAL WORKFLOWS:" in result.output

    # Check for key workflow examples
    assert "Initial Setup:" in result.output
    assert "login" in result.output
    assert "scan" in result.output

    assert "Full Sync" in result.output
    assert "pull" in result.output
    assert "match" in result.output
    assert "export" in result.output

    # Note: The text formatting breaks "Single Playlist Workflow:" across lines
    assert "Single Playlist" in result.output
    assert "Workflow:" in result.output
    assert "playlist pull PLAYLIST_ID" in result.output
    assert "playlist build PLAYLIST_ID" in result.output

    assert "Quality Analysis:" in result.output
    assert "analyze" in result.output
    assert "report" in result.output

    assert "Maintenance:" in result.output
    assert "diagnose" in result.output  # Changed from 'match-diagnose' to 'diagnose'

    # Check concurrency note (updated to reflect WAL mode support)
    assert "concurrent" in result.output.lower() or "wal" in result.output.lower()


def test_all_main_commands_have_help():
    """Test that all main commands have help descriptions."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0

    # Commands that should have help descriptions
    commands_with_help = [
        "analyze",
        "build",
        "config",
        "export",
        "login",
        "match",
        "diagnose",  # Changed from 'match-diagnose' to match actual command name
        "pull",
        "redirect-uri",
        "report",
        "scan",
        "token-info",
    ]

    # Find the Commands section to avoid matching options or other text
    lines = result.output.split("\n")
    commands_start = None
    for i, line in enumerate(lines):
        if line.strip() == "Commands:":
            commands_start = i
            break

    assert commands_start is not None, "Commands section not found in help output"

    # Only look at lines after the Commands: header
    command_lines_section = lines[commands_start + 1 :]

    for command in commands_with_help:
        # Each command should appear with a description
        assert command in result.output
        # Look for the command in the Commands section only
        command_lines = [line for line in command_lines_section if line.strip().startswith(command + " ")]
        assert len(command_lines) > 0, f"Command {command} not found in Commands section"

        # The command line should have description text after spaces
        command_line = command_lines[0]
        parts = command_line.split(maxsplit=1)
        assert len(parts) == 2, f"Command {command} appears to have no description"
        assert len(parts[1].strip()) > 5, f"Command {command} has very short description: {parts[1]}"


def test_playlist_subcommands_have_help():
    """Test that playlist subcommands have help descriptions."""
    runner = CliRunner()
    result = runner.invoke(cli, ["playlist", "--help"])

    assert result.exit_code == 0

    # Check main playlist group has description
    assert "Single playlist operations" in result.output

    # Commands that should have help descriptions
    playlist_commands = ["build", "export", "match", "pull", "push"]

    for command in playlist_commands:
        assert command in result.output
        # Look for the command in the Commands section
        lines = result.output.split("\n")
        command_lines = [line for line in lines if line.strip().startswith(command)]
        assert len(command_lines) > 0, f"Playlist command {command} not found in help output"

        # The command line should have description text
        command_line = command_lines[0]
        parts = command_line.split(maxsplit=1)
        assert len(parts) == 2, f"Playlist command {command} appears to have no description"
        assert len(parts[1].strip()) > 5, f"Playlist command {command} has very short description: {parts[1]}"


def test_help_formatting_is_readable():
    """Test that help output is well-formatted and readable."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0

    # Check basic structure
    assert "Usage:" in result.output
    assert "Options:" in result.output
    assert "Commands:" in result.output

    # Should not have very long lines that would be hard to read
    lines = result.output.split("\n")
    for line in lines:
        # Allow some flexibility for long URLs or paths in examples
        if len(line) > 120:
            # If it's very long, it should be in the workflow examples section
            # where longer lines are more acceptable
            assert any(
                marker in result.output[: result.output.find(line)]
                for marker in ["TYPICAL WORKFLOWS:", "Initial Setup:", "Full Sync", "Single Playlist"]
            )

    # Check that there's reasonable spacing
    assert "\n\n" in result.output  # Should have some blank lines for readability


def test_command_help_consistency():
    """Test that individual commands have consistent help format."""
    runner = CliRunner()

    # Test a few key commands have individual help
    commands_to_test = ["scan", "pull", "match", "export"]

    for command in commands_to_test:
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert command in result.output

        # Should have description or docstring
        lines = result.output.split("\n")
        # Look for description content (not just Usage/Options/etc)
        has_description = any(
            line.strip() and not line.strip().startswith(("Usage:", "Options:", "--", "Show this message"))
            for line in lines[1:6]  # Check first few lines after Usage
        )
        assert has_description, f"Command {command} seems to lack a description in its help"
