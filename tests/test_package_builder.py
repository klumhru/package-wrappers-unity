"""Tests for PackageBuilder.build_all_packages()."""

import tempfile
import yaml
import pytest
from pathlib import Path
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, patch

from unity_wrapper.core.package_builder import PackageBuilder


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

GIT_PKG = "com.test.gitpkg"
NUGET_PKG = "com.test.nugetpkg"


def _write_config(config_dir: Path, *, max_workers: int = 4) -> None:
    packages: Dict[str, Any] = {
        "packages": [
            {
                "name": GIT_PKG,
                "source": {
                    "url": "https://github.com/example/repo.git",
                    "ref": "main",
                },
                "extract_path": "src",
                "namespace": "Test",
            }
        ],
        "nuget_packages": [
            {
                "name": NUGET_PKG,
                "source": {
                    "type": "nuget",
                    "package": "Test.Package",
                    "version": "1.0.0",
                    "framework": "netstandard2.1",
                },
            }
        ],
    }
    with open(config_dir / "packages.yaml", "w") as fh:
        yaml.dump(packages, fh)

    settings: Dict[str, Any] = {
        "output_dir": "packages",
        "work_dir": ".temp",
        "build": {
            "max_parallel_clones": max_workers,
            "git_cache_dir": ".git-cache",
        },
    }
    with open(config_dir / "settings.yaml", "w") as fh:
        yaml.dump(settings, fh)


def _write_git_only_config(config_dir: Path, *, max_workers: int = 4) -> None:
    packages: Dict[str, Any] = {
        "packages": [
            {
                "name": GIT_PKG,
                "source": {
                    "url": "https://github.com/example/repo.git",
                    "ref": "main",
                },
                "extract_path": "src",
            }
        ]
    }
    with open(config_dir / "packages.yaml", "w") as fh:
        yaml.dump(packages, fh)

    settings: Dict[str, Any] = {"build": {"max_parallel_clones": max_workers}}
    with open(config_dir / "settings.yaml", "w") as fh:
        yaml.dump(settings, fh)


def _write_nuget_only_config(config_dir: Path) -> None:
    packages: Dict[str, Any] = {
        "nuget_packages": [
            {
                "name": NUGET_PKG,
                "source": {
                    "type": "nuget",
                    "package": "Test.Package",
                    "version": "1.0.0",
                    "framework": "netstandard2.1",
                },
            }
        ]
    }
    with open(config_dir / "packages.yaml", "w") as fh:
        yaml.dump(packages, fh)

    with open(config_dir / "settings.yaml", "w") as fh:
        yaml.dump({}, fh)


def _write_empty_config(config_dir: Path) -> None:
    with open(config_dir / "packages.yaml", "w") as fh:
        yaml.dump({}, fh)
    with open(config_dir / "settings.yaml", "w") as fh:
        yaml.dump({}, fh)


@pytest.fixture
def tmp_dirs() -> Generator[tuple[Path, Path], None, None]:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        yield base / "config", base / "output"


def _make_builder(
    config_dir: Path, output_dir: Path
) -> tuple["PackageBuilder", MagicMock, MagicMock]:
    """Construct a PackageBuilder with heavy collaborators patched out.

    Returns (builder, mock_git_manager_instance, mock_nuget_manager_instance).
    """
    with (
        patch("unity_wrapper.core.package_builder.GitManager") as MockGitMgr,
        patch(
            "unity_wrapper.core.package_builder.NuGetManager"
        ) as MockNugetMgr,
        patch("unity_wrapper.core.package_builder.UnityGenerator"),
    ):
        mock_git = MockGitMgr.return_value
        mock_git.repos = {}
        mock_git.cache_dir = config_dir / ".git-cache"
        mock_nuget = MockNugetMgr.return_value

        builder = PackageBuilder(config_dir, output_dir)
        # Re-assign so the instance attributes point to our mocks
        builder.git_manager = mock_git
        builder.nuget_manager = mock_nuget

    return builder, mock_git, mock_nuget


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildAllPackages:
    """Unit tests for PackageBuilder.build_all_packages()."""

    def test_prefetch_called_only_for_git_packages(
        self, tmp_dirs: tuple[Path, Path]
    ) -> None:
        """prefetch_all receives only git repos, not NuGet packages."""
        config_dir, output_dir = tmp_dirs
        config_dir.mkdir(parents=True)
        _write_config(config_dir)

        builder, mock_git, _ = _make_builder(config_dir, output_dir)
        expected_path = output_dir / GIT_PKG

        with patch.object(
            builder, "build_package", return_value=expected_path
        ):
            builder.build_all_packages()

        mock_git.prefetch_all.assert_called_once()
        repos_arg = mock_git.prefetch_all.call_args.args[0]
        names = [r["name"] for r in repos_arg]
        assert names == [GIT_PKG]
        assert NUGET_PKG not in names

    def test_max_workers_passed_to_prefetch(
        self, tmp_dirs: tuple[Path, Path]
    ) -> None:
        """max_workers from config is forwarded to prefetch_all."""
        config_dir, output_dir = tmp_dirs
        config_dir.mkdir(parents=True)
        _write_git_only_config(config_dir, max_workers=8)

        builder, mock_git, _ = _make_builder(config_dir, output_dir)

        with patch.object(
            builder, "build_package", return_value=output_dir / GIT_PKG
        ):
            builder.build_all_packages()

        mock_git.prefetch_all.assert_called_once()
        assert mock_git.prefetch_all.call_args.kwargs["max_workers"] == 8

    def test_build_package_called_for_every_package(
        self, tmp_dirs: tuple[Path, Path]
    ) -> None:
        """build_package is called once per configured package."""
        config_dir, output_dir = tmp_dirs
        config_dir.mkdir(parents=True)
        _write_config(config_dir)

        builder, _, _ = _make_builder(config_dir, output_dir)

        with patch.object(
            builder,
            "build_package",
            side_effect=lambda name: output_dir / name,
        ) as mock_build:
            builder.build_all_packages()

        assert mock_build.call_count == 2
        called_names = {c.args[0] for c in mock_build.call_args_list}
        assert called_names == {GIT_PKG, NUGET_PKG}

    def test_returns_all_built_paths(
        self, tmp_dirs: tuple[Path, Path]
    ) -> None:
        """Return value is a list of every successfully built package path."""
        config_dir, output_dir = tmp_dirs
        config_dir.mkdir(parents=True)
        _write_config(config_dir)

        builder, _, _ = _make_builder(config_dir, output_dir)

        with patch.object(
            builder,
            "build_package",
            side_effect=lambda name: output_dir / name,
        ):
            result = builder.build_all_packages()

        assert len(result) == 2
        assert output_dir / GIT_PKG in result
        assert output_dir / NUGET_PKG in result

    def test_nuget_only_skips_prefetch(
        self, tmp_dirs: tuple[Path, Path]
    ) -> None:
        """When there are no git packages, prefetch_all is never called."""
        config_dir, output_dir = tmp_dirs
        config_dir.mkdir(parents=True)
        _write_nuget_only_config(config_dir)

        builder, mock_git, _ = _make_builder(config_dir, output_dir)

        with patch.object(
            builder, "build_package", return_value=output_dir / NUGET_PKG
        ):
            builder.build_all_packages()

        mock_git.prefetch_all.assert_not_called()

    def test_empty_package_list_returns_empty(
        self, tmp_dirs: tuple[Path, Path]
    ) -> None:
        """No packages configured → returns an empty list."""
        config_dir, output_dir = tmp_dirs
        config_dir.mkdir(parents=True)
        _write_empty_config(config_dir)

        builder, mock_git, _ = _make_builder(config_dir, output_dir)
        result = builder.build_all_packages()

        assert result == []
        mock_git.prefetch_all.assert_not_called()

    def test_build_failure_reraises(self, tmp_dirs: tuple[Path, Path]) -> None:
        """build_package exception propagates out of build_all_packages."""
        config_dir, output_dir = tmp_dirs
        config_dir.mkdir(parents=True)
        _write_git_only_config(config_dir)

        builder, _, _ = _make_builder(config_dir, output_dir)

        with patch.object(
            builder, "build_package", side_effect=RuntimeError("build failed")
        ):
            with pytest.raises(RuntimeError, match="build failed"):
                builder.build_all_packages()

    def test_prefetch_repo_url_and_ref_are_correct(
        self, tmp_dirs: tuple[Path, Path]
    ) -> None:
        """The url and ref forwarded to prefetch_all match packages.yaml."""
        config_dir, output_dir = tmp_dirs
        config_dir.mkdir(parents=True)
        _write_git_only_config(config_dir)

        builder, mock_git, _ = _make_builder(config_dir, output_dir)

        with patch.object(
            builder, "build_package", return_value=output_dir / GIT_PKG
        ):
            builder.build_all_packages()

        repos_arg = mock_git.prefetch_all.call_args.args[0]
        assert len(repos_arg) == 1
        assert repos_arg[0]["url"] == "https://github.com/example/repo.git"
        assert repos_arg[0]["ref"] == "main"
        assert repos_arg[0]["name"] == GIT_PKG

    def test_skips_clone_when_repo_already_prefetched(
        self, tmp_dirs: tuple[Path, Path]
    ) -> None:
        """_build_git_package uses cached path when repo already prefetched."""
        config_dir, output_dir = tmp_dirs
        config_dir.mkdir(parents=True)
        _write_git_only_config(config_dir)

        builder, mock_git, _ = _make_builder(config_dir, output_dir)

        # Simulate the repo having been prefetched already
        mock_git.repos[GIT_PKG] = MagicMock()
        repo_path = mock_git.cache_dir / GIT_PKG
        repo_path.mkdir(parents=True)
        (repo_path / "src").mkdir()

        with (
            patch.object(
                builder.unity_generator, "organize_runtime_structure"
            ) as mock_org,
            patch.object(builder.unity_generator, "write_package_json"),
            patch.object(builder.unity_generator, "generate_all_meta_files"),
        ):
            mock_org.return_value = output_dir / GIT_PKG / "Runtime"
            builder._build_git_package(GIT_PKG)

        # clone_or_update must NOT have been called
        mock_git.clone_or_update.assert_not_called()
