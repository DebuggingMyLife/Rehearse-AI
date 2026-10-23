import { useEffect, useState } from "react";
import { api, type Attempt, type QuestionDetail } from "../api/client";
import { navigate } from "../hooks/useHashRoute";
import { recordingUnsupportedReason, useRecorder } from "../hooks/useRecorder";

const TIME_LIMITS: { label: string; seconds: number | null }[] = [
  { label: "1 min", seconds: 60 },
  { label: "2 min", seconds: 120 },
  { label: "3 min", seconds: 180 },
  { label: "5 min", seconds: 300 },
  { label: "No limit", seconds: null },
];
const DEFAULT_LIMIT = 120;
const LIMIT_KEY = "retake.timeLimit";
const WARN_REMAINING_S = 15;
const SHORT_ANSWER_S = 5;

function loadLimit(): number | null {
  try {
    const v = localStorage.getItem(LIMIT_KEY);
    if (v === "none") return null;
    if (v && TIME_LIMITS.some((t) => String(t.seconds) === v)) return Number(v);
  } catch {
    /* storage unavailable */
  }
  return DEFAULT_LIMIT;
}

function saveLimit(seconds: number | null) {
  try {
    localStorage.setItem(LIMIT_KEY, seconds === null ? "none" : String(seconds));
  } catch {
    /* storage unavailable */
  }
}

export function formatTime(s: number): string {
  const total = Math.max(0, Math.floor(s));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function PreviousAttempts({ attempts }: { attempts: Attempt[] }) {
  if (attempts.length === 0) return null;
  return (
    <div className="card stack">
      <h3>Previous attempts</h3>
      <ul className="attempts">
        {[...attempts].reverse().map((a) => (
          <li key={a.id}>
            <span className="muted small">
              Attempt {a.attempt_number} · {a.audio_duration_s ? formatTime(a.audio_duration_s) : "?"} ·{" "}
              {new Date(a.created_at).toLocaleString()}
            </span>
            {a.audio_url ? (
              <audio controls preload="none" src={a.audio_url} />
            ) : (
              <span className="muted small">Audio deleted</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function AttemptPage({ sessionId, questionId }: { sessionId: string; questionId: number }) {
  const [question, setQuestion] = useState<QuestionDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [limit, setLimit] = useState<number | null>(loadLimit);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<Attempt | null>(null);
  const rec = useRecorder({ maxSeconds: limit });
  const unsupported = recordingUnsupportedReason();

  useEffect(() => {
    api.getQuestion(questionId).then(setQuestion).catch((err) => setLoadError((err as Error).message));
  }, [questionId]);

  // Warn before leaving with an unsubmitted recording.
  const unsaved = rec.state === "recording" || (rec.state === "recorded" && !submitted);
  useEffect(() => {
    if (!unsaved) return;
    const handler = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [unsaved]);

  if (!question) {
    return loadError ? <div className="banner error">{loadError}</div> : <p className="muted">Loading…</p>;
  }

  async function submit() {
    if (!rec.recording) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const attempt = await api.submitAttempt(questionId, rec.recording.blob, rec.recording.durationS);
      setSubmitted(attempt);
      setQuestion(await api.getQuestion(questionId));
    } catch (err) {
      setSubmitError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  function tryAgain() {
    setSubmitted(null);
    rec.discard();
  }

  function back() {
    if (unsaved && !window.confirm("Discard your unsubmitted recording?")) return;
    navigate(`/s/${sessionId}`);
  }

  const remaining = limit !== null ? limit - rec.elapsed : null;
  const tooShort = rec.recording !== null && rec.recording.durationS < SHORT_ANSWER_S;

  return (
    <div className="stack">
      <button className="link" onClick={back}>
        ← All questions
      </button>

      <div className="card question-hero">
        <div className="tags">
          <span className="tag">Question {question.position}</span>
          <span className="tag">{question.type === "cv_specific" ? "CV-specific" : question.type}</span>
          <span className="tag">{question.difficulty}</span>
          {question.attempt_count > 0 && <span className="tag status-done">{question.attempt_count} previous</span>}
        </div>
        <p className="q-hero-text">{question.text}</p>
      </div>

      <div className="card recorder">
        {unsupported ? (
          <div className="banner error">{unsupported}</div>
        ) : submitted ? (
          <div className="stack">
            <div className="banner ok">
              Answer saved as attempt {submitted.attempt_number} ({formatTime(submitted.audio_duration_s ?? 0)}).
              Transcription and feedback are added in milestones 4 and 5.
            </div>
            <div className="actions">
              <button className="primary" onClick={tryAgain}>
                Try again
              </button>
              <button onClick={() => navigate(`/s/${sessionId}`)}>Next question</button>
            </div>
          </div>
        ) : (
          <div className="stack">
            <div className="recorder-top">
              <label className="muted small">
                Time limit{" "}
                <select
                  value={limit === null ? "none" : String(limit)}
                  disabled={rec.state === "recording" || rec.state === "requesting"}
                  onChange={(e) => {
                    const v = e.target.value === "none" ? null : Number(e.target.value);
                    setLimit(v);
                    saveLimit(v);
                  }}
                >
                  {TIME_LIMITS.map((t) => (
                    <option key={t.label} value={t.seconds === null ? "none" : String(t.seconds)}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {rec.state === "recording" ? (
              <div className="recording-live">
                <span className="rec-dot" aria-hidden />
                <span className="rec-label">Recording</span>
                <span
                  className={`rec-timer ${remaining !== null && remaining <= WARN_REMAINING_S ? "warn" : ""}`}
                  aria-live="off"
                >
                  {formatTime(rec.elapsed)}
                  {limit !== null && <span className="muted"> / {formatTime(limit)}</span>}
                </span>
                <div className="level" aria-label="Microphone level">
                  <div className="level-fill" style={{ width: `${Math.round(rec.level * 100)}%` }} />
                </div>
                <button className="stop" onClick={rec.stop}>
                  ■ Stop
                </button>
              </div>
            ) : rec.state === "recorded" && rec.recording ? (
              <div className="stack">
                <div className="playback">
                  <audio controls src={rec.recording.url} />
                  <span className="muted small">{formatTime(rec.recording.durationS)}</span>
                </div>
                {tooShort && (
                  <div className="banner warn">That was very short. You may want to re-record a fuller answer.</div>
                )}
                {submitError && <div className="banner error">{submitError}</div>}
                <div className="actions">
                  <button className="primary" onClick={submit} disabled={submitting}>
                    {submitting ? "Uploading…" : "Submit answer"}
                  </button>
                  <button onClick={rec.start} disabled={submitting}>
                    Re-record
                  </button>
                </div>
              </div>
            ) : (
              <div className="stack">
                <button className="record" onClick={rec.start} disabled={rec.state === "requesting"}>
                  {rec.state === "requesting" ? "Waiting for microphone…" : "● Start recording"}
                </button>
                <p className="muted small center">
                  Answer out loud as you would in a real interview. The recording stops automatically at the time
                  limit.
                </p>
              </div>
            )}

            {rec.error && <div className="banner error">{rec.error}</div>}
          </div>
        )}
      </div>

      <PreviousAttempts attempts={question.attempts} />
    </div>
  );
}
