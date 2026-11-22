# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""The dictionary: every known failure, its stable numeric id, plain-language
meaning, suggested fix and the text patterns that recognise it.

RULES FOR EDITING (so old QR codes keep decoding correctly):
  * NEVER renumber or reuse an id. Add new entries with the next free id.
  * Ids are per domain and must be < 100 (3-digit code = domain * 100 + id).
  * Retire an entry by leaving it in place (gaps are fine).

Severity: 0 ok/info, 1 warning, 2 error, 3 fatal.

3-DIGIT CODES (EC2, v0.2+): code = domain * 100 + id, like HTTP status ranges:
    0xx general   1xx Python   2xx C/C++   3xx Windows   4xx Linux
    5xx macOS     6xx network  7xx hardware/GPU  8xx embedded/firmware/printers
    9xx app-defined (each program's own, see define_app)
  So ids must be < 100 per domain. PY.TK_MISSING (domain 1, id 2) is code 102.

DETAILS: a pattern may capture a short detail with a named group (?P<d>...), e.g. the
missing module's name. It travels in the report next to the code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

OK, WARN, ERROR, FATAL = 0, 1, 2, 3
SEV_NAMES = ("ok", "warn", "error", "fatal")

# domain index -> (key, title).  Index fits in 3 bits, so there is room for 8.
DOMAINS = {
    0: ("GEN", "General / portable OS errors"),
    1: ("PY", "Python"),
    2: ("CPP", "C / C++ native code"),
    3: ("WIN", "Windows"),
    4: ("LIN", "Linux"),
    5: ("MAC", "macOS"),
    6: ("NET", "Network"),
    7: ("HW", "Hardware / GPU / devices"),
    8: ("EMB", "Embedded boards / firmware / 3D printers"),
    9: ("APP", "App-defined (each program's own codes)"),
}
REVISION = 2          # bump when entries are added; travels in EC2 reports
DOMAIN_INDEX = {key: idx for idx, (key, _t) in DOMAINS.items()}


@dataclass(frozen=True)
class Entry:
    domain: int
    id: int
    name: str
    sev: int
    msg: str
    fix: str
    patterns: Tuple["re.Pattern", ...] = ()
    errno_name: Optional[str] = None   # portable errno name, e.g. "ENOENT"
    winerr: Optional[int] = None       # Windows error number
    generic: bool = False              # symptom/wrapper: dropped if a specific entry matched
    supersedes: Tuple[str, ...] = ()   # keys this entry makes redundant

    @property
    def key(self) -> str:
        return "%s.%s" % (DOMAINS[self.domain][0], self.name)

    @property
    def code(self) -> int:
        """3-digit code (EC2): domain * 100 + id."""
        return self.domain * 100 + self.id

    @property
    def code3(self) -> str:
        return "%03d" % self.code

    @property
    def sev_name(self) -> str:
        return SEV_NAMES[self.sev]


ENTRIES: List[Entry] = []


def E(dom, id_, name, sev, msg, fix, *pats, errno=None, winerr=None,
      generic=False, over=()):
    ENTRIES.append(Entry(
        domain=DOMAIN_INDEX[dom], id=id_, name=name, sev=sev, msg=msg, fix=fix,
        patterns=tuple(re.compile(p, re.IGNORECASE) for p in pats),
        errno_name=errno, winerr=winerr, generic=generic, supersedes=tuple(over)))


# --------------------------------------------------------------------------
# GEN (0): app-set codes and portable OS (errno) errors
# --------------------------------------------------------------------------
E("GEN", 0, "OK", OK, "All ok - nothing to report.", "Nothing to do.")
E("GEN", 1, "UNKNOWN", ERROR, "An error occurred that the dictionary does not recognise.",
  "Send the full log; add an entry to table.py so it is recognised next time.",
  generic=True)
E("GEN", 2, "CANCELLED", OK, "Cancelled by the user.", "Nothing to do.",
  r"KeyboardInterrupt", r"cancel(?:l)?ed by (?:the )?user")
E("GEN", 3, "CONFIG_INVALID", ERROR, "Configuration file is missing or invalid.",
  "Check the config file syntax, or delete it to regenerate defaults.",
  r"JSONDecodeError", r"configparser\.\w*Error", r"yaml\.(?:scanner|parser)", r"invalid config")
E("GEN", 4, "UNSUPPORTED_OS", ERROR, "This operating system or version is not supported.",
  "Check the README for supported platforms.")
E("GEN", 5, "VERSION_MISMATCH", ERROR, "A component version does not match what the program needs.",
  "Update or reinstall the program and its dependencies together.")
E("GEN", 6, "LOW_DISK", WARN, "Disk space is low.", "Free some disk space.")
E("GEN", 7, "BAD_INPUT", WARN, "Invalid input was supplied.", "Check the input and try again.")

E("GEN", 16, "ENOENT", ERROR, "File or folder not found.",
  "Check the path exists and is spelled correctly (relative paths depend on the working folder).",
  r"No such file or directory: '(?P<d>[^']{1,200})'", r"No such file or directory", r"\[Errno 2\]",
  r"FileNotFoundError", errno="ENOENT")
E("GEN", 17, "EACCES", ERROR, "Permission denied.",
  "Check file permissions / ownership, or run from a folder you own.",
  r"Permission denied", r"\[Errno 13\]", r"PermissionError", errno="EACCES")
E("GEN", 18, "EPERM", ERROR, "Operation not permitted.",
  "Needs higher privileges or is blocked by the OS (macOS privacy settings, SELinux, read-only attribute).",
  r"Operation not permitted", r"\[Errno 1\]", errno="EPERM")
E("GEN", 19, "ENOSPC", ERROR, "No space left on the device.",
  "Free disk space (or inodes), or choose another output location.",
  r"No space left on device", r"\[Errno 28\]", errno="ENOSPC")
E("GEN", 20, "EMFILE", ERROR, "Too many open files.",
  "Close files you no longer need; raise the limit (ulimit -n) if legitimately needed.",
  r"Too many open files", r"\[Errno 24\]", errno="EMFILE")
E("GEN", 21, "EEXIST", ERROR, "File or folder already exists.",
  "Choose a different name or remove the existing item.",
  r"File exists", r"\[Errno 17\]", r"FileExistsError", errno="EEXIST")
E("GEN", 22, "ENOMEM", ERROR, "Cannot allocate memory.",
  "Close other programs, add RAM/swap, or process the data in smaller pieces.",
  r"Cannot allocate memory", r"\[Errno 12\]", r"MemoryError", errno="ENOMEM")
E("GEN", 23, "EBUSY", ERROR, "Device or resource busy.",
  "Another program is using it; close it and retry.",
  r"Device or resource busy", r"\[Errno 16\]", errno="EBUSY")
E("GEN", 24, "EPIPE", WARN, "Broken pipe - the other end closed the connection.",
  "Usually harmless when piping into head/less; otherwise the receiving program crashed.",
  r"Broken pipe", r"\[Errno 32\]", errno="EPIPE")
E("GEN", 25, "EISDIR", ERROR, "Expected a file but found a folder.", "Check the path.",
  r"Is a directory", r"\[Errno 21\]", r"IsADirectoryError", errno="EISDIR")
E("GEN", 26, "ENOTDIR", ERROR, "Expected a folder but found a file.", "Check the path.",
  r"Not a directory", r"\[Errno 20\]", r"NotADirectoryError", errno="ENOTDIR")
E("GEN", 27, "EIO", ERROR, "Input/output error - possible failing drive, cable or flaky USB device.",
  "Check the drive/cable, try another port, and check disk health.",
  r"Input/output error", r"\[Errno 5\]", errno="EIO")
E("GEN", 28, "EROFS", ERROR, "Read-only file system.",
  "The location is read-only (mounted read-only, disk image, or protected); save elsewhere.",
  r"Read-only file system", r"\[Errno 30\]", errno="EROFS")
E("GEN", 29, "ENAMETOOLONG", ERROR, "File name or path too long.", "Use a shorter path or name.",
  r"File name too long", r"\[Errno (?:36|63)\]", errno="ENAMETOOLONG")
E("GEN", 30, "ENOTEMPTY", ERROR, "Folder is not empty.", "Remove the contents first.",
  r"Directory not empty", r"\[Errno (?:39|66)\]", errno="ENOTEMPTY")

# --------------------------------------------------------------------------
# PY (1): Python
# --------------------------------------------------------------------------
E("PY", 1, "MODULE_MISSING", ERROR, "A required Python package is not installed.",
  "Install it inside the project's virtual environment: pip install <name> (or pip install -r requirements.txt).",
  r"No module named ['\"]?(?P<d>[\w.]+)", r"ModuleNotFoundError")
E("PY", 2, "TK_MISSING", ERROR, "Python's Tk GUI toolkit (tkinter) is not installed.",
  "Debian/Ubuntu/Mint: sudo apt install python3-tk | Fedora: sudo dnf install python3-tkinter | "
  "macOS: install Python from python.org or brew install python-tk | Windows: re-run the Python installer and tick 'tcl/tk and IDLE'.",
  r"No module named ['\"]?_?tkinter", r"tkinter.*(?:not|isn't) (?:installed|available)",
  over=("PY.MODULE_MISSING",))
E("PY", 3, "DLL_LOAD_FAILED", ERROR, "A native library needed by a Python package failed to load.",
  "Wrong-bitness Python, or a missing runtime: on Windows install the VC++ Redistributable; reinstall the package.",
  r"DLL load failed", over=("PY.MODULE_MISSING",))
E("PY", 4, "IMPORT_NAME", ERROR, "Imported a name the installed package version does not have.",
  "Package version mismatch: upgrade/downgrade it to the version the code expects.",
  r"cannot import name ['\"]?(?P<d>\w+)")
E("PY", 5, "SYNTAX", ERROR, "Python could not parse the code - often Python is too old for the syntax used.",
  "Check python --version against the README requirement; otherwise the file is corrupt.",
  r"SyntaxError", r"IndentationError")
E("PY", 6, "RECURSION", ERROR, "Recursion too deep (usually an infinite loop in the logic).",
  "Fix the recursion or convert it to a loop.", r"RecursionError", r"maximum recursion depth")
E("PY", 7, "UNICODE", ERROR, "Text encoding problem.",
  "Open files with encoding='utf-8'; on Windows set PYTHONUTF8=1.",
  r"UnicodeDecodeError", r"UnicodeEncodeError")
E("PY", 8, "PIP_EXTERNALLY_MANAGED", ERROR, "The system Python refuses pip installs (externally managed).",
  "Use a virtual environment: python3 -m venv venv && source venv/bin/activate, then pip install.",
  r"externally-managed-environment")
E("PY", 9, "VENV_MISSING", ERROR, "Python's venv/ensurepip support is not installed.",
  "Debian/Ubuntu/Mint: sudo apt install python3-venv.",
  r"ensurepip is not available", r"No module named ['\"]?venv", r"python3-venv")
E("PY", 10, "PIP_NO_DIST", ERROR, "pip cannot find a compatible version of the package.",
  "Check the package name, your Python version and your connection; very new/old Pythons often lack wheels.",
  r"No matching distribution found for (?P<d>[\w.\-\[\]]+)", r"No matching distribution found",
  r"Could not find a version that satisfies")
E("PY", 11, "TCL_DATA_MISSING", ERROR, "Tcl/Tk support files are missing or damaged.",
  "Reinstall Python (or python3-tk); in virtual environments make sure TCL_LIBRARY is not pointing elsewhere.",
  r"Can't find a usable init\.tcl", r"Tcl data directory", r"usable tk\.tcl")
E("PY", 12, "WHEEL_BUILD_FAILED", ERROR, "A package had to be compiled and the build failed.",
  "No prebuilt wheel exists for this Python/OS: install a compiler (build-essential / Xcode CLT / VS Build Tools) "
  "or use a Python version that has wheels.",
  r"Failed building wheel", r"Failed to build", r"subprocess-exited-with-error",
  r"Building wheel for (?P<d>[\w.\-]+) .{0,40}\.\.\. error", generic=True)
E("PY", 13, "PY_VERSION", ERROR, "The installed Python version does not meet the package's requirement.",
  "Install the required Python version.",
  r"requires a different Python", r"Requires-Python", r"python_requires")
E("PY", 14, "UNCAUGHT", ERROR, "Uncaught Python exception.",
  "Read the last line of the traceback.", r"Traceback \(most recent call last\)", generic=True)
E("PY", 15, "TK_THREAD", ERROR, "Tk was used from a background thread.",
  "Only touch widgets from the main thread; use queue + root.after() to hand results over.",
  r"main thread is not in main loop", r"Tcl_AsyncDelete")
E("PY", 16, "FROZEN_FAILED", ERROR, "A packaged (PyInstaller) app failed to start.",
  "Run it from a console to see the real error; usually a missing hidden import or data file.",
  r"Failed to execute script", r"Failed to load Python DLL", r"PYI-\d+")

# --------------------------------------------------------------------------
# CPP (2): native code
# --------------------------------------------------------------------------
E("CPP", 1, "BAD_ALLOC", ERROR, "Memory allocation failed (std::bad_alloc).",
  "Out of RAM or an absurd size was requested; reduce the data size / check the size calculation.",
  r"std::bad_alloc", r"bad_alloc")
E("CPP", 2, "TERMINATE", FATAL, "An unhandled C++ exception terminated the program.",
  "The text after 'instance of' names the exception; catch it or fix its cause.",
  r"terminate called after throwing an instance of '(?P<d>[^']{1,60})'",
  r"terminate called after throwing an instance of", r"terminate called without an active exception")
E("CPP", 3, "UNDEFINED_REF", ERROR, "Linker: a function/symbol is declared but never defined.",
  "Add the missing source file or library to the link line (CMake target_link_libraries).",
  r"undefined reference to [`'](?P<d>[^'`(]{1,60})", r"undefined reference to", r"unresolved external symbol", r"LNK2019", r"LNK2001")
E("CPP", 4, "LINK_LIB_MISSING", ERROR, "Linker cannot find a library.",
  "Install the development package (-dev / -devel) or fix the library search path.",
  r"cannot find -l(?P<d>\S+)", r"LNK1104", r"ld: library not found for")
E("CPP", 5, "HEADER_MISSING", ERROR, "Compiler cannot find a header file.",
  "Install the development package (e.g. libfoo-dev) or add its include path.",
  r"fatal error: (?P<d>[^\s:]+): No such file or directory", r"fatal error C1083",
  r"'(?P<d>[^']+\.h(?:pp)?)' file not found", over=("GEN.ENOENT",))
E("CPP", 6, "CMAKE_ERROR", ERROR, "CMake configuration failed.",
  "Read the first CMake Error: it names the missing dependency or compiler.",
  r"CMake Error", r"cmake: command not found", r"CMake was unable to find", r"Could NOT find")
E("CPP", 7, "NO_COMPILER", ERROR, "No C/C++ compiler found.",
  "Debian/Ubuntu/Mint: sudo apt install build-essential | macOS: xcode-select --install | "
  "Windows: install Visual Studio Build Tools (C++ workload).",
  r"g\+\+: command not found", r"gcc: command not found", r"clang: command not found",
  r"No CMAKE_CXX_COMPILER", r"unable to find a C\+\+ compiler", over=("GEN.COMMAND_NOT_FOUND",))
E("CPP", 8, "SEGFAULT", FATAL, "Segmentation fault - the native code touched invalid memory.",
  "Bug or corrupt input in native code; run under gdb/lldb or with AddressSanitizer.",
  r"Segmentation fault", r"SIGSEGV", r"segfault", r"Fatal Python error: Segmentation")
E("CPP", 9, "ABORT", FATAL, "Program aborted itself (failed assertion or fatal runtime check).",
  "Read the assertion text just before the abort.",
  r"SIGABRT", r"Aborted \(core dumped\)", r"Assertion .{0,200} failed", r"Fatal Python error: Aborted")
E("CPP", 10, "STACK_OVERFLOW", FATAL, "Stack overflow or stack smashing.",
  "Deep recursion or a buffer overrun on the stack.",
  r"stack overflow", r"stack smashing detected")
E("CPP", 11, "ABI_MISMATCH", ERROR, "Native extension was built against a different Python/library ABI.",
  "Rebuild/reinstall the extension with the same Python and compiler as the host program.",
  r"undefined symbol: _Z", r"compiled against API version", r"was compiled against", r"binary incompatibility")
E("CPP", 12, "ILLEGAL_INSTRUCTION", FATAL, "The CPU lacks an instruction the program uses (AVX/AVX2/AVX-512/SSE4...).",
  "Build with a baseline target (-march=x86-64) or add runtime CPU dispatch. Essential for old Core i3/Atom machines.",
  r"Illegal instruction", r"SIGILL")
E("CPP", 13, "HEAP_CORRUPTION", FATAL, "Memory corruption detected (double free / heap damage).",
  "Run under AddressSanitizer/valgrind to find the bad free or overrun.",
  r"double free or corruption", r"free\(\): invalid", r"malloc\(\): corrupted", r"heap corruption", r"munmap_chunk")
E("CPP", 14, "OUT_OF_RANGE", ERROR, "C++ container/index out of range.",
  "Bounds bug in native code; check the index against size().",
  r"std::out_of_range", r"std::length_error", r"vector::_M_range_check")

# --------------------------------------------------------------------------
# WIN (3): Windows
# --------------------------------------------------------------------------
E("WIN", 1, "FILE_NOT_FOUND", ERROR, "Windows: file not found (error 2).",
  "Check the path; Windows paths need escaping/raw strings in code.",
  r"\[WinError 2\]", r"The system cannot find the file specified", winerr=2, over=("GEN.ENOENT",))
E("WIN", 2, "PATH_NOT_FOUND", ERROR, "Windows: path not found (error 3).",
  "A folder in the path does not exist.",
  r"\[WinError 3\]", r"The system cannot find the path specified", winerr=3, over=("GEN.ENOENT",))
E("WIN", 3, "ACCESS_DENIED", ERROR, "Windows: access denied (error 5).",
  "Run as administrator, or avoid protected folders (Program Files, C:\\); check antivirus 'controlled folder access'.",
  r"\[WinError 5\]", r"Access is denied", winerr=5, over=("GEN.EACCES",))
E("WIN", 4, "SHARING_VIOLATION", ERROR, "Windows: file is in use by another process (error 32).",
  "Close the other program (antivirus, Explorer preview, a previous run) and retry.",
  r"\[WinError 32\]", r"being used by another process", winerr=32)
E("WIN", 5, "INVALID_PARAMETER", ERROR, "Windows: invalid parameter (error 87).",
  "A bad argument/path/handle was passed to Windows.",
  r"\[WinError 87\]", r"The parameter is incorrect", winerr=87)
E("WIN", 6, "MOD_NOT_FOUND", ERROR, "Windows: a DLL (or one of its dependencies) was not found (error 126).",
  "Install the missing runtime (see WIN.VCRUNTIME_MISSING); inspect dependencies with the 'Dependencies' tool.",
  r"\[WinError 126\]", r"The specified module could not be found", winerr=126)
E("WIN", 7, "PROC_NOT_FOUND", ERROR, "Windows: DLL found but a function in it is missing (error 127).",
  "DLL version mismatch: a different version of the DLL is earlier on PATH.",
  r"\[WinError 127\]", r"The specified procedure could not be found", winerr=127)
E("WIN", 8, "BAD_EXE_FORMAT", ERROR, "Windows: not a valid Win32 application (error 193).",
  "32/64-bit mismatch, wrong CPU type (ARM), or a corrupt/incomplete download.",
  r"\[WinError 193\]", r"is not a valid Win32 application", winerr=193)
E("WIN", 9, "DLL_INIT_FAILED", ERROR, "Windows: a DLL failed to initialise (error 1114 / 0xC0000142).",
  "Usually a missing runtime or a security product blocking the DLL; reinstall the VC++ Redistributable.",
  r"\[WinError 1114\]", r"DLL initialization routine failed", r"0xC0000142", winerr=1114)
E("WIN", 10, "PAGING_FILE", ERROR, "Windows: out of virtual memory (error 1455).",
  "Close programs or increase the page file (System > Advanced > Performance > Virtual memory).",
  r"\[WinError 1455\]", r"paging file is too small", winerr=1455)
E("WIN", 11, "PATH_TOO_LONG", ERROR, "Windows: path too long (260-character limit).",
  "Use a shorter folder name or enable LongPathsEnabled in the registry/group policy.",
  r"\[WinError 206\]", r"filename or extension is too long", r"path is too long", winerr=206,
  over=("GEN.ENAMETOOLONG",))
E("WIN", 12, "ELEVATION", ERROR, "Windows: the operation requires administrator rights (error 740).",
  "Right-click > Run as administrator.",
  r"\[WinError 740\]", r"requires elevation", winerr=740)
E("WIN", 13, "BLOCKED_POLICY", ERROR, "Windows: blocked by group policy / application control (error 1260).",
  "A policy (AppLocker/WDAC) or security product blocks it; ask the administrator or whitelist the app.",
  r"\[WinError 1260\]", r"blocked by (?:a )?group policy", winerr=1260)
E("WIN", 14, "STATUS_DLL_NOT_FOUND", FATAL, "Windows: program exited because a required DLL is missing (0xC0000135).",
  "Install the VC++ Redistributable / the missing runtime; check PATH.",
  r"0xC0000135", r"STATUS_DLL_NOT_FOUND", r"-1073741515", r"3221225781")
E("WIN", 15, "STATUS_BAD_IMAGE", FATAL, "Windows: bad image - 32-bit and 64-bit code mixed (0xC000007B).",
  "Install the matching-bitness runtime (x64 vs x86) and avoid mixing DLL architectures.",
  r"0xC000007B", r"STATUS_INVALID_IMAGE_FORMAT", r"-1073741701", r"3221225595")
E("WIN", 16, "ACCESS_VIOLATION", FATAL, "Windows: access violation (0xC0000005) - native code touched invalid memory.",
  "Bug in native code or a bad DLL; run under a debugger or update the driver/library.",
  r"0xC0000005", r"access violation", r"-1073741819", r"3221225477")
E("WIN", 17, "STACK_OVERFLOW_NT", FATAL, "Windows: stack overflow (0xC00000FD).",
  "Deep recursion or oversized stack buffers.", r"0xC00000FD", r"-1073741571", r"3221225725")
E("WIN", 18, "STACK_BUFFER_OVERRUN", FATAL, "Windows: security check failure / stack buffer overrun (0xC0000409).",
  "Buffer overrun in native code.", r"0xC0000409", r"-1073740791")
E("WIN", 19, "VCRUNTIME_MISSING", ERROR, "Microsoft Visual C++ runtime DLL is missing.",
  "Install the 'Microsoft Visual C++ Redistributable 2015-2022' (x64, and x86 if the program is 32-bit).",
  r"(?P<d>VCRUNTIME140(?:_1)?\.dll)", r"(?P<d>MSVCP\d+(?:_\d)?\.dll)", r"(?P<d>VCOMP140\.dll)")
E("WIN", 20, "UCRT_MISSING", ERROR, "Windows Universal C Runtime is missing (older Windows 7/8).",
  "Install Windows Update KB2999226 (Universal C Runtime) or update Windows.",
  r"api-ms-win-crt-[a-z-]+-l\d-\d-\d\.dll", r"ucrtbase\.dll")
E("WIN", 21, "PYTHON_DLL_MISSING", ERROR, "The Python runtime DLL (pythonXY.dll) cannot be found.",
  "Reinstall Python, or rebuild/repackage the app so the DLL is bundled.",
  r"python3\d*\.dll")
E("WIN", 22, "MSVC_BUILD_TOOLS", ERROR, "A Microsoft C++ compiler is needed to build this package.",
  "Install 'Visual Studio Build Tools' with the 'Desktop development with C++' workload.",
  r"Microsoft Visual C\+\+ 14\.0 or greater is required", r"vcvarsall\.bat", r"Unable to find vcvarsall")
E("WIN", 23, "NOT_ON_PATH", ERROR, "Command not recognised - program is not on PATH.",
  "Add it to PATH (for Python re-run the installer and tick 'Add python.exe to PATH'), or use the 'py -3' launcher.",
  r"is not recognized as an internal or external command", r"'(?:python3?|py|pip3?)' is not recognized")
E("WIN", 24, "MS_STORE_ALIAS", ERROR, "'python' is the Microsoft Store stub, not a real Python.",
  "Install Python from python.org, then turn off the python.exe 'App execution aliases' in Settings.",
  r"Python was not found; run without arguments to install from the Microsoft Store",
  over=("WIN.NOT_ON_PATH",))
E("WIN", 25, "SMARTSCREEN", WARN, "Windows SmartScreen blocked an unrecognised app.",
  "Click 'More info' > 'Run anyway' (only for software you trust).",
  r"Windows protected your PC", r"SmartScreen")
E("WIN", 26, "CONSOLE_ENCODING", ERROR, "Console/code-page encoding problem (cp1252/cp437).",
  "Set PYTHONUTF8=1 or run 'chcp 65001'; open files with encoding='utf-8'.",
  r"'charmap' codec can't (?:encode|decode)", over=("PY.UNICODE",))

# --------------------------------------------------------------------------
# LIN (4): Linux
# --------------------------------------------------------------------------
E("LIN", 1, "GLIBC_OLD", ERROR, "Program was built for a newer glibc than this Linux provides.",
  "Use a build made on an older distro, an AppImage/static build, or upgrade the OS.",
  r"(?P<d>GLIBC_\d+\.\d+)['\"]? not found", r"version .GLIBC_")
E("LIN", 2, "GLIBCXX_OLD", ERROR, "libstdc++ on this system is older than the one the program was built with.",
  "Update libstdc++ (apt upgrade), 'conda install libstdcxx-ng', or static-link libstdc++.",
  r"GLIBCXX_\d+\.\d+", r"CXXABI_\d+")
E("LIN", 3, "SHARED_LIB_MISSING", ERROR, "A shared library (.so) the program needs is missing.",
  "Run: ldd <program> | grep 'not found', then install the package that provides it.",
  r"(?P<d>[\w.+\-]+\.so[\w.]*): cannot open shared object file", r"error while loading shared libraries",
  r"cannot open shared object file", over=("GEN.ENOENT",))
E("LIN", 4, "LIBGL_MISSING", ERROR, "OpenGL/EGL runtime library is missing.",
  "Debian/Ubuntu/Mint: sudo apt install libgl1 libegl1.",
  r"(?P<d>libGL\.so\.1)", r"libGLX", r"(?P<d>libEGL\.so[\w.]*)", over=("LIN.SHARED_LIB_MISSING", "GEN.ENOENT"))
E("LIN", 5, "QT_XCB", ERROR, "Qt cannot start its X11 (xcb) platform plugin.",
  "Debian/Ubuntu/Mint: sudo apt install libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0.",
  r"Could not load the Qt platform plugin ['\"]xcb", r"libxcb-cursor", r"libxcb-xinerama",
  over=("LIN.SHARED_LIB_MISSING",))
E("LIN", 6, "NO_DISPLAY", ERROR, "No graphical display available (headless/SSH session).",
  "Run on a desktop session, use 'ssh -X', run under xvfb-run, or use the program's command-line mode.",
  r"no display name and no \$DISPLAY", r"couldn't connect to display", r"cannot connect to X server",
  r"Unable to open display", r"cannot open display")
E("LIN", 7, "OOM_KILLED", FATAL, "The program was killed (SIGKILL) - most often the kernel's out-of-memory killer.",
  "Use less memory (smaller data / chunking), close other programs, or add swap.",
  r"Out of memory: Killed process", r"oom-kill", r"oom_reaper", r"exit(?:ed)? (?:with )?(?:code|status) 137",
  r"^Killed$")
E("LIN", 8, "EXEC_FORMAT", ERROR, "Cannot run the file: wrong CPU architecture or missing shebang.",
  "Check 'file <program>': ARM vs x86, 32 vs 64-bit; scripts need a #! line and +x.",
  r"Exec format error", r"cannot execute binary file")
E("LIN", 9, "APT_LOCK", ERROR, "Another package manager is running (apt/dpkg lock).",
  "Wait for Software Updater/another apt to finish; do not delete the lock file.",
  r"Could not get lock /var/lib/(?:dpkg|apt)", r"dpkg frontend lock", r"Unable to acquire the dpkg")
E("LIN", 10, "APT_NO_PACKAGE", ERROR, "apt cannot find that package.",
  "Run sudo apt update; check the package name and that the right repository is enabled.",
  r"Unable to locate package (?P<d>\S+)", r"Package '?(?P<d>[\w.+\-]+)'? has no installation candidate")
E("LIN", 11, "APPIMAGE_FUSE", ERROR, "AppImage needs FUSE, which is not installed.",
  "sudo apt install libfuse2 (or run the AppImage with --appimage-extract-and-run).",
  r"libfuse\.so\.2", r"AppImages require FUSE", r"fusermount", over=("LIN.SHARED_LIB_MISSING",))
E("LIN", 12, "USB_PERMISSION", ERROR, "No permission to access the USB device.",
  "Add a udev rule for the device (or add your user to 'plugdev'), then re-plug it.",
  r"USBError.*(?:Access denied|\[Errno 13\])", r"insufficient permissions", r"LIBUSB_ERROR_ACCESS")
E("LIN", 14, "ROOT_REQUIRED", ERROR, "This needs root privileges.",
  "Re-run with sudo (only if you trust the program).",
  r"sudo: a password is required", r"must be run as root", r"Are you root\?", r"requires root")
E("LIN", 15, "INOTIFY_LIMIT", WARN, "Out of file-watch (inotify) handles.",
  "sudo sysctl fs.inotify.max_user_watches=524288 (persist in /etc/sysctl.d/).",
  r"inotify watch limit", r"fs\.inotify\.max_user_watches")

# --------------------------------------------------------------------------
# MAC (5): macOS
# --------------------------------------------------------------------------
E("MAC", 1, "GATEKEEPER", ERROR, "macOS Gatekeeper blocked the app (unsigned / quarantined).",
  "Right-click > Open, or run: xattr -dr com.apple.quarantine <App.app>, or allow it in System Settings > Privacy & Security.",
  r"is damaged and can.?t be opened", r"cannot be opened because the developer cannot be verified",
  r"cannot be opened because it is from an unidentified developer", r"Apple could not verify",
  r"com\.apple\.quarantine")
E("MAC", 2, "XCODE_CLT", ERROR, "Xcode Command Line Tools are not installed.",
  "Run: xcode-select --install", r"xcode-select: note: no developer tools",
  r"invalid active developer path", r"xcrun: error")
E("MAC", 3, "TK_OS_MISMATCH", FATAL, "This Tk build is too old for this macOS version and crashes at startup.",
  "Install a current Python from python.org (3.11+) or 'brew install python-tk'.",
  r"macOS \d+ \(\d+\) or later required, have instead")
E("MAC", 4, "TK_DEPRECATED", WARN, "The macOS system Tk is deprecated and unreliable.",
  "Use python.org or Homebrew Python rather than /usr/bin/python3.",
  r"DEPRECATION WARNING: The system version of Tk is deprecated")
E("MAC", 5, "DYLIB_MISSING", ERROR, "A dynamic library the program needs was not found.",
  "Install the dependency (e.g. brew install <lib>); check linkage with 'otool -L <binary>'.",
  r"Library not loaded: (?P<d>\S+)", r"Library not loaded", r"dyld\[\d+\]: .*not found", r"image not found")
E("MAC", 6, "ARCH_MISMATCH", ERROR, "CPU architecture mismatch (Intel vs Apple Silicon).",
  "Use a universal2/arm64 build, or run the program under Rosetta: arch -x86_64 <cmd>.",
  r"incompatible architecture", r"mach-o file, but is an incompatible",
  r"have '(?:x86_64|arm64)', need '(?:x86_64|arm64)'")
E("MAC", 7, "NO_ROSETTA", ERROR, "Intel-only program on Apple Silicon and Rosetta is not installed.",
  "Run: softwareupdate --install-rosetta --agree-to-license", r"Bad CPU type in executable")
E("MAC", 8, "CODESIGN", ERROR, "The app's code signature is missing or invalid.",
  "Ad-hoc sign it: codesign --force --deep -s - <App.app> (or sign/notarise properly for distribution).",
  r"code signature (?:in)?valid", r"Code Signature Invalid", r"CODESIGNING", r"Killed: 9")
E("MAC", 9, "TCC_PRIVACY", ERROR, "macOS privacy protection blocked access (camera, files, etc.).",
  "Allow it in System Settings > Privacy & Security; bundled apps need the matching NS...UsageDescription in Info.plist.",
  r"privacy-sensitive data", r"NS\w+UsageDescription", r"not authorized to")
E("MAC", 10, "BREW_MISSING", ERROR, "Homebrew is not installed.", "Install it from https://brew.sh",
  r"brew: command not found", r"command not found: brew", over=("GEN.COMMAND_NOT_FOUND",))
E("MAC", 11, "PYTHON_NAME", ERROR, "'python' does not exist on macOS - use python3.",
  "Run python3, or install Python from python.org.", r"command not found: python$",
  over=("GEN.COMMAND_NOT_FOUND",))
E("MAC", 12, "SIP", ERROR, "System Integrity Protection blocked a change to a system location.",
  "Do not modify /System or /usr/bin; install under /usr/local, /opt/homebrew or your home folder.",
  r"System Integrity Protection", r"rootless")

# --------------------------------------------------------------------------
# NET (6): network
# --------------------------------------------------------------------------
E("NET", 1, "CONN_REFUSED", ERROR, "Connection refused - nothing is listening at that address/port.",
  "Start the server, check host/port, and check firewalls.",
  r"Connection refused", r"\[Errno (?:111|61)\]", r"WinError 10061", r"ECONNREFUSED")
E("NET", 2, "TIMEOUT", ERROR, "The network operation timed out.",
  "Check the connection and the target is reachable; raise the timeout for slow links.",
  r"timed out", r"TimeoutError", r"ETIMEDOUT", r"WinError 10060", r"\[Errno 110\]", r"ConnectTimeout")
E("NET", 3, "DNS_FAIL", ERROR, "Host name could not be resolved (DNS / no internet).",
  "Check internet and DNS settings, VPN, and the spelling of the host name.",
  r"Name or service not known", r"getaddrinfo failed", r"Temporary failure in name resolution",
  r"nodename nor servname provided", r"gaierror", r"Could not resolve host", r"NameResolutionError",
  r"WinError 11001")
E("NET", 4, "SSL_VERIFY", ERROR, "TLS certificate could not be verified.",
  "Check the system clock and any proxy/VPN; macOS python.org: run 'Install Certificates.command'; "
  "Linux: install ca-certificates. Do not disable verification.",
  r"CERTIFICATE_VERIFY_FAILED", r"SSLCertVerificationError", r"certificate verify failed",
  r"self[- ]signed certificate", over=("NET.SSL_HANDSHAKE",))
E("NET", 5, "ADDR_IN_USE", ERROR, "That network port is already in use.",
  "Close the other/previous instance or choose another port.",
  r"Address already in use", r"EADDRINUSE", r"WinError 10048", r"\[Errno (?:98|48)\]")
E("NET", 6, "UNREACHABLE", ERROR, "Network or host unreachable.",
  "Join the right Wi-Fi network, check cables/routing; WiFi gadgets (cameras, printers) host their own network.",
  r"Network is unreachable", r"No route to host", r"ENETUNREACH", r"EHOSTUNREACH",
  r"WinError (?:10051|10065)", r"\[Errno (?:101|113)\]")
E("NET", 7, "CONN_RESET", ERROR, "The connection was reset or dropped by the other side.",
  "Retry; if constant, the server/firewall/device is rejecting the request.",
  r"Connection reset by peer", r"ECONNRESET", r"WinError 10054", r"\[Errno 104\]",
  r"Connection aborted", r"RemoteDisconnected")
E("NET", 8, "HTTP_AUTH", ERROR, "Server refused access (HTTP 401/403).",
  "Check credentials/token and permissions.",
  r"HTTP Error 40[13]", r"40[13] (?:Client Error|Unauthorized|Forbidden)")
E("NET", 9, "HTTP_404", ERROR, "Server says the resource does not exist (HTTP 404).",
  "Check the URL / version number.", r"HTTP Error 404", r"404 (?:Client Error|Not Found)")
E("NET", 10, "HTTP_429", WARN, "Rate limited by the server (HTTP 429).",
  "Wait and retry more slowly.", r"HTTP Error 429", r"429 (?:Client Error|Too Many Requests)", r"rate limit")
E("NET", 11, "HTTP_5XX", ERROR, "The server had an error (HTTP 5xx).",
  "Not your fault: retry later.", r"HTTP Error (?P<d>5\d\d)",
  r"5\d\d (?:Server Error|Internal Server Error|Bad Gateway|Service Unavailable|Gateway Time-?out)")
E("NET", 12, "PROXY", ERROR, "A proxy blocked or failed the connection.",
  "Check proxy settings (HTTP_PROXY / HTTPS_PROXY) and credentials.",
  r"ProxyError", r"407 Proxy Authentication", r"Tunnel connection failed", r"Cannot connect to proxy")
E("NET", 13, "OFFLINE", ERROR, "No network connectivity.", "Check Wi-Fi/cable.")
E("NET", 14, "CHECKSUM", ERROR, "Downloaded data failed its checksum - corrupt or tampered download.",
  "Delete the partial file and download again.",
  r"checksum mismatch", r"hash mismatch", r"DO NOT MATCH THE HASHES", r"Hash sum mismatch")
E("NET", 15, "SSL_HANDSHAKE", ERROR, "TLS handshake failed.",
  "Old OpenSSL/Python vs. modern server, or a middlebox interfering; update Python/OpenSSL.",
  r"SSLError", r"EOF occurred in violation of protocol", r"TLSV1_ALERT", r"wrong version number")

# --------------------------------------------------------------------------
# HW (7): hardware, GPU, devices
# --------------------------------------------------------------------------
E("HW", 1, "OPENCL_NONE", WARN, "No usable OpenCL device - the CPU path will be used.",
  "Optional: install the vendor OpenCL runtime (Intel compute-runtime, pocl) for GPU speed-ups.",
  r"clGetPlatformIDs failed", r"CL_PLATFORM_NOT_FOUND_KHR", r"No OpenCL platforms",
  r"CL_DEVICE_NOT_FOUND", r"pyopencl.*LogicError")
E("HW", 2, "CUDA_FAIL", WARN, "CUDA GPU unavailable - the CPU path will be used.",
  "Update the NVIDIA driver, or leave GPU acceleration switched off.",
  r"CUDA driver version is insufficient", r"no CUDA-capable device", r"cudaErrorNoDevice",
  r"CUDA_ERROR_NO_DEVICE", r"libcuda\.so")
E("HW", 3, "GL_CONTEXT", ERROR, "Could not create an OpenGL context (GPU/driver too old or virtualised).",
  "Use software rendering (Linux: LIBGL_ALWAYS_SOFTWARE=1) or lower the app's OpenGL requirement.",
  r"GLXBadContext", r"Failed to create (?:an )?OpenGL context", r"failed to create GL context",
  r"OpenGL (?:version )?\d\.\d (?:or higher )?(?:is )?required", r"EGL_NOT_INITIALIZED", r"WGL:")
E("HW", 4, "VULKAN_FAIL", WARN, "Vulkan not available - another renderer will be used.",
  "Update the GPU driver or ignore.",
  r"VK_ERROR_INCOMPATIBLE_DRIVER", r"vkCreateInstance failed", r"VK_ERROR_INITIALIZATION_FAILED")
E("HW", 5, "METAL_FAIL", WARN, "Metal GPU not available.", "Ignore (CPU path) or update macOS.",
  r"MTLCreateSystemDefaultDevice", r"no Metal device")
E("HW", 6, "GPU_FALLBACK", WARN, "No usable GPU - running on the CPU path (slower, fully functional).",
  "Nothing to fix; expected on low-end machines. Switch the app's GPU option off to silence this.")
E("HW", 7, "LOW_RAM", WARN, "Less than 2 GB of RAM available.",
  "The app will run in reduced-memory mode; close other programs.")
E("HW", 8, "LOW_END_MODE", OK, "Low-end mode active (reduced threads / quality).", "Nothing to do.")
E("HW", 9, "USB_NO_BACKEND", ERROR, "USB library (libusb) is not installed.",
  "Linux: sudo apt install libusb-1.0-0 | macOS: brew install libusb | Windows: install a libusb driver (Zadig/libusbK).",
  r"NoBackendError", r"No backend available", r"libusb-1\.0", r"libusb0\.dll")
E("HW", 10, "USB_NOT_FOUND", ERROR, "USB device not found.",
  "Check cable, port and power; try another port; check the driver.",
  r"Device not found", r"No device found", r"LIBUSB_ERROR_NO_DEVICE", r"could not find (?:a )?device")
E("HW", 11, "CAMERA_OPEN", ERROR, "Could not open the camera.",
  "Camera busy, unplugged or no permission. Wi-Fi cameras: join the camera's network first.",
  r"Cannot open camera", r"can't open camera", r"Could not open (?:video )?(?:device|camera)",
  r"VIDEOIO.*(?:can't|cannot)", r"cv2\.VideoCapture.*failed")
E("HW", 12, "SERIAL_OPEN", ERROR, "Could not open the serial port.",
  "Wrong port, in use by another program, or no permission (Linux: sudo usermod -aG dialout $USER, then log out/in).",
  r"could not open port '?(?P<d>[^\s:']+)", r"could not open port", r"SerialException", r"PermissionError.*COM\d+", r"Access is denied.*COM\d+")

# --------------------------------------------------------------------------
# v0.2 additions (revision 2). Same rules: append only, never renumber.
# Messages/fixes written from general knowledge; not every one reproduced on a machine.
# --------------------------------------------------------------------------
E("GEN", 31, "EAGAIN", WARN, "Resource temporarily unavailable - try again.",
  "Usually transient (non-blocking I/O, a busy device); retry after a short wait.",
  r"Resource temporarily unavailable", r"\[Errno (?:11|35)\]", r"BlockingIOError", errno="EAGAIN")
E("GEN", 32, "EINVAL", ERROR, "Invalid argument passed to the operating system.",
  "A bad path, setting or value was passed (e.g. an unsupported serial baud rate or a bad file name).",
  r"Invalid argument", r"\[Errno 22\]", errno="EINVAL")
E("GEN", 33, "ENODEV", ERROR, "No such device.",
  "The device was unplugged, is not supported, or its driver is not loaded.",
  r"No such device(?! or address)", r"\[Errno 19\]", errno="ENODEV")
E("GEN", 34, "ENXIO", ERROR, "No such device or address.",
  "The device node exists but nothing answers (unplugged, wrong port, or driver problem).",
  r"No such device or address", r"\[Errno 6\]", errno="ENXIO")
E("GEN", 35, "EXDEV", ERROR, "Cannot move a file between different drives with a rename.",
  "Copy the file and then delete the original (shutil.move does this for you).",
  r"Invalid cross-device link", r"\[Errno 18\]", errno="EXDEV")
E("GEN", 36, "ETXTBSY", ERROR, "The program file is busy (still running or being written).",
  "Close the running copy, or wait for the copy/download to finish.",
  r"Text file busy", r"\[Errno 26\]", errno="ETXTBSY")
E("GEN", 37, "ELOOP", ERROR, "Too many levels of symbolic links (a link points at itself).",
  "Find and fix the looping symlink (ls -l along the path).",
  r"Too many levels of symbolic links", r"\[Errno (?:40|62)\]", errno="ELOOP")
E("GEN", 38, "EFBIG", ERROR, "File too large for this file system (FAT32 stops at 4 GB).",
  "Save to an exFAT/NTFS/ext4 drive, or split the file.",
  r"File too large", r"\[Errno 27\]", errno="EFBIG")
E("GEN", 39, "EDQUOT", ERROR, "Disk quota exceeded.", "Free space in your quota or ask the administrator.",
  r"Disk quota exceeded", r"\[Errno (?:122|69)\]", errno="EDQUOT")
E("GEN", 40, "ESRCH", WARN, "No such process (it already exited).", "Usually harmless; the process had finished.",
  r"No such process", r"\[Errno 3\]", r"ProcessLookupError", errno="ESRCH")
E("GEN", 41, "E2BIG", ERROR, "Argument list too long.",
  "Too many file names on one command line; use a list file or process in batches.",
  r"Argument list too long", r"\[Errno 7\]", errno="E2BIG")
E("GEN", 42, "CORRUPT_FILE", ERROR, "A file is corrupt, truncated or not in the expected format.",
  "Download/export it again; check the file really is the type its extension says.",
  r"BadZipFile", r"File is not a zip file", r"unexpected end of (?:file|data|stream)", r"premature end of",
  r"[Tt]runcated (?:file|data)")
E("GEN", 43, "EXIT_NONZERO", ERROR, "A program exited with a non-zero status.",
  "The detail is the exit status; look at that program's own output just before it ended.",
  generic=True)
E("GEN", 44, "SUBPROCESS_FAILED", ERROR, "A helper command failed.",
  "Run the command by hand to see its full output.",
  r"returned non-zero exit status (?P<d>-?\d+)", r"CalledProcessError", generic=True)
E("GEN", 45, "COMMAND_NOT_FOUND", ERROR, "A command/program is not installed (or not on PATH).",
  "Install the program the detail names, or add it to PATH.",
  r"(?P<d>[\w.+\-]+): command not found", r"command not found: (?P<d>[\w.+\-]+)", r"(?P<d>[\w.+\-]+): not found$")
E("GEN", 46, "DB_LOCKED", ERROR, "Database is locked by another program or another copy of this one.",
  "Close the other copy; if none is running, a crashed run may have left a lock - restart.",
  r"database is locked", r"database table is locked")
E("GEN", 47, "ALREADY_RUNNING", WARN, "Another copy of the program is already running.",
  "Use the copy that is open, or close it first.",
  r"another instance (?:is )?(?:already )?running", r"is already running")

E("PY", 17, "TYPE_ERROR", ERROR, "Python TypeError: a value of the wrong type was used.",
  "A bug, or a package version different from the one the code was written for.",
  r"TypeError")
E("PY", 18, "VALUE_ERROR", ERROR, "Python ValueError: a value was the right type but not acceptable.",
  "Check the input data/settings the message mentions.", r"ValueError")
E("PY", 19, "KEY_ERROR", ERROR, "Python KeyError: a dictionary/config key is missing.",
  "The detail names the key: check the config file or data for it.",
  r"KeyError: ['\"]?(?P<d>[^'\"\s]{1,40})", r"KeyError")
E("PY", 20, "INDEX_ERROR", ERROR, "Python IndexError: list index out of range.",
  "Empty or shorter data than expected; check the input.", r"IndexError")
E("PY", 21, "ATTRIBUTE_ERROR", ERROR, "Python AttributeError: an object lacks the attribute used.",
  "Often a None value or a package version mismatch; the detail names the attribute.",
  r"has no attribute ['\"](?P<d>\w+)", r"AttributeError")
E("PY", 22, "NAME_ERROR", ERROR, "Python NameError: a name is used before it is defined.",
  "Bug or missing import; the detail is the name.", r"NameError: name ['\"](?P<d>\w+)", r"NameError")
E("PY", 23, "ZERO_DIVISION", ERROR, "Division by zero.", "Guard the calculation against empty/zero input.",
  r"ZeroDivisionError")
E("PY", 24, "ASSERTION", ERROR, "A Python assert failed (an internal sanity check).",
  "Report it with the log; the code met a state it did not expect.", r"AssertionError")
E("PY", 25, "NOT_IMPLEMENTED", ERROR, "Feature not implemented yet.", "Use another option, or update the program.",
  r"NotImplementedError")
E("PY", 26, "OVERFLOW", ERROR, "Number too large (OverflowError).", "Check the input values / units.",
  r"OverflowError")
E("PY", 27, "DEPRECATION", WARN, "A deprecated feature was used (still works for now).",
  "Update the code or pin the package version before it is removed.",
  r"DeprecationWarning", r"FutureWarning", r"PendingDeprecationWarning")
E("PY", 28, "RUNTIME_WARNING", WARN, "Python runtime warning (e.g. maths on empty data, divide by zero in numpy).",
  "Check the data that produced it.", r"RuntimeWarning")
E("PY", 29, "NUMPY2_ABI", ERROR, "A package was compiled for NumPy 1.x but NumPy 2 is installed.",
  "pip install \"numpy<2\", or upgrade the package that failed to a NumPy-2 build.",
  r"compiled using NumPy 1\.x cannot be run in", r"numpy\.dtype size changed", r"_ARRAY_API not found",
  r"numpy\.core\.multiarray failed to import", over=("CPP.ABI_MISMATCH",))
E("PY", 30, "DISTUTILS_REMOVED", ERROR, "distutils was removed in Python 3.12.",
  "pip install setuptools (it provides a replacement), or upgrade the package.",
  r"No module named ['\"]?distutils", over=("PY.MODULE_MISSING",))
E("PY", 31, "PIP_CONFLICT", ERROR, "pip cannot satisfy conflicting package version requirements.",
  "Use a fresh virtual environment, or relax the version pins that conflict.",
  r"ResolutionImpossible", r"conflicting dependencies")
E("PY", 32, "PIP_DEP_WARNING", WARN, "pip installed something that breaks another package's requirements.",
  "Check the packages it names; a fresh virtual environment per project avoids this.",
  r"pip's dependency resolver does not currently take into account")
E("PY", 33, "ASYNCIO_LOOP", ERROR, "asyncio event loop misuse (none running, already running, or closed).",
  "Run coroutines with asyncio.run(); do not call it from inside a running loop.",
  r"There is no current event loop", r"Event loop is closed", r"cannot be called from a running event loop",
  r"This event loop is already running")
E("PY", 34, "MP_BOOTSTRAP", ERROR, "multiprocessing started without the if __name__ == '__main__': guard.",
  "Put the program's start-up code under if __name__ == '__main__': (needed on Windows/macOS).",
  r"bootstrapping phase", r"freeze_support\(\)")
E("PY", 35, "THREAD_START", ERROR, "Could not start a new thread (out of threads/memory).",
  "Reuse a thread pool; on small boards lower the worker count.", r"can't start new thread")
E("PY", 36, "PY_FATAL", FATAL, "The Python interpreter hit a fatal error.",
  "Usually a crash inside a native extension; see the lines after 'Fatal Python error'.",
  r"Fatal Python error", generic=True)
E("PY", 37, "PICKLE", ERROR, "Object could not be pickled/unpickled (saving state or multiprocessing).",
  "Pass plain data between processes; delete old cache/state files after an upgrade.",
  r"PicklingError", r"UnpicklingError", r"[Cc]an't pickle", r"cannot pickle")
E("PY", 38, "PIL_IMAGE", ERROR, "Image file could not be read (unknown or damaged format).",
  "Check the file opens in an image viewer; re-export it as PNG/JPEG.",
  r"cannot identify image file", r"UnidentifiedImageError")
E("PY", 39, "PIL_BOMB", WARN, "Image is huge (decompression-bomb protection triggered).",
  "Use a smaller image, or raise PIL.Image.MAX_IMAGE_PIXELS if you trust the file.",
  r"DecompressionBomb(?:Warning|Error)")
E("PY", 40, "TCL_ERROR", ERROR, "Tk reported an error.",
  "Read the TclError text; often a widget used after its window closed.",
  r"_tkinter\.TclError", r"TclError", generic=True)
E("PY", 41, "QT_BINDING_MISSING", ERROR, "No Qt binding (PyQt/PySide) is installed.",
  "pip install PySide6 (or PyQt6) inside the virtual environment.",
  r"No Qt bindings? (?:could be )?found", r"PythonQtError")
E("PY", 42, "MPL_NO_GUI", WARN, "matplotlib has no GUI backend - windows will not appear.",
  "Install tkinter (python3-tk) or a Qt binding; or save figures to files.",
  r"non-GUI backend", r"FigureCanvasAgg is non-interactive")
E("PY", 43, "SSL_MODULE", ERROR, "This Python was built without SSL support.",
  "Install the OpenSSL development package and rebuild Python, or use the python.org / distro build.",
  r"No module named ['\"]?_ssl", r"SSL module is not available", r"ssl module in Python is not available",
  over=("PY.MODULE_MISSING",))
E("PY", 44, "SETUPTOOLS_MISSING", ERROR, "setuptools / pkg_resources is not installed.",
  "pip install setuptools", r"No module named ['\"]?(?:setuptools|pkg_resources)", over=("PY.MODULE_MISSING",))
E("PY", 45, "PIP_MISSING", ERROR, "pip is not installed for this Python.",
  "python3 -m ensurepip --upgrade (Debian/Ubuntu/Mint: sudo apt install python3-pip).",
  r"No module named ['\"]?pip\b", r"\bpip3?: command not found", over=("PY.MODULE_MISSING", "GEN.COMMAND_NOT_FOUND"))
E("PY", 46, "WRONG_SERIAL_PKG", ERROR, "The wrong 'serial' package is installed (not pyserial).",
  "pip uninstall serial, then pip install pyserial.",
  r"module ['\"]serial['\"] has no attribute ['\"]Serial", over=("PY.ATTRIBUTE_ERROR",))
E("PY", 47, "OPENCV_HEADLESS", ERROR, "OpenCV was installed without GUI support (headless build).",
  "pip uninstall opencv-python-headless, then pip install opencv-python.",
  r"Rebuild the library with Windows, GTK\+ 2\.x or Cocoa support")

E("CPP", 15, "LNK_DUPLICATE", ERROR, "Linker: the same symbol is defined twice.",
  "A function defined in a header without 'inline', or a source file listed twice.",
  r"multiple definition of", r"LNK2005", r"duplicate symbol")
E("CPP", 16, "CXX_STD", ERROR, "The compiler is too old or set to an older C++ standard.",
  "Set CMAKE_CXX_STANDARD (17/20) or install a newer compiler.",
  r"requires compiler and library support for the", r"C\+\+(?:17|20) (?:or later )?(?:is )?required")
E("CPP", 17, "PKG_CONFIG", ERROR, "pkg-config could not find a library.",
  "Install the library's -dev/-devel package (or set PKG_CONFIG_PATH).",
  r"Package (?P<d>[\w.+\-]+) was not found in the pkg-config search path", r"No package '(?P<d>[\w.+\-]+)' found",
  r"pkg-config: command not found", over=("GEN.COMMAND_NOT_FOUND",))
E("CPP", 18, "MAKE_NO_RULE", ERROR, "make: no rule / no makefile.",
  "Run it from the right folder, or run CMake first to generate the makefile.",
  r"No rule to make target", r"No targets specified and no makefile found")
E("CPP", 19, "CC_KILLED", ERROR, "The compiler was killed - out of memory while compiling.",
  "Build with fewer jobs (make -j1 / cmake --build . -j1) and add swap; common on Pi and 4 GB machines.",
  r"internal compiler error: Killed", r"Killed signal terminated program cc1", over=("CPP.ICE", "LIN.OOM_KILLED"))
E("CPP", 20, "ICE", ERROR, "Internal compiler error (a compiler bug or bad hardware).",
  "Retry; try another compiler version or lower optimisation.", r"internal compiler error", generic=True)
E("CPP", 21, "PURE_VIRTUAL", FATAL, "Pure virtual method called (object used during/after destruction).",
  "Lifetime bug in native code.", r"pure virtual method called")
E("CPP", 22, "FPE", FATAL, "Arithmetic exception in native code (often integer divide by zero).",
  "Guard the division; check for empty data.", r"Floating point exception", r"SIGFPE")
E("CPP", 23, "BUS_ERROR", FATAL, "Bus error - misaligned access or a file mapped into memory changed size.",
  "Do not modify files while they are open; on ARM check alignment.", r"^Bus error", r"Bus error \(core dumped\)",
  r"SIGBUS")
E("CPP", 24, "CMAKE_OLD", ERROR, "CMake is too old for this project.",
  "pip install --upgrade cmake (gives a current CMake), or install it from cmake.org.",
  r"CMake (?P<d>\d+\.\d+(?:\.\d+)?) or higher is required", over=("CPP.CMAKE_ERROR",))
E("CPP", 25, "FIND_PACKAGE", ERROR, "CMake could not find a dependency.",
  "Install the development package for the detail, or set <Name>_DIR / CMAKE_PREFIX_PATH.",
  r"Could not find a package configuration file provided by \"(?P<d>[\w:.+\-]+)\"", r"Could NOT find (?P<d>\w+)",
  r"By not providing \"Find(?P<d>\w+)\.cmake\"", over=("CPP.CMAKE_ERROR",))
E("CPP", 26, "WERROR", ERROR, "A compiler warning is being treated as an error.",
  "Build without -Werror, or use the compiler version the project was written for.",
  r"\[-Werror(?:=[\w\-]+)?\]", r"warnings being treated as errors")
E("CPP", 27, "LINK_ARCH", ERROR, "Linker: a library was built for a different CPU architecture.",
  "Use the library build for this platform (x86-64 / ARM64 / 32-bit).",
  r"file in wrong format", r"skipping incompatible", r"LNK1112",
  r"building for .{1,40} but attempting to link with file built for")
E("CPP", 28, "MSVC_RUNTIME_MISMATCH", ERROR, "MSVC: libraries built with different runtime settings (/MD vs /MT, Debug vs Release).",
  "Build every library with the same runtime and configuration.", r"LNK2038", r"mismatch detected for 'RuntimeLibrary'")
E("CPP", 29, "PYTHON_DEV", ERROR, "Python.h is missing - the Python development headers are not installed.",
  "Debian/Ubuntu/Mint: sudo apt install python3-dev | Fedora: sudo dnf install python3-devel.",
  r"Python\.h['\"]?:? (?:No such file|file not found)", over=("CPP.HEADER_MISSING",))

E("WIN", 27, "NOT_ENOUGH_MEMORY", ERROR, "Windows: not enough memory resources (error 8).",
  "Close programs; check for a memory leak.", r"\[WinError 8\]", r"Not enough memory resources", winerr=8)
E("WIN", 28, "DISK_FULL", ERROR, "Windows: not enough space on the disk (error 112).", "Free disk space.",
  r"\[WinError 112\]", r"There is not enough space on the disk", winerr=112, over=("GEN.ENOSPC",))
E("WIN", 29, "ALREADY_EXISTS", ERROR, "Windows: cannot create a file that already exists (error 183).",
  "Remove or rename the existing file first.", r"\[WinError 183\]",
  r"Cannot create a file when that file already exists", winerr=183, over=("GEN.EEXIST",))
E("WIN", 30, "DIR_NOT_EMPTY", ERROR, "Windows: the folder is not empty (error 145).", "Remove its contents first.",
  r"\[WinError 145\]", r"The directory is not empty", winerr=145, over=("GEN.ENOTEMPTY",))
E("WIN", 31, "BAD_NAME", ERROR, "Windows: invalid file/folder name (error 123).",
  "Remove characters like : * ? \" < > | from the name; check for stray quotes in the path.",
  r"\[WinError 123\]", r"The filename, directory name, or volume label syntax is incorrect", winerr=123)
E("WIN", 32, "DEVICE_NOT_READY", ERROR, "Windows: the device is not ready (error 21).",
  "Insert the media / reconnect the drive.", r"\[WinError 21\]", r"The device is not ready", winerr=21)
E("WIN", 33, "NETWORK_PATH", ERROR, "Windows: the network path was not found (error 53).",
  "Check the share name, that the PC is on and network discovery is enabled.",
  r"\[WinError 53\]", r"The network path was not found", winerr=53)
E("WIN", 34, "LOCK_VIOLATION", ERROR, "Windows: another process locked part of the file (error 33).",
  "Close the other program using the file.", r"\[WinError 33\]", r"locked a portion of the file", winerr=33)
E("WIN", 35, "SEM_TIMEOUT", ERROR, "Windows: the device stopped responding (semaphore timeout, error 121).",
  "USB/serial device hung: re-plug it, use another port or a shorter cable.",
  r"\[WinError 121\]", r"semaphore timeout period has expired", winerr=121)
E("WIN", 36, "BAD_COMMAND", ERROR, "Windows: the device does not recognise the command (error 22).",
  "Driver or device problem; reinstall the driver or re-plug the device.",
  r"\[WinError 22\]", r"The device does not recognize the command", winerr=22)
E("WIN", 37, "IO_ABORTED", ERROR, "Windows: I/O operation aborted (error 995) - usually a device was unplugged.",
  "Reconnect the device and reopen the port.", r"\[WinError 995\]", r"I/O operation has been aborted",
  winerr=995)
E("WIN", 38, "VIRUS_BLOCKED", ERROR, "Windows Defender blocked or removed the file (error 225).",
  "Packaged Python apps are often false positives: restore it and add an exclusion only if you trust it.",
  r"\[WinError 225\]", r"file contains a virus", winerr=225)
E("WIN", 39, "STATUS_HEAP_CORRUPTION", FATAL, "Windows: heap corruption (0xC0000374).",
  "Memory bug in native code or a mismatched DLL.", r"0xC0000374", r"-1073740940", r"3221226356")
E("WIN", 40, "STATUS_ILLEGAL_INSTRUCTION", FATAL, "Windows: illegal instruction (0xC000001D) - CPU lacks AVX etc.",
  "Use a build for older CPUs (no AVX2/AVX-512); important for old Core i3 / Atom / Celeron.",
  r"0xC000001D", r"-1073741795", r"3221225501")
E("WIN", 41, "STATUS_NO_MEMORY", FATAL, "Windows: out of memory (0xC0000017).", "Close programs or add RAM / page file.",
  r"0xC0000017", r"-1073741801", r"3221225495")
E("WIN", 42, "CTRL_C_EXIT", OK, "Windows: the program was stopped with Ctrl+C (0xC000013A).", "Nothing to do.",
  r"0xC000013A", r"-1073741510", r"STATUS_CONTROL_C_EXIT")
E("WIN", 43, "EXECUTION_POLICY", ERROR, "PowerShell blocked the script (execution policy).",
  "Use the .bat launcher, or: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned (if allowed).",
  r"running scripts is disabled on this system", r"about_Execution_Policies")
E("WIN", 44, "PY_LAUNCHER", ERROR, "The 'py' launcher found no suitable Python.",
  "Install Python from python.org; check 'py --list'.", r"No suitable Python runtime found",
  r"Python \d+\.\d+ not found!")
E("WIN", 45, "DRIVER_UNSIGNED", ERROR, "Windows will not load an unsigned driver (Device Manager code 52).",
  "Install a signed driver from the maker (CH340/CP210x/FTDI), not a random download.",
  r"\(Code 52\)", r"cannot verify the digital signature for the drivers")
E("WIN", 46, "DEVICE_CANNOT_START", ERROR, "Windows: the device cannot start (Device Manager code 10).",
  "Reinstall/roll back the driver; try another USB port.", r"\(Code 10\)", r"This device cannot start")
E("WIN", 47, "DEVICE_PROBLEM_43", ERROR, "Windows stopped the device because it reported problems (code 43).",
  "Re-plug, try another cable/port, update or roll back the driver.", r"\(Code 43\)",
  r"Windows has stopped this device because it has reported problems")

E("LIN", 16, "WAYLAND", WARN, "The app needs X11 but the session is Wayland.",
  "Set QT_QPA_PLATFORM=xcb (Qt apps) or log in to an X11/Xorg session.",
  r"Could not load the Qt platform plugin ['\"]wayland", r"qt\.qpa\.wayland", r"Wayland is not supported")
E("LIN", 17, "DIALOUT", ERROR, "No permission to open the serial port (not in the 'dialout' group).",
  "sudo usermod -aG dialout $USER, then log out and back in (Arch/Fedora: group 'uucp').",
  r"Permission denied: '/dev/tty(?:USB|ACM|S)\d+'", r"/dev/tty(?:USB|ACM)\d+.{0,40}Permission denied",
  over=("HW.SERIAL_OPEN", "GEN.EACCES"))
E("LIN", 18, "BRLTTY", ERROR, "brltty (Braille driver) grabbed a CH340/CH341 USB-serial adapter.",
  "sudo apt remove brltty, then re-plug the board (common on Ubuntu/Mint with ESP32/Arduino clones).",
  r"brltty")
E("LIN", 19, "MODEMMANAGER", WARN, "ModemManager is probing the serial port (can disturb flashing).",
  "sudo systemctl stop ModemManager (or disable it if you never use a mobile modem).", r"ModemManager")
E("LIN", 20, "NOT_EXECUTABLE", ERROR, "File is not marked executable.",
  "chmod +x <file> (or right-click > Properties > allow executing).",
  r"bash: \./\S+: Permission denied", r"Permission denied.{0,40}\.(?:sh|AppImage)\b", over=("GEN.EACCES",))
E("LIN", 21, "BAD_INTERPRETER", ERROR, "Script has Windows line endings or a wrong #! line.",
  "Convert line endings: dos2unix <script> (or sed -i 's/\\r$//' <script>).",
  r"bad interpreter", r"\$'\\r': command not found", over=("GEN.COMMAND_NOT_FOUND",))
E("LIN", 22, "SERVICE_FAILED", ERROR, "A systemd service failed to start.",
  "journalctl -u <service> -b shows why; the detail names the service.",
  r"Job for (?P<d>\S+\.service) failed", r"\[FAILED\] Failed to start (?P<d>[^.\n]{1,40})")
E("LIN", 23, "STORAGE_IO", ERROR, "Storage hardware error - SD card or USB drive failing.",
  "Back up now and replace the SD card/drive; use a good power supply on a Pi.",
  r"I/O error, dev (?P<d>mmcblk\d+|sd[a-z])", r"mmc\d: (?:error|timeout)", over=("GEN.EIO",))
E("LIN", 24, "DPKG_INTERRUPTED", ERROR, "A previous package install was interrupted.",
  "sudo dpkg --configure -a", r"dpkg was interrupted")
E("LIN", 25, "APT_BROKEN", ERROR, "Broken package dependencies.",
  "sudo apt --fix-broken install, then retry.", r"Unmet dependencies", r"you have held broken packages")
E("LIN", 26, "APT_KEY", ERROR, "A package repository's signing key is missing or expired.",
  "Re-add the repository's key as its install page describes, then sudo apt update.",
  r"NO_PUBKEY", r"signatures couldn't be verified", r"is not signed")
E("LIN", 27, "NO_PYTHON_CMD", ERROR, "Script asks for 'python' but only 'python3' exists.",
  "sudo apt install python-is-python3, or run it with python3.",
  r"/usr/bin/env: ['‘]?python['’]?: No such file or directory", over=("GEN.ENOENT",))
E("LIN", 28, "SELINUX", ERROR, "SELinux blocked an action.",
  "Check 'sudo ausearch -m avc -ts recent'; fix the file labels rather than disabling SELinux.",
  r"avc:\s+denied", r"SELinux is preventing")
E("LIN", 29, "IMMUTABLE_OS", ERROR, "System folders are read-only (immutable distro such as Bazzite/Silverblue).",
  "Use Flatpak, Distrobox or 'rpm-ostree install', or install into your home folder.",
  r"Read-only file system.{0,80}/usr", r"rpm-ostree", over=("GEN.EROFS",))
E("LIN", 30, "ALSA", WARN, "Audio: ALSA could not find the sound card/device.",
  "Check the device is plugged in and selected; usually harmless chatter if sound still works.",
  r"ALSA lib .{0,80}(?:cannot find card|Unknown PCM)")
E("LIN", 31, "KERNEL_MODULE", ERROR, "A kernel module (driver) is not available.",
  "Install the matching driver/kernel-modules package or reboot after a kernel update.",
  r"modprobe: FATAL: Module (?P<d>\S+) not found", r"Module (?P<d>\S+) not found in directory")

E("MAC", 13, "FULL_DISK_ACCESS", ERROR, "macOS blocked access to a protected folder (Desktop/Documents/Downloads).",
  "Allow the app (or Terminal) in System Settings > Privacy & Security > Files and Folders / Full Disk Access.",
  r"Operation not permitted.{0,80}(?:Desktop|Documents|Downloads)", r"Full Disk Access", over=("GEN.EPERM",))
E("MAC", 14, "BREW_PREFIX", ERROR, "Intel Homebrew used on an Apple Silicon Mac.",
  "Use the ARM Homebrew in /opt/homebrew (reinstall from brew.sh).",
  r"Cannot install in Homebrew on ARM processor in Intel default prefix")
E("MAC", 15, "APP_TRANSLOCATION", WARN, "The app runs from a read-only random location (App Translocation).",
  "Move the app into the Applications folder and open it again.", r"AppTranslocation")
E("MAC", 16, "SYSEXT_BLOCKED", ERROR, "macOS blocked a driver/system extension (e.g. a USB-serial driver).",
  "Allow it in System Settings > Privacy & Security, then restart.", r"System Extension Blocked",
  r"system extension.{0,40}blocked")
E("MAC", 17, "XCODE_LICENSE", ERROR, "The Xcode licence has not been accepted.", "sudo xcodebuild -license accept",
  r"You have not agreed to the Xcode license")
E("MAC", 18, "OPENMP", ERROR, "Apple clang has no OpenMP support built in.",
  "brew install libomp (and point the build at it), or build without OpenMP.",
  r"unsupported option '-fopenmp'", r"omp\.h['\"]? file not found", over=("CPP.HEADER_MISSING",))
E("MAC", 19, "NOT_FRAMEWORK", ERROR, "Python is not installed as a framework (GUI back-end cannot start).",
  "Use python.org or Homebrew Python, or a different GUI back-end.", r"Python is not installed as a framework")

E("NET", 16, "HTTP_400", ERROR, "The server rejected the request as malformed (HTTP 400).",
  "Check the URL/parameters; the client may be out of date.", r"HTTP Error 400", r"400 (?:Client Error|Bad Request)")
E("NET", 17, "TOO_MANY_REDIRECTS", ERROR, "Too many redirects (redirect loop).",
  "Check the URL; clear cookies or update the server address.", r"Exceeded \d+ redirects", r"TooManyRedirects",
  r"redirect loop")
E("NET", 18, "MDNS", ERROR, "A '.local' name could not be resolved (mDNS/Bonjour).",
  "Use the device's IP address; Windows needs Bonjour, Linux needs avahi-daemon for .local names.",
  r"(?P<d>[\w\-]+\.local)\b.{0,60}(?:Name or service not known|nodename nor servname|getaddrinfo failed|"
  r"Could not resolve)", over=("NET.DNS_FAIL",))
E("NET", 19, "WEBSOCKET", ERROR, "WebSocket connection failed or closed unexpectedly.",
  "Check the server (e.g. Moonraker) is running and the address/port is right.",
  r"WebSocketException", r"WebSocket connection to .{1,80} failed", r"websocket.{0,20}(?:closed|failed)")
E("NET", 20, "PORT_FORBIDDEN", ERROR, "Not allowed to use that network port (firewall or ports < 1024 need root).",
  "Use a port above 1024 or allow the app through the firewall.",
  r"WinError 10013", r"forbidden by its access permissions")
E("NET", 21, "HTTP_413", ERROR, "Upload too large for the server (HTTP 413).",
  "Raise the server's upload limit (e.g. nginx client_max_body_size) or send a smaller file.",
  r"413 (?:Request Entity Too Large|Payload Too Large)", r"HTTP Error 413")
E("NET", 22, "BROKEN_DOWNLOAD", ERROR, "Download was cut off part-way.",
  "Retry; on flaky Wi-Fi resume the download or use a cable.",
  r"IncompleteRead", r"ContentTooShortError", r"Connection broken:")
E("NET", 23, "CERT_EXPIRED", ERROR, "TLS certificate expired (or this computer's clock is wrong).",
  "Check the date/time; if correct, the server's certificate has expired.",
  r"certificate has expired", r"CERTIFICATE_EXPIRED", over=("NET.SSL_VERIFY", "NET.SSL_HANDSHAKE"))
E("NET", 24, "HOST_DOWN", ERROR, "The host is down.", "Power on / wake the device, then retry.",
  r"Host is down", r"EHOSTDOWN")

E("HW", 13, "UNDERVOLTAGE", ERROR, "Raspberry Pi under-voltage - the power supply is too weak.",
  "Use a proper 5 V / 3 A (Pi 4) or 5 A (Pi 5) supply and a short, thick cable.",
  r"[Uu]nder-?voltage detected", r"throttled=0x[1-9a-fA-F]")
E("HW", 14, "USB_ENUM_FAIL", ERROR, "A USB device failed to connect properly (enumeration failed).",
  "Use a data (not charge-only) cable, another port, or a powered hub.",
  r"device descriptor read/\d+, error", r"unable to enumerate USB device", r"device not accepting address")
E("HW", 15, "DEVICE_GONE", ERROR, "The device disconnected while in use.",
  "Check the cable/power; a board that resets on connect may be browning out.",
  r"USB disconnect, device number", r"device reports readiness to read but returned no data",
  r"[Dd]evice (?:was )?disconnected")
E("HW", 16, "SERIAL_TIMEOUT", ERROR, "Serial port read/write timed out.",
  "Check baud rate and wiring (TX/RX swapped?), and that the device is running.",
  r"SerialTimeoutException", r"Write timeout", over=("NET.TIMEOUT",))
E("HW", 17, "GPU_OOM", ERROR, "GPU ran out of memory.",
  "Use smaller batches/resolution, or switch GPU acceleration off (CPU path).",
  r"CUDA out of memory", r"OutOfMemoryError: CUDA", r"CL_MEM_OBJECT_ALLOCATION_FAILURE",
  r"VK_ERROR_OUT_OF_DEVICE_MEMORY", r"CL_OUT_OF_RESOURCES")
E("HW", 18, "SOFTWARE_GL", WARN, "Software OpenGL in use (llvmpipe / Microsoft Basic Render) - slow.",
  "Install/enable the GPU driver; in a VM enable 3D acceleration.",
  r"llvmpipe", r"softpipe", r"Microsoft Basic Render", r"GDI Generic")
E("HW", 19, "BLUETOOTH", ERROR, "Bluetooth adapter is off or not available.",
  "Switch Bluetooth on; on Linux check 'bluetoothctl show' and that bluetoothd is running.",
  r"Bluetooth (?:adapter )?(?:is )?(?:off|not available|unavailable)", r"BleakError", r"No Bluetooth adapters? found")
E("HW", 20, "REALSENSE", ERROR, "Intel RealSense camera not found or not streaming.",
  "Use a USB 3 port and cable; check with realsense-viewer; update the camera firmware.",
  r"No RealSense devices? (?:were )?found", r"rs2::error", r"Frame didn't arrive within")
E("HW", 21, "AUDIO_OPEN", ERROR, "Could not open the audio device.",
  "Check the microphone/speaker is selected and not in use; on macOS allow microphone access.",
  r"PortAudioError", r"Error opening (?:Input|Output)?Stream", r"No Default (?:Input|Output) Device")
E("HW", 22, "OVERHEAT", WARN, "CPU/board is overheating and throttling.",
  "Improve cooling (heatsink/fan) and airflow.", r"thermal throttl", r"temperature above threshold")
E("HW", 23, "USB_POWER", ERROR, "USB port over-current / not enough power.",
  "Use a powered USB hub or the device's own power supply.", r"over-?current", r"not enough power",
  r"Power surge on the USB port")

E("EMB", 1, "ESPTOOL_CONNECT", ERROR, "esptool could not talk to the ESP chip.",
  "Hold BOOT while pressing RESET (or while it connects), use a data USB cable, and try -b 115200.",
  r"Failed to connect to ESP\d*", r"Wrong boot mode detected", r"No serial data received")
E("EMB", 2, "ESP_CHIP_MISMATCH", ERROR, "Firmware/flash command is for a different ESP chip.",
  "Pick the right board/chip (ESP32 vs -S3 vs -C3) in the build settings.",
  r"This chip is (?P<d>ESP32[\w\-]*) not", r"Wrong --chip argument")
E("EMB", 3, "ESP_BROWNOUT", ERROR, "ESP32 brown-out: the supply voltage dipped (often when Wi-Fi starts).",
  "Better USB cable/supply; add a 470-1000 uF capacitor near the board.", r"Brownout detector was triggered")
E("EMB", 4, "ESP_PANIC", FATAL, "ESP32 crashed (Guru Meditation / abort).",
  "Decode the backtrace (ESP Exception Decoder / idf.py monitor) to find the line.",
  r"Guru Meditation Error", r"abort\(\) was called at PC")
E("EMB", 5, "ESP_WDT", ERROR, "ESP32 watchdog fired - a task blocked too long.",
  "Avoid long loops without delay()/yield(); move slow work to its own task.",
  r"Task watchdog got triggered", r"task_wdt", r"Interrupt wdt timeout")
E("EMB", 6, "NO_FIRMWARE", ERROR, "No valid firmware on the board (flash empty or corrupt).",
  "Flash the firmware again (check the flash offset, e.g. 0x0 vs 0x1000 vs 0x10000).",
  r"invalid header: 0x[fF]{8}", r"flash read err")
E("EMB", 7, "FIRMWARE_TOO_BIG", ERROR, "Firmware is too big for the flash/partition.",
  "Choose a bigger partition scheme or disable features.",
  r"Sketch too big", r"text section exceeds available space", r"region `\w+' overflowed by",
  r"exceeds partition size")
E("EMB", 8, "DFU_NOT_FOUND", ERROR, "No board found in DFU/bootloader mode.",
  "Hold BOOT0 and press reset (or plug in while holding); data cable; Windows needs the WinUSB driver (Zadig).",
  r"No DFU capable USB device", r"dfu-util: No DFU")
E("EMB", 9, "DFU_FAILED", ERROR, "DFU firmware download failed.",
  "Retry with a short cable; check the flash address (e.g. 0x08000000 vs 0x08008000 with a bootloader).",
  r"Error during download", r"dfu-util: .{0,40}(?:error|failed)")
E("EMB", 10, "AVRDUDE_SYNC", ERROR, "avrdude cannot sync with the board's bootloader.",
  "Wrong board/port/bootloader; for clone Nanos choose 'ATmega328P (Old Bootloader)'.",
  r"stk500_getsync\(\)", r"avrdude: .{0,40}not in sync", r"programmer is not responding")
E("EMB", 11, "AVRDUDE_SIGNATURE", ERROR, "avrdude read a wrong/blank chip signature.",
  "Check wiring and the selected chip; the chip may be unpowered or damaged.",
  r"Device signature = 0x(?:000000|ffffff)", r"Invalid device signature")
E("EMB", 12, "RP2040_BOOTSEL", ERROR, "No RP2040/RP2350 board in BOOTSEL mode.",
  "Hold BOOTSEL while plugging in; a 'RPI-RP2' drive should appear.",
  r"No accessible RP2\w* devices in BOOTSEL mode", r"no RP2\w* devices")
E("EMB", 13, "KLIPPER_MCU_CONNECT", ERROR, "Klipper cannot connect to the printer board (MCU).",
  "Check serial: in printer.cfg (ls /dev/serial/by-id/) and that the board runs Klipper firmware.",
  r"mcu '(?P<d>\w+)': Unable to connect", over=("HW.SERIAL_OPEN",))
E("EMB", 14, "KLIPPER_SHUTDOWN", FATAL, "Klipper shut the printer down (MCU shutdown).",
  "Read the line after 'shutdown' - it gives the reason (heater, timer, ADC...).",
  r"MCU '(?P<d>\w+)' shutdown", generic=True)
E("EMB", 15, "KLIPPER_LOST_COMM", ERROR, "Klipper lost communication with a board.",
  "Check USB cable/power and grounding; avoid USB hubs; keep the cable away from stepper wires.",
  r"Lost communication with MCU '(?P<d>\w+)'")
E("EMB", 16, "KLIPPER_TIMER", ERROR, "Klipper 'Timer too close' - the host or board could not keep up.",
  "Reduce microsteps/speed, lower webcam load, or use a faster host.", r"Timer too close")
E("EMB", 17, "KLIPPER_PROTOCOL", ERROR, "Klipper firmware on the board does not match the host.",
  "Rebuild and reflash the board with the same Klipper version as the host.",
  r"MCU Protocol error", r"older version of the firmware on the MCU")
E("EMB", 18, "KLIPPER_CONFIG", ERROR, "printer.cfg has an error.",
  "Fix the section/option the detail names, then FIRMWARE_RESTART.",
  r"Section '(?P<d>[\w ]{1,40})' is not a valid config section",
  r"Option '(?P<d>\w+)' in section '[\w ]+' must be specified", r"Unknown pin chip name",
  r"pin \w+ used multiple times")
E("EMB", 19, "THERMISTOR_RANGE", ERROR, "Temperature sensor reading out of range (ADC out of range).",
  "Check the thermistor wiring/plug and sensor_type; a broken wire reads as very cold or very hot.",
  r"ADC out of range")
E("EMB", 20, "HEATER_NOT_HEATING", ERROR, "A heater is not heating at the expected rate (safety stop).",
  "Check the heater, thermistor placement and part-cooling fan; re-run PID tuning.",
  r"Heater (?P<d>\w+) not heating at expected rate", r"[Vv]erify_heater")
E("EMB", 21, "MOVE_OUT_OF_RANGE", ERROR, "A move went outside the printer's limits.",
  "Check position_min/max and the slicer's bed size/origin.", r"Move out of range")
E("EMB", 22, "NOT_HOMED", WARN, "The printer must be homed first.", "Home all axes (G28) before moving.",
  r"Must home axis first", r"Must home [XYZ]")
E("EMB", 23, "TMC_ERROR", ERROR, "A TMC stepper driver reported an error or did not answer.",
  "Check driver UART/SPI wiring, motor power (12/24 V on) and the driver's pins in the config.",
  r"TMC '(?P<d>[\w ]{1,30})' reports error", r"Unable to read tmc uart", r"tmc\w*: Unable to (?:read|write)")
E("EMB", 24, "PROBE_FAIL", ERROR, "Bed probe failed (triggered early or never).",
  "Check probe wiring and pin, z_offset and that the probe deploys.",
  r"Probe triggered prior to movement", r"No trigger on probe after full movement",
  r"BLTouch failed to verify sensor state")
E("EMB", 25, "MOONRAKER_KLIPPY", ERROR, "Moonraker cannot reach Klipper (klippy not connected).",
  "sudo systemctl restart klipper; check klippy.log for the real error.",
  r"[Kk]lippy (?:not connected|disconnected)", r"Moonraker can't connect to Klipper")
E("EMB", 26, "THERMAL_RUNAWAY", FATAL, "Thermal runaway / temperature fault - firmware stopped the printer.",
  "Check thermistor and heater wiring and fan ducts before printing again.",
  r"THERMAL RUNAWAY", r"Thermal Runaway", r"MAXTEMP", r"MINTEMP", r"Heating failed")
E("EMB", 27, "PRINTER_HALTED", FATAL, "Printer firmware halted (kill() called).",
  "Read the line before - it gives the reason - then power-cycle/reset.",
  r"Printer halted", r"kill\(\) called", r"Printer stopped due to errors", generic=True)
E("EMB", 28, "GCODE_UNKNOWN", WARN, "The firmware does not know a G-code command.",
  "Enable it in the firmware/config or remove it from the start G-code; the detail is the command.",
  r"Unknown command:? ['\"]?(?P<d>[GMT]\d+)", r"echo:Unknown command")

# --------------------------------------------------------------------------
# Lookup indexes + integrity checks (run at import so a bad edit fails fast)
# --------------------------------------------------------------------------
BY_KEY: Dict[str, Entry] = {}
BY_ID: Dict[Tuple[int, int], Entry] = {}
BY_CODE: Dict[int, Entry] = {}
for _e in ENTRIES:
    if not 0 <= _e.id < 100:
        raise ValueError("id out of range (must be 0-99): %s" % _e.key)
    for _p in _e.patterns:
        if _p.groups and "d" not in _p.groupindex:
            raise ValueError("%s: use (?:...) for groups; only (?P<d>...) may capture" % _e.key)
    if _e.key in BY_KEY or (_e.domain, _e.id) in BY_ID:
        raise ValueError("duplicate dictionary entry: %s / id %d" % (_e.key, _e.id))
    BY_KEY[_e.key] = _e
    BY_ID[(_e.domain, _e.id)] = _e
    BY_CODE[_e.code] = _e
for _e in ENTRIES:
    for _k in _e.supersedes:
        if _k not in BY_KEY:
            raise ValueError("%s supersedes unknown entry %s" % (_e.key, _k))
del _e, _p


def get(key: str) -> Entry:
    """Look up by 'DOMAIN.NAME', e.g. get('PY.TK_MISSING')."""
    return BY_KEY[key]


def lookup(domain: int, id_: int) -> Optional[Entry]:
    """Look up by numeric domain/id (what a decoded code gives you); None if unknown."""
    return BY_ID.get((domain, id_))


def by_code(code: int) -> Optional[Entry]:
    """Look up by 3-digit code (EC2), e.g. by_code(102); None if unknown."""
    return BY_CODE.get(code)


def define_app(id_: int, name: str, sev: int, msg: str, fix: str = "", *patterns: str) -> Entry:
    """Register one of YOUR program's own codes: 900 + id_ (id_ 0-99), key 'APP.<NAME>'.

    Call it at start-up, e.g. define_app(1, "NO_SCANNER", ERROR, "Scanner not detected", "Plug it in").
    Other machines decode the number and severity; the meaning lives in your program's docs.
    Re-defining the same id with the same name is allowed (re-imports); a different name is not.
    """
    if not 0 <= id_ < 100:
        raise ValueError("app code id must be 0-99 (codes 900-999)")
    name = name.upper()
    cur = BY_ID.get((9, id_))
    if cur is not None:
        if cur.name != name:
            raise ValueError("app code %d is already %s" % (900 + id_, cur.key))
        return cur
    if "APP." + name in BY_KEY:
        raise ValueError("app key APP.%s already used" % name)
    E("APP", id_, name, sev, msg, fix, *patterns)
    e = ENTRIES[-1]
    BY_KEY[e.key] = e
    BY_ID[(9, id_)] = e
    BY_CODE[e.code] = e
    return e
