"""
Phalanx Search - Desktop Application
System tray application with floating search overlay.
Native desktop integration with background file crawling.
"""

import sys
import os
import platform
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
import threading
import re

# IMPORTANT: Import torch FIRST before any other library to avoid
# DLL loading conflicts on Windows (WinError 1114 with c10.dll)
try:
    import torch
except ImportError:
    pass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QTabWidget, QFileDialog, QProgressBar, QComboBox, QSlider, QFrame,
    QScrollArea, QSplitter, QMessageBox, QStackedWidget, QSizePolicy,
    QSpacerItem, QGridLayout, QSystemTrayIcon, QMenu, QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QPoint
from PyQt6.QtGui import (
    QFont, QIcon, QColor, QPalette, QPixmap, QFontDatabase,
    QAction, QKeySequence, QShortcut, QPainter, QPen, QBrush,
)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import SUPPORTED_EXTENSIONS, DOCUMENTS_DIR, DEFAULT_WATCH_DIRS
from backend.search import search_engine

# Lazy import — crawler may not be installed yet on first run
_crawler_service = None

def get_crawler():
    global _crawler_service
    if _crawler_service is None:
        try:
            from backend.crawler import CrawlerService
            _crawler_service = CrawlerService(
                index_callback=search_engine.index_document,
                delete_callback=search_engine.delete_document,
            )
        except Exception:
            pass
    return _crawler_service


# ============== Color Scheme ==============
COLORS = {
    'bg_primary': '#09090b',
    'bg_secondary': '#18181b',
    'bg_tertiary': '#27272a',
    'bg_hover': '#3f3f46',
    'text_primary': '#fafafa',
    'text_secondary': '#a1a1aa',
    'text_muted': '#71717a',
    'accent': '#3b82f6',
    'accent_hover': '#2563eb',
    'border': '#27272a',
    'success': '#22c55e',
    'warning': '#eab308',
    'error': '#ef4444',
}

# ============== Stylesheet ==============
STYLESHEET = f"""
QMainWindow {{
    background-color: {COLORS['bg_primary']};
}}

QWidget {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_primary']};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}}

QLabel {{
    color: {COLORS['text_secondary']};
    padding: 2px;
}}

QLabel[class="title"] {{
    color: {COLORS['text_primary']};
    font-size: 24px;
    font-weight: bold;
}}

QLabel[class="subtitle"] {{
    color: {COLORS['text_muted']};
    font-size: 12px;
}}

QLabel[class="section"] {{
    color: {COLORS['text_muted']};
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QLineEdit {{
    background-color: {COLORS['bg_tertiary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 12px 16px;
    color: {COLORS['text_primary']};
    font-size: 14px;
}}

QLineEdit:focus {{
    border-color: {COLORS['accent']};
}}

QLineEdit::placeholder {{
    color: {COLORS['text_muted']};
}}

QPushButton {{
    background-color: {COLORS['accent']};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 500;
    font-size: 13px;
}}

QPushButton:hover {{
    background-color: {COLORS['accent_hover']};
}}

QPushButton:pressed {{
    background-color: #1d4ed8;
}}

QPushButton[class="secondary"] {{
    background-color: {COLORS['bg_tertiary']};
    border: 1px solid {COLORS['border']};
}}

QPushButton[class="secondary"]:hover {{
    background-color: {COLORS['bg_hover']};
}}

QPushButton[class="danger"] {{
    background-color: {COLORS['error']};
}}

QPushButton[class="danger"]:hover {{
    background-color: #dc2626;
}}

QComboBox {{
    background-color: {COLORS['bg_tertiary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 12px;
    color: {COLORS['text_primary']};
    min-width: 150px;
}}

QComboBox::drop-down {{
    border: none;
    width: 30px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {COLORS['text_secondary']};
    margin-right: 10px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['bg_hover']};
    color: {COLORS['text_primary']};
}}

QSlider::groove:horizontal {{
    background: {COLORS['bg_tertiary']};
    height: 6px;
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: {COLORS['accent']};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}

QSlider::sub-page:horizontal {{
    background: {COLORS['accent']};
    border-radius: 3px;
}}

QProgressBar {{
    background-color: {COLORS['bg_tertiary']};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {COLORS['accent']};
    border-radius: 4px;
}}

QTabWidget::pane {{
    border: none;
    background-color: {COLORS['bg_primary']};
}}

QTabBar::tab {{
    background-color: {COLORS['bg_secondary']};
    color: {COLORS['text_secondary']};
    padding: 12px 24px;
    margin-right: 4px;
    border-radius: 8px 8px 0 0;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background-color: {COLORS['bg_tertiary']};
    color: {COLORS['text_primary']};
}}

QTabBar::tab:hover:!selected {{
    background-color: {COLORS['bg_hover']};
}}

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    background-color: {COLORS['bg_secondary']};
    width: 10px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['bg_hover']};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QTextEdit {{
    background-color: {COLORS['bg_tertiary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 12px;
    color: {COLORS['text_secondary']};
}}

QFrame[class="card"] {{
    background-color: {COLORS['bg_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
}}

QFrame[class="card"]:hover {{
    border-color: {COLORS['bg_hover']};
    background-color: {COLORS['bg_tertiary']};
}}

QCheckBox {{
    color: {COLORS['text_secondary']};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {COLORS['border']};
    background-color: {COLORS['bg_tertiary']};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}
"""


# ============== Worker Threads ==============

class SearchWorker(QThread):
    """Background thread for search operations"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query: str, top_k: int, file_filter: str, search_mode: str):
        super().__init__()
        self.query = query
        self.top_k = top_k
        self.file_filter = file_filter
        self.search_mode = search_mode

    def run(self):
        try:
            results = search_engine.search(
                self.query,
                top_k=self.top_k,
                file_type_filter=self.file_filter,
                search_mode=self.search_mode
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class IndexWorker(QThread):
    """Background thread for indexing operations"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, files: List[str] = None, directory: str = None):
        super().__init__()
        self.files = files
        self.directory = directory

    def run(self):
        try:
            if self.directory:
                result = search_engine.index_directory(self.directory)
                self.finished.emit(result)
            elif self.files:
                results = {"successful": 0, "failed": 0, "files": []}
                for i, filepath in enumerate(self.files):
                    self.progress.emit(int((i + 1) / len(self.files) * 100), Path(filepath).name)
                    try:
                        res = search_engine.index_document(filepath)
                        if res.get("success"):
                            results["successful"] += 1
                        else:
                            results["failed"] += 1
                    except Exception:
                        results["failed"] += 1
                self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


# ============== Custom Widgets ==============

def open_file_location(filepath: str):
    """Cross-platform file location opener."""
    try:
        path = Path(filepath)
        target = path if path.exists() else path.parent
        if not target.exists():
            return
        system = platform.system()
        if system == "Windows":
            subprocess.run(['explorer', '/select,', str(path)])
        elif system == "Darwin":
            subprocess.run(['open', '-R', str(path)])
        else:
            subprocess.run(['xdg-open', str(target)])
    except Exception:
        pass


class ResultCard(QFrame):
    """Compact result card for search results."""

    def __init__(self, result: Dict[str, Any], query: str, parent=None):
        super().__init__(parent)
        self.result = result
        self.query = query
        self.setup_ui()

    def setup_ui(self):
        self.setProperty("class", "card")
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 16px;
            }}
            QFrame:hover {{
                border-color: {COLORS['bg_hover']};
                background-color: {COLORS['bg_tertiary']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        meta = self.result.get("metadata", {})
        filename = meta.get("filename", "Unknown")
        file_type = meta.get("file_type", "txt")
        score = self.result.get("score", 0)
        content = self.result.get("content", "")
        filepath = meta.get("filepath", "")

        # Header row
        header_layout = QHBoxLayout()

        icon_colors = {
            "pdf": COLORS['error'], "docx": COLORS['accent'], "doc": COLORS['accent'],
            "xlsx": COLORS['success'], "xls": COLORS['success'],
            "pptx": COLORS['warning'], "ppt": COLORS['warning'],
            "txt": COLORS['text_muted'], "csv": COLORS['success'],
            "html": "#e34c26", "json": "#f5a623", "py": "#3572A5",
            "js": "#f7df1e", "ts": "#3178c6", "java": "#b07219",
        }
        icon_color = icon_colors.get(file_type.lower(), COLORS['text_muted'])

        icon_label = QLabel(file_type.upper()[:4])
        icon_label.setFixedSize(48, 48)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background-color: {icon_color}20;
            color: {icon_color};
            border: 1px solid {icon_color}40;
            border-radius: 10px;
            font-weight: bold;
            font-size: 10px;
        """)
        header_layout.addWidget(icon_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        name_label = QLabel(filename)
        name_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold; font-size: 14px;")
        info_layout.addWidget(name_label)

        path_label = QLabel(filepath)
        path_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        path_label.setWordWrap(True)
        info_layout.addWidget(path_label)

        header_layout.addLayout(info_layout, 1)

        score_pct = int(score * 100)
        score_color = COLORS['success'] if score_pct >= 70 else COLORS['warning'] if score_pct >= 40 else COLORS['text_muted']
        score_label = QLabel(f"{score_pct}%")
        score_label.setStyleSheet(f"""
            background-color: {score_color}20;
            color: {score_color};
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: bold;
            font-size: 12px;
            border: 1px solid {score_color}40;
        """)
        header_layout.addWidget(score_label)

        layout.addLayout(header_layout)

        # Content preview
        preview = self._highlight(content[:400] + "..." if len(content) > 400 else content)
        content_label = QLabel(preview)
        content_label.setWordWrap(True)
        content_label.setStyleSheet(f"""
            background-color: {COLORS['bg_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 12px;
            color: {COLORS['text_secondary']};
            line-height: 1.6;
        """)
        layout.addWidget(content_label)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        if filepath and Path(filepath).exists():
            open_btn = QPushButton("Open Location")
            open_btn.setProperty("class", "secondary")
            open_btn.clicked.connect(lambda: open_file_location(filepath))
            btn_layout.addWidget(open_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _highlight(self, text: str) -> str:
        if not self.query:
            return text
        words = re.findall(r'\b\w{2,}\b', self.query.lower())
        result = text
        for word in words:
            pattern = re.compile(f'({re.escape(word)})', re.IGNORECASE)
            result = pattern.sub(r'[\1]', result)
        return result


class DocumentCard(QFrame):
    """Compact indexed-document card."""
    deleted = pyqtSignal(str)

    def __init__(self, doc: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
            QFrame:hover {{
                background-color: {COLORS['bg_tertiary']};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        filename = self.doc.get('filename', 'Unknown')
        file_type = self.doc.get('file_type', 'txt')
        chunk_count = self.doc.get('chunk_count', 0)
        filepath = self.doc.get('filepath', '')

        icon_colors = {
            "pdf": COLORS['error'], "docx": COLORS['accent'],
            "xlsx": COLORS['success'], "pptx": COLORS['warning'],
        }
        icon_color = icon_colors.get(file_type.lower(), COLORS['text_muted'])

        type_label = QLabel(file_type.upper()[:3])
        type_label.setFixedSize(40, 40)
        type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        type_label.setStyleSheet(f"""
            background-color: {icon_color}20;
            color: {icon_color};
            border-radius: 8px;
            font-weight: bold;
            font-size: 10px;
        """)
        layout.addWidget(type_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_label = QLabel(filename)
        name_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: 500;")
        info_layout.addWidget(name_label)

        meta_label = QLabel(f"{chunk_count} chunks • {file_type.upper()}")
        meta_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        info_layout.addWidget(meta_label)

        layout.addLayout(info_layout, 1)

        if filepath and Path(filepath).exists():
            open_btn = QPushButton("Open")
            open_btn.setProperty("class", "secondary")
            open_btn.setFixedWidth(70)
            open_btn.clicked.connect(lambda: open_file_location(filepath))
            layout.addWidget(open_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setProperty("class", "danger")
        delete_btn.setFixedWidth(70)
        delete_btn.clicked.connect(lambda: self.deleted.emit(filename))
        layout.addWidget(delete_btn)


# ============== Sidebar Widget ==============

class SidebarWidget(QWidget):
    """Sidebar with settings, stats, and crawler status."""

    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setFixedWidth(280)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_secondary']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Logo
        logo_layout = QHBoxLayout()
        logo_icon = QLabel("◆")
        logo_icon.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {COLORS['accent']}, stop:1 #8b5cf6);
            color: white; font-size: 20px; padding: 8px; border-radius: 10px;
        """)
        logo_icon.setFixedSize(40, 40)
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(logo_icon)

        logo_text_layout = QVBoxLayout()
        logo_text_layout.setSpacing(0)
        logo_title = QLabel("Phalanx")
        logo_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: bold;")
        logo_text_layout.addWidget(logo_title)
        logo_sub = QLabel("System Search")
        logo_sub.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        logo_text_layout.addWidget(logo_sub)
        logo_layout.addLayout(logo_text_layout)
        logo_layout.addStretch()
        layout.addLayout(logo_layout)

        # Privacy badge
        privacy_frame = QFrame()
        privacy_frame.setStyleSheet(f"""
            QFrame {{ background-color: {COLORS['success']}15; border: 1px solid {COLORS['success']}30;
                      border-radius: 20px; padding: 8px 16px; }}
        """)
        pl = QHBoxLayout(privacy_frame)
        pl.setContentsMargins(12, 8, 12, 8)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {COLORS['success']}; font-size: 8px;")
        pl.addWidget(dot)
        pt = QLabel("100% Private & Local")
        pt.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px; font-weight: 500;")
        pl.addWidget(pt)
        pl.addStretch()
        layout.addWidget(privacy_frame)

        # Search config
        layout.addWidget(self._section_label("SEARCH CONFIGURATION"))

        layout.addWidget(self._small_label("Search Mode"))
        self.search_mode = QComboBox()
        self.search_mode.addItems(["Hybrid (Recommended)", "Semantic Only", "Keyword Only"])
        self.search_mode.currentIndexChanged.connect(self.settings_changed.emit)
        layout.addWidget(self.search_mode)

        # Results limit
        lim_row = QHBoxLayout()
        lim_row.addWidget(self._small_label("Results Limit"))
        self.limit_value = QLabel("10")
        self.limit_value.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold;")
        lim_row.addWidget(self.limit_value)
        layout.addLayout(lim_row)

        self.results_slider = QSlider(Qt.Orientation.Horizontal)
        self.results_slider.setMinimum(1)
        self.results_slider.setMaximum(50)
        self.results_slider.setValue(10)
        self.results_slider.valueChanged.connect(lambda v: self.limit_value.setText(str(v)))
        self.results_slider.valueChanged.connect(self.settings_changed.emit)
        layout.addWidget(self.results_slider)

        layout.addWidget(self._small_label("File Type"))
        self.file_type = QComboBox()
        self.file_type.addItem("All Formats")
        self.file_type.addItems(list(SUPPORTED_EXTENSIONS.keys()))
        self.file_type.currentIndexChanged.connect(self.settings_changed.emit)
        layout.addWidget(self.file_type)

        layout.addStretch()

        # Crawler status
        layout.addWidget(self._section_label("CRAWLER STATUS"))

        self.crawler_status_label = QLabel("● Stopped")
        self.crawler_status_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(self.crawler_status_label)

        self.crawler_files_label = QLabel("0 files indexed")
        self.crawler_files_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        layout.addWidget(self.crawler_files_label)

        # Stats
        layout.addWidget(self._section_label("SYSTEM STATUS"))

        self.stats_frame = QFrame()
        self.stats_frame.setStyleSheet(f"""
            QFrame {{ background-color: {COLORS['bg_tertiary']}; border: 1px solid {COLORS['border']};
                      border-radius: 12px; padding: 12px; }}
        """)
        stats_layout = QGridLayout(self.stats_frame)
        stats_layout.setSpacing(12)

        self.doc_count = QLabel("0")
        self.doc_count.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 24px; font-weight: bold;")
        stats_layout.addWidget(self.doc_count, 0, 0)
        dl = QLabel("Documents")
        dl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        stats_layout.addWidget(dl, 1, 0)

        self.chunk_count = QLabel("0")
        self.chunk_count.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 24px; font-weight: bold;")
        stats_layout.addWidget(self.chunk_count, 0, 1)
        cl = QLabel("Chunks")
        cl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        stats_layout.addWidget(cl, 1, 1)

        layout.addWidget(self.stats_frame)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("class", "section")
        return lbl

    def _small_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        return lbl

    def update_stats(self):
        try:
            stats = search_engine.get_stats()
            self.doc_count.setText(str(stats.get("total_documents", 0)))
            self.chunk_count.setText(str(stats.get("total_chunks", 0)))
        except Exception:
            pass

    def update_crawler_status(self, running: bool, files_indexed: int = 0):
        if running:
            self.crawler_status_label.setText("● Running")
            self.crawler_status_label.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")
        else:
            self.crawler_status_label.setText("● Stopped")
            self.crawler_status_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        self.crawler_files_label.setText(f"{files_indexed} files discovered")

    def get_search_mode(self) -> str:
        mode_map = {"Hybrid (Recommended)": "hybrid", "Semantic Only": "semantic", "Keyword Only": "keyword"}
        return mode_map.get(self.search_mode.currentText(), "hybrid")

    def get_results_limit(self) -> int:
        return self.results_slider.value()

    def get_file_filter(self) -> Optional[str]:
        selected = self.file_type.currentText()
        if selected == "All Formats":
            return None
        return selected.replace(".", "")


# ============== Main Window ==============

class PhalanxApp(QMainWindow):
    """Main application window with system tray integration."""

    def __init__(self):
        super().__init__()
        self.search_worker = None
        self.index_worker = None
        self.crawler = get_crawler()
        self.setup_ui()
        self.setup_tray()
        self.setup_timers()
        self.update_stats()
        self.start_crawler()

    # -------- System Tray --------
    def setup_tray(self):
        """Create system tray icon with context menu."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("Phalanx Search")

        # Generate a simple icon programmatically
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(COLORS['accent'])))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
        painter.setPen(QPen(QColor("white")))
        font = QFont("Segoe UI", 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "P")
        painter.end()
        icon = QIcon(pixmap)

        self.tray_icon.setIcon(icon)
        self.setWindowIcon(icon)

        # Context menu
        tray_menu = QMenu()
        tray_menu.setStyleSheet(f"""
            QMenu {{ background-color: {COLORS['bg_secondary']}; color: {COLORS['text_primary']};
                     border: 1px solid {COLORS['border']}; padding: 4px; }}
            QMenu::item {{ padding: 8px 24px; }}
            QMenu::item:selected {{ background-color: {COLORS['bg_hover']}; }}
        """)

        show_action = QAction("Show Phalanx", self)
        show_action.triggered.connect(self.show_and_activate)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        self.crawler_toggle_action = QAction("Start Crawler", self)
        self.crawler_toggle_action.triggered.connect(self.toggle_crawler)
        tray_menu.addAction(self.crawler_toggle_action)

        rescan_action = QAction("Trigger Full Rescan", self)
        rescan_action.triggered.connect(self.trigger_rescan)
        tray_menu.addAction(rescan_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_and_activate()

    def show_and_activate(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    # -------- Crawler --------
    def start_crawler(self):
        if not self.crawler:
            return
        try:
            self.crawler.start()
            self.crawler_toggle_action.setText("Stop Crawler")
            self.sidebar.update_crawler_status(True)
        except Exception:
            pass

    def stop_crawler(self):
        if not self.crawler:
            return
        try:
            self.crawler.stop()
            self.crawler_toggle_action.setText("Start Crawler")
            self.sidebar.update_crawler_status(False)
        except Exception:
            pass

    def toggle_crawler(self):
        if self.crawler and self.crawler.running:
            self.stop_crawler()
        else:
            self.start_crawler()

    def trigger_rescan(self):
        if self.crawler:
            self.crawler.trigger_full_rescan()

    # -------- Timers --------
    def setup_timers(self):
        """Periodic stat refreshes."""
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self._refresh_stats)
        self.stats_timer.start(10000)  # Every 10 seconds

    def _refresh_stats(self):
        self.update_stats()
        if self.crawler:
            try:
                status = self.crawler.get_status()
                self.sidebar.update_crawler_status(
                    self.crawler.running,
                    status.get("total_files_discovered", 0)
                )
            except Exception:
                pass

    # -------- UI Setup --------
    def setup_ui(self):
        self.setWindowTitle("Phalanx Search")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet(STYLESHEET)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = SidebarWidget()
        self.sidebar.settings_changed.connect(self.on_settings_changed)
        main_layout.addWidget(self.sidebar)

        # Main content area
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 32, 32, 32)
        content_layout.setSpacing(24)

        # Header
        header_layout = QVBoxLayout()

        title = QLabel("Document Intelligence")
        title.setProperty("class", "title")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 28px; font-weight: bold;")
        header_layout.addWidget(title)

        subtitle = QLabel("System-wide document search • Hybrid AI + Full-Text • 100% Local")
        subtitle.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14px;")
        header_layout.addWidget(subtitle)

        content_layout.addLayout(header_layout)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # --- Search tab ---
        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)
        search_layout.setContentsMargins(0, 20, 0, 0)
        search_layout.setSpacing(16)

        search_input_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ask a question or search for keywords...")
        self.search_input.returnPressed.connect(self.perform_search)
        search_input_layout.addWidget(self.search_input)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.perform_search)
        search_input_layout.addWidget(search_btn)

        search_layout.addLayout(search_input_layout)

        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(16)
        self.results_layout.addStretch()

        self.results_scroll.setWidget(self.results_widget)
        search_layout.addWidget(self.results_scroll)

        self.search_status = QLabel("")
        self.search_status.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        search_layout.addWidget(self.search_status)

        self.tabs.addTab(search_tab, "Search")

        # --- Upload tab ---
        upload_tab = QWidget()
        upload_layout = QVBoxLayout(upload_tab)
        upload_layout.setContentsMargins(0, 20, 0, 0)
        upload_layout.setSpacing(24)

        # File upload section
        upload_section = QFrame()
        upload_section.setStyleSheet(f"""
            QFrame {{ background-color: {COLORS['bg_secondary']}; border: 2px dashed {COLORS['border']};
                      border-radius: 16px; padding: 40px; }}
        """)
        usl = QVBoxLayout(upload_section)
        usl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ui = QLabel("📁")
        ui.setStyleSheet("font-size: 48px;")
        ui.setAlignment(Qt.AlignmentFlag.AlignCenter)
        usl.addWidget(ui)

        ut = QLabel("Drop files here or click to upload")
        ut.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: bold;")
        ut.setAlignment(Qt.AlignmentFlag.AlignCenter)
        usl.addWidget(ut)

        ud = QLabel("Supports 30+ file types: PDF, DOCX, XLSX, HTML, JSON, Code, and more")
        ud.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        ud.setAlignment(Qt.AlignmentFlag.AlignCenter)
        usl.addWidget(ud)

        upload_btn = QPushButton("Select Files")
        upload_btn.clicked.connect(self.select_files)
        upload_btn.setFixedWidth(150)
        usl.addWidget(upload_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        upload_layout.addWidget(upload_section)

        # Folder index section
        folder_section = QFrame()
        folder_section.setStyleSheet(f"""
            QFrame {{ background-color: {COLORS['bg_secondary']}; border: 1px solid {COLORS['border']};
                      border-radius: 12px; padding: 20px; }}
        """)
        fl = QVBoxLayout(folder_section)

        ft = QLabel("Index Local Folder")
        ft.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: bold;")
        fl.addWidget(ft)

        fi_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("C:\\Documents\\...")
        fi_layout.addWidget(self.folder_input)

        browse_btn = QPushButton("Browse")
        browse_btn.setProperty("class", "secondary")
        browse_btn.clicked.connect(self.browse_folder)
        fi_layout.addWidget(browse_btn)

        index_folder_btn = QPushButton("Index Folder")
        index_folder_btn.clicked.connect(self.index_folder)
        fi_layout.addWidget(index_folder_btn)

        fl.addLayout(fi_layout)
        upload_layout.addWidget(folder_section)

        self.upload_progress = QProgressBar()
        self.upload_progress.setVisible(False)
        upload_layout.addWidget(self.upload_progress)

        self.upload_status = QLabel("")
        self.upload_status.setStyleSheet(f"color: {COLORS['text_muted']};")
        upload_layout.addWidget(self.upload_status)

        upload_layout.addStretch()
        self.tabs.addTab(upload_tab, "Upload")

        # --- Manage tab ---
        manage_tab = QWidget()
        manage_layout = QVBoxLayout(manage_tab)
        manage_layout.setContentsMargins(0, 20, 0, 0)
        manage_layout.setSpacing(16)

        manage_header = QHBoxLayout()
        mt = QLabel("Indexed Documents")
        mt.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: bold;")
        manage_header.addWidget(mt)
        manage_header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.clicked.connect(self.refresh_documents)
        manage_header.addWidget(refresh_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.setProperty("class", "danger")
        clear_btn.clicked.connect(self.clear_all_documents)
        manage_header.addWidget(clear_btn)

        manage_layout.addLayout(manage_header)

        self.docs_scroll = QScrollArea()
        self.docs_scroll.setWidgetResizable(True)
        self.docs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.docs_widget = QWidget()
        self.docs_layout = QVBoxLayout(self.docs_widget)
        self.docs_layout.setContentsMargins(0, 0, 0, 0)
        self.docs_layout.setSpacing(8)
        self.docs_layout.addStretch()

        self.docs_scroll.setWidget(self.docs_widget)
        manage_layout.addWidget(self.docs_scroll)

        self.tabs.addTab(manage_tab, "Manage")

        # --- Watch Dirs tab ---
        watch_tab = QWidget()
        watch_layout = QVBoxLayout(watch_tab)
        watch_layout.setContentsMargins(0, 20, 0, 0)
        watch_layout.setSpacing(16)

        wh = QHBoxLayout()
        wt = QLabel("Watch Directories")
        wt.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: bold;")
        wh.addWidget(wt)
        wh.addStretch()

        add_dir_btn = QPushButton("Add Directory")
        add_dir_btn.clicked.connect(self.add_watch_dir)
        wh.addWidget(add_dir_btn)
        watch_layout.addLayout(wh)

        watch_desc = QLabel(
            "Phalanx automatically monitors these directories for new and changed files.\n"
            "Files are indexed in the background — no manual uploads needed."
        )
        watch_desc.setWordWrap(True)
        watch_desc.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        watch_layout.addWidget(watch_desc)

        self.watch_dirs_scroll = QScrollArea()
        self.watch_dirs_scroll.setWidgetResizable(True)

        self.watch_dirs_widget = QWidget()
        self.watch_dirs_layout = QVBoxLayout(self.watch_dirs_widget)
        self.watch_dirs_layout.setContentsMargins(0, 0, 0, 0)
        self.watch_dirs_layout.setSpacing(8)
        self.watch_dirs_layout.addStretch()

        self.watch_dirs_scroll.setWidget(self.watch_dirs_widget)
        watch_layout.addWidget(self.watch_dirs_scroll)

        self.tabs.addTab(watch_tab, "Watch Dirs")

        self.tabs.currentChanged.connect(self.on_tab_changed)
        content_layout.addWidget(self.tabs)
        main_layout.addWidget(content, 1)

        self.show_empty_state()

    # -------- Empty / No-Results States --------
    def show_empty_state(self):
        self.clear_results()

        empty = QFrame()
        el = QVBoxLayout(empty)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.setSpacing(16)

        icon = QLabel("◆")
        icon.setStyleSheet(f"""
            background-color: {COLORS['bg_tertiary']}; color: {COLORS['text_muted']};
            font-size: 32px; padding: 20px; border-radius: 16px;
            border: 1px solid {COLORS['border']};
        """)
        icon.setFixedSize(80, 80)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        t = QLabel("Ready to search")
        t.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: bold;")
        el.addWidget(t, alignment=Qt.AlignmentFlag.AlignCenter)

        d = QLabel("Enter a query above to find documents using hybrid AI + full-text search.")
        d.setStyleSheet(f"color: {COLORS['text_muted']};")
        el.addWidget(d, alignment=Qt.AlignmentFlag.AlignCenter)

        self.results_layout.insertWidget(0, empty)

    def clear_results(self):
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_no_results(self):
        empty = QFrame()
        el = QVBoxLayout(empty)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.setSpacing(16)

        icon = QLabel("🔍")
        icon.setStyleSheet("font-size: 48px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        t = QLabel("No results found")
        t.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 18px; font-weight: bold;")
        el.addWidget(t, alignment=Qt.AlignmentFlag.AlignCenter)

        d = QLabel("Try adjusting your search terms or filters.")
        d.setStyleSheet(f"color: {COLORS['text_muted']};")
        el.addWidget(d, alignment=Qt.AlignmentFlag.AlignCenter)

        self.results_layout.insertWidget(0, empty)

    # -------- Search --------
    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            return

        self.search_status.setText("Searching...")
        self.clear_results()

        top_k = self.sidebar.get_results_limit()
        file_filter = self.sidebar.get_file_filter()
        search_mode = self.sidebar.get_search_mode()

        self.search_worker = SearchWorker(query, top_k, file_filter, search_mode)
        self.search_worker.finished.connect(self.on_search_complete)
        self.search_worker.error.connect(self.on_search_error)
        self.search_worker.start()

    def on_search_complete(self, results: List[Dict]):
        self.clear_results()
        if results:
            self.search_status.setText(f"Found {len(results)} results")
            for result in results:
                card = ResultCard(result, self.search_input.text())
                self.results_layout.insertWidget(self.results_layout.count() - 1, card)
        else:
            self.search_status.setText("No results found")
            self.show_no_results()

    def on_search_error(self, error: str):
        self.search_status.setText(f"Error: {error}")

    # -------- Upload / Indexing --------
    def select_files(self):
        extensions = " ".join([f"*{ext}" for ext in SUPPORTED_EXTENSIONS.keys()])
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Documents", "",
            f"Documents ({extensions});;All Files (*)"
        )
        if files:
            self.index_files(files)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_input.setText(folder)

    def index_files(self, files: List[str]):
        self.upload_progress.setVisible(True)
        self.upload_progress.setValue(0)
        self.upload_status.setText("Indexing files...")

        self.index_worker = IndexWorker(files=files)
        self.index_worker.progress.connect(self.on_index_progress)
        self.index_worker.finished.connect(self.on_index_complete)
        self.index_worker.error.connect(self.on_index_error)
        self.index_worker.start()

    def index_folder(self):
        folder = self.folder_input.text().strip()
        if not folder or not Path(folder).is_dir():
            QMessageBox.warning(self, "Invalid Folder", "Please enter a valid folder path.")
            return

        self.upload_progress.setVisible(True)
        self.upload_progress.setValue(0)
        self.upload_status.setText("Indexing folder...")

        self.index_worker = IndexWorker(directory=folder)
        self.index_worker.finished.connect(self.on_index_complete)
        self.index_worker.error.connect(self.on_index_error)
        self.index_worker.start()

    def on_index_progress(self, percent: int, filename: str):
        self.upload_progress.setValue(percent)
        self.upload_status.setText(f"Processing: {filename}")

    def on_index_complete(self, result: Dict):
        self.upload_progress.setVisible(False)
        successful = result.get("successful", 0)
        failed = result.get("failed", 0)

        msg = f"✓ Indexed {successful} documents" if successful else "No documents were indexed"
        if failed:
            msg += f" ({failed} failed)"
        self.upload_status.setText(msg)
        self.update_stats()

    def on_index_error(self, error: str):
        self.upload_progress.setVisible(False)
        self.upload_status.setText(f"Error: {error}")

    # -------- Manage --------
    def refresh_documents(self):
        while self.docs_layout.count() > 1:
            item = self.docs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        docs = search_engine.get_indexed_documents()

        if docs:
            for doc in docs:
                card = DocumentCard(doc)
                card.deleted.connect(self.delete_document)
                self.docs_layout.insertWidget(self.docs_layout.count() - 1, card)
        else:
            empty = QLabel("No documents indexed yet.\nThe crawler will auto-index files from watched directories.")
            empty.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 40px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.docs_layout.insertWidget(0, empty)

    def delete_document(self, filename: str):
        reply = QMessageBox.question(
            self, "Delete Document",
            f"Remove '{filename}' from the index?\n(Original file is NOT deleted.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            search_engine.delete_document(filename)
            self.refresh_documents()
            self.update_stats()

    def clear_all_documents(self):
        reply = QMessageBox.question(
            self, "Clear All Documents",
            "Clear all indexed documents?\nThis cannot be undone. Original files are NOT deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            search_engine.clear_index()
            self.refresh_documents()
            self.update_stats()

    # -------- Watch Directories --------
    def refresh_watch_dirs(self):
        while self.watch_dirs_layout.count() > 1:
            item = self.watch_dirs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        dirs = []
        if self.crawler:
            try:
                dirs = list(self.crawler.watch_dirs)
            except Exception:
                pass

        if not dirs:
            dirs = [d for d in DEFAULT_WATCH_DIRS if Path(d).exists()]

        if dirs:
            for d in dirs:
                row = QFrame()
                row.setStyleSheet(f"""
                    QFrame {{ background-color: {COLORS['bg_secondary']};
                              border: 1px solid {COLORS['border']}; border-radius: 8px; }}
                """)
                rl = QHBoxLayout(row)
                rl.setContentsMargins(12, 8, 12, 8)

                icon = QLabel("📁")
                icon.setStyleSheet("font-size: 16px;")
                rl.addWidget(icon)

                lbl = QLabel(d)
                lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px;")
                lbl.setWordWrap(True)
                rl.addWidget(lbl, 1)

                exists = Path(d).exists()
                status = QLabel("● Active" if exists else "● Missing")
                status.setStyleSheet(
                    f"color: {COLORS['success']}; font-size: 11px;" if exists
                    else f"color: {COLORS['error']}; font-size: 11px;"
                )
                rl.addWidget(status)

                rm_btn = QPushButton("Remove")
                rm_btn.setProperty("class", "secondary")
                rm_btn.setFixedWidth(70)
                rm_btn.clicked.connect(lambda _, path=d: self.remove_watch_dir(path))
                rl.addWidget(rm_btn)

                self.watch_dirs_layout.insertWidget(self.watch_dirs_layout.count() - 1, row)
        else:
            empty = QLabel("No watch directories configured.\nClick 'Add Directory' to start monitoring a folder.")
            empty.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 40px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.watch_dirs_layout.insertWidget(0, empty)

    def add_watch_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory to Watch")
        if folder and self.crawler:
            self.crawler.add_watch_dir(folder)
            self.refresh_watch_dirs()

    def remove_watch_dir(self, path: str):
        if self.crawler:
            try:
                self.crawler.remove_watch_dir(path)
            except Exception:
                pass
            self.refresh_watch_dirs()

    # -------- Tab Events --------
    def on_tab_changed(self, index: int):
        if index == 2:  # Manage
            self.refresh_documents()
        elif index == 3:  # Watch Dirs
            self.refresh_watch_dirs()

    def on_settings_changed(self):
        pass

    def update_stats(self):
        self.sidebar.update_stats()

    # -------- Window Lifecycle --------
    def closeEvent(self, event):
        """Minimize to tray instead of quitting."""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Phalanx Search",
            "Running in the background. Double-click tray icon to reopen.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def quit_app(self):
        """Actually quit the application."""
        if self.crawler:
            try:
                self.crawler.stop()
            except Exception:
                pass
        self.tray_icon.hide()
        QApplication.quit()


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("Phalanx Search")
    app.setOrganizationName("Phalanx")
    app.setQuitOnLastWindowClosed(False)  # Keep alive in tray

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = PhalanxApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
