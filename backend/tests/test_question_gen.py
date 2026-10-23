from collections import Counter

from app import prompts
from app.models import Difficulty as D
from app.models import QuestionType as T
from app.services.question_gen import is_duplicate, plan_slots


def test_default_batch_mixes_types_and_difficulties():
    slots = plan_slots(5, [])
    types = Counter(s.type for s in slots)
    assert set(types) == {T.behavioural, T.technical, T.cv_specific}
    assert max(types.values()) - min(types.values()) <= 1
    diffs = Counter(s.difficulty for s in slots)
    assert diffs[D.medium] >= diffs[D.easy] and diffs[D.medium] >= diffs[D.hard]
    assert diffs[D.easy] >= 1 and diffs[D.hard] >= 1


def test_generate_more_balances_against_existing():
    existing = [(T.behavioural, D.medium), (T.behavioural, D.medium), (T.technical, D.medium)]
    slots = plan_slots(2, existing)
    assert [s.type for s in slots] == [T.cv_specific, T.technical]
    assert {s.difficulty for s in slots} == {D.easy, D.hard}


def test_explicit_filters_are_respected():
    slots = plan_slots(3, [], T.technical, D.hard)
    assert all(s.type == T.technical and s.difficulty == D.hard for s in slots)


def test_duplicates():
    prev = ["Tell me about a time you resolved a conflict within your team."]
    assert is_duplicate("Tell me about a time you resolved a conflict in your team?", prev)
    assert is_duplicate("tell me about a time you resolved a conflict within your team", prev)
    assert not is_duplicate("How would you design a rate limiter for a public API?", prev)


# Real rewordings qwen2.5:7b produced on "generate more" during testing.
def test_reworded_duplicates_from_live_run():
    assert is_duplicate(
        "Describe your experience with the migration of the payments ledger from a monolith to "
        "event-driven microservices on Kafka at PayLoop. What was the main challenge you faced "
        "during this migration, and how did you address it?",
        ["In your experience with the migration of the payments ledger from a monolith to "
         "microservices, what challenges did you face and how did you overcome them?"],
    )
    assert is_duplicate(
        "How do you ensure data security and privacy in your backend services, especially when "
        "handling sensitive health data? Can you give an example of a specific security measure "
        "you implemented in a previous project?",
        ["How do you ensure data security and privacy in your backend services, especially when "
         "handling sensitive health data?"],
    )
    assert is_duplicate(
        "Can you walk me through your experience with designing and implementing idempotent "
        "payment APIs in Python/FastAPI?",
        ["Can you explain how you designed and implemented idempotent payment APIs in Python/FastAPI?"],
    )


def test_different_questions_on_same_project_are_not_duplicates():
    asked = ["What challenges did you face migrating the payments ledger to Kafka microservices?"]
    assert not is_duplicate(
        "How did you mentor the three junior engineers and roll out code review guidelines?", asked)
    assert not is_duplicate(
        "How would you model appointment bookings in PostgreSQL to avoid double-booking?", asked)


def test_prompt_renders_previous_questions_and_slots():
    system, user = prompts.render(
        "generate_questions", job_description="JD", cv_text="CV",
        previous_questions=["Old question one?"],
        slots=[{"type": "technical", "difficulty": "hard", "hint": "general knowledge",
               "focus": "Strong PostgreSQL skills"}],
    )
    assert "Respond with JSON only" in system
    assert "- Old question one?" in user
    assert "1. type=technical, difficulty=hard: general knowledge" in user
    assert "exactly 1 new question," in user
    assert 'Focus on: "Strong PostgreSQL skills"' in user


def test_evidence_grounding():
    from app.services.question_gen import grounded_in_cv

    cv = "Led migration of the payments ledger to Kafka. Skills: Python, AWS, PostgreSQL."
    assert grounded_in_cv("Led the payments ledger migration to Kafka", cv)
    # copied from a job description, not the CV
    assert not grounded_in_cv("Experience with AWS, infrastructure as code, and observability", cv)


JD = """Senior Backend Engineer
Requirements:
- 5+ years building backend services in Python or Go
- Strong PostgreSQL skills, data modelling, and performance tuning
- Ability to mentor engineers and communicate trade-offs to stakeholders
Nice to have: Kubernetes."""

CV = """Experience
\u2022 Led migration of the payments ledger to event-driven microservices on Kafka,
reducing settlement latency from 4 hours to 15 minutes.
\u2022 Introduced Redis caching for the product catalogue, lowering p95 latency.
Skills: Python, Go"""


def test_extract_points_joins_wrapped_bullets():
    from app.services.question_gen import extract_cv_items, extract_jd_points

    assert len(extract_jd_points(JD)) == 3
    items = extract_cv_items(CV)
    assert len(items) == 2
    assert items[0].endswith("from 4 hours to 15 minutes.")


def test_assign_focus_spreads_topics_and_matches_type():
    from app.services.question_gen import Slot, assign_focus, extract_cv_items, extract_jd_points

    jd, cv = extract_jd_points(JD), extract_cv_items(CV)
    slots = [Slot(T.technical, D.medium), Slot(T.technical, D.hard),
             Slot(T.behavioural, D.medium), Slot(T.cv_specific, D.easy), Slot(T.cv_specific, D.hard)]
    used = Counter()
    assign_focus(slots, used, jd, cv)
    assert "mentor" in slots[2].focus                     # soft skill -> behavioural
    assert "mentor" not in slots[0].focus + slots[1].focus  # technical gets hard skills
    assert slots[0].focus != slots[1].focus
    assert slots[3].focus != slots[4].focus and "Kafka" in slots[3].focus

    # "generate more" continues with the least-used items
    more = [Slot(T.technical, D.easy)]
    assign_focus(more, used, jd, cv)
    assert used[more[0].focus] == 2


def test_no_bullets_falls_back_to_sentences():
    from app.services.question_gen import extract_jd_points

    jd = "We need someone to own our data platform. You will design pipelines in Spark and Airflow."
    assert len(extract_jd_points(jd)) == 2


def test_jd_points_drop_experience_framing():
    from app.services.question_gen import extract_jd_points

    jd = ("- 5+ years building backend services in Python or Go\n"
          "- Experience designing APIs and distributed systems\n"
          "- Strong PostgreSQL skills, data modelling, and performance tuning\n"
          "- 3 years of experience with Terraform and AWS infrastructure\n")
    assert extract_jd_points(jd) == [
        "Building backend services in Python or Go",
        "Designing APIs and distributed systems",
        "PostgreSQL skills, data modelling, and performance tuning",
        "Terraform and AWS infrastructure",
    ]


def test_behavioural_moves_to_common_competencies_after_jd_soft_skills():
    from app.services.question_gen import COMMON_COMPETENCIES, Slot, assign_focus, extract_jd_points

    slots = [Slot(T.behavioural, D.medium) for _ in range(3)]
    assign_focus(slots, Counter(), extract_jd_points(JD), [])
    assert "mentor" in slots[0].focus
    assert slots[1].focus in COMMON_COMPETENCIES and slots[2].focus in COMMON_COMPETENCIES
    assert len({s.focus for s in slots}) == 3
