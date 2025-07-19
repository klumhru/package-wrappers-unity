"""Test LICENSE file copying functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from unity_wrapper.core.package_builder import PackageBuilder


def test_license_file_copying() -> None:
    """Test that LICENSE files are copied from source repository to package."""

    # Create temporary directories
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "config"
        output_path = temp_path / "output"
        work_path = temp_path / "work"

        config_path.mkdir()
        output_path.mkdir()
        work_path.mkdir()

        # Create test configuration
        config_content = """
packages:
  - name: "com.test.package"
    display_name: "Test Package"
    description: "Test package description"
    version: "1.0.0"
    source:
      type: git
      url: "https://github.com/test/repo.git"
      ref: "main"
    extract_path: "src"
    namespace: "Test.Package"
"""
        (config_path / "packages.yaml").write_text(config_content)
        (config_path / "settings.yaml").write_text(
            "templates_dir: templates\noutput_dir: output"
        )

        # Create fake source directory with LICENSE file
        fake_repo_path = work_path / "com.test.package"
        fake_source_path = fake_repo_path / "src"
        fake_source_path.mkdir(parents=True)

        # Create a LICENSE file in the repo root
        license_content = "MIT License\n\nCopyright (c) 2025 Test"
        (fake_repo_path / "LICENSE").write_text(license_content)

        # Create some source files
        (fake_source_path / "TestClass.cs").write_text(
            "namespace Test.Package { public class TestClass { } }"
        )

        # Mock the git manager to return our fake repository
        with patch(
            "unity_wrapper.core.package_builder.GitManager"
        ) as mock_git_manager:
            mock_git_instance = MagicMock()
            mock_git_instance.clone_or_update.return_value = fake_repo_path
            mock_git_manager.return_value = mock_git_instance

            # Mock the unity generator
            with patch(
                "unity_wrapper.core.package_builder.UnityGenerator"
            ) as mock_unity_gen:
                mock_unity_instance = MagicMock()
                mock_unity_instance.organize_runtime_structure.return_value = (
                    output_path / "com.test.package" / "Runtime"
                )
                mock_unity_instance.generate_package_json.return_value = {
                    "name": "com.test.package",
                    "version": "1.0.0",
                }
                mock_unity_instance.generate_assembly_definition.return_value = {  # noqa: E501
                    "name": "Test.Package"
                }
                mock_unity_gen.return_value = mock_unity_instance

                # Create the package builder and build the package
                builder = PackageBuilder(config_path, output_path, work_path)
                package_path = builder.build_package("com.test.package")

                # Verify the LICENSE file was copied
                license_file = package_path / "LICENSE"
                assert (
                    license_file.exists()
                ), "LICENSE file should be copied to package root"
                assert (
                    license_file.read_text() == license_content
                ), "LICENSE content should match original"

                # Verify that generate_all_meta_files was called
                # (which would generate LICENSE.meta)
                mock_unity_instance.generate_all_meta_files.assert_called_once()  # noqa: E501


def test_license_file_various_names() -> None:
    """Test that various LICENSE file naming conventions are detected."""

    # Create temporary directories
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "config"
        output_path = temp_path / "output"
        work_path = temp_path / "work"

        config_path.mkdir()
        output_path.mkdir()
        work_path.mkdir()

        # Create test configuration
        config_content = """
packages:
  - name: "com.test.package"
    display_name: "Test Package"
    description: "Test package description"
    version: "1.0.0"
    source:
      type: git
      url: "https://github.com/test/repo.git"
      ref: "main"
    extract_path: "src"
    namespace: "Test.Package"
"""
        (config_path / "packages.yaml").write_text(config_content)
        (config_path / "settings.yaml").write_text(
            "templates_dir: templates\noutput_dir: output"
        )

        # Test different LICENSE file names
        license_names = ["LICENSE.md", "License.txt", "license", "COPYING"]

        for license_name in license_names:
            # Create fake source directory with different LICENSE file names
            fake_repo_path = work_path / f"com.test.package-{license_name}"
            fake_source_path = fake_repo_path / "src"
            fake_source_path.mkdir(parents=True)

            # Create a LICENSE file with the specific name
            license_content = f"License content for {license_name}"
            (fake_repo_path / license_name).write_text(license_content)

            # Create some source files
            (fake_source_path / "TestClass.cs").write_text(
                "namespace Test.Package { public class TestClass { } }"
            )

            # Mock the git manager to return our fake repository
            with patch(
                "unity_wrapper.core.package_builder.GitManager"
            ) as mock_git_manager:
                mock_git_instance = MagicMock()
                mock_git_instance.clone_or_update.return_value = fake_repo_path
                mock_git_manager.return_value = mock_git_instance

                # Mock the unity generator
                with patch(
                    "unity_wrapper.core.package_builder.UnityGenerator"
                ) as mock_unity_gen:
                    mock_unity_instance = MagicMock()
                    package_output = (
                        output_path / f"com.test.package-{license_name}"
                    )
                    mock_unity_instance.organize_runtime_structure.return_value = (  # noqa: E501
                        package_output / "Runtime"
                    )
                    mock_unity_instance.generate_package_json.return_value = {
                        "name": "com.test.package",
                        "version": "1.0.0",
                    }
                    mock_unity_instance.generate_assembly_definition.return_value = {  # noqa: E501
                        "name": "Test.Package"
                    }
                    mock_unity_gen.return_value = mock_unity_instance

                    # Create the package builder and build the package
                    builder = PackageBuilder(
                        config_path, output_path, work_path
                    )
                    package_path = builder.build_package("com.test.package")

                    # Verify the LICENSE file was copied (always as "LICENSE")
                    license_file = package_path / "LICENSE"
                    assert (
                        license_file.exists()
                    ), "LICENSE file should be copied for "
                    f"source file {license_name}"
                    assert (
                        license_file.read_text() == license_content
                    ), f"LICENSE content should match for {license_name}"


def test_no_license_file() -> None:
    """Test that build continues successfully when no LICENSE file is found."""

    # Create temporary directories
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "config"
        output_path = temp_path / "output"
        work_path = temp_path / "work"

        config_path.mkdir()
        output_path.mkdir()
        work_path.mkdir()

        # Create test configuration
        config_content = """
packages:
  - name: "com.test.package"
    display_name: "Test Package"
    description: "Test package description"
    version: "1.0.0"
    source:
      type: git
      url: "https://github.com/test/repo.git"
      ref: "main"
    extract_path: "src"
    namespace: "Test.Package"
"""
        (config_path / "packages.yaml").write_text(config_content)
        (config_path / "settings.yaml").write_text(
            "templates_dir: templates\noutput_dir: output"
        )

        # Create fake source directory without LICENSE file
        fake_repo_path = work_path / "com.test.package"
        fake_source_path = fake_repo_path / "src"
        fake_source_path.mkdir(parents=True)

        # Create some source files but no LICENSE
        (fake_source_path / "TestClass.cs").write_text(
            "namespace Test.Package { public class TestClass { } }"
        )

        # Mock the git manager to return our fake repository
        with patch(
            "unity_wrapper.core.package_builder.GitManager"
        ) as mock_git_manager:
            mock_git_instance = MagicMock()
            mock_git_instance.clone_or_update.return_value = fake_repo_path
            mock_git_manager.return_value = mock_git_instance

            # Mock the unity generator
            with patch(
                "unity_wrapper.core.package_builder.UnityGenerator"
            ) as mock_unity_gen:
                mock_unity_instance = MagicMock()
                mock_unity_instance.organize_runtime_structure.return_value = (
                    output_path / "com.test.package" / "Runtime"
                )
                mock_unity_instance.generate_package_json.return_value = {
                    "name": "com.test.package",
                    "version": "1.0.0",
                }
                mock_unity_instance.generate_assembly_definition.return_value = {  # noqa: E501
                    "name": "Test.Package"
                }
                mock_unity_gen.return_value = mock_unity_instance

                # Create the package builder and build the package
                builder = PackageBuilder(config_path, output_path, work_path)
                package_path = builder.build_package("com.test.package")

                # Verify no LICENSE file exists
                license_file = package_path / "LICENSE"
                assert (
                    not license_file.exists()
                ), "LICENSE file should not exist when not found in source"

                # Verify build completed successfully
                assert (
                    package_path.exists()
                ), "Package should still be built successfully"
