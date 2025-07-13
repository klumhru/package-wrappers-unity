"""Unity file generation utilities."""

import json
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from jinja2 import Environment, FileSystemLoader
import logging

if TYPE_CHECKING:
    from .config_manager import ConfigManager

logger = logging.getLogger(__name__)


class UnityGenerator:
    """Generates Unity-specific files for packages."""

    def __init__(
        self, templates_dir: Path, config: Optional["ConfigManager"] = None
    ):
        """Initialize with templates directory and optional configuration."""
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.config = config

        # Create Jinja2 environment for templates
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_package_json(
        self,
        name: str,
        display_name: str,
        version: str,
        description: str,
        author: str,
        namespace: Optional[str] = None,
        dependencies: Optional[Dict[str, str]] = None,
        keywords: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate Unity package.json content."""
        package_json: Dict[str, Any] = {
            "name": name,
            "displayName": display_name,
            "version": version,
            "description": description,
            "author": author,
            "unity": "2019.4",
            "unityRelease": "0f1",
            "keywords": keywords or [],
            "dependencies": dependencies or {},
            "type": "library",
        }

        # Add optional fields
        if namespace:
            package_json["namespace"] = namespace

        # Add any additional fields
        package_json.update(kwargs)

        return package_json

    def write_package_json(
        self, package_dir: Path, package_json: Dict[str, Any]
    ) -> None:
        """Write package.json file to package directory."""
        package_json_path = package_dir / "package.json"

        with open(package_json_path, "w", encoding="utf-8") as f:
            json.dump(package_json, f, indent=2, ensure_ascii=False)

        logger.info(f"Generated package.json at {package_json_path}")

    def generate_assembly_definition(
        self,
        name: str,
        namespace: str,
        references: Optional[List[str]] = None,
        define_constraints: Optional[List[str]] = None,
        version_defines: Optional[List[Dict[str, str]]] = None,
        platforms: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate Unity assembly definition content."""
        asmdef: Dict[str, Any] = {
            "name": name,
            "rootNamespace": namespace,
            "references": references or [],
            "includePlatforms": platforms or [],
            "excludePlatforms": [],
            "allowUnsafeCode": False,
            "overrideReferences": False,
            "precompiledReferences": [],
            "autoReferenced": True,
            "defineConstraints": define_constraints or [],
            "versionDefines": version_defines or [],
            "noEngineReferences": False,
        }

        # Add any additional fields
        asmdef.update(kwargs)

        return asmdef

    def write_assembly_definition(
        self,
        runtime_dir: Path,
        asmdef_name: str,
        asmdef_content: Dict[str, Any],
    ) -> None:
        """Write assembly definition file to Runtime directory."""
        asmdef_path = runtime_dir / f"{asmdef_name}.asmdef"

        with open(asmdef_path, "w", encoding="utf-8") as f:
            json.dump(asmdef_content, f, indent=2, ensure_ascii=False)

        logger.info(f"Generated assembly definition at {asmdef_path}")

    def generate_meta_file(
        self, file_path: Path, file_type: str = "DefaultAsset"
    ) -> str:
        """Generate Unity .meta file content."""
        guid = str(uuid.uuid4()).replace("-", "")

        meta_content: Dict[str, Any] = {
            "fileFormatVersion": 2,
            "guid": guid,
            "importer": file_type,
            "externalObjects": {},
            "userData": "",
            "assetBundleName": "",
            "assetBundleVariant": "",
        }

        # Special handling for different file types
        if file_path.suffix == ".cs":
            meta_content["importer"] = "MonoImporter"
            meta_content["executionOrder"] = 0
            meta_content["icon"] = "{instanceID: 0}"
            meta_content["serializedVersion"] = 2
            meta_content["defaultReferences"] = []

        elif file_path.suffix == ".asmdef":
            meta_content["importer"] = "AssemblyDefinitionImporter"

        elif file_path.is_dir():
            meta_content["importer"] = "DefaultImporter"
            meta_content["folderAsset"] = "yes"

        return f"fileFormatVersion: 2\\nguid: {guid}\\n"

    def write_meta_file(
        self, file_path: Path, file_type: str = "DefaultAsset"
    ) -> None:
        """Write .meta file for a given file or directory."""
        meta_path = Path(str(file_path) + ".meta")
        meta_content = self.generate_meta_file(file_path, file_type)

        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(meta_content)

        logger.info(f"Generated meta file at {meta_path}")

    def generate_all_meta_files(self, package_dir: Path) -> None:
        """Generate .meta files for all files and directories in package."""
        for root, dirs, files in os.walk(package_dir):
            root_path = Path(root)

            # Generate meta files for directories
            for dir_name in dirs:
                dir_path = root_path / dir_name
                if not (dir_path.parent / f"{dir_name}.meta").exists():
                    self.write_meta_file(dir_path, "DefaultImporter")

            # Generate meta files for files
            for file_name in files:
                file_path = root_path / file_name
                if (
                    not file_name.endswith(".meta")
                    and not (file_path.parent / f"{file_name}.meta").exists()
                ):
                    file_type = self._get_file_type(file_path)
                    self.write_meta_file(file_path, file_type)

    def _get_file_type(self, file_path: Path) -> str:
        """Determine Unity importer type based on file extension."""
        suffix = file_path.suffix.lower()

        type_mapping = {
            ".cs": "MonoImporter",
            ".asmdef": "AssemblyDefinitionImporter",
            ".json": "TextAssetImporter",
            ".txt": "TextAssetImporter",
            ".md": "TextAssetImporter",
            ".xml": "TextAssetImporter",
            ".yaml": "TextAssetImporter",
            ".yml": "TextAssetImporter",
        }

        return type_mapping.get(suffix, "DefaultAsset")

    def organize_runtime_structure(
        self, source_dir: Path, package_dir: Path
    ) -> Path:
        """Organize files into Unity package structure with Runtime folder."""
        runtime_dir = package_dir / "Runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        # Copy all source files to Runtime directory
        import shutil

        if source_dir.exists():
            for item in source_dir.iterdir():
                if item.is_file():
                    shutil.copy2(item, runtime_dir)
                elif item.is_dir():
                    shutil.copytree(
                        item, runtime_dir / item.name, dirs_exist_ok=True
                    )

        # Remove C# project files that aren't needed in Unity
        if self._should_remove_csharp_project_files():
            self._remove_csharp_project_files(runtime_dir)

        logger.info(
            f"Organized source files into Runtime structure at {runtime_dir}"
        )
        return runtime_dir

    def _should_remove_csharp_project_files(self) -> bool:
        """Check if C# project files should be removed based on configuration."""
        if not self.config:
            return True  # Default to removing project files

        build_settings = self.config.get_build_settings()
        return bool(build_settings.get("remove_csharp_project_files", True))

    def _remove_csharp_project_files(self, directory: Path) -> None:
        """Remove C# project files that aren't needed in Unity packages."""
        import shutil

        # Define C# project file extensions to remove
        csharp_project_extensions = [
            ".csproj",  # C# project files
            ".sln",  # Visual Studio solution files
            ".vcxproj",  # Visual C++ project files
            ".vcxproj.filters",  # Visual C++ project filters
            ".vcxproj.user",  # Visual C++ user settings
            ".suo",  # Visual Studio solution user options
            ".user",  # User-specific project settings
            ".vs",  # Visual Studio folder
            ".vscode",  # VS Code settings folder
            ".idea",  # JetBrains IDE settings folder
        ]

        # Define C# project file names to remove
        csharp_project_files = [
            "packages.config",  # NuGet packages config
            "app.config",  # Application configuration
            "web.config",  # Web application configuration
            "AssemblyInfo.cs",  # Assembly info (Unity generates its own)
            "GlobalAssemblyInfo.cs",  # Global assembly info
            "Directory.Build.props",  # MSBuild directory props
            "Directory.Build.targets",  # MSBuild directory targets
            ".editorconfig",  # Editor configuration
            ".gitignore",  # Git ignore (not needed in packages)
            ".gitattributes",  # Git attributes
            "README.md",  # Documentation (package.json has description)
            "LICENSE",  # License (package.json has license field)
            "CHANGELOG.md",  # Changelog
            "CONTRIBUTING.md",  # Contributing guidelines
        ]

        files_removed = 0

        # Remove files by extension
        for ext in csharp_project_extensions:
            for file_path in directory.rglob(f"*{ext}"):
                if file_path.is_file():
                    file_path.unlink()
                    logger.debug(
                        f"Removed C# project file: {file_path.relative_to(directory)}"
                    )
                    files_removed += 1
                elif file_path.is_dir() and ext.startswith("."):
                    # Remove directories like .vs, .vscode, .idea
                    shutil.rmtree(file_path)
                    logger.debug(
                        f"Removed C# project directory: {file_path.relative_to(directory)}"
                    )
                    files_removed += 1

        # Remove files by name
        for filename in csharp_project_files:
            for file_path in directory.rglob(filename):
                if file_path.is_file():
                    file_path.unlink()
                    logger.debug(
                        f"Removed C# project file: {file_path.relative_to(directory)}"
                    )
                    files_removed += 1

        if files_removed > 0:
            logger.info(
                f"Removed {files_removed} C# project files from Unity package"
            )
