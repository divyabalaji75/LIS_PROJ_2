# Automated Test Catalog

The repository currently contains 200 named test functions that expand to 354 test cases under the default 2025/2026 validation configuration. Full-data modules use `LIS_TEST_YEARS`, so the same controls can run against a future processed session without editing test code. This catalog states the business protection supplied by every named test.

## `test_vote_fact.py`

- `test_vote_fact_required_columns`: confirms every field required for voting analysis exists.
- `test_vote_fact_not_empty`: prevents an empty parse from appearing successful.
- `test_vote_fact_year_matches`: confirms all rows belong to the requested session.
- `test_vote_fact_no_missing_vote_id`: every row can be traced to a vote event.
- `test_vote_fact_no_missing_member_id`: every row has a member join key.
- `test_vote_fact_no_missing_member_name`: every row has a leadership-readable name.
- `test_vote_fact_valid_chamber`: chamber values are limited to the supported institutions.
- `test_member_id_prefix_matches_chamber`: member ID evidence agrees with chamber.
- `test_vote_fact_valid_party`: party values stay within the allowed set.
- `test_vote_fact_no_missing_party`: every analyzed member-vote has a party.
- `test_vote_fact_vote_codes_expected`: official vote codes are recognized and controlled.
- `test_vote_fact_unique_member_vote_event`: one member appears only once per canonical vote event.
- `test_member_id_maps_to_one_name`: one member ID cannot silently represent several names.
- `test_member_id_maps_to_one_party`: one member ID cannot silently represent several parties in one session.
- `test_member_id_maps_to_one_chamber`: one member ID cannot silently cross chambers.
- `test_vote_events_have_member_responses`: every event contains actual member records.
- `test_vote_fact_no_blank_vote`: official vote values are populated.
- `test_vote_fact_reasonable_scale`: catches an implausibly small or malformed pipeline result.

## `test_cross-party logic.py`

- `test_republican_cross_party_yes`: a Republican Yes against a Republican No majority and with a Democratic Yes majority is cross-party.
- `test_democrat_cross_party_no`: the equivalent Democratic No example works in the opposite direction.
- `test_member_agrees_with_own_party`: agreement with one's party is not a break or cross-party vote.
- `test_party_break_without_cross_party`: breaking with one's party is not enough unless the other party is matched.
- `test_own_party_tie_not_party_break`: an own-party tie creates no position and no party break.
- `test_other_party_tie_not_cross_party`: an other-party tie makes cross-party comparison ineligible.
- `test_x_vote_not_directional`: not-voting (`X`) cannot create party behavior flags.
- `test_a_vote_not_directional`: abstaining (`A`) cannot create party behavior flags.
- `test_p_vote_not_directional`: any retained non-directional `P` example cannot create party behavior flags.
- `test_nondirectional_votes_do_not_affect_party_majority`: only Yes and No determine party position.
- `test_cross_party_always_implies_party_break`: every cross-party flag must also be a party break.
- `test_party_positions_are_chamber_specific`: party comparisons do not mix House and Senate contexts.

## `test_party_join.py`

- `test_party_reference_required_columns`: the party reference contains every required evidence field.
- `test_party_reference_not_empty`: the reference did not collapse to zero rows.
- `test_party_reference_no_blank_member_id`: every party row has a join key.
- `test_party_reference_member_ids_unique`: one member has one reference row per year.
- `test_party_reference_valid_party_values`: only allowed party codes appear.
- `test_party_reference_no_blank_party`: no party assignment is missing.
- `test_party_reference_no_blank_member_name`: every reference row identifies a person.
- `test_every_voting_member_exists_in_party_reference`: every person who voted has party backing.
- `test_vote_fact_party_join_complete`: the production join left no missing parties.
- `test_vote_fact_party_values_valid`: the joined result did not introduce an invalid party.
- `test_vote_fact_party_matches_reference`: production party values equal the reference values.
- `test_each_member_maps_to_one_party`: one member does not have conflicting session parties.
- `test_party_reference_name_matches_vote_fact_name`: names agree across the two sources after documented normalization.
- `test_party_reference_member_id_prefix_valid`: reference member IDs have recognized chamber prefixes.
- `test_party_join_preserves_chamber_identity`: joining party data does not change chamber identity.
- `test_party_counts_reasonable`: party totals remain plausible rather than collapsing to one category.
- `test_all_vote_rows_have_reference_backing`: every canonical row can be traced to the party reference.

## `test_vote_bill_bridge.py`

- `test_bridge_required_columns`: the bridge contains vote, bill, date, and history evidence.
- `test_bridge_not_empty`: the vote/bill extraction produced usable relationships.
- `test_bridge_no_blank_vote_id`: every bridge row identifies a vote.
- `test_bridge_no_blank_bill_id`: every bridge row identifies a bill.
- `test_vote_bill_relationships_unique`: duplicate evidence rows are not created accidentally.
- `test_bridge_vote_ids_exist_in_vote_fact`: every linked vote exists in the canonical vote table.
- `test_bridge_bill_ids_exist_in_bill_lookup`: every linked bill exists in the bill universe.
- `test_bill_lookup_bill_ids_unique`: the bill lookup remains one row per bill.
- `test_some_votes_map_to_multiple_bills`: the real one-to-many relationship is present rather than forced away.
- `test_unmatched_vote_events_are_preserved`: votes without a bill link remain in the canonical vote table.
- `test_vote_fact_grain_remains_unique`: bridge processing cannot change canonical member-vote uniqueness.
- `test_bridge_join_can_expand_vote_rows`: joining bills is allowed to add analytical rows.
- `test_bridge_expansion_does_not_create_new_vote_events`: expansion repeats known votes rather than inventing IDs.
- `test_multibill_join_repeats_member_vote_identity`: repeated member-vote identities are explained by different bills.
- `test_exploded_bill_representation_has_more_rows`: confirms expected row expansion for multi-bill events.
- `test_every_bridge_vote_has_member_responses`: linked events have official member responses.
- `test_bill_lookup_no_blank_bill_id`: the bill side of the relationship has valid keys.

## `test_topic_classification.py`

- `test_bill_lookup_required_columns`: the bill universe contains required identifiers and text.
- `test_topic_lookup_required_columns`: every provenance and evidence field is present.
- `test_topic_lookup_not_empty`: topic processing did not silently produce nothing.
- `test_only_allowed_classifications`: only the four approved provenance values appear.
- `test_no_blank_classification`: every topic row states its provenance.
- `test_topic_lookup_no_blank_bill_id`: every topic can be traced to a bill.
- `test_topic_lookup_no_blank_topic_name`: every row has an explicit analytical subject.
- `test_every_bill_has_topic_classification`: the four tiers partition the complete bill universe.
- `test_topic_lookup_contains_only_known_bills`: no topic row invents a bill.
- `test_official_subject_file_classification`: the official extract contains only official rows.
- `test_derived_file_classification`: each derived extract contains only its named tier.
- `test_unclassified_file_classification`: the unclassified extract contains only unclassified bills.
- `test_unclassified_topic_name_explicit`: missing classification is labeled `Unclassified`, not left blank.
- `test_official_subject_precedence_over_derived`: official-subject bills never use text-derived rules.
- `test_official_bills_not_unclassified`: official evidence cannot be discarded into the fallback tier.
- `test_derived_bills_not_unclassified`: a successful derived match cannot also be unclassified.
- `test_bill_level_classification_partition`: each bill belongs to exactly one provenance set.
- `test_no_duplicate_topic_rows`: identical bill-topic-provenance rows are unique.
- `test_unclassified_bills_have_one_row`: unclassified bills do not create artificial multiple topics.
- `test_derived_topics_not_blank`: successful rules produce named topics.
- `test_official_topics_not_blank`: official subjects produce named analytical topics.
- `test_provenance_key_projections_reconcile_to_topic_lookup`: the four extracts reconstruct the combined lookup.
- `test_derived_bills_have_bill_description`: derived rows remain backed by official bill text.
- `test_unclassified_is_exclusive`: Unclassified never coexists with a named topic for the bill.
- `test_each_bill_has_exactly_one_provenance_tier`: reinforces the one-tier business rule across all rows.
- `test_official_subject_evidence_contract`: official rows have exact/parent/source evidence and no derived-rule claim.
- `test_summary_derived_provenance_contract`: summary rows point to summary text and a matched rule.
- `test_description_derived_provenance_contract`: description rows point to description text and a matched rule.
- `test_provenance_priority_is_exclusive`: official, summary, description, and unclassified priority is enforced.
- `test_topic_coverage_reconciles_to_provenance_sets`: coverage counts equal the actual distinct bill sets.

## `test_source_sample.py`

- `test_raw_vote_records_reconcile_to_vote_fact`: raw vote identities and processed identities reconcile.
- `test_raw_vote_row_count_matches_vote_fact`: the parser did not add or drop raw member-vote rows.
- `test_sampled_processed_votes_match_raw_lis`: sampled official vote codes match `VOTE.CSV`.
- `test_sampled_bill_descriptions_match_raw_lis`: sampled descriptions match `BILLS.CSV`.
- `test_official_subjects_backed_by_raw_lis`: every sampled official topic has an LIS subject row.
- `test_raw_official_subjects_preserved`: exact LIS subject text remains available after processing.
- `test_official_subject_parent_rollup_matches_lis_hierarchy`: analytical parents agree with the official hierarchy file.
- `test_official_subject_provenance_exact`: official rows contain the correct provenance label and fields.
- `test_derived_topics_backed_by_lis_bill_description`: sampled description-derived topics have official source text.
- `test_derived_provenance_exact`: derived rows use the precise summary/description source label.
- `test_voting_members_have_party_reference`: sampled voting members have party-source backing.
- `test_member_names_have_source_backing`: displayed names come from a roster/reference source.
- `test_vote_bill_bridge_rows_backed_by_raw_history`: sampled bridge evidence matches `HISTORY.CSV`.
- `test_bridge_vote_ids_exist_in_raw_votes`: bridge votes are present in the raw vote source.
- `test_bridge_bill_ids_exist_in_raw_bills`: bridge bills are present in the raw bill source.
- `test_create_manual_source_validation_sample`: creates a small traceable sample for a human reviewer.

## `test_reconciliation.py`

- `test_vote_code_counts_reconcile_to_vote_fact`: every official vote-code total reconciles.
- `test_directional_vote_count_reconciles`: Yes plus No agrees between detailed and summarized calculations.
- `test_nondirectional_votes_not_party_breaks`: no `A`/`X` row is a party break.
- `test_nondirectional_votes_not_cross_party`: no `A`/`X` row is cross-party.
- `test_cross_party_implies_party_break`: full production output follows the logical implication.
- `test_delegate_behavior_contains_house_members_only`: the delegate summary does not accidentally include senators.
- `test_delegate_party_break_totals_reconcile`: delegate-level break counts sum to the canonical House rows.
- `test_delegate_cross_party_totals_reconcile`: delegate-level cross-party counts sum to canonical House rows.
- `test_delegate_directional_totals_reconcile`: delegate-level Yes/No volume reconciles.
- `test_bill_classification_partition_reconciles`: all bills appear in exactly one tier.
- `test_bill_provenance_buckets_do_not_overlap`: no bill appears in two source tiers.
- `test_topic_lookup_classification_values_reconcile`: classification labels agree across topic outputs.
- `test_member_vote_topic_grain_unique`: member-vote-subject rows are unique.
- `test_member_vote_topic_rows_backed_by_vote_fact`: every topic-vote row has a canonical vote.
- `test_member_vote_topic_vote_value_matches_vote_fact`: the topic join cannot change the official vote.
- `test_delegate_topic_counts_not_impossible`: aggregated topic counts cannot exceed their own component logic.
- `test_topic_tendency_directional_reconciliation`: tendency Yes/No counts match member-vote-topic inputs.
- `test_topic_tendency_percentages_reconcile`: stored percentages recompute from stored counts.
- `test_topic_tendency_labels_valid`: only documented tendency labels appear.
- `test_insufficient_data_threshold_consistent`: fewer than 10 directional votes remains Insufficient data.
- `test_classified_tendencies_meet_minimum`: non-insufficient labels all meet the minimum.
- `test_yes_tendency_threshold_consistent`: Mostly Yes rows meet the 65% rule.
- `test_no_tendency_threshold_consistent`: Mostly No rows meet the 35% rule.
- `test_mixed_tendency_threshold_consistent`: Mixed rows fall strictly between the two thresholds.
- `test_topic_lookup_bill_ids_backed_by_bill_lookup`: all topic bill IDs exist in the bill universe.
- `test_no_blank_member_ids_across_analysis_outputs`: downstream analytical outputs retain join keys.
- `test_no_blank_party_across_analysis_outputs`: downstream party analyses have complete party values.

## `test_topic_voting_tendency.py`

- `test_clear_yes_tendency`: an obvious Yes-heavy example is Mostly Yes.
- `test_clear_no_tendency`: an obvious No-heavy example is Mostly No.
- `test_clear_mixed_tendency`: a balanced example is Mixed.
- `test_insufficient_data_even_when_all_yes`: a perfect rate is not labeled when the sample is too small.
- `test_exact_minimum_sample_qualifies`: exactly 10 directional votes qualifies.
- `test_exact_65_percent_is_yes`: the upper boundary is inclusive.
- `test_below_65_percent_is_mixed`: just below the upper boundary is Mixed.
- `test_exact_35_percent_is_no`: the lower boundary is inclusive.
- `test_above_35_percent_is_mixed`: just above the lower boundary is Mixed.
- `test_nondirectional_votes_excluded_from_denominator`: `A` and `X` do not change the Yes share.
- `test_nondirectional_votes_do_not_satisfy_minimum`: `A` and `X` cannot create a sufficient directional sample.
- `test_topic_events_include_nondirectional_events`: total event context still retains those records.
- `test_official_classification_preserved`: tendency aggregation keeps official provenance.
- `test_derived_classification_preserved`: tendency aggregation keeps derived provenance.
- `test_official_and_derived_topics_do_not_merge`: identical names with different evidence tiers remain distinct.
- `test_different_topics_do_not_merge`: different subjects remain separate.
- `test_different_members_do_not_merge`: different legislators remain separate.
- `test_different_years_do_not_merge`: different sessions remain separate.
- `test_directional_vote_reconciliation`: tendency directional total equals Yes plus No.
- `test_yes_no_percent_reconciliation`: Yes and No percentages reconcile to 100 for directional rows.
- `test_tendency_label_is_valid`: every parameterized example returns an approved label.

## `test_yoy_logic.py`

- `test_delegate_cross_party_pct_change`: cross-party percentage change is year two minus year one.
- `test_delegate_cross_party_vote_change`: count change is year two minus year one.
- `test_delegate_party_break_pct_change`: party-break percentage change is calculated correctly.
- `test_delegate_present_both_years`: a member in both sessions is recognized as present in both.
- `test_delegate_2025_only`: a departing/absent member is identified correctly.
- `test_delegate_2026_only`: a new/returning member is identified correctly.
- `test_delegate_comparable_sample_requires_both_years`: one-year records cannot become headline comparisons.
- `test_delegate_not_comparable_if_one_year_too_small`: insufficient volume in either year fails comparability.
- `test_yes_to_no_is_behavior_change`: a sufficiently observed Mostly Yes to Mostly No transition counts as change.
- `test_yes_to_mixed_is_behavior_change`: Mostly Yes to Mixed counts as change.
- `test_no_to_mixed_is_behavior_change`: Mostly No to Mixed counts as change.
- `test_same_tendency_is_not_behavior_change`: an unchanged label is not marked as change.
- `test_insufficient_to_yes_not_behavior_change`: entering from insufficient evidence is not called behavior change.
- `test_insufficient_to_no_not_behavior_change`: the same guardrail applies to Mostly No.
- `test_yes_to_insufficient_not_behavior_change`: losing sufficient evidence is not called behavior change.
- `test_no_to_insufficient_not_behavior_change`: the same guardrail applies from Mostly No.
- `test_mixed_to_insufficient_not_behavior_change`: Mixed to insufficient is not called behavior change.
- `test_insufficient_to_mixed_not_behavior_change`: insufficient to Mixed is not called behavior change.
- `test_insufficient_to_insufficient_not_change`: two insufficient samples cannot support change.
- `test_topic_yes_pct_change`: topic Yes-share change is calculated correctly.
- `test_classification_provenance_not_merged`: year-over-year joins keep unlike evidence tiers separate.
- `test_same_topic_and_classification_join`: like-for-like topic/provenance rows do join.
- `test_different_members_not_merged`: year-over-year matching never combines different people.
- `test_different_topics_not_merged`: year-over-year matching never combines different subjects.

## `test_session_configuration.py`

- `test_configured_years_uses_default`: ordinary runs still default to 2025 and 2026.
- `test_configured_years_accepts_future_sessions`: configuration accepts 2027 and 2028 without copied scripts.
- `test_future_regular_session_code`: future regular years map to the expected LIS `YYYY1` session code.
- `test_test_years_are_independent_of_analysis_years`: validation years do not interfere with dashboard or comparison settings.
- `test_environment_flag_accepts_true_values`: recognized true values enable intentional downloads.
- `test_environment_flag_accepts_false_values`: recognized false values preserve retained sources.
- `test_environment_flag_rejects_ambiguous_value`: unclear download settings fail instead of guessing.
- `test_validate_year_accepts_future_regular_sessions`: 2027 and 2028 are accepted onboarding targets.
- `test_validate_year_rejects_out_of_range_values`: implausible session years are rejected.
- `test_onboarding_environment_targets_one_year_and_disables_redownload`: processing targets only the new year and cannot redownload sources a second time.
- `test_available_processed_years_discovers_future_sessions`: the dashboard discovers valid retained session outputs without accepting unrelated filenames.
- `test_comparison_columns_are_relabelled_for_future_pair`: YoY output columns and presence labels use the actual future-session years.

## `test_dashboard_pages.py`

- `test_dashboard_page_renders_independently`: each of the four sidebar pages renders only its intended leadership question, raises no Streamlit exception, and includes a chart.
- `test_subject_drilldown_exposes_bill_and_vote_evidence`: selecting Education with the true cross-party filter produces bill counts, LIS vote-event counts, and an underlying bill table.

## `test_topic_rule_behavior.py`

- `test_commending_resolution_has_auditable_derived_subject`: a formal commending resolution receives the separate deterministic ceremonial category.
- `test_memorial_resolution_has_auditable_derived_subject`: a “Celebrating the life” resolution receives the same auditable ceremonial category.
- `test_precise_analytical_categories_from_official_text`: representative official LIS descriptions map to the intended added analytical categories using explicit deterministic rules.
- `test_incidental_discovery_language_does_not_trigger_criminal_justice`: ordinary business wording does not create a criminal-justice topic merely because it contains “discovery.”

## Latest result

```text
354 passed
```

Passing tests demonstrate that the code follows its specified rules. They do not by themselves prove external source completeness or the substantive correctness of every derived-topic judgment; those remaining reviews are documented in the methods appendix.
