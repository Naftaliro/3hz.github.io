#!/usr/bin/env python3
"""
grab 88x31 buttons from friends' sites for the ~/friends window.

    python3 _tools/grab_buttons.py              crawl, then pick in your browser
    python3 _tools/grab_buttons.py --auto       skip the picker, take the default picks
    python3 _tools/grab_buttons.py --dry-run    just list what it found (with keys)
    python3 _tools/grab_buttons.py --auto --drop KEY --keep KEY
                                                untick / tick specific buttons without the picker

what it does:
  1. visits every site in FRIENDS, plus a few pages on each that look like
     links / buttons / friends pages
  2. finds every 88x31 (and 2x 176x62) image and where it links to
  3. sorts them into
       friend   one of the sites in FRIENDS
       person   links to somebody's personal site
       other    projects, distros, browsers, causes, platforms, "made with" badges
     buttons that don't link anywhere are ignored, there's nowhere to point them
  4. opens a page with friends + people ticked and "other" unticked. change
     whatever you like and hit save
  5. saves the picks into buttons/friends/ and rewrites the list in index.html
     (between the <!-- buttons:start --> and <!-- buttons:end --> lines)

your choices are remembered in _tools/buttons.json, so running it again later
only really asks about new buttons. no dependencies, python 3.8+.
"""
import argparse
import base64
import concurrent.futures as cf
import hashlib
import html
import json
import re
import secrets
import ssl
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ── edit these ────────────────────────────────────────────────────────────────

FRIENDS = [
    "https://williamhorning.dev/",
    "https://vavakado.xyz/",
    "https://girlthi.ng/~thermia/",
    "https://int4.cc/",
    "https://avascik.neocities.org/",
    "https://saphingus.xyz/",
    "https://pastelthepastel.github.io/",
    "https://carsoncoder.com/",
    "https://byte.at.awawa.club/",
    "https://ecl1pzee.github.io/",
    "https://heckadecimal.dev/",
    "https://a-catgirl.dev/",
]

# my own sites. buttons pointing here are skipped (but counted, for the ego)
ME = ["3hz.dev", "naftaliro.dev", "mitchellberg.org"]

# buttons linking to these go under "other". a plain name also covers its
# subdomains (wiki.archlinux.org). a leading = means that exact host only, for
# hosts where subdomains are people (avascik.neocities.org is a person).
NOT_PEOPLE = """
archlinux.org nixos.org debian.org ubuntu.com fedoraproject.org getfedora.org gentoo.org
voidlinux.org alpinelinux.org linuxmint.com opensuse.org manjaro.org zorin.com endeavouros.com
kernel.org linux.org linuxfoundation.org freebsd.org openbsd.org netbsd.org gnu.org fsf.org
eff.org mozilla.org firefox.com librewolf.net vivaldi.com brave.com torproject.org google.com
microsoft.com apple.com w3.org w3schools.com wikipedia.org wikimedia.org archive.org
creativecommons.org anybrowser.org any-browser.org notbyai.fyi yesterweb.org catppuccin.com
vim.org neovim.io gnome.org kde.org xfce.org hyprland.org swaywm.org i3wm.org python.org
rust-lang.org go.dev golang.org nodejs.org deno.com deno.land php.net jetbrains.com
visualstudio.com obsidian.md discord.com discord.gg twitter.com x.com bsky.app youtube.com
twitch.tv reddit.com steampowered.com steamcommunity.com spotify.com letsencrypt.org
cloudflare.com signal.org matrix.org joinmastodon.org ublockorigin.com adblockplus.org
thetrevorproject.org translifeline.org blacklivesmatter.com hackclub.com nintendo.com
minecraft.net sadgrl.online 32bit.cafe indieweb.org
=neocities.org =nekoweb.org =github.io =github.com =gitlab.com =codeberg.org =itch.io
=tumblr.com =carrd.co =bearblog.dev =wordpress.com =blogspot.com =netlify.app =pages.dev
=vercel.app
""".split()

# words in a button's alt text, title, filename or link text that mean it's
# probably not a person. matched as whole words, case doesn't matter.
NOT_PEOPLE_WORDS = """
valid|made with|powered by|built with|best viewed|viewed with|any browser|anybrowser|
firefox|chrome|chromium|netscape|internet explorer|safari|opera|linux|arch|archlinux|
nixos|debian|gentoo|ubuntu|fedora|mint|windows|macos|bsd|vim|neovim|emacs|vscode|
html|html5|xhtml|css|css3|javascript|js|php|python|rust|golang|java|rss|atom|feed|
trans|transgender|trans rights|pride|lgbt|lgbtq|lgbtqia|queer|gay|lesbian|bisexual|
nonbinary|enby|palestine|ukraine|blm|black lives|acab|antifa|anarchy|anarchist|
communism|communist|socialism|vote|abolish|rights|foss|gnu|gpl|open source|free software|
copyleft|no ai|not by ai|anti ai|ai free|noai|adblock|ublock|piracy|neocities|nekoweb|
webring|web ring|discord|steam|twitch|youtube|tumblr|bluesky|mastodon|fediverse|
unicode|utf-8|cookies|tracking|hyprland|sway|i3|kde|gnome|xfce|catppuccin|dracula|
gruvbox|minecraft|nintendo|playstation|xbox|internet archive|wikipedia|creative commons|
winamp|geocities|y2k|hit counter|guestbook|get it on|download|button maker|88x31 maker
""".replace("\n", "").split("|")

# ── the rest ──────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; 3hz-button-grabber; +https://3hz.dev)"
SUBPAGE_HINT = re.compile(r"button|88x?31|link|friend|webring|neighbo|blogroll|cool|site|other|elsewhere|social|web", re.I)
SUBPAGE_STRONG = re.compile(r"button|88x?31|friend|link", re.I)
MAX_SUBPAGES = 6
SIZES = {(88, 31), (176, 62)}
IMAGE_EXTS = ("png", "gif", "jpg", "webp", "bmp")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def ssl_context():
    try:
        import certifi  # macOS python.org builds sometimes need this
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL = ssl_context()
_ssl_hint_shown = False


def fetch(url, limit=2_000_000):
    global _ssl_hint_shown
    if url.startswith("data:"):
        m = re.match(r"data:([\w/+.-]+)?(;base64)?,(.*)", url, re.S)
        if not m:
            return None, None
        raw = m.group(3)
        try:
            data = base64.b64decode(raw) if m.group(2) else urllib.parse.unquote_to_bytes(raw)
        except ValueError:
            return None, None
        return url, data
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=15, context=SSL) as r:
            return r.geturl(), r.read(limit)
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLError) and not _ssl_hint_shown:
            _ssl_hint_shown = True
            log("  ssl error. on macOS, run the 'Install Certificates.command' that came with python,")
            log("  or `pip3 install certifi`, then try again")
        return None, None
    except Exception:
        return None, None


def image_info(data):
    """(ext, (w, h)) from the file's header, or (None, None) for things we don't use"""
    try:
        return _image_info(data)
    except (struct.error, IndexError):
        return None, None


def _image_info(data):
    if not data or len(data) < 24:
        return None, None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png", struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif", struct.unpack("<HH", data[6:10])
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8X":
            w = 1 + int.from_bytes(data[24:27], "little")
            h = 1 + int.from_bytes(data[27:30], "little")
            return "webp", (w, h)
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return "webp", (w & 0x3FFF, h & 0x3FFF)
        if chunk == b"VP8L":
            b = int.from_bytes(data[21:25], "little")
            return "webp", ((b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1)
        return None, None
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "jpg", (w, h)
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
        return None, None
    if data[:2] == b"BM":
        w, h = struct.unpack("<ii", data[18:26])
        return "bmp", (w, abs(h))
    return None, None


def site_key(url):
    """who a url belongs to: the host, plus ~user for tilde sites"""
    p = urllib.parse.urlsplit(url)
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if p.port and p.port not in (80, 443):
        host += f":{p.port}"
    m = re.match(r"/(~[^/]+)", p.path or "")
    if m:
        return host + "/" + m.group(1)
    seg = [x for x in (p.path or "").split("/") if x]
    if host in ("github.com", "gitlab.com", "codeberg.org") and seg:
        return host + "/" + seg[0]  # a profile, one person per account
    return host


def host_of(url):
    h = (urllib.parse.urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def not_people_host(url):
    host = host_of(url)
    path = [s for s in urllib.parse.urlsplit(url).path.split("/") if s]
    for entry in NOT_PEOPLE:
        if entry.startswith("="):
            if host == entry[1:]:
                # a single-segment github/gitlab/codeberg link is a person's profile
                if host in ("github.com", "gitlab.com", "codeberg.org") and len(path) == 1:
                    return None
                return f"links to {host}"
        elif host == entry or host.endswith("." + entry):
            return f"links to {host}"
    if "webring" in host or host.startswith("ring.") or ".ring." in host:
        return "a webring"
    return None


WORD_RES = [(w, re.compile(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])")) for w in NOT_PEOPLE_WORDS if w]


def not_people_words(*texts):
    text = " ".join(t for t in texts if t).lower()
    text = re.sub(r"[_\-.]+", " ", text)
    for w, rx in WORD_RES:
        if rx.search(text):
            return f'says "{w}"'
    return None


class Page(HTMLParser):
    """pulls out images (and the link around them), links, and code snippets"""

    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.base = url
        self.anchors = []      # stack of [href, text]
        self.links = []        # (href, text)
        self.images = []       # dict(src, href, w, h, alt, title, text)
        self.raw = []          # text inside code/pre/textarea
        self._raw_depth = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "base" and a.get("href"):
            self.base = urllib.parse.urljoin(self.base, a["href"])
        elif tag == "a":
            self.anchors.append([a.get("href") or None, ""])
        elif tag == "img":
            src = a.get("src") or a.get("data-src") or ""
            if src:
                num = lambda v: int(re.match(r"\s*(\d+)", v).group(1)) if re.match(r"\s*\d", v or "") else None
                href = next((h for h, _ in reversed(self.anchors) if h), None)
                self.images.append(dict(src=src, href=href, w=num(a.get("width")), h=num(a.get("height")),
                                        alt=a.get("alt", ""), title=a.get("title", ""), anchor=self.anchors[-1] if self.anchors else None))
        elif tag in ("code", "pre", "textarea"):
            self._raw_depth += 1

    def handle_endtag(self, tag):
        if tag == "a" and self.anchors:
            href, text = self.anchors.pop()
            if href:
                self.links.append((href, text.strip()))
        elif tag in ("code", "pre", "textarea") and self._raw_depth:
            self._raw_depth -= 1

    def handle_data(self, data):
        for a in self.anchors:
            a[1] += data
        if self._raw_depth:
            self.raw.append(data)

    def snippets(self):
        """`<a href=..><img src=..></a>` written out as text for people to copy"""
        text = "".join(self.raw)
        for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>\s*<img\b[^>]*src=[\"']([^\"']+)[\"']", text, re.I):
            yield m.group(1), m.group(2)


def crawl(start, aliases):
    """yield candidate dicts from a friend's site. if the site redirects somewhere
    else, the new address is added to `aliases` so it still counts as them"""
    key = site_key(start)
    seen, queue = set(), [start]
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        final, data = fetch(url)
        if not data:
            log(f"  couldn't load {url}")
            continue
        if url == start and site_key(final) != key:
            key = site_key(final)
            aliases.add(key)
        page = Page(final)
        try:
            page.feed(data.decode("utf-8", "replace"))
        except Exception:
            pass
        where = urllib.parse.urlsplit(final).path or "/"
        for img in page.images:
            anchor_text = img["anchor"][1] if img["anchor"] else ""
            yield dict(src=urllib.parse.urljoin(page.base, img["src"]),
                       href=urllib.parse.urljoin(page.base, img["href"]) if img["href"] else None,
                       w=img["w"], h=img["h"], alt=img["alt"], title=img["title"],
                       text=anchor_text, page=final, where=where, snippet=False)
        for href, src in page.snippets():
            yield dict(src=urllib.parse.urljoin(page.base, src), href=urllib.parse.urljoin(page.base, href),
                       w=None, h=None, alt="", title="", text="", page=final, where=where, snippet=True)
        if url != start:
            continue
        # find a few subpages worth checking (links page, buttons page, ...)
        subs = []
        for href, text in page.links:
            full = urllib.parse.urljoin(page.base, href).split("#")[0]
            p = urllib.parse.urlsplit(full)
            if p.scheme not in ("http", "https") or site_key(full) != key or full in seen:
                continue
            if re.search(r"\.(png|gif|jpe?g|webp|svg|zip|pdf|xml|json|txt|mp3|mp4|ico)$", p.path, re.I):
                continue
            blob = p.path + " " + text
            if SUBPAGE_HINT.search(blob):
                subs.append((0 if SUBPAGE_STRONG.search(blob) else 1, full))
        for _, full in sorted(set(subs))[:MAX_SUBPAGES]:
            queue.append(full)
        time.sleep(0.2)


def slug(key):
    s = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
    return s[:60] or "button"


def display(key):
    if "/~" in key:
        return key.split("/", 1)[1]
    if re.match(r"(github\.com|gitlab\.com|codeberg\.org)/", key):
        return "@" + key.split("/", 1)[1]
    return key


def gather(friends, workers=8):
    friend_keys = [site_key(f) for f in friends]
    alias = {k: k for k in friend_keys}           # any address a friend lives at -> their key
    url_of = dict(zip(friend_keys, friends))
    me = set(ME)
    cands = []
    for f, k in zip(friends, friend_keys):
        log(f"· {display(k)}")
        n, moved = 0, set()
        for c in crawl(f, moved):
            c["friend"] = k
            cands.append(c)
            n += 1
        for m in moved:
            alias[m] = k
            log(f"  (redirects to {display(m)})")
        log(f"  {n} images")

    # download every distinct image once, keep the ones that are 88x31
    urls = sorted({c["src"] for c in cands})
    log(f"checking {len(urls)} images…")
    files = {}
    with cf.ThreadPoolExecutor(workers) as ex:
        for url, (final, data) in zip(urls, ex.map(lambda u: fetch(u, 600_000), urls)):
            ext, size = image_info(data)
            if ext:
                files[url] = (ext, size, data)

    buttons, likes_me = {}, set()
    for c in cands:
        f = files.get(c["src"])
        if not f:
            continue
        ext, size, data = f
        attr = (c["w"], c["h"])
        ok = size in SIZES or (attr == (88, 31) and size[1] and abs(size[0] / size[1] - 88 / 31) < 0.15)
        if not ok:
            continue

        href = c["href"]
        if not href or urllib.parse.urlsplit(href).scheme not in ("http", "https"):
            # an unlinked button on a friend's own site that's hosted there is probably theirs
            hosted_there = alias.get(site_key(c["src"]).split("/")[0]) == c["friend"] or site_key(c["src"]).split("/")[0] == c["friend"].split("/")[0]
            if hosted_there and re.search(r"button|88x?31|badge|banner|(?<![a-z])me(?![a-z])", c["src"], re.I):
                href = url_of[c["friend"]]
            else:
                continue
        key = site_key(href)
        if host_of(href) in me:
            likes_me.add(c["friend"])
            continue

        if key in alias:
            key = alias[key]
            kind, why = "friend", "your friend"
        else:
            why = not_people_host(href) or not_people_words(c["alt"], c["title"], c["text"], urllib.parse.unquote(c["src"].rsplit("/", 1)[-1]))
            kind = "other" if why else "person"
            if kind == "person":
                why = "personal site"
            key = key if kind == "person" else "other:" + c["src"]

        # when there are a few versions of someone's button, prefer the one they host
        # themselves, that links to their front page, or that they hand out as a snippet
        b = buttons.get(key)
        src_key = site_key(c["src"])
        own_host = alias.get(src_key, src_key).split("/")[0] == key.split("/")[0]
        to_root = urllib.parse.urlsplit(href).path.strip("/") in ("", key.partition("/")[2])
        score = (4 if own_host else 0) + (2 if c["snippet"] else 0) + (1 if to_root else 0)
        if b is None:
            buttons[key] = b = dict(key=key, kind=kind, why=why, href=href if kind != "friend" else url_of[key],
                                    src=c["src"], ext=ext, data=data, score=score, found_on=set(), alt=c["alt"])
        elif score > b["score"]:
            b.update(src=c["src"], ext=ext, data=data, score=score)
        b["found_on"].add(c["friend"])

    for f in friends:  # friends without a button still get a (text) spot
        k = site_key(f)
        if k not in buttons:
            buttons[k] = dict(key=k, kind="friend", why="no button found", href=f, src=None, ext=None, data=None, score=-1, found_on=set(), alt="")

    order = {k: i for i, k in enumerate(friend_keys)}
    rank = {"friend": 0, "person": 1, "other": 2}
    out = sorted(buttons.values(), key=lambda b: (rank[b["kind"]], order.get(b["key"], 0), -len(b["found_on"]), b["key"]))
    return out, sorted(likes_me)


# ── saving ────────────────────────────────────────────────────────────────────

def load_state(root):
    p = root / "_tools" / "buttons.json"
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"picked": [], "skipped": [], "files": []}


def default_pick(b, state):
    if b["key"] in state.get("picked", []):
        return True
    if b["key"] in state.get("skipped", []):
        return False
    return b["kind"] in ("friend", "person")


def save(root, buttons, picked_keys, state):
    picked_keys = set(picked_keys)
    outdir = root / "buttons" / "friends"
    outdir.mkdir(parents=True, exist_ok=True)
    lines, written, missing, used = [], [], [], set()
    for b in buttons:
        if b["key"] not in picked_keys:
            continue
        if b["kind"] == "other":
            name = slug(b["alt"] or host_of(b["href"]))[:40] + "-" + hashlib.sha1(b["src"].encode()).hexdigest()[:6]
        else:
            name = slug(b["key"])
        if name in used:
            name += "-" + hashlib.sha1(b["key"].encode()).hexdigest()[:4]
        used.add(name)
        old = sorted(p.name for p in outdir.glob(name + ".*") if p.suffix[1:] in IMAGE_EXTS)
        if b["data"]:
            fn = f"{name}.{b['ext']}"
            for o in old:  # a friend switched from .png to .gif, say
                if o != fn:
                    (outdir / o).unlink()
            (outdir / fn).write_bytes(b["data"])
            written.append(fn)
        elif old:
            fn = old[0]  # couldn't load it today, keep the one we already have
            written.append(fn)
        else:
            fn = f"{name}.png"  # doesn't exist yet, the site draws a text button instead
            missing.append((display(b["key"]), fn))
        alt = display(b["key"]) if b["kind"] != "other" else (b["alt"] or host_of(b["href"]))
        lines.append(f'<a href="{html.escape(b["href"])}"><img src="buttons/friends/{html.escape(fn)}" '
                     f'alt="{html.escape(alt)}" width="88" height="31"></a>')

    # tidy up files this script wrote before that aren't picked anymore
    for fn in state.get("files", []):
        if fn not in written and (outdir / fn).exists() and re.fullmatch(r"[a-z0-9-]+\.(" + "|".join(IMAGE_EXTS) + ")", fn):
            (outdir / fn).unlink()

    index = root / "index.html"
    src = index.read_text()
    m = re.search(r"([ \t]*)<!-- buttons:start -->.*?<!-- buttons:end -->", src, re.S)
    block = "\n".join(lines)
    if m:
        ind = m.group(1)
        new = f"{ind}<!-- buttons:start -->\n" + "".join(f"{ind}{l}\n" for l in lines) + f"{ind}<!-- buttons:end -->"
        index.write_text(src[:m.start()] + new + src[m.end():])
        log(f"updated index.html with {len(lines)} buttons")
    else:
        log("couldn't find the buttons:start / buttons:end markers in index.html, paste these in yourself:\n")
        print(block)

    state = {
        "picked": sorted(picked_keys),
        "skipped": sorted({b["key"] for b in buttons} - picked_keys | (set(state.get("skipped", [])) - picked_keys)),
        "files": sorted(written),
    }
    (root / "_tools" / "buttons.json").write_text(json.dumps(state, indent=2) + "\n")
    log(f"saved {len(written)} images to buttons/friends/")
    for who, fn in missing:
        log(f"  no button found for {who}. if you get one, save it as buttons/friends/{fn} (or .gif)")
    return len(lines)


# ── the picker ────────────────────────────────────────────────────────────────

FRIENDS_IN_USE = []

PICKER_CSS = """
:root{--base:#1e1e2e;--mantle:#181825;--crust:#11111b;--s0:#313244;--s1:#45475a;--ov1:#7f849c;--ov2:#9399b2;
--text:#cdd6f4;--sub:#a6adc8;--mauve:#cba6f7;--green:#a6e3a1;--peach:#fab387;--red:#f38ba8}
*{box-sizing:border-box}body{margin:0;background:var(--crust);color:var(--text);font:14px/1.5 ui-monospace,Menlo,Consolas,monospace}
main{max-width:1100px;margin:0 auto;padding:24px 16px 120px}h1{font-size:18px;margin:0 0 4px;color:var(--mauve)}
.sub{color:var(--ov2);margin:0 0 20px}h2{font-size:14px;margin:28px 0 10px;color:var(--text);display:flex;gap:12px;align-items:baseline}
h2 small{color:var(--ov2);font-weight:400}h2 button{font:inherit;font-size:12px;background:var(--s0);color:var(--sub);border:0;border-radius:6px;padding:2px 8px;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px}
label{display:flex;gap:10px;align-items:center;padding:8px 10px;background:var(--base);border:1px solid var(--s0);border-radius:8px;cursor:pointer}
label:has(input:checked){border-color:var(--mauve);background:color-mix(in srgb,var(--mauve) 10%,var(--base))}
label img,.none{width:88px;height:31px;image-rendering:pixelated;flex-shrink:0}
.none{display:grid;place-items:center;border:1px dashed var(--s1);color:var(--ov1);font-size:10px}
.meta{min-width:0;font-size:12px}.meta b{display:block;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.meta span{color:var(--ov2)}.why-other{color:var(--peach)!important}input{accent-color:var(--mauve)}
footer{position:fixed;left:0;right:0;bottom:0;background:var(--mantle);border-top:1px solid var(--s0);padding:14px 16px}
footer div{max-width:1100px;margin:0 auto;display:flex;gap:14px;align-items:center}
#save{font:inherit;background:var(--mauve);color:var(--crust);border:0;border-radius:8px;padding:8px 16px;cursor:pointer;font-weight:700}
#save:disabled{opacity:.6}#status{color:var(--ov2)}.done{color:var(--green)!important}
"""


def picker_html(buttons, state, likes_me, token):
    groups = [("friend", "your friends", "the sites you listed. ones without a button get a little text button"),
              ("person", "people your friends link to", "personal sites. untick anyone you don't know or don't want"),
              ("other", "probably not people", "projects, distros, browsers, causes, badges. tick anything that's actually a person")]
    parts = []
    for kind, title, blurb in groups:
        items = [b for b in buttons if b["kind"] == kind]
        if not items:
            continue
        cards = []
        for i, b in enumerate(buttons):
            if b["kind"] != kind:
                continue
            chk = " checked" if default_pick(b, state) else ""
            img = f'<img src="/img/{i}" alt="">' if b["data"] else '<span class="none">no button</span>'
            on = f"on {len(b['found_on'])} site{'s' if len(b['found_on']) != 1 else ''}" if b["found_on"] else ""
            why = html.escape(b["why"])
            name = display(b["key"]) if kind != "other" else (b["alt"] or host_of(b["href"]))
            cards.append(f'<label title="{html.escape(b["href"])}"><input type="checkbox" value="{i}"{chk}>{img}'
                         f'<span class="meta"><b>{html.escape(name)}</b><span class="{"why-other" if kind == "other" else ""}">{why}</span>'
                         f'{" · " + on if on else ""}</span></label>')
        parts.append(f'<h2>{title} <small>{len(items)} · {blurb}</small> <button type="button" data-all="{kind}">all</button>'
                     f'<button type="button" data-none="{kind}">none</button></h2><div class="grid" data-kind="{kind}">{"".join(cards)}</div>')
    fan = f" {len(likes_me)} of them already link to you." if likes_me else ""
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>pick buttons</title><style>{PICKER_CSS}</style><main>
<h1>~/friends · pick your buttons</h1><p class="sub">found {len(buttons)} buttons across {len(FRIENDS_IN_USE)} sites.{fan} hover one to see where it links.</p>
{"".join(parts)}</main>
<footer><div><button id="save">save</button><span id="status"></span></div></footer>
<script>
const boxes=[...document.querySelectorAll('input[type=checkbox]')],st=document.getElementById('status'),btn=document.getElementById('save');
const count=()=>{{const n=boxes.filter(b=>b.checked).length;btn.textContent='save '+n+' buttons'}};
boxes.forEach(b=>b.addEventListener('change',count));count();
document.querySelectorAll('[data-all],[data-none]').forEach(el=>el.addEventListener('click',()=>{{
  const k=el.dataset.all||el.dataset.none;document.querySelectorAll('[data-kind="'+k+'"] input').forEach(b=>b.checked=!!el.dataset.all);count()}}));
btn.addEventListener('click',async()=>{{btn.disabled=true;st.textContent='saving…';
  const r=await fetch('/save',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{token:'{token}',picked:boxes.filter(b=>b.checked).map(b=>+b.value)}})}});
  const j=await r.json();st.className='done';st.textContent=j.ok?'saved '+j.count+' buttons to index.html. you can close this tab.':'something went wrong: '+j.error}});
</script></html>"""



def serve_picker(root, buttons, state, likes_me, open_browser=True):
    token = secrets.token_hex(16)
    page = picker_html(buttons, state, likes_me, token).encode()
    done = threading.Event()
    types = {"png": "image/png", "gif": "image/gif", "jpg": "image/jpeg", "webp": "image/webp", "bmp": "image/bmp"}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                return self.send(200, page, "text/html; charset=utf-8")
            m = re.fullmatch(r"/img/(\d+)", self.path)
            if m and int(m.group(1)) < len(buttons) and buttons[int(m.group(1))]["data"]:
                b = buttons[int(m.group(1))]
                return self.send(200, b["data"], types[b["ext"]])
            self.send(404, b"not found", "text/plain")

        def do_POST(self):
            if self.path != "/save":
                return self.send(404, b"not found", "text/plain")
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                if body.get("token") != token:
                    return self.send(403, b'{"ok": false, "error": "bad token"}', "application/json")
                idx = [int(i) for i in body["picked"] if 0 <= int(i) < len(buttons)]
                n = save(root, buttons, [buttons[i]["key"] for i in idx], state)
                self.send(200, json.dumps({"ok": True, "count": n}).encode(), "application/json")
                done.set()
            except Exception as e:
                self.send(500, json.dumps({"ok": False, "error": str(e)}).encode(), "application/json")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log(f"\npick your buttons at {url}  (ctrl+c to quit without saving)")
    if open_browser:
        webbrowser.open(url)
    try:
        while not done.wait(0.5):
            pass
        time.sleep(0.5)
    except KeyboardInterrupt:
        log("\nquit, nothing saved")
    srv.shutdown()


def main():
    ap = argparse.ArgumentParser(description="grab friends' 88x31 buttons for the ~/friends window")
    ap.add_argument("--auto", action="store_true", help="skip the picker and save the default picks")
    ap.add_argument("--dry-run", action="store_true", help="just list what was found")
    ap.add_argument("--no-browser", action="store_true", help="don't open the picker automatically")
    ap.add_argument("--keep", nargs="+", default=[], metavar="KEY", help="tick these (keys come from --dry-run)")
    ap.add_argument("--drop", nargs="+", default=[], metavar="KEY", help="untick these")
    ap.add_argument("--sites", nargs="+", metavar="URL", help="crawl these instead of FRIENDS")
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args()

    friends = args.sites or FRIENDS
    FRIENDS_IN_USE[:] = friends
    buttons, likes_me = gather(friends)
    state = load_state(args.root)
    known = {b["key"] for b in buttons}
    for k in args.keep + args.drop:
        if k not in known:
            log(f"no button with key {k!r}, check --dry-run")
    state["picked"] = sorted((set(state.get("picked", [])) - set(args.drop)) | set(args.keep))
    state["skipped"] = sorted((set(state.get("skipped", [])) - set(args.keep)) | set(args.drop))

    counts = {k: sum(b["kind"] == k for b in buttons) for k in ("friend", "person", "other")}
    log(f"\nfound: {counts['friend']} friends, {counts['person']} people, {counts['other']} other")
    if likes_me:
        log(f"{len(likes_me)} already link to you: {', '.join(display(k) for k in likes_me)}")

    if args.dry_run:
        for b in buttons:
            mark = "x" if default_pick(b, state) else " "
            print(f"[{mark}] {b['kind']:<6} {b['key']:<44} {b['why']}")
        return
    if args.auto:
        save(args.root, buttons, [b["key"] for b in buttons if default_pick(b, state)], state)
        return
    serve_picker(args.root, buttons, state, likes_me, not args.no_browser)


if __name__ == "__main__":
    main()
