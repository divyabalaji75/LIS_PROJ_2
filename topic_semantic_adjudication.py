from __future__ import annotations

from pathlib import Path
from enum import Enum
import json
import os
import random
import time

import pandas as pd
from pydantic import BaseModel, Field

from topic_validation_audit import (
    add_risk_band,
    build_match_strength_table,
    build_priority_review_subset,
    build_semantic_review_queue,
    combine_derived,
    load_data as load_audit_data,
)
from lis_common import configured_years

try:
    from openai import OpenAI
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "\nThe OpenAI Python package is required.\n\n"
        "Install it with:\n\n"
        "    python -m pip install openai pydantic\n"
    ) from exc


# =========================================================
# CONFIG
# =========================================================

YEAR = int(
    os.environ.get(
        "LIS_ANALYSIS_YEAR",
        str(configured_years()[0]),
    )
)

MODEL = os.environ.get(
    "OPENAI_MODEL",
    "gpt-5.6-terra",
)

QA_ROOT = Path("data/qa")

OUTPUT_PATH = (
    QA_ROOT
    / f"topic_semantic_adjudication_{YEAR}.csv"
)

CHECKPOINT_PATH = (
    QA_ROOT
    / f"topic_semantic_adjudication_checkpoint_{YEAR}.csv"
)


# =========================================================
# REVIEW SETTINGS
# =========================================================

# Two independent model judgments are much safer than one.
REVIEW_PASSES = int(
    os.environ.get(
        "SEMANTIC_REVIEW_PASSES",
        "2",
    )
)

# Random LOW-risk rows form a control group.
#
# This matters because reviewing only suspicious rows would
# bias our estimate of classifier performance.
CONTROL_SAMPLE_SIZE = int(
    os.environ.get(
        "SEMANTIC_CONTROL_SAMPLE_SIZE",
        "100",
    )
)

RANDOM_STATE = 42

# Useful for testing the workflow before spending money.
#
# Example:
#
# set SEMANTIC_MAX_ROWS=10
#
# Empty / 0 = no artificial limit.
MAX_ROWS = int(
    os.environ.get(
        "SEMANTIC_MAX_ROWS",
        "0",
    )
)

# Set to 1 to print the queue without making API calls.
DRY_RUN = (
    os.environ.get(
        "SEMANTIC_DRY_RUN",
        "0",
    )
    ==
    "1"
)

# API retry behavior.
MAX_RETRIES = 4
BASE_RETRY_SECONDS = 2

# Save progress every N completed assignments.
CHECKPOINT_EVERY = 10


# =========================================================
# REVIEW LABELS
# =========================================================

class Judgment(
    str,
    Enum,
):

    TRUE_POSITIVE = (
        "TRUE_POSITIVE"
    )

    FALSE_POSITIVE = (
        "FALSE_POSITIVE"
    )

    BORDERLINE = (
        "BORDERLINE"
    )


class Confidence(
    str,
    Enum,
):

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RecommendedAction(
    str,
    Enum,
):

    KEEP_ASSIGNMENT = (
        "KEEP_ASSIGNMENT"
    )

    REMOVE_ASSIGNMENT = (
        "REMOVE_ASSIGNMENT"
    )

    REVIEW_RULE = (
        "REVIEW_RULE"
    )

    REVIEW_TOPIC_OVERLAP = (
        "REVIEW_TOPIC_OVERLAP"
    )

    HUMAN_REVIEW = (
        "HUMAN_REVIEW"
    )


# =========================================================
# STRUCTURED MODEL OUTPUT
# =========================================================

class SemanticJudgment(
    BaseModel,
):

    judgment: Judgment

    confidence: Confidence

    substantive_basis: str = Field(
        description=(
            "Brief explanation of what, "
            "if anything, makes the assigned "
            "topic a substantive policy domain "
            "of the measure."
        )
    )

    incidental_basis: str = Field(
        description=(
            "Brief explanation of any evidence "
            "that the matched language is merely "
            "incidental, contextual, ceremonial, "
            "an affected population, an agency "
            "reference, or an implementation method."
        )
    )

    reason: str = Field(
        description=(
            "Concise final justification for "
            "the judgment."
        )
    )

    recommended_action: (
        RecommendedAction
    )

    needs_human_review: bool


# =========================================================
# SYSTEM RUBRIC
#
# This is the semantic methodology.
#
# The reviewer does NOT choose a dominant topic.
# Every bill-topic assignment is judged independently.
# =========================================================

SYSTEM_RUBRIC = """
You are validating policy-topic classifications for Virginia
legislative measures.

Your job is NOT to classify the bill from scratch.

You are evaluating ONE existing bill-topic assignment and deciding
whether that assigned topic is substantively supported by the
legislative measure.

Use exactly these standards:

TRUE_POSITIVE:
The measure regulates, funds, establishes, prohibits, modifies,
requires, authorizes, studies, reports on, or otherwise materially
governs the assigned policy domain.

FALSE_POSITIVE:
The matched language is merely incidental and the measure does not
materially govern the assigned topic.

Examples of incidental evidence include:
- an affected population mentioned only descriptively;
- an organization name;
- an agency or committee referenced only administratively;
- an implementation method;
- an isolated generic word;
- ceremonial recognition or commendation;
- a secondary phrase that does not describe an actual policy domain
  addressed by the measure.

BORDERLINE:
The assigned topic is meaningfully connected to the measure, but
whether it constitutes a substantive policy domain is genuinely
ambiguous.

IMPORTANT RULES:

1. Multiple topics may all be TRUE_POSITIVE.
   Do not force one dominant or primary topic.

2. Do not reject a topic merely because another topic is more central.

3. Do not accept a topic merely because its keyword appears.

4. Evaluate policy substance, not keyword occurrence.

5. A criminal penalty can make Criminal Justice substantive when
   creation, modification, or enforcement of that penalty is a
   meaningful part of the measure.

6. A population descriptor alone usually does not establish a policy
   domain. For example, the word "minor" does not automatically make
   a transportation law a Family and Children measure.

7. A ceremonial commendation or memorial resolution is not
   substantive policy legislation for this analytical purpose merely
   because the honored person, school, organization, profession, or
   activity contains policy-related words.

8. A long summary may contain important substantive information that
   is absent from a short bill description. Absence from the short
   description is therefore NOT sufficient to reject a topic.

9. When Education and Higher Education both appear, evaluate whether
   the broader Education label adds a genuinely distinct substantive
   domain. If it merely duplicates the specific Higher Education
   concept, that broader assignment may be FALSE_POSITIVE or
   BORDERLINE depending on context.

10. Never use political ideology, party identity, sponsor identity,
    or expected legislative intent to make the judgment.

11. Judge only from the supplied legislative text and topic evidence.

12. If evidence is genuinely insufficient or ambiguous, use
    BORDERLINE and set needs_human_review=true.

Keep the explanation concise and evidence-based.
"""


# =========================================================
# FILE HELPERS
# =========================================================

def require_file(
    path: Path,
):

    if not path.exists():

        raise FileNotFoundError(
            f"Missing required file: {path}\n\n"
            "Run topic_validation_audit.py first."
        )


def load_csv(
    path: Path,
):

    require_file(
        path
    )

    return pd.read_csv(
        path,
        dtype=str,
    )


def normalize_text(
    value,
):

    if pd.isna(
        value
    ):

        return ""

    return " ".join(
        str(
            value
        )
        .split()
    )


# =========================================================
# UNIQUE ASSIGNMENT KEY
#
# One semantic judgment belongs to one:
#
# Bill × topic × provenance × rule
# =========================================================

def build_assignment_key(
    row,
):

    values = [
        row.get(
            "Bill_id",
            "",
        ),
        row.get(
            "topic_name",
            "",
        ),
        row.get(
            "classification",
            "",
        ),
        row.get(
            "matched_rule",
            "",
        ),
    ]

    return "||".join(
        normalize_text(
            value
        )
        for value
        in values
    )


# =========================================================
# LOAD REVIEW QUEUE
#
# Review:
#
# 1. ALL HIGH + VERY HIGH priority rows
# 2. A random LOW-risk control sample
#
# Medium-risk rows can be added later after we calibrate
# the adjudicator.
# =========================================================

def build_full_review_queue():

    data = load_audit_data(YEAR)
    derived = combine_derived(
        data["summary"],
        data["description"],
    )
    strength = build_match_strength_table(derived)
    return add_risk_band(
        build_semantic_review_queue(
            derived,
            data["bill_lookup"],
            strength,
        )
    )


def build_review_population():

    full = build_full_review_queue()
    priority = build_priority_review_subset(full)

    # -----------------------------------------------------
    # NORMALIZE
    # -----------------------------------------------------

    for dataframe in [
        priority,
        full,
    ]:

        for column in dataframe.columns:

            dataframe[
                column
            ] = (
                dataframe[
                    column
                ]
                .fillna("")
                .astype(str)
            )

        dataframe[
            "assignment_key"
        ] = dataframe.apply(
            build_assignment_key,
            axis=1,
        )

    # -----------------------------------------------------
    # PRIORITY GROUP
    # -----------------------------------------------------

    priority = (
        priority
        .drop_duplicates(
            subset=[
                "assignment_key"
            ]
        )
        .copy()
    )

    priority[
        "review_sample_type"
    ] = "PRIORITY"

    # -----------------------------------------------------
    # LOW-RISK CONTROL GROUP
    # -----------------------------------------------------

    if (
        "risk_band"
        in full.columns
    ):

        control_pool = full[
            full[
                "risk_band"
            ]
            ==
            "LOW"
        ].copy()

    else:

        # Fallback if risk_band somehow was not saved.
        control_pool = full[
            pd.to_numeric(
                full[
                    "risk_score"
                ],
                errors="coerce",
            )
            .fillna(0)
            <
            2
        ].copy()

    priority_keys = set(
        priority[
            "assignment_key"
        ]
    )

    control_pool = control_pool[
        ~control_pool[
            "assignment_key"
        ]
        .isin(
            priority_keys
        )
    ].copy()

    n_control = min(
        CONTROL_SAMPLE_SIZE,
        len(
            control_pool
        ),
    )

    if n_control > 0:

        control = (
            control_pool.sample(
                n=n_control,
                random_state=RANDOM_STATE,
            )
            .copy()
        )

    else:

        control = (
            control_pool.head(
                0
            )
            .copy()
        )

    control[
        "review_sample_type"
    ] = "LOW_RISK_CONTROL"

    # -----------------------------------------------------
    # COMBINE
    # -----------------------------------------------------

    population = pd.concat(
        [
            priority,
            control,
        ],
        ignore_index=True,
    )

    population = (
        population
        .drop_duplicates(
            subset=[
                "assignment_key"
            ]
        )
        .reset_index(
            drop=True
        )
    )

    if MAX_ROWS > 0:

        population = (
            population.head(
                MAX_ROWS
            )
            .copy()
        )

    return population


# =========================================================
# BLINDED MODEL INPUT
#
# CRITICAL:
#
# Risk score
# risk band
# risk reasons
# high-risk-rule flag
#
# are intentionally NOT provided to the model.
#
# Step 1 chooses WHAT gets reviewed.
# Step 2 independently decides WHETHER it is correct.
# =========================================================

def build_model_prompt(
    row,
):

    bill_id = normalize_text(
        row.get(
            "Bill_id",
            "",
        )
    )

    topic = normalize_text(
        row.get(
            "topic_name",
            "",
        )
    )

    classification = normalize_text(
        row.get(
            "classification",
            "",
        )
    )

    matched_rule = normalize_text(
        row.get(
            "matched_rule",
            "",
        )
    )

    source_file = normalize_text(
        row.get(
            "source_file",
            "",
        )
    )

    source_text = normalize_text(
        row.get(
            "source_text_used",
            "",
        )
    )

    description = normalize_text(
        row.get(
            "Bill_description",
            "",
        )
    )

    return f"""
BILL ID
{bill_id}

ASSIGNED TOPIC
{topic}

CLASSIFICATION PROVENANCE
{classification}

SOURCE FILE USED FOR THE ASSIGNMENT
{source_file}

MATCHED RULE
{matched_rule}

SOURCE TEXT USED FOR CLASSIFICATION
{source_text}

SHORT LIS BILL DESCRIPTION
{description}

TASK

Evaluate ONLY whether the assigned topic "{topic}" is a substantive
policy domain of this measure.

Do not select a primary or dominant topic.

Other topics may also be valid.

Return the structured judgment requested by the schema.
""".strip()


# =========================================================
# ONE MODEL CALL
# =========================================================

def adjudicate_once(
    client,
    row,
):

    prompt = build_model_prompt(
        row
    )

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            response = (
                client.responses.parse(
                    model=MODEL,

                    input=[
                        {
                            "role":
                                "system",

                            "content":
                                SYSTEM_RUBRIC,
                        },
                        {
                            "role":
                                "user",

                            "content":
                                prompt,
                        },
                    ],

                    text_format=
                        SemanticJudgment,
                )
            )

            parsed = (
                response.output_parsed
            )

            if parsed is None:

                raise ValueError(
                    "Model returned no "
                    "structured adjudication."
                )

            return parsed

        except Exception as error:

            last_error = error

            if (
                attempt
                ==
                MAX_RETRIES
            ):

                break

            sleep_seconds = (
                BASE_RETRY_SECONDS
                *
                (
                    2
                    **
                    (
                        attempt - 1
                    )
                )
            )

            print(
                f"    API attempt "
                f"{attempt} failed."
            )

            print(
                f"    Retrying in "
                f"{sleep_seconds}s..."
            )

            time.sleep(
                sleep_seconds
            )

    raise RuntimeError(
        "Semantic adjudication failed "
        f"after {MAX_RETRIES} attempts."
    ) from last_error


# =========================================================
# TWO-PASS CONSENSUS
#
# Neither pass sees the other pass's judgment.
# =========================================================

def adjudicate_assignment(
    client,
    row,
):

    judgments = []

    for pass_number in range(
        1,
        REVIEW_PASSES + 1,
    ):

        print(
            f"    semantic pass "
            f"{pass_number}/"
            f"{REVIEW_PASSES}"
        )

        result = adjudicate_once(
            client,
            row,
        )

        judgments.append(
            result
        )

    # -----------------------------------------------------
    # ONE-PASS MODE
    # -----------------------------------------------------

    if len(
        judgments
    ) == 1:

        result = judgments[
            0
        ]

        return {
            "pass_1_judgment":
                result.judgment.value,

            "pass_1_confidence":
                result.confidence.value,

            "pass_1_reason":
                result.reason,

            "pass_1_substantive_basis":
                result.substantive_basis,

            "pass_1_incidental_basis":
                result.incidental_basis,

            "pass_1_action":
                result.recommended_action.value,

            "pass_1_needs_human_review":
                result.needs_human_review,

            "pass_2_judgment":
                "",

            "pass_2_confidence":
                "",

            "pass_2_reason":
                "",

            "pass_2_substantive_basis":
                "",

            "pass_2_incidental_basis":
                "",

            "pass_2_action":
                "",

            "pass_2_needs_human_review":
                "",

            "model_consensus":
                True,

            "consensus_judgment":
                result.judgment.value,

            "consensus_confidence":
                result.confidence.value,

            "requires_human_review":
                (
                    result.needs_human_review
                    or
                    result.judgment
                    ==
                    Judgment.BORDERLINE
                ),
        }

    # -----------------------------------------------------
    # TWO-PASS MODE
    # -----------------------------------------------------

    first = judgments[
        0
    ]

    second = judgments[
        1
    ]

    same_judgment = (
        first.judgment
        ==
        second.judgment
    )

    # Conservative confidence aggregation.
    confidence_order = {
        Confidence.LOW:
            1,

        Confidence.MEDIUM:
            2,

        Confidence.HIGH:
            3,
    }

    lower_confidence = min(
        [
            first.confidence,
            second.confidence,
        ],
        key=lambda value:
            confidence_order[
                value
            ],
    )

    if same_judgment:

        consensus_judgment = (
            first.judgment.value
        )

        consensus_confidence = (
            lower_confidence.value
        )

    else:

        consensus_judgment = (
            "DISAGREEMENT"
        )

        consensus_confidence = (
            "LOW"
        )

    requires_human_review = (
        not same_judgment
        or
        first.needs_human_review
        or
        second.needs_human_review
        or
        first.judgment
        ==
        Judgment.BORDERLINE
        or
        second.judgment
        ==
        Judgment.BORDERLINE
    )

    return {
        "pass_1_judgment":
            first.judgment.value,

        "pass_1_confidence":
            first.confidence.value,

        "pass_1_reason":
            first.reason,

        "pass_1_substantive_basis":
            first.substantive_basis,

        "pass_1_incidental_basis":
            first.incidental_basis,

        "pass_1_action":
            first.recommended_action.value,

        "pass_1_needs_human_review":
            first.needs_human_review,

        "pass_2_judgment":
            second.judgment.value,

        "pass_2_confidence":
            second.confidence.value,

        "pass_2_reason":
            second.reason,

        "pass_2_substantive_basis":
            second.substantive_basis,

        "pass_2_incidental_basis":
            second.incidental_basis,

        "pass_2_action":
            second.recommended_action.value,

        "pass_2_needs_human_review":
            second.needs_human_review,

        "model_consensus":
            same_judgment,

        "consensus_judgment":
            consensus_judgment,

        "consensus_confidence":
            consensus_confidence,

        "requires_human_review":
            requires_human_review,
    }


# =========================================================
# CHECKPOINT / RESUME
# =========================================================

def load_existing_results():

    if not CHECKPOINT_PATH.exists():

        return pd.DataFrame()

    existing = pd.read_csv(
        CHECKPOINT_PATH,
        dtype=str,
    )

    if (
        "assignment_key"
        not in
        existing.columns
    ):

        return pd.DataFrame()

    return existing


def save_checkpoint(
    results,
):

    dataframe = pd.DataFrame(
        results
    )

    dataframe.to_csv(
        CHECKPOINT_PATH,
        index=False,
    )


# =========================================================
# JOIN STEP-1 RISK DATA BACK AFTER ADJUDICATION
# =========================================================

def join_risk_metadata(
    adjudicated,
    queue,
):

    risk_columns = [
        "assignment_key",
        "risk_score",
        "risk_band",
        "risk_reasons",
        "topic_count_for_bill",
        "high_risk_rule",
        "risk_reason",
        "ceremonial_candidate",
        "description_supports_topic",
        "education_higher_ed_overlap",
        "match_count",
        "first_match_position",
        "relative_match_position",
    ]

    available = [
        column
        for column in risk_columns
        if column
        in queue.columns
    ]

    risk = (
        queue[
            available
        ]
        .drop_duplicates(
            subset=[
                "assignment_key"
            ]
        )
    )

    # Avoid duplicate risk fields from checkpoint rows.
    adjudicated = (
        adjudicated.drop(
            columns=[
                column
                for column in available
                if (
                    column
                    !=
                    "assignment_key"
                    and
                    column
                    in adjudicated.columns
                )
            ],
            errors="ignore",
        )
    )

    return adjudicated.merge(
        risk,
        on="assignment_key",
        how="left",
        validate="one_to_one",
    )


# =========================================================
# RULE-LEVEL EMPIRICAL RESULTS
#
# Precision here is:
#
# TP / (TP + FP)
#
# BORDERLINE is shown separately rather than silently
# counted as correct or incorrect.
# =========================================================

def build_rule_results(
    adjudicated,
):

    usable = adjudicated[
        adjudicated[
            "consensus_judgment"
        ]
        .isin(
            [
                "TRUE_POSITIVE",
                "FALSE_POSITIVE",
                "BORDERLINE",
            ]
        )
    ].copy()

    if len(
        usable
    ) == 0:

        return pd.DataFrame()

    usable[
        "is_tp"
    ] = (
        usable[
            "consensus_judgment"
        ]
        ==
        "TRUE_POSITIVE"
    )

    usable[
        "is_fp"
    ] = (
        usable[
            "consensus_judgment"
        ]
        ==
        "FALSE_POSITIVE"
    )

    usable[
        "is_borderline"
    ] = (
        usable[
            "consensus_judgment"
        ]
        ==
        "BORDERLINE"
    )

    rule_results = (
        usable
        .groupby(
            [
                "classification",
                "topic_name",
                "matched_rule",
            ],
            as_index=False,
            dropna=False,
        )
        .agg(
            reviewed_assignments=(
                "assignment_key",
                "size",
            ),

            true_positive=(
                "is_tp",
                "sum",
            ),

            false_positive=(
                "is_fp",
                "sum",
            ),

            borderline=(
                "is_borderline",
                "sum",
            ),

            human_review_required=(
                "requires_human_review",
                lambda values:
                    sum(
                        str(value)
                        .strip()
                        .lower()
                        ==
                        "true"
                        for value
                        in values
                    ),
            ),
        )
    )

    denominator = (
        rule_results[
            "true_positive"
        ]
        +
        rule_results[
            "false_positive"
        ]
    )

    rule_results[
        "observed_precision_pct"
    ] = pd.NA

    valid = (
        denominator
        >
        0
    )

    rule_results.loc[
        valid,
        "observed_precision_pct"
    ] = (
        rule_results.loc[
            valid,
            "true_positive"
        ]
        /
        denominator[
            valid
        ]
        *
        100
    ).round(
        2
    )

    # -----------------------------------------------------
    # EMPIRICAL RISK TIER
    #
    # Only assign a tier after at least 5 adjudicated
    # non-borderline examples for that rule.
    #
    # These are preliminary thresholds, not universal truth.
    # -----------------------------------------------------

    rule_results[
        "empirical_rule_risk"
    ] = (
        "INSUFFICIENT REVIEW"
    )

    enough = (
        denominator
        >=
        5
    )

    precision = pd.to_numeric(
        rule_results[
            "observed_precision_pct"
        ],
        errors="coerce",
    )

    rule_results.loc[
        enough
        &
        (
            precision
            <
            60
        ),
        "empirical_rule_risk"
    ] = "HIGH"

    rule_results.loc[
        enough
        &
        (
            precision
            >=
            60
        )
        &
        (
            precision
            <
            85
        ),
        "empirical_rule_risk"
    ] = "MEDIUM"

    rule_results.loc[
        enough
        &
        (
            precision
            >=
            85
        ),
        "empirical_rule_risk"
    ] = "LOW"

    return (
        rule_results
        .sort_values(
            [
                "empirical_rule_risk",
                "observed_precision_pct",
                "reviewed_assignments",
            ],
            ascending=[
                True,
                True,
                False,
            ],
        )
        .reset_index(
            drop=True
        )
    )


# =========================================================
# OVERALL REVIEW SUMMARY
# =========================================================

def build_review_summary(
    adjudicated,
):

    rows = []

    total = len(
        adjudicated
    )

    rows.append(
        {
            "metric":
                "Adjudicated assignments",

            "value":
                total,
        }
    )

    for judgment in [
        "TRUE_POSITIVE",
        "FALSE_POSITIVE",
        "BORDERLINE",
        "DISAGREEMENT",
    ]:

        count = int(
            (
                adjudicated[
                    "consensus_judgment"
                ]
                ==
                judgment
            )
            .sum()
        )

        rows.append(
            {
                "metric":
                    judgment,

                "value":
                    count,
            }
        )

    human_count = int(
        adjudicated[
            "requires_human_review"
        ]
        .astype(str)
        .str.lower()
        .eq(
            "true"
        )
        .sum()
    )

    rows.append(
        {
            "metric":
                "Requires human review",

            "value":
                human_count,
        }
    )

    priority = (
        adjudicated[
            adjudicated[
                "review_sample_type"
            ]
            ==
            "PRIORITY"
        ]
    )

    control = (
        adjudicated[
            adjudicated[
                "review_sample_type"
            ]
            ==
            "LOW_RISK_CONTROL"
        ]
    )

    for label, subset in [
        (
            "Priority sample",
            priority,
        ),
        (
            "Low-risk control",
            control,
        ),
    ]:

        rows.append(
            {
                "metric":
                    f"{label} assignments",

                "value":
                    len(
                        subset
                    ),
            }
        )

        if len(
            subset
        ) > 0:

            fp_count = int(
                (
                    subset[
                        "consensus_judgment"
                    ]
                    ==
                    "FALSE_POSITIVE"
                )
                .sum()
            )

            rows.append(
                {
                    "metric":
                        (
                            f"{label} "
                            "false positives"
                        ),

                    "value":
                        fp_count,
                }
            )

    return pd.DataFrame(
        rows
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "\n" + "=" * 72
    )

    print(
        "LIS TOPIC SEMANTIC ADJUDICATION"
    )

    print(
        "=" * 72
    )

    print(
        f"\nYear: {YEAR}"
    )

    print(
        f"Model: {MODEL}"
    )

    print(
        f"Independent passes per row: "
        f"{REVIEW_PASSES}"
    )

    print(
        f"Low-risk control sample: "
        f"{CONTROL_SAMPLE_SIZE}"
    )

    print(
        f"Dry run: {DRY_RUN}"
    )

    # -----------------------------------------------------
    # API KEY CHECK
    # -----------------------------------------------------

    if (
        not DRY_RUN
        and
        not os.environ.get(
            "OPENAI_API_KEY"
        )
    ):

        raise EnvironmentError(
            "\nOPENAI_API_KEY is not set.\n\n"
            "Set it in your environment before "
            "running semantic adjudication.\n"
        )

    # -----------------------------------------------------
    # BUILD REVIEW POPULATION
    # -----------------------------------------------------

    population = (
        build_review_population()
    )

    print(
        "\nReview population:"
    )

    print(
        f"{len(population):,} "
        "bill-topic assignments"
    )

    print(
        "\nBy sample type:"
    )

    print(
        population[
            "review_sample_type"
        ]
        .value_counts()
        .to_string()
    )

    if DRY_RUN:

        print(
            "\nDRY RUN COMPLETE."
        )

        print(
            "\nNo API calls were made."
        )

        return

    # -----------------------------------------------------
    # CLIENT
    # -----------------------------------------------------

    client = OpenAI()

    # -----------------------------------------------------
    # RESUME FROM CHECKPOINT
    # -----------------------------------------------------

    existing = (
        load_existing_results()
    )

    completed_keys = set()

    results = []

    if len(
        existing
    ) > 0:

        completed_keys = set(
            existing[
                "assignment_key"
            ]
        )

        results = (
            existing
            .to_dict(
                orient="records"
            )
        )

        print(
            "\nResuming checkpoint:"
        )

        print(
            f"{len(completed_keys):,} "
            "assignments already completed"
        )

    # -----------------------------------------------------
    # ADJUDICATE
    # -----------------------------------------------------

    pending = population[
        ~population[
            "assignment_key"
        ]
        .isin(
            completed_keys
        )
    ].copy()

    total_pending = len(
        pending
    )

    print(
        f"\nPending assignments: "
        f"{total_pending:,}"
    )

    for sequence, (
        _,
        row,
    ) in enumerate(
        pending.iterrows(),
        start=1,
    ):

        bill_id = (
            row[
                "Bill_id"
            ]
        )

        topic = (
            row[
                "topic_name"
            ]
        )

        print(
            "\n" + "-" * 72
        )

        print(
            f"[{sequence:,}/"
            f"{total_pending:,}] "
            f"{bill_id} -> {topic}"
        )

        # Small jitter ensures repeated calls
        # are not perfectly synchronized.
        time.sleep(
            random.uniform(
                0.05,
                0.20,
            )
        )

        adjudication = (
            adjudicate_assignment(
                client,
                row,
            )
        )

        output_row = (
            row.to_dict()
        )

        output_row.update(
            adjudication
        )

        results.append(
            output_row
        )

        print(
            "    consensus: "
            f"{adjudication['consensus_judgment']}"
        )

        print(
            "    human review: "
            f"{adjudication['requires_human_review']}"
        )

        if (
            sequence
            %
            CHECKPOINT_EVERY
            ==
            0
        ):

            save_checkpoint(
                results
            )

            print(
                "    checkpoint saved"
            )

    # -----------------------------------------------------
    # FINAL CHECKPOINT
    # -----------------------------------------------------

    save_checkpoint(
        results
    )

    adjudicated = pd.DataFrame(
        results
    )

    # -----------------------------------------------------
    # JOIN STEP-1 RISK INFORMATION BACK AFTER REVIEW
    # -----------------------------------------------------

    full_queue = build_full_review_queue()

    for column in full_queue.columns:

        full_queue[
            column
        ] = (
            full_queue[
                column
            ]
            .fillna("")
            .astype(str)
        )

    full_queue[
        "assignment_key"
    ] = (
        full_queue.apply(
            build_assignment_key,
            axis=1,
        )
    )

    adjudicated = (
        join_risk_metadata(
            adjudicated,
            full_queue,
        )
    )

    # -----------------------------------------------------
    # SAVE FINAL ADJUDICATION
    # -----------------------------------------------------

    adjudicated.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    # -----------------------------------------------------
    # DISAGREEMENTS / HUMAN REVIEW QUEUE
    # -----------------------------------------------------

    disagreements = adjudicated[
        (
            adjudicated[
                "model_consensus"
            ]
            .astype(str)
            .str.lower()
            !=
            "true"
        )
        |
        (
            adjudicated[
                "requires_human_review"
            ]
            .astype(str)
            .str.lower()
            ==
            "true"
        )
    ].copy()

    # -----------------------------------------------------
    # EMPIRICAL RULE RESULTS
    # -----------------------------------------------------

    rule_results = (
        build_rule_results(
            adjudicated
        )
    )

    # -----------------------------------------------------
    # REVIEW SUMMARY
    # -----------------------------------------------------

    review_summary = (
        build_review_summary(
            adjudicated
        )
    )

    # -----------------------------------------------------
    # TERMINAL REPORT
    # -----------------------------------------------------

    print(
        "\n" + "=" * 72
    )

    print(
        "SEMANTIC ADJUDICATION SUMMARY"
    )

    print(
        "=" * 72
    )

    print()

    print(
        review_summary.to_string(
            index=False
        )
    )

    print(
        "\nRows requiring human review:"
    )

    print(
        f"{len(disagreements):,}"
    )

    if len(
        rule_results
    ) > 0:

        print(
            "\n" + "=" * 72
        )

        print(
            "PRELIMINARY EMPIRICAL RULE PRECISION"
        )

        print(
            "=" * 72
        )

        print()

        print(
            rule_results[
                [
                    "topic_name",
                    "matched_rule",
                    "reviewed_assignments",
                    "true_positive",
                    "false_positive",
                    "borderline",
                    "observed_precision_pct",
                    "empirical_rule_risk",
                ]
            ]
            .head(40)
            .to_string(
                index=False
            )
        )

    print(
        "\n" + "=" * 72
    )

    print(
        "FILES SAVED"
    )

    print(
        "=" * 72
    )

    print(OUTPUT_PATH)

    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()

    print(
        "\nIMPORTANT:"
    )

    print(
        "These are QA judgments."
    )

    print(
        "No production classifications "
        "were changed."
    )

    print(
        "\nSemantic adjudication complete."
    )


if __name__ == "__main__":

    main()
