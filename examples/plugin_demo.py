#!/usr/bin/env python3
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""The whole integration: one line.  Run this file to see the footer errcode prints.

    python examples/plugin_demo.py            # crashes on purpose
"""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import errcode  # noqa: E402

errcode.install(app="plugin_demo")          # <- this is all a program needs

log = logging.getLogger("demo")
log.info("starting up")                      # INFO is ignored (noise)
errcode.record("HW.GPU_FALLBACK")            # app-set code: "no GPU, using the CPU path"
log.warning("Retrying after Read timed out") # WARNING+ is scanned

import tkinter                               # noqa: E402,F401  (missing on many Linux installs -> fatal here)
