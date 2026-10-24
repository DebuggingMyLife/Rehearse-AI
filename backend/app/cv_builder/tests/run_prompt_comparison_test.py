import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cv_generator import CV_GENERATION_SYSTEM_PROMPT_V1, CV_GENERATION_SYSTEM_PROMPT_V2, CVGenerator
from job_retrieval_tool import JobRetrievalTool
from profile_model import Profile

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STUDENT_PROFILES_PATH = PROJECT_ROOT / "01_System" / "source_code" / "data" / "student_profiles.jsonl"

TEST_DOCUMENT_ID = "student_profile_02"


def load_profile(document_id: str) -> Profile:
    with open(STUDENT_PROFILES_PATH, encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if record["document_id"] == document_id:
                return Profile.from_record(record)
    raise KeyError(document_id)


def main():
    profile = load_profile(TEST_DOCUMENT_ID)
    tool = JobRetrievalTool()
    top_matches = tool.search(profile, top_k=3)
    job_a = tool.get_job_by_id(top_matches[0]["document_id"])
    job_b = tool.get_job_by_id(top_matches[1]["document_id"])

    generator = CVGenerator()

    v1_a = generator.generate(profile, job_a, system_prompt=CV_GENERATION_SYSTEM_PROMPT_V1)
    v1_b = generator.generate(profile, job_b, system_prompt=CV_GENERATION_SYSTEM_PROMPT_V1)
    v2_a = generator.generate(profile, job_a, system_prompt=CV_GENERATION_SYSTEM_PROMPT_V2)
    v2_b = generator.generate(profile, job_b, system_prompt=CV_GENERATION_SYSTEM_PROMPT_V2)

    result = {
        "profile": profile.contact.name,
        "job_a": {"document_id": job_a["document_id"], "title": job_a["title"]},
        "job_b": {"document_id": job_b["document_id"], "title": job_b["title"]},
        "v1_skills_job_a": v1_a["skills"],
        "v1_skills_job_b": v1_b["skills"],
        "v1_identical_order": v1_a["skills"] == v1_b["skills"],
        "v2_skills_job_a": v2_a["skills"],
        "v2_skills_job_b": v2_b["skills"],
        "v2_identical_order": v2_a["skills"] == v2_b["skills"],
        "v1_grounding_warnings": v1_a["grounding_warnings"] + v1_b["grounding_warnings"],
        "v2_grounding_warnings": v2_a["grounding_warnings"] + v2_b["grounding_warnings"],
    }

    print(json.dumps(result, indent=2))

    out_path = Path(__file__).resolve().parent / "_prompt_comparison_raw.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Raw comparison written to: {out_path}")


if __name__ == "__main__":
    main()
