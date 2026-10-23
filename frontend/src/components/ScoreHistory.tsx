import type { Attempt } from "../api/client";

export function scoreDelta(current: number, previous: number | null | undefined) {
  if (previous === null || previous === undefined) return null;
  const d = current - previous;
  return (
    <span className={`delta ${d > 0 ? "up" : d < 0 ? "down" : "same"}`}>
      {d > 0 ? `+${d}` : d < 0 ? `${d}` : "±0"}
    </span>
  );
}

/** Scores across all scored attempts at one question, oldest first, with the change each time. */
export default function ScoreHistory({ attempts }: { attempts: Attempt[] }) {
  const scored = attempts.filter((a) => a.score !== null);
  if (scored.length < 2) return null;
  const first = scored[0].score!;
  const last = scored[scored.length - 1].score!;
  return (
    <div className="score-history" aria-label="Score history">
      <span className="muted small">Score history</span>
      <ol>
        {scored.map((a, i) => (
          <li key={a.id}>
            {i > 0 && <span className="arrow">→</span>}
            <span className={`chip score-${a.score}`} title={`Attempt ${a.attempt_number}`}>
              {a.score}
            </span>
          </li>
        ))}
      </ol>
      <span className="small">
        {last > first ? `Up ${last - first} since your first attempt` : last < first ? `Down ${first - last} since your first attempt` : "No change since your first attempt"}
      </span>
    </div>
  );
}
