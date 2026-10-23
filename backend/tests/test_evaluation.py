import json

import pytest

from app.services import pipeline, transcription
from app.services.evaluation import quote_in_transcript
from app.services.llm import LLMResult, LLMUnavailable, TopLevelFieldStream
from tests.test_pipeline import LONG, FakeTranscriber, run

SCORING = {
    "rubric_coverage": [
        {"point": "paraphrased", "covered": True, "evidence_quote": "I led the migration of our payments ledger to Kafka"},
        {"point": "x", "covered": True, "evidence_quote": "we reduced costs by half"},  # never said
    ],
    "score": 4,
}
FEEDBACK = {
    "what_you_did_well": [{"point": "Named the project", "quote": "led the migration of our payments ledger"}],
    "what_could_be_improved": ["Explain your own decisions, not just the outcome."],
    "missed_opportunities": ["Ran both systems in parallel for six weeks"],
    "example_stronger_answer": "At PayLoop I led the payments ledger migration to Kafka. " * 3,
}


class FakeLLM:
    def __init__(self, fail_on: str | None = None):
        self.fail_on = fail_on
        self.calls: list[dict] = []

    def chat_json(self, system, user, model, *, label, on_field=None, **_):
        kind = "score" if model.__name__ == "Scoring" else "feedback"
        self.calls.append({"kind": kind, "system": system, "user": user, "fields": list(model.model_fields)})
        if kind == self.fail_on:
            raise LLMUnavailable("invalid twice")
        data = SCORING if kind == "score" else dict(FEEDBACK)
        if kind == "feedback":
            if "structure_feedback" in model.model_fields:
                data["structure_feedback"] = {
                    **{k: {"quote": "I led the migration", "comment": "ok"} for k in ("situation", "task", "action", "result")},
                    "overall": "ok"}
            if "previous_attempt_comparison" in model.model_fields:
                data["previous_attempt_comparison"] = {"addressed": [], "not_addressed": ["x"], "summary": "Same."}
            if on_field:
                for k, v in data.items():
                    on_field(k, v)
        return LLMResult(model.model_validate(data), 10, 100, 50, 1)


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setattr(transcription, "_transcriber", FakeTranscriber(LONG))

    def use(fail_on=None):
        llm = FakeLLM(fail_on)
        monkeypatch.setattr(pipeline, "get_llm", lambda: llm)
        return llm
    return use


def test_full_evaluation(client, question_id, fake_llm):
    llm = fake_llm()
    a = run(client, question_id)
    assert a["status"] == "complete" and a["error"] is None
    assert a["score"] == 4
    cov = a["scoring"]["rubric_coverage"]
    assert cov[0]["point"] == "Names the migration"  # real rubric text, not the paraphrase
    assert cov[0]["quote_verified"] is True
    assert cov[1]["quote_verified"] is False  # not something the candidate said...
    assert cov[1]["covered"] is False and cov[1]["unverified_claim"] is True  # ...so it doesn't count
    assert a["feedback"]["what_you_did_well"][0]["quote_verified"] is True
    assert a["feedback"]["structure_feedback"] is None  # cv_specific question
    assert a["feedback"]["previous_attempt_comparison"] is None
    for key in ("llm_score_ms", "llm_feedback_ms", "score_ready_ms", "first_feedback_ms"):
        assert key in a["timings"], key
    # Both calls share the same prefix so Ollama can reuse its KV cache.
    score_call, feedback_call = llm.calls
    assert score_call["system"] == feedback_call["system"]
    shared = score_call["user"].split("TASK:")[0]
    assert feedback_call["user"].startswith(shared)
    assert "TRANSCRIPT OF THE CANDIDATE'S ANSWER" in shared and LONG in shared


def test_second_attempt_gets_previous_feedback(client, question_id, fake_llm):
    llm = fake_llm()
    run(client, question_id)
    a = run(client, question_id)
    feedback_call = llm.calls[-1]
    assert "previous_attempt_comparison" in feedback_call["fields"]
    assert "PREVIOUS ATTEMPT AT THIS QUESTION (score 4/5)" in feedback_call["user"]
    assert "Explain your own decisions" in feedback_call["user"]
    comp = a["feedback"]["previous_attempt_comparison"]
    assert comp["previous_score"] == 4 and comp["not_addressed"] == ["x"]


def test_scoring_failure_keeps_transcript_and_metrics(client, question_id, fake_llm):
    fake_llm(fail_on="score")
    a = run(client, question_id)
    assert a["status"] == "complete"
    assert a["score"] is None and a["feedback"] is None
    assert "Feedback unavailable" in a["error"]
    assert a["transcript"] == LONG and a["wpm"] > 0


def test_feedback_failure_keeps_score(client, question_id, fake_llm):
    fake_llm(fail_on="feedback")
    a = run(client, question_id)
    assert a["score"] == 4 and a["feedback"] is None
    assert "Detailed feedback unavailable" in a["error"]


def test_quote_check_tolerates_small_wording_differences():
    t = "Um, at PayLoop I led the migration of our payments ledger to Kafka, and we cut settlement time."
    assert quote_in_transcript("I led the migration of our payments ledger to Kafka", t)
    assert quote_in_transcript("led the migration of the payment ledger to kafka", t)
    assert not quote_in_transcript("I reduced cloud costs by half", t)
    assert not quote_in_transcript("", t)


def test_streaming_parser_emits_fields_as_they_complete():
    doc = json.dumps({
        "what_you_did_well": [{"point": "a, b", "quote": "he said \"hi\", then {left}"}],
        "what_could_be_improved": ["x"],
        "structure_feedback": {"situation": "s", "task": "t"},
        "example_stronger_answer": "long text, with commas",
    })
    parser = TopLevelFieldStream()
    emitted = []
    for i in range(0, len(doc), 7):  # awkward chunk boundaries, including mid-escape
        emitted += [name for name, _ in parser.feed(doc[i:i + 7])]
    assert emitted == ["what_you_did_well", "what_could_be_improved", "structure_feedback",
                       "example_stronger_answer"]


def test_score_clamped_to_coverage_band():
    from app.services.evaluation import consistent_score

    assert consistent_score(1, covered=1, total=6) == 2  # 1 means "nothing covered"
    assert consistent_score(2, covered=6, total=6) == 4  # everything covered can't be a 2
    assert consistent_score(5, covered=0, total=4) == 2  # nothing covered can't be a 5
    assert consistent_score(3, covered=3, total=6) == 3  # consistent scores are untouched
    assert consistent_score(4, covered=3, total=6) == 4


# A real example answer from qwen2.5:7b during testing; the A/B testing claim was invented.
def test_example_answer_drops_invented_specifics():
    from app.services.evaluation import remove_unsupported_sentences

    sources = ("Led migration of the payments ledger to Kafka, reducing settlement latency from "
               "4 hours to 15 minutes. Designed idempotent payment APIs in Python/FastAPI.")
    text = ("I led the payments ledger migration to Kafka. It cut settlement to 15 minutes. "
            "We measured the improvements through A/B testing and Datadog. It saved 40% of costs.")
    kept, removed = remove_unsupported_sentences(text, sources)
    assert kept == "I led the payments ledger migration to Kafka. It cut settlement to 15 minutes."
    assert len(removed) == 2


def test_empty_strengths_fall_back_to_verified_coverage():
    from app.services.evaluation import _verify_quotes

    scoring = {"rubric_coverage": [
        {"point": "Names the migration", "evidence_quote": "led the migration", "covered": True, "quote_verified": True},
        {"point": "States results", "evidence_quote": "", "covered": False, "quote_verified": False},
    ]}
    value = _verify_quotes("what_you_did_well", [], "I led the migration", scoring)
    assert value == [{"point": "Names the migration", "quote": "led the migration", "quote_verified": True}]
