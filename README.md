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

## common edits

**add a friend's button.** save it as `buttons/friends/<name>.png` (or `.gif`, both work).
then in `index.html`, find `ls friends`, copy one of the lines under it and change the link,
the image name and the alt text. if the image is missing, a little text button shows up instead.

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
