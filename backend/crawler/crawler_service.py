"""
Phalanx Search - Crawler Service
Orchestrates file scanning, watching, and background indexing.
The central coordinator for system-wide document discovery.
"""

import sys
import json
import threading
import time
from pathlib import Path
from typing import List, Dict, Optional, Callable, Set
from rich.console import Console

console = Console()

sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import (
    DEFAULT_WATCH_DIRS, CRAWLER_STATE_DIR,
    CRAWLER_SCAN_INTERVAL_HOURS, CRAWLER_BATCH_SIZE
)
from backend.crawler.file_scanner import FileScanner, ScanStateDB
from backend.crawler.file_watcher import FileWatcher
from backend.crawler.index_queue import IndexQueue, Priority


class CrawlerService:
    """
    Main crawler service that orchestrates:
    1. Initial file discovery scan
    2. Live filesystem monitoring
    3. Background indexing queue
    4. Persistent state management

    Usage:
        crawler = CrawlerService(
            index_callback=search_engine.index_document,
            delete_callback=search_engine.delete_document,
        )
        crawler.start()
    """

    def __init__(
        self,
        index_callback: Callable[[str], Dict],
        delete_callback: Callable[[str], Dict],
    ):
        self._state_db = ScanStateDB()
        self._scanner = FileScanner(state_db=self._state_db)
        self._queue = IndexQueue(
            index_callback=index_callback,
            delete_callback=delete_callback,
        )
        self._watcher = FileWatcher(on_files_changed=self._on_files_changed)

        # Configured watch directories
        self._watch_dirs: List[str] = self._load_watch_dirs()

        # State
        self._running = False
        self._scan_thread: Optional[threading.Thread] = None
        self._periodic_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # UI callbacks
        self.on_scan_progress: Optional[Callable[[str, int], None]] = None
        self.on_scan_complete: Optional[Callable[[Dict], None]] = None
        self.on_file_indexed: Optional[Callable[[str, bool], None]] = None
        self.on_queue_progress: Optional[Callable[[str, int, int], None]] = None

    def start(self):
        """Start the crawler service: watcher + queue + initial scan."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()

        console.print("[bold cyan]🚀 Starting Phalanx Crawler Service...[/bold cyan]")

        # Wire up callbacks
        self._queue.on_file_indexed = self._on_file_indexed
        self._queue.on_progress = self.on_queue_progress

        # 1. Start the indexing queue workers
        self._queue.start()

        # 2. Start the filesystem watcher
        if self._watch_dirs:
            self._watcher.start(self._watch_dirs)

        # 3. Kick off initial scan in background
        self._scan_thread = threading.Thread(
            target=self._run_initial_scan, daemon=True, name="initial-scan"
        )
        self._scan_thread.start()

        # 4. Start periodic re-scan
        self._periodic_thread = threading.Thread(
            target=self._periodic_scan_loop, daemon=True, name="periodic-scan"
        )
        self._periodic_thread.start()

        console.print("[bold green]✅ Crawler service running[/bold green]")

    def stop(self):
        """Stop all crawler components."""
        self._running = False
        self._stop_event.set()
        self._scanner.cancel()
        self._watcher.stop()
        self._queue.stop()
        console.print("[dim]Crawler service stopped[/dim]")

    def _run_initial_scan(self):
        """Run the initial filesystem scan and queue discovered files."""
        try:
            console.print("[cyan]📂 Running initial file scan...[/cyan]")
            stats = self._scanner.scan_directories(
                self._watch_dirs,
                progress_callback=self.on_scan_progress,
            )

            # Queue all pending files for indexing
            pending = self._scanner.get_pending_files(limit=10000)
            if pending:
                filepaths = [f["filepath"] for f in pending]
                self._queue.add_scan_results(filepaths)
                console.print(f"[cyan]📥 Queued {len(filepaths)} files for background indexing[/cyan]")

            if self.on_scan_complete:
                self.on_scan_complete(stats)

        except Exception as e:
            console.print(f"[red]Initial scan error: {e}[/red]")

    def _periodic_scan_loop(self):
        """Periodically re-scan directories to catch missed changes."""
        interval = CRAWLER_SCAN_INTERVAL_HOURS * 3600
        while not self._stop_event.is_set():
            self._stop_event.wait(interval)
            if self._stop_event.is_set():
                break
            try:
                console.print("[dim]Running periodic re-scan...[/dim]")
                self._scanner.scan_directories(self._watch_dirs)
                pending = self._scanner.get_pending_files(limit=5000)
                if pending:
                    self._queue.add_scan_results([f["filepath"] for f in pending])
            except Exception as e:
                console.print(f"[red]Periodic scan error: {e}[/red]")

    def _on_files_changed(self, events: List[Dict]):
        """Handle file change events from the watcher."""
        self._queue.add_changed_files(events)

        # Update scanner state for new/modified files
        for event in events:
            action = event.get("action")
            filepath = event.get("filepath", "")
            if action == "deleted":
                self._state_db.mark_deleted(filepath)

    def _on_file_indexed(self, filepath: str, success: bool):
        """Handle file indexed callback."""
        if success:
            self._state_db.mark_indexed(filepath)
        else:
            self._state_db.mark_failed(filepath)

        if self.on_file_indexed:
            self.on_file_indexed(filepath, success)

    # ============== Watch Directory Management ==============

    def get_watch_dirs(self) -> List[str]:
        """Get current watch directories."""
        return self._watch_dirs.copy()

    def set_watch_dirs(self, directories: List[str]):
        """Update watch directories."""
        self._watch_dirs = [d for d in directories if Path(d).is_dir()]
        self._save_watch_dirs()

        # Restart watcher with new directories
        if self._running:
            self._watcher.stop()
            if self._watch_dirs:
                self._watcher.start(self._watch_dirs)

    def add_watch_dir(self, directory: str):
        """Add a single directory to watch."""
        dir_path = Path(directory)
        if dir_path.is_dir() and str(dir_path) not in self._watch_dirs:
            self._watch_dirs.append(str(dir_path))
            self._save_watch_dirs()

            if self._running:
                self._watcher.add_directory(str(dir_path))

                # Scan the new directory
                scan_thread = threading.Thread(
                    target=self._scan_single_dir,
                    args=(str(dir_path),),
                    daemon=True,
                )
                scan_thread.start()

    def remove_watch_dir(self, directory: str):
        """Remove a directory from watch list."""
        if directory in self._watch_dirs:
            self._watch_dirs.remove(directory)
            self._save_watch_dirs()
            # Watcher restart needed to remove a watch
            if self._running:
                self._watcher.stop()
                if self._watch_dirs:
                    self._watcher.start(self._watch_dirs)

    def _scan_single_dir(self, directory: str):
        """Scan a single newly-added directory."""
        try:
            stats = self._scanner.scan_directories(
                [directory], progress_callback=self.on_scan_progress
            )
            pending = self._scanner.get_pending_files(limit=5000)
            if pending:
                self._queue.add_scan_results([f["filepath"] for f in pending])
        except Exception as e:
            console.print(f"[red]Scan error for {directory}: {e}[/red]")

    # ============== Manual Operations ==============

    def index_file_now(self, filepath: str):
        """Immediately queue a file for indexing (user priority)."""
        self._queue.add_user_file(filepath)

    def index_directory_now(self, directory: str):
        """Immediately scan and index a directory (user priority)."""
        def _scan_and_queue():
            stats = self._scanner.scan_directories([directory])
            pending = self._scanner.get_pending_files(limit=10000)
            for f in pending:
                self._queue.add_file(
                    f["filepath"], action="index", priority=Priority.USER_UPLOAD
                )
        threading.Thread(target=_scan_and_queue, daemon=True).start()

    def trigger_full_rescan(self):
        """Trigger a full re-scan of all watch directories."""
        def _rescan():
            self._scanner.scan_directories(self._watch_dirs)
            pending = self._scanner.get_pending_files(limit=10000)
            if pending:
                self._queue.add_scan_results([f["filepath"] for f in pending])
        threading.Thread(target=_rescan, daemon=True).start()

    # ============== Persistence ==============

    def _load_watch_dirs(self) -> List[str]:
        """Load watch directories from config file."""
        config_path = Path(CRAWLER_STATE_DIR) / "watch_dirs.json"
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    dirs = json.load(f)
                # Filter to only existing directories
                return [d for d in dirs if Path(d).is_dir()]
            except Exception:
                pass
        return [d for d in DEFAULT_WATCH_DIRS if Path(d).is_dir()]

    def _save_watch_dirs(self):
        """Save watch directories to config file."""
        config_path = Path(CRAWLER_STATE_DIR) / "watch_dirs.json"
        try:
            with open(config_path, 'w') as f:
                json.dump(self._watch_dirs, f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving watch dirs: {e}[/red]")

    # ============== Stats ==============

    def get_stats(self) -> Dict:
        """Get comprehensive crawler statistics."""
        scanner_stats = self._scanner.get_stats()
        queue_stats = self._queue.get_stats()
        return {
            "running": self._running,
            "watcher_active": self._watcher.is_running,
            "watched_directories": list(self._watcher.watched_directories),
            "configured_directories": self._watch_dirs,
            "scanner": scanner_stats,
            "queue": queue_stats,
        }

    @property
    def running(self) -> bool:
        return self._running

    @property
    def watch_dirs(self) -> Set[str]:
        return set(self._watch_dirs)

    def get_status(self) -> Dict:
        """Lightweight status for UI polling."""
        try:
            total = self._state_db.get_total_count() if hasattr(self._state_db, 'get_total_count') else 0
        except Exception:
            total = 0
        return {
            "running": self._running,
            "total_files_discovered": total,
            "watch_dirs_count": len(self._watch_dirs),
        }
