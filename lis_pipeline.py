from pathlib import Path
from datetime import datetime
import csv

import pandas as pd
import requests


# =========================================================
# CONFIG
# =========================================================

YEARS = [2025, 2026]

FILES = [
    "BILLS.CSV",
    "HISTORY.CSV",
    "VOTE.CSV",
    "Members.csv",
    "CIBillSubjects.csv",
]

BASE_URL = "https://lis.blob.core.windows.net/lisfiles"

RAW_ROOT = Path("data/raw")
REFERENCE_ROOT = Path("data/reference")
PROCESSED_ROOT = Path("data/processed")

# False = use files already downloaded
# True  = refresh LIS bulk files
RUN_DOWNLOAD = False

# For now we are analyzing 2026.
# Later we will convert this to loop through YEARS automatically.
ANALYSIS_YEAR = 2026


# =========================================================
# SESSION CODE
# =========================================================

def get_session_code(year):
    """
    Virginia LIS session code.

    Example:
    2026 regular session -> 20261
    """
    return f"{year}1"


# =========================================================
# DOWNLOAD ONE FILE
# =========================================================

def download_file(year, filename):

    session_code = get_session_code(year)

    url = (
        f"{BASE_URL}/"
        f"{session_code}/"
        f"{filename}"
    )

    year_dir = RAW_ROOT / str(year)

    year_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = (
        year_dir / filename
    )

    response = requests.get(
        url,
        timeout=30
    )

    response.raise_for_status()

    try:

        output_path.write_bytes(
            response.content
        )

    except PermissionError:

        print(
            f"\nPermission denied: {output_path}"
        )

        print(
            "Close the file if it is open in "
            "Excel, ArcGIS, VS Code, or another program."
        )

        raise

    return output_path


# =========================================================
# DOWNLOAD ONE YEAR
# =========================================================

def download_year(year):

    print(
        f"\nDownloading {year}..."
    )

    for filename in FILES:

        try:

            path = download_file(
                year,
                filename
            )

            print(
                f"  ✓ {filename} -> {path}"
            )

        except requests.RequestException as error:

            print(
                f"  ✗ Failed: {filename}"
            )

            print(
                f"    {error}"
            )


# =========================================================
# PARSE VOTE FILE
# =========================================================

def parse_vote_file(year):

    path = (
        RAW_ROOT
        / str(year)
        / "VOTE.CSV"
    )

    records = []

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.reader(
            file
        )

        for row_number, row in enumerate(
            reader,
            start=1
        ):

            # Skip blank rows
            if not row:
                continue

            # LIS VOTE.CSV begins with metadata.
            # Real vote rows have at least:
            # vote_id, member_id, vote
            if len(row) < 3:
                continue

            vote_id = (
                row[0]
                .strip()
            )

            vote_data = (
                row[1:]
            )

            # After vote_id, values should come in pairs:
            # member_id, vote
            if len(vote_data) % 2 != 0:

                print(
                    f"Warning: row {row_number} "
                    f"in {year} has an unexpected "
                    f"number of values."
                )

                continue

            for i in range(
                0,
                len(vote_data),
                2
            ):

                member_id = (
                    vote_data[i]
                    .strip()
                    .upper()
                )

                vote = (
                    vote_data[i + 1]
                    .strip()
                    .upper()
                )

                records.append(
                    {
                        "year": year,
                        "vote_id": vote_id,
                        "member_id": member_id,
                        "vote": vote,
                    }
                )

    votes = pd.DataFrame(
        records
    )

    return votes


# =========================================================
# ADD LIS MEMBER INFORMATION
# =========================================================

def add_member_names(
    year,
    votes_long
):

    path = (
        RAW_ROOT
        / str(year)
        / "Members.csv"
    )

    members = pd.read_csv(
        path,
        dtype=str
    )

    required_columns = {
        "MBR_HOU",
        "MBR_MBRNO",
        "MBR_NAME",
    }

    missing_columns = (
        required_columns
        - set(members.columns)
    )

    if missing_columns:

        raise ValueError(
            f"{path} is missing columns: "
            f"{missing_columns}"
        )

    members["MBR_MBRNO"] = (
        members["MBR_MBRNO"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    members["MBR_NAME"] = (
        members["MBR_NAME"]
        .fillna("")
        .str.strip()
    )

    members["MBR_HOU"] = (
        members["MBR_HOU"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    result = votes_long.merge(
        members[
            [
                "MBR_HOU",
                "MBR_MBRNO",
                "MBR_NAME",
            ]
        ],
        left_on="member_id",
        right_on="MBR_MBRNO",
        how="left",
        validate="many_to_one"
    )

    return result


# =========================================================
# ADD PARTY INFORMATION
# =========================================================

def add_party_info(
    year,
    vote_fact
):

    path = (
        REFERENCE_ROOT
        / f"party_{year}.csv"
    )

    if not path.exists():

        raise FileNotFoundError(
            f"Missing party file: {path}"
        )

    party = pd.read_csv(
        path,
        dtype=str
    )

    required_columns = {
        "member_id",
        "party",
        "member",
    }

    missing_columns = (
        required_columns
        - set(party.columns)
    )

    if missing_columns:

        raise ValueError(
            f"{path} is missing columns: "
            f"{missing_columns}"
        )

    party["member_id"] = (
        party["member_id"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    party["party"] = (
        party["party"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    party["member"] = (
        party["member"]
        .fillna("")
        .str.strip()
    )

    valid_parties = {
        "D",
        "R",
        "I",
    }

    invalid_party = party[
        ~party["party"].isin(
            valid_parties
        )
    ]

    if len(invalid_party) > 0:

        print(
            f"\nInvalid or missing party "
            f"values in {year}:"
        )

        print(
            invalid_party[
                [
                    "member_id",
                    "party",
                    "member",
                ]
            ]
            .to_string(
                index=False
            )
        )

        raise ValueError(
            f"{year} party file contains "
            "missing or invalid values."
        )

    duplicate_ids = party[
        party["member_id"]
        .duplicated(
            keep=False
        )
    ]

    if len(duplicate_ids) > 0:

        print(
            "\nDuplicate party member IDs:"
        )

        print(
            duplicate_ids.to_string(
                index=False
            )
        )

        raise ValueError(
            f"{year} party file contains "
            "duplicate member IDs."
        )

    party = party.rename(
        columns={
            "member":
                "party_reference_name"
        }
    )

    result = vote_fact.merge(
        party[
            [
                "member_id",
                "party",
                "party_reference_name",
            ]
        ],
        on="member_id",
        how="left",
        validate="many_to_one"
    )

    return result


# =========================================================
# VALIDATE PARTY JOIN
# =========================================================

def validate_party_join(
    year,
    vote_fact
):

    print(
        "\n" + "=" * 60
    )

    print(
        f"PARTY JOIN VALIDATION: {year}"
    )

    print(
        "=" * 60
    )

    members = (
        vote_fact[
            [
                "member_id",
                "MBR_NAME",
                "MBR_HOU",
                "party",
                "party_reference_name",
            ]
        ]
        .drop_duplicates()
        .copy()
    )

    print(
        "\nUnique voting members:"
    )

    print(
        len(members)
    )

    print(
        "\nParty counts among unique voting members:"
    )

    print(
        members["party"]
        .value_counts(
            dropna=False
        )
    )

    missing_party = members[
        members["party"].isna()
        |
        (
            members["party"]
            .astype(str)
            .str.strip()
            == ""
        )
    ]

    print(
        "\nVoting members with no party:"
    )

    print(
        len(missing_party)
    )

    if len(missing_party) > 0:

        print(
            missing_party[
                [
                    "member_id",
                    "MBR_NAME",
                    "MBR_HOU",
                ]
            ]
            .to_string(
                index=False
            )
        )

        raise ValueError(
            f"{year}: party join is incomplete."
        )

    # Member ID is our actual join key.
    # This name comparison is an extra quality check.
    name_check = (
        members.copy()
    )

    name_check[
        "lis_name_check"
    ] = (
        name_check["MBR_NAME"]
        .fillna("")
        .str.strip()
        .str.casefold()
    )

    name_check[
        "party_name_check"
    ] = (
        name_check[
            "party_reference_name"
        ]
        .fillna("")
        .str.strip()
        .str.casefold()
    )

    mismatch = name_check[
        name_check[
            "lis_name_check"
        ]
        !=
        name_check[
            "party_name_check"
        ]
    ]

    print(
        "\nExact name mismatches:"
    )

    print(
        len(mismatch)
    )

    if len(mismatch) > 0:

        print(
            mismatch[
                [
                    "member_id",
                    "MBR_NAME",
                    "party_reference_name",
                ]
            ]
            .head(20)
            .to_string(
                index=False
            )
        )

    print(
        f"\n✓ {year} party join passed."
    )


# =========================================================
# CALCULATE PARTY POSITIONS
# =========================================================

def calculate_party_positions(
    vote_fact
):

    # Only Y/N votes determine a directional
    # caucus position.
    #
    # X and A stay in vote_fact, but do not
    # determine whether the caucus position is Y or N.

    directional = vote_fact[
        vote_fact["vote"]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        vote_fact["party"]
        .isin(
            [
                "D",
                "R",
            ]
        )
    ].copy()

    counts = (
        directional
        .groupby(
            [
                "year",
                "MBR_HOU",
                "vote_id",
                "party",
                "vote",
            ]
        )
        .size()
        .reset_index(
            name="count"
        )
    )

    positions = (
        counts
        .pivot_table(
            index=[
                "year",
                "MBR_HOU",
                "vote_id",
                "party",
            ],
            columns="vote",
            values="count",
            fill_value=0,
        )
        .reset_index()
    )

    if "Y" not in positions.columns:
        positions["Y"] = 0

    if "N" not in positions.columns:
        positions["N"] = 0

    positions[
        "party_position"
    ] = "TIE"

    positions.loc[
        positions["Y"]
        >
        positions["N"],
        "party_position"
    ] = "Y"

    positions.loc[
        positions["N"]
        >
        positions["Y"],
        "party_position"
    ] = "N"

    positions = (
        positions.rename(
            columns={
                "Y":
                    "party_yes",

                "N":
                    "party_no",
            }
        )
    )

    return positions


# =========================================================
# ADD OWN-PARTY POSITION
# =========================================================

def add_own_party_position(
    vote_fact,
    party_positions
):

    own_party = (
        party_positions[
            [
                "year",
                "MBR_HOU",
                "vote_id",
                "party",
                "party_position",
                "party_yes",
                "party_no",
            ]
        ]
        .copy()
        .rename(
            columns={
                "party_position":
                    "own_party_position",

                "party_yes":
                    "own_party_yes",

                "party_no":
                    "own_party_no",
            }
        )
    )

    result = vote_fact.merge(
        own_party,
        on=[
            "year",
            "MBR_HOU",
            "vote_id",
            "party",
        ],
        how="left",
        validate="many_to_one"
    )

    return result


# =========================================================
# FLAG OWN-PARTY BREAKS
# =========================================================

def flag_party_breaks(
    vote_fact
):

    result = (
        vote_fact.copy()
    )

    result[
        "broke_with_party"
    ] = (
        result["vote"]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        result[
            "own_party_position"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        (
            result["vote"]
            !=
            result[
                "own_party_position"
            ]
        )
    )

    return result


# =========================================================
# ADD OTHER-PARTY POSITION
# =========================================================

def add_other_party_position(
    vote_fact,
    party_positions
):

    other_party = (
        party_positions[
            party_positions["party"]
            .isin(
                [
                    "D",
                    "R",
                ]
            )
        ][
            [
                "year",
                "MBR_HOU",
                "vote_id",
                "party",
                "party_position",
                "party_yes",
                "party_no",
            ]
        ]
        .copy()
    )

    # Flip the party label so that:
    #
    # Democratic caucus position joins to Republicans
    # Republican caucus position joins to Democrats

    other_party["party"] = (
        other_party["party"]
        .map(
            {
                "D": "R",
                "R": "D",
            }
        )
    )

    other_party = (
        other_party.rename(
            columns={
                "party_position":
                    "other_party_position",

                "party_yes":
                    "other_party_yes",

                "party_no":
                    "other_party_no",
            }
        )
    )

    result = vote_fact.merge(
        other_party,
        on=[
            "year",
            "MBR_HOU",
            "vote_id",
            "party",
        ],
        how="left",
        validate="many_to_one"
    )

    return result


# =========================================================
# FLAG TRUE CROSS-PARTY VOTES
# =========================================================

def flag_cross_party_votes(
    vote_fact
):

    result = (
        vote_fact.copy()
    )

    # Our stricter definition:
    #
    # 1. Member cast Y or N
    # 2. Own party has a clear Y/N majority
    # 3. Other party has a clear Y/N majority
    # 4. Member differs from own-party majority
    # 5. Member matches other-party majority

    result[
        "cross_party"
    ] = (
        result["vote"]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        result[
            "own_party_position"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        result[
            "other_party_position"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        result[
            "broke_with_party"
        ]
        &
        (
            result["vote"]
            ==
            result[
                "other_party_position"
            ]
        )
    )

    return result


# =========================================================
# VALIDATE PARTY / CROSS-PARTY BEHAVIOR
# =========================================================

def validate_party_behavior(
    vote_fact
):

    print(
        "\n" + "=" * 60
    )

    print(
        "PARTY / CROSS-PARTY ANALYSIS"
    )

    print(
        "=" * 60
    )

    eligible = vote_fact[
        vote_fact["vote"]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        vote_fact[
            "own_party_position"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        vote_fact[
            "other_party_position"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
    ].copy()

    print(
        "\nEligible directional vote rows:"
    )

    print(
        len(eligible)
    )

    print(
        "\nVotes against own-party majority:"
    )

    print(
        eligible[
            "broke_with_party"
        ].sum()
    )

    print(
        "\nTrue cross-party votes:"
    )

    print(
        eligible[
            "cross_party"
        ].sum()
    )

    # -----------------------------------------------------
    # SANITY CHECKS
    # -----------------------------------------------------

    invalid_non_directional_breaks = (
        vote_fact[
            vote_fact["vote"]
            .isin(
                [
                    "X",
                    "A",
                ]
            )
        ][
            "broke_with_party"
        ]
        .sum()
    )

    invalid_non_directional_cross = (
        vote_fact[
            vote_fact["vote"]
            .isin(
                [
                    "X",
                    "A",
                ]
            )
        ][
            "cross_party"
        ]
        .sum()
    )

    if invalid_non_directional_breaks != 0:

        raise ValueError(
            "X/A vote rows were incorrectly "
            "flagged as party breaks."
        )

    if invalid_non_directional_cross != 0:

        raise ValueError(
            "X/A vote rows were incorrectly "
            "flagged as cross-party votes."
        )

    invalid_cross_without_break = (
        vote_fact[
            vote_fact["cross_party"]
            &
            ~vote_fact[
                "broke_with_party"
            ]
        ]
    )

    if len(
        invalid_cross_without_break
    ) > 0:

        raise ValueError(
            "Cross-party votes exist that "
            "were not party breaks."
        )

    print(
        "\n✓ Party behavior sanity checks passed."
    )


# =========================================================
# BUILD DELEGATE BEHAVIOR SUMMARY
# =========================================================

def build_member_behavior_summary(
    vote_fact
):

    # The master vote table contains both chambers.
    #
    # This summary is specifically for House delegates.

    house = vote_fact[
        vote_fact["MBR_HOU"] == "H"
    ].copy()

    # A member-vote row is eligible for our
    # cross-party definition only when both
    # parties have clear directional positions.

    house[
        "eligible_cross_party"
    ] = (
        house["vote"]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        house[
            "own_party_position"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        house[
            "other_party_position"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
    )

    summary = (
        house
        .groupby(
            [
                "member_id",
                "MBR_NAME",
                "party",
            ],
            as_index=False
        )
        .agg(

            total_vote_records=(
                "vote_id",
                "count"
            ),

            directional_votes=(
                "vote",
                lambda x:
                    x.isin(
                        [
                            "Y",
                            "N",
                        ]
                    ).sum()
            ),

            eligible_cross_party_votes=(
                "eligible_cross_party",
                "sum"
            ),

            party_breaks=(
                "broke_with_party",
                "sum"
            ),

            cross_party_votes=(
                "cross_party",
                "sum"
            ),
        )
    )

    summary[
        "cross_party_pct"
    ] = (
        summary[
            "cross_party_votes"
        ]
        /
        summary[
            "eligible_cross_party_votes"
        ]
        * 100
    )

    summary[
        "party_break_pct"
    ] = (
        summary[
            "party_breaks"
        ]
        /
        summary[
            "directional_votes"
        ]
        * 100
    )

    summary = (
        summary
        .sort_values(
            [
                "cross_party_votes",
                "cross_party_pct",
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

    return summary


# =========================================================
# BUILD VOTE-BILL BRIDGE
# =========================================================

def build_vote_bill_bridge(
    year,
    vote_fact
):

    history_path = (
        RAW_ROOT
        / str(year)
        / "HISTORY.CSV"
    )

    history = pd.read_csv(
        history_path,
        dtype=str
    )

    required_columns = {
        "Bill_id",
        "History_date",
        "History_description",
        "History_refid",
    }

    missing_columns = (
        required_columns
        - set(history.columns)
    )

    if missing_columns:

        raise ValueError(
            f"{history_path} is missing columns: "
            f"{missing_columns}"
        )

    history[
        "History_refid"
    ] = (
        history[
            "History_refid"
        ]
        .fillna("")
        .str.strip()
    )

    history[
        "Bill_id"
    ] = (
        history[
            "Bill_id"
        ]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    history[
        "History_date"
    ] = (
        history[
            "History_date"
        ]
        .fillna("")
        .str.strip()
    )

    history[
        "History_description"
    ] = (
        history[
            "History_description"
        ]
        .fillna("")
        .str.strip()
    )

    # History_refid is polymorphic.
    # We ONLY keep History_refid values that
    # actually appear as vote IDs in VOTE.CSV.

    actual_vote_ids = set(
        vote_fact[
            "vote_id"
        ]
        .astype(str)
        .str.strip()
        .unique()
    )

    bridge = history[
        history[
            "History_refid"
        ]
        .isin(
            actual_vote_ids
        )
    ][
        [
            "History_refid",
            "Bill_id",
            "History_date",
            "History_description",
        ]
    ].copy()

    bridge = bridge.rename(
        columns={
            "History_refid":
                "vote_id"
        }
    )

    bridge = (
        bridge
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )

    return bridge


# =========================================================
# VALIDATE VOTE-BILL BRIDGE
# =========================================================

def validate_vote_bill_bridge(
    vote_bill_bridge
):

    print(
        "\n" + "=" * 60
    )

    print(
        "VOTE-BILL BRIDGE"
    )

    print(
        "=" * 60
    )

    print(
        "\nRows:"
    )

    print(
        len(vote_bill_bridge)
    )

    print(
        "\nUnique vote IDs:"
    )

    print(
        vote_bill_bridge[
            "vote_id"
        ].nunique()
    )

    print(
        "\nUnique bills:"
    )

    print(
        vote_bill_bridge[
            "Bill_id"
        ].nunique()
    )

    bills_per_vote = (
        vote_bill_bridge
        .groupby(
            "vote_id"
        )[
            "Bill_id"
        ]
        .nunique()
    )

    multi_bill_votes = (
        bills_per_vote
        >
        1
    ).sum()

    print(
        "\nVote events connected to multiple bills:"
    )

    print(
        multi_bill_votes
    )

    if len(
        bills_per_vote
    ) > 0:

        print(
            "\nLargest block vote:"
        )

        print(
            bills_per_vote.max()
        )


# =========================================================
# BUILD BILL LOOKUP
# =========================================================

def build_bill_lookup(
    year
):

    bills_path = (
        RAW_ROOT
        / str(year)
        / "BILLS.CSV"
    )

    bills = pd.read_csv(
        bills_path,
        dtype=str
    )

    required_columns = {
        "Bill_id",
        "Bill_description",
        "Patron_id",
        "Patron_name",
    }

    missing_columns = (
        required_columns
        - set(bills.columns)
    )

    if missing_columns:

        raise ValueError(
            f"{bills_path} is missing columns: "
            f"{missing_columns}"
        )

    bills[
        "Bill_id"
    ] = (
        bills[
            "Bill_id"
        ]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    bills[
        "Bill_description"
    ] = (
        bills[
            "Bill_description"
        ]
        .fillna("")
        .str.strip()
    )

    bills[
        "Patron_id"
    ] = (
        bills[
            "Patron_id"
        ]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    bills[
        "Patron_name"
    ] = (
        bills[
            "Patron_name"
        ]
        .fillna("")
        .str.strip()
    )

    bill_lookup = (
        bills[
            [
                "Bill_id",
                "Bill_description",
                "Patron_id",
                "Patron_name",
            ]
        ]
        .drop_duplicates(
            subset=[
                "Bill_id",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return bill_lookup


# =========================================================
# BUILD BILL-SUBJECT LOOKUP
# =========================================================

def build_bill_subject_lookup(
    year
):

    path = (
        RAW_ROOT
        / str(year)
        / "CIBillSubjects.csv"
    )

    subjects = pd.read_csv(
        path,
        dtype=str
    )

    required_columns = {
        "Bill_Number",
        "Subject_Name",
        "Subject_Id",
    }

    missing_columns = (
        required_columns
        - set(subjects.columns)
    )

    if missing_columns:

        raise ValueError(
            f"{path} is missing columns: "
            f"{missing_columns}"
        )

    subjects[
        "Bill_Number"
    ] = (
        subjects[
            "Bill_Number"
        ]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    subjects[
        "Subject_Name"
    ] = (
        subjects[
            "Subject_Name"
        ]
        .fillna("")
        .str.strip()
    )

    subjects[
        "Subject_Id"
    ] = (
        subjects[
            "Subject_Id"
        ]
        .fillna("")
        .str.strip()
    )

    # Remove unusable rows.
    subjects = subjects[
        (
            subjects[
                "Bill_Number"
            ]
            !=
            ""
        )
        &
        (
            subjects[
                "Subject_Name"
            ]
            !=
            ""
        )
    ].copy()

    subjects = subjects.rename(
        columns={
            "Bill_Number":
                "Bill_id"
        }
    )

    # A bill may legitimately have multiple subjects.
    #
    # We only remove exact duplicate
    # bill/subject relationships.

    bill_subject_lookup = (
        subjects[
            [
                "Bill_id",
                "Subject_Id",
                "Subject_Name",
            ]
        ]
        .drop_duplicates(
            subset=[
                "Bill_id",
                "Subject_Id",
                "Subject_Name",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return bill_subject_lookup


# =========================================================
# VALIDATE SUBJECT LOOKUP
# =========================================================

def validate_subject_lookup(
    year,
    bill_lookup,
    bill_subject_lookup
):

    print(
        "\n" + "=" * 60
    )

    print(
        f"BILL SUBJECT LOOKUP: {year}"
    )

    print(
        "=" * 60
    )

    print(
        "\nBill-subject relationships:"
    )

    print(
        len(
            bill_subject_lookup
        )
    )

    print(
        "\nBills with at least one official subject:"
    )

    bills_with_subject = (
        bill_subject_lookup[
            "Bill_id"
        ]
        .nunique()
    )

    print(
        bills_with_subject
    )

    total_bills = (
        bill_lookup[
            "Bill_id"
        ]
        .nunique()
    )

    print(
        "\nTotal bills in BILLS.CSV:"
    )

    print(
        total_bills
    )

    if total_bills > 0:

        coverage_pct = (
            bills_with_subject
            /
            total_bills
            *
            100
        )

        print(
            "\nOfficial subject coverage:"
        )

        print(
            f"{coverage_pct:.2f}%"
        )

    print(
        "\nUnique subject names:"
    )

    print(
        bill_subject_lookup[
            "Subject_Name"
        ]
        .nunique()
    )

    print(
        "\nImportant:"
    )

    print(
        "Bills without an official subject are NOT "
        "automatically assigned a guessed subject."
    )


# =========================================================
# BUILD MEMBER × VOTE × SUBJECT TABLE
# =========================================================

def build_member_vote_subject(
    vote_fact,
    vote_bill_bridge,
    bill_subject_lookup
):

    # -----------------------------------------------------
    # HOUSE ONLY
    # -----------------------------------------------------
    #
    # The current research question is about delegates.
    # The master vote_fact still retains both chambers.

    house_votes = vote_fact[
        vote_fact[
            "MBR_HOU"
        ]
        ==
        "H"
    ].copy()

    # -----------------------------------------------------
    # VOTE -> BILL
    # -----------------------------------------------------
    #
    # This intentionally expands block votes because
    # one vote event can genuinely connect to many bills.

    vote_bill = (
        house_votes.merge(
            vote_bill_bridge[
                [
                    "vote_id",
                    "Bill_id",
                ]
            ],
            on="vote_id",
            how="inner"
        )
    )

    # -----------------------------------------------------
    # BILL -> SUBJECT
    # -----------------------------------------------------
    #
    # This can expand again because one bill can have
    # multiple official LIS subjects.

    vote_bill_subject = (
        vote_bill.merge(
            bill_subject_lookup,
            on="Bill_id",
            how="inner"
        )
    )

    # -----------------------------------------------------
    # BLOCK-VOTE PROTECTION
    # -----------------------------------------------------
    #
    # This is the critical step.
    #
    # Imagine vote 123 is connected to:
    #
    # HB1 -> Education
    # HB2 -> Education
    # HB3 -> Education
    #
    # That is ONE member decision on ONE vote event
    # associated with Education.
    #
    # It must NOT become three independent
    # Education crossover events.
    #
    # Therefore the analytical grain becomes:
    #
    # year + member + vote + subject
    #
    # not:
    #
    # year + member + vote + bill + subject

    member_vote_subject = (
        vote_bill_subject[
            [
                "year",
                "vote_id",
                "member_id",
                "MBR_NAME",
                "MBR_HOU",
                "party",
                "vote",
                "own_party_position",
                "other_party_position",
                "broke_with_party",
                "cross_party",
                "Subject_Id",
                "Subject_Name",
            ]
        ]
        .drop_duplicates(
            subset=[
                "year",
                "vote_id",
                "member_id",
                "Subject_Id",
                "Subject_Name",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    member_vote_subject[
        "eligible_cross_party"
    ] = (
        member_vote_subject[
            "vote"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        member_vote_subject[
            "own_party_position"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        member_vote_subject[
            "other_party_position"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
    )

    return member_vote_subject


# =========================================================
# VALIDATE MEMBER × VOTE × SUBJECT
# =========================================================

def validate_member_vote_subject(
    member_vote_subject
):

    print(
        "\n" + "=" * 60
    )

    print(
        "MEMBER × VOTE × SUBJECT TABLE"
    )

    print(
        "=" * 60
    )

    print(
        "\nRows:"
    )

    print(
        len(
            member_vote_subject
        )
    )

    print(
        "\nUnique delegates:"
    )

    print(
        member_vote_subject[
            "member_id"
        ]
        .nunique()
    )

    print(
        "\nUnique vote events represented:"
    )

    print(
        member_vote_subject[
            "vote_id"
        ]
        .nunique()
    )

    print(
        "\nUnique subjects represented:"
    )

    print(
        member_vote_subject[
            "Subject_Name"
        ]
        .nunique()
    )

    duplicate_grain = (
        member_vote_subject
        .duplicated(
            subset=[
                "year",
                "vote_id",
                "member_id",
                "Subject_Id",
                "Subject_Name",
            ]
        )
        .sum()
    )

    print(
        "\nDuplicate member-vote-subject rows:"
    )

    print(
        duplicate_grain
    )

    if duplicate_grain != 0:

        raise ValueError(
            "Member-vote-subject table still "
            "contains duplicate analytical rows."
        )

    print(
        "\nCross-party subject rows:"
    )

    print(
        member_vote_subject[
            "cross_party"
        ]
        .sum()
    )

    print(
        "\n✓ Block-vote subject deduplication passed."
    )


# =========================================================
# BUILD DELEGATE × SUBJECT SUMMARY
# =========================================================

def build_delegate_subject_summary(
    member_vote_subject
):

    summary = (
        member_vote_subject
        .groupby(
            [
                "member_id",
                "MBR_NAME",
                "party",
                "Subject_Id",
                "Subject_Name",
            ],
            as_index=False
        )
        .agg(

            # Number of unique vote events associated
            # with this delegate + subject.
            subject_vote_events=(
                "vote_id",
                "nunique"
            ),

            # Number of those subject events where
            # both parties had clear directional
            # positions.
            eligible_subject_events=(
                "eligible_cross_party",
                "sum"
            ),

            party_break_events=(
                "broke_with_party",
                "sum"
            ),

            cross_party_events=(
                "cross_party",
                "sum"
            ),
        )
    )

    # -----------------------------------------------------
    # CROSS-PARTY RATE
    # -----------------------------------------------------
    #
    # Denominator:
    # subject events where our cross-party definition
    # could actually be evaluated.

    summary[
        "cross_party_pct"
    ] = 0.0

    valid_cross_denominator = (
        summary[
            "eligible_subject_events"
        ]
        >
        0
    )

    summary.loc[
        valid_cross_denominator,
        "cross_party_pct"
    ] = (
        summary.loc[
            valid_cross_denominator,
            "cross_party_events"
        ]
        /
        summary.loc[
            valid_cross_denominator,
            "eligible_subject_events"
        ]
        *
        100
    )

    # -----------------------------------------------------
    # PARTY-BREAK RATE
    # -----------------------------------------------------

    summary[
        "party_break_pct"
    ] = 0.0

    valid_break_denominator = (
        summary[
            "subject_vote_events"
        ]
        >
        0
    )

    summary.loc[
        valid_break_denominator,
        "party_break_pct"
    ] = (
        summary.loc[
            valid_break_denominator,
            "party_break_events"
        ]
        /
        summary.loc[
            valid_break_denominator,
            "subject_vote_events"
        ]
        *
        100
    )

    summary = (
        summary
        .sort_values(
            [
                "cross_party_events",
                "cross_party_pct",
                "eligible_subject_events",
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

    return summary


# =========================================================
# PRINT DELEGATE SUMMARY
# =========================================================

def print_delegate_summary(
    year,
    delegate_summary
):

    print(
        "\n" + "=" * 60
    )

    print(
        f"{year} DELEGATE CROSS-PARTY SUMMARY"
    )

    print(
        "=" * 60
    )

    print(
        "\nTop 25 delegates by "
        "cross-party vote count:"
    )

    print(
        delegate_summary[
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
        .head(25)
        .to_string(
            index=False,
            float_format=lambda x:
                f"{x:.2f}"
        )
    )


# =========================================================
# PRINT DELEGATE × SUBJECT SUMMARY
# =========================================================

def print_delegate_subject_summary(
    year,
    delegate_subject_summary
):

    print(
        "\n" + "=" * 60
    )

    print(
        f"{year} DELEGATE × SUBJECT CROSS-PARTY SUMMARY"
    )

    print(
        "=" * 60
    )

    print(
        "\nTop 30 delegate-subject combinations "
        "by observed cross-party event count:"
    )

    print(
        delegate_subject_summary[
            [
                "member_id",
                "MBR_NAME",
                "party",
                "Subject_Name",
                "subject_vote_events",
                "eligible_subject_events",
                "party_break_events",
                "cross_party_events",
                "cross_party_pct",
            ]
        ]
        .head(30)
        .to_string(
            index=False,
            float_format=lambda x:
                f"{x:.2f}"
        )
    )


# =========================================================
# SAVE OUTPUTS
# =========================================================

def save_outputs(
    year,
    vote_fact,
    vote_bill_bridge,
    bill_lookup,
    bill_subject_lookup,
    delegate_summary,
    member_vote_subject,
    delegate_subject_summary
):

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    paths = {
        "vote_fact":
            PROCESSED_ROOT
            / f"vote_fact_{year}.csv",

        "vote_bill_bridge":
            PROCESSED_ROOT
            / f"vote_bill_bridge_{year}.csv",

        "bill_lookup":
            PROCESSED_ROOT
            / f"bill_lookup_{year}.csv",

        "bill_subject_lookup":
            PROCESSED_ROOT
            / f"bill_subject_lookup_{year}.csv",

        "delegate_behavior":
            PROCESSED_ROOT
            / f"delegate_behavior_{year}.csv",

        "member_vote_subject":
            PROCESSED_ROOT
            / f"member_vote_subject_{year}.csv",

        "delegate_subject_behavior":
            PROCESSED_ROOT
            / f"delegate_subject_behavior_{year}.csv",
    }

    vote_fact.to_csv(
        paths["vote_fact"],
        index=False
    )

    vote_bill_bridge.to_csv(
        paths["vote_bill_bridge"],
        index=False
    )

    bill_lookup.to_csv(
        paths["bill_lookup"],
        index=False
    )

    bill_subject_lookup.to_csv(
        paths["bill_subject_lookup"],
        index=False
    )

    delegate_summary.to_csv(
        paths["delegate_behavior"],
        index=False
    )

    member_vote_subject.to_csv(
        paths["member_vote_subject"],
        index=False
    )

    delegate_subject_summary.to_csv(
        paths[
            "delegate_subject_behavior"
        ],
        index=False
    )

    return paths


# =========================================================
# RUN PIPELINE
# =========================================================

if __name__ == "__main__":

    print(
        "LIS pipeline started:"
    )

    print(
        datetime.now()
    )

    # -----------------------------------------------------
    # DOWNLOAD / EXTRACT
    # -----------------------------------------------------

    if RUN_DOWNLOAD:

        print(
            "\nRUN_DOWNLOAD = True"
        )

        print(
            "Refreshing LIS source files..."
        )

        for download_year_value in YEARS:

            download_year(
                download_year_value
            )

    else:

        print(
            "\nRUN_DOWNLOAD = False"
        )

        print(
            "Using existing files in data/raw/"
        )

    # -----------------------------------------------------
    # ANALYSIS YEAR
    # -----------------------------------------------------

    year = ANALYSIS_YEAR

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    # -----------------------------------------------------
    # 1. PARSE VOTE.CSV
    # -----------------------------------------------------

    votes = parse_vote_file(
        year
    )

    # -----------------------------------------------------
    # 2. ADD LIS MEMBER INFORMATION
    # -----------------------------------------------------

    vote_fact = (
        add_member_names(
            year,
            votes
        )
    )

    # -----------------------------------------------------
    # 3. ADD PARTY
    # -----------------------------------------------------

    vote_fact = (
        add_party_info(
            year,
            vote_fact
        )
    )

    validate_party_join(
        year,
        vote_fact
    )

    # -----------------------------------------------------
    # 4. CALCULATE PARTY POSITIONS
    # -----------------------------------------------------

    party_positions = (
        calculate_party_positions(
            vote_fact
        )
    )

    # -----------------------------------------------------
    # 5. ADD OWN-PARTY POSITION
    # -----------------------------------------------------

    vote_fact = (
        add_own_party_position(
            vote_fact,
            party_positions
        )
    )

    # -----------------------------------------------------
    # 6. FLAG OWN-PARTY BREAKS
    # -----------------------------------------------------

    vote_fact = (
        flag_party_breaks(
            vote_fact
        )
    )

    # -----------------------------------------------------
    # 7. ADD OTHER-PARTY POSITION
    # -----------------------------------------------------

    vote_fact = (
        add_other_party_position(
            vote_fact,
            party_positions
        )
    )

    # -----------------------------------------------------
    # 8. FLAG TRUE CROSS-PARTY VOTES
    # -----------------------------------------------------

    vote_fact = (
        flag_cross_party_votes(
            vote_fact
        )
    )

    validate_party_behavior(
        vote_fact
    )

    # -----------------------------------------------------
    # 9. BUILD HOUSE DELEGATE SUMMARY
    # -----------------------------------------------------

    delegate_summary = (
        build_member_behavior_summary(
            vote_fact
        )
    )

    print_delegate_summary(
        year,
        delegate_summary
    )

    # -----------------------------------------------------
    # 10. BUILD VOTE -> BILL BRIDGE
    # -----------------------------------------------------

    vote_bill_bridge = (
        build_vote_bill_bridge(
            year,
            vote_fact
        )
    )

    validate_vote_bill_bridge(
        vote_bill_bridge
    )

    # -----------------------------------------------------
    # 11. BUILD BILL LOOKUP
    # -----------------------------------------------------

    bill_lookup = (
        build_bill_lookup(
            year
        )
    )

    # -----------------------------------------------------
    # 12. BUILD OFFICIAL BILL -> SUBJECT LOOKUP
    # -----------------------------------------------------

    bill_subject_lookup = (
        build_bill_subject_lookup(
            year
        )
    )

    validate_subject_lookup(
        year,
        bill_lookup,
        bill_subject_lookup
    )

    # -----------------------------------------------------
    # 13. BUILD MEMBER × VOTE × SUBJECT TABLE
    # -----------------------------------------------------

    member_vote_subject = (
        build_member_vote_subject(
            vote_fact,
            vote_bill_bridge,
            bill_subject_lookup
        )
    )

    validate_member_vote_subject(
        member_vote_subject
    )

    # -----------------------------------------------------
    # 14. BUILD DELEGATE × SUBJECT SUMMARY
    # -----------------------------------------------------

    delegate_subject_summary = (
        build_delegate_subject_summary(
            member_vote_subject
        )
    )

    print_delegate_subject_summary(
        year,
        delegate_subject_summary
    )

    # -----------------------------------------------------
    # 15. SAVE ALL PROCESSED TABLES
    # -----------------------------------------------------

    output_paths = (
        save_outputs(
            year,
            vote_fact,
            vote_bill_bridge,
            bill_lookup,
            bill_subject_lookup,
            delegate_summary,
            member_vote_subject,
            delegate_subject_summary
        )
    )

    # -----------------------------------------------------
    # FINAL PIPELINE STATUS
    # -----------------------------------------------------

    print(
        "\n" + "=" * 60
    )

    print(
        "PIPELINE STATUS"
    )

    print(
        "=" * 60
    )

    print(
        f"\nAnalysis year: {year}"
    )

    print(
        f"Vote fact rows: "
        f"{len(vote_fact):,}"
    )

    print(
        f"Unique vote events: "
        f"{vote_fact['vote_id'].nunique():,}"
    )

    print(
        f"Unique voting members: "
        f"{vote_fact['member_id'].nunique():,}"
    )

    print(
        f"Party breaks: "
        f"{vote_fact['broke_with_party'].sum():,}"
    )

    print(
        f"True cross-party votes: "
        f"{vote_fact['cross_party'].sum():,}"
    )

    print(
        f"House delegates summarized: "
        f"{len(delegate_summary):,}"
    )

    print(
        f"Vote-bill bridge rows: "
        f"{len(vote_bill_bridge):,}"
    )

    print(
        f"Unique vote IDs linked to bills: "
        f"{vote_bill_bridge['vote_id'].nunique():,}"
    )

    print(
        f"Unique bills linked to votes: "
        f"{vote_bill_bridge['Bill_id'].nunique():,}"
    )

    print(
        f"Bill lookup rows: "
        f"{len(bill_lookup):,}"
    )

    print(
        f"Bill-subject relationships: "
        f"{len(bill_subject_lookup):,}"
    )

    print(
        f"Bills with official subjects: "
        f"{bill_subject_lookup['Bill_id'].nunique():,}"
    )

    print(
        f"Member-vote-subject rows: "
        f"{len(member_vote_subject):,}"
    )

    print(
        f"Delegate-subject summary rows: "
        f"{len(delegate_subject_summary):,}"
    )

    print(
        "\nFiles saved:"
    )

    for path in output_paths.values():

        print(
            path
        )

    print(
        "\nFinished."
    )