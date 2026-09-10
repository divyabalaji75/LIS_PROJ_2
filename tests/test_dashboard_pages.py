from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


PAGES = [
    ("Voting overview", "How did legislators vote?"),
    ("Subjects and delegates", "Where did voting patterns differ by subject?"),
    ("Session comparison", "What changed between sessions?"),
    ("Bills and context", "How did bills move, and what context is available?"),
]
DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "dashboard.py"


@pytest.mark.parametrize(("page", "expected_header"), PAGES)
def test_dashboard_page_renders_independently(page, expected_header):
    app = AppTest.from_file(DASHBOARD_PATH)
    app.run(timeout=40)
    app.radio[0].set_value(page)
    app.run(timeout=40)

    assert not app.exception
    assert [header.value for header in app.header] == [expected_header]
    assert len(app.get("plotly_chart")) >= 1


def test_subject_drilldown_exposes_bill_and_vote_evidence():
    app = AppTest.from_file(DASHBOARD_PATH)
    app.run(timeout=40)
    app.radio[0].set_value("Subjects and delegates")
    app.run(timeout=40)
    subject_selector = next(item for item in app.selectbox if item.label == "Subject to compare")
    subject_selector.set_value("Education")
    app.run(timeout=40)

    metrics = {item.label: item.value for item in app.metric}
    assert not app.exception
    assert int(metrics["Bills"].replace(",", "")) > 0
    assert int(metrics["LIS vote events"].replace(",", "")) > 0
    assert any("HB1208" in str(table.value) for table in app.dataframe)


def test_unclassified_is_retained_and_labeled_as_vote_records():
    app = AppTest.from_file(DASHBOARD_PATH)
    app.run(timeout=40)

    subject_selector = next(item for item in app.selectbox if item.label == "Subject")
    visible_text = " ".join(item.value for item in app.caption)

    assert not app.exception
    assert "Unclassified" in subject_selector.options
    assert "recorded member-vote-subject count—not a count of bills" in visible_text
