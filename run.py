"""
Phalanx Search - Quick Start Script
Run this to start the search engine
"""

import subprocess
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    print("\n" + "="*60)
    print("🔍 PHALANX SEARCH - Local AI Document Search Engine")
    print("="*60)
    print("\n🔒 Privacy: 100% Local - No data leaves your system\n")
    
    # Run Streamlit from project root with PYTHONPATH set
    frontend_app = project_root / "frontend" / "app.py"
    
    print("🚀 Starting web interface...")
    print("📍 Open your browser to: http://localhost:8501\n")
    
    # Set PYTHONPATH environment variable to include project root
    env = os.environ.copy()
    env['PYTHONPATH'] = str(project_root)
    
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", str(frontend_app),
        "--server.port=8501",
        "--server.address=localhost",
        "--browser.gatherUsageStats=false"
    ], env=env)

if __name__ == "__main__":
    main()
