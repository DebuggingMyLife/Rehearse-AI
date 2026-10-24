import { useEffect, useState } from "react";
import { api, type Session } from "../api/client";
import CvBuilderBadge from "../components/CvBuilderBadge";
import { navigate } from "../hooks/useHashRoute";
import { useElapsed } from "../hooks/useElapsed";

export default function CvConfirmPage({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<Session | null>(null);
  const [cvText, setCvText] = useState("");
  const [jd, setJd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const elapsed = useElapsed(busy);

  useEffect(() => {
    api
      .getSession(sessionId)
      .then((s) => {
        setSession(s);
        setCvText(s.cv_text);
        setJd(s.job_description);
      })
      .catch((err) => setError((err as Error).message));
  }, [sessionId]);

  if (!session) {
    return error ? <div className="banner error">{error}</div> : <p className="muted">Loading…</p>;
  }

  const hasQuestions = session.questions.length > 0;
  const edited = cvText !== session.cv_text || jd !== session.job_description;

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      if (edited) await api.updateSession(sessionId, { cv_text: cvText, job_description: jd });
      if (!hasQuestions) await api.generateQuestions(sessionId, { count: 5 });
      navigate(`/s/${sessionId}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="card stack">
      <h2>Check your CV was read correctly</h2>
      <CvBuilderBadge session={session} />
      <p className="muted">
        This is the text extracted from <strong>{session.cv_filename}</strong>. Questions and feedback are based only
        on this text, so fix anything that's missing or garbled.
      </p>

      <label className="field">
        <span className="label">
          CV text <span className="muted small">({cvText.length.toLocaleString()} characters)</span>
        </span>
        <textarea className="mono" rows={18} value={cvText} onChange={(e) => setCvText(e.target.value)} disabled={busy} />
      </label>

      <details>
        <summary>Job description</summary>
        <textarea rows={10} value={jd} onChange={(e) => setJd(e.target.value)} disabled={busy} />
      </details>

      {error && <div className="banner error">{error}</div>}

      <div className="actions">
        <button className="primary" onClick={confirm} disabled={busy || cvText.trim().length < 50}>
          {busy
            ? `Generating questions… ${elapsed}s`
            : hasQuestions
              ? edited
                ? "Save and continue"
                : "Continue to questions"
              : "Looks right, generate questions"}
        </button>
        {session.cv_build_id ? (
          <button onClick={() => navigate(`/build/${session.cv_build_id}`)} disabled={busy}>
            Back to your CV
          </button>
        ) : (
          <button onClick={() => navigate("/start")} disabled={busy}>
            Upload a different CV
          </button>
        )}
        {busy && !hasQuestions && <span className="muted small">Usually 10 to 20 seconds on a GPU.</span>}
      </div>
    </div>
  );
}
