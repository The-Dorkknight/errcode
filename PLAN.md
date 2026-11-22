> **WORK IN PROGRESS** (`0.2.0-wip`). Plan and to-do list, newest first. Ticked items are done in this repository.

# ErrCode plan

## Where it stands (2026-11-02)

* [x] 3-digit codes (`0xx`-`9xx`), quick codes (`E102 W706`), 287-entry dictionary incl. embedded/3D-printer area `8xx`
* [x] EC2 digit reports: details, counts, app name, log statistics, time; 20-digit blocks with Damm check digits
* [x] Budgets (one QR by default, `--page` for about a page), multi-part QR codes (up to 9, any order)
* [x] Offline HTML decoder with code book; QR can link straight to it
* [x] Single-header C encoder for firmware
* [x] `define_app()` for each program's own `9xx` codes
* [x] Research write-up with measurements ([RESEARCH.md](RESEARCH.md))
* [ ] **Not yet used by any other project.** That is the next job, below.

## Next: roll it into the other projects

The cheapest route for each kind of project. Each is a small, separate change in that project's own repository.

| Kind of project | Examples | What to add |
|---|---|---|
| Python GUI / tool | STL2STEP / Twoo STEP CAD Toolbox, SlicerSwap, Scantastic, Pico Quarantine, This PC for Linux | the `errcode @ git+...` line in `requirements.txt`, the guarded `install(app=...)` at start-up, `record("HW.GPU_FALLBACK")` where the CPU path is chosen |
| Slicer / CAD plug-ins (run inside Cura, FreeCAD, Blender) | Shift-LoK, FlatLoK, Cura Hybrid Supports, SimpleCAD, SimpleMesh | do **not** hook the host's global exception handler; use `errcode.scan()` on the plug-in's own log, or `Collector()` objects, and show `rep.quick` in the plug-in's error dialog |
| Klipper / Pi hosts | GadgetDesk, SkiPiPir, KlipperTFT-Pico host side | `python -m errcode scan ~/printer_data/logs/klippy.log --link` for a phone-scannable status; the `8xx` entries cover the common klippy errors |
| ESP32 / RP2040 / STM32 firmware | esp-printhost (Skipper Flipper), SquawkBox, SpaghettiCam, Angry Putty / Putty Probe, caliper logger | copy `c/errcode_ec2.h`; print the `EC2-...` line on boot faults and on serial command `?err`; show it as a QR on boards with a display |
| Flashing / recovery tools | OctoRevive, ClonePLC Flasher, FYSETC E4 Klipper | run esptool / dfu-util / avrdude through `errcode.run([...])`, which maps their errors to `801`-`812` |

* [ ] Add the guarded install to the project bootstrap template (`project_bootstrap.py`), uncommented, so every
      new project has it from day one
* [ ] Pick one Python app and one firmware project as first adopters; note what the dictionary missed
* [ ] Switch on GitHub Pages for this repository so `--link` QR codes open the decoder

## Later

* [ ] Build and run `c/example.c` on a real ESP32-S3 and an RP2040 (size, speed); add an on-device QR example
* [ ] Test on real Windows 11, macOS (Apple Silicon), a Raspberry Pi and an old Core i3; fix what breaks
* [ ] Run the GitHub Actions workflows and fix any platform-specific failures
* [ ] Reproduce the most common dictionary entries on real machines; correct messages and fixes
* [ ] Python decoder for MicroPython? (only if a project needs to decode on-device)
* [ ] Frequency-based (Huffman) code packing, only if real reports turn out to be routinely too big
* [ ] Optional: look up a full log by session number (needs a server; out of scope for now)
