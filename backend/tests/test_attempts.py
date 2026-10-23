from pathlib import Path

AUDIO = b"\x1aE\xdf\xa3" + b"\x00" * 4096  # webm magic + padding


def upload(client, qid, data=AUDIO, mime="audio/webm;codecs=opus", duration="42.5"):
    return client.post(
        f"/api/questions/{qid}/attempts",
        files={"audio": ("answer.webm", data, mime)},
        data={"duration_s": duration},
    )


def test_rubric_hidden_until_first_attempt(client, question_id):
    q = client.get(f"/api/questions/{question_id}").json()
    assert q["status"] == "not_attempted" and q["rubric"] is None and q["attempts"] == []

    res = upload(client, question_id)
    assert res.status_code == 201, res.text
    a = res.json()
    assert a["attempt_number"] == 1 and a["status"] == "uploaded"
    assert a["audio_duration_s"] == 42.5
    assert "upload_ms" in a["timings"]

    q = client.get(f"/api/questions/{question_id}").json()
    assert q["status"] == "attempted" and q["attempt_count"] == 1
    assert q["rubric"] == ["Names the migration", "States the latency result"]


def test_attempt_numbers_increment_and_audio_served(client, question_id):
    upload(client, question_id)
    second = upload(client, question_id).json()
    assert second["attempt_number"] == 2

    audio = client.get(second["audio_url"])
    assert audio.status_code == 200
    assert audio.content == AUDIO
    assert audio.headers["content-type"].startswith("audio/webm")


def test_safari_mp4_is_accepted(client, question_id):
    res = upload(client, question_id, mime="audio/mp4")
    assert res.status_code == 201
    from app.db import SessionLocal
    from app.models import Attempt

    with SessionLocal() as db:
        assert Path(db.get(Attempt, res.json()["id"]).audio_path).suffix == ".m4a"


def test_rejects_bad_uploads(client, question_id):
    assert upload(client, question_id, mime="video/x-msvideo").status_code == 415
    assert upload(client, question_id, data=b"tiny").status_code == 422
    assert upload(client, question_id, duration="0").status_code == 422
    assert upload(client, 999999).status_code == 404


def test_missing_audio_file_gives_clear_404(client, question_id):
    a = upload(client, question_id).json()
    from app.db import SessionLocal
    from app.models import Attempt

    with SessionLocal() as db:
        Path(db.get(Attempt, a["id"]).audio_path).unlink()
    res = client.get(a["audio_url"])
    assert res.status_code == 404 and "retention" in res.json()["detail"]


def test_timestamps_are_utc(client, question_id):
    a = upload(client, question_id).json()
    assert a["created_at"].endswith(("Z", "+00:00"))
