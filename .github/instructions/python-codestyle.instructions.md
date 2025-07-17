===
applyTo: "**/*.py"
===
# Python Code Style Guide
This document outlines the coding style and conventions for Python code in the Unity Package Wrapper project. It is designed to ensure consistency, readability, and maintainability across the codebase.

## General Guidelines
- Use Python 3.10 or later
- Use pre-commit hooks to enforce style checks before committing code
- Use type hints for all function parameters and return values
- Follow consistent naming conventions (snake_case for variables and functions, CamelCase for classes)
- Use docstrings for all public functions and classes
- Use f-strings for string formatting (Python 3.6+)
- Keep line length to a maximum of 79 characters
- Use spaces around operators and after commas
- Use 4 spaces for indentation (no tabs)
- Use `flake8` for linting and `black` for formatting. Perform these checks before committing code.
- Use `mypy` for type checking to ensure type safety
