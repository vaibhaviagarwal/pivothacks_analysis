# PivotHacks 2026 — rebuilding the funnel from what was left behind

PivotHacks was a 12-hour hackathon I co-founded as part of Waterloo Tech
Week. When it was over I had a registration export, a sheet of problem
assignments, some Instagram numbers and a list of sponsors — and no
reliable answer to simple questions like how many people actually
applied, which teams formed, or whether our promotion worked.

This is the pipeline that reconstructs those answers, and the record of
what the data could not support.

## What it found

**The promotional reel ran one day too late.** Our August 27 reel had the
widest reach of any post (7,800) and the most shares (76), and produced
almost no applications above baseline. Applications closed August 28. The
August 18 post, with less reach, preceded 25 applications in two days —
close to a quarter of the entire pool. Timing beat reach by a factor of
three.

**Teams were recoverable from a text box, at a price.** The registration
platform has team fields; they were never populated. The only record of
who intended to work with whom was a free-text box where applicants typed
their teammates' names. Matching those names against the roster recovers
teams at **1.00 precision and 0.44 recall** when scored against the real
problem assignments — it never invents a teammate pair, and it misses more
than half of them, because the matcher refuses ambiguous cases.

**Five people competed who are not in the registration export.** They
appear on the problem assignment sheet and nowhere else, which means the
export is incomplete and every rate computed from it is an upper bound.

**The only application field that discriminated was the essay.** Accepted
applicants wrote a median of 130 words on the adaptability question;
denied applicants wrote 88. Portfolio links, resumes and LinkedIn profiles
were supplied by essentially everyone (98, 106 and 105 of 107), so none of
them separated anybody from anybody.

**One sponsor was 76% of the budget.** $7,940 in total value, of which
$900 was cash. The venue alone was $6,000. There was no second option.

## What it could not find

Worth stating plainly, because the gaps shaped the analysis more than the
data did:

- **Attendance was never recorded.** `checked_in_at` is empty for all
  rows and `num_events_checked_in` is 0 for all of them. QR codes were
  generated and never scanned, so the funnel stops at "accepted."
- **Channel attribution is 9% covered.** Only 10 applications carry a
  `utm_source`. Instagram probably drove around half the pool, judging by
  timing, and the tracking data can account for six of them.
- **There is no click-through data.** The per-post engagement metric
  available is shares, which measures amplification rather than intent, so
  no post-to-application conversion rate can be computed. Applications per
  thousand reached is the closest available substitute.
- **Selection scores were never stored.** Reviewers rated on experience
  first, then project depth and variety, but only the accept/deny outcome
  survives.

## Method notes

Three decisions worth defending if you are reading the code:

**Raw data is immutable.** Everything in `data/raw/` is read and never
written. Every file in `data/processed/` is regenerable by re-running the
pipeline, which is why both directories are gitignored — one holds
personal data, the other holds nothing that cannot be rebuilt.

**Name matching is deliberately conservative.** `teams.py` tries full
name, then surname-plus-initial, then first name alone, and accepts a
match only when exactly one roster entry fits. A first name shared by
three applicants resolves to nobody. This is why recall is 0.44: for
reconstructing who worked with whom, a wrong edge is worse than a missing
one, and the scorecard shows the trade rather than hiding it.

**Small numbers are flagged, not interpreted.** With 100+ applications,
most subgroups are tiny. `decisions.py` marks any group under 10 as
uninterpretable and reports the count anyway, so the long tail stays
visible without inviting conclusions it cannot support.

## Layout

```
data/raw/          source exports, never modified (gitignored)
data/processed/    regenerable output (gitignored)
src/config.py      paths, column renames, status groupings
src/pipeline/
  clean.py         load, normalize schools, bucket decisions
  teams.py         resolve typed names, build the team graph
  validate.py      score the graph against real assignments
  decisions.py     selection criteria vs actual outcomes
  social.py        align posts against the application curve
  dashboard.py     render reports/dashboard.html
reports/           generated findings and the dashboard
```

## Running it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# the four source files go in data/raw/ (not published: they hold personal data):
#   pivot_attendees_export.csv   registration export
#   problem_assignments.csv      who competed on which problem (ground truth for teams)
#   social_posts.csv             Instagram posts: date, reach, likes, shares
#   sponsors.csv                 sponsors and contribution value

python src/pipeline/clean.py
python src/pipeline/teams.py
python src/pipeline/validate.py
python src/pipeline/decisions.py
python src/pipeline/social.py
python src/pipeline/dashboard.py

open reports/dashboard.html
```

Run the stages in this order. Each reads the previous one's output:
`teams.py` needs `clean.py`'s, `validate.py` needs `teams.py`'s, and
`dashboard.py` needs all of them.

## A note on the data

The registration export contains applicants' names, emails, schools and
written answers. It is gitignored and not published here. The pipeline
code and the aggregate findings are the only things in this repository;
the rows belong to the people who wrote them.
