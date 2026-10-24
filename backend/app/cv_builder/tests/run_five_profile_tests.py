import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cv_builder_cli import run_full_flow

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEST_PROFILES_DIR = PROJECT_ROOT / "03_Evidence" / "04_System_Tests" / "test_profiles"
RESULTS_PATH = PROJECT_ROOT / "03_Evidence" / "04_System_Tests" / "five_profile_results.md"

# Five distinct personas: varied education/year, skills, experience, projects, and
# career goals. Two are complete (0 follow-ups expected); three are deliberately
# incomplete, each missing a different combination of required fields, to exercise
# the agent's follow-up mechanism in more than one way.

PROFILES = [
    {
        "slug": "profile_1_ethan_brooks",
        "label": "Ethan Brooks - backend/software generalist (complete)",
        "intro": (
            "Hi, I'm Ethan Brooks, a third-year Bachelor of Computing Science student at UTS. "
            "I'm solid in Java, Python, SQL and Git. Last semester I built a library-booking "
            "REST API as a team project using Spring Boot and PostgreSQL, and I worked "
            "part-time as a junior IT helpdesk assistant fixing account and login issues. "
            "I'm targeting Junior Backend Developer and Graduate Software Engineer roles."
        ),
        # Predates education_dates becoming a mandatory gap and never states
        # the project's dates either - both scripted so run() never falls
        # through to input() in a non-interactive run.
        "scripted_replies": ["I started in February 2023 and expect to graduate in December 2025."],
        "scripted_review_replies": [
            "It ran from February 2025 to March 2025.",
            "It let staff and students search for and reserve library items through a simple web interface.",
        ],
    },
    {
        "slug": "profile_2_priya_nair",
        "label": "Priya Nair - data/analytics (complete)",
        "intro": (
            "I'm Priya Nair, a second-year Bachelor of Computing Science student at UTS. My "
            "skills include Python, pandas, SQL and Power BI. For a coursework project I "
            "cleaned a messy retail sales dataset and built a Power BI dashboard to track "
            "store performance. I'm aiming for Data Analyst Intern and Business Intelligence "
            "Intern roles."
        ),
        "scripted_replies": ["I started in February 2024 and expect to graduate in December 2026."],
        "scripted_review_replies": [
            "It ran from March 2024 to April 2024.",
            "The dashboard let store managers track sales trends and stock levels at a glance.",
        ],
    },
    {
        "slug": "profile_3_devon_okafor",
        "label": "Devon Okafor - AI/NLP (incomplete: name, target_roles)",
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
    },
    {
        "slug": "profile_4_marcus_webb",
        "label": "Marcus Webb - cybersecurity/systems (incomplete: technical_skills, target_roles)",
        "intro": (
            "My name is Marcus Webb, a third-year Bachelor of Computing Science student at "
            "UTS. For a networking course I set up a small home lab and documented common "
            "attack patterns I found while monitoring traffic. I'm not sure which skills to "
            "highlight or what roles to apply for yet."
        ),
        "scripted_replies": [
            # technical_skills and target_roles now arrive as one bundled
            # follow-up question, so one reply covering both is what a real
            # student would send back in a single message.
            "I'd say Linux, Wireshark, and basic network troubleshooting. I think "
            "Cybersecurity Intern or Junior SOC Analyst roles would suit me.",
            "I started in February 2023 and expect to graduate in December 2025.",
        ],
        "scripted_review_replies": [
            "It ran from August 2025 to September 2025.",
            "I used it to monitor traffic on my home network and identify common attack signatures.",
        ],
    },
    {
        "slug": "profile_5_sarah_chen",
        "label": "Sarah Chen - full-stack/cloud (incomplete: degree, year, institution)",
        "intro": (
            "Hi, I'm Sarah Chen. My skills are JavaScript, React, Node.js, and AWS basics. "
            "I'm looking for Full-Stack Developer Intern and Junior Cloud Engineer roles."
        ),
        "scripted_replies": [
            # degree and year now arrive as one bundled follow-up question -
            # evidence/projects is no longer a gap at all (lowered bar), so
            # no reply is needed for that dimension anymore.
            "I'm doing a Bachelor of Computing Science, and I'm a second-year student.",
            "I started in February 2024 and expect to graduate in December 2026.",
            # Unlike the other four, Sarah's intro never names an institution
            # at all - it's a genuinely separate gap here.
            "I'm at UTS.",
        ],
        # No project/experience mentioned at all for Sarah - review phase has
        # nothing to ask, no scripted_review_replies needed.
    },
]


def format_entry(entry: dict) -> str:
    if entry["role"] == "user":
        return f"**User:** {entry['text']}\n"
    lines = [f"### Step {entry['step']} - Action: {entry['action']}"]
    if entry.get("detail"):
        lines.append(f"- Input: `{json.dumps(entry['detail'])}`")
    lines.append(f"- Observation: `{json.dumps(entry['observation'])}`")
    return "\n".join(lines) + "\n"


def run_one(profile_def: dict) -> dict:
    result = run_full_flow(
        profile_def["intro"],
        scripted_replies=profile_def["scripted_replies"],
        scripted_review_replies=profile_def.get("scripted_review_replies", []),
        job_choice=None,
        scripted_edits={},
        interactive_job_pick=False,
        skip_pdf=True,
        # Some of these five profiles are deliberately incomplete across
        # MULTIPLE separate dimensions (name, target_roles, education_dates),
        # each answered by its own scripted reply rather than one combined
        # message - that legitimately needs more than step_cap=5's 2-round
        # budget (each round is 2 steps: ExtractFields + AskFollowUp).
        step_cap=8,
        # The auto-picked top job may have its own stated requirement gaps
        # (JobRequirementAgent) - without a reply, run_full_flow() falls
        # through to input() in a non-interactive run. A generic decline is
        # accurate for all five personas here (none of them claim the kind
        # of gaps this job corpus tends to ask about).
        job_requirement_reply="No, I don't have experience with any of those.",
    )
    return result


def write_profile_file(profile_def: dict, result: dict) -> None:
    parts = [
        f"# {profile_def['label']}",
        "",
        f"**Initial introduction:** {profile_def['intro']}",
        "",
    ]
    if result["status"] != "confirmed":
        parts.append(f"**Status:** {result['status']} (did not confirm within step limit)")
        for entry in result["agent_result"]["trace"]:
            parts.append(format_entry(entry))
        (TEST_PROFILES_DIR / f"{profile_def['slug']}.md").write_text("\n".join(parts), encoding="utf-8")
        return

    parts.append(f"**Status:** confirmed ({len([e for e in result['agent_result']['trace'] if e['role'] == 'agent' and e['action'] == 'AskFollowUp'])} follow-up question(s) asked)")
    parts.append("")
    parts.append("## Action/Observation trace")
    parts.append("")
    for entry in result["agent_result"]["trace"]:
        parts.append(format_entry(entry))

    parts.append("## Confirmed profile")
    parts.append(f"```json\n{json.dumps(asdict(result['profile']), indent=2)}\n```")

    (TEST_PROFILES_DIR / f"{profile_def['slug']}.md").write_text("\n".join(parts), encoding="utf-8")


def format_summary_section(profile_def: dict, result: dict) -> str:
    if result["status"] != "confirmed":
        return f"## {profile_def['label']}\n\n**Status:** {result['status']} (did not confirm within step limit — see test_profiles/{profile_def['slug']}.md)\n"

    follow_ups = [e for e in result["agent_result"]["trace"] if e["role"] == "agent" and e["action"] == "AskFollowUp"]
    matches = result["job_matches"]
    cv = result["cv"]
    lines = [
        f"## {profile_def['label']}",
        "",
        f"**Follow-up questions asked:** {len(follow_ups)}" + (f" ({'; '.join(e['detail']['target_field'] for e in follow_ups)})" if follow_ups else ""),
        f"**Target roles:** {', '.join(result['profile'].job_goal.target_roles)}",
        "",
        "**Top 3 job matches (document_id — score):**",
    ]
    for m in matches:
        lines.append(f"- `{m['document_id']}` — {m['title']} (score {m['score']})")
    lines.append("")
    lines.append(f"**CV generated for:** `{cv['target_job_document_id']}` ({cv['target_job_title']})")
    lines.append(f"**Matched skills:** {', '.join(cv['matched_skills']) or '(none)'}")
    lines.append(f"**Missing requirements:** {', '.join(cv['missing_requirements']) or '(none)'}")
    lines.append(f"**Grounding warnings:** {cv['grounding_warnings'] or '(none)'}")
    lines.append("")
    lines.append(f"**Final CV summary:** {cv['summary']}")
    lines.append(f"**Final CV skills:** {', '.join(cv['skills'])}")
    lines.append(f"(Full profile + trace: test_profiles/{profile_def['slug']}.md)")
    return "\n".join(lines)


def main():
    TEST_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    summary_sections = [
        "# Five Profile Results",
        "",
        "Five distinct synthetic introductions run through the full agent -> job "
        "retrieval -> CV generation flow (`cv_builder_cli.run_full_flow`). Two are "
        "complete introductions (0 follow-ups expected); three are deliberately "
        "incomplete, each missing a different combination of required fields, to "
        "exercise the follow-up mechanism in more than one way. CV generated against "
        "each profile's own #1 retrieved job.",
        "",
    ]
    for profile_def in PROFILES:
        print(f"Running: {profile_def['label']}")
        result = run_one(profile_def)
        write_profile_file(profile_def, result)
        summary_sections.append(format_summary_section(profile_def, result))
        if result["status"] == "confirmed":
            n_followups = len([e for e in result["agent_result"]["trace"] if e["role"] == "agent" and e["action"] == "AskFollowUp"])
            print(f"  -> confirmed, {n_followups} follow-up(s), top job: {result['job_matches'][0]['document_id']}")
        else:
            print(f"  -> {result['status']}")

    RESULTS_PATH.write_text("\n\n".join(summary_sections), encoding="utf-8")
    print(f"\nSummary written to: {RESULTS_PATH}")
    print(f"Per-profile files written to: {TEST_PROFILES_DIR}")


if __name__ == "__main__":
    main()
