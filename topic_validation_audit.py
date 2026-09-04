from pathlib import Path
import os
import re

import pandas as pd

# Reuse the production classifier rather than duplicating its rules.
from lis_pipeline import derive_topics_with_rules
from lis_common import configured_years


# =========================================================
# CONFIG
# =========================================================

YEAR = int(
    os.environ.get(
        "LIS_ANALYSIS_YEAR",
        str(configured_years()[0]),
    )
)

PROCESSED_ROOT = Path("data/processed")
QA_ROOT = Path("data/qa")

QA_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)

RANDOM_STATE = 42

SAMPLE_PER_TOPIC = 5
SAMPLE_PER_RULE = 2
UNCLASSIFIED_SAMPLE_SIZE = 50
OFFICIAL_SAMPLE_SIZE = 25
SUMMARY_SELECTION_SAMPLE_SIZE = 25


# =========================================================
# HIGH-RISK RULES
#
# These rules are NOT automatically wrong.
# They receive extra QA attention because they are broad
# enough to match incidental language.
# =========================================================

HIGH_RISK_RULES = {
    r"\bminors?\b":
        "Generic population descriptor",

    r"\bcommercial\b":
        "Generic adjective",

    r"\belectronically\b":
        "Delivery method may not represent technology policy",

    r"\blocalit":
        "Locality may be incidental rather than local-government policy",

    r"\bstudents?\b":
        "Student reference may be incidental",

    r"\beducation\b":
        "Broad term may overlap Higher Education",

    r"\bchildren\b":
        "Children may be affected population or organization name",

    r"\bworkforce\b":
        "May occur in organization names or general context",

    r"\bemployees?\b":
        "Broad employment term",

    r"\bmedical\b":
        "Broad health-related term",

    r"\bcoverage\b":
        "Coverage can occur outside insurance substance",

    r"\brevenue\b":
        "Revenue may be incidental fiscal language",
}


# =========================================================
# CEREMONIAL / NON-SUBSTANTIVE CANDIDATES
#
# QA ONLY.
#
# We are not modifying production classification here.
# =========================================================

CEREMONIAL_PATTERNS = [
    r"^\s*commending\b",
    r"^\s*celebrating the life\b",
    r"^\s*celebrating\b",
    r"^\s*honoring\b",
    r"^\s*recognizing\b",
]


# =========================================================
# POTENTIALLY REDUNDANT TOPIC PAIRS
#
# These are review candidates, not automatic errors.
# =========================================================

REDUNDANT_TOPIC_PAIRS = [
    (
        "Education",
        "Higher Education",
    ),
]


# =========================================================
# BASIC HELPERS
# =========================================================

def require_file(path):

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )


def load_csv(path):

    require_file(path)

    return pd.read_csv(
        path,
        dtype=str,
    )


def clean_string_series(series):

    return (
        series
        .fillna("")
        .astype(str)
        .str.strip()
    )


def normalize_bill_id(series):

    return (
        clean_string_series(series)
        .str.upper()
    )


def safe_bool(value):

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
    }


def join_sorted(values):

    return " | ".join(
        sorted(
            {
                str(value).strip()
                for value in values
                if str(value).strip()
            }
        )
    )


# =========================================================
# LOAD CURRENT PIPELINE OUTPUTS
# =========================================================

def load_data(year):

    paths = {
        "summary":
            PROCESSED_ROOT
            / f"derived_from_lis_bill_summary_{year}.csv",

        "description":
            PROCESSED_ROOT
            / f"derived_from_lis_bill_description_{year}.csv",

        "unclassified":
            PROCESSED_ROOT
            / f"unclassified_bills_{year}.csv",

        "topic_lookup":
            PROCESSED_ROOT
            / f"bill_topic_lookup_{year}.csv",

        "bill_lookup":
            PROCESSED_ROOT
            / f"bill_lookup_{year}.csv",

        "summary_lookup":
            PROCESSED_ROOT
            / f"bill_summary_lookup_{year}.csv",

        "official":
            PROCESSED_ROOT
            / f"official_lis_subjects_{year}.csv",
    }

    data = {}

    for name, path in paths.items():
        data[name] = load_csv(path)

    # Normalize Bill_id everywhere.
    for dataframe in data.values():

        if "Bill_id" in dataframe.columns:

            dataframe["Bill_id"] = normalize_bill_id(
                dataframe["Bill_id"]
            )

    return data


# =========================================================
# COMBINE DERIVED CLASSIFICATIONS
# =========================================================

def combine_derived(
    summary,
    description,
):

    derived = pd.concat(
        [
            summary,
            description,
        ],
        ignore_index=True,
    )

    required = {
        "Bill_id",
        "topic_name",
        "classification",
        "source_file",
        "source_text_used",
        "matched_rule",
    }

    missing = (
        required
        -
        set(derived.columns)
    )

    if missing:

        raise ValueError(
            "Derived classification files are "
            f"missing required columns: {sorted(missing)}"
        )

    for column in required:

        derived[column] = clean_string_series(
            derived[column]
        )

    derived["Bill_id"] = normalize_bill_id(
        derived["Bill_id"]
    )

    return derived


# =========================================================
# RULE-LEVEL POPULATION AUDIT
# =========================================================

def build_rule_audit(
    derived,
):

    audit = (
        derived
        .groupby(
            [
                "classification",
                "topic_name",
                "matched_rule",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            assignment_rows=(
                "Bill_id",
                "size",
            ),

            unique_bills=(
                "Bill_id",
                "nunique",
            ),
        )
    )

    audit["high_risk_rule"] = (
        audit["matched_rule"]
        .isin(HIGH_RISK_RULES)
    )

    audit["risk_reason"] = (
        audit["matched_rule"]
        .map(HIGH_RISK_RULES)
        .fillna("")
    )

    # These are intentionally blank.
    # They can later be populated from human/model QA.
    audit["qa_true_positive"] = ""
    audit["qa_borderline"] = ""
    audit["qa_false_positive"] = ""
    audit["qa_precision_pct"] = ""
    audit["qa_recommendation"] = ""
    audit["qa_notes"] = ""

    return (
        audit
        .sort_values(
            [
                "high_risk_rule",
                "assignment_rows",
                "topic_name",
                "matched_rule",
            ],
            ascending=[
                False,
                False,
                True,
                True,
            ],
        )
        .reset_index(drop=True)
    )


# =========================================================
# CEREMONIAL DETECTION
# =========================================================

def is_ceremonial_text(text):

    if pd.isna(text):
        return False

    text = str(text)

    return any(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        is not None
        for pattern in CEREMONIAL_PATTERNS
    )


def build_ceremonial_candidates(
    derived,
):

    result = derived.copy()

    result["ceremonial_candidate"] = (
        result["source_text_used"]
        .map(is_ceremonial_text)
    )

    result = result[
        result["ceremonial_candidate"]
    ].copy()

    result["qa_judgment"] = ""
    result["qa_confidence"] = ""
    result["qa_reason"] = ""
    result["qa_recommended_action"] = ""

    return (
        result
        .sort_values(
            [
                "Bill_id",
                "topic_name",
            ]
        )
        .reset_index(drop=True)
    )


# =========================================================
# HIGH-RISK RULE ROWS
# =========================================================

def build_high_risk_rule_rows(
    derived,
):

    result = derived[
        derived["matched_rule"]
        .isin(HIGH_RISK_RULES)
    ].copy()

    result["risk_reason"] = (
        result["matched_rule"]
        .map(HIGH_RISK_RULES)
        .fillna("")
    )

    result["qa_judgment"] = ""
    result["qa_confidence"] = ""
    result["qa_reason"] = ""
    result["qa_recommended_action"] = ""

    return (
        result
        .sort_values(
            [
                "matched_rule",
                "topic_name",
                "Bill_id",
            ]
        )
        .reset_index(drop=True)
    )


# =========================================================
# TOPIC COUNT PER BILL
# =========================================================

def build_topic_count_by_bill(
    derived,
):

    result = (
        derived
        .groupby(
            [
                "Bill_id",
                "classification",
            ],
            as_index=False,
        )
        .agg(
            topic_count=(
                "topic_name",
                "nunique",
            ),

            topics=(
                "topic_name",
                join_sorted,
            ),
        )
    )

    return (
        result
        .sort_values(
            [
                "topic_count",
                "Bill_id",
            ],
            ascending=[
                False,
                True,
            ],
        )
        .reset_index(drop=True)
    )


# =========================================================
# MULTI-TOPIC REVIEW CANDIDATES
# =========================================================

def build_multi_topic_candidates(
    derived,
    topic_counts,
):

    suspicious = topic_counts[
        topic_counts["topic_count"] >= 3
    ].copy()

    result = derived.merge(
        suspicious[
            [
                "Bill_id",
                "classification",
                "topic_count",
                "topics",
            ]
        ],
        on=[
            "Bill_id",
            "classification",
        ],
        how="inner",
        validate="many_to_one",
    )

    result["qa_judgment"] = ""
    result["qa_notes"] = ""

    return (
        result
        .sort_values(
            [
                "topic_count",
                "Bill_id",
                "topic_name",
            ],
            ascending=[
                False,
                True,
                True,
            ],
        )
        .reset_index(drop=True)
    )


# =========================================================
# REDUNDANT TOPIC PAIRS
# =========================================================

def build_redundant_topic_candidates(
    derived,
):

    records = []

    grouped = derived.groupby(
        [
            "Bill_id",
            "classification",
        ]
    )

    for (
        bill_id,
        classification
    ), group in grouped:

        topics = set(
            group["topic_name"]
        )

        for (
            broad_topic,
            specific_topic
        ) in REDUNDANT_TOPIC_PAIRS:

            if (
                broad_topic in topics
                and
                specific_topic in topics
            ):

                records.append(
                    {
                        "Bill_id":
                            bill_id,

                        "classification":
                            classification,

                        "broad_topic":
                            broad_topic,

                        "specific_topic":
                            specific_topic,

                        "issue":
                            (
                                f"{broad_topic} + "
                                f"{specific_topic}"
                            ),

                        "qa_judgment":
                            "",

                        "qa_notes":
                            "",
                    }
                )

    return pd.DataFrame(
        records,
        columns=[
            "Bill_id",
            "classification",
            "broad_topic",
            "specific_topic",
            "issue",
            "qa_judgment",
            "qa_notes",
        ],
    )


# =========================================================
# STRATIFIED TOPIC SAMPLE
# =========================================================

def build_topic_manual_sample(
    derived,
):

    samples = []

    grouped = derived.groupby(
        [
            "classification",
            "topic_name",
        ],
        dropna=False,
    )

    for _, group in grouped:

        n = min(
            SAMPLE_PER_TOPIC,
            len(group),
        )

        samples.append(
            group.sample(
                n=n,
                random_state=RANDOM_STATE,
            )
        )

    if not samples:
        return pd.DataFrame()

    result = pd.concat(
        samples,
        ignore_index=True,
    )

    result["qa_judgment"] = ""
    result["qa_confidence"] = ""
    result["qa_reason"] = ""
    result["qa_recommended_action"] = ""

    return (
        result
        .sort_values(
            [
                "classification",
                "topic_name",
                "Bill_id",
            ]
        )
        .reset_index(drop=True)
    )


# =========================================================
# STRATIFIED RULE SAMPLE
# =========================================================

def build_rule_manual_sample(
    derived,
):

    samples = []

    grouped = derived.groupby(
        [
            "classification",
            "topic_name",
            "matched_rule",
        ],
        dropna=False,
    )

    for _, group in grouped:

        n = min(
            SAMPLE_PER_RULE,
            len(group),
        )

        samples.append(
            group.sample(
                n=n,
                random_state=RANDOM_STATE,
            )
        )

    if not samples:
        return pd.DataFrame()

    result = pd.concat(
        samples,
        ignore_index=True,
    )

    result["qa_judgment"] = ""
    result["qa_confidence"] = ""
    result["qa_reason"] = ""
    result["qa_recommended_action"] = ""

    return (
        result
        .sort_values(
            [
                "classification",
                "topic_name",
                "matched_rule",
                "Bill_id",
            ]
        )
        .reset_index(drop=True)
    )


# =========================================================
# UNCLASSIFIED FALSE-NEGATIVE SAMPLE
# =========================================================

def build_unclassified_sample(
    unclassified,
    bill_lookup,
    summary_lookup,
):

    if len(unclassified) == 0:
        return pd.DataFrame()

    n = min(
        UNCLASSIFIED_SAMPLE_SIZE,
        len(unclassified),
    )

    result = (
        unclassified
        .sample(
            n=n,
            random_state=RANDOM_STATE,
        )
        .copy()
    )

    bill_fields = (
        bill_lookup[
            [
                "Bill_id",
                "Bill_description",
            ]
        ]
        .drop_duplicates(
            subset=["Bill_id"]
        )
    )

    summary_fields = (
        summary_lookup[
            [
                "Bill_id",
                "summary_type",
                "summary_text",
            ]
        ]
        .drop_duplicates(
            subset=["Bill_id"]
        )
    )

    # Avoid duplicate column names if the source file
    # already contains one of these fields.
    for column in [
        "Bill_description",
        "summary_type",
        "summary_text",
    ]:

        if column in result.columns:
            result = result.drop(
                columns=[column]
            )

    result = (
        result
        .merge(
            bill_fields,
            on="Bill_id",
            how="left",
            validate="many_to_one",
        )
        .merge(
            summary_fields,
            on="Bill_id",
            how="left",
            validate="many_to_one",
        )
    )

    result["qa_existing_topic_should_apply"] = ""
    result["qa_suggested_topic"] = ""
    result["qa_judgment"] = ""
    result["qa_reason_missed"] = ""
    result["qa_notes"] = ""

    return (
        result
        .sort_values("Bill_id")
        .reset_index(drop=True)
    )


# =========================================================
# OFFICIAL LIS QA SAMPLE
# =========================================================

def build_official_sample(
    official,
):

    if len(official) == 0:
        return pd.DataFrame()

    n = min(
        OFFICIAL_SAMPLE_SIZE,
        len(official),
    )

    result = (
        official
        .sample(
            n=n,
            random_state=RANDOM_STATE,
        )
        .copy()
    )

    result["qa_raw_subject_matches"] = ""
    result["qa_parent_matches"] = ""
    result["qa_topic_rollup_correct"] = ""
    result["qa_judgment"] = ""
    result["qa_notes"] = ""

    sort_columns = [
        column
        for column in [
            "Bill_id",
            "topic_name",
        ]
        if column in result.columns
    ]

    if sort_columns:

        result = result.sort_values(
            sort_columns
        )

    return result.reset_index(
        drop=True
    )


# =========================================================
# SUMMARY-SELECTION SAMPLE
# =========================================================

def build_summary_selection_sample(
    summary_lookup,
):

    if len(summary_lookup) == 0:
        return pd.DataFrame()

    n = min(
        SUMMARY_SELECTION_SAMPLE_SIZE,
        len(summary_lookup),
    )

    result = (
        summary_lookup
        .sample(
            n=n,
            random_state=RANDOM_STATE,
        )
        .copy()
    )

    result["qa_expected_summary_type"] = ""
    result["qa_selection_correct"] = ""
    result["qa_notes"] = ""

    return (
        result
        .sort_values("Bill_id")
        .reset_index(drop=True)
    )


# =========================================================
# INDEPENDENT TEXT CLASSIFICATION
#
# QA ONLY.
#
# This deliberately runs the same production text rules
# against BOTH summary and description regardless of the
# production provenance tier.
# =========================================================

def classify_text_for_qa(text):

    if pd.isna(text):
        return []

    text = str(text).strip()

    if not text:
        return []

    return derive_topics_with_rules(
        text
    )


def topics_from_matches(matches):

    return {
        match["topic_name"]
        for match in matches
        if match.get("topic_name")
    }


# =========================================================
# CROSS-SOURCE COMPARISON
#
# This is useful because the production pipeline normally
# stops at summary classification if summary rules match.
#
# Here we ask:
#
# What would the summary say?
# What would the short description say?
# Do they independently agree?
# =========================================================

def build_cross_source_comparison(
    bill_lookup,
    summary_lookup,
    official,
):

    official_ids = set(
        normalize_bill_id(
            official["Bill_id"]
        )
    )

    bills = (
        bill_lookup[
            [
                "Bill_id",
                "Bill_description",
            ]
        ]
        .drop_duplicates(
            subset=["Bill_id"]
        )
        .copy()
    )

    summaries = (
        summary_lookup[
            [
                "Bill_id",
                "summary_type",
                "summary_text",
            ]
        ]
        .drop_duplicates(
            subset=["Bill_id"]
        )
        .copy()
    )

    combined = bills.merge(
        summaries,
        on="Bill_id",
        how="left",
        validate="one_to_one",
    )

    rows = []

    for _, row in combined.iterrows():

        bill_id = row["Bill_id"]

        description = (
            ""
            if pd.isna(
                row["Bill_description"]
            )
            else
            str(
                row["Bill_description"]
            )
        )

        summary_text = (
            ""
            if pd.isna(
                row["summary_text"]
            )
            else
            str(
                row["summary_text"]
            )
        )

        description_matches = (
            classify_text_for_qa(
                description
            )
        )

        summary_matches = (
            classify_text_for_qa(
                summary_text
            )
        )

        description_topics = (
            topics_from_matches(
                description_matches
            )
        )

        summary_topics = (
            topics_from_matches(
                summary_matches
            )
        )

        shared = (
            summary_topics
            &
            description_topics
        )

        summary_only = (
            summary_topics
            -
            description_topics
        )

        description_only = (
            description_topics
            -
            summary_topics
        )

        union = (
            summary_topics
            |
            description_topics
        )

        if union:

            agreement_score = (
                len(shared)
                /
                len(union)
            )

        else:

            agreement_score = 1.0

        rows.append(
            {
                "Bill_id":
                    bill_id,

                "has_official_lis_subject":
                    bill_id
                    in official_ids,

                "summary_type":
                    (
                        ""
                        if pd.isna(
                            row["summary_type"]
                        )
                        else
                        str(
                            row["summary_type"]
                        )
                    ),

                "summary_topics":
                    join_sorted(
                        summary_topics
                    ),

                "description_topics":
                    join_sorted(
                        description_topics
                    ),

                "shared_topics":
                    join_sorted(
                        shared
                    ),

                "summary_only_topics":
                    join_sorted(
                        summary_only
                    ),

                "description_only_topics":
                    join_sorted(
                        description_only
                    ),

                "summary_topic_count":
                    len(summary_topics),

                "description_topic_count":
                    len(description_topics),

                "shared_topic_count":
                    len(shared),

                "union_topic_count":
                    len(union),

                "agreement_score":
                    round(
                        agreement_score,
                        4,
                    ),

                "Bill_description":
                    description,

                "summary_text":
                    summary_text,
            }
        )

    result = pd.DataFrame(
        rows
    )

    result["needs_review"] = (
        (
            result[
                "summary_topic_count"
            ]
            >
            0
        )
        &
        (
            result[
                "agreement_score"
            ]
            <
            0.50
        )
    )

    return (
        result
        .sort_values(
            [
                "needs_review",
                "agreement_score",
                "Bill_id",
            ],
            ascending=[
                False,
                True,
                True,
            ],
        )
        .reset_index(drop=True)
    )


# =========================================================
# MATCH-STRENGTH MEASUREMENT
#
# Objective text-position evidence.
#
# It does NOT determine whether the topic is substantively
# correct.
# =========================================================

def measure_match_strength(
    text,
    pattern,
):

    if pd.isna(text):
        text = ""

    if pd.isna(pattern):
        pattern = ""

    text = str(text)
    pattern = str(pattern).strip()

    result = {
        "match_count":
            0,

        "first_match_position":
            -1,

        "text_length":
            len(text),

        "relative_match_position":
            None,

        "match_in_first_100_chars":
            False,

        "match_in_first_200_chars":
            False,
    }

    if (
        not text
        or
        not pattern
    ):
        return result

    try:

        matches = list(
            re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
        )

    except re.error as exc:

        raise ValueError(
            "Invalid regex encountered "
            f"during QA: {pattern!r}"
        ) from exc

    if not matches:
        return result

    first_position = (
        matches[0].start()
    )

    text_length = len(text)

    result.update(
        {
            "match_count":
                len(matches),

            "first_match_position":
                first_position,

            "text_length":
                text_length,

            "relative_match_position":
                round(
                    (
                        first_position
                        /
                        text_length
                    )
                    if text_length
                    else
                    0,
                    4,
                ),

            "match_in_first_100_chars":
                first_position < 100,

            "match_in_first_200_chars":
                first_position < 200,
        }
    )

    return result


def build_match_strength_table(
    derived,
):

    rows = []

    for _, row in derived.iterrows():

        strength = measure_match_strength(
            row["source_text_used"],
            row["matched_rule"],
        )

        record = row.to_dict()

        record.update(
            strength
        )

        matched_rule = (
            str(
                row["matched_rule"]
            )
            .strip()
        )

        record["high_risk_rule"] = (
            matched_rule
            in HIGH_RISK_RULES
        )

        record["risk_reason"] = (
            HIGH_RISK_RULES.get(
                matched_rule,
                "",
            )
        )

        rows.append(
            record
        )

    return pd.DataFrame(
        rows
    )


# =========================================================
# DESCRIPTION SUPPORT CACHE
#
# Avoid rerunning the classifier repeatedly for every
# topic row belonging to the same bill.
# =========================================================

def build_description_topic_map(
    bill_lookup,
):

    topic_map = {}

    for _, row in (
        bill_lookup[
            [
                "Bill_id",
                "Bill_description",
            ]
        ]
        .drop_duplicates(
            subset=["Bill_id"]
        )
        .iterrows()
    ):

        bill_id = row["Bill_id"]

        matches = classify_text_for_qa(
            row["Bill_description"]
        )

        topic_map[bill_id] = (
            topics_from_matches(
                matches
            )
        )

    return topic_map


# =========================================================
# DETERMINISTIC RISK SCORE
#
# Higher = review sooner.
#
# IMPORTANT:
#
# This is a TRIAGE score.
# It is not a probability and not a truth label.
# =========================================================

def calculate_risk_score(row):

    score = 0
    reasons = []

    if safe_bool(
        row["ceremonial_candidate"]
    ):

        score += 4

        reasons.append(
            "ceremonial text"
        )

    if safe_bool(
        row["high_risk_rule"]
    ):

        score += 3

        reasons.append(
            "high-risk regex"
        )

    topic_count = int(
        row["topic_count_for_bill"]
    )

    if topic_count >= 5:

        score += 3

        reasons.append(
            "5+ derived topics"
        )

    elif topic_count >= 3:

        score += 1

        reasons.append(
            "3-4 derived topics"
        )

    match_count = int(
        row["match_count"]
    )

    if match_count == 1:

        score += 1

        reasons.append(
            "single textual hit"
        )

    relative_position = (
        row[
            "relative_match_position"
        ]
    )

    if pd.notna(
        relative_position
    ):

        relative_position = float(
            relative_position
        )

        if relative_position >= 0.60:

            score += 2

            reasons.append(
                "match late in text"
            )

        elif relative_position >= 0.35:

            score += 1

            reasons.append(
                "match in latter text"
            )

    if safe_bool(
        row[
            "match_in_first_100_chars"
        ]
    ):

        score -= 2

        reasons.append(
            "match near beginning"
        )

    if match_count >= 3:

        score -= 1

        reasons.append(
            "repeated textual support"
        )

    if safe_bool(
        row[
            "description_supports_topic"
        ]
    ):

        score -= 3

        reasons.append(
            "summary/description agree"
        )

    elif (
        row["classification"]
        ==
        "Derived from LIS bill summary"
    ):

        score += 2

        reasons.append(
            "summary-only topic"
        )

    if safe_bool(
        row[
            "education_higher_ed_overlap"
        ]
    ):

        score += 2

        reasons.append(
            "Education/Higher Education overlap"
        )

    return (
        score,
        " | ".join(reasons),
    )


# =========================================================
# SEMANTIC REVIEW QUEUE
#
# This is the main human/model review table.
# =========================================================

def build_semantic_review_queue(
    derived,
    bill_lookup,
    match_strength,
):

    bill_fields = (
        bill_lookup[
            [
                "Bill_id",
                "Bill_description",
            ]
        ]
        .drop_duplicates(
            subset=["Bill_id"]
        )
        .copy()
    )

    bill_description_map = (
        bill_fields
        .set_index("Bill_id")[
            "Bill_description"
        ]
        .fillna("")
        .to_dict()
    )

    description_topic_map = (
        build_description_topic_map(
            bill_lookup
        )
    )

    topic_counts = (
        derived
        .groupby("Bill_id")[
            "topic_name"
        ]
        .nunique()
        .to_dict()
    )

    topic_sets = (
        derived
        .groupby("Bill_id")[
            "topic_name"
        ]
        .agg(set)
        .to_dict()
    )

    result = match_strength.copy()

    result["Bill_description"] = (
        result["Bill_id"]
        .map(bill_description_map)
        .fillna("")
    )

    result["topic_count_for_bill"] = (
        result["Bill_id"]
        .map(topic_counts)
        .fillna(0)
        .astype(int)
    )

    result["ceremonial_candidate"] = (
        result["source_text_used"]
        .map(is_ceremonial_text)
    )

    result["description_supports_topic"] = (
        result.apply(
            lambda row:
                row["topic_name"]
                in
                description_topic_map.get(
                    row["Bill_id"],
                    set(),
                ),
            axis=1,
        )
    )

    result[
        "education_higher_ed_overlap"
    ] = (
        result["Bill_id"]
        .map(
            lambda bill_id:
                {
                    "Education",
                    "Higher Education",
                }
                .issubset(
                    topic_sets.get(
                        bill_id,
                        set(),
                    )
                )
        )
    )

    scored = result.apply(
        calculate_risk_score,
        axis=1,
        result_type="expand",
    )

    result["risk_score"] = (
        scored[0]
        .astype(int)
    )

    result["risk_reasons"] = (
        scored[1]
    )

    # Human/model adjudication fields.
    result["qa_judgment"] = ""
    result["qa_confidence"] = ""
    result["qa_reason"] = ""
    result["qa_recommended_action"] = ""
    result["qa_reviewer"] = ""
    result["qa_review_date"] = ""

    return (
        result
        .sort_values(
            [
                "risk_score",
                "topic_count_for_bill",
                "Bill_id",
                "topic_name",
            ],
            ascending=[
                False,
                False,
                True,
                True,
            ],
        )
        .reset_index(drop=True)
    )


# =========================================================
# RISK-BAND SUMMARY
# =========================================================

def add_risk_band(
    semantic_queue,
):

    result = semantic_queue.copy()

    def assign_band(score):

        score = int(score)

        if score >= 8:
            return "VERY HIGH"

        if score >= 5:
            return "HIGH"

        if score >= 2:
            return "MEDIUM"

        return "LOW"

    result["risk_band"] = (
        result["risk_score"]
        .map(assign_band)
    )

    return result


def build_risk_summary(
    semantic_queue,
):

    return (
        semantic_queue
        .groupby(
            "risk_band",
            as_index=False,
        )
        .agg(
            assignment_rows=(
                "Bill_id",
                "size",
            ),

            unique_bills=(
                "Bill_id",
                "nunique",
            ),

            average_risk_score=(
                "risk_score",
                "mean",
            ),

            maximum_risk_score=(
                "risk_score",
                "max",
            ),
        )
        .sort_values(
            "maximum_risk_score",
            ascending=False,
        )
        .reset_index(drop=True)
    )


# =========================================================
# HIGH-PRIORITY REVIEW SUBSET
#
# A much smaller table for actual semantic/manual review.
# =========================================================

def build_priority_review_subset(
    semantic_queue,
):

    result = semantic_queue[
        semantic_queue[
            "risk_band"
        ]
        .isin(
            [
                "VERY HIGH",
                "HIGH",
            ]
        )
    ].copy()

    return (
        result
        .sort_values(
            [
                "risk_score",
                "Bill_id",
                "topic_name",
            ],
            ascending=[
                False,
                True,
                True,
            ],
        )
        .reset_index(drop=True)
    )


# =========================================================
# AUDIT SUMMARY
# =========================================================

def build_audit_summary(
    year,
    data,
    derived,
    ceremonial,
    high_risk,
    topic_counts,
    multi_topic,
    redundant,
    cross_source,
    semantic_queue,
):

    rows = [
        {
            "year":
                year,

            "metric":
                "Official LIS subject rows",

            "value":
                len(data["official"]),
        },

        {
            "year":
                year,

            "metric":
                "Official LIS subject bills",

            "value":
                data["official"][
                    "Bill_id"
                ].nunique(),
        },

        {
            "year":
                year,

            "metric":
                "Summary-derived rows",

            "value":
                len(data["summary"]),
        },

        {
            "year":
                year,

            "metric":
                "Summary-derived bills",

            "value":
                data["summary"][
                    "Bill_id"
                ].nunique(),
        },

        {
            "year":
                year,

            "metric":
                "Description-derived rows",

            "value":
                len(data["description"]),
        },

        {
            "year":
                year,

            "metric":
                "Description-derived bills",

            "value":
                data["description"][
                    "Bill_id"
                ].nunique(),
        },

        {
            "year":
                year,

            "metric":
                "Unclassified bills",

            "value":
                data["unclassified"][
                    "Bill_id"
                ].nunique(),
        },

        {
            "year":
                year,

            "metric":
                "Derived topic assignments",

            "value":
                len(derived),
        },

        {
            "year":
                year,

            "metric":
                "Ceremonial candidate assignments",

            "value":
                len(ceremonial),
        },

        {
            "year":
                year,

            "metric":
                "High-risk-rule assignments",

            "value":
                len(high_risk),
        },

        {
            "year":
                year,

            "metric":
                "Bills with 3+ derived topics",

            "value":
                (
                    multi_topic[
                        "Bill_id"
                    ].nunique()
                    if len(multi_topic)
                    else
                    0
                ),
        },

        {
            "year":
                year,

            "metric":
                "Bills with Education/Higher Education overlap",

            "value":
                len(redundant),
        },

        {
            "year":
                year,

            "metric":
                "Maximum derived topics on one bill",

            "value":
                (
                    int(
                        topic_counts[
                            "topic_count"
                        ].max()
                    )
                    if len(topic_counts)
                    else
                    0
                ),
        },

        {
            "year":
                year,

            "metric":
                "Cross-source low-agreement bills",

            "value":
                int(
                    cross_source[
                        "needs_review"
                    ].sum()
                ),
        },

        {
            "year":
                year,

            "metric":
                "Very-high-risk assignments",

            "value":
                int(
                    (
                        semantic_queue[
                            "risk_band"
                        ]
                        ==
                        "VERY HIGH"
                    )
                    .sum()
                ),
        },

        {
            "year":
                year,

            "metric":
                "High-risk assignments",

            "value":
                int(
                    (
                        semantic_queue[
                            "risk_band"
                        ]
                        ==
                        "HIGH"
                    )
                    .sum()
                ),
        },
    ]

    return pd.DataFrame(
        rows
    )


# =========================================================
# SAVE OUTPUTS
# =========================================================

def save_outputs(
    year,
    outputs,
):

    sections = []

    for name, dataframe in outputs.items():
        section = dataframe.copy()
        section.insert(0, "audit_section", name)
        sections.append(section)

    audit = pd.concat(
        sections,
        ignore_index=True,
        sort=False,
    ).fillna("")

    path = QA_ROOT / f"topic_validation_audit_{year}.csv"
    audit.to_csv(path, index=False)

    return {"topic_validation_audit": path}


# =========================================================
# TERMINAL REPORT HELPERS
# =========================================================

def print_rule_summary(
    rule_audit,
):

    print(
        "\n" + "=" * 70
    )

    print(
        "MOST COMMON DERIVED RULES"
    )

    print(
        "=" * 70
    )

    columns = [
        "classification",
        "topic_name",
        "matched_rule",
        "assignment_rows",
        "unique_bills",
        "high_risk_rule",
    ]

    print()

    print(
        rule_audit[
            columns
        ]
        .head(40)
        .to_string(
            index=False
        )
    )


def print_high_risk_summary(
    high_risk,
):

    print(
        "\n" + "=" * 70
    )

    print(
        "HIGH-RISK RULE ASSIGNMENTS"
    )

    print(
        "=" * 70
    )

    if len(high_risk) == 0:

        print(
            "\nNo high-risk rule "
            "assignments found."
        )

        return

    counts = (
        high_risk
        .groupby(
            [
                "topic_name",
                "matched_rule",
                "risk_reason",
            ],
            as_index=False,
        )
        .agg(
            assignment_rows=(
                "Bill_id",
                "size",
            ),

            unique_bills=(
                "Bill_id",
                "nunique",
            ),
        )
        .sort_values(
            "assignment_rows",
            ascending=False,
        )
    )

    print()

    print(
        counts.to_string(
            index=False
        )
    )


def print_risk_summary(
    risk_summary,
):

    print(
        "\n" + "=" * 70
    )

    print(
        "SEMANTIC REVIEW RISK BANDS"
    )

    print(
        "=" * 70
    )

    print()

    if len(risk_summary):

        print(
            risk_summary.to_string(
                index=False
            )
        )

    else:

        print(
            "No derived assignments."
        )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "\n" + "=" * 70
    )

    print(
        "LIS TOPIC VALIDATION AUDIT"
    )

    print(
        "=" * 70
    )

    print(
        f"\nYear: {YEAR}"
    )

    # -----------------------------------------------------
    # LOAD CURRENT PIPELINE OUTPUTS
    # -----------------------------------------------------

    data = load_data(
        YEAR
    )

    derived = combine_derived(
        data["summary"],
        data["description"],
    )

    # -----------------------------------------------------
    # ORIGINAL FULL-POPULATION QA
    # -----------------------------------------------------

    rule_audit = build_rule_audit(
        derived
    )

    ceremonial = (
        build_ceremonial_candidates(
            derived
        )
    )

    high_risk = (
        build_high_risk_rule_rows(
            derived
        )
    )

    topic_counts = (
        build_topic_count_by_bill(
            derived
        )
    )

    multi_topic = (
        build_multi_topic_candidates(
            derived,
            topic_counts,
        )
    )

    redundant = (
        build_redundant_topic_candidates(
            derived
        )
    )

    # -----------------------------------------------------
    # STRATIFIED HUMAN QA SAMPLES
    # -----------------------------------------------------

    topic_sample = (
        build_topic_manual_sample(
            derived
        )
    )

    rule_sample = (
        build_rule_manual_sample(
            derived
        )
    )

    unclassified_sample = (
        build_unclassified_sample(
            data["unclassified"],
            data["bill_lookup"],
            data["summary_lookup"],
        )
    )

    official_sample = (
        build_official_sample(
            data["official"]
        )
    )

    summary_selection_sample = (
        build_summary_selection_sample(
            data["summary_lookup"]
        )
    )

    # -----------------------------------------------------
    # NEW AUTOMATED QA
    # -----------------------------------------------------

    cross_source = (
        build_cross_source_comparison(
            data["bill_lookup"],
            data["summary_lookup"],
            data["official"],
        )
    )

    match_strength = (
        build_match_strength_table(
            derived
        )
    )

    semantic_queue = (
        build_semantic_review_queue(
            derived,
            data["bill_lookup"],
            match_strength,
        )
    )

    semantic_queue = (
        add_risk_band(
            semantic_queue
        )
    )

    risk_summary = (
        build_risk_summary(
            semantic_queue
        )
    )

    priority_review = (
        build_priority_review_subset(
            semantic_queue
        )
    )

    # -----------------------------------------------------
    # MASTER SUMMARY
    # -----------------------------------------------------

    audit_summary = (
        build_audit_summary(
            YEAR,
            data,
            derived,
            ceremonial,
            high_risk,
            topic_counts,
            multi_topic,
            redundant,
            cross_source,
            semantic_queue,
        )
    )

    # -----------------------------------------------------
    # SAVE ONE SECTIONED AUDIT ARTIFACT
    # -----------------------------------------------------

    # Full-population diagnostic tables above are validation machinery, not
    # durable datasets. Persist only compact summaries and bounded samples.
    outputs = {
        "topic_validation_summary":
            audit_summary,

        "topic_rule_audit":
            rule_audit,

        "topic_manual_validation_sample":
            topic_sample,

        "topic_rule_validation_sample":
            rule_sample,

        "topic_unclassified_validation_sample":
            unclassified_sample,

        "topic_official_validation_sample":
            official_sample,

        "topic_summary_selection_sample":
            summary_selection_sample,

        "topic_risk_band_summary":
            risk_summary,

        "topic_priority_review_sample":
            priority_review.head(100),

        "topic_ceremonial_sample":
            ceremonial.head(50),

        "topic_multi_topic_sample":
            multi_topic.head(50),

        "topic_redundant_pair_sample":
            redundant.head(50),
    }

    paths = save_outputs(
        YEAR,
        outputs,
    )

    # -----------------------------------------------------
    # TERMINAL OUTPUT
    # -----------------------------------------------------

    print(
        "\n" + "=" * 70
    )

    print(
        "AUDIT SUMMARY"
    )

    print(
        "=" * 70
    )

    print()

    print(
        audit_summary.to_string(
            index=False
        )
    )

    print_rule_summary(
        rule_audit
    )

    print_high_risk_summary(
        high_risk
    )

    print_risk_summary(
        risk_summary
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "CROSS-SOURCE QA"
    )

    print(
        "=" * 70
    )

    print(
        "\nBills compared: "
        f"{len(cross_source):,}"
    )

    print(
        "Bills flagged for low "
        "summary/description agreement: "
        f"{int(cross_source['needs_review'].sum()):,}"
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "MANUAL / SEMANTIC REVIEW WORKLOAD"
    )

    print(
        "=" * 70
    )

    print(
        "\nTopic-stratified sample rows: "
        f"{len(topic_sample):,}"
    )

    print(
        "Rule-stratified sample rows: "
        f"{len(rule_sample):,}"
    )

    print(
        "Unclassified sample rows: "
        f"{len(unclassified_sample):,}"
    )

    print(
        "Official LIS sample rows: "
        f"{len(official_sample):,}"
    )

    print(
        "Summary-selection sample rows: "
        f"{len(summary_selection_sample):,}"
    )

    print(
        "HIGH + VERY HIGH priority "
        "semantic-review rows: "
        f"{len(priority_review):,}"
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "FILES SAVED"
    )

    print(
        "=" * 70
    )

    for name, path in paths.items():

        print(
            f"\n{name}:"
        )

        print(
            path
        )

    print(
        "\n" + "=" * 70
    )

    print(
        "IMPORTANT"
    )

    print(
        "=" * 70
    )

    print(
        "\nRisk scores are QA triage scores, "
        "not probabilities and not truth labels."
    )

    print(
        "No production classifications were changed."
    )

    print(
        "\nAudit complete."
    )


if __name__ == "__main__":

    main()
