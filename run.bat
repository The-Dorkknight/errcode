@echo off
rem Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
rem Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
rem One-step launcher (Windows): private venv, install the one dependency, open the demo window.
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py -3
if not exist .venv\Scripts\python.exe (
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create a virtual environment. Install Python from python.org and tick "Add python.exe to PATH".
    pause
    exit /b 1
  )
)
.venv\Scripts\python -m pip install -q -r requirements.txt
rem The window is built with TK 4K. Try the bundled wheel (Linux only today); otherwise use the tkinter window.
.venv\Scripts\python -m pip install -q --find-links vendor tk4k >nul 2>nul
.venv\Scripts\python -c "import tk4k._core" 2>nul
if not errorlevel 1 (
  echo Starting ErrCode with TK 4K as its UI.
  .venv\Scripts\python src\main.py %*
  goto :eof
)
echo TK 4K is not available for this system yet - using the older tkinter window.
.venv\Scripts\python -c "import tkinter" 2>nul
if errorlevel 1 (
  echo tkinter is missing: re-run the Python installer and tick "tcl/tk and IDLE".
  echo The command line still works:  .venv\Scripts\python -m errcode scan --sample 1
  pause
  exit /b 1
)
.venv\Scripts\python src\main.py %*
