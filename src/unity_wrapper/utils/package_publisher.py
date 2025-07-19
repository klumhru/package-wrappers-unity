"""Package publisher for multiple registries."""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PackagePublisher:
    """Publishes Unity packages to various package registries."""

    REGISTRY_CONFIGS: Dict[str, Dict[str, Any]] = {
        "github": {
            "url": "https://npm.pkg.github.com",
            "requires_auth": True,
            "scope_prefix": "@",
        },
        "npmjs": {
            "url": "https://registry.npmjs.org",
            "requires_auth": True,  # For publishing
            "scope_prefix": "@",
        },
        "openupm": {
            "url": "https://package.openupm.com",
            "requires_auth": False,
            "scope_prefix": "",
        },
    }

    def __init__(
        self,
        registry: str = "npmjs",
        token: Optional[str] = None,
        owner: Optional[str] = None,
    ):
        """Initialize package publisher.

        Args:
            registry: Target registry ('github', 'npmjs', 'openupm')
            token: Authentication token (if required)
            owner: Package owner/organization name
        """
        if registry not in self.REGISTRY_CONFIGS:
            raise ValueError(
                f"Unsupported registry: {registry}. "
                f"Supported: {list(self.REGISTRY_CONFIGS.keys())}"
            )

        self.registry = registry
        self.config = self.REGISTRY_CONFIGS[registry]
        self.token = token or self._get_token_from_env()
        self.owner = owner or self._get_owner_from_env()

        # Check authentication requirements
        if self.config["requires_auth"] and not self.token:
            raise ValueError(
                f"Authentication token is required for {registry} registry"
            )

        # Check if npm is available
        self._check_npm_available()

    def _get_token_from_env(self) -> Optional[str]:
        """Get authentication token from environment variables."""
        if self.registry == "github":
            return os.getenv("GITHUB_TOKEN")
        elif self.registry == "npmjs":
            return os.getenv("NPM_TOKEN")
        return None

    def _get_owner_from_env(self) -> Optional[str]:
        """Get owner from environment variables."""
        # Try GitHub Actions environment first
        github_repo = os.getenv("GITHUB_REPOSITORY")
        if github_repo:
            return github_repo.split("/")[0]

        # Fall back to generic owner environment variable
        return os.getenv("PACKAGE_OWNER")

    def _check_npm_available(self) -> None:
        """Check if npm is available."""
        try:
            subprocess.run(
                ["npm", "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise RuntimeError(
                "npm is not available. Please install Node.js and npm."
            ) from e

    def publish_package(self, package_dir: Path) -> None:
        """Publish a Unity package to the configured registry."""
        package_json_path = package_dir / "package.json"

        if not package_json_path.exists():
            raise FileNotFoundError(f"package.json not found in {package_dir}")

        # Load package.json
        with open(package_json_path, "r", encoding="utf-8") as f:
            package_json = json.load(f)

        package_name = package_json["name"]
        version = package_json["version"]

        logger.info(
            f"Publishing {package_name}@{version} to {self.registry} registry"
        )

        # Create a temporary directory for npm operations
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Copy package to temp directory
            package_copy = temp_path / "package"
            self._copy_package(package_dir, package_copy)

            # Update package.json for the target registry
            self._update_package_json(package_copy / "package.json")

            # Configure npm for the target registry
            self._configure_npm(temp_path)

            # Publish using npm
            self._npm_publish(package_copy)

        logger.info(f"Successfully published {package_name}@{version}")

    def _copy_package(self, source: Path, dest: Path) -> None:
        """Copy package directory to destination."""
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)

    def _update_package_json(self, package_json_path: Path) -> None:
        """Update package.json for the target registry."""
        with open(package_json_path, "r", encoding="utf-8") as f:
            package_json = json.load(f)

        # Update package name with scope if needed
        original_name = package_json["name"]

        if self.registry == "github" and self.owner:
            # GitHub requires scoped packages
            if not original_name.startswith("@"):
                package_json["name"] = f"@{self.owner}/{original_name}"
        elif self.registry == "npmjs" and self.owner:
            # npmjs can use scoped packages
            if not original_name.startswith("@"):
                package_json["name"] = f"@{self.owner}/{original_name}"
        # OpenUPM doesn't require scoping

        # Add repository information
        if self.owner and self.registry in ["github", "npmjs"]:
            package_json["repository"] = {
                "type": "git",
                "url": (
                    f"https://github.com/{self.owner}/"
                    f"{original_name}.package-wrappers-unity.git"
                ),
            }

        # Add publishConfig for GitHub
        if self.registry == "github":
            package_json["publishConfig"] = {"registry": self.config["url"]}

        # Write updated package.json
        with open(package_json_path, "w", encoding="utf-8") as f:
            json.dump(package_json, f, indent=2, ensure_ascii=False)

    def _configure_npm(self, work_dir: Path) -> None:
        """Configure npm for the target registry."""
        npmrc_path = work_dir / ".npmrc"

        with open(npmrc_path, "w", encoding="utf-8") as f:
            if self.registry == "github":
                f.write(f"@{self.owner}:registry={self.config['url']}\n")
                if self.token:
                    f.write(f"//npm.pkg.github.com/:_authToken={self.token}\n")
            elif self.registry == "npmjs":
                f.write(f"registry={self.config['url']}\n")
                if self.token:
                    f.write(f"//registry.npmjs.org/:_authToken={self.token}\n")
            # OpenUPM submission is manual, not via npm publish

    def _npm_publish(self, package_dir: Path) -> None:
        """Publish package using npm."""
        if self.registry == "openupm":
            logger.warning(
                "OpenUPM packages must be submitted manually at "
                "https://openupm.com/packages/add/"
            )
            return

        try:
            result = subprocess.run(
                ["npm", "publish"],
                cwd=package_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.debug(f"npm publish output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"npm publish failed: {e.stderr}")
            raise

    def check_package_exists(self, package_name: str, version: str) -> bool:
        """Check if a package version already exists in the registry."""
        if self.registry == "openupm":
            logger.info("OpenUPM package existence check not implemented")
            return False

        scoped_name = package_name
        if self.registry in ["github", "npmjs"] and self.owner:
            if not package_name.startswith("@"):
                scoped_name = f"@{self.owner}/{package_name}"

        try:
            subprocess.run(
                [
                    "npm",
                    "view",
                    f"{scoped_name}@{version}",
                    f"--registry={self.config['url']}",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False


def create_publisher(
    registry: str,
    token: Optional[str] = None,
    owner: Optional[str] = None,
) -> PackagePublisher:
    """Factory function to create a package publisher.

    Args:
        registry: Target registry ('github', 'npmjs', 'openupm')
        token: Authentication token
        owner: Package owner/organization

    Returns:
        Configured PackagePublisher instance
    """
    return PackagePublisher(registry=registry, token=token, owner=owner)
