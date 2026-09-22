"""
draws the 3hz.dev 88x31 button (still + animated) and the favicons.

    pip install pillow
    python3 _tools/button.py

writes buttons/3hz.png, buttons/3hz.gif, favicon-32.png, apple-touch-icon.png.
every pixel is placed by hand below, so tweak away. folders starting with _
aren't published by github pages, so this file stays off the site.
"""
import math
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

# catppuccin mocha
PAL = dict(
    crust="#11111b", mantle="#181825", base="#1e1e2e", s0="#313244", s1="#45475a",
    s2="#585b70", ov0="#6c7086", ov1="#7f849c", text="#cdd6f4", lav="#b4befe",
    mauve="#cba6f7", pink="#f5c2e7",
)
C = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in PAL.items()}


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


# chunky 2px-stroke glyphs for the wordmark, 8x13
BIG = {
    "3": [".######.", "########", "##....##", "......##", "......##", "..#####.", "..#####.",
          "......##", "......##", "......##", "##....##", "########", ".######."],
    "h": ["##......", "##......", "##......", "##......", "##.####.", "########", "###...##",
          "##....##", "##....##", "##....##", "##....##", "##....##", "##....##"],
    "z": ["........", "........", "........", "........", "########", "########", ".....###",
          "....###.", "...###..", "..###...", ".###....", "########", "########"],
}
# tiny 3x5 font for ".dev"
SMALL = {
    ".": [".", ".", ".", ".", "#"],
    "d": ["..#", ".##", "#.#", "#.#", ".##"],
    "e": ["...", ".##", "###", "#..", ".##"],
    "v": ["...", "#.#", "#.#", "#.#", ".#."],
}


def blit(px, rows, x0, y0, color):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                px[x0 + x, y0 + y] = color(y) if callable(color) else color


def wordmark(px, x0, y0):
    light, deep = mix(C["mauve"], C["text"], .45), mix(C["mauve"], C["lav"], .55)
    shade = lambda y: light if y <= 2 else C["mauve"] if y <= 8 else deep
    for color, off in ((C["crust"], 1), (shade, 0)):  # shadow, then the letters
        x = x0
        for ch in "3hz":
            blit(px, BIG[ch], x + off, y0 + off, color)
            x += len(BIG[ch][0]) + 2
    return x - 2


def small_text(px, s, x0, y0, color):
    x = x0
    for ch in s:
        blit(px, SMALL[ch], x, y0, color)
        x += len(SMALL[ch][0]) + 1


def bevel(px, w, h):
    for x in range(w):
        for y in range(h):
            px[x, y] = C["base"]
    for x in range(w):
        px[x, 0], px[x, h - 1] = C["ov0"], C["crust"]
    for y in range(h):
        px[0, y], px[w - 1, y] = C["ov0"], C["crust"]
    for x in range(1, w - 1):
        px[x, 1], px[x, h - 2] = C["s1"], C["mantle"]
    for y in range(1, h - 1):
        px[1, y], px[w - 2, y] = C["s1"], C["mantle"]


def scope(px, x0, y0, w, h, phase=0, led=True, amp=5, cycles=3, dots=True):
    """a little oscilloscope screen with a 3 cycle sine wave. 3 hz, get it"""
    for x in range(x0, x0 + w):
        for y in range(y0, y0 + h):
            px[x, y] = C["crust"]
    mid = y0 + h // 2
    if dots:
        for x in range(x0 + 3, x0 + w - 1, 6):
            for y in range(y0 + 2, y0 + h, 4):
                px[x, y] = C["s0"]
        for x in range(x0 + 1, x0 + w - 1, 2):
            px[x, mid] = C["s0"]
    per = w / cycles
    pts = [(x0 + i, round(mid - amp * math.sin((i + phase) / per * 2 * math.pi))) for i in range(w)]
    glow = mix(C["crust"], C["mauve"], .30)
    for layer in ("glow", "line"):
        prev = None
        for x, y in pts:
            if prev is None or prev == y:
                ys = [y]
            else:
                step = 1 if y > prev else -1
                ys = list(range(prev + step, y + step, step))
            for yy in ys:
                if layer == "glow":
                    for dy in (-1, 1):
                        if y0 <= yy + dy < y0 + h and px[x, yy + dy] != C["mauve"]:
                            px[x, yy + dy] = glow
                else:
                    px[x, yy] = C["mauve"]
            prev = y
    if led is not None:
        px[x0 + w - 3, y0 + 1] = C["pink"] if led else C["s1"]


def button(phase=0, led=True):
    img = Image.new("RGB", (88, 31))
    px = img.load()
    bevel(px, 88, 31)
    scope(px, 4, 4, 36, 23, phase, led)
    for x in range(4, 41):          # recessed edge under/right of the screen
        px[x, 27] = C["s1"]
    for y in range(4, 28):
        px[40, y] = C["s1"]
    end = wordmark(px, 49, 5)
    small_text(px, ".dev", end - 14, 21, C["ov1"])
    return img


def favicon(size):
    img = Image.new("RGBA", (size, size), C["crust"] + (255,))
    px = img.load()
    scope(px, 0, 0, size, size, 0, None, amp=size // 4 - 1, dots=size >= 32)
    for x, y in ((0, 0), (1, 0), (0, 1)):  # rounded-ish corners
        for cx, cy in ((x, y), (size - 1 - x, y), (x, size - 1 - y), (size - 1 - x, size - 1 - y)):
            px[cx, cy] = (0, 0, 0, 0)
    return img


if __name__ == "__main__":
    out = ROOT / "buttons"
    out.mkdir(exist_ok=True)
    button().save(out / "3hz.png", optimize=True)
    frames = [button(i, i < 6).convert("P", palette=Image.ADAPTIVE, colors=64) for i in range(12)]
    frames[0].save(out / "3hz.gif", save_all=True, append_images=frames[1:], duration=85, loop=0, disposal=1)

    favicon(32).save(ROOT / "favicon-32.png", optimize=True)
    # apple wants a solid square, so draw it at 45px and scale up with hard pixels
    touch = Image.new("RGB", (45, 45), C["crust"])
    scope(touch.load(), 3, 3, 39, 39, 0, None, amp=9)
    touch.resize((180, 180), Image.NEAREST).save(ROOT / "apple-touch-icon.png", optimize=True)
    print("done")
