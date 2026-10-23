import pytest

from app.services import pipeline, transcription
from app.services.transcription import TranscriberInfo, Transcript, Word

LONG = ("Um, at PayLoop I led the migration of our payments ledger to Kafka, and we cut "
        "settlement from four hours to fifteen minutes")


class FakeTranscriber:
    def __init__(self, text: str):
        self.text = text
        self.info = TranscriberInfo("fake", "tiny", "cpu", "int8")

    def transcribe(self, path):
        words = [Word(w, i * 0.4, i * 0.4 + 0.3) for i, w in enumerate(self.text.split())]
        return Transcript(self.text, words, duration_s=len(words) * 0.4)


@pytest.fixture
def fake_whisper(monkeypatch):
    def use(text):
        monkeypatch.setattr(transcription, "_transcriber", FakeTranscriber(text))
    yield use


def run(client, question_id):
    from tests.test_attempts import upload

    attempt_id = upload(client, question_id).json()["id"]
    pipeline.process_attempt(attempt_id)
    return client.get(f"/api/attempts/{attempt_id}").json()


def test_full_answer_gets_transcript_metrics_and_timings(client, question_id, fake_whisper, monkeypatch):
    from tests.test_evaluation import FakeLLM

    monkeypatch.setattr(pipeline, "get_llm", lambda: FakeLLM())
    fake_whisper(LONG)
    a = run(client, question_id)
    assert a["status"] == "complete"
    assert a["transcript"] == LONG
    assert a["filler_breakdown"] == {"um": 1}
    assert a["wpm"] > 0 and a["long_pause_count"] == 0
    assert a["delivery"]["word_count"] == 23
    for key in ("upload_ms", "queue_ms", "transcription_ms", "metrics_ms", "total_ms"):
        assert key in a["timings"], key
    assert a["timings"]["whisper_device"] == "cpu/int8"


def test_under_ten_words_is_too_short_and_not_counted(client, question_id, fake_whisper):
    fake_whisper("I don't know, sorry.")
    a = run(client, question_id)
    assert a["status"] == "too_short"
    assert "4 words" in a["error"] and a["wpm"] is None
    q = client.get(f"/api/questions/{question_id}").json()
    assert q["status"] == "not_attempted" and q["rubric"] is None


def test_silence(client, question_id, fake_whisper):
    fake_whisper("")
    a = run(client, question_id)
    assert a["status"] == "too_short" and "couldn't hear any speech" in a["error"]


def test_whisper_not_loaded_fails_with_clear_message(client, question_id, monkeypatch):
    monkeypatch.setattr(transcription, "_transcriber", None)
    monkeypatch.setattr(transcription, "_load_error", "WHISPER_BACKEND=mlx is not installed")
    a = run(client, question_id)
    assert a["status"] == "failed" and "not installed" in a["error"]
