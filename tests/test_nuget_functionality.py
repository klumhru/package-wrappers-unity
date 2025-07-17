"""Test NuGet package functionality."""

import tempfile
from pathlib import Path
import pytest
from typing import Dict, List, Union

from unity_wrapper.core.nuget_manager import NuGetManager
from unity_wrapper.core.config_manager import ConfigManager
from unity_wrapper.core.package_builder import PackageBuilder


def test_nuget_manager_download() -> None:
    """Test that NuGet manager can download packages."""
    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir)
        manager = NuGetManager(work_dir)

        # Test downloading a known package
        package_path = manager.download_package("System.IO.Pipelines", "7.0.0")

        assert package_path.exists()
        assert package_path.is_dir()
        assert (package_path / "System.IO.Pipelines.nuspec").exists()

        # Test DLL extraction
        dlls = manager.extract_dlls(package_path, "netstandard2.0")
        assert len(dlls) > 0
        assert any(dll.name == "System.IO.Pipelines.dll" for dll in dlls)


def test_nuget_package_config() -> None:
    """Test that NuGet package configuration works."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir)

        # Create test config files
        packages_config: Dict[
            str, List[Dict[str, Union[str, Dict[str, str]]]]
        ] = {
            "packages": [
                {
                    "name": "com.test.git-package",
                    "source": {
                        "type": "git",
                        "url": "https://github.com/test/repo.git",
                        "ref": "main",
                    },
                    "namespace": "Test.Package",
                }
            ],
            "nuget_packages": [
                {
                    "name": "com.test.nuget-package",
                    "nuget_id": "TestPackage",
                    "version": "1.0.0",
                    "framework": "netstandard2.0",
                }
            ],
        }

        import yaml

        with open(config_dir / "packages.yaml", "w") as f:
            yaml.dump(packages_config, f)

        with open(config_dir / "settings.yaml", "w") as f:
            yaml.dump({"templates_dir": "templates"}, f)

        # Test config manager
        config_manager = ConfigManager(config_dir)

        # Test package type detection
        assert config_manager.get_package_type("com.test.git-package") == "git"
        assert (
            config_manager.get_package_type("com.test.nuget-package")
            == "nuget"
        )
        assert config_manager.get_package_type("com.test.unknown") == "unknown"

        # Test package listing
        all_packages = config_manager.get_all_package_names()
        assert "com.test.git-package" in all_packages
        assert "com.test.nuget-package" in all_packages
        assert len(all_packages) == 2

        # Test NuGet package config
        nuget_config = config_manager.get_nuget_package_config(
            "com.test.nuget-package"
        )
        assert nuget_config is not None
        assert nuget_config["nuget_id"] == "TestPackage"
        assert nuget_config["version"] == "1.0.0"
        assert nuget_config["framework"] == "netstandard2.0"


def test_nuget_package_building() -> None:
    """Test that NuGet packages can be built (integration test)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir) / "config"
        output_dir = Path(temp_dir) / "output"
        work_dir = Path(temp_dir) / "work"

        config_dir.mkdir()
        output_dir.mkdir()
        work_dir.mkdir()

        # Create test config files
        packages_config: Dict[str, List[Dict[str, Union[str, List[str]]]]] = {
            "nuget_packages": [
                {
                    "name": "com.test.system-io-pipelines",
                    "display_name": "System.IO.Pipelines Test",
                    "description": "Test package for System.IO.Pipelines",
                    "version": "7.0.0",
                    "nuget_id": "System.IO.Pipelines",
                    "framework": "netstandard2.0",
                    "keywords": ["test", "pipelines"],
                }
            ]
        }

        import yaml

        with open(config_dir / "packages.yaml", "w") as f:
            yaml.dump(packages_config, f)

        with open(config_dir / "settings.yaml", "w") as f:
            yaml.dump({"templates_dir": "templates"}, f)

        # Create templates directory
        templates_dir = config_dir.parent / "templates"
        templates_dir.mkdir()

        # Test package builder
        builder = PackageBuilder(config_dir, output_dir, work_dir)

        try:
            package_path = builder.build_package(
                "com.test.system-io-pipelines"
            )

            # Verify package structure
            assert package_path.exists()
            assert (package_path / "package.json").exists()
            assert (package_path / "Plugins").exists()
            assert (
                package_path / "Plugins" / "System.IO.Pipelines.dll"
            ).exists()
            assert (
                package_path / "Plugins" / "System.IO.Pipelines.dll.meta"
            ).exists()

            # Verify no assembly definition (NuGet packages don't have asmdef)
            assert not any(package_path.glob("**/*.asmdef"))

            # Verify no Runtime folder (NuGet packages use Plugins)
            assert not (package_path / "Runtime").exists()

        finally:
            builder.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
