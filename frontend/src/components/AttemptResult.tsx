import type { Attempt, AttemptMetrics, AttemptStatus, Feedback, Scoring } from "../api/client";
import { FeedbackSections, RubricCoverageList, ScoreBadge } from "./FeedbackView";

export interface LiveAttempt {
  status: AttemptStatus;
  transcript: string | null;
  metrics: AttemptMetrics | null;
  scoring: Scoring | null;
  feedback: Partial<Feedback>;
  final: Attempt | null;
  connectionLost: boolean;
}

export function liveFromAttempt(a: Attempt, metrics: AttemptMetrics | null): LiveAttempt {
  return {
    status: a.status,
    transcript: a.transcript,
    metrics,
    scoring: a.scoring,
    feedback: a.feedback ?? {},
    final: a,
    connectionLost: false,
  };
}

// Typical conversational interview pace. Outside this range is worth a gentle note.
const WPM_LOW = 110;
const WPM_HIGH = 170;

type Step = { key: string; label: string };
const STEPS: Step[] = [
  { key: "upload", label: "Uploaded" },
  { key: "transcribe", label: "Transcribing" },
  { key: "score", label: "Scoring" },
  { key: "feedback", label: "Writing feedback" },
];

function currentStep(live: LiveAttempt): number {
  if (live.status === "uploaded") return 0;
  if (live.status === "transcribing") return 1;
  if (!live.scoring) return 2;
  return 3;
}

function Progress({ live }: { live: LiveAttempt }) {
  const current = currentStep(live);
  return (
    <ol className="progress" aria-label="Progress" aria-live="polite">
      {STEPS.map((step, i) => {
        const state = current > i ? "done" : current === i ? "active" : "todo";
        return (
          <li key={step.key} className={state}>
            {state === "done" ? "✓ " : ""}
            {step.label}
            {state === "active" && i > 0 ? "…" : ""}
          </li>
        );
      })}
    </ol>
  );
}

function paceNote(wpm: number): string {
  if (wpm < WPM_LOW) return "A little slow; aim for 120 to 160.";
  if (wpm > WPM_HIGH) return "Quite fast; slow down so key points land.";
  return "Comfortable pace.";
}

export function Metrics({ metrics }: { metrics: AttemptMetrics }) {
  const fillers = Object.entries(metrics.filler_breakdown);
  return (
    <div className="metrics">
      <div className="metric">
        <div className="metric-value">{Math.round(metrics.wpm)}</div>
        <div className="metric-label">words per minute</div>
        <div className="metric-note">{paceNote(metrics.wpm)}</div>
      </div>
      <div className="metric">
        <div className="metric-value">{metrics.filler_count}</div>
        <div className="metric-label">filler words</div>
        <div className="metric-note">
          {fillers.length ? fillers.map(([w, n]) => `"${w}" ×${n}`).join(", ") : "None detected."}
        </div>
      </div>
      <div className="metric">
        <div className="metric-value">{metrics.long_pause_count}</div>
        <div className="metric-label">pauses over 2 s</div>
        <div className="metric-note">
          {metrics.long_pause_count
            ? `Longest ${metrics.longest_pause_s.toFixed(1)} s`
            : `Longest gap ${metrics.longest_pause_s.toFixed(1)} s`}
        </div>
      </div>
    </div>
  );
}

const TIMING_ROWS: [string, string][] = [
  ["upload_ms", "Upload"],
  ["queue_ms", "Queue"],
  ["transcription_ms", "Transcription"],
  ["metrics_ms", "Metrics"],
  ["llm_score_ms", "LLM call 1 (score)"],
  ["llm_feedback_ms", "LLM call 2 (feedback)"],
  ["score_ready_ms", "Submit → score"],
  ["first_feedback_ms", "Submit → first feedback"],
  ["total_ms", "Submit → done"],
];

function Timings({ timings }: { timings: Attempt["timings"] }) {
  return (
    <details className="timings">
      <summary className="muted small">Processing time</summary>
      <table>
        <tbody>
          {TIMING_ROWS.filter(([k]) => typeof timings[k] === "number").map(([k, label]) => (
            <tr key={k}>
              <td>{label}</td>
              <td>{((timings[k] as number) / 1000).toFixed(2)} s</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">
        Whisper {String(timings.whisper_model ?? "?")} on {String(timings.whisper_device ?? "?")} · LLM{" "}
        {String(timings.llm_model ?? "?")}
      </p>
    </details>
  );
}

export default function AttemptResult({ live, audioUrl }: { live: LiveAttempt; audioUrl: string | null }) {
  const final = live.final;

  if (final?.status === "too_short" || final?.status === "failed") {
    return <div className={`banner ${final.status === "failed" ? "error" : "warn"}`}>{final.error}</div>;
  }

  const evaluating = !final && (live.status === "analysing" || live.scoring !== null);
  const hasFeedback = Object.keys(live.feedback).length > 0;

  return (
    <div className="stack">
      {!final && <Progress live={live} />}
      {live.connectionLost && !final && (
        <div className="banner warn">Lost connection to the server. Refresh to see the result.</div>
      )}
      {final?.error && <div className="banner warn">{final.error}</div>}

      {live.scoring && (
        <div className="score-row">
          <ScoreBadge score={live.scoring.score} />
          <RubricCoverageList scoring={live.scoring} />
        </div>
      )}

      {(hasFeedback || (evaluating && live.scoring)) && (
        <FeedbackSections feedback={live.feedback} streaming={!final} />
      )}

      {live.metrics && (
        <section className="fb-section">
          <h4>Delivery</h4>
          <Metrics metrics={live.metrics} />
        </section>
      )}
      {live.transcript !== null && (
        <section className="fb-section transcript">
          <h4>Transcript</h4>
          <p>{live.transcript}</p>
          {audioUrl && <audio controls preload="metadata" src={audioUrl} />}
        </section>
      )}
      {final && <Timings timings={final.timings} />}
    </div>
  );
}
