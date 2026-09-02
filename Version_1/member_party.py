from pathlib import Path
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup

# =========================================================
# CONFIG
# =========================================================

YEARS = [2025, 2026]

RAW_ROOT = Path("data/raw")
REFERENCE_ROOT = Path("data/reference")

REFERENCE_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# =========================================================
# VERIFIED FALLBACK PARTY VALUES
#
# These are used ONLY if the website lookup returns None.
# Existing successful website results are not overwritten.
# =========================================================

PARTY_FALLBACKS = {

    2025: {

        # -----------------------------
        # HOUSE
        # -----------------------------

        "H0352": "R",
        "H0313": "R",
        "H0334": "D",
        "H0177": "D",
        "H0337": "R",
        "H0315": "R",
        "H0358": "R",
        "H0359": "R",
        "H0279": "R",
        "H0181": "R",
        "H0363": "R",
        "H0367": "R",
        "H0368": "D",
        "H0206": "R",
        "H0373": "R",
        "H0340": "D",
        "H0150": "R",
        "H0376": "R",
        "H0330": "D",
        "H0378": "R",
        "H0073": "R",
        "H0379": "R",
        "H0172": "D",
        "H0346": "R",

        # -----------------------------
        # SENATE
        # -----------------------------

        "S0115": "D",
        "S0114": "D",
        "S0106": "D",
        "S0117": "D",
        "S0132": "R",
        "S0118": "R",
        "S0062": "D",
        "S0096": "R",
        "S0119": "R",
        "S0120": "R",
        "S0085": "D",
        "S0086": "D",
        "S0121": "R",
        "S0112": "R",
        "S0108": "D",
        "S0122": "R",
        "S0116": "R",
        "S0067": "D",
        "S0019": "D",
        "S0080": "D",
        "S0069": "R",
        "S0098": "D",
        "S0131": "R",
        "S0068": "R",
        "S0105": "R",
        "S0124": "D",
        "S0125": "D",
        "S0111": "R",
        "S0088": "R",
        "S0126": "D",
        "S0113": "D",
        "S0127": "D",
        "S0133": "D",
        "S0082": "R",
        "S0078": "R",
        "S0099": "R",
        "S0101": "R",
        "S0100": "D",
        "S0129": "D",
        "S0130": "D",
    },

    2026: {

        # -----------------------------
        # HOUSE
        # -----------------------------

        "H0334": "D",
        "H0177": "D",
        "H0368": "D",
        "H0206": "R",
        "H0340": "D",
        "H0330": "D",
        "H0172": "D",

        # -----------------------------
        # SENATE
        # -----------------------------

        "S0115": "D",
        "S0114": "D",
        "S0135": "D",
        "S0106": "D",
        "S0117": "D",
        "S0132": "R",
        "S0118": "R",
        "S0062": "D",
        "S0096": "R",
        "S0119": "R",
        "S0120": "R",
        "S0085": "D",
        "S0086": "D",
        "S0121": "R",
        "S0112": "R",
        "S0108": "D",
        "S0122": "R",
        "S0134": "D",
        "S0116": "R",
        "S0067": "D",
        "S0019": "D",
        "S0080": "D",
        "S0069": "R",
        "S0098": "D",
        "S0131": "R",
        "S0068": "R",
        "S0105": "R",
        "S0124": "D",
        "S0125": "D",
        "S0111": "R",
        "S0088": "R",
        "S0126": "D",
        "S0113": "D",
        "S0127": "D",
        "S0133": "D",
        "S0082": "R",
        "S0078": "R",
        "S0099": "R",
        "S0101": "R",
        "S0100": "D",
        "S0129": "D",
        "S0130": "D",
    },
}


# =========================================================
# OFFICIAL PROFILE URL
# =========================================================

def get_profile_url(member_id):

    member_id = str(member_id).strip().upper()

    if member_id.startswith("H"):

        return (
            "https://house.vga.virginia.gov/"
            f"members/{member_id}"
        )

    elif member_id.startswith("S"):

        # LIS uses values such as S0115.
        # Senate profile URLs generally use S115.
        try:
            senate_number = int(member_id[1:])
            senate_id = f"S{senate_number}"
        except ValueError:
            return None

        return (
            "https://apps.senate.virginia.gov/"
            "Senator/memberpage.php"
            f"?id={senate_id}"
        )

    return None


# =========================================================
# EXTRACT PARTY FROM HOUSE PROFILE
# =========================================================

def extract_house_party(text):

    if not text:
        return None

    # House profile often contains:
    #
    # D - Counties...
    # R - Counties...

    match = re.search(
        r"\b([DRI])\s*-\s*",
        text
    )

    if match:
        return match.group(1)

    return None


# =========================================================
# EXTRACT PARTY FROM SENATE PROFILE
# =========================================================

def extract_senate_party(text):

    if not text:
        return None

    text_lower = text.lower()

    party_patterns = {

        "D": [
            r"\bdemocrat(?:ic)?\s*,?\s*district\b",
            r"\bparty\s*:?\s*democrat(?:ic)?\b",
        ],

        "R": [
            r"\brepublican\s*,?\s*district\b",
            r"\bparty\s*:?\s*republican\b",
        ],

        "I": [
            r"\bindependent\s*,?\s*district\b",
            r"\bparty\s*:?\s*independent\b",
        ],
    }

    for party_code, patterns in party_patterns.items():

        for pattern in patterns:

            if re.search(
                pattern,
                text_lower
            ):
                return party_code

    return None


# =========================================================
# FETCH ONE MEMBER PARTY
# =========================================================

def fetch_member_party(member_id):

    member_id = str(
        member_id
    ).strip().upper()

    url = get_profile_url(
        member_id
    )

    if url is None:

        return (
            None,
            None,
            "unknown chamber"
        )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

    except requests.RequestException as error:

        return (
            None,
            url,
            f"request error: {error}"
        )

    if not response.text.strip():

        return (
            None,
            url,
            "empty profile page"
        )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    if member_id.startswith("H"):

        party = extract_house_party(
            text
        )

        source = (
            "Virginia House of Delegates"
        )

    elif member_id.startswith("S"):

        party = extract_senate_party(
            text
        )

        source = (
            "Virginia Senate"
        )

    else:

        return (
            None,
            url,
            "unknown chamber"
        )

    if party is None:

        return (
            None,
            url,
            f"{source} - party not found"
        )

    return (
        party,
        url,
        source
    )


# =========================================================
# BUILD ONE YEAR
# =========================================================

def build_year(year):

    members_path = (
        RAW_ROOT
        / str(year)
        / "Members.csv"
    )

    print(
        "\n" + "=" * 60
    )

    print(
        f"BUILDING PARTY LIST: {year}"
    )

    print(
        "=" * 60
    )

    members = pd.read_csv(
        members_path,
        dtype=str
    )

    members["MBR_HOU"] = (
        members["MBR_HOU"]
        .fillna("")
        .str.strip()
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

    results = []

    total = len(
        members
    )

    for number, row in members.iterrows():

        member_id = (
            row["MBR_MBRNO"]
        )

        member_name = (
            row["MBR_NAME"]
        )

        chamber_code = (
            row["MBR_HOU"]
        )

        chamber = (
            "House"
            if chamber_code == "H"
            else "Senate"
        )

        print(
            f"[{number + 1}/{total}] "
            f"{member_id} - "
            f"{member_name}"
        )

        # -------------------------------------------------
        # FIRST TRY AUTOMATIC OFFICIAL PROFILE
        # -------------------------------------------------

        party, url, source = (
            fetch_member_party(
                member_id
            )
        )

        # -------------------------------------------------
        # FALLBACK ONLY IF AUTOMATIC LOOKUP FAILED
        # -------------------------------------------------

        if party is None:

            fallback_party = (
                PARTY_FALLBACKS
                .get(year, {})
                .get(member_id)
            )

            if fallback_party is not None:

                party = fallback_party

                source = (
                    "verified fallback reference"
                )

        # -------------------------------------------------
        # SAVE RESULT
        # -------------------------------------------------

        results.append(
            {
                "year": year,
                "member": member_name,
                "member_id": member_id,
                "chamber": chamber,
                "party": party,
                "source": source,
                "source_url": url,
            }
        )

        # Be polite to source sites
        time.sleep(
            0.15
        )

    result = pd.DataFrame(
        results
    )

    return result


# =========================================================
# VALIDATE
# =========================================================

def validate_year(
    year,
    df
):

    print(
        "\n" + "=" * 60
    )

    print(
        f"VALIDATION: {year}"
    )

    print(
        "=" * 60
    )

    print(
        "\nMembers:"
    )

    print(
        len(df)
    )

    print(
        "\nBy chamber:"
    )

    print(
        df["chamber"]
        .value_counts(
            dropna=False
        )
    )

    print(
        "\nParty counts:"
    )

    print(
        df["party"]
        .value_counts(
            dropna=False
        )
    )

    print(
        "\nSource counts:"
    )

    print(
        df["source"]
        .value_counts(
            dropna=False
        )
    )

    missing = df[
        df["party"].isna()
        |
        (
            df["party"]
            .astype(str)
            .str.strip()
            == ""
        )
    ].copy()

    print(
        "\nMissing party:"
    )

    print(
        len(missing)
    )

    if len(missing) > 0:

        print(
            missing[
                [
                    "member",
                    "member_id",
                    "chamber",
                    "source",
                    "source_url",
                ]
            ]
            .to_string(
                index=False
            )
        )

        raise ValueError(
            f"{year} still has "
            f"{len(missing)} members "
            f"with no party."
        )

    # -------------------------------------
    # CHECK VALID PARTY VALUES
    # -------------------------------------

    invalid = df[
        ~df["party"].isin(
            [
                "D",
                "R",
                "I",
            ]
        )
    ]

    if len(invalid) > 0:

        print(
            "\nInvalid party values:"
        )

        print(
            invalid.to_string(
                index=False
            )
        )

        raise ValueError(
            f"{year} contains "
            f"invalid party values."
        )

    # -------------------------------------
    # CHECK MEMBER ID UNIQUENESS
    # -------------------------------------

    duplicates = df[
        df["member_id"]
        .duplicated(
            keep=False
        )
    ]

    if len(duplicates) > 0:

        print(
            "\nDuplicate member IDs:"
        )

        print(
            duplicates.to_string(
                index=False
            )
        )

        raise ValueError(
            f"{year} contains "
            f"duplicate member IDs."
        )

    print(
        f"\n✓ {year} validation passed."
    )


# =========================================================
# SAVE
# =========================================================

def save_year(
    year,
    df
):

    output_csv = (
        REFERENCE_ROOT
        / f"party_{year}.csv"
    )

    output_reference_csv = (
        REFERENCE_ROOT
        / f"party_reference_{year}.csv"
    )

    # -----------------------------------------------------
    # SMALL FILE USED BY MAIN LIS PIPELINE
    #
    # EXACTLY THREE COLUMNS:
    #
    # member_id
    # party
    # member
    # -----------------------------------------------------

    production = (
        df[
            [
                "member_id",
                "party",
                "member",
            ]
        ]
        .copy()
    )

    production.to_csv(
        output_csv,
        index=False
    )

    # -----------------------------------------------------
    # FULL AUDIT FILE
    # -----------------------------------------------------

    df.to_csv(
        output_reference_csv,
        index=False
    )

    print(
        f"\nSaved: {output_csv}"
    )

    print(
        f"Saved: {output_reference_csv}"
    )


# =========================================================
# RUN BOTH YEARS
# =========================================================

if __name__ == "__main__":

    all_years = []

    for year in YEARS:

        df = build_year(
            year
        )

        validate_year(
            year,
            df
        )

        save_year(
            year,
            df
        )

        all_years.append(
            df
        )

    combined = pd.concat(
        all_years,
        ignore_index=True
    )

    combined_path = (
        REFERENCE_ROOT
        / "party_reference_2025_2026.csv"
    )

    combined.to_csv(
        combined_path,
        index=False
    )

    print(
        "\n" + "=" * 60
    )

    print(
        "COMBINED FILE"
    )

    print(
        "=" * 60
    )

    print(
        combined_path
    )

    print(
        "\nSUCCESS:"
    )

    print(
        "2025 and 2026 party reference "
        "files contain no missing parties."
    )

    print(
        "\nFinished."
    )