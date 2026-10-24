import { useEffect, useState } from "react";
import { api, type CvBuild, type CvBuildStage } from "../api/client";
import CvEditor from "../components/cvbuilder/CvEditor";
import FollowupChat from "../components/cvbuilder/FollowupChat";
import JobMatches from "../components/cvbuilder/JobMatches";
import ProfileForm from "../components/cvbuilder/ProfileForm";
import RequirementGaps from "../components/cvbuilder/RequirementGaps";

const STEPS: { label: string; stages: CvBuildStage[] }[] = [
  { label: "About you", stages: ["followup"] },
  { label: "Confirm profile", stages: ["confirm"] },
  { label: "Pick a job", stages: ["jobs", "requirements"] },
  { label: "Your CV", stages: ["cv"] },
];

function BuildProgress({ stage }: { stage: CvBuildStage }) {
  const current = STEPS.findIndex((s) => s.stages.includes(stage));
  return (
    <ol className="progress build-progress">
      {STEPS.map((s, i) => (
        <li key={s.label} className={i < current ? "done" : i === current ? "active" : "todo"}>
          {i < current ? "✓ " : `${i + 1}. `}
          {s.label}
        </li>
      ))}
    </ol>
  );
}

export default function BuildPage({ buildId }: { buildId: string }) {
  const [build, setBuild] = useState<CvBuild | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getBuild(buildId).then(setBuild).catch((err) => setError((err as Error).message));
  }, [buildId]);

  // Each stage scrolls to the top, as a new page would.
  const stage = build?.stage;
  useEffect(() => {
    if (stage) window.scrollTo(0, 0);
  }, [stage]);

  if (!build) {
    return error ? <div className="banner error">{error}</div> : <p className="muted">Loading…</p>;
  }

  // Keyed by stage (and job) so each step mounts fresh and plays the page transition.
  const key = `${build.stage}:${build.selected_job?.document_id ?? ""}`;
  return (
    <div className="stack">
      <BuildProgress stage={build.stage} />
      <div key={key} className="page-enter">
        {build.stage === "followup" && <FollowupChat build={build} onChange={setBuild} />}
        {build.stage === "confirm" && <ProfileForm build={build} onChange={setBuild} />}
        {build.stage === "jobs" && <JobMatches build={build} onChange={setBuild} />}
        {build.stage === "requirements" && <RequirementGaps build={build} onChange={setBuild} />}
        {build.stage === "cv" && <CvEditor build={build} onChange={setBuild} />}
      </div>
    </div>
  );
}
