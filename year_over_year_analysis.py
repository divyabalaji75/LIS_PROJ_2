from pathlib import Path
import pandas as pd


# =========================================================
# CONFIG
# =========================================================

PROCESSED_ROOT = Path("data/processed")

YEAR_1 = 2025
YEAR_2 = 2026

# Overall delegate comparison threshold
MIN_ELIGIBLE_VOTES = 50

# Exploratory topic comparison threshold
MIN_TOPIC_ELIGIBLE_VOTES = 20

# Stronger threshold for headline topic comparisons
ROBUST_TOPIC_ELIGIBLE_VOTES = 50

# Minimum number of delegates required for a topic
# to appear in headline topic summaries
MIN_DELEGATES_FOR_TOPIC_SUMMARY = 10


# =========================================================
# INPUT FILES
# =========================================================

DELEGATE_FILES = {
    YEAR_1: (
        PROCESSED_ROOT
        / f"delegate_behavior_{YEAR_1}.csv"
    ),
    YEAR_2: (
        PROCESSED_ROOT
        / f"delegate_behavior_{YEAR_2}.csv"
    ),
}

TOPIC_FILES = {
    YEAR_1: (
        PROCESSED_ROOT
        / f"delegate_topic_behavior_{YEAR_1}.csv"
    ),
    YEAR_2: (
        PROCESSED_ROOT
        / f"delegate_topic_behavior_{YEAR_2}.csv"
    ),
}


# =========================================================
# HELPERS
# =========================================================

def require_file(path):

    if not path.exists():

        raise FileNotFoundError(
            f"Missing required file: {path}"
        )


def load_csv(path):

    require_file(path)

    return pd.read_csv(
        path,
        dtype={
            "member_id": str,
            "party": str,
        }
    )


# =========================================================
# LOAD DELEGATE BEHAVIOR
# =========================================================

def load_delegate_behavior(year):

    df = load_csv(
        DELEGATE_FILES[year]
    )

    required = {
        "member_id",
        "MBR_NAME",
        "party",
        "directional_votes",
        "eligible_cross_party_votes",
        "party_breaks",
        "cross_party_votes",
        "cross_party_pct",
        "party_break_pct",
    }

    missing = (
        required
        - set(df.columns)
    )

    if missing:

        raise ValueError(
            f"delegate_behavior_{year}.csv "
            f"is missing columns: {missing}"
        )

    df["member_id"] = (
        df["member_id"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    df["MBR_NAME"] = (
        df["MBR_NAME"]
        .fillna("")
        .str.strip()
    )

    df["party"] = (
        df["party"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    numeric_columns = [
        "directional_votes",
        "eligible_cross_party_votes",
        "party_breaks",
        "cross_party_votes",
        "cross_party_pct",
        "party_break_pct",
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df["year"] = year

    return df


# =========================================================
# BUILD DELEGATE YEAR-OVER-YEAR
# =========================================================

def build_delegate_yoy(
    df_2025,
    df_2026
):

    left = (
        df_2025[
            [
                "member_id",
                "MBR_NAME",
                "party",
                "directional_votes",
                "eligible_cross_party_votes",
                "party_breaks",
                "cross_party_votes",
                "cross_party_pct",
                "party_break_pct",
            ]
        ]
        .copy()
        .rename(
            columns={
                "MBR_NAME":
                    "MBR_NAME_2025",

                "party":
                    "party_2025",

                "directional_votes":
                    "directional_votes_2025",

                "eligible_cross_party_votes":
                    "eligible_cross_party_votes_2025",

                "party_breaks":
                    "party_breaks_2025",

                "cross_party_votes":
                    "cross_party_votes_2025",

                "cross_party_pct":
                    "cross_party_pct_2025",

                "party_break_pct":
                    "party_break_pct_2025",
            }
        )
    )

    right = (
        df_2026[
            [
                "member_id",
                "MBR_NAME",
                "party",
                "directional_votes",
                "eligible_cross_party_votes",
                "party_breaks",
                "cross_party_votes",
                "cross_party_pct",
                "party_break_pct",
            ]
        ]
        .copy()
        .rename(
            columns={
                "MBR_NAME":
                    "MBR_NAME_2026",

                "party":
                    "party_2026",

                "directional_votes":
                    "directional_votes_2026",

                "eligible_cross_party_votes":
                    "eligible_cross_party_votes_2026",

                "party_breaks":
                    "party_breaks_2026",

                "cross_party_votes":
                    "cross_party_votes_2026",

                "cross_party_pct":
                    "cross_party_pct_2026",

                "party_break_pct":
                    "party_break_pct_2026",
            }
        )
    )

    yoy = left.merge(
        right,
        on="member_id",
        how="outer",
        indicator=True,
        validate="one_to_one"
    )

    yoy[
        "member_status"
    ] = (
        yoy[
            "_merge"
        ]
        .map(
            {
                "both":
                    "Present both years",

                "left_only":
                    "2025 only",

                "right_only":
                    "2026 only",
            }
        )
    )

    yoy = yoy.drop(
        columns=[
            "_merge"
        ]
    )

    yoy[
        "MBR_NAME"
    ] = (
        yoy[
            "MBR_NAME_2026"
        ]
        .fillna(
            yoy[
                "MBR_NAME_2025"
            ]
        )
    )

    yoy[
        "party"
    ] = (
        yoy[
            "party_2026"
        ]
        .fillna(
            yoy[
                "party_2025"
            ]
        )
    )

    # -----------------------------------------------------
    # CHANGE METRICS
    # -----------------------------------------------------

    yoy[
        "cross_party_vote_change"
    ] = (
        yoy[
            "cross_party_votes_2026"
        ]
        -
        yoy[
            "cross_party_votes_2025"
        ]
    )

    yoy[
        "cross_party_pct_change"
    ] = (
        yoy[
            "cross_party_pct_2026"
        ]
        -
        yoy[
            "cross_party_pct_2025"
        ]
    )

    yoy[
        "party_break_change"
    ] = (
        yoy[
            "party_breaks_2026"
        ]
        -
        yoy[
            "party_breaks_2025"
        ]
    )

    yoy[
        "party_break_pct_change"
    ] = (
        yoy[
            "party_break_pct_2026"
        ]
        -
        yoy[
            "party_break_pct_2025"
        ]
    )

    # -----------------------------------------------------
    # COMPARABILITY
    # -----------------------------------------------------

    yoy[
        "comparable_sample"
    ] = (
        (
            yoy[
                "member_status"
            ]
            ==
            "Present both years"
        )
        &
        (
            yoy[
                "eligible_cross_party_votes_2025"
            ]
            >=
            MIN_ELIGIBLE_VOTES
        )
        &
        (
            yoy[
                "eligible_cross_party_votes_2026"
            ]
            >=
            MIN_ELIGIBLE_VOTES
        )
    )

    columns = [
        "member_id",
        "MBR_NAME",
        "party",
        "member_status",
        "comparable_sample",

        "directional_votes_2025",
        "directional_votes_2026",

        "eligible_cross_party_votes_2025",
        "eligible_cross_party_votes_2026",

        "cross_party_votes_2025",
        "cross_party_votes_2026",
        "cross_party_vote_change",

        "cross_party_pct_2025",
        "cross_party_pct_2026",
        "cross_party_pct_change",

        "party_breaks_2025",
        "party_breaks_2026",
        "party_break_change",

        "party_break_pct_2025",
        "party_break_pct_2026",
        "party_break_pct_change",

        "MBR_NAME_2025",
        "MBR_NAME_2026",
        "party_2025",
        "party_2026",
    ]

    return (
        yoy[
            columns
        ]
        .sort_values(
            [
                "comparable_sample",
                "cross_party_pct_change",
            ],
            ascending=[
                False,
                False,
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# LOAD TOPIC BEHAVIOR
# =========================================================

def load_topic_behavior(year):

    df = load_csv(
        TOPIC_FILES[year]
    )

    required = {
        "member_id",
        "MBR_NAME",
        "party",
        "topic_name",
        "classification",
        "topic_vote_events",
        "eligible_topic_events",
        "party_break_events",
        "cross_party_events",
        "cross_party_pct",
    }

    missing = (
        required
        - set(df.columns)
    )

    if missing:

        raise ValueError(
            f"delegate_topic_behavior_{year}.csv "
            f"is missing columns: {missing}"
        )

    df["member_id"] = (
        df["member_id"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    df["MBR_NAME"] = (
        df["MBR_NAME"]
        .fillna("")
        .str.strip()
    )

    df["party"] = (
        df["party"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    df["topic_name"] = (
        df["topic_name"]
        .fillna("")
        .str.strip()
    )

    df["classification"] = (
        df["classification"]
        .fillna("")
        .str.strip()
    )

    numeric_columns = [
        "topic_vote_events",
        "eligible_topic_events",
        "party_break_events",
        "cross_party_events",
        "cross_party_pct",
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df["year"] = year

    return df


# =========================================================
# BUILD TOPIC YEAR-OVER-YEAR
# =========================================================

def build_topic_yoy(
    topic_2025,
    topic_2026
):

    # -----------------------------------------------------
    # UNCLASSIFIED STAYS IN SOURCE FILES
    #
    # It is excluded from policy-topic YoY analysis.
    # -----------------------------------------------------

    topic_2025 = topic_2025[
        topic_2025[
            "classification"
        ]
        !=
        "Unclassified"
    ].copy()

    topic_2026 = topic_2026[
        topic_2026[
            "classification"
        ]
        !=
        "Unclassified"
    ].copy()

    # -----------------------------------------------------
    # CLASSIFICATION REMAINS PART OF JOIN KEY
    #
    # Official LIS subject and description-derived
    # labels are not silently treated as equivalent.
    # -----------------------------------------------------

    join_keys = [
        "member_id",
        "topic_name",
        "classification",
    ]

    left = (
        topic_2025[
            join_keys
            +
            [
                "MBR_NAME",
                "party",
                "topic_vote_events",
                "eligible_topic_events",
                "party_break_events",
                "cross_party_events",
                "cross_party_pct",
            ]
        ]
        .copy()
        .rename(
            columns={
                "MBR_NAME":
                    "MBR_NAME_2025",

                "party":
                    "party_2025",

                "topic_vote_events":
                    "topic_vote_events_2025",

                "eligible_topic_events":
                    "eligible_topic_events_2025",

                "party_break_events":
                    "party_break_events_2025",

                "cross_party_events":
                    "cross_party_events_2025",

                "cross_party_pct":
                    "cross_party_pct_2025",
            }
        )
    )

    right = (
        topic_2026[
            join_keys
            +
            [
                "MBR_NAME",
                "party",
                "topic_vote_events",
                "eligible_topic_events",
                "party_break_events",
                "cross_party_events",
                "cross_party_pct",
            ]
        ]
        .copy()
        .rename(
            columns={
                "MBR_NAME":
                    "MBR_NAME_2026",

                "party":
                    "party_2026",

                "topic_vote_events":
                    "topic_vote_events_2026",

                "eligible_topic_events":
                    "eligible_topic_events_2026",

                "party_break_events":
                    "party_break_events_2026",

                "cross_party_events":
                    "cross_party_events_2026",

                "cross_party_pct":
                    "cross_party_pct_2026",
            }
        )
    )

    yoy = left.merge(
        right,
        on=join_keys,
        how="outer",
        indicator=True,
        validate="one_to_one"
    )

    yoy[
        "topic_status"
    ] = (
        yoy[
            "_merge"
        ]
        .map(
            {
                "both":
                    "Present both years",

                "left_only":
                    "2025 only",

                "right_only":
                    "2026 only",
            }
        )
    )

    yoy = yoy.drop(
        columns=[
            "_merge"
        ]
    )

    yoy[
        "MBR_NAME"
    ] = (
        yoy[
            "MBR_NAME_2026"
        ]
        .fillna(
            yoy[
                "MBR_NAME_2025"
            ]
        )
    )

    yoy[
        "party"
    ] = (
        yoy[
            "party_2026"
        ]
        .fillna(
            yoy[
                "party_2025"
            ]
        )
    )

    # -----------------------------------------------------
    # CHANGE METRICS
    # -----------------------------------------------------

    yoy[
        "cross_party_event_change"
    ] = (
        yoy[
            "cross_party_events_2026"
        ]
        -
        yoy[
            "cross_party_events_2025"
        ]
    )

    yoy[
        "cross_party_pct_change"
    ] = (
        yoy[
            "cross_party_pct_2026"
        ]
        -
        yoy[
            "cross_party_pct_2025"
        ]
    )

    yoy[
        "party_break_event_change"
    ] = (
        yoy[
            "party_break_events_2026"
        ]
        -
        yoy[
            "party_break_events_2025"
        ]
    )

    yoy[
        "eligible_topic_event_change"
    ] = (
        yoy[
            "eligible_topic_events_2026"
        ]
        -
        yoy[
            "eligible_topic_events_2025"
        ]
    )

    # -----------------------------------------------------
    # EXPLORATORY COMPARABILITY FLAG
    #
    # Keep 20+ eligible events in each year.
    # This preserves a broad research dataset.
    # -----------------------------------------------------

    yoy[
        "comparable_topic_sample"
    ] = (
        (
            yoy[
                "topic_status"
            ]
            ==
            "Present both years"
        )
        &
        (
            yoy[
                "eligible_topic_events_2025"
            ]
            >=
            MIN_TOPIC_ELIGIBLE_VOTES
        )
        &
        (
            yoy[
                "eligible_topic_events_2026"
            ]
            >=
            MIN_TOPIC_ELIGIBLE_VOTES
        )
    )

    # -----------------------------------------------------
    # ROBUST COMPARABILITY FLAG
    #
    # Stronger standard for headline results.
    # -----------------------------------------------------

    yoy[
        "robust_topic_sample"
    ] = (
        (
            yoy[
                "topic_status"
            ]
            ==
            "Present both years"
        )
        &
        (
            yoy[
                "eligible_topic_events_2025"
            ]
            >=
            ROBUST_TOPIC_ELIGIBLE_VOTES
        )
        &
        (
            yoy[
                "eligible_topic_events_2026"
            ]
            >=
            ROBUST_TOPIC_ELIGIBLE_VOTES
        )
    )

    columns = [
        "member_id",
        "MBR_NAME",
        "party",

        "topic_name",
        "classification",

        "topic_status",

        "comparable_topic_sample",
        "robust_topic_sample",

        "topic_vote_events_2025",
        "topic_vote_events_2026",

        "eligible_topic_events_2025",
        "eligible_topic_events_2026",
        "eligible_topic_event_change",

        "cross_party_events_2025",
        "cross_party_events_2026",
        "cross_party_event_change",

        "cross_party_pct_2025",
        "cross_party_pct_2026",
        "cross_party_pct_change",

        "party_break_events_2025",
        "party_break_events_2026",
        "party_break_event_change",

        "MBR_NAME_2025",
        "MBR_NAME_2026",
        "party_2025",
        "party_2026",
    ]

    return (
        yoy[
            columns
        ]
        .sort_values(
            [
                "robust_topic_sample",
                "comparable_topic_sample",
                "cross_party_pct_change",
            ],
            ascending=[
                False,
                False,
                False,
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# PARTY-LEVEL SUMMARY
# =========================================================

def build_party_yoy_summary(
    delegate_yoy
):

    comparable = (
        delegate_yoy[
            delegate_yoy[
                "comparable_sample"
            ]
        ]
        .copy()
    )

    if len(
        comparable
    ) == 0:

        return pd.DataFrame()

    summary = (
        comparable
        .groupby(
            "party",
            as_index=False
        )
        .agg(

            delegates=(
                "member_id",
                "nunique"
            ),

            avg_cross_party_pct_2025=(
                "cross_party_pct_2025",
                "mean"
            ),

            avg_cross_party_pct_2026=(
                "cross_party_pct_2026",
                "mean"
            ),

            avg_cross_party_pct_change=(
                "cross_party_pct_change",
                "mean"
            ),

            median_cross_party_pct_change=(
                "cross_party_pct_change",
                "median"
            ),

            total_cross_party_votes_2025=(
                "cross_party_votes_2025",
                "sum"
            ),

            total_cross_party_votes_2026=(
                "cross_party_votes_2026",
                "sum"
            ),
        )
    )

    return summary


# =========================================================
# TOPIC SUMMARY
#
# This uses ROBUST topic pairs only.
#
# Topics must also have enough delegates before appearing
# in the headline summary.
# =========================================================

def build_topic_change_summary(
    topic_yoy
):

    robust = (
        topic_yoy[
            topic_yoy[
                "robust_topic_sample"
            ]
        ]
        .copy()
    )

    if len(
        robust
    ) == 0:

        return pd.DataFrame()

    summary = (
        robust
        .groupby(
            [
                "topic_name",
                "classification",
            ],
            as_index=False
        )
        .agg(

            delegates_compared=(
                "member_id",
                "nunique"
            ),

            avg_cross_party_pct_2025=(
                "cross_party_pct_2025",
                "mean"
            ),

            avg_cross_party_pct_2026=(
                "cross_party_pct_2026",
                "mean"
            ),

            avg_cross_party_pct_change=(
                "cross_party_pct_change",
                "mean"
            ),

            median_cross_party_pct_change=(
                "cross_party_pct_change",
                "median"
            ),

            total_cross_party_events_2025=(
                "cross_party_events_2025",
                "sum"
            ),

            total_cross_party_events_2026=(
                "cross_party_events_2026",
                "sum"
            ),

            total_eligible_topic_events_2025=(
                "eligible_topic_events_2025",
                "sum"
            ),

            total_eligible_topic_events_2026=(
                "eligible_topic_events_2026",
                "sum"
            ),
        )
    )

    summary[
        "headline_topic"
    ] = (
        summary[
            "delegates_compared"
        ]
        >=
        MIN_DELEGATES_FOR_TOPIC_SUMMARY
    )

    return (
        summary
        .sort_values(
            [
                "headline_topic",
                "avg_cross_party_pct_change",
            ],
            ascending=[
                False,
                False,
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# EXPLORATORY TOPIC SUMMARY
#
# This keeps the broader 20-vote threshold.
# Useful for research / drill-down, but not headline claims.
# =========================================================

def build_exploratory_topic_summary(
    topic_yoy
):

    exploratory = (
        topic_yoy[
            topic_yoy[
                "comparable_topic_sample"
            ]
        ]
        .copy()
    )

    if len(
        exploratory
    ) == 0:

        return pd.DataFrame()

    summary = (
        exploratory
        .groupby(
            [
                "topic_name",
                "classification",
            ],
            as_index=False
        )
        .agg(

            delegates_compared=(
                "member_id",
                "nunique"
            ),

            avg_cross_party_pct_2025=(
                "cross_party_pct_2025",
                "mean"
            ),

            avg_cross_party_pct_2026=(
                "cross_party_pct_2026",
                "mean"
            ),

            avg_cross_party_pct_change=(
                "cross_party_pct_change",
                "mean"
            ),

            median_cross_party_pct_change=(
                "cross_party_pct_change",
                "median"
            ),

            total_cross_party_events_2025=(
                "cross_party_events_2025",
                "sum"
            ),

            total_cross_party_events_2026=(
                "cross_party_events_2026",
                "sum"
            ),
        )
    )

    return (
        summary
        .sort_values(
            "avg_cross_party_pct_change",
            ascending=False
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# PRINT DELEGATE RESULTS
# =========================================================

def print_delegate_results(
    delegate_yoy
):

    comparable = (
        delegate_yoy[
            delegate_yoy[
                "comparable_sample"
            ]
        ]
        .copy()
    )

    print(
        "\n" + "=" * 78
    )

    print(
        "2025 → 2026 DELEGATE "
        "YEAR-OVER-YEAR ANALYSIS"
    )

    print(
        "=" * 78
    )

    print(
        "\nDelegates present both years:"
    )

    print(
        (
            delegate_yoy[
                "member_status"
            ]
            ==
            "Present both years"
        )
        .sum()
    )

    print(
        "\nDelegates meeting "
        "comparison threshold:"
    )

    print(
        len(
            comparable
        )
    )

    # -----------------------------------------------------
    # INCREASES
    # -----------------------------------------------------

    increases = (
        comparable
        .sort_values(
            "cross_party_pct_change",
            ascending=False
        )
        .head(20)
    )

    print(
        "\nTop 20 increases in "
        "cross-party voting rate:"
    )

    print(
        increases[
            [
                "member_id",
                "MBR_NAME",
                "party",
                "cross_party_pct_2025",
                "cross_party_pct_2026",
                "cross_party_pct_change",
                "cross_party_votes_2025",
                "cross_party_votes_2026",
            ]
        ]
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:7.2f}"
        )
    )

    # -----------------------------------------------------
    # DECREASES
    # -----------------------------------------------------

    decreases = (
        comparable
        .sort_values(
            "cross_party_pct_change",
            ascending=True
        )
        .head(20)
    )

    print(
        "\nTop 20 decreases in "
        "cross-party voting rate:"
    )

    print(
        decreases[
            [
                "member_id",
                "MBR_NAME",
                "party",
                "cross_party_pct_2025",
                "cross_party_pct_2026",
                "cross_party_pct_change",
                "cross_party_votes_2025",
                "cross_party_votes_2026",
            ]
        ]
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:7.2f}"
        )
    )


# =========================================================
# PRINT PARTY SUMMARY
# =========================================================

def print_party_summary(
    party_summary
):

    print(
        "\n" + "=" * 78
    )

    print(
        "PARTY-LEVEL DESCRIPTIVE SUMMARY"
    )

    print(
        "=" * 78
    )

    if len(
        party_summary
    ) == 0:

        print(
            "\nNo comparable party-level data."
        )

        return

    print(
        "\nComparable delegates only:"
    )

    print(
        party_summary.to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:7.2f}"
        )
    )


# =========================================================
# PRINT TOPIC RESULTS
# =========================================================

def print_topic_results(
    topic_yoy,
    topic_summary
):

    exploratory = (
        topic_yoy[
            topic_yoy[
                "comparable_topic_sample"
            ]
        ]
        .copy()
    )

    robust = (
        topic_yoy[
            topic_yoy[
                "robust_topic_sample"
            ]
        ]
        .copy()
    )

    print(
        "\n" + "=" * 78
    )

    print(
        "DELEGATE × TOPIC YEAR-OVER-YEAR ANALYSIS"
    )

    print(
        "=" * 78
    )

    print(
        "\nExploratory comparable "
        "delegate-topic pairs "
        f"(>= {MIN_TOPIC_ELIGIBLE_VOTES} "
        "eligible events each year):"
    )

    print(
        len(
            exploratory
        )
    )

    print(
        "\nRobust delegate-topic pairs "
        f"(>= {ROBUST_TOPIC_ELIGIBLE_VOTES} "
        "eligible events each year):"
    )

    print(
        len(
            robust
        )
    )

    # -----------------------------------------------------
    # ROBUST DELEGATE-TOPIC INCREASES
    # -----------------------------------------------------

    if len(
        robust
    ) > 0:

        print(
            "\nTop 25 ROBUST delegate-topic "
            "cross-party increases:"
        )

        print(
            robust
            .sort_values(
                "cross_party_pct_change",
                ascending=False
            )
            [
                [
                    "member_id",
                    "MBR_NAME",
                    "party",
                    "topic_name",
                    "classification",
                    "cross_party_pct_2025",
                    "cross_party_pct_2026",
                    "cross_party_pct_change",
                    "eligible_topic_events_2025",
                    "eligible_topic_events_2026",
                ]
            ]
            .head(25)
            .to_string(
                index=False,
                float_format=
                    lambda x:
                        f"{x:7.2f}"
            )
        )

        print(
            "\nTop 25 ROBUST delegate-topic "
            "cross-party decreases:"
        )

        print(
            robust
            .sort_values(
                "cross_party_pct_change",
                ascending=True
            )
            [
                [
                    "member_id",
                    "MBR_NAME",
                    "party",
                    "topic_name",
                    "classification",
                    "cross_party_pct_2025",
                    "cross_party_pct_2026",
                    "cross_party_pct_change",
                    "eligible_topic_events_2025",
                    "eligible_topic_events_2026",
                ]
            ]
            .head(25)
            .to_string(
                index=False,
                float_format=
                    lambda x:
                        f"{x:7.2f}"
            )
        )

    # -----------------------------------------------------
    # HEADLINE TOPICS
    # -----------------------------------------------------

    print(
        "\nHeadline topic-level summary:"
    )

    if len(
        topic_summary
    ) == 0:

        print(
            "\nNo robust topic-level data."
        )

        return

    headline = (
        topic_summary[
            topic_summary[
                "headline_topic"
            ]
        ]
        .copy()
    )

    if len(
        headline
    ) == 0:

        print(
            "\nNo topics meet the "
            f"{MIN_DELEGATES_FOR_TOPIC_SUMMARY}-delegate "
            "headline threshold."
        )

        return

    print(
        headline[
            [
                "topic_name",
                "classification",
                "delegates_compared",
                "avg_cross_party_pct_2025",
                "avg_cross_party_pct_2026",
                "avg_cross_party_pct_change",
                "median_cross_party_pct_change",
                "total_cross_party_events_2025",
                "total_cross_party_events_2026",
                "total_eligible_topic_events_2025",
                "total_eligible_topic_events_2026",
            ]
        ]
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:7.2f}"
        )
    )


# =========================================================
# SAVE OUTPUTS
# =========================================================

def save_outputs(
    delegate_yoy,
    topic_yoy,
    party_summary,
    topic_summary,
    exploratory_topic_summary
):

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    outputs = {

        "delegate_yoy":
            PROCESSED_ROOT
            / "delegate_behavior_yoy_2025_2026.csv",

        "topic_yoy":
            PROCESSED_ROOT
            / "delegate_topic_behavior_yoy_2025_2026.csv",

        "party_summary":
            PROCESSED_ROOT
            / "party_behavior_yoy_2025_2026.csv",

        "topic_summary_robust":
            PROCESSED_ROOT
            / "topic_behavior_yoy_robust_2025_2026.csv",

        "topic_summary_exploratory":
            PROCESSED_ROOT
            / "topic_behavior_yoy_exploratory_2025_2026.csv",
    }

    delegate_yoy.to_csv(
        outputs[
            "delegate_yoy"
        ],
        index=False
    )

    topic_yoy.to_csv(
        outputs[
            "topic_yoy"
        ],
        index=False
    )

    party_summary.to_csv(
        outputs[
            "party_summary"
        ],
        index=False
    )

    topic_summary.to_csv(
        outputs[
            "topic_summary_robust"
        ],
        index=False
    )

    exploratory_topic_summary.to_csv(
        outputs[
            "topic_summary_exploratory"
        ],
        index=False
    )

    return outputs


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print(
        "Year-over-year analysis started."
    )

    print(
        "\nLoading delegate behavior..."
    )

    delegate_2025 = (
        load_delegate_behavior(
            YEAR_1
        )
    )

    delegate_2026 = (
        load_delegate_behavior(
            YEAR_2
        )
    )

    print(
        "Loading topic behavior..."
    )

    topic_2025 = (
        load_topic_behavior(
            YEAR_1
        )
    )

    topic_2026 = (
        load_topic_behavior(
            YEAR_2
        )
    )

    # -----------------------------------------------------
    # DELEGATE YOY
    # -----------------------------------------------------

    delegate_yoy = (
        build_delegate_yoy(
            delegate_2025,
            delegate_2026
        )
    )

    # -----------------------------------------------------
    # TOPIC YOY
    # -----------------------------------------------------

    topic_yoy = (
        build_topic_yoy(
            topic_2025,
            topic_2026
        )
    )

    # -----------------------------------------------------
    # PARTY SUMMARY
    # -----------------------------------------------------

    party_summary = (
        build_party_yoy_summary(
            delegate_yoy
        )
    )

    # -----------------------------------------------------
    # ROBUST TOPIC SUMMARY
    # -----------------------------------------------------

    topic_summary = (
        build_topic_change_summary(
            topic_yoy
        )
    )

    # -----------------------------------------------------
    # EXPLORATORY TOPIC SUMMARY
    # -----------------------------------------------------

    exploratory_topic_summary = (
        build_exploratory_topic_summary(
            topic_yoy
        )
    )

    # -----------------------------------------------------
    # PRINT
    # -----------------------------------------------------

    print_delegate_results(
        delegate_yoy
    )

    print_party_summary(
        party_summary
    )

    print_topic_results(
        topic_yoy,
        topic_summary
    )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    outputs = (
        save_outputs(
            delegate_yoy,
            topic_yoy,
            party_summary,
            topic_summary,
            exploratory_topic_summary
        )
    )

    print(
        "\n" + "=" * 78
    )

    print(
        "FILES SAVED"
    )

    print(
        "=" * 78
    )

    for path in (
        outputs.values()
    ):

        print(
            path
        )

    print(
        "\nFinished."
    )