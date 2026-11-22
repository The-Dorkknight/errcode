> **WORK IN PROGRESS** (`0.2.0-wip`). Research notes behind the EC2 format. Figures marked *measured* were produced
> in this repository with `errcode bench` and the scripts named below, on a Linux sandbox (not on real hardware).

# Research notes: how to fit the most error information on a page or in a QR code

**The question (November 2026):** ErrCode v0.1 put up to 12 four-character codes into one QR string. The aim for
v0.2 was: as many common errors as possible as quick **3-digit lookup codes**, their details multiplexed into
**20-digit blocks**, and the best value-for-effort way to get as much data as possible into a page of text.

**Short answer.** The biggest gain is not clever bit-packing; it is **not sending the log at all**. Send a
dictionary number for the *kind* of message and only the few variable parts (a module name, a port, an exit
code). That is the same idea the research system CLP uses to compress logs. Then pack it all as **digits**: inside
a QR code digits cost the same as letters or bytes, and outside a QR code anyone can read, type or text them.
Add a check digit per 20-digit block so a mistyped block is found and named.

---

## 1. Inside a QR code, digits are free

A QR code has three useful text modes. Each packs characters into bits differently:

| Mode | Characters | Packing | Bits per character |
|---|---|---|---|
| Numeric | `0-9` | 3 digits in 10 bits | 3.33 |
| Alphanumeric | `0-9 A-Z space $%*+-./:` (45) | 2 characters in 11 bits | 5.5 |
| Byte | anything | 8 bits each | 8 |

*Measured* with `segno` at error level M, version 40 (the biggest symbol): 5,596 digits, 3,391 alphanumeric
characters, or 2,331 bytes. Converted to information, that is 5,596 × log₂10 ≈ **18,590 bits**,
3,391 × log₂45 ≈ **18,620 bits** and 2,331 × 8 = **18,650 bits**. The three modes hold the same information to
within 0.3 %.

So the encoding inside the QR can be chosen for the humans around it. Digits win there: they can be read over the
phone, typed on any keypad, sent by SMS or written down, in any language, with no confusion between `O` and `0`.

Others reached the same conclusion:

* **SMART Health Cards** (US vaccination QR codes) put their data in a **numeric** segment, two digits per
  character: "with Numeric Mode, 20% more data can fit in a given QR, vs Binary Mode." The specification keeps
  codes at **version 22 (105×105 modules)** so they work printed at 40 mm × 40 mm. Their multi-QR "chunking" was
  later deprecated because readers did not adopt it. [SMART Health Cards spec]
* **Base45** (RFC 9285, used by the EU Digital COVID Certificate) does the same job for alphanumeric mode:
  2 bytes in 3 characters, using exactly the 45 characters alphanumeric mode allows. [RFC 9285]

**Mixed segments.** One QR symbol can switch modes part-way. ErrCode puts the short `EC2-` header in
alphanumeric mode and the digits in numeric mode. *Measured:* 300 digits alone need version 8; with `EC2-` in
front, still version 8; with a full `https://...` link in byte mode in front, version 9. So a QR that **opens the
decoder web page directly** costs about one size step.

## 2. Semantic compression beats general compression

General-purpose compressors (zlib, zstd, brotli) are poor at small inputs: there is little repetition to find,
and they have fixed overheads. Logs, however, are mostly fixed text with a few variables. The CLP system
(OSDI 2021) splits each log message into a **log type** (the static template), **dictionary variables** and
**encoded variables**, and reports an average compression ratio of 32, about twice gzip. [CLP paper]

ErrCode's dictionary is a hand-made, very small version of the same split:

| CLP | ErrCode |
|---|---|
| log type (template) | 3-digit code (`101` = "No module named …") |
| dictionary / encoded variables | the **detail** (`pyrealsense2`), a number or short text |
| repeated messages | one code with a **count** |

*Measured* (`errcode bench`, sizes in bytes, EC2 in digits):

| Log | Lines | Raw | zlib -9 | Noise removed + zlib | + preset dictionary | **EC2** |
|---|---:|---:|---:|---:|---:|---:|
| pip install fails (noisy) | 17 | 1,108 | 410 | 217 | 160 | **31 digits** |
| Linux: tkinter missing | 5 | 189 | 152 | 126 | 89 | **25 digits** |
| Windows: missing C++ runtime | 6 | 335 | 226 | 224 | 142 | **39 digits** |
| Synthetic 20,000-line install/build log | 20,000 | 1,022,192 | 110,970 | 380 | 243 | **108 digits** |

For a sense of scale, 108 digits is about 43 bytes of information. The 1 MB log becomes a **33×33 QR code**
(version 4), and its eight ranked codes still carry the details that matter (`[pyrealsense2]`, `[libGL.so.1]`,
`[mcu]`, `[extruder]`). The ordering matters too: **noise removal does most of the work** (111 KB → 380 B), and
the dictionary does the rest.

What this throws away: the exact wording, line numbers and anything the dictionary does not know. An unknown
error line still travels, as text in the `GEN.UNKNOWN` detail (first 40 characters) when nothing known was
found. Keep the original log for serious problems.

## 3. Packing the numbers

| Technique | Where it is used | Why |
|---|---|---|
| Fixed 10-bit code field | each event | 1,000 codes; 1000-1023 are reserved for a future extension |
| **exp-Golomb** variable-length integers | counts, details, header numbers | small numbers dominate: a count of 1 costs 1 bit, 2-3 cost 3 bits, a 32-bit Windows status about 65 |
| Shared **word list** (256 entries, append-only) | text details | a known word costs 14 bits instead of 6 per letter: `No module named` goes from 90 to 14 bits |
| 6-bit symbol alphabet with SHIFT / CAPS | text details | lower-case paths and module names are the common case |
| Severity stored with each event | each event | a reader with an older dictionary can still rank a code it does not know |
| 25-bit minute time stamp | header | minutes since 2026-01-01 UTC, good for about 63 years |

*Measured costs:* an event with no detail is **15 bits** (about 4.8 digits). With a module or library name from
the word list, or a short name such as `mcu`, it is **32 bits**. Exit code 139 is 30 bits. The header is
47 bits, plus the app name and log statistics if present. For comparison, v0.1 spent 20 bits per code with no
count and no detail.

## 4. Digits that survive people: 20-digit blocks with a Damm check digit

Each block is 19 data digits (one 63-bit chunk, since 2⁶³ < 10¹⁹) plus 1 check digit. The **Damm algorithm**
"detects all single-digit errors and all adjacent transposition errors" [Damm algorithm]. That covers the two
mistakes people make most when reading or typing digits. Because every block has its own check, the decoder
can say **which** block to re-read ("block 3, digits 41-60"). The test suite checks every single-digit error and
every neighbour swap on 200 random blocks.

The check digit costs 5 % of capacity (63 bits in 20 digits, against 66 bits possible). Inside a QR code it is
redundant, because QR already has Reed-Solomon error correction. Outside a QR code, it is what makes digits safe
to read aloud.

The last block is shorter: it uses the fewest digits that can hold the remaining bits (`cap(k)` = the largest
b with 2ᵇ ≤ 10ᵏ), plus its check digit.

## 5. How much fits: a QR, several QRs, a page

| Container | Digits | What fits (measured) |
|---|---:|---|
| Small QR, version 2 (25×25) | about 40 | a typical failure report: 1-3 codes with details |
| Default report, 960 digits = one QR of version 15 (77×77) | 960 | **196 events** without details (957 digits) |
| Printed page: about 4,000 digits in 5-digit groups | 4,000 | 200 events (the hard cap) with short details in 2,673 digits; or 144 events with 14-character text details in 3,996 digits, as 5 QR parts |
| SMART Health Card size, version 22 (105×105) | 1,872 | for comparison only |

*Measured:* the 200-event report split into 3 parts (QR versions 15, 15 and 13). OpenCV and ZXing both read
every generated test symbol back exactly (15 of 15), including those parts.

**Multi-part QR codes.** The QR standard has "structured append" for up to 16 linked symbols, but phone camera
apps generally ignore it. SMART Health Cards' own chunking was deprecated for lack of adoption. ErrCode therefore
writes a short, readable part tag into each QR's text instead (`EC2/<part><of><set>-…`, up to 9 parts). Any QR
reader shows it, and the decoder accepts the parts in any order and names the missing ones.

## 6. Options considered and not used (yet)

| Option | Why not now |
|---|---|
| zlib/zstd/brotli with a trained dictionary | needs the same library and dictionary file at both ends; poor on tiny inputs; hard on microcontrollers. *Measured:* a preset dictionary helped zlib, but stayed 3-6× larger than EC2 |
| Huffman or arithmetic coding of codes by frequency | saves a few bits per event; makes the JavaScript and C decoders much harder |
| Animated QR / fountain codes (many frames) | for megabytes, not for error reports; needs a special app |
| Base45 or alphanumeric payloads | same density inside the QR, but letters are worse to read aloud or type |
| A server to look up the full log by session id | the session tag is in every report, so it remains possible later; no network code today |

## 7. Implementation checks done

* Python encoder and decoder: 300 random reports round-trip, also when split into parts and shuffled
  (`tests/test_ec2.py`).
* **JavaScript decoder** (`docs/decode.html`): 300 random reports decoded identically to Python, in Chromium
  (`tools/check_decoder_js.py`). A one-digit error is caught and the block is named.
* **C encoder** (`c/errcode_ec2.h`): builds cleanly as C99 (`-Wall -Wextra -pedantic`) and as C++; its output
  decodes in Python (also a unit test). The example program is about 6 KB on x86-64 Linux. It has **not** been
  built for an ESP32, RP2040 or STM32 yet.
* QR images: generated with `segno`, read back exactly by OpenCV and by ZXing (15 of 15 symbols).

## Sources

* [SMART Health Cards Framework, "Encoding Chunks as QR codes"](https://spec.smarthealth.cards/) (numeric mode,
  version 22 at 40 mm, chunking deprecated)
* [RFC 9285, The Base45 Data Encoding](https://www.rfc-editor.org/rfc/rfc9285.html)
* [Damm algorithm, Wikipedia](https://en.wikipedia.org/wiki/Damm_algorithm) (error-detection properties; the
  operation table used here is the one given there, from Damm's 2004 dissertation)
* [Rodrigues et al., "CLP: Efficient and Scalable Search on Compressed Text Logs", OSDI 2021](https://www.usenix.org/system/files/osdi21-rodrigues.pdf)
* [Thonky QR Code Tutorial, data encoding](https://www.thonky.com/qr-code-tutorial/data-encoding) (mode bit layout)
* QR capacities: measured with [segno](https://github.com/heuer/segno) 1.6.6, not copied from a table
