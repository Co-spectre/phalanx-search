"""
Phalanx Search - Desktop Application Launcher
Starts the system-tray app with background crawler.
"""

import subprocess
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    print("\n" + "="*60)
    print("◆ PHALANX SEARCH - System Search Engine")
    print("="*60)
    print("\n🔒 Privacy: 100% Local — No data leaves your system")
    print("🔍 Hybrid AI + Full-Text search across 30+ file types")
    print("📡 Background crawler auto-indexes your files\n")

    desktop_app = project_root / "desktop" / "app.py"

    print("🚀 Starting Phalanx (minimizes to system tray)...")

    env = os.environ.copy()
    env['PYTHONPATH'] = str(project_root)

    subprocess.run([sys.executable, str(desktop_app)], env=env)

if __name__ == "__main__":
    main()
