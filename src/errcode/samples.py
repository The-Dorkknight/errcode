# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Sample logs for the demo GUI, the CLI (--sample) and the tests."""

SAMPLES = {
    "pip install fails (noisy log)": """\
Collecting segno>=1.5
  Downloading segno-1.6.6-py3-none-any.whl (76 kB)
     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 76.3/76.3 kB 1.2 MB/s eta 0:00:00
Collecting numpy
  Downloading numpy-2.1.0.tar.gz (12.0 MB)
     ━━━━━━━━╸━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2.6/12.0 MB 2.1 MB/s eta 0:00:05
     ━━━━━━━━━━━━━╸━━━━━━━━━━━━━━━━━━━━━━━━━━ 4.1/12.0 MB 2.3 MB/s eta 0:00:04
12% downloading numpy-2.1.0.tar.gz
34% downloading numpy-2.1.0.tar.gz
71% downloading numpy-2.1.0.tar.gz
WARNING: Retrying (Retry(total=4)) after connection broken by 'ReadTimeoutError: Read timed out. (read timeout=15)'
  Preparing metadata (pyproject.toml): started
  Building wheel for numpy (pyproject.toml) ... error
  error: subprocess-exited-with-error
  × Building wheel for numpy (pyproject.toml) did not run successfully.
  g++: command not found
ERROR: Failed building wheel for numpy
""",
    "Linux: tkinter missing": """\
INFO: starting ErrCode 0.1.0
Traceback (most recent call last):
  File "/home/matt/app/main.py", line 3, in <module>
    import tkinter as tk
ModuleNotFoundError: No module named 'tkinter'
""",
    "Windows: missing C++ runtime": """\
Traceback (most recent call last):
  File "C:\\Users\\matt\\app\\main.py", line 1, in <module>
    import cv2
ImportError: DLL load failed while importing cv2: The specified module could not be found.
OSError: [WinError 126] The specified module could not be found
The code execution cannot proceed because VCRUNTIME140.dll was not found.
""",
    "macOS: Gatekeeper blocked app": """\
"ErrCode.app" is damaged and can't be opened. You should move it to the Trash.
xattr: com.apple.quarantine present on /Applications/ErrCode.app
""",
    "Crash with GPU + CPU warnings": """\
[INFO] probing devices
clGetPlatformIDs failed: CL_PLATFORM_NOT_FOUND_KHR
[INFO] falling back to CPU path
Illegal instruction (core dumped)
""",
    "Healthy run (nothing wrong)": """\
INFO 10:02:11 loading model
 12% loading
 55% loading
100% loaded
INFO 10:02:15 done in 4.1s, 0 errors
""",
}
