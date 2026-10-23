import { useEffect, useRef, useState } from "react";
import {
  api,
  watchAttempt,
  type Attempt,
  type AttemptEvent,
  type AttemptMetrics,
  type QuestionDetail,
} from "../api/client";
import AttemptResult, { type LiveAttempt } from "../components/AttemptResult";
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

function metricsOf(a: Attempt): AttemptMetrics | null {
  if (a.wpm === null || a.delivery === null) return null;
  return {
    ...a.delivery,
    wpm: a.wpm,
    filler_count: a.filler_count ?? 0,
    filler_breakdown: a.filler_breakdown ?? {},
    long_pause_count: a.long_pause_count ?? 0,
  };
}

const STATUS_LABEL: Partial<Record<Attempt["status"], string>> = {
  too_short: "too short",
  failed: "failed",
  uploaded: "processing",
  transcribing: "processing",
  analysing: "processing",
};

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
              {a.wpm !== null && ` · ${Math.round(a.wpm)} wpm · ${a.filler_count} fillers`}
              {STATUS_LABEL[a.status] && ` · ${STATUS_LABEL[a.status]}`}
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
  const [live, setLive] = useState<LiveAttempt | null>(null);
  const closeStream = useRef<(() => void) | null>(null);
  const rec = useRecorder({ maxSeconds: limit });
  const unsupported = recordingUnsupportedReason();

  useEffect(() => {
    api.getQuestion(questionId).then(setQuestion).catch((err) => setLoadError((err as Error).message));
  }, [questionId]);

  useEffect(() => () => closeStream.current?.(), []);

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
      setLive({ status: attempt.status, transcript: null, metrics: null, final: null, connectionLost: false });
      closeStream.current = watchAttempt(attempt.id, onEvent, () =>
        setLive((l) => (l ? { ...l, connectionLost: true } : l)),
      );
    } catch (err) {
      setSubmitError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  function onEvent(e: AttemptEvent) {
    setLive((l) => {
      if (!l) return l;
      switch (e.type) {
        case "status":
          return { ...l, status: e.status };
        case "transcript":
          return { ...l, transcript: e.transcript };
        case "metrics":
          return { ...l, metrics: e.metrics };
        case "done":
          return {
            ...l,
            status: e.attempt.status,
            final: e.attempt,
            transcript: e.attempt.transcript,
            metrics: metricsOf(e.attempt),
          };
      }
    });
    if (e.type === "done") api.getQuestion(questionId).then(setQuestion).catch(() => {});
  }

  function tryAgain() {
    closeStream.current?.();
    setSubmitted(null);
    setLive(null);
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
          {question.attempt_count > 0 && (
            <span className="tag status-done">
              {question.attempt_count} attempt{question.attempt_count > 1 ? "s" : ""}
            </span>
          )}
        </div>
        <p className="q-hero-text">{question.text}</p>
      </div>

      <div className="card recorder">
        {unsupported ? (
          <div className="banner error">{unsupported}</div>
        ) : submitted && live ? (
          <div className="stack">
            <h3>
              Attempt {submitted.attempt_number}{" "}
              <span className="muted small">({formatTime(submitted.audio_duration_s ?? 0)})</span>
            </h3>
            <AttemptResult live={live} audioUrl={submitted.audio_url} />
            <div className="actions">
              {live.final?.status === "too_short" ? (
                <button className="primary" onClick={tryAgain}>
                  Re-record
                </button>
              ) : (
                <button className="primary" onClick={tryAgain} disabled={!live.final}>
                  Try again
                </button>
              )}
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

      <PreviousAttempts attempts={question.attempts.filter((a) => a.id !== submitted?.id)} />
    </div>
  );
}
