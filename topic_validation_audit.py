"""
Topic-classification quality audit for the Virginia LIS project.

WHY THIS FILE EXISTS
====================

The normal test suite answers questions such as:

    "Did the program follow the rules we wrote?"

This file asks a different question:

    "What are those rules actually doing to our data?"

That distinction matters.

For example, suppose our rule says:

    minor -> Family and Children

The program can apply that rule perfectly.

All programming tests can pass.

But after reading a bill about an unlicensed minor driver,
we may decide that "minor" only describes the affected
person and that the bill is really about transportation
and criminal penalties.

That would not be a coding error.

It would be a METHODOLOGY issue.

This audit helps us find those situations without changing
the real pipeline.

WHAT THIS FILE DOES
===================

For every available session year, it checks:

1. How many bills are:
       - Official LIS subject
       - Derived from LIS summary
       - Derived from LIS bill description
       - Unclassified

2. Which keyword rules create the most classifications.

3. Which broad keyword rules deserve closer review.

4. How many topics each derived bill receives.

5. Whether the summary and short bill description point
   toward similar topics.

6. Whether every saved regex really appears in the text
   that supposedly caused the classification.

7. Whether Unclassified bills are attached to recorded
   House vote events.

8. Why an Unclassified vote event can remain Unclassified
   even after some bills are newly classified.

IMPORTANT
=========

This script does NOT:

- change bill topics;
- change votes;
- change Streamlit;
- decide whether a classification is truly right or wrong;
- create one CSV for every diagnostic.

It writes ONE consolidated QA file per year:

    data/qa/topic_validation_audit_<year>.csv

The audit_section column tells you what each row represents.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import re

import pandas as pd

from lis_common import (
    PROCESSED_ROOT,
    available_processed_years,
)

from lis_pipeline import derive_topics_with_rules


# =========================================================
# OUTPUT LOCATION
#
# All QA results go into data/qa.
#
# We deliberately create only one audit CSV per year.
# =========================================================

QA_ROOT = Path("data/qa")

QA_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# KEYWORD-RISK NOTES
#
# These are NOT automatic errors.
#
# A "higher-risk" keyword is simply one that can easily
# appear in a bill even when that bill is mainly about
# something else.
#
# Example:
#
#     "minor"
#
# can appear in transportation, firearms, criminal law,
# internet regulation, employment law, and many other
# subjects.
#
# Compare that with:
#
#     "campaign finance"
#
# which is much more specific.
#
# These labels help us decide what deserves human review.
# They do NOT change classification.
# =========================================================

RULE_RISK = {

    r"\bminors?\b": {
        "risk": "HIGH",
        "reason": (
            "Minor status can describe an affected person "
            "without making the bill Family and Children policy."
        ),
    },

    r"\bcommercial\b": {
        "risk": "HIGH",
        "reason": (
            "Commercial is a broad adjective used in many "
            "different policy areas."
        ),
    },

    r"\belectronically\b": {
        "risk": "HIGH",
        "reason": (
            "Electronically often describes how something "
            "is done rather than Technology and Data policy."
        ),
    },

    r"\blocalit": {
        "risk": "HIGH",
        "reason": (
            "Many state bills mention a locality even when "
            "local-government authority is not the main issue."
        ),
    },

    r"\bmedical\b": {
        "risk": "HIGH",
        "reason": (
            "Medical language appears across health, insurance, "
            "employment, licensing, education, and criminal law."
        ),
    },

    r"\brevenue\b": {
        "risk": "HIGH",
        "reason": (
            "Revenue can describe a financial consequence "
            "without making Taxes and Revenue the policy subject."
        ),
    },

    r"\bcoverage\b": {
        "risk": "HIGH",
        "reason": (
            "Coverage is broad enough to appear outside "
            "substantive insurance regulation."
        ),
    },

    r"\bstudents?\b": {
        "risk": "MEDIUM",
        "reason": (
            "Students often signals education but can also "
            "only identify the affected population."
        ),
    },

    r"\beducation\b": {
        "risk": "MEDIUM",
        "reason": (
            "Education is broad and may duplicate the more "
            "specific Higher Education topic."
        ),
    },

    r"\bchildren\b": {
        "risk": "MEDIUM",
        "reason": (
            "Children may be the policy subject, an affected "
            "population, or part of an organization name."
        ),
    },

    r"\bworkforce\b": {
        "risk": "MEDIUM",
        "reason": (
            "Workforce can indicate labor policy or merely "
            "appear in an organization or economic context."
        ),
    },

    r"\bemployees?\b": {
        "risk": "MEDIUM",
        "reason": (
            "Employees can be the policy subject or simply "
            "people affected by another policy."
        ),
    },
}


# =========================================================
# TEXT PATTERNS FOR CEREMONIAL MEASURES
#
# Ceremonial resolutions frequently mention schools,
# professions, children, farmers, health organizations,
# and other policy-related words.
#
# That can create accidental topic matches.
#
# We flag them for review.
#
# We do NOT automatically delete their classifications.
# =========================================================

CEREMONIAL_PATTERNS = [
    r"^\s*commending\b",
    r"^\s*celebrating the life\b",
    r"^\s*celebrating\b",
    r"^\s*honoring\b",
    r"^\s*recognizing\b",
]


# =========================================================
# BASIC HELPERS
# =========================================================

def clean_text(value) -> str:

    if pd.isna(value):
        return ""

    return (
        re.sub(
            r"\s+",
            " ",
            str(value),
        )
        .strip()
    )


def clean_series(series: pd.Series) -> pd.Series:

    return (
        series
        .fillna("")
        .astype(str)
        .str.strip()
    )


def normalize_bill_id(value) -> str:

    value = clean_text(value).upper()

    if not value:
        return ""

    # HB0001 and HB1 should be treated as the same bill.
    match = re.fullmatch(
        r"([A-Z]+)0*([0-9]+)",
        value,
    )

    if match:

        return (
            f"{match.group(1)}"
            f"{int(match.group(2))}"
        )

    return value


def normalize_bill_series(
    series: pd.Series,
) -> pd.Series:

    return series.map(
        normalize_bill_id
    )


def load_csv(path: Path) -> pd.DataFrame:

    if not path.exists():

        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    return pd.read_csv(
        path,
        dtype=str,
        low_memory=False,
    )


def join_values(values) -> str:

    cleaned = {
        clean_text(value)
        for value in values
        if clean_text(value)
    }

    return " | ".join(
        sorted(cleaned)
    )


# =========================================================
# WHICH YEARS SHOULD WE CHECK?
#
# Normal use:
#
#     python topic_validation_audit.py
#
# checks every processed year.
#
# You can also request particular years:
#
#     python topic_validation_audit.py --years 2025 2026
# =========================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "Check LIS topic classification and "
            "Unclassified vote behavior."
        )
    )

    parser.add_argument(
        "--years",
        nargs="*",
        type=int,
        help=(
            "Optional years to check. "
            "Example: --years 2025 2026"
        ),
    )

    return parser.parse_args()


def determine_years() -> list[int]:

    arguments = parse_arguments()

    if arguments.years:

        return sorted(
            set(arguments.years)
        )

    years = available_processed_years(
        PROCESSED_ROOT
    )

    if not years:

        raise FileNotFoundError(
            "No processed LIS years were found."
        )

    return years


# =========================================================
# LOAD THE TABLES NEEDED FOR ONE YEAR
# =========================================================

def load_year(
    year: int,
) -> dict[str, pd.DataFrame]:

    names = [
        "vote_fact",
        "vote_bill_bridge",
        "bill_lookup",
        "bill_topic_lookup",
        "derived_from_lis_bill_summary",
        "derived_from_lis_bill_description",
        "official_lis_subjects",
        "unclassified_bills",
        "member_vote_topic",
    ]

    data = {}

    for name in names:

        path = (
            PROCESSED_ROOT
            /
            f"{name}_{year}.csv"
        )

        data[name] = load_csv(
            path
        )

        if (
            "Bill_id"
            in
            data[name].columns
        ):

            data[name][
                "Bill_id"
            ] = normalize_bill_series(
                data[name][
                    "Bill_id"
                ]
            )

    return data


# =========================================================
# COMBINE THE TWO RULE-DERIVED CLASSIFICATION FILES
#
# Official LIS subjects are excluded here because their
# topics came directly from LIS rather than our regex rules.
# =========================================================

def build_derived_rows(
    data,
) -> pd.DataFrame:

    result = pd.concat(
        [
            data[
                "derived_from_lis_bill_summary"
            ],
            data[
                "derived_from_lis_bill_description"
            ],
        ],
        ignore_index=True,
    )

    for column in [
        "Bill_id",
        "topic_name",
        "classification",
        "source_text_used",
        "matched_rule",
    ]:

        result[column] = clean_series(
            result[column]
        )

    result[
        "Bill_id"
    ] = normalize_bill_series(
        result[
            "Bill_id"
        ]
    )

    return result


# =========================================================
# HOW OFTEN DOES EACH RULE FIRE?
#
# This is population information, not an accuracy score.
#
# A rule being common does not mean it is bad.
# =========================================================

def build_rule_summary(
    derived,
) -> pd.DataFrame:

    result = (
        derived
        .groupby(
            [
                "classification",
                "topic_name",
                "matched_rule",
            ],
            as_index=False,
            dropna=False,
        )
        .agg(
            assignments=(
                "Bill_id",
                "size",
            ),

            bills=(
                "Bill_id",
                "nunique",
            ),
        )
    )

    result[
        "keyword_risk"
    ] = (
        result[
            "matched_rule"
        ]
        .map(
            lambda rule:
                RULE_RISK
                .get(
                    clean_text(rule),
                    {},
                )
                .get(
                    "risk",
                    "LOW",
                )
        )
    )

    result[
        "why_keyword_deserves_review"
    ] = (
        result[
            "matched_rule"
        ]
        .map(
            lambda rule:
                RULE_RISK
                .get(
                    clean_text(rule),
                    {},
                )
                .get(
                    "reason",
                    (
                        "No special broad-keyword concern "
                        "has currently been identified."
                    ),
                )
        )
    )

    risk_order = {
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    result[
        "_risk_order"
    ] = (
        result[
            "keyword_risk"
        ]
        .map(risk_order)
    )

    return (
        result
        .sort_values(
            [
                "_risk_order",
                "assignments",
            ],
            ascending=[
                False,
                False,
            ],
        )
        .drop(
            columns=[
                "_risk_order"
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# CHECK WHETHER THE SAVED REGEX REALLY MATCHES THE SAVED
# SOURCE TEXT.
#
# This is an integrity check.
#
# It does NOT tell us whether the topic is sensible.
# =========================================================

def build_match_check(
    derived,
) -> pd.DataFrame:

    rows = []

    for _, row in derived.iterrows():

        pattern = clean_text(
            row[
                "matched_rule"
            ]
        )

        text = clean_text(
            row[
                "source_text_used"
            ]
        )

        found = False
        count = 0
        first_position = -1

        if (
            pattern
            and
            text
        ):

            matches = list(
                re.finditer(
                    pattern,
                    text,
                    flags=re.IGNORECASE,
                )
            )

            found = bool(
                matches
            )

            count = len(
                matches
            )

            if matches:

                first_position = (
                    matches[
                        0
                    ]
                    .start()
                )

        risk = (
            RULE_RISK
            .get(
                pattern,
                {}
            )
        )

        rows.append(
            {
                "Bill_id":
                    row[
                        "Bill_id"
                    ],

                "classification":
                    row[
                        "classification"
                    ],

                "topic_name":
                    row[
                        "topic_name"
                    ],

                "matched_rule":
                    pattern,

                "keyword_risk":
                    risk.get(
                        "risk",
                        "LOW",
                    ),

                "source_text_used":
                    text,

                "regex_found_in_source_text":
                    found,

                "match_count":
                    count,

                "first_match_position":
                    first_position,

                "text_length":
                    len(text),

                "ceremonial_text":
                    any(
                        re.search(
                            ceremonial_pattern,
                            text,
                            flags=re.IGNORECASE,
                        )
                        is not None
                        for ceremonial_pattern
                        in CEREMONIAL_PATTERNS
                    ),

                "why_review_this_row":
                    (
                        risk.get(
                            "reason",
                            "",
                        )
                    ),
            }
        )

    result = pd.DataFrame(
        rows
    )

    return (
        result
        .sort_values(
            [
                "regex_found_in_source_text",
                "ceremonial_text",
                "keyword_risk",
                "Bill_id",
            ],
            ascending=[
                True,
                False,
                True,
                True,
            ],
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# HOW MANY DERIVED TOPICS DOES EACH BILL RECEIVE?
#
# Multiple topics are allowed.
#
# This simply lets us see where keyword accumulation may
# deserve closer review.
# =========================================================

def build_topic_count_check(
    derived,
) -> pd.DataFrame:

    return (
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
                join_values,
            ),
        )
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
        .reset_index(
            drop=True
        )
    )


# =========================================================
# APPLY OUR EXISTING RULES TO ANY PIECE OF TEXT.
#
# This is used only for comparison.
#
# It does not change the production classification.
# =========================================================

def topics_from_text(
    text,
) -> set[str]:

    text = clean_text(
        text
    )

    if not text:

        return set()

    matches = (
        derive_topics_with_rules(
            text
        )
    )

    return {
        match[
            "topic_name"
        ]
        for match in matches
        if match.get(
            "topic_name"
        )
    }


# =========================================================
# COMPARE SUMMARY-DERIVED TOPICS TO THE SHORT DESCRIPTION
#
# Agreement provides useful additional evidence.
#
# Disagreement is NOT automatically a problem.
#
# A long LIS summary naturally contains more information
# than the short description.
# =========================================================

def build_cross_source_check(
    data,
) -> pd.DataFrame:

    bills = (
        data[
            "bill_lookup"
        ][
            [
                "Bill_id",
                "Bill_description",
            ]
        ]
        .drop_duplicates(
            "Bill_id"
        )
    )

    summary_rows = (
        data[
            "derived_from_lis_bill_summary"
        ]
        .groupby(
            "Bill_id",
            as_index=False,
        )
        .agg(
            summary_topics=(
                "topic_name",
                join_values,
            ),

            summary_text=(
                "source_text_used",
                "first",
            ),
        )
    )

    result = bills.merge(
        summary_rows,
        on="Bill_id",
        how="left",
        validate="one_to_one",
    )

    records = []

    for _, row in result.iterrows():

        summary_text = clean_text(
            row.get(
                "summary_text",
                "",
            )
        )

        description = clean_text(
            row[
                "Bill_description"
            ]
        )

        summary_topics = set(
            value.strip()
            for value
            in clean_text(
                row.get(
                    "summary_topics",
                    "",
                )
            ).split("|")
            if value.strip()
        )

        description_topics = (
            topics_from_text(
                description
            )
        )

        shared = (
            summary_topics
            &
            description_topics
        )

        union = (
            summary_topics
            |
            description_topics
        )

        agreement = (
            len(shared)
            /
            len(union)
            if union
            else
            1.0
        )

        records.append(
            {
                "Bill_id":
                    row[
                        "Bill_id"
                    ],

                "summary_topics":
                    join_values(
                        summary_topics
                    ),

                "description_topics":
                    join_values(
                        description_topics
                    ),

                "shared_topics":
                    join_values(
                        shared
                    ),

                "summary_only_topics":
                    join_values(
                        summary_topics
                        -
                        description_topics
                    ),

                "description_only_topics":
                    join_values(
                        description_topics
                        -
                        summary_topics
                    ),

                "agreement_score":
                    round(
                        agreement,
                        4,
                    ),

                "Bill_description":
                    description,

                "summary_text":
                    summary_text,

                "how_to_read_this":
                    (
                        "Low agreement means the two LIS text "
                        "sources produced different topic sets. "
                        "It does not automatically mean the "
                        "summary classification is wrong."
                    ),
            }
        )

    return (
        pd.DataFrame(
            records
        )
        .sort_values(
            [
                "agreement_score",
                "Bill_id",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# THE UNCLASSIFIED VOTE CHECK
#
# This directly addresses the question that triggered this
# audit.
#
#
# IMPORTANT IDEA
# ==============
#
# One LIS vote can cover several bills.
#
# Example:
#
# Vote V1
#   -> HB1 = Education
#   -> HB2 = Unclassified
#
# V1 still legitimately appears in the Unclassified bucket
# because HB2 remains Unclassified.
#
#
# Later:
#
# Vote V1
#   -> HB1 = Education
#   -> HB2 = Transportation
#
# Now no bill on V1 is Unclassified.
#
# V1 should therefore disappear from the Unclassified
# subject bucket.
#
#
# This table shows exactly how many vote events are being
# kept Unclassified for that reason.
# =========================================================

def build_unclassified_vote_check(
    data,
) -> pd.DataFrame:

    bridge = (
        data[
            "vote_bill_bridge"
        ]
        .copy()
    )

    topics = (
        data[
            "bill_topic_lookup"
        ]
        .copy()
    )

    votes = (
        data[
            "vote_fact"
        ]
        .copy()
    )

    member_topics = (
        data[
            "member_vote_topic"
        ]
        .copy()
    )

    bridge[
        "Bill_id"
    ] = normalize_bill_series(
        bridge[
            "Bill_id"
        ]
    )

    topics[
        "Bill_id"
    ] = normalize_bill_series(
        topics[
            "Bill_id"
        ]
    )

    topics[
        "topic_name"
    ] = clean_series(
        topics[
            "topic_name"
        ]
    )

    unclassified_bills = set(
        topics.loc[
            topics[
                "topic_name"
            ]
            ==
            "Unclassified",
            "Bill_id",
        ]
    )

    bridge_simple = (
        bridge[
            [
                "vote_id",
                "Bill_id",
            ]
        ]
        .drop_duplicates()
    )

    vote_groups = (
        bridge_simple
        .groupby(
            "vote_id"
        )
    )

    member_topics[
        "topic_name"
    ] = clean_series(
        member_topics[
            "topic_name"
        ]
    )

    observed_unclassified_vote_ids = set(
        member_topics.loc[
            member_topics[
                "topic_name"
            ]
            ==
            "Unclassified",
            "vote_id",
        ]
        .astype(str)
        .str.strip()
    )

    house_vote_ids = set(
        votes.loc[
            clean_series(
                votes[
                    "MBR_HOU"
                ]
            )
            .str.upper()
            ==
            "H",
            "vote_id",
        ]
        .astype(str)
        .str.strip()
    )

    rows = []

    for (
        vote_id,
        group
    ) in vote_groups:

        vote_id = clean_text(
            vote_id
        )

        bill_ids = set(
            group[
                "Bill_id"
            ]
        )

        remaining_unclassified = (
            bill_ids
            &
            unclassified_bills
        )

        classified = (
            bill_ids
            -
            unclassified_bills
        )

        touches_house_vote = (
            vote_id
            in
            house_vote_ids
        )

        expected_unclassified = (
            touches_house_vote
            and
            bool(
                remaining_unclassified
            )
        )

        observed_unclassified = (
            vote_id
            in
            observed_unclassified_vote_ids
        )

        rows.append(
            {
                "vote_id":
                    vote_id,

                "bills_on_vote":
                    len(
                        bill_ids
                    ),

                "bill_ids":
                    join_values(
                        bill_ids
                    ),

                "classified_bills_on_vote":
                    len(
                        classified
                    ),

                "classified_bill_ids":
                    join_values(
                        classified
                    ),

                "unclassified_bills_on_vote":
                    len(
                        remaining_unclassified
                    ),

                "unclassified_bill_ids":
                    join_values(
                        remaining_unclassified
                    ),

                "house_vote_event":
                    touches_house_vote,

                "should_appear_as_unclassified":
                    expected_unclassified,

                "does_appear_as_unclassified":
                    observed_unclassified,

                "unclassified_flow_correct":
                    (
                        expected_unclassified
                        ==
                        observed_unclassified
                    ),

                "plain_english_explanation":
                    (
                        "This vote remains Unclassified because "
                        "at least one bill attached to the vote "
                        "is still Unclassified."
                        if expected_unclassified
                        else
                        (
                            "No Unclassified bill remains attached "
                            "to this House vote, so it should not "
                            "appear in the Unclassified subject bucket."
                            if touches_house_vote
                            else
                            "This vote is not a House vote used in "
                            "member_vote_topic."
                        )
                    ),
            }
        )

    result = pd.DataFrame(
        rows
    )

    return (
        result
        .sort_values(
            [
                "unclassified_flow_correct",
                "unclassified_bills_on_vote",
                "bills_on_vote",
            ],
            ascending=[
                True,
                False,
                False,
            ],
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# SESSION SUMMARY
#
# These are the main numbers to read in the terminal.
# =========================================================

def build_session_summary(
    year,
    data,
    derived,
    rule_summary,
    match_check,
    topic_counts,
    cross_source,
    unclassified_vote_check,
) -> pd.DataFrame:

    topic_lookup = (
        data[
            "bill_topic_lookup"
        ]
    )

    bill_lookup = (
        data[
            "bill_lookup"
        ]
    )

    classification_by_bill = (
        topic_lookup[
            [
                "Bill_id",
                "classification",
            ]
        ]
        .drop_duplicates()
    )

    metrics = []

    def add_metric(
        metric,
        value,
        explanation,
    ):

        metrics.append(
            {
                "year":
                    year,

                "metric":
                    metric,

                "value":
                    value,

                "what_this_number_means":
                    explanation,
            }
        )

    add_metric(
        "Bills in bill lookup",
        bill_lookup[
            "Bill_id"
        ].nunique(),
        (
            "Total distinct bills available to the "
            "classification process."
        ),
    )

    for classification in [
        "Official LIS subject",
        "Derived from LIS bill summary",
        "Derived from LIS bill description",
        "Unclassified",
    ]:

        count = (
            classification_by_bill.loc[
                classification_by_bill[
                    "classification"
                ]
                ==
                classification,
                "Bill_id",
            ]
            .nunique()
        )

        add_metric(
            f"Bills: {classification}",
            count,
            (
                "Distinct bills whose classification "
                "provenance is this category."
            ),
        )

    add_metric(
        "Derived topic assignments",
        len(
            derived
        ),
        (
            "Bill-topic rows created by our summary "
            "or description rules. One bill may have "
            "more than one topic."
        ),
    )

    add_metric(
        "Distinct derived rules used",
        rule_summary[
            "matched_rule"
        ].nunique(),
        (
            "Number of different regex rules that "
            "actually created at least one topic."
        ),
    )

    add_metric(
        "Derived rows whose saved regex cannot be reproduced",
        int(
            (
                ~match_check[
                    "regex_found_in_source_text"
                ]
            )
            .sum()
        ),
        (
            "Should normally be zero. A nonzero value "
            "means the saved rule does not match the "
            "saved source text."
        ),
    )

    add_metric(
        "Bills with 3 or more derived topics",
        int(
            (
                topic_counts[
                    "topic_count"
                ]
                >=
                3
            )
            .sum()
        ),
        (
            "These are not automatically wrong. "
            "They simply deserve more attention "
            "because several rules fired."
        ),
    )

    add_metric(
        "Maximum derived topics on one bill",
        (
            int(
                topic_counts[
                    "topic_count"
                ]
                .max()
            )
            if len(
                topic_counts
            )
            else
            0
        ),
        (
            "Largest number of rule-derived topics "
            "assigned to one bill."
        ),
    )

    add_metric(
        "Summary-derived bills with low description agreement",
        int(
            (
                cross_source[
                    "agreement_score"
                ]
                <
                0.50
            )
            .sum()
        ),
        (
            "The summary and short description produce "
            "substantially different topic sets. This "
            "is a review signal, not an error."
        ),
    )

    add_metric(
        "House vote events that should remain Unclassified",
        int(
            unclassified_vote_check[
                "should_appear_as_unclassified"
            ]
            .sum()
        ),
        (
            "Distinct House vote events connected to at "
            "least one bill that is still Unclassified."
        ),
    )

    add_metric(
        "House vote events observed as Unclassified",
        int(
            unclassified_vote_check[
                "does_appear_as_unclassified"
            ]
            .sum()
        ),
        (
            "Distinct vote IDs currently appearing in "
            "member_vote_topic under Unclassified."
        ),
    )

    add_metric(
        "Unclassified vote-flow mismatches",
        int(
            (
                ~unclassified_vote_check[
                    "unclassified_flow_correct"
                ]
            )
            .sum()
        ),
        (
            "Should be zero. A mismatch means the downstream "
            "Unclassified vote representation does not agree "
            "with the current bill classifications."
        ),
    )

    return pd.DataFrame(
        metrics
    )


# =========================================================
# SAVE ONE FILE PER YEAR
#
# Different checks are stacked into one CSV.
#
# audit_section tells us which part each row belongs to.
# =========================================================

def save_consolidated_audit(
    year,
    sections,
):

    combined_sections = []

    for (
        section_name,
        frame,
    ) in sections.items():

        section = (
            frame.copy()
        )

        section.insert(
            0,
            "audit_section",
            section_name,
        )

        combined_sections.append(
            section
        )

    output = (
        pd.concat(
            combined_sections,
            ignore_index=True,
            sort=False,
        )
        .fillna("")
    )

    path = (
        QA_ROOT
        /
        f"topic_validation_audit_{year}.csv"
    )

    output.to_csv(
        path,
        index=False,
    )

    return path


# =========================================================
# RUN ONE SESSION
# =========================================================

def run_year(
    year,
):

    print(
        "\n" + "=" * 78
    )

    print(
        f"LIS TOPIC METHODOLOGY AUDIT: {year}"
    )

    print(
        "=" * 78
    )

    data = load_year(
        year
    )

    derived = build_derived_rows(
        data
    )

    rule_summary = (
        build_rule_summary(
            derived
        )
    )

    match_check = (
        build_match_check(
            derived
        )
    )

    topic_counts = (
        build_topic_count_check(
            derived
        )
    )

    cross_source = (
        build_cross_source_check(
            data
        )
    )

    unclassified_vote_check = (
        build_unclassified_vote_check(
            data
        )
    )

    session_summary = (
        build_session_summary(
            year,
            data,
            derived,
            rule_summary,
            match_check,
            topic_counts,
            cross_source,
            unclassified_vote_check,
        )
    )

    # -----------------------------------------------------
    # Only save rows that are especially useful for review
    # inside the one consolidated file.
    #
    # The checks themselves ran across the full population.
    # -----------------------------------------------------

    rule_review = rule_summary[
        rule_summary[
            "keyword_risk"
        ]
        .isin(
            [
                "HIGH",
                "MEDIUM",
            ]
        )
    ].copy()

    match_problems = match_check[
        (
            ~match_check[
                "regex_found_in_source_text"
            ]
        )
        |
        (
            match_check[
                "ceremonial_text"
            ]
        )
        |
        (
            match_check[
                "keyword_risk"
            ]
            .isin(
                [
                    "HIGH",
                    "MEDIUM",
                ]
            )
        )
    ].copy()

    high_topic_count = topic_counts[
        topic_counts[
            "topic_count"
        ]
        >=
        3
    ].copy()

    low_agreement = cross_source[
        cross_source[
            "agreement_score"
        ]
        <
        0.50
    ].copy()

    unclassified_vote_relevant = (
        unclassified_vote_check[
            (
                unclassified_vote_check[
                    "should_appear_as_unclassified"
                ]
            )
            |
            (
                ~unclassified_vote_check[
                    "unclassified_flow_correct"
                ]
            )
        ]
        .copy()
    )

    path = save_consolidated_audit(
        year,
        {
            "SESSION SUMMARY":
                session_summary,

            "BROAD KEYWORD RULES":
                rule_review,

            "DERIVED ROWS TO REVIEW":
                match_problems,

            "BILLS WITH 3+ TOPICS":
                high_topic_count,

            "LOW SUMMARY/DESCRIPTION AGREEMENT":
                low_agreement,

            "UNCLASSIFIED VOTE FLOW":
                unclassified_vote_relevant,
        },
    )

    print(
        "\nWhat the audit found:"
    )

    print()

    print(
        session_summary[
            [
                "metric",
                "value",
            ]
        ]
        .to_string(
            index=False
        )
    )

    mismatches = int(
        (
            ~unclassified_vote_check[
                "unclassified_flow_correct"
            ]
        )
        .sum()
    )

    print(
        "\nUnclassified vote check:"
    )

    if mismatches == 0:

        print(
            "PASS — every downstream Unclassified vote "
            "event is consistent with the current bill "
            "classifications."
        )

    else:

        print(
            f"FAIL — {mismatches:,} vote events do not "
            "reconcile with the current Unclassified bills."
        )

    print(
        "\nSaved one QA file:"
    )

    print(
        path
    )

    return session_summary


# =========================================================
# MAIN
# =========================================================

def main():

    years = determine_years()

    print(
        "\n" + "=" * 78
    )

    print(
        "VIRGINIA LIS TOPIC QUALITY CHECK"
    )

    print(
        "=" * 78
    )

    print(
        "\nWhy we are running this:"
    )

    print(
        "The regular tests tell us whether the program "
        "followed our rules."
    )

    print(
        "This audit helps us understand whether those "
        "rules are producing suspicious patterns."
    )

    print(
        "\nYears being checked:"
    )

    print(
        years
    )

    summaries = []

    for year in years:

        summaries.append(
            run_year(
                year
            )
        )

    print(
        "\n" + "=" * 78
    )

    print(
        "AUDIT COMPLETE"
    )

    print(
        "=" * 78
    )

    print(
        "\nNo production files were changed."
    )

    print(
        "The audit created one QA CSV for each session."
    )


if __name__ == "__main__":

    main()