"""Command line interface for Unity Package Wrapper."""

import click
import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

from .core.package_builder import PackageBuilder
from .core.config_manager import ConfigManager
from .utils.file_watcher import FileWatcher
from .utils.github_publisher import GitHubPublisher


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
@click.option(
    "--config", "-c", default="config", help="Configuration directory path"
)
@click.option(
    "--output", "-o", default="packages", help="Output directory for packages"
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx: click.Context, config: str, output: str, verbose: bool) -> None:
    """Unity Package Wrapper - Build OSS Unity Packages."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    ctx.ensure_object(dict)
    ctx.obj["config_path"] = Path(config)
    ctx.obj["output_path"] = Path(output)


@cli.command()
@click.argument("package_name", required=False)
@click.pass_context
def build(ctx: click.Context, package_name: Optional[str]) -> None:
    """Build Unity packages. If package_name is specified, build only that."""
    config_path: Path = ctx.obj["config_path"]
    output_path: Path = ctx.obj["output_path"]

    try:
        with PackageBuilder(config_path, output_path) as builder:
            if package_name:
                click.echo(f"Building package: {package_name}")
                package_path = builder.build_package(package_name)
                click.echo(f"Package built successfully: {package_path}")
            else:
                click.echo("Building all packages...")
                built_packages = builder.build_all_packages()
                click.echo(
                    f"Successfully built {len(built_packages)} packages:"
                )
                for package_path in built_packages:
                    click.echo(f"  - {package_path}")

    except Exception as e:
        click.echo(f"Error building packages: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def watch(ctx: click.Context) -> None:
    """Watch for configuration changes and automatically rebuild packages."""
    config_path: Path = ctx.obj["config_path"]
    output_path: Path = ctx.obj["output_path"]

    click.echo("Starting file watcher...")
    click.echo("Press Ctrl+C to stop")

    try:

        def on_change(changed_files: List[Path]) -> None:
            click.echo(f"Configuration changed: {changed_files}")
            with PackageBuilder(config_path, output_path) as builder:
                updated_packages = builder.check_for_updates()
                if updated_packages:
                    click.echo(
                        f"Rebuilding {len(updated_packages)} packages..."
                    )
                    for package_name in updated_packages:
                        try:
                            package_path = builder.build_package(package_name)
                            click.echo(f"Rebuilt: {package_path}")
                        except Exception as e:
                            click.echo(
                                f"Failed to rebuild {package_name}: {e}",
                                err=True,
                            )
                else:
                    click.echo("No packages need rebuilding")

        watcher = FileWatcher(config_path, on_change)
        watcher.start()

    except KeyboardInterrupt:
        click.echo("\\nStopping file watcher...")
    except Exception as e:
        click.echo(f"Error in file watcher: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def check(ctx: click.Context) -> None:
    """Check which packages need updates."""
    config_path: Path = ctx.obj["config_path"]
    output_path: Path = ctx.obj["output_path"]

    try:
        with PackageBuilder(config_path, output_path) as builder:
            updated_packages = builder.check_for_updates()

            if updated_packages:
                click.echo(
                    f"Packages needing updates ({len(updated_packages)}):"
                )
                for package_name in updated_packages:
                    click.echo(f"  - {package_name}")
            else:
                click.echo("All packages are up to date")

    except Exception as e:
        click.echo(f"Error checking for updates: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("package_name", required=False)
@click.option("--token", help="GitHub token for authentication")
@click.pass_context
def publish(
    ctx: click.Context, package_name: Optional[str], token: Optional[str]
) -> None:
    """Publish packages to GitHub Package Registry."""
    config_path: Path = ctx.obj["config_path"]
    output_path: Path = ctx.obj["output_path"]

    try:
        config_manager = ConfigManager(config_path)
        github_settings = config_manager.get_github_settings()

        publisher = GitHubPublisher(
            token=token or github_settings.get("token"),
            registry_url=github_settings.get("registry_url"),
            owner=github_settings.get("owner"),
            repository=github_settings.get("repository"),
        )

        if package_name:
            package_path: Path = output_path / package_name
            if not package_path.exists():
                click.echo(f"Package not found: {package_path}", err=True)
                sys.exit(1)

            click.echo(f"Publishing package: {package_name}")
            publisher.publish_package(package_path)
            click.echo(f"Package published successfully: {package_name}")
        else:
            click.echo("Publishing all packages...")
            published_count = 0

            for package_dir in output_path.iterdir():
                if (
                    package_dir.is_dir()
                    and (package_dir / "package.json").exists()
                ):
                    try:
                        publisher.publish_package(package_dir)
                        click.echo(f"Published: {package_dir.name}")
                        published_count += 1
                    except Exception as e:
                        click.echo(
                            f"Failed to publish {package_dir.name}: {e}",
                            err=True,
                        )

            click.echo(f"Successfully published {published_count} packages")

    except Exception as e:
        click.echo(f"Error publishing packages: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--name", required=True, help="Package name")
@click.option("--url", required=True, help="Git repository URL")
@click.option("--ref", default="main", help="Git ref (branch, tag, or commit)")
@click.option(
    "--extract-path", default=".", help="Path to extract from repository"
)
@click.option("--namespace", help="C# namespace for the package")
@click.pass_context
def add(
    ctx: click.Context,
    name: str,
    url: str,
    ref: str,
    extract_path: str,
    namespace: Optional[str],
) -> None:
    """Add a new package configuration."""
    config_path: Path = ctx.obj["config_path"]

    try:
        config_manager = ConfigManager(config_path)

        package_config: Dict[str, Any] = {
            "name": name,
            "source": {"type": "git", "url": url, "ref": ref},
            "extract_path": extract_path,
        }

        if namespace:
            package_config["namespace"] = namespace

        config_manager.add_package(package_config)
        config_manager.save_configuration()

        click.echo(f"Package '{name}' added successfully")

    except Exception as e:
        click.echo(f"Error adding package: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("package_name")
@click.pass_context
def remove(ctx: click.Context, package_name: str) -> None:
    """Remove a package configuration."""
    config_path: Path = ctx.obj["config_path"]

    try:
        config_manager = ConfigManager(config_path)

        if config_manager.remove_package(package_name):
            config_manager.save_configuration()
            click.echo(f"Package '{package_name}' removed successfully")
        else:
            click.echo(f"Package '{package_name}' not found", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error removing package: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def list_packages(ctx: click.Context) -> None:
    """List all configured packages."""
    config_path: Path = ctx.obj["config_path"]

    try:
        config_manager = ConfigManager(config_path)
        package_names = config_manager.get_package_names()

        if package_names:
            click.echo(f"Configured packages ({len(package_names)}):")
            for package_name in package_names:
                package_config = config_manager.get_package_config(
                    package_name
                )
                if package_config is not None:
                    source = package_config["source"]
                    click.echo(
                        f"  - {package_name} ({source['url']}@{source['ref']})"
                    )
                else:
                    click.echo(f"  - {package_name} (configuration error)")
        else:
            click.echo("No packages configured")

    except Exception as e:
        click.echo(f"Error listing packages: {e}", err=True)
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
