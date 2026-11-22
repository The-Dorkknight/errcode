# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""errcode - compact, dictionary-backed error codes you can read off a QR code.

    import errcode
    errcode.install(app="myprog")            # plug in: hooks exceptions + logging
    errcode.record("HW.GPU_FALLBACK")        # app-set codes by dictionary key
    r = errcode.scan(open("run.log").read()) # or analyse any log text
    r.quick, r.payload, r.text(), r.save_qr("r.png")
    errcode.decode("EC2-3473902382...")      # the other end: digits -> meaning (EC1 too)
    errcode.decode("E102 W706")              # quick 3-digit codes
"""
__version__ = "0.3.3"
__version_label__ = "0.3.3-wip"      # shown in titles / --version while unfinished
__build_date__ = "2026-11-22 01:10"

from . import codec, ec2, table
from .codec import CodecError
from .table import define_app
from .plugin import (Collector, collector, from_exception, install, record, report,
                     reset, run, scan, uninstall)
from .report import Decoded, DecodedCode, Report, decode

__all__ = ["__version__", "__version_label__", "__build_date__", "codec", "ec2", "table", "define_app", "CodecError", "Collector", "collector",
           "from_exception", "install", "uninstall", "record", "report", "reset", "run", "scan",
           "Decoded", "DecodedCode", "Report", "decode"]
