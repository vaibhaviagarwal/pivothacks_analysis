"""Attribute applications to Instagram posts by timing.

Only 9% of applications carry a utm_source, so channel attribution
cannot be done directly. What can be done is comparing post dates
against the daily application curve: if applications spike on the day a
post went out and decay afterwards, the post plausibly caused them.

This is weaker than tracked attribution and it is important to say so.
Correlation in time is not proof — word of mouth, a Discord message, or
a club newsletter could land the same day. The analysis reports the
alignment and a baseline, and leaves the causal claim hedged.

Note on metrics: the per-post engagement figure available here is
SHARES, not link clicks. Shares measure amplification (someone passed
the post on), not intent to apply, so no click-to-application
conversion rate can be computed. Shares are reported alongside reach as
a reach-quality signal and nothing more.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DATA_PROCESSED, DATA_RAW, REPORTS  # noqa: E402

# Days after a post during which an application is attributed to it.
# Instagram posts decay fast; most reach lands within 48 hours.
ATTRIBUTION_WINDOW_DAYS = 1


def main() -> None:
    apps = pd.read_csv(DATA_PROCESSED / "applicants_with_teams.csv")
    posts = pd.read_csv(DATA_RAW / "social_posts.csv")

    apps["applied_date"] = pd.to_datetime(apps["applied_date"]).dt.date
    posts["post_date"] = pd.to_datetime(posts["post_date"]).dt.date

    daily = apps.groupby("applied_date").size()
    window_start, window_end = daily.index.min(), daily.index.max()

    lines: list[str] = []

    def emit(text: str = "") -> None:
        print(text)
        lines.append(text)

    emit("REACH")
    emit(f"  posts recorded : {len(posts)}")
    emit(f"  total reach    : {int(posts['reach'].sum()):,}")
    emit(f"  total likes    : {int(posts['likes'].sum()):,}")
    emit(f"  total shares   : {int(posts['shares'].sum()):,}")
    est = posts["reach_is_estimate"].sum()
    if est:
        emit(f"  note: {est} of {len(posts)} reach figures are rounded estimates")
    emit()

    # Posts outside the application window can't have driven applications.
    in_window = posts[
        (posts["post_date"] >= window_start) & (posts["post_date"] <= window_end)
    ]
    out_window = posts[~posts.index.isin(in_window.index)]

    emit(f"APPLICATION WINDOW: {window_start} to {window_end}")
    emit(f"  posts inside the window : {len(in_window)}")
    if len(out_window):
        emit(f"  posts outside (excluded from attribution):")
        for r in out_window.itertuples():
            emit(f"    {r.post_date}  {r.description}")
    emit()

    # Baseline: mean applications on days with no post in the window.
    post_days = set()
    for r in in_window.itertuples():
        for offset in range(ATTRIBUTION_WINDOW_DAYS + 1):
            post_days.add(r.post_date + pd.Timedelta(days=offset))

    quiet = daily[[d not in post_days for d in daily.index]]
    baseline = quiet.mean()

    emit(f"BASELINE (days with no post, +{ATTRIBUTION_WINDOW_DAYS}d window)")
    emit(f"  quiet days        : {len(quiet)}")
    emit(f"  mean applications : {baseline:.1f}/day")
    emit()

    emit(f"POST-DAY ALIGNMENT (+{ATTRIBUTION_WINDOW_DAYS}d)")
    rows = []
    for r in in_window.itertuples():
        days = [
            r.post_date + pd.Timedelta(days=offset)
            for offset in range(ATTRIBUTION_WINDOW_DAYS + 1)
        ]
        observed = int(sum(daily.get(d, 0) for d in days))
        expected = baseline * len(days)
        lift = observed - expected
        # Applications per 1,000 reached. This is the only conversion-like
        # figure the data supports: shares are amplification, not intent,
        # so reach is the denominator.
        per_1k = 1000 * observed / r.reach if r.reach else float("nan")
        rows.append(
            {
                "post_date": r.post_date,
                "description": r.description,
                "reach": r.reach,
                "shares": r.shares,
                "applications": observed,
                "expected": round(expected, 1),
                "excess": round(lift, 1),
                "apps_per_1k_reach": round(per_1k, 2),
            }
        )
        emit(f"  {r.post_date}  {r.description}")
        emit(f"      reach {r.reach:>6,}   shares {r.shares:>4}")
        emit(
            f"      applications in window: {observed:>3}   "
            f"expected {expected:>5.1f}   excess {lift:>+5.1f}"
        )
        emit(f"      applications per 1,000 reached: {per_1k:.2f}")
        emit()

    attributed = sum(r["applications"] for r in rows)
    emit(f"  applications on post days: {attributed}/{len(apps)} "
         f"({100*attributed/len(apps):.0f}% of the pool)")
    emit()
    emit("  Caveat: this is timing correlation, not tracked attribution.")
    emit("  Only 9% of applications carry a utm_source, and other channels")
    emit("  (Discord, word of mouth, club newsletters) are not observable here.")
    emit("  No click-through data exists: the per-post engagement metric is")
    emit("  shares, which measures amplification rather than intent, so the")
    emit("  link between a post and an application cannot be traced per user.")

    REPORTS.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(
        DATA_PROCESSED / "post_attribution.csv", index=False
    )
    (REPORTS / "social_attribution.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
