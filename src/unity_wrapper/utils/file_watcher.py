"""File watcher for monitoring configuration changes."""

import time
import logging
from pathlib import Path
from typing import Callable, List, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


logger = logging.getLogger(__name__)


class ConfigChangeHandler(FileSystemEventHandler):
    """Handler for configuration file changes."""

    def __init__(self, callback: Callable[[List[Path]], None]):
        """Initialize with callback function."""
        self.callback = callback
        self.changed_files: Set[Path] = set()
        self.last_call_time = 0
        self.debounce_delay = 1.0  # 1 second debounce

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(str(event.src_path))

        # Only watch YAML configuration files
        if file_path.suffix.lower() in [".yaml", ".yml"]:
            self.changed_files.add(file_path)
            self._debounced_callback()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        self.on_modified(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events."""
        if hasattr(event, "dest_path"):
            dest_path = Path(str(event.dest_path))
            if dest_path.suffix.lower() in [".yaml", ".yml"]:
                self.changed_files.add(dest_path)
                self._debounced_callback()

    def _debounced_callback(self) -> None:
        """Call callback with debouncing to avoid multiple rapid calls."""
        current_time = time.time()

        if current_time - self.last_call_time > self.debounce_delay:
            if self.changed_files:
                changed_list = list(self.changed_files)
                self.changed_files.clear()
                self.callback(changed_list)
                self.last_call_time = current_time


class FileWatcher:
    """Watches configuration directory for changes and triggers rebuilds."""

    def __init__(self, config_dir: Path, callback: Callable[[List[Path]], None]):
        """Initialize file watcher."""
        self.config_dir = Path(config_dir)
        self.callback = callback
        self.observer = Observer()
        self.handler = ConfigChangeHandler(callback)

    def start(self) -> None:
        """Start watching for file changes."""
        if not self.config_dir.exists():
            logger.warning(f"Configuration directory does not exist: {self.config_dir}")
            return

        self.observer.schedule(self.handler, str(self.config_dir), recursive=True)

        self.observer.start()
        logger.info(f"Started watching: {self.config_dir}")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop watching for file changes."""
        self.observer.stop()
        self.observer.join()
        logger.info("File watcher stopped")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        """Context manager exit."""
        self.stop()
