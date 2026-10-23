import { useCallback, useEffect, useState } from "react";
import { api, type Health } from "../api/client";

export default function HealthBanner() {
  const [health, setHealth] = useState<Health | null>(null);
  const [backendDown, setBackendDown] = useState(false);

  const refresh = useCallback(() => {
    api
      .health()
      .then((h) => {
        setHealth(h);
        setBackendDown(false);
      })
      .catch(() => setBackendDown(true));
  }, []);

  useEffect(refresh, [refresh]);

  // Whisper loads in the background after startup; re-check until it's ready.
  const whisperLoading = health?.whisper.loading ?? false;
  useEffect(() => {
    if (!whisperLoading) return;
    const id = window.setTimeout(refresh, 3000);
    return () => window.clearTimeout(id);
  }, [whisperLoading, health, refresh]);

  if (backendDown) {
    return (
      <div className="banner error">
        <strong>Backend not reachable.</strong> Start it with the start script, then{" "}
        <button onClick={refresh}>retry</button>.
      </div>
    );
  }
  if (!health) return <div className="banner">Checking local services…</div>;

  const { ollama, whisper } = health;
  const whisperProblem = whisper.error ?? null;
  return (
    <>
      <div className={`banner ${ollama.ok ? "ok" : "error"}`}>
      {ollama.ok ? (
        <span>
          LLM <code>{ollama.model}</code> ready at {ollama.host} · Whisper <code>{whisper.model_size}</code>{" "}
          {whisper.loaded
            ? `on ${whisper.device}/${whisper.compute_type} (${whisper.backend})`
            : whisper.loading
              ? "loading…"
              : whisperProblem
                ? "unavailable"
                : "not loaded"}
          {whisper.loading && (
            <>
              {" "}
              <button onClick={refresh}>Re-check</button>
            </>
          )}
        </span>
      ) : (
        <span>
          <strong>{ollama.error}</strong>
          {ollama.fix && (
            <>
              {" "}
              Fix: <code>{ollama.fix}</code>
            </>
          )}{" "}
          <button onClick={refresh}>Re-check</button>
        </span>
      )}
      </div>
      {whisperProblem && <div className="banner error">{whisperProblem}</div>}
      {whisper.warnings?.map((w) => (
        <div key={w} className="banner warn">
          {w}
        </div>
      ))}
    </>
  );
}
