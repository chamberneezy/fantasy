"""App icon from the NBA Fantasy mark (docs/img/mark.png), as the site's header shows it:
the mark inside a blue→red conic ring, on the dark page colour.

    .venv/bin/python ios/Resources/icon-source/make_icon.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[3]
MARK = ROOT / "docs" / "img" / "mark.png"
OUT = Path(__file__).resolve().parents[1] / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon-1024.png"
SIZE = 1024
PAGE = (7, 13, 26)  # --page-bg, dark theme
BLUE, RED = (43, 119, 231), (231, 63, 43)
RING = 0.80  # ring diameter as a share of the icon
RING_WIDTH = 0.022


def conic(size: int) -> Image.Image:
    """Blue → red → blue around the circle, starting at 200°, like the site's .mark-wrap."""
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    centre = (size - 1) / 2
    for y in range(size):
        for x in range(size):
            turn = (math.degrees(math.atan2(x - centre, centre - y)) - 200) % 360 / 360
            mix = 1 - abs(turn * 2 - 1)  # 0 at blue, 1 at red
            pixels[x, y] = tuple(round(b + (r - b) * mix) for b, r in zip(BLUE, RED))
    return image


def main() -> None:
    icon = Image.new("RGB", (SIZE, SIZE), PAGE)
    ring = round(SIZE * RING)
    corner = (SIZE - ring) // 2
    # Soft blue and red glow behind the ring.
    glow = Image.new("RGB", (SIZE, SIZE), PAGE)
    ImageDraw.Draw(glow).ellipse((corner - 20, corner - 20, corner + ring + 20, corner + ring + 20), fill=(30, 70, 150))
    icon = Image.blend(icon, glow.filter(ImageFilter.GaussianBlur(60)), 0.55)
    disc = Image.new("L", (ring, ring), 0)
    ImageDraw.Draw(disc).ellipse((0, 0, ring - 1, ring - 1), fill=255)
    icon.paste(conic(ring), (corner, corner), disc)
    inner = round(ring * (1 - 2 * RING_WIDTH))
    mark = Image.open(MARK).convert("RGBA").resize((inner, inner), Image.LANCZOS)
    backing = Image.new("L", (inner, inner), 0)
    ImageDraw.Draw(backing).ellipse((0, 0, inner - 1, inner - 1), fill=255)
    offset = (SIZE - inner) // 2
    icon.paste(Image.new("RGB", (inner, inner), PAGE), (offset, offset), backing)
    icon.paste(mark, (offset, offset), mark)
    icon.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
