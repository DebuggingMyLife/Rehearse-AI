import json
import sys
from dataclasses import asdict
from pathlib import Path

# backend/, so the `app` package imports when this is run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.cv_builder.agent import LLMClient, ProfileAgent, build_llm
from app.cv_builder.cv_generator import CVGenerator
from app.cv_builder.job_retrieval_tool import JobRetrievalTool

# The A1 record (evidence, setup docs) stays in CV_Builder/ at the repo root.
PROJECT_ROOT = Path(__file__).resolve().parents[4] / "CV_Builder"
EVIDENCE_PATH = PROJECT_ROOT / "03_Evidence" / "04_System_Tests" / "cross_user_test.md"

USER_A = {
    "name": "Ethan Brooks",
    "intro": (
        "Hi, I'm Ethan Brooks, a third-year Bachelor of Computing Science student at UTS. "
        "I'm solid in Java, Python, SQL and Git. Last semester I built a library-booking "
        "REST API as a team project using Spring Boot and PostgreSQL, and I worked "
        "part-time as a junior IT helpdesk assistant fixing account and login issues. "
        "I'm targeting Junior Backend Developer and Graduate Software Engineer roles."
    ),
    # Predates education_dates becoming a mandatory gap and never states the
    # project's dates either - both scripted here so run() never falls
    # through to input() in a non-interactive run.
    "scripted_replies": ["I started in February 2023 and expect to graduate in December 2025."],
    "scripted_review_replies": [
        "It ran from February 2025 to March 2025.",
        "It let staff and students search for and reserve library items through a simple web interface.",
    ],
}

USER_B = {
    "name": "Devon Okafor",
    "intro": (
        "I'm a third-year Bachelor of Computing Science student at UTS. I've been working "
        "with Python, Hugging Face Transformers and PyTorch, and I built a "
        "sentiment-analysis tool for coursework that classifies product reviews. I haven't "
        "figured out exactly what kind of role I want yet."
    ),
    "scripted_replies": [
        "Oh, I'm Devon Okafor.",
        "I'd like to apply for AI Intern or NLP Research Assistant roles.",
        "I started in February 2023 and expect to graduate in December 2025.",
    ],
    "scripted_review_replies": [
        "It ran from March 2025 to April 2025.",
        "It correctly classified sentiment for most of the test reviews I ran it against.",
    ],
}


def run_user(user_def: dict, llm: LLMClient, job_tool: JobRetrievalTool):
    agent = ProfileAgent(llm, step_cap=8, review_step_cap=10, job_tool=job_tool)
    agent_result = agent.run(
        user_def["intro"],
        scripted_replies=user_def["scripted_replies"],
        scripted_review_replies=user_def["scripted_review_replies"],
    )
    assert agent_result["status"] == "confirmed", f"{user_def['name']} did not confirm"
    profile = agent.tool.to_profile(document_id=f"live_{user_def['name'].replace(' ', '_').lower()}")
    return agent, agent_result, profile


def main():
    llm = build_llm()
    job_tool = JobRetrievalTool()

    # Run User A to completion first, snapshot their state.
    agent_a, result_a, profile_a = run_user(USER_A, llm, job_tool)
    draft_a_after_a = agent_a.tool.read_profile()["draft"]

    # Now run User B, in the same process, sharing the same llm/job_tool instances
    # (but each with their OWN ProfileAgent/ProfileTool) - this is the isolation
    # boundary actually being tested: shared stateless services (llm, job_tool),
    # separate per-user state (agent.tool).
    agent_b, result_b, profile_b = run_user(USER_B, llm, job_tool)

    # Re-read User A's state again, after User B's entire run, to confirm nothing changed.
    draft_a_after_b = agent_a.tool.read_profile()["draft"]

    a_unaffected_by_b = draft_a_after_a == draft_a_after_b
    different_objects = agent_a.tool is not agent_b.tool
    no_name_leak = profile_a.contact.name not in json.dumps(asdict(profile_b)) and profile_b.contact.name not in json.dumps(asdict(profile_a))

    # Skills alone are a poor isolation signal - two real, unrelated people can both
    # legitimately know "Python". Project titles are unique per persona in this test
    # data, so they're a reliable leak detector: neither profile's own project(s)
    # should ever appear on the other's project list.
    titles_a = {p.title for p in profile_a.projects.entries}
    titles_b = {p.title for p in profile_b.projects.entries}
    no_project_leak = not (titles_a & titles_b)

    generator = CVGenerator()
    matches_a = result_a["job_matches"]
    matches_b = result_b["job_matches"]
    cv_a = generator.generate(profile_a, job_tool.get_job_by_id(matches_a[0]["document_id"]))
    cv_b = generator.generate(profile_b, job_tool.get_job_by_id(matches_b[0]["document_id"]))

    cv_a_project_titles = {p["title"] for p in cv_a["projects"]}
    cv_b_project_titles = {p["title"] for p in cv_b["projects"]}
    cv_a_mentions_b = profile_b.contact.name in cv_a["summary"] or bool(cv_a_project_titles & titles_b)
    cv_b_mentions_a = profile_a.contact.name in cv_b["summary"] or bool(cv_b_project_titles & titles_a)

    print(f"draft A unaffected by running B: {a_unaffected_by_b}")
    print(f"separate ProfileTool objects: {different_objects}")
    print(f"no name cross-leak: {no_name_leak}")
    print(f"no project cross-leak: {no_project_leak}")
    print(f"CV A contaminated by B: {cv_a_mentions_b}, CV B contaminated by A: {cv_b_mentions_a}")

    all_passed = a_unaffected_by_b and different_objects and no_name_leak and no_project_leak and not cv_a_mentions_b and not cv_b_mentions_a

    sections = [
        "# Cross-User Isolation Test",
        "",
        "Two separate users run through the full agent -> job retrieval -> CV generation flow "
        "in the same Python process, sharing the same stateless service instances (the shared "
        "LLMClient, JobRetrievalTool) but each with their own ProfileAgent/ProfileTool. User A completes "
        "first (0 follow-ups); User B runs afterward (2 follow-ups) to also confirm a completed "
        "user's state survives a second, unrelated conversation happening after it.",
        "",
        f"**User A:** {USER_A['name']} — {USER_A['intro']}",
        "",
        f"**User B:** {USER_B['name']} — {USER_B['intro']}",
        "",
        "## Isolation checks",
        "",
        f"- User A's draft profile unchanged after User B's entire run completed: `{a_unaffected_by_b}`",
        f"- User A and User B have separate ProfileTool instances (`agent_a.tool is not agent_b.tool`): `{different_objects}`",
        f"- No cross-contamination of names between the two confirmed profiles: `{no_name_leak}`",
        f"- No project-title cross-contamination between the two confirmed profiles: `{no_project_leak}`",
        f"- User A's generated CV does not mention User B's name/skills: `{not cv_a_mentions_b}`",
        f"- User B's generated CV does not mention User A's name/skills: `{not cv_b_mentions_a}`",
        "",
        f"**All isolation checks passed: `{all_passed}`**",
        "",
        "## User A result",
        "",
        f"- Retrieved top job: `{matches_a[0]['document_id']}` ({matches_a[0]['title']})",
        f"- Matched skills: {', '.join(cv_a['matched_skills']) or '(none)'}",
        f"- Missing requirements: {', '.join(cv_a['missing_requirements']) or '(none)'}",
        f"- CV summary: {cv_a['summary']}",
        f"- CV skills: {', '.join(cv_a['skills'])}",
        "",
        "## User B result",
        "",
        f"- Retrieved top job: `{matches_b[0]['document_id']}` ({matches_b[0]['title']})",
        f"- Matched skills: {', '.join(cv_b['matched_skills']) or '(none)'}",
        f"- Missing requirements: {', '.join(cv_b['missing_requirements']) or '(none)'}",
        f"- CV summary: {cv_b['summary']}",
        f"- CV skills: {', '.join(cv_b['skills'])}",
    ]
    EVIDENCE_PATH.write_text("\n".join(sections), encoding="utf-8")
    print(f"\nEvidence written to: {EVIDENCE_PATH}")


if __name__ == "__main__":
    main()
