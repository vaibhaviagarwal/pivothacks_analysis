"""Shared paths and column names.

The raw export's column headers are the full question text from the
registration form, which makes them unusable as identifiers. Everything
downstream refers to the short names defined here instead, so that a
change to the form's wording only has to be handled in one place.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

RAW_EXPORT = DATA_RAW / "pivot_attendees_export.csv"

# Form questions -> short names. The keys must match the export exactly.
COLUMN_RENAMES = {
    "Are you applying with teammates? If so, list their names below. We'll make "
    "every effort to keep accepted teams together, but admission decisions are "
    "made on an individual basis.": "teammates_raw",
    "PIVOT introduces a new constraint every 2 hours. Tell us about a time you "
    "had to quickly adapt to changing requirements or unexpected challenges "
    "(ie. while building something).": "adaptability_essay",
    "What is your GitHub / Portfolio / Personal Website?": "portfolio_url",
    "What is your LinkedIn profile?": "linkedin_url",
    "Please add a link to your resume. (make sure to enable visibility "
    "settings)": "resume_url",
    "Will you be able to attend it in person in Waterloo? (this is an "
    "in-person hackathon)": "can_attend_in_person",
    "What School/University are you attending?": "school_raw",
    "Industry you last worked in": "industry_raw",
    "City you are based in": "city_raw",
    "Program": "program_raw",
    "Accommodations": "accommodations",
    "Pronouns": "pronouns",
}

# Columns that are entirely empty in the export. Recorded here rather than
# silently dropped, because "this field was never populated" is a finding
# about how the event was run, not noise to hide.
EMPTY_COLUMNS = [
    "payment_status",
    "payment_expiry_date",
    "coupon_code",
    "group_leader_id",
    "checked_in_at",
]

# Values people type when they mean "nothing here".
NULL_ANSWERS = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "n.a.",
    "no",
    "none",
    "no answer",
    "no answer.",
    "nope",
    "nil",
    "not applicable",
}

# attending_status values, grouped by what they mean for the funnel.
STATUS_ACCEPTED = {"attending", "revoked_rsvp", "kicked_out"}
STATUS_DENIED = {"denied"}
STATUS_UNDECIDED = {"awaiting_approval"}
