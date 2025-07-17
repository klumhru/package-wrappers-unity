"""Configuration management for Unity package wrapper."""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, cast


logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration for Unity package wrapper."""

    def __init__(self, config_path: Path):
        """Initialize ConfigManager with configuration file path."""
        self.config_path = Path(config_path)
        self.config_data: Dict[str, Any] = {}
        self.packages_config: Dict[str, Any] = {}
        self.settings_config: Dict[str, Any] = {}

        self.load_configuration()

    def load_configuration(self) -> None:
        """Load configuration from YAML files."""
        # Load main packages configuration
        packages_file = self.config_path / "packages.yaml"
        if packages_file.exists():
            with open(packages_file, "r", encoding="utf-8") as f:
                self.packages_config = yaml.safe_load(f) or {}
        else:
            logger.warning(
                f"Packages configuration file not found: {packages_file}"
            )
            self.packages_config = {"packages": []}

        # Load settings configuration
        settings_file = self.config_path / "settings.yaml"
        if settings_file.exists():
            with open(settings_file, "r", encoding="utf-8") as f:
                self.settings_config = yaml.safe_load(f) or {}
        else:
            logger.warning(
                f"Settings configuration file not found: {settings_file}"
            )
            self.settings_config = {}

        logger.info("Configuration loaded successfully")

    def get_package_config(
        self, package_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific package."""
        packages = self.packages_config.get("packages", [])

        for package in packages:
            if package.get("name") == package_name:
                return cast(Dict[str, Any], package)

        return None

    def get_nuget_package_config(
        self, package_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific NuGet package."""
        nuget_packages = self.packages_config.get("nuget_packages", [])

        for package in nuget_packages:
            if package.get("name") == package_name:
                return cast(Dict[str, Any], package)

        return None

    def get_package_names(self) -> List[str]:
        """Get list of all configured package names."""
        packages = self.packages_config.get("packages", [])
        return [
            package.get("name") for package in packages if package.get("name")
        ]

    def get_all_package_names(self) -> List[str]:
        """Get list of all configured package names (both Git and NuGet)."""
        git_packages = self.packages_config.get("packages", [])
        nuget_packages = self.packages_config.get("nuget_packages", [])

        all_names: List[str] = []

        # Add Git packages
        for package in git_packages:
            name = package.get("name")
            if name:
                all_names.append(name)

        # Add NuGet packages
        for package in nuget_packages:
            name = package.get("name")
            if name:
                all_names.append(name)

        return all_names

    def get_package_type(self, package_name: str) -> str:
        """Get the type of package (git or nuget)."""
        if self.get_package_config(package_name):
            return "git"
        elif self.get_nuget_package_config(package_name):
            return "nuget"
        else:
            return "unknown"

    def get_templates_dir(self) -> Path:
        """Get templates directory path."""
        templates_dir = self.settings_config.get("templates_dir", "templates")
        if Path(templates_dir).is_absolute():
            return Path(cast(str, templates_dir))
        else:
            return self.config_path.parent / cast(str, templates_dir)

    def get_output_dir(self) -> Path:
        """Get output directory path."""
        output_dir = self.settings_config.get("output_dir", "packages")
        if Path(output_dir).is_absolute():
            return Path(cast(str, output_dir))
        else:
            return self.config_path.parent / cast(str, output_dir)

    def get_work_dir(self) -> Path:
        """Get working directory path for temporary files."""
        work_dir = self.settings_config.get("work_dir", ".unity_wrapper_temp")
        if Path(work_dir).is_absolute():
            return Path(cast(str, work_dir))
        else:
            return self.config_path.parent / cast(str, work_dir)

    def get_github_settings(self) -> Dict[str, Any]:
        """Get GitHub publishing settings."""
        return cast(Dict[str, Any], self.settings_config.get("github", {}))

    def get_global_settings(self) -> Dict[str, Any]:
        """Get global settings."""
        return self.settings_config

    def get_build_settings(self) -> Dict[str, Any]:
        """Get build settings."""
        return cast(Dict[str, Any], self.settings_config.get("build", {}))

    def add_package(self, package_config: Dict[str, Any]) -> None:
        """Add a new package configuration."""
        if "packages" not in self.packages_config:
            self.packages_config["packages"] = []

        packages_list = cast(
            List[Dict[str, Any]], self.packages_config["packages"]
        )
        packages_list.append(package_config)

    def remove_package(self, package_name: str) -> bool:
        """Remove a package configuration."""
        packages = self.packages_config.get("packages", [])

        for i, package in enumerate(packages):
            if package.get("name") == package_name:
                del packages[i]
                return True

        return False

    def save_configuration(self) -> None:
        """Save configuration back to YAML files."""
        # Save packages configuration
        packages_file = self.config_path / "packages.yaml"
        with open(packages_file, "w", encoding="utf-8") as f:
            yaml.dump(
                self.packages_config, f, default_flow_style=False, indent=2
            )

        # Save settings configuration
        settings_file = self.config_path / "settings.yaml"
        with open(settings_file, "w", encoding="utf-8") as f:
            yaml.dump(
                self.settings_config, f, default_flow_style=False, indent=2
            )

        logger.info("Configuration saved successfully")
