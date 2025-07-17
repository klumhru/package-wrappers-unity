"""Test GitHub publisher functionality with npm CLI."""

import os
import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from unity_wrapper.utils.github_publisher import GitHubPublisher


def test_github_publisher_uses_provided_token() -> None:
    """Test that GitHubPublisher uses the provided token."""
    with patch("subprocess.run") as mock_run:
        # Mock npm --version check
        mock_run.return_value.stdout = "10.0.0"
        mock_run.return_value.returncode = 0

        publisher = GitHubPublisher(token="test-token", owner="testowner")

        assert publisher.token == "test-token"


def test_github_publisher_uses_environment_token() -> None:
    """Test that GitHubPublisher falls back to environment token."""
    with patch("subprocess.run") as mock_run:
        # Mock npm --version check
        mock_run.return_value.stdout = "10.0.0"
        mock_run.return_value.returncode = 0

        with patch.dict(os.environ, {"GITHUB_TOKEN": "env-token"}):
            publisher = GitHubPublisher(owner="testowner")

            assert publisher.token == "env-token"


def test_github_publisher_prefers_provided_token() -> None:
    """Test that GitHubPublisher prefers provided token over environment."""
    with patch("subprocess.run") as mock_run:
        # Mock npm --version check
        mock_run.return_value.stdout = "10.0.0"
        mock_run.return_value.returncode = 0

        with patch.dict(os.environ, {"GITHUB_TOKEN": "env-token"}):
            publisher = GitHubPublisher(
                token="provided-token", owner="testowner"
            )

            assert publisher.token == "provided-token"


def test_github_publisher_raises_error_when_no_token() -> None:
    """Test that GitHubPublisher raises error when no token is available."""
    with patch("subprocess.run") as mock_run:
        # Mock npm --version check
        mock_run.return_value.stdout = "10.0.0"
        mock_run.return_value.returncode = 0

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GitHub token is required"):
                GitHubPublisher(owner="testowner")


def test_github_publisher_ignores_empty_token() -> None:
    """Test that GitHubPublisher ignores empty token and uses environment."""
    with patch("subprocess.run") as mock_run:
        # Mock npm --version check
        mock_run.return_value.stdout = "10.0.0"
        mock_run.return_value.returncode = 0

        with patch.dict(os.environ, {"GITHUB_TOKEN": "env-token"}):
            publisher = GitHubPublisher(token="", owner="testowner")

            assert publisher.token == "env-token"


def test_github_publisher_requires_owner() -> None:
    """Test that GitHubPublisher requires owner for initialization."""
    with patch("subprocess.run") as mock_run:
        # Mock npm --version check
        mock_run.return_value.stdout = "10.0.0"
        mock_run.return_value.returncode = 0

        with pytest.raises(
            ValueError, match="Owner is required for GitHub Package Registry"
        ):
            GitHubPublisher(token="test-token")


def test_github_publisher_requires_npm() -> None:
    """Test that GitHubPublisher raises error when npm is not available."""
    with patch("subprocess.run") as mock_run:
        # Mock npm command not found
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(RuntimeError, match="npm command not found"):
            GitHubPublisher(token="test-token", owner="testowner")


def test_github_publisher_check_package_exists() -> None:
    """Test check_package_exists functionality."""
    with patch("subprocess.run") as mock_run:
        # First call: npm --version check (success)
        # Second call: npm view package@version (success)
        mock_run.side_effect = [
            MagicMock(stdout="10.0.0", returncode=0),  # npm version check
            MagicMock(returncode=0),  # npm view success
        ]

        publisher = GitHubPublisher(token="test-token", owner="testowner")
        result = publisher.check_package_exists("test-package", "1.0.0")

        assert result is True

        # Verify npm view was called with correct parameters
        assert mock_run.call_count == 2

        # Check first call (npm version)
        first_call_args = mock_run.call_args_list[0][0][0]
        assert first_call_args == ["npm", "--version"]

        # Check second call (npm view)
        second_call_args = mock_run.call_args_list[1][0][0]
        assert second_call_args == [
            "npm",
            "view",
            "@testowner/test-package@1.0.0",
            "version",
        ]


def test_github_publisher_check_package_not_exists() -> None:
    """Test check_package_exists when package doesn't exist."""
    with patch("subprocess.run") as mock_run:
        # First call: npm --version check (success)
        # Second call: npm view package@version (failure)
        mock_run.side_effect = [
            MagicMock(stdout="10.0.0", returncode=0),  # npm version check
            MagicMock(returncode=1),  # npm view failure (package not found)
        ]

        publisher = GitHubPublisher(token="test-token", owner="testowner")
        result = publisher.check_package_exists("test-package", "1.0.0")

        assert result is False


def test_github_publisher_get_package_info() -> None:
    """Test get_package_info functionality."""
    with patch("subprocess.run") as mock_run:
        package_info = {"name": "@testowner/test-package", "version": "1.0.0"}

        # First call: npm --version check (success)
        # Second call: npm view package --json (success)
        mock_run.side_effect = [
            MagicMock(stdout="10.0.0", returncode=0),  # npm version check
            MagicMock(
                stdout='{"name": "@testowner/test-package", '
                '"version": "1.0.0"}',
                returncode=0,
            ),  # npm view success
        ]

        publisher = GitHubPublisher(token="test-token", owner="testowner")
        result = publisher.get_package_info("test-package")

        assert result == package_info


def test_github_publisher_get_package_info_not_found() -> None:
    """Test get_package_info when package doesn't exist."""
    with patch("subprocess.run") as mock_run:
        # First call: npm --version check (success)
        # Second call: npm view package --json (failure)
        mock_run.side_effect = [
            MagicMock(stdout="10.0.0", returncode=0),  # npm version check
            MagicMock(returncode=1),  # npm view failure (package not found)
        ]

        publisher = GitHubPublisher(token="test-token", owner="testowner")
        result = publisher.get_package_info("test-package")

        assert result is None


def test_github_publisher_publish_package_success() -> None:
    """Test successful package publishing."""
    with patch("subprocess.run") as mock_run, \
         patch("tempfile.TemporaryDirectory") as mock_temp_dir, \
         patch("pathlib.Path.exists") as mock_exists, \
         patch("builtins.open", mock_open(read_data='{"name": "test-package", "version": "1.0.0"}')):

        # Mock npm version check
        mock_run.side_effect = [
            MagicMock(stdout="10.0.0", returncode=0),  # npm version check
            MagicMock(stdout="", returncode=0),  # npm publish success
        ]

        # Mock temporary directory context manager
        mock_temp_dir.return_value.__enter__.return_value = "/tmp/test"
        mock_exists.return_value = True

        publisher = GitHubPublisher(token="test-token", owner="testowner")

        # Mock package directory
        package_dir = Path("/fake/package")

        with patch.object(publisher, '_copy_package'), \
             patch.object(publisher, '_update_package_json_for_github'), \
             patch.object(publisher, '_configure_npm'):

            # Should not raise any exception
            publisher.publish_package(package_dir)


def test_github_publisher_publish_package_missing_json() -> None:
    """Test publishing when package.json is missing."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "10.0.0"
        mock_run.return_value.returncode = 0

        publisher = GitHubPublisher(token="test-token", owner="testowner")

        # Mock non-existent package.json
        package_dir = Path("/fake/package")

        with pytest.raises(FileNotFoundError, match="package.json not found"):
            publisher.publish_package(package_dir)


def test_github_publisher_publish_package_auth_error() -> None:
    """Test publishing with authentication error."""
    with patch("subprocess.run") as mock_run, \
         patch("tempfile.TemporaryDirectory") as mock_temp_dir, \
         patch("pathlib.Path.exists") as mock_exists, \
         patch("builtins.open", mock_open(read_data='{"name": "test-package", "version": "1.0.0"}')):

        # Mock npm version check success, publish auth failure
        auth_error = subprocess.CalledProcessError(1, "npm", stderr="ENEEDAUTH: need auth")
        mock_run.side_effect = [
            MagicMock(stdout="10.0.0", returncode=0),  # npm version check
            auth_error,  # npm publish auth error
        ]

        mock_temp_dir.return_value.__enter__.return_value = "/tmp/test"
        mock_exists.return_value = True

        publisher = GitHubPublisher(token="test-token", owner="testowner")
        package_dir = Path("/fake/package")

        with patch.object(publisher, '_copy_package'), \
             patch.object(publisher, '_update_package_json_for_github'), \
             patch.object(publisher, '_configure_npm'):

            with pytest.raises(RuntimeError, match="Authentication required"):
                publisher.publish_package(package_dir)


def test_github_publisher_configure_npm() -> None:
    """Test npm configuration with .npmrc file."""
    with patch("subprocess.run") as mock_run, \
         patch("builtins.open", mock_open()) as mock_file:

        mock_run.return_value.stdout = "10.0.0"
        mock_run.return_value.returncode = 0

        publisher = GitHubPublisher(token="test-token", owner="testowner")
        working_dir = Path("/tmp/test")

        publisher._configure_npm(working_dir)

        # Verify .npmrc content was written
        mock_file.assert_called()
        written_content = "".join(call.args[0] for call in mock_file().write.call_args_list)
        assert "//npm.pkg.github.com/:_authToken=test-token" in written_content
        assert "@testowner:registry=https://npm.pkg.github.com" in written_content


def test_github_publisher_update_package_json() -> None:
    """Test package.json update for GitHub scoping."""
    original_package_json = '{"name": "test-package", "version": "1.0.0"}'

    with patch("subprocess.run") as mock_run, \
         patch("builtins.open", mock_open(read_data=original_package_json)) as mock_file:

        mock_run.return_value.stdout = "10.0.0"
        mock_run.return_value.returncode = 0

        publisher = GitHubPublisher(token="test-token", owner="testowner")
        package_json_path = Path("/fake/package.json")

        publisher._update_package_json_for_github(package_json_path)

        # Verify the file was read and written
        mock_file.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
