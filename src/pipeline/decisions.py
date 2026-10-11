"""Compare the stated selection criteria against the actual decisions.

Reviewers rated applicants on experience first, then project depth and
variety. None of that was stored as a score, so the ratings themselves
are gone. What survives is the inputs reviewers were looking at and the
decision they reached, which is enough to ask whether the decisions
line up with the stated criteria.

Caveat that belongs on every number below: n=107, and most subgroups are
far smaller. Differences of a few percentage points are noise. Where a
split has fewer than 10 people on either side it is reported but not
interpreted.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DATA_PROCESSED, REPORTS  # noqa: E402

MIN_GROUP = 10  # below this, report the count and don't draw a conclusion


def rate_table(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Acceptance rate broken down by one column."""
    decided = df[df["decision"].isin(["accepted", "denied"])]
    grouped = decided.groupby(by)["decision"]
    table = pd.DataFrame(
        {
            "n": grouped.size(),
            "accepted": grouped.apply(lambda s: (s == "accepted").sum()),
        }
    )
    table["rate"] = (100 * table["accepted"] / table["n"]).round(1)
    table["interpretable"] = table["n"] >= MIN_GROUP
    return table.sort_values("n", ascending=False)


def main() -> None:
    df = pd.read_csv(DATA_PROCESSED / "applicants_with_teams.csv")
    decided = df[df["decision"].isin(["accepted", "denied"])]

    lines: list[str] = []

    def emit(text: str = "") -> None:
        print(text)
        lines.append(text)

    emit("FUNNEL")
    emit(f"  applications in this export : {len(df)}")
    emit(f"  decided                     : {len(decided)}")
    emit(f"  accepted                    : {(df['decision'] == 'accepted').sum()}")
    emit(f"  denied                      : {(df['decision'] == 'denied').sum()}")
    emit(f"  still awaiting              : {(df['decision'] == 'undecided').sum()}")
    rate = 100 * (decided["decision"] == "accepted").mean()
    emit(f"  acceptance rate             : {rate:.1f}%")
    emit()
    emit("  after acceptance:")
    emit(f"    revoked RSVP   : {(df['attending_status'] == 'revoked_rsvp').sum()}")
    emit(f"    kicked out     : {(df['attending_status'] == 'kicked_out').sum()}")
    emit(
        f"    still attending: "
        f"{(df['attending_status'] == 'attending').sum()}"
    )
    emit()

    emit("SIGNALS REVIEWERS SAW")
    for col, label in [
        ("has_portfolio", "gave a GitHub/portfolio link"),
        ("has_resume", "gave a resume link"),
        ("has_linkedin", "gave a LinkedIn"),
        ("listed_teammates", "applied with teammates"),
    ]:
        table = rate_table(decided, col)
        emit(f"\n  {label}:")
        for idx, row in table.iterrows():
            flag = "" if row["interpretable"] else "   (n too small)"
            emit(
                f"    {str(idx):>6}  n={int(row['n']):>3}  "
                f"accepted {int(row['accepted']):>3}  {row['rate']:>5.1f}%{flag}"
            )

    emit()
    emit("ESSAY LENGTH (words in the adaptability answer)")
    for decision in ["accepted", "denied"]:
        subset = decided[decided["decision"] == decision]["essay_length"]
        emit(
            f"  {decision:>8}: n={len(subset):>3}  "
            f"median={subset.median():>5.0f}  mean={subset.mean():>6.1f}  "
            f"p25={subset.quantile(.25):>4.0f}  p75={subset.quantile(.75):>4.0f}"
        )

    emit()
    emit("BY SCHOOL (groups of 10+ only interpreted)")
    table = rate_table(decided, "school")
    for idx, row in table.iterrows():
        flag = "" if row["interpretable"] else "   (n too small)"
        emit(
            f"  {str(idx)[:34]:<34} n={int(row['n']):>3}  "
            f"{row['rate']:>5.1f}%{flag}"
        )

    emit()
    emit("APPLICATION TIMING")
    by_date = df.groupby("applied_date").size()
    emit(f"  window      : {by_date.index.min()} to {by_date.index.max()}")
    emit(f"  busiest days:")
    for date, count in by_date.sort_values(ascending=False).head(5).items():
        emit(f"    {date}  {count:>3}")

    emit()
    emit("UTM COVERAGE")
    tagged = df["utm_source"].notna().sum()
    emit(f"  applications with a utm_source: {tagged}/{len(df)} "
         f"({100*tagged/len(df):.0f}%)")
    for source, count in df["utm_source"].value_counts().items():
        emit(f"    {source:<28} {count:>3}")
    emit("  Coverage is too low to attribute the pool to channels.")

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "decision_analysis.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
