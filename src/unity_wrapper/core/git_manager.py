"""Git repository management for Unity package wrapper."""

import shutil
import logging
from pathlib import Path
from typing import Dict, Optional
from git import Repo, GitCommandError


logger = logging.getLogger(__name__)


class GitManager:
    """Manages Git repositories for Unity package building."""

    def __init__(self, work_dir: Path):
        """Initialize GitManager with working directory."""
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.repos: Dict[str, Repo] = {}

    def clone_or_update(self, url: str, ref: str, name: str) -> Path:
        """Clone or update a repository to the specified ref."""
        repo_path = self.work_dir / name

        try:
            if repo_path.exists():
                # Repository exists, update it
                repo = Repo(repo_path)
                logger.info(f"Updating existing repository: {name}")

                # Fetch latest changes
                repo.remotes.origin.fetch()

                # Check if ref has changed
                current_ref = self._get_current_ref(repo)
                if current_ref != ref:
                    logger.info(f"Ref changed from {current_ref} to {ref}, updating...")
                    self._checkout_ref(repo, ref)
                    return repo_path
                else:
                    logger.info(f"Repository {name} already at ref {ref}")
                    return repo_path
            else:
                # Clone new repository
                logger.info(f"Cloning repository: {url}")
                repo = Repo.clone_from(url, repo_path)
                self._checkout_ref(repo, ref)

            self.repos[name] = repo
            return repo_path

        except GitCommandError as e:
            logger.error(f"Git operation failed for {name}: {e}")
            raise

    def _checkout_ref(self, repo: Repo, ref: str) -> None:
        """Checkout a specific ref (branch, tag, or commit)."""
        try:
            # Try to checkout as branch first
            repo.git.checkout(ref)
        except GitCommandError:
            try:
                # Try as tag
                repo.git.checkout(f"refs/tags/{ref}")
            except GitCommandError:
                # Try as commit hash
                repo.git.checkout(ref)

    def _get_current_ref(self, repo: Repo) -> str:
        """Get current ref (branch name, tag, or commit hash)."""
        try:
            # Check if on a branch
            if repo.active_branch:
                return repo.active_branch.name
        except TypeError:
            pass

        # Check if on a tag
        try:
            for tag in repo.tags:
                if tag.commit == repo.head.commit:
                    return tag.name
        except:
            pass

        # Return commit hash
        return repo.head.commit.hexsha[:8]

    def get_repo_info(self, name: str) -> Optional[Dict[str, str]]:
        """Get information about a repository."""
        if name not in self.repos:
            return None

        repo = self.repos[name]
        return {
            "name": name,
            "url": repo.remotes.origin.url,
            "ref": self._get_current_ref(repo),
            "commit": repo.head.commit.hexsha,
            "last_updated": repo.head.commit.committed_datetime.isoformat(),
        }

    def extract_folder(
        self, repo_name: str, source_path: str, destination: Path
    ) -> None:
        """Extract a specific folder from a repository."""
        if repo_name not in self.repos:
            raise ValueError(f"Repository {repo_name} not found")

        repo_path = self.work_dir / repo_name
        source_full_path = repo_path / source_path

        if not source_full_path.exists():
            raise FileNotFoundError(
                f"Source path {source_path} not found in {repo_name}"
            )

        # Remove destination if it exists
        if destination.exists():
            shutil.rmtree(destination)

        # Copy the folder
        shutil.copytree(source_full_path, destination)
        logger.info(f"Extracted {source_path} from {repo_name} to {destination}")

    def cleanup(self) -> None:
        """Clean up temporary repositories."""
        for _, repo in self.repos.items():
            repo.close()

        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)
        logger.info("Cleaned up temporary repositories")
