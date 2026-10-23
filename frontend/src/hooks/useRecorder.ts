import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderState = "idle" | "requesting" | "recording" | "recorded";

export interface Recording {
  blob: Blob;
  url: string;
  durationS: number;
  mimeType: string;
}

// Preference order. Chrome/Edge/Firefox support webm or ogg Opus; Safari only mp4.
const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];

/** Why recording can't work in this browser at all, or null if it can. */
export function recordingUnsupportedReason(): string | null {
  if (!window.isSecureContext) {
    return "Microphone access needs a secure page. Open Retake at http://localhost:5173 (not a network IP address).";
  }
  if (!navigator.mediaDevices?.getUserMedia || typeof window.MediaRecorder === "undefined") {
    return "This browser can't record audio. Use a recent version of Chrome, Edge, Firefox or Safari.";
  }
  return null;
}

function pickMimeType(): string | undefined {
  return MIME_CANDIDATES.find((m) => MediaRecorder.isTypeSupported(m));
}

function micErrorMessage(err: unknown): string {
  const name = (err as DOMException)?.name;
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Microphone access was blocked. Click the microphone or lock icon in the address bar, allow the microphone for this site, then try again.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "No microphone was found. Plug one in or check your system sound settings, then try again.";
    case "NotReadableError":
    case "AbortError":
      return "The microphone is in use by another app or couldn't be started. Close other apps using it and try again.";
    default:
      return `Couldn't start the microphone (${name || "unknown error"}).`;
  }
}

export function useRecorder({ maxSeconds }: { maxSeconds: number | null }) {
  const [state, setState] = useState<RecorderState>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [level, setLevel] = useState(0);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const tickRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);

  const releaseMic = useCallback(() => {
    if (tickRef.current !== null) window.clearInterval(tickRef.current);
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    tickRef.current = rafRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close().catch(() => {});
    audioCtxRef.current = null;
    setLevel(0);
  }, []);

  const stop = useCallback(() => {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
  }, []);

  const start = useCallback(async () => {
    const unsupported = recordingUnsupportedReason();
    if (unsupported) {
      setError(unsupported);
      return;
    }
    setError(null);
    setState("requesting");
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      });
    } catch (err) {
      setError(micErrorMessage(err));
      setState(recording ? "recorded" : "idle");
      return;
    }
    streamRef.current = stream;

    // Input level meter, so the user can see the mic is picking them up.
    try {
      const ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(analyser);
      audioCtxRef.current = ctx;
      const buf = new Uint8Array(analyser.fftSize);
      const draw = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (const v of buf) sum += ((v - 128) / 128) ** 2;
        setLevel(Math.min(1, Math.sqrt(sum / buf.length) * 4));
        rafRef.current = requestAnimationFrame(draw);
      };
      draw();
    } catch {
      /* meter is optional */
    }

    const mimeType = pickMimeType();
    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    chunksRef.current = [];
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    rec.onstop = () => {
      const durationS = (performance.now() - startedAtRef.current) / 1000;
      releaseMic();
      const type = rec.mimeType || mimeType || "audio/webm";
      const blob = new Blob(chunksRef.current, { type });
      setRecording((prev) => {
        if (prev) URL.revokeObjectURL(prev.url);
        return { blob, url: URL.createObjectURL(blob), durationS, mimeType: type };
      });
      setState("recorded");
    };
    recorderRef.current = rec;
    rec.start(1000); // timeslice: don't lose everything if the tab crashes mid-answer
    startedAtRef.current = performance.now();
    setElapsed(0);
    setState("recording");
    tickRef.current = window.setInterval(() => {
      setElapsed((performance.now() - startedAtRef.current) / 1000);
    }, 200);
  }, [recording, releaseMic]);

  // Auto-stop at the time limit.
  useEffect(() => {
    if (state === "recording" && maxSeconds !== null && elapsed >= maxSeconds) stop();
  }, [state, elapsed, maxSeconds, stop]);

  const discard = useCallback(() => {
    setRecording((prev) => {
      if (prev) URL.revokeObjectURL(prev.url);
      return null;
    });
    setElapsed(0);
    setState("idle");
  }, []);

  // Release the mic if the user navigates away mid-recording.
  useEffect(
    () => () => {
      const rec = recorderRef.current;
      if (rec && rec.state !== "inactive") {
        rec.onstop = null;
        rec.stop();
      }
      releaseMic();
    },
    [releaseMic],
  );

  return { state, elapsed, level, recording, error, start, stop, discard };
}
