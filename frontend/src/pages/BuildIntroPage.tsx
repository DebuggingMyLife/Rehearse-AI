import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import Working from "../components/cvbuilder/Working";
import { useElapsed } from "../hooks/useElapsed";
import { navigate } from "../hooks/useHashRoute";

const PLACEHOLDER =
  "e.g. I'm Priya, a third-year Bachelor of Computing Science student at UTS. I know Python, SQL and React. " +
  "Last semester I built a study-planner web app with a team of four... I'm looking for graduate software " +
  "engineering roles.";

export default function BuildIntroPage() {
  const [intro, setIntro] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const elapsed = useElapsed(busy);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const build = await api.createBuild(intro.trim());
      navigate(`/build/${build.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <form className="card stack" onSubmit={submit}>
        <h2>Build a CV</h2>
        <p className="muted">
          Tell us about yourself in your own words. The CV Builder asks a few follow-up questions, matches you to
          jobs, and writes a tailored CV using only what you've told it.
        </p>
        <label className="field">
          <span className="label">Introduction</span>
          <span className="muted small">Your education, skills, projects or experience, and the roles you're after.</span>
          <textarea rows={9} placeholder={PLACEHOLDER} value={intro} onChange={(e) => setIntro(e.target.value)} disabled={busy} />
        </label>
        {error && <div className="banner error">{error}</div>}
        <div className="actions">
          <button className="primary" type="submit" disabled={busy || intro.trim().length < 20}>
            Start
          </button>
          {busy && <Working label="Reading your introduction…" elapsed={elapsed} />}
        </div>
      </form>
    </div>
  );
}
