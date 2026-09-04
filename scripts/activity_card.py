#!/usr/bin/env python3
"""Render the contribution activity card as SVG.

GitHub's own calendar sorts every day into one of four shades, so on this
account a 137-contribution day is drawn exactly like a 23-contribution day:
the top bucket alone holds 70% of the year's contributions, and 40% of the
grid is flat grey carrying nothing. This card keeps the same day grid and
fixes the encoding instead - magnitude is the area of the mark, on a log
scale, and quiet days shrink to a dot so the canvas belongs to the days that
have data.

Colour comes from the owner's design system. The hematite steps are defined
there as "shallow section -> main rock section -> internal density peak",
which is already a density ramp; silver.200 is "shallow layering and spatial
transition", which is what a quiet day is; verdigris is reserved for
"oxidation contact points and time nodes", so it marks only the heaviest days.

Standard library only, and the output is self-contained: no external
references, nothing that needs the network to render inside an <img>.
"""

import argparse
import json
import math
import os
import sys
import urllib.request

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

# --- the owner's design system -------------------------------------------
TOKENS = {
    "surface.membrane":      "#F6F3EF",
    "ink.primary":           "#1A1C1E",
    "structure.silver.700":  "#55595D",
    "structure.silver.500":  "#9BA1A6",
    "structure.silver.200":  "#E8E8E6",
    "material.hematite.900": "#5A241D",
    "material.hematite.700": "#8A3529",
    "material.hematite.400": "#B96B5C",
    "event.verdigris":       "#4E8577",
}

# How the card is tuned. Both of these are meant to be edited.
WINDOW_DAYS = None      # None = the whole calendar GitHub returns (about 52 weeks)
EVENT_TOP_FRACTION = 0.10   # the heaviest tenth of active days are time nodes

# --- geometry -------------------------------------------------------------
PAD = 24
PITCH = 16.0
GAP = 3.2
CELL = PITCH - GAP
GRID_TOP = 26
HEAD_Y = 14
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"
MONO_ADVANCE = 0.605    # holds across SF Mono, Menlo, Consolas and DejaVu Sans Mono


# --- OKLab, so the ramp does not go muddy between the designer's steps -----
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


def ramp(stops, t):
    t = max(0.0, min(1.0, t))
    n = len(stops) - 1
    seg = min(int(t * n), n - 1)
    f = t * n - seg
    a, b = _rgb2oklab(_hex2rgb(stops[seg])), _rgb2oklab(_hex2rgb(stops[seg + 1]))
    return _rgb2hex(_oklab2rgb(tuple(a[i] + (b[i] - a[i]) * f for i in range(3))))


HEMATITE = [TOKENS["material.hematite.400"], TOKENS["material.hematite.700"],
            TOKENS["material.hematite.900"]]

THEMES = {
    # On membrane the ramp runs light to dark, as the tokens are numbered.
    "light": {
        "ground": TOKENS["surface.membrane"], "fg": TOKENS["ink.primary"],
        "sub": TOKENS["structure.silver.700"], "tick": TOKENS["structure.silver.500"],
        "quiet": TOKENS["structure.silver.200"], "quiet_op": 1.0,
        "stops": HEMATITE,
    },
    # On ink it runs the other way: a density peak painted hematite.900 would
    # disappear into the ground, so the peak has to be the most luminous step.
    "dark": {
        "ground": TOKENS["ink.primary"], "fg": TOKENS["surface.membrane"],
        "sub": TOKENS["structure.silver.500"], "tick": TOKENS["structure.silver.700"],
        "quiet": TOKENS["structure.silver.700"], "quiet_op": 0.55,
        "stops": list(reversed(HEMATITE)),
    },
}


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


def month_label(iso):
    names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return names[int(iso[5:7]) - 1]


def event_days(counts):
    """The heaviest slice of active days - the contact points."""
    active = sorted((i for i, c in enumerate(counts) if c > 0), key=lambda i: -counts[i])
    if not active:
        return set()
    return set(active[:max(1, int(len(active) * EVENT_TOP_FRACTION))])


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(days, theme_name, login, stamp, note):
    th = THEMES[theme_name]
    dates = [d for d, _ in days]
    counts = [c for _, c in days]
    n = len(counts)
    cols = math.ceil(n / 7)
    width = PAD + cols * PITCH + PAD
    grid_h = 7 * PITCH
    height = GRID_TOP + grid_h + 46
    peak = max(counts) if counts else 0
    scale = math.log1p(peak) if peak else 1.0
    events = event_days(counts)
    min_mark = 3.4

    def t(c):
        return math.log1p(c) / scale if c > 0 else 0.0

    marks = []
    for i, c in enumerate(counts):
        col, row = divmod(i, 7)
        x, y = PAD + col * PITCH, GRID_TOP + row * PITCH
        if c == 0:
            off = (CELL - 2.8) / 2
            marks.append(f'<rect class="m w{col}" x="{x + off:.2f}" y="{y + off:.2f}" '
                         f'width="2.8" height="2.8" fill="{th["quiet"]}" '
                         f'fill-opacity="{th["quiet_op"]}"/>')
            continue
        size = min_mark + (CELL - min_mark) * t(c)
        off = (CELL - size) / 2
        fill = TOKENS["event.verdigris"] if i in events else ramp(th["stops"], t(c))
        marks.append(f'<rect class="m w{col}" x="{x + off:.2f}" y="{y + off:.2f}" '
                     f'width="{size:.2f}" height="{size:.2f}" fill="{fill}"/>')

    ticks, seen = [], None
    for i, iso in enumerate(dates):
        if iso[:7] != seen:
            seen = iso[:7]
            col = i // 7
            if 0 < col < cols - 2:
                ticks.append(f'<text class="tick" x="{PAD + col * PITCH:.1f}" '
                             f'y="{GRID_TOP + grid_h + 14:.0f}">{month_label(iso)}</text>')

    total = sum(counts)
    active = sum(1 for c in counts if c > 0)
    peak_date = dates[counts.index(peak)] if peak else ""
    stats, x = [], PAD
    sy = GRID_TOP + grid_h + 36
    for value, label in ((f"{total:,}", "contributions"),
                         (str(peak), "peak · %s" % peak_date),
                         (f"{active}/{n}", "active days")):
        stats.append(f'<text class="val" x="{x:.0f}" y="{sy:.0f}">{esc(value)}</text>')
        vw = len(value) * 13 * MONO_ADVANCE
        stats.append(f'<text class="lbl" x="{x + vw + 7:.0f}" y="{sy:.0f}">{esc(label)}</text>')
        x += vw + 7 + len(label) * 9 * MONO_ADVANCE + 30

    # A one-time wash across the year, week by week. It lifts each column from
    # .22 to full rather than from zero, so every frame - including the one a
    # thumbnail or the GitHub mobile app captures - shows the whole mosaic. The
    # base state is the finished state, so not animating at all is also correct.
    stagger = "".join(f".w{c}{{animation-delay:{0.10 + c * 0.017:.3f}s}}" for c in range(cols))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" height="{height:.0f}" role="img" aria-label="{esc(login)} contribution activity: {total:,} contributions over {n} days, peak {peak} on {peak_date}">
<title>{esc(login)} — {total:,} contributions, peak {peak} on {peak_date}</title>
<!-- {esc(note)} -->
<style>
text{{font-family:{MONO}}}
.hd{{font-size:9.5px;letter-spacing:.14em;fill:{th["sub"]}}}
.meta{{font-size:9.5px;letter-spacing:.08em;fill:{th["tick"]}}}
.tick{{font-size:9px;letter-spacing:.1em;fill:{th["tick"]}}}
.val{{font-size:13px;fill:{th["fg"]}}}
.lbl{{font-size:9px;letter-spacing:.1em;fill:{th["sub"]}}}
@media (prefers-reduced-motion:no-preference){{
.m{{animation:wash .45s cubic-bezier(.16,1,.3,1) 1 backwards}}
@keyframes wash{{from{{opacity:.22}}to{{opacity:1}}}}
{stagger}
}}
</style>
<rect width="{width:.0f}" height="{height:.0f}" fill="{th["ground"]}"/>
<text class="hd" x="{PAD}" y="{HEAD_Y}">CONTRIBUTION ACTIVITY · {n} DAYS · AREA BY MAGNITUDE · LOG</text>
<text class="meta" x="{width - PAD:.0f}" y="{HEAD_Y}" text-anchor="end">{esc(login)} · {esc(stamp)}</text>
{''.join(marks)}
{''.join(ticks)}
{''.join(stats)}
</svg>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", default="duanyiqun")
    ap.add_argument("--out", default="out")
    ap.add_argument("--fixture", help="render from a fixture instead of the live API")
    ap.add_argument("--stamp", required=True, help="UTC date stamp, e.g. 2026-09-04")
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
