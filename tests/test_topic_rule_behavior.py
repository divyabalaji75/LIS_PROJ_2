import pytest

from lis_pipeline import derive_topics_from_description


def test_commending_resolution_has_auditable_derived_subject():
    topics = derive_topics_from_description("Commending the Arlington Food Assistance Center.")

    assert topics == ["Commendations and Commemorations"]


def test_memorial_resolution_has_auditable_derived_subject():
    topics = derive_topics_from_description("Celebrating the life of Jane Virginia Doe.")

    assert topics == ["Commendations and Commemorations"]


@pytest.mark.parametrize(
    ("description", "expected_topic"),
    [
        ("Discovery materials or evidence; accused may request copies.", "Criminal Justice"),
        ("Town of Louisa; new charter, previous charter repealed.", "Local Government"),
        ("Alcoholic beverage control; retail licenses.", "Alcoholic Beverage and Cannabis Control"),
        ("Virginia Retirement System; enhanced retirement benefits.", "Pensions, Benefits, and Retirement"),
        ("Financial institutions; loans and legal rate of interest.", "Financial Institutions and Services"),
        ("Charitable gaming; regulations for poker tournaments.", "Gambling, Lotteries, Etc."),
        ("Virginia National Guard; biennial training.", "Armed Forces"),
        ("Data centers; industrial zoning.", "Data Centers"),
        ("Uniform Trust Code; qualified trustee.", "Wills, Trusts, and Fiduciaries"),
        ("Real property; public hearing required for conveyance.", "Property and Conveyances"),
        ("Consultation with federally recognized tribes; permits and reviews.", "Indian Tribes"),
        ("Constitutional amendment; first reference.", "Constitutional Amendments"),
        ("Emergency management; work group to evaluate needs.", "Public Safety"),
        ("License plates; only rear plate required.", "Transportation"),
    ],
)
def test_specific_lis_description_phrases_map_to_reviewed_subjects(description, expected_topic):
    assert expected_topic in derive_topics_from_description(description)


def test_discovery_without_criminal_context_does_not_trigger_criminal_justice():
    topics = derive_topics_from_description("Company brand discovery materials and design guidance.")

    assert "Criminal Justice" not in topics
