// 3hz.dev
// flavor switcher, clock, focus-follows-mouse, friend buttons, and the wallpaper.
(() => {
  const root = document.documentElement;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── catppuccin flavors ───────────────────────────── */

  const FLAVORS = ['mocha', 'macchiato', 'frappe', 'latte'];
  const PRETTY = { mocha: 'mocha', macchiato: 'macchiato', frappe: 'frappé', latte: 'latte' };
  let flavor = FLAVORS.includes(root.dataset.flavor) ? root.dataset.flavor : 'mocha';

  function setFlavor(f, save) {
    flavor = f;
    root.dataset.flavor = f;
    $$('#flavor-name, #fetch-flavor').forEach(el => { el.textContent = PRETTY[f]; });
    $('#flavor')?.setAttribute('aria-label', `catppuccin flavor: ${PRETTY[f]}. click to switch`);
    const base = getComputedStyle(root).getPropertyValue('--base').trim();
    $('meta[name="theme-color"]').setAttribute('content', base);
    if (save) { try { localStorage.setItem('flavor', f); } catch (e) {} }
    wall.build();
  }
  const nextFlavor = () => setFlavor(FLAVORS[(FLAVORS.indexOf(flavor) + 1) % FLAVORS.length], true);
  $('#flavor')?.addEventListener('click', nextFlavor);

  /* ── clock (my time, not yours) ───────────────────── */

  const clockFmt = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Chicago', weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  });
  function tick() {
    const p = Object.fromEntries(clockFmt.formatToParts(new Date()).map(x => [x.type, x.value]));
    const el = $('#clock');
    if (!el) return;
    el.innerHTML = `<span class="day">${p.weekday.toLowerCase()}</span> ${p.hour}:${p.minute}`;
    el.setAttribute('datetime', `${p.hour}:${p.minute}`);
  }
  tick();
  setInterval(tick, 15000);

  /* ── windows: focus follows mouse ─────────────────── */

  const wins = $$('.win');
  const barTitle = $('#bar-title');
  const WS = { fetch: 'fetch', links: 'fetch', about: 'about', now: 'about', projects: 'projects', writing: 'writing', friends: 'friends', man: 'man' };
  let focused = null;
  let hovered = null;

  function focus(win) {
    if (!win || win === focused) return;
    focused?.classList.remove('is-focused');
    win.classList.add('is-focused');
    focused = win;
    if (barTitle) barTitle.textContent = win.dataset.title;
    const ws = WS[win.id];
    $$('.ws a').forEach(a => a.setAttribute('aria-current', a.dataset.ws === ws ? 'true' : 'false'));
  }

  wins.forEach(w => {
    w.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') { hovered = w; focus(w); } });
    w.addEventListener('pointerleave', () => { if (hovered === w) hovered = null; });
    w.addEventListener('focusin', () => focus(w));
  });

  // when scrolling (or on touch), focus whatever sits under a line 40% down the screen
  let scrollQueued = false;
  addEventListener('scroll', () => {
    if (scrollQueued) return;
    scrollQueued = true;
    requestAnimationFrame(() => {
      scrollQueued = false;
      if (hovered) return;
      const y = innerHeight * 0.4;
      focus(wins.find(w => { const r = w.getBoundingClientRect(); return r.top <= y && r.bottom >= y; }));
    });
  }, { passive: true });
  focus($('#fetch') || wins[0]);

  // super+1..6, minus the super
  const wsLinks = $$('.ws a');
  document.addEventListener('keydown', e => {
    if (e.ctrlKey || e.metaKey || e.altKey || e.target.closest('input, textarea, [contenteditable]')) return;
    const n = parseInt(e.key, 10);
    if (n >= 1 && n <= wsLinks.length) {
      const win = document.getElementById(wsLinks[n - 1].dataset.ws);
      if (!win) { location.href = wsLinks[n - 1].href; return; }
      win.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
      focus(win);
    } else if (e.key === 't') {
      nextFlavor();
    }
  });

  /* ── friends' 88x31s ──────────────────────────────── */
  // tries name.png, then name.gif, then gives up and draws a little text button

  function textButton(img) {
    const alt = img.alt;
    const dot = alt.indexOf('.');
    const span = document.createElement('span');
    span.className = 'btn-fallback';
    span.title = alt;
    const b = document.createElement('b');
    b.textContent = dot > 0 ? alt.slice(0, dot) : alt;
    const small = document.createElement('small');
    small.textContent = dot > 0 ? alt.slice(dot) : '~';
    span.append(b, small);
    img.replaceWith(span);
  }
  function onButtonError(img) {
    if (/\.png$/.test(img.src) && !img.dataset.triedGif) {
      img.dataset.triedGif = '1';
      img.src = img.src.replace(/\.png$/, '.gif');
    } else {
      textButton(img);
    }
  }
  $$('.buttons img').forEach(img => {
    img.addEventListener('error', () => onButtonError(img));
    if (img.complete && img.naturalWidth === 0) onButtonError(img);
  });

  /* ── copy the link-to-me snippet ──────────────────── */

  $$('.copy').forEach(btn => btn.addEventListener('click', async () => {
    const src = document.getElementById(btn.dataset.copy);
    try {
      await navigator.clipboard.writeText(src.textContent);
      btn.textContent = 'copied';
      btn.classList.add('done');
    } catch (e) {
      getSelection().selectAllChildren(src);
      btn.textContent = 'ctrl+c';
    }
    setTimeout(() => { btn.textContent = 'copy'; btn.classList.remove('done'); }, 1600);
  }));

  /* ── wallpaper ────────────────────────────────────── */
  // a prairie at night, drawn at low res and scaled up. a kestrel hovers over
  // the field and another one sits on the power line. colors come from the
  // current flavor so it re-themes with everything else.

  const wall = (() => {
    const canvas = $('#wall');
    const ctx = canvas.getContext('2d');
    const bg = document.createElement('canvas');
    const bgx = bg.getContext('2d');
    let W = 0, H = 0, P = {}, stars = [], hover = null, timer = 0;

    const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map(v => (v + 0.5) / 16);
    const HOVER = [
      ['#...........#', '##.........##', '.##.......##.', '..###.#.###..', '....#####....', '.....###.....', '.....###.....', '....##.##....'],
      ['.............', '.............', '......#......', '#############', '##..#####..##', '.....###.....', '.....###.....', '....##.##....'],
      ['.............', '.............', '......#......', '...#######...', '..##.###.##..', '.##..###..##.', '##..##.##..##', '.............'],
    ];
    const FLAP = [0, 1, 2, 1];
    const PERCH = ['.##..', '###..', '.###.', '.###.', '.####', '..###', '...#.', '...#.'];

    const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
    const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
    const css = c => `rgb(${c[0]},${c[1]},${c[2]})`;
    function rng(seed) {
      return () => {
        seed |= 0; seed = seed + 0x6d2b79f5 | 0;
        let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
        t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
      };
    }

    function sprite(g, rows, x0, y0, color) {
      g.fillStyle = css(color);
      rows.forEach((r, y) => { for (let x = 0; x < r.length; x++) if (r[x] === '#') g.fillRect(x0 + x, y0 + y, 1, 1); });
    }

    function build() {
      const cs = getComputedStyle(root);
      ['crust', 'mantle', 'base', 'surface0', 'surface1', 'surface2', 'overlay0', 'overlay1', 'overlay2', 'text', 'lavender', 'mauve', 'rosewater', 'blue']
        .forEach(k => { P[k] = hex(cs.getPropertyValue('--' + k).trim()); });
      const light = flavor === 'latte';

      const scale = innerWidth < 720 ? 3 : 4;
      W = Math.ceil(innerWidth / scale);
      H = Math.ceil(Math.max(innerHeight, canvas.clientHeight || 0) / scale);
      canvas.width = bg.width = W;
      canvas.height = bg.height = H;

      const rand = rng(3);
      const img = bgx.createImageData(W, H);
      const d = img.data;
      const put = (x, y, c) => { const i = (y * W + x) * 4; d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = 255; };

      // sky: dithered gradient that warms up toward the horizon
      const horizon = Math.round(H * 0.8);
      const glow = mix(P.base, P.mauve, light ? 0.12 : 0.2);
      const half = mix(P.base, glow, 0.5);
      const stops = light
        ? [[0, P.crust], [0.55, P.mantle], [0.85, P.base], [0.93, half], [1, glow]]
        : [[0, P.crust], [0.45, P.mantle], [0.78, P.base], [0.9, half], [1, glow]];
      for (let y = 0; y < H; y++) {
        const t = Math.min(y / horizon, 1);
        let s = 0;
        while (s < stops.length - 2 && t > stops[s + 1][0]) s++;
        const [p0, c0] = stops[s], [p1, c1] = stops[s + 1];
        const k = (t - p0) / (p1 - p0);
        for (let x = 0; x < W; x++) put(x, y, k > BAYER[(y & 3) * 4 + (x & 3)] ? c1 : c0);
      }

      // hills. the far treeline is scalloped, the field in front is flat-ish (it's illinois)
      const ph = [rand() * 9, rand() * 9, rand() * 9, rand() * 9];
      const far = mix(P.surface0, P.base, 0.25);
      const mid = light ? P.surface0 : P.mantle;
      const near = light ? P.surface1 : P.crust;
      const farY = x => horizon - 4 - Math.round(Math.sin(x * 0.011 + ph[0]) * 4 + Math.sin(x * 0.037 + ph[1]) * 2 + Math.abs(Math.sin(x * 0.29 + ph[2])) * 3);
      const midY = x => horizon + 3 + Math.round(Math.sin(x * 0.008 + ph[3]) * 2);
      const nearY = x => Math.round(H * 0.93 + Math.sin(x * 0.02 + ph[1]) * 2);
      for (let x = 0; x < W; x++) {
        for (let y = Math.max(farY(x), 0); y < H; y++) put(x, y, far);
        for (let y = midY(x); y < H; y++) put(x, y, mid);
        for (let y = nearY(x); y < H; y++) put(x, y, near);
      }
      // grass tufts on the near field
      for (let x = 0; x < W; x++) {
        if (rand() < 0.45) {
          const h = 1 + Math.floor(rand() * 3);
          for (let k = 1; k <= h; k++) if (nearY(x) - k >= 0) put(x, nearY(x) - k, near);
        }
      }
      bgx.putImageData(img, 0, 0);

      // power line: poles every so often, two sagging wires between them
      const ink = light ? P.overlay0 : P.crust;
      const wireC = light ? mix(P.surface0, P.surface1, 0.4) : mix(P.crust, P.surface0, 0.6);
      const gapX = 110, poleH = 30;
      const poles = [];
      for (let x = 14 - Math.round(ph[0] * 6); x < W + gapX; x += gapX) poles.push(x);
      bgx.fillStyle = css(ink);
      poles.forEach(x => {
        const g = midY(x);
        bgx.fillRect(x, g - poleH, 2, poleH);
        bgx.fillRect(x - 5, g - poleH + 2, 12, 1);
        bgx.fillRect(x - 5, g - poleH + 1, 1, 1);
        bgx.fillRect(x + 6, g - poleH + 1, 1, 1);
      });
      const wire = [];
      bgx.fillStyle = css(wireC);
      for (let i = 0; i < poles.length - 1; i++) {
        const a = poles[i], b = poles[i + 1];
        for (const off of [-5, 6]) {
          const ya = midY(a) - poleH + 1, yb = midY(b) - poleH + 1;
          for (let x = a + off; x < b + off; x++) {
            const u = (x - a - off) / gapX;
            const y = Math.round(ya + (yb - ya) * u + 5 * 4 * u * (1 - u));
            bgx.fillRect(x, y, 1, 1);
            if (off === 6) wire[x] = y;
          }
        }
      }
      // birds go in the side margins when there's room, so the windows don't cover them
      const margin = (innerWidth - 1200) / 2 / scale;
      const roomy = margin > 22;

      // someone's sitting on the wire, near the right edge
      const px = roomy ? Math.round(W - margin / 2) : Math.max(20, W - 34);
      if (wire[px] != null) sprite(bgx, PERCH, px - 2, wire[px] - 6, ink);

      // moon
      if (!light) {
        const mx = W - 30, my = Math.round(H * 0.16), r = 6;
        bgx.fillStyle = css(P.rosewater);
        for (let y = -r; y <= r; y++) for (let x = -r; x <= r; x++) {
          if (x * x + y * y <= r * r + 2 && (x + 3) * (x + 3) + (y - 1) * (y - 1) > r * r) bgx.fillRect(mx + x, my + y, 1, 1);
        }
      }

      // stars (static ones go on the background, twinklers get drawn each frame)
      stars = [];
      if (!light) {
        const n = Math.round(W * horizon / 240);
        for (let i = 0; i < n; i++) {
          const x = Math.floor(rand() * W), y = Math.floor(Math.pow(rand(), 1.4) * horizon * 0.72);
          const roll = rand();
          const c = roll < 0.08 ? P.lavender : roll < 0.3 ? P.overlay1 : P.surface2;
          if (rand() < 0.25) stars.push({ x, y, c, p: rand() * 6.28, s: 0.6 + rand() * 1.4 });
          else { bgx.fillStyle = css(c); bgx.fillRect(x, y, 1, 1); }
        }
      }

      // the one that hovers, low over the field on the left
      hover = { x: roomy ? Math.round(margin / 2 - 6) : Math.round(W * 0.12), y: horizon - 26, c: ink };
      draw(performance.now());
    }

    function draw(t) {
      ctx.drawImage(bg, 0, 0);
      stars.forEach(s => {
        const v = (Math.sin(t / 1000 * s.s + s.p) + 1) / 2;
        ctx.fillStyle = css(mix(P.surface1, s.c === P.surface2 ? P.overlay2 : P.text, v));
        ctx.fillRect(s.x, s.y, 1, 1);
      });
      if (hover) sprite(ctx, HOVER[FLAP[Math.floor(t / 90) % FLAP.length]], hover.x, hover.y, hover.c);
    }

    function loop(t) {
      if (t - loop.last > 90) { draw(t); loop.last = t; }
      timer = requestAnimationFrame(loop);
    }
    loop.last = 0;

    function start() { if (!reduceMotion && !timer) timer = requestAnimationFrame(loop); }
    function stop() { cancelAnimationFrame(timer); timer = 0; }
    document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));

    let resizeT;
    addEventListener('resize', () => {
      clearTimeout(resizeT);
      resizeT = setTimeout(() => {
        const w = Math.ceil(innerWidth / (innerWidth < 720 ? 3 : 4));
        if (w !== W || Math.abs(innerHeight - canvas.clientHeight) > 120) build();
      }, 150);
    });

    return { build, start };
  })();

  setFlavor(flavor, false);
  wall.start();
})();
