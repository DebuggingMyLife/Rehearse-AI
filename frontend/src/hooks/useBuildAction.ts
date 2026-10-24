import { useState } from "react";
import type { CvBuild } from "../api/client";
import { useElapsed } from "./useElapsed";

/** Runs one CV Builder step at a time. gpt-oss calls are slow, so the step's label and the
 *  elapsed seconds are shown while it runs; a failed step leaves the build as it was. */
export function useBuildAction(onDone: (build: CvBuild) => void) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const elapsed = useElapsed(busy !== null);

  async function run(label: string, fn: () => Promise<CvBuild>): Promise<boolean> {
    setBusy(label);
    setError(null);
    try {
      onDone(await fn());
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    } finally {
      setBusy(null);
    }
  }

  return { busy, error, elapsed, run, setError };
}
