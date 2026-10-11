"""Score the inferred team graph against the real problem assignments.

teams.py reconstructs who worked with whom from a free-text box. The
problem assignment list records who actually ended up on which team. One
is a guess, the other is ground truth, so the guess can be measured.

This is the part that makes the project defensible: instead of claiming
the matching works, it reports precision and recall on teammate pairs
and names every case it got wrong.
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DATA_PROCESSED, DATA_RAW, REPORTS  # noqa: E402
from pipeline.clean import normalize_text  # noqa: E402
from pipeline.teams import (  # noqa: E402
    build_roster_indexes,
    match_name,
)


def load_truth(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resolve the assigned names to roster user_ids.

    Reuses the same matcher teams.py uses, so a name that the matcher
    cannot resolve here is the same kind of failure it has there. Names
    that resolve to nobody are reported: they are participants who never
    appear in the registration export at all.
    """
    truth_raw = pd.read_csv(DATA_RAW / "problem_assignments.csv")
    by_full, by_first, by_surname_initial = build_roster_indexes(df)

    rows = []
    for row in truth_raw.itertuples():
        if pd.isna(row.assigned_names):
            continue
        for raw_name in str(row.assigned_names).split(","):
            raw_name = raw_name.strip().rstrip(".")
            if not raw_name:
                continue
            match = match_name(raw_name, by_full, by_first, by_surname_initial)
            rows.append(
                {
                    "problem_number": row.problem_number,
                    "problem_title": row.problem_title,
                    "assigned_name": raw_name,
                    "user_id": match.matched_user_id,
                    "method": match.method,
                }
            )
    return pd.DataFrame(rows), truth_raw


def pairs_from_groups(df: pd.DataFrame, group_col: str, id_col: str) -> set:
    """All unordered teammate pairs implied by a grouping."""
    out = set()
    for _, group in df.dropna(subset=[id_col]).groupby(group_col):
        ids = sorted(group[id_col].unique())
        for a, b in combinations(ids, 2):
            out.add((a, b))
    return out


def main() -> None:
    applicants = pd.read_csv(DATA_PROCESSED / "applicants_with_teams.csv")
    truth, truth_raw = load_truth(applicants)

    name_to_id = dict(zip(applicants["user_id"], applicants["full_name"]))

    matched = truth["user_id"].notna().sum()
    print("GROUND TRUTH COVERAGE")
    print(f"  problems with assignments : {truth['problem_number'].nunique()}")
    print(f"  names on the sheet        : {len(truth)}")
    print(f"  resolved to the roster    : {matched}/{len(truth)}")
    print()
    print(truth["method"].value_counts().to_string())

    missing = truth[truth["user_id"].isna()]
    if len(missing):
        print()
        print(f"  participants NOT in the registration export ({len(missing)}):")
        for r in missing.itertuples():
            print(f"    P{r.problem_number:<3} {r.assigned_name}")

    # Did everyone who competed actually get accepted?
    resolved = truth.dropna(subset=["user_id"]).merge(
        applicants[["user_id", "decision", "attending_status", "full_name"]],
        on="user_id",
        how="left",
    )
    print()
    print("STATUS OF ACTUAL COMPETITORS")
    print(resolved["attending_status"].value_counts().to_string())

    # Score the inferred graph.
    truth_pairs = pairs_from_groups(
        truth.dropna(subset=["user_id"]), "problem_number", "user_id"
    )
    inferred_pairs = pairs_from_groups(
        applicants[applicants["user_id"].isin(truth["user_id"].dropna())],
        "team_id",
        "user_id",
    )

    tp = truth_pairs & inferred_pairs
    fp = inferred_pairs - truth_pairs
    fn = truth_pairs - inferred_pairs

    precision = len(tp) / len(inferred_pairs) if inferred_pairs else 0.0
    recall = len(tp) / len(truth_pairs) if truth_pairs else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    print()
    print("INFERRED GRAPH vs ACTUAL TEAMS (teammate pairs)")
    print(f"  true teammate pairs     : {len(truth_pairs)}")
    print(f"  inferred pairs          : {len(inferred_pairs)}")
    print(f"  correct   (TP)          : {len(tp)}")
    print(f"  wrong     (FP)          : {len(fp)}")
    print(f"  missed    (FN)          : {len(fn)}")
    print(f"  precision               : {precision:.2f}")
    print(f"  recall                  : {recall:.2f}")
    print(f"  f1                      : {f1:.2f}")

    if fp:
        print()
        print("  pairs we invented:")
        for a, b in sorted(fp)[:10]:
            print(f"    {name_to_id.get(a, a)} <-> {name_to_id.get(b, b)}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    truth.to_csv(DATA_PROCESSED / "ground_truth_teams.csv", index=False)

    with open(REPORTS / "team_inference_scorecard.txt", "w") as fh:
        fh.write(
            f"teammate-pair precision {precision:.3f}\n"
            f"teammate-pair recall    {recall:.3f}\n"
            f"f1                      {f1:.3f}\n"
            f"ground-truth names      {len(truth)}\n"
            f"resolved to roster      {matched}\n"
        )


if __name__ == "__main__":
    main()
