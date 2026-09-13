# -*- coding: utf-8 -*-
"""Generate the InsightDesk desktop app icon (gradient rounded square + chat bubble)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path("desktop/electron/build")
OUT.mkdir(parents=True, exist_ok=True)

SIZE = 1024
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# vertical gradient (indigo -> violet) masked by a rounded square
gradient = Image.new("RGBA", (SIZE, SIZE))
top, bottom = (79, 110, 255), (151, 71, 255)
for y in range(SIZE):
    t = y / (SIZE - 1)
    row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
    for x in range(0, SIZE, SIZE):
        pass
    gradient.paste(row, (0, y, SIZE, y + 1))

mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([16, 16, SIZE - 16, SIZE - 16], radius=210, fill=255)
img.paste(gradient, (0, 0), mask)

# white chat bubble (circle + tail), with three dots
white = (255, 255, 255, 255)
dot_color = (124, 93, 255, 255)
cx, cy, r = SIZE // 2, SIZE // 2 - 40, 300
draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=white)
draw.polygon([(cx - 150, cy + 230), (cx + 60, cy + 230), (cx - 190, cy + 380)], fill=white)
dot_r = 38
for dx in (-110, 0, 110):
    draw.ellipse([cx + dx - dot_r, cy - dot_r, cx + dx + dot_r, cy + dot_r], fill=dot_color)

# 256px master for ICO
img_256 = img.resize((256, 256), Image.LANCZOS)
img_256.save(OUT / "icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
img.resize((512, 512), Image.LANCZOS).save(OUT / "icon.png")
print("icons written to", OUT)
