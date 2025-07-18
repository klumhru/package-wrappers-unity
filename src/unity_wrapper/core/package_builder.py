"""Main package builder orchestrating the Unity package creation process."""

import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any

from .git_manager import GitManager
from .nuget_manager import NuGetManager
from .unity_generator import UnityGenerator
from .config_manager import ConfigManager


logger = logging.getLogger(__name__)


class PackageBuilder:
    """Main orchestrator for building Unity OSS Packages."""

    def __init__(
        self,
        config_path: Path,
        output_dir: Path,
        work_dir: Optional[Path] = None,
    ):
        """Initialize PackageBuilder with configuration and output folders."""
        self.config = ConfigManager(config_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Set up working directory for git operations
        self.work_dir = work_dir or (Path.cwd() / ".unity_wrapper_temp")
        self.git_manager = GitManager(self.work_dir)

        # Set up NuGet manager
        self.nuget_manager = NuGetManager(self.work_dir / "nuget")

        # Set up Unity file generator
        templates_dir = self.config.get_templates_dir()
        self.unity_generator = UnityGenerator(templates_dir, self.config)

    def build_package(self, package_name: str) -> Path:
        """Build a single Unity package."""
        logger.info(f"Building package: {package_name}")

        # Determine package type and get configuration
        package_type = self.config.get_package_type(package_name)

        if package_type == "git":
            return self._build_git_package(package_name)
        elif package_type == "nuget":
            return self._build_nuget_package(package_name)
        else:
            raise ValueError(
                f"Package configuration not found: {package_name}"
            )

    def _build_git_package(self, package_name: str) -> Path:
        """Build a Unity package from a Git repository."""
        package_config = self.config.get_package_config(package_name)
        if not package_config:
            raise ValueError(
                f"Git package configuration not found: {package_name}"
            )

        # Extract source configuration
        source_config = package_config["source"]
        extract_path = package_config.get("extract_path", ".")

        # Clone or update repository
        repo_path = self.git_manager.clone_or_update(
            url=source_config["url"],
            ref=source_config["ref"],
            name=package_name,
        )

        # Create package output directory
        package_output_dir = self.output_dir / package_name
        if package_output_dir.exists():
            shutil.rmtree(package_output_dir)
        package_output_dir.mkdir(parents=True)

        # Extract specified folder from repository
        source_dir = repo_path / extract_path
        if not source_dir.exists():
            raise FileNotFoundError(
                f"Extract path '{extract_path}' not found in repository"
            )

        # Organize into Unity package structure
        runtime_dir = self.unity_generator.organize_runtime_structure(
            source_dir, package_output_dir
        )

        # Generate package.json
        package_json_content = self._generate_package_json(package_config)
        self.unity_generator.write_package_json(
            package_output_dir, package_json_content
        )

        # Generate assembly definition if namespace is specified
        namespace = package_config.get("namespace")
        if namespace:
            asmdef_name = package_config.get(
                "asmdef_name", package_name.replace(".", "_")
            )
            asmdef_content = self._generate_assembly_definition(package_config)
            self.unity_generator.write_assembly_definition(
                runtime_dir, asmdef_name, asmdef_content
            )

        # Copy LICENSE file if available
        self._copy_license_file(repo_path, package_output_dir)

        # Generate README.md with disclaimer and original content
        self._generate_readme_file(
            repo_path, package_output_dir, package_config
        )

        # Generate all meta files (including for LICENSE and README if copied)
        self.unity_generator.generate_all_meta_files(package_output_dir)

        logger.info(
            f"Package '{package_name}' success: at {package_output_dir}"
        )
        return package_output_dir

    def _build_nuget_package(self, package_name: str) -> Path:
        """Build a Unity package from a NuGet package."""
        package_config = self.config.get_nuget_package_config(package_name)
        if not package_config:
            raise ValueError(
                f"NuGet package configuration not found: {package_name}"
            )

        # Extract NuGet package configuration
        nuget_id = package_config["nuget_id"]
        version = package_config["version"]
        framework = package_config.get("framework", "netstandard2.0")

        # Download NuGet package
        package_path = self.nuget_manager.download_package(
            nuget_id, version, framework
        )

        # Extract DLL files
        dll_files = self.nuget_manager.extract_dlls(package_path, framework)
        if not dll_files:
            raise FileNotFoundError(
                f"No DLL files found in NuGet package {nuget_id} v{version} "
                f"for framework {framework}"
            )

        # Create package output directory
        package_output_dir = self.output_dir / package_name
        if package_output_dir.exists():
            shutil.rmtree(package_output_dir)
        package_output_dir.mkdir(parents=True)

        # Organize DLLs into Plugins structure
        plugins_dir = self.unity_generator.organize_plugins_structure(
            dll_files, package_output_dir
        )

        # Generate package.json
        package_json_content = self._generate_package_json(package_config)
        self.unity_generator.write_package_json(
            package_output_dir, package_json_content
        )

        # Generate meta files for DLLs (no asmdef for NuGet packages)
        self.unity_generator.generate_dll_meta_files(plugins_dir)

        # Copy LICENSE file if available from NuGet package
        self._copy_nuget_license_file(package_path, package_output_dir)

        # Generate README.md with disclaimer
        # (NuGet packages typically don't have README in package)
        self._generate_readme_file(
            package_path, package_output_dir, package_config
        )

        # Generate meta files for directories
        # (including for LICENSE and README if copied)
        self.unity_generator.generate_all_meta_files(package_output_dir)

        logger.info(
            f"Package '{package_name}' success: at {package_output_dir}"
        )
        return package_output_dir

    def build_all_packages(self) -> List[Path]:
        """Build all configured packages."""
        package_names = self.config.get_all_package_names()
        built_packages: List[Path] = []

        for package_name in package_names:
            try:
                package_path = self.build_package(package_name)
                built_packages.append(package_path)
            except Exception as e:
                logger.error(f"Failed to build package '{package_name}': {e}")
                raise

        logger.info(f"Successfully built {len(built_packages)} packages")
        return built_packages

    def check_for_updates(self) -> List[str]:
        """Check which packages need updates based on ref changes."""
        updated_packages: List[str] = []
        package_names = self.config.get_all_package_names()

        for package_name in package_names:
            package_type = self.config.get_package_type(package_name)

            if package_type == "git":
                if self._check_git_package_updates(package_name):
                    updated_packages.append(package_name)
            elif package_type == "nuget":
                # For NuGet packages, we'll assume they need updates
                # In the future, we could check for new versions
                updated_packages.append(package_name)
                logger.info(
                    f"NuGet package '{package_name}' marked for update"
                )

        return updated_packages

    def _check_git_package_updates(self, package_name: str) -> bool:
        """Check if a Git package needs updates."""
        package_config = self.config.get_package_config(package_name)
        if package_config is None:
            return False

        source_config = package_config["source"]

        # Check if repository exists and if ref has changed
        repo_path = self.work_dir / package_name
        if repo_path.exists():
            current_info = self.git_manager.get_repo_info(package_name)
            if current_info and current_info["ref"] != source_config["ref"]:
                logger.info(
                    f"Package '{package_name}' needs update:"
                    f" {current_info['ref']} ->"
                    f" {source_config['ref']}"
                )
                return True
        else:
            # Repository doesn't exist, needs to be built
            return True

        return False

    def _generate_package_json(
        self, package_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate package.json content from package configuration."""
        # Get defaults from settings
        defaults = self.config.get_global_settings().get("defaults", {})
        github_settings = self.config.get_github_settings()

        # Handle author field - can be string or object
        author = package_config.get("author", defaults.get("author", ""))

        # Generate publishConfig for GitHub Package Registry
        publish_config = {}
        github_owner = github_settings.get("owner")
        if github_owner:
            publish_config = {
                "publishConfig": {
                    "registry": f"https://npm.pkg.github.com/@{github_owner}"
                }
            }

        # Merge package_json_extra with publishConfig
        extra_config = package_config.get("package_json_extra", {})
        extra_config.update(publish_config)

        return self.unity_generator.generate_package_json(
            name=package_config["name"],
            display_name=package_config.get(
                "display_name", package_config["name"]
            ),
            version=package_config.get("version", "1.0.0"),
            description=package_config.get("description", ""),
            author=author,
            namespace=package_config.get("namespace"),
            dependencies=package_config.get("dependencies", {}),
            keywords=package_config.get("keywords", []),
            **extra_config,
        )

    def _generate_assembly_definition(
        self, package_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate assembly definition content from package configuration."""
        asmdef_name = package_config.get(
            "asmdef_name", package_config["name"].replace(".", "_")
        )
        namespace = package_config["namespace"]

        return self.unity_generator.generate_assembly_definition(
            name=asmdef_name,
            namespace=namespace,
            references=package_config.get("assembly_references", []),
            define_constraints=package_config.get("define_constraints", []),
            version_defines=package_config.get("version_defines", []),
            platforms=package_config.get("platforms", []),
            **package_config.get("asmdef_extra", {}),
        )

    def _copy_license_file(
        self, source_dir: Path, package_output_dir: Path
    ) -> None:
        """
        Copy LICENSE file from source repository to package root if available.
        """
        # Common LICENSE file names to look for
        license_names = [
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
            "License",
            "License.txt",
            "License.md",
            "license",
            "license.txt",
            "license.md",
            "COPYING",
            "COPYING.txt",
            "COPYRIGHT",
            "COPYRIGHT.txt",
        ]

        license_file_found = None

        # Search for LICENSE file in the source directory
        for license_name in license_names:
            license_path = source_dir / license_name
            if license_path.exists() and license_path.is_file():
                license_file_found = license_path
                logger.info(f"Found LICENSE file: {license_name}")
                break

        if license_file_found:
            # Copy LICENSE file to package root
            dest_license_path = package_output_dir / "LICENSE"
            try:
                shutil.copy2(license_file_found, dest_license_path)
                logger.info(
                    f"Copied LICENSE file to package: {dest_license_path}"
                )

            except Exception as e:
                logger.warning(f"Failed to copy LICENSE file: {e}")
        else:
            logger.info("No LICENSE file found in source repository")

    def _copy_nuget_license_file(
        self, nuget_package_path: Path, package_output_dir: Path
    ) -> None:
        """
        Copy LICENSE file from NuGet package to package root if available.
        """
        # Common LICENSE file names to look for in NuGet packages
        license_names = [
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
            "License",
            "License.txt",
            "License.md",
            "license",
            "license.txt",
            "license.md",
            "COPYING",
            "COPYING.txt",
            "COPYRIGHT",
            "COPYRIGHT.txt",
        ]

        license_file_found = None

        # Search for LICENSE file in the NuGet package directory
        for license_name in license_names:
            license_path = nuget_package_path / license_name
            if license_path.exists() and license_path.is_file():
                license_file_found = license_path
                logger.info(
                    f"Found LICENSE file in NuGet package: {license_name}"
                )
                break

        if license_file_found:
            # Copy LICENSE file to package root
            dest_license_path = package_output_dir / "LICENSE"
            try:
                shutil.copy2(license_file_found, dest_license_path)
                logger.info(
                    f"Copied LICENSE file to package: {dest_license_path}"
                )

            except Exception as e:
                logger.warning(
                    f"Failed to copy LICENSE file from NuGet package: {e}"
                )
        else:
            logger.info("No LICENSE file found in NuGet package")

    def _generate_readme_file(
        self,
        source_dir: Path,
        package_output_dir: Path,
        package_config: Dict[str, Any],
    ) -> None:
        """Generate README.md file with disclaimer
        and original content if available."""
        readme_content: List[str] = []

        # Generate disclaimer header
        package_name = package_config["name"]
        display_name = package_config.get("display_name", package_name)
        source_config = package_config.get("source", {})
        source_url = source_config.get("url", "")

        # Extract organization/author from source URL or use generic
        author_name = "the original package author"
        if "github.com" in source_url:
            # Extract GitHub organization/user
            url_parts = (
                source_url.replace("https://github.com/", "")
                .replace(".git", "")
                .split("/")
            )
            if len(url_parts) >= 1:
                org_name = url_parts[0]
                # Common organizations that should be mentioned specifically
                if org_name.lower() in [
                    "microsoft",
                    "google",
                    "facebook",
                    "meta",
                    "apple",
                    "oracle",
                    "ibm",
                    "amazon",
                    "aws",
                ]:
                    author_name = org_name.title()
                else:
                    author_name = f"the {org_name} organization"

        # Create disclaimer
        disclaimer = f"""# {display_name}

> **⚠️ IMPORTANT DISCLAIMER ⚠️**
>
> This Unity package is a community-created wrapper and is **NOT officially \n
> affiliated with, endorsed by, or supported by {author_name}**.
>
> - The wrapper author has **no affiliation** with {author_name}
> - This package is provided **as-is** for Unity developers' convenience
> - For official support, please refer to the original repository
> - Use at your own risk in production environments

---

"""

        readme_content.append(disclaimer)

        # Look for original README files
        readme_names = [
            "README.md",
            "README.MD",
            "Readme.md",
            "readme.md",
            "README.txt",
            "README.rst",
            "README",
            "readme",
        ]

        original_readme_found = None
        original_readme_content = ""

        # Search for README file in the source directory
        for readme_name in readme_names:
            readme_path = source_dir / readme_name
            if readme_path.exists() and readme_path.is_file():
                original_readme_found = readme_path
                logger.info(f"Found original README file: {readme_name}")
                break

        if original_readme_found:
            try:
                # Try to read as UTF-8, fallback to latin-1 if needed
                try:
                    original_readme_content = original_readme_found.read_text(
                        encoding="utf-8"
                    )
                except UnicodeDecodeError:
                    original_readme_content = original_readme_found.read_text(
                        encoding="latin-1"
                    )

                readme_content.append("## Original Package Documentation\n\n")
                readme_content.append(original_readme_content)
                logger.info(
                    "Included original README content in package README"
                )

            except Exception as e:
                logger.warning(f"Failed to read original README file: {e}")
                readme_content.append("## Original Package Documentation\n\n")
                readme_content.append(
                    "*Original README content could not be included due "
                    "to encoding issues.*\n"
                )
        else:
            logger.info("No original README file found in source repository")
            readme_content.append("## Package Information\n\n")
            readme_content.append(
                f"This package wraps functionality from: {source_url}\n\n"
            )
            readme_content.append(
                "Please refer to the original repository for documentation "
                "and usage examples.\n"
            )

        # Add Unity-specific information
        readme_content.append("\n---\n\n## Unity Package Information\n\n")
        readme_content.append(f"- **Package Name**: `{package_name}`\n")
        if package_config.get("version"):
            readme_content.append(
                f"- **Version**: {package_config['version']}\n"
            )
        if package_config.get("namespace"):
            readme_content.append(
                f"- **Namespace**: `{package_config['namespace']}`\n"
            )
        if source_url:
            readme_content.append(f"- **Original Source**: {source_url}\n")

        # Write README.md file
        readme_file_path = package_output_dir / "README.md"
        try:
            with open(readme_file_path, "w", encoding="utf-8") as f:
                f.write("".join(readme_content))
            logger.info(f"Generated README.md at {readme_file_path}")

        except Exception as e:
            logger.warning(f"Failed to generate README.md file: {e}")

    def cleanup(self) -> None:
        """Clean up temporary files and repositories."""
        self.git_manager.cleanup()
        self.nuget_manager.cleanup()
        logger.info("PackageBuilder cleanup completed")

    def __enter__(self) -> "PackageBuilder":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Context manager exit."""
        self.cleanup()
