import { useEffect, useState, type FormEvent } from "react";
import { api, type CvBuildSummary } from "../api/client";
import { navigate } from "../hooks/useHashRoute";

const ACCEPT = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

type Source = "upload" | "built";

export default function SetupPage() {
  const [source, setSource] = useState<Source>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [builds, setBuilds] = useState<CvBuildSummary[]>([]);
  const [buildId, setBuildId] = useState<string | null>(null);
  const [jd, setJd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listBuilds()
      .then((all) => setBuilds(all.filter((b) => b.has_cv)))
      .catch(() => setBuilds([]));
  }, []);

  const hasCv = source === "upload" ? file !== null : buildId !== null;
  const ready = hasCv && jd.trim().length >= 20 && !busy;

  function pickBuild(b: CvBuildSummary) {
    setBuildId(b.id);
    // Prefill from the job this CV was built for; it stays editable.
    setJd(b.job_description ?? "");
    setError(null);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session =
        source === "upload" ? await api.createSession(file!, jd) : await api.startPractice(buildId!, jd);
      navigate(`/s/${session.id}/cv`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>Start a mock interview</h2>

      <div className="segmented" role="tablist" aria-label="Which CV">
        <button type="button" role="tab" aria-selected={source === "upload"} className={source === "upload" ? "on" : ""}
          onClick={() => setSource("upload")}>
          Upload a CV
        </button>
        <button type="button" role="tab" aria-selected={source === "built"} className={source === "built" ? "on" : ""}
          onClick={() => setSource("built")}>
          Use a CV I built
        </button>
      </div>

      {source === "upload" ? (
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
      ) : builds.length === 0 ? (
        <p className="muted">
          You haven't built a CV yet. <a href="#/build">Build one</a> with the CV Builder, then come back.
        </p>
      ) : (
        <div className="field">
          <span className="label">Your built CVs</span>
          <ul className="build-list pickable">
            {builds.map((b) => (
              <li key={b.id}>
                <label>
                  <input type="radio" name="build" checked={buildId === b.id} onChange={() => pickBuild(b)} />
                  <strong>{b.name ?? "Untitled CV"}</strong>
                  {b.job_title && <span> · {b.job_title}</span>}
                </label>
                <span className="muted small">{new Date(b.updated_at).toLocaleDateString()}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

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
