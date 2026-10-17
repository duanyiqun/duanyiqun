# Maintaining this profile

`duanyiqun/duanyiqun` is the profile repository: its `README.md` is what renders
at the top of <https://github.com/duanyiqun>. The repository has to stay
**public** for that to happen.

The profile is one image on purpose: the contribution card, re-rendered every
day. No banner, no project list.

## What the card is

`scripts/activity_card.py` renders an 896px-wide SVG (about 300px tall) of the
trailing year of public contributions, in light and dark variants.

- **The headline** is the year's total in large type, then "contributions in
  the last year", with the login and "Updated <date>" on the right.
- **The grid** has the same shape as GitHub's calendar: weeks across, weekdays
  down, Sunday on top.
- **The facts row** under a hairline gives the peak day and the active days,
  with a size legend on the right.

GitHub sorts every day into one of four shades. On this account that flattens
almost everything worth seeing: the top bucket spans 23 to 137 contributions,
holds about 70% of the year's total, and draws all of it identically, while 40%
of the grid is flat grey carrying no data at all. This card keeps the grid and
fixes the encoding:

- **Magnitude is the area of a round mark**, on a log scale. A peak day nearly
  fills its 15.3px cell (`RMAX`). An area floor (`R0`) keeps a one-contribution
  day visible. Log rather than linear or square root: with a 137 peak, a typical
  8-contribution day would be a speck under either, and log is closer to what
  the year actually was. The legend's size steps are on the same log scale.
- **Quiet days shrink to a small warm-grey dot**, so the canvas belongs to the
  days that have data.

## Colour

The look is warm white and soft:

- **The ground** is warm white `#F6F3EF` on the light card and warm charcoal
  `#1A1917` on the dark one.
- **The type** is near-black and warm greys (inverted to warm light greys on the
  dark card).
- **The marks** carry the only colour.

Their hue follows the year, not the data: peach `#F4B79A` → rose `#EDA8BC` →
lilac `#C3B4EC` → sky `#A8CBEE`, from the first week to the last. Steps between
the four are interpolated in **OKLab**, which keeps the path from going muddy
between them. Magnitude adds a slight tone lift on top of the area:

- **On warm white** a busier day settles a little deeper and more saturated.
- **On charcoal** the lift runs the other way, so busy days glow. A deep mark
  would sink into a dark ground.

The legend is drawn in one neutral mid hue on purpose, so that colour keeps
meaning "time of year" and only size means "how much".

The heaviest tenth of active days get a **glow**: a blurred halo in their own
hue at 40–45% opacity behind the mark.

## The type

An SVG in an `<img>` cannot load a web font, and system fonts differ on every
machine, so every word on the card is Geist drawn as outlines. Each glyph is
defined once in `<defs>` and placed with `<use>`, which keeps the card around
44 KB.

`scripts/glyphs/geist-400.json` and `geist-500.json` hold the outline, advance
and kerning of every printable ASCII character (SIL Open Font License,
`scripts/glyphs/OFL.txt`). They are generated, and the daily run only reads
them. To change the typeface, the weights or the character set, rerun the
builder. It needs two packages the workflow does not install:

```
pip install fonttools uharfbuzz
python3 scripts/glyphs/build.py 'Geist[wght].ttf' 400 500
```

A character outside the set renders as `?`.

## The two things meant to be tuned

Both are constants near the top of `scripts/activity_card.py`:

- `WINDOW_DAYS` — `None` renders the whole calendar GitHub returns, about 52
  weeks. Set it to `182` for a trailing half-year; the headline then says "the
  last 182 days". The trade: a shorter window is denser, and a longer one keeps
  the ramp-up visible and averages out quiet stretches.
- `EVENT_TOP_FRACTION` — how much of the active-day list glows. `0.10` puts
  about 28 glows on the sample year (a tenth of 289 active days). Below about
  0.05 the glows look arbitrary; above about 0.15 they stop reading as an
  accent and start reading as noise.

## How it runs

`.github/workflows/activity.yml` runs daily at 04:23 UTC, on manual dispatch,
and on pushes that touch `scripts/`, `fixtures/`, or the workflow itself.

1. Queries the contribution calendar over GraphQL with the workflow's built-in
   `GITHUB_TOKEN` (public contributions only, about one rate-limit point).
2. Renders `activity-dark.svg` and `activity-light.svg`.
3. Validates them with `scripts/check_svg.py`, which rejects anything that
   cannot render inside an `<img>`: malformed XML, external references,
   `@import`, `<script>`, `<foreignObject>`, `<image>`, or over 60 KB.
4. Force-pushes the results to the orphan `output` branch, which the README
   references by raw URL.

A render failure exits non-zero before step 4, so a bad API call leaves the
previous card in place rather than publishing a broken one.

### Two scheduling facts worth remembering

- **Scheduled workflows are disabled after 60 days without repository
  activity.** Every run commits `stamp.txt`, which counts as activity. Check the
  Actions tab every couple of months anyway.
- **`raw.githubusercontent.com` sends `cache-control: max-age=300` and is not
  proxied through camo.** A new card is normally visible within about ten
  minutes: five for the CDN, five more for a browser that fetched late in that
  window. GitHub's CDN has had incidents where raw files stayed stale much
  longer; there is no purge endpoint for this, so wait it out.

## Animation

Two motions, both inside `prefers-reduced-motion: no-preference`.

**The wash.** The grid fades in week by week, once, then holds; the glows
arrive just after. Each column lifts from `.22` opacity to full rather than from
zero, so every frame shows the whole year, including the frame a thumbnail, a
screenshot or the GitHub mobile app captures. It takes about 1.6s and plays only
at image load, which makes it easy to miss on a cached page; that is the cost of
keeping every frame readable.

**The pulse.** The glows breathe continuously, 5.4s per cycle, with their phase
spread across the columns so they are not in step. Only the glows move; the
marks never do, so the card is stable at any instant but never entirely still.

Two things to keep if you change it:

- The pulse animates **`fill-opacity`** on the halos, and the wash animates
  **`opacity`** on the group around them. Two animations on the same property
  would replace each other rather than compose; on different properties they
  multiply.
- Nothing declares a base opacity, so a renderer that ignores animation still
  shows the finished card.

A README loads an SVG as an `<img>`. Pointer events never reach inside it and
script never runs, so hover and click are not available here at any price. Real
per-day interaction needs a real page.

## Previewing locally

```
python3 scripts/activity_card.py \
  --fixture fixtures/calendar_sample.json \
  --stamp 2026-10-17 --out out
```

`fixtures/calendar_sample.json` holds **synthetic** daily values. Its aggregates
match the verified public totals so the layout is exercised at the right scale,
but the individual days are made up. `assets/preview-activity-*.svg` are renders
of that fixture, kept for reference only — the README points at the `output`
branch, which is always real data.
