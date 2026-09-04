"""Small read-only Streamlit front end for the canonical LIS outputs."""

from pathlib import Path

import pandas as pd
import streamlit as st

from lis_common import PROCESSED_ROOT, configured_years


st.set_page_config(page_title="Virginia LIS analysis", layout="wide")


@st.cache_data
def load_output(name: str, year: int) -> pd.DataFrame:
    path = PROCESSED_ROOT / f"{name}_{year}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def show_table(frame: pd.DataFrame, columns: list[str] | None = None) -> None:
    if frame.empty:
        st.info("No processed data is available for this view. Run the pipeline first.")
        return
    if columns:
        frame = frame[[column for column in columns if column in frame.columns]]
    st.dataframe(frame, use_container_width=True, hide_index=True)


available_years = [
    year
    for year in configured_years()
    if (PROCESSED_ROOT / f"vote_fact_{year}.csv").exists()
]
if not available_years:
    available_years = configured_years()

st.title("Virginia legislative behavior")
st.caption(
    "A read-only view of observable LIS records. Cross-party voting is a "
    "recorded-vote measure, not an inference about beliefs or motivation."
)
year = st.sidebar.selectbox("Session", available_years, index=len(available_years) - 1)

vote_fact = load_output("vote_fact", year)
coverage = load_output("topic_coverage", year)
delegates = load_output("delegate_behavior", year)
delegate_topics = load_output("delegate_topic_behavior", year)
bill_topics = load_output("bill_topic_lookup", year)
bills = load_output("bill_lookup", year)

overview_tab, legislators_tab, topics_tab, bills_tab, evidence_tab = st.tabs(
    ["Overview", "Legislators", "Topics", "Bills", "LIS evidence"]
)

with overview_tab:
    metric_columns = st.columns(4)
    metric_columns[0].metric("Recorded member-votes", f"{len(vote_fact):,}")
    metric_columns[1].metric(
        "Vote events", f"{vote_fact.get('vote_id', pd.Series(dtype=str)).nunique():,}"
    )
    metric_columns[2].metric(
        "Bills", f"{bills.get('Bill_id', pd.Series(dtype=str)).nunique():,}"
    )
    metric_columns[3].metric(
        "Cross-party events",
        f"{int(vote_fact.get('cross_party', pd.Series(dtype=int)).sum()):,}",
    )
    if not coverage.empty:
        st.subheader("Topic provenance coverage")
        chart = coverage.set_index("classification")["bill_percentage"]
        st.bar_chart(chart)
        show_table(coverage)

with legislators_tab:
    st.subheader("Recorded voting behavior")
    parties = sorted(delegates.get("party", pd.Series(dtype=str)).dropna().unique())
    party = st.multiselect("Party", parties, default=parties)
    filtered = delegates[delegates["party"].isin(party)] if party else delegates
    show_table(filtered.sort_values("cross_party_pct", ascending=False))

    if not delegate_topics.empty:
        names = sorted(delegate_topics["MBR_NAME"].dropna().unique())
        selected_name = st.selectbox("Legislator topic detail", names)
        detail = delegate_topics[delegate_topics["MBR_NAME"].eq(selected_name)]
        show_table(detail.sort_values("topic_vote_events", ascending=False))

with topics_tab:
    st.subheader("Voting patterns by topic")
    if not delegate_topics.empty:
        topic_summary = (
            delegate_topics.groupby(["topic_name", "classification"], as_index=False)
            .agg(
                legislators=("member_id", "nunique"),
                vote_events=("topic_vote_events", "sum"),
                eligible_events=("eligible_topic_events", "sum"),
                cross_party_events=("cross_party_events", "sum"),
            )
        )
        topic_summary["cross_party_pct"] = (
            100 * topic_summary["cross_party_events"] / topic_summary["eligible_events"]
        ).where(topic_summary["eligible_events"].gt(0), 0)
        show_table(topic_summary.sort_values("vote_events", ascending=False))

with bills_tab:
    st.subheader("Bill topics and provenance")
    bill_id = st.text_input("Filter by bill ID", placeholder="For example: HB123")
    bill_view = bill_topics
    if bill_id:
        bill_view = bill_view[
            bill_view["Bill_id"].astype(str).str.contains(bill_id, case=False, na=False)
        ]
    show_table(
        bill_view,
        [
            "Bill_id",
            "topic_name",
            "classification",
            "lis_subject_name",
            "lis_parent_subject",
            "source_file",
            "source_text_used",
            "matched_rule",
        ],
    )

with evidence_tab:
    st.subheader("Separate official LIS evidence layers")
    layer = st.selectbox(
        "Layer",
        [
            "sponsor_fact",
            "sponsor_vote_behavior",
            "committee_members",
            "bill_history",
            "vote_statement_fact",
            "vote_bill_bridge",
        ],
    )
    show_table(load_output(layer, year))

