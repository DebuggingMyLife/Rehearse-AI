"""Pydantic models for LLM outputs. Their JSON schemas are sent to Ollama as `format`
and every response is validated against them."""

from typing import Literal

from pydantic import BaseModel, Field, create_model

QuestionTypeLit = Literal["behavioural", "technical", "cv_specific"]
DifficultyLit = Literal["easy", "medium", "hard"]


class GeneratedQuestion(BaseModel):
    question: str = Field(min_length=10)
    type: QuestionTypeLit
    difficulty: DifficultyLit
    # Stored as Question.rubric. The descriptive field name matters: with "rubric", qwen2.5:7b
    # writes generic structure ("Describes the situation"); with this name it lists actual
    # content ("Used EXPLAIN to analyse query plans"). A/B tested 2026-10-23.
    points_a_strong_answer_would_mention: list[str] = Field(min_length=3, max_length=6)
    cv_evidence: list[str] = Field(max_length=4)


class QuestionBatch(BaseModel):
    questions: list[GeneratedQuestion] = Field(min_length=1)


# --- Evaluation (two calls) ---------------------------------------------------------------
# Field order matters for a 7B model: coverage is decided point by point *before* the score,
# and short feedback fields come before the long example answer so they stream first.


class RubricCoverage(BaseModel):
    # Quote first, then judge: the model looks for supporting words before deciding,
    # which made coverage noticeably less erratic on qwen2.5:7b than judging first.
    point: str
    evidence_quote: str = Field(description="exact words from the transcript, or empty if none")
    covered: bool


def scoring_model(n_points: int) -> type[BaseModel]:
    """Call 1 schema; the coverage list length is pinned to the rubric length."""
    return create_model(
        "Scoring",
        rubric_coverage=(list[RubricCoverage], Field(min_length=n_points, max_length=n_points)),
        score=(int, Field(ge=1, le=5)),
    )


class QuotedPoint(BaseModel):
    point: str
    quote: str


class StarPart(BaseModel):
    # Quote first, as with rubric coverage: without it the model wrote the same generic
    # comment ("Present, but not clearly described") for all four parts.
    quote: str = Field(description="the candidate's words for this part, or empty if missing")
    comment: str


class StarAssessment(BaseModel):
    situation: StarPart
    task: StarPart
    action: StarPart
    result: StarPart
    overall: str


class AttemptComparison(BaseModel):
    addressed: list[str]
    not_addressed: list[str]
    summary: str


def feedback_model(behavioural: bool, has_previous: bool) -> type[BaseModel]:
    """Call 2 schema. Optional sections are left out of the schema entirely when they don't
    apply, which is shorter and more reliable than asking a small model to emit null."""
    fields: dict = {
        "what_you_did_well": (list[QuotedPoint], Field(max_length=4)),
        "what_could_be_improved": (list[str], Field(min_length=1, max_length=4)),
        "missed_opportunities": (list[str], Field(max_length=3)),
    }
    if behavioural:
        fields["structure_feedback"] = (StarAssessment, ...)
    if has_previous:
        fields["previous_attempt_comparison"] = (AttemptComparison, ...)
    fields["example_stronger_answer"] = (str, Field(min_length=40))
    return create_model("Feedback", **fields)


# --- Session summary -------------------------------------------------------------------------


class Priority(BaseModel):
    title: str
    why: str
    how_to_practise: str


class SessionSummaryOut(BaseModel):
    recurring_strengths: list[str] = Field(max_length=4)
    recurring_weaknesses: list[str] = Field(min_length=1, max_length=4)
    top_priorities: list[Priority] = Field(min_length=2, max_length=3)
    overall: str
