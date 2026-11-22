# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Shared word list for the EC2 text coder (details such as a module name, a
library file or an unrecognised log line).

A word in this list costs 14 bits (escape symbol + 8-bit index) instead of
6 bits per character, so "No module named" (15 chars, 90 bits) becomes 14 bits.

RULES (exactly like the dictionary ids):
  * APPEND ONLY. Never reorder, edit or delete a word - old reports would decode wrongly.
  * At most 256 words (8-bit index). Matching is case-sensitive.
  * Only words of 3+ characters are worth it.
"""
WORDS = (
    # 0-49: log vocabulary
    "error", "Error", "ERROR", "failed", "Failed", "cannot", "Cannot", "can't", "could not", "Could not",
    "unable to", "Unable to", "not found", "No such file or directory", "Permission denied", "timed out",
    "Connection", "connection", "refused", "No module named", "module", "device", "Device", "file", "File",
    "open", "invalid", "Invalid", "missing", "version", "required", "requires", "expected", "unexpected",
    "already", "exists", "access", "denied", "memory", "allocation", "received", "response", "server",
    "socket", "timeout", "Traceback", "Exception", "exception", "line ", "the ",
    # 50-89: Python
    "ImportError", "ValueError", "TypeError", "KeyError", "RuntimeError", "OSError", "AttributeError",
    "has no attribute", "object", "'NoneType' object", "argument", "positional", "keyword", "unsupported",
    "index out of range", "division by zero", "utf-8", "codec", "import", "from ", "self", "def ",
    "numpy", "scipy", "cv2", "PIL", "tkinter", "_tkinter", "serial", "pyserial", "PyQt5", "PyQt6",
    "PySide6", "matplotlib", "pandas", "requests", "urllib3", "yaml", "segno", "esptool",
    # 90-119: more packages
    "open3d", "trimesh", "cadquery", "OCP", "pyrealsense2", "torch", "onnxruntime", "pyopencl", "pycuda",
    "setuptools", "wheel", "pip", "distutils", "bleak", "sounddevice", "pyaudio", "websocket", "aiohttp",
    "asyncio", "psutil", "zeroconf", "FreeCAD", "bpy", "shapely", "OpenGL", "pygame", "flask", "pyusb",
    "usb.core", "moonraker",
    # 120-159: native libraries and files
    "libGL.so.1", "libEGL.so.1", "libgthread-2.0.so.0", "libxcb-cursor.so.0", "libstdc++.so.6",
    "libusb-1.0", "libfuse.so.2", "libvulkan.so.1", "libpython3", "VCRUNTIME140.dll", "VCRUNTIME140_1.dll",
    "MSVCP140.dll", "api-ms-win-crt-", "python3", ".dll", ".so", ".dylib", ".exe", ".py", ".cfg", ".json",
    ".stl", ".step", ".gcode", ".txt", ".log", ".bin", ".hex", ".uf2", "site-packages", "/usr/lib/",
    "/usr/local/", "/home/", "C:\\Users\\", "Program Files", "AppData", "/dev/ttyUSB", "/dev/ttyACM",
    "/dev/serial/by-id/", "COM",
    # 160-219: devices, firmware, printers, network
    "USB", "usb", "ESP32", "ESP32-S3", "ESP32-C3", "STM32", "RP2040", "Pico", "Raspberry Pi", "firmware",
    "bootloader", "flash", "upload", "printer", "printer.cfg", "extruder", "heater_bed", "heater",
    "thermistor", "stepper_", "probe", "homing", "endstop", "klipper", "Klipper", "mcu", "http://",
    "https://", "localhost", "127.0.0.1", "192.168.", ".local", "HTTP", "json", "config", "setting",
    "value", "path", "directory", "folder", "install", "installed", "package", "update", "download",
    "network", "WiFi", "display", "window", "camera", "image", "frame", "video", "audio", "thread",
    "process", "running",
    # 220-255: status words
    "return", "returned", "status", "code", "exit", "killed", "signal", "Segmentation fault",
    "core dumped", "GPU", "CUDA", "OpenCL", "Vulkan", "driver", "support", "supported", "available",
    "unavailable", "disabled", "enabled", "started", "stopped", "warning", "Warning", "WARNING", "fatal",
    "Fatal", "FATAL", "while ", "during ", "after ", "before ", "with ", "for ", "and ", "not ",
)

if len(WORDS) > 256:
    raise ValueError("word list is limited to 256 entries (8-bit index), has %d" % len(WORDS))
if len(set(WORDS)) != len(WORDS):
    raise ValueError("duplicate word in the EC2 word list")
if any(len(w) < 3 for w in WORDS):
    raise ValueError("EC2 words must be at least 3 characters")
