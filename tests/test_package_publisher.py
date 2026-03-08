"""Tests for PackagePublisher."""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any
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
            patch.object(pub, "_github_publish_direct"),
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

        # GitHub path raises _PublishConflict from _github_publish_direct
        from unity_wrapper.utils.package_publisher import _PublishConflict

        with (
            patch.object(pub, "_copy_package"),
            patch.object(pub, "_update_package_json"),
            patch.object(
                pub,
                "_github_publish_direct",
                side_effect=_PublishConflict("pkg"),
            ),
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
        from unity_wrapper.utils.package_publisher import _PublishConflict

        with (
            patch.object(pub, "_copy_package"),
            patch.object(pub, "_update_package_json"),
            patch.object(
                pub,
                "_github_publish_direct",
                side_effect=_PublishConflict("pkg"),
            ),
        ):
            pub.publish_package(pkg_dir)  # should not raise

    def test_non_conflict_error_raises(self, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "package.json").write_text(self._PKG_JSON)

        pub = self._publisher_with_repo()
        import requests as req

        with (
            patch.object(pub, "_copy_package"),
            patch.object(pub, "_update_package_json"),
            patch.object(
                pub,
                "_github_publish_direct",
                side_effect=req.HTTPError(response=MagicMock(status_code=401)),
            ),
        ):
            with pytest.raises(req.HTTPError):
                pub.publish_package(pkg_dir)

    def test_missing_package_json_raises(self, tmp_path: Path) -> None:
        pub = self._publisher_with_repo()
        with pytest.raises(FileNotFoundError, match="package.json not found"):
            pub.publish_package(tmp_path / "nonexistent")


class TestUpdatePackageJson:
    """Verify _update_package_json UPM-compatible name handling."""

    def _write_pkg(self, path: Path, name: str = "com.foo.bar") -> None:
        (path / "package.json").write_text(
            json.dumps({"name": name, "version": "1.0.0"})
        )

    def _read_pkg(self, path: Path) -> dict[str, Any]:
        result: dict[str, Any] = json.loads(
            (path / "package.json").read_text()
        )
        return result

    def test_github_keeps_unscoped_name(self, tmp_path: Path) -> None:
        """GitHub registry must NOT scope the name so UPM can resolve it."""
        self._write_pkg(tmp_path)
        pub = _make_publisher(registry="github", owner="myorg")
        pub._update_package_json(tmp_path / "package.json")
        pkg = self._read_pkg(tmp_path)
        assert pkg["name"] == "com.foo.bar"

    def test_github_adds_repository_field(self, tmp_path: Path) -> None:
        self._write_pkg(tmp_path)
        pub = _make_publisher(registry="github", owner="myorg")
        pub._update_package_json(tmp_path / "package.json")
        pkg = self._read_pkg(tmp_path)
        assert pkg["repository"]["type"] == "git"
        assert "myorg" in pkg["repository"]["url"]

    def test_github_uses_actual_repo_when_available(
        self, tmp_path: Path
    ) -> None:
        """When GITHUB_REPOSITORY is set, repository.url points to it."""
        self._write_pkg(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="10.0.0", returncode=0)
            with patch.dict(
                os.environ,
                {"GITHUB_REPOSITORY": "myorg/package-wrappers-unity"},
                clear=False,
            ):
                pub = PackagePublisher(
                    registry="github", token="tok", owner="myorg"
                )
        pub._update_package_json(tmp_path / "package.json")
        pkg = self._read_pkg(tmp_path)
        assert (
            pkg["repository"]["url"]
            == "https://github.com/myorg/package-wrappers-unity.git"
        )

    def test_github_no_publish_config(self, tmp_path: Path) -> None:
        """publishConfig is not needed: we PUT directly with the scoped URL."""
        self._write_pkg(tmp_path)
        pub = _make_publisher(registry="github", owner="myorg")
        pub._update_package_json(tmp_path / "package.json")
        pkg = self._read_pkg(tmp_path)
        assert "publishConfig" not in pkg

    def test_npmjs_scopes_name(self, tmp_path: Path) -> None:
        """npmjs registry MUST scope the name."""
        self._write_pkg(tmp_path)
        pub = _make_publisher(registry="npmjs", owner="myorg")
        pub._update_package_json(tmp_path / "package.json")
        pkg = self._read_pkg(tmp_path)
        assert pkg["name"] == "@myorg/com.foo.bar"

    def test_npmjs_no_publish_config(self, tmp_path: Path) -> None:
        self._write_pkg(tmp_path)
        pub = _make_publisher(registry="npmjs", owner="myorg")
        pub._update_package_json(tmp_path / "package.json")
        pkg = self._read_pkg(tmp_path)
        assert "publishConfig" not in pkg


class TestPublishPackageUpmNames:
    """Verify publish_package logs the scoped name for all registries."""

    _PKG_JSON = json.dumps({"name": "com.foo.bar", "version": "1.0.0"})

    def test_github_logs_scoped_name(
        self,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
    ) -> None:
        """GitHub uses direct HTTP publish; name is scoped in the registry."""
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "package.json").write_text(self._PKG_JSON)

        pub = _make_publisher(registry="github")
        pub.repo = "my-wrappers"

        with (
            patch.object(pub, "_copy_package"),
            patch.object(pub, "_update_package_json"),
            patch.object(pub, "_github_publish_direct"),
        ):
            with caplog.at_level(logging.INFO):
                pub.publish_package(pkg_dir)

        assert "@testowner/com.foo.bar@1.0.0" in caplog.text

    def test_npmjs_logs_scoped_name(
        self,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
    ) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "package.json").write_text(self._PKG_JSON)

        pub = _make_publisher(registry="npmjs")

        with (
            patch.object(pub, "_copy_package"),
            patch.object(pub, "_update_package_json"),
            patch.object(pub, "_configure_npm"),
            patch.object(pub, "_npm_publish"),
        ):
            with caplog.at_level(logging.INFO):
                pub.publish_package(pkg_dir)

        assert "@testowner/com.foo.bar@1.0.0" in caplog.text


class TestCheckPackageExistsUpmNames:
    """check_package_exists always uses the scoped name."""

    def test_github_uses_scoped_name(self) -> None:
        """GitHub packages are stored under @owner/name in the registry."""
        pub = _make_publisher(registry="github", owner="myorg")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1.0.0")
            pub.check_package_exists("com.foo.bar", "1.0.0")
            call_args = " ".join(mock_run.call_args[0][0])

        assert "@myorg/com.foo.bar" in call_args

    def test_npmjs_uses_scoped_name(self) -> None:
        pub = _make_publisher(registry="npmjs", owner="myorg")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1.0.0")
            pub.check_package_exists("com.foo.bar", "1.0.0")
            call_args = " ".join(mock_run.call_args[0][0])

        assert "@myorg/com.foo.bar" in call_args


class TestNpmPublishScope:
    """_npm_publish does not pass --scope (GitHub uses direct HTTP now)."""

    def test_npmjs_omits_scope_flag(self) -> None:
        pub = _make_publisher(registry="npmjs", owner="myorg")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            pub._npm_publish(Path("/tmp/pkg"))
            cmd = mock_run.call_args[0][0]
        assert not any(a.startswith("--scope") for a in cmd)

    def test_npmjs_uses_npm_publish_command(self) -> None:
        pub = _make_publisher(registry="npmjs", owner="myorg")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            pub._npm_publish(Path("/tmp/pkg"))
            cmd = mock_run.call_args[0][0]
        assert cmd[:2] == ["npm", "publish"]


class TestGithubPublishDirect:
    """_github_publish_direct sends a scoped PUT to GitHub Packages."""

    _PKG_JSON = json.dumps({"name": "com.foo.bar", "version": "1.0.0"})

    def _setup_pkg(self, path: Path) -> None:
        (path / "package.json").write_text(self._PKG_JSON)

    @patch("unity_wrapper.utils.package_publisher.http_requests.put")
    def test_puts_to_scoped_url(
        self, mock_put: MagicMock, tmp_path: Path
    ) -> None:
        self._setup_pkg(tmp_path)
        pub = _make_publisher(registry="github", owner="myorg")
        mock_put.return_value = MagicMock(status_code=200)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="com.foo.bar-1.0.0.tgz\n",
                stderr="",
            )
            with patch("pathlib.Path.read_bytes", return_value=b"x"):
                pub._github_publish_direct(tmp_path)

        called_url = mock_put.call_args[0][0]
        assert called_url == ("https://npm.pkg.github.com/@myorg/com.foo.bar")

    @patch("unity_wrapper.utils.package_publisher.http_requests.put")
    def test_packument_body_has_scoped_name(
        self, mock_put: MagicMock, tmp_path: Path
    ) -> None:
        self._setup_pkg(tmp_path)
        pub = _make_publisher(registry="github", owner="myorg")
        mock_put.return_value = MagicMock(status_code=200)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="com.foo.bar-1.0.0.tgz\n",
                stderr="",
            )
            with patch("pathlib.Path.read_bytes", return_value=b"x"):
                pub._github_publish_direct(tmp_path)

        body = mock_put.call_args[1]["json"]
        assert body["name"] == "@myorg/com.foo.bar"
        assert body["versions"]["1.0.0"]["name"] == "@myorg/com.foo.bar"
        # Attachment key must be scoped name + version for GitHub routing
        assert "@myorg/com.foo.bar-1.0.0.tgz" in body["_attachments"]

    @patch("unity_wrapper.utils.package_publisher.http_requests.put")
    def test_conflict_raises_publish_conflict(
        self, mock_put: MagicMock, tmp_path: Path
    ) -> None:
        from unity_wrapper.utils.package_publisher import _PublishConflict

        self._setup_pkg(tmp_path)
        pub = _make_publisher(registry="github", owner="myorg")
        mock_put.return_value = MagicMock(status_code=409)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="com.foo.bar-1.0.0.tgz\n",
                stderr="",
            )
            with patch("pathlib.Path.read_bytes", return_value=b"x"):
                with pytest.raises(_PublishConflict):
                    pub._github_publish_direct(tmp_path)

    @patch("unity_wrapper.utils.package_publisher.http_requests.put")
    def test_pages_publisher_called_on_success(
        self, mock_put: MagicMock, tmp_path: Path
    ) -> None:
        """PagesPublisher.update_registry is called after a successful PUT."""
        self._setup_pkg(tmp_path)
        pub = _make_publisher(registry="github", owner="myorg")
        mock_put.return_value = MagicMock(status_code=200)
        registry_dir = tmp_path / "registry"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="com.foo.bar-1.0.0.tgz\n",
                stderr="",
            )
            with patch("pathlib.Path.read_bytes", return_value=b"x"):
                with patch(
                    "unity_wrapper.utils.package_publisher"
                    ".PagesPublisher.update_registry"
                ) as mock_pages:
                    pub._github_publish_direct(
                        tmp_path, registry_dir=registry_dir
                    )

        mock_pages.assert_called_once()
        call_kwargs = mock_pages.call_args[1]
        assert call_kwargs["unscoped_name"] == "com.foo.bar"
        assert call_kwargs["version"] == "1.0.0"
        assert call_kwargs["registry_dir"] == registry_dir

    @patch("unity_wrapper.utils.package_publisher.http_requests.put")
    def test_pages_publisher_passes_tarball_data(
        self, mock_put: MagicMock, tmp_path: Path
    ) -> None:
        """tarball_data bytes are forwarded to PagesPublisher."""
        self._setup_pkg(tmp_path)
        pub = _make_publisher(registry="github", owner="myorg")
        mock_put.return_value = MagicMock(status_code=200)
        registry_dir = tmp_path / "registry"
        tarball_bytes = b"fake-tarball-content"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="com.foo.bar-1.0.0.tgz\n",
                stderr="",
            )
            with patch("pathlib.Path.read_bytes", return_value=tarball_bytes):
                with patch(
                    "unity_wrapper.utils.package_publisher"
                    ".PagesPublisher.update_registry"
                ) as mock_pages:
                    pub._github_publish_direct(
                        tmp_path, registry_dir=registry_dir
                    )

        call_kwargs = mock_pages.call_args[1]
        assert call_kwargs["tarball_data"] == tarball_bytes

    @patch("unity_wrapper.utils.package_publisher.http_requests.put")
    def test_pages_uses_pages_base_url_from_env(
        self, mock_put: MagicMock, tmp_path: Path
    ) -> None:
        """PAGES_BASE_URL env var is forwarded to PagesPublisher."""
        self._setup_pkg(tmp_path)
        pub = _make_publisher(registry="github", owner="myorg")
        mock_put.return_value = MagicMock(status_code=200)
        registry_dir = tmp_path / "registry"

        with patch.dict(
            os.environ,
            {"PAGES_BASE_URL": "https://myorg.github.io/my-repo"},
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="com.foo.bar-1.0.0.tgz\n",
                    stderr="",
                )
                with patch("pathlib.Path.read_bytes", return_value=b"x"):
                    with patch(
                        "unity_wrapper.utils.package_publisher"
                        ".PagesPublisher.update_registry"
                    ) as mock_pages:
                        pub._github_publish_direct(
                            tmp_path, registry_dir=registry_dir
                        )

        call_kwargs = mock_pages.call_args[1]
        assert call_kwargs["pages_base_url"] == (
            "https://myorg.github.io/my-repo"
        )

    @patch("unity_wrapper.utils.package_publisher.http_requests.put")
    def test_pages_publisher_skipped_when_no_registry_dir(
        self, mock_put: MagicMock, tmp_path: Path
    ) -> None:
        """PagesPublisher is not called when registry_dir is None."""
        self._setup_pkg(tmp_path)
        pub = _make_publisher(registry="github", owner="myorg")
        mock_put.return_value = MagicMock(status_code=200)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="com.foo.bar-1.0.0.tgz\n",
                stderr="",
            )
            with patch("pathlib.Path.read_bytes", return_value=b"x"):
                with patch(
                    "unity_wrapper.utils.package_publisher"
                    ".PagesPublisher.update_registry"
                ) as mock_pages:
                    pub._github_publish_direct(tmp_path, registry_dir=None)

        mock_pages.assert_not_called()

    @patch("unity_wrapper.utils.package_publisher.http_requests.put")
    def test_pages_publisher_called_on_conflict(
        self, mock_put: MagicMock, tmp_path: Path
    ) -> None:
        """Static packument is written even when GitHub returns 409."""
        from unity_wrapper.utils.package_publisher import _PublishConflict

        self._setup_pkg(tmp_path)
        pub = _make_publisher(registry="github", owner="myorg")
        mock_put.return_value = MagicMock(status_code=409)
        registry_dir = tmp_path / "registry"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="com.foo.bar-1.0.0.tgz\n",
                stderr="",
            )
            with patch("pathlib.Path.read_bytes", return_value=b"x"):
                with patch(
                    "unity_wrapper.utils.package_publisher"
                    ".PagesPublisher.update_registry"
                ) as mock_pages:
                    with pytest.raises(_PublishConflict):
                        pub._github_publish_direct(
                            tmp_path, registry_dir=registry_dir
                        )

        mock_pages.assert_called_once()
