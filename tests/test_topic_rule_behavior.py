"""Reviewed validity examples, distinct from structural pipeline checks.

Structural tests ask whether code followed a rule.  These validity tests ask
whether the rule produces a substantively reasonable subject assignment.
Neither kind of test replaces the other.
"""

import pytest

from lis_pipeline import derive_topics_from_description


@pytest.mark.parametrize("description,expected", [
    ("Commending the Lake Braddock Secondary School robotics team.", {"Commendations and Commemorations"}),
    ("Celebrating the life of Dr. Jane Doe, a beloved physician.", {"Commendations and Commemorations"}),
    ("Public schools; teacher licensure and student instruction.", {"Education"}),
    ("Hospitals; patient discharge and nurse staffing requirements.", {"Health and Healthcare"}),
    ("Minimum wage; employer obligations and paid leave.", {"Labor and Employment"}),
    ("Local governments; zoning appeals and municipal authority.", {"Local Government"}),
    ("Artificial intelligence; data privacy and automated decision systems.", {"Technology and Data"}),
    ("Income tax; refundable tax credit.", {"Taxes and Revenue"}),
    ("Motor vehicle insurance; minimum liability coverage.", {"Transportation", "Insurance", "Courts and Civil Law"}),
    ("Small businesses; consumer protection and commercial licensing.", {"Business and Commerce"}),
    ("Vehicle operation; unlicensed driver; misdemeanor penalty.", {"Transportation", "Criminal Justice"}),
])
def test_realistic_central_subject_language(description, expected):
    assert set(derive_topics_from_description(description)) == expected


@pytest.mark.parametrize("description,excluded", [
    ("Commending the Jefferson High School championship team.", "Education"),
    ("Celebrating the life of a longtime hospital volunteer.", "Health and Healthcare"),
    ("Court notice may be sent electronically in a civil action.", "Technology and Data"),
    ("A state procurement contract requires designated employees to sign the form.", "Labor and Employment"),
    ("A criminal restitution order may include medical expenses.", "Health and Healthcare"),
    ("A highway project shall notify each affected locality.", "Local Government"),
    ("Budget bill; deposits nongeneral fund revenue into an existing account.", "Taxes and Revenue"),
    ("Broadband coverage mapping for underserved areas.", "Insurance"),
    ("Civil procedure; discovery of electronically stored records.", "Technology and Data"),
    ("A public school shall use commercially available textbooks.", "Business and Commerce"),
    ("Vehicle operation by an unlicensed minor; misdemeanor penalty.", "Family and Children"),
])
def test_incidental_words_do_not_create_unrelated_topics(description, excluded):
    assert excluded not in derive_topics_from_description(description)


def test_multitopic_bill_keeps_each_substantive_topic():
    topics = set(derive_topics_from_description("Public school buses; motor vehicle safety and traffic offenses."))
    assert {"Education", "Transportation", "Criminal Justice"} <= topics


def test_unrelated_text_remains_unclassified():
    assert derive_topics_from_description("Corrects a cross-reference in the Code of Virginia.") == []
