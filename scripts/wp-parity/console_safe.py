"""Make stdout safe to print non-ASCII on a default Windows console.

A gate that crashes while printing its own result is the worst outcome there
is: the crash is caught by whatever launched it, the exit code is read as a
pass or a zero, and the run reports green. That happened here — a negative test
printed a Persian string from a failure message, `UnicodeEncodeError` killed it
at the `print`, and the process still exited 0. A gate whose failure is
invisible is not a gate.

Importing this module once at the top of any script that prints Persian, Arabic,
or any other non-ASCII makes the console codec incapable of failing the run:
characters it cannot represent become `?` instead of an exception. The test
result is still correct — only the glyph is lost.

The alternative is `PYTHONIOENCODING=utf-8` in every invocation, which works
and is easy to forget in exactly the one place it matters: someone running a
single file by hand, or a CI step that runs one test rather than the suite.
"""

from __future__ import annotations

import io
import sys


def make_stdout_safe() -> None:
    """Re-wrap stdout and stderr so no character can raise.

    Idempotent — importing this from a script that already wraps its own
    stdout is fine, and so is importing it twice.
    """
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        # Already safe (reconfigured or wrapped): leave it alone, so a script
        # that chose a different encoding keeps it.
        encoding = (getattr(stream, "encoding", "") or "").lower()
        if "utf" in encoding:
            continue
        buffer = getattr(stream, "buffer", None)
        if buffer is None:
            # Captured to a StringIO (pytest, a test harness): already a str
            # sink, nothing to do.
            continue
        setattr(
            sys, name,
            io.TextIOWrapper(buffer, encoding="utf-8", errors="replace",
                             line_buffering=True),
        )


make_stdout_safe()
