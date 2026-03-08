"""Tests for PackagePublisher."""

import json
import logging
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from unity_wrapper.utils.package_publisher import PackagePublisher


def _make_publisher(
    registry: str = "github",
    owner: str = "testowner",
    token: str = "tok",
) -> PackagePublisher:
    """Helper to create a PackagePublisher with npm mocked out."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="10.0.0", returncode=0)
        return PackagePublisher(registry=registry, token=token, owner=owner)


class TestGetRepoFromEnv:
    def test_returns_repo_part_from_github_repository(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="10.0.0", returncode=0)
            with patch.dict(
                os.environ,
                {"GITHUB_REPOSITORY": "owner/my-repo", "GITHUB_TOKEN": "t"},
                clear=True,
            ):
                pub = PackagePublisher(registry="github")
                assert pub.repo == "my-repo"

    def test_returns_none_when_env_not_set(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="10.0.0", returncode=0)
            with patch.dict(os.environ, {}, clear=True):
                pub = PackagePublisher(
                    registry="openupm", token=None, owner=None
                )
                assert pub.repo is None

    def test_handles_repo_name_with_dots(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="10.0.0", returncode=0)
            with patch.dict(
                os.environ,
                {
                    "GITHUB_REPOSITORY": "owner/pkg.package-wrappers-unity",
                    "GITHUB_TOKEN": "t",
                },
                clear=True,
            ):
                pub = PackagePublisher(registry="github")
                assert pub.repo == "pkg.package-wrappers-unity"


class TestComputeScopedName:
    def test_github_adds_owner_scope(self) -> None:
        pub = _make_publisher(registry="github")
        assert (
            pub._compute_scoped_name("com.foo.bar") == "@testowner/com.foo.bar"
        )

    def test_npmjs_adds_owner_scope(self) -> None:
        pub = _make_publisher(registry="npmjs")
        assert (
            pub._compute_scoped_name("com.foo.bar") == "@testowner/com.foo.bar"
        )

    def test_openupm_no_scope(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="10.0.0", returncode=0)
            pub = PackagePublisher(
                registry="openupm", token=None, owner="testowner"
            )
        assert pub._compute_scoped_name("com.foo.bar") == "com.foo.bar"

    def test_already_scoped_name_unchanged(self) -> None:
        pub = _make_publisher(registry="github")
        assert (
            pub._compute_scoped_name("@testowner/com.foo.bar")
            == "@testowner/com.foo.bar"
        )

    def test_no_owner_returns_name_unchanged(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="10.0.0", returncode=0)
            with patch.dict(os.environ, {}, clear=True):
                pub = PackagePublisher(
                    registry="openupm", token=None, owner=None
                )
        assert pub._compute_scoped_name("com.foo.bar") == "com.foo.bar"


class TestPackageBrowseUrl:
    def test_github_with_owner_and_repo(self) -> None:
        pub = _make_publisher(registry="github")
        pub.repo = "my-wrappers"
        url = pub._package_browse_url(
            "@testowner/com.foo.bar", "com.foo.bar", "1.0.0"
        )
        assert url == (
            "https://github.com/testowner/my-wrappers/pkgs/npm/com.foo.bar"
        )

    def test_github_without_repo_falls_back_to_packages_tab(self) -> None:
        pub = _make_publisher(registry="github")
        pub.repo = None
        url = pub._package_browse_url(
            "@testowner/com.foo.bar", "com.foo.bar", "1.0.0"
        )
        assert url == "https://github.com/testowner?tab=packages"

    def test_github_without_owner_returns_github_root(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="10.0.0", returncode=0)
            with patch.dict(os.environ, {}, clear=True):
                pub = PackagePublisher(
                    registry="openupm", token=None, owner=None
                )
        pub.registry = "github"
        pub.owner = None
        pub.repo = None
        url = pub._package_browse_url("com.foo.bar", "com.foo.bar", "1.0.0")
        assert url == "https://github.com"

    def test_npmjs_url_includes_version(self) -> None:
        pub = _make_publisher(registry="npmjs")
        url = pub._package_browse_url(
            "@testowner/com.foo.bar", "com.foo.bar", "2.3.4"
        )
        assert url == (
            "https://www.npmjs.com/package/@testowner/com.foo.bar/v/2.3.4"
        )

    def test_openupm_url_uses_original_name(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="10.0.0", returncode=0)
            pub = PackagePublisher(
                registry="openupm", token=None, owner="testowner"
            )
        url = pub._package_browse_url("com.foo.bar", "com.foo.bar", "1.0.0")
        assert url == "https://openupm.com/packages/com.foo.bar/"


class TestIsPublishConflict:
    def _err(self, stderr: str) -> subprocess.CalledProcessError:
        return subprocess.CalledProcessError(1, "npm", stderr=stderr)

    def test_detects_e409(self) -> None:
        pub = _make_publisher()
        assert pub._is_publish_conflict(self._err("npm ERR! code E409"))

    def test_detects_409_conflict(self) -> None:
        pub = _make_publisher()
        assert pub._is_publish_conflict(self._err("409 Conflict - PUT"))

    def test_detects_already_exists(self) -> None:
        pub = _make_publisher()
        assert pub._is_publish_conflict(self._err("version already exists"))

    def test_detects_cannot_publish_over(self) -> None:
        pub = _make_publisher()
        assert pub._is_publish_conflict(
            self._err("cannot publish over the previously published versions")
        )

    def test_detects_epublishconflict(self) -> None:
        pub = _make_publisher()
        assert pub._is_publish_conflict(self._err("EPUBLISHCONFLICT"))

    def test_non_conflict_error_returns_false(self) -> None:
        pub = _make_publisher()
        assert not pub._is_publish_conflict(
            self._err("ENEEDAUTH need auth npm ERR!")
        )

    def test_none_stderr_does_not_raise(self) -> None:
        pub = _make_publisher()
        err = subprocess.CalledProcessError(1, "npm")
        err.stderr = None
        assert not pub._is_publish_conflict(err)


class TestPublishPackage:
    _PKG_JSON = json.dumps({"name": "com.foo.bar", "version": "1.2.3"})

    def _publisher_with_repo(self) -> PackagePublisher:
        pub = _make_publisher(registry="github")
        pub.repo = "my-wrappers"
        return pub

    def test_success_logs_url(
        self,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
    ) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "package.json").write_text(self._PKG_JSON)

        pub = self._publisher_with_repo()

        with (
            patch.object(pub, "_copy_package"),
            patch.object(pub, "_update_package_json"),
            patch.object(pub, "_configure_npm"),
            patch.object(pub, "_npm_publish"),
        ):
            with caplog.at_level(logging.INFO):
                pub.publish_package(pkg_dir)

        assert "View at:" in caplog.text
        assert "/pkgs/npm/com.foo.bar" in caplog.text

    def test_conflict_logs_warning_not_error(
        self,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
    ) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "package.json").write_text(self._PKG_JSON)

        pub = self._publisher_with_repo()
        conflict = subprocess.CalledProcessError(
            1, "npm", stderr="npm ERR! code E409"
        )

        with (
            patch.object(pub, "_copy_package"),
            patch.object(pub, "_update_package_json"),
            patch.object(pub, "_configure_npm"),
            patch.object(pub, "_npm_publish", side_effect=conflict),
        ):
            with caplog.at_level(logging.WARNING):
                pub.publish_package(pkg_dir)  # must not raise

        assert any(
            record.levelno == logging.WARNING
            and "version conflict" in record.getMessage()
            for record in caplog.records
        ), "Expected a WARNING record mentioning 'version conflict'"
        assert not any(
            record.levelno >= logging.ERROR for record in caplog.records
        ), "Expected no ERROR records for a version conflict"
        assert "View at:" in caplog.text

    def test_conflict_does_not_raise(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "package.json").write_text(self._PKG_JSON)

        pub = self._publisher_with_repo()
        conflict = subprocess.CalledProcessError(
            1, "npm", stderr="E409 conflict"
        )

        with (
            patch.object(pub, "_copy_package"),
            patch.object(pub, "_update_package_json"),
            patch.object(pub, "_configure_npm"),
            patch.object(pub, "_npm_publish", side_effect=conflict),
        ):
            pub.publish_package(pkg_dir)  # should not raise

    def test_non_conflict_error_raises(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "package.json").write_text(self._PKG_JSON)

        pub = self._publisher_with_repo()
        auth_err = subprocess.CalledProcessError(
            1, "npm", stderr="ENEEDAUTH need auth"
        )

        with (
            patch.object(pub, "_copy_package"),
            patch.object(pub, "_update_package_json"),
            patch.object(pub, "_configure_npm"),
            patch.object(pub, "_npm_publish", side_effect=auth_err),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                pub.publish_package(pkg_dir)

    def test_missing_package_json_raises(self, tmp_path: Path) -> None:
        pub = self._publisher_with_repo()
        with pytest.raises(FileNotFoundError, match="package.json not found"):
            pub.publish_package(tmp_path / "nonexistent")
