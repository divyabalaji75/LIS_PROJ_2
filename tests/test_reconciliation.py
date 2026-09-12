"""
Cross-output reconciliation tests.

These tests are intentionally different from unit tests.

A unit test asks whether one function behaves correctly.

A reconciliation test asks whether separate production outputs agree
with each other.

This file therefore focuses on relationships between canonical outputs
rather than repeating every lower-level rule already tested elsewhere.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lis_common import configured_test_years


YEARS = configured_test_years()

ROOT = Path(
    "data/processed"
)


# =========================================================
# HELPERS
# =========================================================

def load(
    name,
    year,
):

    path = (
        ROOT
        /
        f"{name}_{year}.csv"
    )

    assert path.exists(), (
        f"Missing required processed file: {path}"
    )

    return pd.read_csv(
        path,
        low_memory=False,
    )


def normalized_strings(series):

    return (
        series
        .fillna("")
        .astype(str)
        .str.strip()
    )


def normalized_upper(series):

    return (
        normalized_strings(
            series
        )
        .str.upper()
    )


def boolean_series(series):

    return (
        normalized_strings(
            series
        )
        .str.lower()
        .isin(
            [
                "true",
                "1",
            ]
        )
    )


# =========================================================
# 1. VOTE FLAGS OBEY THE DEFINITIONS
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_vote_flags_obey_directional_and_true_cross_party_definitions(
    year,
):

    votes = load(
        "vote_fact",
        year,
    )

    directional = (
        normalized_upper(
            votes[
                "vote"
            ]
        )
        .isin(
            [
                "Y",
                "N",
            ]
        )
    )

    nondirectional = (
        ~directional
    )

    broke = boolean_series(
        votes[
            "broke_with_party"
        ]
    )

    crossed = boolean_series(
        votes[
            "cross_party"
        ]
    )

    assert not broke[
        nondirectional
    ].any()

    assert not crossed[
        nondirectional
    ].any()

    assert broke[
        crossed
    ].all()

    assert (
        normalized_upper(
            votes.loc[
                crossed,
                "vote",
            ]
        )
        ==
        normalized_upper(
            votes.loc[
                crossed,
                "other_party_position",
            ]
        )
    ).all()

    assert (
        normalized_upper(
            votes.loc[
                crossed,
                "vote",
            ]
        )
        !=
        normalized_upper(
            votes.loc[
                crossed,
                "own_party_position",
            ]
        )
    ).all()


# =========================================================
# 2. DELEGATE BEHAVIOR RECONCILES TO HOUSE VOTE FACT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_delegate_behavior_reconciles_to_house_vote_fact(
    year,
):

    votes = load(
        "vote_fact",
        year,
    )

    summary = load(
        "delegate_behavior",
        year,
    )

    house = votes[
        normalized_upper(
            votes[
                "MBR_HOU"
            ]
        )
        .eq("H")
    ].copy()

    house[
        "is_directional"
    ] = (
        normalized_upper(
            house[
                "vote"
            ]
        )
        .isin(
            [
                "Y",
                "N",
            ]
        )
    )

    house[
        "party_break_bool"
    ] = boolean_series(
        house[
            "broke_with_party"
        ]
    )

    house[
        "cross_party_bool"
    ] = boolean_series(
        house[
            "cross_party"
        ]
    )

    expected = (
        house
        .groupby(
            "member_id"
        )
        .agg(
            directional_votes=(
                "is_directional",
                "sum",
            ),

            party_breaks=(
                "party_break_bool",
                "sum",
            ),

            cross_party_votes=(
                "cross_party_bool",
                "sum",
            ),
        )
    )

    actual = (
        summary
        .set_index(
            "member_id"
        )
    )

    assert (
        set(actual.index)
        ==
        set(expected.index)
    )

    for column in (
        expected.columns
    ):

        pd.testing.assert_series_equal(
            pd.to_numeric(
                actual[
                    column
                ]
            )
            .sort_index(),

            expected[
                column
            ]
            .sort_index(),

            check_names=False,
        )


# =========================================================
# 3. BILL CLASSIFICATION PARTITION RECONCILES
#
# Every bill must belong to exactly one provenance tier.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_classification_partition_and_coverage_reconcile(
    year,
):

    bills = load(
        "bill_lookup",
        year,
    )

    topics = load(
        "bill_topic_lookup",
        year,
    )

    coverage = load(
        "topic_coverage",
        year,
    )

    partition = (
        topics[
            [
                "Bill_id",
                "classification",
            ]
        ]
        .drop_duplicates()
    )

    assert (
        set(
            partition[
                "Bill_id"
            ]
        )
        ==
        set(
            bills[
                "Bill_id"
            ]
        )
    )

    assert (
        partition
        .groupby(
            "Bill_id"
        )[
            "classification"
        ]
        .nunique()
        .eq(1)
        .all()
    )

    expected_counts = (
        partition
        .groupby(
            "classification"
        )[
            "Bill_id"
        ]
        .nunique()
        .sort_index()
    )

    reported_counts = (
        coverage
        .set_index(
            "classification"
        )[
            "bill_count"
        ]
        .astype(int)
        .sort_index()
    )

    pd.testing.assert_series_equal(
        expected_counts,
        reported_counts,
        check_names=False,
    )


# =========================================================
# 4. MEMBER-VOTE-TOPIC HAS CANONICAL GRAIN
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_member_vote_topic_has_canonical_grain_and_vote_backing(
    year,
):

    member_topics = load(
        "member_vote_topic",
        year,
    )

    votes = load(
        "vote_fact",
        year,
    )

    grain = [
        "year",
        "vote_id",
        "member_id",
        "topic_name",
    ]

    assert not (
        member_topics
        .duplicated(
            grain
        )
        .any()
    )

    assert (
        "topic_provenance"
        in member_topics.columns
    )

    assert (
        "classification"
        not in member_topics.columns
    )

    checked = (
        member_topics.merge(
            votes[
                [
                    "year",
                    "vote_id",
                    "member_id",
                    "vote",
                ]
            ],
            on=[
                "year",
                "vote_id",
                "member_id",
            ],
            how="left",
            validate="many_to_one",
            suffixes=(
                "_topic",
                "_fact",
            ),
            indicator=True,
        )
    )

    assert (
        checked[
            "_merge"
        ]
        .eq("both")
        .all()
    )

    assert (
        normalized_upper(
            checked[
                "vote_topic"
            ]
        )
        ==
        normalized_upper(
            checked[
                "vote_fact"
            ]
        )
    ).all()

    assert (
        normalized_strings(
            member_topics[
                "topic_provenance"
            ]
        )
        .ne("")
        .all()
    )


# =========================================================
# 5. MEMBER-VOTE-TOPIC TOPICS MUST BE RECONSTRUCTIBLE
#
# THIS IS THE IMPORTANT NEW CHECK.
#
# A topic attached to a recorded vote must be traceable
# through:
#
#     member_vote_topic.vote_id
#
#         ->
#
#     vote_bill_bridge.Bill_id
#
#         ->
#
#     bill_topic_lookup.topic_name
#
#
# Example:
#
# If member_vote_topic says:
#
#     vote V100 -> Education
#
# there must be at least one bill attached to V100 whose
# bill_topic_lookup contains Education.
#
# This protects against downstream topic rows being created
# without bill-level topic evidence.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_member_vote_topics_reconstruct_from_vote_bill_topic_relationships(
    year,
):

    member_topics = load(
        "member_vote_topic",
        year,
    )

    bridge = load(
        "vote_bill_bridge",
        year,
    )

    bill_topics = load(
        "bill_topic_lookup",
        year,
    )

    expected_vote_topics = (
        bridge[
            [
                "vote_id",
                "Bill_id",
            ]
        ]
        .drop_duplicates()
        .merge(
            bill_topics[
                [
                    "Bill_id",
                    "topic_name",
                ]
            ]
            .drop_duplicates(),
            on="Bill_id",
            how="inner",
            validate="many_to_many",
        )[
            [
                "vote_id",
                "topic_name",
            ]
        ]
        .drop_duplicates()
    )

    expected_keys = set(
        zip(
            normalized_strings(
                expected_vote_topics[
                    "vote_id"
                ]
            ),

            normalized_strings(
                expected_vote_topics[
                    "topic_name"
                ]
            ),
        )
    )

    actual_keys = set(
        zip(
            normalized_strings(
                member_topics[
                    "vote_id"
                ]
            ),

            normalized_strings(
                member_topics[
                    "topic_name"
                ]
            ),
        )
    )

    unexpected = (
        actual_keys
        -
        expected_keys
    )

    assert not unexpected, (
        f"{year}: member_vote_topic contains vote/topic "
        "relationships that cannot be reconstructed through "
        "vote_bill_bridge + bill_topic_lookup. "
        f"Examples: {list(unexpected)[:20]}"
    )


# =========================================================
# 6. TOPIC PROVENANCE MUST ALSO BE RECONSTRUCTIBLE
#
# topic_provenance may combine several bill-level
# classification labels for one vote/topic.
#
# Every stored provenance label must actually occur among
# the bills contributing that vote/topic.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_member_vote_topic_provenance_reconstructs_from_bill_classifications(
    year,
):

    member_topics = load(
        "member_vote_topic",
        year,
    )

    bridge = load(
        "vote_bill_bridge",
        year,
    )

    bill_topics = load(
        "bill_topic_lookup",
        year,
    )

    evidence = (
        bridge[
            [
                "vote_id",
                "Bill_id",
            ]
        ]
        .drop_duplicates()
        .merge(
            bill_topics[
                [
                    "Bill_id",
                    "topic_name",
                    "classification",
                ]
            ],
            on="Bill_id",
            how="inner",
            validate="many_to_many",
        )
    )

    provenance_lookup = {}

    for (
        vote_id,
        topic_name,
    ), group in evidence.groupby(
        [
            "vote_id",
            "topic_name",
        ]
    ):

        provenance_lookup[
            (
                str(vote_id).strip(),
                str(topic_name).strip(),
            )
        ] = {
            str(value).strip()
            for value
            in group[
                "classification"
            ]
            if str(value).strip()
        }

    bad = []

    for row in (
        member_topics[
            [
                "vote_id",
                "topic_name",
                "topic_provenance",
            ]
        ]
        .drop_duplicates()
        .itertuples(
            index=False
        )
    ):

        key = (
            str(
                row.vote_id
            ).strip(),

            str(
                row.topic_name
            ).strip(),
        )

        actual_provenance = {
            part.strip()
            for part
            in str(
                row.topic_provenance
            ).split("|")
            if part.strip()
        }

        expected_provenance = (
            provenance_lookup
            .get(
                key,
                set(),
            )
        )

        if (
            not actual_provenance
            <=
            expected_provenance
        ):

            bad.append(
                {
                    "vote_id":
                        key[0],

                    "topic_name":
                        key[1],

                    "actual":
                        actual_provenance,

                    "expected":
                        expected_provenance,
                }
            )

    assert not bad, (
        f"{year}: topic_provenance contains labels not backed "
        "by contributing bill-topic rows. "
        f"Examples: {bad[:10]}"
    )


# =========================================================
# 7. DELEGATE-TOPIC SUMMARY RECONCILES TO EVENT DATA
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_delegate_topic_summary_reconciles_to_member_topic_events(
    year,
):

    member_topics = load(
        "member_vote_topic",
        year,
    )

    delegates = load(
        "delegate_topic_behavior",
        year,
    )

    member_topics[
        "party_break_bool"
    ] = boolean_series(
        member_topics[
            "broke_with_party"
        ]
    )

    member_topics[
        "cross_party_bool"
    ] = boolean_series(
        member_topics[
            "cross_party"
        ]
    )

    expected = (
        member_topics
        .groupby(
            [
                "member_id",
                "topic_name",
            ]
        )
        .agg(
            topic_vote_events=(
                "vote_id",
                "nunique",
            ),

            party_break_events=(
                "party_break_bool",
                "sum",
            ),

            cross_party_events=(
                "cross_party_bool",
                "sum",
            ),
        )
    )

    actual = (
        delegates
        .set_index(
            [
                "member_id",
                "topic_name",
            ]
        )
    )

    assert not (
        delegates
        .duplicated(
            [
                "member_id",
                "topic_name",
            ]
        )
        .any()
    )

    assert (
        set(actual.index)
        ==
        set(expected.index)
    )

    for column in (
        expected.columns
    ):

        pd.testing.assert_series_equal(
            pd.to_numeric(
                actual[
                    column
                ]
            )
            .sort_index(),

            expected[
                column
            ]
            .sort_index(),

            check_names=False,
        )


# =========================================================
# 8. DELEGATE-TOPIC COUNTS ARE MATHEMATICALLY POSSIBLE
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_delegate_topic_event_counts_are_possible(
    year,
):

    delegates = load(
        "delegate_topic_behavior",
        year,
    )

    total = pd.to_numeric(
        delegates[
            "topic_vote_events"
        ]
    )

    eligible = pd.to_numeric(
        delegates[
            "eligible_topic_events"
        ]
    )

    crossed = pd.to_numeric(
        delegates[
            "cross_party_events"
        ]
    )

    assert (
        eligible
        <=
        total
    ).all()

    assert (
        crossed
        <=
        eligible
    ).all()


# =========================================================
# 9. TOPIC VOTING TENDENCY RECONCILES
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_topic_tendency_counts_percentages_and_labels_reconcile(
    year,
):

    tendency = load(
        "delegate_topic_voting_tendency",
        year,
    )

    directional = pd.to_numeric(
        tendency[
            "directional_topic_votes"
        ]
    )

    yes = pd.to_numeric(
        tendency[
            "yes_votes"
        ]
    )

    no = pd.to_numeric(
        tendency[
            "no_votes"
        ]
    )

    assert (
        yes
        +
        no
    ).eq(
        directional
    ).all()

    mask = (
        directional
        >
        0
    )

    assert np.allclose(
        pd.to_numeric(
            tendency.loc[
                mask,
                "yes_pct",
            ]
        ),
        yes[
            mask
        ]
        /
        directional[
            mask
        ]
        *
        100,
    )

    assert np.allclose(
        pd.to_numeric(
            tendency.loc[
                mask,
                "no_pct",
            ]
        ),
        no[
            mask
        ]
        /
        directional[
            mask
        ]
        *
        100,
    )

    expected = pd.Series(
        "MIXED",
        index=tendency.index,
        dtype="object",
    )

    expected.loc[
        directional
        <
        10
    ] = (
        "INSUFFICIENT DATA"
    )

    valid = (
        directional
        >=
        10
    )

    yes_rate = (
        yes
        /
        directional
    )

    expected.loc[
        valid
        &
        yes_rate.ge(
            0.65
        )
    ] = (
        "YES"
    )

    expected.loc[
        valid
        &
        yes_rate.le(
            0.35
        )
    ] = (
        "NO"
    )

    assert (
        normalized_strings(
            tendency[
                "voting_tendency"
            ]
        )
        ==
        expected
    ).all()


# =========================================================
# 10. CORE IDENTIFIERS REMAIN POPULATED
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS,
)
def test_member_and_party_keys_are_populated_across_analysis_outputs(
    year,
):

    for name in (
        "vote_fact",
        "member_vote_topic",
        "delegate_behavior",
        "delegate_topic_behavior",
        "delegate_topic_voting_tendency",
    ):

        frame = load(
            name,
            year,
        )

        assert (
            normalized_strings(
                frame[
                    "member_id"
                ]
            )
            .ne("")
            .all()
        ), name

        assert (
            normalized_strings(
                frame[
                    "party"
                ]
            )
            .ne("")
            .all()
        ), name