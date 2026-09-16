"""Generate assets/nyx.ico — dark rounded square, cyan→violet gradient, N glyph."""
from PIL import Image, ImageDraw, ImageFont

S = 256


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# gradient square with rounded corners (mask)
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
c1, c2 = (8, 12, 26, 255), (20, 24, 48, 255)
for y in range(S):
    gd.line([(0, y), (S, y)], fill=lerp(c1, c2, y / S))
mask = Image.new("L", (S, S), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([4, 4, S - 4, S - 4], radius=52, fill=255)
img.paste(grad, (0, 0), mask)

# neon frame
d.rounded_rectangle([4, 4, S - 4, S - 4], radius=52, outline=(34, 211, 238, 220), width=6)

# glyph: "N" drawn as two verticals + diagonal, with glow
n_top, n_bot = 62, 194
x1, x2 = 76, 180
w = 16
glow = (34, 211, 238, 90)
main = (224, 242, 254, 255)
mag = (167, 139, 250, 255)
for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
    d.rectangle([x1 + dx, n_top + dy, x1 + w + dx, n_bot + dy], fill=glow)
    d.rectangle([x2 - w + dx, n_top + dy, x2 + dx, n_bot + dy], fill=glow)
    d.line([x1 + w, n_top + 8, x2 - w, n_bot - 8], fill=glow, width=22)
d.rectangle([x1, n_top, x1 + w, n_bot], fill=main)
d.rectangle([x2 - w, n_top, x2, n_bot], fill=mag)
d.line([x1 + w, n_top + 8, x2 - w, n_bot - 8], fill=main, width=12)
d.ellipse([x1 - 6, n_top - 6, x1 + w + 6, n_top + w - 6 + 6], fill=main)
d.ellipse([x2 - w - 6, n_bot - w - 6 + 6, x2 + 6, n_bot + 6], fill=mag)

img.save("assets/nyx.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                  (64, 64), (128, 128), (256, 256)])
img.save("assets/nyx.png")
print("OK assets/nyx.ico + assets/nyx.png")
