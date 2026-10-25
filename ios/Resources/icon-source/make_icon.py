"""App icon: a basketball on navy, drawn at 4x and scaled down. No NBA marks.

    ../../.venv/bin/python Resources/icon-source/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE, SCALE = 1024, 4
NAVY, ORANGE, SEAM = (17, 30, 58), (240, 128, 34), (28, 22, 20)
OUT = Path(__file__).resolve().parents[1] / "Assets.xcassets" / "AppIcon.appiconset" / "AppIcon-1024.png"

big = SIZE * SCALE
image = Image.new("RGB", (big, big), NAVY)
draw = ImageDraw.Draw(image)
c, r = big / 2, big * 0.34
box = (c - r, c - r, c + r, c + r)
draw.ellipse(box, fill=ORANGE)
w = int(big * 0.022)
draw.line((c, c - r, c, c + r), fill=SEAM, width=w)
draw.line((c - r, c, c + r, c), fill=SEAM, width=w)
# The two curved seams: arcs of circles centred off the ball, left and right.
for side in (-1, 1):
    cx = c + side * r * 1.45
    rr = r * 1.05
    draw.arc((cx - rr, c - rr, cx + rr, c + rr), 0, 360, fill=SEAM, width=w)
# Clip the seams to the ball, keep the navy outside.
mask = Image.new("L", (big, big), 0)
ImageDraw.Draw(mask).ellipse(box, fill=255)
image = Image.composite(image, Image.new("RGB", (big, big), NAVY), mask)
ImageDraw.Draw(image).ellipse(box, outline=SEAM, width=w)
image.resize((SIZE, SIZE), Image.LANCZOS).save(OUT)
print(OUT)
