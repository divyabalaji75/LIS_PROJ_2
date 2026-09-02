from pathlib import Path
import pandas as pd


# =========================================================
# CONFIG
# =========================================================

PROCESSED_ROOT = Path("data/processed")

YEARS = [2025, 2026]

# Minimum number of directional Y/N topic votes required
# before assigning a voting tendency.
MIN_TOPIC_DIRECTIONAL_VOTES = 10

# Voting tendency thresholds.
YES_THRESHOLD = 0.65
NO_THRESHOLD = 0.35

# Valid upstream classification labels.
ALLOWED_CLASSIFICATIONS = {
    "Official LIS subject",
    "Derived from LIS bill description",
    "Unclassified",
}


# =========================================================
# INPUT FILES
# =========================================================

MEMBER_TOPIC_FILES = {
    year: (
        PROCESSED_ROOT
        / f"member_vote_topic_{year}.csv"
    )
    for year in YEARS
}


# =========================================================
# HELPERS
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
# LOAD MEMBER-VOTE-TOPIC
# =========================================================

def load_member_vote_topic(year):

    path = MEMBER_TOPIC_FILES[year]

    require_file(path)

    df = pd.read_csv(
        path,
        dtype=str
    )

    required = {
        "year",
        "vote_id",
        "member_id",
        "MBR_NAME",
        "party",
        "vote",
        "topic_name",
        "classification",
    }

    missing = (
        required
        - set(df.columns)
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

    df["classification"] = normalize_text(
        df["classification"]
    )

    invalid_classifications = (
        set(
            df["classification"]
            .dropna()
            .unique()
        )
        -
        ALLOWED_CLASSIFICATIONS
    )

    if invalid_classifications:

        raise ValueError(
            f"{year}: unexpected classification "
            f"values: {invalid_classifications}"
        )

    return df


# =========================================================
# ASSIGN VOTING TENDENCY
#
# IMPORTANT:
#
# YES means:
# the delegate generally voted Yes on vote events
# associated with this topic.
#
# NO means:
# the delegate generally voted No on vote events
# associated with this topic.
#
# MIXED means:
# the delegate's Yes/No record is not strongly one-sided.
#
# This does NOT infer the delegate's personal policy view.
# =========================================================

def assign_voting_tendency(
    directional_votes,
    yes_rate
):

    if (
        directional_votes
        <
        MIN_TOPIC_DIRECTIONAL_VOTES
    ):
        return "INSUFFICIENT DATA"

    if (
        yes_rate
        >=
        YES_THRESHOLD
    ):
        return "YES"

    if (
        yes_rate
        <=
        NO_THRESHOLD
    ):
        return "NO"

    return "MIXED"


# =========================================================
# BUILD DELEGATE × TOPIC VOTING TENDENCY
# =========================================================

def build_delegate_topic_voting_tendency(
    member_vote_topic
):

    # -----------------------------------------------------
    # Exclude Unclassified from policy-topic tendency.
    # It remains preserved upstream.
    # -----------------------------------------------------

    df = (
        member_vote_topic[
            member_vote_topic[
                "classification"
            ]
            !=
            "Unclassified"
        ]
        .copy()
    )

    # -----------------------------------------------------
    # DIRECTIONAL FLAGS
    # -----------------------------------------------------

    df["is_yes"] = (
        df["vote"]
        ==
        "Y"
    )

    df["is_no"] = (
        df["vote"]
        ==
        "N"
    )

    df["is_directional"] = (
        df["vote"]
        .isin(
            [
                "Y",
                "N",
            ]
        )
    )

    # -----------------------------------------------------
    # AGGREGATE
    # -----------------------------------------------------

    summary = (
        df
        .groupby(
            [
                "year",
                "member_id",
                "MBR_NAME",
                "party",
                "topic_name",
                "classification",
            ],
            as_index=False
        )
        .agg(
            topic_vote_events=(
                "vote_id",
                "nunique"
            ),

            yes_votes=(
                "is_yes",
                "sum"
            ),

            no_votes=(
                "is_no",
                "sum"
            ),

            directional_topic_votes=(
                "is_directional",
                "sum"
            ),
        )
    )

    # -----------------------------------------------------
    # RATE CALCULATION
    # -----------------------------------------------------

    summary["yes_rate"] = 0.0
    summary["no_rate"] = 0.0

    valid = (
        summary[
            "directional_topic_votes"
        ]
        >
        0
    )

    summary.loc[
        valid,
        "yes_rate"
    ] = (
        summary.loc[
            valid,
            "yes_votes"
        ]
        /
        summary.loc[
            valid,
            "directional_topic_votes"
        ]
    )

    summary.loc[
        valid,
        "no_rate"
    ] = (
        summary.loc[
            valid,
            "no_votes"
        ]
        /
        summary.loc[
            valid,
            "directional_topic_votes"
        ]
    )

    # -----------------------------------------------------
    # ASSIGN TENDENCY
    # -----------------------------------------------------

    summary[
        "voting_tendency"
    ] = summary.apply(
        lambda row:
            assign_voting_tendency(
                row[
                    "directional_topic_votes"
                ],
                row[
                    "yes_rate"
                ]
            ),
        axis=1
    )

    # -----------------------------------------------------
    # DISPLAY PERCENTAGES
    # -----------------------------------------------------

    summary[
        "yes_pct"
    ] = (
        summary[
            "yes_rate"
        ]
        *
        100
    )

    summary[
        "no_pct"
    ] = (
        summary[
            "no_rate"
        ]
        *
        100
    )

    summary = summary.drop(
        columns=[
            "yes_rate",
            "no_rate",
        ]
    )

    return (
        summary
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
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# BUILD TOPIC YES / NO / MIXED ROSTER
#
# Answers:
# "Who are the Yes, No, and Mixed delegates
# for this topic?"
# =========================================================

def build_topic_voting_tendency_roster(
    delegate_topic_tendency
):

    roster = (
        delegate_topic_tendency[
            [
                "year",
                "topic_name",
                "classification",
                "member_id",
                "MBR_NAME",
                "party",
                "topic_vote_events",
                "yes_votes",
                "no_votes",
                "directional_topic_votes",
                "yes_pct",
                "no_pct",
                "voting_tendency",
            ]
        ]
        .copy()
    )

    return (
        roster
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
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# BUILD TOPIC SUMMARY
#
# Counts Yes / No / Mixed delegates by topic.
# =========================================================

def build_topic_voting_tendency_summary(
    delegate_topic_tendency
):

    usable = (
        delegate_topic_tendency[
            delegate_topic_tendency[
                "voting_tendency"
            ]
            !=
            "INSUFFICIENT DATA"
        ]
        .copy()
    )

    counts = (
        usable
        .groupby(
            [
                "year",
                "topic_name",
                "classification",
                "voting_tendency",
            ]
        )
        .size()
        .reset_index(
            name="delegates"
        )
    )

    pivot = (
        counts
        .pivot_table(
            index=[
                "year",
                "topic_name",
                "classification",
            ],
            columns=
                "voting_tendency",
            values=
                "delegates",
            fill_value=
                0
        )
        .reset_index()
    )

    for column in [
        "YES",
        "NO",
        "MIXED",
    ]:

        if column not in pivot.columns:
            pivot[column] = 0

    pivot = pivot.rename(
        columns={
            "YES":
                "yes_delegates",

            "NO":
                "no_delegates",

            "MIXED":
                "mixed_delegates",
        }
    )

    pivot[
        "classified_delegates"
    ] = (
        pivot[
            "yes_delegates"
        ]
        +
        pivot[
            "no_delegates"
        ]
        +
        pivot[
            "mixed_delegates"
        ]
    )

    # -----------------------------------------------------
    # SHARE OF CLASSIFIED DELEGATES
    # -----------------------------------------------------

    for column in [
        "yes_delegate_pct",
        "no_delegate_pct",
        "mixed_delegate_pct",
    ]:
        pivot[column] = 0.0

    valid = (
        pivot[
            "classified_delegates"
        ]
        >
        0
    )

    pivot.loc[
        valid,
        "yes_delegate_pct"
    ] = (
        pivot.loc[
            valid,
            "yes_delegates"
        ]
        /
        pivot.loc[
            valid,
            "classified_delegates"
        ]
        *
        100
    )

    pivot.loc[
        valid,
        "no_delegate_pct"
    ] = (
        pivot.loc[
            valid,
            "no_delegates"
        ]
        /
        pivot.loc[
            valid,
            "classified_delegates"
        ]
        *
        100
    )

    pivot.loc[
        valid,
        "mixed_delegate_pct"
    ] = (
        pivot.loc[
            valid,
            "mixed_delegates"
        ]
        /
        pivot.loc[
            valid,
            "classified_delegates"
        ]
        *
        100
    )

    return (
        pivot
        .sort_values(
            [
                "year",
                "topic_name",
                "classification",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# BUILD PARTY × TOPIC TENDENCY SUMMARY
# =========================================================

def build_party_topic_voting_tendency_summary(
    delegate_topic_tendency
):

    usable = (
        delegate_topic_tendency[
            delegate_topic_tendency[
                "voting_tendency"
            ]
            !=
            "INSUFFICIENT DATA"
        ]
        .copy()
    )

    counts = (
        usable
        .groupby(
            [
                "year",
                "topic_name",
                "classification",
                "party",
                "voting_tendency",
            ]
        )
        .size()
        .reset_index(
            name="delegates"
        )
    )

    pivot = (
        counts
        .pivot_table(
            index=[
                "year",
                "topic_name",
                "classification",
                "party",
            ],
            columns=
                "voting_tendency",
            values=
                "delegates",
            fill_value=
                0
        )
        .reset_index()
    )

    for column in [
        "YES",
        "NO",
        "MIXED",
    ]:

        if column not in pivot.columns:
            pivot[column] = 0

    pivot = pivot.rename(
        columns={
            "YES":
                "yes_delegates",

            "NO":
                "no_delegates",

            "MIXED":
                "mixed_delegates",
        }
    )

    pivot[
        "classified_delegates"
    ] = (
        pivot[
            "yes_delegates"
        ]
        +
        pivot[
            "no_delegates"
        ]
        +
        pivot[
            "mixed_delegates"
        ]
    )

    return (
        pivot
        .sort_values(
            [
                "year",
                "topic_name",
                "classification",
                "party",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# BUILD YEAR-OVER-YEAR TENDENCY COMPARISON
# =========================================================

def build_voting_tendency_yoy(
    tendency_2025,
    tendency_2026
):

    join_keys = [
        "member_id",
        "topic_name",
        "classification",
    ]

    left = (
        tendency_2025[
            join_keys
            +
            [
                "MBR_NAME",
                "party",
                "yes_votes",
                "no_votes",
                "directional_topic_votes",
                "yes_pct",
                "no_pct",
                "voting_tendency",
            ]
        ]
        .copy()
        .rename(
            columns={
                "MBR_NAME":
                    "MBR_NAME_2025",

                "party":
                    "party_2025",

                "yes_votes":
                    "yes_votes_2025",

                "no_votes":
                    "no_votes_2025",

                "directional_topic_votes":
                    "directional_topic_votes_2025",

                "yes_pct":
                    "yes_pct_2025",

                "no_pct":
                    "no_pct_2025",

                "voting_tendency":
                    "voting_tendency_2025",
            }
        )
    )

    right = (
        tendency_2026[
            join_keys
            +
            [
                "MBR_NAME",
                "party",
                "yes_votes",
                "no_votes",
                "directional_topic_votes",
                "yes_pct",
                "no_pct",
                "voting_tendency",
            ]
        ]
        .copy()
        .rename(
            columns={
                "MBR_NAME":
                    "MBR_NAME_2026",

                "party":
                    "party_2026",

                "yes_votes":
                    "yes_votes_2026",

                "no_votes":
                    "no_votes_2026",

                "directional_topic_votes":
                    "directional_topic_votes_2026",

                "yes_pct":
                    "yes_pct_2026",

                "no_pct":
                    "no_pct_2026",

                "voting_tendency":
                    "voting_tendency_2026",
            }
        )
    )

    yoy = left.merge(
        right,
        on=
            join_keys,
        how=
            "outer",
        indicator=
            True,
        validate=
            "one_to_one"
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

    # -----------------------------------------------------
    # CURRENT NAME / PARTY DISPLAY
    # -----------------------------------------------------

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
    # YES-PERCENT CHANGE
    # -----------------------------------------------------

    yoy[
        "yes_pct_change"
    ] = (
        yoy[
            "yes_pct_2026"
        ]
        -
        yoy[
            "yes_pct_2025"
        ]
    )

    # -----------------------------------------------------
    # BOTH YEARS HAVE ENOUGH DATA?
    # -----------------------------------------------------

    yoy[
        "comparable_tendency"
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
                "voting_tendency_2025"
            ]
            .isin(
                [
                    "YES",
                    "NO",
                    "MIXED",
                ]
            )
        )
        &
        (
            yoy[
                "voting_tendency_2026"
            ]
            .isin(
                [
                    "YES",
                    "NO",
                    "MIXED",
                ]
            )
        )
    )

    # -----------------------------------------------------
    # TRUE OBSERVED TENDENCY CHANGE
    #
    # Insufficient-data transitions are NOT counted.
    # -----------------------------------------------------

    yoy[
        "voting_tendency_changed"
    ] = (
        yoy[
            "comparable_tendency"
        ]
        &
        (
            yoy[
                "voting_tendency_2025"
            ]
            !=
            yoy[
                "voting_tendency_2026"
            ]
        )
    )

    # -----------------------------------------------------
    # DATA AVAILABILITY CHANGE
    #
    # Kept separately for QA / interpretation.
    # -----------------------------------------------------

    yoy[
        "data_availability_changed"
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
            (
                yoy[
                    "voting_tendency_2025"
                ]
                ==
                "INSUFFICIENT DATA"
            )
            ^
            (
                yoy[
                    "voting_tendency_2026"
                ]
                ==
                "INSUFFICIENT DATA"
            )
        )
    )

    return (
        yoy
        .sort_values(
            [
                "voting_tendency_changed",
                "comparable_tendency",
                "yes_pct_change",
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
# PRINT YEAR RESULTS
# =========================================================

def print_delegate_topic_results(
    year,
    tendency
):

    print(
        "\n" + "=" * 78
    )

    print(
        f"{year} DELEGATE × TOPIC "
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
        "\nExample classified rows:"
    )

    print(
        usable[
            [
                "member_id",
                "MBR_NAME",
                "party",
                "topic_name",
                "classification",
                "yes_votes",
                "no_votes",
                "directional_topic_votes",
                "yes_pct",
                "voting_tendency",
            ]
        ]
        .head(40)
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:7.2f}"
        )
    )


# =========================================================
# PRINT TOPIC ROSTER EXAMPLES
# =========================================================

def print_topic_roster_examples(
    year,
    roster
):

    print(
        "\n" + "=" * 78
    )

    print(
        f"{year} TOPIC YES / NO / MIXED ROSTER"
    )

    print(
        "=" * 78
    )

    topics = (
        roster[
            "topic_name"
        ]
        .dropna()
        .unique()
        .tolist()
    )

    if not topics:

        print(
            "\nNo topic data."
        )

        return

    for topic in topics[:5]:

        topic_rows = (
            roster[
                roster[
                    "topic_name"
                ]
                ==
                topic
            ]
            .copy()
        )

        print(
            f"\n--- {topic} ---"
        )

        print(
            topic_rows[
                [
                    "MBR_NAME",
                    "party",
                    "yes_votes",
                    "no_votes",
                    "directional_topic_votes",
                    "yes_pct",
                    "voting_tendency",
                ]
            ]
            .head(30)
            .to_string(
                index=False,
                float_format=
                    lambda x:
                        f"{x:7.2f}"
            )
        )


# =========================================================
# PRINT YOY RESULTS
# =========================================================

def print_voting_tendency_yoy(
    tendency_yoy
):

    print(
        "\n" + "=" * 78
    )

    print(
        "2025 → 2026 TOPIC VOTING TENDENCY CHANGES"
    )

    print(
        "=" * 78
    )

    comparable = (
        tendency_yoy[
            tendency_yoy[
                "comparable_tendency"
            ]
        ]
        .copy()
    )

    changed = (
        tendency_yoy[
            tendency_yoy[
                "voting_tendency_changed"
            ]
        ]
        .copy()
    )

    availability_changed = (
        tendency_yoy[
            tendency_yoy[
                "data_availability_changed"
            ]
        ]
        .copy()
    )

    print(
        "\nComparable delegate-topic pairs:"
    )

    print(
        len(
            comparable
        )
    )

    print(
        "\nTrue observed tendency changes:"
    )

    print(
        len(
            changed
        )
    )

    print(
        "\nData-availability changes "
        "(not counted as behavioral changes):"
    )

    print(
        len(
            availability_changed
        )
    )

    if len(
        changed
    ) == 0:

        return

    print(
        "\nLargest increases in Yes-vote tendency "
        "among comparable changed pairs:"
    )

    print(
        changed[
            [
                "member_id",
                "MBR_NAME",
                "party",
                "topic_name",
                "classification",
                "voting_tendency_2025",
                "voting_tendency_2026",
                "yes_pct_2025",
                "yes_pct_2026",
                "yes_pct_change",
                "directional_topic_votes_2025",
                "directional_topic_votes_2026",
            ]
        ]
        .sort_values(
            "yes_pct_change",
            ascending=False
        )
        .head(30)
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:7.2f}"
        )
    )

    print(
        "\nLargest decreases in Yes-vote tendency "
        "among comparable changed pairs:"
    )

    print(
        changed[
            [
                "member_id",
                "MBR_NAME",
                "party",
                "topic_name",
                "classification",
                "voting_tendency_2025",
                "voting_tendency_2026",
                "yes_pct_2025",
                "yes_pct_2026",
                "yes_pct_change",
                "directional_topic_votes_2025",
                "directional_topic_votes_2026",
            ]
        ]
        .sort_values(
            "yes_pct_change",
            ascending=True
        )
        .head(30)
        .to_string(
            index=False,
            float_format=
                lambda x:
                    f"{x:7.2f}"
        )
    )


# =========================================================
# SAVE YEAR OUTPUTS
# =========================================================

def save_year_outputs(
    year,
    tendency,
    roster,
    topic_summary,
    party_topic_summary
):

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    outputs = {

        "delegate_topic_voting_tendency":
            (
                PROCESSED_ROOT
                / f"delegate_topic_voting_tendency_{year}.csv"
            ),

        "topic_yes_no_mixed":
            (
                PROCESSED_ROOT
                / f"topic_yes_no_mixed_{year}.csv"
            ),

        "topic_voting_tendency_summary":
            (
                PROCESSED_ROOT
                / f"topic_voting_tendency_summary_{year}.csv"
            ),

        "party_topic_voting_tendency_summary":
            (
                PROCESSED_ROOT
                / f"party_topic_voting_tendency_summary_{year}.csv"
            ),
    }

    tendency.to_csv(
        outputs[
            "delegate_topic_voting_tendency"
        ],
        index=False
    )

    roster.to_csv(
        outputs[
            "topic_yes_no_mixed"
        ],
        index=False
    )

    topic_summary.to_csv(
        outputs[
            "topic_voting_tendency_summary"
        ],
        index=False
    )

    party_topic_summary.to_csv(
        outputs[
            "party_topic_voting_tendency_summary"
        ],
        index=False
    )

    return outputs


# =========================================================
# SAVE YOY OUTPUT
# =========================================================

def save_yoy_output(
    tendency_yoy
):

    path = (
        PROCESSED_ROOT
        / (
            "delegate_topic_voting_tendency_"
            "yoy_2025_2026.csv"
        )
    )

    tendency_yoy.to_csv(
        path,
        index=False
    )

    return path


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print(
        "Topic voting tendency analysis started."
    )

    yearly_tendency = {}
    yearly_roster = {}
    yearly_topic_summary = {}
    yearly_party_topic_summary = {}

    all_output_paths = []

    # -----------------------------------------------------
    # BUILD EACH YEAR
    # -----------------------------------------------------

    for year in YEARS:

        print(
            f"\nLoading member-vote-topic data "
            f"for {year}..."
        )

        member_vote_topic = (
            load_member_vote_topic(
                year
            )
        )

        tendency = (
            build_delegate_topic_voting_tendency(
                member_vote_topic
            )
        )

        roster = (
            build_topic_voting_tendency_roster(
                tendency
            )
        )

        topic_summary = (
            build_topic_voting_tendency_summary(
                tendency
            )
        )

        party_topic_summary = (
            build_party_topic_voting_tendency_summary(
                tendency
            )
        )

        yearly_tendency[
            year
        ] = tendency

        yearly_roster[
            year
        ] = roster

        yearly_topic_summary[
            year
        ] = topic_summary

        yearly_party_topic_summary[
            year
        ] = party_topic_summary

        print_delegate_topic_results(
            year,
            tendency
        )

        print_topic_roster_examples(
            year,
            roster
        )

        outputs = (
            save_year_outputs(
                year,
                tendency,
                roster,
                topic_summary,
                party_topic_summary
            )
        )

        all_output_paths.extend(
            outputs.values()
        )

    # -----------------------------------------------------
    # YEAR-OVER-YEAR
    # -----------------------------------------------------

    tendency_yoy = (
        build_voting_tendency_yoy(
            yearly_tendency[
                2025
            ],
            yearly_tendency[
                2026
            ]
        )
    )

    print_voting_tendency_yoy(
        tendency_yoy
    )

    yoy_path = (
        save_yoy_output(
            tendency_yoy
        )
    )

    all_output_paths.append(
        yoy_path
    )

    # -----------------------------------------------------
    # FINAL STATUS
    # -----------------------------------------------------

    print(
        "\n" + "=" * 78
    )

    print(
        "FILES SAVED"
    )

    print(
        "=" * 78
    )

    for path in all_output_paths:

        print(
            path
        )

    print(
        "\nFinished."
    )