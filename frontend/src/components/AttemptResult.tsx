import type { Attempt, AttemptMetrics, AttemptStatus } from "../api/client";

export interface LiveAttempt {
  status: AttemptStatus;
  transcript: string | null;
  metrics: AttemptMetrics | null;
  final: Attempt | null;
  connectionLost: boolean;
}

// Typical conversational interview pace. Outside this range is worth a gentle note.
const WPM_LOW = 110;
const WPM_HIGH = 170;

const STEPS: { status: AttemptStatus; label: string }[] = [
  { status: "uploaded", label: "Uploaded" },
  { status: "transcribing", label: "Transcribing" },
  { status: "analysing", label: "Analysing" },
];
const ORDER: AttemptStatus[] = ["uploaded", "transcribing", "analysing", "complete"];

function Progress({ status }: { status: AttemptStatus }) {
  const current = ORDER.indexOf(status);
  return (
    <ol className="progress" aria-label="Progress">
      {STEPS.map((step, i) => {
        const state = current > i ? "done" : current === i ? "active" : "todo";
        return (
          <li key={step.status} className={state}>
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

function Timings({ timings }: { timings: Attempt["timings"] }) {
  const rows = ["upload_ms", "queue_ms", "transcription_ms", "metrics_ms", "llm_score_ms", "llm_feedback_ms", "total_ms"]
    .filter((k) => typeof timings[k] === "number")
    .map((k) => [k.replace(/_ms$/, "").replace("_", " "), `${((timings[k] as number) / 1000).toFixed(2)} s`]);
  return (
    <details className="timings">
      <summary className="muted small">Processing time</summary>
      <table>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td>{v}</td>
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
  const status = final?.status ?? live.status;

  if (final?.status === "too_short" || final?.status === "failed") {
    return <div className={`banner ${final.status === "failed" ? "error" : "warn"}`}>{final.error}</div>;
  }

  return (
    <div className="stack">
      {!final && <Progress status={status} />}
      {live.connectionLost && !final && (
        <div className="banner warn">Lost connection to the server. Refresh to see the result.</div>
      )}
      {live.metrics && <Metrics metrics={live.metrics} />}
      {live.transcript !== null && (
        <div className="transcript">
          <div className="label">Transcript</div>
          <p>{live.transcript}</p>
        </div>
      )}
      {audioUrl && <audio controls preload="metadata" src={audioUrl} />}
      {final && <Timings timings={final.timings} />}
    </div>
  );
}
