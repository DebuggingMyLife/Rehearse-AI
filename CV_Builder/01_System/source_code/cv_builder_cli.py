import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import List, Optional

from agent import EXTRACTION_SYSTEM_PROMPT, LLMClient, JobRequirementAgent, ProfileAgent, build_llm
from cv_generator import CVGenerator
from cv_pdf import render_cv_pdf
from export_cv import edit_cv_interactive
from job_retrieval_tool import JobRetrievalTool

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "03_Evidence" / "04_System_Tests"


def run_full_flow(
    intro: str,
    scripted_replies: Optional[List[str]] = None,
    scripted_review_replies: Optional[List[str]] = None,
    job_choice: Optional[str] = None,
    scripted_edits: Optional[dict] = None,
    output_path: Optional[Path] = None,
    step_cap: int = 5,
    review_step_cap: int = 10,
    llm: Optional[LLMClient] = None,
    job_tool: Optional[JobRetrievalTool] = None,
    interactive_job_pick: bool = True,
    skip_pdf: bool = False,
    job_requirement_reply: Optional[str] = None,
) -> dict:
    """Runs the complete profile-to-PDF flow once: introduction -> ProfileAgent
    intake (with follow-ups as needed, projects never asked about here) ->
    review (project dates/outcome/confirmation, one at a time) -> confirmed
    profile -> job retrieval -> job pick -> job-specific requirement check ->
    CV generation -> edit -> PDF export. Returns everything a caller (the
    CLI below, or a test harness) needs to inspect: the agent trace, the
    confirmed profile, the job matches, the job-requirement check/
    resolution, the generated CV, and the PDF path.
    """
    llm = llm or build_llm()
    job_tool = job_tool or JobRetrievalTool()
    agent = ProfileAgent(llm, step_cap=step_cap, review_step_cap=review_step_cap, job_tool=job_tool)

    agent_result = agent.run(
        intro, scripted_replies=scripted_replies, scripted_review_replies=scripted_review_replies
    )

    if agent_result["status"] != "confirmed":
        return {"status": agent_result["status"], "agent_result": agent_result, "agent": agent}

    matches = agent_result["job_matches"]

    if job_choice:
        chosen = job_tool.get_job_by_id(job_choice)
    elif interactive_job_pick:
        print("\nTop 3 matched jobs:")
        for i, m in enumerate(matches, start=1):
            print(f"  {i}. {m['title']} ({m['document_id']}) - score {m['score']}")
            print(f"     {m['excerpt']}")
        choice = input("Pick a job number: ").strip()
        chosen = job_tool.get_job_by_id(matches[int(choice) - 1]["document_id"])
    else:
        chosen = job_tool.get_job_by_id(matches[0]["document_id"])

    checker = JobRequirementAgent(llm, agent.tool)
    job_requirement_check = checker.check(chosen)
    job_requirement_resolution = None
    if job_requirement_check["status"] == "needs_input":
        reply = job_requirement_reply if job_requirement_reply is not None else input(job_requirement_check["question"] + "\n> ")
        # Resolves the NAMED requirement gaps specifically (grounds each one
        # as confirmed or confirmed-absent), but JobRequirementAgent only
        # ever writes to technical_skills/achievements - it has no schema
        # for a new project, a second degree, or a new experience entry, so
        # a reply carrying one of those would otherwise be silently lost.
        job_requirement_resolution = checker.resolve(job_requirement_check["gaps"], reply)
        if job_requirement_resolution["confirmed_skills"]:
            print(f"\nConfirmed for this role: {', '.join(job_requirement_resolution['confirmed_skills'])}")
        if job_requirement_resolution["declined"]:
            print(f"Recorded as not currently held (won't appear on this CV): {', '.join(job_requirement_resolution['declined'])}")

        # ALWAYS also run the same reply through general extraction - a
        # reply to a named requirement is still an ordinary message and may
        # carry facts JobRequirementAgent has no schema for at all.
        extracted = llm.extract_json(
            EXTRACTION_SYSTEM_PROMPT,
            json.dumps(
                {
                    "current_draft": agent.tool.read_profile()["draft"],
                    "last_question_asked": job_requirement_check["question"],
                    "latest_message": reply,
                }
            ),
            # See agent.py's take_turn() for the max_tokens tightrope this
            # now walks between truncated output and GROQ rejecting an
            # over-large request outright.
            max_tokens=4000,
        )
        update_observation = agent.tool.update_profile(extracted)
        if update_observation["new_facts"]:
            print(f"Also captured: {'; '.join(update_observation['new_facts'])}")

    document_id = f"live_{uuid.uuid4().hex[:8]}"
    # Built AFTER the job-requirement check/resolution above, so any newly
    # confirmed skill or note is reflected in the CV; anything the student
    # didn't confirm was recorded as declined, never added here, so
    # CVGenerator can never claim it.
    profile = agent.tool.to_profile(document_id=document_id)

    generator = CVGenerator()
    cv = generator.generate(profile, chosen)

    if cv["grounding_warnings"]:
        print("\nGrounding warnings (content removed as ungrounded):")
        for w in cv["grounding_warnings"]:
            print(f"  - {w}")

    print("\n--- Review and edit your CV ---")
    cv = edit_cv_interactive(cv, scripted_edits=scripted_edits)

    if skip_pdf:
        output_path = None
    else:
        if output_path is None:
            safe_name = (profile.contact.name or "candidate").replace(" ", "_")
            output_path = DEFAULT_OUTPUT_DIR / f"{safe_name}_{chosen['document_id']}_cv.pdf"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        render_cv_pdf(cv, profile, output_path)

    return {
        "status": "confirmed",
        "agent": agent,
        "agent_result": agent_result,
        "profile": profile,
        "job_matches": matches,
        "chosen_job": chosen,
        "job_requirement_check": job_requirement_check,
        "job_requirement_resolution": job_requirement_resolution,
        "cv": cv,
        "output_path": output_path,
    }


def main():
    parser = argparse.ArgumentParser(description="Complete profile-to-PDF CV Builder flow.")
    parser.add_argument("--intro", help="Initial introduction text (skips the interactive prompt)")
    parser.add_argument("--intro-file", help="Path to a text file containing the initial introduction")
    parser.add_argument("--replies-json", help="Path to a JSON list of scripted follow-up replies")
    parser.add_argument("--review-replies-json", help="Path to a JSON list of scripted project-review replies")
    parser.add_argument("--job", help="jobs.jsonl document_id (skips the interactive job pick)")
    parser.add_argument("--edits-json", help="Path to a JSON file of scripted CV edits")
    parser.add_argument("--job-requirement-reply", help="Scripted reply to the job-specific requirement follow-up, if one is asked")
    parser.add_argument("--output", help="Output PDF path")
    parser.add_argument("--step-cap", type=int, default=5)
    parser.add_argument("--review-step-cap", type=int, default=10)
    parser.add_argument(
        "--llm-backend",
        choices=["groq", "local"],
        help="Override LLM_BACKEND for this run (default: env var, or 'groq' if unset)",
    )
    args = parser.parse_args()

    if args.intro:
        intro = args.intro
    elif args.intro_file:
        intro = Path(args.intro_file).read_text(encoding="utf-8").strip()
    else:
        intro = input("Tell me about yourself (education, skills, projects/experience, target roles): ")

    scripted_replies = json.loads(Path(args.replies_json).read_text(encoding="utf-8")) if args.replies_json else None
    scripted_review_replies = (
        json.loads(Path(args.review_replies_json).read_text(encoding="utf-8")) if args.review_replies_json else None
    )
    scripted_edits = json.loads(Path(args.edits_json).read_text(encoding="utf-8")) if args.edits_json else None

    result = run_full_flow(
        intro,
        scripted_replies=scripted_replies,
        scripted_review_replies=scripted_review_replies,
        job_choice=args.job,
        scripted_edits=scripted_edits,
        output_path=Path(args.output) if args.output else None,
        step_cap=args.step_cap,
        review_step_cap=args.review_step_cap,
        llm=build_llm(args.llm_backend) if args.llm_backend else None,
        interactive_job_pick=(args.job is None),
        job_requirement_reply=args.job_requirement_reply,
    )

    if result["status"] != "confirmed":
        print(f"\nProfile could not be confirmed (status={result['status']}).")
        return

    print(f"\nPDF exported to: {result['output_path']}")


if __name__ == "__main__":
    main()
