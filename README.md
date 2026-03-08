# Unity Package Wrapper

This project automatically builds Unity packages from open source repositories and publishes them to npmjs.org package registry.

## ✅ Features Implemented

### **Must Have** (All Implemented)
- ✅ **Automatic building** when changes are detected via file watcher
- ✅ **Git repository management** with ref tracking and automatic updates
- ✅ **Unity Package Manager integration** with proper `package.json` generation
- ✅ **Meta file creation** for Unity compatibility (.meta files for all assets)
- ✅ **Runtime folder organization** following Unity conventions
- ✅ **GitHub Package Registry publishing** with npm-compatible API

### **Should Have** (All Implemented)
- ✅ **Assembly definition generation** with root namespace detection
- ✅ **Package dependency management** in `package.json`
- ✅ **Configuration-driven** package definitions via YAML
- ✅ **CI/CD automation** with GitHub Actions workflow

### **Additional Features**
- ✅ **Command-line interface** with full package management
- ✅ **File watching** for automatic rebuilds on configuration changes
- ✅ **Template system** using Jinja2 for customizable Unity files
- ✅ **Comprehensive testing** setup with pytest and coverage
- ✅ **Development tools** (linting, formatting, type checking)
- ✅ **VS Code integration** with tasks and proper Python environment

## 🚀 Quick Start

### Prerequisites
- **Python 3.12+**
- **Poetry** for dependency and environment management
- **Node.js and npm** (required for package publishing)
  - Install from https://nodejs.org/
  - Used by the GitHub Package Registry publisher

### 1. Development Setup
```bash
# Clone and set up development environment
make dev-setup

# Or manually:
poetry install --with dev
```

### 2. Configure Your Packages
Edit `config/packages.yaml`:
```yaml
packages:
  - name: "com.yourcompany.package"
    display_name: "Your Package Name"
    description: "Package description"
    version: "1.0.0"
    author: "Your Name <email@example.com>"

    source:
      type: git
      url: "https://github.com/user/repo.git"
      ref: "main"

    extract_path: "src"              # Path within repo to extract
    namespace: "YourCompany.Package" # C# namespace

    dependencies: {}                 # Unity package dependencies
    keywords: ["tag1", "tag2"]       # Discovery tags
```

### 3. Configure GitHub Publishing
Edit `config/settings.yaml`:
```yaml
github:
  token: "your_github_token_here"    # Personal access token with packages:write
  owner: "your_github_username"      # GitHub username or org
  repository: "your_repo_name"       # Repository name
```

### 4. Authenticate with GitHub Package Registry

#### For Local Development
Before publishing locally, you need to authenticate npm with GitHub:
```bash
# Login to GitHub Package Registry
npm login --scope=@your_github_username --registry=https://npm.pkg.github.com

# When prompted, use:
# Username: your_github_username
# Password: your_github_personal_access_token (with packages:write scope)
# Email: your_email@example.com
```

#### For CI/CD (GitHub Actions)
The project includes automated CI/CD with GitHub Actions that:
- **Automatically publishes** to npmjs.org using your NPM_TOKEN secret
- **Uses @klumhru scope** for all published packages
- **No complex authentication** required for end users
- **Everything works out of the box** after setting up the NPM_TOKEN secret!

The GitHub Actions workflow will automatically publish packages when:
- Changes are made to `config/packages.yaml`
- Source repositories have updates
- Manual workflow dispatch is triggered

**Setup:** Add an `NPM_TOKEN` secret to your GitHub repository with write access to the @klumhru scope.

### 5. Build and Publish
```bash
# Build all packages (via Makefile)
make build

# Watch for changes and auto-rebuild
make watch

# Check for package updates
make check

# Publish to GitHub Package Registry
make publish

# Alternatively, run the CLI directly via Poetry
poetry run unity-wrapper build
poetry run unity-wrapper watch
poetry run unity-wrapper check
poetry run unity-wrapper publish
```

## 📦 Local Package Registry (for Unity developers)

Packages are built by GitHub CI and hosted on GitHub Pages as the authoritative source.
To consume them in Unity, run a local nginx proxy that forwards requests to GitHub Pages
while suppressing HTTP gzip encoding — this is required because GitHub Pages applies
`Content-Encoding: gzip` to binary files, which causes Unity UPM to fail with
"stream size mismatch" or sha512 integrity errors.

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — start on login is
  recommended so the registry is always available without manual steps.

### Start the registry

```bash
# Start the local proxy (once; Docker Desktop keeps it running on login)
make registry-up

# Check logs
make registry-logs

# Stop
make registry-down
```

The registry will be available at **`http://localhost:4873`**.

### Configure Unity

In your Unity project's `Packages/manifest.json`, add (or update) the scoped registry:

```json
{
  "scopedRegistries": [
    {
      "name": "klumhru packages",
      "url": "http://localhost:4873",
      "scopes": ["com.klumhru"]
    }
  ]
}
```

Once Unity resolves the packages via the proxy they are cached locally in
`Library/PackageCache` — subsequent opens do not hit the network.

## 📁 Project Structure

```
├── src/unity_wrapper/              # Main Python package
│   ├── core/                       # Core functionality
│   │   ├── git_manager.py         # Git repository operations
│   │   ├── unity_generator.py     # Unity file generation
│   │   ├── package_builder.py     # Main orchestrator
│   │   └── config_manager.py      # Configuration management
│   ├── utils/                      # Utility modules
│   │   ├── file_watcher.py        # Configuration file monitoring
│   │   └── github_publisher.py    # GitHub Package Registry API
│   └── cli.py                      # Command-line interface
├── config/                         # Configuration files
│   ├── packages.yaml              # Package definitions
│   └── settings.yaml              # Global settings
├── templates/                      # Jinja2 templates
│   ├── package.json.j2           # Unity package.json template
│   └── assembly_definition.json.j2 # Assembly definition template
├── packages/                       # Generated Unity packages (output)
├── tests/                          # Test suite
├── .github/                        # GitHub integration
│   ├── workflows/build-packages.yml # CI/CD automation
│   └── copilot-instructions.md    # AI assistant instructions
└── .vscode/tasks.json             # VS Code tasks
```

## 🛠️ Available Commands

```bash
# Package Management (via Poetry)
poetry run unity-wrapper build [PACKAGE_NAME]  # Build packages (all or specific)
poetry run unity-wrapper check                  # Check for updates
poetry run unity-wrapper list-packages          # List configured packages
poetry run unity-wrapper add                    # Add new package configuration
poetry run unity-wrapper remove PACKAGE_NAME    # Remove package configuration

# Automation
make watch                           # Watch for config changes
make publish                         # Publish to npmjs.org (default)
# Or via Poetry:
poetry run unity-wrapper watch
poetry run unity-wrapper publish --registry github

# Development (via Makefile)
make dev-setup                      # Complete development setup
make test                           # Run tests with coverage
make lint                           # Run linting checks
make format                         # Format code with black
make clean                          # Clean temporary files
```

## 🔧 Development

### Prerequisites for Development
- Python 3.12+
- Poetry
- Node.js and npm (for package publishing functionality)
- Git

```bash
# Complete development setup with pre-commit hooks
make setup

# Or step by step:
# Install development dependencies
poetry install -E dev

# Install pre-commit hooks (runs quality checks on every commit)
make install-hooks

# Run tests
poetry run pytest tests/ -v --cov=unity_wrapper

# Format code
poetry run black src tests

# Type checking
poetry run mypy src

# Run all quality checks
make qa
```

### Code Quality Automation
This project uses [pre-commit hooks](docs/pre-commit-hooks.md) that automatically run on every commit:
- ✅ **Code formatting** with Black
- ✅ **Linting** with flake8 and mypy
- ✅ **Testing** with 50%+ coverage requirement
- ✅ **File validation** and cleanup

Pre-commit hooks ensure all committed code meets quality standards!

## 🎯 Unity Package Output Structure

Generated packages follow Unity Package Manager conventions:

```
com.example.package/
├── package.json                    # Unity package manifest
├── package.json.meta              # Unity meta file
├── Runtime/                        # Runtime code directory
│   ├── Runtime.meta               # Directory meta file
│   ├── *.cs                       # C# source files
│   ├── *.cs.meta                  # Source file meta files
│   ├── PackageName.asmdef         # Assembly definition
│   └── PackageName.asmdef.meta    # Assembly definition meta file
└── Runtime.meta                    # Runtime directory meta file
```

## 📦 Using Packages in Unity

### Step 1: Configure Scoped Registry
Add this to your Unity project's `Packages/manifest.json`:

```json
{
  "scopedRegistries": [
    {
      "name": "npm",
      "url": "https://registry.npmjs.org",
      "scopes": [ "klumhru" ]
    }
  ],
  "dependencies": {
    "com.klumhru.wrapper.google-protobuf": "31.1.0"
  }
}
```

### Step 2: No Authentication Required! 🎉
Unlike GitHub Package Registry, npmjs.org is completely free and open:
- ✅ **No tokens needed** for installing packages
- ✅ **No `.npmrc` configuration** required
- ✅ **Works immediately** in Unity Package Manager
- ✅ **Full semantic versioning** support

### Available Packages
- `com.klumhru.wrapper.google-protobuf` - Protocol Buffers for Unity
- `com.klumhru.wrapper.unitask` - UniTask async/await support
- `com.klumhru.wrapper.system-io-pipelines` - System.IO.Pipelines for Unity

Browse all packages at: https://www.npmjs.com/org/klumhru

### Alternative: Install via Git URL
If you prefer, you can still install packages directly from GitHub:

```json
{
  "dependencies": {
    "com.klumhru.wrapper.google-protobuf": "https://github.com/klumhru/package-wrappers-unity.git?path=packages/com.klumhru.wrapper.google-protobuf"
  }
}
```

**Note:** Git URL installation doesn't support automatic version resolution and updates like registry-based installation.

## 🚀 CI/CD Automation

The included GitHub Actions workflow automatically:
- **Monitors** configuration changes in `config/packages.yaml`
- **Builds** packages when source repositories are updated
- **Runs** tests and quality checks with 50%+ code coverage
- **Publishes** packages to npmjs.org using npm CLI
- **Schedules** daily checks for upstream updates
- **Auto-detects** GitHub repository context for seamless CI publishing
- **Uses your NPM_TOKEN** secret for authenticated publishing

### CI/CD Features
- ✅ **Zero-configuration publishing** - works out of the box with NPM_TOKEN secret
- ✅ **Free npmjs.org hosting** - no authentication required for users
- ✅ **Smart caching** and artifact management
- ✅ **Quality gates** with automated testing and linting
- ✅ **Coverage reporting** with Codecov integration
- ✅ **Manual triggers** for specific package builds

## ⚙️ Configuration Examples

### Complex Package Configuration
```yaml
packages:
  - name: "com.company.advanced-package"
    display_name: "Advanced Package"
    description: "A complex package with dependencies"
    version: "2.1.0"
    author: "Company Name <dev@company.com>"

    source:
      type: git
      url: "https://github.com/company/advanced-repo.git"
      ref: "v2.1.0"

    extract_path: "src/main"
    namespace: "Company.Advanced"
    asmdef_name: "Company.Advanced.Runtime"

    dependencies:
      "com.unity.mathematics": "1.2.6"
      "com.unity.collections": "1.2.4"

    keywords: ["math", "collections", "performance"]

    assembly_references: ["Unity.Mathematics", "Unity.Collections"]
    define_constraints: ["UNITY_2021_3_OR_NEWER"]
    platforms: ["Editor", "Standalone", "iOS", "Android"]

    package_json_extra:
      license: "MIT"
      homepage: "https://company.com/packages"
      repository: "https://github.com/company/advanced-repo"

    asmdef_extra:
      allowUnsafeCode: true
      autoReferenced: false
```

## 📄 License

MIT License - see LICENSE file for details
