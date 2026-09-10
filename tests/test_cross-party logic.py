import pandas as pd
import pytest

from lis_pipeline import add_other_party_position, add_own_party_position, calculate_party_positions, flag_cross_party_votes, flag_party_breaks


def analyze(d_votes, r_votes, target_party, target_index=-1, chamber="H", vote_id="V1"):
    rows = []
    for party, votes in (("D", d_votes), ("R", r_votes)):
        for index, vote in enumerate(votes):
            rows.append({"year": 2026, "MBR_HOU": chamber, "vote_id": vote_id,
                         "member_id": f"{chamber}{party}{index}", "MBR_NAME": f"{party}{index}",
                         "party": party, "vote": vote})
    frame = pd.DataFrame(rows)
    positions = calculate_party_positions(frame)
    result = add_own_party_position(frame, positions)
    result = flag_party_breaks(result)
    result = add_other_party_position(result, positions)
    result = flag_cross_party_votes(result)
    target = f"{chamber}{target_party}{target_index % len(d_votes if target_party == 'D' else r_votes)}"
    return result.loc[result.member_id.eq(target)].iloc[0], result


@pytest.mark.parametrize(
    "d_votes,r_votes,target_party,expected",
    [
        (["Y", "Y", "Y", "N"], ["N", "N", "N", "Y"], "R", ("N", "Y", True, True)),
        (["Y", "Y", "Y", "N"], ["N", "N", "N", "Y"], "D", ("Y", "N", True, True)),
        (["Y", "Y", "Y", "N"], ["N", "N", "N", "N"], "R", ("N", "Y", False, False)),
        (["Y", "Y", "Y", "N"], ["Y", "Y", "Y", "N"], "R", ("Y", "Y", True, False)),
        (["Y", "Y", "Y", "N"], ["N", "Y"], "R", ("TIE", "Y", False, False)),
        (["Y", "Y", "N", "N"], ["N", "N", "N", "Y"], "R", ("N", "TIE", True, False)),
    ],
    ids=["republican-crosses", "democrat-crosses", "agrees-with-party", "breaks-without-crossing", "own-party-tie", "other-party-tie"],
)
def test_directional_cross_party_definition(d_votes, r_votes, target_party, expected):
    row, _ = analyze(d_votes, r_votes, target_party)
    own, other, broke, crossed = expected
    assert (row.own_party_position, row.other_party_position) == (own, other)
    assert bool(row.broke_with_party) is broke
    assert bool(row.cross_party) is crossed


@pytest.mark.parametrize("vote", ["X", "A", "P"])
def test_nondirectional_votes_never_break_or_cross_and_do_not_set_majority(vote):
    row, result = analyze(["Y", "Y", "N", vote], ["N", "N", "Y", "Y"], "D")
    assert row.vote == vote
    assert not row.broke_with_party and not row.cross_party
    d_rows = result[(result.party == "D") & result.vote.isin(["Y", "N"])]
    assert d_rows.own_party_position.eq("Y").all()


def test_cross_party_always_implies_party_break():
    _, result = analyze(["Y", "Y", "Y", "N"], ["N", "N", "N", "Y"], "R")
    assert result.loc[result.cross_party, "broke_with_party"].all()


def test_party_majorities_are_chamber_specific():
    _, house = analyze(["Y", "Y", "N"], ["N", "N", "Y"], "R", chamber="H")
    _, senate = analyze(["N", "N", "Y"], ["Y", "Y", "N"], "R", chamber="S")
    combined = pd.concat([house.drop(columns=[c for c in house if c.startswith("own_") or c.startswith("other_") or c in {"broke_with_party", "cross_party"}]),
                          senate.drop(columns=[c for c in senate if c.startswith("own_") or c.startswith("other_") or c in {"broke_with_party", "cross_party"}])])
    positions = calculate_party_positions(combined)
    assert positions.groupby(["MBR_HOU", "party"])["party_position"].first().to_dict() == {("H", "D"): "Y", ("H", "R"): "N", ("S", "D"): "N", ("S", "R"): "Y"}
