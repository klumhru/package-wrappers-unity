"""Static npm registry generator for GitHub Pages.

Generates unscoped packument JSON files that can be served by any
static file host (e.g. GitHub Pages) as a UPM-compatible npm registry.

The problem this solves
-----------------------
GitHub Packages always returns a *scoped* package name in its packument
responses (e.g. ``@klumhru/com.foo.bar``).  Unity Package Manager
(UPM) requires *unscoped* names (e.g. ``com.foo.bar``) and fails to
resolve packages whose packument ``name`` field contains a ``@scope/``
prefix.

By generating static packument files with the correct unscoped name
and hosting them on GitHub Pages, UPM can resolve packages normally.
The tarball download URLs still point to GitHub Packages, so the
existing ``.upmconfig.toml`` token is reused for auth.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PagesPublisher:
    """Generates static npm packument files for a GitHub Pages registry.

    Each package gets a single JSON file at
    ``{registry_dir}/{package_name}`` (no file extension) following the
    npm packument
    format.  Multiple versions accumulate in the same file; the
    ``dist-tags.latest`` tag always points to the most-recently-added
    version.

    Example usage::

        pub = PagesPublisher()
        pub.update_registry(
            registry_dir=Path("dist/registry"),
            unscoped_name="com.foo.bar",
            version="1.2.3",
            version_meta={...},           # npm version object
            tarball_url="https://...",
            shasum="abc123",
            integrity="sha512-...",
        )
    """

    def update_registry(
        self,
        registry_dir: Path,
        unscoped_name: str,
        version: str,
        version_meta: Dict[str, Any],
        tarball_url: str,
        shasum: str,
        integrity: str,
        description: Optional[str] = None,
    ) -> Path:
        """Create or update the static packument file for a package.

        If the file already exists, the new version is merged into the
        existing packument and ``dist-tags.latest`` is updated.

        Args:
            registry_dir: Directory where packument JSON files are stored.
            unscoped_name: Unscoped UPM package name (e.g.
                ``com.foo.bar``).
            version: Semver version string (e.g. ``1.2.3``).
            version_meta: npm version metadata dict to embed under the
                version key.  The ``name`` field will be overwritten with
                ``unscoped_name``; ``dist`` will be set from the
                ``tarball_url``, ``shasum``, and ``integrity`` args.
            tarball_url: Publicly accessible (or auth-gated) tarball URL.
            shasum: SHA-1 hex digest of the tarball.
            integrity: SRI integrity string (e.g. ``sha512-...``).
            description: Optional human-readable description; used only
                when creating a new packument file.

        Returns:
            Path to the written packument JSON file.
        """
        registry_dir.mkdir(parents=True, exist_ok=True)
        packument_path = registry_dir / unscoped_name

        packument = self._load_or_create(
            packument_path, unscoped_name, description
        )

        version_entry: Dict[str, Any] = dict(version_meta)
        version_entry["name"] = unscoped_name
        version_entry["version"] = version
        version_entry["dist"] = {
            "tarball": tarball_url,
            "shasum": shasum,
            "integrity": integrity,
        }
        # Ensure the version entry name is never scoped.
        version_entry.pop("_id", None)

        packument["versions"][version] = version_entry
        packument["dist-tags"]["latest"] = version

        with open(packument_path, "w", encoding="utf-8") as f:
            json.dump(packument, f, indent=2, ensure_ascii=False)
            f.write("\n")

        logger.info(
            f"Updated static registry: {packument_path} "
            f"({unscoped_name}@{version})"
        )
        return packument_path

    def _load_or_create(
        self,
        packument_path: Path,
        unscoped_name: str,
        description: Optional[str],
    ) -> Dict[str, Any]:
        """Load an existing packument or create a new skeleton."""
        if packument_path.exists():
            with open(packument_path, encoding="utf-8") as f:
                existing: Dict[str, Any] = json.load(f)
            # Ensure the name is always unscoped, even if an older run
            # wrote a scoped name by mistake.
            existing["name"] = unscoped_name
            return existing

        return {
            "name": unscoped_name,
            "description": description or "",
            "dist-tags": {},
            "versions": {},
        }
