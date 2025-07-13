"""Tests for ConfigManager."""

import pytest
import tempfile
import yaml
from pathlib import Path
from unity_wrapper.core.config_manager import ConfigManager
from typing import Dict, Any


@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir)

        # Create sample packages.yaml
        packages_config: Dict[str, Any] = {
            "packages": [
                {
                    "name": "com.test.package",
                    "source": {
                        "type": "git",
                        "url": "https://github.com/test/repo.git",
                        "ref": "main",
                    },
                    "extract_path": "src",
                    "namespace": "Test.Package",
                }
            ]
        }

        with open(config_dir / "packages.yaml", "w") as f:
            yaml.dump(packages_config, f)

        # Create sample settings.yaml
        settings_config: Dict[str, Any] = {
            "output_dir": "packages",
            "work_dir": ".temp",
            "github": {"owner": "testowner", "repository": "testrepo"},
        }

        with open(config_dir / "settings.yaml", "w") as f:
            yaml.dump(settings_config, f)

        yield config_dir


def test_config_manager_load(temp_config_dir: Path):
    """Test ConfigManager loads configuration correctly."""
    config = ConfigManager(temp_config_dir)

    assert len(config.get_package_names()) == 1
    assert "com.test.package" in config.get_package_names()

    package_config = config.get_package_config("com.test.package")
    assert package_config is not None
    assert package_config["source"]["url"] == "https://github.com/test/repo.git"
    assert package_config["namespace"] == "Test.Package"


def test_config_manager_github_settings(temp_config_dir: Path):
    """Test ConfigManager returns GitHub settings."""
    config = ConfigManager(temp_config_dir)

    github_settings = config.get_github_settings()
    assert github_settings["owner"] == "testowner"
    assert github_settings["repository"] == "testrepo"


def test_config_manager_add_remove_package(temp_config_dir: Path):
    """Test adding and removing packages."""
    config = ConfigManager(temp_config_dir)

    # Add new package
    new_package: Dict[str, Any] = {
        "name": "com.test.newpackage",
        "source": {
            "type": "git",
            "url": "https://github.com/test/newrepo.git",
            "ref": "develop",
        },
    }

    config.add_package(new_package)
    assert len(config.get_package_names()) == 2
    assert "com.test.newpackage" in config.get_package_names()

    # Remove package
    success = config.remove_package("com.test.newpackage")
    assert success is True
    assert len(config.get_package_names()) == 1
    assert "com.test.newpackage" not in config.get_package_names()

    # Try to remove non-existent package
    success = config.remove_package("com.test.nonexistent")
    assert success is False
