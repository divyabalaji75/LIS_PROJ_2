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
