import { api, type CvBuild } from "../../api/client";
import { useBuildAction } from "../../hooks/useBuildAction";
import Working from "./Working";

/** The top 3 matched jobs. Picking one checks that job's stated requirements against the profile. */
export default function JobMatches({
  build,
  onChange,
  onCancel,
}: {
  build: CvBuild;
  onChange: (b: CvBuild) => void;
  onCancel?: () => void;
}) {
  const { busy, error, elapsed, run } = useBuildAction(onChange);
  return (
    <div className="card stack">
      <div className="page-head">
        <div>
          <h2>Pick a target job</h2>
          <p className="muted small">Your top 3 matches, most relevant first. Your CV will be tailored to the one you pick.</p>
        </div>
        {onCancel ? (
          <button onClick={onCancel} disabled={busy !== null}>
            Keep current job
          </button>
        ) : (
          <button onClick={() => run("Opening your profile…", () => api.reopenProfile(build.id))} disabled={busy !== null}>
            Edit profile
          </button>
        )}
      </div>
      <ul className="job-list">
        {build.job_matches.map((m) => (
          <li key={m.document_id} className={`job-card ${build.selected_job?.document_id === m.document_id ? "selected" : ""}`}>
            <div className="job-body">
              <h3>{m.title}</h3>
              {m.location && <p className="muted small">{m.location}</p>}
              {m.excerpt && <q className="quote">{m.excerpt}</q>}
            </div>
            <button
              className="primary"
              disabled={busy !== null}
              onClick={() =>
                run(`Checking the ${m.title} requirements against your profile…`, () => api.selectJob(build.id, m.document_id))
              }
            >
              Select
            </button>
          </li>
        ))}
      </ul>
      {error && <div className="banner error">{error}</div>}
      {busy && <Working label={busy} elapsed={elapsed} />}
    </div>
  );
}
