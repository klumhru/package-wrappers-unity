"""Main package builder orchestrating the Unity package creation process."""

import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any

from .git_manager import GitManager
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

        # Set up Unity file generator
        templates_dir = self.config.get_templates_dir()
        self.unity_generator = UnityGenerator(templates_dir, self.config)

    def build_package(self, package_name: str) -> Path:
        """Build a single Unity package."""
        logger.info(f"Building package: {package_name}")

        # Get package configuration
        package_config = self.config.get_package_config(package_name)
        if not package_config:
            raise ValueError(
                f"Package configuration not found: {package_name}"
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

        # Generate all meta files
        self.unity_generator.generate_all_meta_files(package_output_dir)

        logger.info(
            f"Package '{package_name}' success: at {package_output_dir}"
        )
        return package_output_dir

    def build_all_packages(self) -> List[Path]:
        """Build all configured packages."""
        package_names = self.config.get_package_names()
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
        package_names = self.config.get_package_names()

        for package_name in package_names:
            package_config = self.config.get_package_config(package_name)
            if package_config is None:
                continue

            source_config = package_config["source"]

            # Check if repository exists and if ref has changed
            repo_path = self.work_dir / package_name
            if repo_path.exists():
                current_info = self.git_manager.get_repo_info(package_name)
                if (
                    current_info
                    and current_info["ref"] != source_config["ref"]
                ):
                    updated_packages.append(package_name)
                    logger.info(
                        f"Package '{package_name}' needs update:"
                        f" {current_info['ref']} ->"
                        f" {source_config['ref']}"
                    )
            else:
                # Repository doesn't exist, needs to be built
                updated_packages.append(package_name)

        return updated_packages

    def _generate_package_json(
        self, package_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate package.json content from package configuration."""
        return self.unity_generator.generate_package_json(
            name=package_config["name"],
            display_name=package_config.get(
                "display_name", package_config["name"]
            ),
            version=package_config.get("version", "1.0.0"),
            description=package_config.get("description", ""),
            author=package_config.get("author", ""),
            namespace=package_config.get("namespace"),
            dependencies=package_config.get("dependencies", {}),
            keywords=package_config.get("keywords", []),
            **package_config.get("package_json_extra", {}),
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

    def cleanup(self) -> None:
        """Clean up temporary files and repositories."""
        self.git_manager.cleanup()
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
