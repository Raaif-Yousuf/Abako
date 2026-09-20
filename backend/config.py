import os
import sys


def _bundle_dir():
    """Directory holding the bundled read-only resources: the PyInstaller
    bundle dir when frozen (sys._MEIPASS), the repo root otherwise."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


EXAM_DURATION_MINUTES = 30
TOTAL_QUESTIONS = 60
QUESTION_BANK_PATH = os.path.join(_bundle_dir(), "resources", "question_bank.xlsx")
# Where generated PDFs/reports are written. main.js passes ABAKO_OUTPUT_DIR
# for packaged runs (a real, writable folder next to the portable exe) so
# both sides agree on one location; dev runs fall back to "output" relative
# to the process cwd, same as before.
OUTPUT_BASE_PATH = os.environ.get("ABAKO_OUTPUT_DIR") or "output"
