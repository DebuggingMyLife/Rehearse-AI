"""Pydantic models for LLM outputs. Their JSON schemas are sent to Ollama as `format`
and every response is validated against them."""

from typing import Literal

from pydantic import BaseModel, Field

QuestionTypeLit = Literal["behavioural", "technical", "cv_specific"]
DifficultyLit = Literal["easy", "medium", "hard"]


class GeneratedQuestion(BaseModel):
    question: str = Field(min_length=10)
    type: QuestionTypeLit
    difficulty: DifficultyLit
    # Stored as Question.rubric. The descriptive field name matters: with "rubric", qwen2.5:7b
    # writes generic structure ("Describes the situation"); with this name it lists actual
    # content ("Used EXPLAIN to analyse query plans"). A/B tested 2026-10-23.
    points_a_strong_answer_would_mention: list[str] = Field(min_length=3, max_length=6)
    cv_evidence: list[str] = Field(max_length=4)


class QuestionBatch(BaseModel):
    questions: list[GeneratedQuestion] = Field(min_length=1)
