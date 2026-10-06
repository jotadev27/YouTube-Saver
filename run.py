"""Application entry point for Python and frozen Windows builds."""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from youtube_saver.ui import run

if __name__ == "__main__":
    run()
