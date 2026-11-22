# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Start the ErrCode window: the TK 4K one when TK 4K is installed and starts, otherwise the tkinter one."""
from __future__ import annotations

import os
import sys


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    want = os.environ.get("ERRCODE_UI", "").lower() or ("tkinter" if "--tkinter" in argv else "tk4k")
    if want != "tkinter":
        try:
            from . import gui_tk4k
        except ImportError as exc:  # tk4k missing or its native part cannot load on this platform
            print("TK 4K is not available (%s); using the tkinter window instead." % exc, file=sys.stderr)
        else:
            gui_tk4k.main()
            return
    from . import gui
    gui.main()


if __name__ == "__main__":
    main()
