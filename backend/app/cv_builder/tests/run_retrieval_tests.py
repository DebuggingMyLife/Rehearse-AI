import json
import sys
from pathlib import Path

# backend/, so the `app` package imports when this is run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.cv_builder.agent import ProfileAgent, build_llm
from app.cv_builder.job_retrieval_tool import JobRetrievalTool
from app.cv_builder.profile_model import Profile

# The A1 record (evidence, setup docs) stays in CV_Builder/ at the repo root.
PROJECT_ROOT = Path(__file__).resolve().parents[4] / "CV_Builder"
STUDENT_PROFILES_PATH = Path(__file__).resolve().parents[1] / "data" / "student_profiles.jsonl"
EVIDENCE_PATH = PROJECT_ROOT / "03_Evidence" / "03_Retrieval" / "retrieval_results.md"

TEST_DOCUMENT_IDS = ["student_profile_01", "student_profile_02", "student_profile_04"]

AGENT_DEMO_INTRO = (
    "Hi, I'm Jordan Ramirez, a third-year Bachelor of Computing Science student at UTS. "
    "My strongest skills are Python, SQL and Git. I built a course-timetable API as a "
    "university group project using Flask and SQLite. I'm looking for Junior Backend "
    "Developer or Software Engineering Intern roles."
)


def load_test_profiles() -> list:
    records = {}
    with open(STUDENT_PROFILES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                record = json.loads(line)
                records[record["document_id"]] = record
    return [Profile.from_record(records[doc_id]) for doc_id in TEST_DOCUMENT_IDS]


def format_profile_results(profile: Profile, matches: list) -> str:
    lines = [
        f"## {profile.contact.name} ({profile.document_id})",
        "",
        f"**Target roles:** {', '.join(profile.job_goal.target_roles)}",
        f"**Skills:** {', '.join(profile.skills.technical_skills)}",
        "",
        "**Top 3 matched jobs:**",
        "",
    ]
    for rank, match in enumerate(matches, start=1):
        lines.append(f"{rank}. **{match['title']}** (`{match['document_id']}`) — score {match['score']}")
        lines.append(f"   > {match['excerpt']}")
        lines.append("")
    return "\n".join(lines)


def main():
    tool = JobRetrievalTool()
    profiles = load_test_profiles()

    sections = [
        "# Retrieval Results",
        "",
        "Top-3 semantic job matches per test profile, from `run_retrieval_tests.py` "
        "using `JobRetrievalTool` (sentence-transformers `all-MiniLM-L6-v2` embeddings, "
        "cosine similarity). Excerpts are the single sentence within each job's actual "
        "description with the highest similarity to the profile's query embedding, not "
        "a generic label.",
        "",
    ]
    for profile in profiles:
        matches = tool.search(profile, top_k=3)
        sections.append(format_profile_results(profile, matches))
        print(f"[{profile.document_id}] {profile.contact.name}: " + ", ".join(m["document_id"] for m in matches))

    sections.append("---")
    sections.append("")
    sections.append("## Tool wiring check: job_retrieval_tool called from ProfileAgent")
    sections.append("")
    sections.append(
        "Demonstrates `job_retrieval_tool` wired into the agent from the previous step: once "
        "`ProfileAgent.run()` reaches `FinalAnswer`, it takes one further `RetrieveJobs` Action "
        "calling `job_tool.search()` on the confirmed draft profile."
    )
    sections.append("")

    llm = build_llm()
    agent = ProfileAgent(llm, step_cap=8, review_step_cap=10, job_tool=tool)
    # AGENT_DEMO_INTRO predates education_dates becoming a mandatory gap and
    # never states the project's dates either - without these, run() falls
    # through to input() in a non-interactive run.
    agent_result = agent.run(
        AGENT_DEMO_INTRO,
        scripted_replies=["I started in March 2023 and expect to graduate in December 2026."],
        scripted_review_replies=[
            "It ran from March 2024 to April 2024.",
            "It let students search and enrol in units through a web interface backed by the Flask API.",
        ],
    )
    retrieve_action = next(e for e in agent_result["trace"] if e.get("action") == "RetrieveJobs")
    sections.append(f"**Introduction used:** {AGENT_DEMO_INTRO}")
    sections.append("")
    sections.append(f"**Agent RetrieveJobs Observation:** `{json.dumps(retrieve_action['observation'])}`")
    print("[agent-wired] RetrieveJobs matches:", [m["document_id"] for m in agent_result["job_matches"]])

    EVIDENCE_PATH.write_text("\n".join(sections), encoding="utf-8")
    print(f"Evidence written to: {EVIDENCE_PATH}")


if __name__ == "__main__":
    main()
