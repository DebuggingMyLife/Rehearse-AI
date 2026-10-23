import { useEffect, useState } from "react";

/** Seconds elapsed while `running` is true; resets when it becomes true again. */
export function useElapsed(running: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) return;
    setSeconds(0);
    const start = Date.now();
    const id = window.setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 250);
    return () => window.clearInterval(id);
  }, [running]);
  return seconds;
}
