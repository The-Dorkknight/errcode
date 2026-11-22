# Third-party notices

The [PolyForm Noncommercial License](LICENSE.md) covers only Matthew Armstrong's own code in this repository.
Everything below keeps its own licence and belongs to its authors. No affiliation with, or endorsement by, any of
them is stated or implied.

| Component | Used for | Licence | Where |
|---|---|---|---|
| [segno](https://github.com/heuer/segno) (Python QR code generator) | Optional QR image output | BSD licence (see the project's own licence file) | Installed from PyPI via `requirements.txt`; not bundled in this repository |
| Python standard library, including tkinter / Tcl/Tk | Everything; demo window | Python Software Foundation licence; Tcl/Tk licence | Comes with your Python |
| [Crockford base32](https://www.crockford.com/base32.html) | The alphabet and `O`/`I`/`L` folding convention only | Specification; no code taken | `src/errcode/codec.py` is an independent implementation |
| GitHub Actions `checkout`, `setup-python` | CI workflows | MIT (see their repositories) | `.github/workflows/` |
| Damm check-digit algorithm (H. Michael Damm, 2004) | Check digit of each 20-digit block | Published algorithm; the operation table is the one given in the Wikipedia article on the algorithm, from Damm's dissertation | `src/errcode/ec2.py`, `c/errcode_ec2.h`, `docs/decode.html` (independent implementations) |
| [IBM Plex Sans / IBM Plex Mono](https://github.com/IBM/plex) | Typeface of the decoder page | SIL Open Font License 1.1 | Loaded from Google Fonts when online; not bundled. The page falls back to system fonts offline |
| SMART Health Cards numeric QR encoding, RFC 9285 (Base45), CLP log compression | Ideas only (see RESEARCH.md) | Specifications / paper; no code taken | — |

**Trademarks.** "QR Code" is a registered trademark of DENSO WAVE INCORPORATED. Python, Windows, macOS, Linux,
GitHub and other names mentioned in the dictionary messages belong to their respective owners; they are used only
to describe the error messages those systems produce.

**Dictionary content.** The error descriptions and suggested fixes were written for this project from general
knowledge of common failures. Where they quote an error message fragment (for example `Library not loaded`) it is
only to recognise that message.
