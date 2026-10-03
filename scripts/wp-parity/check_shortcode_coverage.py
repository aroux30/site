"""Every WordPress media shortcode exists, and none of them runs a script.

Two halves, and the second is the one that decides whether the first is a
feature or a hole.

**Coverage.** `caption`, `audio`, `video` and `playlist` were absent: an author
who pasted `[video]` got the literal text on the page. That reads as a broken
site, and the fix is a decorator — so it is checked by rendering, not by
grepping for the name.

**Safety.** These run on content a marketing author typed, and three of them
reach a URL that lands in a `src`. `javascript:` and `data:` there run in the
page's origin, which makes a shortcode a script injection vector. The refusal is
a allow-list of schemes rather than a block-list, because the block-list is
where a new scheme goes to hide.

The refusal is also checked against what must *keep* working: a control that
also blocks `/media/…` is an outage wearing a security badge.

Run:  python scripts/wp-parity/check_shortcode_coverage.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

#: WordPress's ten media shortcodes. The six that already existed are listed
#: too: a refactor that drops one is as silent as one that forgets to add.
EXPECTED = {
    "gallery", "youtube", "aparat", "button", "alert", "embed",
    "caption", "audio", "video", "playlist",
}

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {label}: {ok}")
    if not ok:
        failures.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    import app.main  # noqa: F401 — registers every model, which is the point
    from app.shared.content import shortcodes as sc

    registered = set(sc._HANDLERS)
    print(f"  registered shortcodes: {len(registered)}")

    missing = sorted(EXPECTED - registered)
    check("every WordPress media shortcode is registered", not missing,
          "; ".join(missing))

    render = sc.process_shortcodes

    # Each one actually produces its element, rather than a name being present.
    cases = [
        ("caption", "[caption align='center']ز[/caption]", "<figure"),
        ("audio", "[audio src='/media/a.mp3']", "<audio"),
        ("video", "[video src='/media/v.mp4']", "<video"),
        ("playlist", "[playlist ids='1,2']", "<ol>"),
    ]
    for name, source, needle in cases:
        check(f"{name} renders", needle in render(source),
              render(source)[:80])

    # caption's body is the image the author pasted; escaping it would show
    # the markup instead of the picture.
    out = render("[caption]<img src='/media/a.jpg' />[/caption]")
    check("caption's body stays HTML", "<img" in out, out[:80])

    # A source that would run script is refused, and renders as nothing so the
    # author sees the shortcode produced no output rather than a blocked
    # request they will chase.
    for hostile in ("javascript:alert(1)",
                    "data:text/html,<script>alert(1)</script>",
                    "vbscript:msgbox(1)", "JAVASCRIPT:alert(1)"):
        for tag in ("video", "audio"):
            out = render(f'[{tag} src="{hostile}"]')
            check(f"{tag} refuses {hostile[:22]}", out == "", out[:60])

    # and the ordinary cases keep working
    for good in ("/media/a.mp3", "https://cdn.example/a.mp3", "/uploads/a.mp3"):
        out = render(f'[audio src="{good}"]')
        check(f"allowed: {good[:28]}", "<audio" in out, out[:60])

    # A hostile value in a caption attribute is escaped rather than injected.
    out = render("[caption align='x\" onerror=\"alert(1)']z[/caption]")
    check("a caption attribute cannot inject an event handler",
          "onerror=" not in out, out[:120])

    # A malformed shortcode is left as text: an author who typed `[video src=`
    # has to see what they typed, not an empty box.
    check("a malformed shortcode is left visible",
          "video" in render("[video src="), render("[video src=")[:60])

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("\nPASS: all ten WordPress media shortcodes render, and none of "
          "them will execute a source an author pasted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())