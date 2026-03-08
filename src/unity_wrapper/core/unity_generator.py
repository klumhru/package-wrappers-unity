"""Unity file generation utilities."""

import json
import os
import uuid
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING, Union
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
        author: Union[str, Dict[str, str]],
        namespace: Optional[str] = None,
        dependencies: Optional[Dict[str, str]] = None,
        keywords: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate Unity package.json content."""
        # UPM requires strict semver without a leading 'v' (e.g. '1.0.0',
        # not 'v1.0.0'). Strip any leading 'v' from git tag–style versions.
        normalized_version = version.lstrip("v")
        package_json: Dict[str, Any] = {
            "name": name,
            "displayName": display_name,
            "version": normalized_version,
            "description": description,
            "author": self._parse_author(author),
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

        elif file_path.suffix == ".dll":
            meta_content["importer"] = "PluginImporter"
            meta_content["platformData"] = []
            meta_content["userData"] = ""
            meta_content["assetBundleName"] = ""
            meta_content["assetBundleVariant"] = ""

        elif file_path.is_dir():
            meta_content["importer"] = "DefaultImporter"
            meta_content["folderAsset"] = "yes"

        # Use YAML to generate properly formatted meta file content
        return str(
            yaml.dump(
                meta_content,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        )

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
            ".dll": "PluginImporter",
            ".json": "TextAssetImporter",
            ".txt": "TextAssetImporter",
            ".md": "TextAssetImporter",
            ".xml": "TextAssetImporter",
            ".yaml": "TextAssetImporter",
            ".yml": "TextAssetImporter",
        }

        return type_mapping.get(suffix, "DefaultAsset")

    @staticmethod
    def _build_exclude_ignore(root: Path, exclude_paths: List[str]) -> Any:
        """Return a ``shutil.copytree`` ignore callable.

        Each entry in *exclude_paths* is matched against the name of each
        item being copied OR against its path relative to *root* (POSIX
        separators, no leading slash).  A trailing ``/`` in an entry is
        stripped before matching.

        Examples::

            exclude_paths=["External"]
            # skips Runtime/External/ wherever it appears

            exclude_paths=["External/TMP"]
            # skips only Runtime/External/TMP/
        """
        normalized = [p.rstrip("/").rstrip("\\") for p in exclude_paths]

        def _ignore(src: str, names: List[str]) -> set:
            src_path = Path(src)
            ignored: set = set()
            for name in names:
                rel = (src_path / name).relative_to(root)
                rel_str = rel.as_posix()
                for excl in normalized:
                    if (
                        name == excl
                        or rel_str == excl
                        or rel_str.startswith(excl + "/")
                    ):
                        ignored.add(name)
                        break
            return ignored

        return _ignore

    def organize_runtime_structure(
        self,
        source_dir: Path,
        package_dir: Path,
        exclude_paths: Optional[List[str]] = None,
    ) -> Path:
        """Organize files into Unity package structure with Runtime folder.

        Args:
            source_dir: Root of the extracted source tree.
            package_dir: Destination Unity package directory.
            exclude_paths: Optional list of paths (relative to the Runtime
                root) or directory names to exclude from the copy.  Trailing
                slashes are ignored.  For example ``["External"]`` will omit
                the ``Runtime/External/`` subtree entirely.
        """
        import shutil

        effective_excludes: List[str] = exclude_paths or []

        # Check if source directory already has a Runtime folder
        source_runtime_dir = source_dir / "Runtime"

        if source_runtime_dir.exists() and source_runtime_dir.is_dir():
            # If source already has Runtime folder, copy it directly
            runtime_dir = package_dir / "Runtime"

            if runtime_dir.exists():
                shutil.rmtree(runtime_dir)

            ignore_fn = (
                self._build_exclude_ignore(
                    source_runtime_dir, effective_excludes
                )
                if effective_excludes
                else None
            )
            shutil.copytree(source_runtime_dir, runtime_dir, ignore=ignore_fn)

            # Also copy any other files/folders at the root level
            if source_dir.exists():
                for item in source_dir.iterdir():
                    if (
                        item.name != "Runtime"
                        and not (package_dir / item.name).exists()
                    ):
                        if item.is_file():
                            shutil.copy2(item, package_dir)
                        elif item.is_dir():
                            shutil.copytree(
                                item,
                                package_dir / item.name,
                                dirs_exist_ok=True,
                            )

            if effective_excludes:
                logger.info(
                    f"Found existing Runtime folder, copied to {runtime_dir}"
                    f" (excluded: {effective_excludes})"
                )
            else:
                logger.info(
                    f"Found existing Runtime folder, copied directly to "
                    f"{runtime_dir}"
                )
        else:
            # Original behavior: create Runtime folder
            # and copy all content into it
            runtime_dir = package_dir / "Runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)

            ignore_fn = (
                self._build_exclude_ignore(source_dir, effective_excludes)
                if effective_excludes
                else None
            )

            # Copy all source files to Runtime directory
            if source_dir.exists():
                for item in source_dir.iterdir():
                    if ignore_fn and item.name in ignore_fn(
                        str(source_dir), [item.name]
                    ):
                        logger.debug(f"Excluded: {item.name}")
                        continue
                    if item.is_file():
                        shutil.copy2(item, runtime_dir)
                    elif item.is_dir():
                        shutil.copytree(
                            item,
                            runtime_dir / item.name,
                            dirs_exist_ok=True,
                            ignore=ignore_fn,
                        )

            if effective_excludes:
                logger.info(
                    f"Organized source files into Runtime structure at "
                    f"{runtime_dir} (excluded: {effective_excludes})"
                )
            else:
                logger.info(
                    f"Organized source files into Runtime structure at "
                    f"{runtime_dir}"
                )

        # Remove C# project files that aren't needed in Unity
        if self._should_remove_csharp_project_files():
            self._remove_csharp_project_files(runtime_dir)

        # Fix global/file-scoped namespaces to Unity-compatible block syntax
        if self._should_fix_global_namespaces():
            self._fix_global_namespaces(runtime_dir)

        return runtime_dir

    def organize_plugins_structure(
        self, dll_files: List[Path], package_dir: Path
    ) -> Path:
        """Organize DLL files into Unity package Plugins folder structure."""
        import shutil

        # Create Plugins directory
        plugins_dir = package_dir / "Plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)

        # Copy DLL files to Plugins directory
        for dll_file in dll_files:
            if dll_file.is_file():
                dest_path = plugins_dir / dll_file.name
                shutil.copy2(dll_file, dest_path)
                logger.debug(f"Copied DLL: {dll_file.name} to Plugins folder")

        logger.info(
            f"Organized {len(dll_files)} DLL files into Plugins structure at "
            f"{plugins_dir}"
        )
        return plugins_dir

    def generate_dll_meta_files(self, plugins_dir: Path) -> None:
        """Generate Unity meta files for DLL files in Plugins directory."""
        dll_files = list(plugins_dir.glob("*.dll"))

        for dll_file in dll_files:
            if dll_file.is_file():
                self.write_meta_file(dll_file, "PluginImporter")
                logger.debug(f"Generated meta file for DLL: {dll_file.name}")

        logger.info(f"Generated meta files for {len(dll_files)} DLL files")

    def _should_remove_csharp_project_files(self) -> bool:
        """Check if C# project files should be removed (config)."""
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
                        f"Removed C# project file: "
                        f"{file_path.relative_to(directory)}"
                    )
                    files_removed += 1
                elif file_path.is_dir() and ext.startswith("."):
                    # Remove directories like .vs, .vscode, .idea
                    shutil.rmtree(file_path)
                    logger.debug(
                        f"Removed C# project directory: "
                        f"{file_path.relative_to(directory)}"
                    )
                    files_removed += 1

        # Remove files by name
        for filename in csharp_project_files:
            for file_path in directory.rglob(filename):
                if file_path.is_file():
                    file_path.unlink()
                    logger.debug(
                        f"Removed C# project file: "
                        f"{file_path.relative_to(directory)}"
                    )
                    files_removed += 1

        if files_removed > 0:
            logger.info(
                f"Removed {files_removed} C# project files from Unity package"
            )

    def _fix_global_namespaces(self, directory: Path) -> None:
        """Fix C# files that use file-scoped namespace syntax."""
        import re

        # Pattern to match file-scoped namespace declarations
        # Matches "namespace Some.Namespace;" at the start
        # of a line
        file_scoped_pattern = re.compile(
            r"^namespace\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_]"
            r"[a-zA-Z0-9_]*)*)\s*;\s*$",
            re.MULTILINE,
        )
        files_fixed = 0

        # Find all C# files that use file-scoped namespace syntax
        for cs_file in directory.rglob("*.cs"):
            if cs_file.is_file():
                try:
                    with open(cs_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    match = file_scoped_pattern.search(content)
                    if match:
                        namespace_name = match.group(1)
                        namespace_line = match.group(0)

                        # Replace file-scoped namespace with block-scoped
                        # namespace
                        # Remove the semicolon and replace with opening brace
                        new_namespace_line = f"namespace {namespace_name}\n{{"

                        # Replace the namespace declaration
                        new_content = content.replace(
                            namespace_line, new_namespace_line, 1
                        )

                        # Add closing brace at the end of the file for the
                        # namespace
                        # Always add a namespace closing brace since we
                        # converted from file-scoped to block-scoped namespace
                        stripped_content = new_content.rstrip()
                        new_content = stripped_content + "\n}\n"

                        # Write the modified content back
                        with open(cs_file, "w", encoding="utf-8") as f:
                            f.write(new_content)

                        logger.debug(
                            f"Fixed file-scoped namespace in: "
                            f"{cs_file.relative_to(directory)}"
                        )
                        files_fixed += 1

                except Exception as e:
                    logger.warning(
                        f"Failed to process namespace in {cs_file}: {e}"
                    )

        if files_fixed > 0:
            logger.info(
                f"Fixed {files_fixed} C# files with file-scoped namespaces"
            )

    def _should_fix_global_namespaces(self) -> bool:
        """Check if global namespace fixing should be performed (config)."""
        if not self.config:
            return True  # Default to fixing namespaces

        build_settings = self.config.get_build_settings()
        return bool(build_settings.get("fix_global_namespaces", True))

    def _parse_author(
        self, author: Union[str, Dict[str, str]]
    ) -> Dict[str, str]:
        """
        Parse an author specification into a Unity Package Manager (UPM)
        author object.
        This method accepts either a dictionary or a string representing
        the author, and returns a dictionary with 'name', 'email', and 'url'
        fields as required by UPM.
        Args:
            author (Union[str, Dict[str, str]]): The author information.
            Supported formats:
                - dict: {'name': str, 'email': str, 'url': str}
                    (missing keys default to empty string)
                - str: "Name <email@domain.com>"
                - str: "Name"
                - str: "" (empty string)
        Returns:
            Dict[str, str]: A dictionary with keys:
                - 'name': The author's name (str).
                - 'email': The author's email address (str, may be empty).
                - 'url': The author's URL (str, may be empty).
        Examples:
            >>> _parse_author("Jane Doe <jane@example.com>")
            {'name': 'Jane Doe', 'email': 'jane@example.com', 'url': ''}
            >>> _parse_author("Jane Doe")
            {'name': 'Jane Doe', 'email': '', 'url': ''}
            >>> _parse_author({"name": "Jane Doe",
                               "email": "jane@example.com"})
            {'name': 'Jane Doe', 'email': 'jane@example.com', 'url': ''}
        """
        # If already a dict, validate and return with defaults
        if isinstance(author, dict):
            return {
                "name": str(author.get("name", "")),
                "email": str(author.get("email", "")),
                "url": str(author.get("url", "")),
            }

        # Handle string formats
        if not author or not author.strip():
            return {"name": "", "email": "", "url": ""}

        import re

        # Pattern to match "Name <email@domain.com>" format
        match = re.match(r"^(.+?)\s*<(.+?)>$", author.strip())

        if match:
            name = match.group(1).strip()
            email = match.group(2).strip()
            return {"name": name, "email": email, "url": ""}
        else:
            # Just a name without email
            return {"name": author.strip(), "email": "", "url": ""}
