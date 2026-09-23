# 3hz.dev

my corner of the internet. plain html, css and js. no framework, no build step.

## where things live

| file | what's in it |
| --- | --- |
| `index.html` | the whole homepage. every window is a `<section class="win">` |
| `assets/css/style.css` | catppuccin palettes (top of the file), the bar, windows, layout |
| `assets/js/main.js` | flavor switcher, clock, focus-follows-mouse, friend buttons, the wallpaper |
| `buttons/3hz.gif`, `buttons/3hz.png` | my 88x31 |
| `buttons/friends/` | everyone else's 88x31s |
| `_tools/button.py` | redraws my button and the favicons |
| `404.html` | for when the kestrel can't find something |

## friends' buttons

```sh
python3 _tools/grab_buttons.py
```

visits everyone in `FRIENDS` (top of the script), plus their links/buttons pages, and finds
every 88x31. it sorts them into your friends, people your friends link to, and stuff that
isn't a person (distros, browsers, causes, "made with" badges, repos). then a page opens in
your browser with the people ticked. untick anyone you don't want, hit save, and it drops
the images in `buttons/friends/` and rewrites the list in `index.html`.

- your picks are remembered in `_tools/buttons.json`, so running it again later only really
  asks about new buttons
- `--dry-run` just lists what it found, `--auto` skips the picker and takes the defaults
- `--drop KEY` / `--keep KEY` untick or tick specific buttons without the picker. the keys
  are in the `--dry-run` list (like `int4.cc` or `girlthi.ng/~thermia`)
- if a friend's site is down when you run it, the button you already saved for them stays
- if a friend doesn't have a button yet, they get a little text one. the script tells you
  what filename to use if you get one later
- on macOS, if it says ssl error: run the `Install Certificates.command` that came with
  python, or `pip3 install certifi`
- to add one by hand: drop the image in `buttons/friends/` and copy a line between the
  `buttons:start` / `buttons:end` comments

## keeping it fresh

stuff that goes out of date when life changes. `grep -n 2026 index.html` finds most dates.

- **job:** the `work` line in fetch, line 3 of about.md, and DESCRIPTION + STATUS in the man page
- **~/.now:** the four lines, plus the month in its title bar (`sep 2026`)
- **man page:** the date in its footer line
- **projects:** the dates and the pz-server-manager release count update themselves from
  github (cached an hour per visitor). the descriptions and the list itself don't

## common edits

**update ~/.now.** it's the `now` window in `index.html`, a list of `<dt>`/`<dd>` pairs.

**projects.** each one is an `<li>` inside `ls -l projects`. the four spans are
permissions (decoration), name, languages, and a tag. the description goes in `ls-desc`.

**change the layout.** on wide screens the windows are placed with `grid-template-areas`
near the bottom of `style.css`. each word is a column in a 12-column grid, so
`fetch fetch fetch fetch fetch fetch fetch links links links links links` = 7/5 split.

**colors.** use the variables (`var(--mauve)`, `var(--surface0)`, etc.) and it'll follow
whichever flavor someone picks. `--dim` is for secondary text.

**redraw the button / favicons.**

```sh
pip install pillow
python3 _tools/button.py
```

folders starting with `_` don't get published by github pages, so `_tools/` stays off the site.

## preview locally

```sh
python3 -m http.server
# then open http://localhost:8000
```

or just double-click `index.html`. the 404 page needs the server.

## keys

`1`-`6` jump between workspaces, `t` cycles the catppuccin flavor.

## credits

- colors: [catppuccin](https://catppuccin.com) (MIT)
- fonts: [iosevka](https://typeof.net/Iosevka/) and [silkscreen](https://kottke.org/plus/type/silkscreen/), both SIL OFL, see `assets/fonts/LICENSE.txt`
- icons: [tabler icons](https://tabler.io/icons) (MIT)
