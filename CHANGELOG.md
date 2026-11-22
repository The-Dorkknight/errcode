# Changelog

All notable changes are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.3-wip] - 2026-11-22
- The front page of the TK 4K window now opens on a sample QR carrying the most one QR can hold: a real, decodable report of 5,575 of the 5,584 digits (172 codes, QR version 40, 177 x 177 modules). "Biggest sample QR" brings it back.
- New Import QR and Export QR files buttons. Export writes each QR part as PNG and SVG plus report.txt into an `errcode-export-<time>/` folder; the report text is embedded in the PNG and SVG, so ErrCode's own exports import back exactly. Import reads those, a plain text file, or (if OpenCV is installed) a photo/screenshot of any ErrCode QR. Multi-part reports can be imported one part at a time, in any order.
- New module `errcode.qrio`; tests in `tests/test_qrio.py`. Not tested on Windows, macOS or a real phone camera; a 177 x 177 QR on screen is dense, so scan the exported PNG at full size.

## [0.3.2-wip] - 2026-11-22
- Checked against TK 4K 0.5.6: all tests pass (98 passed, 1 skipped because OpenCV is not installed for the QR read-back test), run headless on Python 3.13.
- Vendored TK 4K 0.5.6 wheel (0.4.0 kept as the previous build). The README's first page now says the window is built with experimental TK 4K, and the TK 4K paper (PDF) is included in `docs/`.

## [0.3.1-wip] - 2026-11-22
- Vendored TK 4K 0.4.0 wheel. "Open file" with an empty path now opens TK 4K's in-app file chooser.

## [0.3.0-wip] - 2026-11-22
### Added
- **The window is now built with TK 4K** (`errcode/gui_tk4k.py`): log box, sample drop-down, coloured ranked table, detail,
  QR drawn natively, multi-part navigation, time bar, quick codes, copy, save, decode. "UI: TK 4K" is in the title bar,
  the header and the README. `errcode/launch.py` starts it and falls back to the tkinter window.
- `vendor/` holds the TK 4K 0.3.0 wheel (Linux x86-64); `run.sh`/`run.bat` try it first.
- 14 tests (`tests/test_gui_tk4k.py`), run headless, including mouse/keyboard clicks and a QR read back off the rendered screen.
### Known limits
- No file dialogs (typed path instead); block characters show as `?`; not tested on Windows or macOS.

### Added
- Nothing yet.

### Changed
- Nothing yet.

## [0.2.0-wip] - 2026-11-02

Multiplexing rework: 3-digit codes and all-digit reports.

### Added
- **3-digit codes** (`code = area * 100 + id`): `0xx` general ... `7xx` hardware, new `8xx` embedded boards,
  firmware and 3D printers, and `9xx` for each program's own codes (`errcode.define_app`). v0.1 entries keep
  their numbers (`PY.TK_MISSING` = `102`). **Quick codes** with a severity letter: `E102 W706`.
- **EC2 report format**: one bit stream written as digits in 20-digit blocks, each with a Damm check digit that
  catches any single wrong digit or swapped neighbours and names the block to re-read. Carries the time, a session
  number, the app name, log statistics, and per event its code, severity, count and **detail**.
- **Details**: patterns can capture the missing module, library, port, service, MCU name or exit code; exceptions
  add the module or file name; unknown exit codes become `043` with the code.
- Shared, append-only word list (`words.py`) for compact text details.
- Budgets: one QR by default (960 digits, QR version 15), `--page` for about 4,000 digits; reports split into up to
  9 QR parts that can be scanned in any order. QR codes use numeric mode for the digits.
- Optional QR link to the decoder web page (`--link`, `link=True`).
- Offline HTML decoder `docs/decode.html` with a searchable code book (`errcode decoder`).
- Single-header C encoder `c/errcode_ec2.h` with an example.
- 155 new dictionary entries (287 in total, 680 patterns), including ESP32/esptool, STM32 DFU, avrdude, RP2040,
  Klipper and Marlin errors, more Python exceptions, Windows device and status codes, Linux serial-port problems.
- `errcode bench` (raw vs zlib vs EC2 sizes), `RESEARCH.md`, `PLAN.md`, `tools/check_decoder_js.py`.
- 28 new tests (79 in total).

### Changed
- `Report.payload` is now the EC2 string; `Report.codes` are 3-digit codes. The old string is `Report.payload_ec1`.
- The plug-in footer starts with the quick codes, then the EC2 string.
- `errcode.record()` accepts `detail=`; `scan()` and `report()` accept Report options such as `budget` and `app`.
- Demo window: quick codes, details, QR parts, page-sized option, decoder-link option.
- Dictionary ids must now be below 100 per area (all v0.1 ids already were).

### Kept
- EC1 strings and 4-character codes still decode everywhere.

## [0.1.0-wip] - 2026-10-02

First work-in-progress release (proof of concept).

### Added
- 4-character, 20-bit error codes (domain, severity, entry id, check digit) and a multiplexed `EC1-...` report
  string with a minute-resolution UTC time stamp and a session tag. The demo window shows a time and date bar above the QR.
- 132-entry dictionary across General/portable OS, Python, C/C++, Windows, Linux, macOS, Network and
  Hardware/GPU, with errno, WinError and process exit-code mapping.
- Noise filter (progress, percentages, downloads, routine INFO), repeat collapsing, and worst-first ranking.
- `errcode.install()` plugin: uncaught exceptions, worker threads, logging, atexit footer; `record()`, `run()`,
  `scan()`, `decode()`, `report()`.
- Command line: `scan`, `decode`, `list`, `export`, `gui`, `--version`.
- Optional QR output (PNG/SVG/terminal) through the pure-Python `segno` package.
- Demo tkinter window with samples, decode box, machine check and QR display.
- 48 automated tests; one-step launchers `run.sh` / `run.bat`.

### Changed
- Nothing (first release).
