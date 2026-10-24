import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import ProfileAgent, build_llm
from cv_generator import CVGenerator
from cv_pdf import render_cv_pdf
from job_retrieval_tool import JobRetrievalTool

PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_PATH = PROJECT_ROOT / "03_Evidence" / "04_System_Tests" / "two_job_comparison.md"
PDF_DIR = PROJECT_ROOT / "03_Evidence" / "04_System_Tests" / "sample_cv_pdfs"

INTRO = (
    "Hi, I'm Ethan Brooks, a third-year Bachelor of Computing Science student at UTS. "
    "I'm solid in Java, Python, SQL and Git. Last semester I built a library-booking "
    "REST API as a team project using Spring Boot and PostgreSQL, and I worked "
    "part-time as a junior IT helpdesk assistant fixing account and login issues. "
    "I'm targeting Junior Backend Developer and Graduate Software Engineer roles."
)


def format_cv_column(label: str, cv: dict) -> str:
    lines = [
        f"### {label}: {cv['target_job_title']} (`{cv['target_job_document_id']}`)",
        "",
        f"**Summary:** {cv['summary']}",
        "",
        f"**Skills (order as generated):** {', '.join(cv['skills'])}",
        "",
        "**Section order in this CV:** Summary -> Education -> Skills"
        + (" -> Experience" if cv["experience"] else "")
        + (" -> Projects" if cv["projects"] else ""),
        "",
        f"**Matched skills:** {', '.join(cv['matched_skills']) or '(none)'}",
        f"**Missing requirements:** {', '.join(cv['missing_requirements']) or '(none)'}",
        f"**Grounding warnings:** {cv['grounding_warnings'] or '(none)'}",
    ]
    return "\n".join(lines)


def main():
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    llm = build_llm()
    job_tool = JobRetrievalTool()
    agent = ProfileAgent(llm, step_cap=8, review_step_cap=10, job_tool=job_tool)
    # INTRO predates education_dates becoming a mandatory gap and never states
    # the project's dates either - without these, run() falls through to
    # input() in a non-interactive run.
    agent_result = agent.run(
        INTRO,
        scripted_replies=["I started in February 2023 and expect to graduate in December 2025."],
        scripted_review_replies=[
            "It ran from February 2025 to March 2025.",
            "It let staff and students search for and reserve library items through a simple web interface.",
        ],
    )
    assert agent_result["status"] == "confirmed"

    matches = agent_result["job_matches"]
    job_a = job_tool.get_job_by_id(matches[0]["document_id"])
    job_b = job_tool.get_job_by_id(matches[1]["document_id"])

    profile = agent.tool.to_profile(document_id="live_ethan_brooks")
    profile_before = asdict(profile)

    generator = CVGenerator()
    cv_a = generator.generate(profile, job_a)
    cv_b = generator.generate(profile, job_b)

    profile_after = asdict(profile)
    unchanged = profile_before == profile_after
    print(f"Profile unchanged after generating both CVs: {unchanged}")

    pdf_a = PDF_DIR / f"Ethan_Brooks_{job_a['document_id']}_cv.pdf"
    pdf_b = PDF_DIR / f"Ethan_Brooks_{job_b['document_id']}_cv.pdf"
    render_cv_pdf(cv_a, profile, pdf_a)
    render_cv_pdf(cv_b, profile, pdf_b)
    print(f"PDFs written: {pdf_a.name}, {pdf_b.name}")

    sections = [
        "# Two-Job Comparison",
        "",
        "Same confirmed profile (Ethan Brooks, live agent-confirmed via `cv_builder_cli`, not "
        "a dataset profile), two different target jobs from his own top-3 retrieval results, "
        "generated via `CVGenerator`.",
        "",
        f"**Initial introduction:** {INTRO}",
        "",
        f"**Profile unchanged after generating both CVs:** `{unchanged}` "
        "(profile dict compared field-for-field before vs. after both generate() calls)",
        "",
        "## Side-by-side comparison",
        "",
        "| | Job A | Job B |",
        "|---|---|---|",
        f"| Target job | {cv_a['target_job_title']} (`{cv_a['target_job_document_id']}`) | {cv_b['target_job_title']} (`{cv_b['target_job_document_id']}`) |",
        f"| Skills order | {', '.join(cv_a['skills'])} | {', '.join(cv_b['skills'])} |",
        f"| Matched skills | {', '.join(cv_a['matched_skills']) or '(none)'} | {', '.join(cv_b['matched_skills']) or '(none)'} |",
        f"| # Missing requirements | {len(cv_a['missing_requirements'])} | {len(cv_b['missing_requirements'])} |",
        "",
        format_cv_column("Job A", cv_a),
        "",
        "---",
        "",
        format_cv_column("Job B", cv_b),
        "",
        "---",
        "",
        f"Sample PDFs exported to: `03_Evidence/04_System_Tests/sample_cv_pdfs/{pdf_a.name}`, "
        f"`03_Evidence/04_System_Tests/sample_cv_pdfs/{pdf_b.name}`",
    ]
    EVIDENCE_PATH.write_text("\n".join(sections), encoding="utf-8")
    print(f"Evidence written to: {EVIDENCE_PATH}")


if __name__ == "__main__":
    main()
