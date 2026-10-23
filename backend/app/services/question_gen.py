"""Question generation with type/difficulty planning and duplicate avoidance."""

import logging
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import prompts
from ..models import Difficulty, InterviewSession, Question, QuestionType
from ..schemas.llm import GeneratedQuestion, QuestionBatch
from .llm import OllamaClient
from .text import content_words, norm, overlap

log = logging.getLogger(__name__)

# Keep the prompt within LLM_NUM_CTX: ~3.5 chars/token, so these cap CV + JD at roughly
# 3.4k + 1.7k tokens, leaving room for instructions, previous questions and the output.
MAX_CV_CHARS = 12_000
MAX_JD_CHARS = 6_000

TYPE_ORDER = [QuestionType.behavioural, QuestionType.technical, QuestionType.cv_specific]
# Target ratio easy:medium:hard = 1:2:1
DIFFICULTY_WEIGHTS = {Difficulty.easy: 1, Difficulty.medium: 2, Difficulty.hard: 1}
DIFFICULTY_ORDER = [Difficulty.medium, Difficulty.easy, Difficulty.hard]

DUPLICATE_RATIO = 0.8
# Share of the shorter question's content words that also appear in the other. Catches
# rewordings and "same question plus an extra sentence", which a 7B model often produces.
DUPLICATE_OVERLAP = 0.75
MIN_WORDS_FOR_OVERLAP = 4

# Spelled out next to each slot in the prompt; a 7B model follows a rule placed beside
# the item far more reliably than one in the system prompt alone.
SLOT_HINTS = {
    QuestionType.behavioural: "a 'Tell me about a time...' question on a competency this role needs",
    QuestionType.technical: "a knowledge or problem-solving question for this role that any "
                            "candidate could be asked; must NOT mention the candidate's own past work",
    QuestionType.cv_specific: "about one named project or achievement from the CV that no "
                              "earlier question covers",
}
GENERATION_TEMPERATURE = 0.3
MAX_TOP_UPS = 1


@dataclass
class Slot:
    type: QuestionType
    difficulty: Difficulty
    focus: str | None = None


BULLET_RE = re.compile(r"^\s*(?:[-*•▪◦●‣]|\d{1,2}[.)])\s+")
SOFT_SKILL_RE = re.compile(
    r"mentor|communicat|stakeholder|lead|collaborat|team|ownership|prioriti|conflict|"
    r"influenc|cross-functional|customer|present|negotiat|coach|feedback|ambigu",
    re.IGNORECASE,
)
# Behavioural fallbacks once the JD's soft-skill lines are used up (many JDs have one or two).
COMMON_COMPETENCIES = [
    "Handling a disagreement or conflict with a colleague or stakeholder",
    "Owning a mistake or failure and what changed afterwards",
    "Delivering under a tight deadline or sudden change of priorities",
    "Taking initiative on a problem nobody had asked you to fix",
    "Making progress when requirements were ambiguous or unclear",
    "Receiving difficult feedback and acting on it",
    "Influencing a decision without having authority over the people involved",
]
MIN_POINT_CHARS = 25
MAX_POINT_CHARS = 250


def extract_points(text: str) -> list[str]:
    """Bullet points from a JD or CV, joining wrapped continuation lines."""
    points: list[str] = []
    in_bullet = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            in_bullet = False
        elif BULLET_RE.match(line):
            points.append(BULLET_RE.sub("", line))
            in_bullet = True
        elif in_bullet and line[0].islower():
            points[-1] += " " + line
        else:
            in_bullet = False
    return [p[:MAX_POINT_CHARS] for p in points if len(p) >= MIN_POINT_CHARS]


# "5+ years of experience with X" as a focus makes the model ask "walk me through your
# experience with X" even for technical questions; keep just the skill.
JD_PREFIX_RE = re.compile(
    r"^(?:\d+\+?\s*years?\s*(?:of\s+)?(?:experience\s+)?(?:with\s+|in\s+)?|experience\s+(?:with\s+|in\s+|of\s+)?|"
    r"strong\s+|proven\s+|solid\s+|demonstrated\s+|excellent\s+|deep\s+|"
    r"understanding\s+of\s+|knowledge\s+of\s+|familiarity\s+with\s+)+",
    re.IGNORECASE,
)


def _clean_jd_point(point: str) -> str:
    cleaned = JD_PREFIX_RE.sub("", point).strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else point


def extract_jd_points(jd: str) -> list[str]:
    points = extract_points(jd)
    if not points:
        # No bullets: fall back to sentences.
        sentences = re.split(r"(?<=[.!?])\s+|\n+", jd)
        points = [s.strip()[:MAX_POINT_CHARS] for s in sentences if len(s.strip()) >= 30]
    return [_clean_jd_point(p) for p in points]


def extract_cv_items(cv: str) -> list[str]:
    items = extract_points(cv)
    if items:
        return items
    return [line.strip()[:MAX_POINT_CHARS] for line in cv.splitlines()
            if len(line.strip()) >= 40 and "@" not in line]


def assign_focus(slots: list[Slot], used: Counter, jd_points: list[str], cv_items: list[str]) -> None:
    """Give each slot the least-used relevant JD requirement or CV item, so questions spread
    across topics instead of clustering on whatever the JD stresses most."""
    soft = [p for p in jd_points if SOFT_SKILL_RE.search(p)]
    hard = [p for p in jd_points if not SOFT_SKILL_RE.search(p)]
    pools = {
        QuestionType.behavioural: soft + COMMON_COMPETENCIES,
        QuestionType.technical: hard or jd_points,
        QuestionType.cv_specific: cv_items,
    }
    for slot in slots:
        pool = pools[slot.type]
        if not pool:
            continue
        slot.focus = min(pool, key=lambda p: (used[p], pool.index(p)))
        used[slot.focus] += 1


def plan_slots(
    count: int,
    existing: list[tuple[QuestionType, Difficulty]],
    type_: QuestionType | None = None,
    difficulty: Difficulty | None = None,
) -> list[Slot]:
    """Pick a type and difficulty per new question, balancing against existing questions."""
    type_counts = Counter(t for t, _ in existing)
    diff_counts = Counter(d for _, d in existing)
    slots = []
    for _ in range(count):
        t = type_ or min(TYPE_ORDER, key=lambda x: (type_counts[x], TYPE_ORDER.index(x)))
        d = difficulty or min(
            DIFFICULTY_ORDER,
            key=lambda x: (diff_counts[x] / DIFFICULTY_WEIGHTS[x], DIFFICULTY_ORDER.index(x)),
        )
        type_counts[t] += 1
        diff_counts[d] += 1
        slots.append(Slot(t, d))
    return slots


EVIDENCE_MIN_OVERLAP = 0.6


def is_duplicate(candidate: str, others: list[str]) -> bool:
    c = norm(candidate)
    c_words = content_words(candidate)
    for other in others:
        if SequenceMatcher(None, c, norm(other)).ratio() >= DUPLICATE_RATIO:
            return True
        o_words = content_words(other)
        smaller = min(len(c_words), len(o_words))
        if smaller >= MIN_WORDS_FOR_OVERLAP and len(c_words & o_words) / smaller >= DUPLICATE_OVERLAP:
            return True
    return False


def grounded_in_cv(evidence: str, cv_text: str) -> bool:
    """True if most of the evidence's content words appear in the CV (guards against
    the model inventing experience or copying from the job description)."""
    return overlap(evidence, cv_text) >= EVIDENCE_MIN_OVERLAP


def _truncate(text: str, limit: int, what: str) -> str:
    if len(text) <= limit:
        return text
    log.warning("%s is %d chars; truncated to %d for the prompt", what, len(text), limit)
    return text[:limit] + "\n[...truncated]"


@dataclass
class GenerationOutcome:
    questions: list[Question]
    duplicates_removed: int
    duration_ms: int


def generate_questions(
    db: Session,
    llm: OllamaClient,
    session_id: str,
    count: int,
    type_: QuestionType | None = None,
    difficulty: Difficulty | None = None,
) -> GenerationOutcome:
    """Generate and store `count` new questions. Runs on the worker thread."""
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise LookupError(session_id)

    existing = list(session.questions)
    existing_mix = [(q.type, q.difficulty) for q in existing]
    previous_texts = [q.text for q in existing]
    jd = _truncate(session.job_description, MAX_JD_CHARS, "Job description")
    cv = _truncate(session.cv_text, MAX_CV_CHARS, "CV text")

    jd_points = extract_jd_points(session.job_description)
    cv_items = extract_cv_items(session.cv_text)
    used_focus = Counter(q.focus for q in existing if q.focus)

    kept: list[tuple[GeneratedQuestion, str | None]] = []
    dupes = 0
    duration_ms = 0
    # One call, plus a top-up call if duplicates were dropped, so the user gets `count`.
    for _ in range(1 + MAX_TOP_UPS):
        missing = count - len(kept)
        if missing <= 0:
            break
        mix = existing_mix + [(QuestionType(k.type), Difficulty(k.difficulty)) for k, _ in kept]
        slots = plan_slots(missing, mix, type_, difficulty)
        assign_focus(slots, used_focus, jd_points, cv_items)
        asked = previous_texts + [k.question for k, _ in kept]
        system, user = prompts.render(
            "generate_questions", job_description=jd, cv_text=cv, previous_questions=asked,
            slots=[{"type": s.type.value, "difficulty": s.difficulty.value,
                    "hint": SLOT_HINTS[s.type], "focus": s.focus} for s in slots],
        )
        result = llm.chat_json(
            system, user, QuestionBatch, label=f"questions:{session_id[:8]}",
            temperature=GENERATION_TEMPERATURE, num_predict=400 * missing + 200,
        )
        duration_ms += result.duration_ms
        # The model answers slots in order, so question i was steered by slots[i].focus.
        for gq, slot in zip(result.data.questions, slots):
            if is_duplicate(gq.question, previous_texts + [k.question for k, _ in kept]):
                dupes += 1
                continue
            kept.append((gq, slot.focus))
    if dupes:
        log.info("Dropped %d duplicate question(s) for session %s", dupes, session_id[:8])

    next_pos = (db.scalar(select(func.max(Question.position)).where(Question.session_id == session_id)) or 0) + 1
    batch = (db.scalar(select(func.max(Question.batch)).where(Question.session_id == session_id)) or 0) + 1
    new = []
    ungrounded = 0
    for i, (gq, focus) in enumerate(kept):
        evidence = [e.strip() for e in gq.cv_evidence if e.strip()]
        grounded = [e for e in evidence if grounded_in_cv(e, session.cv_text)]
        ungrounded += len(evidence) - len(grounded)
        q = Question(
            session_id=session_id, position=next_pos + i, batch=batch, text=gq.question.strip(),
            type=QuestionType(gq.type), difficulty=Difficulty(gq.difficulty), focus=focus,
            rubric=[r.strip() for r in gq.points_a_strong_answer_would_mention if r.strip()],
            cv_evidence=grounded,
        )
        db.add(q)
        new.append(q)
    if ungrounded:
        log.info("Dropped %d cv_evidence item(s) not found in the CV", ungrounded)
    db.commit()
    for q in new:
        db.refresh(q)
    return GenerationOutcome(new, dupes, duration_ms)
