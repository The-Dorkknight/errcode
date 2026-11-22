# Security policy

## Reporting a vulnerability

Please report security problems **privately**: on the repository page choose **Security > Report a vulnerability**
(GitHub private vulnerability reporting). Please do not open a public issue for a security problem.

This is a one-person, work-in-progress project: there is no service-level promise, but reports are welcome and will
be read.

## Scope notes

* ErrCode contains no network code and sends nothing anywhere.
* It hooks `sys.excepthook`, `threading.excepthook` and the root logger **only** after you call
  `errcode.install()`; it writes image files only when you ask.
* An EC2 report contains codes, counts, a UTC time stamp (to the minute), a random session number, the app name
  you gave, log line counts, and short **details**: for example a module or library name, a port such as
  `/dev/ttyUSB0` or `COM3`, an exit code, the last part of a file path, or the first 40 characters of an
  unrecognised error line. Captured paths are cut to their last part, but the unrecognised-line detail is raw
  log text and can contain a path, a user name or other text from your log. Look at the decoded report
  (`errcode decode ...`) before sharing a QR code publicly.
  Check the original log yourself before sharing it elsewhere.
* The Damm check digits (EC2) and the 3-bit check (EC1) are typo guards, not integrity or authenticity mechanisms.
