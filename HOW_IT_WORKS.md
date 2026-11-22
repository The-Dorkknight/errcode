> **WORK IN PROGRESS** (`0.2.0-wip`)

# How ErrCode works

Plain English first, details after. Why the format looks the way it does is in [RESEARCH.md](RESEARCH.md).

## What it reads, changes, and never does

**It reads**
* Text you give it (a log, a traceback) via `errcode.scan()`, the command line, or the demo window.
* In a program that called `errcode.install()`: uncaught exceptions (main thread and worker threads) and
  `logging` records at WARNING and above.
* The output and exit code of commands you start through `errcode.run()`.
* For "Check this machine": the number of CPU cores, total RAM, the Python version, and whether the `segno` QR
  package is importable.

**It changes** (only after you call `install()`)
* Replaces `sys.excepthook` and `threading.excepthook` with wrappers that record the exception and then call the
  original hook, so your normal traceback still prints. `uninstall()` puts the originals back.
* Adds one logging handler to the root logger, and registers one `atexit` function.
* Prints a short footer to standard error (once per distinct set of codes). `ERRCODE_QUIET=1` turns that off.
* Writes a file **only** when you ask (`save_qr`, `--png`, `errcode export`, `errcode decoder`, *Save QR*).

**It never**
* Opens a network connection, sends anything anywhere, or phones home. There is no network code in the package.
  (A QR made with the *link* option contains a web address; the phone that scans it opens that page, and the
  report travels after the `#`, which browsers do not send to the server.)
* Modifies your files, settings or system.
* Raises an exception into your program: every hook swallows its own errors.

## 3-digit codes

Every dictionary entry has a fixed **3-digit code** = domain × 100 + id, grouped like HTTP status codes:

| Codes | Area | Codes | Area |
|---|---|---|---|
| `0xx` | general / portable OS (`000` = all ok) | `5xx` | macOS |
| `1xx` | Python | `6xx` | network |
| `2xx` | C / C++ native code and builds | `7xx` | hardware, GPU, USB, serial, cameras |
| `3xx` | Windows | `8xx` | embedded boards, firmware, 3D printers (ESP32, STM32, RP2040, Klipper, Marlin) |
| `4xx` | Linux | `9xx` | **your program's own codes** (`errcode.define_app`) |

The v0.1 entries kept their numbers: `PY.TK_MISSING` was domain 1, id 2, so it is `102`.
**Quick codes** put the severity letter in front, `O`/`W`/`E`/`F` (ok, warn, error, fatal): `E102 W706` is short
enough to read out on the phone, and `errcode decode E102 W706` looks it up.

## The EC2 report (what goes in the QR)

A report is one stream of bits, written out as digits in 20-digit blocks:

```
EC2-<block><block>...<last block>          one QR, one line of text
EC2/<i><n><set>-<blocks>                   part i of n (n <= 9) when it is split over several QRs
                                           set = 3 digits, so parts of different reports never mix
```

* **Block:** 19 data digits (one 63-bit chunk) plus 1 **Damm check digit**. The check catches every single wrong
  digit and every swap of two neighbouring digits, so the decoder can say "block 3 (digits 41-60) is wrong".
* **Last block:** only as many digits as the remaining bits need, plus its check digit.
* Spaces, dashes and line breaks are ignored when decoding; the CLI shows blocks as `12345 67890 12345 67890`.
* In the QR, `EC2-` is stored in alphanumeric mode and the digits in **numeric mode** (3 digits in 10 bits).

### The bit stream

`G` = exp-Golomb order 0, a variable-length number: 0 takes 1 bit, 1-2 take 3 bits, 3-6 take 5 bits, and so on.

```
header   revision:G   minute:25   session:15   flags:3 (app, stats, omitted)
         [app name: TEXT]   [lines:G noise:G repeats:G]   [omitted:G]
         event count:G
event    code:10 (000-999)   severity:2   count-1:G
         detail tag:2  ->  0 none | 1 number >= 0 (G) | 2 TEXT | 3 negative number (G of -n-1)
TEXT     symbol count:G, then 6-bit symbols:
         0 SHIFT (next letter upper case)   1 CAPS (toggle)   2 WORD + 8-bit index into words.py
         3 RAW + 8-bit byte   4-29 a-z   30-39 0-9   40-63  space . _ - / \ : , ; = + @ ( ) [ ] ' " ~ # % & ! ?
```

* `minute` = minutes since 2026-01-01 00:00 UTC (about 63 years of range). The viewer shows UTC and its own local
  time. A board without a clock sends 0.
* `revision` = the dictionary revision of the sender (2 for v0.2), so a decoder can warn when it is older.
* Every field says how long it is, so a decoder that does not know a code still reads the rest of the report.
* Padding bits at the end must be zero; anything else means parts from different reports were mixed.

### Fitting the space

`Report(budget=...)` sets the most digits a report may use (default **960** = one QR of version 15, 77×77
modules; `PAGE_BUDGET` = 4000 for a printed page). If the report is too big, long text details are first cut to
16 characters, then the lowest-priority events are left out and counted in `omitted`. A report longer than
`part_digits` (default 960) is split into up to 9 QR parts on block boundaries.

### Older formats

`EC1-...` strings and bare 4-character codes from v0.1 still decode (`errcode decode`, the HTML decoder and the
demo window), and `Report.payload_ec1` can still produce one. EC1 has no room for the new 8xx/9xx areas, counts or
details.

## From text to ranked codes

1. **Split and clean.** Lines are checked against noise patterns: percentages, progress bars, sizes and speeds
   (`3.1 MB/s`), ETA, package-manager chatter, routine INFO/DEBUG lines, bare timestamps, lines with no letters or
   digits. A line is kept regardless if it contains a failure word (`error`, `fail`, `denied`, `refused`,
   `timed out`, `not found`, ...). Noise is removed from the whole log first; only if a very large amount of real
   signal remains are the first 5,000 and last 15,000 lines kept.
2. **Collapse repeats.** Lines identical after replacing digits are counted once (with a count).
3. **Match.** One combined pattern quickly skips lines that match nothing; the rest are tested against every
   entry's patterns. A pattern may capture a **detail** with `(?P<d>...)`: the missing module, library, port,
   service, Klipper MCU name, exit status. Paths keep only their last part; details are cut to 40 characters.
   Exceptions are also matched by `errno` name and Windows `winerror` number (walking `__cause__`/`__context__`),
   with the file name or module name as the detail. Process exit codes map to entries; an unknown non-zero exit
   code becomes `043 GEN.EXIT_NONZERO` with the code as its detail.
4. **Cap severity.** A line starting `WARNING:`, or a `log.warning()` record, cannot rank above *warn*.
5. **Rank and prune.** Entries that another entry `supersedes` are removed (for example `LIN.LIBGL_MISSING`
   replaces `GEN.ENOENT` for `libGL.so.1: ... No such file or directory`). Wrapper entries marked `generic`
   (bare traceback, "build failed", "Klipper shutdown") are removed if a specific cause was found. `GEN.UNKNOWN` is
   removed if anything else was found. Ok/info entries are removed if anything at warn or above exists. What is
   left is sorted fatal, error, warn, ok; ties go to the earliest occurrence.
6. **Nothing found?** A clean log reports `000` (`GEN.OK`). A log with failure words but no match reports `001`
   `GEN.UNKNOWN`, with the first 40 characters of the first such line as its detail.

## The dictionary

All entries live in [`src/errcode/table.py`](src/errcode/table.py), one `E(...)` call each: domain, id, name,
severity, meaning, fix, then regular expressions. Import-time checks reject duplicate ids or names, ids of 100 or
more, capture groups other than `(?P<d>...)`, and unknown `supersedes` targets.

**Rules:** never renumber or reuse an id, and only append to the word list in
[`src/errcode/words.py`](src/errcode/words.py). A QR code saved today must decode the same way in ten years.

Your program's own codes go in `9xx`:

```python
errcode.define_app(1, "NO_SCANNER", errcode.table.ERROR, "Scanner not detected", "Plug it in and retry",
                   r"scanner (?:is )?missing")       # optional patterns
errcode.record("APP.NO_SCANNER")                     # -> code 901
```

Another computer decodes `901` as "app-defined code"; the meaning lives in your program's documentation.

## Using it from other languages

* **JavaScript:** `docs/decode.html` is a complete offline decoder (dictionary embedded). Rebuild it with
  `errcode decoder docs/decode.html` after changing the dictionary.
* **C / C++ / microcontrollers:** [`c/errcode_ec2.h`](c/errcode_ec2.h) is a single-header encoder with no malloc
  (see [`c/example.c`](c/example.c)). It writes the same `EC2-...` text, ready for a serial port, a small display
  or a QR library on the device.
* **Anything else:** `errcode export dictionary.json` writes every entry, the word list and the format version.
