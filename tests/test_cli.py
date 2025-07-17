"""Test CLI functionality."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from unity_wrapper.cli import cli


def test_cli_help() -> None:
    """Test CLI help command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "Unity Package Wrapper" in result.output


def test_cli_build_help() -> None:
    """Test build command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["build", "--help"])

    assert result.exit_code == 0
    assert "Build Unity packages" in result.output


def test_cli_publish_help() -> None:
    """Test publish command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["publish", "--help"])

    assert result.exit_code == 0
    assert "Publish packages to GitHub Package Registry" in result.output
    assert "Node.js and npm" in result.output


def test_cli_list_packages_help() -> None:
    """Test list-packages command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list-packages", "--help"])

    assert result.exit_code == 0
    assert "List all configured packages" in result.output


def test_cli_watch_help() -> None:
    """Test watch command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["watch", "--help"])

    assert result.exit_code == 0
    assert "Watch for configuration changes" in result.output


def test_cli_check_help() -> None:
    """Test check command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--help"])

    assert result.exit_code == 0
    assert "Check which packages need updates" in result.output


def test_cli_add_help() -> None:
    """Test add command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["add", "--help"])

    assert result.exit_code == 0
    assert "Add a new package configuration" in result.output


def test_cli_remove_help() -> None:
    """Test remove command help."""
    runner = CliRunner()
    result = runner.invoke(cli, ["remove", "--help"])

    assert result.exit_code == 0
    assert "Remove a package configuration" in result.output


@patch("unity_wrapper.cli.PackageBuilder")
def test_build_command_success(mock_package_builder: MagicMock) -> None:
    """Test successful build command."""
    # Mock PackageBuilder context manager
    mock_builder = MagicMock()
    mock_package_builder.return_value.__enter__.return_value = mock_builder
    mock_builder.build_all_packages.return_value = [
        "/path/to/package1",
        "/path/to/package2",
    ]

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["build"])

    assert result.exit_code == 0
    assert "Building all packages" in result.output
    assert "Successfully built 2 packages" in result.output


@patch("unity_wrapper.cli.PackageBuilder")
def test_build_command_specific_package(
    mock_package_builder: MagicMock,
) -> None:
    """Test building a specific package."""
    mock_builder = MagicMock()
    mock_package_builder.return_value.__enter__.return_value = mock_builder
    mock_builder.build_package.return_value = "/path/to/package"

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["build", "test-package"])

    assert result.exit_code == 0
    assert "Building package: test-package" in result.output
    assert "Package built successfully" in result.output


@patch("unity_wrapper.cli.ConfigManager")
def test_list_packages_command(mock_config_manager: MagicMock) -> None:
    """Test list-packages command."""
    mock_manager = MagicMock()
    mock_config_manager.return_value = mock_manager
    mock_manager.get_all_package_names.return_value = ["package1", "package2"]
    mock_manager.get_package_type.side_effect = ["git", "nuget"]
    mock_manager.get_package_config.return_value = {
        "source": {"url": "https://github.com/test/repo.git", "ref": "main"}
    }
    mock_manager.get_nuget_package_config.return_value = {
        "nuget_id": "TestPackage",
        "version": "1.0.0",
        "framework": "netstandard2.0",
    }

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["list-packages"])

    assert result.exit_code == 0
    assert "Configured packages (2)" in result.output


@patch("unity_wrapper.cli.ConfigManager")
def test_list_packages_command_empty(mock_config_manager: MagicMock) -> None:
    """Test list-packages command with no packages."""
    mock_manager = MagicMock()
    mock_config_manager.return_value = mock_manager
    mock_manager.get_all_package_names.return_value = []

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["list-packages"])

    assert result.exit_code == 0
    assert "No packages configured" in result.output


@patch("unity_wrapper.cli.PackageBuilder")
def test_check_command(mock_package_builder: MagicMock) -> None:
    """Test check command."""
    mock_builder = MagicMock()
    mock_package_builder.return_value.__enter__.return_value = mock_builder
    mock_builder.check_for_updates.return_value = ["package1", "package2"]

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["check"])

    assert result.exit_code == 0
    assert "Packages needing updates (2)" in result.output


@patch("unity_wrapper.cli.PackageBuilder")
def test_check_command_no_updates(mock_package_builder: MagicMock) -> None:
    """Test check command with no updates needed."""
    mock_builder = MagicMock()
    mock_package_builder.return_value.__enter__.return_value = mock_builder
    mock_builder.check_for_updates.return_value = []

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["check"])

    assert result.exit_code == 0
    assert "All packages are up to date" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
