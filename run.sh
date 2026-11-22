#!/usr/bin/env sh
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
# One-step launcher (Linux / macOS): private venv, install the one dependency, open the demo window.
set -e
cd "$(dirname "$0")"
PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
if [ ! -d .venv ]; then
  "$PY" -m venv .venv || {
    echo "Could not create a virtual environment."
    echo "Debian/Ubuntu/Mint: sudo apt install python3-venv"
    exit 1
  }
fi
. .venv/bin/activate
python -m pip install -q -r requirements.txt
# The window is built with TK 4K (SDL3 + Dear ImGui). Try the bundled Linux wheel; elsewhere pip may find nothing.
python -m pip install -q --find-links vendor tk4k 2>/dev/null || true
if python -c "import tk4k._core" 2>/dev/null; then
  echo "Starting ErrCode with TK 4K as its UI."
  exec python src/main.py "$@"
fi
echo "TK 4K is not available for this system yet - using the older tkinter window."
python -c "import tkinter" 2>/dev/null || {
  echo "tkinter (the demo window) is not installed."
  echo "Debian/Ubuntu/Mint: sudo apt install python3-tk | Fedora: sudo dnf install python3-tkinter"
  echo "macOS: install Python from python.org, or: brew install python-tk"
  echo "The command line still works:  .venv/bin/python -m errcode scan --sample 1"
  exit 1
}
exec python src/main.py "$@"
