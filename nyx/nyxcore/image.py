"""Image analysis — metadata, thumbnails and perceptual hashing (aHash)."""
from __future__ import annotations

import io
import struct
import zlib


def jpeg_dimensions(data: bytes) -> tuple:
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            h, w = struct.unpack_from(">HH", data, i + 5)
            return w, h
        if marker in (0xD8, 0x01, 0xFF) or 0xD0 <= marker <= 0xD7:
            i += 2
        elif marker == 0xDA:  # start of scan: stop scanning
            break
        else:
            if i + 4 > n:
                break
            seglen = struct.unpack_from(">H", data, i + 2)[0]
            if seglen < 2:
                break
            i += 2 + seglen
    return 0, 0


def png_dimensions(data: bytes) -> tuple:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0
    w, h = struct.unpack_from(">II", data, 16)
    return w, h


def gif_dimensions(data: bytes) -> tuple:
    if data[:4] != b"GIF8":
        return 0, 0
    w, h = struct.unpack_from("<HH", data, 6)
    return w, h


def bmp_dimensions(data: bytes) -> tuple:
    if data[:2] != b"BM":
        return 0, 0
    w, h = struct.unpack_from("<ii", data, 18)
    return abs(w), abs(h)


def dims_for(sig: str, data: bytes) -> tuple:
    return {"jpeg": jpeg_dimensions, "png": png_dimensions,
            "gif": gif_dimensions, "gif89a": gif_dimensions,
            "bmp": bmp_dimensions}.get(sig, lambda _d: (0, 0))(data)


def ahash(data: bytes, sig: str, size: int = 8) -> str:
    """64-bit average-hash without PIL: resize via nearest on raw pixels.

    Supports PNG (8-bit RGB/RGBA non-interlaced) and grayscale BMP;
    JPEG needs Pillow at runtime — falls back to hash of dimensions.
    """
    try:
        if sig == "png":
            w, h, rows = _png_rgb(data)
        elif sig == "bmp":
            w, h, rows = _bmp_rgb(data)
        else:
            d = dims_for(sig, data)
            return f"dim:{d[0]}x{d[1]}"
        if not rows:
            return "n/a"
        small = [[0] * size for _ in range(size)]
        for y in range(size):
            for x in range(size):
                sy = y * h // size
                sx = x * w // size
                px = rows[sy * w + sx]
                small[y][x] = (px[0] + px[1] + px[2]) // 3
        avg = sum(v for row in small for v in row) // (size * size)
        bits = "".join("1" if small[y][x] >= avg else "0"
                       for y in range(size) for x in range(size))
        return f"{int(bits, 2):016x}"
    except Exception:
        return "n/a"


def _png_rgb(data: bytes) -> tuple:
    i = 8
    w = h = 0
    bitdepth = colortype = interlace = 0
    idat = b""
    while i + 8 <= len(data):
        clen = struct.unpack_from(">I", data, i)[0]
        ctype = data[i + 4:i + 8]
        chunk = data[i + 8:i + 8 + clen]
        if ctype == b"IHDR":
            w, h, bitdepth, colortype, _comp, _filt, interlace = struct.unpack(
                ">IIBBBBB", chunk[:13])
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
        i += 12 + clen
    if not w or not h or interlace or bitdepth != 8 or colortype not in (2, 6):
        return 0, 0, []
    raw = zlib.decompress(idat)
    channels = 3 if colortype == 2 else 4
    stride = w * channels
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _y in range(h):
        f = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if f == 1:
            for x in range(channels, stride):
                line[x] = (line[x] + line[x - channels]) & 0xFF
        elif f == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif f == 3:
            for x in range(stride):
                a = line[x - channels] if x >= channels else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
        elif f == 4:
            for x in range(stride):
                a = line[x - channels] if x >= channels else 0
                b = prev[x]
                c = prev[x - channels] if x >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xFF
        out.extend(line)
        prev = line
    px = [(out[i], out[i + 1], out[i + 2])
          for i in range(0, len(out) - channels + 1, channels)]
    return w, h, px


def _bmp_rgb(data: bytes) -> tuple:
    w, h = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0]
    if bpp != 24:
        return 0, 0, []
    off = struct.unpack_from("<I", data, 10)[0]
    h = abs(h)
    row = ((w * 3 + 3) // 4) * 4
    px = []
    for y in range(h):
        base = off + y * row
        for x in range(w):
            b, g, r = data[base + x * 3: base + x * 3 + 3]
            px.append((r, g, b))
    return w, h, px
