import { useCallback, useEffect, useState } from "react";
import { api, type Health } from "../api/client";

type State = "ok" | "loading" | "error";

function Indicator({ state, label, detail }: { state: State; label: string; detail: string }) {
  const text = state === "ok" ? "ready" : state === "loading" ? "loading" : "unavailable";
  return (
    <span className={`status ${state}`} title={detail}>
      <span className="status-dot" aria-hidden />
      {label} {text}
    </span>
  );
}

/** Compact LLM / Whisper status for the header, plus error banners (with fix commands) when needed. */
export function useHealth() {
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

  return { health, backendDown, refresh };
}

export function StatusIndicators({ health, backendDown }: { health: Health | null; backendDown: boolean }) {
  if (backendDown) return <Indicator state="error" label="Backend" detail="The backend isn't running." />;
  if (!health) return null;
  const { ollama, whisper } = health;
  const whisperState: State = whisper.loaded ? "ok" : whisper.loading ? "loading" : "error";
  return (
    <div className="statuses">
      <Indicator state={ollama.ok ? "ok" : "error"} label="LLM" detail={`${ollama.model} at ${ollama.host}`} />
      <Indicator
        state={whisperState}
        label="Whisper AI"
        detail={
          whisper.loaded
            ? `${whisper.model_size} on ${whisper.device}/${whisper.compute_type} (${whisper.backend})`
            : `${whisper.model_size} (${whisper.backend})`
        }
      />
    </div>
  );
}

export function StatusProblems({
  health,
  backendDown,
  refresh,
}: {
  health: Health | null;
  backendDown: boolean;
  refresh: () => void;
}) {
  if (backendDown) {
    return (
      <div className="banner error">
        <strong>Backend not reachable.</strong> Start it with the start script, then{" "}
        <button onClick={refresh}>retry</button>.
      </div>
    );
  }
  if (!health) return null;
  const { ollama, whisper } = health;
  return (
    <>
      {!ollama.ok && (
        <div className="banner error">
          <strong>{ollama.error}</strong>
          {ollama.fix && (
            <>
              {" "}
              Fix: <code>{ollama.fix}</code>
            </>
          )}{" "}
          <button onClick={refresh}>Re-check</button>
        </div>
      )}
      {whisper.error && <div className="banner error">{whisper.error}</div>}
      {whisper.warnings?.map((w) => (
        <div key={w} className="banner warn">
          {w}
        </div>
      ))}
    </>
  );
}
