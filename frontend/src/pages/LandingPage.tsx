// Bundled (not loaded from a CDN) so the app keeps working offline.
import "@fontsource/mrs-saint-delafield/latin-400.css";
import { navigate } from "../hooks/useHashRoute";

const STEPS = [
  { title: "Add your CV and the job", body: "Upload a PDF or DOCX and paste the job description you're preparing for." },
  { title: "Answer out loud", body: "Get behavioural, technical and CV-specific questions, and answer them as you would in the room." },
  { title: "Get feedback in seconds", body: "See your score, what landed, what was missing, and a stronger answer built from your own CV." },
  { title: "Retry and improve", body: "Try the same question again and see exactly what changed since your last attempt." },
];

const FEATURES = [
  {
    icon: "M4 6h16M4 12h10M4 18h7",
    title: "Tailored questions",
    body: "Generated from your CV and the job description, with a hidden rubric for every question. Ask for more at any time.",
  },
  {
    icon: "M5 12l4 4L19 6",
    title: "Honest, specific feedback",
    body: "Scored against the rubric, not length or confidence. Feedback quotes what you actually said and never invents experience.",
  },
  {
    icon: "M12 3v12m0 0a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm-6-3a6 6 0 0 0 12 0M12 18v3",
    title: "Delivery coaching",
    body: "Pace, filler words and long pauses are measured from your recording, so you hear how you come across.",
  },
  {
    icon: "M4 17l5-5 4 4 7-7M14 9h6v6",
    title: "Track your progress",
    body: "Every retry is compared with the last. Watch scores move and see which improvement points you've addressed.",
  },
  {
    icon: "M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6l7-3z",
    title: "Private by design",
    body: "Speech recognition and the language model run on your own computer. Your CV and answers never leave it.",
  },
  {
    icon: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
    title: "Session report",
    body: "Finish with a summary of recurring strengths, weaknesses and your top priorities, and export it as a PDF.",
  },
];

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GetStarted({ label = "Get started" }: { label?: string }) {
  return (
    <button className="cta" onClick={() => navigate("/start")}>
      {label}
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <path d="M5 12h14m-6-6 6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}

/** A static preview of the feedback screen, so people see what they'll get. */
function Preview() {
  return (
    <div className="preview" aria-label="Example feedback">
      <div className="preview-q">
        <span className="tag">Behavioural</span>
        <span>Tell me about a time you disagreed with a stakeholder.</span>
      </div>
      <div className="preview-body">
        <div className="score score-4">
          <span className="score-num">4</span>
          <span className="score-of">/5</span>
          <span className="score-label">Good</span>
        </div>
        <ul className="coverage">
          <li className="yes">
            <span className="mark">✓</span>
            <div>
              Set out the situation and the disagreement
              <q className="quote">I disagreed, because our inventory sync hadn't been tested at that scale.</q>
            </div>
          </li>
          <li className="yes">
            <span className="mark">✓</span>
            <div>Backed the position with data</div>
          </li>
          <li className="no">
            <span className="mark">✗</span>
            <div>
              <div>Stated the outcome and what you learned</div>
            </div>
          </li>
        </ul>
      </div>
      <div className="preview-metrics">
        <span>
          <strong>142</strong> wpm
        </span>
        <span>
          <strong>2</strong> filler words
        </span>
        <span>
          <strong>0</strong> long pauses
        </span>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="landing">
      <section className="hero">
        <span className="eyebrow">
          <span className="eyebrow-dot" aria-hidden />
          Runs entirely on your computer
        </span>
        <h1 className="hero-title">
          Rehearse your next interview{" "}
          <span className="accent-line">
            <span className="accent">out loud</span>
          </span>
        </h1>
        <p className="hero-sub">
          RehearseAI asks the questions this role will ask you, listens to your spoken answers, and gives you
          honest, specific feedback in seconds, based on your own CV.
        </p>
        <div className="hero-cta">
          <GetStarted />
          <span className="muted small">No account. No cloud. About ten minutes a session.</span>
        </div>
        <Preview />
      </section>

      <section className="landing-section">
        <h2 className="section-title">How it works</h2>
        <ol className="steps">
          {STEPS.map((s, i) => (
            <li key={s.title}>
              <span className="step-num">{i + 1}</span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-section">
        <h2 className="section-title">Practice that feels like the real thing</h2>
        <div className="features">
          {FEATURES.map((f) => (
            <div key={f.title} className="feature">
              <span className="feature-icon">
                <Icon d={f.icon} />
              </span>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="closing">
        <h2>Walk into your next interview having already answered the questions.</h2>
        <GetStarted label="Start practising" />
      </section>
    </div>
  );
}
