"""Reconstruct teams from the free-text teammate field.

The registration platform has a team feature (group_leader_id,
is_group_leader) but it went unused: group_leader_id is empty for every
row and is_group_leader is False for every row. The only record of who
intended to work with whom is a text box where applicants typed their
teammates' names.

So teams have to be recovered by matching those typed names against the
applicant roster. That matching is the hard part and it is not fully
solvable: people typed first names only, nicknames, misspellings, and
names of friends who never applied. Everything here is built to make the
uncertainty visible rather than to hide it behind a confidence score.

The output is a graph where an edge means "A named B". Edges are
directed at first, because listing is often one-sided, and the analysis
reports how often it was mutual.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DATA_PROCESSED  # noqa: E402
from pipeline.clean import is_null_answer, normalize_text  # noqa: E402


# Separators people actually used between names.
SPLIT_PATTERN = re.compile(r"[,;/&\n]| and | \+ ", flags=re.IGNORECASE)

# Phrases that are prose rather than a name. Checked after splitting.
NON_NAME_PHRASES = {
    "i am single",
    "single",
    "solo",
    "alone",
    "by myself",
    "just me",
    "myself",
    "no teammates",
    "not yet",
    "tbd",
    "looking for a team",
    "no team",
    "none yet",
    "open to teaming up",
    "i dont have a team",
    "i do not have a team",
}


@dataclass
class NameMatch:
    """One typed name, resolved (or not) against the roster."""

    raw: str
    normalized: str
    matched_user_id: str | None
    method: str  # exact | surname_initial | firstname_unique | unmatched


def split_names(text: str) -> list[str]:
    """Break a teammate answer into individual candidate names."""
    if is_null_answer(text):
        return []
    parts = SPLIT_PATTERN.split(str(text))
    names = []
    for part in parts:
        cleaned = part.strip()
        if not cleaned:
            continue
        if normalize_text(cleaned) in NON_NAME_PHRASES:
            continue
        # A "name" of one character or more than five words is prose.
        words = normalize_text(cleaned).split()
        if not words or len(words) > 5 or len(normalize_text(cleaned)) < 2:
            continue
        names.append(cleaned)
    return names


def build_roster_indexes(df: pd.DataFrame) -> tuple[dict, dict, dict]:
    """Index the roster by the keys we can match against.

    Returns three lookups:
      by_full    : "vaibhavi agarwal" -> [user_id, ...]
      by_first   : "vaibhavi"         -> [user_id, ...]
      by_surname_initial : ("agarwal", "v") -> [user_id, ...]

    Each maps to a LIST, because collisions are the thing we care about.
    A first name that matches three people is not a match.
    """
    by_full: dict[str, list[str]] = defaultdict(list)
    by_first: dict[str, list[str]] = defaultdict(list)
    by_surname_initial: dict[tuple[str, str], list[str]] = defaultdict(list)

    for row in df.itertuples():
        uid = row.user_id
        first = normalize_text(row.first_name)
        last = normalize_text(row.last_name)
        full = normalize_text(f"{first} {last}")

        if full:
            by_full[full].append(uid)
        if first:
            by_first[first].append(uid)
        if last and first:
            by_surname_initial[(last, first[0])].append(uid)

    return dict(by_full), dict(by_first), dict(by_surname_initial)


def match_name(
    raw: str,
    by_full: dict,
    by_first: dict,
    by_surname_initial: dict,
) -> NameMatch:
    """Resolve one typed name to a roster entry, or report why not.

    Tried in descending order of confidence. Each tier only matches when
    the result is unambiguous: a tier that returns several candidates is
    treated as no match, because a wrong edge is worse than a missing
    one when the whole point is reconstructing who worked with whom.
    """
    key = normalize_text(raw)
    if not key:
        return NameMatch(raw, key, None, "unmatched")

    # Tier 1: full name, exactly.
    candidates = by_full.get(key, [])
    if len(candidates) == 1:
        return NameMatch(raw, key, candidates[0], "exact")
    if len(candidates) > 1:
        return NameMatch(raw, key, None, "ambiguous_full")

    words = key.split()

    # Tier 2: "Agarwal V" or "V Agarwal" style, surname plus initial.
    if len(words) == 2:
        for surname, initial in ((words[1], words[0][0]), (words[0], words[1][0])):
            candidates = by_surname_initial.get((surname, initial), [])
            if len(candidates) == 1:
                return NameMatch(raw, key, candidates[0], "surname_initial")

    # Tier 3: first name alone, only if it is unique on the roster.
    if len(words) == 1:
        candidates = by_first.get(words[0], [])
        if len(candidates) == 1:
            return NameMatch(raw, key, candidates[0], "firstname_unique")
        if len(candidates) > 1:
            return NameMatch(raw, key, None, "ambiguous_firstname")

    return NameMatch(raw, key, None, "unmatched")


def build_edges(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Produce the directed edge list and the per-name match log.

    The match log is the honest record: every name anyone typed, and
    what happened to it. It is what makes the coverage claim checkable.
    """
    by_full, by_first, by_surname_initial = build_roster_indexes(df)

    edges = []
    log = []

    for row in df.itertuples():
        source = row.user_id
        for raw_name in split_names(row.teammates_raw):
            match = match_name(raw_name, by_full, by_first, by_surname_initial)
            log.append(
                {
                    "source_user_id": source,
                    "source_name": row.full_name,
                    "typed_name": match.raw,
                    "matched_user_id": match.matched_user_id,
                    "method": match.method,
                }
            )
            if match.matched_user_id and match.matched_user_id != source:
                edges.append(
                    {
                        "source": source,
                        "target": match.matched_user_id,
                    }
                )

    return pd.DataFrame(edges), pd.DataFrame(log)


def connected_components(edges: pd.DataFrame, nodes: list[str]) -> dict[str, int]:
    """Group users into teams by treating edges as undirected.

    Union-find. A team is a connected component: if A named B and B
    named C, all three end up together even though nobody named all
    three. That is usually right for hackathon teams and occasionally
    wrong, which is why component sizes get reported.
    """
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for row in edges.itertuples():
        if row.source in parent and row.target in parent:
            union(row.source, row.target)

    roots = {}
    component_id = {}
    next_id = 0
    for n in nodes:
        r = find(n)
        if r not in roots:
            roots[r] = next_id
            next_id += 1
        component_id[n] = roots[r]
    return component_id


def main() -> None:
    df = pd.read_csv(DATA_PROCESSED / "applicants_clean.csv")

    edges, log = build_edges(df)

    nodes = df["user_id"].tolist()
    component_id = connected_components(edges, nodes)
    df["team_id"] = df["user_id"].map(component_id)

    sizes = df["team_id"].value_counts()
    multi = sizes[sizes > 1]

    # Mutual listing: both directions present.
    pairs = {(r.source, r.target) for r in edges.itertuples()}
    mutual = {(a, b) for (a, b) in pairs if (b, a) in pairs}

    edges.to_csv(DATA_PROCESSED / "team_edges.csv", index=False)
    log.to_csv(DATA_PROCESSED / "name_match_log.csv", index=False)
    df.to_csv(DATA_PROCESSED / "applicants_with_teams.csv", index=False)

    print("NAME RESOLUTION")
    print(f"  names typed across all answers : {len(log)}")
    print(f"  people who listed anyone       : {df['listed_teammates'].sum()}")
    print()
    print(log["method"].value_counts().to_string())
    resolved = log["matched_user_id"].notna().sum()
    pct = 100 * resolved / len(log) if len(log) else 0
    print(f"\n  resolved to roster: {resolved}/{len(log)} ({pct:.0f}%)")
    print()
    print("TEAM GRAPH")
    print(f"  directed edges        : {len(edges)}")
    print(f"  mutual pairs          : {len(mutual) // 2}")
    print(f"  one-sided listings    : {len(pairs) - len(mutual)}")
    print(f"  components with 2+    : {len(multi)}")
    print(f"  people in a team      : {int(multi.sum())}")
    print(f"  people unteamed       : {len(df) - int(multi.sum())}")
    print()
    print("  team sizes:")
    print(multi.value_counts().sort_index().to_string())
    print()
    unmatched = log[log["matched_user_id"].isna()]
    if len(unmatched):
        print(f"  unresolved names ({len(unmatched)}) — sample:")
        for r in unmatched.head(12).itertuples():
            print(f"    {r.typed_name!r:32} [{r.method}]")


if __name__ == "__main__":
    main()
