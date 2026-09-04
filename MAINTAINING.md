# Maintaining this profile

`duanyiqun/duanyiqun` is the profile repository: its `README.md` is what renders
at the top of <https://github.com/duanyiqun>. The repository has to stay
**public** for that to happen.

## What the card is

`scripts/activity_card.py` renders a 896×184 SVG of the trailing year of public
contributions, as a day grid in the same shape as GitHub's own calendar.

GitHub sorts every day into one of four shades. On this account that flattens
almost everything worth seeing: the top bucket spans 23 to 137 contributions,
holds about 70% of the year's total, and draws all of it identically, while 40%
of the grid is flat grey carrying no data at all.

This card keeps the grid and fixes the encoding:

- **Magnitude is the area of the mark**, on a log scale. A quiet day is a small
  square, the 137-day fills its cell. Log rather than linear or square root:
  with a 137 peak, a typical 8-contribution day renders at 24% of the cell under
  a square-root scale and around 45% under log, which is closer to what the year
  actually was.
- **Quiet days shrink to a 2.8px dot** instead of a filled grey box, so the
  canvas belongs to the days that have data.
- The header states `LOG` because the transform changes how the shape reads.
  Do not remove that label.

## Colour

Every colour is a token from the owner's design system, and the mapping follows
what the tokens are *for*:

| Token | Used for |
| --- | --- |
| `surface.membrane` `#F6F3EF` | the light card's ground |
| `ink.primary` `#1A1C1E` | headline figures; the dark card's ground |
| `structure.silver.700` `#55595D` | labels; quiet days on the dark card |
| `structure.silver.500` `#9BA1A6` | month ticks |
| `structure.silver.200` `#E8E8E6` | quiet days on the light card — the token is "shallow layering and spatial transition" |
| `material.hematite.400 → 700 → 900` | the magnitude ramp — the tokens already describe "shallow section → main rock section → internal density peak" |
| `event.verdigris` `#4E8577` | the heaviest days — the token is "oxidation contact points and time nodes" |

Steps between the three hematite stops are interpolated in **OKLab**, not sRGB,
which keeps the midtones from going muddy.

On the dark card the ramp runs the other way. A density peak painted
`hematite.900` would sink into an `ink.primary` ground, so the peak has to be
the most luminous step, not the darkest.

## The two things meant to be tuned

Both are constants near the top of `scripts/activity_card.py`:

- `WINDOW_DAYS` — `None` renders the whole calendar GitHub returns, about 52
  weeks. Set it to `182` for a trailing half-year. The trade: the first five
  months of the current year carry 3% of the contributions across 45% of the
  card's width, so a shorter window is denser; a longer one keeps the ramp-up
  visible and averages out quiet stretches.
- `EVENT_TOP_FRACTION` — how much of the active-day list counts as a time node
  and gets verdigris. `0.10` puts roughly 22 marks on a full year. Below about
  0.05 the green looks arbitrary; above about 0.15 it stops reading as an accent
  and starts reading as a second category.

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

## Animation, and why it starts at .22

The card washes in week by week, once, then holds. Each column lifts from `.22`
opacity to full rather than from zero, so every frame shows the whole mosaic —
including the frame a thumbnail, a screenshot, or the GitHub mobile app
captures. The base state is the finished state, so a renderer that ignores the
animation entirely is also correct. It is wrapped in
`prefers-reduced-motion: no-preference`.

A README loads an SVG as an `<img>`. Pointer events never reach inside it and
script never runs, so hover and click are not available here at any price. Real
per-day interaction needs a real page.

## Previewing locally

```
python3 scripts/activity_card.py \
  --fixture fixtures/calendar_sample.json \
  --stamp 2026-09-04 --out out
```

`fixtures/calendar_sample.json` holds **synthetic** daily values. Its aggregates
match the verified public totals so the layout is exercised at the right scale,
but the individual days are made up. `assets/preview-activity-*.svg` are renders
of that fixture, kept for reference only — the README points at the `output`
branch, which is always real data.

## Not yet settled

The positioning copy, selected work and links. The README is currently the card
and nothing else.
