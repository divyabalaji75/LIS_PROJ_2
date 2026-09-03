from pathlib import Path
import csv

import pandas as pd
import pytest


# =========================================================
# CONFIG
# =========================================================

RAW_ROOT = Path("data/raw")
PROCESSED_ROOT = Path("data/processed")
REFERENCE_ROOT = Path("data/reference")

YEARS = [
    2025,
    2026,
]

SAMPLE_SIZE = 25
RANDOM_STATE = 42

ALLOWED_CLASSIFICATIONS = {
    "Official LIS subject",
    "Derived from LIS bill summary",
    "Derived from LIS bill description",
    "Unclassified",
}


# =========================================================
# GENERAL HELPERS
# =========================================================

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


def load_csv(path):

    if not path.exists():

        pytest.fail(
            f"Missing required file: {path}"
        )

    return pd.read_csv(
        path,
        dtype=str
    )


def load_processed(year, filename):

    return load_csv(
        PROCESSED_ROOT
        / f"{filename}_{year}.csv"
    )


def load_raw(year, filename):

    return load_csv(
        RAW_ROOT
        / str(year)
        / filename
    )


# =========================================================
# RAW LIS VOTE PARSER
#
# IMPORTANT:
#
# VOTE.CSV is not a normal rectangular CSV.
#
# First field:
#     vote_id
#
# Remaining fields repeat:
#     member_id, vote
#
# Example:
#
# 26110000,H0056,N,H0108,Y,H0124,N
#
# becomes:
#
# vote_id   member_id   vote
# 26110000  H0056       N
# 26110000  H0108       Y
# 26110000  H0124       N
#
# We parse the raw source independently here rather
# than importing the production parser.
#
# That is intentional.
# =========================================================

def parse_raw_lis_vote_file(year):

    path = (
        RAW_ROOT
        / str(year)
        / "VOTE.CSV"
    )

    if not path.exists():

        pytest.fail(
            f"Missing raw LIS vote file: {path}"
        )

    rows = []

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.reader(file)

        for raw_row in reader:

            # Metadata/header-like rows do not contain
            # a complete vote/member/vote structure.
            if len(raw_row) < 3:
                continue

            vote_id = (
                str(raw_row[0])
                .strip()
            )

            if vote_id == "":
                continue

            values = raw_row[1:]

            # Member/vote fields occur in pairs.
            for index in range(
                0,
                len(values) - 1,
                2
            ):

                member_id = (
                    str(values[index])
                    .strip()
                    .upper()
                )

                vote = (
                    str(values[index + 1])
                    .strip()
                    .upper()
                )

                if (
                    member_id == ""
                    or
                    vote == ""
                ):
                    continue

                rows.append(
                    {
                        "vote_id": vote_id,
                        "member_id": member_id,
                        "vote": vote,
                    }
                )

    return pd.DataFrame(rows)


# =========================================================
# TEST 1
# RAW VOTE PARSER RECONCILES TO PROCESSED VOTE FACT
#
# This is stronger than checking a sample.
#
# Independently parse raw LIS VOTE.CSV and compare
# vote_id + member_id + vote to the production output.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_raw_vote_records_reconcile_to_vote_fact(year):

    raw_votes = parse_raw_lis_vote_file(year)

    processed = load_processed(
        year,
        "vote_fact"
    )

    raw_keys = set(
        zip(
            normalize_text(
                raw_votes["vote_id"]
            ),
            normalize_upper(
                raw_votes["member_id"]
            ),
            normalize_upper(
                raw_votes["vote"]
            ),
        )
    )

    processed_keys = set(
        zip(
            normalize_text(
                processed["vote_id"]
            ),
            normalize_upper(
                processed["member_id"]
            ),
            normalize_upper(
                processed["vote"]
            ),
        )
    )

    missing_from_processed = (
        raw_keys
        -
        processed_keys
    )

    unexpected_processed = (
        processed_keys
        -
        raw_keys
    )

    assert not missing_from_processed, (
        f"{year}: raw LIS vote records are missing "
        f"from vote_fact. Examples: "
        f"{list(missing_from_processed)[:10]}"
    )

    assert not unexpected_processed, (
        f"{year}: vote_fact contains vote records "
        f"not found in raw LIS VOTE.CSV. Examples: "
        f"{list(unexpected_processed)[:10]}"
    )


# =========================================================
# TEST 2
# RAW AND PROCESSED VOTE ROW COUNTS MATCH
#
# This protects against a set comparison hiding
# accidental duplicate rows.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_raw_vote_row_count_matches_vote_fact(year):

    raw_votes = parse_raw_lis_vote_file(year)

    processed = load_processed(
        year,
        "vote_fact"
    )

    assert len(raw_votes) == len(processed), (
        f"{year}: independently parsed raw VOTE.CSV "
        f"has {len(raw_votes)} rows but vote_fact "
        f"has {len(processed)} rows"
    )


# =========================================================
# TEST 3
# DETERMINISTIC VOTE SAMPLE MATCHES RAW LIS
#
# This produces a smaller human-understandable
# source-validation sample.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_sampled_processed_votes_match_raw_lis(year):

    raw_votes = parse_raw_lis_vote_file(year)

    processed = load_processed(
        year,
        "vote_fact"
    ).copy()

    processed["member_id"] = normalize_upper(
        processed["member_id"]
    )

    processed["vote"] = normalize_upper(
        processed["vote"]
    )

    sample_n = min(
        SAMPLE_SIZE,
        len(processed)
    )

    sample = processed.sample(
        n=sample_n,
        random_state=RANDOM_STATE
    )

    raw_lookup = set(
        zip(
            normalize_text(
                raw_votes["vote_id"]
            ),
            normalize_upper(
                raw_votes["member_id"]
            ),
            normalize_upper(
                raw_votes["vote"]
            ),
        )
    )

    missing = []

    for _, row in sample.iterrows():

        key = (
            str(row["vote_id"]).strip(),
            str(row["member_id"]).strip().upper(),
            str(row["vote"]).strip().upper(),
        )

        if key not in raw_lookup:

            missing.append(
                key
            )

    assert not missing, (
        f"{year}: sampled processed votes "
        f"not found in raw LIS VOTE.CSV: "
        f"{missing}"
    )


# =========================================================
# TEST 4
# PROCESSED BILL LOOKUP MATCHES RAW LIS BILL DESCRIPTION
#
# We are validating source text here, not merely IDs.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_sampled_bill_descriptions_match_raw_lis(year):

    raw = load_raw(
        year,
        "BILLS.CSV"
    ).copy()

    processed = load_processed(
        year,
        "bill_lookup"
    ).copy()

    raw["Bill_id"] = normalize_upper(
        raw["Bill_id"]
    )

    processed["Bill_id"] = normalize_upper(
        processed["Bill_id"]
    )

    raw["Bill_description"] = normalize_text(
        raw["Bill_description"]
    )

    processed["Bill_description"] = normalize_text(
        processed["Bill_description"]
    )

    sample_n = min(
        SAMPLE_SIZE,
        len(processed)
    )

    sample = processed.sample(
        n=sample_n,
        random_state=RANDOM_STATE
    )

    check = sample[
        [
            "Bill_id",
            "Bill_description",
        ]
    ].merge(
        raw[
            [
                "Bill_id",
                "Bill_description",
            ]
        ].rename(
            columns={
                "Bill_description":
                    "raw_Bill_description"
            }
        ),
        on="Bill_id",
        how="left",
        validate="many_to_one"
    )

    missing = check[
        check[
            "raw_Bill_description"
        ]
        .isna()
    ]

    assert len(missing) == 0, (
        f"{year}: sampled processed bills "
        f"were not found in raw BILLS.CSV"
    )

    mismatch = check[
        check[
            "Bill_description"
        ]
        !=
        check[
            "raw_Bill_description"
        ]
    ]

    assert len(mismatch) == 0, (
        f"{year}: sampled Bill_description "
        f"values differ from raw LIS BILLS.CSV:\n"
        f"{mismatch.to_string(index=False)}"
    )


# =========================================================
# TEST 5
# OFFICIAL LIS SUBJECT ROWS MATCH RAW CIBillSubjects
#
# This validates the "Official LIS subject" label
# against the actual LIS subject file.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_official_subjects_backed_by_raw_lis(year):

    raw = load_raw(
        year,
        "CIBillSubjects.csv"
    ).copy()

    official = load_processed(
        year,
        "official_lis_subjects"
    ).copy()

    raw["Bill_Number"] = normalize_upper(
        raw["Bill_Number"]
    )

    raw["Subject_Name"] = normalize_text(
        raw["Subject_Name"]
    )

    official["Bill_id"] = normalize_upper(
        official["Bill_id"]
    )

    official["lis_subject_name"] = normalize_text(
        official["lis_subject_name"]
    )

    raw_pairs = set(
        zip(
            raw["Bill_Number"],
            raw["Subject_Name"],
        )
    )

    official_pairs = set(
        zip(
            official["Bill_id"],
            official["lis_subject_name"],
        )
    )

    unsupported = (
        official_pairs
        -
        raw_pairs
    )

    assert not unsupported, (
        f"{year}: processed Official LIS subject "
        f"rows are not present in raw "
        f"CIBillSubjects.csv. Examples: "
        f"{list(unsupported)[:10]}"
    )


# =========================================================
# TEST 6
# RAW OFFICIAL SUBJECTS ARE NOT LOST
#
# Reverse direction of Test 5.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_raw_official_subjects_preserved(year):

    raw = load_raw(
        year,
        "CIBillSubjects.csv"
    ).copy()

    official = load_processed(
        year,
        "official_lis_subjects"
    ).copy()

    raw_pairs = set(
        zip(
            normalize_upper(
                raw["Bill_Number"]
            ),
            normalize_text(
                raw["Subject_Name"]
            ),
        )
    )

    official_pairs = set(
        zip(
            normalize_upper(
                official["Bill_id"]
            ),
            normalize_text(
                official["lis_subject_name"]
            ),
        )
    )

    lost = (
        raw_pairs
        -
        official_pairs
    )

    assert not lost, (
        f"{year}: raw LIS subject rows are missing "
        f"from processed official subjects. "
        f"Examples: {list(lost)[:10]}"
    )


@pytest.mark.parametrize("year", YEARS)
def test_official_subject_parent_rollup_matches_lis_hierarchy(year):

    raw_subjects = load_raw(
        year,
        "CIBillSubjects.csv"
    ).copy()
    hierarchy = load_raw(
        year,
        "CIParentChildSubjects.csv"
    ).copy()
    official = load_processed(
        year,
        "official_lis_subjects"
    ).copy()

    raw_subjects["Bill_Number"] = normalize_upper(
        raw_subjects["Bill_Number"]
    )
    raw_subjects["Subject_Name"] = normalize_text(
        raw_subjects["Subject_Name"]
    )
    raw_subjects["Subject_Id"] = normalize_text(
        raw_subjects["Subject_Id"]
    )
    hierarchy["C_Subject_Id"] = normalize_text(
        hierarchy["C_Subject_Id"]
    )
    hierarchy["Parent_Subject"] = normalize_text(
        hierarchy["Parent_Subject"]
    )

    expected = raw_subjects.merge(
        hierarchy[
            ["C_Subject_Id", "Parent_Subject"]
        ].drop_duplicates("C_Subject_Id"),
        left_on="Subject_Id",
        right_on="C_Subject_Id",
        how="left",
        validate="many_to_one"
    )
    expected["lis_parent_subject"] = normalize_text(
        expected["Parent_Subject"]
    )
    expected["topic_name"] = expected[
        "lis_parent_subject"
    ].where(
        expected["lis_parent_subject"].ne(""),
        expected["Subject_Name"]
    )

    expected_rows = set(zip(
        expected["Bill_Number"],
        expected["Subject_Name"],
        expected["lis_parent_subject"],
        expected["topic_name"],
    ))
    actual_rows = set(zip(
        normalize_upper(official["Bill_id"]),
        normalize_text(official["lis_subject_name"]),
        normalize_text(official["lis_parent_subject"]),
        normalize_text(official["topic_name"]),
    ))

    assert actual_rows == expected_rows


# =========================================================
# TEST 7
# OFFICIAL SUBJECT PROVENANCE LABEL IS EXACT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_official_subject_provenance_exact(year):

    official = load_processed(
        year,
        "official_lis_subjects"
    )

    values = set(
        normalize_text(
            official["classification"]
        )
        .unique()
    )

    assert values == {
        "Official LIS subject"
    }, (
        f"{year}: official subject output "
        f"has unexpected provenance labels: "
        f"{values}"
    )


# =========================================================
# TEST 8
# DERIVED TOPICS ARE ATTACHED TO REAL LIS BILLS
# WITH REAL LIS BILL DESCRIPTIONS
#
# This does NOT prove that every keyword rule is
# substantively perfect. That requires manual review.
#
# It DOES prove derived topics are grounded in the
# LIS bill-description source rather than some
# external source.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_derived_topics_backed_by_lis_bill_description(year):

    raw_bills = load_raw(
        year,
        "BILLS.CSV"
    ).copy()

    derived = load_processed(
        year,
        "derived_from_lis_bill_description"
    ).copy()

    raw_bills["Bill_id"] = normalize_upper(
        raw_bills["Bill_id"]
    )

    raw_bills["Bill_description"] = normalize_text(
        raw_bills["Bill_description"]
    )

    derived["Bill_id"] = normalize_upper(
        derived["Bill_id"]
    )

    check = derived.merge(
        raw_bills[
            [
                "Bill_id",
                "Bill_description",
            ]
        ],
        on="Bill_id",
        how="left",
        validate="many_to_one"
    )

    missing_bill = check[
        check[
            "Bill_description"
        ]
        .isna()
    ]

    assert len(missing_bill) == 0, (
        f"{year}: derived topic rows reference "
        f"bills absent from raw LIS BILLS.CSV"
    )

    blank_description = check[
        normalize_text(
            check[
                "Bill_description"
            ]
        )
        .eq("")
    ]

    assert len(blank_description) == 0, (
        f"{year}: derived topics exist for bills "
        f"with blank LIS Bill_description"
    )


# =========================================================
# TEST 9
# DERIVED PROVENANCE LABEL IS EXACT
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_derived_provenance_exact(year):

    derived = load_processed(
        year,
        "derived_from_lis_bill_description"
    )

    values = set(
        normalize_text(
            derived["classification"]
        )
        .unique()
    )

    assert values == {
        "Derived from LIS bill description"
    }, (
        f"{year}: derived output has "
        f"unexpected provenance labels: "
        f"{values}"
    )


# =========================================================
# TEST 10
# PARTY REFERENCE MEMBERS ARE ACTUALLY VOTING MEMBERS
#
# We do NOT treat party as coming from VOTE.CSV.
# Party is reference metadata.
#
# This test makes sure the reference IDs used in
# analysis correspond to actual member IDs.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_voting_members_have_party_reference(year):

    vote_fact = load_processed(
        year,
        "vote_fact"
    )

    party_path = (
        REFERENCE_ROOT
        / f"party_{year}.csv"
    )

    party = load_csv(
        party_path
    )

    voting_members = set(
        normalize_upper(
            vote_fact["member_id"]
        )
        .unique()
    )

    party_members = set(
        normalize_upper(
            party["member_id"]
        )
        .unique()
    )

    missing = (
        voting_members
        -
        party_members
    )

    assert not missing, (
        f"{year}: voting members missing "
        f"from party reference: "
        f"{sorted(missing)}"
    )


# =========================================================
# TEST 11
# MEMBER NAMES TRACE TO MEMBERS.CSV OR DOCUMENTED
# REFERENCE RECOVERY
#
# Most member names should come directly from Members.csv.
#
# Historical roster gaps may be recovered through the
# documented party reference fallback.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_member_names_have_source_backing(year):

    vote_fact = load_processed(
        year,
        "vote_fact"
    ).copy()

    members = load_raw(
        year,
        "Members.csv"
    ).copy()

    party = load_csv(
        REFERENCE_ROOT
        / f"party_{year}.csv"
    ).copy()

    vote_fact["member_id"] = normalize_upper(
        vote_fact["member_id"]
    )

    members["MBR_MBRNO"] = normalize_upper(
        members["MBR_MBRNO"]
    )

    party["member_id"] = normalize_upper(
        party["member_id"]
    )

    member_ids = set(
        members["MBR_MBRNO"]
    )

    party_ids = set(
        party["member_id"]
    )

    voting_ids = set(
        vote_fact["member_id"]
    )

    unsupported = (
        voting_ids
        -
        (
            member_ids
            |
            party_ids
        )
    )

    assert not unsupported, (
        f"{year}: voting member IDs lack "
        f"Members.csv or party-reference backing: "
        f"{sorted(unsupported)}"
    )


# =========================================================
# TEST 12
# VOTE-BILL BRIDGE REFERENCES REAL RAW LIS HISTORY ROWS
#
# Because your chosen bridge intentionally preserves:
#
# vote_id
# Bill_id
# History_date
# History_description
#
# we validate that those exact relationships exist in
# raw HISTORY.CSV.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_vote_bill_bridge_rows_backed_by_raw_history(year):

    history = load_raw(
        year,
        "HISTORY.CSV"
    ).copy()

    bridge = load_processed(
        year,
        "vote_bill_bridge"
    ).copy()

    required_bridge = {
        "vote_id",
        "Bill_id",
        "History_date",
        "History_description",
    }

    missing = (
        required_bridge
        -
        set(bridge.columns)
    )

    assert not missing, (
        f"{year}: vote_bill_bridge missing "
        f"history columns: {missing}"
    )

    history["History_refid"] = normalize_text(
        history["History_refid"]
    )

    history["Bill_id"] = normalize_upper(
        history["Bill_id"]
    )

    history["History_date"] = normalize_text(
        history["History_date"]
    )

    history["History_description"] = normalize_text(
        history["History_description"]
    )

    bridge["vote_id"] = normalize_text(
        bridge["vote_id"]
    )

    bridge["Bill_id"] = normalize_upper(
        bridge["Bill_id"]
    )

    bridge["History_date"] = normalize_text(
        bridge["History_date"]
    )

    bridge["History_description"] = normalize_text(
        bridge["History_description"]
    )

    raw_keys = set(
        zip(
            history["History_refid"],
            history["Bill_id"],
            history["History_date"],
            history["History_description"],
        )
    )

    bridge_keys = set(
        zip(
            bridge["vote_id"],
            bridge["Bill_id"],
            bridge["History_date"],
            bridge["History_description"],
        )
    )

    unsupported = (
        bridge_keys
        -
        raw_keys
    )

    assert not unsupported, (
        f"{year}: bridge contains rows "
        f"not backed by raw LIS HISTORY.CSV. "
        f"Examples: {list(unsupported)[:10]}"
    )


# =========================================================
# TEST 13
# EVERY BRIDGE VOTE ID EXISTS IN RAW LIS VOTE DATA
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_bridge_vote_ids_exist_in_raw_votes(year):

    raw_votes = parse_raw_lis_vote_file(year)

    bridge = load_processed(
        year,
        "vote_bill_bridge"
    )

    raw_vote_ids = set(
        normalize_text(
            raw_votes["vote_id"]
        )
        .unique()
    )

    bridge_vote_ids = set(
        normalize_text(
            bridge["vote_id"]
        )
        .unique()
    )

    unknown = (
        bridge_vote_ids
        -
        raw_vote_ids
    )

    assert not unknown, (
        f"{year}: bridge contains vote IDs "
        f"not present in raw LIS VOTE.CSV: "
        f"{sorted(unknown)[:20]}"
    )


# =========================================================
# TEST 14
# EVERY BRIDGE BILL EXISTS IN RAW LIS BILLS.CSV
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_bridge_bill_ids_exist_in_raw_bills(year):

    bills = load_raw(
        year,
        "BILLS.CSV"
    )

    bridge = load_processed(
        year,
        "vote_bill_bridge"
    )

    bill_ids = set(
        normalize_upper(
            bills["Bill_id"]
        )
        .unique()
    )

    bridge_bill_ids = set(
        normalize_upper(
            bridge["Bill_id"]
        )
        .unique()
    )

    unknown = (
        bridge_bill_ids
        -
        bill_ids
    )

    assert not unknown, (
        f"{year}: bridge contains Bill_id "
        f"values not present in raw LIS "
        f"BILLS.CSV: {sorted(unknown)[:20]}"
    )


# =========================================================
# TEST 15
# CREATE DETERMINISTIC MANUAL QA SAMPLE
#
# This is intentionally not a normal assertion-only test.
#
# It creates a file we can manually inspect.
#
# The sample includes:
#
# processed vote
# member
# party
# bill
# bill description
# topic
# classification
#
# We can then compare selected rows to LIS.
# =========================================================

@pytest.mark.parametrize(
    "year",
    YEARS
)
def test_create_manual_source_validation_sample(year):

    vote_fact = load_processed(
        year,
        "vote_fact"
    ).copy()

    bridge = load_processed(
        year,
        "vote_bill_bridge"
    ).copy()

    bills = load_processed(
        year,
        "bill_lookup"
    ).copy()

    topics = load_processed(
        year,
        "bill_topic_lookup"
    ).copy()

    # ---------------------------------------------
    # House only for the manual analytical sample.
    # ---------------------------------------------

    vote_fact["MBR_HOU"] = normalize_upper(
        vote_fact["MBR_HOU"]
    )

    sample_source = vote_fact[
        vote_fact["MBR_HOU"] == "H"
    ].copy()

    # ---------------------------------------------
    # Sample vote events deterministically.
    # ---------------------------------------------

    sample_n = min(
        SAMPLE_SIZE,
        len(sample_source)
    )

    sample = sample_source.sample(
        n=sample_n,
        random_state=RANDOM_STATE
    )

    # ---------------------------------------------
    # Attach vote -> bill relationship.
    #
    # Multiple rows are allowed because one vote can
    # legitimately relate to multiple bills/history rows.
    # ---------------------------------------------

    sample = sample.merge(
        bridge,
        on="vote_id",
        how="left"
    )

    # ---------------------------------------------
    # Attach LIS bill description.
    # ---------------------------------------------

    bill_columns = [
        column
        for column in [
            "Bill_id",
            "Bill_description",
        ]
        if column in bills.columns
    ]

    sample = sample.merge(
        bills[
            bill_columns
        ].drop_duplicates(),
        on="Bill_id",
        how="left"
    )

    # ---------------------------------------------
    # Attach topic/provenance.
    # ---------------------------------------------

    sample = sample.merge(
        topics[
            [
                "Bill_id",
                "topic_name",
                "classification",
            ]
        ],
        on="Bill_id",
        how="left"
    )

    # ---------------------------------------------
    # Add explicit manual-review fields.
    #
    # These are intentionally blank.
    # A human fills them in.
    # ---------------------------------------------

    sample[
        "manual_vote_verified"
    ] = ""

    sample[
        "manual_bill_verified"
    ] = ""

    sample[
        "manual_topic_verified"
    ] = ""

    sample[
        "manual_review_notes"
    ] = ""

    output_path = (
        PROCESSED_ROOT
        / f"manual_source_validation_sample_{year}.csv"
    )

    sample.to_csv(
        output_path,
        index=False
    )

    assert output_path.exists(), (
        f"{year}: manual validation "
        f"sample was not created"
    )

    assert len(sample) > 0, (
        f"{year}: manual validation "
        f"sample is empty"
    )
