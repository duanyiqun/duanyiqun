# Maintaining this profile

`duanyiqun/duanyiqun` is the profile repository: its `README.md` is what renders
at the top of <https://github.com/duanyiqun>.

## Blocker: this repository is private

GitHub only renders a profile README when the repository is **public**. While it
stays private the README does not appear on the profile at all, and the
`raw.githubusercontent.com` URLs the README points at return 404 for everyone
else.

Fix it under **Settings → General → Danger Zone → Change repository visibility →
Make public**. Nothing else in this repo works until that is done.

## What the activity card is

`scripts/activity_card.py` renders a 900×220 SVG of the trailing year of public
contributions. The GraphQL calendar comes back as whole weeks, so the series is
usually a few days over 365; the header states the real count rather than
assuming 365. GitHub's own calendar buckets every day into one of four shades,
so a 138-contribution day is drawn exactly like a 5-contribution day. This card
plots the real daily count on a log scale, with a 7-day trend line over it, so
both the everyday baseline and the bursts stay legible.

The header says `LOG SCALE` because the transform changes how the shape reads.
Do not remove that label.

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
  activity.** Every run commits `stamp.txt`, which counts as activity. Check
  the Actions tab every couple of months anyway.
- **`raw.githubusercontent.com` sends `cache-control: max-age=300` and is not
  proxied through camo.** A new card is normally visible within about ten
  minutes: five for the CDN, five more for a browser that fetched late in that
  window. GitHub's CDN has had incidents where raw files stayed stale much
  longer; there is no purge endpoint for this, so wait it out.

## Previewing locally

```
python3 scripts/activity_card.py \
  --fixture fixtures/calendar_sample.json \
  --stamp 2026-09-01 --out out
```

`fixtures/calendar_sample.json` holds **synthetic** daily values. Its aggregates
match the verified public totals (4,283 contributions in the trailing year, a
single-day peak of 138) so the layout is exercised at the right scale, but the
individual days are made up. `assets/preview-activity-*.svg` are renders of that
fixture, kept for reference only — the README points at the `output` branch,
which is always real data.

## Settled, and not yet settled

Settled:

- The card: what it plots, the log scale, the daily cadence, the output branch.
- One renderer, written here, with no third-party services in the output.

Not settled:

- The positioning line. The current README line lists post-training, world
  models, brain foundation models, ultrasound and robotics because that is the
  actual spread; the finished copy still needs writing.
- Selected work, links, and the profile sidebar (display name, bio, pinned
  repositories).
