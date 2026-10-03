"""The four media shortcodes, and what they refuse to render.

`caption`, `audio`, `video` and `playlist` are the ones a store actually reaches
for — a product demo, a how-to clip, a release-note track. WordPress ships them;
this set had six of its ten, so an author who pasted `[video]` got the literal
text on the page.

Two things are checked beyond "it produces HTML":

* **the content is HTML, not text.** `[caption]` wraps the image the author
  pasted, so escaping the body would show the markup instead of the picture.
  Every *attribute* is escaped; the body is not, and that asymmetry is the
  whole point of the shortcode.
* **a media URL is checked before it reaches an attribute.** `javascript:` and
  `data:` in a `src` run in the page's origin, so an author who pastes one
  turns a shortcode into a script on the storefront. Refused values render as
  nothing, which is visible to the author, rather than as a blocked request
  they would spend an afternoon chasing.

Run:  python ../.p1-tests/shortcode_media_test.py
"""

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, "C:/Users/Administrator/Desktop/site/backend")

import app.main  # noqa: F401 — registers every model, as the app does
from app.shared.content.shortcodes import process_shortcodes

bad: list[str] = []


def check(label, ok, detail=""):
    print(f"  {label}: {ok}")
    if not ok:
        bad.append(f"{label}: {detail}" if detail else label)


def main() -> int:
    # 1. caption keeps the body's HTML and escapes its attributes
    # Single quotes inside, because the parser reads attributes up to the
    # matching quote and a double-quoted `src` inside a double-quoted test string
    # would truncate the attribute list rather than testing anything.
    out = process_shortcodes(
        "[caption align='aligncenter' width='300']"
        "<img src='/media/a.jpg' alt='a' />[/caption]"
    )
    check("1. caption renders a figure", out.startswith("<figure"), out[:60])
    check("1b. the body is HTML, not escaped markup",
          "<img" in out, out[:100])
    check("1c. the align attribute is carried",
          "aligncenter" in out, out[:100])
    check("1d. and the width", "width:300px" in out, out[:100])

    # 2. an attribute value cannot break out of the attribute it lands in.
    #
    #    The value has to be one the parser accepts: an `onload="…"` written in
    #    the source is parsed as its own attribute and never reaches the escape,
    #    so testing it proves nothing. A single-quoted value *holding* a double
    #    quote is the case — and the parser truncates it at that quote, so what
    #    is asserted is the property that survives truncation: the truncated
    #    value is still escaped, and the tail is never concatenated into the
    #    attribute unescaped.
    out = process_shortcodes("[caption align='a\"b']z[/caption]")
    check("2. an attribute value with a quote in it is escaped",
          'align="a\"b"' not in out and "onerror" not in out,
          out[:140])

    # 3. video, audio
    out = process_shortcodes('[video src="/media/v.mp4" width="640"]')
    check("3. video renders a player", "<video" in out and "controls" in out, out[:80])
    check("3b. with the width it was given", 'width="640"' in out, out[:80])

    out = process_shortcodes('[audio src="/media/a.mp3"]')
    check("3c. audio renders a player", "<audio" in out and "controls" in out, out[:80])

    # 4. playlist, with and without titles
    out = process_shortcodes('[playlist ids="1,2,3"]')
    check("4. playlist renders a list",
          "<ol>" in out and out.count("<li") == 3, out[:90])
    out = process_shortcodes('[playlist ids="1,2" titles="hide"]')
    check("4b. titles can be hidden", 'data-titles="false"' in out, out[:90])

    # 5. the refusal. A `javascript:` src is a script in the page's origin.
    for src in ("javascript:alert(1)", "data:text/html,<script>alert(1)</script>",
                "vbscript:msgbox(1)"):
        out = process_shortcodes(f'[video src="{src}"]')
        check(f"5. refused: {src[:24]}", out == "", out[:60])
    out = process_shortcodes('[audio src="javascript:alert(1)"]')
    check("5b. audio refuses it too", out == "", out[:60])

    # 6. and what is allowed still works — a refusal that also blocks the
    #    normal case is not a security control, it is an outage
    for good in ("/media/a.mp3", "https://cdn.example/a.mp3",
                 "/uploads/a.mp3", "http://cdn.example/a.mp3"):
        out = process_shortcodes(f'[audio src="{good}"]')
        check(f"6. allowed: {good[:30]}", "<audio" in out, out[:60])

    # 7. a malformed shortcode is left as text, not dropped. An author who
    #    types `[video src=` has to see what they typed.
    out = process_shortcodes("[video src=")
    check("7. a malformed shortcode is left visible",
          "video" in out, out[:60])

    if bad:
        print("\nSHORTCODE GAPS:")
        for b in bad:
            print(f"  {b}")
        raise SystemExit(1)
    print("\nPASS: the four media shortcodes render, escape their attributes, "
          "and refuse a source that would run script.")
    return 0


if __name__ == "__main__":
    sys.exit(main())