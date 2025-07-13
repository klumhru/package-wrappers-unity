<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Unity Package Wrapper Project Instructions

This is a Python project that automatically builds Unity packages from open source repositories and publishes them to GitHub's package registry.

## Project Structure

- `src/unity_wrapper/` - Main Python package
- `config/` - Configuration files (packages.yaml, settings.yaml)
- `templates/` - Jinja2 templates for Unity files
- `packages/` - Generated Unity packages (output directory)
- `tests/` - Test suite

## Key Components

### Core Modules
- `GitManager` - Handles Git repository operations and ref tracking
- `UnityGenerator` - Generates Unity-specific files (package.json, .asmdef, .meta)
- `PackageBuilder` - Main orchestrator for the package building process
- `ConfigManager` - Manages YAML configuration files

### Utilities
- `FileWatcher` - Monitors configuration changes for automatic rebuilds
- `GitHubPublisher` - Publishes packages to GitHub Package Registry

## Unity Package Structure

Generated packages follow Unity Package Manager conventions:
```
package_name/
├── package.json         # Unity package manifest
├── Runtime/            # Runtime code and assets
│   ├── *.cs           # C# source files
│   ├── *.asmdef       # Assembly definition
│   └── *.meta         # Unity meta files
└── *.meta             # Meta files for all directories
```

## Configuration

### packages.yaml
Defines source repositories and package settings:
- Git repository URL and ref
- Extract path within repository
- C# namespace and assembly definition settings
- Unity package metadata

### settings.yaml
Global settings for the wrapper:
- Output directories
- GitHub registry configuration
- Default package settings

## Development Guidelines

- Use type hints for all function parameters and return values
- Follow Unity Package Manager naming conventions (com.company.package)
- Generate .meta files for all Unity assets and directories
- Support Git refs (branches, tags, commit hashes)
- Implement proper error handling for Git operations
- Use structured logging for debugging

## Unity Conventions

- Package names use reverse domain notation (com.example.package)
- Runtime code goes in Runtime/ folder
- Assembly definitions have root namespace matching the package
- All files and folders need corresponding .meta files
- package.json follows Unity Package Manager schema

## Python Code Style Guide
This document outlines the coding style and conventions for Python code in the Unity Package Wrapper project. It is designed to ensure consistency, readability, and maintainability across the codebase.
- Use PEP 8 style guide for Python code
- Use type hints for all function parameters and return values
- Follow consistent naming conventions (snake_case for variables and functions, CamelCase for classes)
- Use docstrings for all public functions and classes
- Use f-strings for string formatting (Python 3.6+)
- Keep line length to a maximum of 79 characters
- Use spaces around operators and after commas
- Use 4 spaces for indentation (no tabs)
- Use `flake8` for linting and `black` for formatting. Perform these checks before committing code.