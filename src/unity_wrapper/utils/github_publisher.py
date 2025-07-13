"""GitHub Package Registry publisher."""

import json
import requests
import tarfile
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import base64


logger = logging.getLogger(__name__)


class GitHubPublisher:
    """Publishes Unity packages to GitHub Package Registry."""

    def __init__(
        self,
        token: Optional[str] = None,
        registry_url: Optional[str] = None,
        owner: Optional[str] = None,
        repository: Optional[str] = None,
    ):
        """Initialize GitHub publisher."""
        self.token = token
        self.registry_url = registry_url or "https://npm.pkg.github.com"
        self.owner = owner
        self.repository = repository

        if not self.token:
            raise ValueError("GitHub token is required")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "unity-package-wrapper",
            }
        )

    def publish_package(self, package_dir: Path) -> None:
        """Publish a Unity package to GitHub Package Registry."""
        package_json_path = package_dir / "package.json"

        if not package_json_path.exists():
            raise FileNotFoundError(f"package.json not found in {package_dir}")

        # Load package.json
        with open(package_json_path, "r", encoding="utf-8") as f:
            package_json = json.load(f)

        package_name = package_json["name"]
        version = package_json["version"]

        logger.info(f"Publishing {package_name}@{version} to GitHub Package Registry")

        # Create tarball
        with tempfile.NamedTemporaryFile(suffix=".tgz", delete=False) as temp_file:
            tarball_path = Path(temp_file.name)

        try:
            self._create_tarball(package_dir, tarball_path)

            # Calculate tarball info
            tarball_size = tarball_path.stat().st_size

            with open(tarball_path, "rb") as f:
                tarball_data = f.read()

            # Encode tarball as base64
            tarball_b64 = base64.b64encode(tarball_data).decode("utf-8")

            # Prepare npm package metadata
            npm_metadata = self._create_npm_metadata(
                package_json, tarball_b64, tarball_size
            )

            # Publish to npm registry
            self._publish_to_npm_registry(package_name, npm_metadata)

            logger.info(f"Successfully published {package_name}@{version}")

        finally:
            # Clean up temporary tarball
            if tarball_path.exists():
                tarball_path.unlink()

    def _create_tarball(self, package_dir: Path, output_path: Path) -> None:
        """Create a tarball of the package directory."""
        with tarfile.open(output_path, "w:gz") as tar:
            for item in package_dir.rglob("*"):
                if item.is_file():
                    # Use relative path from package directory
                    arcname = item.relative_to(package_dir)
                    tar.add(item, arcname=f"package/{arcname}")

        logger.info(f"Created tarball: {output_path}")

    def _create_npm_metadata(
        self, package_json: Dict[str, Any], tarball_b64: str, tarball_size: int
    ) -> Dict[str, Any]:
        """Create npm-compatible package metadata."""
        name = package_json["name"]
        version = package_json["version"]

        # Create dist info
        dist: Dict[str, Any] = {
            "shasum": "",  # GitHub will calculate this
            "tarball": f"{self.registry_url}/{name}/-/{name}-{version}.tgz",
            "integrity": "",  # GitHub will calculate this
            "size": tarball_size,
        }

        # Create version metadata
        version_metadata: Dict[str, Any] = {
            **package_json,
            "dist": dist,
            "_nodeVersion": "16.0.0",
            "_npmVersion": "8.0.0",
        }

        # Create full package metadata
        metadata: Dict[str, Any] = {
            "name": name,
            "versions": {version: version_metadata},
            "dist-tags": {"latest": version},
            "_attachments": {
                f"{name}-{version}.tgz": {
                    "content_type": "application/octet-stream",
                    "data": tarball_b64,
                    "length": tarball_size,
                }
            },
        }

        return metadata

    def _publish_to_npm_registry(
        self, package_name: str, metadata: Dict[str, Any]
    ) -> None:
        """Publish package metadata to npm registry."""
        # URL encode package name for GitHub
        encoded_name = package_name.replace("/", "%2F")
        url = f"{self.registry_url}/{encoded_name}"

        response = self.session.put(url, json=metadata)

        if response.status_code == 200:
            logger.info(f"Package {package_name} published successfully")
        elif response.status_code == 409:
            logger.warning(f"Package {package_name} version already exists")
        else:
            response.raise_for_status()

    def check_package_exists(self, package_name: str, version: str) -> bool:
        """Check if a package version already exists in the registry."""
        encoded_name = package_name.replace("/", "%2F")
        url = f"{self.registry_url}/{encoded_name}/{version}"

        response = self.session.get(url)
        return response.status_code == 200

    def get_package_info(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Get package information from the registry."""
        encoded_name = package_name.replace("/", "%2F")
        url = f"{self.registry_url}/{encoded_name}"

        response = self.session.get(url)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            response.raise_for_status()
            return None
