from pathlib import Path
from datetime import datetime
import csv
import re

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

RUN_DOWNLOAD = False

# ---------------------------------------------------------
# CURRENT ANALYSIS YEAR
# ---------------------------------------------------------
#
# Run 2025 now using the exact same frozen logic
# that has already been validated on 2026.
#
# ---------------------------------------------------------

ANALYSIS_YEAR = 2025

QA_SAMPLE_PER_TOPIC = 10
QA_RANDOM_STATE = 42


# =========================================================
# ONLY ALLOWED CLASSIFICATION LABELS
# =========================================================

ALLOWED_CLASSIFICATIONS = {
    "Official LIS subject",
    "Derived from LIS bill description",
    "Unclassified",
}


# =========================================================
# DERIVED TOPIC RULES
#
# SOURCE:
# Virginia LIS BILLS.CSV -> Bill_description
#
# IMPORTANT:
#
# These are NOT official LIS subjects.
#
# These are used only when a bill does not have
# an official LIS subject in CIBillSubjects.csv.
#
# These rules are frozen for 2025 + 2026.
# =========================================================

DERIVED_TOPIC_RULES = {

    "Education": [
        r"\bpublic schools?\b",
        r"\bschool boards?\b",
        r"\bschool divisions?\b",
        r"\belementary school\b",
        r"\bsecondary school\b",
        r"\bhigh school\b",
        r"\bstudents?\b",
        r"\bteachers?\b",
        r"\beducation\b",
        r"\btuition\b",
    ],

    "Health and Healthcare": [
        r"\bhealth care\b",
        r"\bhealthcare\b",
        r"\bhospitals?\b",
        r"\bmedical\b",
        r"\bmedicaid\b",
        r"\bpatients?\b",
        r"\bphysicians?\b",
        r"\bnurses?\b",
        r"\bnursing\b",
        r"\bpharmacy\b",
        r"\bpharmacists?\b",
        r"\bhealth carriers?\b",
    ],

    "Behavioral Health": [
        r"\bmental health\b",
        r"\bbehavioral health\b",
        r"\bsubstance abuse\b",
        r"\bsubstance use\b",
        r"\baddiction\b",
        r"\bpsychiatric\b",
        r"\bopioids?\b",
    ],

    "Housing": [
        r"\baffordable housing\b",
        r"\bhousing authorit",
        r"\bhousing needs\b",
        r"\bhousing targets\b",
        r"\bresidential landlord\b",
        r"\bresidential tenant\b",
        r"\btenants?\b",
        r"\blandlords?\b",
        r"\brental agreements?\b",
        r"\brent escrow\b",
        r"\beviction\b",
        r"\bresidential property\b",
        r"\bmixed-income housing\b",
    ],

    "Labor and Employment": [
        r"\bemployment\b",
        r"\bemployers?\b",
        r"\bemployees?\b",
        r"\bminimum wage\b",
        r"\bwages?\b",
        r"\blabor\b",
        r"\bpaid leave\b",
        r"\bsick leave\b",
        r"\bworkers'? compensation\b",
        r"\bworkforce\b",
        r"\bprevailing wage\b",
    ],

    "Energy and Utilities": [
        r"\belectric utilit",
        r"\bpublic utilit",
        r"\belectricity\b",
        r"\benergy\b",
        r"\bsolar\b",
        r"\bwind energy\b",
        r"\brenewable energy\b",
        r"\bpower plant\b",
        r"\belectric grid\b",
        r"\bgrid\b",
        r"\brate adjustment clause\b",
        r"\bdemand response\b",
    ],

    "Environment and Conservation": [
        r"\benvironmental justice\b",
        r"\benvironmental\b",
        r"\bconservation\b",
        r"\bpollution\b",
        r"\bwetlands?\b",
        r"\bwater quality\b",
        r"\bair quality\b",
        r"\bwildlife\b",
        r"\bforest\b",
        r"\bforestry\b",
        r"\brecycling\b",
        r"\bsoil and water conservation\b",
    ],

    "Transportation": [
        r"\bdepartment of transportation\b",
        r"\btransportation\b",
        r"\bhighways?\b",
        r"\bmotor vehicles?\b",
        r"\bvehicle registration\b",
        r"\bdriver'?s licenses?\b",
        r"\bdriving\b",
        r"\btraffic\b",
        r"\btransit\b",
        r"\brailroads?\b",
        r"\brail\b",
        r"\broad user\b",
        r"\broad safety\b",
    ],

    "Criminal Justice": [
        r"\bcriminal\b",
        r"\bcrimes?\b",
        r"\boffenses?\b",
        r"\bfelony\b",
        r"\bmisdemeanor\b",
        r"\bsentenc",
        r"\bprobation\b",
        r"\bparole\b",
        r"\bcorrectional\b",
        r"\binmates?\b",
        r"\bprisoners?\b",
    ],

    "Courts and Civil Law": [
        r"\bcivil action\b",
        r"\bcivil procedure\b",
        r"\bcivil liability\b",
        r"\blawsuit\b",
        r"\bliability\b",
        r"\bdamages\b",
        r"\bjudgments?\b",
        r"\bcourt-assessed\b",
        r"\bcourt of appeals\b",
        r"\bcourt service unit\b",
    ],

    "Public Safety": [
        r"\bpublic safety\b",
        r"\blaw-enforcement officers?\b",
        r"\blaw enforcement officers?\b",
        r"\bpolice departments?\b",
        r"\bfirefighters?\b",
        r"\bemergency medical services\b",
        r"\bemergency services\b",
        r"\bdisaster preparedness\b",
    ],

    "Firearms": [
        r"\bfirearms?\b",
        r"\bhandguns?\b",
        r"\bassault firearms?\b",
        r"\bammunition\b",
        r"\bweapons?\b",
    ],

    "Elections and Voting": [
        r"\belections?\b",
        r"\bvoters?\b",
        r"\bvoting\b",
        r"\bballots?\b",
        r"\bpolling places?\b",
        r"\babsentee voting\b",
        r"\babsentee ballots?\b",
        r"\bcampaign finance\b",
        r"\bpolitical campaign\b",
        r"\bprimary dates?\b",
    ],

    "Taxes and Revenue": [
        r"\bincome tax\b",
        r"\bsales and use tax\b",
        r"\bsales tax\b",
        r"\bproperty tax\b",
        r"\bpersonal property tax\b",
        r"\btax credits?\b",
        r"\btax deductions?\b",
        r"\btaxation\b",
        r"\btaxable\b",
        r"\btaxes\b",
        r"\brevenue\b",
    ],

    "Budget and Appropriations": [
        r"\bbudget bill\b",
        r"\bbudget\b",
        r"\bappropriations?\b",
        r"\bgeneral fund\b",
        r"\bstate funds\b",
        r"\blocal school funds\b",
    ],

    "Business and Commerce": [
        r"\bbusiness licenses?\b",
        r"\bsmall businesses?\b",
        r"\bcorporation act\b",
        r"\bstock corporation\b",
        r"\bcorporations\b",
        r"\bcommercial\b",
        r"\bcommerce\b",
        r"\bconsumer protection\b",
        r"\bconsumer debt\b",
        r"\bprocurement\b",
        r"\bfranchise agreements?\b",
    ],

    "Insurance": [
        r"\bhealth insurance\b",
        r"\bmotor vehicle insurance\b",
        r"\bliability insurance\b",
        r"\binsurance polic",
        r"\binsurers?\b",
        r"\bhealth plan\b",
        r"\bcoverage\b",
        r"\bannuit",
    ],

    "Agriculture and Food": [
        r"\bagricultur",
        r"\bfarms?\b",
        r"\bfarmers?\b",
        r"\bforest prosperity\b",
        r"\blivestock\b",
        r"\bfood service\b",
        r"\bfood products?\b",
        r"\bfood insecurity\b",
        r"\bfertilizer\b",
    ],

    "Local Government": [
        r"\blocal governments?\b",
        r"\blocalit",
        r"\bcounty boards?\b",
        r"\bboard of supervisors\b",
        r"\btown charter\b",
        r"\bcity charter\b",
        r"\bmunicipal\b",
        r"\bzoning appeals\b",
        r"\blocal school funds\b",
    ],

    "State Government": [
        r"\bstate agencies?\b",
        r"\bstate boards?\b",
        r"\bstate commissions?\b",
        r"\bstate government\b",
        r"\bstate employees\b",
        r"\bvirginia personnel act\b",
    ],

    "Technology and Data": [
        r"\bartificial intelligence\b",
        r"\bcybersecurity\b",
        r"\bdata privacy\b",
        r"\bdigital assets?\b",
        r"\bdigital identification\b",
        r"\bautomated decision systems?\b",
        r"\binternet\b",
        r"\belectronically\b",
        r"\bdigital personal property\b",
    ],

    "Family and Children": [
        r"\bfoster care\b",
        r"\bchild abuse\b",
        r"\bchild neglect\b",
        r"\bchild custody\b",
        r"\bchild support\b",
        r"\bchild care\b",
        r"\bchildren\b",
        r"\bminors?\b",
        r"\bparental\b",
        r"\badoption\b",
        r"\badoptee\b",
    ],

    "Marriage and Domestic Relations": [
        r"\bmarriage\b",
        r"\bmarried\b",
        r"\bdivorce\b",
        r"\bspouse\b",
        r"\bdomestic relations\b",
        r"\bannulment\b",
    ],

    "Social Services": [
        r"\bsocial services\b",
        r"\bpublic assistance\b",
        r"\badult protective services\b",
        r"\bfamily assessments\b",
        r"\bcare homes\b",
        r"\bchild care assistance\b",
        r"\bfood insecurity\b",
        r"\bhunger\b",
    ],

    "Higher Education": [
        r"\bhigher education\b",
        r"\binstitutions? of higher education\b",
        r"\bpublic university\b",
        r"\bcommunity colleges?\b",
        r"\bstate council of higher education\b",
        r"\bbaccalaureate public institutions\b",
    ],
}


# =========================================================
# TOPIC EXCLUSION RULES
#
# These do NOT create new categories.
#
# They only prevent known QA false positives.
# =========================================================

TOPIC_EXCLUSION_RULES = {

    "Elections and Voting": [
        r"\bjudges?\b",
        r"\bjudicial\b",
        r"\bcircuit court\b",
        r"\bgeneral district court\b",
        r"\bjuvenile and domestic relations district court\b",
        r"\bnominations? for election\b",
    ],

    "Business and Commerce": [
        r"\bdriver'?s licenses?\b",
        r"\bconsumer-directed services\b",
        r"\bmedicaid waivers?\b",
    ],

    "State Government": [
        r"\bdepartment of motor vehicles\b",
        r"\bdepartment of environmental quality\b",
        r"\bdepartment of taxation\b",
        r"\bdepartment of fire programs\b",
    ],

    "Local Government": [
        r"\bcommending\b",
        r"\bcelebrating the life\b",
    ],
}


# =========================================================
# SESSION CODE
# =========================================================

def get_session_code(year):

    return f"{year}1"


# =========================================================
# DOWNLOAD
# =========================================================

def download_file(
    year,
    filename
):

    url = (
        f"{BASE_URL}/"
        f"{get_session_code(year)}/"
        f"{filename}"
    )

    year_dir = (
        RAW_ROOT
        / str(year)
    )

    year_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = (
        year_dir
        / filename
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
            f"\nPermission denied: "
            f"{output_path}"
        )

        print(
            "Close the file if it is open "
            "in Excel, VS Code, or another program."
        )

        raise

    return output_path


def download_year(year):

    print(
        f"\nDownloading {year}..."
    )

    for filename in FILES:

        try:

            path = (
                download_file(
                    year,
                    filename
                )
            )

            print(
                f"  ✓ {filename} -> "
                f"{path}"
            )

        except requests.RequestException as error:

            print(
                f"  ✗ Failed: "
                f"{filename}"
            )

            print(
                f"    {error}"
            )


# =========================================================
# LOAD PARTY REFERENCE
# =========================================================

def load_party_reference(year):

    path = (
        REFERENCE_ROOT
        / f"party_{year}.csv"
    )

    if not path.exists():

        raise FileNotFoundError(
            f"Missing party file: "
            f"{path}"
        )

    party = pd.read_csv(
        path,
        dtype=str
    )

    required = {
        "member_id",
        "party",
        "member",
    }

    missing = (
        required
        -
        set(
            party.columns
        )
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: "
            f"{missing}"
        )

    party[
        "member_id"
    ] = (
        party[
            "member_id"
        ]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    party[
        "party"
    ] = (
        party[
            "party"
        ]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    party[
        "member"
    ] = (
        party[
            "member"
        ]
        .fillna("")
        .str.strip()
    )

    valid_parties = {
        "D",
        "R",
        "I",
    }

    invalid = party[
        (
            party[
                "party"
            ]
            !=
            ""
        )
        &
        ~party[
            "party"
        ]
        .isin(
            valid_parties
        )
    ]

    if len(
        invalid
    ) > 0:

        print(
            "\nInvalid party-reference rows:"
        )

        print(
            invalid.to_string(
                index=False
            )
        )

        raise ValueError(
            f"{year}: invalid party values."
        )

    duplicate_ids = party[
        party[
            "member_id"
        ]
        .duplicated(
            keep=False
        )
    ]

    if len(
        duplicate_ids
    ) > 0:

        print(
            "\nDuplicate party-reference IDs:"
        )

        print(
            duplicate_ids.to_string(
                index=False
            )
        )

        raise ValueError(
            f"{year}: duplicate party "
            "member IDs."
        )

    return party


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

            if not row:
                continue

            if len(row) < 3:
                continue

            vote_id = (
                row[0]
                .strip()
            )

            vote_data = (
                row[1:]
            )

            if (
                len(vote_data)
                %
                2
                !=
                0
            ):

                print(
                    f"Warning: row "
                    f"{row_number} in {year} "
                    f"has an unexpected "
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
                    vote_data[
                        i + 1
                    ]
                    .strip()
                    .upper()
                )

                if member_id == "":
                    continue

                records.append(
                    {
                        "year":
                            year,

                        "vote_id":
                            vote_id,

                        "member_id":
                            member_id,

                        "vote":
                            vote,
                    }
                )

    return pd.DataFrame(
        records
    )


# =========================================================
# ADD MEMBERS.CSV INFO
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

    required = {
        "MBR_HOU",
        "MBR_MBRNO",
        "MBR_NAME",
    }

    missing = (
        required
        -
        set(
            members.columns
        )
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: "
            f"{missing}"
        )

    members[
        "MBR_MBRNO"
    ] = (
        members[
            "MBR_MBRNO"
        ]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    members[
        "MBR_NAME"
    ] = (
        members[
            "MBR_NAME"
        ]
        .fillna("")
        .str.strip()
    )

    members[
        "MBR_HOU"
    ] = (
        members[
            "MBR_HOU"
        ]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    duplicate_members = members[
        members[
            "MBR_MBRNO"
        ]
        .duplicated(
            keep=False
        )
        &
        (
            members[
                "MBR_MBRNO"
            ]
            !=
            ""
        )
    ]

    if len(
        duplicate_members
    ) > 0:

        print(
            "\nDuplicate member IDs "
            "inside Members.csv:"
        )

        print(
            duplicate_members[
                [
                    "MBR_MBRNO",
                    "MBR_NAME",
                    "MBR_HOU",
                ]
            ]
            .to_string(
                index=False
            )
        )

        raise ValueError(
            f"{year}: Members.csv contains "
            "duplicate member IDs."
        )

    members = members[
        [
            "MBR_MBRNO",
            "MBR_NAME",
            "MBR_HOU",
        ]
    ].copy()

    return votes_long.merge(
        members,
        left_on=
            "member_id",
        right_on=
            "MBR_MBRNO",
        how=
            "left",
        validate=
            "many_to_one"
    )


# =========================================================
# ADD PARTY INFO
# =========================================================

def add_party_info(
    year,
    vote_fact
):

    party = (
        load_party_reference(
            year
        )
    )

    party = (
        party.rename(
            columns={
                "member":
                    "party_reference_name"
            }
        )
    )

    return vote_fact.merge(
        party[
            [
                "member_id",
                "party",
                "party_reference_name",
            ]
        ],

        on=
            "member_id",

        how=
            "left",

        validate=
            "many_to_one"
    )


# =========================================================
# RECONCILE MEMBER METADATA
#
# Canonical identifier:
# VOTE.CSV -> member_id
#
# Name preference:
# 1. Members.csv
# 2. party_<year>.csv member name
#
# Chamber preference:
# 1. Members.csv
# 2. H/S prefix of member_id
#
# Nothing is silently recovered.
# Every fallback is logged.
# =========================================================

def reconcile_member_metadata(
    year,
    vote_fact
):

    result = (
        vote_fact.copy()
    )

    # -----------------------------------------------------
    # NORMALIZE
    # -----------------------------------------------------

    result[
        "MBR_NAME"
    ] = (
        result[
            "MBR_NAME"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    result[
        "MBR_HOU"
    ] = (
        result[
            "MBR_HOU"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    result[
        "party_reference_name"
    ] = (
        result[
            "party_reference_name"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # -----------------------------------------------------
    # DID MEMBERS.CSV MATCH?
    # -----------------------------------------------------

    result[
        "member_found_in_members_csv"
    ] = (
        result[
            "MBR_MBRNO"
        ]
        .notna()
        &
        (
            result[
                "MBR_MBRNO"
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            !=
            ""
        )
    )

    # -----------------------------------------------------
    # MEMBER-ID PREFIX
    # -----------------------------------------------------

    result[
        "member_id_prefix"
    ] = (
        result[
            "member_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .str[:1]
    )

    valid_prefix = (
        result[
            "member_id_prefix"
        ]
        .isin(
            [
                "H",
                "S",
            ]
        )
    )

    # -----------------------------------------------------
    # RECOVER MISSING CHAMBER
    # -----------------------------------------------------

    missing_chamber = (
        result[
            "MBR_HOU"
        ]
        ==
        ""
    )

    result[
        "chamber_recovered_from_member_id"
    ] = (
        missing_chamber
        &
        valid_prefix
    )

    result.loc[
        result[
            "chamber_recovered_from_member_id"
        ],
        "MBR_HOU"
    ] = (
        result.loc[
            result[
                "chamber_recovered_from_member_id"
            ],
            "member_id_prefix"
        ]
    )

    # -----------------------------------------------------
    # RECOVER MISSING NAME
    # -----------------------------------------------------

    missing_name = (
        result[
            "MBR_NAME"
        ]
        ==
        ""
    )

    has_reference_name = (
        result[
            "party_reference_name"
        ]
        !=
        ""
    )

    result[
        "name_recovered_from_party_reference"
    ] = (
        missing_name
        &
        has_reference_name
    )

    result.loc[
        result[
            "name_recovered_from_party_reference"
        ],
        "MBR_NAME"
    ] = (
        result.loc[
            result[
                "name_recovered_from_party_reference"
            ],
            "party_reference_name"
        ]
    )

    # -----------------------------------------------------
    # RECOVERY REPORT
    # -----------------------------------------------------

    recovery = (
        result[
            (
                ~result[
                    "member_found_in_members_csv"
                ]
            )
            |
            result[
                "chamber_recovered_from_member_id"
            ]
            |
            result[
                "name_recovered_from_party_reference"
            ]
        ][
            [
                "member_id",
                "MBR_NAME",
                "MBR_HOU",
                "party",
                "party_reference_name",
                "member_found_in_members_csv",
                "chamber_recovered_from_member_id",
                "name_recovered_from_party_reference",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            "member_id"
        )
        .reset_index(
            drop=True
        )
    )

    if len(
        recovery
    ) > 0:

        PROCESSED_ROOT.mkdir(
            parents=True,
            exist_ok=True
        )

        recovery_path = (
            PROCESSED_ROOT
            / f"member_roster_recovery_{year}.csv"
        )

        recovery.to_csv(
            recovery_path,
            index=False
        )

        print(
            "\n" + "=" * 60
        )

        print(
            f"MEMBER ROSTER "
            f"RECONCILIATION: {year}"
        )

        print(
            "=" * 60
        )

        print(
            "\nVoting members requiring "
            "metadata recovery:"
        )

        print(
            len(
                recovery
            )
        )

        print(
            "\nRecovered member metadata:"
        )

        print(
            recovery.to_string(
                index=False
            )
        )

        print(
            "\nRecovery log saved:"
        )

        print(
            recovery_path
        )

    # -----------------------------------------------------
    # FINAL METADATA CHECK
    # -----------------------------------------------------

    unresolved = (
        result[
            (
                result[
                    "MBR_NAME"
                ]
                ==
                ""
            )
            |
            (
                ~result[
                    "MBR_HOU"
                ]
                .isin(
                    [
                        "H",
                        "S",
                    ]
                )
            )
        ][
            [
                "member_id",
                "MBR_NAME",
                "MBR_HOU",
                "party",
                "party_reference_name",
            ]
        ]
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )

    if len(
        unresolved
    ) > 0:

        unresolved_path = (
            PROCESSED_ROOT
            / f"unresolved_member_metadata_{year}.csv"
        )

        unresolved.to_csv(
            unresolved_path,
            index=False
        )

        print(
            "\nUnresolved member metadata:"
        )

        print(
            unresolved.to_string(
                index=False
            )
        )

        print(
            "\nUnresolved metadata saved:"
        )

        print(
            unresolved_path
        )

        raise ValueError(
            f"{year}: member metadata remains "
            f"unresolved for "
            f"{len(unresolved)} voting members."
        )

    return result


# =========================================================
# VALIDATE PARTY JOIN
#
# Missing parties are exported before stopping.
# =========================================================

def validate_party_join(
    year,
    vote_fact
):

    print(
        "\n" + "=" * 60
    )

    print(
        f"PARTY JOIN VALIDATION: "
        f"{year}"
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
        len(
            members
        )
    )

    print(
        "\nParty counts:"
    )

    print(
        members[
            "party"
        ]
        .replace(
            "",
            pd.NA
        )
        .value_counts(
            dropna=False
        )
    )

    # -----------------------------------------------------
    # MISSING PARTY CHECK
    # -----------------------------------------------------

    missing_party = members[
        members[
            "party"
        ]
        .isna()
        |
        (
            members[
                "party"
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            ==
            ""
        )
    ].copy()

    missing_party = (
        missing_party[
            [
                "member_id",
                "MBR_NAME",
                "MBR_HOU",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            [
                "MBR_HOU",
                "member_id",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    print(
        "\nVoting members with no party:"
    )

    print(
        len(
            missing_party
        )
    )

    if len(
        missing_party
    ) > 0:

        PROCESSED_ROOT.mkdir(
            parents=True,
            exist_ok=True
        )

        missing_path = (
            PROCESSED_ROOT
            / f"missing_party_members_{year}.csv"
        )

        missing_export = (
            missing_party.copy()
        )

        missing_export[
            "party"
        ] = ""

        missing_export.to_csv(
            missing_path,
            index=False
        )

        print(
            "\nMissing party assignments:"
        )

        print(
            missing_export.to_string(
                index=False
            )
        )

        print(
            "\nMissing-party file saved:"
        )

        print(
            missing_path
        )

        raise ValueError(
            f"{year}: party join incomplete. "
            f"{len(missing_party)} voting members "
            f"still have no party assignment."
        )

    # -----------------------------------------------------
    # NAME QA
    # -----------------------------------------------------

    name_check = (
        members.copy()
    )

    name_check[
        "lis_name_check"
    ] = (
        name_check[
            "MBR_NAME"
        ]
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
        len(
            mismatch
        )
    )

    if len(
        mismatch
    ) > 0:

        print(
            mismatch[
                [
                    "member_id",
                    "MBR_NAME",
                    "party_reference_name",
                    "party",
                ]
            ]
            .head(30)
            .to_string(
                index=False
            )
        )

    print(
        f"\n✓ {year} party join passed."
    )


# =========================================================
# PARTY POSITIONS
# =========================================================

def calculate_party_positions(
    vote_fact
):

    directional = vote_fact[
        vote_fact[
            "vote"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        vote_fact[
            "party"
        ]
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
            name=
                "count"
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

            columns=
                "vote",

            values=
                "count",

            fill_value=
                0
        )
        .reset_index()
    )

    if (
        "Y"
        not in
        positions.columns
    ):

        positions[
            "Y"
        ] = 0

    if (
        "N"
        not in
        positions.columns
    ):

        positions[
            "N"
        ] = 0

    positions[
        "party_position"
    ] = "TIE"

    positions.loc[
        positions[
            "Y"
        ]
        >
        positions[
            "N"
        ],

        "party_position"
    ] = "Y"

    positions.loc[
        positions[
            "N"
        ]
        >
        positions[
            "Y"
        ],

        "party_position"
    ] = "N"

    return positions.rename(
        columns={
            "Y":
                "party_yes",

            "N":
                "party_no",
        }
    )


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

    return vote_fact.merge(
        own_party,

        on=[
            "year",
            "MBR_HOU",
            "vote_id",
            "party",
        ],

        how=
            "left",

        validate=
            "many_to_one"
    )


# =========================================================
# FLAG PARTY BREAK
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
        result[
            "vote"
        ]
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
            result[
                "vote"
            ]
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
            party_positions[
                "party"
            ]
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

    other_party[
        "party"
    ] = (
        other_party[
            "party"
        ]
        .map(
            {
                "D":
                    "R",

                "R":
                    "D",
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

    return vote_fact.merge(
        other_party,

        on=[
            "year",
            "MBR_HOU",
            "vote_id",
            "party",
        ],

        how=
            "left",

        validate=
            "many_to_one"
    )


# =========================================================
# FLAG TRUE CROSS-PARTY VOTES
# =========================================================

def flag_cross_party_votes(
    vote_fact
):

    result = (
        vote_fact.copy()
    )

    result[
        "cross_party"
    ] = (
        result[
            "vote"
        ]
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
            result[
                "vote"
            ]
            ==
            result[
                "other_party_position"
            ]
        )
    )

    return result


# =========================================================
# VALIDATE PARTY BEHAVIOR
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
        vote_fact[
            "vote"
        ]
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
        "\nEligible directional "
        "vote rows:"
    )

    print(
        len(
            eligible
        )
    )

    print(
        "\nVotes against "
        "own-party majority:"
    )

    print(
        eligible[
            "broke_with_party"
        ]
        .sum()
    )

    print(
        "\nTrue cross-party votes:"
    )

    print(
        eligible[
            "cross_party"
        ]
        .sum()
    )

    invalid_cross = (
        vote_fact[
            vote_fact[
                "cross_party"
            ]
            &
            ~vote_fact[
                "broke_with_party"
            ]
        ]
    )

    if len(
        invalid_cross
    ) > 0:

        raise ValueError(
            "Cross-party rows exist "
            "without a party break."
        )

    print(
        "\n✓ Party behavior checks passed."
    )


# =========================================================
# BUILD DELEGATE BEHAVIOR SUMMARY
# =========================================================

def build_member_behavior_summary(
    vote_fact
):

    house = (
        vote_fact[
            vote_fact[
                "MBR_HOU"
            ]
            ==
            "H"
        ]
        .copy()
    )

    house[
        "eligible_cross_party"
    ] = (
        house[
            "vote"
        ]
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

            directional_votes=(
                "vote",

                lambda x:
                    x.isin(
                        [
                            "Y",
                            "N",
                        ]
                    )
                    .sum()
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
    ] = 0.0

    eligible_mask = (
        summary[
            "eligible_cross_party_votes"
        ]
        >
        0
    )

    summary.loc[
        eligible_mask,
        "cross_party_pct"
    ] = (
        summary.loc[
            eligible_mask,
            "cross_party_votes"
        ]
        /
        summary.loc[
            eligible_mask,
            "eligible_cross_party_votes"
        ]
        *
        100
    )

    summary[
        "party_break_pct"
    ] = 0.0

    directional_mask = (
        summary[
            "directional_votes"
        ]
        >
        0
    )

    summary.loc[
        directional_mask,
        "party_break_pct"
    ] = (
        summary.loc[
            directional_mask,
            "party_breaks"
        ]
        /
        summary.loc[
            directional_mask,
            "directional_votes"
        ]
        *
        100
    )

    return (
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


# =========================================================
# VOTE -> BILL BRIDGE
# =========================================================

def build_vote_bill_bridge(
    year,
    vote_fact
):

    path = (
        RAW_ROOT
        / str(year)
        / "HISTORY.CSV"
    )

    history = pd.read_csv(
        path,
        dtype=str
    )

    required = {
        "Bill_id",
        "History_date",
        "History_description",
        "History_refid",
    }

    missing = (
        required
        -
        set(
            history.columns
        )
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: "
            f"{missing}"
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

    bridge = (
        bridge.rename(
            columns={
                "History_refid":
                    "vote_id"
            }
        )
    )

    return (
        bridge
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )


# =========================================================
# BILL LOOKUP
# =========================================================

def build_bill_lookup(
    year
):

    path = (
        RAW_ROOT
        / str(year)
        / "BILLS.CSV"
    )

    bills = pd.read_csv(
        path,
        dtype=str
    )

    required = {
        "Bill_id",
        "Bill_description",
        "Patron_id",
        "Patron_name",
    }

    missing = (
        required
        -
        set(
            bills.columns
        )
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: "
            f"{missing}"
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

    return (
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
                "Bill_id"
            ]
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# OFFICIAL LIS SUBJECTS
# =========================================================

def build_official_bill_subject_lookup(
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

    required = {
        "Bill_Number",
        "Subject_Name",
        "Subject_Id",
    }

    missing = (
        required
        -
        set(
            subjects.columns
        )
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: "
            f"{missing}"
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

    subjects = (
        subjects.rename(
            columns={
                "Bill_Number":
                    "Bill_id",

                "Subject_Name":
                    "topic_name",
            }
        )
    )

    subjects[
        "classification"
    ] = (
        "Official LIS subject"
    )

    return (
        subjects[
            [
                "Bill_id",
                "topic_name",
                "classification",
            ]
        ]
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )


# =========================================================
# DERIVE TOPICS FROM LIS BILL DESCRIPTION
# =========================================================

def derive_topics_from_description(
    description
):

    if pd.isna(
        description
    ):

        return []

    text = (
        str(
            description
        )
        .strip()
        .lower()
    )

    if not text:

        return []

    matched_topics = []

    for (
        topic_name,
        patterns
    ) in (
        DERIVED_TOPIC_RULES
        .items()
    ):

        exclusions = (
            TOPIC_EXCLUSION_RULES
            .get(
                topic_name,
                []
            )
        )

        excluded = any(
            re.search(
                exclusion_pattern,
                text,
                flags=
                    re.IGNORECASE
            )
            for exclusion_pattern
            in exclusions
        )

        if excluded:
            continue

        for pattern in patterns:

            if re.search(
                pattern,
                text,
                flags=
                    re.IGNORECASE
            ):

                matched_topics.append(
                    topic_name
                )

                break

    return matched_topics


# =========================================================
# BUILD COMPLETE BILL TOPIC LOOKUP
#
# EXACTLY THREE CLASSIFICATIONS:
#
# Official LIS subject
# Derived from LIS bill description
# Unclassified
# =========================================================

def build_bill_topic_lookup(
    year,
    bill_lookup
):

    official = (
        build_official_bill_subject_lookup(
            year
        )
    )

    official_bill_ids = set(
        official[
            "Bill_id"
        ]
        .unique()
    )

    derived_records = []

    unclassified_records = []

    for _, row in (
        bill_lookup
        .iterrows()
    ):

        bill_id = (
            row[
                "Bill_id"
            ]
        )

        description = (
            row[
                "Bill_description"
            ]
        )

        # -------------------------------------------------
        # OFFICIAL LIS SUBJECT ALWAYS WINS
        # -------------------------------------------------

        if (
            bill_id
            in
            official_bill_ids
        ):

            continue

        topics = (
            derive_topics_from_description(
                description
            )
        )

        if topics:

            for topic_name in topics:

                derived_records.append(
                    {
                        "Bill_id":
                            bill_id,

                        "topic_name":
                            topic_name,

                        "classification":
                            (
                                "Derived from LIS "
                                "bill description"
                            ),
                    }
                )

        else:

            unclassified_records.append(
                {
                    "Bill_id":
                        bill_id,

                    "topic_name":
                        "Unclassified",

                    "classification":
                        "Unclassified",
                }
            )

    derived = pd.DataFrame(
        derived_records,

        columns=[
            "Bill_id",
            "topic_name",
            "classification",
        ]
    )

    unclassified = pd.DataFrame(
        unclassified_records,

        columns=[
            "Bill_id",
            "topic_name",
            "classification",
        ]
    )

    combined = pd.concat(
        [
            official,
            derived,
            unclassified,
        ],

        ignore_index=True
    )

    combined = (
        combined
        .drop_duplicates(
            subset=[
                "Bill_id",
                "topic_name",
                "classification",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return (
        official,
        derived,
        unclassified,
        combined
    )


# =========================================================
# VALIDATE TOPIC CLASSIFICATION
# =========================================================

def validate_topic_classifications(
    bill_lookup,
    official,
    derived,
    unclassified,
    combined
):

    print(
        "\n" + "=" * 60
    )

    print(
        "LIS TOPIC CLASSIFICATION"
    )

    print(
        "=" * 60
    )

    actual_labels = set(
        combined[
            "classification"
        ]
        .dropna()
        .unique()
    )

    unexpected_labels = (
        actual_labels
        -
        ALLOWED_CLASSIFICATIONS
    )

    if unexpected_labels:

        raise ValueError(
            "Unexpected classification "
            f"labels: "
            f"{unexpected_labels}"
        )

    total_bills = (
        bill_lookup[
            "Bill_id"
        ]
        .nunique()
    )

    official_bills = (
        official[
            "Bill_id"
        ]
        .nunique()
    )

    derived_bills = (
        derived[
            "Bill_id"
        ]
        .nunique()
    )

    unclassified_bills = (
        unclassified[
            "Bill_id"
        ]
        .nunique()
    )

    source_ids = set(
        bill_lookup[
            "Bill_id"
        ]
        .unique()
    )

    classified_ids = set(
        combined[
            "Bill_id"
        ]
        .unique()
    )

    missing_ids = (
        source_ids
        -
        classified_ids
    )

    print(
        f"\nTotal LIS bills: "
        f"{total_bills:,}"
    )

    print(
        "\nOfficial LIS subject:"
    )

    print(
        f"{official_bills:,}"
    )

    print(
        "\nDerived from LIS "
        "bill description:"
    )

    print(
        f"{derived_bills:,}"
    )

    print(
        "\nUnclassified:"
    )

    print(
        f"{unclassified_bills:,}"
    )

    print(
        "\nBills missing from "
        "classification table:"
    )

    print(
        len(
            missing_ids
        )
    )

    if missing_ids:

        raise ValueError(
            "Some bills received no "
            "classification record."
        )

    print(
        "\nClassification rows:"
    )

    print(
        combined[
            "classification"
        ]
        .value_counts(
            dropna=False
        )
    )

    print(
        "\n✓ Every bill has one of "
        "the three permitted classifications."
    )


# =========================================================
# BUILD QA SAMPLE
# =========================================================

def build_topic_qa_sample(
    bill_lookup,
    bill_topic_lookup
):

    qa_source = (
        bill_topic_lookup.merge(
            bill_lookup[
                [
                    "Bill_id",
                    "Bill_description",
                ]
            ],

            on=
                "Bill_id",

            how=
                "left",

            validate=
                "many_to_one"
        )
    )

    # -----------------------------------------------------
    # DERIVED
    # -----------------------------------------------------

    derived = qa_source[
        qa_source[
            "classification"
        ]
        ==
        "Derived from LIS bill description"
    ].copy()

    derived_samples = []

    for (
        topic_name,
        group
    ) in (
        derived.groupby(
            "topic_name"
        )
    ):

        sample_size = min(
            QA_SAMPLE_PER_TOPIC,
            len(
                group
            )
        )

        derived_samples.append(
            group.sample(
                n=
                    sample_size,

                random_state=
                    QA_RANDOM_STATE
            )
        )

    if derived_samples:

        derived_qa = pd.concat(
            derived_samples,
            ignore_index=True
        )

    else:

        derived_qa = pd.DataFrame(
            columns=
                qa_source.columns
        )

    # -----------------------------------------------------
    # OFFICIAL
    # -----------------------------------------------------

    official = qa_source[
        qa_source[
            "classification"
        ]
        ==
        "Official LIS subject"
    ].copy()

    if len(
        official
    ) > 0:

        official_qa = (
            official.sample(
                n=
                    min(
                        50,
                        len(
                            official
                        )
                    ),

                random_state=
                    QA_RANDOM_STATE
            )
        )

    else:

        official_qa = pd.DataFrame(
            columns=
                qa_source.columns
        )

    # -----------------------------------------------------
    # UNCLASSIFIED
    # -----------------------------------------------------

    unclassified = qa_source[
        qa_source[
            "classification"
        ]
        ==
        "Unclassified"
    ].copy()

    if len(
        unclassified
    ) > 0:

        unclassified_qa = (
            unclassified.sample(
                n=
                    min(
                        100,
                        len(
                            unclassified
                        )
                    ),

                random_state=
                    QA_RANDOM_STATE
            )
        )

    else:

        unclassified_qa = pd.DataFrame(
            columns=
                qa_source.columns
        )

    qa = pd.concat(
        [
            official_qa,
            derived_qa,
            unclassified_qa,
        ],

        ignore_index=True
    )

    qa[
        "qa_review"
    ] = ""

    qa[
        "qa_notes"
    ] = ""

    return qa[
        [
            "Bill_id",
            "Bill_description",
            "topic_name",
            "classification",
            "qa_review",
            "qa_notes",
        ]
    ]


# =========================================================
# MEMBER × VOTE × TOPIC
# =========================================================

def build_member_vote_topic(
    vote_fact,
    vote_bill_bridge,
    bill_topic_lookup
):

    house_votes = (
        vote_fact[
            vote_fact[
                "MBR_HOU"
            ]
            ==
            "H"
        ]
        .copy()
    )

    vote_bill = (
        house_votes.merge(
            vote_bill_bridge[
                [
                    "vote_id",
                    "Bill_id",
                ]
            ],

            on=
                "vote_id",

            how=
                "inner"
        )
    )

    vote_topic = (
        vote_bill.merge(
            bill_topic_lookup,

            on=
                "Bill_id",

            how=
                "inner"
        )
    )

    # -----------------------------------------------------
    # BLOCK-VOTE PROTECTION
    #
    # One member + vote + topic + classification
    # counts once.
    # -----------------------------------------------------

    member_vote_topic = (
        vote_topic[
            [
                "year",
                "vote_id",
                "member_id",
                "MBR_NAME",
                "party",
                "vote",
                "own_party_position",
                "other_party_position",
                "broke_with_party",
                "cross_party",
                "topic_name",
                "classification",
            ]
        ]
        .drop_duplicates(
            subset=[
                "year",
                "vote_id",
                "member_id",
                "topic_name",
                "classification",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    member_vote_topic[
        "eligible_cross_party"
    ] = (
        member_vote_topic[
            "vote"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        member_vote_topic[
            "own_party_position"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
        &
        member_vote_topic[
            "other_party_position"
        ]
        .isin(
            [
                "Y",
                "N",
            ]
        )
    )

    return member_vote_topic


# =========================================================
# DELEGATE × TOPIC SUMMARY
# =========================================================

def build_delegate_topic_summary(
    member_vote_topic
):

    summary = (
        member_vote_topic
        .groupby(
            [
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

            eligible_topic_events=(
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

    summary[
        "cross_party_pct"
    ] = 0.0

    valid_denominator = (
        summary[
            "eligible_topic_events"
        ]
        >
        0
    )

    summary.loc[
        valid_denominator,
        "cross_party_pct"
    ] = (
        summary.loc[
            valid_denominator,
            "cross_party_events"
        ]
        /
        summary.loc[
            valid_denominator,
            "eligible_topic_events"
        ]
        *
        100
    )

    return (
        summary
        .sort_values(
            [
                "cross_party_events",
                "cross_party_pct",
                "eligible_topic_events",
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
        f"{year} DELEGATE "
        "CROSS-PARTY SUMMARY"
    )

    print(
        "=" * 60
    )

    print(
        "\nTop 25 delegates:"
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
            float_format=
                lambda x:
                    f"{x:.2f}"
        )
    )


# =========================================================
# PRINT TOPIC SUMMARY
#
# Unclassified remains in saved datasets.
#
# It is excluded ONLY from this printed leaderboard
# because it is not an actual policy topic.
# =========================================================

def print_topic_summary(
    year,
    delegate_topic_summary
):

    print(
        "\n" + "=" * 60
    )

    print(
        f"{year} DELEGATE × "
        "LIS TOPIC SUMMARY"
    )

    print(
        "=" * 60
    )

    classified_topics = (
        delegate_topic_summary[
            delegate_topic_summary[
                "classification"
            ]
            !=
            "Unclassified"
        ]
        .copy()
    )

    print(
        "\nTop 40 classified "
        "delegate-topic combinations:"
    )

    print(
        classified_topics[
            [
                "member_id",
                "MBR_NAME",
                "party",
                "topic_name",
                "classification",
                "topic_vote_events",
                "eligible_topic_events",
                "cross_party_events",
                "cross_party_pct",
            ]
        ]
        .head(40)
        .to_string(
            index=False,
            float_format=
                lambda x:
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
    official,
    derived,
    unclassified,
    bill_topic_lookup,
    delegate_summary,
    member_vote_topic,
    delegate_topic_summary,
    qa_sample
):

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    outputs = {

        "vote_fact":
            PROCESSED_ROOT
            / f"vote_fact_{year}.csv",

        "vote_bill_bridge":
            PROCESSED_ROOT
            / f"vote_bill_bridge_{year}.csv",

        "bill_lookup":
            PROCESSED_ROOT
            / f"bill_lookup_{year}.csv",

        "official_lis_subjects":
            PROCESSED_ROOT
            / f"official_lis_subjects_{year}.csv",

        "derived":
            PROCESSED_ROOT
            / (
                f"derived_from_lis_"
                f"bill_description_{year}.csv"
            ),

        "unclassified":
            PROCESSED_ROOT
            / f"unclassified_bills_{year}.csv",

        "bill_topic_lookup":
            PROCESSED_ROOT
            / f"bill_topic_lookup_{year}.csv",

        "delegate_behavior":
            PROCESSED_ROOT
            / f"delegate_behavior_{year}.csv",

        "member_vote_topic":
            PROCESSED_ROOT
            / f"member_vote_topic_{year}.csv",

        "delegate_topic_behavior":
            PROCESSED_ROOT
            / f"delegate_topic_behavior_{year}.csv",

        "topic_qa_sample":
            PROCESSED_ROOT
            / f"topic_qa_sample_{year}.csv",
    }

    vote_fact.to_csv(
        outputs[
            "vote_fact"
        ],
        index=False
    )

    vote_bill_bridge.to_csv(
        outputs[
            "vote_bill_bridge"
        ],
        index=False
    )

    bill_lookup.to_csv(
        outputs[
            "bill_lookup"
        ],
        index=False
    )

    official.to_csv(
        outputs[
            "official_lis_subjects"
        ],
        index=False
    )

    derived.to_csv(
        outputs[
            "derived"
        ],
        index=False
    )

    unclassified.to_csv(
        outputs[
            "unclassified"
        ],
        index=False
    )

    bill_topic_lookup.to_csv(
        outputs[
            "bill_topic_lookup"
        ],
        index=False
    )

    delegate_summary.to_csv(
        outputs[
            "delegate_behavior"
        ],
        index=False
    )

    member_vote_topic.to_csv(
        outputs[
            "member_vote_topic"
        ],
        index=False
    )

    delegate_topic_summary.to_csv(
        outputs[
            "delegate_topic_behavior"
        ],
        index=False
    )

    qa_sample.to_csv(
        outputs[
            "topic_qa_sample"
        ],
        index=False
    )

    return outputs


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
    # DOWNLOAD
    # -----------------------------------------------------

    if RUN_DOWNLOAD:

        print(
            "\nRUN_DOWNLOAD = True"
        )

        print(
            "Refreshing LIS files..."
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
            "Using existing files "
            "in data/raw/"
        )

    year = (
        ANALYSIS_YEAR
    )

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )

    # -----------------------------------------------------
    # 1. PARSE VOTES
    # -----------------------------------------------------

    votes = (
        parse_vote_file(
            year
        )
    )

    # -----------------------------------------------------
    # 2. MEMBERS.CSV
    # -----------------------------------------------------

    vote_fact = (
        add_member_names(
            year,
            votes
        )
    )

    # -----------------------------------------------------
    # 3. PARTY REFERENCE
    # -----------------------------------------------------

    vote_fact = (
        add_party_info(
            year,
            vote_fact
        )
    )

    # -----------------------------------------------------
    # 4. RECONCILE MEMBER METADATA
    #
    # Handles legitimate VOTE.CSV member IDs that are
    # absent from the current Members.csv roster.
    #
    # No silent recovery:
    # all fallback activity is logged.
    # -----------------------------------------------------

    vote_fact = (
        reconcile_member_metadata(
            year,
            vote_fact
        )
    )

    # -----------------------------------------------------
    # 5. PARTY JOIN VALIDATION
    #
    # Missing party assignments are exported to:
    #
    # data/processed/missing_party_members_<year>.csv
    # -----------------------------------------------------

    validate_party_join(
        year,
        vote_fact
    )

    # -----------------------------------------------------
    # 6. PARTY POSITIONS
    # -----------------------------------------------------

    party_positions = (
        calculate_party_positions(
            vote_fact
        )
    )

    vote_fact = (
        add_own_party_position(
            vote_fact,
            party_positions
        )
    )

    vote_fact = (
        flag_party_breaks(
            vote_fact
        )
    )

    vote_fact = (
        add_other_party_position(
            vote_fact,
            party_positions
        )
    )

    vote_fact = (
        flag_cross_party_votes(
            vote_fact
        )
    )

    validate_party_behavior(
        vote_fact
    )

    # -----------------------------------------------------
    # 7. DELEGATE SUMMARY
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
    # 8. VOTE -> BILL
    # -----------------------------------------------------

    vote_bill_bridge = (
        build_vote_bill_bridge(
            year,
            vote_fact
        )
    )

    # -----------------------------------------------------
    # 9. BILL LOOKUP
    # -----------------------------------------------------

    bill_lookup = (
        build_bill_lookup(
            year
        )
    )

    # -----------------------------------------------------
    # 10. BILL TOPICS
    #
    # EXACTLY THREE CLASSIFICATIONS:
    #
    # Official LIS subject
    # Derived from LIS bill description
    # Unclassified
    # -----------------------------------------------------

    (
        official,
        derived,
        unclassified,
        bill_topic_lookup
    ) = (
        build_bill_topic_lookup(
            year,
            bill_lookup
        )
    )

    validate_topic_classifications(
        bill_lookup,
        official,
        derived,
        unclassified,
        bill_topic_lookup
    )

    # -----------------------------------------------------
    # 11. QA SAMPLE
    # -----------------------------------------------------

    qa_sample = (
        build_topic_qa_sample(
            bill_lookup,
            bill_topic_lookup
        )
    )

    print(
        "\n" + "=" * 60
    )

    print(
        "TOPIC QA SAMPLE"
    )

    print(
        "=" * 60
    )

    print(
        f"\nQA rows: "
        f"{len(qa_sample):,}"
    )

    print(
        "\nQA rows by classification:"
    )

    print(
        qa_sample[
            "classification"
        ]
        .value_counts(
            dropna=False
        )
    )

    # -----------------------------------------------------
    # 12. MEMBER × VOTE × TOPIC
    # -----------------------------------------------------

    member_vote_topic = (
        build_member_vote_topic(
            vote_fact,
            vote_bill_bridge,
            bill_topic_lookup
        )
    )

    # -----------------------------------------------------
    # 13. DELEGATE × TOPIC
    # -----------------------------------------------------

    delegate_topic_summary = (
        build_delegate_topic_summary(
            member_vote_topic
        )
    )

    print_topic_summary(
        year,
        delegate_topic_summary
    )

    # -----------------------------------------------------
    # 14. SAVE OUTPUTS
    # -----------------------------------------------------

    outputs = (
        save_outputs(
            year,
            vote_fact,
            vote_bill_bridge,
            bill_lookup,
            official,
            derived,
            unclassified,
            bill_topic_lookup,
            delegate_summary,
            member_vote_topic,
            delegate_topic_summary,
            qa_sample
        )
    )

    # -----------------------------------------------------
    # FINAL STATUS
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
        f"\nAnalysis year: "
        f"{year}"
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
        "\nBill classifications:"
    )

    print(
        f"Official LIS subject bills: "
        f"{official['Bill_id'].nunique():,}"
    )

    print(
        f"Derived from LIS bill "
        f"description bills: "
        f"{derived['Bill_id'].nunique():,}"
    )

    print(
        f"Unclassified bills: "
        f"{unclassified['Bill_id'].nunique():,}"
    )

    print(
        f"\nMember-vote-topic rows: "
        f"{len(member_vote_topic):,}"
    )

    print(
        f"Delegate-topic summary rows: "
        f"{len(delegate_topic_summary):,}"
    )

    print(
        f"QA sample rows: "
        f"{len(qa_sample):,}"
    )

    print(
        "\nFiles saved:"
    )

    for output_path in (
        outputs.values()
    ):

        print(
            output_path
        )

    print(
        "\nFinished."
    )