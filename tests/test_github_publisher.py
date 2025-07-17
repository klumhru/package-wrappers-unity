"""Test GitHub publisher functionality with npm CLI."""

import os
import pytest
from unittest.mock import patch, MagicMock
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
