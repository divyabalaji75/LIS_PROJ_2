"""
Analyze how Virginia House delegates voted on recorded vote events
associated with legislative topics.

IMPORTANT IDEA
==============

This file analyzes RECORDED VOTES BY TOPIC.

It does not determine whether a delegate "supports" or "opposes"
a policy idea.

For example:

    Education
    80% Yes

means:

    Of the directional Y/N vote events associated with Education
    for this delegate, 80% were recorded as Yes.

It does NOT mean:

    "This delegate supports 80% of education policy."

WHY THE GRAIN CHANGED
=====================

The production pipeline now defines member_vote_topic at:

    year
    + vote_id
    + member_id
    + topic_name

Classification provenance is NOT part of the analytical grain.

That matters because one LIS vote can cover several bills.

Example:

    Vote V1

        HB1 -> Education -> Official LIS subject
        HB2 -> Education -> Derived from LIS summary

A delegate cast ONE recorded vote event associated with Education.

We therefore count that Education vote once.

The fact that the Education topic came from two different provenance
sources is still preserved in topic_provenance, but it does not create
two analytical vote records.
"""

from pathlib import Path

import pandas as pd

from lis_common import (
    configured_years,
    write_csv,
)


# =========================================================
# PROJECT SETTINGS
# =========================================================

PROCESSED_ROOT = Path(
    "data/processed"
)

YEARS = configured_years()


# =========================================================
# MINIMUM EVIDENCE FOR A VOTING-TENDENCY LABEL
#
# We require at least 10 directional Yes/No vote events
# before labeling a delegate/topic combination YES, NO,
# or MIXED.
#
# Fewer than 10 directional vote events becomes:
#
#     INSUFFICIENT DATA
#
# Non-directional codes such as X, A, and P do not count
# toward this minimum.
# =========================================================

MIN_TOPIC_DIRECTIONAL_VOTES = 10


# =========================================================
# YES / NO THRESHOLDS
#
# 65% or more Yes:
#
#     YES
#
# 35% or less Yes:
#
#     NO
#
# Between those thresholds:
#
#     MIXED
#
# These are analytical labels describing recorded voting.
# They are not ideological labels.
# =========================================================

YES_THRESHOLD = 0.65
NO_THRESHOLD = 0.35


# =========================================================
# PROVENANCE LABELS
#
# These are metadata describing where a topic assignment
# came from.
#
# Provenance NEVER creates additional vote events.
#
# The order below is used only to keep the output readable
# and consistent.
# =========================================================

PROVENANCE_ORDER = [
    "Official LIS subject",
    "Derived from LIS bill summary",
    "Derived from LIS bill description",
    "Unclassified",
]

PROVENANCE_RANK = {
    label: index
    for index, label
    in enumerate(
        PROVENANCE_ORDER
    )
}


# =========================================================
# INPUT FILES
# =========================================================

MEMBER_TOPIC_FILES = {
    year: (
        PROCESSED_ROOT
        /
        f"member_vote_topic_{year}.csv"
    )
    for year in YEARS
}


# =========================================================
# BASIC HELPERS
# =========================================================

def require_file(path):

    if not path.exists():

        raise FileNotFoundError(
            f"Missing required file: {path}"
        )


def normalize_text(series):

    return (
        series
        .fillna("")
        .astype(str)
        .str.strip()
    )


# =========================================================
# NORMALIZE ONE PROVENANCE LABEL
#
# This handles minor whitespace problems without changing
# the meaning of the provenance.
#
# Example:
#
#     "Derivedfrom LIS bill summary"
#
# becomes:
#
#     "Derived from LIS bill summary"
#
# This is descriptive cleanup only.
# =========================================================

def normalize_provenance_label(value):

    text = (
        str(value)
        .strip()
    )

    if not text:

        return ""

    # Collapse repeated whitespace.
    text = " ".join(
        text.split()
    )

    # Repair the malformed spacing observed in older output.
    text = text.replace(
        "Derivedfrom LIS bill summary",
        "Derived from LIS bill summary",
    )

    text = text.replace(
        "Derivedfrom LIS bill description",
        "Derived from LIS bill description",
    )

    return text


# =========================================================
# SPLIT A PROVENANCE FIELD
#
# member_vote_topic may already contain several provenance
# labels in one cell:
#
#     Official LIS subject |
#     Derived from LIS bill summary
#
# When we summarize many vote rows, we must split those
# labels BEFORE deduplicating them.
#
# Otherwise a combined string is incorrectly treated as one
# giant provenance label.
# =========================================================

def split_provenance(value):

    text = (
        str(value)
        .strip()
    )

    if not text:

        return []

    parts = (
        text.split("|")
    )

    cleaned = []

    for part in parts:

        label = (
            normalize_provenance_label(
                part
            )
        )

        if label:

            cleaned.append(
                label
            )

    return cleaned


# =========================================================
# COMBINE UNIQUE PROVENANCE
#
# Example input rows:
#
#     Derived from LIS bill summary
#
#     Derived from LIS bill description |
#     Derived from LIS bill summary
#
#     Derived from LIS bill summary
#
# becomes:
#
#     Derived from LIS bill summary |
#     Derived from LIS bill description
#
# Each provenance label appears at most once.
# =========================================================

def join_unique(values):

    unique_labels = set()

    for value in values:

        for label in (
            split_provenance(
                value
            )
        ):

            unique_labels.add(
                label
            )

    def sort_key(label):

        return (
            PROVENANCE_RANK.get(
                label,
                len(
                    PROVENANCE_RANK
                ),
            ),
            label,
        )

    return " | ".join(
        sorted(
            unique_labels,
            key=sort_key,
        )
    )


# =========================================================
# LOAD MEMBER-VOTE-TOPIC
#
# REQUIRED GRAIN:
#
#     year
#     + vote_id
#     + member_id
#     + topic_name
#
# topic_provenance is descriptive information.
#
# It tells us how the bills connected to that vote/topic
# were classified, but it does not create additional vote
# records.
# =========================================================

def load_member_vote_topic(year):

    path = (
        PROCESSED_ROOT
        /
        f"member_vote_topic_{year}.csv"
    )

    require_file(
        path
    )

    df = pd.read_csv(
        path,
        dtype=str,
        low_memory=False,
    )

    required = {
        "year",
        "vote_id",
        "member_id",
        "MBR_NAME",
        "party",
        "vote",
        "topic_name",
        "topic_provenance",
    }

    missing = (
        required
        -
        set(df.columns)
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: "
            f"{missing}"
        )

    df["member_id"] = (
        normalize_text(
            df["member_id"]
        )
        .str.upper()
    )

    df["MBR_NAME"] = normalize_text(
        df["MBR_NAME"]
    )

    df["party"] = (
        normalize_text(
            df["party"]
        )
        .str.upper()
    )

    df["vote"] = (
        normalize_text(
            df["vote"]
        )
        .str.upper()
    )

    df["topic_name"] = normalize_text(
        df["topic_name"]
    )

    df["topic_provenance"] = normalize_text(
        df["topic_provenance"]
    )

    # Normalize each already-combined provenance cell.
    #
    # This does NOT change the number of rows.
    df["topic_provenance"] = (
        df[
            "topic_provenance"
        ]
        .map(
            lambda value:
                join_unique(
                    [value]
                )
        )
    )

    duplicate_rows = df[
        df.duplicated(
            subset=[
                "year",
                "vote_id",
                "member_id",
                "topic_name",
            ],
            keep=False,
        )
    ]

    if len(
        duplicate_rows
    ) > 0:

        raise ValueError(
            f"{year}: member_vote_topic contains "
            f"{len(duplicate_rows)} duplicate rows "
            "at year + vote_id + member_id + topic_name grain."
        )

    return df


# =========================================================
# ASSIGN A SIMPLE VOTING-TENDENCY LABEL
# =========================================================

def assign_voting_tendency(
    directional_votes,
    yes_votes,
):

    if directional_votes < MIN_TOPIC_DIRECTIONAL_VOTES:

        return "INSUFFICIENT DATA"

    yes_rate = (
        yes_votes
        /
        directional_votes
    )

    if yes_rate >= YES_THRESHOLD:

        return "YES"

    if yes_rate <= NO_THRESHOLD:

        return "NO"

    return "MIXED"


# =========================================================
# BUILD DELEGATE × TOPIC VOTING TENDENCY
#
# One output row means:
#
#     one year
#     + one delegate
#     + one topic
#
# Provenance does NOT split the analytical row.
#
# If Education reached this delegate's vote records through
# both official and derived classifications, the provenance
# values are combined into one informational field.
# =========================================================

def build_delegate_topic_voting_tendency(
    member_vote_topic,
):

    df = (
        member_vote_topic.copy()
    )

    required = {
        "year",
        "vote_id",
        "member_id",
        "MBR_NAME",
        "party",
        "topic_name",
        "vote",
    }

    missing = (
        required
        -
        set(df.columns)
    )

    if missing:

        raise ValueError(
            "member_vote_topic missing columns: "
            f"{missing}"
        )

    if (
        "topic_provenance"
        not in df.columns
    ):

        # Convenient for small synthetic unit tests.
        #
        # Real production input is expected to contain the
        # column.
        df["topic_provenance"] = ""

    df["vote"] = (
        normalize_text(
            df["vote"]
        )
        .str.upper()
    )

    df["member_id"] = (
        normalize_text(
            df["member_id"]
        )
        .str.upper()
    )

    df["MBR_NAME"] = normalize_text(
        df["MBR_NAME"]
    )

    df["party"] = (
        normalize_text(
            df["party"]
        )
        .str.upper()
    )

    df["topic_name"] = normalize_text(
        df["topic_name"]
    )

    df["topic_provenance"] = (
        normalize_text(
            df[
                "topic_provenance"
            ]
        )
        .map(
            lambda value:
                join_unique(
                    [value]
                )
        )
    )

    # -----------------------------------------------------
    # PROTECT THE ANALYTICAL GRAIN
    #
    # Even if a caller accidentally supplies repeated rows,
    # a member's one vote event should count only once for
    # one topic.
    # -----------------------------------------------------

    df = (
        df
        .drop_duplicates(
            subset=[
                "year",
                "vote_id",
                "member_id",
                "topic_name",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    df[
        "is_yes"
    ] = (
        df[
            "vote"
        ]
        ==
        "Y"
    )

    df[
        "is_no"
    ] = (
        df[
            "vote"
        ]
        ==
        "N"
    )

    df[
        "is_directional"
    ] = (
        df[
            "vote"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
    )

    result = (
        df
        .groupby(
            [
                "year",
                "member_id",
                "MBR_NAME",
                "party",
                "topic_name",
            ],
            as_index=False,
            dropna=False,
        )
        .agg(
            topic_vote_events=(
                "vote_id",
                "nunique",
            ),

            directional_topic_votes=(
                "is_directional",
                "sum",
            ),

            yes_votes=(
                "is_yes",
                "sum",
            ),

            no_votes=(
                "is_no",
                "sum",
            ),

            topic_provenance=(
                "topic_provenance",
                join_unique,
            ),
        )
    )

    # -----------------------------------------------------
    # BASIC COUNT INVARIANT
    #
    # Every directional vote must be either Y or N.
    # -----------------------------------------------------

    invalid_directional_counts = result[
        (
            result[
                "yes_votes"
            ]
            +
            result[
                "no_votes"
            ]
        )
        !=
        result[
            "directional_topic_votes"
        ]
    ]

    if len(
        invalid_directional_counts
    ) > 0:

        raise ValueError(
            "Delegate-topic directional vote counts "
            "do not reconcile: yes_votes + no_votes "
            "must equal directional_topic_votes."
        )

    result[
        "yes_pct"
    ] = 0.0

    result[
        "no_pct"
    ] = 0.0

    directional_mask = (
        result[
            "directional_topic_votes"
        ]
        >
        0
    )

    result.loc[
        directional_mask,
        "yes_pct",
    ] = (
        result.loc[
            directional_mask,
            "yes_votes",
        ]
        /
        result.loc[
            directional_mask,
            "directional_topic_votes",
        ]
        *
        100
    )

    result.loc[
        directional_mask,
        "no_pct",
    ] = (
        result.loc[
            directional_mask,
            "no_votes",
        ]
        /
        result.loc[
            directional_mask,
            "directional_topic_votes",
        ]
        *
        100
    )

    result[
        "voting_tendency"
    ] = result.apply(
        lambda row:
            assign_voting_tendency(
                int(
                    row[
                        "directional_topic_votes"
                    ]
                ),
                int(
                    row[
                        "yes_votes"
                    ]
                ),
            ),
        axis=1,
    )

    return (
        result
        .sort_values(
            [
                "year",
                "member_id",
                "topic_name",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# BUILD A HUMAN-READABLE TOPIC ROSTER
# =========================================================

def build_topic_roster(
    tendency,
):

    return (
        tendency
        .sort_values(
            [
                "topic_name",
                "voting_tendency",
                "yes_pct",
                "MBR_NAME",
            ],
            ascending=[
                True,
                True,
                False,
                True,
            ],
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# SUMMARIZE DELEGATE TENDENCIES WITHIN EACH TOPIC
# =========================================================

def build_topic_tendency_summary(
    tendency,
):

    result = (
        tendency
        .groupby(
            [
                "year",
                "topic_name",
                "voting_tendency",
            ],
            as_index=False,
        )
        .agg(
            delegates=(
                "member_id",
                "nunique",
            )
        )
    )

    return (
        result
        .sort_values(
            [
                "year",
                "topic_name",
                "voting_tendency",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# SUMMARIZE TENDENCIES BY PARTY AND TOPIC
# =========================================================

def build_party_topic_tendency_summary(
    tendency,
):

    result = (
        tendency
        .groupby(
            [
                "year",
                "party",
                "topic_name",
                "voting_tendency",
            ],
            as_index=False,
        )
        .agg(
            delegates=(
                "member_id",
                "nunique",
            )
        )
    )

    return (
        result
        .sort_values(
            [
                "year",
                "topic_name",
                "party",
                "voting_tendency",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# COMPARE TWO YEARS OF TOPIC VOTING TENDENCY
#
# JOIN KEY:
#
#     member_id
#     + topic_name
#
# Provenance is NOT a join key.
#
# The same analytical topic remains comparable across years
# even when its classification provenance differs.
# =========================================================

def build_voting_tendency_yoy(
    earlier,
    later,
):

    left = (
        earlier.copy()
    )

    right = (
        later.copy()
    )

    if left.empty and right.empty:

        return pd.DataFrame()

    if (
        "year"
        in left.columns
        and
        len(left) > 0
    ):

        earlier_year = int(
            pd.to_numeric(
                left[
                    "year"
                ],
                errors="coerce",
            )
            .dropna()
            .iloc[0]
        )

    else:

        earlier_year = 2025

    if (
        "year"
        in right.columns
        and
        len(right) > 0
    ):

        later_year = int(
            pd.to_numeric(
                right[
                    "year"
                ],
                errors="coerce",
            )
            .dropna()
            .iloc[0]
        )

    else:

        later_year = 2026

    join_keys = [
        "member_id",
        "topic_name",
    ]

    left_columns = [
        "member_id",
        "MBR_NAME",
        "party",
        "topic_name",
        "topic_vote_events",
        "directional_topic_votes",
        "yes_votes",
        "no_votes",
        "yes_pct",
        "no_pct",
        "voting_tendency",
    ]

    right_columns = list(
        left_columns
    )

    if (
        "topic_provenance"
        in left.columns
    ):

        left_columns.append(
            "topic_provenance"
        )

    if (
        "topic_provenance"
        in right.columns
    ):

        right_columns.append(
            "topic_provenance"
        )

    left = left[
        [
            column
            for column
            in left_columns
            if column in left.columns
        ]
    ].copy()

    right = right[
        [
            column
            for column
            in right_columns
            if column in right.columns
        ]
    ].copy()

    yoy = left.merge(
        right,
        on=join_keys,
        how="outer",
        suffixes=(
            f"_{earlier_year}",
            f"_{later_year}",
        ),
        indicator=True,
    )

    yoy[
        "topic_status"
    ] = yoy[
        "_merge"
    ].map(
        {
            "both":
                "Present both years",

            "left_only":
                f"{earlier_year} only",

            "right_only":
                f"{later_year} only",
        }
    )

    tendency_left = (
        f"voting_tendency_"
        f"{earlier_year}"
    )

    tendency_right = (
        f"voting_tendency_"
        f"{later_year}"
    )

    yes_left = (
        f"yes_pct_"
        f"{earlier_year}"
    )

    yes_right = (
        f"yes_pct_"
        f"{later_year}"
    )

    directional_left = (
        f"directional_topic_votes_"
        f"{earlier_year}"
    )

    directional_right = (
        f"directional_topic_votes_"
        f"{later_year}"
    )

    comparable_values = {
        "YES",
        "NO",
        "MIXED",
    }

    yoy[
        "comparable_tendency"
    ] = (
        yoy[
            tendency_left
        ]
        .isin(
            comparable_values
        )
        &
        yoy[
            tendency_right
        ]
        .isin(
            comparable_values
        )
    )

    yoy[
        "voting_tendency_changed"
    ] = (
        yoy[
            "comparable_tendency"
        ]
        &
        (
            yoy[
                tendency_left
            ]
            !=
            yoy[
                tendency_right
            ]
        )
    )

    left_insufficient = (
        yoy[
            tendency_left
        ]
        ==
        "INSUFFICIENT DATA"
    )

    right_insufficient = (
        yoy[
            tendency_right
        ]
        ==
        "INSUFFICIENT DATA"
    )

    yoy[
        "data_availability_changed"
    ] = (
        (
            left_insufficient
            &
            yoy[
                tendency_right
            ]
            .isin(
                comparable_values
            )
        )
        |
        (
            right_insufficient
            &
            yoy[
                tendency_left
            ]
            .isin(
                comparable_values
            )
        )
    )

    yoy[
        "yes_pct_change"
    ] = (
        pd.to_numeric(
            yoy[
                yes_right
            ],
            errors="coerce",
        )
        -
        pd.to_numeric(
            yoy[
                yes_left
            ],
            errors="coerce",
        )
    )

    yoy[
        "directional_topic_vote_change"
    ] = (
        pd.to_numeric(
            yoy[
                directional_right
            ],
            errors="coerce",
        )
        -
        pd.to_numeric(
            yoy[
                directional_left
            ],
            errors="coerce",
        )
    )

    # -----------------------------------------------------
    # ONE DISPLAY NAME / PARTY
    #
    # Prefer the later session when available.
    # -----------------------------------------------------

    later_name = (
        f"MBR_NAME_"
        f"{later_year}"
    )

    earlier_name = (
        f"MBR_NAME_"
        f"{earlier_year}"
    )

    later_party = (
        f"party_"
        f"{later_year}"
    )

    earlier_party = (
        f"party_"
        f"{earlier_year}"
    )

    yoy[
        "MBR_NAME"
    ] = (
        yoy[
            later_name
        ]
        .fillna(
            yoy[
                earlier_name
            ]
        )
    )

    yoy[
        "party"
    ] = (
        yoy[
            later_party
        ]
        .fillna(
            yoy[
                earlier_party
            ]
        )
    )

    yoy = yoy.drop(
        columns=[
            "_merge"
        ]
    )

    return (
        yoy
        .sort_values(
            [
                "comparable_tendency",
                "voting_tendency_changed",
                "yes_pct_change",
            ],
            ascending=[
                False,
                False,
                False,
            ],
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# PRINT A SMALL TERMINAL SUMMARY
# =========================================================

def print_topic_tendency(
    year,
    tendency,
):

    print(
        "\n" + "=" * 78
    )

    print(
        f"{year} DELEGATE x TOPIC "
        "VOTING TENDENCY"
    )

    print(
        "=" * 78
    )

    print(
        "\nVoting tendency counts:"
    )

    print(
        tendency[
            "voting_tendency"
        ]
        .value_counts(
            dropna=False
        )
    )

    usable = (
        tendency[
            tendency[
                "voting_tendency"
            ]
            !=
            "INSUFFICIENT DATA"
        ]
        .copy()
    )

    print(
        "\nExample rows:"
    )

    columns = [
        "member_id",
        "MBR_NAME",
        "party",
        "topic_name",
        "topic_provenance",
        "yes_votes",
        "no_votes",
        "directional_topic_votes",
        "yes_pct",
        "voting_tendency",
    ]

    print(
        usable[
            columns
        ]
        .head(40)
        .to_string(
            index=False,
            float_format=
                lambda value:
                    f"{value:7.2f}",
        )
    )


# =========================================================
# SAVE ONE YEAR'S OUTPUTS
# =========================================================

def save_year_outputs(
    year,
    tendency,
    roster,
    topic_summary,
    party_topic_summary,
):

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    outputs = {

        "delegate_topic_voting_tendency":
            (
                PROCESSED_ROOT
                /
                f"delegate_topic_voting_tendency_{year}.csv"
            ),

        "topic_yes_no_mixed":
            (
                PROCESSED_ROOT
                /
                f"topic_yes_no_mixed_{year}.csv"
            ),

        "topic_voting_tendency_summary":
            (
                PROCESSED_ROOT
                /
                f"topic_voting_tendency_summary_{year}.csv"
            ),

        "party_topic_voting_tendency_summary":
            (
                PROCESSED_ROOT
                /
                f"party_topic_voting_tendency_summary_{year}.csv"
            ),
    }

    write_csv(
        tendency,
        outputs[
            "delegate_topic_voting_tendency"
        ],
    )

    write_csv(
        roster,
        outputs[
            "topic_yes_no_mixed"
        ],
    )

    write_csv(
        topic_summary,
        outputs[
            "topic_voting_tendency_summary"
        ],
    )

    write_csv(
        party_topic_summary,
        outputs[
            "party_topic_voting_tendency_summary"
        ],
    )

    return outputs


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "Topic voting tendency analysis started."
    )

    results = {}

    for year in YEARS:

        member_topic = (
            load_member_vote_topic(
                year
            )
        )

        tendency = (
            build_delegate_topic_voting_tendency(
                member_topic
            )
        )

        roster = (
            build_topic_roster(
                tendency
            )
        )

        topic_summary = (
            build_topic_tendency_summary(
                tendency
            )
        )

        party_topic_summary = (
            build_party_topic_tendency_summary(
                tendency
            )
        )

        print_topic_tendency(
            year,
            tendency,
        )

        outputs = (
            save_year_outputs(
                year,
                tendency,
                roster,
                topic_summary,
                party_topic_summary,
            )
        )

        results[
            year
        ] = tendency

        print(
            "\nSaved:"
        )

        for path in outputs.values():

            print(
                path
            )

    # -----------------------------------------------------
    # OPTIONAL CROSS-YEAR COMPARISON
    #
    # Use the earliest and latest configured sessions.
    # -----------------------------------------------------

    if len(
        YEARS
    ) >= 2:

        earlier_year = (
            YEARS[
                0
            ]
        )

        later_year = (
            YEARS[
                -1
            ]
        )

        yoy = (
            build_voting_tendency_yoy(
                results[
                    earlier_year
                ],
                results[
                    later_year
                ],
            )
        )

        yoy_path = (
            PROCESSED_ROOT
            /
            (
                "delegate_topic_voting_tendency_"
                f"yoy_{earlier_year}_{later_year}.csv"
            )
        )

        write_csv(
            yoy,
            yoy_path,
        )

        print(
            "\nSaved:"
        )

        print(
            yoy_path
        )

    print(
        "\nTopic voting tendency analysis complete."
    )


if __name__ == "__main__":

    main()