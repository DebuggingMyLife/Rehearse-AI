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
  return (
    <div className={`banner ${ollama.ok ? "ok" : "error"}`}>
      {ollama.ok ? (
        <span>
          LLM <code>{ollama.model}</code> ready at {ollama.host} · Whisper{" "}
          <code>{whisper.model_size}</code> on {whisper.device} ({whisper.backend})
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
  );
}
