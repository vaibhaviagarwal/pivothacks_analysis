"""Load the raw export and normalize the messy free-text fields.

The two fields that need real work are school and program. Applicants
typed them freely, so the same institution appears under half a dozen
spellings. Everything here is deliberately rule-based rather than fuzzy:
with ~100 rows the mapping is small enough to be explicit, and an
explicit mapping can be reviewed and argued with, which a similarity
threshold cannot.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (  # noqa: E402
    COLUMN_RENAMES,
    DATA_PROCESSED,
    NULL_ANSWERS,
    RAW_EXPORT,
    STATUS_ACCEPTED,
    STATUS_DENIED,
    STATUS_UNDECIDED,
)


# Canonical school name -> patterns that should map to it. Patterns are
# matched against the lowercased, punctuation-stripped input, so
# "University Of Waterloo", "uwaterloo" and "Waterloo" all collapse.
SCHOOL_PATTERNS: dict[str, list[str]] = {
    "University of Waterloo": [
        "university of waterloo",
        "uwaterloo",
        "u waterloo",
        "waterloo",
        "uw",
    ],
    "University of Toronto": [
        "university of toronto",
        "uoft",
        "u of t",
        "toronto metropolitan",  # handled separately below if needed
    ],
    "Wilfrid Laurier University": [
        "wilfrid laurier",
        "wilfred laurier",
        "laurier",
        "wlu",
    ],
    "McMaster University": ["mcmaster", "mac"],
    "York University": ["york university", "york u"],
    "University of Guelph": ["university of guelph", "guelph"],
    "University of Ottawa": ["university of ottawa", "uottawa", "ottawa u"],
    "University of Oxford": ["university of oxford", "oxford"],
    "Conestoga College": ["conestoga"],
    "Not currently enrolled": ["graduated", "none", "not in school", "working"],
}

# "toronto metropolitan" must not fall through to University of Toronto,
# so it gets its own entry checked before the substring pass.
EXACT_OVERRIDES: dict[str, str] = {
    "toronto metropolitan university": "Toronto Metropolitan University",
    "tmu": "Toronto Metropolitan University",
    "ryerson": "Toronto Metropolitan University",
}


def normalize_text(value: object) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace.

    Used as the comparison key everywhere. Keeping it in one function
    means the school mapping and the name matching in teams.py agree on
    what "the same string" means.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_null_answer(value: object) -> bool:
    """Whether a free-text answer means 'nothing here'."""
    return normalize_text(value) in NULL_ANSWERS


def canonical_school(raw: object) -> tuple[str, str]:
    """Map a free-text school to a canonical name.

    Returns (canonical_name, match_method) so the caller can report how
    many rows were resolved confidently versus left alone. Unmatched
    values are passed through unchanged rather than bucketed into
    "Other", because losing them hides the long tail.
    """
    key = normalize_text(raw)
    if not key or key in NULL_ANSWERS:
        return "Unknown", "null"

    if key in EXACT_OVERRIDES:
        return EXACT_OVERRIDES[key], "override"

    for canonical, patterns in SCHOOL_PATTERNS.items():
        for pattern in patterns:
            if key == pattern:
                return canonical, "exact"

    for canonical, patterns in SCHOOL_PATTERNS.items():
        for pattern in patterns:
            # Word-boundary match so "uw" doesn't fire inside "uwo".
            if re.search(rf"\b{re.escape(pattern)}\b", key):
                return canonical, "substring"

    return str(raw).strip(), "unmatched"


def decision_bucket(status: object) -> str:
    """Collapse attending_status into accepted / denied / undecided.

    revoked_rsvp and kicked_out were both accepted at decision time;
    they left afterwards. Treating them as denials would understate the
    acceptance rate, so the distinction is kept in a separate column.
    """
    value = str(status).strip().lower()
    if value in STATUS_ACCEPTED:
        return "accepted"
    if value in STATUS_DENIED:
        return "denied"
    if value in STATUS_UNDECIDED:
        return "undecided"
    return "unknown"


def load_raw(path: Path = RAW_EXPORT) -> pd.DataFrame:
    """Read the export and apply short column names."""
    df = pd.read_csv(path)
    return df.rename(columns=COLUMN_RENAMES)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Add normalized columns. The raw columns are kept alongside."""
    out = df.copy()

    out["email_key"] = out["email"].fillna("").str.strip().str.lower()
    out["full_name"] = (
        out["first_name"].fillna("").str.strip()
        + " "
        + out["last_name"].fillna("").str.strip()
    ).str.strip()
    out["name_key"] = out["full_name"].map(normalize_text)

    schools = out["school_raw"].map(canonical_school)
    out["school"] = [s for s, _ in schools]
    out["school_match_method"] = [m for _, m in schools]

    out["decision"] = out["attending_status"].map(decision_bucket)
    out["left_after_acceptance"] = out["attending_status"].isin(
        {"revoked_rsvp", "kicked_out"}
    )

    out["has_portfolio"] = ~out["portfolio_url"].map(is_null_answer)
    out["has_resume"] = ~out["resume_url"].map(is_null_answer)
    out["has_linkedin"] = ~out["linkedin_url"].map(is_null_answer)
    out["essay_length"] = (
        out["adaptability_essay"].fillna("").astype(str).str.split().str.len()
    )
    out["listed_teammates"] = ~out["teammates_raw"].map(is_null_answer)

    out["applied_at"] = pd.to_datetime(
        out["created_at"], format="mixed", utc=True
    )
    out["applied_date"] = out["applied_at"].dt.date

    return out


def main() -> None:
    df = load_raw()
    cleaned = clean(df)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "applicants_clean.csv"
    cleaned.to_csv(out_path, index=False)

    print(f"rows in  : {len(df)}")
    print(f"rows out : {len(cleaned)}")
    print()
    print("school normalization:")
    print(f"  distinct raw strings      : {df['school_raw'].nunique()}")
    print(f"  distinct canonical schools: {cleaned['school'].nunique()}")
    print()
    print(cleaned["school_match_method"].value_counts().to_string())
    print()
    unmatched = cleaned.loc[
        cleaned["school_match_method"] == "unmatched", "school_raw"
    ].unique()
    if len(unmatched):
        print("unmatched school strings (left as typed):")
        for value in unmatched:
            print(f"  - {value}")
    print()
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
