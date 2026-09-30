"""Wave 5 #69 — prove flip actually flips, rather than just existing.

Run:  cd backend && PYTHONIOENCODING=utf-8 python ../scripts/wp-parity/w5_flip.py

`ImageEditor.flip` was fully implemented and had no route and no caller, so it
was dead code. Wiring a route to it is only half the job: a transposed image
that is written to the same path it was read from would look fine and change
nothing. These checks read the pixels.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"C:\Users\Administrator\Desktop\site\backend")

from PIL import Image  # noqa: E402

from app.modules.media.application.image_editor import ImageEditor  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n      {detail}")


def sample(path: Path) -> list[tuple[int, int, int]]:
    """Two edge pixels of the top row: left and right.

    Deliberately NOT the centre. On an even-width image the geometric middle
    falls between two pixels, so `w // 2` is not the mirror of itself: on a
    120px image x=60 maps to x=59. An earlier version of this file sampled the
    middle and asserted it was unchanged, which failed on correct code — the
    assertion, not the flip, was wrong.
    """
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        w, _ = rgb.size
        return [rgb.getpixel((0, 0)), rgb.getpixel((w - 1, 0))]


async def main() -> int:
    tmp = Path(tempfile.mkdtemp())

    # An image whose two sampled edge pixels differ, so a no-op cannot
    # accidentally look like a flip.
    src = tmp / "source.png"
    with Image.new("RGB", (120, 80), "black") as im:
        im.putpixel((0, 0), (255, 0, 0))       # red    left
        im.putpixel((119, 0), (0, 0, 255))     # blue   right
        im.save(src)

    before = sample(src)
    check(
        "the fixture is asymmetric",
        before[0] != before[1],
        f"top row edges are {before} — different, so a no-op would be visible",
    )

    # 1. Horizontal flip mirrors left-right: the left and right edge swap.
    out_h = Path(await ImageEditor.flip(str(src), horizontal=True))
    after_h = sample(out_h)
    check(
        "horizontal flip mirrors left-right",
        after_h == [before[1], before[0]],
        f"left {before[0]} right {before[1]}  ->  left {after_h[0]} right {after_h[1]} (swapped)",
    )

    # 2. Vertical flip mirrors top-bottom: a top-row-only fixture is unchanged
    #    in its sampled row, so compare a pixel that IS mirrored.
    out_v = Path(await ImageEditor.flip(str(src), horizontal=False))
    with Image.open(src) as a, Image.open(out_v) as b:
        top_src = a.convert("RGB").getpixel((0, 0))
        top_flip = b.convert("RGB").getpixel((0, 0))
        h = a.size[1]
        bottom_src = a.convert("RGB").getpixel((0, h - 1))
        bottom_flip = b.convert("RGB").getpixel((0, h - 1))
    check(
        "vertical flip mirrors top-bottom",
        top_flip == bottom_src and bottom_flip == top_src,
        f"top {top_src}->{top_flip}, bottom {bottom_src}->{bottom_flip} (rows swapped)",
    )

    # 3. The original is NOT overwritten — the rotate/crop/resize contract is
    #    "create a new asset", and a flip that clobbered the source would make
    #    the feature unusable (you could not try the other axis).
    check(
        "the source file is left intact",
        sample(src) == before,
        "the original still reads as it did before the flip",
    )

    # 4. The output lands on a NEW path (so it can become a derived asset).
    check(
        "output goes to a new path",
        out_h.resolve() != src.resolve(),
        f"{out_h.name} is distinct from {src.name}",
    )

    # 5. Flipping twice is a no-op, which proves the transform is an involution
    #    rather than an accumulating corruption.
    out_h2 = Path(await ImageEditor.flip(str(out_h), horizontal=True))
    check(
        "flipping twice returns the original",
        sample(out_h2) == before,
        f"after two horizontal flips: {sample(out_h2)}",
    )

    print()
    failed = [r for r in results if not r[1]]
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("FAILED: " + ", ".join(r[0] for r in failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
