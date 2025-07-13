"""Tests for UnityGenerator."""

import pytest
import tempfile
from pathlib import Path
from typing import Tuple, Generator
from unity_wrapper.core.unity_generator import UnityGenerator


@pytest.fixture
def temp_directories() -> Generator[Tuple[Path, Path, Path], None, None]:
    """Create temporary source and package directories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base_dir = Path(temp_dir)
        source_dir = base_dir / "source"
        package_dir = base_dir / "package"
        templates_dir = base_dir / "templates"

        source_dir.mkdir()
        package_dir.mkdir()
        templates_dir.mkdir()

        yield source_dir, package_dir, templates_dir


def test_organize_runtime_structure_without_existing_runtime(
    temp_directories: Tuple[Path, Path, Path],
) -> None:
    """Test organizing files when no Runtime folder exists in source."""
    source_dir, package_dir, templates_dir = temp_directories
    generator = UnityGenerator(templates_dir)

    # Create some test files in source
    (source_dir / "test.cs").write_text("// Test C# file")
    (source_dir / "subfolder").mkdir()
    (source_dir / "subfolder" / "another.cs").write_text("// Another file")

    # Organize runtime structure
    runtime_dir = generator.organize_runtime_structure(source_dir, package_dir)

    # Verify Runtime folder was created
    assert runtime_dir == package_dir / "Runtime"
    assert runtime_dir.exists()

    # Verify files were copied into Runtime
    assert (runtime_dir / "test.cs").exists()
    assert (runtime_dir / "subfolder" / "another.cs").exists()


def test_organize_runtime_structure_with_existing_runtime(
    temp_directories: Tuple[Path, Path, Path],
) -> None:
    """Test organizing files when Runtime folder already exists in source."""
    source_dir, package_dir, templates_dir = temp_directories
    generator = UnityGenerator(templates_dir)

    # Create Runtime folder in source with files
    runtime_source = source_dir / "Runtime"
    runtime_source.mkdir()
    (runtime_source / "script.cs").write_text("// Runtime script")
    (runtime_source / "subfolder").mkdir()
    (runtime_source / "subfolder" / "nested.cs").write_text("// Nested script")

    # Create other files outside Runtime
    (source_dir / "package.json").write_text('{"name": "test"}')
    (source_dir / "README.md").write_text("# Test Package")

    # Organize runtime structure
    runtime_dir = generator.organize_runtime_structure(source_dir, package_dir)

    # Verify Runtime folder was copied directly
    assert runtime_dir == package_dir / "Runtime"
    assert runtime_dir.exists()

    # Verify Runtime contents were copied correctly
    assert (runtime_dir / "script.cs").exists()
    assert (runtime_dir / "subfolder" / "nested.cs").exists()

    # Verify other files were copied to package root
    assert (package_dir / "package.json").exists()
    assert (package_dir / "README.md").exists()

    # Verify no nested Runtime/Runtime structure
    assert not (runtime_dir / "Runtime").exists()


def test_organize_runtime_structure_preserves_existing_structure(
    temp_directories: Tuple[Path, Path, Path],
) -> None:
    """Test that existing Unity package structure is preserved."""
    source_dir, package_dir, templates_dir = temp_directories
    generator = UnityGenerator(templates_dir)

    # Create a complete Unity package structure in source
    runtime_dir_source = source_dir / "Runtime"
    runtime_dir_source.mkdir()
    (runtime_dir_source / "MyScript.cs").write_text("// Unity script")
    (runtime_dir_source / "MyScript.asmdef").write_text(
        '{"name": "MyPackage"}'
    )

    editor_dir_source = source_dir / "Editor"
    editor_dir_source.mkdir()
    (editor_dir_source / "EditorScript.cs").write_text("// Editor script")

    (source_dir / "package.json").write_text('{"name": "my-package"}')

    # Organize runtime structure
    result_runtime_dir = generator.organize_runtime_structure(
        source_dir, package_dir
    )

    # Verify structure was preserved correctly
    assert result_runtime_dir == package_dir / "Runtime"
    assert (package_dir / "Runtime" / "MyScript.cs").exists()
    assert (package_dir / "Runtime" / "MyScript.asmdef").exists()
    assert (package_dir / "Editor" / "EditorScript.cs").exists()
    assert (package_dir / "package.json").exists()
