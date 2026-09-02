from pathlib import Path
import pandas as pd


# =========================================================
# CONFIG
# =========================================================

PROCESSED_ROOT = Path("data/processed")

YEARS = [2025, 2026]

# Minimum number of directional Y/N votes required
# before assigning a stance.
MIN_TOPIC_DIRECTIONAL_VOTES = 10

# Stance thresholds
YES_THRESHOLD = 0.65
NO_THRESHOLD = 0.35

# Only these classifications are valid from the pipeline.
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


def load_member_vote_topic(year):

    path = MEMBER_TOPIC_FILES[year]

    require_file(path)

    df = pd.read_csv(
        path,
        dtype={
            "member_id": str,
            "MBR_NAME": str,
            "party": str,
            "vote": str,
            "topic_name": str,
            "classification": str,
        }
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

    df["vote"] = (
        df["vote"]
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

    invalid_classifications = (
        set(
            df[
                "classification"
            ]
            .dropna()
            .unique()
        )
        -
        ALLOWED_CLASSIFICATIONS
    )

    if invalid_classifications:

        raise ValueError(
            f"{year}: unexpected "
            f"classification values: "
            f"{invalid_classifications}"
        )

    return df


# =========================================================
# STANCE LABEL
#
# IMPORTANT:
#
# "YES" means a member tended to vote Y on bills/motions
# associated with this topic.
#
# It does NOT mean:
# "supports the topic"
# or
# "is politically in favor of the issue."
#
# Topics can contain bills with different policy directions.
# =========================================================

def assign_stance(
    directional_votes,
    yes_pct
):

    if (
        directional_votes
        <
        MIN_TOPIC_DIRECTIONAL_VOTES
    ):

        return "INSUFFICIENT DATA"

    if (
        yes_pct
        >=
        YES_THRESHOLD
    ):

        return "YES"

    if (
        yes_pct
        <=
        NO_THRESHOLD
    ):

        return "NO"

    return "MIXED"


# =========================================================
# BUILD DELEGATE × TOPIC STANCE
# =========================================================

def build_delegate_topic_stance(
    member_vote_topic
):

    # -----------------------------------------------------
    # REMOVE UNCLASSIFIED FROM POLICY STANCE ANALYSIS
    #
    # It stays in upstream pipeline outputs.
    # -----------------------------------------------------

    df = member_vote_topic[
        member_vote_topic[
            "classification"
        ]
        !=
        "Unclassified"
    ].copy()

    # -----------------------------------------------------
    # DIRECTIONAL VOTES ONLY
    #
    # X / A are not interpreted as Yes or No.
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

    # -----------------------------------------------------
    # AGGREGATE MEMBER × TOPIC
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
    # RATES
    # -----------------------------------------------------

    summary[
        "yes_pct"
    ] = 0.0

    summary[
        "no_pct"
    ] = 0.0

    valid = (
        summary[
            "directional_topic_votes"
        ]
        >
        0
    )

    summary.loc[
        valid,
        "yes_pct"
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
        "no_pct"
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
    # STANCE
    # -----------------------------------------------------

    summary[
        "stance"
    ] = summary.apply(
        lambda row:
            assign_stance(
                row[
                    "directional_topic_votes"
                ],
                row[
                    "yes_pct"
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
            "yes_pct"
        ]
        *
        100
    )

    summary[
        "no_pct"
    ] = (
        summary[
            "no_pct"
        ]
        *
        100
    )

    return (
        summary
        .sort_values(
            [
                "topic_name",
                "stance",
                "yes_pct",
            ],
            ascending=[
                True,
                True,
                False,
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# BUILD TOPIC ROSTER
#
# This answers:
#
# "Who are the YES / NO / MIXED people for each subject?"
# =========================================================

def build_topic_stance_roster(
    delegate_topic_stance
):

    roster = (
        delegate_topic_stance[
            [
                "year",
                "topic_name",
                "classification",
                "member_id",
                "MBR_NAME",
                "party",
                "yes_votes",
                "no_votes",
                "directional_topic_votes",
                "yes_pct",
                "no_pct",
                "stance",
            ]
        ]
        .copy()
    )

    return (
        roster
        .sort_values(
            [
                "topic_name",
                "stance",
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
# This shows how many YES / NO / MIXED delegates exist
# for each topic.
# =========================================================

def build_topic_stance_summary(
    delegate_topic_stance
):

    usable = (
        delegate_topic_stance[
            delegate_topic_stance[
                "stance"
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
                "stance",
            ]
        )
        .size()
        .reset_index(
            name=
                "delegates"
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
                "stance",

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

        if (
            column
            not in
            pivot.columns
        ):

            pivot[
                column
            ] = 0

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
    # SHARES
    # -----------------------------------------------------

    pivot[
        "yes_delegate_pct"
    ] = 0.0

    pivot[
        "no_delegate_pct"
    ] = 0.0

    pivot[
        "mixed_delegate_pct"
    ] = 0.0

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
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# BUILD PARTY × TOPIC STANCE SUMMARY
#
# This helps answer:
# "How do D / R delegates tend to vote within this topic?"
# =========================================================

def build_party_topic_stance_summary(
    delegate_topic_stance
):

    usable = (
        delegate_topic_stance[
            delegate_topic_stance[
                "stance"
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
                "stance",
            ]
        )
        .size()
        .reset_index(
            name=
                "delegates"
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
                "stance",

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

        if (
            column
            not in
            pivot.columns
        ):

            pivot[
                column
            ] = 0

    pivot = (
        pivot.rename(
            columns={
                "YES":
                    "yes_delegates",

                "NO":
                    "no_delegates",

                "MIXED":
                    "mixed_delegates",
            }
        )
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
                "party",
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# YEAR-OVER-YEAR STANCE COMPARISON
# =========================================================

def build_stance_yoy(
    stance_2025,
    stance_2026
):

    join_keys = [
        "member_id",
        "topic_name",
        "classification",
    ]

    left = (
        stance_2025[
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
                "stance",
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

                "stance":
                    "stance_2025",
            }
        )
    )

    right = (
        stance_2026[
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
                "stance",
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

                "stance":
                    "stance_2026",
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
    # YES-RATE CHANGE
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
    # STANCE CHANGE
    # -----------------------------------------------------

    yoy[
        "stance_changed"
    ] = (
        yoy[
            "topic_status"
        ]
        .eq(
            "Present both years"
        )
        &
        yoy[
            "stance_2025"
        ]
        .notna()
        &
        yoy[
            "stance_2026"
        ]
        .notna()
        &
        (
            yoy[
                "stance_2025"
            ]
            !=
            yoy[
                "stance_2026"
            ]
        )
    )

    return (
        yoy
        .sort_values(
            [
                "stance_changed",
                "yes_pct_change",
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
# PRINT DELEGATE STANCE EXAMPLES
# =========================================================

def print_delegate_topic_results(
    year,
    stance
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
        "\nStance counts:"
    )

    print(
        stance[
            "stance"
        ]
        .value_counts(
            dropna=False
        )
    )

    usable = (
        stance[
            stance[
                "stance"
            ]
            !=
            "INSUFFICIENT DATA"
        ]
        .copy()
    )

    print(
        "\nExample rows:"
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
                "stance",
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

    # Show first five topics in console.
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
                    "yes_pct",
                    "stance",
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
# PRINT YEAR-OVER-YEAR STANCE CHANGES
# =========================================================

def print_stance_yoy(
    stance_yoy
):

    print(
        "\n" + "=" * 78
    )

    print(
        "2025 → 2026 TOPIC STANCE CHANGES"
    )

    print(
        "=" * 78
    )

    changed = (
        stance_yoy[
            stance_yoy[
                "stance_changed"
            ]
        ]
        .copy()
    )

    print(
        "\nDelegate-topic pairs "
        "with changed stance:"
    )

    print(
        len(
            changed
        )
    )

    if len(
        changed
    ) == 0:

        return

    print(
        "\nLargest increases in "
        "Yes-vote tendency among "
        "changed classifications:"
    )

    print(
        changed[
            [
                "member_id",
                "MBR_NAME",
                "party",
                "topic_name",
                "classification",
                "stance_2025",
                "stance_2026",
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


# =========================================================
# SAVE OUTPUTS
# =========================================================

def save_year_outputs(
    year,
    stance,
    roster,
    topic_summary,
    party_topic_summary
):

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    outputs = {

        "delegate_topic_stance":
            PROCESSED_ROOT
            / f"delegate_topic_stance_{year}.csv",

        "topic_roster":
            PROCESSED_ROOT
            / f"topic_yes_no_mixed_{year}.csv",

        "topic_summary":
            PROCESSED_ROOT
            / f"topic_stance_summary_{year}.csv",

        "party_topic_summary":
            PROCESSED_ROOT
            / f"party_topic_stance_summary_{year}.csv",
    }

    stance.to_csv(
        outputs[
            "delegate_topic_stance"
        ],
        index=False
    )

    roster.to_csv(
        outputs[
            "topic_roster"
        ],
        index=False
    )

    topic_summary.to_csv(
        outputs[
            "topic_summary"
        ],
        index=False
    )

    party_topic_summary.to_csv(
        outputs[
            "party_topic_summary"
        ],
        index=False
    )

    return outputs


def save_yoy_output(
    stance_yoy
):

    path = (
        PROCESSED_ROOT
        / "delegate_topic_stance_yoy_2025_2026.csv"
    )

    stance_yoy.to_csv(
        path,
        index=False
    )

    return path


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print(
        "Topic stance analysis started."
    )

    yearly_stance = {}
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

        stance = (
            build_delegate_topic_stance(
                member_vote_topic
            )
        )

        roster = (
            build_topic_stance_roster(
                stance
            )
        )

        topic_summary = (
            build_topic_stance_summary(
                stance
            )
        )

        party_topic_summary = (
            build_party_topic_stance_summary(
                stance
            )
        )

        yearly_stance[
            year
        ] = stance

        yearly_roster[
            year
        ] = roster

        yearly_topic_summary[
            year
        ] = topic_summary

        yearly_party_topic_summary[
            year
        ] = (
            party_topic_summary
        )

        print_delegate_topic_results(
            year,
            stance
        )

        print_topic_roster_examples(
            year,
            roster
        )

        outputs = (
            save_year_outputs(
                year,
                stance,
                roster,
                topic_summary,
                party_topic_summary
            )
        )

        all_output_paths.extend(
            outputs.values()
        )

    # -----------------------------------------------------
    # YEAR-OVER-YEAR STANCE
    # -----------------------------------------------------

    stance_yoy = (
        build_stance_yoy(
            yearly_stance[
                2025
            ],
            yearly_stance[
                2026
            ]
        )
    )

    print_stance_yoy(
        stance_yoy
    )

    yoy_path = (
        save_yoy_output(
            stance_yoy
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

    for path in (
        all_output_paths
    ):

        print(
            path
        )

    print(
        "\nFinished."
    )