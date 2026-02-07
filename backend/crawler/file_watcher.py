"""
Phalanx Search - File Watcher
Real-time filesystem monitoring using watchdog.
Detects file creates, modifications, and deletions.
"""

import sys
import time
import threading
from pathlib import Path
from typing import List, Dict, Optional, Callable, Set
from collections import defaultdict
from rich.console import Console

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
    FileMovedEvent,
)

console = Console()

sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import (
    SUPPORTED_EXTENSIONS, EXCLUDED_DIRS, EXCLUDED_PATTERNS,
    CRAWLER_DEBOUNCE_SECONDS, MAX_FILE_SIZE_MB
)


class DebouncedHandler(FileSystemEventHandler):
    """
    Filesystem event handler with debouncing.
    Collects rapid file changes and batches them together.
    """

    def __init__(
        self,
        on_files_changed: Callable[[List[Dict]], None],
        debounce_seconds: float = CRAWLER_DEBOUNCE_SECONDS,
    ):
        super().__init__()
        self._on_files_changed = on_files_changed
        self._debounce_seconds = debounce_seconds
        self._pending: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._supported_extensions = set(SUPPORTED_EXTENSIONS.keys())
        self._excluded_dirs = EXCLUDED_DIRS

    def _should_process(self, path: str) -> bool:
        """Check if a file event should be processed."""
        p = Path(path)

        # Must be a supported extension
        if p.suffix.lower() not in self._supported_extensions:
            return False

        # Check excluded directories
        for part in p.parts:
            if part in self._excluded_dirs or part.startswith('.'):
                return False

        # Check file size (only for existing files)
        if p.exists():
            try:
                if p.stat().st_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                    return False
                if p.stat().st_size == 0:
                    return False
            except OSError:
                return False

        return True

    def on_created(self, event):
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            self._add_event(event.src_path, "created")

    def on_modified(self, event):
        if event.is_directory:
            return
        if self._should_process(event.src_path):
            self._add_event(event.src_path, "modified")

    def on_deleted(self, event):
        if event.is_directory:
            return
        # For deletions, skip extension check (file is gone)
        p = Path(event.src_path)
        if p.suffix.lower() in self._supported_extensions:
            self._add_event(event.src_path, "deleted")

    def on_moved(self, event):
        if event.is_directory:
            return
        # Treat move as delete old + create new
        p_src = Path(event.src_path)
        p_dst = Path(event.dest_path)

        if p_src.suffix.lower() in self._supported_extensions:
            self._add_event(event.src_path, "deleted")

        if self._should_process(event.dest_path):
            self._add_event(event.dest_path, "created")

    def _add_event(self, filepath: str, action: str):
        """Add an event to the debounce buffer."""
        resolved = str(Path(filepath).resolve())
        with self._lock:
            self._pending[resolved] = {
                "filepath": resolved,
                "action": action,
                "timestamp": time.time(),
            }
            # Reset debounce timer
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_seconds, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self):
        """Flush all pending events to the callback."""
        with self._lock:
            if not self._pending:
                return
            events = list(self._pending.values())
            self._pending.clear()
            self._timer = None

        try:
            self._on_files_changed(events)
        except Exception as e:
            console.print(f"[red]Error processing file events: {e}[/red]")


class FileWatcher:
    """
    Real-time filesystem watcher.
    Monitors configured directories for file changes and triggers indexing.
    """

    def __init__(self, on_files_changed: Callable[[List[Dict]], None]):
        self._on_files_changed = on_files_changed
        self._observer: Optional[Observer] = None
        self._watched_dirs: Set[str] = set()
        self._handler = DebouncedHandler(on_files_changed)
        self._running = False

    def start(self, directories: List[str]):
        """Start watching the specified directories."""
        if self._running:
            self.stop()

        self._observer = Observer()
        self._observer.daemon = True

        for directory in directories:
            dir_path = Path(directory)
            if dir_path.exists() and dir_path.is_dir():
                try:
                    self._observer.schedule(
                        self._handler, str(dir_path), recursive=True
                    )
                    self._watched_dirs.add(str(dir_path))
                    console.print(f"[dim]  👁 Watching: {dir_path}[/dim]")
                except Exception as e:
                    console.print(f"[yellow]⚠ Cannot watch {directory}: {e}[/yellow]")

        if self._watched_dirs:
            self._observer.start()
            self._running = True
            console.print(f"[green]✅ File watcher active on {len(self._watched_dirs)} directories[/green]")
        else:
            console.print("[yellow]⚠ No directories to watch[/yellow]")

    def stop(self):
        """Stop watching all directories."""
        if self._observer and self._running:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._running = False
            self._watched_dirs.clear()
            console.print("[dim]File watcher stopped[/dim]")

    def add_directory(self, directory: str):
        """Add a directory to watch at runtime."""
        if not self._running or self._observer is None:
            return

        dir_path = Path(directory)
        if dir_path.exists() and str(dir_path) not in self._watched_dirs:
            try:
                self._observer.schedule(
                    self._handler, str(dir_path), recursive=True
                )
                self._watched_dirs.add(str(dir_path))
                console.print(f"[dim]  👁 Now watching: {dir_path}[/dim]")
            except Exception as e:
                console.print(f"[yellow]⚠ Cannot watch {directory}: {e}[/yellow]")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def watched_directories(self) -> Set[str]:
        return self._watched_dirs.copy()
