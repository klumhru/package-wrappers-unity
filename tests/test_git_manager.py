"""Tests for GitManager parallel fetching and persistent cache behaviour."""

import pytest
import tempfile
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Dict, Generator, List
from unittest.mock import MagicMock, patch

from unity_wrapper.core.git_manager import GitManager


@pytest.fixture
def temp_dirs() -> Generator[tuple[Path, Path], None, None]:
    """Provide separate work_dir and cache_dir in a temp location."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        yield base / "work", base / "cache"


class TestCacheDir:
    """GitManager uses cache_dir for clones; work_dir is separate."""

    def test_cache_dir_defaults_to_work_dir(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """When cache_dir is omitted, it falls back to work_dir."""
        work_dir, _ = temp_dirs
        gm = GitManager(work_dir)
        assert gm.cache_dir == gm.work_dir

    def test_explicit_cache_dir_is_used(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """Explicit cache_dir is stored separately from work_dir."""
        work_dir, cache_dir = temp_dirs
        gm = GitManager(work_dir, cache_dir=cache_dir)
        assert gm.cache_dir == cache_dir
        assert gm.work_dir != gm.cache_dir

    def test_cache_dir_is_created(self, temp_dirs: tuple[Path, Path]) -> None:
        """Both directories are created on init."""
        work_dir, cache_dir = temp_dirs
        GitManager(work_dir, cache_dir=cache_dir)
        assert work_dir.exists()
        assert cache_dir.exists()


class TestCloneOrUpdateRegistersRepo:
    """clone_or_update always registers the repo in self.repos."""

    def test_fresh_clone_registers_repo(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """A freshly cloned repo is added to self.repos."""
        work_dir, cache_dir = temp_dirs
        gm = GitManager(work_dir, cache_dir=cache_dir)

        mock_repo = MagicMock()
        with patch(
            "unity_wrapper.core.git_manager.Repo.clone_from",
            return_value=mock_repo,
        ):
            gm.clone_or_update(
                "https://example.com/repo.git", "main", "myrepo"
            )

        assert "myrepo" in gm.repos
        assert gm.repos["myrepo"] is mock_repo

    def test_existing_repo_update_registers_repo(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """Updating an existing repo still registers it in self.repos."""
        work_dir, cache_dir = temp_dirs
        gm = GitManager(work_dir, cache_dir=cache_dir)

        # Pre-create the repo path to simulate an existing clone
        repo_path = cache_dir / "myrepo"
        repo_path.mkdir(parents=True)

        mock_remote = MagicMock()
        mock_repo = MagicMock()
        mock_repo.remotes.origin = mock_remote
        mock_repo.active_branch.name = "main"

        with patch(
            "unity_wrapper.core.git_manager.Repo",
            return_value=mock_repo,
        ):
            gm.clone_or_update(
                "https://example.com/repo.git", "main", "myrepo"
            )

        assert "myrepo" in gm.repos
        assert gm.repos["myrepo"] is mock_repo


class TestCleanup:
    """cleanup() preserves cache_dir and only removes work_dir."""

    def test_cleanup_removes_work_dir_not_cache(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """cleanup() deletes work_dir but leaves cache_dir intact."""
        work_dir, cache_dir = temp_dirs
        gm = GitManager(work_dir, cache_dir=cache_dir)

        # Add a dummy file so the dirs definitely exist
        (work_dir / "tmp.txt").write_text("tmp")
        (cache_dir / "cached_repo").mkdir()

        gm.cleanup()

        assert not work_dir.exists()
        assert cache_dir.exists()
        assert (cache_dir / "cached_repo").exists()

    def test_cleanup_when_cache_equals_work_dir(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """When cache_dir == work_dir, cleanup does NOT delete it."""
        work_dir, _ = temp_dirs
        gm = GitManager(work_dir)  # cache_dir defaults to work_dir

        (work_dir / "something").mkdir()
        gm.cleanup()

        # The shared dir must NOT be removed (cache takes precedence)
        assert work_dir.exists()

    def test_cleanup_cache_nested_inside_work_dir(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """When cache nested in work_dir, only non-cache contents removed."""
        work_dir, _ = temp_dirs
        cache_dir = work_dir / ".git-cache"
        cache_dir.mkdir(parents=True)
        gm = GitManager(work_dir, cache_dir=cache_dir)

        (work_dir / "tmp.txt").write_text("tmp")
        (work_dir / "scratch").mkdir()
        (cache_dir / "myrepo").mkdir()

        gm.cleanup()

        assert work_dir.exists()
        assert cache_dir.exists()
        assert (cache_dir / "myrepo").exists()
        assert not (work_dir / "tmp.txt").exists()
        assert not (work_dir / "scratch").exists()


class TestPrefetchAll:
    """prefetch_all parallelises clone_or_update calls."""

    def _make_repos(self, n: int = 3) -> List[Dict[str, str]]:
        return [
            {
                "url": f"https://example.com/repo{i}.git",
                "ref": "main",
                "name": f"repo{i}",
            }
            for i in range(n)
        ]

    def test_all_repos_are_fetched(self, temp_dirs: tuple[Path, Path]) -> None:
        """Every repo in the list has clone_or_update called."""
        work_dir, cache_dir = temp_dirs
        gm = GitManager(work_dir, cache_dir=cache_dir)
        repos = self._make_repos(3)

        with patch.object(gm, "clone_or_update") as mock_cu:
            gm.prefetch_all(repos, max_workers=4)

        assert mock_cu.call_count == 3
        called_names = {c.args[2] for c in mock_cu.call_args_list}
        assert called_names == {"repo0", "repo1", "repo2"}

    def test_max_workers_is_respected(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """ThreadPoolExecutor is created with the configured max_workers."""
        work_dir, cache_dir = temp_dirs
        gm = GitManager(work_dir, cache_dir=cache_dir)
        repos = self._make_repos(2)

        with patch.object(gm, "clone_or_update"):
            with patch(
                "unity_wrapper.core.git_manager.ThreadPoolExecutor"
            ) as mock_tpe:
                executor_mock = MagicMock()
                executor_mock.submit.side_effect = (
                    lambda fn, *a, **kw: _immediate_future(fn(*a, **kw))
                )
                mock_tpe.return_value.__enter__.return_value = executor_mock
                mock_tpe.return_value.__exit__ = MagicMock(return_value=False)

                gm.prefetch_all(repos, max_workers=7)

                mock_tpe.assert_called_once_with(max_workers=7)

    def test_errors_are_aggregated_not_aborted(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """All repos are attempted even if one fails; RuntimeError raised."""
        work_dir, cache_dir = temp_dirs
        gm = GitManager(work_dir, cache_dir=cache_dir)
        repos = self._make_repos(3)
        attempted: List[str] = []

        def side_effect(url: str, ref: str, name: str) -> None:
            attempted.append(name)
            if name == "repo1":
                raise RuntimeError("network error")

        with patch.object(gm, "clone_or_update", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="Failed to fetch 1 repo"):
                gm.prefetch_all(repos, max_workers=4)

        assert len(attempted) == 3

    def test_error_message_lists_repos_in_sorted_order(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """Failed repo names appear sorted in the RuntimeError message."""
        work_dir, cache_dir = temp_dirs
        gm = GitManager(work_dir, cache_dir=cache_dir)
        repos = self._make_repos(3)

        def side_effect(url: str, ref: str, name: str) -> None:
            raise RuntimeError("bang")

        with patch.object(gm, "clone_or_update", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="repo0, repo1, repo2"):
                gm.prefetch_all(repos, max_workers=4)

    def test_empty_repo_list_is_a_noop(
        self, temp_dirs: tuple[Path, Path]
    ) -> None:
        """prefetch_all with an empty list completes without error."""
        work_dir, cache_dir = temp_dirs
        gm = GitManager(work_dir, cache_dir=cache_dir)
        gm.prefetch_all([], max_workers=4)  # should not raise


def _immediate_future(result: Any) -> Future:  # type: ignore[type-arg]
    """Helper: return an already-resolved Future."""
    f: Future[Any] = Future()
    f.set_result(result)
    return f
