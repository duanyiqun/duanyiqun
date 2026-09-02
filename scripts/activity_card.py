#!/usr/bin/env python3
"""Render a contribution-activity card as SVG.

Why this exists: GitHub's own contribution calendar buckets every day into one
of four shades, so a 138-contribution day is drawn exactly like a 5-contribution
day. This card plots the real daily magnitude instead, on a square-root scale so
the everyday baseline and the bursts are both legible.

Standard library only. No third-party renderers, no external resources in the
output: the SVG is self-contained and safe to serve from raw.githubusercontent.
"""

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

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

# Monospace advance width is ~0.605 em across SF Mono, Menlo, Consolas and
# DejaVu Sans Mono, which is close enough to lay text out without measuring.
MONO_15, MONO_10, MONO_9_5 = 15 * 0.605, 10 * 0.605, 9.5 * 0.605

# --- geometry -------------------------------------------------------------
W, H = 900, 220
PAD_L, PAD_R = 24, 24
CHART_TOP, BASELINE = 42, 150
TICK_Y = 166
RULE_Y = 184
STATS_Y = 204

PALETTES = {
    "dark": {
        "ink": "#e6e1d7",
        "dim": "#79838d",
        "faint": "#4d555e",
        "rule": "#242b33",
        "bar": "#e6e1d7",
        "trend": "#8fa8b4",
    },
    "light": {
        "ink": "#1b1d22",
        "dim": "#5c656d",
        "faint": "#8b939b",
        "rule": "#d6dbe0",
        "bar": "#1b1d22",
        "trend": "#3d6b7d",
    },
}


def fetch_calendar(login, token):
    """Return (total, [(date, count), ...]) from the GitHub GraphQL API."""
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        GRAPHQL,
        data=body,
        headers={
            "Authorization": "bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "duanyiqun-activity-card",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError("GraphQL error: %s" % payload["errors"])
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [
        (d["date"], int(d["contributionCount"]))
        for week in cal["weeks"]
        for d in week["contributionDays"]
    ]
    return int(cal["totalContributions"]), days


def load_fixture(path):
    with open(path) as fh:
        blob = json.load(fh)
    days = [(d["date"], int(d["count"])) for d in blob["days"]]
    return sum(c for _, c in days), days


def moving_average(counts, window=7):
    out, run = [], 0.0
    for i, c in enumerate(counts):
        run += c
        if i >= window:
            run -= counts[i - window]
        out.append(run / min(i + 1, window))
    return out


def streaks(days):
    """Longest run of consecutive active days, and the run ending on the last day."""
    longest = current = 0
    for _, c in days:
        current = current + 1 if c > 0 else 0
        longest = max(longest, current)
    trailing = 0
    for _, c in reversed(days):
        if c == 0:
            break
        trailing += 1
    return longest, trailing


def month_ticks(days):
    """x-index of the first day of each month, with a short label."""
    names = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    ticks = []
    seen = None
    for i, (iso, _) in enumerate(days):
        y, m, _d = (int(p) for p in iso.split("-"))
        if (y, m) != seen:
            seen = (y, m)
            ticks.append((i, names[m - 1]))
    return ticks[1:] if ticks else ticks  # drop the partial leading month


def esc(s):
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def render(days, total, theme, login, stamp, source_note):
    p = PALETTES[theme]
    counts = [c for _, c in days]
    n = len(counts)
    span = W - PAD_L - PAD_R
    step = span / n
    bar_w = max(1.0, step * 0.72)
    height = BASELINE - CHART_TOP

    peak = max(counts) if counts else 0
    peak_i = counts.index(peak) if counts else 0
    peak_date = days[peak_i][0] if days else ""
    scale = math.log1p(peak) if peak else 1.0

    def y_of(v):
        return BASELINE - (math.log1p(v) / scale) * height

    # bars
    bars = []
    for i, c in enumerate(counts):
        if c <= 0:
            continue
        x = PAD_L + i * step + (step - bar_w) / 2
        y = y_of(c)
        bars.append(
            '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f"/>'
            % (x, y, bar_w, BASELINE - y)
        )

    # 7-day trend
    avg = moving_average(counts)
    pts = " ".join(
        "%.2f,%.2f" % (PAD_L + i * step + step / 2, y_of(v)) for i, v in enumerate(avg)
    )

    # month ticks
    ticks = []
    for i, label in month_ticks(days):
        x = PAD_L + i * step
        ticks.append('<line x1="%.2f" y1="%d" x2="%.2f" y2="%d"/>' % (x, BASELINE + 3, x, BASELINE + 7))
        if x + 4 + len(label) * MONO_9_5 <= W - PAD_R:
            ticks.append('<text class="tick" x="%.2f" y="%d">%s</text>' % (x + 4, TICK_Y, label))

    longest, trailing = streaks(days)
    active = sum(1 for c in counts if c > 0)

    stats = [
        ("%s" % f"{total:,}", "contributions"),
        ("%d" % peak, "peak day · %s" % peak_date),
        ("%d" % longest, "longest streak"),
        ("%d/%d" % (active, n), "active days"),
    ]
    stat_svg, x = [], PAD_L
    for value, label in stats:
        vw = len(value) * MONO_15
        stat_svg.append('<text class="val" x="%.1f" y="%d">%s</text>' % (x, STATS_Y, esc(value)))
        stat_svg.append(
            '<text class="lbl" x="%.1f" y="%d">%s</text>' % (x + vw + 9, STATS_Y, esc(label))
        )
        x += vw + 9 + len(label) * MONO_10 + 34

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{esc(login)} contribution activity: {total} contributions in the last year">
<title>{esc(login)} — {total:,} contributions in the last year</title>
<!-- {esc(source_note)} -->
<style>
text{{font-family:'SF Mono',Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace}}
.hd{{font-size:10.5px;letter-spacing:.14em;fill:{p['dim']}}}
.meta{{font-size:10.5px;letter-spacing:.08em;fill:{p['faint']}}}
.tick{{font-size:9.5px;letter-spacing:.1em;fill:{p['faint']}}}
.val{{font-size:15px;letter-spacing:.02em;fill:{p['ink']}}}
.lbl{{font-size:10px;letter-spacing:.1em;fill:{p['faint']}}}
.bars rect{{fill:{p['bar']};fill-opacity:.72}}
.trend{{fill:none;stroke:{p['trend']};stroke-opacity:.85;stroke-width:1.1;stroke-linejoin:round;stroke-linecap:round}}
.axis{{stroke:{p['rule']};stroke-width:1}}
</style>
<text class="hd" x="{PAD_L}" y="20">CONTRIBUTION ACTIVITY · 365 DAYS · LOG SCALE</text>
<text class="meta" x="{W - PAD_R}" y="20" text-anchor="end">{esc(login)} · {esc(stamp)}</text>
<g class="bars">{''.join(bars)}</g>
<polyline class="trend" points="{pts}"/>
<line class="axis" x1="{PAD_L}" y1="{BASELINE}" x2="{W - PAD_R}" y2="{BASELINE}"/>
<g class="axis" stroke="{p['rule']}">{''.join(t for t in ticks if t.startswith('<line'))}</g>
{''.join(t for t in ticks if t.startswith('<text'))}
<line class="axis" x1="{PAD_L}" y1="{RULE_Y}" x2="{W - PAD_R}" y2="{RULE_Y}"/>
{''.join(stat_svg)}
</svg>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", default="duanyiqun")
    ap.add_argument("--out", default="out")
    ap.add_argument("--fixture", help="render from a fixture instead of the live API")
    ap.add_argument("--stamp", required=True, help="UTC date stamp, e.g. 2026-09-01")
    args = ap.parse_args()

    if args.fixture:
        total, days = load_fixture(args.fixture)
        note = "PREVIEW: synthetic fixture, not real activity"
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("no GH_TOKEN in the environment")
        total, days = fetch_calendar(args.login, token)
        note = "generated from the public contribution calendar"

    if len(days) < 300:
        sys.exit("calendar looks truncated (%d days) - refusing to publish" % len(days))

    os.makedirs(args.out, exist_ok=True)
    for theme in ("dark", "light"):
        svg = render(days, total, theme, args.login, args.stamp, note)
        with open(os.path.join(args.out, "activity-%s.svg" % theme), "w") as fh:
            fh.write(svg)
    with open(os.path.join(args.out, "meta.json"), "w") as fh:
        json.dump(
            {"total": total, "days": len(days), "stamp": args.stamp, "login": args.login},
            fh,
            indent=1,
        )
    print("rendered %d days, %d contributions" % (len(days), total))


if __name__ == "__main__":
    main()
