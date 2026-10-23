import { useEffect, useState } from "react";
import { api, type Difficulty, type Question, type QuestionType, type Session } from "../api/client";
import { navigate } from "../hooks/useHashRoute";
import { useElapsed } from "../hooks/useElapsed";

const TYPE_LABEL: Record<QuestionType, string> = {
  behavioural: "Behavioural",
  technical: "Technical",
  cv_specific: "CV-specific",
};

function QuestionCard({ q, isNew }: { q: Question; isNew: boolean }) {
  return (
    <li className={`question ${isNew ? "new" : ""}`}>
      <div className="q-num">{q.position}</div>
      <div className="q-body">
        <p className="q-text">{q.text}</p>
        <div className="tags">
          <span className={`tag type-${q.type}`}>{TYPE_LABEL[q.type]}</span>
          <span className={`tag diff-${q.difficulty}`}>{q.difficulty}</span>
          {q.status === "attempted" ? (
            <span className="tag status-done">
              {q.attempt_count} attempt{q.attempt_count > 1 ? "s" : ""}
              {q.best_score !== null && ` · best ${q.best_score}/5`}
            </span>
          ) : (
            <span className="tag status-todo">Not attempted</span>
          )}
        </div>
      </div>
      <button disabled title="Recording arrives in milestone 3">
        Answer
      </button>
    </li>
  );
}

function GenerateMore({ sessionId, onAdded }: { sessionId: string; onAdded: (qs: Question[], msg: string) => void }) {
  const [count, setCount] = useState(3);
  const [type, setType] = useState<QuestionType | "">("");
  const [difficulty, setDifficulty] = useState<Difficulty | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const elapsed = useElapsed(busy);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.generateQuestions(sessionId, {
        count,
        type: type || null,
        difficulty: difficulty || null,
      });
      const n = res.questions.length;
      let msg = `Added ${n} question${n === 1 ? "" : "s"}.`;
      if (n < res.requested) {
        msg += ` ${res.requested - n} came out too similar to existing questions and were skipped.`;
      }
      onAdded(res.questions, msg);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card generate">
      <div className="generate-row">
        <strong>Generate more</strong>
        <select value={count} onChange={(e) => setCount(Number(e.target.value))} disabled={busy} aria-label="How many">
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value as QuestionType | "")} disabled={busy} aria-label="Type">
          <option value="">Any type</option>
          {(Object.keys(TYPE_LABEL) as QuestionType[]).map((t) => (
            <option key={t} value={t}>
              {TYPE_LABEL[t]}
            </option>
          ))}
        </select>
        <select
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value as Difficulty | "")}
          disabled={busy}
          aria-label="Difficulty"
        >
          <option value="">Any difficulty</option>
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>
        <button className="primary" onClick={generate} disabled={busy}>
          {busy ? `Generating… ${elapsed}s` : "Generate"}
        </button>
      </div>
      {error && <div className="banner error">{error}</div>}
    </div>
  );
}

export default function QuestionsPage({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newIds, setNewIds] = useState<Set<number>>(new Set());
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    api.getSession(sessionId).then(setSession).catch((err) => setError((err as Error).message));
  }, [sessionId]);

  if (!session) {
    return error ? <div className="banner error">{error}</div> : <p className="muted">Loading…</p>;
  }

  function added(qs: Question[], msg: string) {
    setSession((s) => (s ? { ...s, questions: [...s.questions, ...qs] } : s));
    setNewIds(new Set(qs.map((q) => q.id)));
    setNotice(msg);
  }

  const attempted = session.questions.filter((q) => q.status === "attempted").length;

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h2>Your questions</h2>
          <p className="muted small">
            {session.questions.length} questions · {attempted} attempted · CV: {session.cv_filename}{" "}
            <a href={`#/s/${sessionId}/cv`}>review</a>
          </p>
        </div>
        <button onClick={() => navigate("/")}>New session</button>
      </div>

      {session.questions.length === 0 ? (
        <div className="card">
          <p>No questions yet. Generate some below.</p>
        </div>
      ) : (
        <ul className="questions">
          {session.questions.map((q) => (
            <QuestionCard key={q.id} q={q} isNew={newIds.has(q.id)} />
          ))}
        </ul>
      )}

      {notice && <div className="banner ok">{notice}</div>}
      <GenerateMore sessionId={sessionId} onAdded={added} />
    </div>
  );
}
