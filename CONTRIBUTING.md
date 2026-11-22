# Contributing

Thanks for helping. By contributing you agree your contribution is licensed under the same
[PolyForm Noncommercial License 1.0.0](LICENSE.md) as the rest of the project.

## The most useful contribution: a dictionary entry

Entries live in `src/errcode/table.py`. Add one `E(...)` line at the end of the right domain:

```python
E("WIN", 48, "EXAMPLE_NAME", ERROR, "What went wrong, in plain words.",
  "What to do about it.",
  r"regex that recognises the message", r"thing (?P<d>[\w.]+) is missing")
```

Its 3-digit code is area × 100 + id (`WIN` is area 3, so this is `348`).

Rules:

1. **Never renumber or reuse an id.** Use the next free number in that area (gaps are fine). Ids must be below 100.
2. Use `(?:...)` for groups. Only one named group, `(?P<d>...)`, may capture: it becomes the event's detail.
3. Bump `REVISION` in `table.py` when you add entries, and rebuild the decoder page:
   `python -m errcode decoder docs/decode.html`.
4. Every warn/error/fatal entry needs a fix hint. Say what you verified; hedge what you did not.
5. Use `generic=True` for wrapper/symptom messages (for example "build failed") so a specific cause outranks them.
6. Use `over=("DOMAIN.NAME",)` if your entry is a more specific form of another one.
7. Add a test (a sample line and the key it should produce) in `tests/test_errcode.py`.
8. `src/errcode/words.py` (the word list for details) is **append only**, at most 256 words.

## Running the tests

```
python -m unittest discover -s tests -v
```

Tests that need the optional `segno` package skip themselves if it is not installed.

## Style

Standard library only for the core package. Keep it light enough for old hardware (a 7th-generation Core i3-class
machine): no GPU requirements, no heavy dependencies. Every source file carries the licence header.

## Reporting problems

Use the bug-report form (it asks for version, platform and the report string). For security issues see
[SECURITY.md](SECURITY.md).
