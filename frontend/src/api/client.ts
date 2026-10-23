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
};
