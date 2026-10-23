"""Generates the animated SVGs used by the profile README.

Usage:  pip install fonttools brotli && python scripts/build.py

Every SVG embeds a subset of its fonts, so it renders identically everywhere
(GitHub serves README images as <img>, which can't load external fonts).
Each graphic is generated in a dark and a light variant; the README picks one
with <picture> based on the viewer's GitHub theme.
"""
import base64
import io
import math
import random
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
OUT = ROOT / "assets"

THEMES = {
    "dark": dict(bg="#0b0b0c", bg2="#121214", bg3="#1a1a1d", fg="#ecebe6", fg2="#b9b8b1", muted="#7d7c76",
                 node="236,235,230", hot="212,255,58", accent="#d4ff3a", accent_text="#d4ff3a", ink="#0b0b0c",
                 warn="255,92,60"),
    "light": dict(bg="#f3f1ea", bg2="#ebe8df", bg3="#e2ded3", fg="#111110", fg2="#3b3a36", muted="#74726b",
                  node="17,17,16", hot="80,130,0", accent="#c5f02c", accent_text="#3f6a00", ink="#111110",
                  warn="214,64,32"),
}

FONT_FILES = {
    "Grotesk": ("SpaceGrotesk.woff2", "300 700", "normal"),
    "Mono": ("JetBrainsMono.woff2", "500", "normal"),
    "Serif": ("InstrumentSerif-Italic.woff2", "400", "italic"),
    "Deva": ("NotoDeva.woff2", "600", "normal"),
}
SANS = "font-family:Grotesk,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "font-family:Mono,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
SERIF = "font-family:Serif,Georgia,serif;font-style:italic"


# ---------------------------------------------------------------- fonts & text

_metrics = {}


def _font_metrics(name):
    if name not in _metrics:
        f = TTFont(FONTS / FONT_FILES[name][0])
        _metrics[name] = (f.getBestCmap(), f["hmtx"].metrics, f["head"].unitsPerEm)
    return _metrics[name]


def text_width(text, size, font="Grotesk", tracking=0.0, weight=400):
    cmap, hmtx, upm = _font_metrics(font)
    units = sum(hmtx.get(cmap.get(ord(ch), ".notdef"), (upm * 0.55, 0))[0] for ch in text)
    bold = 1 + max(0, weight - 400) / 300 * 0.05 if font == "Grotesk" else 1
    return units / upm * size * bold + tracking * size * len(text)


def font_faces(svg_text):
    """@font-face rules with each font subset to the characters used in the SVG."""
    import re
    chars = "".join(set(re.sub(r"<[^>]+>", "", svg_text)))
    chars = escape_chars = chars.replace("&amp;", "&")
    rules = []
    for name, (file, weight, style) in FONT_FILES.items():
        if name == "Deva":
            if not any("ऀ" <= c <= "ॿ" for c in chars):
                continue
            data = (FONTS / file).read_bytes()
        else:
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga"]
            font = subset.load_font(str(FONTS / file), opts)
            sub = subset.Subsetter(opts)
            sub.populate(text=escape_chars + "&" + " ")
            sub.subset(font)
            buf = io.BytesIO()
            subset.save_font(font, buf, opts)
            data = buf.getvalue()
        b64 = base64.b64encode(data).decode()
        rules.append(f"@font-face{{font-family:{name};src:url(data:font/woff2;base64,{b64}) format('woff2');"
                     f"font-weight:{weight};font-style:{style}}}")
    return "".join(rules)


def svg(w, h, body, css, title, desc=""):
    inner = (f'<title id="t">{escape(title)}</title><desc id="d">{escape(desc)}</desc>'
             f"<style>{{FONTS}}{css}"
             "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>" + body)
    inner = inner.replace("{FONTS}", font_faces(body))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-labelledby="t d">{inner}</svg>')


def T(x, y, s, size, fill, style=SANS, weight=400, anchor="start", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}" style="{style}" {extra}>{s}</text>')


def rgba(triplet, a):
    return f"rgba({triplet},{a:.3f})"


# ---------------------------------------------------------------- header banner

def neural_field(t, w, h, seed=7, count=58, link=150):
    rnd = random.Random(seed)
    nodes = [(rnd.uniform(10, w - 10), rnd.uniform(10, h - 10)) for _ in range(count)]
    out = ['<g class="net">']
    neigh = {i: [] for i in range(count)}
    for i, (ax, ay) in enumerate(nodes):
        for j in range(i + 1, count):
            bx, by = nodes[j]
            d = math.hypot(ax - bx, ay - by)
            if d < link:
                neigh[i].append(j)
                neigh[j].append(i)
                out.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
                           f'stroke="{rgba(t["node"], (1 - d / link) * 0.16)}"/>')
    for i, (x, y) in enumerate(nodes):
        delay = rnd.uniform(0, 6)
        out.append(f'<circle class="n" cx="{x:.1f}" cy="{y:.1f}" r="1.8" style="animation-delay:{delay:.2f}s"/>')

    # signals: chains of hops that light up as a pulse travels through them
    sigs = []
    for k in range(9):
        cur = rnd.randrange(count)
        path = [cur]
        for _ in range(5):
            options = [n for n in neigh[cur] if n not in path]
            if not options:
                break
            cur = rnd.choice(options)
            path.append(cur)
        if len(path) < 3:
            continue
        pts = [nodes[p] for p in path]
        length = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
        d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        dur = 6.0
        begin = k * 0.85
        sigs.append(
            f'<path d="{d}" class="trail" style="stroke-dasharray:70 {length + 200:.0f};'
            f'--len:{-length:.0f}px;animation-delay:{begin:.2f}s"/>'
            f'<circle r="3.2" class="sig" style="animation-delay:{begin:.2f}s">'
            f'<animateMotion dur="{dur}s" begin="{begin:.2f}s" repeatCount="indefinite" path="{d}" '
            f'keyPoints="0;1;1" keyTimes="0;0.45;1" calcMode="linear"/></circle>')
        for (x, y), frac in zip(pts, [i / (len(pts) - 1) * 0.45 for i in range(len(pts))]):
            sigs.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" class="halo" '
                        f'style="animation-delay:{begin + frac * dur:.2f}s"/>')
    out.extend(sigs)
    out.append("</g>")
    return "".join(out)


def header(theme):
    t = THEMES[theme]
    W, H = 1200, 470
    css = f"""
.n{{fill:{rgba(t['node'], .45)};animation:twinkle 6s ease-in-out infinite}}
@keyframes twinkle{{0%,100%{{fill:{rgba(t['node'], .4)}}}50%{{fill:{rgba(t['node'], .7)}}}}}
.trail{{fill:none;stroke:{rgba(t['hot'], .85)};stroke-width:1.6;stroke-linecap:round;stroke-dashoffset:70px;
  animation:travel 6s linear infinite}}
@keyframes travel{{0%{{stroke-dashoffset:70px}}45%,100%{{stroke-dashoffset:var(--len)}}}}
.sig{{fill:{rgba(t['hot'], 1)};opacity:0;animation:sig 6s linear infinite}}
@keyframes sig{{0%,44%{{opacity:1}}45%,100%{{opacity:0}}}}
.halo{{fill:{rgba(t['hot'], .22)};opacity:0;animation:halo 6s ease-out infinite}}
@keyframes halo{{0%{{opacity:1}}12%,100%{{opacity:0}}}}
.up{{animation:up 1.1s cubic-bezier(.22,1,.36,1) both}}
.up2{{animation-delay:.12s}}
@keyframes up{{from{{transform:translateY(160px)}}to{{transform:none}}}}
.fade{{animation:fade 1s ease .5s both}}
@keyframes fade{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}
.ping{{animation:ping 2s ease-out infinite;transform-box:fill-box;transform-origin:center}}
@keyframes ping{{0%{{opacity:.7;transform:scale(1)}}80%,100%{{opacity:0;transform:scale(3)}}}}
.role{{opacity:0;animation:role 15s infinite}}
@keyframes role{{0%{{opacity:0;transform:translateY(8px)}}3%,18%{{opacity:1;transform:none}}21%,100%{{opacity:0;transform:translateY(-8px)}}}}
.caret{{animation:blink 1s steps(1) infinite}}
@keyframes blink{{50%{{opacity:0}}}}
"""
    b = [f'<rect width="{W}" height="{H}" rx="22" fill="{t["bg"]}"/>',
         f'<clipPath id="card"><rect width="{W}" height="{H}" rx="22"/></clipPath><g clip-path="url(#card)">',
         neural_field(t, W, H),
         f'<rect y="{H - 150}" width="{W}" height="150" fill="url(#fadeb)"/>',
         f'<linearGradient id="fadeb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["bg"]}" stop-opacity="0"/>'
         f'<stop offset="1" stop-color="{t["bg"]}" stop-opacity=".92"/></linearGradient>']

    # meta row
    b.append(T(56, 62, "[ SOFTWARE &amp; AI ENGINEER ]", 15, t["fg2"], MONO, 500))
    b.append(T(600, 62, "SINGAPORE · UTC+8", 15, t["fg2"], MONO, 500, "middle"))
    status = "Open to SWE &amp; AI roles"
    sw = text_width("Open to SWE & AI roles", 15, "Mono")
    dx = W - 56 - sw - 16
    b.append(f'<circle cx="{dx:.1f}" cy="57" r="5" fill="{t["accent"]}"/>'
             f'<circle cx="{dx:.1f}" cy="57" r="5" fill="{t["accent"]}" class="ping"/>')
    b.append(T(W - 56, 62, status, 15, t["fg"], MONO, 500, "end"))

    # name
    size, track = 152, -0.06
    for i, (word, x, y) in enumerate([("RAYAAN", 50, 212), ("QURAISHI", 50 + 0.9 * size, 340)]):
        b.append(f'<clipPath id="l{i}"><rect x="0" y="{y - 130}" width="{W}" height="150"/></clipPath>')
        dot = f'<tspan fill="{t["accent"]}">.</tspan>' if i == 1 else ""
        b.append(f'<g clip-path="url(#l{i})"><g class="up{" up2" if i else ""}">'
                 + T(x, y, word + dot, size, t["fg"], SANS, 700, extra=f'letter-spacing="{track * size:.1f}"')
                 + "</g></g>")

    # lede
    acc = t["accent_text"]
    b.append('<g class="fade">')
    b.append(f'<text x="56" y="404" font-size="21" fill="{t["fg"]}" style="{SANS}">I build '
             f'<tspan style="{SERIF}" font-size="24" fill="{acc}">intelligent</tspan> software: production microservices,</text>')
    b.append(f'<text x="56" y="436" font-size="21" fill="{t["fg"]}" style="{SANS}">RAG pipelines and LLM agents that turn messy data into '
             f'<tspan style="{SERIF}" font-size="24" fill="{acc}">decisions</tspan>.</text>')
    lede_end = 56 + text_width("RAG pipelines and LLM agents that turn messy data into ", 21) + text_width("decisions.", 24, "Serif")
    # rotating "currently" line, aligned so the longest role ends at the right margin
    roles = ["SWE Intern @ BIOTRONIK", "MComp AI @ NUS", "building microservices", "shipping LLM agents",
             "AWS Certified Developer"]
    cx = W - 56 - text_width("currently → " + max(roles, key=len) + "_", 15, "Mono")
    assert lede_end < cx - 24, f"lede ({lede_end:.0f}) collides with right column ({cx:.0f})"
    b.append(T(cx, 404, "currently →", 15, t["muted"], MONO, 500))
    rx = cx + text_width("currently → ", 15, "Mono")
    for i, r in enumerate(roles):
        b.append(f'<g class="role" style="animation-delay:{i * 3}s">'
                 + T(rx, 404, escape(r) + f'<tspan class="caret" fill="{acc}">_</tspan>', 15, t["fg"], MONO, 500)
                 + "</g>")
    b.append(T(cx, 436, "rayaanq.github.io/Portfolio ↗", 15, acc, MONO, 500))
    b.append("</g></g>")
    return svg(W, H, "".join(b), css, "Rayaan Quraishi — Software & AI Engineer",
               "Animated banner: a neural network with signals travelling between nodes behind the name Rayaan Quraishi. "
               "Software & AI Engineer in Singapore, open to Software Development and AI Engineering roles.")


# ---------------------------------------------------------------- project cards

CARDS = [
    dict(id="crisis", meta="01 · 2026 · ML FORECASTING", title="Community Crisis Predictor",
         desc=["Forecasts mental-health crises on Reddit a week", "ahead with an LSTM over language and topic drift."],
         tags=["PyTorch", "XGBoost", "BERTopic", "SHAP"]),
    dict(id="summarizer", meta="02 · 2025 · GENAI · CHROME EXTENSION", title="AI Web Page Summarizer",
         desc=["Summarize and chat with any page, including PDFs,", "images (OCR) and YouTube, grounded by RAG."],
         tags=["LangChain", "RAG", "FastAPI", "Docker"]),
    dict(id="juristrack", meta="03 · 2025 · HACKATHON · REGTECH", title="JurisTrack — Compliance Radar",
         desc=["Flags region-specific legal risk in feature specs", "and links every flag to the clause behind it."],
         tags=["Gemini", "TF-IDF", "FastAPI", "React"]),
    dict(id="lingoleap", meta="04 · 2024 · EDTECH · ACCESSIBILITY", title="LingoLeap — Speech Therapy",
         desc=["Gamified pronunciation practice for children", "with misarticulation in Hindi-speaking homes."],
         tags=["Next.js", "Node.js", "MongoDB", "Speech AI"]),
]
CW, CH, VH = 600, 400, 212


def viz_crisis(t):
    css = (".bar{transform-box:fill-box;transform-origin:50% 100%;animation:grow var(--d) ease-in-out infinite alternate}"
           "@keyframes grow{from{transform:scaleY(var(--a))}to{transform:scaleY(1)}}")
    rnd = random.Random(3)
    vals, v = [], 0.3
    for _ in range(24):
        v = min(0.95, max(0.12, v + rnd.uniform(-0.16, 0.2)))
        vals.append(v)
    vals[-4:] = [0.66, 0.74, 0.7, 0.8]
    x0, top, base, n = 30, 30, 172, 24
    bw = (CW - 60) / n
    fx = x0 + bw * (n - 4)
    out = [f'<rect x="{fx:.1f}" y="{top}" width="{CW - 30 - fx:.1f}" height="{base - top}" fill="{rgba(t["hot"], .07)}"/>',
           f'<line x1="{fx:.1f}" y1="{top}" x2="{fx:.1f}" y2="{base}" stroke="{rgba(t["hot"], .7)}" stroke-dasharray="3 4"/>',
           T(fx + 8, top + 14, "FORECAST →", 11, t["accent_text"], MONO, 500)]
    for s in (1, 2, 3):
        y = base - (base - top) * (0.2 + s * 0.2)
        out.append(f'<line x1="30" y1="{y:.1f}" x2="{CW - 30}" y2="{y:.1f}" stroke="{rgba(t["node"], .07)}"/>')
    for i, v in enumerate(vals):
        h = v * (base - top)
        st = 0 if v < .4 else 1 if v < .6 else 2 if v < .8 else 3
        a = [0.2, 0.38, 0.68, 1][st]
        col = rgba(t["hot"], a) if st >= 2 else rgba(t["node"], a)
        x = x0 + i * bw + 2
        style = f'--d:{2.2 + (i * 7 % 10) / 6:.2f}s;--a:{0.72 + (i * 13 % 20) / 100:.2f};animation-delay:-{i * 0.37 % 3:.2f}s'
        if i >= n - 4:
            out.append(f'<rect class="bar" style="{style}" x="{x + .5:.1f}" y="{base - h:.1f}" width="{bw - 5:.1f}" '
                       f'height="{h:.1f}" fill="none" stroke="{rgba(t["hot"], .85)}" stroke-dasharray="3 3"/>')
        else:
            out.append(f'<rect class="bar" style="{style}" x="{x:.1f}" y="{base - h:.1f}" width="{bw - 4:.1f}" '
                       f'height="{h:.1f}" fill="{col}"/>')
    out += [T(30, 198, "NEXT WEEK", 11, t["muted"], MONO, 500),
            T(108, 198, "STATE 2 · ELEVATED", 12, t["accent_text"], MONO, 500),
            T(CW - 30, 198, "LSTM · 8-WEEK WINDOW", 11, t["muted"], MONO, 500, "end")]
    return css, "".join(out)


def viz_summarizer(t):
    css = (".scan{animation:scan 3.4s linear infinite}"
           "@keyframes scan{from{transform:translateY(0)}to{transform:translateY(132px)}}"
           ".fly{opacity:0;animation:fly 2.4s ease-in infinite}"
           "@keyframes fly{0%{opacity:0}10%,80%{opacity:1}100%{opacity:0}}")
    px, py, pw, ph = 30, 22, 172, 170
    out = [f'<rect x="{px + .5}" y="{py + .5}" width="{pw}" height="{ph}" rx="4" fill="none" stroke="{rgba(t["node"], .25)}"/>',
           f'<rect x="{px + 1}" y="{py + 1}" width="{pw - 1}" height="16" fill="{rgba(t["node"], .1)}"/>']
    y = py + 30
    for i in range(12):
        if i == 3:
            out.append(f'<rect x="{px + 12}" y="{y}" width="{pw - 24}" height="34" fill="{rgba(t["node"], .12)}"/>'
                       + T(px + 18, y + 21, "IMG · OCR", 9, t["muted"], MONO, 500))
            y += 44
            continue
        if i == 7:
            out.append(f'<rect x="{px + 12}" y="{y}" width="{pw - 24}" height="30" fill="{rgba(t["node"], .12)}"/>'
                       f'<path d="M{px + pw / 2 - 5} {y + 9} l12 6 l-12 6z" fill="{rgba(t["node"], .5)}"/>')
            y += 40
            continue
        if y > py + ph - 10:
            break
        lw = (pw - 24) * (0.55 + (i * 37 % 40) / 100)
        out.append(f'<rect x="{px + 12}" y="{y}" width="{lw:.1f}" height="4" fill="{rgba(t["node"], .22)}"/>')
        y += 11
    out.append(f'<linearGradient id="sg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{rgba(t["hot"], 0)}"/>'
               f'<stop offset="1" stop-color="{rgba(t["hot"], .4)}"/></linearGradient>'
               f'<g class="scan"><rect x="{px + 1}" y="{py + 6}" width="{pw - 1}" height="26" fill="url(#sg)"/>'
               f'<rect x="{px + 1}" y="{py + 31}" width="{pw - 1}" height="1.6" fill="{rgba(t["hot"], .95)}"/></g>')
    bx, by, bw, bh = 236, 22, CW - 30 - 236, 170
    for k in range(6):
        sy = py + 40 + k * 22
        d = f"M{px + pw} {sy} Q {(px + pw + bx) / 2} {sy - 40} {bx + 4} {by + 50 + (k * 17) % 70}"
        out.append(f'<rect width="3" height="3" class="fly" fill="{rgba(t["hot"], .95)}" style="animation-delay:{k * .4:.1f}s">'
                   f'<animateMotion dur="2.4s" begin="{k * .4:.1f}s" repeatCount="indefinite" path="{d}"/></rect>')
    out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="12" fill="{t["bg3"]}"/>')
    out.append(T(bx + 16, by + 24, "✦ SUMMARY", 11, t["accent_text"], MONO, 500))
    lines = ["• RAG grounds every answer in sources", "• PDF p.3 → pricing table extracted", "• Video 02:14 → live API demo"]
    for i, line in enumerate(lines):
        yy = by + 50 + i * 24
        tw = text_width(line, 14) + 6
        b0, b1 = i / 3 * 0.55, (i + 1) / 3 * 0.55
        out.append(f'<clipPath id="tl{i}"><rect x="{bx + 14}" y="{yy - 14}" height="20" width="0">'
                   f'<animate attributeName="width" dur="7s" repeatCount="indefinite" calcMode="linear" '
                   f'values="0;0;{tw:.0f};{tw:.0f};0" keyTimes="0;{b0:.3f};{b1:.3f};0.93;1"/></rect></clipPath>'
                   f'<g clip-path="url(#tl{i})">' + T(bx + 16, yy, escape(line), 14, t["fg2"]) + "</g>")
    iy = by + bh - 44
    out.append(f'<rect x="{bx + 12.5}" y="{iy + .5}" width="{bw - 25}" height="30" rx="15" fill="none" stroke="{rgba(t["node"], .2)}"/>'
               + T(bx + 28, iy + 20, "Ask a follow-up about this page…", 12, t["muted"])
               + f'<circle cx="{bx + bw - 30}" cy="{iy + 15.5}" r="10" fill="{t["accent"]}"/>'
               f'<path d="M{bx + bw - 30} {iy + 21}v-10m-4 4l4-4l4 4" stroke="{t["ink"]}" stroke-width="1.6" fill="none" '
               f'stroke-linecap="round" stroke-linejoin="round"/>')
    return css, "".join(out)


def viz_juristrack(t):
    cx, cy, R, period = 390, 106, 88, 4.0
    css = ""
    out = []
    for i in range(1, 5):
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{R * i / 4:.1f}" fill="none" stroke="{rgba(t["node"], .14)}"/>')
    for i in range(12):
        a = i / 12 * math.tau
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{cx + math.cos(a) * R:.1f}" y2="{cy + math.sin(a) * R:.1f}" '
                   f'stroke="{rgba(t["node"], .1)}"/>')
    wedge = []
    for i in range(16):
        a0, a1 = math.radians(-(i + 1) * 3.2), math.radians(-i * 3.2)
        wedge.append(f'<path d="M{cx} {cy} L{cx + math.cos(a0) * R:.1f} {cy + math.sin(a0) * R:.1f} '
                     f'A{R} {R} 0 0 1 {cx + math.cos(a1) * R:.1f} {cy + math.sin(a1) * R:.1f}Z" '
                     f'fill="{rgba(t["hot"], .26 * (1 - i / 16))}"/>')
    out.append(f'<g>{"".join(wedge)}<line x1="{cx}" y1="{cy}" x2="{cx + R}" y2="{cy}" stroke="{rgba(t["hot"], .95)}" '
               f'stroke-width="1.5"/><animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" '
               f'to="360 {cx} {cy}" dur="{period}s" repeatCount="indefinite"/></g>')
    blips = [(35, .58, "EU DSA", "HIGH"), (105, .78, "CCPA", "MED"), (165, .4, "UTAH", "HIGH"),
             (235, .68, "FLORIDA", "LOW"), (300, .5, "NCMEC", "HIGH")]
    for ang, r, label, risk in blips:
        a = math.radians(ang)
        x, y = cx + math.cos(a) * R * r, cy + math.sin(a) * R * r
        hot = risk == "HIGH"
        col = rgba(t["hot"], 1) if hot else rgba(t["node"], .85)
        begin = ang / 360 * period
        anim = (f'<animate attributeName="opacity" values="1;.18;.18" keyTimes="0;.7;1" dur="{period}s" '
                f'begin="{begin:.2f}s" repeatCount="indefinite"/>')
        lx = x + (12 if math.cos(a) >= -0.2 else -12)
        anchor = "start" if math.cos(a) >= -0.2 else "end"
        out.append(f'<g opacity=".18"><circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{col}"/>'
                   + T(lx, y - 7, f"{label} · {risk}", 10, t["accent_text"] if hot else t["fg2"], MONO, 500, anchor)
                   + anim + "</g>")
    out.append(T(30, 34, "GEO-COMPLIANCE RADAR", 11, t["muted"], MONO, 500))
    out.append(T(30, 52, "5 REGULATIONS · 3 FLAGGED", 11, t["accent_text"], MONO, 500))
    out.append(T(CW - 30, 198, "RISK 0–100 · EXPLAINABLE", 11, t["muted"], MONO, 500, "end"))
    return css, "".join(out)


def viz_lingoleap(t):
    css = (".lt{opacity:0;animation:lt 8s infinite}"
           "@keyframes lt{0%{opacity:0;transform:translateY(6px)}4%,22%{opacity:1;transform:none}26%,100%{opacity:0}}"
           ".wv{transform-box:fill-box;transform-origin:center;animation:wv var(--d) ease-in-out infinite alternate}"
           "@keyframes wv{from{transform:scaleY(.25)}to{transform:scaleY(1)}}"
           ".lit{animation:lit 2s linear infinite}"
           f"@keyframes lit{{0%{{fill:{rgba(t['hot'], .9)}}}50%,100%{{fill:{rgba(t['node'], .22)}}}}}"
           ".ring{animation:ring 2s cubic-bezier(.22,1,.36,1) infinite}"
           "@keyframes ring{from{stroke-dashoffset:138}to{stroke-dashoffset:25}}")
    out = []
    for i, ch in enumerate("कखगर"):
        out.append(f'<g class="lt" style="animation-delay:{i * 2}s">'
                   + T(CW / 2, 98, ch, 80, t["fg"], "font-family:Deva,'Nirmala UI','Kohinoor Devanagari',sans-serif", 600, "middle")
                   + "</g>")
    out.append(T(CW / 2, 122, "SAY IT OUT LOUD", 11, t["muted"], MONO, 500, "middle"))
    n, x0, cyw = 72, 34, 166
    step = (CW - 2 * x0) / n
    for i in range(n):
        env = math.sin(i / n * math.pi)
        h = 6 + env * 46 * (0.55 + 0.45 * abs(math.sin(i * 0.7)))
        out.append(f'<rect class="wv lit" x="{x0 + i * step:.1f}" y="{cyw - h / 2:.1f}" width="3" height="{h:.1f}" rx="1.5" '
                   f'style="--d:{0.5 + (i * 7 % 9) / 12:.2f}s;animation-delay:-{i * .05:.2f}s,{i / n * 1.0:.2f}s" '
                   f'fill="{rgba(t["node"], .22)}"/>')
    sx, sy = CW - 70, 52
    out.append(f'<circle cx="{sx}" cy="{sy}" r="22" fill="none" stroke="{rgba(t["node"], .12)}" stroke-width="4"/>'
               f'<circle class="ring" cx="{sx}" cy="{sy}" r="22" fill="none" stroke="{rgba(t["hot"], .95)}" stroke-width="4" '
               f'stroke-dasharray="138.2" stroke-linecap="round" transform="rotate(-90 {sx} {sy})"/>'
               + T(sx, sy + 5, "82", 14, t["fg"], SANS, 600, "middle"))
    out.append(T(30, 34, "LEVEL 3 · STREAK 7 ✦", 11, t["muted"], MONO, 500))
    return css, "".join(out)


VIZ = dict(crisis=viz_crisis, summarizer=viz_summarizer, juristrack=viz_juristrack, lingoleap=viz_lingoleap)


def chip_row(t, x, y, labels, size=13, pad=11, h=28, gap=8, font="Mono", fill=None, color=None):
    out = []
    for label in labels:
        w = text_width(label, size, font) + pad * 2
        out.append(f'<rect x="{x + .5:.1f}" y="{y + .5:.1f}" width="{w:.1f}" height="{h}" rx="{h / 2}" '
                   f'fill="{fill or "none"}" stroke="{rgba(t["node"], .16)}"/>'
                   + T(x + pad, y + h / 2 + size * 0.36, escape(label), size, color or t["fg2"],
                       MONO if font == "Mono" else SANS, 500))
        x += w + gap
    return "".join(out), x


def card(theme, c):
    t = THEMES[theme]
    vcss, vbody = VIZ[c["id"]](t)
    for line in c["desc"]:
        w = text_width(line, 18)
        assert w < CW - 56, f"{c['id']}: description line too long ({w:.0f}px): {line}"
    b = [f'<clipPath id="cc"><rect width="{CW}" height="{CH}" rx="18"/></clipPath>',
         f'<g clip-path="url(#cc)"><rect width="{CW}" height="{CH}" fill="{t["bg2"]}"/>',
         f'<rect width="{CW}" height="{VH}" fill="{t["bg"]}"/>', vbody,
         f'<line x1="0" y1="{VH + .5}" x2="{CW}" y2="{VH + .5}" stroke="{rgba(t["node"], .12)}"/>',
         T(28, VH + 36, escape(c["meta"]), 13, t["muted"], MONO, 500),
         T(28, VH + 74, escape(c["title"]), 30, t["fg"], SANS, 600, extra='letter-spacing="-1"'),
         T(28, VH + 106, escape(c["desc"][0]), 18, t["fg2"]),
         T(28, VH + 130, escape(c["desc"][1]), 18, t["fg2"])]
    chips, _ = chip_row(t, 28, VH + 146, c["tags"])
    b.append(chips)
    b.append(T(CW - 28, VH + 165, "→", 20, t["accent_text"], SANS, 600, "end"))
    b.append("</g>")
    b.append(f'<rect x=".5" y=".5" width="{CW - 1}" height="{CH - 1}" rx="18" fill="none" stroke="{rgba(t["node"], .14)}"/>')
    return svg(CW, CH, "".join(b), vcss, c["title"], " ".join(c["desc"]))


# ---------------------------------------------------------------- toolbox

TOOLBOX = [
    ("AI / ML", ["LangChain", "LLM Agents", "RAG", "PyTorch", "TensorFlow", "XGBoost", "BERTopic", "SHAP"]),
    ("LANGUAGES", ["Python", "Java", "C++", "JavaScript", "TypeScript", "SQL", "HTML / CSS"]),
    ("BACKEND & WEB", ["Spring Boot", "FastAPI", "Node.js", "Express", "React", "Next.js", "JUnit", "Mockito"]),
    ("CLOUD, DEVOPS & DATA", ["AWS", "Azure", "Docker", "Kubernetes", "GitHub Actions", "Grafana", "Hadoop",
                              "MongoDB", "MySQL", "SQLite", "Git"]),
]


def toolbox(theme):
    t = THEMES[theme]
    W, gap, cols = 1200, 16, 4
    cw = (W - gap * (cols - 1)) / cols
    size, ch, cg, pad = 15, 32, 8, 12
    layouts, heights, idx = [], [], 0
    for title, items in TOOLBOX:
        x, y, chips = 20, 62, []
        for it in items:
            w = text_width(it, size) + pad * 2
            if x + w > cw - 20:
                x, y = 20, y + ch + cg
            chips.append((x, y, w, it, idx))
            idx += 1
            x += w + cg
        layouts.append((title, chips))
        heights.append(y + ch + 22)
    H = int(max(heights))
    total = idx
    cycle = total * 0.55
    css = (f".chip{{fill:{t['bg3']};animation:chip {cycle:.1f}s linear infinite}}"
           f"@keyframes chip{{0%{{fill:{t['accent']}}}{100 / total * 1.4:.2f}%,100%{{fill:{t['bg3']}}}}}"
           f".chipt{{fill:{t['fg']};animation:chipt {cycle:.1f}s linear infinite}}"
           f"@keyframes chipt{{0%{{fill:{t['ink']}}}{100 / total * 1.4:.2f}%,100%{{fill:{t['fg']}}}}}"
           "")
    b = []
    for i, (title, chips) in enumerate(layouts):
        gx = i * (cw + gap)
        b.append(f'<g><g transform="translate({gx:.1f} 0)">'
                 f'<rect x=".5" y=".5" width="{cw - 1:.1f}" height="{H - 1}" rx="18" fill="{t["bg2"]}" stroke="{rgba(t["node"], .14)}"/>'
                 + T(20, 36, escape(title), 13, t["accent_text"], MONO, 500))
        for x, y, w, it, k in chips:
            delay = f"animation-delay:{k * 0.55:.2f}s"
            b.append(f'<rect class="chip" style="{delay}" x="{x:.1f}" y="{y}" width="{w:.1f}" height="{ch}" rx="8"/>'
                     f'<text class="chipt" style="{SANS};{delay}" x="{x + pad:.1f}" y="{y + ch / 2 + size * .36:.1f}" '
                     f'font-size="{size}">{escape(it)}</text>')
        b.append("</g></g>")
    return svg(W, H, "".join(b), css, "Toolbox",
               "; ".join(f"{title}: {', '.join(items)}" for title, items in TOOLBOX))


# ---------------------------------------------------------------- stats font bundle

def stats_fonts():
    """Font subset used by scripts/stats.mjs, which runs in CI without Python."""
    chars = "".join(chr(c) for c in range(32, 127)) + "·→↗★✦—–"
    rules = []
    for name in ("Grotesk", "Mono"):
        file, weight, style = FONT_FILES[name]
        opts = subset.Options()
        opts.flavor = "woff2"
        font = subset.load_font(str(FONTS / file), opts)
        sub = subset.Subsetter(opts)
        sub.populate(text=chars)
        sub.subset(font)
        buf = io.BytesIO()
        subset.save_font(font, buf, opts)
        b64 = base64.b64encode(buf.getvalue()).decode()
        rules.append(f"@font-face{{font-family:{name};src:url(data:font/woff2;base64,{b64}) format('woff2');"
                     f"font-weight:{weight};font-style:{style}}}")
    (OUT / "fonts" / "stats-fonts.css").write_text("".join(rules))


def main():
    for theme in THEMES:
        (OUT / f"header-{theme}.svg").write_text(header(theme))
        (OUT / f"toolbox-{theme}.svg").write_text(toolbox(theme))
        for c in CARDS:
            (OUT / f"card-{c['id']}-{theme}.svg").write_text(card(theme, c))
    stats_fonts()
    for p in sorted(OUT.glob("*.svg")):
        print(f"{p.name:32} {p.stat().st_size / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
