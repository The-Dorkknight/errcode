#!/usr/bin/env python3
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""ErrCode demo window.  Run:  python src/main.py   (the real product is the 'errcode' package)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from errcode.launch import main  # noqa: E402  (TK 4K window, tkinter fallback)

if __name__ == "__main__":
    main()
