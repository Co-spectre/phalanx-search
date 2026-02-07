"""
Phalanx Search - File Scanner
High-performance recursive file discovery across the filesystem.
Finds all supported documents in configured directories.
"""

import os
import sys
import fnmatch
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Optional, Callable
from dataclasses import dataclass, field
from rich.console import Console

console = Console()

# Import settings
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import (
    SUPPORTED_EXTENSIONS, EXCLUDED_DIRS, EXCLUDED_PATTERNS,
    MAX_FILE_SIZE_MB, CRAWLER_STATE_DIR
)


@dataclass
class FileInfo:
    """Information about a discovered file"""
    filepath: str
    filename: str
    extension: str
    size_bytes: int
    modified_time: float
    file_hash: str = ""
    needs_indexing: bool = True


class ScanStateDB:
    """
    SQLite-backed persistent state for the file scanner.
    Tracks which files have been scanned, their modification times,
    and enables resumable scanning.
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(CRAWLER_STATE_DIR) / "scan_state.db")
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scanned_files (
                    filepath TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    modified_time REAL NOT NULL,
                    indexed_at TEXT,
                    file_hash TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scan_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    directories TEXT NOT NULL,
                    files_found INTEGER DEFAULT 0,
                    files_new INTEGER DEFAULT 0,
                    files_modified INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON scanned_files(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_extension ON scanned_files(extension)
            """)
            conn.commit()
            conn.close()

    def get_file_record(self, filepath: str) -> Optional[Dict]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM scanned_files WHERE filepath = ?", (filepath,)
            ).fetchone()
            conn.close()
            return dict(row) if row else None

    def upsert_file(self, file_info: FileInfo, status: str = "pending"):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT INTO scanned_files (filepath, filename, extension, size_bytes, modified_time, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET
                    size_bytes = excluded.size_bytes,
                    modified_time = excluded.modified_time,
                    status = excluded.status
            """, (
                file_info.filepath, file_info.filename, file_info.extension,
                file_info.size_bytes, file_info.modified_time, status
            ))
            conn.commit()
            conn.close()

    def mark_indexed(self, filepath: str):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                UPDATE scanned_files SET status = 'indexed', indexed_at = ?
                WHERE filepath = ?
            """, (datetime.now().isoformat(), filepath))
            conn.commit()
            conn.close()

    def mark_failed(self, filepath: str):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "UPDATE scanned_files SET status = 'failed' WHERE filepath = ?",
                (filepath,)
            )
            conn.commit()
            conn.close()

    def mark_deleted(self, filepath: str):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "DELETE FROM scanned_files WHERE filepath = ?", (filepath,)
            )
            conn.commit()
            conn.close()

    def get_pending_files(self, limit: int = 100) -> List[Dict]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM scanned_files WHERE status = 'pending' LIMIT ?",
                (limit,)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def get_all_indexed_paths(self) -> Set[str]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT filepath FROM scanned_files WHERE status = 'indexed'"
            ).fetchall()
            conn.close()
            return {r[0] for r in rows}

    def get_stats(self) -> Dict:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            total = conn.execute("SELECT COUNT(*) FROM scanned_files").fetchone()[0]
            indexed = conn.execute(
                "SELECT COUNT(*) FROM scanned_files WHERE status = 'indexed'"
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM scanned_files WHERE status = 'pending'"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM scanned_files WHERE status = 'failed'"
            ).fetchone()[0]
            conn.close()
            return {
                "total_discovered": total,
                "indexed": indexed,
                "pending": pending,
                "failed": failed,
            }

    def get_total_count(self) -> int:
        """Quick count of all discovered files."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            total = conn.execute("SELECT COUNT(*) FROM scanned_files").fetchone()[0]
            conn.close()
            return total


class FileScanner:
    """
    High-performance filesystem scanner.
    Discovers all supported files across configured directories.
    Uses incremental scanning — only processes new/modified files.
    """

    def __init__(self, state_db: ScanStateDB = None):
        self.state_db = state_db or ScanStateDB()
        self._supported_extensions = set(SUPPORTED_EXTENSIONS.keys())
        self._excluded_dirs = EXCLUDED_DIRS
        self._excluded_patterns = EXCLUDED_PATTERNS
        self._cancel_flag = threading.Event()

    def scan_directories(
        self,
        directories: List[str],
        progress_callback: Optional[Callable[[str, int], None]] = None,
    ) -> Dict:
        """
        Scan multiple directories for supported files.
        Incremental: skips files already indexed with same mtime.

        Args:
            directories: List of directory paths to scan
            progress_callback: Optional callback(current_file, files_found_so_far)

        Returns:
            Dict with scan statistics
        """
        self._cancel_flag.clear()
        stats = {
            "directories_scanned": 0,
            "files_found": 0,
            "files_new": 0,
            "files_modified": 0,
            "files_skipped": 0,
            "errors": 0,
        }

        console.print(f"[bold cyan]🔍 Starting system scan across {len(directories)} directories...[/bold cyan]")

        for directory in directories:
            if self._cancel_flag.is_set():
                break

            dir_path = Path(directory)
            if not dir_path.exists() or not dir_path.is_dir():
                console.print(f"[yellow]⚠ Skipping non-existent directory: {directory}[/yellow]")
                continue

            stats["directories_scanned"] += 1
            self._scan_directory(dir_path, stats, progress_callback)

        console.print(f"[bold green]✅ Scan complete: {stats['files_found']} files found, "
                       f"{stats['files_new']} new, {stats['files_modified']} modified[/bold green]")
        return stats

    def _scan_directory(
        self,
        directory: Path,
        stats: Dict,
        progress_callback: Optional[Callable] = None,
    ):
        """Recursively scan a single directory using os.scandir for speed."""
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if self._cancel_flag.is_set():
                        return

                    try:
                        # Skip excluded directories
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name in self._excluded_dirs or entry.name.startswith('.'):
                                continue
                            self._scan_directory(Path(entry.path), stats, progress_callback)
                            continue

                        # Skip non-files
                        if not entry.is_file(follow_symlinks=False):
                            continue

                        # Check extension
                        ext = Path(entry.name).suffix.lower()
                        if ext not in self._supported_extensions:
                            continue

                        # Check excluded patterns
                        if self._is_excluded_file(entry.name):
                            continue

                        # Get file info
                        try:
                            stat = entry.stat(follow_symlinks=False)
                        except OSError:
                            stats["errors"] += 1
                            continue

                        # Skip files too large
                        if stat.st_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                            continue

                        # Skip empty files
                        if stat.st_size == 0:
                            continue

                        filepath = str(Path(entry.path).resolve())
                        stats["files_found"] += 1

                        # Check if file needs indexing (new or modified)
                        existing = self.state_db.get_file_record(filepath)

                        file_info = FileInfo(
                            filepath=filepath,
                            filename=entry.name,
                            extension=ext,
                            size_bytes=stat.st_size,
                            modified_time=stat.st_mtime,
                        )

                        if existing is None:
                            # New file
                            file_info.needs_indexing = True
                            self.state_db.upsert_file(file_info, status="pending")
                            stats["files_new"] += 1
                        elif existing["modified_time"] < stat.st_mtime:
                            # Modified file
                            file_info.needs_indexing = True
                            self.state_db.upsert_file(file_info, status="pending")
                            stats["files_modified"] += 1
                        else:
                            # Already indexed and not modified
                            stats["files_skipped"] += 1
                            continue

                        if progress_callback:
                            progress_callback(filepath, stats["files_found"])

                    except PermissionError:
                        continue
                    except Exception as e:
                        stats["errors"] += 1
                        continue

        except PermissionError:
            pass
        except Exception as e:
            stats["errors"] += 1

    def _is_excluded_file(self, filename: str) -> bool:
        """Check if a filename matches any exclusion pattern."""
        for pattern in self._excluded_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False

    def cancel(self):
        """Cancel an ongoing scan."""
        self._cancel_flag.set()

    def get_pending_files(self, limit: int = 100) -> List[Dict]:
        """Get files that need indexing."""
        return self.state_db.get_pending_files(limit)

    def get_stats(self) -> Dict:
        """Get scanner statistics."""
        return self.state_db.get_stats()
