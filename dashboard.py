"""Leadership briefing built from the canonical Virginia LIS outputs."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lis_common import PROCESSED_ROOT, configured_years


st.set_page_config(
    page_title="Virginia legislative briefing",
    page_icon=":classical_building:",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container {max-width: 1180px; padding-top: 1.7rem; padding-bottom: 4rem;}
      h1 {font-size: 2.1rem !important; line-height: 1.2 !important;}
      h2 {font-size: 1.35rem !important; margin-top: 2.2rem !important;}
      [data-testid="stMetric"] {background: rgba(128,128,128,.07); padding: .8rem 1rem; border-radius: .5rem;}
      [data-testid="stMetricValue"] {font-size: 1.65rem;}
      .answer {font-size: 1.05rem; line-height: 1.55; padding: .85rem 1rem; border-left: 4px solid #2d6cdf; background: rgba(45,108,223,.07); margin: .35rem 0 1rem;}
      .question-number {color: #2d6cdf; font-weight: 600;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_output(name: str, year: int | str) -> pd.DataFrame:
    path = PROCESSED_ROOT / f"{name}_{year}.csv"
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def pct(numerator: float, denominator: float) -> float:
    return 100 * numerator / denominator if denominator else 0.0


def answer(text: str) -> None:
    st.markdown(f'<div class="answer"><strong>What the records show:</strong> {text}</div>', unsafe_allow_html=True)


def compact_table(frame: pd.DataFrame, height: int = 280) -> None:
    st.dataframe(frame, width="stretch", hide_index=True, height=height)


def bar_chart(
    frame: pd.DataFrame,
    x: str,
    y: str,
    *,
    color: str | None = None,
    horizontal: bool = False,
    percent: bool = False,
) -> None:
    labels = {x: x, y: y}
    if horizontal:
        figure = px.bar(frame, x=y, y=x, color=color, orientation="h", text=y, labels=labels)
        figure.update_layout(yaxis={"categoryorder": "total ascending"})
    else:
        figure = px.bar(frame, x=x, y=y, color=color, barmode="group", text=y, labels=labels)
    figure.update_traces(texttemplate="%{text:.1f}%" if percent else "%{text:,.0f}", textposition="outside")
    figure.update_layout(
        height=340,
        margin=dict(t=20, b=20, l=10, r=10),
        legend_title_text="",
        hovermode="x unified" if not horizontal else "closest",
    )
    st.plotly_chart(figure, width="stretch")


def session_vote_metrics(votes: pd.DataFrame) -> dict[str, float]:
    directional = votes[votes["vote"].isin(["Y", "N"])].copy()
    own_position = directional[directional["own_party_position"].isin(["Y", "N"])]
    cross_eligible = own_position[own_position["other_party_position"].isin(["Y", "N"])]
    return {
        "directional": len(directional),
        "yes": int(directional["vote"].eq("Y").sum()),
        "yes_pct": pct(directional["vote"].eq("Y").sum(), len(directional)),
        "party_breaks": int(own_position["broke_with_party"].sum()),
        "party_break_pct": pct(own_position["broke_with_party"].sum(), len(own_position)),
        "cross_party": int(cross_eligible["cross_party"].sum()),
        "cross_party_pct": pct(cross_eligible["cross_party"].sum(), len(cross_eligible)),
        "cross_eligible": len(cross_eligible),
        "members": votes["member_id"].nunique(),
        "vote_events": votes["vote_id"].nunique(),
    }


def party_vote_summary(votes: pd.DataFrame) -> pd.DataFrame:
    directional = votes[votes["vote"].isin(["Y", "N"])].copy()
    directional["eligible for party-break test"] = directional["own_party_position"].isin(["Y", "N"])
    directional["eligible for cross-party test"] = (
        directional["eligible for party-break test"]
        & directional["other_party_position"].isin(["Y", "N"])
    )
    rows = []
    for party, group in directional.groupby("party"):
        party_eligible = group[group["eligible for party-break test"]]
        cross_eligible = group[group["eligible for cross-party test"]]
        rows.append(
            {
                "Party": party,
                "Party-break rate": pct(party_eligible["broke_with_party"].sum(), len(party_eligible)),
                "Cross-party rate": pct(cross_eligible["cross_party"].sum(), len(cross_eligible)),
            }
        )
    return pd.DataFrame(rows)


def topic_summary(delegate_topics: pd.DataFrame) -> pd.DataFrame:
    if delegate_topics.empty:
        return pd.DataFrame()
    result = (
        delegate_topics.groupby("topic_name", as_index=False)
        .agg(
            vote_events=("topic_vote_events", "sum"),
            eligible_events=("eligible_topic_events", "sum"),
            cross_party_events=("cross_party_events", "sum"),
        )
        .rename(columns={"topic_name": "Subject"})
    )
    result["Cross-party rate"] = 100 * result["cross_party_events"] / result["eligible_events"]
    return result


def subject_vote_counts(member_topics: pd.DataFrame) -> pd.DataFrame:
    """Count official vote codes once per member-vote-subject row."""

    if member_topics.empty:
        return pd.DataFrame()
    result = (
        member_topics.groupby("topic_name", as_index=False)
        .agg(
            Yes=("vote", lambda values: values.eq("Y").sum()),
            No=("vote", lambda values: values.eq("N").sum()),
            Abstained=("vote", lambda values: values.eq("A").sum()),
            Not_voting=("vote", lambda values: values.eq("X").sum()),
            Cross_party=("cross_party", "sum"),
        )
        .rename(
            columns={
                "topic_name": "Subject",
                "Not_voting": "Not voting",
                "Cross_party": "Cross-party votes",
            }
        )
    )
    result["Yes/No votes"] = result["Yes"] + result["No"]
    return result


def bill_outcomes(history: pd.DataFrame) -> dict[str, int]:
    if history.empty:
        return {"Became law": 0, "Left in committee": 0, "Failed or stricken": 0}
    descriptions = history["history_description"].fillna("")
    return {
        "Became law": history.loc[
            descriptions.str.contains(r"Approved by Governor-Chapter|Acts of Assembly Chapter text", case=False, regex=True),
            "Bill_id",
        ].nunique(),
        "Left in committee": history.loc[
            descriptions.str.contains("Left in", case=False, regex=False), "Bill_id"
        ].nunique(),
        "Failed or stricken": history.loc[
            descriptions.str.contains(r"Failed|Defeated|Stricken", case=False, regex=True), "Bill_id"
        ].nunique(),
    }


available_years = [
    year for year in configured_years() if (PROCESSED_ROOT / f"vote_fact_{year}.csv").exists()
]
if not available_years:
    st.error("No processed sessions were found. Run the pipeline before opening the briefing.")
    st.stop()

with st.sidebar:
    st.subheader("Briefing options")
    selected_year = st.selectbox("Session detail", available_years, index=len(available_years) - 1)
    st.caption("The session selector changes questions 1, 2, 4, and 5. Question 3 always compares available sessions.")

votes = load_output("vote_fact", selected_year)
delegates = load_output("delegate_behavior", selected_year)
delegate_topics = load_output("delegate_topic_behavior", selected_year)
member_topics = load_output("member_vote_topic", selected_year)
bills = load_output("bill_lookup", selected_year)
bill_topics = load_output("bill_topic_lookup", selected_year)
coverage = load_output("topic_coverage", selected_year)
sponsors = load_output("sponsor_fact", selected_year)
sponsor_votes = load_output("sponsor_vote_behavior", selected_year)
history = load_output("bill_history", selected_year)
vote_bridge = load_output("vote_bill_bridge", selected_year)
statements = load_output("vote_statement_fact", selected_year)
committee_members = load_output("committee_members", selected_year)

metrics = session_vote_metrics(votes)
topics = topic_summary(delegate_topics)
subject_counts = subject_vote_counts(member_topics)
outcomes = bill_outcomes(history)

st.title("What Virginia’s legislative records show")
st.markdown(
    f"**Executive briefing | {selected_year} Regular Session, with 2025–2026 comparison**  "
    "  \nOfficial Virginia LIS records; observable actions only."
)

headline_columns = st.columns(4)
headline_columns[0].metric("Yes-vote rate", f"{metrics['yes_pct']:.1f}%")
headline_columns[1].metric("Cross-party rate", f"{metrics['cross_party_pct']:.2f}%")
headline_columns[2].metric("Became law", f"{outcomes['Became law']:,}")
headline_columns[3].metric("Bills analyzed", f"{bills['Bill_id'].nunique():,}")


# 1. VOTING BEHAVIOR
st.header("1. How did legislators vote?")
party_summary = party_vote_summary(votes)
party_rates = dict(zip(party_summary["Party"], party_summary["Cross-party rate"]))
cross_party_leader = delegates.nlargest(1, "cross_party_votes").iloc[0]
directional_votes = votes[votes["vote"].isin(["Y", "N"])]
party_break_rows = directional_votes[
    directional_votes["own_party_position"].isin(["Y", "N"])
    & directional_votes["broke_with_party"].eq(True)
]
same_party_majority_breaks = int(
    party_break_rows["other_party_position"].eq(party_break_rows["own_party_position"]).sum()
)
no_other_party_majority = int(
    (~party_break_rows["other_party_position"].isin(["Y", "N"])).sum()
)
party_comparison = ""
if {"D", "R"}.issubset(party_rates):
    party_comparison = (
        f" The eligible-vote rate was {party_rates['D']:.2f}% for Democratic members and "
        f"{party_rates['R']:.2f}% for Republican members."
    )
answer(
    f"In {selected_year}, {metrics['members']:,} legislators cast {metrics['directional']:,} recorded Yes/No votes "
    f"across {metrics['vote_events']:,} vote events. {metrics['yes_pct']:.1f}% were Yes votes. "
    f"There were {metrics['party_breaks']:,} votes against a legislator’s own party majority and "
    f"{metrics['cross_party']:,} true cross-party votes ({metrics['cross_party_pct']:.2f}% of eligible votes)."
    f" Of the remaining party breaks, {same_party_majority_breaks:,} occurred when both parties had the same majority "
    f"position, and {no_other_party_majority:,} had no clear other-party majority to match."
    f" {cross_party_leader['MBR_NAME']} recorded the most true cross-party votes ({int(cross_party_leader['cross_party_votes']):,})."
    f"{party_comparison}"
)

q1_left, q1_right = st.columns([1, 1.35])
with q1_left:
    compact_table(party_summary.style.format({"Party-break rate": "{:.2f}%", "Cross-party rate": "{:.2f}%"}), 115)
with q1_right:
    leaders = delegates.nlargest(8, "cross_party_votes")
    leaders = leaders[["MBR_NAME", "party", "cross_party_votes"]].rename(
        columns={"MBR_NAME": "Legislator", "party": "Party", "cross_party_votes": "Cross-party votes"}
    )
    bar_chart(leaders, "Legislator", "Cross-party votes", color="Party", horizontal=True)

with st.expander("Explore one legislator’s recorded votes by subject"):
    person = st.selectbox(
        "Legislator",
        sorted(member_topics["MBR_NAME"].dropna().unique()),
        key="person_subject_drilldown",
    )
    person_id = member_topics.loc[member_topics["MBR_NAME"].eq(person), "member_id"].iloc[0]
    person_votes = votes[votes["member_id"].eq(person_id)]
    person_columns = st.columns(5)
    person_columns[0].metric("Yes", f"{person_votes['vote'].eq('Y').sum():,}")
    person_columns[1].metric("No", f"{person_votes['vote'].eq('N').sum():,}")
    person_columns[2].metric("Abstained (A)", f"{person_votes['vote'].eq('A').sum():,}")
    person_columns[3].metric("Not voting (X)", f"{person_votes['vote'].eq('X').sum():,}")
    person_columns[4].metric("Cross-party", f"{person_votes['cross_party'].sum():,}")

    person_subjects = subject_vote_counts(member_topics[member_topics["member_id"].eq(person_id)])
    person_subjects = person_subjects.sort_values("Yes/No votes", ascending=False)
    person_chart = person_subjects.head(12).melt(
        id_vars="Subject",
        value_vars=["Yes", "No", "Abstained", "Not voting"],
        var_name="Recorded vote",
        value_name="Count",
    )
    bar_chart(person_chart, "Subject", "Count", color="Recorded vote", horizontal=True)
    compact_table(
        person_subjects[
            ["Subject", "Yes", "No", "Abstained", "Not voting", "Cross-party votes"]
        ],
        330,
    )
    st.caption(
        "These are observed vote counts, not a measure of personal belief. A subject can contain bills with different "
        "policy directions, and some recorded votes concern procedure rather than final passage."
    )


# 2. TOPICS
st.header("2. Where did voting patterns differ by subject?")
classified_topics = topics[topics["Subject"].ne("Unclassified")].copy()
highest_volume = classified_topics.nlargest(3, "vote_events")
substantive = classified_topics[classified_topics["eligible_events"].ge(1000)]
highest_cross = substantive.nlargest(1, "Cross-party rate")
volume_names = ", ".join(highest_volume["Subject"].tolist())
if not highest_cross.empty:
    cross_name = highest_cross.iloc[0]["Subject"]
    cross_rate = highest_cross.iloc[0]["Cross-party rate"]
    topic_finding = (
        f"The most voting activity was associated with {volume_names}. Among subjects with at least 1,000 eligible "
        f"member-votes, {cross_name} had the highest true cross-party rate at {cross_rate:.1f}%."
    )
else:
    topic_finding = f"The most voting activity was associated with {volume_names}."
answer(topic_finding)

q2_left, q2_right = st.columns(2)
with q2_left:
    volume_view = classified_topics.nlargest(8, "vote_events")[["Subject", "vote_events"]].rename(
        columns={"vote_events": "Recorded member-votes"}
    )
    st.markdown("**Most active subjects**")
    bar_chart(volume_view, "Subject", "Recorded member-votes", horizontal=True)
with q2_right:
    cross_view = substantive.nlargest(8, "Cross-party rate")[["Subject", "Cross-party rate"]]
    st.markdown("**Highest cross-party rates**  ")
    st.caption("Subjects with at least 1,000 eligible member-votes")
    bar_chart(cross_view, "Subject", "Cross-party rate", horizontal=True, percent=True)

if not subject_counts.empty:
    st.markdown("**Which subjects contained the most Yes, No, abstention, non-voting, or cross-party records?**")
    measure = st.selectbox(
        "Recorded vote measure",
        ["Yes", "No", "Abstained", "Not voting", "Cross-party votes"],
        index=4,
        key="subject_measure",
    )
    subject_measure_view = (
        subject_counts[subject_counts["Subject"].ne("Unclassified")]
        .nlargest(10, measure)[["Subject", measure]]
    )
    bar_chart(subject_measure_view, "Subject", measure, horizontal=True)
    st.caption("A = abstained; X = not voting. Counts are member-vote-subject records.")

    st.markdown("**How did each party vote within a subject?**")
    selected_subject = st.selectbox(
        "Subject",
        sorted(subject_counts.loc[subject_counts["Subject"].ne("Unclassified"), "Subject"]),
        key="party_subject_drilldown",
    )
    party_subject_rows = member_topics[member_topics["topic_name"].eq(selected_subject)]
    party_subject = (
        party_subject_rows.groupby("party", as_index=False)
        .agg(
            Yes=("vote", lambda values: values.eq("Y").sum()),
            No=("vote", lambda values: values.eq("N").sum()),
            Abstained=("vote", lambda values: values.eq("A").sum()),
            Not_voting=("vote", lambda values: values.eq("X").sum()),
            Cross_party_votes=("cross_party", "sum"),
        )
        .rename(
            columns={
                "party": "Party",
                "Not_voting": "Not voting",
                "Cross_party_votes": "Cross-party votes",
            }
        )
    )
    party_subject["Yes rate"] = 100 * party_subject["Yes"] / (party_subject["Yes"] + party_subject["No"])
    compact_table(
        party_subject.style.format({"Yes rate": "{:.1f}%"}),
        150,
    )
    st.caption(
        "The Yes rate summarizes recorded votes on bills assigned to this subject; it should not be interpreted as "
        "support for a single policy position."
    )


# 3. CHANGE OVER TIME
st.header("3. What changed between sessions?")
year_metrics = []
for year in available_years:
    year_votes = load_output("vote_fact", year)
    year_summary = session_vote_metrics(year_votes)
    year_metrics.append(
        {
            "Session": str(year),
            "Yes rate": year_summary["yes_pct"],
            "Party-break rate": year_summary["party_break_pct"],
            "Cross-party rate": year_summary["cross_party_pct"],
        }
    )
change = pd.DataFrame(year_metrics)
if len(change) >= 2:
    first, last = change.iloc[0], change.iloc[-1]
    difference = last["Cross-party rate"] - first["Cross-party rate"]
    direction = "increased" if difference > 0 else "decreased" if difference < 0 else "did not change"
    answer(
        f"The overall true cross-party rate {direction} from {first['Cross-party rate']:.2f}% in {first['Session']} "
        f"to {last['Cross-party rate']:.2f}% in {last['Session']} ({difference:+.2f} percentage points). "
        f"The Yes-vote rate changed from {first['Yes rate']:.1f}% to {last['Yes rate']:.1f}%."
    )
    comparison = change.set_index("Session").T.reset_index().rename(columns={"index": "Measure"})
    comparison["Change"] = comparison[str(last["Session"])] - comparison[str(first["Session"])]
    comparison = comparison.rename(
        columns={str(first["Session"]): str(first["Session"]), str(last["Session"]): str(last["Session"])}
    )

    party_change_rows = []
    for year in available_years:
        for row in party_vote_summary(load_output("vote_fact", year)).to_dict("records"):
            party_change_rows.append(
                {"Session": str(year), "Party": row["Party"], "Cross-party rate": row["Cross-party rate"]}
            )
    q3_left, q3_right = st.columns([0.85, 1.25])
    with q3_left:
        compact_table(
            comparison.style.format(
                {str(first["Session"]): "{:.2f}%", str(last["Session"]): "{:.2f}%", "Change": "{:+.2f} points"}
            ),
            180,
        )
    with q3_right:
        st.markdown("**Cross-party rate by party**")
        bar_chart(pd.DataFrame(party_change_rows), "Party", "Cross-party rate", color="Session", percent=True)

    comparison_label = "_".join(str(year) for year in available_years[:2])
    member_change = load_output("delegate_behavior_yoy", comparison_label)
    if not member_change.empty and "comparable_sample" in member_change:
        comparable = member_change[member_change["comparable_sample"].eq(True)].copy()
        comparable = comparable.reindex(comparable["cross_party_pct_change"].abs().sort_values(ascending=False).index)
        member_view = comparable.head(8)[
            ["MBR_NAME", "party", "cross_party_pct_2025", "cross_party_pct_2026", "cross_party_pct_change"]
        ].rename(
            columns={
                "MBR_NAME": "Legislator",
                "party": "Party",
                "cross_party_pct_2025": "2025 rate",
                "cross_party_pct_2026": "2026 rate",
                "cross_party_pct_change": "Change",
            }
        )
        st.markdown("**Largest individual changes among comparable legislators**")
        compact_table(member_view.style.format({"2025 rate": "{:.2f}%", "2026 rate": "{:.2f}%", "Change": "{:+.2f} points"}), 315)
else:
    answer("A second processed session is needed before a year-over-year comparison can be calculated.")


# 4. SPONSORSHIP
st.header("4. What did sponsorship tell us?")
directional_sponsor_votes = sponsor_votes[sponsor_votes["vote"].isin(["Y", "N"])].copy()
sponsored_bill_count = sponsor_votes["Bill_id"].nunique() if not sponsor_votes.empty else 0
sponsor_yes_rate = pct(directional_sponsor_votes["vote"].eq("Y").sum(), len(directional_sponsor_votes))
answer(
    f"The data connected sponsors to {sponsored_bill_count:,} bills with recorded votes in {selected_year}. "
    f"Sponsors voted Yes on {sponsor_yes_rate:.1f}% of their own recorded Yes/No votes. The official sponsor role "
    "remains visible so chief patrons and co-patrons can be evaluated separately."
)

if not directional_sponsor_votes.empty:
    sponsor_role_summary = (
        directional_sponsor_votes.groupby("patron_role", as_index=False)
        .agg(Recorded_votes=("vote", "size"), Yes_votes=("vote", lambda values: values.eq("Y").sum()))
        .rename(columns={"patron_role": "Sponsor role"})
    )
    sponsor_role_summary["Yes rate"] = 100 * sponsor_role_summary["Yes_votes"] / sponsor_role_summary["Recorded_votes"]
    sponsor_role_summary = sponsor_role_summary.nlargest(8, "Recorded_votes")
    q4_left, q4_right = st.columns([1.25, 1])
    with q4_left:
        bar_chart(sponsor_role_summary, "Sponsor role", "Yes rate", horizontal=True, percent=True)
    with q4_right:
        compact_table(
            sponsor_role_summary[["Sponsor role", "Recorded_votes", "Yes rate"]]
            .rename(columns={"Recorded_votes": "Recorded votes"})
            .style.format({"Yes rate": "{:.1f}%"}),
            300,
        )


# 5. PATHWAY AND CONTEXT
st.header("5. How did bills move, and what context is available?")
statement_count = len(statements)
explicit_intentions = int(statements.get("intended_vote_explicit", pd.Series(dtype=bool)).fillna(False).sum())
answer(
    f"LIS history records identify {outcomes['Became law']:,} bills that became law, "
    f"{outcomes['Left in committee']:,} bills left in committee, and {outcomes['Failed or stricken']:,} bills explicitly "
    f"recorded as failed, defeated, or stricken in {selected_year}. LIS also provides {statement_count:,} vote statements; "
    f"{explicit_intentions:,} explicitly state an intended Yes or No without replacing the official recorded vote."
)

outcome_view = pd.DataFrame({"Recorded pathway marker": outcomes.keys(), "Bills": outcomes.values()})
st.caption("Pathway markers summarize official history text and are not mutually exclusive outcome categories.")
q5_left, q5_right = st.columns([1.15, 1])
with q5_left:
    bar_chart(outcome_view, "Recorded pathway marker", "Bills")
with q5_right:
    st.metric("Committees represented", f"{committee_members.get('committee_name', pd.Series(dtype=str)).nunique():,}")
    st.metric("Committee membership records", f"{len(committee_members):,}")
    st.metric("Vote statements", f"{statement_count:,}")

with st.expander("Look up the official record for one bill"):
    bill_choice = st.selectbox("Bill", sorted(bills["Bill_id"].dropna().unique()))
    bill_row = bills[bills["Bill_id"].eq(bill_choice)]
    if not bill_row.empty:
        st.markdown(f"**{bill_choice} — {bill_row.iloc[0].get('Bill_description', '')}**")

    bill_topic_rows = bill_topics[bill_topics["Bill_id"].eq(bill_choice)]
    if not bill_topic_rows.empty:
        topic_view = bill_topic_rows[
            ["topic_name", "classification", "lis_subject_name", "lis_parent_subject"]
        ].rename(
            columns={
                "topic_name": "Analytical subject",
                "classification": "How it was classified",
                "lis_subject_name": "Exact LIS subject",
                "lis_parent_subject": "Broader LIS subject",
            }
        )
        compact_table(topic_view, 150)

    bill_sponsors = sponsors[sponsors["Bill_id"].eq(bill_choice)]
    if not bill_sponsors.empty:
        st.markdown("**Sponsors**")
        compact_table(
            bill_sponsors[["member_name", "patron_role"]].rename(
                columns={"member_name": "Legislator", "patron_role": "Role"}
            ),
            150,
        )

    bill_history = history[history["Bill_id"].eq(bill_choice)].copy()
    if not bill_history.empty:
        st.markdown("**Official LIS timeline**")
        bill_history["sort_date"] = pd.to_datetime(bill_history["history_date"], errors="coerce")
        timeline = bill_history.sort_values(["sort_date", "history_date"])[
            ["history_date", "history_description"]
        ].rename(columns={"history_date": "Date", "history_description": "Action"})
        compact_table(timeline, 300)

    bill_vote_ids = vote_bridge.loc[vote_bridge["Bill_id"].eq(bill_choice), "vote_id"].drop_duplicates()
    if not bill_vote_ids.empty:
        vote_tally = (
            votes[votes["vote_id"].isin(bill_vote_ids)]
            .groupby(["vote_id", "vote"], as_index=False)
            .size()
            .rename(columns={"vote_id": "Vote record", "vote": "Recorded vote", "size": "Members"})
        )
        st.markdown("**Recorded vote totals**")
        compact_table(vote_tally, 190)

    bill_statements = statements[statements["Bill_id"].eq(bill_choice)] if not statements.empty else pd.DataFrame()
    if not bill_statements.empty:
        st.markdown("**Vote statements**")
        statement_view = bill_statements[
            ["member_id", "recorded_vote", "intended_vote", "vote_statement"]
        ].rename(
            columns={
                "member_id": "Member",
                "recorded_vote": "Official vote",
                "intended_vote": "Explicit intended vote",
                "vote_statement": "Statement",
            }
        )
        compact_table(statement_view, 240)


with st.expander("Definitions, coverage, and limitations"):
    st.markdown(
        "- **True cross-party vote:** a recorded Yes/No vote that differs from the legislator’s own party majority "
        "and matches the other party’s majority. Ties and unavailable party positions are excluded.\n"
        "- **Subjects:** official LIS subjects take priority. The exact LIS subject and its broader parent are retained. "
        "Bills without an official subject use documented rules applied first to the LIS summary and then to the bill description.\n"
        "- **Interpretation:** these measures describe recorded legislative behavior. They do not establish ideology, "
        "motivation, persuasion, or causation. Session differences can also reflect agenda and membership changes."
    )
    if not coverage.empty:
        coverage_view = coverage[["classification", "bill_count", "bill_percentage"]].rename(
            columns={"classification": "Subject source", "bill_count": "Bills", "bill_percentage": "Share of bills"}
        )
        compact_table(coverage_view.style.format({"Share of bills": "{:.1f}%"}), 210)
