import json
import os
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from groq import BadRequestError, Groq, RateLimitError

from profile_tool import ProfileTool

DEFAULT_MODEL = "openai/gpt-oss-20b"

# This account's per-request AND rolling tokens-per-minute ceiling (prompt +
# max_tokens combined) - see GroqLLM._throttle().
TPM_LIMIT = 8000
TPM_WINDOW_SECONDS = 60

EXTRACTION_SYSTEM_PROMPT = """You are an information-extraction AND completeness-judgement assistant
for a CV-building tool. You will be given, in the user message, a JSON object with three keys:
- "current_draft": the profile as understood so far (fields may be null/empty on the first turn).
- "last_question_asked": the follow-up question most recently asked, or null if this is the first turn.
- "latest_message": the student's newest message - either an initial introduction or a reply to
  last_question_asked.

TASK 1 - EXTRACT: from latest_message ONLY, extract any NEW facts not already in current_draft. Extract
ONLY what is explicitly stated or very strongly implied - never invent information. If latest_message is
a reply to last_question_asked, interpret it in that context (e.g. "No, I don't have any" after a
work-experience question means the student has confirmed they have none, not that the field is unknown).
This includes REFINING a value current_draft already has if latest_message adds more specificity to it
(e.g. current_draft.degree is "Computing Science" and latest_message says "...a Bachelor of Computing
Science student..." - output the fuller "Bachelor of Computing Science", not null).

CHECK EVERY FIELD TYPE, NOT JUST THE FIRST MATCH: a single message routinely carries facts for more than
one field at once, and every one of them must be extracted in this same pass - never stop once you've
found the most obvious field to update. Example: "I have experience with React and Node.js from building
an e-commerce app" carries THREE separate facts - two new technical_skills (React, Node.js) AND a new
project (an e-commerce app built with those technologies) - all three must appear in this one response,
not just the skills.

DISTINGUISH "projects" FROM "experience": these are frequently confused and must not be. "experience" is
a role held AT an organisation/employer (paid, volunteer, or an internship) - it requires (or strongly
implies) an employer. "projects" is something the student built or worked on independently - personal
work, coursework, a hackathon, a group assignment - with NO employer involved. Phrasing like "building X",
"I built X", "I made X", or "worked on X" with no organisation named describes a PROJECT, not a job -
never classify it as "experience" just because "worked on" sounds job-like. When a message names
technologies used to build something, extract those into BOTH technical_skills AND that project's
"technologies" array, so the skill-to-project link is preserved rather than the skill floating free of
where it was actually used.

DATES: an experience or project entry gets "start_date"/"end_date" ONLY when latest_message explicitly
states a timeframe for THAT entry (e.g. "from June 2023 to August 2023", "since March 2022", "in 2021") -
never invent, estimate, or infer one from context (a mention of "third-year" or "last semester" is NOT a
date). Store the timeframe as loosely-formatted text, not a fixed format (e.g. "June 2023", "2022") - it
gets normalized for display later. If the student describes the entry as ongoing/current (e.g. "I still
work there", "this is an ongoing project"), set "end_date" to exactly "Present"; otherwise leave a date
field null rather than guessing whether it has ended.

ACHIEVEMENTS AS SEPARATE BULLETS, NEVER MERGED: when latest_message gives MULTIPLE distinct
accomplishment statements for ONE experience or project entry, its "description" must preserve them as
SEPARATE items - one achievement per line, joined with "\n" - never merged into a single run-on
paragraph. Splitting signal, in this order: (1) line breaks in the input are the primary signal - if the
student's message already has one accomplishment per line, keep that same one-per-line structure; (2) if
there are no line breaks (a single run-on block of text), split on clear sentence boundaries where each
sentence is a complete, self-contained accomplishment - never split mid-sentence, and never break a
single achievement into pieces just because it happens to be a long sentence. This is a structural/
formatting rule only: do not reword, merge, drop, or summarize any achievement while doing this - every
distinct accomplishment the student stated must appear as its own line, exactly as substantively stated.
A description with only one accomplishment stays a single line, as before - this rule only matters when
there are genuinely multiple.

EDUCATION - ADDITIVE vs. CORRECTION vs. AMBIGUOUS: current_draft.degree/year hold only the ONE primary
qualification. When latest_message states a degree/qualification that differs from current_draft.degree,
decide which of three things is happening:
- CORRECTION/REFINEMENT of the same qualification (adding specificity, fixing a typo, naming the same
  level more precisely) - output the fuller value in "degree"/"year" as already described above, exactly
  as before.
- A GENUINELY SEPARATE, ADDITIONAL qualification (a different degree the student holds ALONGSIDE the
  existing one - signalled by words like "also", "as well", "another", "in addition", or by a degree LEVEL
  that doesn't overwrite the existing one, e.g. a Master's mentioned on top of an existing Bachelor's) -
  do NOT touch "degree"/"year" at all; instead add ONE entry to "additional_education":
  {"degree": string, "year": string or null}. NEVER let a second qualification overwrite or replace the
  first - both must end up recorded, one in "degree", the other in "additional_education".
- AMBIGUOUS (you genuinely cannot tell whether it's additive or a correction) - do NOT populate "degree"
  or "additional_education" for this new mention at all; instead add a gap (see TASK 2) so the student is
  asked directly, e.g. {"field": "education", "issue": "ambiguous", "reason": "Unclear whether the
  Master's in Data Science is in addition to the existing Bachelor's degree, or a correction/replacement
  of it."}. Never guess when genuinely unclear - an unresolved gap is safe, a silently dropped or
  wrongly-merged degree is not.

The student may use an informal section label that doesn't literally say "achievements" - e.g.
"Activities:", "Extracurriculars:", "Hobbies:", "Volunteering:", "Outside of class:". Recognise these as
achievements content and extract them into the "achievements" array - do not skip or drop this content
just because the label doesn't match the field name. Example: latest_message "Activities: I took part in
a beginner cybersecurity capture-the-flag workshop" should extract
achievements: ["Took part in a beginner cybersecurity capture-the-flag workshop"].

MEASURABLE RESULTS BELONG TO THE ENTRY THEY'RE ABOUT, NOT "achievements": when the student states a
metric, scale, or impact result FOR a specific existing project or experience entry (e.g. "it was used by
50 students", "that cut planning time in half", "the tool saved the team 5 hours a week"), that result is
an ADDITIONAL LINE in THAT entry's own "description" (per the ACHIEVEMENTS AS SEPARATE BULLETS rule
above) - never put it in the top-level "achievements" array, which is reserved for things NOT tied to a
listed project/experience (e.g. a certification, an award, an extracurricular activity, a competition).
If it's genuinely ambiguous which project/experience a result belongs to, ask rather than guessing.

TASK 2 - JUDGE COMPLETENESS: given current_draft plus whatever you just extracted, judge whether the
resulting profile is ready to write a truthful, specific CV from. This is NOT a null-check - a field can
be present and still not be CV-ready. Check each of the following, in this priority order (most important
first - only the first few may fit within the conversation's step budget, so order matters). Work
experience, projects, and achievements are never reported as unaddressed here - an unmentioned section for
any of the three is simply treated as none, not a gap. Only report ambiguity for content that DOES exist:

1. name - missing.
2. degree - missing, OR present but missing a degree level (e.g. "Computing Science" alone does not say
   Bachelor's / Master's / PhD), OR missing a major/sub-major that the conversation implies exists (e.g.
   the student mentions a specialisation or stream but the recorded degree name doesn't include it).
3. institution - missing (which university/institution the student attends) - never assume or default
   this, it must come from the student.
4. year - missing (what year of study).
5. education - a new degree/qualification mentioned this turn that is genuinely ambiguous between being
   additive (a separate qualification) or a correction to the existing one - see TASK 1's EDUCATION rule.
6. education_dates - the PRIMARY degree (current_draft.degree) has NEVER had a start date or an end date/
   expected graduation stated. Accept an approximate answer ("early 2026", "sometime next year") - never
   require an exact date, and never fabricate one if the student doesn't have or give one. Once asked and
   answered (even "I don't know exactly"), never flag this again.
7. technical_skills - missing entirely, OR every listed "skill" is a vague activity/domain phrase rather
   than a real named technology, tool, or skill (e.g. "networking", "software", "IT support" are NOT
   specific skills; "Linux", "Python", "Wireshark" are).
8. an existing experience entry that's too thin to write a CV bullet from (no description of what was
   done).
9. project_dates - an existing project entry has NEVER had a start/end date (or "ongoing"/"Present")
   stated. Same approximate-date-accepted, never-fabricate, never-re-ask-once-answered rules as
   education_dates.
10. project_outcome - an existing project entry has no concrete description of what was actually built or
    achieved - a list of technologies alone, with no statement of what it does or accomplished, is not an
    outcome.
11. target_roles - missing.

Never flag a project's measurable results/metrics as a gap - this is fully optional and must never be
asked about at any stage; only capture it (into that entry's own "description", never the top-level
"achievements") if the student states it unprompted.

For education_dates/project_dates/project_outcome specifically, also set "entry_identifier" on that gap:
the primary degree's is the literal string "primary"; a project's is that project's exact title (matching
current_draft.projects); do not set entry_identifier on any other gap (name, degree, institution, year,
technical_skills, target_roles, education, experience-too-thin) - leave it null there.

Do not flag minor stylistic imperfections - only flag something a hiring manager would find genuinely
unusable or unclear.

NO CONFIRMATION READ-BACK: a fact the student states clearly and unambiguously is trusted and saved the
moment it's captured - never read back for a "does that look right?" round-trip. The only exception is
DECLINING A SPECIFIC MISSING PROJECT DETAIL below, which is a genuinely different case (the student was
just asked for one specific missing thing and is responding to that specific question, not confirming an
already-complete entry). The single point the student explicitly confirms the whole profile is the
separate summary step once every gap is resolved - nothing here should try to replicate that per-entry.

DECLINING A SPECIFIC MISSING PROJECT DETAIL: if last_question_asked was asking specifically for ONE
project's missing dates or missing outcome (you can tell because it names that one project and asks for
exactly that one detail, not a general introduction), interpret latest_message as one of two things:
- A DECLINE with no actual detail given (e.g. "I don't remember the exact dates", "not sure", "there's no
  specific outcome beyond what I already said", "I don't have that") - add ONE entry to "declined_fields":
  {"entry_kind": "project", "entry_identifier": string (that project's exact title), "field": "dates" |
  "outcome"} matching whichever one was asked about. Do not guess "outcome" vs "dates" - match exactly
  what last_question_asked was about.
- The ACTUAL DETAIL given (a date, or a description of what was built/achieved) - extract it normally into
  that project's start_date/end_date or description as usual, and do NOT add a declined_fields entry for
  it.

OUTPUT FORMAT: Respond with strict JSON only, exactly these keys:
{
  "name": string or null,
  "degree": string or null,
  "institution": string or null,
  "year": string or null,
  "education_start_date": string or null,
  "education_end_date": string or null,
  "additional_education": array of {"degree": string, "year": string or null, "start_date": string or
      null, "end_date": string or null},
  "technical_skills": array of strings,
  "projects": array of {"title": string, "description": string or null, "technologies": array of strings,
      "start_date": string or null, "end_date": string or null},
  "experience": array of {"role": string, "organisation": string or null, "description": string or null,
      "start_date": string or null, "end_date": string or null},
  "target_roles": array of strings,
  "achievements": array of strings,
  "summary": string or null,
  "declined_fields": array of {"entry_kind": "project", "entry_identifier": string, "field": "dates" |
      "outcome"} - see DECLINING above; empty array unless latest_message is declining a specific
      project-detail question,
  "gaps": array of {"field": string, "issue": "missing" | "ambiguous", "reason": string,
      "entry_identifier": string or null}
}

"gaps" must be ordered most-important-first per the priority list above and must only use "missing" or
"ambiguous" as the issue - never a "section unaddressed" style issue. Only include a gap if it is real -
an empty array means the profile is ready. Use only current_draft plus this turn's extraction to judge
gaps - do not invent facts to fill one. Output JSON only, no commentary."""

FOLLOW_UP_SYSTEM_PROMPT = """You are a friendly assistant helping a student build a CV profile through
conversation. You will be given a "things still needed" list and the current draft profile for context.
Ask about ONLY the items in that list, together in ONE short, natural message - a single combined
follow-up, not one question at a time across multiple turns. Phrase it however reads most naturally (a
few sentences, or a short list if that's clearer for several items) - the point is the student can answer
everything in one reply instead of a back-and-forth.

ACKNOWLEDGING WHAT WAS JUST CAPTURED: you may also be given a "Facts just recorded" list - facts the
student's latest reply added, computed independently from your own output so it is always accurate. If
present, open your reply with ONE brief, natural sentence acknowledging what was captured - mention every
item in that list somewhere in the sentence (never omit one), but group and summarize them naturally
(e.g. "Got your degree and institution down.") rather than itemizing each one as its own clause ("recorded
your degree as X; recorded your institution as Y"). Then clearly separate that acknowledgment from the
actual question(s) that follow - a new sentence, or its own short paragraph - never merged into the same
run-on sentence as the acknowledgment, so the question never gets buried after it. If no "Facts just
recorded" list is given, skip the acknowledgment entirely and open directly with the question(s).

If the "things still needed" list spans clearly distinct topics (e.g. education dates versus a project's
timeline and impact), ask about each topic as its own clearly separated question (separate sentences, or
a short line break between them) rather than merging unrelated asks into a single run-on sentence.

The draft profile is shown ONLY so you can phrase things naturally (e.g. referencing what's already
known) - it will usually contain OTHER fields that are also still empty or null, such as experience,
achievements, summary, or contact details (email/phone/GitHub/LinkedIn), that are NOT in the "things
still needed" list. An empty or null field in the draft is NOT, by itself, a reason to ask about it - do
not ask about anything unless it is explicitly named in the "things still needed" list, no matter how
incomplete the rest of the draft looks. Do not repeat information already collected, and do not add
filler.

NEVER ask the student to re-confirm something they just stated clearly - no "does that look right?" about
a single fact. Trust it and move straight to the next item in the list (or, if the list has only one item
and it's now answered, there is nothing left to ask here at all). The one place the whole profile gets
confirmed is a separate, later summary step - this message should never try to replicate that for a
single field or entry."""

SUMMARY_SYSTEM_PROMPT = """You are a friendly assistant helping a student build a CV profile. Given the
completed draft profile as JSON, write a short, plain-language summary (a few sentences or bullet
points) of what was captured, then ask the student to confirm it looks correct. Do not invent details
beyond what is in the JSON."""

JOB_REQUIREMENT_GAP_SYSTEM_PROMPT = """You are a CV-building assistant. You will be given, in the user
message, a JSON object with three keys:
- "confirmed_profile": the candidate's complete, already-confirmed profile - the ONLY source of what
  the candidate currently has.
- "selected_job": the target job's title and full description text.
- "already_declined": requirement names the candidate has already told us, for a previous job, that
  they don't have - never ask about these again, silently treat them as still confirmed-absent.

TASK: Read selected_job's description and identify every concrete requirement it explicitly states - a
required skill, tool, technology, degree level, or years/domain of experience. Do not invent a
requirement that isn't actually in the text, and do not treat a responsibility, nice-to-have, or
aspirational company-mission line as a hard requirement. For each one, check whether confirmed_profile
already covers it (a technical skill already listed, an experience/project entry that clearly
demonstrates it, or the stated degree). Keep ONLY the requirements confirmed_profile does NOT already
cover, and drop any requirement that matches - even loosely, e.g. "SQL" vs "SQL Server" - something in
already_declined.

For each kept gap, classify "kind" as "skill" (a single named tool/technology/language) or "experience"
(a duration, domain, or qualification-level requirement that isn't one named tool).

If any gaps remain, write ONE short, natural, combined follow-up question covering ALL of them together
in a single message - never one message per gap. Example: "This role also lists SQL and Docker
experience, and prior work in a regulated industry - do you have any of these? If so, briefly tell me
about it." If there are no gaps, "question" must be null and "gaps" must be an empty array.

OUTPUT FORMAT: Respond with strict JSON only, exactly these keys:
{
  "gaps": array of {"requirement": string, "kind": "skill" | "experience", "reason": string},
  "question": string or null
}
No commentary outside the JSON."""

JOB_REQUIREMENT_ANSWER_SYSTEM_PROMPT = """You are a CV-building assistant processing a student's reply
to a single combined follow-up question about specific job requirements. You will be given, in the user
message, a JSON object with two keys:
- "gaps": the exact list of requirement gaps that were just asked about, each
  {"requirement": string, "kind": string, "reason": string}.
- "reply": the student's free-text reply.

TASK: For EVERY item in gaps (all of them, none skipped), decide from reply whether the student has
confirmed they DO have it ("confirmed") or has not clearly confirmed it ("declined" - this also covers
silence about that item, a vague or partial answer, or an explicit "no"). Only mark "confirmed" when the
reply clearly and explicitly states or strongly implies the student has that requirement - never infer
from tone alone, and when genuinely unclear, use "declined" rather than guessing "confirmed": a real
requirement marked unconfirmed is safe, a fabricated confirmation is not. For a "confirmed" item, if the
reply gives any concrete detail beyond just naming it (e.g. where or how they used it), capture that in
"note" as a short factual restatement in third person, CV-register - otherwise "note" is null. Never
invent a detail the reply didn't state.

Separately, for a "confirmed" item, decide "skill_name": a short, CV-ready skill/technology name to add
to the candidate's skill list, taken from the requirement's own name (e.g. "SQL") or from a specific
tool/technique named in the reply - whichever the reply actually supports. Use null when the confirmed
item is a duration, domain, or qualification-level fact that doesn't reduce to one discrete named skill
(e.g. "two years of professional experience"). This is decided from what the reply demonstrates, not
from whether the original requirement read like a "skill" or an "experience" gap.

OUTPUT FORMAT: Respond with strict JSON only, exactly these keys:
{
  "resolutions": array of {"requirement": string (must exactly match one from gaps), "status": "confirmed" | "declined", "skill_name": string or null, "note": string or null}
}
Include exactly one entry per item in gaps, in the same order as given. No commentary outside the JSON."""


class LLMClient:
    """Common interface both GroqLLM (cloud, via GROQ) and LocalLLM (a
    locally-run model via Ollama's OpenAI-compatible endpoint) implement -
    see build_llm(), which picks one based on the LLM_BACKEND env var.
    Every other class in this project that talks to an LLM (ProfileAgent,
    JobRequirementAgent, CVGenerator) only ever depends on this interface,
    never on which backend is actually running, so switching backends
    needs no changes anywhere else."""

    def extract_json(self, system_prompt: str, user_content: str, max_tokens: int = 1024) -> dict:
        raise NotImplementedError

    def generate_text(self, system_prompt: str, user_content: str, max_tokens: int = 400) -> str:
        raise NotImplementedError


class GroqLLM(LLMClient):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, env_path: Optional[str] = None):
        load_dotenv(env_path or Path(__file__).resolve().parents[2] / "02_Setup" / ".env")
        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Create 02_Setup/.env with GROQ_API_KEY=<your key>."
            )
        self.client = Groq(api_key=key)
        self.model = model or os.environ.get("GROQ_MODEL", DEFAULT_MODEL)
        # (timestamp, tokens) for every call made in the last TPM_WINDOW_SECONDS -
        # see _throttle().
        self._token_usage_window: deque = deque()

    @staticmethod
    def _estimate_tokens(*texts: str) -> int:
        # Deliberately simple ~4-chars-per-token heuristic - the same rule
        # of thumb already used informally throughout this project's
        # max_tokens tuning (see extract_json()'s comments). Good enough to
        # throttle proactively; not meant to match GROQ's own count exactly.
        return sum(len(t) for t in texts) // 4

    def _throttle(self, estimated_tokens: int) -> None:
        """Proactively sleeps just long enough to keep this account's 8000
        TPM ceiling from being hit, instead of firing the request and
        handling the 429 after the fact - client-side only and approximate
        (see _estimate_tokens), covering both extract_json() and
        generate_text() since both share this ceiling."""
        now = time.monotonic()
        while self._token_usage_window and now - self._token_usage_window[0][0] > TPM_WINDOW_SECONDS:
            self._token_usage_window.popleft()
        used = sum(tokens for _, tokens in self._token_usage_window)
        if used + estimated_tokens > TPM_LIMIT and self._token_usage_window:
            wait = TPM_WINDOW_SECONDS - (now - self._token_usage_window[0][0])
            if wait > 0:
                time.sleep(wait)
            now = time.monotonic()
            while self._token_usage_window and now - self._token_usage_window[0][0] > TPM_WINDOW_SECONDS:
                self._token_usage_window.popleft()
        self._token_usage_window.append((time.monotonic(), estimated_tokens))

    def extract_json(self, system_prompt: str, user_content: str, max_tokens: int = 1024) -> dict:
        # This reasoning model spends hidden thinking tokens before any
        # visible output, and how much it spends isn't fully deterministic
        # even at temperature=0.2 - occasionally it burns the ENTIRE
        # max_tokens budget on reasoning and returns a genuinely empty
        # completion, which GROQ reports as a 400 "Failed to validate JSON"
        # with an empty failed_generation. This has hit every extract_json
        # call site in this project at one point or another, tuning
        # max_tokens up only reduces the odds, it doesn't eliminate them
        # (going higher risks a DIFFERENT failure - GROQ rejecting the
        # request outright for exceeding the account's per-request token
        # ceiling). A single retry is the pragmatic fix: the same request
        # at the same settings has a good chance of reasoning less and
        # producing real output the second time, and this is far cheaper
        # than crashing the caller (e.g. mid-CV-generation in the GUI).
        for attempt in range(2):
            self._throttle(self._estimate_tokens(system_prompt, user_content) + max_tokens)
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=max_tokens,
                    temperature=0.2,
                )
                return json.loads(resp.choices[0].message.content)
            except BadRequestError as e:
                body = e.body if isinstance(e.body, dict) else {}
                code = (body.get("error") or {}).get("code")
                if attempt == 0 and code == "json_validate_failed":
                    continue
                raise
            except RateLimitError as e:
                # No retry here by design - proactive throttling above is
                # meant to prevent this; if GROQ still rejects the request
                # (e.g. another process sharing this account, or a burst
                # this window's estimate didn't foresee), surface it clearly
                # rather than silently retrying into the same limit.
                print(f"[GroqLLM.extract_json] Groq TPM rate limit hit despite client-side throttling: {e}")
                raise

    def generate_text(self, system_prompt: str, user_content: str, max_tokens: int = 400) -> str:
        self._throttle(self._estimate_tokens(system_prompt, user_content) + max_tokens)
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=max_tokens,
                temperature=0.4,
            )
        except RateLimitError as e:
            print(f"[GroqLLM.generate_text] Groq TPM rate limit hit despite client-side throttling: {e}")
            raise
        return resp.choices[0].message.content.strip()


DEFAULT_LOCAL_MODEL = "gpt-oss:20b"
DEFAULT_LOCAL_BASE_URL = "http://localhost:11434"
# Ollama's default RUNTIME context window is 4096 regardless of a model's
# own supported maximum (gpt-oss:20b supports up to 131072) - confirmed
# live via `ollama ps` after a request with no override. This project's own
# EXTRACTION_SYSTEM_PROMPT is already ~4k tokens on its own, so at the
# 4096 default the model has essentially no room left to reason AND
# produce output, and returns an empty completion no matter how high
# max_tokens/num_predict is set (confirmed live - still empty even at
# 32000). 16384 was confirmed live to handle the real production prompt
# correctly (~20s, matching GROQ's own output shape). Going straight to
# 32768 crashed the local llama-server process outright on this machine
# (a CUDA/stack-overrun crash, not a graceful error) - almost certainly a
# GPU VRAM ceiling - so this default is deliberately conservative;
# override LOCAL_LLM_NUM_CTX upward only if your hardware has the VRAM
# for it, and downward if 16384 itself is too much for a smaller GPU.
DEFAULT_LOCAL_NUM_CTX = 16384


class LocalLLM(LLMClient):
    """Runs the SAME two operations as GroqLLM (extract_json/generate_text)
    against a model running locally via Ollama, instead of GROQ's cloud API -
    selected by setting LLM_BACKEND=local (see build_llm()). Deliberately
    uses Ollama's NATIVE /api/chat endpoint, NOT its OpenAI-compatible
    /v1/chat/completions one: the OpenAI-compatible endpoint silently
    ignores Ollama-specific options like num_ctx (confirmed live - passing
    options.num_ctx to it left `ollama ps`'s reported context size
    unchanged), and num_ctx is exactly what's needed here (see
    DEFAULT_LOCAL_NUM_CTX). Only the native endpoint actually reloads the
    model with a bigger context window when it's set. Uses plain httpx
    (already a transitive dependency of groq/openai) rather than a
    dedicated Ollama client library, since this is a small, fixed request
    shape. No API key or throttling is needed - GROQ's 8000 TPM ceiling is
    an account-level cloud limit that doesn't exist for hardware you own."""

    # Escalation cap for the empty-completion retries below - see _chat().
    # Local inference has no GROQ-style TPM ceiling to respect, so unlike
    # GroqLLM there's no downside to a large num_predict budget beyond
    # slower generation time; this just bounds the worst case.
    _MAX_RETRY_TOKENS = 32000

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None, num_ctx: Optional[int] = None):
        import httpx

        # Same as GroqLLM.__init__() - needed so a LocalLLM() constructed
        # directly (bypassing build_llm()) still picks up 02_Setup/.env's
        # LOCAL_LLM_* values.
        load_dotenv(Path(__file__).resolve().parents[2] / "02_Setup" / ".env")
        self._client = httpx.Client(
            base_url=base_url or os.environ.get("LOCAL_LLM_BASE_URL", DEFAULT_LOCAL_BASE_URL),
            timeout=180.0,  # local generation, especially at a larger num_ctx, can take a while
        )
        self.model = model or os.environ.get("LOCAL_LLM_MODEL", DEFAULT_LOCAL_MODEL)
        self.num_ctx = num_ctx or int(os.environ.get("LOCAL_LLM_NUM_CTX", DEFAULT_LOCAL_NUM_CTX))

    def _chat(self, system_prompt: str, user_content: str, num_predict: int, temperature: float, json_mode: bool) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "options": {"num_ctx": self.num_ctx, "num_predict": num_predict, "temperature": temperature},
            # gpt-oss:20b is a reasoning model that otherwise burns hundreds-
            # to-thousands of hidden "thinking" tokens before ever emitting
            # visible output - "low" cut a real extraction call from ~18.5s/
            # 1333 tokens to ~9.5s/585 tokens with identical extracted
            # fields (verified live against EXTRACTION_SYSTEM_PROMPT), so
            # this is a genuine latency fix, not a quality tradeoff. GROQ has
            # its own equivalent (reasoning_effort) but that's untested here.
            "think": "low",
        }
        if json_mode:
            payload["format"] = "json"
        resp = self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    def extract_json(self, system_prompt: str, user_content: str, max_tokens: int = 1024) -> dict:
        # Same hidden-reasoning-tokens quirk as GroqLLM.extract_json() - this
        # IS the same gpt-oss:20b model, just served locally - can still
        # spend the whole num_predict budget reasoning and return an empty
        # completion (no exception, just ""). Now that num_ctx is sized
        # correctly (see DEFAULT_LOCAL_NUM_CTX) this should be rare, but
        # each retry still doubles the budget as a secondary safety net,
        # up to _MAX_RETRY_TOKENS - local has no per-request ceiling to
        # respect, so there's no downside besides slower generation.
        attempt_tokens = max_tokens
        while True:
            content = self._chat(system_prompt, user_content, attempt_tokens, 0.2, json_mode=True)
            if content:
                return json.loads(content)
            if attempt_tokens >= self._MAX_RETRY_TOKENS:
                raise ValueError(
                    f"LocalLLM.extract_json: the model returned an empty completion even at "
                    f"max_tokens={attempt_tokens} with num_ctx={self.num_ctx} - if this persists, "
                    "try raising LOCAL_LLM_NUM_CTX (watch for GPU VRAM limits when doing so)."
                )
            attempt_tokens = min(attempt_tokens * 2, self._MAX_RETRY_TOKENS)

    def generate_text(self, system_prompt: str, user_content: str, max_tokens: int = 400) -> str:
        attempt_tokens = max_tokens
        while True:
            content = self._chat(system_prompt, user_content, attempt_tokens, 0.4, json_mode=False)
            if content and content.strip():
                return content.strip()
            if attempt_tokens >= self._MAX_RETRY_TOKENS:
                raise ValueError(
                    f"LocalLLM.generate_text: the model returned an empty completion even at "
                    f"max_tokens={attempt_tokens} with num_ctx={self.num_ctx} - if this persists, "
                    "try raising LOCAL_LLM_NUM_CTX (watch for GPU VRAM limits when doing so)."
                )
            attempt_tokens = min(attempt_tokens * 2, self._MAX_RETRY_TOKENS)


def build_llm(backend: Optional[str] = None, **kwargs) -> LLMClient:
    """The one place every other class in this project should get its LLM
    client from, instead of constructing GroqLLM()/LocalLLM() directly -
    reads LLM_BACKEND from the environment ("groq", the default, or
    "local") when `backend` isn't passed explicitly, so switching backends
    is a one-line env var change (02_Setup/.env) with no code changes
    anywhere else. kwargs are forwarded to whichever backend is chosen
    (e.g. model=/base_url= for LocalLLM, api_key=/model= for GroqLLM)."""
    # Must load .env HERE, before reading LLM_BACKEND below - GroqLLM/
    # LocalLLM's own __init__ each load it too (for direct construction,
    # bypassing this factory), but that happens too late for THIS decision:
    # without this, LLM_BACKEND=local in .env was silently ignored on a
    # fresh process (nothing had loaded .env into os.environ yet), always
    # falling through to the "groq" default and constructing GroqLLM
    # regardless of what .env actually said.
    load_dotenv(Path(__file__).resolve().parents[2] / "02_Setup" / ".env")
    backend = (backend or os.environ.get("LLM_BACKEND", "groq")).strip().lower()
    if backend in ("local", "ollama"):
        return LocalLLM(**kwargs)
    if backend == "groq":
        return GroqLLM(**kwargs)
    raise ValueError(f"Unknown LLM_BACKEND {backend!r} - expected 'groq' or 'local'.")


class ProfileAgent:
    """Multi-turn profile-building agent.

    Each loop iteration is one Action: ExtractFields always runs first on the
    latest user text, producing an Observation from profile_tool. The next
    Action (AskFollowUp vs FinalAnswer) is chosen purely from that
    Observation's gaps list - the same extraction call's own judgement of
    what's missing, ambiguous, or unaddressed, not a separate presence-check.
    The step counter only counts agent Actions, not the user's replies, since
    the cap bounds the agent's own behaviour.
    """

    def __init__(self, llm: LLMClient, step_cap: int = 5, review_step_cap: int = 10, job_tool=None):
        self.llm = llm
        # Two separate budgets for two separate phases (see take_turn()'s
        # phase param): intake's budget shrank from 8 once project follow-
        # ups (dates/outcome/confirmation) were deferred entirely out of it
        # - what used to take several extra turns per project no longer
        # happens here at all. review gets its own, larger budget since it
        # deliberately asks one project field at a time rather than
        # batching, which needs more turns to cover the same ground.
        self.step_cap = step_cap
        self.review_step_cap = review_step_cap
        self.tool = ProfileTool()
        self.job_tool = job_tool
        self.trace: List[dict] = []
        self.step = 0
        self.review_step = 0
        self._last_question: Optional[str] = None

    def _log_action(self, action: str, detail: dict, observation: dict, phase: str = "intake") -> None:
        if phase == "review":
            self.review_step += 1
            step = self.review_step
        else:
            self.step += 1
            step = self.step
        self.trace.append(
            {"step": step, "phase": phase, "role": "agent", "action": action, "detail": detail, "observation": observation}
        )

    def _log_user(self, text: str) -> None:
        self.trace.append({"step": None, "role": "user", "text": text})

    def _log_terminal(self, action: str, detail: dict, observation: dict, phase: str = "intake") -> None:
        step = self.review_step if phase == "review" else self.step
        self.trace.append(
            {"step": f"{step}+", "phase": phase, "role": "agent", "action": action, "detail": detail, "observation": observation}
        )

    def take_turn(self, user_text: str, phase: str = "intake", log_user: bool = True) -> dict:
        """Runs exactly one turn: logs user_text, extracts fields from it, and
        then either finalizes (optionally retrieving jobs), asks a follow-up,
        or reports the step cap was reached. Does not block for input - the
        caller decides how to obtain the next user_text (a scripted list,
        input(), or a GUI widget), which is what lets both run() and a
        turn-by-turn UI drive the same underlying loop.

        phase="intake" (default) covers every required field plus education
        gaps, batching everything currently outstanding into ONE combined
        follow-up message, exactly as before - projects are never asked
        about here (see DraftProfile.compute_gaps()). phase="review" covers
        ONLY project gaps (dates, outcome, the per-entry confirmation
        read-back), one at a time - compute_gaps() guarantees at most one
        gap is ever returned in this phase, so the question generated below
        is always about exactly one project field of one entry. log_user
        controls whether user_text is logged to the trace as a user turn -
        set False only for the one-off bootstrap call made with an empty
        user_text right when review starts, to compute the first review gap
        (if any) from the draft alone before the student has said anything
        new (see start_review()).

        Returns one of:
          {"status": "confirmed", "draft": ..., "summary": ..., "job_matches": [...] (if job_tool set)}
          {"status": "needs_input", "question": ..., "target_field": ...} (target_field is a
              comma-joined summary of every field the combined question covers this turn)
          {"status": "step_limit_reached", "draft": ...}
        """
        if log_user:
            self._log_user(user_text)

        current_draft = self.tool.read_profile()["draft"]
        extraction_input = json.dumps(
            {
                "current_draft": current_draft,
                "last_question_asked": self._last_question,
                "latest_message": user_text,
            }
        )
        # EXTRACTION_SYSTEM_PROMPT is now ~3.8k tokens on its own (achievement
        # splitting, date capture, widened project/education checks, entry
        # confirmation AND decline handling), against this account's 8000
        # TPM ceiling PER REQUEST (prompt + max_tokens together, confirmed
        # via a live 413 "Request too large" at max_tokens=6144, and again
        # at 4300 once the prompt grew further with the review-phase
        # decline rules and a richer current_draft mid-conversation) - so
        # max_tokens here is a genuine tightrope: too low and the reasoning
        # model spends its whole budget on hidden thinking with zero visible
        # output (BadRequestError: json_validate_failed, empty
        # failed_generation); too high and GROQ rejects the request
        # outright before it even runs. 4000 is the largest value confirmed
        # to clear both failure modes live with the current prompt size.
        extracted = self.llm.extract_json(EXTRACTION_SYSTEM_PROMPT, extraction_input, max_tokens=4000)
        observation = self.tool.update_profile(extracted, phase=phase)
        self._log_action("ExtractFields", {"user_text": user_text, "extracted": extracted}, observation, phase=phase)

        gaps = observation["gaps"]
        new_facts = observation["new_facts"]

        if not gaps:
            summary = self.llm.generate_text(SUMMARY_SYSTEM_PROMPT, json.dumps(observation["draft"]))
            self._log_action("FinalAnswer", {}, {"summary": summary, "status": "profile_confirmed"}, phase=phase)
            result = {"status": "confirmed", "draft": observation["draft"], "summary": summary, "new_facts": new_facts}

            if self.job_tool is not None:
                profile_obj = self.tool.to_profile(document_id="live_profile")
                matches = self.job_tool.search(profile_obj, top_k=3)
                self._log_action("RetrieveJobs", {}, {"matches": matches}, phase=phase)
                result["job_matches"] = matches

            return result

        current_cap = self.review_step_cap if phase == "review" else self.step_cap
        current_step = self.review_step if phase == "review" else self.step
        if current_step >= current_cap:
            observation = self.tool.read_profile()
            self._log_terminal(
                "StepLimitReached",
                {},
                {"draft": observation["draft"], "gaps": observation["gaps"], "status": "step_limit_reached"},
                phase=phase,
            )
            return {"status": "step_limit_reached", "draft": observation["draft"]}

        gaps_list = "\n".join(f"- {g['reason']}" for g in gaps)
        # facts_section feeds the deterministic, Python-computed new_facts
        # (see profile_model.describe_new_facts) into the SAME call that
        # phrases the question, rather than gluing a separately-generated
        # "Got it - X; Y; Z." prefix on afterwards in Python. That old
        # concatenation read as a mechanical field-by-field log dump ahead
        # of the real question; the model is now told to acknowledge the
        # same ground-truth list (nothing added, nothing dropped) but in
        # one brief natural sentence, clearly separated from the question
        # that follows - see FOLLOW_UP_SYSTEM_PROMPT's ACKNOWLEDGING WHAT
        # WAS JUST CAPTURED rule.
        facts_section = ""
        if new_facts:
            facts_section = (
                "\nFacts just recorded from the student's latest reply, to briefly and naturally "
                "acknowledge before asking the question(s) above (mention all of them, but phrase them "
                f"together naturally rather than listing each one separately): {'; '.join(new_facts)}\n"
            )
        question = self.llm.generate_text(
            FOLLOW_UP_SYSTEM_PROMPT,
            f"Things still needed (ask about ONLY these, all together in one message):\n{gaps_list}\n"
            f"{facts_section}"
            f"Current draft profile, for phrasing context only - do not ask about any other empty/null "
            f"field in here that isn't listed above: {json.dumps(observation['draft'])}",
            # A confirmation item (see FOLLOW_UP_SYSTEM_PROMPT's CONFIRMATION
            # ITEMS rule) reads a full entry back before asking anything -
            # noticeably longer than a plain missing-field question. This
            # model spends hidden reasoning tokens before any visible output
            # even outside JSON mode (the same headroom issue hit and fixed
            # at every other call site in this project) - 400, then 800,
            # both observed truncating mid-sentence live; 1500 is not.
            max_tokens=1500,
        )
        fields_asked = ", ".join(g["field"] for g in gaps)
        self._log_action(
            "AskFollowUp",
            {"target_field": fields_asked, "gaps": gaps},
            {"question": question, "new_facts": new_facts},
            phase=phase,
        )
        self._last_question = question
        return {"status": "needs_input", "question": question, "target_field": fields_asked, "new_facts": new_facts}

    def start_review(self) -> dict:
        """Called exactly once, right when intake finishes (gaps empty in
        phase="intake"), to determine the FIRST review-phase gap, if any,
        purely from the draft as intake left it - there is no new user_text
        to extract from yet, so this is take_turn() with an empty message
        and log_user=False (an empty turn has nothing worth showing in the
        trace as something the student said). If the student has no
        projects, or every project is already fully specified, this comes
        back "confirmed" immediately and the caller (the GUI's "confirm"
        stage) shows no review chat at all - see take_turn()'s phase="review"
        docstring for what gets asked."""
        return self.take_turn("", phase="review", log_user=False)

    def run(
        self,
        initial_text: str,
        scripted_replies: Optional[List[str]] = None,
        scripted_review_replies: Optional[List[str]] = None,
    ) -> dict:
        scripted_replies = list(scripted_replies or [])
        user_text = initial_text

        while True:
            result = self.take_turn(user_text, phase="intake")

            if result["status"] == "confirmed":
                break

            if result["status"] == "step_limit_reached":
                return {"status": "step_limit_reached", "trace": self.trace, "draft": result["draft"]}

            if scripted_replies:
                user_text = scripted_replies.pop(0)
            else:
                user_text = input(result["question"] + "\n> ")

        # Intake never asks about projects by design (see
        # DraftProfile.compute_gaps()) - review picks up here, one project
        # field at a time, until nothing project-related is left.
        review_result = self.start_review()
        scripted_review_replies = list(scripted_review_replies or [])

        while review_result["status"] == "needs_input":
            if scripted_review_replies:
                review_text = scripted_review_replies.pop(0)
            else:
                review_text = input(review_result["question"] + "\n> ")
            review_result = self.take_turn(review_text, phase="review")

        if review_result["status"] == "step_limit_reached":
            return {"status": "step_limit_reached", "trace": self.trace, "draft": review_result["draft"]}

        out = {"status": "confirmed", "trace": self.trace, "draft": review_result["draft"]}
        if "job_matches" in review_result:
            out["job_matches"] = review_result["job_matches"]
        return out


class JobRequirementAgent:
    """Runs once per target-job selection, after the profile is confirmed
    and before CV generation: compares the confirmed profile against the
    SPECIFIC selected job's stated requirements (not a generic
    profile-completeness check) and asks about only the genuine gaps.

    Unlike ProfileAgent's multi-turn loop, this is a single round-trip by
    design - check() asks at most one combined question covering every gap
    for this job, and resolve() processes the one reply and finalizes every
    gap from that round: whatever wasn't clearly confirmed is recorded as
    confirmed-absent via decline_requirements(), never fabricated and never
    re-asked, so the loop cannot go on indefinitely. Re-running check() with
    a different job naturally produces a different gap list, since it's
    always computed fresh against that job's own requirement text."""

    def __init__(self, llm: LLMClient, tool: ProfileTool):
        self.llm = llm
        self.tool = tool
        self.trace: List[dict] = []

    def check(self, job: dict) -> dict:
        profile = self.tool.to_profile(document_id="_job_requirement_check")
        declined = self.tool.read_profile()["draft"].get("declined_requirements", [])
        user_content = json.dumps(
            {
                "confirmed_profile": asdict(profile),
                "selected_job": {"title": job["title"], "description": job["description"]},
                "already_declined": declined,
            }
        )
        result = self.llm.extract_json(JOB_REQUIREMENT_GAP_SYSTEM_PROMPT, user_content, max_tokens=4096)
        gaps = result.get("gaps") or []
        if not gaps:
            self.trace.append(
                {"role": "agent", "action": "CheckJobRequirements", "detail": {"job": job["document_id"]}, "observation": {"gaps": gaps}}
            )
            return {"status": "no_gaps"}

        # Safety net: gaps is non-empty but the model occasionally omits
        # "question" (most often when there's exactly one gap) - never let a
        # real gap surface with a null/blank question, since that would
        # render as an empty prompt in the CLI/GUI.
        question = result.get("question") or (
            f"This role also lists {', '.join(g['requirement'] for g in gaps)}. Do you have experience "
            "with any of these? If so, briefly tell me about it."
        )
        self.trace.append(
            {"role": "agent", "action": "CheckJobRequirements", "detail": {"job": job["document_id"]}, "observation": {"gaps": gaps, "question": question}}
        )
        return {"status": "needs_input", "question": question, "gaps": gaps}

    def resolve(self, gaps: List[dict], user_text: str) -> dict:
        user_content = json.dumps({"gaps": gaps, "reply": user_text})
        result = self.llm.extract_json(JOB_REQUIREMENT_ANSWER_SYSTEM_PROMPT, user_content, max_tokens=4096)
        resolutions = {r.get("requirement"): r for r in result.get("resolutions", []) if r.get("requirement")}

        confirmed_skills, confirmed_notes, declined = [], [], []
        for gap in gaps:
            req = gap["requirement"]
            res = resolutions.get(req)
            # Safety net independent of the prompt (same pattern as
            # cv_generator._verify_and_clean): any gap the model's response
            # doesn't clearly resolve as "confirmed" defaults to declined,
            # so a missing/malformed entry can never linger as re-askable.
            if res and res.get("status") == "confirmed":
                if res.get("skill_name"):
                    confirmed_skills.append(str(res["skill_name"]).strip())
                if res.get("note"):
                    confirmed_notes.append(str(res["note"]).strip())
            else:
                declined.append(req)

        self.tool.apply_job_requirement_facts(
            fields={"technical_skills": confirmed_skills, "achievements": confirmed_notes}, declined=declined
        )
        self.trace.append({"role": "user", "text": user_text})
        self.trace.append(
            {
                "role": "agent",
                "action": "ResolveJobRequirements",
                "detail": {"resolutions": result.get("resolutions", [])},
                "observation": {"confirmed_skills": confirmed_skills, "confirmed_notes": confirmed_notes, "declined": declined},
            }
        )
        return {"confirmed_skills": confirmed_skills, "confirmed_notes": confirmed_notes, "declined": declined}
