import { useEffect, useRef, useState } from "react";
import { api, type Session, type SessionSummary } from "../api/client";
import { ScoreBadge } from "../components/FeedbackView";
import { navigate } from "../hooks/useHashRoute";
import { useElapsed } from "../hooks/useElapsed";

function Stat({ value, label, note }: { value: string; label: string; note?: string }) {
  return (
    <div className="metric">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
      {note && <div className="metric-note">{note}</div>}
    </div>
  );
}

function SummaryBody({ session, summary }: { session: Session; summary: SessionSummary }) {
  const { stats } = summary;
  const d = stats.delivery;
  const answered = session.questions.filter((q) => q.best_score !== null);
  return (
    <div className="stack">
      <div className="metrics">
        <Stat
          value={stats.avg_best_score !== null ? `${stats.avg_best_score}/5` : "–"}
          label="average best score"
          note={`${stats.questions_answered} of ${stats.questions_total} questions answered`}
        />
        <Stat value={d.avg_wpm !== null ? String(d.avg_wpm) : "–"} label="words per minute" note="Aim for 120 to 160." />
        <Stat
          value={d.fillers_per_min !== null ? String(d.fillers_per_min) : "–"}
          label="filler words per minute"
          note={d.avg_fillers !== null ? `${d.avg_fillers} per answer` : undefined}
        />
        <Stat
          value={d.avg_long_pauses !== null ? String(d.avg_long_pauses) : "–"}
          label="pauses over 2 s per answer"
        />
      </div>

      <section className="fb-section">
        <h4>Overall</h4>
        <p>{summary.overall}</p>
      </section>

      <section className="fb-section">
        <h4>Most important things to work on</h4>
        <ol className="priorities">
          {summary.top_priorities.map((p, i) => (
            <li key={i}>
              <strong>{p.title}</strong>
              <div>{p.why}</div>
              <div className="muted small">Practise: {p.how_to_practise}</div>
            </li>
          ))}
        </ol>
      </section>

      <div className="two-col">
        <section className="fb-section">
          <h4>Recurring strengths</h4>
          {summary.recurring_strengths.length ? (
            <ul className="ticks yes">
              {summary.recurring_strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">No clear recurring strengths yet.</p>
          )}
        </section>
        <section className="fb-section">
          <h4>Recurring weaknesses</h4>
          <ul className="ticks no">
            {summary.recurring_weaknesses.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </section>
      </div>

      <section className="fb-section">
        <h4>Questions</h4>
        <ul className="summary-questions">
          {answered.map((q) => (
            <li key={q.id}>
              <ScoreBadge score={q.best_score!} />
              <div>
                <a href={`#/s/${session.id}/q/${q.id}`}>{q.text}</a>
                <div className="muted small">
                  {q.scores.length > 1 ? `Scores over attempts: ${q.scores.join(" → ")}` : "1 scored attempt"}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export default function SummaryPage({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<Session | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const elapsed = useElapsed(busy);
  const autoStarted = useRef(false); // StrictMode runs effects twice; summarise only once

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      setSession(await api.endSession(sessionId));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    api
      .getSession(sessionId)
      .then((s) => {
        setSession(s);
        if (!s.summary && !autoStarted.current) {
          autoStarted.current = true;
          void generate();
        }
      })
      .catch((err) => setError((err as Error).message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h2>Session summary</h2>
          {session?.ended_at && (
            <p className="muted small">Ended {new Date(session.ended_at).toLocaleString()}</p>
          )}
        </div>
        <div className="actions">
          <a className="button primary" href={`/api/sessions/${sessionId}/export.pdf`} download>
            Export PDF
          </a>
          <button onClick={() => navigate(`/s/${sessionId}`)}>Back to questions</button>
        </div>
      </div>

      {error && <div className="banner error">{error}</div>}
      {busy && (
        <div className="card">
          <p className="pending">Summarising your session… {elapsed}s</p>
        </div>
      )}
      {session?.summary && !busy && (
        <div className="card">
          <SummaryBody session={session} summary={session.summary} />
          <div className="actions" style={{ marginTop: 16 }}>
            <button onClick={generate}>Regenerate summary</button>
            <span className="muted small">Regenerate after answering more questions.</span>
          </div>
        </div>
      )}
    </div>
  );
}
