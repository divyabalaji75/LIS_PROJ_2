from pathlib import Path
from datetime import datetime
import csv
import html
import os
import re
from urllib.request import urlopen

import pandas as pd

from lis_common import (
    configured_years,
    environment_flag,
    write_csv,
)

try:
    import requests
except ModuleNotFoundError:
    requests = None


DOWNLOAD_REQUEST_ERROR = (
    requests.RequestException
    if requests is not None
    else OSError
)


# =========================================================
# PROJECT CONFIGURATION
# =========================================================
#
# This is the main production pipeline for the Virginia
# Legislative Information System (LIS) research project.
#
# Its job is to:
#
#   - read official LIS files;
#   - create the recorded-vote dataset;
#   - connect votes to bills;
#   - attach party information;
#   - calculate observable cross-party behavior;
#   - classify bills by topic;
#   - build sponsorship, committee, history, and
#     vote-statement datasets;
#   - create reusable House delegate/topic datasets.
#
# Quality-control experiments do NOT belong here.
#
# Topic-methodology QA belongs in:
#
#     topic_validation_audit.py
#
# Keeping those jobs separate prevents the production
# pipeline from generating a large number of temporary QA
# files.
# =========================================================

YEARS = configured_years()


# =========================================================
# WHICH YEARS SHOULD THIS RUN?
#
# DEFAULT:
#
#     python lis_pipeline.py
#
# processes every year configured in lis_common.py.
#
# Example:
#
#     [2025, 2026]
#
#
# OPTIONAL SINGLE-YEAR MODE:
#
# If you deliberately set:
#
#     LIS_ANALYSIS_YEAR=2026
#
# only that year is processed.
#
# PowerShell example:
#
#     $env:LIS_ANALYSIS_YEAR = "2026"
#     python lis_pipeline.py
#
# Remove the environment variable to return to the normal
# all-years behavior:
#
#     Remove-Item Env:LIS_ANALYSIS_YEAR
#
# This fixes the old behavior where the script silently
# processed only the first configured year.
# =========================================================

REQUESTED_ANALYSIS_YEAR = (
    os.environ
    .get(
        "LIS_ANALYSIS_YEAR",
        "",
    )
    .strip()
)

if REQUESTED_ANALYSIS_YEAR:

    ANALYSIS_YEARS = [
        int(
            REQUESTED_ANALYSIS_YEAR
        )
    ]

else:

    ANALYSIS_YEARS = list(
        YEARS
    )


# =========================================================
# OFFICIAL LIS FILES USED BY THE PROJECT
# =========================================================

FILES = [
    "BILLS.CSV",
    "HISTORY.CSV",
    "VOTE.CSV",
    "Members.csv",
    "CIBillSubjects.csv",
    "Summaries.csv",
    "Sponsors.csv",
    "Committees.csv",
    "CommitteeMembers.csv",
    "VoteStatements.csv",
    "CIParentChildSubjects.csv",
]


BASE_URL = (
    "https://lis.blob.core.windows.net/lisfiles"
)

RAW_ROOT = Path(
    "data/raw"
)

REFERENCE_ROOT = Path(
    "data/reference"
)

PROCESSED_ROOT = Path(
    "data/processed"
)


# =========================================================
# SHOULD WE DOWNLOAD NEW LIS FILES?
#
# Normal use:
#
#     LIS_DOWNLOAD is not set
#
# means:
#
#     use the raw LIS files already stored in data/raw/
#
#
# To refresh official LIS files:
#
#     $env:LIS_DOWNLOAD = "1"
#     python lis_pipeline.py
#
# The downloaded raw files remain the source of truth.
# =========================================================

RUN_DOWNLOAD = environment_flag(
    "LIS_DOWNLOAD",
    default=False,
)


# =========================================================
# BILL-TOPIC PROVENANCE
#
# Every bill belongs to exactly ONE of these four source
# categories.
#
# A bill may receive more than one topic.
#
# However, all topics assigned to a bill come from the same
# provenance tier.
#
# Example:
#
#     HB100
#       Education
#       Local Government
#
# could have both topics derived from its LIS summary.
#
# The bill does NOT simultaneously become:
#
#     Official LIS subject
#     AND
#     Derived from LIS summary.
# =========================================================

ALLOWED_CLASSIFICATIONS = {
    "Official LIS subject",
    "Derived from LIS bill summary",
    "Derived from LIS bill description",
    "Unclassified",
}


TOPIC_LOOKUP_COLUMNS = [
    "Bill_id",
    "topic_name",
    "classification",
    "lis_subject_name",
    "lis_parent_subject",
    "source_file",
    "source_text_used",
    "rule_derived",
    "matched_rule",
]


# =========================================================
# WHICH LIS SUMMARY VERSION DO WE USE?
#
# LIS may publish several summaries for the same bill.
#
# We prefer the most mature supported version.
#
# Smaller number = higher priority.
#
# House-passed and Senate-passed summaries intentionally
# share the same priority because neither chamber is
# universally "more final" than the other.
#
# If both exist, original LIS source order is used as the
# deterministic tie-breaker.
# =========================================================

SUMMARY_TYPE_PRIORITY = {
    "SUMMARY AS ENACTED WITH GOVERNOR'S RECOMMENDATION": 1,
    "SUMMARY AS PASSED": 2,
    "SUMMARY AS PASSED HOUSE": 3,
    "SUMMARY AS PASSED SENATE": 3,
    "SUMMARY AS INTRODUCED": 4,
}


# =========================================================
# DERIVED TOPIC RULES
#
# WHY THESE RULES EXIST
# ---------------------
#
# LIS does not provide an official subject for every bill.
#
# When an official subject is unavailable, the project uses
# official LIS text to create broad analytical topics.
#
# Evidence order:
#
#   1. Official LIS subject
#   2. Selected LIS bill summary
#   3. Short LIS bill description
#   4. Unclassified
#
#
# IMPORTANT
# ---------
#
# These regex-derived topics are OUR analytical
# classifications.
#
# They are not official Virginia LIS subjects.
#
# Their accuracy is evaluated separately in:
#
#     topic_validation_audit.py
#
#
# ALSO IMPORTANT
# --------------
#
# "Unclassified" is a valid result.
#
# The objective is NOT to force every bill into a topic.
#
# A bill should remain Unclassified when available LIS text
# does not provide adequate evidence for one of our topics.
#
#
# MULTIPLE TOPICS
# ---------------
#
# Bills may legitimately receive more than one topic.
#
# Example:
#
# A motor-vehicle bill creating a criminal penalty could
# genuinely involve:
#
#     Transportation
#     Criminal Justice
#
# We therefore do not force one "primary" topic.
# =========================================================

DERIVED_TOPIC_RULES = {

    "Commendations and Commemorations": [
        r"^\s*commending\b",
        r"^\s*celebrating the life\b",
    ],

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
        r"\bwork-based learning\b",
        r"\beducational institutions?\b",
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
        r"\bassisted living facilities?\b",
        r"\bstillbirth\b",
        r"\bdeath reg(?:istration|istry)\b",
    ],

    "Behavioral Health": [
        r"\bmental health\b",
        r"\bbehavioral health\b",
        r"\bsubstance abuse\b",
        r"\bsubstance use\b",
        r"\baddiction\b",
        r"\bpsychiatric\b",
        r"\bopioids?\b",
        r"\bpeer recovery specialists?\b",
        r"\bsuicide prevention\b",
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
        r"\bvehicle operation\b",
        r"\bvehicle registration\b",
        r"\bdriver'?s licenses?\b",
        r"\bdriving\b",
        r"\btraffic\b",
        r"\btransit\b",
        r"\brailroads?\b",
        r"\brail\b",
        r"\broad user\b",
        r"\broad safety\b",
        r"\blicense plates?\b",
        r"\btoll facilities?\b",
        r"\bmemorial (?:bridge|highway|road)\b",
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
        r"\baccused\b",
        r"\bsearch warrants?\b",
        r"\bfines and costs\b",
        r"\bdepartment of corrections\b",
        r"\boffenders?\b",
        r"\bhuman trafficking\b",
        r"\bwrit of vacatur\b",
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
        r"\bcircuit courts?\b",
        r"\bgeneral district courts?\b",
        r"\bjudicial districts?\b",
        r"\bjudgeships?\b",
        r"\bjurors?\b",
        r"\bprotective orders?\b",
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
        r"\bemergency management\b",
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
        r"\bplastic bag tax\b",
        r"\breal property tax\b",
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
        r"\bamending (?:the )?charter\b",
        r"\bnew charter\b",
        r"\bprevious charter repealed\b",
    ],

    "State Government": [
        r"\bstate agencies?\b",
        r"\bstate boards?\b",
        r"\bstate commissions?\b",
        r"\bstate government\b",
        r"\bstate employees\b",
        r"\bvirginia personnel act\b",
        r"\bgeneral assembly conflicts of interests act\b",
        r"\boffice of regulatory management\b",
        r"\bconfirming governor'?s appointments\b",
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

    "Study Commissions, Committees, and Reports": [
        r"\btask force\b",
        r"\bwork group\b",
        r"\bstudy feasibility\b",
    ],

    "Alcoholic Beverage and Cannabis Control": [
        r"\balcoholic beverage control\b",
        r"\bboard of directors of the virginia alcohol",
    ],

    "Pensions, Benefits, and Retirement": [
        r"\bvirginia retirement system\b",
        r"\bva\. retirement system\b",
        r"\blaw officers'? retirement system\b",
        r"\bretirement benefits?\b",
        r"\bservice retirement allowance\b",
        r"\bpensions?\b",
        r"\bira savings program\b",
    ],

    "Financial Institutions and Services": [
        r"\bfinancial institutions?(?: and services)?\b",
        r"\bconsumer finance companies\b",
        r"\bcredit unions?\b",
        r"\bcheck cashers?\b",
    ],

    "Gambling, Lotteries, Etc.": [
        r"\bcharitable gaming\b",
        r"\bhorse racing\b",
        r"\bpari-mutuel wagering\b",
        r"\bproblem gambling\b",
    ],

    "Armed Forces": [
        r"\bvirginia national guard\b",
        r"\bmembers? of (?:the )?armed forces\b",
        r"\bdisabled veterans?\b",
    ],

    "Data Centers": [
        r"\bdata centers?\b",
        r"\bcloud computing cluster infrastructure\b",
    ],

    "Property and Conveyances": [
        r"^\s*real property;",
        r"\bunclaimed property\b",
        r"\bconveyances? of interests?\b",
        r"\bcommon interest communities\b",
        r"\bresale disclosure act\b",
    ],

    "Wills, Trusts, and Fiduciaries": [
        r"\buniform trust code\b",
        r"\bqualified trustee\b",
        r"\bdecedents?' estates\b",
        r"\bfiduciar(?:y|ies)\b",
    ],

    "Professions and Occupations": [
        r"\bprofessional licens",
        r"\boccupational licens",
        r"\bboard of medicine\b",
        r"\binternational licensure and certification\b",
    ],

    "Indian Tribes": [
        r"\bfederally recognized tribes?\b",
        r"\bamerican indians?\b",
        r"\btribal consultation\b",
    ],

    "Constitutional Amendments": [
        r"\bconstitutional amendment\b",
    ],

    "Economic Development": [
        r"\beconomic development\b",
        r"\benterprise zone grant program\b",
        r"\bsports tourism grant program\b",
        r"\bmanufacturing (?:expansion )?grant fund\b",
    ],
}


# =========================================================
# TOPIC EXCLUSIONS
#
# Some phrases create known misleading matches in particular
# contexts.
#
# Exclusions do not create topics.
#
# They only prevent a particular derived topic from being
# assigned in a known false-positive context.
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
        r"\bcommercially available\b",
    ],

    "Health and Healthcare": [
        r"\bmedical expenses?\b",
    ],

    "Labor and Employment": [
        r"\bdesignated employees?\b",
    ],

    "Family and Children": [
        r"\bunlicensed minors?\b",
    ],

    "Insurance": [
        r"\b(?:broadband|news|media) coverage\b",
    ],

    "Taxes and Revenue": [
        r"\bbudget bill\b.*\brevenue\b",
    ],

    "Technology and Data": [
        r"\b(?:notice|filing|application|record)\b.{0,40}\belectronically\b",
        r"\bdiscovery\b.{0,40}\belectronically stored\b",
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
        r"\baffected locality\b",
    ],
}


# =========================================================
# SMALL GENERAL HELPERS
# =========================================================

def normalize_text_value(value):

    if pd.isna(value):

        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def strip_summary_html(value):

    text = normalize_text_value(
        value
    )

    if not text:

        return ""

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = html.unescape(
        text
    )

    return normalize_text_value(
        text
    )


def combine_unique_text(values):

    """
    Combine text labels without repeating them.

    Example input:

        Official LIS subject
        Derived from LIS bill summary
        Official LIS subject

    becomes:

        Derived from LIS bill summary | Official LIS subject

    This is used for informational provenance columns.
    It does not affect analytical counts.
    """

    cleaned = {
        normalize_text_value(value)
        for value in values
        if normalize_text_value(value)
    }

    return " | ".join(
        sorted(cleaned)
    )


# =========================================================
# LIS SESSION CODE
#
# Regular sessions use YYYY1.
#
# Example:
#
#     2025 -> 20251
#     2026 -> 20261
#
# Special sessions would require separate configuration and
# should not silently use this convention.
# =========================================================

def get_session_code(year):

    return f"{year}1"


# =========================================================
# DOWNLOAD RAW FILE
# =========================================================

def download_file(
    year,
    filename,
):

    url = (
        f"{BASE_URL}/"
        f"{get_session_code(year)}/"
        f"{filename}"
    )

    year_dir = (
        RAW_ROOT
        /
        str(year)
    )

    year_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        year_dir
        /
        filename
    )

    if requests is not None:

        response = requests.get(
            url,
            timeout=30,
        )

        response.raise_for_status()

        content = response.content

    else:

        with urlopen(
            url,
            timeout=30,
        ) as response:

            content = (
                response.read()
            )

    output_path.write_bytes(
        content
    )

    return output_path


def download_year(year):

    print(
        f"\nDownloading official LIS files for {year}..."
    )

    for filename in FILES:

        try:

            path = download_file(
                year,
                filename,
            )

            print(
                f"  OK  {filename} -> {path}"
            )

        except DOWNLOAD_REQUEST_ERROR as error:

            print(
                f"  FAILED  {filename}"
            )

            print(
                f"    {error}"
            )

            raise


# =========================================================
# PARTY REFERENCE
# =========================================================

def load_party_reference(year):

    path = (
        REFERENCE_ROOT
        /
        f"party_{year}.csv"
    )

    if not path.exists():

        raise FileNotFoundError(
            f"Missing party reference: {path}"
        )

    party = pd.read_csv(
        path,
        dtype=str,
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
            f"{path} missing columns: {missing}"
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

    duplicate_ids = party[
        party[
            "member_id"
        ]
        .duplicated(
            keep=False
        )
        &
        party[
            "member_id"
        ]
        .ne("")
    ]

    if len(
        duplicate_ids
    ) > 0:

        raise ValueError(
            f"{year}: duplicate member IDs "
            "in party reference."
        )

    valid_parties = {
        "D",
        "R",
        "I",
    }

    invalid = party[
        party[
            "party"
        ]
        .ne("")
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

        raise ValueError(
            f"{year}: invalid party values."
        )

    return party


# =========================================================
# PARSE VOTE.CSV
#
# VOTE.CSV stores a vote ID followed by repeating:
#
#     member ID
#     vote value
#
# We convert it into:
#
#     one row per year + vote + member.
# =========================================================

def parse_vote_file(year):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "VOTE.CSV"
    )

    records = []

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.reader(
            file
        )

        for (
            row_number,
            row
        ) in enumerate(
            reader,
            start=1,
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
                    f"Warning: {year} VOTE.CSV "
                    f"row {row_number} has an "
                    "unexpected number of values."
                )

                continue

            for index in range(
                0,
                len(vote_data),
                2,
            ):

                member_id = (
                    vote_data[
                        index
                    ]
                    .strip()
                    .upper()
                )

                vote = (
                    vote_data[
                        index + 1
                    ]
                    .strip()
                    .upper()
                )

                if not member_id:

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
# ADD MEMBER NAME AND CHAMBER
# =========================================================

def add_member_names(
    year,
    votes_long,
):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "Members.csv"
    )

    members = pd.read_csv(
        path,
        dtype=str,
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
            f"{path} missing columns: {missing}"
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
        members[
            "MBR_MBRNO"
        ]
        .ne("")
    ]

    if len(
        duplicate_members
    ) > 0:

        raise ValueError(
            f"{year}: duplicate member IDs "
            "inside Members.csv."
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
        left_on="member_id",
        right_on="MBR_MBRNO",
        how="left",
        validate="many_to_one",
    )


# =========================================================
# ADD PARTY INFORMATION
# =========================================================

def add_party_info(
    year,
    vote_fact,
):

    party = (
        load_party_reference(
            year
        )
        .rename(
            columns={
                "member":
                    "party_reference_name",
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
        on="member_id",
        how="left",
        validate="many_to_one",
    )


# =========================================================
# RECOVER MISSING MEMBER METADATA
#
# VOTE.CSV's member ID remains the authoritative identifier.
#
# If Members.csv lacks a voting member:
#
#   - chamber can be recovered from H/S member-ID prefix;
#   - name can be recovered from party reference.
#
# Recovery is printed so it is never silent.
# =========================================================

def reconcile_member_metadata(
    year,
    vote_fact,
):

    result = (
        vote_fact.copy()
    )

    for column in [
        "MBR_NAME",
        "MBR_HOU",
        "party_reference_name",
    ]:

        result[
            column
        ] = (
            result[
                column
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
        .str.upper()
    )

    result[
        "member_found_in_members_csv"
    ] = (
        result[
            "MBR_MBRNO"
        ]
        .notna()
        &
        result[
            "MBR_MBRNO"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
    )

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

    missing_chamber = (
        result[
            "MBR_HOU"
        ]
        ==
        ""
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
        "MBR_HOU",
    ] = (
        result.loc[
            result[
                "chamber_recovered_from_member_id"
            ],
            "member_id_prefix",
        ]
    )

    missing_name = (
        result[
            "MBR_NAME"
        ]
        ==
        ""
    )

    reference_name_available = (
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
        reference_name_available
    )

    result.loc[
        result[
            "name_recovered_from_party_reference"
        ],
        "MBR_NAME",
    ] = (
        result.loc[
            result[
                "name_recovered_from_party_reference"
            ],
            "party_reference_name",
        ]
    )

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

        print(
            "\n" + "=" * 60
        )

        print(
            f"MEMBER ROSTER RECONCILIATION: {year}"
        )

        print(
            "=" * 60
        )

        print(
            "\nVoting members requiring metadata recovery:"
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

    unresolved = result[
        result[
            "MBR_NAME"
        ]
        .eq("")
        |
        ~result[
            "MBR_HOU"
        ]
        .isin(
            [
                "H",
                "S",
            ]
        )
    ]

    if len(
        unresolved
    ) > 0:

        raise ValueError(
            f"{year}: unresolved member metadata "
            "remains after recovery."
        )

    return result


# =========================================================
# VALIDATE PARTY JOIN
# =========================================================

def validate_party_join(
    year,
    vote_fact,
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
            pd.NA,
        )
        .value_counts(
            dropna=False
        )
    )

    missing_party = members[
        members[
            "party"
        ]
        .isna()
        |
        members[
            "party"
        ]
        .fillna("")
        .str.strip()
        .eq("")
    ]

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

        raise ValueError(
            f"{year}: party join incomplete."
        )

    exact_name_mismatch = members[
        members[
            "MBR_NAME"
        ]
        .fillna("")
        .str.strip()
        .str.casefold()
        !=
        members[
            "party_reference_name"
        ]
        .fillna("")
        .str.strip()
        .str.casefold()
    ]

    print(
        "\nExact name mismatches:"
    )

    print(
        len(
            exact_name_mismatch
        )
    )

    print(
        f"\nOK {year} party join passed."
    )


# =========================================================
# PARTY POSITION ON EACH VOTE
#
# Only directional Y/N votes are used.
#
# If a party has equal Y and N votes, its position is TIE.
# =========================================================

def calculate_party_positions(
    vote_fact,
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

        positions[
            "Y"
        ] = 0

    if "N" not in positions.columns:

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
        "party_position",
    ] = "Y"

    positions.loc[
        positions[
            "N"
        ]
        >
        positions[
            "Y"
        ],
        "party_position",
    ] = "N"

    return positions.rename(
        columns={
            "Y":
                "party_yes",

            "N":
                "party_no",
        }
    )


def add_own_party_position(
    vote_fact,
    party_positions,
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
        how="left",
        validate="many_to_one",
    )


def flag_party_breaks(
    vote_fact,
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


def add_other_party_position(
    vote_fact,
    party_positions,
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
        how="left",
        validate="many_to_one",
    )


# =========================================================
# TRUE CROSS-PARTY VOTE
#
# A recorded vote is considered cross-party only when:
#
#   - member voted Y/N;
#   - member's party had a Y/N majority;
#   - other major party had a Y/N majority;
#   - member voted against own-party majority;
#   - member voted with other-party majority.
# =========================================================

def flag_cross_party_votes(
    vote_fact,
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


def validate_party_behavior(
    vote_fact,
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
    ]

    print(
        "\nEligible directional vote rows:"
    )

    print(
        len(
            eligible
        )
    )

    print(
        "\nVotes against own-party majority:"
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

    invalid = vote_fact[
        vote_fact[
            "cross_party"
        ]
        &
        ~vote_fact[
            "broke_with_party"
        ]
    ]

    if len(
        invalid
    ) > 0:

        raise ValueError(
            "Cross-party rows exist "
            "without an own-party break."
        )

    print(
        "\nOK Party behavior checks passed."
    )


# =========================================================
# OVERALL HOUSE DELEGATE SUMMARY
# =========================================================

def build_member_behavior_summary(
    vote_fact,
):

    house = vote_fact[
        vote_fact[
            "MBR_HOU"
        ]
        ==
        "H"
    ].copy()

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
            as_index=False,
        )
        .agg(
            directional_votes=(
                "vote",
                lambda values:
                    values.isin(
                        [
                            "Y",
                            "N",
                        ]
                    )
                    .sum(),
            ),

            eligible_cross_party_votes=(
                "eligible_cross_party",
                "sum",
            ),

            party_breaks=(
                "broke_with_party",
                "sum",
            ),

            cross_party_votes=(
                "cross_party",
                "sum",
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
        "cross_party_pct",
    ] = (
        summary.loc[
            eligible_mask,
            "cross_party_votes",
        ]
        /
        summary.loc[
            eligible_mask,
            "eligible_cross_party_votes",
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
        "party_break_pct",
    ] = (
        summary.loc[
            directional_mask,
            "party_breaks",
        ]
        /
        summary.loc[
            directional_mask,
            "directional_votes",
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
            ],
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# VOTE -> BILL BRIDGE
#
# HISTORY.CSV links recorded vote IDs to bills.
#
# One vote may legitimately apply to multiple bills.
# =========================================================

def build_vote_bill_bridge(
    year,
    vote_fact,
):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "HISTORY.CSV"
    )

    history = pd.read_csv(
        path,
        dtype=str,
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
            f"{path} missing columns: {missing}"
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

    bridge = bridge.rename(
        columns={
            "History_refid":
                "vote_id",
        }
    )

    return (
        bridge
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )


# =========================================================
# COMPLETE BILL HISTORY
# =========================================================

def build_bill_history(year):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "HISTORY.CSV"
    )

    history = pd.read_csv(
        path,
        dtype=str,
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
            f"{path} missing columns: {missing}"
        )

    history = (
        history[
            [
                "Bill_id",
                "History_date",
                "History_description",
                "History_refid",
            ]
        ]
        .rename(
            columns={
                "History_date":
                    "history_date",

                "History_description":
                    "history_description",

                "History_refid":
                    "history_refid",
            }
        )
    )

    for column in history.columns:

        history[
            column
        ] = (
            history[
                column
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
        .str.upper()
    )

    history.insert(
        0,
        "year",
        year,
    )

    return (
        history
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )


# =========================================================
# BILL LOOKUP
# =========================================================

def build_bill_lookup(year):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "BILLS.CSV"
    )

    bills = pd.read_csv(
        path,
        dtype=str,
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
            f"{path} missing columns: {missing}"
        )

    for column in [
        "Bill_id",
        "Bill_description",
        "Patron_id",
        "Patron_name",
    ]:

        bills[
            column
        ] = (
            bills[
                column
            ]
            .fillna("")
            .str.strip()
        )

    bills[
        "Bill_id"
    ] = (
        bills[
            "Bill_id"
        ]
        .str.upper()
    )

    bills[
        "Patron_id"
    ] = (
        bills[
            "Patron_id"
        ]
        .str.upper()
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
# LIS SUBJECT HIERARCHY
# =========================================================

def build_lis_subject_hierarchy(year):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "CIParentChildSubjects.csv"
    )

    hierarchy = pd.read_csv(
        path,
        dtype=str,
    )

    required = {
        "Parent_Subject",
        "P_Subject_Id",
        "Child_Subject",
        "C_Subject_Id",
    }

    missing = (
        required
        -
        set(
            hierarchy.columns
        )
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: {missing}"
        )

    hierarchy = hierarchy.rename(
        columns={
            "Parent_Subject":
                "lis_parent_subject",

            "P_Subject_Id":
                "lis_parent_subject_id",

            "Child_Subject":
                "lis_subject_name",

            "C_Subject_Id":
                "lis_subject_id",
        }
    )

    for column in hierarchy.columns:

        hierarchy[
            column
        ] = (
            hierarchy[
                column
            ]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    return (
        hierarchy[
            [
                "lis_parent_subject_id",
                "lis_parent_subject",
                "lis_subject_id",
                "lis_subject_name",
            ]
        ]
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )


# =========================================================
# SELECT ONE LIS SUMMARY PER BILL
# =========================================================

def build_bill_summary_lookup(year):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "Summaries.csv"
    )

    summaries = pd.read_csv(
        path,
        dtype=str,
    )

    required = {
        "SUM_BILNO",
        "SUMMARY_DOCID",
        "SUMMARY_TYPE",
        "SUMMARY_TEXT",
    }

    missing = (
        required
        -
        set(
            summaries.columns
        )
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: {missing}"
        )

    summaries = summaries.rename(
        columns={
            "SUM_BILNO":
                "Bill_id",

            "SUMMARY_DOCID":
                "summary_doc_id",

            "SUMMARY_TYPE":
                "summary_type",

            "SUMMARY_TEXT":
                "summary_text_html",
        }
    )

    summaries[
        "Bill_id"
    ] = (
        summaries[
            "Bill_id"
        ]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    summaries[
        "summary_doc_id"
    ] = (
        summaries[
            "summary_doc_id"
        ]
        .fillna("")
        .str.strip()
    )

    summaries[
        "summary_type"
    ] = (
        summaries[
            "summary_type"
        ]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    summaries[
        "summary_text"
    ] = (
        summaries[
            "summary_text_html"
        ]
        .map(
            strip_summary_html
        )
    )

    summaries[
        "summary_priority"
    ] = (
        summaries[
            "summary_type"
        ]
        .map(
            SUMMARY_TYPE_PRIORITY
        )
    )

    supported = summaries[
        summaries[
            "summary_priority"
        ]
        .notna()
        &
        summaries[
            "Bill_id"
        ]
        .ne("")
        &
        summaries[
            "summary_text"
        ]
        .ne("")
    ].copy()

    supported[
        "summary_priority"
    ] = (
        supported[
            "summary_priority"
        ]
        .astype(int)
    )

    supported[
        "source_row_number"
    ] = (
        supported.index
        +
        2
    )

    selected = (
        supported
        .sort_values(
            [
                "Bill_id",
                "summary_priority",
                "source_row_number",
            ],
            kind="stable",
        )
        .drop_duplicates(
            subset=[
                "Bill_id"
            ],
            keep="first",
        )
        .reset_index(
            drop=True
        )
    )

    selected[
        "source_file"
    ] = "Summaries.csv"

    return selected[
        [
            "Bill_id",
            "summary_doc_id",
            "summary_type",
            "summary_priority",
            "summary_text",
            "source_file",
            "source_row_number",
        ]
    ]


# =========================================================
# OFFICIAL LIS BILL SUBJECTS
#
# Exact LIS subject is preserved.
#
# If the exact subject has a parent in the official LIS
# hierarchy, topic_name uses the parent as the analytical
# rollup.
# =========================================================

def build_official_bill_subject_lookup(
    year,
    hierarchy=None,
):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "CIBillSubjects.csv"
    )

    subjects = pd.read_csv(
        path,
        dtype=str,
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
            f"{path} missing columns: {missing}"
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
        subjects[
            "Bill_Number"
        ]
        .ne("")
        &
        subjects[
            "Subject_Name"
        ]
        .ne("")
    ].copy()

    subjects = subjects.rename(
        columns={
            "Bill_Number":
                "Bill_id",

            "Subject_Name":
                "lis_subject_name",

            "Subject_Id":
                "lis_subject_id",
        }
    )

    subjects[
        "lis_subject_id"
    ] = (
        subjects[
            "lis_subject_id"
        ]
        .fillna("")
        .str.strip()
    )

    if hierarchy is None:

        hierarchy = (
            build_lis_subject_hierarchy(
                year
            )
        )

    hierarchy_lookup = (
        hierarchy[
            [
                "lis_subject_id",
                "lis_parent_subject",
            ]
        ]
        .drop_duplicates(
            subset=[
                "lis_subject_id"
            ]
        )
    )

    subjects = subjects.merge(
        hierarchy_lookup,
        on="lis_subject_id",
        how="left",
        validate="many_to_one",
    )

    subjects[
        "lis_parent_subject"
    ] = (
        subjects[
            "lis_parent_subject"
        ]
        .fillna("")
        .str.strip()
    )

    subjects[
        "topic_name"
    ] = (
        subjects[
            "lis_parent_subject"
        ]
        .where(
            subjects[
                "lis_parent_subject"
            ]
            .ne(""),
            subjects[
                "lis_subject_name"
            ],
        )
    )

    subjects[
        "classification"
    ] = (
        "Official LIS subject"
    )

    subjects[
        "source_file"
    ] = (
        "CIBillSubjects.csv"
    )

    subjects[
        "source_text_used"
    ] = (
        subjects[
            "lis_subject_name"
        ]
    )

    subjects[
        "rule_derived"
    ] = False

    subjects[
        "matched_rule"
    ] = ""

    return (
        subjects[
            TOPIC_LOOKUP_COLUMNS
        ]
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )


# =========================================================
# APPLY DERIVED TOPIC RULES
# =========================================================

def derive_topics_with_rules(
    text_value,
):

    if pd.isna(
        text_value
    ):

        return []

    text = (
        str(
            text_value
        )
        .strip()
        .lower()
    )

    if not text:

        return []

    # A ceremonial resolution can mention schools, hospitals, businesses, or
    # professions only to identify an honoree. Those words are not policy
    # subjects, so the ceremonial classification is intentionally terminal.
    ceremonial_rule = r"^\s*(?:commending|celebrating the life)\b"

    if re.search(ceremonial_rule, text, flags=re.IGNORECASE):

        return [
            {
                "topic_name": "Commendations and Commemorations",
                "matched_rule": ceremonial_rule,
            }
        ]

    matched_topics = []

    for (
        topic_name,
        patterns,
    ) in DERIVED_TOPIC_RULES.items():

        exclusions = (
            TOPIC_EXCLUSION_RULES
            .get(
                topic_name,
                [],
            )
        )

        excluded = any(
            re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
            for pattern in exclusions
        )

        if excluded:

            continue

        for pattern in patterns:

            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):

                matched_topics.append(
                    {
                        "topic_name":
                            topic_name,

                        "matched_rule":
                            pattern,
                    }
                )

                break

    return matched_topics


def derive_topics_from_description(
    description,
):

    return [
        match[
            "topic_name"
        ]
        for match
        in derive_topics_with_rules(
            description
        )
    ]


# =========================================================
# BUILD BILL-TOPIC LOOKUP
# =========================================================

def build_bill_topic_lookup(
    year,
    bill_lookup,
    hierarchy=None,
    summary_lookup=None,
):

    official = (
        build_official_bill_subject_lookup(
            year,
            hierarchy=hierarchy,
        )
    )

    if summary_lookup is None:

        summary_lookup = (
            build_bill_summary_lookup(
                year
            )
        )

    summary_by_bill = (
        summary_lookup
        .set_index(
            "Bill_id"
        )[
            "summary_text"
        ]
        .to_dict()
    )

    official_bill_ids = set(
        official[
            "Bill_id"
        ]
        .unique()
    )

    # -----------------------------------------------------
    # Several exact LIS child subjects may roll up to the
    # same analytical parent topic.
    #
    # Collapse duplicate analytical parent rows while
    # retaining exact source subjects for traceability.
    # -----------------------------------------------------

    analytical_official = (
        official
        .groupby(
            [
                "Bill_id",
                "topic_name",
                "classification",
            ],
            as_index=False,
            sort=False,
        )
        .agg(
            lis_subject_name=(
                "lis_subject_name",
                combine_unique_text,
            ),

            lis_parent_subject=(
                "lis_parent_subject",
                lambda values:
                    next(
                        (
                            value
                            for value
                            in values
                            if normalize_text_value(
                                value
                            )
                        ),
                        "",
                    ),
            ),

            source_file=(
                "source_file",
                "first",
            ),

            source_text_used=(
                "lis_subject_name",
                combine_unique_text,
            ),

            rule_derived=(
                "rule_derived",
                "first",
            ),

            matched_rule=(
                "matched_rule",
                "first",
            ),
        )
    )[
        TOPIC_LOOKUP_COLUMNS
    ]

    summary_records = []
    description_records = []
    unclassified_records = []

    for _, row in (
        bill_lookup.iterrows()
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

        # Official LIS subjects always win.
        if (
            bill_id
            in
            official_bill_ids
        ):

            continue

        # Next use selected LIS summary.
        selected_summary = (
            summary_by_bill
            .get(
                bill_id,
                "",
            )
        )

        summary_topics = (
            derive_topics_with_rules(
                selected_summary
            )
        )

        if summary_topics:

            for match in (
                summary_topics
            ):

                summary_records.append(
                    {
                        "Bill_id":
                            bill_id,

                        "topic_name":
                            match[
                                "topic_name"
                            ],

                        "classification":
                            "Derived from LIS bill summary",

                        "lis_subject_name":
                            "",

                        "lis_parent_subject":
                            "",

                        "source_file":
                            "Summaries.csv",

                        "source_text_used":
                            selected_summary,

                        "rule_derived":
                            True,

                        "matched_rule":
                            match[
                                "matched_rule"
                            ],
                    }
                )

            continue

        # Finally use short LIS description.
        description_topics = (
            derive_topics_with_rules(
                description
            )
        )

        if description_topics:

            for match in (
                description_topics
            ):

                description_records.append(
                    {
                        "Bill_id":
                            bill_id,

                        "topic_name":
                            match[
                                "topic_name"
                            ],

                        "classification":
                            "Derived from LIS bill description",

                        "lis_subject_name":
                            "",

                        "lis_parent_subject":
                            "",

                        "source_file":
                            "BILLS.CSV",

                        "source_text_used":
                            description,

                        "rule_derived":
                            True,

                        "matched_rule":
                            match[
                                "matched_rule"
                            ],
                    }
                )

        else:

            # No rule supplied enough evidence.
            unclassified_records.append(
                {
                    "Bill_id":
                        bill_id,

                    "topic_name":
                        "Unclassified",

                    "classification":
                        "Unclassified",

                    "lis_subject_name":
                        "",

                    "lis_parent_subject":
                        "",

                    "source_file":
                        "BILLS.CSV",

                    "source_text_used":
                        description,

                    "rule_derived":
                        False,

                    "matched_rule":
                        "",
                }
            )

    summary_derived = pd.DataFrame(
        summary_records,
        columns=TOPIC_LOOKUP_COLUMNS,
    )

    description_derived = pd.DataFrame(
        description_records,
        columns=TOPIC_LOOKUP_COLUMNS,
    )

    unclassified = pd.DataFrame(
        unclassified_records,
        columns=TOPIC_LOOKUP_COLUMNS,
    )

    combined = (
        pd.concat(
            [
                analytical_official,
                summary_derived,
                description_derived,
                unclassified,
            ],
            ignore_index=True,
        )
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )

    return (
        official,
        summary_derived,
        description_derived,
        unclassified,
        combined,
    )


# =========================================================
# VALIDATE BILL CLASSIFICATION STRUCTURE
# =========================================================

def validate_topic_classifications(
    bill_lookup,
    official,
    summary_derived,
    description_derived,
    unclassified,
    combined,
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

    unexpected = (
        actual_labels
        -
        ALLOWED_CLASSIFICATIONS
    )

    if unexpected:

        raise ValueError(
            f"Unexpected classifications: {unexpected}"
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

    summary_bills = (
        summary_derived[
            "Bill_id"
        ]
        .nunique()
    )

    description_bills = (
        description_derived[
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
    )

    classified_ids = set(
        combined[
            "Bill_id"
        ]
    )

    missing_ids = (
        source_ids
        -
        classified_ids
    )

    tier_counts = (
        combined[
            [
                "Bill_id",
                "classification",
            ]
        ]
        .drop_duplicates()
        .groupby(
            "Bill_id"
        )[
            "classification"
        ]
        .nunique()
    )

    multiple_tiers = (
        tier_counts[
            tier_counts
            !=
            1
        ]
    )

    print(
        f"\nTotal LIS bills: {total_bills:,}"
    )

    print(
        "\nOfficial LIS subject:"
    )

    print(
        f"{official_bills:,}"
    )

    print(
        "\nDerived from LIS bill summary:"
    )

    print(
        f"{summary_bills:,}"
    )

    print(
        "\nDerived from LIS bill description:"
    )

    print(
        f"{description_bills:,}"
    )

    print(
        "\nUnclassified:"
    )

    print(
        f"{unclassified_bills:,}"
    )

    print(
        "\nBills missing from classification table:"
    )

    print(
        len(
            missing_ids
        )
    )

    if missing_ids:

        raise ValueError(
            "Some bills have no classification row."
        )

    if len(
        multiple_tiers
    ) > 0:

        raise ValueError(
            "Some bills belong to more than one "
            "classification provenance tier."
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
        "\nOK Every bill has one permitted "
        "classification provenance tier."
    )


# =========================================================
# TOPIC COVERAGE
# =========================================================

def build_topic_coverage(
    year,
    bill_lookup,
    bill_topic_lookup,
):

    bill_classes = (
        bill_topic_lookup[
            [
                "Bill_id",
                "classification",
            ]
        ]
        .drop_duplicates()
    )

    counts = (
        bill_classes[
            "classification"
        ]
        .value_counts()
        .reindex(
            [
                "Official LIS subject",
                "Derived from LIS bill summary",
                "Derived from LIS bill description",
                "Unclassified",
            ],
            fill_value=0,
        )
    )

    total_bills = (
        bill_lookup[
            "Bill_id"
        ]
        .nunique()
    )

    result = (
        counts
        .rename_axis(
            "classification"
        )
        .reset_index(
            name="bill_count"
        )
    )

    result.insert(
        0,
        "year",
        year,
    )

    result[
        "total_bills"
    ] = (
        total_bills
    )

    result[
        "bill_percentage"
    ] = (
        (
            result[
                "bill_count"
            ]
            /
            total_bills
            *
            100
        )
        .round(
            4
        )
        if total_bills
        else
        0.0
    )

    return result


# =========================================================
# MEMBER + RECORDED VOTE + TOPIC
#
# THIS IS THE CANONICAL ANALYTICAL GRAIN.
#
# One row means:
#
#     one House member
#     + one actual LIS vote event
#     + one analytical topic.
#
#
# WHY PROVENANCE IS NOT PART OF THE GRAIN
# ---------------------------------------
#
# Imagine one block vote:
#
#     HB1 -> Education -> Official LIS subject
#     HB2 -> Education -> Derived from summary
#
# The member cast one Education-related recorded vote.
#
# Therefore this table contains one Education row.
#
# The underlying classification sources are retained in:
#
#     topic_provenance
#
# and the exact bill-level provenance remains available in:
#
#     bill_topic_lookup_<year>.csv
# =========================================================

def build_member_vote_topic(
    vote_fact,
    vote_bill_bridge,
    bill_topic_lookup,
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
            ]
            .drop_duplicates(
                subset=[
                    "vote_id",
                    "Bill_id",
                ]
            ),
            on="vote_id",
            how="inner",
        )
    )

    vote_topic = (
        vote_bill.merge(
            bill_topic_lookup[
                [
                    "Bill_id",
                    "topic_name",
                    "classification",
                ]
            ],
            on="Bill_id",
            how="inner",
        )
    )

    grain = [
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
    ]

    member_vote_topic = (
        vote_topic[
            grain
            +
            [
                "classification",
            ]
        ]
        .groupby(
            grain,
            as_index=False,
            dropna=False,
        )
        .agg(
            topic_provenance=(
                "classification",
                combine_unique_text,
            )
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

    # -----------------------------------------------------
    # HARD CHECK
    #
    # No duplicate analytical rows should remain.
    # -----------------------------------------------------

    duplicates = (
        member_vote_topic
        .duplicated(
            subset=[
                "year",
                "vote_id",
                "member_id",
                "topic_name",
            ],
            keep=False,
        )
    )

    if duplicates.any():

        raise ValueError(
            "member_vote_topic contains duplicate "
            "member + vote + topic rows."
        )

    return member_vote_topic


# =========================================================
# DELEGATE + TOPIC SUMMARY
# =========================================================

def build_delegate_topic_summary(
    member_vote_topic,
):

    summary = (
        member_vote_topic
        .groupby(
            [
                "member_id",
                "MBR_NAME",
                "party",
                "topic_name",
            ],
            as_index=False,
        )
        .agg(
            topic_vote_events=(
                "vote_id",
                "nunique",
            ),

            eligible_topic_events=(
                "eligible_cross_party",
                "sum",
            ),

            party_break_events=(
                "broke_with_party",
                "sum",
            ),

            cross_party_events=(
                "cross_party",
                "sum",
            ),
        )
    )

    summary[
        "cross_party_pct"
    ] = 0.0

    usable = (
        summary[
            "eligible_topic_events"
        ]
        >
        0
    )

    summary.loc[
        usable,
        "cross_party_pct",
    ] = (
        summary.loc[
            usable,
            "cross_party_events",
        ]
        /
        summary.loc[
            usable,
            "eligible_topic_events",
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
            ],
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# SPONSORSHIP DATA
# =========================================================

def build_sponsor_fact(year):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "Sponsors.csv"
    )

    sponsors = pd.read_csv(
        path,
        dtype=str,
    )

    required = {
        "MEMBER_NAME",
        "MEMBER_ID",
        "BILL_NUMBER",
        "PATRON_TYPE",
    }

    missing = (
        required
        -
        set(
            sponsors.columns
        )
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: {missing}"
        )

    sponsors = sponsors.rename(
        columns={
            "MEMBER_NAME":
                "member_name",

            "MEMBER_ID":
                "member_id",

            "BILL_NUMBER":
                "Bill_id",

            "PATRON_TYPE":
                "patron_type",
        }
    )

    for column in [
        "member_name",
        "member_id",
        "Bill_id",
        "patron_type",
    ]:

        sponsors[
            column
        ] = (
            sponsors[
                column
            ]
            .fillna("")
            .str.strip()
        )

    sponsors[
        "member_id"
    ] = (
        sponsors[
            "member_id"
        ]
        .str.upper()
    )

    sponsors[
        "Bill_id"
    ] = (
        sponsors[
            "Bill_id"
        ]
        .str.upper()
    )

    parsed = (
        sponsors[
            "patron_type"
        ]
        .str.extract(
            r"^\s*(\d+)\s*-\s*(.*?)\s*$"
        )
    )

    sponsors[
        "patron_order"
    ] = (
        pd.to_numeric(
            parsed[0],
            errors="coerce",
        )
        .astype(
            "Int64"
        )
    )

    sponsors[
        "patron_role"
    ] = (
        parsed[1]
        .fillna("")
        .str.strip()
    )

    sponsors[
        "is_chief_patron"
    ] = (
        sponsors[
            "patron_role"
        ]
        .eq(
            "Chief Patron"
        )
    )

    sponsors[
        "is_chief_co_patron"
    ] = (
        sponsors[
            "patron_role"
        ]
        .isin(
            [
                "Chief Co-Patron",
                "Incorporated Chief Co-Patron",
            ]
        )
    )

    sponsors[
        "is_co_patron"
    ] = (
        sponsors[
            "patron_role"
        ]
        .eq(
            "Co-Patron"
        )
    )

    sponsors.insert(
        0,
        "year",
        year,
    )

    return (
        sponsors[
            [
                "year",
                "member_id",
                "member_name",
                "Bill_id",
                "patron_type",
                "patron_order",
                "patron_role",
                "is_chief_patron",
                "is_chief_co_patron",
                "is_co_patron",
            ]
        ]
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )


def build_sponsor_vote_behavior(
    sponsor_fact,
    vote_fact,
    vote_bill_bridge,
):

    bill_votes = (
        vote_bill_bridge[
            [
                "vote_id",
                "Bill_id",
            ]
        ]
        .drop_duplicates()
    )

    sponsor_votes = (
        sponsor_fact.merge(
            bill_votes,
            on="Bill_id",
            how="inner",
            validate="many_to_many",
        )
    )

    base_vote_columns = [
        "vote_id",
        "member_id",
        "vote",
        "broke_with_party",
        "cross_party",
    ]

    optional_vote_columns = [
        column
        for column
        in [
            "vote_date",
            "chamber",
            "party",
        ]
        if column
        in vote_fact.columns
    ]

    sponsor_votes = sponsor_votes.merge(
        vote_fact[
            base_vote_columns
            +
            optional_vote_columns
        ],
        on=[
            "vote_id",
            "member_id",
        ],
        how="inner",
        validate="many_to_one",
    )

    return (
        sponsor_votes
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )


# =========================================================
# COMMITTEES
# =========================================================

def build_committees(year):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "Committees.csv"
    )

    committees = pd.read_csv(
        path,
        dtype=str,
    )

    required = {
        "CHAMBER",
        "COM_NAME",
        "COM_COMNO",
    }

    missing = (
        required
        -
        set(
            committees.columns
        )
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: {missing}"
        )

    committees = committees.rename(
        columns={
            "CHAMBER":
                "chamber",

            "COM_NAME":
                "committee_name",

            "COM_COMNO":
                "committee_id",
        }
    )

    for column in [
        "chamber",
        "committee_name",
        "committee_id",
    ]:

        committees[
            column
        ] = (
            committees[
                column
            ]
            .fillna("")
            .str.strip()
        )

    committees.insert(
        0,
        "year",
        year,
    )

    return (
        committees[
            [
                "year",
                "committee_id",
                "committee_name",
                "chamber",
            ]
        ]
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )


def build_committee_members(
    year,
    committees,
):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "CommitteeMembers.csv"
    )

    memberships = pd.read_csv(
        path,
        dtype=str,
    )

    required = {
        "CMB_COMNO",
        "CMB_MBRNO",
    }

    missing = (
        required
        -
        set(
            memberships.columns
        )
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: {missing}"
        )

    memberships = memberships.rename(
        columns={
            "CMB_COMNO":
                "committee_id",

            "CMB_MBRNO":
                "member_id",
        }
    )

    for column in [
        "committee_id",
        "member_id",
    ]:

        memberships[
            column
        ] = (
            memberships[
                column
            ]
            .fillna("")
            .str.strip()
            .str.upper()
        )

    member_path = (
        RAW_ROOT
        /
        str(year)
        /
        "Members.csv"
    )

    members = pd.read_csv(
        member_path,
        dtype=str,
    )

    member_names = (
        members[
            [
                "MBR_MBRNO",
                "MBR_NAME",
            ]
        ]
        .rename(
            columns={
                "MBR_MBRNO":
                    "member_id",

                "MBR_NAME":
                    "member_name",
            }
        )
    )

    member_names[
        "member_id"
    ] = (
        member_names[
            "member_id"
        ]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    member_names[
        "member_name"
    ] = (
        member_names[
            "member_name"
        ]
        .fillna("")
        .str.strip()
    )

    member_names = (
        member_names
        .drop_duplicates(
            subset=[
                "member_id"
            ]
        )
    )

    result = (
        memberships.merge(
            committees.drop(
                columns=[
                    "year"
                ]
            ),
            on="committee_id",
            how="left",
            validate="many_to_one",
        )
        .merge(
            member_names,
            on="member_id",
            how="left",
            validate="many_to_one",
        )
    )

    result.insert(
        0,
        "year",
        year,
    )

    return (
        result[
            [
                "year",
                "committee_id",
                "committee_name",
                "chamber",
                "member_id",
                "member_name",
            ]
        ]
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )


# =========================================================
# VOTE STATEMENTS
#
# The recorded vote remains unchanged.
#
# An explicit "intended to vote..." statement is retained as
# separate contextual evidence.
# =========================================================

def build_vote_statement_fact(year):

    path = (
        RAW_ROOT
        /
        str(year)
        /
        "VoteStatements.csv"
    )

    statements = pd.read_csv(
        path,
        dtype=str,
    )

    required = {
        "Bill_ID",
        "History_RefID",
        "Vote_Date",
        "Legislator_ID",
        "Recorded_Vote",
        "Vote_Statement",
    }

    missing = (
        required
        -
        set(
            statements.columns
        )
    )

    if missing:

        raise ValueError(
            f"{path} missing columns: {missing}"
        )

    statements = statements.rename(
        columns={
            "Bill_ID":
                "Bill_id",

            "History_RefID":
                "vote_id",

            "Vote_Date":
                "vote_date",

            "Legislator_ID":
                "member_id",

            "Recorded_Vote":
                "recorded_vote",

            "Vote_Statement":
                "vote_statement",
        }
    )

    for column in (
        statements.columns
    ):

        statements[
            column
        ] = (
            statements[
                column
            ]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    statements[
        "Bill_id"
    ] = (
        statements[
            "Bill_id"
        ]
        .str.upper()
    )

    statements[
        "member_id"
    ] = (
        statements[
            "member_id"
        ]
        .str.upper()
    )

    statements[
        "recorded_vote"
    ] = (
        statements[
            "recorded_vote"
        ]
        .str.upper()
    )

    intended = (
        statements[
            "vote_statement"
        ]
        .str.extract(
            (
                r"(?i)\bintended\s+to\s+"
                r"vote\s+(yea|yes|nay|no)\b"
            ),
            expand=False,
        )
        .fillna("")
        .str.lower()
    )

    statements[
        "intended_vote"
    ] = (
        intended
        .map(
            {
                "yea":
                    "Y",

                "yes":
                    "Y",

                "nay":
                    "N",

                "no":
                    "N",
            }
        )
        .fillna("")
    )

    statements[
        "intended_vote_explicit"
    ] = (
        statements[
            "intended_vote"
        ]
        .ne("")
    )

    statements.insert(
        0,
        "year",
        year,
    )

    return (
        statements[
            [
                "year",
                "Bill_id",
                "vote_id",
                "vote_date",
                "member_id",
                "recorded_vote",
                "vote_statement",
                "intended_vote",
                "intended_vote_explicit",
            ]
        ]
        .drop_duplicates()
        .reset_index(
            drop=True
        )
    )


# =========================================================
# TERMINAL REPORTS
# =========================================================

def print_delegate_summary(
    year,
    delegate_summary,
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
        .head(
            25
        )
        .to_string(
            index=False,
            float_format=
                lambda value:
                    f"{value:.2f}",
        )
    )


def print_topic_summary(
    year,
    delegate_topic_summary,
):

    print(
        "\n" + "=" * 60
    )

    print(
        f"{year} DELEGATE x LIS TOPIC SUMMARY"
    )

    print(
        "=" * 60
    )

    classified = (
        delegate_topic_summary[
            delegate_topic_summary[
                "topic_name"
            ]
            !=
            "Unclassified"
        ]
        .copy()
    )

    print(
        "\nTop 40 classified delegate-topic combinations:"
    )

    print(
        classified[
            [
                "member_id",
                "MBR_NAME",
                "party",
                "topic_name",
                "topic_vote_events",
                "eligible_topic_events",
                "cross_party_events",
                "cross_party_pct",
            ]
        ]
        .head(
            40
        )
        .to_string(
            index=False,
            float_format=
                lambda value:
                    f"{value:.2f}",
        )
    )


# =========================================================
# SAVE DURABLE PRODUCTION OUTPUTS
#
# Random QA samples are intentionally NOT created here.
# =========================================================

def save_outputs(
    year,
    vote_fact,
    vote_bill_bridge,
    bill_lookup,
    subject_hierarchy,
    summary_lookup,
    official,
    summary_derived,
    description_derived,
    unclassified,
    bill_topic_lookup,
    topic_coverage,
    sponsor_fact,
    committees,
    committee_members,
    vote_statement_fact,
    bill_history,
    sponsor_vote_behavior,
    delegate_summary,
    member_vote_topic,
    delegate_topic_summary,
):

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    outputs = {

        "vote_fact":
            (
                PROCESSED_ROOT
                /
                f"vote_fact_{year}.csv"
            ),

        "vote_bill_bridge":
            (
                PROCESSED_ROOT
                /
                f"vote_bill_bridge_{year}.csv"
            ),

        "bill_lookup":
            (
                PROCESSED_ROOT
                /
                f"bill_lookup_{year}.csv"
            ),

        "subject_hierarchy":
            (
                PROCESSED_ROOT
                /
                f"lis_subject_hierarchy_{year}.csv"
            ),

        "summary_lookup":
            (
                PROCESSED_ROOT
                /
                f"bill_summary_lookup_{year}.csv"
            ),

        "official_lis_subjects":
            (
                PROCESSED_ROOT
                /
                f"official_lis_subjects_{year}.csv"
            ),

        "summary_derived":
            (
                PROCESSED_ROOT
                /
                f"derived_from_lis_bill_summary_{year}.csv"
            ),

        "description_derived":
            (
                PROCESSED_ROOT
                /
                f"derived_from_lis_bill_description_{year}.csv"
            ),

        "unclassified":
            (
                PROCESSED_ROOT
                /
                f"unclassified_bills_{year}.csv"
            ),

        "bill_topic_lookup":
            (
                PROCESSED_ROOT
                /
                f"bill_topic_lookup_{year}.csv"
            ),

        "topic_coverage":
            (
                PROCESSED_ROOT
                /
                f"topic_coverage_{year}.csv"
            ),

        "sponsor_fact":
            (
                PROCESSED_ROOT
                /
                f"sponsor_fact_{year}.csv"
            ),

        "committees":
            (
                PROCESSED_ROOT
                /
                f"committees_{year}.csv"
            ),

        "committee_members":
            (
                PROCESSED_ROOT
                /
                f"committee_members_{year}.csv"
            ),

        "vote_statement_fact":
            (
                PROCESSED_ROOT
                /
                f"vote_statement_fact_{year}.csv"
            ),

        "bill_history":
            (
                PROCESSED_ROOT
                /
                f"bill_history_{year}.csv"
            ),

        "sponsor_vote_behavior":
            (
                PROCESSED_ROOT
                /
                f"sponsor_vote_behavior_{year}.csv"
            ),

        "delegate_behavior":
            (
                PROCESSED_ROOT
                /
                f"delegate_behavior_{year}.csv"
            ),

        "member_vote_topic":
            (
                PROCESSED_ROOT
                /
                f"member_vote_topic_{year}.csv"
            ),

        "delegate_topic_behavior":
            (
                PROCESSED_ROOT
                /
                f"delegate_topic_behavior_{year}.csv"
            ),
    }

    write_csv(
        vote_fact,
        outputs[
            "vote_fact"
        ],
    )

    vote_bill_bridge.to_csv(
        outputs[
            "vote_bill_bridge"
        ],
        index=False,
    )

    bill_lookup.to_csv(
        outputs[
            "bill_lookup"
        ],
        index=False,
    )

    subject_hierarchy.to_csv(
        outputs[
            "subject_hierarchy"
        ],
        index=False,
    )

    summary_lookup.to_csv(
        outputs[
            "summary_lookup"
        ],
        index=False,
    )

    official.to_csv(
        outputs[
            "official_lis_subjects"
        ],
        index=False,
    )

    summary_derived.to_csv(
        outputs[
            "summary_derived"
        ],
        index=False,
    )

    description_derived.to_csv(
        outputs[
            "description_derived"
        ],
        index=False,
    )

    unclassified.to_csv(
        outputs[
            "unclassified"
        ],
        index=False,
    )

    bill_topic_lookup.to_csv(
        outputs[
            "bill_topic_lookup"
        ],
        index=False,
    )

    topic_coverage.to_csv(
        outputs[
            "topic_coverage"
        ],
        index=False,
    )

    sponsor_fact.to_csv(
        outputs[
            "sponsor_fact"
        ],
        index=False,
    )

    committees.to_csv(
        outputs[
            "committees"
        ],
        index=False,
    )

    committee_members.to_csv(
        outputs[
            "committee_members"
        ],
        index=False,
    )

    vote_statement_fact.to_csv(
        outputs[
            "vote_statement_fact"
        ],
        index=False,
    )

    write_csv(
        bill_history,
        outputs[
            "bill_history"
        ],
    )

    write_csv(
        sponsor_vote_behavior,
        outputs[
            "sponsor_vote_behavior"
        ],
    )

    delegate_summary.to_csv(
        outputs[
            "delegate_behavior"
        ],
        index=False,
    )

    member_vote_topic.to_csv(
        outputs[
            "member_vote_topic"
        ],
        index=False,
    )

    delegate_topic_summary.to_csv(
        outputs[
            "delegate_topic_behavior"
        ],
        index=False,
    )

    return outputs


# =========================================================
# RUN ONE YEAR
#
# Everything needed for one session lives in this function.
#
# The main function below simply calls it once for every
# configured year.
#
# This is what the previous script was missing.
# =========================================================

def run_year(year):

    print(
        "\n" + "#" * 78
    )

    print(
        f"PROCESSING LIS SESSION: {year}"
    )

    print(
        "#" * 78
    )

    # -----------------------------------------------------
    # 1. RECORDED VOTES
    # -----------------------------------------------------

    votes = parse_vote_file(
        year
    )

    # -----------------------------------------------------
    # 2. MEMBER INFORMATION
    # -----------------------------------------------------

    vote_fact = add_member_names(
        year,
        votes,
    )

    # -----------------------------------------------------
    # 3. PARTY
    # -----------------------------------------------------

    vote_fact = add_party_info(
        year,
        vote_fact,
    )

    # -----------------------------------------------------
    # 4. MEMBER METADATA RECOVERY
    # -----------------------------------------------------

    vote_fact = reconcile_member_metadata(
        year,
        vote_fact,
    )

    # -----------------------------------------------------
    # 5. PARTY VALIDATION
    # -----------------------------------------------------

    validate_party_join(
        year,
        vote_fact,
    )

    # -----------------------------------------------------
    # 6. PARTY POSITIONS AND CROSS-PARTY BEHAVIOR
    # -----------------------------------------------------

    party_positions = (
        calculate_party_positions(
            vote_fact
        )
    )

    vote_fact = (
        add_own_party_position(
            vote_fact,
            party_positions,
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
            party_positions,
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
    # 7. OVERALL HOUSE DELEGATE BEHAVIOR
    # -----------------------------------------------------

    delegate_summary = (
        build_member_behavior_summary(
            vote_fact
        )
    )

    print_delegate_summary(
        year,
        delegate_summary,
    )

    # -----------------------------------------------------
    # 8. VOTE -> BILL
    # -----------------------------------------------------

    vote_bill_bridge = (
        build_vote_bill_bridge(
            year,
            vote_fact,
        )
    )

    bill_history = (
        build_bill_history(
            year
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
    # 10. TOPIC INPUTS
    # -----------------------------------------------------

    subject_hierarchy = (
        build_lis_subject_hierarchy(
            year
        )
    )

    summary_lookup = (
        build_bill_summary_lookup(
            year
        )
    )

    # -----------------------------------------------------
    # 11. CLASSIFY BILLS
    # -----------------------------------------------------

    (
        official,
        summary_derived,
        description_derived,
        unclassified,
        bill_topic_lookup,
    ) = (
        build_bill_topic_lookup(
            year,
            bill_lookup,
            hierarchy=
                subject_hierarchy,
            summary_lookup=
                summary_lookup,
        )
    )

    validate_topic_classifications(
        bill_lookup,
        official,
        summary_derived,
        description_derived,
        unclassified,
        bill_topic_lookup,
    )

    topic_coverage = (
        build_topic_coverage(
            year,
            bill_lookup,
            bill_topic_lookup,
        )
    )

    # -----------------------------------------------------
    # 12. OTHER OFFICIAL LIS EVIDENCE
    #
    # These do not change topic classification.
    # -----------------------------------------------------

    sponsor_fact = (
        build_sponsor_fact(
            year
        )
    )

    sponsor_vote_behavior = (
        build_sponsor_vote_behavior(
            sponsor_fact,
            vote_fact,
            vote_bill_bridge,
        )
    )

    committees = (
        build_committees(
            year
        )
    )

    committee_members = (
        build_committee_members(
            year,
            committees,
        )
    )

    vote_statement_fact = (
        build_vote_statement_fact(
            year
        )
    )

    # -----------------------------------------------------
    # 13. MEMBER + VOTE + TOPIC
    # -----------------------------------------------------

    member_vote_topic = (
        build_member_vote_topic(
            vote_fact,
            vote_bill_bridge,
            bill_topic_lookup,
        )
    )

    # -----------------------------------------------------
    # 14. DELEGATE + TOPIC SUMMARY
    # -----------------------------------------------------

    delegate_topic_summary = (
        build_delegate_topic_summary(
            member_vote_topic
        )
    )

    print_topic_summary(
        year,
        delegate_topic_summary,
    )

    # -----------------------------------------------------
    # 15. SAVE
    # -----------------------------------------------------

    outputs = (
        save_outputs(
            year,
            vote_fact,
            vote_bill_bridge,
            bill_lookup,
            subject_hierarchy,
            summary_lookup,
            official,
            summary_derived,
            description_derived,
            unclassified,
            bill_topic_lookup,
            topic_coverage,
            sponsor_fact,
            committees,
            committee_members,
            vote_statement_fact,
            bill_history,
            sponsor_vote_behavior,
            delegate_summary,
            member_vote_topic,
            delegate_topic_summary,
        )
    )

    # -----------------------------------------------------
    # SESSION STATUS
    # -----------------------------------------------------

    print(
        "\n" + "=" * 60
    )

    print(
        f"{year} PIPELINE STATUS"
    )

    print(
        "=" * 60
    )

    print(
        f"\nVote fact rows: "
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
        f"Derived from LIS bill summary bills: "
        f"{summary_derived['Bill_id'].nunique():,}"
    )

    print(
        f"Derived from LIS bill description bills: "
        f"{description_derived['Bill_id'].nunique():,}"
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
        "Member-vote-topic grain: "
        "year + vote_id + member_id + topic_name"
    )

    print(
        f"Delegate-topic summary rows: "
        f"{len(delegate_topic_summary):,}"
    )

    print(
        "\nFiles saved:"
    )

    for path in (
        outputs.values()
    ):

        print(
            path
        )

    print(
        f"\n{year} finished."
    )

    return {
        "year":
            year,

        "vote_fact":
            vote_fact,

        "delegate_behavior":
            delegate_summary,

        "bill_topic_lookup":
            bill_topic_lookup,

        "member_vote_topic":
            member_vote_topic,

        "delegate_topic_behavior":
            delegate_topic_summary,

        "outputs":
            outputs,
    }


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "LIS pipeline started:"
    )

    print(
        datetime.now()
    )

    print(
        "\nConfigured session years:"
    )

    print(
        list(
            YEARS
        )
    )

    print(
        "\nSession years being processed:"
    )

    print(
        ANALYSIS_YEARS
    )

    # -----------------------------------------------------
    # OPTIONAL DOWNLOAD
    #
    # Only download years we are actually processing.
    # -----------------------------------------------------

    if RUN_DOWNLOAD:

        print(
            "\nRUN_DOWNLOAD = True"
        )

        print(
            "Refreshing official LIS files."
        )

        for year in (
            ANALYSIS_YEARS
        ):

            download_year(
                year
            )

    else:

        print(
            "\nRUN_DOWNLOAD = False"
        )

        print(
            "Using existing files in data/raw/"
        )

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = {}

    # -----------------------------------------------------
    # THIS IS THE IMPORTANT FIX.
    #
    # The old script did:
    #
    #     year = ANALYSIS_YEAR
    #
    # and therefore processed only one session.
    #
    # We now run the same production pipeline independently
    # for every configured analysis year.
    # -----------------------------------------------------

    for year in (
        ANALYSIS_YEARS
    ):

        results[
            year
        ] = run_year(
            year
        )

    # -----------------------------------------------------
    # FINAL ALL-YEARS STATUS
    # -----------------------------------------------------

    print(
        "\n" + "#" * 78
    )

    print(
        "ALL REQUESTED LIS SESSIONS COMPLETE"
    )

    print(
        "#" * 78
    )

    for year in (
        ANALYSIS_YEARS
    ):

        result = (
            results[
                year
            ]
        )

        print(
            f"\n{year}:"
        )

        print(
            "  vote rows: "
            f"{len(result['vote_fact']):,}"
        )

        print(
            "  member-vote-topic rows: "
            f"{len(result['member_vote_topic']):,}"
        )

        print(
            "  delegate-topic rows: "
            f"{len(result['delegate_topic_behavior']):,}"
        )

    print(
        "\nFinished."
    )


if __name__ == "__main__":

    main()
