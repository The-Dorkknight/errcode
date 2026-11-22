# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""A tiny 'is this machine OK?' probe. Doubles as the demo of app-set codes."""
from __future__ import annotations

import os
import sys
from typing import List, Optional

from . import qr
from .detect import Hit, hit_for_key

LOW_RAM_BYTES = 2 * 1024 ** 3


def total_ram_bytes() -> Optional[int]:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        pass
    if sys.platform == "win32":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return int(st.ullTotalPhys)
        except Exception:
            return None
    return None


def machine_check() -> List[Hit]:
    hits: List[Hit] = []
    if sys.version_info < (3, 8):
        hits.append(hit_for_key("GEN.VERSION_MISMATCH"))
    ram = total_ram_bytes()
    if ram is not None and ram < LOW_RAM_BYTES:
        hits.append(hit_for_key("HW.LOW_RAM"))
    if (os.cpu_count() or 1) <= 2 or (ram is not None and ram < LOW_RAM_BYTES):
        hits.append(hit_for_key("HW.LOW_END_MODE"))
    if not qr.available():
        hits.append(hit_for_key("PY.MODULE_MISSING", sev=1))   # only QR output is affected: warn
    return hits
