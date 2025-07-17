"""NuGet package manager for Unity package wrapper."""

import logging
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List
import xml.etree.ElementTree as ET
import requests

logger = logging.getLogger(__name__)


class NuGetManager:
    """Manages NuGet package operations."""

    def __init__(self, work_dir: Path):
        """Initialize NuGetManager with working directory."""
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def download_package(
        self,
        package_id: str,
        version: str,
        framework: str = "netstandard2.0",
    ) -> Path:
        """
        Download a NuGet package and extract its contents.

        Args:
            package_id: The NuGet package ID (e.g., "System.IO.Pipelines")
            version: The package version
            framework: Target framework folder (default: "netstandard2.0")

        Returns:
            Path to the extracted package directory
        """
        logger.info(f"Downloading NuGet package: {package_id} v{version}")

        # Create package-specific work directory
        package_dir = self.work_dir / f"nuget_{package_id}_{version}"
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir(parents=True)

        # Download package using NuGet API
        return self._download_package_from_nuget_api(
            package_id, version, framework, package_dir
        )

    def _download_package_from_nuget_api(
        self,
        package_id: str,
        version: str,
        framework: str,
        package_dir: Path,
    ) -> Path:
        """Download NuGet package using the NuGet API."""
        # Try multiple NuGet API endpoints
        api_urls = [
            f"https://www.nuget.org/api/v2/package/{package_id}/{version}",
            f"https://api.nuget.org/v3-flatcontainer/{package_id.lower()}/"
            f"{version}/{package_id.lower()}.{version}.nupkg",
        ]

        logger.info(f"Downloading {package_id} v{version} from NuGet API")

        nupkg_path = package_dir / f"{package_id}.{version}.nupkg"

        for api_url in api_urls:
            try:
                logger.debug(f"Trying URL: {api_url}")
                response = requests.get(api_url, timeout=30)
                response.raise_for_status()

                # Write the package content to file
                with open(nupkg_path, "wb") as f:
                    f.write(response.content)

                logger.info(f"Successfully downloaded {package_id} v{version}")
                break

            except requests.exceptions.RequestException as e:
                logger.debug(f"Failed to download from {api_url}: {e}")
                continue
        else:
            # If all URLs failed
            raise FileNotFoundError(
                f"Failed to download {package_id} "
                f"v{version} from all NuGet API endpoints"
            )

        # Extract the nupkg (it's a zip file)
        extract_dir = package_dir / f"{package_id}.{version}"
        try:
            with zipfile.ZipFile(nupkg_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
        except zipfile.BadZipFile as e:
            raise FileNotFoundError(
                f"Downloaded package {package_id} v{version} is "
                f"not a valid zip file: {e}"
            )

        return extract_dir

    def extract_dlls(
        self, package_path: Path, framework: str = "netstandard2.0"
    ) -> List[Path]:
        """
        Extract DLL files from a NuGet package for the specified framework.

        Args:
            package_path: Path to the extracted NuGet package
            framework: Target framework folder (default: "netstandard2.0")

        Returns:
            List of paths to extracted DLL files
        """
        logger.info(f"Extracting DLLs for framework: {framework}")

        dll_files: List[Path] = []

        # Common framework folder patterns
        framework_patterns = [
            f"lib/{framework}",
            f"lib/{framework.replace('.', '')}",
            "lib/netstandard2.0",  # fallback
            "lib/netstandard20",  # fallback
            "lib/net6.0",  # fallback
            "lib/net5.0",  # fallback
            "lib/netcoreapp3.1",  # fallback
            "lib",  # last resort
        ]

        # Try each pattern
        for pattern in framework_patterns:
            framework_dir = package_path / pattern
            if framework_dir.exists():
                logger.info(f"Found framework directory: {framework_dir}")

                # Find all DLL files in this directory
                for dll_file in framework_dir.glob("*.dll"):
                    dll_files.append(dll_file)
                    logger.debug(f"Found DLL: {dll_file}")

                # If we found DLLs, use this directory
                if dll_files:
                    break

        if not dll_files:
            logger.warning(
                f"No DLL files found for framework {framework} in "
                f"{package_path}"
            )

            # List available lib folders for debugging
            lib_dir = package_path / "lib"
            if lib_dir.exists():
                available_frameworks = [
                    f.name for f in lib_dir.iterdir() if f.is_dir()
                ]
                logger.info(f"Available frameworks: {available_frameworks}")

        return dll_files

    def get_package_dependencies(
        self, package_path: Path
    ) -> List[Dict[str, str]]:
        """
        Extract package dependencies from the nuspec file.

        Args:
            package_path: Path to the extracted NuGet package

        Returns:
            List of dependency dictionaries with 'id' and 'version' keys
        """
        dependencies: List[Dict[str, str]] = []

        # Find the nuspec file
        nuspec_files = list(package_path.glob("*.nuspec"))
        if not nuspec_files:
            logger.warning(f"No nuspec file found in {package_path}")
            return dependencies

        nuspec_file = nuspec_files[0]
        logger.debug(f"Reading dependencies from: {nuspec_file}")

        try:
            tree = ET.parse(nuspec_file)
            root = tree.getroot()

            # Handle XML namespace
            namespace = {
                "": "http://schemas.microsoft.com/packaging/2010/07/nuspec.xsd"
            }

            # Find dependencies
            deps = root.findall(".//dependency", namespace)
            for dep in deps:
                dep_id = dep.get("id")
                dep_version = dep.get("version")
                if dep_id and dep_version:
                    dependencies.append({"id": dep_id, "version": dep_version})
                    logger.debug(f"Found dependency: {dep_id} v{dep_version}")

        except Exception as e:
            logger.warning(f"Failed to parse nuspec file: {e}")

        return dependencies

    def cleanup(self) -> None:
        """Clean up temporary files."""
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)
            logger.info("NuGet temporary files cleaned up")
