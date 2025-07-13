.PHONY: install install-dev test lint format clean build publish watch help

# Variables
PYTHON := python
PIP := pip
PYTEST := pytest
BLACK := black
FLAKE8 := flake8
MYPY := mypy

help: ## Show this help message
	@echo "Unity Package Wrapper - Development Commands"
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install the package
	$(PIP) install -e .

install-dev: ## Install development dependencies
	$(PIP) install -e ".[dev]"

test: ## Run tests
	$(PYTEST) tests/ -v --cov=unity_wrapper --cov-report=term-missing

test-coverage: ## Run tests with coverage report
	$(PYTEST) tests/ -v --cov=unity_wrapper --cov-report=html --cov-report=xml

lint: ## Run linting checks
	$(BLACK) --check src tests
	$(FLAKE8) src tests
	$(MYPY) src

format: ## Format code
	$(BLACK) src tests

clean: ## Clean temporary files
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf coverage.xml
	rm -rf .unity_wrapper_temp/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: ## Build Unity packages
	unity-wrapper build

build-package: ## Build specific package (usage: make build-package PACKAGE=com.example.package)
	unity-wrapper build $(PACKAGE)

watch: ## Watch for configuration changes and auto-rebuild
	unity-wrapper watch

check: ## Check which packages need updates
	unity-wrapper check

publish: ## Publish packages to GitHub Package Registry
	unity-wrapper publish

list: ## List configured packages
	unity-wrapper list-packages

setup-config: ## Create example configuration files
	@echo "Creating example configuration files..."
	@mkdir -p config
	@if [ ! -f config/packages.yaml ]; then \
		echo "# Example packages configuration" > config/packages.yaml; \
		echo "packages:" >> config/packages.yaml; \
		echo "  - name: \"com.example.package\"" >> config/packages.yaml; \
		echo "    source:" >> config/packages.yaml; \
		echo "      type: git" >> config/packages.yaml; \
		echo "      url: \"https://github.com/example/repo.git\"" >> config/packages.yaml; \
		echo "      ref: \"main\"" >> config/packages.yaml; \
		echo "    extract_path: \"src\"" >> config/packages.yaml; \
		echo "    namespace: \"Example.Package\"" >> config/packages.yaml; \
	fi
	@if [ ! -f config/settings.yaml ]; then \
		echo "# Global settings" > config/settings.yaml; \
		echo "output_dir: \"packages\"" >> config/settings.yaml; \
		echo "work_dir: \".unity_wrapper_temp\"" >> config/settings.yaml; \
		echo "github:" >> config/settings.yaml; \
		echo "  token: \"\"" >> config/settings.yaml; \
		echo "  owner: \"\"" >> config/settings.yaml; \
		echo "  repository: \"\"" >> config/settings.yaml; \
	fi
	@echo "Configuration files created in config/"

dev-setup: install-dev setup-config ## Complete development setup
	@echo "Development environment setup complete!"
	@echo "Next steps:"
	@echo "1. Configure your GitHub token in config/settings.yaml"
	@echo "2. Add package definitions to config/packages.yaml"
	@echo "3. Run 'make build' to build packages"

# Docker targets (optional)
docker-build: ## Build Docker image
	docker build -t unity-package-wrapper .

docker-run: ## Run in Docker container
	docker run -v $(PWD)/config:/app/config -v $(PWD)/packages:/app/packages unity-package-wrapper

# Git hooks
install-hooks: ## Install pre-commit hooks
	pre-commit install

run-hooks: ## Run pre-commit hooks on all files
	pre-commit run --all-files
