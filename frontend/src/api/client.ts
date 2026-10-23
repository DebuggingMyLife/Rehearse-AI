export interface OllamaStatus {
  ok: boolean;
  host: string;
  model: string;
  reachable: boolean;
  model_available: boolean;
  available_models: string[];
  error: string | null;
  fix: string | null;
}

export interface Health {
  ok: boolean;
  ollama: OllamaStatus;
  whisper: {
    backend: string;
    model_size: string;
    device: string;
    compute_type: string;
    loaded: boolean;
    loading: boolean;
    error: string | null;
    warnings?: string[];
  };
  config: { llm_num_ctx: number; audio_retention_days: number };
}

export type QuestionType = "behavioural" | "technical" | "cv_specific";
export type Difficulty = "easy" | "medium" | "hard";

export interface Question {
  id: number;
  position: number;
  batch: number;
  text: string;
  type: QuestionType;
  difficulty: Difficulty;
  status: "not_attempted" | "attempted";
  attempt_count: number;
  best_score: number | null;
  rubric: string[] | null;
  cv_evidence: string[] | null;
}

export interface Session {
  id: string;
  created_at: string;
  status: "active" | "ended";
  cv_filename: string;
  cv_text: string;
  job_description: string;
  questions: Question[];
}

export type AttemptStatus = "uploaded" | "transcribing" | "analysing" | "complete" | "too_short" | "failed";

export interface Attempt {
  id: number;
  question_id: number;
  attempt_number: number;
  status: AttemptStatus;
  audio_url: string | null;
  audio_duration_s: number | null;
  transcript: string | null;
  wpm: number | null;
  filler_count: number | null;
  filler_breakdown: Record<string, number> | null;
  long_pause_count: number | null;
  delivery: Delivery | null;
  score: number | null;
  scoring: Record<string, unknown> | null;
  feedback: Record<string, unknown> | null;
  timings: Record<string, number | string>;
  error: string | null;
  created_at: string;
}

export interface Delivery {
  word_count: number;
  speaking_time_s: number;
  longest_pause_s: number;
  pauses: { at: number; duration: number }[];
}

export interface AttemptMetrics extends Delivery {
  wpm: number;
  filler_count: number;
  filler_breakdown: Record<string, number>;
  long_pause_count: number;
}

export type AttemptEvent =
  | { type: "status"; status: AttemptStatus }
  | { type: "transcript"; transcript: string }
  | { type: "metrics"; metrics: AttemptMetrics }
  | { type: "done"; attempt: Attempt };

/** Subscribe to an attempt's progress (server-sent events). Returns a function that closes the stream. */
export function watchAttempt(
  attemptId: number,
  onEvent: (e: AttemptEvent) => void,
  onConnectionLost: () => void,
): () => void {
  const source = new EventSource(`/api/attempts/${attemptId}/events`);
  let finished = false;
  for (const type of ["status", "transcript", "metrics", "done"]) {
    source.addEventListener(type, (msg) => {
      const event = JSON.parse((msg as MessageEvent).data) as AttemptEvent;
      if (event.type === "done") {
        finished = true;
        source.close();
      }
      onEvent(event);
    });
  }
  source.onerror = () => {
    // EventSource auto-reconnects; the server re-sends a snapshot. Only report if it gives up.
    if (!finished && source.readyState === EventSource.CLOSED) onConnectionLost();
  };
  return () => source.close();
}

export interface QuestionDetail extends Question {
  session_id: string;
  attempts: Attempt[];
}

export interface GenerateRequest {
  count: number;
  type?: QuestionType | null;
  difficulty?: Difficulty | null;
}

export interface GenerateResponse {
  questions: Question[];
  requested: number;
  duplicates_removed: number;
  duration_ms: number;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Can't reach the Retake backend. Is it running?");
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<Health>("/api/health"),

  createSession: (cv: File, jobDescription: string) => {
    const form = new FormData();
    form.append("cv", cv);
    form.append("job_description", jobDescription);
    return request<Session>("/api/sessions", { method: "POST", body: form });
  },

  getSession: (id: string) => request<Session>(`/api/sessions/${id}`),

  updateSession: (id: string, patch: { cv_text?: string; job_description?: string }) =>
    request<Session>(`/api/sessions/${id}`, json("PATCH", patch)),

  generateQuestions: (id: string, req: GenerateRequest) =>
    request<GenerateResponse>(`/api/sessions/${id}/questions`, json("POST", req)),

  getQuestion: (questionId: number) => request<QuestionDetail>(`/api/questions/${questionId}`),

  submitAttempt: (questionId: number, audio: Blob, durationS: number) => {
    const form = new FormData();
    const ext = audio.type.includes("mp4") ? "m4a" : audio.type.includes("ogg") ? "ogg" : "webm";
    form.append("audio", audio, `answer.${ext}`);
    form.append("duration_s", durationS.toFixed(2));
    return request<Attempt>(`/api/questions/${questionId}/attempts`, { method: "POST", body: form });
  },
};
