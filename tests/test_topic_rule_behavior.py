"""
Reviewed subject-validity tests.

These tests are different from structural pipeline tests.

STRUCTURAL TEST:
    Did the code follow the classification rule?

VALIDITY TEST:
    Does the resulting subject assignment make substantive sense?

Both kinds of tests are necessary.

This file focuses on known false-positive risks from broad words such as:

    education
    students
    high school
    medical
    employees
    workforce
    locality
    revenue
    coverage
    electronically
    commercial
    minors

The objective is NOT to force every realistic sentence into exactly one
topic.

The objective is to protect clear true positives and clear false
positives.
"""

import pytest

from lis_pipeline import derive_topics_from_description


# =========================================================
# HELPER
# =========================================================

def topics_for(description):

    return set(
        derive_topics_from_description(
            description
        )
    )


# =========================================================
# CLEAR TRUE POSITIVES
#
# These examples describe situations where the subject is
# substantively central to the text.
# =========================================================

@pytest.mark.parametrize(
    "description,expected_topics",
    [

        (
            "Public schools; teacher licensure and student instruction.",
            {
                "Education",
            },
        ),

        (
            "Board of Education; high school graduation requirements.",
            {
                "Education",
            },
        ),

        (
            "Hospitals; patient discharge and nurse staffing requirements.",
            {
                "Health and Healthcare",
            },
        ),

        (
            "Medicaid eligibility and hospital reimbursement requirements.",
            {
                "Health and Healthcare",
            },
        ),

        (
            "Minimum wage; employer obligations and paid leave.",
            {
                "Labor and Employment",
            },
        ),

        (
            "Employees; minimum wage and overtime requirements.",
            {
                "Labor and Employment",
            },
        ),

        (
            "Local governments; zoning appeals and municipal authority.",
            {
                "Local Government",
            },
        ),

        (
            "Town charter; amending the charter and municipal powers.",
            {
                "Local Government",
            },
        ),

        (
            "Artificial intelligence; data privacy and automated decision systems.",
            {
                "Technology and Data",
            },
        ),

        (
            "Income tax; refundable tax credit.",
            {
                "Taxes and Revenue",
            },
        ),

        (
            "Individual income tax credit; eligibility and refundability.",
            {
                "Taxes and Revenue",
            },
        ),

        (
            "Motor vehicle insurance; minimum liability coverage.",
            {
                "Transportation",
                "Insurance",
            },
        ),

        (
            "Small businesses; consumer protection and commercial licensing.",
            {
                "Business and Commerce",
            },
        ),

        (
            "Vehicle operation; unlicensed driver; misdemeanor penalty.",
            {
                "Transportation",
                "Criminal Justice",
            },
        ),

        (
            "Residential landlord and tenant; eviction procedures.",
            {
                "Housing",
            },
        ),

        (
            "Absentee ballots; polling places and voter registration.",
            {
                "Elections and Voting",
            },
        ),

        (
            "Public institutions of higher education; tuition and student fees.",
            {
                "Higher Education",
            },
        ),

        (
            "Data centers; industrial zoning and electric load requirements.",
            {
                "Data Centers",
            },
        ),

        (
            "Constitutional amendment; first reference.",
            {
                "Constitutional Amendments",
            },
        ),

        (
            "Virginia Retirement System; enhanced retirement benefits.",
            {
                "Pensions, Benefits, and Retirement",
            },
        ),

        (
            "Charitable gaming; regulations for poker tournaments.",
            {
                "Gambling, Lotteries, Etc.",
            },
        ),

        (
            "Virginia National Guard; biennial training requirements.",
            {
                "Armed Forces",
            },
        ),

        (
            "Uniform Trust Code; qualified trustee requirements.",
            {
                "Wills, Trusts, and Fiduciaries",
            },
        ),

        (
            "Real property; public hearing required for conveyance.",
            {
                "Property and Conveyances",
            },
        ),

        (
            "Consultation with federally recognized tribes; permits and reviews.",
            {
                "Indian Tribes",
            },
        ),

    ],
)
def test_clear_subject_language_includes_expected_topics(
    description,
    expected_topics,
):

    actual = topics_for(
        description
    )

    assert expected_topics <= actual


# =========================================================
# CEREMONIAL RESOLUTIONS
#
# A commendation can mention schools, hospitals, employees,
# communities, or professions without becoming policy about
# those subjects.
# =========================================================

@pytest.mark.parametrize(
    "description",
    [

        (
            "Commending the Blacksburg High School "
            "girls' track and field team."
        ),

        (
            "Commending the Christiansburg High School "
            "softball team."
        ),

        (
            "Commending the Lake Braddock Secondary School "
            "robotics team."
        ),

        (
            "Celebrating the life of Dr. Jane Doe, "
            "a beloved physician."
        ),

        (
            "Commending the employees of a local family business "
            "for their charitable service."
        ),

    ],
)
def test_ceremonial_resolutions_get_ceremonial_topic(
    description,
):

    actual = topics_for(
        description
    )

    assert (
        "Commendations and Commemorations"
        in actual
    )


@pytest.mark.parametrize(
    "description,excluded_topic",
    [

        (
            "Commending the Jefferson High School championship team.",
            "Education",
        ),

        (
            "Celebrating the life of a longtime hospital volunteer.",
            "Health and Healthcare",
        ),

        (
            "Commending the employees of a local business.",
            "Labor and Employment",
        ),

        (
            "Commending a locality for hosting a community festival.",
            "Local Government",
        ),

    ],
)
def test_ceremonial_mentions_do_not_create_incidental_policy_topics(
    description,
    excluded_topic,
):

    actual = topics_for(
        description
    )

    assert excluded_topic not in actual


# =========================================================
# TECHNOLOGY FALSE POSITIVES
#
# "electronically" often describes HOW something is sent or
# filed, not technology policy.
# =========================================================

@pytest.mark.parametrize(
    "description",
    [

        "Court notice may be sent electronically in a civil action.",

        "The application may be submitted electronically to the agency.",

        "A locality may transmit the annual report electronically.",

        (
            "Civil procedure; discovery of electronically stored "
            "records."
        ),

    ],
)
def test_electronically_alone_does_not_imply_technology_policy(
    description,
):

    assert (
        "Technology and Data"
        not in topics_for(
            description
        )
    )


# =========================================================
# HEALTH FALSE POSITIVES
#
# "medical" can be incidental when describing damages,
# evidence, reimbursement, or another legal issue.
# =========================================================

@pytest.mark.parametrize(
    "description",
    [

        "A criminal restitution order may include medical expenses.",

        (
            "Civil damages may include reimbursement for "
            "medical expenses."
        ),

        (
            "Evidence of medical expenses may be admitted "
            "in a civil action."
        ),

    ],
)
def test_incidental_medical_reference_does_not_create_health_topic(
    description,
):

    assert (
        "Health and Healthcare"
        not in topics_for(
            description
        )
    )


# =========================================================
# LABOR FALSE POSITIVES
#
# Merely mentioning employees does not necessarily make the
# bill employment policy.
# =========================================================

@pytest.mark.parametrize(
    "description",
    [

        (
            "A state procurement contract requires designated "
            "employees to sign the form."
        ),

        (
            "Employees of the agency may access the confidential "
            "database for administrative purposes."
        ),

        (
            "A licensed business shall designate one employee "
            "to maintain the records."
        ),

    ],
)
def test_employee_mentions_do_not_automatically_create_labor_topic(
    description,
):

    assert (
        "Labor and Employment"
        not in topics_for(
            description
        )
    )


# =========================================================
# LOCAL GOVERNMENT FALSE POSITIVES
#
# "locality" is especially risky because many statewide
# policies simply require notice to or action by a locality.
# =========================================================

@pytest.mark.parametrize(
    "description",
    [

        "A highway project shall notify each affected locality.",

        (
            "The Department of Transportation shall provide "
            "information to each locality crossed by the route."
        ),

        (
            "A state grant recipient shall notify the locality "
            "where the project is located."
        ),

    ],
)
def test_incidental_locality_reference_does_not_create_local_government(
    description,
):

    assert (
        "Local Government"
        not in topics_for(
            description
        )
    )


# =========================================================
# TAX / REVENUE FALSE POSITIVES
#
# "revenue" can describe money flowing into an account
# without the bill actually changing taxes or revenue policy.
# =========================================================

@pytest.mark.parametrize(
    "description",
    [

        (
            "Budget bill; deposits nongeneral fund revenue "
            "into an existing account."
        ),

        (
            "The agency shall report annual fee revenue "
            "to the General Assembly."
        ),

        (
            "Program administration shall be supported by "
            "existing revenue in the fund."
        ),

    ],
)
def test_incidental_revenue_language_does_not_create_tax_topic(
    description,
):

    assert (
        "Taxes and Revenue"
        not in topics_for(
            description
        )
    )


# =========================================================
# INSURANCE FALSE POSITIVES
#
# "coverage" is not always insurance coverage.
# =========================================================

@pytest.mark.parametrize(
    "description",
    [

        "Broadband coverage mapping for underserved areas.",

        "News coverage of the public meeting may be recorded.",

        (
            "The report shall include statewide geographic "
            "coverage of the program."
        ),

    ],
)
def test_noninsurance_coverage_does_not_create_insurance_topic(
    description,
):

    assert (
        "Insurance"
        not in topics_for(
            description
        )
    )


# =========================================================
# BUSINESS FALSE POSITIVES
#
# "commercial" can be a generic adjective.
# =========================================================

@pytest.mark.parametrize(
    "description",
    [

        "A public school shall use commercially available textbooks.",

        "Commercial motor vehicles; highway safety requirements.",

        (
            "Commercial fishing licenses; saltwater fishing "
            "requirements."
        ),

    ],
)
def test_generic_commercial_language_does_not_automatically_create_business(
    description,
):

    assert (
        "Business and Commerce"
        not in topics_for(
            description
        )
    )


# =========================================================
# FAMILY / CHILDREN FALSE POSITIVES
#
# "minor" can describe age/status in another substantive
# policy area without making the bill family policy.
# =========================================================

@pytest.mark.parametrize(
    "description",
    [

        "Vehicle operation by an unlicensed minor; misdemeanor penalty.",

        (
            "A minor operating a motor vehicle without a license "
            "is subject to a traffic penalty."
        ),

        (
            "Alcoholic beverage possession by a minor; criminal penalty."
        ),

    ],
)
def test_minor_reference_does_not_automatically_create_family_topic(
    description,
):

    assert (
        "Family and Children"
        not in topics_for(
            description
        )
    )


# =========================================================
# EDUCATION FALSE POSITIVES
#
# School words can occur in ceremonies or location names.
# =========================================================

@pytest.mark.parametrize(
    "description",
    [

        "Commending the Jefferson High School championship team.",

        (
            "Designating a portion of Route 460 near Central High School "
            "as a memorial highway."
        ),

    ],
)
def test_school_reference_does_not_always_mean_education_policy(
    description,
):

    assert (
        "Education"
        not in topics_for(
            description
        )
    )


# =========================================================
# TRUE MULTI-TOPIC EXAMPLES
#
# Multi-topic classification is allowed when several policy
# areas are genuinely substantive.
# =========================================================

def test_multitopic_school_transportation_criminal_bill():

    actual = topics_for(
        "Public school buses; motor vehicle safety and traffic offenses."
    )

    assert {
        "Education",
        "Transportation",
        "Criminal Justice",
    } <= actual


def test_multitopic_motor_vehicle_insurance_bill():

    actual = topics_for(
        "Motor vehicle insurance; liability coverage requirements."
    )

    assert {
        "Transportation",
        "Insurance",
    } <= actual

    # "Liability" by itself should not automatically make this
    # a civil-law bill.
    assert (
        "Courts and Civil Law"
        not in actual
    )


# =========================================================
# UNCLASSIFIED / NO CLEAR SUBJECT
# =========================================================

@pytest.mark.parametrize(
    "description",
    [

        "Corrects a cross-reference in the Code of Virginia.",

        "Makes technical corrections to obsolete statutory references.",

        "Updates terminology throughout the title.",

    ],
)
def test_text_without_clear_policy_subject_can_remain_unclassified(
    description,
):

    assert (
        derive_topics_from_description(
            description
        )
        ==
        []
    )


# =========================================================
# KNOWN CLEAR RULE BEHAVIOR
#
# These keep some previously reviewed examples so that
# refactoring does not silently remove established coverage.
# =========================================================

@pytest.mark.parametrize(
    "description,expected_topic",
    [

        (
            "Discovery materials or evidence; accused may request copies.",
            "Criminal Justice",
        ),

        (
            "Town of Louisa; new charter, previous charter repealed.",
            "Local Government",
        ),

        (
            "Alcoholic beverage control; retail licenses.",
            "Alcoholic Beverage and Cannabis Control",
        ),

        (
            "Financial institutions; loans and legal rate of interest.",
            "Financial Institutions and Services",
        ),

        (
            "Emergency management; work group to evaluate needs.",
            "Public Safety",
        ),

        (
            "License plates; only rear plate required.",
            "Transportation",
        ),

    ],
)
def test_reviewed_specific_phrases_keep_expected_subject(
    description,
    expected_topic,
):

    assert (
        expected_topic
        in topics_for(
            description
        )
    )


def test_discovery_without_criminal_context_does_not_trigger_criminal_justice():

    actual = topics_for(
        "Company brand discovery materials and design guidance."
    )

    assert (
        "Criminal Justice"
        not in actual
    )