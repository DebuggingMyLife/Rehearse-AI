import { useState, type FormEvent } from "react";
import { api, type CvBuild } from "../../api/client";
import { useBuildAction } from "../../hooks/useBuildAction";
import Working from "./Working";

/** The selected job's requirements the profile doesn't show yet: one combined question, one reply. */
export default function RequirementGaps({ build, onChange }: { build: CvBuild; onChange: (b: CvBuild) => void }) {
  const [reply, setReply] = useState("");
  const { busy, error, elapsed, run } = useBuildAction(onChange);

  function submit(e: FormEvent) {
    e.preventDefault();
    run("Updating your profile…", () => api.answerRequirements(build.id, reply.trim()));
  }

  return (
    <form className="card stack" onSubmit={submit}>
      <h2>{build.selected_job?.title}: a few more questions</h2>
      <p className="muted small">
        This listing asks for things your profile doesn't show yet. Answer honestly: anything you don't confirm won't
        appear on your CV, and the practice interview will ask how you'd handle it instead.
      </p>
      {build.requirement_gaps && (
        <div className="tags">
          {build.requirement_gaps.map((g) => (
            <span key={g.requirement} className="tag gap-tag">
              {g.requirement}
            </span>
          ))}
        </div>
      )}
      <ol className="chat">
        <li className="msg agent">
          <span className="msg-who">CV Builder</span>
          <p>{build.requirement_question}</p>
        </li>
      </ol>
      <label className="field">
        <span className="label">Your answer</span>
        <textarea rows={3} value={reply} onChange={(e) => setReply(e.target.value)} disabled={busy !== null} autoFocus />
      </label>
      {error && <div className="banner error">{error}</div>}
      <div className="actions">
        <button className="primary" type="submit" disabled={busy !== null || !reply.trim()}>
          Send answer
        </button>
        <button
          type="button"
          disabled={busy !== null}
          onClick={() => run("Skipping…", () => api.answerRequirements(build.id, null))}
        >
          I don't have these
        </button>
        {busy && <Working label={busy} elapsed={elapsed} />}
      </div>
    </form>
  );
}
