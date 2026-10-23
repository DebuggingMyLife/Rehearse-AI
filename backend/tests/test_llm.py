import json
import logging

import httpx
import pytest

from app.config import Settings
from app.schemas.llm import QuestionBatch
from app.services.llm import LLMUnavailable, OllamaClient, inline_refs

VALID = {"questions": [{
    "question": "Tell me about a time you led a migration.",
    "type": "cv_specific", "difficulty": "medium",
    "points_a_strong_answer_would_mention": ["context", "own role", "measurable result"], "cv_evidence": [],
}]}


def client_with(responses, num_ctx=8192):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        content, prompt_tokens = responses[len(calls) - 1]
        return httpx.Response(200, json={
            "message": {"content": content}, "prompt_eval_count": prompt_tokens, "eval_count": 50,
        })

    settings = Settings(_env_file=None, llm_num_ctx=num_ctx)
    return OllamaClient(settings, httpx.Client(transport=httpx.MockTransport(handler))), calls


def test_valid_first_time_sends_required_options():
    llm, calls = client_with([(json.dumps(VALID), 100)])
    res = llm.chat_json("sys", "user", QuestionBatch, label="t")
    assert res.attempts == 1 and res.data.questions[0].type == "cv_specific"
    body = calls[0]
    assert body["options"]["num_ctx"] == 8192
    assert 0.2 <= body["options"]["temperature"] <= 0.3
    assert body["keep_alive"] and body["stream"] is False
    assert "$ref" not in json.dumps(body["format"])


def test_retries_once_with_validation_error():
    bad = json.dumps({"questions": [{**VALID["questions"][0], "points_a_strong_answer_would_mention": ["only one"]}]})
    llm, calls = client_with([(bad, 100), (json.dumps(VALID), 100)])
    res = llm.chat_json("sys", "user", QuestionBatch, label="t")
    assert res.attempts == 2
    retry_msg = calls[1]["messages"][-1]["content"]
    assert "invalid" in retry_msg and "points_a_strong_answer_would_mention" in retry_msg


def test_gives_up_after_two_failures():
    llm, _ = client_with([("not json", 100), ("{}", 100)])
    with pytest.raises(LLMUnavailable):
        llm.chat_json("sys", "user", QuestionBatch, label="t")


def test_warns_when_prompt_near_context_limit(caplog):
    llm, _ = client_with([(json.dumps(VALID), 900)], num_ctx=1000)
    with caplog.at_level(logging.WARNING):
        llm.chat_json("sys", "user", QuestionBatch, label="t")
    assert "exceed 80% of num_ctx=1000" in caplog.text


def test_unreachable_raises_unavailable():
    def boom(request):
        raise httpx.ConnectError("refused")

    llm = OllamaClient(Settings(_env_file=None), httpx.Client(transport=httpx.MockTransport(boom)))
    with pytest.raises(LLMUnavailable):
        llm.chat_json("sys", "user", QuestionBatch, label="t")


def test_inline_refs():
    schema = inline_refs(QuestionBatch.model_json_schema())
    assert "$defs" not in schema
    assert schema["properties"]["questions"]["items"]["properties"]["points_a_strong_answer_would_mention"]["minItems"] == 3
