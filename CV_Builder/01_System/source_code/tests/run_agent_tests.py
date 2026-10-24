import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent import ProfileAgent, build_llm

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = PROJECT_ROOT / "03_Evidence" / "02_Agent"

COMPLETE_INTRO = (
    "Hi, I'm Jordan Ramirez, a third-year Bachelor of Computing Science student at UTS, "
    "who started in February 2024 and expects to graduate in November 2026 with a WAM of 85 "
    "and coursework in databases and software engineering. My strongest skills are Python, "
    "SQL and Git. Between March 2024 and May 2024 I built a course-timetable API as a "
    "university group project using Flask and SQLite, which my faculty's timetabling office "
    "adopted and which cut manual scheduling time by around 30%. I'm looking for Junior "
    "Backend Developer or Software Engineering Intern roles."
)
# Every field the widened project/education checks look for (dates,
# distinctions, outcome, measurable results) is given upfront above, so the
# ONLY thing left is the mandatory read-back-and-confirm round every
# complete project/education entry now gets (see profile_model.compute_
# gaps()'s confirm_project/confirm_education gaps) - this is unconditional
# by design, not a leftover gap, so even a fully-detailed intro needs
# exactly one confirming reply rather than zero follow-ups.
COMPLETE_SCRIPTED_REPLIES = ["Yes, that's all correct."]

INCOMPLETE_INTRO = (
    "I'm a third-year Bachelor of Computing Science student at UTS. I'm confident with "
    "Python, SQL and Git, and I built a small course-timetable API in a team project using "
    "Flask and SQLite. I haven't decided what kind of role I want yet."
)
INCOMPLETE_SCRIPTED_REPLIES = [
    "Oh sorry, I'm Priya Kapoor.",
    "I think I'd like to apply for Junior Backend Developer or Software Engineering Intern roles.",
    # Covers the widened project/education checks (dates, distinctions,
    # outcome, measurable results) this profile never mentioned upfront -
    # bundled into one reply the same way the agent bundles its own
    # questions, plus a spare confirmation reply for the mandatory
    # read-back round every complete project/education entry now gets.
    "My degree started in February 2023 and I expect to graduate in June 2026, with a WAM of 78 "
    "and coursework in software engineering and databases. I worked on the course-timetable API "
    "from March 2024 to May 2024, and it was used by around 40 students in my course, reducing "
    "reported timetable clashes by about 25%.",
    "Yes, that's all correct.",
]


def format_entry(entry: dict) -> str:
    if entry["role"] == "user":
        return f"**User:** {entry['text']}\n"
    lines = [f"### Step {entry['step']} - Action: {entry['action']}"]
    if entry["detail"]:
        lines.append(f"- Input: `{json.dumps(entry['detail'])}`")
    lines.append(f"- Observation: `{json.dumps(entry['observation'])}`")
    return "\n".join(lines) + "\n"


def format_trace_markdown(title: str, intro: str, result: dict) -> str:
    parts = [f"## {title}", "", f"**Initial introduction:** {intro}", "", f"**Final status:** {result['status']}", ""]
    for entry in result["trace"]:
        parts.append(format_entry(entry))
    return "\n".join(parts)


def run_case(label: str, intro: str, llm, scripted_replies=None) -> dict:
    agent = ProfileAgent(llm, step_cap=8)
    result = agent.run(intro, scripted_replies=scripted_replies)
    print(f"[{label}] status={result['status']} steps_used={agent.step}")
    return result


def main():
    # Built once and reused for both cases - ProfileAgent's job_tool aside, LLMClient
    # is stateless (see agent.py's Isolation notes), and this also gives us the actual
    # backend that answered these calls, for the header below - LLM_BACKEND selects
    # between GROQ's cloud API and a local Ollama model (see agent.build_llm()), and
    # this file's own evidence should say which one actually ran rather than assuming.
    llm = build_llm()
    backend_label = "GROQ's cloud API" if llm.__class__.__name__ == "GroqLLM" else "a local Ollama model"

    complete_result = run_case("complete profile", COMPLETE_INTRO, llm, COMPLETE_SCRIPTED_REPLIES)
    incomplete_result = run_case("incomplete profile", INCOMPLETE_INTRO, llm, INCOMPLETE_SCRIPTED_REPLIES)

    combined_md = "\n\n".join(
        [
            "# Agent Actions and Observations",
            "",
            "Traces produced by `run_agent_tests.py` against the live `ProfileAgent`. "
            "The LLM backend is selected via `LLM_BACKEND` (see `agent.build_llm()`) - "
            f"either GROQ's cloud API or a local Ollama model; this run used {backend_label}. "
            "Each Action is one agent decision (ExtractFields, "
            "AskFollowUp, or FinalAnswer); the branch taken after each ExtractFields "
            "Observation depends on that Observation's `gaps` (the same extraction "
            "call's own field-aware completeness judgement - missing, ambiguous, or an "
            "unaddressed section), not a fixed script. Step limit: 8 agent actions.",
            format_trace_markdown("Test 1: Complete introduction (expect exactly 1 confirmation round)", COMPLETE_INTRO, complete_result),
            format_trace_markdown("Test 2: Incomplete introduction (expect >=2 follow-ups)", INCOMPLETE_INTRO, incomplete_result),
        ]
    )
    (EVIDENCE_DIR / "agent_actions_and_observations.md").write_text(combined_md, encoding="utf-8")

    follow_up_entries = [e for e in incomplete_result["trace"] if e["role"] == "user" or e.get("action") in ("AskFollowUp", "ExtractFields")]
    follow_up_md_parts = [
        "# Follow-up Question Test",
        "",
        "Focused excerpt from the incomplete-profile run in "
        "`agent_actions_and_observations.md`, isolating the follow-up questions the "
        "agent asked and the replies that resolved them.",
        "",
        f"**Initial introduction:** {INCOMPLETE_INTRO}",
        "",
    ]
    for entry in follow_up_entries:
        follow_up_md_parts.append(format_entry(entry))
    follow_up_md_parts.append(f"**Final status:** {incomplete_result['status']}")
    (EVIDENCE_DIR / "follow_up_question_test.md").write_text("\n".join(follow_up_md_parts), encoding="utf-8")

    print("Evidence written to:")
    print(f" - {EVIDENCE_DIR / 'agent_actions_and_observations.md'}")
    print(f" - {EVIDENCE_DIR / 'follow_up_question_test.md'}")


if __name__ == "__main__":
    main()
