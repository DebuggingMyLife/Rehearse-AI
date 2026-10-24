// Bundled (not loaded from a CDN) so the app keeps working offline.
import "@fontsource/mrs-saint-delafield/latin-400.css";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { navigate } from "../hooks/useHashRoute";
import { useReveal } from "../hooks/useReveal";

const STEPS = [
  {
    title: "Build your CV",
    body: "Describe yourself in your own words. The CV Builder asks follow-ups, matches you to jobs and writes a tailored PDF. Already have a CV? Upload it instead.",
  },
  {
    title: "Practise for that job",
    body: "Get behavioural, technical and CV-specific questions, including how you'd handle what the role asks for that your CV doesn't show yet.",
  },
  { title: "Answer out loud", body: "Answer each question as you would in the room. Your answer is transcribed on your own computer." },
  { title: "Get feedback and retry", body: "See your score, what landed and what was missing, then try again and see exactly what changed." },
];

const FEATURES = [
  {
    icon: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
    title: "A CV from a conversation",
    body: "Tell the CV Builder about yourself and it writes a CV tailored to a matched job, using only facts you've confirmed.",
  },
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
    body: "Every retry is compared with the last, and each session ends with a summary of your top priorities, exportable as a PDF.",
  },
  {
    icon: "M12 3l7 3v5c0 4.5-3 8.5-7 10-4-1.5-7-5.5-7-10V6l7-3z",
    title: "Private by design",
    body: "Speech recognition and the language model run on your own computer. Your CV and answers never leave it.",
  },
];

const STEP_MS = 2600;

/** "How it works": highlights each step in turn (1 -> 4, then loops) once the section is on
 *  screen. Hovering a step holds it; reduced-motion users get the static cards. */
function Steps() {
  const ref = useRef<HTMLOListElement>(null);
  const [active, setActive] = useState(-1); // -1 until the section has been seen
  const [held, setHeld] = useState<number | null>(null);
  const [visible, setVisible] = useState(false);
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

  useEffect(() => {
    const el = ref.current;
    if (!el || reducedMotion) return;
    const io = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.4 });
    io.observe(el);
    return () => io.disconnect();
  }, [reducedMotion]);

  useEffect(() => {
    if (!visible || held !== null) return;
    setActive((a) => (a < 0 ? 0 : a));
    const id = window.setInterval(() => setActive((a) => (a + 1) % STEPS.length), STEP_MS);
    return () => window.clearInterval(id);
  }, [visible, held]);

  const current = held ?? active;
  return (
    <ol
      ref={ref}
      className={`steps ${reducedMotion ? "" : "animated"}`}
      style={{ ["--step-ms" as string]: `${STEP_MS}ms` }}
      onMouseLeave={() => setHeld(null)}
    >
      {STEPS.map((s, i) => (
        <li
          key={s.title}
          className={`reveal-item ${i === current ? "active" : i < current ? "done" : ""}`}
          style={revealOrder(i + 1)}
          onMouseEnter={() => setHeld(i)}
          aria-current={i === current ? "step" : undefined}
        >
          <span className="step-num">{i + 1}</span>
          <h3>{s.title}</h3>
          <p>{s.body}</p>
          {/* Re-keyed each time this step becomes active so the bar restarts from empty. */}
          {i === current && held === null && <span key={`bar-${active}`} className="step-bar" aria-hidden />}
        </li>
      ))}
    </ol>
  );
}

/** Order within a revealing section: items fade in one after another. */
function revealOrder(i: number) {
  return { ["--reveal-i" as string]: i };
}

/** A landing section whose `.reveal-item` children fade and rise in when it scrolls into view. */
function RevealSection({ children }: { children: ReactNode }) {
  const { ref, shown } = useReveal<HTMLElement>(0.2);
  return (
    <section ref={ref} className={`landing-section reveal-group ${shown ? "in" : ""}`}>
      {children}
    </section>
  );
}

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GetStarted({ label, to }: { label: string; to: string }) {
  return (
    <button className="cta" onClick={() => navigate(to)}>
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
        <div className="hero-choices">
          <div className="choice">
            <h3>Need a CV?</h3>
            <p className="muted small">Talk it through and get a tailored PDF for a matched job.</p>
            <GetStarted label="Build a CV" to="/build" />
          </div>
          <div className="choice">
            <h3>Have one already?</h3>
            <p className="muted small">Walk into your next interview with a CV made for the job, having already answered the questions.</p>
            <GetStarted label="Start practising" to="/start" />
          </div>
        </div>
        <Preview />
      </section>

      <RevealSection>
        <h2 className="section-title reveal-item">How it works</h2>
        <Steps />
      </RevealSection>

      <RevealSection>
        <h2 className="section-title reveal-item">Practice that feels like the real thing</h2>
        <div className="features">
          {FEATURES.map((f, i) => (
            <div key={f.title} className="feature reveal-item" style={revealOrder(i + 1)}>
              <span className="feature-icon">
                <Icon d={f.icon} />
              </span>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
            </div>
          ))}
        </div>
      </RevealSection>

    </div>
  );
}
