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

export interface CvBuilderStatus {
  ok: boolean;
  backend: "local" | "groq";
  model: string;
  error: string | null;
  fix: string | null;
}

export interface Health {
  ok: boolean;
  ollama: OllamaStatus;
  cv_builder: CvBuilderStatus;
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
  scores: number[];
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
  ended_at: string | null;
  summary: SessionSummary | null;
  cv_build_id: string | null;
  cv_builder_context: CvBuilderContext | null;
}

/** Set on sessions started from a CV Builder build. */
export interface CvBuilderContext {
  job_title: string;
  matched_skills: string[];
  missing_requirements: string[];
  summary: string;
}

export interface SessionStats {
  questions_total: number;
  questions_answered: number;
  attempts_scored: number;
  avg_best_score: number | null;
  retried: { question_id: number; first: number; best: number }[];
  delivery: {
    avg_wpm: number | null;
    fillers_per_min: number | null;
    avg_fillers: number | null;
    avg_long_pauses: number | null;
  };
}

export interface SessionSummary {
  recurring_strengths: string[];
  recurring_weaknesses: string[];
  top_priorities: { title: string; why: string; how_to_practise: string }[];
  overall: string;
  stats: SessionStats;
  generated_at: string;
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
  scoring: Scoring | null;
  feedback: Feedback | null;
  timings: Record<string, number | string>;
  error: string | null;
  created_at: string;
}

export interface RubricCoverage {
  point: string;
  evidence_quote: string;
  covered: boolean;
  quote_verified: boolean;
  unverified_claim?: boolean;
}

export interface Scoring {
  rubric_coverage: RubricCoverage[];
  score: number;
  model_score?: number;
}

export interface QuotedPoint {
  point: string;
  quote: string;
  quote_verified?: boolean;
}

export interface StarPart {
  quote: string;
  comment: string;
  quote_verified?: boolean;
}

export interface StarAssessment {
  situation: StarPart;
  task: StarPart;
  action: StarPart;
  result: StarPart;
  overall: string;
}

export interface AttemptComparison {
  addressed: string[];
  not_addressed: string[];
  summary: string;
  previous_attempt_number?: number;
  previous_score?: number | null;
}

export interface Feedback {
  what_you_did_well: QuotedPoint[];
  what_could_be_improved: string[];
  missed_opportunities: string[];
  structure_feedback: StarAssessment | null;
  previous_attempt_comparison: AttemptComparison | null;
  example_stronger_answer: string;
  example_answer_sentences_removed?: number;
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
  | { type: "score"; scoring: Scoring }
  | { type: "feedback_field"; field: keyof Feedback; value: unknown }
  | { type: "done"; attempt: Attempt };

/** Subscribe to an attempt's progress (server-sent events). Returns a function that closes the stream. */
export function watchAttempt(
  attemptId: number,
  onEvent: (e: AttemptEvent) => void,
  onConnectionLost: () => void,
): () => void {
  const source = new EventSource(`/api/attempts/${attemptId}/events`);
  let finished = false;
  for (const type of ["status", "transcript", "metrics", "score", "feedback_field", "done"]) {
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

// --- CV Builder ---

export type CvBuildStage = "followup" | "confirm" | "jobs" | "requirements" | "cv";

export interface DraftExperience {
  role: string | null;
  organisation: string | null;
  description: string | null;
  start_date: string | null;
  end_date: string | null;
}

export interface DraftProject {
  title: string;
  description: string | null;
  technologies: string[];
  start_date: string | null;
  end_date: string | null;
  dates_declined: boolean;
  outcome_declined: boolean;
}

/** The CV Builder's DraftProfile (only the fields the UI reads or edits). */
export interface Draft {
  name: string | null;
  email: string | null;
  phone: string | null;
  github: string | null;
  linkedin: string | null;
  degree: string | null;
  institution: string | null;
  year: string | null;
  technical_skills: string[];
  target_roles: string[];
  summary: string | null;
  achievements: string[];
  experience: DraftExperience[];
  projects: DraftProject[];
}

export interface JobMatch {
  document_id: string;
  title: string;
  location: string | null;
  score: number | null;
  excerpt: string | null;
}

export interface GeneratedCv {
  summary: string;
  education: string;
  additional_education?: { text: string }[];
  skills: string[];
  experience: { role: string; organisation: string; description: string }[];
  projects: { title: string; description: string; technologies?: string[] }[];
  matched_skills: string[];
  missing_requirements: string[];
  grounding_warnings: string[];
  target_job_title: string;
}

export interface CvBuildSummary {
  id: string;
  created_at: string;
  updated_at: string;
  stage: CvBuildStage;
  name: string | null;
  job_title: string | null;
  has_cv: boolean;
  job_description: string | null;
}

export interface CvBuild extends CvBuildSummary {
  phase: "intake" | "review";
  pending_question: string | null;
  review_checked: boolean;
  ended_at_step_limit: boolean;
  conversation: { role: "user" | "agent"; text: string; phase: "intake" | "review" }[];
  confirm_summary: string | null;
  draft: Draft;
  job_matches: JobMatch[];
  selected_job: JobMatch | null;
  requirement_question: string | null;
  requirement_gaps: { requirement: string; kind: string; reason: string }[] | null;
  last_resolution: { confirmed_skills: string[]; confirmed_notes: string[]; declined: string[] } | null;
  cv: GeneratedCv | null;
}

export type ProfileEdit = Omit<Draft, "experience" | "projects"> & {
  experience: DraftExperience[];
  projects: DraftProject[];
  confirm: boolean;
};

export interface CvEdit {
  summary?: string;
  education?: string;
  skills?: string[];
  additional_education?: string[];
  experience?: string[];
  projects?: string[];
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
    throw new ApiError(0, "Can't reach the RehearseAI backend. Is it running?");
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

  endSession: (id: string) => request<Session>(`/api/sessions/${id}/end`, { method: "POST" }),

  getQuestion: (questionId: number) => request<QuestionDetail>(`/api/questions/${questionId}`),

  listBuilds: () => request<CvBuildSummary[]>("/api/cv-builds"),
  createBuild: (intro: string) => request<CvBuild>("/api/cv-builds", json("POST", { intro })),
  getBuild: (id: string) => request<CvBuild>(`/api/cv-builds/${id}`),
  replyBuild: (id: string, text: string) => request<CvBuild>(`/api/cv-builds/${id}/reply`, json("POST", { text })),
  startReview: (id: string) => request<CvBuild>(`/api/cv-builds/${id}/review/start`, { method: "POST" }),
  saveProfile: (id: string, edit: ProfileEdit) => request<CvBuild>(`/api/cv-builds/${id}/profile`, json("PUT", edit)),
  reopenProfile: (id: string) => request<CvBuild>(`/api/cv-builds/${id}/profile/reopen`, { method: "POST" }),
  selectJob: (id: string, jobId: string) => request<CvBuild>(`/api/cv-builds/${id}/job`, json("POST", { job_id: jobId })),
  answerRequirements: (id: string, text: string | null) =>
    request<CvBuild>(`/api/cv-builds/${id}/requirements`, json("POST", text === null ? { skip: true } : { text })),
  generateCv: (id: string) => request<CvBuild>(`/api/cv-builds/${id}/cv`, { method: "POST" }),
  updateCv: (id: string, edit: CvEdit) => request<CvBuild>(`/api/cv-builds/${id}/cv`, json("PATCH", edit)),
  cvPdfUrl: (id: string, download = false) => `/api/cv-builds/${id}/cv.pdf${download ? "?download=1" : ""}`,
  startPractice: (id: string, jobDescription?: string) =>
    request<Session>(`/api/cv-builds/${id}/practice`, json("POST", { job_description: jobDescription ?? null })),

  submitAttempt: (questionId: number, audio: Blob, durationS: number) => {
    const form = new FormData();
    const ext = audio.type.includes("mp4") ? "m4a" : audio.type.includes("ogg") ? "ogg" : "webm";
    form.append("audio", audio, `answer.${ext}`);
    form.append("duration_s", durationS.toFixed(2));
    return request<Attempt>(`/api/questions/${questionId}/attempts`, { method: "POST", body: form });
  },
};
