#!/usr/bin/env python3
"""Render the contribution activity card as SVG.

The card is the trailing year of public contributions as a day grid in the
same shape as GitHub's own calendar - weeks across, weekdays down, Sunday on
top - but with the encoding fixed. GitHub sorts every day into one of four
shades, so on this account a 137-contribution day is drawn exactly like a
23-contribution day. Here magnitude is the area of a round mark on a log
scale, and quiet days shrink to a dot so the canvas belongs to the days that
have data.

The look is warm white and soft: the marks' hue drifts through the year from
peach to rose to lilac to sky, magnitude adds a slight tone lift, and the
heaviest tenth of days carry a faint glow of their own hue that breathes. The
type is Geist, drawn as outlines from scripts/glyphs/, because an SVG inside
an <img> can neither load a web font nor count on a system one.

Standard library only, and the output is self-contained: no external
references, nothing that needs the network to render inside an <img>.
"""

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import date

GRAPHQL = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

# How the card is tuned. Both of these are meant to be edited.
WINDOW_DAYS = None          # None = the whole calendar GitHub returns (about 52 weeks)
EVENT_TOP_FRACTION = 0.10   # the heaviest tenth of active days glow

# --- palette ---------------------------------------------------------------
# The year's path: four low-saturation pastels, interpolated in OKLab.
YEAR = ["#F4B79A", "#EDA8BC", "#C3B4EC", "#A8CBEE"]   # peach, rose, lilac, sky

THEMES = {
    "light": {"ground": "#F6F3EF", "ink": "#141414", "ink2": "#5E5B56", "ink3": "#9A958D",
              "rule": "#E2DDD5", "zero": "#D9D3CA", "halo_op": 0.45},
    "dark": {"ground": "#1A1917", "ink": "#EEEAE4", "ink2": "#ABA59C", "ink3": "#77726A",
             "rule": "#2D2B28", "zero": "#3A3733", "halo_op": 0.40},
}

# --- geometry ---------------------------------------------------------------
WIDTH = 896
PADX = 40
PITCH = 15.3        # centre to centre, in both directions
RMAX = 6.2          # a peak day nearly fills its cell
R0 = 1.8            # area floor, so a 1-contribution day is still a visible mark
RZ = 1.15           # a quiet day
GRID_Y = 92         # top edge of the Sunday row

GLYPHS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glyphs")


# --- OKLab, so the year's path does not go muddy between the pastels -------
def _hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb2hex(c):
    return "#" + "".join(f"{max(0, min(255, round(v * 255))):02X}" for v in c)


def _to_linear(u):
    return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4


def _to_srgb(u):
    return 12.92 * u if u <= 0.0031308 else 1.055 * (u ** (1 / 2.4)) - 0.055


def _rgb2oklab(c):
    r, g, b = (_to_linear(u) for u in c)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def _oklab2rgb(lab):
    L, a, b = lab
    l_, m_, s_ = (L + 0.3963377774 * a + 0.2158037573 * b,
                  L - 0.1055613458 * a - 0.0638541728 * b,
                  L - 0.0894841775 * a - 1.2914855480 * b)
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return tuple(_to_srgb(max(0.0, min(1.0, u))) for u in (
        +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s))


YEAR_LAB = [_rgb2oklab(_hex2rgb(h)) for h in YEAR]


def tone(s, t, theme):
    """The mark colour: hue from the time of year s, a tone lift from magnitude t.

    On warm white, busier days settle a little deeper and more saturated. On
    charcoal the lift runs the other way, so busy days glow.
    """
    n = len(YEAR_LAB) - 1
    seg = min(int(s * n), n - 1)
    f = s * n - seg
    a, b = YEAR_LAB[seg], YEAR_LAB[seg + 1]
    L0, A, B = (a[i] + (b[i] - a[i]) * f for i in range(3))
    chroma, hue = math.hypot(A, B), math.atan2(B, A)
    if theme == "light":
        L, C = L0 + 0.04 - 0.115 * t, chroma * (0.72 + 0.38 * t)
    else:
        L, C = 0.50 + 0.32 * t, chroma * (0.66 + 0.40 * t)
    return _rgb2hex(_oklab2rgb((L, C * math.cos(hue), C * math.sin(hue))))


# --- type ---------------------------------------------------------------------
class Type:
    """Sets lines of Geist as outlines, with the font's kerning.

    Each glyph is outlined once into <defs> and every run places it with <use>,
    which keeps the card well inside check_svg.py's 60 KB budget.
    """

    def __init__(self):
        self.fonts, self.ids = {}, {}

    def _font(self, weight):
        if weight not in self.fonts:
            with open(os.path.join(GLYPHS, "geist-%d.json" % weight)) as fh:
                self.fonts[weight] = json.load(fh)
        return self.fonts[weight]

    def run(self, weight, text, x, y, size, fill, tracking=0.0, anchor="start"):
        """`text` with its baseline at y; returns (svg, width). tracking is in em."""
        f = self._font(weight)
        upm, glyphs, kern = f["unitsPerEm"], f["glyphs"], f["kern"]
        pen, parts = 0.0, []
        for i, ch in enumerate(text):
            if ch not in glyphs:
                ch = "?"
            if glyphs[ch]["d"]:
                gid = self.ids.setdefault((weight, ch), "g%x" % len(self.ids))
                parts.append(f'<use href="#{gid}" x="{pen:.0f}"/>')
            pen += glyphs[ch]["adv"] + kern.get(text[i:i + 2], 0)
            if i < len(text) - 1:
                pen += tracking * upm
        k = size / upm
        if anchor == "end":
            x -= pen * k
        return (f'<g transform="translate({x:.2f} {y:.2f}) scale({k:.5f} {-k:.5f})" fill="{fill}">'
                + "".join(parts) + "</g>"), pen * k

    def defs(self):
        return "".join(f'<path id="{gid}" d="{self._font(w)["glyphs"][ch]["d"]}"/>'
                       for (w, ch), gid in self.ids.items())


# --- data -------------------------------------------------------------------
def fetch_calendar(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(GRAPHQL, data=body, headers={
        "Authorization": "bearer " + token,
        "Content-Type": "application/json",
        "User-Agent": "duanyiqun-activity-card",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError("GraphQL error: %s" % payload["errors"])
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return [(d["date"], int(d["contributionCount"]))
            for week in cal["weeks"] for d in week["contributionDays"]]


def load_fixture(path):
    with open(path) as fh:
        blob = json.load(fh)
    return [(d["date"], int(d["count"])) for d in blob["days"]]


def event_days(counts):
    """The heaviest slice of active days - the ones that glow."""
    active = sorted((i for i, c in enumerate(counts) if c > 0), key=lambda i: -counts[i])
    if not active:
        return set()
    return set(active[:max(1, int(len(active) * EVENT_TOP_FRACTION))])


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def nice_date(iso, year=True):
    d = date.fromisoformat(iso)
    return "%s %d" % (d.strftime("%b"), d.day) + (", %d" % d.year if year else "")


# --- the card ---------------------------------------------------------------
def render(days, theme_name, login, stamp, note):
    th = THEMES[theme_name]
    T = Type()
    dates = [d for d, _ in days]
    counts = [c for _, c in days]
    n = len(counts)
    lead = (date.fromisoformat(dates[0]).weekday() + 1) % 7   # Sunday-first rows, as GitHub draws them
    cols = math.ceil((n + lead) / 7)
    peak = max(counts)
    scale = math.log1p(peak) if peak else 1.0
    events = event_days(counts)
    total = sum(counts)
    active = sum(1 for c in counts if c > 0)
    peak_date = dates[counts.index(peak)] if peak else None      # an empty year has no peak day
    span = "the last year" if n >= 360 else "the last %d days" % n   # WINDOW_DAYS can shorten it

    grid_w = (cols - 1) * PITCH + 2 * RMAX
    measure = WIDTH - 2 * PADX
    if grid_w >= 0.8 * measure:
        # A full year: centre the grid, and hang the text on its edges.
        x0 = PADX + RMAX + (measure - grid_w) / 2
        tx0, tx1 = x0 - RMAX, x0 - RMAX + grid_w
    else:
        # A short WINDOW_DAYS: grid on the left, text across the whole card,
        # so the facts row and the legend still have room side by side.
        x0 = PADX + RMAX
        tx0, tx1 = PADX, WIDTH - PADX
    gx0 = x0 - RMAX
    cy = [GRID_Y + RMAX + r * PITCH for r in range(7)]
    grid_bottom = cy[6] + RMAX

    # One <g> per week, translated, so each mark only carries cy, r and fill.
    colmarks = [[] for _ in range(cols)]
    halos = []
    for i, c in enumerate(counts):
        col, row = divmod(i + lead, 7)
        y = cy[row]
        if c == 0:
            colmarks[col].append(f'<circle cy="{y:.1f}" r="{RZ}" class="z"/>')
            continue
        t = math.log1p(c) / scale
        r = math.sqrt(R0 * R0 + (RMAX * RMAX - R0 * R0) * t)     # area grows with log magnitude
        fill = tone(col / max(1, cols - 1), t, theme_name)
        if i in events:
            halos.append(f'<circle cx="{x0 + col * PITCH:.1f}" cy="{y:.1f}" r="{r + 2.6:.1f}" '
                         f'fill="{fill}" class="h p{col % 9}"/>')
        colmarks[col].append(f'<circle cy="{y:.1f}" r="{r:.2f}" fill="{fill}"/>')
    grid = "".join(f'<g class="c w{c}" transform="translate({x0 + c * PITCH:.1f} 0)">{"".join(m)}</g>'
                   for c, m in enumerate(colmarks))

    parts = []
    # The headline: the year's total, then what it is; who and when on the right.
    big, bw = T.run(500, f"{total:,}", tx0, 60, 34, th["ink"], tracking=-0.035)
    cap, _ = T.run(400, "contributions in " + span, tx0 + bw + 12, 60, 14, th["ink2"])
    who, _ = T.run(500, login, tx1, 60, 13, th["ink2"], anchor="end", tracking=-0.005)
    when, _ = T.run(400, "Updated " + nice_date(stamp), tx1, 41, 12, th["ink3"], anchor="end")
    parts += [big, cap, who, when]

    # Months under the grid, each over the week that holds its 1st. The month
    # the window starts in keeps the first column only while the next month
    # starts at least three weeks later; otherwise it gives way to that month,
    # as GitHub's calendar does. A month starting in the last two weeks goes
    # unlabelled.
    my = grid_bottom + 20
    ticks = [(0, dates[0])]
    for i, iso in enumerate(dates):
        if i and iso.endswith("-01"):
            col = (i + lead) // 7
            if col > cols - 3:
                continue
            if col - ticks[-1][0] >= 3:
                ticks.append((col, iso))
            elif len(ticks) == 1:
                ticks[0] = (col, iso)
    for col, iso in ticks:
        s, _ = T.run(400, nice_date(iso, False).split()[0], gx0 + col * PITCH + 0.5, my, 11, th["ink3"],
                     tracking=0.005)
        parts.append(s)

    # A hairline, then the facts row and a size-only legend.
    ry = my + 22
    parts.append(f'<rect x="{tx0:.1f}" y="{ry:.1f}" width="{tx1 - tx0:.1f}" height="1" fill="{th["rule"]}"/>')
    fy = ry + 30
    x = tx0
    for label, value in (("Peak day", f"{peak} on {nice_date(peak_date)}" if peak else "—"),
                         ("Active days", f"{active} of {n}")):
        s, w = T.run(400, label, x, fy, 12.5, th["ink3"])
        s2, w2 = T.run(500, value, x + w + 8, fy, 12.5, th["ink"])
        parts += [s, s2]
        x += w + 8 + w2 + 34

    # The legend steps are sizes in one fixed hue, the year's midpoint, so that
    # only size reads as magnitude and colour stays the time of year.
    lx = tx1
    s, w = T.run(400, "More", lx, fy, 12, th["ink3"], anchor="end")
    parts.append(s)
    lx -= w + 10
    for tt in (1.0, 0.7, 0.45, 0.2, 0.0):
        r = math.sqrt(R0 * R0 + (RMAX * RMAX - R0 * R0) * tt)
        lx -= r
        parts.append(f'<circle cx="{lx:.1f}" cy="{fy - 4.3:.1f}" r="{r:.2f}" fill="{tone(0.62, tt, theme_name)}"/>')
        lx -= r + 5
    lx += 1
    parts.append(f'<circle cx="{lx - RZ:.1f}" cy="{fy - 4.3:.1f}" r="{RZ}" class="z"/>')
    lx -= 2 * RZ + 10
    s, _ = T.run(400, "Less", lx, fy, 12, th["ink3"], anchor="end")
    parts.append(s)

    height = round(fy + 30)
    # The card washes in week by week, once, lifting each column from .22 to
    # full rather than from zero, so every frame - including the one a
    # thumbnail or the GitHub mobile app captures - shows the whole year. The
    # glows wash in on their group's opacity and breathe on their own
    # fill-opacity; the two multiply. Their phase is spread so they are not
    # in step.
    stagger = "".join(f".w{c}{{animation-delay:{0.08 + c * 0.018:.3f}s}}" for c in range(cols))
    phases = "".join(f".p{k}{{animation-delay:-{k * 0.6:.1f}s}}" for k in range(9))
    title = f"{login} - {total:,} contributions in {span}" + (f", peak {peak} on {peak_date}" if peak else "")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}" role="img" aria-label="{esc(title)}">
<title>{esc(title)}</title>
<!-- {esc(note)} -->
<style>
.z{{fill:{th["zero"]}}}
@media (prefers-reduced-motion:no-preference){{
.c{{animation:wash .6s cubic-bezier(.16,1,.3,1) 1 backwards}}
.hl{{animation:wash 1.2s ease-out .7s 1 backwards}}
.h{{animation:pulse 5.4s ease-in-out infinite}}
@keyframes wash{{from{{opacity:.22}}to{{opacity:1}}}}
@keyframes pulse{{0%,100%{{fill-opacity:1}}50%{{fill-opacity:.35}}}}
{stagger}{phases}
}}
</style>
<defs><filter id="soft" filterUnits="userSpaceOnUse" x="{gx0 - 12:.1f}" y="{GRID_Y - 12}" width="{grid_w + 24:.1f}" height="{grid_bottom - GRID_Y + 24:.1f}"><feGaussianBlur stdDeviation="2.2"/></filter>{T.defs()}</defs>
<rect width="{WIDTH}" height="{height}" rx="16" fill="{th["ground"]}"/>
<g class="hl"><g filter="url(#soft)" opacity="{th["halo_op"]}">{"".join(halos)}</g></g>
{grid}
{"".join(parts)}
</svg>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", default="duanyiqun")
    ap.add_argument("--out", default="out")
    ap.add_argument("--fixture", help="render from a fixture instead of the live API")
    ap.add_argument("--stamp", required=True, help="UTC date stamp, e.g. 2026-10-17")
    args = ap.parse_args()

    if args.fixture:
        days = load_fixture(args.fixture)
        note = "PREVIEW: synthetic fixture, not real activity"
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("no GH_TOKEN in the environment")
        days = fetch_calendar(args.login, token)
        note = "generated from the public contribution calendar"

    if len(days) < 300:
        sys.exit("calendar looks truncated (%d days) - refusing to publish" % len(days))
    if WINDOW_DAYS:
        days = days[-WINDOW_DAYS:]

    os.makedirs(args.out, exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(args.out, "activity-%s.svg" % theme), "w") as fh:
            fh.write(render(days, theme, args.login, args.stamp, note))
    with open(os.path.join(args.out, "meta.json"), "w") as fh:
        json.dump({"total": sum(c for _, c in days), "days": len(days),
                   "stamp": args.stamp, "login": args.login}, fh, indent=1)
    print("rendered %d days, %d contributions" % (len(days), sum(c for _, c in days)))


if __name__ == "__main__":
    main()
