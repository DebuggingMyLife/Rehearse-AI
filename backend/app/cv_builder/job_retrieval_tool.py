import contextlib
import io
import json
import re
from pathlib import Path
from typing import List

import numpy as np

# sentence-transformers pulls in `transformers`, which prints unconditional
# "[ERROR] ... not documented" lines at import time for undocumented kwargs
# on unrelated model classes (an upstream transformers issue, unrelated to
# the model actually used here). Suppress that import-time noise only.
with contextlib.redirect_stdout(io.StringIO()):
    from sentence_transformers import SentenceTransformer

from profile_model import Profile

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
JOBS_PATH = Path(__file__).resolve().parent / "data" / "jobs.jsonl"


def _split_sentences(text: str) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _cosine_sim(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
    return matrix_norm @ query_norm


class JobRetrievalTool:
    """Semantic job matching over data/jobs.jsonl.

    Embeddings come from a local sentence-transformers model (no external
    API) so every job description and profile query is encoded into the
    same dense vector space; ranking is cosine similarity between the
    profile's query embedding and each job's embedding. Each job's
    description is also split into sentences and embedded separately, so
    the sentence closest to the profile's query vector can be surfaced as
    a supporting excerpt instead of a generic label.
    """

    def __init__(self, jobs_path: Path = JOBS_PATH, model_name: str = DEFAULT_MODEL_NAME):
        self.model = SentenceTransformer(model_name)
        self.jobs = self._load_jobs(jobs_path)

        job_texts = [f"{j['title']}. {j['description']}" for j in self.jobs]
        self.job_embeddings = self.model.encode(job_texts)

        self._job_sentences = [_split_sentences(j["description"]) for j in self.jobs]
        self._job_sentence_embeddings = [
            self.model.encode(sentences) if sentences else np.zeros((0, self.job_embeddings.shape[1]))
            for sentences in self._job_sentences
        ]

    @staticmethod
    def _load_jobs(path: Path) -> List[dict]:
        jobs = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    jobs.append(json.loads(line))
        return jobs

    def get_job_by_id(self, document_id: str) -> dict:
        for job in self.jobs:
            if job["document_id"] == document_id:
                return job
        raise KeyError(f"No job with document_id={document_id!r}")

    @staticmethod
    def _build_query_text(profile: Profile) -> str:
        parts = []
        if profile.job_goal.target_roles:
            parts.append("Target roles: " + ", ".join(profile.job_goal.target_roles) + ".")
        if profile.job_goal.summary:
            parts.append(profile.job_goal.summary)
        if profile.skills.technical_skills:
            parts.append("Skills: " + ", ".join(profile.skills.technical_skills) + ".")
        for p in profile.projects.entries:
            parts.append(f"Project - {p.title}: {p.description}")
        for e in profile.experience.entries:
            parts.append(f"Experience - {e.role} at {e.organisation}: {e.description}")
        return " ".join(parts)

    def _best_excerpt(self, job_index: int, query_vec: np.ndarray) -> str:
        sentences = self._job_sentences[job_index]
        embeddings = self._job_sentence_embeddings[job_index]
        if len(sentences) == 0:
            return self.jobs[job_index]["description"][:200]
        sims = _cosine_sim(query_vec, embeddings)
        best_idx = int(np.argmax(sims))
        return sentences[best_idx]

    def search(self, profile: Profile, top_k: int = 3) -> List[dict]:
        query_text = self._build_query_text(profile)
        query_vec = self.model.encode(query_text)
        sims = _cosine_sim(query_vec, self.job_embeddings)
        ranked_indices = np.argsort(-sims)[:top_k]

        results = []
        for idx in ranked_indices:
            idx = int(idx)
            job = self.jobs[idx]
            results.append(
                {
                    "document_id": job["document_id"],
                    "title": job["title"],
                    "score": round(float(sims[idx]), 4),
                    "excerpt": self._best_excerpt(idx, query_vec),
                }
            )
        return results
