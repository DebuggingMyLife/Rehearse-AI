import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type CvBuild } from "../../api/client";
import { useBuildAction } from "../../hooks/useBuildAction";
import Working from "./Working";

export function Conversation({ build }: { build: CvBuild }) {
  let lastPhase = "intake";
  return (
    <ol className="chat">
      {build.conversation.map((m, i) => {
        const divider = m.phase === "review" && lastPhase !== "review";
        lastPhase = m.phase;
        return (
          <li key={i} className={`msg ${m.role}`}>
            {divider && <div className="phase-divider">Project review</div>}
            <span className="msg-who">{m.role === "user" ? "You" : "CV Builder"}</span>
            <p>{m.text}</p>
          </li>
        );
      })}
    </ol>
  );
}

/** Intake follow-ups (everything outstanding in one combined question), then the project review
 *  (one missing date or outcome at a time). */
export default function FollowupChat({ build, onChange }: { build: CvBuild; onChange: (b: CvBuild) => void }) {
  const [reply, setReply] = useState("");
  const { busy, error, elapsed, run } = useBuildAction((b) => {
    setReply("");
    onChange(b);
  });
  const needsReviewStart = build.phase === "review" && !build.review_checked;
  const started = useRef(false);

  // Intake just finished: check the projects once, as its own step with its own progress line.
  useEffect(() => {
    if (!needsReviewStart || started.current) return;
    started.current = true;
    run("Checking your projects for anything missing…", () => api.startReview(build.id));
  }, [needsReviewStart, build.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(e: FormEvent) {
    e.preventDefault();
    await run("Thinking…", () => api.replyBuild(build.id, reply.trim()));
  }

  return (
    <div className="card stack">
      <h2>{build.phase === "review" ? "A quick check of your projects" : "A couple of follow-up questions"}</h2>
      <p className="muted small">
        {build.phase === "review"
          ? "One of your projects is missing a detail. Answer below, or say you don't have it and it'll be left off."
          : "Answer in your own words. Anything you state is saved as given; you'll confirm the whole profile at the end."}
      </p>
      <Conversation build={build} />

      {error && (
        <div className="banner error">
          {error}{" "}
          {needsReviewStart && (
            <button onClick={() => run("Checking your projects for anything missing…", () => api.startReview(build.id))}>
              Retry
            </button>
          )}
        </div>
      )}

      {build.pending_question && (
        <form className="stack" onSubmit={submit}>
          <label className="field">
            <span className="label">Your answer</span>
            <textarea rows={3} value={reply} onChange={(e) => setReply(e.target.value)} disabled={busy !== null} autoFocus />
          </label>
          <div className="actions">
            <button className="primary" type="submit" disabled={busy !== null || !reply.trim()}>
              Send answer
            </button>
          </div>
        </form>
      )}
      {busy && <Working label={busy} elapsed={elapsed} />}
    </div>
  );
}
