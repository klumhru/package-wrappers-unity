<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Unity Package Wrapper

Python tool that automatically wraps open-source C# libraries into Unity Package Manager (UPM) packages and publishes them to a registry.

## Commands

```bash
# Setup
make dev-setup          # Full dev setup: install deps, config, pre-commit hooks
poetry install --with dev

# Testing
make test               # Run full test suite with coverage
poetry run pytest tests/test_unity_generator.py -v   # Single test file
poetry run pytest tests/ -k "test_organize_runtime"  # Single test by name

# Quality
make lint               # black --check + flake8 + mypy
make format             # Auto-format with black
make qa                 # format + lint + test

# Package operations (CLI)
poetry run unity-wrapper build                       # Build all packages
poetry run unity-wrapper build com.example.pkg       # Build one package
poetry run unity-wrapper check                       # Check which need updates
poetry run unity-wrapper publish --registry github --owner <org>
poetry run unity-wrapper watch                       # Auto-rebuild on config change

# Makefile shortcuts
make build-package PACKAGE=com.example.pkg
make publish REGISTRY=github OWNER=myorg
```

## Architecture

`PackageBuilder` is the top-level orchestrator used as a context manager. It wires together:
- `ConfigManager` — reads `config/packages.yaml` and `config/settings.yaml`
- `GitManager` — clones/updates source repos into `.unity_wrapper_temp/`
- `NuGetManager` — downloads `.nupkg` files from nuget.org for NuGet-sourced packages
- `UnityGenerator` — produces all Unity-specific output files using Jinja2 templates from `templates/`
- `PackagePublisher` / `GitHubPublisher` — publishes via npm CLI (npm must be installed)

**Two package source types** are supported in `config/packages.yaml`:
- `source.type: git` — clones a repo, extracts `extract_path` subtree into `Runtime/`
- `source.type: nuget` — downloads NuGet package, extracts DLLs for the target framework

The `PackageBuilder` determines type via `ConfigManager.get_package_type()`, which checks `packages` (git) vs `nuget_packages` (separate top-level key) in packages.yaml.

**Publishing** uses the npm registry protocol. `PackagePublisher` wraps `npm publish` with a generated `.npmrc`; supported registries are `github`, `npmjs`, and `openupm`. Auth tokens are read from `GITHUB_TOKEN` / `NPM_TOKEN` env vars or `config/settings.yaml`.

## Key Conventions

**Meta file generation**: Every file and directory in a generated package must have a corresponding `.meta` file with a stable GUID. `UnityGenerator` generates these automatically; never copy files into the output without going through `UnityGenerator`.

**Runtime folder logic**: If the source already contains a `Runtime/` directory, it is used as-is. Otherwise all source files are placed under a new `Runtime/` folder. This logic lives in `UnityGenerator.organize_runtime_structure()`.

**Assembly definitions**: Generated `.asmdef` files use `asmdef_name` as the assembly name and `namespace` as `rootNamespace`. Extra fields (e.g., `allowUnsafeCode: true`) are injected via `asmdef_extra` in packages.yaml.

**`package.json` extras**: Arbitrary UPM manifest fields can be added per-package using `package_json_extra` in packages.yaml (e.g., `license`, `homepage`).

**`assembly_references`**: Optional list in packages.yaml for adding cross-assembly references to the `.asmdef` (e.g., `["UniTask"]`).

**Work directory**: `.unity_wrapper_temp/` is a throwaway scratch space for git clones and NuGet downloads. It is cleaned up when `PackageBuilder` exits its context. Do not persist data there.

## Code Style

- Python 3.10+, `src/` layout (`src/unity_wrapper/`)
- Type hints required on all public functions; `mypy` enforced in CI
- Line length: 79 characters (`black` + `flake8`)
- Docstrings on all public classes and methods
- `logging` (not `print`) for all diagnostic output; module-level `logger = logging.getLogger(__name__)`
- Pre-commit hooks enforce formatting/linting before each commit (`make install-hooks`)
