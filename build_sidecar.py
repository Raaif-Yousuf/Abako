"""
Builds the Python Flask sidecar as a --onedir PyInstaller bundle.
Output: resources/abako_sidecar/abako_sidecar.exe
Run with: python build_sidecar.py  (use the project venv Python)
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--name", "abako_sidecar",
    "--distpath", os.path.join(ROOT, "resources"),
    "--workpath", os.path.join(ROOT, "build"),
    "--specpath", os.path.join(ROOT, "build"),
    "--hidden-import", "flask",
    "--hidden-import", "flask_cors",
    "--hidden-import", "pandas",
    "--hidden-import", "openpyxl",
    "--hidden-import", "reportlab",
    "--hidden-import", "matplotlib",
    "--add-data", os.path.join(ROOT, "resources", "question_bank.xlsx") + ";resources",
    "--add-data", os.path.join(ROOT, "resources", "abako_logo.png") + ";resources",
    os.path.join(ROOT, "backend", "main.py"),
]

print("Running PyInstaller...")
subprocess.run(cmd, check=True)
print("\nDone. Sidecar at: resources/abako_sidecar/abako_sidecar.exe")
