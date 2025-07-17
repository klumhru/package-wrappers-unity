"""GitHub Package Registry publisher."""

import json
import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any, cast


logger = logging.getLogger(__name__)


class GitHubPublisher:
    """Publishes Unity packages to GitHub Package Registry using npm CLI."""

    def __init__(
        self,
        token: Optional[str] = None,
        registry_url: Optional[str] = None,
        owner: Optional[str] = None,
        repository: Optional[str] = None,
    ):
        """Initialize GitHub publisher."""
        # Use provided token, or fall back to GitHub Actions token
        # from environment
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.registry_url = registry_url or "https://npm.pkg.github.com"
        self.owner = owner
        self.repository = repository

        if not self.token:
            raise ValueError(
                "GitHub token is required. Provide a token or set "
                "the GITHUB_TOKEN environment variable."
            )

        if not self.owner:
            raise ValueError("Owner is required for GitHub Package Registry")

        # Check if npm is available
        self._check_npm_available()

    def _check_npm_available(self) -> None:
        """Check if npm is available in the system."""
        try:
            result = subprocess.run(
                ["npm", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.debug(f"npm version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "npm command not found. Please ensure Node.js and npm are "
                "installed. You can install them from https://nodejs.org/"
            )

    def publish_package(self, package_dir: Path) -> None:
        """Publish a Unity package to GitHub Package Registry using npm."""
        package_json_path = package_dir / "package.json"

        if not package_json_path.exists():
            raise FileNotFoundError(f"package.json not found in {package_dir}")

        # Load package.json
        with open(package_json_path, "r", encoding="utf-8") as f:
            package_json = json.load(f)

        package_name = package_json["name"]
        version = package_json["version"]

        logger.info(
            f"Publishing {package_name}@{version} to GitHub Package Registry"
        )

        # Create a temporary directory for npm operations
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Copy package to temp directory
            package_copy = temp_path / "package"
            self._copy_package(package_dir, package_copy)

            # Update package.json to ensure it's scoped for GitHub
            self._update_package_json_for_github(package_copy / "package.json")

            # Configure npm for GitHub Package Registry
            self._configure_npm(temp_path)

            # Publish using npm
            self._npm_publish(package_copy)

        logger.info(f"Successfully published {package_name}@{version}")

    def _copy_package(self, source: Path, dest: Path) -> None:
        """Copy package directory to destination."""
        dest.mkdir(parents=True, exist_ok=True)

        # Copy all files and directories
        for item in source.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(source)
                dest_file = dest / rel_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                # Copy file content
                with open(item, "rb") as src_f, open(dest_file, "wb") as dst_f:
                    dst_f.write(src_f.read())

    def _update_package_json_for_github(self, package_json_path: Path) -> None:
        """Update package.json to ensure it's properly scoped for GitHub."""
        with open(package_json_path, "r", encoding="utf-8") as f:
            package_json = json.load(f)

        name = package_json["name"]

        # Ensure the package name is properly scoped for GitHub
        if not name.startswith("@"):
            package_json["name"] = f"@{self.owner}/{name}"

        # Add publishConfig to ensure it publishes to GitHub Package Registry
        package_json["publishConfig"] = {"registry": self.registry_url}

        with open(package_json_path, "w", encoding="utf-8") as f:
            json.dump(package_json, f, indent=2)

    def _configure_npm(self, working_dir: Path) -> None:
        """Configure npm for GitHub Package Registry authentication."""
        # Create .npmrc file for authentication
        npmrc_content = f"""//npm.pkg.github.com/:_authToken={self.token}
@{self.owner}:registry={self.registry_url}
"""

        npmrc_path = working_dir / ".npmrc"
        with open(npmrc_path, "w", encoding="utf-8") as f:
            f.write(npmrc_content)

    def _npm_publish(self, package_dir: Path) -> None:
        """Publish package using npm CLI."""
        try:
            # Run npm publish
            result = subprocess.run(
                ["npm", "publish", "--access", "public"],
                cwd=package_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            logger.debug(f"npm publish output: {result.stdout}")

        except subprocess.CalledProcessError as e:
            if (
                "EPUBLISHCONFLICT" in e.stderr
                or "cannot publish over the previously published version"
                in e.stderr
            ):
                logger.warning(f"Package version already exists: {e.stderr}")
            elif "ENEEDAUTH" in e.stderr or "need auth" in e.stderr:
                logger.error(
                    f"Authentication required for npm registry: {e.stderr}"
                )
                raise RuntimeError(
                    "Authentication required. Please run 'npm login "
                    "--scope=@{} --registry={}' to authenticate with the "
                    "GitHub Package Registry.".format(
                        self.owner, self.registry_url
                    )
                )
            else:
                logger.error(f"npm publish failed: {e.stderr}")
                raise RuntimeError(f"Failed to publish package: {e.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                "npm command not found. Please ensure Node.js and npm are "
                "installed."
            )

    def check_package_exists(self, package_name: str, version: str) -> bool:
        """Check if a package version already exists in the registry."""
        if not package_name.startswith("@"):
            scoped_name = f"@{self.owner}/{package_name}"
        else:
            scoped_name = package_name

        try:
            result = subprocess.run(
                ["npm", "view", f"{scoped_name}@{version}", "version"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except FileNotFoundError:
            raise RuntimeError(
                "npm command not found. Please ensure Node.js and npm are "
                "installed."
            )

    def get_package_info(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Get package information from the registry."""
        if not package_name.startswith("@"):
            scoped_name = f"@{self.owner}/{package_name}"
        else:
            scoped_name = package_name

        try:
            result = subprocess.run(
                ["npm", "view", scoped_name, "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                return cast(Dict[str, Any], json.loads(result.stdout))
            else:
                return None

        except (FileNotFoundError, json.JSONDecodeError):
            return None
