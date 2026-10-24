/** Progress line for a running CV Builder step. */
export default function Working({ label, elapsed }: { label: string; elapsed: number }) {
  return (
    <div className="working" role="status">
      <span className="spinner" aria-hidden />
      <span>
        {label} <span className="muted">{elapsed}s</span>
      </span>
      {elapsed >= 8 && (
        <span className="muted small working-note">
          The CV Builder uses gpt-oss:20b, a reasoning model: a step usually takes 10 to 60 seconds, and longer
          while the model loads.
        </span>
      )}
    </div>
  );
}
