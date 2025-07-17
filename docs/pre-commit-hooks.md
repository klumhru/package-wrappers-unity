# Pre-commit Hooks Setup

This project uses [pre-commit](https://pre-commit.com/) to automatically run code quality checks before each commit.

## What's Included

The pre-commit hooks automatically run:

### Code Quality Checks
- **Trailing whitespace removal**
- **End-of-file fixing**
- **YAML/JSON/TOML validation**
- **Large file detection**
- **Merge conflict detection**

### Python Code Standards
- **Black formatting** - Automatically formats code to consistent style
- **Flake8 linting** - Checks for code style and common errors
- **MyPy type checking** - Static type analysis

### Project-Specific Checks
- **Full test suite** - Runs all tests with coverage requirement (50%+)
- **Make targets** - Runs `make format` and `make lint`

## Installation

Pre-commit hooks are automatically installed when you run:

```bash
make setup
# or
make install-hooks
```

## Manual Usage

To run hooks manually on all files:
```bash
make run-hooks
# or
pre-commit run --all-files
```

To run hooks on specific files:
```bash
pre-commit run --files src/unity_wrapper/cli.py
```

## How It Works

1. **On every `git commit`**: All configured hooks run automatically
2. **If any hook fails**: The commit is blocked until issues are fixed
3. **Auto-formatting**: Some hooks (like Black) automatically fix issues
4. **Manual fixes**: Other issues require manual intervention

## Quality Standards Enforced

- ✅ **Code formatting**: Consistent style with Black
- ✅ **Linting**: No style violations or common errors
- ✅ **Type safety**: Static type checking with MyPy
- ✅ **Test coverage**: Minimum 50% code coverage required
- ✅ **File integrity**: No trailing whitespace, proper line endings

## Bypass (Emergency Only)

If you absolutely need to bypass pre-commit hooks:
```bash
git commit --no-verify -m "Emergency commit message"
```

**Note**: This should only be used in emergencies as it skips all quality checks.

## Configuration

The pre-commit configuration is in `.pre-commit-config.yaml`. Key features:

- **Excludes**: Unity project files and build artifacts are excluded
- **Stages**: Hooks run during the pre-commit stage
- **Dependencies**: Automatically installs required tools
- **Version pinning**: Uses specific versions for reproducibility

## Troubleshooting

### Hook Installation Issues
```bash
# Reinstall hooks
pre-commit uninstall
make install-hooks
```

### Update Hook Versions
```bash
# Update to latest versions
pre-commit autoupdate

# Reinstall with new versions
pre-commit install --install-hooks
```

### Cache Issues
```bash
# Clear pre-commit cache
pre-commit clean
```

## Development Workflow

1. **Write code**
2. **Stage changes**: `git add .`
3. **Commit**: `git commit -m "Your message"`
4. **Hooks run automatically**:
   - If successful: Commit proceeds
   - If failed: Fix issues and try again
5. **Push**: `git push`

This ensures that all committed code meets the project's quality standards!
