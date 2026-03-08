"""Tests for ConfigManager."""

import pytest
import tempfile
import yaml
from pathlib import Path
from unity_wrapper.core.config_manager import ConfigManager
from typing import Dict, Any, Generator


@pytest.fixture
def temp_config_dir() -> Generator[Path, None, None]:
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


def test_config_manager_load(temp_config_dir: Path) -> None:
    """Test ConfigManager loads configuration correctly."""
    config = ConfigManager(temp_config_dir)

    assert len(config.get_package_names()) == 1
    assert "com.test.package" in config.get_package_names()

    package_config = config.get_package_config("com.test.package")
    assert package_config is not None
    assert (
        package_config["source"]["url"] == "https://github.com/test/repo.git"
    )
    assert package_config["namespace"] == "Test.Package"


def test_config_manager_github_settings(temp_config_dir: Path) -> None:
    """Test ConfigManager returns GitHub settings."""
    config = ConfigManager(temp_config_dir)

    github_settings = config.get_github_settings()
    assert github_settings["owner"] == "testowner"
    assert github_settings["repository"] == "testrepo"


def test_config_manager_add_remove_package(temp_config_dir: Path) -> None:
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


def test_get_git_cache_dir_default(temp_config_dir: Path) -> None:
    """get_git_cache_dir returns default when not in settings."""
    config = ConfigManager(temp_config_dir)
    cache_dir = config.get_git_cache_dir()
    assert cache_dir == temp_config_dir.parent / ".git-cache"


def test_get_git_cache_dir_custom(temp_config_dir: Path) -> None:
    """get_git_cache_dir respects a custom value in settings.yaml."""
    settings_path = temp_config_dir / "settings.yaml"
    with open(settings_path) as f:
        import yaml

        data = yaml.safe_load(f)
    data.setdefault("build", {})["git_cache_dir"] = "my-cache"
    with open(settings_path, "w") as f:
        yaml.dump(data, f)

    config = ConfigManager(temp_config_dir)
    assert config.get_git_cache_dir() == temp_config_dir.parent / "my-cache"


def test_get_max_parallel_clones_default(temp_config_dir: Path) -> None:
    """get_max_parallel_clones returns 4 when not in settings."""
    config = ConfigManager(temp_config_dir)
    assert config.get_max_parallel_clones() == 4


def test_get_max_parallel_clones_custom(temp_config_dir: Path) -> None:
    """get_max_parallel_clones respects a custom value in settings.yaml."""
    settings_path = temp_config_dir / "settings.yaml"
    with open(settings_path) as f:
        import yaml

        data = yaml.safe_load(f)
    data.setdefault("build", {})["max_parallel_clones"] = 8
    with open(settings_path, "w") as f:
        yaml.dump(data, f)

    config = ConfigManager(temp_config_dir)
    assert config.get_max_parallel_clones() == 8


def test_get_max_parallel_clones_invalid_type(temp_config_dir: Path) -> None:
    """get_max_parallel_clones raises ValueError for a non-integer value."""
    settings_path = temp_config_dir / "settings.yaml"
    with open(settings_path) as f:
        import yaml

        data = yaml.safe_load(f)
    data.setdefault("build", {})["max_parallel_clones"] = "fast"
    with open(settings_path, "w") as f:
        yaml.dump(data, f)

    config = ConfigManager(temp_config_dir)
    with pytest.raises(ValueError, match="max_parallel_clones"):
        config.get_max_parallel_clones()


def test_get_max_parallel_clones_zero_raises(temp_config_dir: Path) -> None:
    """get_max_parallel_clones raises ValueError when value is 0."""
    settings_path = temp_config_dir / "settings.yaml"
    with open(settings_path) as f:
        import yaml

        data = yaml.safe_load(f)
    data.setdefault("build", {})["max_parallel_clones"] = 0
    with open(settings_path, "w") as f:
        yaml.dump(data, f)

    config = ConfigManager(temp_config_dir)
    with pytest.raises(ValueError, match="max_parallel_clones"):
        config.get_max_parallel_clones()
