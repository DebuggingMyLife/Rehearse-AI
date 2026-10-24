import { useState } from "react";
import { api, type CvBuild, type DraftExperience, type DraftProject } from "../../api/client";
import { useBuildAction } from "../../hooks/useBuildAction";
import Working from "./Working";

const BLANK_EXPERIENCE: DraftExperience = { role: "", organisation: "", description: "", start_date: null, end_date: null };
const BLANK_PROJECT: DraftProject = {
  title: "", description: "", technologies: [], start_date: null, end_date: null,
  dates_declined: false, outcome_declined: false,
};

const splitList = (line: string) => line.split(",").map((s) => s.trim()).filter(Boolean);

function Text({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="field">
      <span className="label">{label}</span>
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function RemoveRow({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <div className="entry-head">
      <button type="button" className="link danger" onClick={onClick} aria-label={label}>
        Remove
      </button>
    </div>
  );
}

/** The whole-profile summary and edit form: the one point everything is confirmed together. */
export default function ProfileForm({ build, onChange }: { build: CvBuild; onChange: (b: CvBuild) => void }) {
  const d = build.draft;
  const [scalars, setScalars] = useState({
    name: d.name ?? "", email: d.email ?? "", phone: d.phone ?? "", github: d.github ?? "",
    linkedin: d.linkedin ?? "", degree: d.degree ?? "", institution: d.institution ?? "", year: d.year ?? "",
    summary: d.summary ?? "",
  });
  const [skills, setSkills] = useState(d.technical_skills.join(", "));
  const [roles, setRoles] = useState(d.target_roles.join(", "));
  const [achievements, setAchievements] = useState(d.achievements.join(", "));
  // At least one (blank) slot each, as in the old GUI, so a section can be added later.
  const [experience, setExperience] = useState<DraftExperience[]>(d.experience.length ? d.experience : [BLANK_EXPERIENCE]);
  const [projects, setProjects] = useState<DraftProject[]>(d.projects.length ? d.projects : [BLANK_PROJECT]);
  const [techLines, setTechLines] = useState(projects.map((p) => p.technologies.join(", ")));
  const { busy, error, elapsed, run } = useBuildAction(onChange);

  const set = (key: keyof typeof scalars) => (v: string) => setScalars((s) => ({ ...s, [key]: v }));
  const setExp = (i: number, patch: Partial<DraftExperience>) =>
    setExperience((rows) => rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const setProj = (i: number, patch: Partial<DraftProject>) =>
    setProjects((rows) => rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const removeExp = (i: number) => setExperience((rows) => rows.filter((_, j) => j !== i));
  const removeProj = (i: number) => {
    setProjects((rows) => rows.filter((_, j) => j !== i));
    setTechLines((lines) => lines.filter((_, j) => j !== i));
  };

  function save(confirm: boolean) {
    const edit = {
      ...scalars,
      technical_skills: splitList(skills),
      target_roles: splitList(roles),
      achievements: splitList(achievements),
      experience,
      projects: projects.map((p, i) => ({ ...p, technologies: splitList(techLines[i] ?? "") })),
      confirm,
    };
    return run(confirm ? "Finding matching jobs…" : "Updating your summary…", () => api.saveProfile(build.id, edit));
  }

  const disabled = busy !== null;
  return (
    <div className="stack">
      <div className="card stack">
        <h2>Confirm your profile</h2>
        {build.ended_at_step_limit && (
          <div className="banner warn">We couldn't get everything from the conversation. Fill in anything missing below.</div>
        )}
        {build.confirm_summary && <p className="prewrap">{build.confirm_summary}</p>}
      </div>

      <fieldset className="card stack" disabled={disabled}>
        <h3>Edit your profile</h3>
        <p className="muted small">Correct anything wrong, or fill in what the introduction didn't cover.</p>

        <h4>Contact details</h4>
        <Text label="Name" value={scalars.name} onChange={set("name")} />
        <div className="form-grid">
          <Text label="Email" value={scalars.email} onChange={set("email")} />
          <Text label="Phone" value={scalars.phone} onChange={set("phone")} />
          <Text label="GitHub" value={scalars.github} onChange={set("github")} />
          <Text label="LinkedIn" value={scalars.linkedin} onChange={set("linkedin")} />
        </div>

        <h4>Education</h4>
        <div className="form-grid">
          <Text label="Degree" value={scalars.degree} onChange={set("degree")} />
          <Text label="Year of study" value={scalars.year} onChange={set("year")} />
          <Text label="Institution" value={scalars.institution} onChange={set("institution")} />
        </div>

        <h4>Experience</h4>
        {!d.experience.length && (
          <p className="muted small">No work experience was mentioned. Leave this blank if you don't have any.</p>
        )}
        {experience.map((e, i) => (
          <div key={i} className="entry stack">
            <RemoveRow label={`Remove experience ${i + 1}`} onClick={() => removeExp(i)} />
            <div className="form-grid">
              <Text label={`Role ${i + 1}`} value={e.role ?? ""} onChange={(v) => setExp(i, { role: v })} />
              <Text label="Organisation" value={e.organisation ?? ""} onChange={(v) => setExp(i, { organisation: v })} />
            </div>
            <label className="field">
              <span className="label">Description</span>
              <textarea rows={3} value={e.description ?? ""} onChange={(ev) => setExp(i, { description: ev.target.value })} />
            </label>
          </div>
        ))}
        <button type="button" className="link" onClick={() => setExperience((rows) => [...rows, BLANK_EXPERIENCE])}>
          + Add experience
        </button>

        <h4>Skills and goals</h4>
        <Text label="Technical skills (comma-separated)" value={skills} onChange={setSkills} />
        <Text label="Target roles (comma-separated)" value={roles} onChange={setRoles} />
        <label className="field">
          <span className="label">Career summary</span>
          <textarea rows={3} value={scalars.summary} onChange={(e) => set("summary")(e.target.value)} />
        </label>
        <Text label="Achievements and activities (comma-separated)" value={achievements} onChange={setAchievements} />

        <h4>Projects</h4>
        {!d.projects.length && (
          <p className="muted small">No projects were mentioned. Leave this blank if you don't have any.</p>
        )}
        {projects.map((p, i) => (
          <div key={i} className="entry stack">
            <RemoveRow label={`Remove project ${i + 1}`} onClick={() => removeProj(i)} />
            <div className="form-grid">
              <Text label={`Project ${i + 1} title`} value={p.title} onChange={(v) => setProj(i, { title: v })} />
              <Text
                label="Technologies (comma-separated)"
                value={techLines[i] ?? ""}
                onChange={(v) => setTechLines((lines) => lines.map((l, j) => (j === i ? v : l)))}
              />
            </div>
            <label className="field">
              <span className="label">Description</span>
              <textarea rows={3} value={p.description ?? ""} onChange={(e) => setProj(i, { description: e.target.value })} />
            </label>
          </div>
        ))}
        <button
          type="button"
          className="link"
          onClick={() => {
            setProjects((rows) => [...rows, BLANK_PROJECT]);
            setTechLines((lines) => [...lines, ""]);
          }}
        >
          + Add project
        </button>
      </fieldset>

      {error && <div className="banner error">{error}</div>}
      <div className="actions">
        <button className="primary" onClick={() => save(true)} disabled={disabled || !scalars.name.trim()}>
          Confirm &amp; find matching jobs
        </button>
        <button onClick={() => save(false)} disabled={disabled}>
          Save changes
        </button>
        {busy && <Working label={busy} elapsed={elapsed} />}
      </div>
    </div>
  );
}
