import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from cv_generator import CVGenerator
from cv_pdf import render_cv_pdf
from job_retrieval_tool import JobRetrievalTool
from profile_model import Profile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUDENT_PROFILES_PATH = PROJECT_ROOT / "01_System" / "source_code" / "data" / "student_profiles.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "03_Evidence" / "04_System_Tests"


def _load_profile_records() -> list:
    with open(STUDENT_PROFILES_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_profile(document_id: str) -> Profile:
    for record in _load_profile_records():
        if record["document_id"] == document_id:
            return Profile.from_record(record)
    raise KeyError(f"No profile with document_id={document_id!r}")


def prompt_choose_profile() -> Profile:
    records = _load_profile_records()
    print("Available profiles:")
    for i, r in enumerate(records, start=1):
        print(f"  {i}. {r['name']} ({r['document_id']})")
    choice = input("Pick a profile number: ").strip()
    return Profile.from_record(records[int(choice) - 1])


def prompt_choose_job(tool: JobRetrievalTool, profile: Profile) -> dict:
    matches = tool.search(profile, top_k=3)
    print(f"\nTop 3 matched jobs for {profile.contact.name}:")
    for i, m in enumerate(matches, start=1):
        print(f"  {i}. {m['title']} ({m['document_id']}) - score {m['score']}")
        print(f"     {m['excerpt']}")
    choice = input("Pick a job number: ").strip()
    chosen = matches[int(choice) - 1]
    return tool.get_job_by_id(chosen["document_id"])


def edit_cv_interactive(cv: dict, scripted_edits: Optional[dict] = None) -> dict:
    """Walk through each editable field. Press Enter to keep the generated
    text, or type a replacement. If scripted_edits is provided (e.g. by an
    automated test run via --edits-json), fields it names are applied
    without prompting and every other field is left as-is, with no input()
    call at all - this is what makes the script runnable non-interactively."""
    interactive = scripted_edits is None
    scripted_edits = scripted_edits or {}

    def edit_text(label: str, current: str, key: str) -> str:
        if key in scripted_edits:
            new_value = scripted_edits[key]
            print(f"\n{label}:\n  current: {current}\n  edited: {new_value}")
            return new_value
        if not interactive:
            return current
        print(f"\n{label}:\n  {current}")
        new_value = input("  Press Enter to keep, or type a replacement: ").strip()
        return new_value if new_value else current

    cv["summary"] = edit_text("Summary", cv["summary"], "summary")
    cv["education"] = edit_text("Education", cv["education"], "education")

    skills_line = edit_text("Skills (comma-separated)", ", ".join(cv["skills"]), "skills")
    cv["skills"] = [s.strip() for s in skills_line.split(",") if s.strip()]

    for i, exp in enumerate(cv["experience"]):
        key = f"experience[{i}].description"
        exp["description"] = edit_text(f"Experience - {exp['role']} @ {exp['organisation']}", exp["description"], key)

    for i, proj in enumerate(cv["projects"]):
        key = f"projects[{i}].description"
        proj["description"] = edit_text(f"Project - {proj['title']}", proj["description"], key)

    return cv


def main():
    parser = argparse.ArgumentParser(description="Generate, edit, and export a tailored CV to PDF.")
    parser.add_argument("--profile", help="student_profiles.jsonl document_id (skips the interactive profile prompt)")
    parser.add_argument("--job", help="jobs.jsonl document_id (skips the interactive job prompt)")
    parser.add_argument("--output", help="Output PDF path (default: 03_Evidence/04_System_Tests/<name>_<job>.pdf)")
    parser.add_argument("--edits-json", help="Path to a JSON file of scripted edits, for non-interactive runs")
    args = parser.parse_args()

    tool = JobRetrievalTool()

    profile = load_profile(args.profile) if args.profile else prompt_choose_profile()
    job = tool.get_job_by_id(args.job) if args.job else prompt_choose_job(tool, profile)

    generator = CVGenerator()
    cv = generator.generate(profile, job)

    if cv["grounding_warnings"]:
        print("\nGrounding warnings (content removed as ungrounded):")
        for w in cv["grounding_warnings"]:
            print(f"  - {w}")

    scripted_edits = json.loads(Path(args.edits_json).read_text(encoding="utf-8")) if args.edits_json else None

    print("\n--- Review and edit your CV ---")
    cv = edit_cv_interactive(cv, scripted_edits=scripted_edits)

    if args.output:
        output_path = Path(args.output)
    else:
        safe_name = profile.contact.name.replace(" ", "_")
        output_path = DEFAULT_OUTPUT_DIR / f"{safe_name}_{job['document_id']}_cv.pdf"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    render_cv_pdf(cv, profile, output_path)
    print(f"\nPDF exported to: {output_path}")


if __name__ == "__main__":
    main()
