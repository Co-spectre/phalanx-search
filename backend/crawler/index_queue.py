"""
Phalanx Search - Index Queue
Priority-based background indexing with rate limiting.
Ensures user actions are processed before background crawl work.
"""

import sys
import time
import queue
import threading
from pathlib import Path
from typing import Dict, List, Callable, Optional
from enum import IntEnum
from dataclasses import dataclass, field
from rich.console import Console

console = Console()

sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import CRAWLER_BATCH_SIZE, CRAWLER_MAX_WORKERS


class Priority(IntEnum):
    """Task priority levels. Lower number = higher priority."""
    USER_UPLOAD = 0      # User explicitly uploaded a file
    FILE_CHANGE = 1      # Live file change detected by watcher
    BACKGROUND_SCAN = 2  # Background crawl discovery


@dataclass(order=True)
class IndexTask:
    """A file indexing task with priority."""
    priority: int
    filepath: str = field(compare=False)
    action: str = field(compare=False, default="index")  # index, reindex, delete
    timestamp: float = field(compare=False, default_factory=time.time)
    retries: int = field(compare=False, default=0)


class IndexQueue:
    """
    Priority queue for background file indexing.
    Processes files in priority order with rate limiting.
    """

    def __init__(
        self,
        index_callback: Callable[[str], Dict],
        delete_callback: Callable[[str], Dict],
        max_workers: int = CRAWLER_MAX_WORKERS,
    ):
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._index_callback = index_callback
        self._delete_callback = delete_callback
        self._max_workers = max_workers
        self._workers: List[threading.Thread] = []
        self._running = False
        self._paused = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self._lock = threading.Lock()

        # Stats
        self._processed = 0
        self._failed = 0
        self._total_queued = 0

        # Callbacks for UI updates
        self.on_progress: Optional[Callable[[str, int, int], None]] = None
        self.on_file_indexed: Optional[Callable[[str, bool], None]] = None

    def start(self):
        """Start processing the queue."""
        if self._running:
            return

        self._running = True
        for i in range(self._max_workers):
            t = threading.Thread(target=self._worker_loop, name=f"indexer-{i}", daemon=True)
            t.start()
            self._workers.append(t)

        console.print(f"[green]✅ Index queue started with {self._max_workers} workers[/green]")

    def stop(self):
        """Stop processing the queue."""
        self._running = False
        self._pause_event.set()  # Unpause to let threads exit
        # Put sentinel values to unblock workers
        for _ in self._workers:
            self._queue.put(IndexTask(priority=999, filepath="__STOP__", action="stop"))
        for t in self._workers:
            t.join(timeout=5)
        self._workers.clear()

    def pause(self):
        """Pause queue processing (e.g., during active search)."""
        self._paused = True
        self._pause_event.clear()

    def resume(self):
        """Resume queue processing."""
        self._paused = False
        self._pause_event.set()

    def add_file(self, filepath: str, action: str = "index", priority: Priority = Priority.BACKGROUND_SCAN):
        """Add a file to the indexing queue."""
        task = IndexTask(
            priority=priority.value,
            filepath=filepath,
            action=action,
        )
        self._queue.put(task)
        with self._lock:
            self._total_queued += 1

    def add_user_file(self, filepath: str):
        """Add a user-uploaded file (highest priority)."""
        self.add_file(filepath, action="index", priority=Priority.USER_UPLOAD)

    def add_changed_files(self, events: List[Dict]):
        """Add file change events from the watcher."""
        for event in events:
            action = event.get("action", "index")
            filepath = event.get("filepath", "")
            if action == "deleted":
                self.add_file(filepath, action="delete", priority=Priority.FILE_CHANGE)
            else:
                self.add_file(filepath, action="index", priority=Priority.FILE_CHANGE)

    def add_scan_results(self, filepaths: List[str]):
        """Add discovered files from a background scan (lowest priority)."""
        for fp in filepaths:
            self.add_file(fp, action="index", priority=Priority.BACKGROUND_SCAN)

    def _worker_loop(self):
        """Worker thread main loop."""
        while self._running:
            # Respect pause
            self._pause_event.wait()

            try:
                task: IndexTask = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if task.action == "stop" or task.filepath == "__STOP__":
                break

            try:
                self._process_task(task)
            except Exception as e:
                console.print(f"[red]Worker error: {e}[/red]")
                with self._lock:
                    self._failed += 1
            finally:
                self._queue.task_done()

    def _process_task(self, task: IndexTask):
        """Process a single indexing task."""
        filepath = task.filepath

        if task.action == "delete":
            try:
                filename = Path(filepath).name
                self._delete_callback(filename)
                if self.on_file_indexed:
                    self.on_file_indexed(filepath, True)
            except Exception as e:
                console.print(f"[red]Delete failed for {filepath}: {e}[/red]")
            return

        # Index or re-index
        if not Path(filepath).exists():
            return

        try:
            result = self._index_callback(filepath)
            success = result.get("success", False)

            with self._lock:
                if success:
                    self._processed += 1
                else:
                    self._failed += 1

            if self.on_file_indexed:
                self.on_file_indexed(filepath, success)

            if self.on_progress:
                self.on_progress(filepath, self._processed, self._total_queued)

        except Exception as e:
            with self._lock:
                self._failed += 1

            # Retry up to 2 times for transient errors
            if task.retries < 2:
                task.retries += 1
                task.priority = max(task.priority, Priority.BACKGROUND_SCAN.value)
                self._queue.put(task)

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    @property
    def is_idle(self) -> bool:
        return self._queue.empty()

    def get_stats(self) -> Dict:
        with self._lock:
            return {
                "pending": self._queue.qsize(),
                "processed": self._processed,
                "failed": self._failed,
                "total_queued": self._total_queued,
                "is_paused": self._paused,
                "workers": len(self._workers),
            }
