import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { navigate } from "../hooks/useHashRoute";

const ACCEPT = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export default function SetupPage() {
  const [file, setFile] = useState<File | null>(null);
  const [jd, setJd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready = file !== null && jd.trim().length >= 20 && !busy;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const session = await api.createSession(file, jd);
      navigate(`/s/${session.id}/cv`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>Start a mock interview</h2>

      <label className="field">
        <span className="label">Your CV (PDF or DOCX)</span>
        <input
          type="file"
          accept={ACCEPT}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setError(null);
          }}
        />
      </label>

      <label className="field">
        <span className="label">Job description</span>
        <textarea
          rows={12}
          placeholder="Paste the full job description here"
          value={jd}
          onChange={(e) => setJd(e.target.value)}
        />
      </label>

      {error && <div className="banner error">{error}</div>}

      <div className="actions">
        <button className="primary" type="submit" disabled={!ready}>
          {busy ? "Reading your CV…" : "Continue"}
        </button>
      </div>
    </form>
  );
}
