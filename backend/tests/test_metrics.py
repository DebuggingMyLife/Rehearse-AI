from app.services.metrics import compute_metrics, count_fillers
from app.services.transcription import Transcript, Word


def words_at(text: str, start: float = 0.0, step: float = 0.4, gaps: dict[int, float] | None = None) -> list[Word]:
    """One word every `step` seconds; `gaps` adds extra silence before word index i."""
    out, t = [], start
    for i, w in enumerate(text.split()):
        t += (gaps or {}).get(i, 0.0)
        out.append(Word(w, round(t, 3), round(t + step * 0.8, 3)))
        t += step
    return out


def test_hesitations_always_count():
    assert count_fillers("Um, so I, uh, led the migration. Umm and erm hmm.") == {
        "um": 2, "uh": 1, "er": 1, "hmm": 1}


def test_like_only_counts_as_filler_when_set_off():
    assert count_fillers("It was, like, really slow.") == {"like": 1}
    assert count_fillers("Like, we had no tests.") == {"like": 1}
    assert count_fillers("I'd like to explain. It looks like Kafka. Something like that.") == {}


def test_phrase_fillers():
    assert count_fillers("You know, it was hard. I mean, really hard, you know.") == {"you know": 2, "i mean": 1}
    assert count_fillers("Do you know what happened? I mean the outage") == {}
    assert count_fillers("It was kind of, um, broken.") == {"kind of": 1, "um": 1}
    assert count_fillers("What kind of database did you use?") == {}


def test_wpm_uses_speaking_span_not_leading_silence():
    text = " ".join(["word"] * 60)
    # 60 words, one every 0.5 s, starting after 10 s of silence -> 30 s span -> ~120 wpm
    t = Transcript(text, words_at(text, start=10.0, step=0.5), duration_s=45.0)
    m = compute_metrics(t)
    assert m.word_count == 60
    assert 115 <= m.wpm <= 125
    assert m.long_pause_count == 0


def test_long_pauses():
    text = "one two three four five six seven eight nine ten eleven twelve"
    t = Transcript(text, words_at(text, gaps={4: 2.5, 8: 3.0, 10: 1.5}), duration_s=20.0)
    m = compute_metrics(t)
    assert m.long_pause_count == 2
    assert [p["at"] for p in m.pauses] == [t.words[3].end, t.words[7].end]
    assert m.longest_pause_s >= 3.0


def test_empty_transcript():
    m = compute_metrics(Transcript("", [], duration_s=5.0))
    assert m.word_count == 0 and m.wpm == 0 and m.filler_count == 0
