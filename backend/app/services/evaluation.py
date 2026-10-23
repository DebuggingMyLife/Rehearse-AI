"""Two-call evaluation of an answer: (1) rubric coverage + score, (2) written feedback.

Both prompts start with the same system message and context block (question, rubric, CV,
JD, transcript), so Ollama can reuse the KV cache from call 1 and only process the
call-specific tail in call 2.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import prompts
from ..models import Attempt, AttemptStatus, Question, QuestionType
from ..schemas.llm import feedback_model, scoring_model
from .llm import OllamaClient
from .text import norm, overlap

log = logging.getLogger(__name__)

# Tighter than question generation: the transcript and the call-2 output also need room.
MAX_CV_CHARS = 8_000
MAX_JD_CHARS = 3_000
QUOTE_MIN_OVERLAP = 0.75
ADDRESSED_MIN_OVERLAP = 0.4


@dataclass
class EvaluationContext:
    question: str
    question_type: str
    difficulty: str
    rubric: list[str]
    cv_text: str
    job_description: str
    transcript: str
    cv_evidence: list[str]
    behavioural: bool

    def prompt_vars(self) -> dict:
        return {
            "question": self.question, "question_type": self.question_type.replace("_", "-"),
            "difficulty": self.difficulty, "rubric": self.rubric, "cv_text": self.cv_text,
            "job_description": self.job_description, "transcript": self.transcript,
        }


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n[...truncated]"


def build_context(question: Question, transcript: str) -> EvaluationContext:
    session = question.session
    return EvaluationContext(
        question=question.text,
        question_type=question.type.value,
        difficulty=question.difficulty.value,
        rubric=list(question.rubric),
        cv_text=_truncate(session.cv_text, MAX_CV_CHARS),
        job_description=_truncate(session.job_description, MAX_JD_CHARS),
        transcript=transcript,
        cv_evidence=list(question.cv_evidence or []),
        behavioural=question.type == QuestionType.behavioural,
    )


def quote_in_transcript(quote: str, transcript: str) -> bool:
    """Is this (claimed) quote really something the candidate said? Allows small
    differences in wording/punctuation, since models rarely copy verbatim."""
    q = norm(quote)
    if not q:
        return False
    return q in norm(transcript) or overlap(quote, transcript) >= QUOTE_MIN_OVERLAP


def consistent_score(score: int, covered: int, total: int) -> int:
    """Clamp the model's score into the band its own rubric coverage supports. The 7B model
    occasionally returns e.g. 1/5 with a point covered, or 2/5 with everything covered."""
    ratio = covered / total if total else 0.0
    expected = round(1 + 4 * ratio)
    low, high = max(1, expected - 1), min(5, expected + 1)
    if covered > 0:
        low = max(low, 2)  # the anchors define 1 as "no rubric point covered"
    if covered == 0:
        high = min(high, 2)
    return min(max(score, low), high)


def score_answer(llm: OllamaClient, ctx: EvaluationContext, label: str) -> tuple[dict, int]:
    system, user = prompts.render("evaluate_score", **ctx.prompt_vars())
    res = llm.chat_json(system, user, scoring_model(len(ctx.rubric)), label=f"score:{label}",
                        num_predict=120 * len(ctx.rubric) + 60)
    data = res.data.model_dump()
    for i, item in enumerate(data["rubric_coverage"]):
        item["point"] = ctx.rubric[i]  # the model sometimes paraphrases; keep the real rubric text
        if not item["covered"]:
            item["evidence_quote"] = ""
        item["quote_verified"] = bool(item["evidence_quote"]) and quote_in_transcript(
            item["evidence_quote"], ctx.transcript)
        if item["covered"] and not item["quote_verified"]:
            # Coverage "evidenced" by words the candidate never said (often copied from the CV)
            # doesn't count.
            item["covered"] = False
            item["unverified_claim"] = True
    covered = sum(1 for c in data["rubric_coverage"] if c["covered"])
    adjusted = consistent_score(data["score"], covered, len(ctx.rubric))
    if adjusted != data["score"]:
        log.info("[score:%s] model score %d inconsistent with %d/%d covered; adjusted to %d",
                 label, data["score"], covered, len(ctx.rubric), adjusted)
        data["model_score"] = data["score"]
        data["score"] = adjusted
    return data, res.duration_ms


# Capitalised names/tools and numbers: the kind of detail a model invents ("A/B testing",
# "Datadog", "40%"). Sentence-initial words and "I" are skipped.
_SPECIFIC_RE = re.compile(r"(?<!^)(?<![.!?] )\b(?:[A-Z][A-Za-z0-9+#/.-]*[A-Za-z0-9+#]|\d[\d,.]*%?)")
_NOT_SPECIFIC = {"I", "I'm", "I've", "I'd", "OK"}


def remove_unsupported_sentences(text: str, sources: str) -> tuple[str, list[str]]:
    """Drop sentences naming numbers, tools or names that appear in neither the CV nor the
    transcript, so the model answer never puts invented facts in the candidate's mouth."""
    haystack = sources.lower()
    kept, removed = [], []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        specifics = [t for t in _SPECIFIC_RE.findall(sentence) if t not in _NOT_SPECIFIC]
        unsupported = [t for t in specifics if t.lower().rstrip(".,") not in haystack]
        (removed if unsupported else kept).append(sentence)
    return " ".join(kept), removed


def previous_feedback(db: Session, attempt: Attempt) -> dict | None:
    """Most recent earlier attempt at the same question that got feedback."""
    prev = db.scalars(
        select(Attempt)
        .where(Attempt.question_id == attempt.question_id, Attempt.attempt_number < attempt.attempt_number,
               Attempt.status == AttemptStatus.complete, Attempt.feedback_json.is_not(None))
        .order_by(Attempt.attempt_number.desc())
    ).first()
    if prev is None:
        return None
    return {
        "attempt_number": prev.attempt_number,
        "score": prev.score,
        "improvements": prev.feedback_json.get("what_could_be_improved", []),
    }


def _verify_quotes(field: str, value, transcript: str, scoring: dict | None = None):
    if field == "what_you_did_well" and isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                item["quote_verified"] = quote_in_transcript(item.get("quote", ""), transcript)
        if not value and scoring:
            # The model sometimes returns no strengths despite covering rubric points; fall
            # back to the verified covered points so the feedback agrees with the score.
            value.extend({"point": c["point"], "quote": c["evidence_quote"], "quote_verified": True}
                         for c in scoring["rubric_coverage"] if c["covered"] and c["quote_verified"])
    if field == "previous_attempt_comparison" and isinstance(value, dict) and scoring:
        # The model sometimes claims improvements the candidate never talked about. Keep an
        # "addressed" item only if it shows up in this transcript or in a covered rubric point.
        covered = [c["point"] for c in scoring["rubric_coverage"] if c["covered"]]
        keep, moved = [], []
        for item in value.get("addressed", []):
            supported = overlap(item, transcript) >= ADDRESSED_MIN_OVERLAP or any(
                overlap(item, point) >= 0.6 for point in covered)
            (keep if supported else moved).append(item)
        value["addressed"] = keep
        value["not_addressed"] = list(value.get("not_addressed", [])) + moved
    if field == "structure_feedback" and isinstance(value, dict):
        for part in ("situation", "task", "action", "result"):
            p = value.get(part)
            if isinstance(p, dict):
                p["quote_verified"] = quote_in_transcript(p.get("quote", ""), transcript)
    return value


def write_feedback(
    llm: OllamaClient,
    ctx: EvaluationContext,
    scoring: dict,
    previous: dict | None,
    label: str,
    on_field: Callable[[str, object], None] | None = None,
) -> tuple[dict, int]:
    system, user = prompts.render(
        "evaluate_feedback", **ctx.prompt_vars(), score=scoring["score"], coverage=scoring["rubric_coverage"],
        cv_evidence=ctx.cv_evidence, previous=previous, behavioural=ctx.behavioural,
    )

    def stream_field(name, value):
        if on_field:
            on_field(name, _verify_quotes(name, value, ctx.transcript, scoring))

    res = llm.chat_json(
        system, user, feedback_model(ctx.behavioural, previous is not None), label=f"feedback:{label}",
        num_predict=1200, on_field=stream_field if on_field else None,
    )
    data = res.data.model_dump()
    _verify_quotes("what_you_did_well", data["what_you_did_well"], ctx.transcript, scoring)
    if data.get("structure_feedback"):
        _verify_quotes("structure_feedback", data["structure_feedback"], ctx.transcript)
    if data.get("previous_attempt_comparison"):
        _verify_quotes("previous_attempt_comparison", data["previous_attempt_comparison"], ctx.transcript, scoring)
    example, removed = remove_unsupported_sentences(
        data["example_stronger_answer"], f"{ctx.cv_text}\n{ctx.transcript}\n{ctx.question}")
    if removed:
        log.info("[feedback:%s] removed %d example-answer sentence(s) with details not in the CV or transcript",
                 label, len(removed))
        data["example_stronger_answer"] = example
        data["example_answer_sentences_removed"] = len(removed)
    data.setdefault("structure_feedback", None)
    data.setdefault("previous_attempt_comparison", None)
    if previous is not None and data["previous_attempt_comparison"] is not None:
        data["previous_attempt_comparison"]["previous_attempt_number"] = previous["attempt_number"]
        data["previous_attempt_comparison"]["previous_score"] = previous["score"]
    return data, res.duration_ms
