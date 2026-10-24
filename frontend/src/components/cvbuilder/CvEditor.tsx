import { useEffect, useRef, useState } from "react";
import { api, type CvBuild, type GeneratedCv } from "../../api/client";
import { useBuildAction } from "../../hooks/useBuildAction";
import { navigate } from "../../hooks/useHashRoute";
import JobMatches from "./JobMatches";
import Working from "./Working";

interface Fields {
  summary: string;
  education: string;
  skills: string;
  additional_education: string[];
  experience: string[];
  projects: string[];
}

function fieldsOf(cv: GeneratedCv): Fields {
  return {
    summary: cv.summary,
    education: cv.education,
    skills: cv.skills.join(", "),
    additional_education: (cv.additional_education ?? []).map((e) => e.text),
    experience: cv.experience.map((e) => e.description),
    projects: cv.projects.map((p) => p.description),
  };
}

function List({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div>
      <h4>{title}</h4>
      {items.length ? (
        <div className="tags">
          {items.map((s) => (
            <span key={s} className="tag no-caps">
              {s}
            </span>
          ))}
        </div>
      ) : (
        <p className="muted small">{empty}</p>
      )}
    </div>
  );
}

/** The tailored CV: edit, preview the PDF, download it, or go straight to practising for this job. */
export default function CvEditor({ build, onChange }: { build: CvBuild; onChange: (b: CvBuild) => void }) {
  const cv = build.cv;
  const [fields, setFields] = useState<Fields | null>(cv ? fieldsOf(cv) : null);
  const [dirty, setDirty] = useState(false);
  const [version, setVersion] = useState(0); // bumps the preview URL after a save
  const [pickJob, setPickJob] = useState(false);
  const { busy, error, elapsed, run, setError } = useBuildAction((b) => {
    onChange(b);
    if (b.cv) setFields(fieldsOf(b.cv));
    setDirty(false);
    setVersion((v) => v + 1);
  });
  const generating = useRef(false);

  // A job was just picked (or its requirement questions answered): write the CV.
  useEffect(() => {
    if (cv || generating.current) return;
    generating.current = true;
    run("Writing your tailored CV…", () => api.generateCv(build.id)).finally(() => (generating.current = false));
  }, [cv, build.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (pickJob) {
    const picked = (b: CvBuild) => {
      setPickJob(false);
      setFields(null);
      onChange(b);
    };
    return <JobMatches build={build} onChange={picked} onCancel={() => setPickJob(false)} />;
  }

  if (!cv || !fields) {
    return (
      <div className="card stack">
        <h2>Your CV for {build.selected_job?.title}</h2>
        {busy && <Working label={busy} elapsed={elapsed} />}
        {error && (
          <div className="banner error">
            {error} <button onClick={() => run("Writing your tailored CV…", () => api.generateCv(build.id))}>Retry</button>
          </div>
        )}
      </div>
    );
  }

  const edit = (patch: Partial<Fields>) => {
    setFields((f) => (f ? { ...f, ...patch } : f));
    setDirty(true);
  };
  const setAt = (key: "additional_education" | "experience" | "projects", i: number, v: string) =>
    edit({ [key]: fields[key].map((x, j) => (j === i ? v : x)) });

  function saveEdits() {
    return api.updateCv(build.id, {
      summary: fields!.summary,
      education: fields!.education,
      skills: fields!.skills.split(",").map((s) => s.trim()).filter(Boolean),
      additional_education: fields!.additional_education,
      experience: fields!.experience,
      projects: fields!.projects,
    });
  }

  function editProfile() {
    // Going back resets the job and this CV (they were built from the old profile).
    if (!window.confirm("Edit your profile? You'll pick a job again afterwards, and this CV, including your edits, will be regenerated.")) return;
    run("Opening your profile…", () => api.reopenProfile(build.id));
  }

  async function practise() {
    setError(null);
    await run("Preparing your practice interview…", async () => {
      const saved = dirty ? await saveEdits() : build;
      const session = await api.startPractice(build.id);
      navigate(`/s/${session.id}/cv`);
      return saved;
    });
  }

  const disabled = busy !== null;
  return (
    <div className="stack">
      <div className="card stack">
        <div className="page-head">
          <div>
            <h2>Your CV for {build.selected_job?.title}</h2>
            {build.selected_job?.location && <p className="muted small">{build.selected_job.location}</p>}
          </div>
          <div className="actions">
            <button onClick={() => setPickJob(true)} disabled={disabled}>
              Choose a different job
            </button>
            <button onClick={editProfile} disabled={disabled}>
              Edit profile
            </button>
          </div>
        </div>
        {build.last_resolution && (build.last_resolution.confirmed_skills.length > 0 || build.last_resolution.declined.length > 0) && (
          <div className="banner ok">
            {build.last_resolution.confirmed_skills.length > 0 && <>Added for this role: {build.last_resolution.confirmed_skills.join(", ")}. </>}
            {build.last_resolution.declined.length > 0 && <>Left off (not confirmed): {build.last_resolution.declined.join(", ")}.</>}
          </div>
        )}
        {cv.grounding_warnings.length > 0 && (
          <details className="banner warn">
            <summary>Some generated content didn't match your confirmed profile and was removed.</summary>
            <ul>
              {cv.grounding_warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </details>
        )}
        <div className="two-col">
          <List title="Matched skills" items={cv.matched_skills} empty="None" />
          <List title="Missing requirements" items={cv.missing_requirements} empty="None: you cover what the listing asks for." />
        </div>
      </div>

      <div className="actions practise-row">
        <button className="cta" onClick={practise} disabled={disabled}>
          Practise the interview for this job
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <path d="M5 12h14m-6-6 6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <a className="button" href={api.cvPdfUrl(build.id, true)} download>
          Download PDF
        </a>
      </div>
      {busy && <Working label={busy} elapsed={elapsed} />}
      {error && <div className="banner error">{error}</div>}

      <fieldset className="card stack" disabled={disabled}>
        <h3>Edit</h3>
        <p className="muted small">
          Edits only change this CV, not your confirmed profile, so they won't carry over if you pick a different job.
        </p>
        <label className="field">
          <span className="label">Summary</span>
          <textarea rows={4} value={fields.summary} onChange={(e) => edit({ summary: e.target.value })} />
        </label>
        <label className="field">
          <span className="label">Education</span>
          <textarea rows={2} value={fields.education} onChange={(e) => edit({ education: e.target.value })} />
        </label>
        {fields.additional_education.map((t, i) => (
          <label key={i} className="field">
            <span className="label">Additional qualification {i + 1}</span>
            <input type="text" value={t} onChange={(e) => setAt("additional_education", i, e.target.value)} />
          </label>
        ))}
        {cv.experience.map((e, i) => (
          <label key={i} className="field">
            <span className="label">{e.organisation ? `${e.role}, ${e.organisation}` : e.role}</span>
            <textarea rows={4} value={fields.experience[i]} onChange={(ev) => setAt("experience", i, ev.target.value)} />
          </label>
        ))}
        <label className="field">
          <span className="label">Skills (comma-separated)</span>
          <input type="text" value={fields.skills} onChange={(e) => edit({ skills: e.target.value })} />
        </label>
        {cv.projects.map((p, i) => (
          <label key={i} className="field">
            <span className="label">{p.title}</span>
            <textarea rows={4} value={fields.projects[i]} onChange={(e) => setAt("projects", i, e.target.value)} />
          </label>
        ))}
        <div className="actions">
          <button className="primary" onClick={() => run("Saving…", saveEdits)} disabled={!dirty}>
            Save &amp; refresh preview
          </button>
          {dirty && <span className="muted small">Unsaved changes</span>}
        </div>
      </fieldset>

      <div className="card stack">
        <h3>Preview</h3>
        <object className="pdf-frame" data={`${api.cvPdfUrl(build.id)}#v=${version}`} type="application/pdf" key={version}>
          <p className="muted">
            Your browser can't show PDFs inline. <a href={api.cvPdfUrl(build.id, true)}>Download the PDF</a> instead.
          </p>
        </object>
      </div>
    </div>
  );
}
