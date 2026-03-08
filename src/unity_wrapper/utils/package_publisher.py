"""Package publisher for multiple registries."""

import base64
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import requests as http_requests

from unity_wrapper.utils.pages_publisher import PagesPublisher

logger = logging.getLogger(__name__)


class _PublishConflict(Exception):
    """Raised when a package version already exists in the registry."""


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
        self.repo = self._get_repo_from_env()

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

    def _get_repo_from_env(self) -> Optional[str]:
        """Get repository name from GITHUB_REPOSITORY env var."""
        github_repo = os.getenv("GITHUB_REPOSITORY")
        if github_repo and "/" in github_repo:
            return github_repo.split("/", 1)[1]
        return None

    def _compute_scoped_name(self, name: str) -> str:
        """Return the scoped package name for the current registry."""
        if (
            self.registry in ("github", "npmjs")
            and self.owner
            and not name.startswith("@")
        ):
            return f"@{self.owner}/{name}"
        return name

    def _package_browse_url(
        self, scoped_name: str, original_name: str, version: str
    ) -> str:
        """Return a browser URL to inspect the published package.

        Args:
            scoped_name: Fully-scoped npm package name.
            original_name: Unscoped Unity package name.
            version: Package version string.

        Returns:
            Browser-accessible URL for the package.
        """
        if self.registry == "github":
            if self.owner and self.repo:
                pkg_slug = scoped_name.split("/")[-1]
                return (
                    f"https://github.com/{self.owner}/{self.repo}"
                    f"/pkgs/npm/{pkg_slug}"
                )
            if self.owner:
                return f"https://github.com/{self.owner}?tab=packages"
            return "https://github.com"
        if self.registry == "npmjs":
            return (
                f"https://www.npmjs.com/package/{scoped_name}" f"/v/{version}"
            )
        if self.registry == "openupm":
            return f"https://openupm.com/packages/{original_name}/"
        return ""

    def _is_publish_conflict(
        self, error: subprocess.CalledProcessError
    ) -> bool:
        """Return True if the error indicates a 409 version conflict."""
        stderr = (error.stderr or "").lower()
        return any(
            indicator in stderr
            for indicator in (
                "e409",
                "409 conflict",
                "already exists",
                "cannot publish over",
                "epublishconflict",
            )
        )

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

    def publish_package(
        self,
        package_dir: Path,
        registry_dir: Optional[Path] = None,
    ) -> None:
        """Publish a Unity package to the configured registry.

        Args:
            package_dir: Path to the built Unity package directory.
            registry_dir: Optional directory for static packument files
                used by the GitHub Pages registry.  Only used when
                ``registry == 'github'``.  Defaults to
                ``dist/registry`` relative to the current working
                directory when ``registry == 'github'`` and this
                argument is ``None``.
        """
        package_json_path = package_dir / "package.json"

        if not package_json_path.exists():
            raise FileNotFoundError(f"package.json not found in {package_dir}")

        with open(package_json_path, "r", encoding="utf-8") as f:
            package_json = json.load(f)

        original_name = package_json["name"]
        version = package_json["version"]
        display_name = self._compute_scoped_name(original_name)
        browse_url = self._package_browse_url(
            display_name, original_name, version
        )

        logger.info(
            f"Publishing {display_name}@{version} to "
            f"{self.registry} registry"
        )

        if self.registry == "github" and registry_dir is None:
            registry_dir = Path("dist/registry")

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                package_copy = temp_path / "package"
                self._copy_package(package_dir, package_copy)
                self._update_package_json(package_copy / "package.json")
                if self.registry == "github":
                    self._github_publish_direct(
                        package_copy, registry_dir=registry_dir
                    )
                else:
                    self._configure_npm(temp_path)
                    self._npm_publish(package_copy)

            logger.info(
                f"Successfully published {display_name}@{version}. "
                f"View at: {browse_url}"
            )
        except _PublishConflict:
            logger.warning(
                f"{display_name}@{version} already published "
                f"(version conflict). View at: {browse_url}"
            )
        except subprocess.CalledProcessError as e:
            if self._is_publish_conflict(e):
                logger.warning(
                    f"{display_name}@{version} already published "
                    f"(version conflict). View at: {browse_url}"
                )
            else:
                logger.error(f"npm publish failed: {e.stderr}")
                raise

    def _copy_package(self, source: Path, dest: Path) -> None:
        """Copy package directory to destination."""
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)

    def _update_package_json(self, package_json_path: Path) -> None:
        """Update package.json for the target registry.

        For GitHub, the ``name`` field is kept unscoped (e.g.
        ``com.foo.bar``) so that Unity Package Manager can resolve it.
        The scope is applied at publish time via the direct HTTP PUT
        URL, not via the ``name`` field.  For npmjs the name is scoped
        (e.g. ``@owner/com.foo.bar``).
        """
        with open(package_json_path, "r", encoding="utf-8") as f:
            package_json = json.load(f)

        original_name = package_json["name"]
        # GitHub: keep unscoped name in the tarball for UPM compatibility.
        # npmjs: scope the name so consumers can install it.
        if self.registry != "github":
            package_json["name"] = self._compute_scoped_name(original_name)

        if self.owner and self.registry in ["github", "npmjs"]:
            if self.registry == "github" and self.repo:
                repo_url = f"https://github.com/{self.owner}/{self.repo}.git"
            else:
                repo_url = (
                    f"https://github.com/{self.owner}/"
                    f"{original_name}.package-wrappers-unity.git"
                )
            package_json["repository"] = {
                "type": "git",
                "url": repo_url,
            }

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

    def _github_publish_direct(
        self,
        package_dir: Path,
        registry_dir: Optional[Path] = None,
    ) -> None:
        """Publish to GitHub Packages using the npm registry HTTP API.

        Bypasses the npm CLI so we can PUT directly to the scoped URL
        (``/@owner/com.foo.bar``) that GitHub requires for routing, while
        keeping the ``name`` field inside the tarball unscoped
        (``com.foo.bar``) so Unity Package Manager can resolve it.

        After a successful publish, writes a static packument JSON file
        to ``registry_dir`` (if provided) with the unscoped name so that
        a GitHub Pages-hosted registry can serve it to UPM consumers.

        Raises:
            _PublishConflict: If the version already exists (HTTP 409).
            requests.HTTPError: For other HTTP errors.
        """
        with open(package_dir / "package.json", encoding="utf-8") as f:
            pkg_data: Dict[str, Any] = json.load(f)

        original_name = pkg_data["name"]  # unscoped: com.foo.bar
        version = pkg_data["version"]
        scoped_name = self._compute_scoped_name(original_name)

        # Create tarball with npm pack.  The package.json inside the
        # tarball keeps the unscoped name for UPM.
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                ["npm", "pack", "--pack-destination", tmp],
                cwd=package_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            tarball_filename = result.stdout.strip().split("\n")[-1]
            tarball_data = (Path(tmp) / tarball_filename).read_bytes()

        shasum = hashlib.sha1(tarball_data).hexdigest()  # nosec B324
        integrity = (
            "sha512-"
            + base64.b64encode(hashlib.sha512(tarball_data).digest()).decode()
        )

        # Registry metadata uses the scoped name for GitHub routing.
        # The tarball attachment contains the files with unscoped name.
        # The attachment key must be the scoped name followed by the
        # version: ``@owner/name-version.tgz``.  GitHub's npm registry
        # derives the attachment by matching this exact key format.
        attachment_key = f"{scoped_name}-{version}.tgz"
        tarball_url = f"{self.config['url']}/{scoped_name}/-/{attachment_key}"

        version_meta: Dict[str, Any] = {
            **pkg_data,
            "name": scoped_name,
            "_id": f"{scoped_name}@{version}",
            "dist": {
                "integrity": integrity,
                "shasum": shasum,
                "tarball": tarball_url,
            },
        }

        packument = {
            "_id": scoped_name,
            "name": scoped_name,
            "dist-tags": {"latest": version},
            "versions": {version: version_meta},
            "_attachments": {
                attachment_key: {
                    "content_type": "application/octet-stream",
                    "data": base64.b64encode(tarball_data).decode(),
                    "length": len(tarball_data),
                }
            },
        }

        url = f"{self.config['url']}/{scoped_name}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.npm.install-v1+json",
        }
        response = http_requests.put(
            url, json=packument, headers=headers, timeout=120
        )

        if response.status_code == 409:
            # Version already exists — still update the static registry so
            # the Pages packument stays current (e.g. on first run after
            # adding PagesPublisher, or after a manual re-publish).
            if registry_dir is not None:
                PagesPublisher().update_registry(
                    registry_dir=registry_dir,
                    unscoped_name=original_name,
                    version=version,
                    version_meta=version_meta,
                    tarball_url=tarball_url,
                    shasum=shasum,
                    integrity=integrity,
                    description=pkg_data.get("description"),
                )
            raise _PublishConflict(scoped_name)

        response.raise_for_status()
        logger.debug(f"GitHub publish HTTP status: {response.status_code}")

        if registry_dir is not None:
            PagesPublisher().update_registry(
                registry_dir=registry_dir,
                unscoped_name=original_name,
                version=version,
                version_meta=version_meta,
                tarball_url=tarball_url,
                shasum=shasum,
                integrity=integrity,
                description=pkg_data.get("description"),
            )

    def _npm_publish(self, package_dir: Path) -> None:
        """Publish package using npm (non-GitHub registries)."""
        if self.registry == "openupm":
            logger.warning(
                "OpenUPM packages must be submitted manually at "
                "https://openupm.com/packages/add/"
            )
            return

        result = subprocess.run(
            ["npm", "publish"],
            cwd=package_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.debug(f"npm publish output: {result.stdout}")

    def check_package_exists(self, package_name: str, version: str) -> bool:
        """Check if a package version already exists in the registry."""
        if self.registry == "openupm":
            logger.info("OpenUPM package existence check not implemented")
            return False

        scoped_name = self._compute_scoped_name(package_name)

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
