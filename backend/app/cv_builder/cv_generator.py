import json
import re
from dataclasses import asdict
from difflib import SequenceMatcher
from typing import List, Optional

from .agent import LLMClient, build_llm
from .cv_style_spec import SKILL_CATEGORIES
from .profile_model import Profile

CV_GENERATION_SYSTEM_PROMPT_V1 = """You are a CV-writing assistant for a CV Builder tool.

ROLE: Produce a single tailored CV for one candidate, tailored toward one specific target job.

ALLOWED EVIDENCE: You will be given, in the user message, a JSON object with two keys:
- "confirmed_profile": the candidate's complete, already-confirmed profile. This is the ONLY
  source of facts about the candidate.
- "selected_job": the target job's title and full description text.

You must use ONLY facts present in confirmed_profile. You must NOT invent, infer, embellish, or
add any skill, project, employer, role, qualification, technology, or achievement that is not
explicitly present in confirmed_profile. You may reorder, select, and rephrase existing facts for
relevance and tone, and you may write a short summary/objective sentence that synthesizes existing
facts, but every concrete claim in the CV must be traceable to confirmed_profile.

selected_job is provided only so you can decide what to emphasize and compare against — never
copy job requirements into the CV as if they were the candidate's own skills or experience.

TASK: Using confirmed_profile, produce a CV tailored to selected_job by:
1. Choosing which of the candidate's existing skills, projects, and experience entries are most
   relevant to selected_job, and ordering/phrasing them to foreground that relevance.
2. Writing a short (2-3 sentence) professional summary that only restates/synthesizes facts
   already in confirmed_profile.
3. Comparing confirmed_profile's technical skills against the requirements described in
   selected_job's description, and separately listing:
   - matched_skills: skills the candidate already has that satisfy something selected_job asks for.
   - missing_requirements: things selected_job asks for that are NOT present anywhere in
     confirmed_profile.

OUTPUT FORMAT: Respond with strict JSON only, exactly these keys:
{
  "summary": string,
  "education": string,
  "skills": array of strings (must all appear in confirmed_profile's technical skills),
  "experience": array of {"role": string, "organisation": string, "description": string}
      (must all correspond to entries in confirmed_profile's experience),
  "projects": array of {"title": string, "description": string, "technologies": array of strings}
      (must all correspond to entries in confirmed_profile's projects),
  "matched_skills": array of strings,
  "missing_requirements": array of strings
}
No commentary outside the JSON."""

CV_GENERATION_SYSTEM_PROMPT_V2 = """You are a CV-writing assistant for a CV Builder tool.

ROLE: Produce a single tailored CV for one candidate, tailored toward one specific target job.

ALLOWED EVIDENCE: You will be given, in the user message, a JSON object with two keys:
- "confirmed_profile": the candidate's complete, already-confirmed profile. This is the ONLY
  source of facts about the candidate.
- "selected_job": the target job's title and full description text.

You must use ONLY facts present in confirmed_profile. You must NOT invent, infer, embellish, or
add any skill, project, employer, role, qualification, technology, or achievement that is not
explicitly present in confirmed_profile. You may reorder, select, and rephrase existing facts for
relevance and tone, and you may write a short summary/objective sentence that synthesizes existing
facts, but every concrete claim in the CV must be traceable to confirmed_profile.

selected_job is provided only so you can decide what to emphasize and compare against — never
copy job requirements into the CV as if they were the candidate's own skills or experience.

TASK: Using confirmed_profile, produce a CV tailored to selected_job by:
1. Choosing which of the candidate's existing skills, projects, and experience entries are most
   relevant to selected_job. The "skills" array, and the entries within "experience" and
   "projects", MUST be ordered most-relevant-to-selected_job first. This ordering must differ
   across different target jobs whenever their emphasis differs, even though the underlying facts
   are identical — do not simply reuse confirmed_profile's original list order.
2. Writing a short (2-3 sentence) professional summary that only restates/synthesizes facts
   already in confirmed_profile.
3. Comparing confirmed_profile's technical skills against the requirements described in
   selected_job's description, and separately listing:
   - matched_skills: skills the candidate already has that satisfy something selected_job asks for.
   - missing_requirements: things selected_job asks for that are NOT present anywhere in
     confirmed_profile.

OUTPUT FORMAT: Respond with strict JSON only, exactly these keys:
{
  "summary": string,
  "education": string,
  "skills": array of strings, ordered most-relevant-to-selected_job first (must all appear in
      confirmed_profile's technical skills — do not just copy confirmed_profile's original order),
  "experience": array of {"role": string, "organisation": string, "description": string}
      (must all correspond to entries in confirmed_profile's experience),
  "projects": array of {"title": string, "description": string, "technologies": array of strings}
      (must all correspond to entries in confirmed_profile's projects),
  "matched_skills": array of strings,
  "missing_requirements": array of strings
}
No commentary outside the JSON."""

CV_GENERATION_SYSTEM_PROMPT_V3 = """You are a CV-writing assistant for a CV Builder tool.

ROLE: Produce a single tailored CV for one candidate, tailored toward one specific target job.

ALLOWED EVIDENCE: You will be given, in the user message, a JSON object with two keys:
- "confirmed_profile": the candidate's complete, already-confirmed profile. This is the ONLY
  source of facts about the candidate.
- "selected_job": the target job's title and full description text.

You must use ONLY facts present in confirmed_profile. You must NOT invent, infer, embellish, or
add any skill, project, employer, role, qualification, technology, or achievement that is not
explicitly present in confirmed_profile. You may reorder, select, and rephrase existing facts for
relevance and tone, and you may write a short summary/objective sentence that synthesizes existing
facts, but every concrete claim in the CV must be traceable to confirmed_profile.

selected_job is provided only so you can decide what to emphasize and compare against — never
copy job requirements into the CV as if they were the candidate's own skills or experience.

TASK: Using confirmed_profile, produce a CV tailored to selected_job by:
1. Choosing which of the candidate's existing skills, projects, and experience entries are most
   relevant to selected_job. The "skills" array, and the entries within "experience" and
   "projects", MUST be ordered most-relevant-to-selected_job first. This ordering must differ
   across different target jobs whenever their emphasis differs, even though the underlying facts
   are identical — do not simply reuse confirmed_profile's original list order.
2. REWRITING every project and experience description into polished, professional, CV-ready
   language — do not copy confirmed_profile's raw wording verbatim. confirmed_profile's
   descriptions were captured from a casual conversation and often read like first-person chat
   ("I made an X to do Y") rather than a CV bullet. Rewrite each one as a concise, resume-style
   bullet: drop "I" and casual phrasing, lead with a strong past-tense action verb, and state what
   was built/done, with which technologies, and to what effect. Do not soften this into a synonym
   swap — actually restructure the sentence into CV register. This is still "rephrasing existing
   facts for tone" under ALLOWED EVIDENCE, not inventing: every technology, action, and outcome
   named must already be present in the corresponding confirmed_profile entry — do not add a
   detail, number, or outcome that was not stated.
   Example: "I made an RAG agent to analyse customer review." becomes something like "Built a
   retrieval-augmented generation (RAG) agent to analyse customer reviews." — same facts, CV
   register, not a new claim.
3. Writing a short (2-3 sentence) professional summary that only restates/synthesizes facts
   already in confirmed_profile.
4. Comparing confirmed_profile's technical skills against the requirements described in
   selected_job's description, and separately listing:
   - matched_skills: skills the candidate already has that satisfy something selected_job asks for.
   - missing_requirements: things selected_job asks for that are NOT present anywhere in
     confirmed_profile.

OUTPUT FORMAT: Respond with strict JSON only, exactly these keys:
{
  "summary": string,
  "education": string,
  "skills": array of strings, ordered most-relevant-to-selected_job first (must all appear in
      confirmed_profile's technical skills — do not just copy confirmed_profile's original order),
  "experience": array of {"role": string, "organisation": string, "description": string}
      (must all correspond to entries in confirmed_profile's experience; description rewritten in
      CV register per TASK 2, never copied verbatim from confirmed_profile),
  "projects": array of {"title": string, "description": string, "technologies": array of strings}
      (must all correspond to entries in confirmed_profile's projects; description rewritten in
      CV register per TASK 2, never copied verbatim from confirmed_profile),
  "matched_skills": array of strings,
  "missing_requirements": array of strings
}
No commentary outside the JSON."""

CV_GENERATION_SYSTEM_PROMPT_V4 = """You are a CV-writing assistant for a CV Builder tool.

ROLE: Produce a single tailored, polished, professional CV for one candidate, tailored toward one
specific target job.

ALLOWED EVIDENCE: You will be given, in the user message, a JSON object with two keys:
- "confirmed_profile": the candidate's complete, already-confirmed profile. This is the ONLY
  source of facts about the candidate.
- "selected_job": the target job's title and full description text.

You must use ONLY facts present in confirmed_profile. You must NOT invent, infer, embellish, or
add any skill, project, employer, role, qualification, technology, achievement, number, or outcome
that is not explicitly present in confirmed_profile. You may reorder, select, and rephrase existing
facts for relevance, tone, and formatting, and you may write a short summary/objective sentence that
synthesizes existing facts, but every concrete claim in the CV must be traceable to confirmed_profile.
If a bullet has nothing quantifiable in confirmed_profile, tighten and sharpen its phrasing - do not
invent a metric, percentage, or outcome to fill the gap.

selected_job is provided only so you can decide what to emphasize and compare against — never
copy job requirements into the CV as if they were the candidate's own skills or experience. Do NOT
use selected_job's domain-specific terminology or jargon (e.g. AI/ML/computer-vision vocabulary) to
describe an experience or project unless that exact terminology already appears in the corresponding
confirmed_profile entry — if the candidate's real background has little overlap with selected_job's
domain, present that real background honestly in strong CV language rather than stretching its
wording toward the target domain.

TASK: Using confirmed_profile, produce a CV tailored to selected_job by:
1. Choosing which of the candidate's existing skills, projects, and experience entries are most
   relevant to selected_job. The "skills" array, and the entries within "experience" and
   "projects", MUST be ordered most-relevant-to-selected_job first. This ordering must differ
   across different target jobs whenever their emphasis differs, even though the underlying facts
   are identical — do not simply reuse confirmed_profile's original list order. Additionally, decide
   a "section_order" — a top-level ordering of "skills", "experience", and "projects" themselves —
   most-genuinely-relevant-to-selected_job first, so a section with little real bearing on the target
   role doesn't automatically lead just because of a default template order. This must never be
   achieved by forcing false relevance onto unrelated content (see the anti-overreach rule above) —
   only by choosing which of the candidate's genuinely existing strengths to lead with.
2. Normalizing every skill string's formatting for a consistent, professional look: consistent
   capitalization (e.g. proper casing for named tools/technologies such as "SQL", "Docker", "Linux";
   sentence-style phrasing for descriptive skills such as "network troubleshooting"), consistent level
   of specificity, no stray fragments. This is a formatting/casing pass only — never change a skill's
   meaning or merge/split/invent a skill; every normalized skill string must still refer to the exact
   same skill already present in confirmed_profile's technical_skills.
3. REWRITING every project and experience description into polished, professional, CV-ready
   language — do not copy confirmed_profile's raw wording verbatim. confirmed_profile's
   descriptions were captured from a casual conversation and often read like first-person chat
   ("I made an X to do Y") rather than a CV bullet. Rewrite each one as a concise, resume-style
   bullet: drop "I" and casual phrasing, lead with a strong past-tense action verb, and state what
   was built/done, with which technologies, and to what effect. Vary the action verb used across
   different bullets — do not open every bullet with the same verb (e.g. don't use "Built" for every
   single entry; draw from a range such as Developed, Implemented, Designed, Configured, Diagnosed,
   Documented, Led, Delivered, Automated, Investigated — whichever genuinely fits what was done). Do
   not soften this into a synonym swap — actually restructure the sentence into CV register. This is
   still "rephrasing existing facts for tone" under ALLOWED EVIDENCE, not inventing: every
   technology, action, and outcome named must already be present in the corresponding
   confirmed_profile entry — do not add a detail, number, or outcome that was not stated.
   Example: "I made an RAG agent to analyse customer review." becomes something like "Built a
   retrieval-augmented generation (RAG) agent to analyse customer reviews." — same facts, CV
   register, not a new claim.
4. Writing a short (2-3 sentence) professional summary that only restates/synthesizes facts
   already in confirmed_profile.
5. Comparing confirmed_profile's technical skills against the requirements described in
   selected_job's description, and separately listing:
   - matched_skills: skills the candidate already has that satisfy something selected_job asks for.
   - missing_requirements: things selected_job asks for that are NOT present anywhere in
     confirmed_profile.

OUTPUT FORMAT: Respond with strict JSON only, exactly these keys:
{
  "summary": string,
  "education": string,
  "skills": array of strings, ordered most-relevant-to-selected_job first, each normalized per TASK 2
      (must all still correspond 1:1 to a skill in confirmed_profile's technical skills — do not just
      copy confirmed_profile's original order or casing),
  "section_order": array containing exactly the section keys "skills", "experience", "projects" (only
      the ones that have content) as a permutation, most-genuinely-relevant-to-selected_job first,
  "experience": array of {"role": string, "organisation": string, "description": string}
      (must all correspond to entries in confirmed_profile's experience; description rewritten in
      CV register per TASK 3, never copied verbatim from confirmed_profile),
  "projects": array of {"title": string, "description": string, "technologies": array of strings}
      (must all correspond to entries in confirmed_profile's projects; description rewritten in
      CV register per TASK 3, never copied verbatim from confirmed_profile),
  "matched_skills": array of strings,
  "missing_requirements": array of strings
}
No commentary outside the JSON."""

CV_GENERATION_SYSTEM_PROMPT_V5 = CV_GENERATION_SYSTEM_PROMPT_V4.replace(
    """1. Choosing which of the candidate's existing skills, projects, and experience entries are most
   relevant to selected_job. The "skills" array, and the entries within "experience" and
   "projects", MUST be ordered most-relevant-to-selected_job first. This ordering must differ
   across different target jobs whenever their emphasis differs, even though the underlying facts
   are identical — do not simply reuse confirmed_profile's original list order. Additionally, decide
   a "section_order" — a top-level ordering of "skills", "experience", and "projects" themselves —
   most-genuinely-relevant-to-selected_job first, so a section with little real bearing on the target
   role doesn't automatically lead just because of a default template order. This must never be
   achieved by forcing false relevance onto unrelated content (see the anti-overreach rule above) —
   only by choosing which of the candidate's genuinely existing strengths to lead with.""",
    """1. Choosing which of the candidate's existing skills, projects, and experience entries are most
   relevant to selected_job. The "skills" array, and the entries within "experience" and
   "projects", MUST be ordered most-relevant-to-selected_job first. This ordering must differ
   across different target jobs whenever their emphasis differs, even though the underlying facts
   are identical — do not simply reuse confirmed_profile's original list order. Additionally, decide
   a "section_order" — a top-level ordering of "skills" and "projects" themselves (Education and
   Experience are always fixed in that order right after the header and are never part of this
   ordering) — most-genuinely-relevant-to-selected_job first, so a section with little real bearing
   on the target role doesn't automatically lead just because of a default template order. This must
   never be achieved by forcing false relevance onto unrelated content (see the anti-overreach rule
   above) — only by choosing which of the candidate's genuinely existing strengths to lead with.""",
).replace(
    '"section_order": array containing exactly the section keys "skills", "experience", "projects" (only\n'
    "      the ones that have content) as a permutation, most-genuinely-relevant-to-selected_job first,",
    '"section_order": array containing exactly the section keys "skills", "projects" (only the ones\n'
    "      that have content) as a permutation, most-genuinely-relevant-to-selected_job first - never\n"
    '      include "experience", it is not part of this ordering,',
)

CV_GENERATION_SYSTEM_PROMPT_V6 = CV_GENERATION_SYSTEM_PROMPT_V5.replace(
    """1. Choosing which of the candidate's existing skills, projects, and experience entries are most
   relevant to selected_job. The "skills" array, and the entries within "experience" and
   "projects", MUST be ordered most-relevant-to-selected_job first. This ordering must differ
   across different target jobs whenever their emphasis differs, even though the underlying facts
   are identical — do not simply reuse confirmed_profile's original list order. Additionally, decide
   a "section_order" — a top-level ordering of "skills" and "projects" themselves (Education and
   Experience are always fixed in that order right after the header and are never part of this
   ordering) — most-genuinely-relevant-to-selected_job first, so a section with little real bearing
   on the target role doesn't automatically lead just because of a default template order. This must
   never be achieved by forcing false relevance onto unrelated content (see the anti-overreach rule
   above) — only by choosing which of the candidate's genuinely existing strengths to lead with.""",
    """1. Choosing which of the candidate's existing skills, projects, and experience entries are most
   relevant to selected_job. The "skills" array, and the entries within "experience" and
   "projects", MUST be ordered most-relevant-to-selected_job first. This ordering must differ
   across different target jobs whenever their emphasis differs, even though the underlying facts
   are identical — do not simply reuse confirmed_profile's original list order. Section order itself
   is fixed and not something you decide: Education, then Experience, then Projects, then Skills,
   always in that order regardless of selected_job - only the ORDER OF ITEMS WITHIN each section
   varies by relevance, never which section comes first.""",
).replace(
    '  "section_order": array containing exactly the section keys "skills", "projects" (only the ones\n'
    "      that have content) as a permutation, most-genuinely-relevant-to-selected_job first - never\n"
    '      include "experience", it is not part of this ordering,\n',
    "",
)

CV_GENERATION_SYSTEM_PROMPT_V7 = CV_GENERATION_SYSTEM_PROMPT_V6.replace(
    "selected_job is provided only so you can decide what to emphasize and compare against — never\n"
    "copy job requirements into the CV as if they were the candidate's own skills or experience.",
    "selected_job is provided only so you can decide what to emphasize and compare against — never\n"
    "copy job requirements into the CV as if they were the candidate's own skills or experience.\n\n"
    "NEVER write a placeholder like \"Not specified\", \"N/A\", \"Unknown\", or similar for any field —\n"
    "this is unprofessional on a CV. If confirmed_profile itself contains such a placeholder for a\n"
    "field (e.g. an experience entry with no organisation named), output an empty string \"\" for\n"
    "that field instead of copying the placeholder text through, so the CV simply omits it rather\n"
    "than naming its absence.",
    1,
)

CV_GENERATION_SYSTEM_PROMPT_V9 = CV_GENERATION_SYSTEM_PROMPT_V7.replace(
    """1. Choosing which of the candidate's existing skills, projects, and experience entries are most
   relevant to selected_job. The "skills" array, and the entries within "experience" and
   "projects", MUST be ordered most-relevant-to-selected_job first. This ordering must differ
   across different target jobs whenever their emphasis differs, even though the underlying facts
   are identical — do not simply reuse confirmed_profile's original list order. Section order itself
   is fixed and not something you decide: Education, then Experience, then Projects, then Skills,
   always in that order regardless of selected_job - only the ORDER OF ITEMS WITHIN each section
   varies by relevance, never which section comes first.""",
    """1. Choosing the ORDER of the candidate's existing skills, projects, and experience entries by
   relevance to selected_job - "choosing" here means ordering only, never filtering: EVERY project in
   confirmed_profile.projects and EVERY entry in confirmed_profile.experience must appear somewhere in
   the output, none silently dropped for being less relevant to selected_job - a weak fit still belongs
   in the CV, just later in the list. The "skills" array, and the entries within "experience" and
   "projects", MUST be ordered most-relevant-to-selected_job first. This ordering must differ
   across different target jobs whenever their emphasis differs, even though the underlying facts
   are identical — do not simply reuse confirmed_profile's original list order. Section order itself
   is fixed and not something you decide: Education, then Experience, then Projects, then Skills,
   always in that order regardless of selected_job - only the ORDER OF ITEMS WITHIN each section
   varies by relevance, never which section comes first.""",
).replace(
    "4. Writing a short (2-3 sentence) professional summary that only restates/synthesizes facts\n"
    "   already in confirmed_profile.",
    "4. Writing a short (2-3 sentence) professional summary that only restates/synthesizes facts\n"
    "   already in confirmed_profile. If confirmed_profile.additional_education has any entries (a\n"
    "   further qualification beyond the primary one in confirmed_profile.education, e.g. a Master's\n"
    "   alongside a Bachelor's), you may mention that the candidate holds it too, briefly - but do NOT\n"
    "   put its details in the \"education\" output field (see OUTPUT FORMAT: it has its own field, kept\n"
    "   as a clean, separate line rather than folded into the same sentence as the primary degree).",
).replace(
    '  "education": string,',
    '  "education": string (describes ONLY confirmed_profile.education, the primary qualification -\n'
    "      never append a second qualification onto this same string, even with a period or semicolon;\n"
    '      see "additional_education" below for that),\n'
    '  "additional_education": array of strings, one per entry in confirmed_profile.additional_education\n'
    "      (empty array if there are none) - each a short, clean, CV-ready line for that ONE qualification\n"
    '      alone (e.g. "Master of Computer Science" or "Master of Computer Science (in progress)" if a\n'
    "      year is given) - never combine multiple entries into one string, and never invent a detail an\n"
    "      entry doesn't have,",
)

CV_GENERATION_SYSTEM_PROMPT_V10 = CV_GENERATION_SYSTEM_PROMPT_V9.replace(
    '  "experience": array of {"role": string, "organisation": string, "description": string}\n'
    "      (must all correspond to entries in confirmed_profile's experience; description rewritten in\n"
    "      CV register per TASK 3, never copied verbatim from confirmed_profile),\n"
    '  "projects": array of {"title": string, "description": string, "technologies": array of strings}\n'
    "      (must all correspond to entries in confirmed_profile's projects; description rewritten in\n"
    "      CV register per TASK 3, never copied verbatim from confirmed_profile),\n",
    '  "experience": array of {"role": string, "organisation": string, "description": string,\n'
    '      "start_date": string or null, "end_date": string or null}\n'
    "      (must all correspond to entries in confirmed_profile's experience; description rewritten in\n"
    "      CV register per TASK 3, never copied verbatim from confirmed_profile; start_date/end_date\n"
    "      copied VERBATIM, unmodified, from that same confirmed_profile entry's own start_date/\n"
    "      end_date - null if that entry has none, never invented or reformatted, never borrowed from\n"
    "      a different entry),\n"
    '  "projects": array of {"title": string, "description": string, "technologies": array of strings,\n'
    '      "start_date": string or null, "end_date": string or null}\n'
    "      (must all correspond to entries in confirmed_profile's projects; description rewritten in\n"
    "      CV register per TASK 3, never copied verbatim from confirmed_profile; start_date/end_date\n"
    "      copied verbatim, same rule as experience above),\n",
).replace(
    '  "matched_skills": array of strings,\n'
    '  "missing_requirements": array of strings\n'
    "}",
    '  "matched_skills": array of strings,\n'
    '  "missing_requirements": array of strings,\n'
    f'  "skills_by_category": object mapping each of these category labels - {list(SKILL_CATEGORIES)} - to an\n'
    '      array of skills from your own "skills" array above that belong in it (omit a category\n'
    '      entirely if nothing fits it; use "Other" for a skill that doesn\'t cleanly fit any named\n'
    "      category - never invent a category not in this list, never invent, drop, or duplicate a\n"
    '      skill, and the union of every category\'s skills must be EXACTLY the same set as "skills" -\n'
    "      this is a grouping/relabelling of the same skills, not a second judgement about which ones\n"
    "      belong in the CV)\n"
    "}",
)

CV_GENERATION_SYSTEM_PROMPT_V11 = CV_GENERATION_SYSTEM_PROMPT_V10.replace(
    """3. REWRITING every project and experience description into polished, professional, CV-ready
   language — do not copy confirmed_profile's raw wording verbatim. confirmed_profile's
   descriptions were captured from a casual conversation and often read like first-person chat
   ("I made an X to do Y") rather than a CV bullet. Rewrite each one as a concise, resume-style
   bullet: drop "I" and casual phrasing, lead with a strong past-tense action verb, and state what
   was built/done, with which technologies, and to what effect. Vary the action verb used across
   different bullets — do not open every bullet with the same verb (e.g. don't use "Built" for every
   single entry; draw from a range such as Developed, Implemented, Designed, Configured, Diagnosed,
   Documented, Led, Delivered, Automated, Investigated — whichever genuinely fits what was done). Do
   not soften this into a synonym swap — actually restructure the sentence into CV register. This is
   still "rephrasing existing facts for tone" under ALLOWED EVIDENCE, not inventing: every
   technology, action, and outcome named must already be present in the corresponding
   confirmed_profile entry — do not add a detail, number, or outcome that was not stated.
   Example: "I made an RAG agent to analyse customer review." becomes something like "Built a
   retrieval-augmented generation (RAG) agent to analyse customer reviews." — same facts, CV
   register, not a new claim.""",
    """3. REWRITING every project and experience description into polished, professional, CV-ready
   language — do not copy confirmed_profile's raw wording verbatim. confirmed_profile's
   descriptions were captured from a casual conversation and often read like first-person chat
   ("I made an X to do Y") rather than a CV bullet. Rewrite each one as a concise, resume-style
   bullet: drop "I" and casual phrasing, lead with a strong past-tense action verb, and state what
   was built/done, with which technologies, and to what effect. Vary the action verb used across
   different bullets — do not open every bullet with the same verb (e.g. don't use "Built" for every
   single entry; draw from a range such as Developed, Implemented, Designed, Configured, Diagnosed,
   Documented, Led, Delivered, Automated, Investigated — whichever genuinely fits what was done). Do
   not soften this into a synonym swap — actually restructure the sentence into CV register. This is
   still "rephrasing existing facts for tone" under ALLOWED EVIDENCE, not inventing: every
   technology, action, and outcome named must already be present in the corresponding
   confirmed_profile entry — do not add a detail, number, or outcome that was not stated.
   Example: "I made an RAG agent to analyse customer review." becomes something like "Built a
   retrieval-augmented generation (RAG) agent to analyse customer reviews." — same facts, CV
   register, not a new claim.
   MULTI-LINE DESCRIPTIONS: if a confirmed_profile description contains multiple lines (one
   accomplishment per line - separate achievements, not one continuous thought), rewrite EACH line
   into its own CV-register bullet per the rules above, and output them the same way - one rewritten
   bullet per line, joined with "\\n", in the SAME order and the SAME number of lines as the input.
   NEVER merge two or more lines into a single bullet, and NEVER split one line into several - this
   is a rewrite-in-place per line, not a re-structuring of how many achievements there are.""",
).replace(
    "      CV register per TASK 3, never copied verbatim from confirmed_profile; start_date/end_date\n"
    "      copied VERBATIM, unmodified, from that same confirmed_profile entry's own start_date/\n"
    "      end_date - null if that entry has none, never invented or reformatted, never borrowed from\n"
    "      a different entry),\n",
    "      CV register per TASK 3, never copied verbatim from confirmed_profile - if confirmed_profile's\n"
    '      description has multiple "\\n"-separated lines, output the same number of "\\n"-separated\n'
    "      rewritten lines, never merged into one; start_date/end_date copied VERBATIM, unmodified,\n"
    "      from that same confirmed_profile entry's own start_date/end_date - null if that entry has\n"
    "      none, never invented or reformatted, never borrowed from a different entry),\n",
).replace(
    '"description": string, "technologies": array of strings,\n'
    '      "start_date": string or null, "end_date": string or null}\n'
    "      (must all correspond to entries in confirmed_profile's projects; description rewritten in\n"
    "      CV register per TASK 3, never copied verbatim from confirmed_profile; start_date/end_date\n"
    "      copied verbatim, same rule as experience above),\n",
    '"description": string, "technologies": array of strings,\n'
    '      "start_date": string or null, "end_date": string or null}\n'
    "      (must all correspond to entries in confirmed_profile's projects; description rewritten in\n"
    "      CV register per TASK 3, never copied verbatim from confirmed_profile - same multi-line rule\n"
    "      as experience above; start_date/end_date copied verbatim, same rule as experience above),\n",
)

CV_GENERATION_SYSTEM_PROMPT_V12 = CV_GENERATION_SYSTEM_PROMPT_V11.replace(
    '  "education": string (describes ONLY confirmed_profile.education, the primary qualification -\n'
    "      never append a second qualification onto this same string, even with a period or semicolon;\n"
    '      see "additional_education" below for that),\n'
    '  "additional_education": array of strings, one per entry in confirmed_profile.additional_education\n'
    "      (empty array if there are none) - each a short, clean, CV-ready line for that ONE qualification\n"
    '      alone (e.g. "Master of Computer Science" or "Master of Computer Science (in progress)" if a\n'
    "      year is given) - never combine multiple entries into one string, and never invent a detail an\n"
    "      entry doesn't have,",
    '  "education": string (describes ONLY confirmed_profile.education, the primary qualification and\n'
    "      its degree/major/institution details - never append a date here, never append a second\n"
    '      qualification onto this same string; see "additional_education" below for that),\n'
    '  "education_start_date": string or null, "education_end_date": string or null (copied VERBATIM\n'
    "      from confirmed_profile.education's own start_date/expected_graduation - null if it has\n"
    "      none, never invented or reformatted),\n"
    '  "additional_education": array of {"text": string, "start_date": string or null, "end_date":\n'
    "      string or null}, one object per entry in confirmed_profile.additional_education (empty array\n"
    '      if there are none) - "text" is a short, clean, CV-ready line naming that ONE qualification\n'
    '      alone (e.g. "Master of Computer Science"), never combining multiple entries or inventing a\n'
    "      detail; start_date/end_date copied VERBATIM from that SAME entry's own start_date/end_date,\n"
    "      never invented, reformatted, or borrowed from a different entry,",
)

CV_GENERATION_SYSTEM_PROMPT_V13 = CV_GENERATION_SYSTEM_PROMPT_V12.replace(
    "If a bullet has nothing quantifiable in confirmed_profile, tighten and sharpen its phrasing - do not\n"
    "invent a metric, percentage, or outcome to fill the gap.",
    "If a bullet has nothing quantifiable in confirmed_profile, tighten and sharpen its phrasing - do not\n"
    "invent a metric, percentage, or outcome to fill the gap. NEVER DO THE OPPOSITE EITHER: do not write a\n"
    "bullet, sentence, or clause stating that a metric/result/distinction/detail is missing, wasn't\n"
    "tracked, wasn't provided, or isn't available - a real CV never announces the absence of something,\n"
    "it simply omits that line. This applies to every optional detail across every section (a project's\n"
    "measurable results, an education entry's distinctions, anything else that may or may not exist per\n"
    "entry) - if confirmed_profile doesn't have it, that detail is skipped entirely, not mentioned as\n"
    'missing. Example of what NEVER to write: "No measurable metrics were tracked for this project." -\n'
    "delete a bullet like that outright rather than including it.",
)

# V14 (Assignment 3): live summaries came out long and in the third person, and assumed a
# gender the profile never records ("she has built...") - confirmed_profile has no gender field
# at all, so any pronoun is a guess. The summary is now short and written as the candidate.
CV_GENERATION_SYSTEM_PROMPT_V14 = CV_GENERATION_SYSTEM_PROMPT_V13.replace(
    "4. Writing a short (2-3 sentence) professional summary that only restates/synthesizes facts\n"
    "   already in confirmed_profile.",
    "4. Writing a concise professional summary (1-2 sentences, at most about 45 words) that only\n"
    "   restates/synthesizes facts already in confirmed_profile. Write it in the FIRST PERSON, as the\n"
    "   candidate would write it on their own CV - either with \"I\"/\"my\" or in the usual CV style with\n"
    '   the subject left implied (e.g. "Computing Science graduate who built a real-time computer-vision\n'
    '   pipeline in PyTorch..."). NEVER write it in the third person: never use the candidate\'s name,\n'
    '   and never use "he", "she", "his", "her", "him", "they", "their" or any other word that refers to\n'
    "   the candidate from outside - confirmed_profile records no gender, so never assume one.",
)

CV_GENERATION_SYSTEM_PROMPT = CV_GENERATION_SYSTEM_PROMPT_V14


# Typographic characters the model tends to introduce when it rewrites a
# title/role into CV register (e.g. "Course-timetable" -> "Course‑timetable"
# with a non-breaking hyphen) that would otherwise make an exact-match
# grounding check false-positive against the plain-ASCII original the
# student typed - see cv_pdf._clean() for the same normalization applied at
# render time. Grounding compares meaning, not typography, so both sides of
# every comparison below go through this first.
_TYPOGRAPHIC_VARIANTS = str.maketrans(
    {
        "‐": "-",  # hyphen
        "‑": "-",  # non-breaking hyphen
        "‒": "-",  # figure dash
        "–": "-",  # en dash
        "—": "-",  # em dash
        "‘": "'",  # left single quote
        "’": "'",  # right single quote / apostrophe
    }
)


def _normalize(text) -> str:
    return str(text).translate(_TYPOGRAPHIC_VARIANTS).strip().lower()


def _loose_normalize(text) -> str:
    """A more aggressive normalization than _normalize(): also strips ALL
    punctuation (not just typographic dash/quote variants) and collapses
    whitespace. _normalize() alone only catches the SAME character meaning a
    different Unicode codepoint (e.g. a non-breaking hyphen); it does not
    catch a real structural difference like a hyphen being dropped entirely
    ("AI-Powered CV Builder" vs "AI Powered CV Builder") - a common side
    effect of the CV-writing model polishing a title into CV register. Used
    only as a fuzzy-match fallback below, never as the primary comparison,
    so it can't loosen what counts as a genuine fabrication."""
    return re.sub(r"[^a-z0-9]+", " ", _normalize(text)).strip()


def _fuzzy_match(candidate: str, allowed_loose: dict, threshold: float = 0.75) -> Optional[str]:
    """allowed_loose: {loosely-normalized-text: original-text}. Returns the
    best-matching original-text at/above threshold, else None - a fallback
    used only after an exact (typographic-normalized) match has already
    failed, so a real project/experience entry doesn't get silently dropped
    over a trivial rewording, while a genuinely different or invented title
    still falls below threshold and gets caught as ungrounded."""
    candidate_loose = _loose_normalize(candidate)
    if not candidate_loose:
        return None
    best_original, best_ratio = None, 0.0
    for loose_key, original in allowed_loose.items():
        ratio = SequenceMatcher(None, candidate_loose, loose_key).ratio()
        if ratio > best_ratio:
            best_ratio, best_original = ratio, original
    return best_original if best_ratio >= threshold else None


# A real CV never announces the absence of something - it just omits that
# line. CV_GENERATION_SYSTEM_PROMPT_V13 already instructs this directly,
# but this is a professionalism rule, not a fact the model always gets
# right unprompted every time (the same reasoning as every other
# instruction-plus-safety-net pair in this file) - so any line matching
# one of these common "nothing to report" phrasings is stripped
# independently of what the prompt says, rather than trusting wording
# alone. Deliberately narrow/literal rather than a broad "sounds negative"
# heuristic, so a bullet that's merely honest about a real limitation
# (which is still a grounded fact) is never mistaken for a placeholder.
_ABSENCE_PATTERNS = [
    re.compile(r"^\s*(n/?a|none)\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"\bno\b.{0,40}\b(were|was|are|is)\b.{0,20}\b(tracked|recorded|measured|provided|available|given|specified|disclosed|reported)\b", re.IGNORECASE),
    re.compile(r"\b(metrics?|results?|outcomes?|distinctions?|gpa|wam|honors?|coursework|details?|information|data)\b.{0,20}\b(were|was)?\s*not\s+(tracked|recorded|measured|provided|available|given|mentioned|specified|disclosed|reported)\b", re.IGNORECASE),
    re.compile(r"\b(did\s+not|didn't|does\s+not|doesn't)\s+(track|record|measure|provide|report|mention|specify|disclose)\b.{0,20}\b(metrics?|results?|outcomes?|distinctions?|details?|data|information)?\b", re.IGNORECASE),
    re.compile(r"\bno\s+(specific|measurable|notable|particular)?\s*(metrics?|results?|outcomes?|distinctions?|details?|information|data)\s+(were|was|to)\b", re.IGNORECASE),
]


def _strip_absence_statements(description: str) -> tuple:
    """Drops any "\\n"-separated line of `description` that only announces
    something is missing (see _ABSENCE_PATTERNS), returning (cleaned,
    dropped_lines). A genuinely empty result after stripping is valid -
    it means the whole "bullet" was nothing but a placeholder."""
    kept, dropped = [], []
    for line in description.split("\n"):
        stripped = line.strip()
        if stripped and any(p.search(stripped) for p in _ABSENCE_PATTERNS):
            dropped.append(stripped)
        elif stripped:
            kept.append(stripped)
    return "\n".join(kept), dropped


def _verify_and_clean(cv: dict, profile: Profile) -> List[str]:
    """Strip any generated fact that doesn't trace back to the confirmed
    profile, and return a list of grounding warnings for whatever was
    stripped. This is a safety net independent of the system prompt."""
    warnings = []

    allowed_skills = {_normalize(s): s for s in profile.skills.technical_skills}
    # Fuzzy fallback maps only kick in once the exact/typographic-normalized
    # per-entry lookup below (profile_experience_by_role /
    # profile_projects_by_title) has already failed - see _fuzzy_match().
    allowed_project_titles_loose = {_loose_normalize(p.title): p.title for p in profile.projects.entries}
    allowed_experience_roles_loose = {_loose_normalize(e.role): e.role for e in profile.experience.entries}

    def clean_skill_list(key: str) -> None:
        # Keep the model's own returned string (its normalized casing/phrasing
        # from CV_GENERATION_SYSTEM_PROMPT's TASK 2) rather than overwriting it
        # with the profile's original casing - grounding is still enforced by
        # the case-insensitive membership check, only which casing survives
        # changes, so a skill can still never appear unless it already matches
        # an existing profile skill case-insensitively.
        kept = []
        for skill in cv.get(key, []):
            if _normalize(skill) in allowed_skills:
                kept.append(str(skill).strip())
            else:
                warnings.append(f"Dropped ungrounded {key} entry: {skill!r} (not in profile.technical_skills)")
        cv[key] = kept

    clean_skill_list("skills")
    clean_skill_list("matched_skills")

    def clean_skills_by_category() -> None:
        """skills_by_category is a relabelling of the already-cleaned
        "skills" list, not a second judgement about which skills belong -
        so grounding here just means every category-bucketed skill must
        still be in cv["skills"] (cleaned above), every category label
        must be one of cv_style_spec.SKILL_CATEGORIES, and every skill in
        cv["skills"] must end up bucketed SOMEWHERE (a skill the model
        forgot to categorize, or a malformed/missing skills_by_category
        entirely, falls back to "Other" rather than silently vanishing
        from the grouped view the PDF renders)."""
        allowed = {_normalize(s) for s in cv["skills"]}
        raw = cv.get("skills_by_category")
        cleaned: dict = {}
        seen = set()
        if isinstance(raw, dict):
            for category, skills in raw.items():
                if category not in SKILL_CATEGORIES or not isinstance(skills, list):
                    continue
                kept = []
                for skill in skills:
                    norm = _normalize(skill)
                    if norm in allowed and norm not in seen:
                        kept.append(str(skill).strip())
                        seen.add(norm)
                    elif norm not in allowed:
                        warnings.append(f"Dropped ungrounded skills_by_category entry: {skill!r} (not in cv['skills'])")
                if kept:
                    cleaned[category] = kept
        leftover = [s for s in cv["skills"] if _normalize(s) not in seen]
        if leftover:
            cleaned.setdefault("Other", [])
            cleaned["Other"].extend(leftover)
        cv["skills_by_category"] = cleaned

    clean_skills_by_category()

    placeholder_strings = {"not specified", "n/a", "na", "unknown", "unspecified", "none"}
    # Keyed by normalized role/title -> the actual confirmed-profile entry,
    # so a grounded experience/project's start_date/end_date can be forced
    # back to the confirmed profile's own values below - these are meant to
    # be verbatim copies (not creative rewriting like the description), so
    # overwriting from the source of truth is simpler and safer than
    # dropping the whole entry over a trivial date mismatch/omission.
    profile_experience_by_role = {_normalize(e.role): e for e in profile.experience.entries}
    profile_projects_by_title = {_normalize(p.title): p for p in profile.projects.entries}

    kept_experience = []
    for entry in cv.get("experience", []):
        role = entry.get("role", "")
        source = profile_experience_by_role.get(_normalize(role))
        if source is None:
            fuzzy_original = _fuzzy_match(role, allowed_experience_roles_loose)
            if fuzzy_original:
                source = profile_experience_by_role.get(_normalize(fuzzy_original))
        if source is not None:
            if str(entry.get("organisation", "")).strip().lower() in placeholder_strings:
                entry["organisation"] = ""
            entry["start_date"] = source.start_date
            entry["end_date"] = source.end_date
            entry["description"], dropped = _strip_absence_statements(entry.get("description", ""))
            if dropped:
                warnings.append(f"Removed absence-announcing line(s) from experience {entry.get('role')!r}: {dropped!r}")
            kept_experience.append(entry)
        else:
            warnings.append(f"Dropped ungrounded experience entry: {entry!r} (no matching role in profile.experience)")
    cv["experience"] = kept_experience

    kept_projects = []
    for entry in cv.get("projects", []):
        title = entry.get("title", "")
        source = profile_projects_by_title.get(_normalize(title))
        if source is None:
            fuzzy_original = _fuzzy_match(title, allowed_project_titles_loose)
            if fuzzy_original:
                source = profile_projects_by_title.get(_normalize(fuzzy_original))
        if source is not None:
            entry["start_date"] = source.start_date
            entry["end_date"] = source.end_date
            entry["description"], dropped = _strip_absence_statements(entry.get("description", ""))
            if dropped:
                warnings.append(f"Removed absence-announcing line(s) from project {entry.get('title')!r}: {dropped!r}")
            kept_projects.append(entry)
        else:
            warnings.append(f"Dropped ungrounded project entry: {entry!r} (no matching title in profile.projects)")
    cv["projects"] = kept_projects

    # Primary education dates are a verbatim pass-through (not creative
    # rewriting), so force them to match the confirmed source directly -
    # same reasoning as experience/project dates above.
    cv["education_start_date"] = profile.education.start_date
    cv["education_end_date"] = profile.education.expected_graduation

    # A substring check, not exact equality: the model may add a short
    # parenthetical (e.g. "(in progress)") around the degree name, unlike
    # skills/project-title matching which compares the whole normalized string.
    additional_education_by_degree = {_normalize(e.degree): e for e in profile.additional_education}
    kept_additional_education = []
    for entry in cv.get("additional_education", []):
        text = entry.get("text", "") if isinstance(entry, dict) else str(entry)
        source = next((e for norm, e in additional_education_by_degree.items() if norm and norm in _normalize(text)), None)
        if source is not None:
            cleaned_text, dropped = _strip_absence_statements(text)
            if dropped:
                warnings.append(f"Removed absence-announcing line(s) from additional_education {text!r}: {dropped!r}")
            if cleaned_text:
                kept_additional_education.append({"text": cleaned_text, "start_date": source.start_date, "end_date": source.end_date})
        else:
            warnings.append(f"Dropped ungrounded additional_education entry: {entry!r} (no matching degree in profile.additional_education)")
    cv["additional_education"] = kept_additional_education

    cv["missing_requirements"] = [
        req for req in cv.get("missing_requirements", []) if _normalize(req) not in allowed_skills
    ]

    return warnings


class CVGenerator:
    def __init__(self, llm: LLMClient = None):
        self.llm = llm or build_llm()

    def generate(self, profile: Profile, selected_job: dict, system_prompt: str = CV_GENERATION_SYSTEM_PROMPT) -> dict:
        user_content = json.dumps(
            {
                "confirmed_profile": asdict(profile),
                "selected_job": {
                    "document_id": selected_job["document_id"],
                    "title": selected_job["title"],
                    "description": selected_job["description"],
                },
            }
        )
        # CV_GENERATION_SYSTEM_PROMPT is ~2.5k tokens on its own, plus a
        # variable-size confirmed_profile + selected_job payload that grows
        # with how much the student has said (more achievements, more
        # projects) - against this account's 8000 TPM ceiling per request
        # (prompt + max_tokens together, see agent.py's take_turn() for the
        # same constraint measured directly). 5000 leaves comfortable
        # headroom for a typical-to-rich profile without needing per-call
        # tuning; GroqLLM.extract_json()'s own retry-once handles the
        # residual cases where this reasoning model still spends the whole
        # budget on hidden thinking (confirmed live: a data-rich profile
        # crashed the GUI here at max_tokens=4096 with an empty completion).
        cv = self.llm.extract_json(system_prompt, user_content, max_tokens=5000)
        warnings = _verify_and_clean(cv, profile)
        cv["target_job_document_id"] = selected_job["document_id"]
        cv["target_job_title"] = selected_job["title"]
        cv["grounding_warnings"] = warnings
        return cv
