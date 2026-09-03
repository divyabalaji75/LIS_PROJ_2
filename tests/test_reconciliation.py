from pathlib import Path

import pandas as pd
import pytest


# =========================================================
# CONFIG
# =========================================================

PROCESSED_ROOT = Path("data/processed")

YEARS = [
    2025,
    2026,
]

DIRECTIONAL_VOTES = {
    "Y",
    "N",
}

NON_DIRECTIONAL_VOTES = {
    "X",
    "A",
    "P",
}

ALLOWED_CLASSIFICATIONS = {
    "Official LIS subject",
    "Derived from LIS bill summary",
    "Derived from LIS bill description",
    "Unclassified",
}

VALID_TENDENCIES = {
    "YES",
    "NO",
    "MIXED",
    "INSUFFICIENT DATA",
}


# =========================================================
# HELPERS
# =========================================================

def load_processed_file(filename):

    path = (
        PROCESSED_ROOT
        / filename
    )

    if not path.exists():

        pytest.fail(
            f"Missing required processed file: {path}"
        )

    return pd.read_csv(
        path,
        dtype=str
    )


def normalize_text(series):

    return (
        series
        .fillna("")
        .astype(str)
        .str.strip()
    )


def normalize_upper(series):

    return (
        normalize_text(series)
        .str.upper()
    )


def to_numeric(series):

    return pd.to_numeric(
        series,
        errors="coerce"
    )


def load_vote_fact(year):

    return load_processed_file(
        f"vote_fact_{year}.csv"
    )


def load_delegate_behavior(year):

    return load_processed_file(
        f"delegate_behavior_{year}.csv"
    )


def load_bill_lookup(year):

    return load_processed_file(
        f"bill_lookup_{year}.csv"
    )


def load_topic_lookup(year):

    return load_processed_file(
        f"bill_topic_lookup_{year}.csv"
    )


def load_official_subjects(year):

    return load_processed_file(
        f"official_lis_subjects_{year}.csv"
    )


def load_derived_topics(year):

    return load_processed_file(
        f"derived_from_lis_bill_description_{year}.csv"
    )


def load_summary_derived_topics(year):

    return load_processed_file(
        f"derived_from_lis_bill_summary_{year}.csv"
    )


def load_unclassified(year):

    return load_processed_file(
        f"unclassified_bills_{year}.csv"
    )


def load_member_vote_topic(year):

    return load_processed_file(
        f"member_vote_topic_{year}.csv"
    )


def load_delegate_topic_behavior(year):

    return load_processed_file(
        f"delegate_topic_behavior_{year}.csv"
    )


def load_topic_voting_tendency(year):

    return load_processed_file(
        f"delegate_topic_voting_tendency_{year}.csv"
    )


# =========================================================
# TEST 1
# ALL OBSERVED VOTE CODES RECONCILE TO VOTE FACT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_code_counts_reconcile_to_vote_fact(year):

    df = load_vote_fact(year)

    vote = normalize_upper(
        df["vote"]
    )

    counted = (
        vote.isin(
            DIRECTIONAL_VOTES
            |
            NON_DIRECTIONAL_VOTES
        )
        .sum()
    )

    assert counted == len(df), (
        f"{year}: known vote-code rows "
        f"do not reconcile to total vote_fact rows"
    )


# =========================================================
# TEST 2
# DIRECTIONAL VOTE COUNT = Y + N
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_directional_vote_count_reconciles(year):

    df = load_vote_fact(year)

    vote = normalize_upper(
        df["vote"]
    )

    directional = (
        vote.isin(
            DIRECTIONAL_VOTES
        )
        .sum()
    )

    yes_count = (
        vote.eq("Y")
        .sum()
    )

    no_count = (
        vote.eq("N")
        .sum()
    )

    assert directional == (
        yes_count
        +
        no_count
    ), (
        f"{year}: Y + N does not equal "
        f"directional vote count"
    )


# =========================================================
# TEST 3
# NON-DIRECTIONAL VOTES CAN NEVER BE PARTY BREAKS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_nondirectional_votes_not_party_breaks(year):

    df = load_vote_fact(year).copy()

    required = {
        "vote",
        "broke_with_party",
    }

    missing = (
        required
        - set(df.columns)
    )

    assert not missing, (
        f"{year}: vote_fact missing "
        f"party behavior columns: {missing}"
    )

    df["vote"] = normalize_upper(
        df["vote"]
    )

    nondirectional = df[
        ~df[
            "vote"
        ]
        .isin(
            DIRECTIONAL_VOTES
        )
    ]

    bad = nondirectional[
        normalize_text(
            nondirectional[
                "broke_with_party"
            ]
        )
        .str.lower()
        .eq("true")
    ]

    assert len(bad) == 0, (
        f"{year}: {len(bad)} non-directional "
        f"votes were marked as party breaks"
    )


# =========================================================
# TEST 4
# NON-DIRECTIONAL VOTES CAN NEVER BE CROSS-PARTY
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_nondirectional_votes_not_cross_party(year):

    df = load_vote_fact(year).copy()

    required = {
        "vote",
        "cross_party",
    }

    missing = (
        required
        - set(df.columns)
    )

    assert not missing, (
        f"{year}: vote_fact missing "
        f"cross-party columns: {missing}"
    )

    df["vote"] = normalize_upper(
        df["vote"]
    )

    nondirectional = df[
        ~df[
            "vote"
        ]
        .isin(
            DIRECTIONAL_VOTES
        )
    ]

    bad = nondirectional[
        normalize_text(
            nondirectional[
                "cross_party"
            ]
        )
        .str.lower()
        .eq("true")
    ]

    assert len(bad) == 0, (
        f"{year}: {len(bad)} non-directional "
        f"votes were marked cross-party"
    )


# =========================================================
# TEST 5
# EVERY CROSS-PARTY VOTE IS ALSO A PARTY BREAK
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_cross_party_implies_party_break(year):

    df = load_vote_fact(year)

    cross_party = (
        normalize_text(
            df[
                "cross_party"
            ]
        )
        .str.lower()
        .eq("true")
    )

    broke = (
        normalize_text(
            df[
                "broke_with_party"
            ]
        )
        .str.lower()
        .eq("true")
    )

    invalid = df[
        cross_party
        &
        ~broke
    ]

    assert len(invalid) == 0, (
        f"{year}: {len(invalid)} "
        f"cross-party rows are not party breaks"
    )


# =========================================================
# TEST 6
# DELEGATE BEHAVIOR IS HOUSE-ONLY
#
# delegate_behavior intentionally summarizes
# House delegates, not Senate members.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_delegate_behavior_contains_house_members_only(year):

    delegate = load_delegate_behavior(year)

    member_ids = normalize_upper(
        delegate[
            "member_id"
        ]
    )

    invalid = delegate[
        ~member_ids.str.startswith("H")
    ]

    assert len(invalid) == 0, (
        f"{year}: delegate_behavior contains "
        f"non-House member IDs"
    )


# =========================================================
# TEST 7
# HOUSE DELEGATE PARTY-BREAK TOTAL
# RECONCILES TO HOUSE ROWS IN VOTE FACT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_delegate_party_break_totals_reconcile(year):

    vote_fact = load_vote_fact(year).copy()
    delegate = load_delegate_behavior(year)

    vote_fact["MBR_HOU"] = normalize_upper(
        vote_fact[
            "MBR_HOU"
        ]
    )

    house_vote_fact = vote_fact[
        vote_fact[
            "MBR_HOU"
        ]
        ==
        "H"
    ].copy()

    vote_fact_breaks = (
        normalize_text(
            house_vote_fact[
                "broke_with_party"
            ]
        )
        .str.lower()
        .eq("true")
        .sum()
    )

    delegate_breaks = (
        to_numeric(
            delegate[
                "party_breaks"
            ]
        )
        .fillna(0)
        .sum()
    )

    assert delegate_breaks == vote_fact_breaks, (
        f"{year}: House delegate_behavior "
        f"party-break total ({delegate_breaks}) "
        f"does not match House vote_fact "
        f"({vote_fact_breaks})"
    )


# =========================================================
# TEST 8
# HOUSE DELEGATE CROSS-PARTY TOTAL
# RECONCILES TO HOUSE ROWS IN VOTE FACT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_delegate_cross_party_totals_reconcile(year):

    vote_fact = load_vote_fact(year).copy()
    delegate = load_delegate_behavior(year)

    vote_fact["MBR_HOU"] = normalize_upper(
        vote_fact[
            "MBR_HOU"
        ]
    )

    house_vote_fact = vote_fact[
        vote_fact[
            "MBR_HOU"
        ]
        ==
        "H"
    ].copy()

    vote_fact_cross = (
        normalize_text(
            house_vote_fact[
                "cross_party"
            ]
        )
        .str.lower()
        .eq("true")
        .sum()
    )

    delegate_cross = (
        to_numeric(
            delegate[
                "cross_party_votes"
            ]
        )
        .fillna(0)
        .sum()
    )

    assert delegate_cross == vote_fact_cross, (
        f"{year}: House delegate_behavior "
        f"cross-party total ({delegate_cross}) "
        f"does not match House vote_fact "
        f"({vote_fact_cross})"
    )


# =========================================================
# TEST 9
# HOUSE DELEGATE DIRECTIONAL VOTE TOTAL
# RECONCILES TO HOUSE ROWS IN VOTE FACT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_delegate_directional_totals_reconcile(year):

    vote_fact = load_vote_fact(year).copy()
    delegate = load_delegate_behavior(year)

    vote_fact["MBR_HOU"] = normalize_upper(
        vote_fact[
            "MBR_HOU"
        ]
    )

    house_vote_fact = vote_fact[
        vote_fact[
            "MBR_HOU"
        ]
        ==
        "H"
    ].copy()

    vote_fact_directional = (
        normalize_upper(
            house_vote_fact[
                "vote"
            ]
        )
        .isin(
            DIRECTIONAL_VOTES
        )
        .sum()
    )

    delegate_directional = (
        to_numeric(
            delegate[
                "directional_votes"
            ]
        )
        .fillna(0)
        .sum()
    )

    assert delegate_directional == vote_fact_directional, (
        f"{year}: House delegate directional total "
        f"({delegate_directional}) does not match "
        f"House vote_fact "
        f"({vote_fact_directional})"
    )


# =========================================================
# TEST 10
# BILL CLASSIFICATION PARTITION
# RECONCILES TO BILL LOOKUP
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_bill_classification_partition_reconciles(year):

    bills = load_bill_lookup(year)

    official = load_official_subjects(year)
    summary_derived = load_summary_derived_topics(year)
    derived = load_derived_topics(year)
    unclassified = load_unclassified(year)

    bill_ids = set(
        normalize_upper(
            bills[
                "Bill_id"
            ]
        )
        .unique()
    )

    official_ids = set(
        normalize_upper(
            official[
                "Bill_id"
            ]
        )
        .unique()
    )

    derived_ids = set(
        normalize_upper(
            derived[
                "Bill_id"
            ]
        )
        .unique()
    )

    summary_derived_ids = set(
        normalize_upper(
            summary_derived["Bill_id"]
        )
        .unique()
    )

    unclassified_ids = set(
        normalize_upper(
            unclassified[
                "Bill_id"
            ]
        )
        .unique()
    )

    combined = (
        official_ids
        |
        summary_derived_ids
        |
        derived_ids
        |
        unclassified_ids
    )

    assert combined == bill_ids, (
        f"{year}: classified bill partition "
        f"does not equal bill_lookup bill set"
    )


# =========================================================
# TEST 11
# NO BILL BELONGS TO MULTIPLE PROVENANCE BUCKETS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_bill_provenance_buckets_do_not_overlap(year):

    official = load_official_subjects(year)
    summary_derived = load_summary_derived_topics(year)
    derived = load_derived_topics(year)
    unclassified = load_unclassified(year)

    official_ids = set(
        normalize_upper(
            official[
                "Bill_id"
            ]
        )
        .unique()
    )

    derived_ids = set(
        normalize_upper(
            derived[
                "Bill_id"
            ]
        )
        .unique()
    )

    summary_derived_ids = set(
        normalize_upper(
            summary_derived["Bill_id"]
        )
        .unique()
    )

    unclassified_ids = set(
        normalize_upper(
            unclassified[
                "Bill_id"
            ]
        )
        .unique()
    )

    assert not (
        official_ids
        &
        summary_derived_ids
    )

    assert not (
        official_ids
        &
        derived_ids
    )

    assert not (
        official_ids
        &
        unclassified_ids
    )

    assert not (
        summary_derived_ids
        &
        derived_ids
    )

    assert not (
        summary_derived_ids
        &
        unclassified_ids
    )

    assert not (
        derived_ids
        &
        unclassified_ids
    )


# =========================================================
# TEST 12
# TOPIC LOOKUP ONLY USES ALLOWED CLASSIFICATIONS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_topic_lookup_classification_values_reconcile(year):

    topics = load_topic_lookup(year)

    actual = set(
        normalize_text(
            topics[
                "classification"
            ]
        )
        .unique()
    )

    invalid = (
        actual
        - ALLOWED_CLASSIFICATIONS
    )

    assert not invalid, (
        f"{year}: unexpected classification "
        f"values: {invalid}"
    )


# =========================================================
# TEST 13
# MEMBER-VOTE-TOPIC HAS UNIQUE ANALYTICAL GRAIN
#
# year + vote_id + member_id
# + topic_name + classification
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_member_vote_topic_grain_unique(year):

    df = load_member_vote_topic(year)

    duplicates = df[
        df.duplicated(
            subset=[
                "year",
                "vote_id",
                "member_id",
                "topic_name",
                "classification",
            ],
            keep=False
        )
    ]

    assert len(duplicates) == 0, (
        f"{year}: found {len(duplicates)} "
        f"duplicate member-vote-topic rows"
    )


# =========================================================
# TEST 14
# MEMBER-VOTE-TOPIC MEMBER/VOTE PAIRS
# MUST COME FROM VOTE FACT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_member_vote_topic_rows_backed_by_vote_fact(year):

    vote_fact = load_vote_fact(year)

    topic_votes = load_member_vote_topic(year)

    vote_pairs = set(
        zip(
            normalize_text(
                vote_fact[
                    "vote_id"
                ]
            ),
            normalize_upper(
                vote_fact[
                    "member_id"
                ]
            ),
        )
    )

    topic_pairs = set(
        zip(
            normalize_text(
                topic_votes[
                    "vote_id"
                ]
            ),
            normalize_upper(
                topic_votes[
                    "member_id"
                ]
            ),
        )
    )

    unknown = (
        topic_pairs
        - vote_pairs
    )

    assert not unknown, (
        f"{year}: member_vote_topic contains "
        f"member/vote identities not in vote_fact"
    )


# =========================================================
# TEST 15
# MEMBER-VOTE-TOPIC VOTE VALUE AGREES WITH VOTE FACT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_member_vote_topic_vote_value_matches_vote_fact(year):

    vote_fact = load_vote_fact(year)[
        [
            "vote_id",
            "member_id",
            "vote",
        ]
    ].copy()

    topic_votes = load_member_vote_topic(year)[
        [
            "vote_id",
            "member_id",
            "vote",
        ]
    ].copy()

    vote_fact["member_id"] = normalize_upper(
        vote_fact[
            "member_id"
        ]
    )

    vote_fact["vote"] = normalize_upper(
        vote_fact[
            "vote"
        ]
    )

    topic_votes["member_id"] = normalize_upper(
        topic_votes[
            "member_id"
        ]
    )

    topic_votes["vote"] = normalize_upper(
        topic_votes[
            "vote"
        ]
    )

    check = (
        topic_votes
        .drop_duplicates()
        .merge(
            vote_fact.rename(
                columns={
                    "vote":
                        "vote_fact_vote"
                }
            ),
            on=[
                "vote_id",
                "member_id",
            ],
            how="left",
            validate="many_to_one"
        )
    )

    mismatch = check[
        check[
            "vote"
        ]
        !=
        check[
            "vote_fact_vote"
        ]
    ]

    assert len(mismatch) == 0, (
        f"{year}: {len(mismatch)} "
        f"member_vote_topic rows disagree "
        f"with vote_fact vote values"
    )


# =========================================================
# TEST 16
# DELEGATE TOPIC COUNTS ARE MATHEMATICALLY POSSIBLE
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_delegate_topic_counts_not_impossible(year):

    summary = load_delegate_topic_behavior(year)

    topic_vote_events = to_numeric(
        summary[
            "topic_vote_events"
        ]
    )

    eligible_topic_events = to_numeric(
        summary[
            "eligible_topic_events"
        ]
    )

    cross_party_events = to_numeric(
        summary[
            "cross_party_events"
        ]
    )

    assert (
        eligible_topic_events
        <=
        topic_vote_events
    ).all(), (
        f"{year}: eligible topic events exceed "
        f"total topic events"
    )

    assert (
        cross_party_events
        <=
        eligible_topic_events
    ).all(), (
        f"{year}: cross-party topic events exceed "
        f"eligible topic events"
    )


# =========================================================
# TEST 17
# TOPIC VOTING TENDENCY:
# YES + NO = DIRECTIONAL TOPIC VOTES
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_topic_tendency_directional_reconciliation(year):

    df = load_topic_voting_tendency(year)

    yes_votes = to_numeric(
        df[
            "yes_votes"
        ]
    )

    no_votes = to_numeric(
        df[
            "no_votes"
        ]
    )

    directional = to_numeric(
        df[
            "directional_topic_votes"
        ]
    )

    assert (
        yes_votes
        +
        no_votes
        ==
        directional
    ).all(), (
        f"{year}: yes_votes + no_votes does not "
        f"equal directional_topic_votes"
    )


# =========================================================
# TEST 18
# TOPIC VOTING TENDENCY:
# YES% + NO% = 100 WHEN DIRECTIONAL > 0
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_topic_tendency_percentages_reconcile(year):

    df = load_topic_voting_tendency(year)

    yes_pct = to_numeric(
        df[
            "yes_pct"
        ]
    )

    no_pct = to_numeric(
        df[
            "no_pct"
        ]
    )

    directional = to_numeric(
        df[
            "directional_topic_votes"
        ]
    )

    valid = (
        directional
        >
        0
    )

    totals = (
        yes_pct[
            valid
        ]
        +
        no_pct[
            valid
        ]
    )

    assert (
        totals
        .sub(100)
        .abs()
        <
        0.0001
    ).all(), (
        f"{year}: yes_pct + no_pct "
        f"does not reconcile to 100%"
    )


# =========================================================
# TEST 19
# TOPIC VOTING TENDENCY LABELS ARE VALID
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_topic_tendency_labels_valid(year):

    df = load_topic_voting_tendency(year)

    actual = set(
        normalize_text(
            df[
                "voting_tendency"
            ]
        )
        .unique()
    )

    invalid = (
        actual
        - VALID_TENDENCIES
    )

    assert not invalid, (
        f"{year}: invalid voting tendency "
        f"labels found: {invalid}"
    )


# =========================================================
# TEST 20
# INSUFFICIENT DATA REALLY HAS < 10 DIRECTIONAL VOTES
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_insufficient_data_threshold_consistent(year):

    df = load_topic_voting_tendency(year)

    directional = to_numeric(
        df[
            "directional_topic_votes"
        ]
    )

    tendency = normalize_text(
        df[
            "voting_tendency"
        ]
    )

    insufficient = (
        tendency
        ==
        "INSUFFICIENT DATA"
    )

    bad = df[
        insufficient
        &
        (
            directional
            >=
            10
        )
    ]

    assert len(bad) == 0, (
        f"{year}: {len(bad)} rows marked "
        f"INSUFFICIENT DATA despite having "
        f"10+ directional topic votes"
    )


# =========================================================
# TEST 21
# CLASSIFIED TENDENCIES HAVE >= 10 DIRECTIONAL VOTES
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_classified_tendencies_meet_minimum(year):

    df = load_topic_voting_tendency(year)

    directional = to_numeric(
        df[
            "directional_topic_votes"
        ]
    )

    tendency = normalize_text(
        df[
            "voting_tendency"
        ]
    )

    classified = tendency.isin(
        {
            "YES",
            "NO",
            "MIXED",
        }
    )

    bad = df[
        classified
        &
        (
            directional
            <
            10
        )
    ]

    assert len(bad) == 0, (
        f"{year}: {len(bad)} classified "
        f"topic tendencies have fewer "
        f"than 10 directional votes"
    )


# =========================================================
# TEST 22
# YES TENDENCY RESPECTS 65% THRESHOLD
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_yes_tendency_threshold_consistent(year):

    df = load_topic_voting_tendency(year)

    tendency = normalize_text(
        df[
            "voting_tendency"
        ]
    )

    yes_pct = to_numeric(
        df[
            "yes_pct"
        ]
    )

    bad = df[
        (
            tendency
            ==
            "YES"
        )
        &
        (
            yes_pct
            <
            65.0
        )
    ]

    assert len(bad) == 0, (
        f"{year}: YES tendencies found "
        f"below 65% Yes"
    )


# =========================================================
# TEST 23
# NO TENDENCY RESPECTS 35% THRESHOLD
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_no_tendency_threshold_consistent(year):

    df = load_topic_voting_tendency(year)

    tendency = normalize_text(
        df[
            "voting_tendency"
        ]
    )

    yes_pct = to_numeric(
        df[
            "yes_pct"
        ]
    )

    bad = df[
        (
            tendency
            ==
            "NO"
        )
        &
        (
            yes_pct
            >
            35.0
        )
    ]

    assert len(bad) == 0, (
        f"{year}: NO tendencies found "
        f"above 35% Yes"
    )


# =========================================================
# TEST 24
# MIXED TENDENCY IS STRICTLY BETWEEN 35% AND 65%
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_mixed_tendency_threshold_consistent(year):

    df = load_topic_voting_tendency(year)

    tendency = normalize_text(
        df[
            "voting_tendency"
        ]
    )

    yes_pct = to_numeric(
        df[
            "yes_pct"
        ]
    )

    bad = df[
        (
            tendency
            ==
            "MIXED"
        )
        &
        (
            (yes_pct <= 35.0)
            |
            (yes_pct >= 65.0)
        )
    ]

    assert len(bad) == 0, (
        f"{year}: MIXED tendencies found "
        f"outside 35%-65% interval"
    )


# =========================================================
# TEST 25
# TOPIC LOOKUP BILL IDS ARE BACKED BY BILL LOOKUP
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_topic_lookup_bill_ids_backed_by_bill_lookup(year):

    bills = load_bill_lookup(year)

    topics = load_topic_lookup(year)

    bill_ids = set(
        normalize_upper(
            bills[
                "Bill_id"
            ]
        )
        .unique()
    )

    topic_bill_ids = set(
        normalize_upper(
            topics[
                "Bill_id"
            ]
        )
        .unique()
    )

    unknown = (
        topic_bill_ids
        - bill_ids
    )

    assert not unknown, (
        f"{year}: topic lookup contains "
        f"Bill_id values absent from bill_lookup"
    )


# =========================================================
# TEST 26
# NO BLANK MEMBER IDS IN MAJOR ANALYTICAL OUTPUTS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_no_blank_member_ids_across_analysis_outputs(year):

    files = {
        "vote_fact":
            load_vote_fact(year),

        "delegate_behavior":
            load_delegate_behavior(year),

        "member_vote_topic":
            load_member_vote_topic(year),

        "delegate_topic_behavior":
            load_delegate_topic_behavior(year),

        "delegate_topic_voting_tendency":
            load_topic_voting_tendency(year),
    }

    for name, df in files.items():

        if (
            "member_id"
            not in
            df.columns
        ):
            pytest.fail(
                f"{year}: {name} missing member_id"
            )

        blank = (
            normalize_text(
                df[
                    "member_id"
                ]
            )
            .eq("")
            .sum()
        )

        assert blank == 0, (
            f"{year}: {name} contains "
            f"{blank} blank member_id rows"
        )


# =========================================================
# TEST 27
# NO BLANK PARTY VALUES IN MAJOR ANALYTICAL OUTPUTS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_no_blank_party_across_analysis_outputs(year):

    files = {
        "vote_fact":
            load_vote_fact(year),

        "delegate_behavior":
            load_delegate_behavior(year),

        "member_vote_topic":
            load_member_vote_topic(year),

        "delegate_topic_behavior":
            load_delegate_topic_behavior(year),

        "delegate_topic_voting_tendency":
            load_topic_voting_tendency(year),
    }

    for name, df in files.items():

        if (
            "party"
            not in
            df.columns
        ):
            pytest.fail(
                f"{year}: {name} missing party"
            )

        blank = (
            normalize_text(
                df[
                    "party"
                ]
            )
            .eq("")
            .sum()
        )

        assert blank == 0, (
            f"{year}: {name} contains "
            f"{blank} blank party rows"
        )
