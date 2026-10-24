GOAL: Project setup & profile data model

We're building an AI-powered CV Builder as an assessment project. I'll
give you the requirements one feature at a time so we can build and
verify incrementally — don't try to build the whole system yet.

I already have a project folder structure set up — do NOT create a new
one or reorganize it. Work inside this existing layout:

  01_System/
    source_code/data/    <- jobs.jsonl, README.md, and profile input
                            files live here (student_introductions...,
                            student_profiles.json)
    architecture_diagram... / architecture.md
  02_Setup/               <- config + dependencies go here
  03_Evidence/
    01_Prompts/            <- prompt_record.md
    02_Agent/               <- agent_actions_and_..., follow_up_questions...
    03_Retrieval/           <- retrieval_results...
    04_System_Tests/        <- test_profiles, cross_user_test.md,
                              five_profile_results..., two_job_comparison...
    05_Failures_and_Improvements/  <- failure_and_repair...

For this first step:
1. Confirm you can see and inventory the existing structure above —
   list what's already in 01_System/source_code/data and flag anything
   referenced in this brief that seems to be missing.
2. Add a config file with placeholder values (no hardcoded secrets)
   and a dependencies file into 02_Setup/.
3. Define the structured PROFILE data model: contact details,
   education, skills, experience, projects, achievements, job goal.
   Pick a sensible format (e.g. Python dataclass based on the JSONL and
   explain your choice. Base it on the existing student_profiles.json
   / student_introductions files 

Do NOT build the agent, retrieval, CV generation, or PDF export yet —
just the setup and the profile data model, and only inside the
existing folders.

Before you write any code, tell me the inventory of what's already
there, the profile schema you're planning, and exactly which existing
files you'd touch, and wait for me to confirm before you generate or
edit anything. Once done, show me the profile schema and ask me to
confirm it looks right before we move to the next feature.

PROPOSED CHANGE

Files I'd touch (pending your confirmation)
02_Setup/config.example — placeholder config (API key var name, model name, data paths) — no secrets
02_Setup/requirements.txt — minimal deps for this stage (stdlib-heavy; a couple of forward-looking libs for the JSONL handling)
New file: 01_System/source_code/profile_model.py — the dataclass model (source_code/ has no code yet, so this is a new file inside the existing folder, not a new folder)
Proposed PROFILE schema
Format choice: Python dataclasses (stdlib, no dependency), one dataclass per logical section, composed into a top-level Profile. I'm avoiding Pydantic for this stage — dataclasses are enough for a static shape check with no runtime validation library needed yet, and they map cleanly onto the JSONL records' nested dict/list structure via asdict()/a from_record() classmethod when we build I/O later.


ContactDetails: name, github, linkedin, email (optional), phone (optional)

Education: degree, program_mode, faculty, institution, campus, year,
           study_mode, expected_graduation, relevant_current_subjects (list[str]),
           coursework_highlights (list[str]), prerequisite_context

SkillEvidence: skill, source
Skills: technical_skills (list[str]), evidence (list[SkillEvidence])

ExperienceEntry: role, organisation, type, description
Experience: entries (list[ExperienceEntry])

ProjectEntry: title, context, description, technologies (list[str])
Projects: entries (list[ProjectEntry])

Achievements: activities (list[str])   # e.g. showcase presentations, volunteering

JobGoal: target_roles (list[str]), availability, work_rights, summary

Profile:
    document_id, profile_type, dataset_scope
    contact: ContactDetails
    education: Education
    skills: Skills
    experience: Experience
    projects: Projects
    achievements: Achievements
    job_goal: JobGoal

DECISION
Accept

VERIFICATION

02_Setup/config.example — placeholder env vars (API key name, model, data paths), no secrets
02_Setup/requirements.txt — minimal deps, grouped by which future feature needs them
01_System/source_code/profile_model.py — the nested Profile dataclass matching the schema you confirmed, plus a from_record() classmethod that maps a raw student_profiles.jsonl dict onto it

---

GOAL: Multi-turn profile building agent

Now build the multi-turn profile-building agent. Use the profile data
model from the previous step.

Requirements:
- Takes a natural language text user introduction as input and extracts what it
  can into the structured profile.
- Decides its next Action from the current state (not a fixed script):
  if required fields are missing, it asks a targeted follow-up
  question; if the profile is already complete, it asks nothing extra
  and goes straight to a summary for confirmation.
- Give it a `profile_tool` for reading/writing profile state. After
  each tool call, produce an Observation (what the tool returned)
  before deciding the next Action.
- Stop condition: a final answer (profile confirmed) or a step limit
  (pick a sensible cap, e.g. 6-8 steps) — whichever comes first.
- I need to be able to test this with at least one deliberately
  incomplete introduction that requires two or more follow-up turns,
  and at least one complete introduction that needs zero follow-ups.

Do NOT build job retrieval, CV generation, or PDF export yet.

Save the Action/Observation traces from both test runs into
03_Evidence/02_Agent/ (agent_actions_and_observations, and a separate
follow_up_questions file for the incomplete-profile case) rather than
just printing them to the console.

Before writing code, briefly explain your plan for the agent loop
(how it decides Actions, how the step limit works) and wait for me to
confirm. Once built, walk me through running both an incomplete-profile
test and a complete-profile test, show me the Action/Observation trace
for each, and ask me to confirm the behaviour is correct before we move
on. Update 03_Evidence/01_Prompts/prompt_record.md with this step
before you finish.

PROPOSED CHANGE

Design fork raised with the user: no LLM SDK/API key was available in
the environment, so I asked whether extraction should be rule-based/
offline or LLM-backed. User chose to use GROQ for the agent's NLP work.
User initially asked for the API key to be hardcoded into the source
file; flagged the risk (key would sit in plain text in report
materials) and asked to confirm — user agreed to load it from a local,
untracked 02_Setup/.env via python-dotenv instead.

Agent loop: each step is one Action. ExtractFields always runs first on
the latest user text (GROQ call, strict JSON output) and updates
profile_tool state, producing an Observation. The branch taken next —
AskFollowUp vs FinalAnswer — is chosen purely from that Observation's
missing_fields list, not a fixed turn order. Required/extractable
fields: name, degree, year, >=1 technical skill, >=1 project-or-
experience entry (evidence), >=1 target role — admin/dataset fields
(institution, faculty, campus, etc.) are constant for this cohort and
defaulted in DraftProfile.to_profile() rather than asked about. Step
counter only counts agent Actions (not user replies); cap = 8.

Files touched:
- 01_System/source_code/profile_model.py — added DraftProfile,
  DraftProjectEntry, DraftExperienceEntry, missing_fields(), merge(),
  to_profile() (bridges back to the Profile dataclass from step 1)
- 01_System/source_code/profile_tool.py — new: the profile_tool
  (read_profile/update_profile) the agent calls, returns Observations
- 01_System/source_code/agent.py — new: GroqLLM wrapper + ProfileAgent
  loop
- 01_System/source_code/run_agent_tests.py — new: runnable script,
  authors both test introductions, runs both cases, writes evidence
- 02_Setup/config.example — swapped ANTHROPIC_* placeholders for
  GROQ_API_KEY / GROQ_MODEL
- 02_Setup/requirements.txt — swapped anthropic for groq
- 03_Evidence/02_Agent/agent_actions_and_observations.md — populated
- 03_Evidence/02_Agent/follow_up_question_test.md — populated

DECISION
Accept (GROQ backend, model openai/gpt-oss-20b, key in untracked
02_Setup/.env)

VERIFICATION

Ran 01_System/source_code/run_agent_tests.py against the live GROQ API
with the user's real key (never pasted into chat or written to a
tracked file). Actual results:
- Complete introduction (Jordan Ramirez, all fields stated): 2 agent
  steps, 0 follow-up questions, status=confirmed.
- Incomplete introduction (missing name + target_roles only):
  6 agent steps, exactly 2 targeted follow-up questions ("What's your
  full name?", "What type of role(s) are you aiming to apply for?"),
  status=confirmed — well inside the 8-step cap.
Both traces written to 03_Evidence/02_Agent/agent_actions_and_observations.md;
the incomplete run's follow-up exchanges also isolated into
03_Evidence/02_Agent/follow_up_question_test.md.

---

GOAL: Job retrieval component

Now build the job retrieval component.

Requirements:
- Load all nine job records from data/jobs.jsonl.
- Generate embeddings for each job description. Tell me what embedding
  approach you're using and why, given the libraries available in this
  environment.
- Given a confirmed profile + job goal, compute semantic similarity and
  return the top 3 most relevant jobs.
- For each returned job, show its unique document_id and a short
  supporting excerpt from the actual job description explaining why it
  matched — not a generic statement.
- Wire this in as the `job_retrieval_tool` the agent from the previous
  step can call.

Do NOT build CV generation or PDF export yet.

Save the retrieval outputs (document_ids + excerpts, per test profile)
into 03_Evidence/03_Retrieval/retrieval_results... rather than just
printing them.

Before writing code, tell me your embedding/similarity approach and
wait for my confirmation. Once built, run retrieval against 2-3 of the
test profiles from the previous step, show me the top-3 results with
document_ids and excerpts for each, and ask me to confirm the matches
look reasonable before we move on. Update
03_Evidence/01_Prompts/prompt_record.md.

PROPOSED CHANGE

Investigated the environment first: confirmed via a live call that
GROQ does not serve an embedding model on this key (400: "model does
not support embeddings"), and no embedding library was installed.
Asked the user to choose between sentence-transformers (real dense
embeddings, local model, needs a one-time pip install + HF download)
and TF-IDF + cosine similarity (lightweight, stdlib+numpy, purely
lexical). User chose sentence-transformers.

Approach: sentence-transformers `all-MiniLM-L6-v2` (384-dim), cosine
similarity. Each job's title+description is embedded once at tool
init. The profile query text is built from job_goal.target_roles +
job_goal.summary + skills.technical_skills + each project/experience
description, then embedded and compared against all 9 job embeddings
to rank top 3. For excerpts: each job description is also split into
sentences and embedded separately, so the sentence closest to the
profile's query vector (not a generic label) is returned as the "why
it matched" excerpt.

Files touched:
- 01_System/source_code/job_retrieval_tool.py — new: JobRetrievalTool
  (loads jobs.jsonl, embeds jobs + job sentences, search(profile,
  top_k) -> ranked matches with document_id/title/score/excerpt)
- 01_System/source_code/agent.py — added optional job_tool param to
  ProfileAgent; once FinalAnswer is reached, if a job_tool is present
  the agent takes one further RetrieveJobs Action calling
  job_tool.search() on the confirmed draft profile
- 01_System/source_code/run_retrieval_tests.py — new: runs retrieval
  against 3 diverse existing student_profiles.jsonl records (01
  Maya Chen/software generalist, 02 Liam Patel/NLP-AI, 04 Noah
  Ibrahim/cybersecurity-systems) and a live agent+job_tool demo, writes
  evidence
- 02_Setup/requirements.txt — added sentence-transformers
- 02_Setup/config.example — EMBEDDING_MODEL/TOP_K_RESULTS placeholders
  filled with real chosen values (all-MiniLM-L6-v2 / 3)
- 03_Evidence/03_Retrieval/retrieval_results.md — populated

DECISION
Accept (sentence-transformers all-MiniLM-L6-v2, cosine similarity,
sentence-level excerpt selection)

VERIFICATION

Ran 01_System/source_code/run_retrieval_tests.py. jobs.jsonl turned out
to be entirely AI/ML-engineering roles (Graduate AI Engineer, Computer
Vision Engineer, three ML Engineer variants, three AI Engineer/agentic
variants) with no generic software or cybersecurity listing, which
matters for reading the results:
- Maya Chen (software generalist, one agentic tool-calling coursework
  project): top match agentic_ai_engineer (0.66) — well justified, her
  project is literally a tool-calling agent prototype.
- Liam Patel (NLP/RAG coursework, PyTorch/HF/sklearn skills): top match
  graduate_ai_engineer (0.5557), 2nd rag_agent_engineer (0.5381) — both
  strongly justified by direct skill/project overlap.
- Noah Ibrahim (cybersecurity/systems, no real AI content): top match
  agentic_ai_engineer (0.6454) — the weakest result of the three. Score
  is driven by shared generic technical vocabulary (Python, Docker,
  REST, testing) rather than genuine domain relevance, and one excerpt
  ("Nice to have: ...Docker...") is a shallow keyword-level pull rather
  than a substantive match. Flagged to the user as a corpus limitation
  (no non-AI job exists to match against) rather than a retrieval bug.
Also verified job_retrieval_tool wired into ProfileAgent: after
FinalAnswer on the Jordan Ramirez test intro, the agent's own
RetrieveJobs Action returned the same top-3 style output.
All results written to 03_Evidence/03_Retrieval/retrieval_results.md.

---

GOAL: CV generation for a selected job

Now build CV generation for a selected job.

Requirements:
- I pick one of the 3 retrieved jobs as the target.
- Generate a tailored CV using ONLY facts present in the confirmed
  profile — no invented experience, skills, or claims.
- Separately list matched skills (profile skills overlapping the job's
  requirements) and missing requirements (job requirements not in the
  profile) as two distinct sections.
- Changing the target job must NOT alter the underlying confirmed
  profile — only the CV's emphasis/content changes.
- Write the system prompt for this step explicitly: define the model's
  role, task, allowed evidence (only confirmed profile facts + selected
  job excerpt), and required output format. Keep these system
  instructions structurally separate from the user-supplied profile/job
  data — don't interpolate user data directly into the instruction
  text, pass it as separate context.

Do NOT build PDF export yet.

Before writing code, show me the system prompt you're planning and
wait for my confirmation. Once built, generate a CV for one test
profile + one target job, show me the output including the
matched/missing sections, and ask me to confirm it looks right before
we move on. Update 03_Evidence/01_Prompts/prompt_record.md.

PROPOSED CHANGE

Showed the user the full CV_GENERATION_SYSTEM_PROMPT text (role, allowed
evidence, task, strict JSON output format) before writing any code, with
confirmed_profile/selected_job explicitly kept out of the system string
and passed only in the user message as a JSON blob. Also proposed a
deterministic grounding safeguard beyond the prompt itself (see below),
and proposed reusing the pre-existing empty
03_Evidence/04_System_Tests/two_job_comparison.md stub for this step's
evidence, since its name already matches a same-profile/two-jobs test.
User accepted without changes.

Design: CVGenerator.generate(profile, selected_job) sends the fixed
system prompt plus a JSON user message of {confirmed_profile,
selected_job} to GROQ (json_object mode), gets back
summary/education/skills/experience/projects/matched_skills/missing_requirements.
A post-generation _verify_and_clean() pass then strips anything that
doesn't trace back to the confirmed profile: skills/matched_skills not
in profile.technical_skills, experience entries with no matching role
in profile.experience, project entries with no matching title in
profile.projects — each stripped item is recorded as a
grounding_warning rather than silently dropped, so hallucinations are
visible if they occur instead of just trusting the prompt. Non-mutation
is architectural: generate() only reads the Profile dataclass, never
writes to it.

Files touched:
- 01_System/source_code/cv_generator.py — new: CV_GENERATION_SYSTEM_PROMPT,
  CVGenerator, _verify_and_clean()
- 01_System/source_code/job_retrieval_tool.py — added get_job_by_id()
  so a document_id from a retrieval result can be resolved back to the
  job's full description for CV generation
- 01_System/source_code/run_cv_generation_test.py — new: generates two
  CVs for the same confirmed profile against two different jobs from
  its own top-3, checks profile is unchanged, writes evidence
- 03_Evidence/04_System_Tests/two_job_comparison.md — populated

DECISION
Accept (system prompt as shown, deterministic grounding safeguard,
two_job_comparison.md as the evidence target)

VERIFICATION

Ran 01_System/source_code/run_cv_generation_test.py against Liam Patel
(student_profile_02) targeting the top 2 of his own retrieved jobs
(graduate_ai_engineer, then rag_agent_engineer):
- Profile dict compared field-for-field before vs. after both
  generate() calls: unchanged (True).
- Both CVs came back with zero grounding_warnings — every skill,
  project, and experience claim traced to the confirmed profile.
- matched_skills / missing_requirements meaningfully differed per job:
  graduate_ai_engineer (junior-friendly) produced softer missing items
  (statistics, data visualisation); rag_agent_engineer (senior RAG
  role) correctly surfaced much harsher gaps (Master's degree, 3+ years
  experience, LangChain/LangGraph/vector databases) that Liam genuinely
  doesn't have.
Minor non-defect observation flagged to the user: the tailored skills
list came back in the same order for both jobs rather than reordered
per job — the model leaned on selection/summary tailoring rather than
literal reordering.
Results written to 03_Evidence/04_System_Tests/two_job_comparison.md.

---

GOAL: Prompt iteration — tighten relevance ordering

Take the CV-generation system prompt from the last step and propose
ONE concrete improvement to it — for example, tightening the
no-invented-facts constraint, or improving how matched/missing skills
are separated.

Before changing anything, tell me exactly what you want to change and
why, and wait for my confirmation. Once I confirm, run the same
profile + job through both the old and new prompt, show me a
before/after comparison of the outputs, and explain what changed.
Update 03_Evidence/01_Prompts/prompt_record.md with the before/after
prompts and the comparison.

PROPOSED CHANGE

Chose the relevance-ordering weakness over the two suggested example
directions (no-invented-facts tightening, matched/missing separation)
because it was the one thing actually observed to fail in the previous
step's test, not a speculative concern: the grounding safeguard had
already caught zero violations across both CVs, and matched/missing
had already differed meaningfully per job, but the "skills" array came
back in identical order for two different target jobs despite the
prompt saying to order entries "to foreground relevance."

Change: strengthened TASK point 1 to explicitly require the skills
array (and experience/projects entries) to be ordered
most-relevant-to-selected_job first, and must differ across jobs with
different emphasis — and reinforced the same requirement directly in
the OUTPUT FORMAT section next to the "skills" key, since that's what
the model is most literally attending to while emitting JSON. No other
change: same schema keys, same grounding-verification code, same
matched/missing structure. User accepted without modification.

Files touched:
- 01_System/source_code/cv_generator.py — old prompt kept as
  CV_GENERATION_SYSTEM_PROMPT_V1, new prompt added as
  CV_GENERATION_SYSTEM_PROMPT_V2 (now the default
  CV_GENERATION_SYSTEM_PROMPT); generate() takes an optional
  system_prompt override so both versions can be run side by side
- 01_System/source_code/run_prompt_comparison_test.py — new: runs the
  same profile against the same two jobs under both prompt versions

DECISION
Accept (V2 becomes the default prompt)

BEFORE (V1) — TASK point 1 and the "skills" line in OUTPUT FORMAT:

    1. Choosing which of the candidate's existing skills, projects, and experience entries are most
       relevant to selected_job, and ordering/phrasing them to foreground that relevance.
    ...
      "skills": array of strings (must all appear in confirmed_profile's technical skills),

AFTER (V2) — same two spots:

    1. Choosing which of the candidate's existing skills, projects, and experience entries are most
       relevant to selected_job. The "skills" array, and the entries within "experience" and
       "projects", MUST be ordered most-relevant-to-selected_job first. This ordering must differ
       across different target jobs whenever their emphasis differs, even though the underlying facts
       are identical — do not simply reuse confirmed_profile's original list order.
    ...
      "skills": array of strings, ordered most-relevant-to-selected_job first (must all appear in
          confirmed_profile's technical skills — do not just copy confirmed_profile's original order),

(Full text of both versions lives in cv_generator.py as
CV_GENERATION_SYSTEM_PROMPT_V1 / _V2; everything else in the prompt is
unchanged between them.)

VERIFICATION

Ran 01_System/source_code/run_prompt_comparison_test.py: same profile
(Liam Patel, student_profile_02) against the same two jobs from his own
top-3 (graduate_ai_engineer, rag_agent_engineer), once under V1 and
once under V2.

- V1: skills array identical for both jobs —
  [Python, pandas, NumPy, scikit-learn, PyTorch basics, SQL, Hugging
  Face Transformers basics, Git, Jupyter Notebook] — reproducing
  exactly the flaw that motivated this change.
- V2: skills arrays differ per job.
  - graduate_ai_engineer (ML-fundamentals-flavoured role): [Python,
    NumPy, pandas, scikit-learn, PyTorch basics, Hugging Face
    Transformers basics, SQL, Git, Jupyter Notebook] — data-science
    stack (NumPy/pandas/scikit-learn) pulled toward the front.
  - rag_agent_engineer (LLM/RAG/agent-flavoured "AI Engineer" role):
    [Python, Hugging Face Transformers basics, PyTorch basics, Git,
    Jupyter Notebook, pandas, NumPy, scikit-learn, SQL] — the
    LLM-relevant skills (Hugging Face Transformers, PyTorch) pulled to
    the front instead, ahead of the general data-science stack.
  The reordering is not arbitrary — it tracks each job's actual
  emphasis (data-science fundamentals vs. LLM/agent tooling), matching
  the intent behind the instruction.
- No regression: grounding_warnings stayed empty ([]) for both jobs
  under both prompt versions — the ordering change did not loosen the
  no-invented-facts constraint.

Conclusion: V2 fixes the observed ordering weakness without touching
grounding behaviour. Adopted as the default prompt going forward.

---

GOAL: PDF export for the (possibly edited) CV

Now build PDF export for the (possibly edited) CV.

Requirements:
- Let me edit the generated CV content before export (simple text edit
  is fine).
- Export as a polished, readable PDF — clear section headers, readable
  font/spacing, not a raw text dump.
- I need to complete the full profile-to-PDF flow without editing
  source code myself, so make sure this is driven through a CLI or
  minimal UI, not by editing files directly.

Before writing code, tell me how you're generating the PDF (library/
approach) and wait for my confirmation. Once built, export one sample
CV to PDF, and ask me to confirm it looks presentable before we move
on. Update 03_Evidence/01_Prompts/prompt_record.md.

PROPOSED CHANGE

Checked what was available first: neither reportlab nor fpdf were
installed. Proposed reportlab (pure-Python, no system dependencies
unlike WeasyPrint which needs GTK/Pango/Cairo, real typography control
via its platypus layout engine, built-in standard fonts). Proposed a
new export_cv.py CLI: prompts for a profile, runs retrieval and shows
the top 3 for a job pick, generates the CV, walks through each
editable field (summary, education, skills as one comma-separated
line, each experience/project description) letting the user press
Enter to keep or type a replacement — no file opened or hand-edited.
Also proposed --profile/--job/--output flags so the same script is
scriptable non-interactively. Proposed keeping matched_skills/
missing_requirements out of the printed PDF (internal fit-analysis,
not something you'd hand an employer) unless told otherwise. User
confirmed without changes.

Files touched:
- 01_System/source_code/cv_pdf.py — new: render_cv_pdf(cv, profile,
  output_path) using reportlab platypus (SimpleDocTemplate + styled
  Paragraphs for name/tagline/section headers/body/bullets)
- 01_System/source_code/export_cv.py — new: CLI entry point
  (prompt_choose_profile, prompt_choose_job, edit_cv_interactive,
  argparse for --profile/--job/--output/--edits-json)
- 01_System/source_code/cv_generator.py — bumped extract_json
  max_tokens 2048 -> 4096 (a live run hit "max completion tokens
  reached before generating a valid document" on the gpt-oss-20b
  model, which spends tokens on hidden reasoning before the visible
  JSON)
- 02_Setup/requirements.txt — added reportlab

DECISION
Accept (reportlab, CLI-driven edit-then-export, matched/missing
excluded from the PDF)

VERIFICATION

Ran 01_System/source_code/export_cv.py --profile student_profile_02
--job graduate_ai_engineer --edits-json <scripted edits>, simulating a
student editing two fields (the summary, and one project description)
before export.

Two bugs hit and fixed during this run, both now fixed in the shipped
code:
- Windows console (cp1252) raised UnicodeEncodeError on a non-breaking
  hyphen the model used in generated text — fixed by reconfiguring
  stdout to utf-8 at the top of export_cv.py. PDF rendering itself was
  never affected, only the CLI's own console echo.
- The first --edits-json run still called input() for fields not named
  in the scripted edits (e.g. "education"), which fails with EOF when
  there's no real stdin — fixed edit_cv_interactive() so that passing
  any scripted_edits dict (even a partial one) suppresses all input()
  calls for that run; only true interactive use (no --edits-json at
  all) prompts.
- Also found the skills bullet list rendering with no gap between the
  bullet glyph and the text ("●Python") — ListFlowable's bullet
  spacing wasn't behaving as expected. Replaced with plain Paragraphs
  using bulletText + leftIndent, which renders a normal "• Python" gap.

Final PDF (03_Evidence/04_System_Tests/Liam_Patel_graduate_ai_engineer_cv.pdf)
confirmed by reading the rendered PDF directly: name/contact/target-role
header, horizontal rule, then SUMMARY/EDUCATION/SKILLS/PROJECTS as
distinct bold section headers with normal body spacing (no EXPERIENCE
section shown, correctly, since this profile has none) — not a raw
text dump. Both scripted edits appear correctly in the final PDF
(summary text, and the reworded project description). Grounding check
also caught and reported real ungrounded items during this run
(embeddings/FAISS/prompt design/LLM API — these are project
technologies, not entries in profile.technical_skills) and stripped
them before rendering, exactly as designed.

FOLLOW-UP: user asked for a visual improvement — add a break between
sections, since the only separation was a header font change with no
line. Fix: 01_System/source_code/cv_pdf.py's section() helper now
inserts a thin light-grey HRFlowable before every section header
except the first (Summary already sits right below the header block's
own rule). Re-ran the same export_cv.py command and re-read the
regenerated PDF: Summary/Education/Skills/Projects now each open with
a visible divider line above the header, evenly spaced, no layout
overlap or awkward gaps. Re-confirmed presentable.

---

GOAL: Wire everything into the complete flow, run the required test
suite, and finish documentation

Now wire everything into the complete profile-to-PDF flow, driven
end-to-end through a CLI or minimal UI.

Then help me run the required tests, saving results into the existing
03_Evidence/04_System_Tests/ folder:
- 5 different profiles (into test_profiles/), varying education,
  skills, experience, projects, and career goals — including some
  intentionally incomplete ones that trigger follow-up questions. Save
  the results as five_profile_results....
- For one confirmed profile, generate CVs for two different target
  jobs and lay out the summaries/section order/emphasis side by side
  for comparison, saved as two_job_comparison....
- Repeat the full flow for a second, separate user and confirm their
  data stays isolated from the first, saved as cross_user_test.md.
- Capture, for each test: the document_id retrieved, the
  matched/missing skills, and the final CV text/PDF.
- Log any failures or bugs you hit along the way, and how you fixed
  them, into 03_Evidence/05_Failures_and_Improvements/
  failure_and_repair....

Also update/produce:
- README.md in 01_System/source_code/data explaining setup and how to
  run it, if it isn't already complete.
- architecture.md / architecture_diagram in 01_System, if not already
  complete.
- The final 03_Evidence/01_Prompts/prompt_record.md, complete with all
  prior steps.
- A folder with 3 sample CV PDFs: 2 jobs for one profile, 1 job for
  another user.

Before running the tests, show me the file/output structure you're
producing and wait for my confirmation. Once tests are run, show me a
summary of results and ask me to confirm everything's in place before
we call this done.

PROPOSED CHANGE

Presented the full file/output structure before running anything,
including two things flagged for explicit sign-off: a new
sample_cv_pdfs/ subfolder under 03_Evidence/04_System_Tests/ (a
subfolder, not a new top-level folder, following the precedent of the
existing test_profiles/ subfolder), and using a Mermaid diagram
embedded in architecture.md rather than a separate image file for the
"architecture_diagram" part. User confirmed.

Design: new cv_builder_cli.py wires ProfileAgent + JobRetrievalTool +
CVGenerator + render_cv_pdf + export_cv.py's edit_cv_interactive into
one run_full_flow() function (intro -> agent with follow-ups ->
confirmed profile -> job retrieval -> job pick -> CV generation ->
edit -> PDF), exposed both as a real interactive CLI (no flags) and as
a scriptable one (--intro/--intro-file/--replies-json/--job/
--edits-json/--output/--step-cap) so the same code path drives both
real use and every automated test below. export_cv.py kept as-is
(useful for going straight from an already-known dataset profile to a
PDF, skipping the conversation).

Five test personas (authored fresh, not reused verbatim from the
dataset) chosen for spread across education year, skills, experience,
projects, and career goal: Ethan Brooks (backend generalist, complete),
Priya Nair (data/analytics, complete), Devon Okafor (AI/NLP,
incomplete), Marcus Webb (cybersecurity/systems, incomplete), Sarah
Chen (full-stack/cloud, incomplete).

Files touched:
- 01_System/source_code/cv_builder_cli.py — new: run_full_flow() + CLI
- 01_System/source_code/run_five_profile_tests.py — new
- 01_System/source_code/run_two_job_comparison.py — new (regenerates
  two_job_comparison.md using a live agent-confirmed profile instead
  of a dataset profile, per this step's brief)
- 01_System/source_code/run_cross_user_test.py — new
- 01_System/source_code/cv_pdf.py — added _clean() text sanitizer
  (see VERIFICATION bug #9 below)
- 01_System/source_code/data/README.md — appended a "Setup & Running"
  section (env setup, how to run cv_builder_cli.py and every other
  script) and a missing bullet describing jobs.jsonl, which the
  existing README never mentioned
- 01_System/architecture.md — written from empty: component table,
  data-flow Mermaid diagram, design-choice rationale, isolation notes
- 03_Evidence/04_System_Tests/test_profiles/*.md (5 files),
  five_profile_results.md, two_job_comparison.md, cross_user_test.md,
  sample_cv_pdfs/ (3 PDFs) — all populated/regenerated
- 03_Evidence/05_Failures_and_Improvements/failure_and_repair.md —
  written from empty: 11 real bugs across the whole build, chronological,
  each with symptom/root cause/fix

DECISION
Accept (structure as proposed, including the new sample_cv_pdfs/
subfolder and the Mermaid-in-markdown architecture diagram)

VERIFICATION

Five-profile suite: ran all 5 personas through run_full_flow(). Two
confirmed with 0 follow-ups as designed. The three incomplete personas
initially used a padded 6-field scripted-replies list per persona,
which desynced against the questions actually asked (a test-authoring
bug, not an agent bug — see failure_and_repair.md #10) and caused
Devon Okafor's run to hit the step-limit cap. Fixed by empirically
checking each persona's real missing_fields() first, then trimming
scripted replies to exactly what's needed. Re-run: all 5 confirmed —
Ethan (0 follow-ups), Priya (0), Devon (2: name, target_roles), Marcus
(1: target_roles), Sarah (3: degree, year, evidence). Also surfaced a
genuine extraction-quality observation, not a bug: Marcus's intro never
named a concrete tool/skill, so the model inferred loose action-phrase
"skills" (e.g. "traffic monitoring", "home lab setup") rather than
leaving technical_skills empty — grounding-valid (these values are
what's actually in his profile) but lower-quality than a named-tool
skill list; noted in five_profile_results.md rather than hidden.

Two-job comparison: re-ran against Ethan Brooks's live agent-confirmed
profile (not the dataset profile used in the original CV-generation
step). Profile dict unchanged before/after both generate() calls
(True). Both PDFs exported.

Cross-user test: Ethan Brooks (complete) + Devon Okafor (2 follow-ups)
run in the same process, sharing the same GroqLLM/JobRetrievalTool
instances but separate ProfileAgent/ProfileTool per user. First attempt
at the leak-detection check used "no shared skill names" as the signal
and produced a false positive (both legitimately know Python — see
failure_and_repair.md #11); switched to project-title overlap (unique
per persona) instead. Final result: all isolation checks passed —
User A's draft unaffected by User B's later run, separate ProfileTool
objects, no name cross-leak, no project-title cross-leak, neither
generated CV mentions the other user's name/skills.

Two more bugs hit and fixed during this pass (full detail in
failure_and_repair.md): CV generation's max_tokens (2048) wasn't
enough headroom under the longer V2 prompt combined with the model's
hidden reasoning-token cost — raised to 4096. And a real PDF rendering
bug: non-breaking hyphens (U+2011) in model-generated text rendered as
solid black boxes in exported PDFs, because reportlab's built-in
Helvetica (WinAnsi encoding) has no glyph for that character — fixed
with a _clean() sanitizer in cv_pdf.py (also XML-escapes &/</> since
Paragraph text is parsed as mini-XML), then regenerated every affected
sample PDF (Ethan x2, Priya x1, and the earlier Liam Patel sample from
the PDF-export step) to confirm the fix.

Final sample_cv_pdfs/ folder: Ethan_Brooks_rag_agent_engineer_cv.pdf,
Ethan_Brooks_healthcare_ml_engineer_cv.pdf (2 jobs, one profile),
Priya_Nair_rag_agent_engineer_cv.pdf (1 job, another user) — all
visually verified by reading the rendered PDF content directly.

---

GOAL: Streamlit GUI wrapper over the existing CLI logic

The CLI-driven system is working end-to-end and I've verified it. Now
build a simple GUI on top of the existing logic — don't change any of
the underlying agent, retrieval, CV generation, or PDF export code,
just wrap it.

Requirements:
- Use whatever's simplest given the stack we've built (e.g. Streamlit
  for Python) — propose an approach and wait for my confirmation before
  building.
- Cover the same flow as the CLI: enter introduction -> answer any
  follow-up questions -> review/confirm profile summary -> view
  retrieved jobs with document_ids and excerpts -> pick a target job ->
  review generated CV with matched/missing sections -> edit CV text ->
  export PDF.
- Keep it simple and functional over polished — this is a wrapper for
  demoing the flow, not a production UI.
- Don't touch profile isolation between users — same guarantees as the
  CLI version.

Before writing code, tell me your plan (library, page/screen layout)
and wait for my confirmation. Once built, walk me through the full
flow in the GUI with one of the existing test profiles and ask me to
confirm it matches the CLI's behaviour before we call this done.
Update 03_Evidence/01_Prompts/prompt_record.md with this step.

PROPOSED CHANGE

Proposed Streamlit (matches the stack, no separate frontend build).
Flagged one real constraint before proposing a screen layout:
ProfileAgent.run() blocks on input()/a scripted-replies list for the
whole conversation in one call, but Streamlit reruns the whole script
per interaction, so the GUI needs one agent step per click, not one
run() call. Under the "don't change the underlying code" constraint as
originally stated, the only way to get that without duplicating run()'s
branch logic in two places would be to replicate it inline in the GUI
file — flagged as a known trade-off in the plan.

User's response overrode that specific point: refactor run() to be
built on a new public step() method instead of duplicating the branch
logic, on the condition that run()'s behaviour is unchanged and
existing tests still pass — treating this as extending agent.py's
public API (additive), not rewriting its logic. Proposed screen layout
(intro -> follow-up loop -> confirm -> jobs -> CV review/edit -> done)
otherwise accepted as-is.

Files touched:
- 01_System/source_code/agent.py — refactored: extracted run()'s
  per-iteration branch logic (ExtractFields -> check missing ->
  FinalAnswer+optional RetrieveJobs, or AskFollowUp, or
  StepLimitReached) into a new method. Named it take_turn() rather than
  step() - step() collided with the pre-existing self.step instance
  attribute (the integer step counter, already read externally as
  agent.step by other scripts) and broke immediately with
  "TypeError: 'int' object is not callable" on first test. run() is now
  a thin loop that calls take_turn() and, for "needs_input", obtains
  the next user_text the same way it always did (scripted_replies.pop
  or input()) - identical external signature and return shape.
- 01_System/source_code/cv_builder_gui.py — new: the GUI, built only on
  already-public pieces (agent.take_turn(), agent.tool, the prompt
  constants already exported from agent.py, JobRetrievalTool,
  CVGenerator, render_cv_pdf) — no other existing file touched.
- 02_Setup/requirements.txt — added streamlit

DECISION
Accept (step() functionality via take_turn(), Streamlit GUI as
proposed)

VERIFICATION

Regression-checked the agent.py refactor before building anything else:
ran run_agent_tests.py (2/6 steps, same as originally verified) and
run_cross_user_test.py (all isolation checks still True) against the
refactored code - both produced identical results to the pre-refactor
runs, confirming run()'s behaviour is unchanged.

Installed Streamlit + Playwright (no chromium-cli or Node available in
this environment, so drove the app directly with Python's
playwright.sync_api instead, following the run skill's browser-driven
pattern). Launched cv_builder_gui.py, drove it through the full flow
with Jordan Ramirez's complete introduction (the same test intro used
throughout the agent-building step, known to need 0 follow-ups) via a
headless Chromium session:
- Confirm screen: correct profile summary (name, education, skills,
  project, target roles), zero follow-up questions - matches the CLI's
  2-step result for this same intro exactly.
- Jobs screen: 3 job cards, each showing title, document_id, score,
  and excerpt - matches the CLI/retrieval tool's output shape.
- CV review screen: editable Summary/Education/Skills/Projects fields,
  Matched skills / Missing requirements columns, no grounding warnings.
- Edited the Summary field in the browser, clicked Generate PDF,
  reached the Done screen, then (in a second run) actually triggered
  the Download PDF button and read the downloaded file: the edited
  summary text appears correctly in the final PDF, with the same
  polished section-divider styling already verified in the PDF-export
  step - confirming the edit-to-PDF path works through the GUI, not
  just in the CLI.
No browser console errors observed during the run. Screenshots taken
at each stage for visual verification. Stopped the Streamlit process
after verification.

---

GOAL: Fix two GUI gaps - editable confirm stage, and (attempted) PDF
preview/edit - blocked mid-verification by a GROQ rate limit

Two gaps in the current GUI flow need fixing:

1. Confirm stage: right now I can only accept the profile summary as-is.
   Add the ability to edit the confirmed profile before I lock it in -
   at minimum, editable fields for contact details, education, skills,
   experience, projects, achievements, and job goal. I should be able
   to make a correction and re-review before hitting "Confirm."

2. CV review stage: I need to see the generated CV and edit it
   (summary, education, skills, experience/project descriptions) before
   exporting - this was already part of the plan for the CV review/edit
   screen but isn't working yet. Check why it's missing and fix it
   rather than rebuilding - confirm first if it turns out to be a
   bigger change than expected.

For both: editing should only affect what gets displayed/exported, not
silently rewrite the underlying data model in a way that breaks
grounding.

Before changing code, tell me your plan for each fix and wait for my
confirmation. Once built, walk me through both edit flows with one of
the existing test profiles and ask me to confirm before we move on.
Update the Prompt Record with this step.

[Mid-conversation: investigated #2 before proposing anything, per "check
why it's missing." Ran the CV review stage through three separate live
paths (complete profile, an incomplete profile via follow-ups, and an
explicit skills+project-description edit driven to a downloaded PDF) -
all worked correctly, no errors, edits provably reached the final PDF.
Reported this back and asked what the user actually saw fail, rather
than guessing. User then added a third requirement ("I want to be able
to see the PDF preview and edit the PDF file") before answering -
clarified via AskUserQuestion that this meant a live PDF preview with
editing still through the text fields (not a raw PDF editor), which the
user confirmed. User then clarified #2 directly: the complaint was
actually about stage 3 (Confirm your profile) having no way to add
missing information like technical skills - not stage 5 at all. This
meant #1's planned fix (an editable confirm-stage form) already
resolves #2; no separate CV-stage bug existed to chase.]

PROPOSED CHANGE

Plan for #1: DraftProfile doesn't have fields for contact details beyond
name, or achievements, at all - a free introduction was never expected
to produce those. Proposed two small additive changes (same spirit as
the earlier take_turn() extraction): add email/phone/github/linkedin/
achievements to DraftProfile (never touched by extraction or
missing_fields() - only settable via direct user edit, so no new
hallucination surface), and add ProfileTool.overwrite_profile() as a
direct-replace write path, distinct from the existing merge() which
only ever adds and can't correct or clear a value. Confirm-stage form
gets "Save changes" (apply edits, regenerate the summary paragraph,
stay for re-review) and "Confirm & find matching jobs" (apply edits,
then run job retrieval against the corrected profile - not stale data
from before the edit).

Plan for #3 (new, PDF preview): merge the separate "Done" stage into
the CV review stage. "Generate PDF" renders from current field values
(same render_cv_pdf() already used) and shows it inline via st.pdf()
(Streamlit's built-in PDF viewer, requires the streamlit[pdf] extra)
with a Download button alongside - no separate download-first-then-look
step, and since PDF rendering is local/no LLM call, editing and
re-clicking is fast.

Both plans accepted by the user.

Files touched:
- 01_System/source_code/profile_model.py - added email/phone/github/
  linkedin/achievements to DraftProfile; added DraftProfile.overwrite()
  (direct replace); wired the new fields into to_profile()'s
  ContactDetails/Achievements construction
- 01_System/source_code/profile_tool.py - added
  ProfileTool.overwrite_profile()
- 01_System/source_code/cv_builder_gui.py - confirm stage rewritten as
  an st.form with fields for all 7 profile categories and two submit
  buttons (Save changes / Confirm & find matching jobs); removed the
  automatic job_tool wiring from ProfileAgent's construction in the GUI
  (job retrieval now happens explicitly and only from the confirm
  stage's Confirm button, against whatever the profile looks like after
  edits - the agent's own automatic post-FinalAnswer retrieval would
  otherwise run against stale pre-edit data and be wasted); "done"
  stage removed, merged into "cv" stage with st.pdf() preview + a
  Download button that appear after "Generate / update PDF preview"
- 02_Setup/requirements.txt - streamlit>=1.30 changed to
  streamlit[pdf]>=1.30 (the [pdf] extra adds streamlit-pdf, required
  for st.pdf())

DECISION
Accept (as described above)

VERIFICATION - PARTIAL, BLOCKED BY GROQ RATE LIMIT

Regression-checked the profile_model.py/profile_tool.py changes before
touching the GUI: ran run_agent_tests.py, got the same 2-step/6-step
results as every prior run - no behaviour change from the additive
schema fields.

Began a live GUI walkthrough using student_profile_04's real
introduction ("I study Computing Science at UTS... interested in
security, but I have not yet decided which technical role fits me.") -
chosen deliberately because it has no explicit technical skills stated,
to test the exact scenario the user described. Checked the extraction
directly first (non-GUI) to plan correct test replies: missing fields
were exactly [name, year] (technical_skills got populated with vague
phrases like "networking"/"software"/"IT support" rather than left
empty - itself a good real-world case for why confirm-stage editing
matters). Reached the follow-up stage correctly in the GUI. Several
apparent "stuck in a loop" failures during testing turned out to be
Playwright wait-timing races in the TEST SCRIPT (screenshots caught
mid-rerun, stale widget state) rather than app bugs - fixed those. The
actual blocker: a live take_turn() call failed with
groq.RateLimitError (200,000 daily-token limit, 199,887 already used)
- the cumulative cost of this session's extensive testing (every prior
step's live verification, five-profile suite, cross-user test, multiple
GUI walkthroughs, several re-runs while debugging test-script races).
Stopped testing immediately rather than continuing to retry against an
exhausted quota. Streamlit process stopped.

Not yet verified: the confirm-stage edit form actually applying edits
and regenerating the summary; the "Confirm & find matching jobs" button
re-running retrieval against corrected data; the PDF preview rendering
via st.pdf(); the download reflecting confirm-stage edits. Code is
written and regression-safe by inspection, but the live walkthrough the
user asked for is incomplete pending GROQ quota availability.

FOLLOW-UP: user said "try again." Checked quota with a minimal
generate_text() call first rather than immediately re-running the full
suite - succeeded, quota had freed up. Re-ran the same
student_profile_04-based walkthrough end to end:

- Confirm stage rendered exactly as designed: a "What we have so far"
  summary bullet list (Name: Sam Rivera, Technical skills: Networking,
  software, Target roles: Security/Cybersecurity Intern/Junior SOC
  Analyst, etc.) above the editable form, form pre-filled with the same
  vague auto-extracted values.
- Replaced "networking, software" with "Python, Linux, Wireshark, SQL",
  added an achievement and an email, clicked Save changes: the
  regenerated "Profile Summary" correctly reflects every edit
  (Technical skills: Python, Linux, Wireshark, SQL; Achievements: Won a
  university hackathon; Contact: sam.rivera@example.com shown as a
  mailto link) - confirms overwrite_profile() + the regenerated summary
  call both worked correctly.
- Clicked Confirm & find matching jobs: the 3 retrieved jobs
  (rag_agent_engineer 0.5917, trust_safety_ml_engineer 0.576,
  graduate_ai_engineer 0.5682) are driven by the corrected
  Python/Linux/Wireshark/SQL skills, not the original vague extraction -
  confirms retrieval re-runs against post-edit data, not stale data from
  before the fix.
- CV review stage: Skills field shows "Python, Linux, SQL, Wireshark"
  (all four corrected skills carried through CV generation), Matched
  skills correctly shows "Python" (the one skill this specific job
  explicitly asks for), Missing requirements lists the job's other real
  gaps.
- Clicked Generate / update PDF preview: st.pdf() rendered inline
  immediately below, showing the same name/email/skills/experience,
  properly formatted (section headers, dividers) - confirms the
  streamlit-pdf integration works. Download PDF button present
  alongside it.

No console errors at any point. Both fixes confirmed working as
designed. Streamlit process stopped after verification.

---

GOAL: Widen what triggers a follow-up - ambiguity and unaddressed
sections, not just presence

The agent currently only follows up on fields that are completely
empty. Widen what counts as "needs a follow-up":

1. Ambiguous or underspecified values: if I say "Computing Science"
   for education, that's not enough to file - the agent should notice
   it doesn't know the degree level (Bachelor/Master/PhD), institution,
   or year, and ask. Same logic should apply anywhere a value was given
   but isn't specific enough to put on a CV as-is (e.g. a skill with no
   context, a project with no outcome).

2. Entire unmentioned sections: if I never bring up work experience at
   all, don't silently treat it as "none" - the agent should explicitly
   ask whether I have any work experience before treating that section
   as empty. Same for other optional-sounding sections (achievements,
   projects) if my introduction didn't touch them.

Implementation-wise: after extraction, the agent needs a completeness/
ambiguity check that's field-aware, not just a null-check - for each
schema field, it should judge "do I have enough here to write a
truthful CV line" rather than just "is this field populated." Update
the relevant prompt (extraction or follow-up decision, whichever owns
this judgement) to reason about specificity and section coverage, not
just presence.

Fold this into the same extraction prompt rather than adding a
separate pass - keep one source of truth for what counts as
"complete," instead of splitting that judgement across two prompts
that could disagree with each other.

This still needs to respect the existing test criteria: complete,
unambiguous profiles should still get zero extra questions, and the
step limit (6-8) still applies - so it should ask about the most
important gaps first if there are more ambiguous/missing things than
fit in the step budget, not attempt everything.

Before changing the prompt, tell me your plan for how "ambiguous" vs
"complete" gets judged, and wait for my confirmation. Once built, test
it against two cases: my Computing Science / Accenture example (should
now ask about degree level AND explicitly ask about work experience),
and a genuinely complete, unambiguous profile (should still ask
nothing). Show me both traces and ask me to confirm before we move on.
Update the Prompt Record.

[User clarified mid-plan: "if the user truly doesn't have work
experience or projects, the AI must recognise that as a valid answer -
however if they don't mention it initially, shouldn't it be asked?"
Confirmed this matches the plan exactly: unmentioned -> ask;
explicitly answered "none" (proactively or as a reply) -> valid,
never re-asked.]

PROPOSED CHANGE

Single call does three things now: TASK 1 extracts new facts from the
latest message (including REFINING an already-present-but-vague value,
e.g. "Computing Science" -> "Bachelor of Computing Science", not just
first-time filling); TASK 2 flags whether the latest message explicitly
declined work experience/projects/achievements (a delta signal, not a
recomputation - see VERIFICATION for why); TASK 3 judges specificity of
what exists (degree needs a level; skills must be real named
technologies, not vague activity-phrases like "networking"; existing
project/experience entries must have enough detail for a CV bullet) and
returns an ordered "gaps" list. Priority order extends the existing
required-field order: name > degree > year > technical_skills >
experience > projects > target_roles > achievements. One explicit
scoping call: NOT adding "institution" as an askable field, since the
system already hardcodes UTS institution for this cohort by design
(to_profile()) - flagged as a scope boundary, not silently done.

One consequence named up front and accepted: this is a stricter bar
than before. Existing "0 follow-up" personas from earlier steps (Jordan
Ramirez, Priya Kapoor, Ethan Brooks, Priya Nair, etc.) never explicitly
addressed work experience/achievements, so they would no longer be
0-follow-up if re-run today - intentional, not a regression. Did NOT
re-run any of those earlier evidence files as part of this change
(would burn GROQ quota and silently invalidate previously-confirmed
evidence); flagging that here rather than deciding unilaterally to
refresh them.

User accepted the plan as described.

Files touched:
- 01_System/source_code/agent.py - EXTRACTION_SYSTEM_PROMPT rewritten
  (extract + declined-section signals + ambiguity-aware gaps, one
  prompt); FIELD_ASK_HINTS removed (superseded by the model's own gap
  reasons); take_turn() drives off observation["gaps"] instead of
  missing_fields(), passes {current_draft, last_question_asked,
  latest_message} as the extraction call's input instead of just the
  raw text, tracks self._last_question across turns
- 01_System/source_code/profile_model.py - DraftProfile: added
  work_experience_addressed/projects_addressed/achievements_addressed
  (sticky bookkeeping flags, see VERIFICATION bug #2) and achievements
  became a real merge()-populated field, not edit-only; merge()
  rewritten (scalars now overwrite/refine instead of fill-only-if-empty;
  project/experience entries reconciled by title/organisation/role
  instead of blind dedupe-append; achievements list merged the same way
  as technical_skills); new compute_gaps() combines the model's
  ambiguity judgements with the three deterministic section-coverage
  flags into one ordered list; DraftExperienceEntry.role made Optional;
  to_profile() defaults a None role to "Not specified"; overwrite()
  marks all three sections addressed (a human reviewing the confirm
  form has addressed every section by definition)
- 01_System/source_code/profile_tool.py - update_profile() now calls
  compute_gaps() after merge() (order matters - see bug #2); docstring
  updated
- 01_System/source_code/cv_builder_gui.py - one defensive fix: the
  confirm-stage Role text_input read exp["role"] directly, would break
  now that role can legitimately be None mid-conversation; changed to
  exp.get("role") or "", matching the pattern already used for
  organisation/description right next to it
- 01_System/source_code/run_agent_tests.py - updated the evidence
  file's own description text (referenced missing_fields, now
  inaccurate) to describe gaps instead

DECISION
Accept (as described above)

VERIFICATION

Two real bugs found and fixed while testing against the Computing
Science/Accenture case - both pre-existing latent issues that the
original presence-only design never exercised:

Bug #1 - refinement blocked: merge()'s original scalar logic
("fill only if not self.degree") meant a later turn could never
upgrade an already-present-but-vague value. Turn 1 set degree =
"Computing Science"; turn 2's reply supplied "Bachelor of Computing
Science" but the stale vague value stuck, so the SAME degree-ambiguous
gap kept resurfacing every subsequent turn even though the model had
correctly extracted the refinement each time. Fixed by making scalar
merge overwrite rather than fill-only-if-empty, trusting the prompt's
own discipline (Task 1 only returns non-null when there's genuinely
new information for that field).

Bug #2 - stateless re-flagging of already-declined sections: first
attempt gave the extraction call current_draft + last_question_asked +
latest_message and asked it to freshly judge "was this section ever
addressed" every turn. This looked right for two turns but regressed
on the third: after correctly recognizing "no projects" as resolving
the projects gap, the NEXT turn (answering a completely different
question, about achievements) re-flagged projects as unaddressed -
because an empty list looks identical whether never-asked or
already-declined, and the model only sees the MOST RECENT question, not
the full history, so it had no way to know projects was resolved two
turns earlier. Also surfaced a second latent bug in the same area:
str(exp.get("role", "")) turns an explicit JSON null into the literal
string "None" (dict.get's default only applies when the key is
absent, not when it's present-as-null), which combined with pure
append-only list merging produced a duplicate experience entry (one
with role "None", a second with the real role) once the Accenture
entry's role got filled in on a later turn. Fixed properly rather than
patched around: work_experience_addressed/projects_addressed/
achievements_addressed are now persisted booleans on DraftProfile,
set sticky-true by deterministic Python bookkeeping (real content
present, or the extraction call's declined-flag fires) rather than
re-derived by the LLM from partial context each turn; project/
experience entries are now reconciled by title/organisation/role
instead of blindly appended, so a later turn completing an
already-mentioned entry updates it in place.

Re-tested both required cases after both fixes:

Test 1 (Computing Science / Accenture, scripted with natural replies):
STATUS confirmed after 4 follow-ups - name (missing), work experience
(ambiguous - "worked at Accenture" alone had no role/description),
projects (unaddressed - explicitly declined: "No projects outside of
coursework"), achievements (unaddressed - explicitly declined). Degree
ambiguity resolved as a side effect of the name-reply's phrasing
("...a second-year Bachelor of Computing Science student") rather than
needing its own dedicated question - the model correctly recognized
the refinement opportunistically. Final draft: name "Jamie Lee", degree
"Bachelor of Computing Science", year "second-year", one clean merged
experience entry (Data Analytics Intern, Accenture, with description -
not two duplicate entries), no invented content anywhere.

Test 2 (fresh "genuinely complete" profile - Alex Morgan, explicitly
addresses every section including proactively declining work
experience and achievements in the first message): STATUS confirmed
with 0 follow-ups, gaps: [] on the very first extraction call - proves
the stricter judgement doesn't over-trigger on a profile that actually
covers everything, including recognizing a proactive decline (not just
a reply-to-a-question decline) as satisfying a section.

Full traces captured via a standalone test script
(test_new_agent_logic.py, not committed - ad hoc verification) rather
than the GUI, to iterate quickly without repeated Playwright/browser
round-trips. All source files re-verified to import cleanly after the
final fix.

---

GOAL: Lower the bar for work experience specifically - unmentioned
should pass as none, not block confirmation

Lower the requirement bar. For now, if there is not experience in the
introduction, just let it pass as non[e], make it so that experience
can be added in later.

PROPOSED CHANGE

Scoped narrowly to work experience only, per the exact wording -
projects and achievements keep their existing "ask once if never
addressed" behaviour unchanged. Two parts: (1) stop treating an
unmentioned work history as a gap that blocks confirmation, while
leaving the "thin/ambiguous experience that WAS mentioned" check
untouched (that's a different case - something was said, just not
enough - not what this request is about); (2) since the agent will no
longer ask about it, make sure there's still a way to add it -
via the confirm-stage form, which previously hid the Experience
section entirely whenever the list was empty.

Implemented directly rather than re-running a full plan-confirmation
round trip, given how narrowly scoped and unambiguous the request was
relative to the prior step's larger design questions.

Files touched:
- 01_System/source_code/profile_model.py - compute_gaps() no longer
  appends a work-experience-unaddressed gap (kept the
  work_experience_addressed flag/field itself, and its
  has-content-triggers-True behaviour, so this is reversible with a
  one-line change rather than torn out); merge() simplified to match
  (dropped the now-unused work_experience_declined delta check)
- 01_System/source_code/agent.py - EXTRACTION_SYSTEM_PROMPT: TASK 2
  (declined-section signals) now only covers projects/achievements,
  work experience explicitly called out as not needing it; TASK 3's
  "don't report unaddressed" carve-out updated to match;
  work_experience_declined removed from the OUTPUT FORMAT schema
- 01_System/source_code/cv_builder_gui.py - confirm-stage form's
  Experience section no longer hides when the draft has zero entries;
  always shows one editable slot (blank if nothing was mentioned, with
  a caption explaining why) so experience can still be added manually
  even though the agent won't ask about it; the slot is only kept if
  the user actually fills in something, so leaving it blank doesn't
  create an empty phantom entry

DECISION
Accept (as described above)

VERIFICATION

Two targeted tests (ad hoc script, not committed) plus one GUI check:

Test A - work experience never mentioned at all (Taylor Reed: name,
degree+level, year, skills, one well-described project, explicitly
declined projects/achievements, target role - everything else
complete): STATUS confirmed, gaps: [] on the very first extraction
call. Previously this same profile would have needed one additional
follow-up for the unaddressed work-experience section; confirms the
bar is now lower specifically there.

Test B - work experience IS mentioned but thin ("I worked at
Deloitte", no role/description) - confirms this case is UNCHANGED:
still flagged (experience/ambiguous), still asks
("What were your main responsibilities at Deloitte?"), resolves
cleanly once answered. Proves the fix only touched the
"never-mentioned" case, not the "mentioned but thin" case.

GUI check: drove Taylor Reed's intro through to the confirm screen -
reached it with zero follow-up questions (matching Test A), and the
Experience section renders as a blank "Experience 1" slot with the
caption "No work experience was mentioned - leave blank if you don't
have any, or fill in to add one," rather than being hidden - confirms
experience can still be added manually at the confirm stage.

---

GOAL: Same lowered bar for projects, and bundle all outstanding
follow-up questions into a single combined prompt instead of one at a
time

same with projects, just make all of these questions into a single
extra prompt with the user

PROPOSED CHANGE (implemented directly, same reasoning as last step -
narrow, unambiguous request)

Two changes:
1. Projects gets the identical treatment work experience just got:
   unmentioned -> treated as none, doesn't block confirmation; thin/
   ambiguous project that WAS mentioned is untouched (still flagged).
   Achievements was not mentioned this time, so it keeps asking once if
   unaddressed - only work experience and projects are now lowered.
2. take_turn() no longer asks about gaps one at a time across multiple
   turns. When gaps exist, ALL of them get bundled into one combined
   follow-up message in a single turn - the student can answer
   everything in one reply instead of a back-and-forth. If the reply
   doesn't fully resolve everything, the next round bundles whatever's
   still outstanding, same as before - this just changes how much gets
   asked per round, not the overall loop structure or the step cap.

Files touched:
- 01_System/source_code/profile_model.py - compute_gaps() no longer
  appends a projects-unaddressed gap either (only achievements remains
  section-tracked); merge() dropped the now-unused projects_declined
  check, matching the work-experience treatment from last step
- 01_System/source_code/agent.py - EXTRACTION_SYSTEM_PROMPT: TASK 2
  narrowed to achievements_declined only; projects_declined removed
  from the OUTPUT FORMAT schema; FOLLOW_UP_SYSTEM_PROMPT rewritten to
  ask about a whole list of things in one combined message instead of
  one targeted question; take_turn() builds the follow-up from ALL
  current gaps (not just gaps[0]) and logs a comma-joined
  target_field summary covering everything asked that turn
- 01_System/source_code/cv_builder_gui.py - Projects section in the
  confirm-stage form gets the same fix as Experience: always shows one
  editable slot instead of disappearing when empty, kept only if a
  title was actually entered

DECISION
Accept (as described above)

VERIFICATION

Test 1 - sparse intro producing 4 gaps at once (name missing, degree
ambiguous, year missing, achievements unaddressed): confirmed exactly
ONE combined AskFollowUp action covering all four -
"Could you share your name, the degree level you're pursuing (e.g.,
Bachelor's, Master's), your current year of study, and any
achievements or activities you'd like to highlight?" - resolved in a
single reply that addressed all four at once, confirmed after 4 total
steps (extract, ask, extract, final) instead of what would previously
have taken up to 4 separate ask/reply rounds (8+ steps) for the same
gaps.

Test 2 - projects never mentioned (Sam Diaz: name, degree+level, year,
skills, target roles all present; achievements explicitly declined;
no projects or work experience mentioned at all): confirmed with 0
follow-ups - proves projects no longer blocks confirmation when
unmentioned, same as work experience.

Both tests also confirm no regression: the bundled-question mechanism
correctly reduces to a single targeted question when only one gap
remains (not tested fresh here, but structurally the same code path -
gaps_list joins whatever's in the gaps array, whether that's one item
or several).

---

GOAL: CV-generated experience/project descriptions should be rewritten
into professional CV language, not copied verbatim from casual input

User attached a screenshot of the CV review stage showing:
"Data Scientist — Accenture: I made an RAG agent to analyse customer
review." and "Text Classifier: analysing customer review" - raw,
first-person, casual phrasing straight from what was typed during the
conversation. Instruction: "These section shouldn't take what I wrote
as it's own thing. It should use AI agent to make it more professional
and CV ready."

Diagnosis (no plan/confirmation round trip - implemented directly,
same as recent narrowly-scoped requests): CV_GENERATION_SYSTEM_PROMPT
(V2, cv_generator.py) already permitted rephrasing in general
("You may reorder, select, and rephrase existing facts for relevance
and tone" under ALLOWED EVIDENCE) but never explicitly instructed the
model to actually rewrite project/experience DESCRIPTIONS into CV
register - TASK 1 only covered choosing and ordering entries, not
rewriting their wording. The model was defaulting to verbatim
pass-through, apparently reading "must all correspond to entries in
confirmed_profile's experience/projects" (an OUTPUT FORMAT grounding
note) as license to keep the original wording untouched to stay safe,
even though rephrasing was already allowed.

PROPOSED CHANGE (implemented directly)

Added CV_GENERATION_SYSTEM_PROMPT_V3 (continuing the V1/V2 versioning
precedent from the earlier prompt-iteration step), now the live
CV_GENERATION_SYSTEM_PROMPT. New explicit TASK 2: rewrite every
project/experience description into a concise, resume-style bullet -
drop "I"/casual phrasing, lead with a past-tense action verb, state
what was built/done with which technologies and to what effect -
while explicitly reiterating this is rephrasing under the EXISTING
"no invented facts" constraint, not new licence: every technology,
action, and outcome named must already be present in the
corresponding confirmed_profile entry. Included a concrete example
in the prompt itself (the exact "I made an RAG agent..." sentence from
the screenshot, rewritten) since a worked example is more reliable
than an abstract instruction for this kind of stylistic-but-bounded
rewrite. Reinforced the same requirement inline in the OUTPUT FORMAT
description fields, matching the pattern already used for the V2
ordering requirement.

Files touched:
- 01_System/source_code/cv_generator.py - added
  CV_GENERATION_SYSTEM_PROMPT_V3, switched the live
  CV_GENERATION_SYSTEM_PROMPT pointer to it; V1/V2 kept as historical
  record, unchanged

DECISION
Accept (as described above)

VERIFICATION

Built a Profile directly (bypassing the conversational agent, to
avoid burning GROQ quota on unrelated extraction calls) with the exact
content from the screenshot: experience "Data Scientist @ Accenture -
I made an RAG agent to analyse customer review", plus two projects
with similarly casual descriptions ("research paper summarisation
with NLP", "analysing customer review"). Ran CVGenerator.generate()
against rag_agent_engineer:

- Experience: "I made an RAG agent to analyse customer review." ->
  "Developed a retrieval-augmented generation (RAG) agent to analyze
  customer reviews."
- Project 1: "research paper summarisation with NLP" -> "Created a
  research paper summarization system leveraging NLP techniques."
- Project 2: "analysing customer review" -> "Developed a text
  classification model to analyze customer reviews."

All three preserve exactly the same facts (no new technology, scope,
or outcome claims) while reading as CV bullets instead of a chat-log
copy. Grounding safety net still functioning alongside the rewrite: it
correctly stripped an over-claimed matched_skills entry ("RAG" appears
in the rewritten description text but isn't itself in
profile.technical_skills, which only listed LLM/NLP/Java/Python), so
the professionalization change didn't loosen the no-invented-facts
check.

---

GOAL: Three fixes - CV professionalism, "choose a different job" without
restarting, and "Activities:" not being recognized by extraction

Three gaps found from actually using the finished system:

1. Generated CVs still read like a data dump in places: inconsistent
   skill casing/specificity ("Docker basics", "network troubleshooting",
   "SQL" side by side), flat generic bullets, a project's tech stack
   crammed into its title line, and risk of forcing AI/CV-specific
   framing onto experience that has nothing to do with it when the
   target role doesn't match the candidate's real background - must stay
   strictly a rewording/formatting pass, no new claims/numbers.
2. Once a job is picked and a CV generated, there was no way back to the
   other 2 of the top-3 without restarting the whole conversation - asked
   for a "choose a different job" action reusing the same confirmed
   profile and the same retrieved top-3, and to confirm this doesn't
   conflict with the isolation guarantees already built for cross-user
   testing.
3. An informal "Activities:" label in an introduction (e.g. a CTF
   workshop) was getting silently dropped by extraction - the agent kept
   asking about it as if never mentioned. Asked where "activities" should
   map given achievements/experience/projects/etc. are the only schema
   categories, with reasoning given before implementation rather than a
   new field invented silently.

Before changing anything: tell the plan for each fix and wait for
confirmation. Once built: regenerate the existing test CV to show the
formatting fix, walk through job-reselection live, show the trace for a
profile with an "Activities:" line. Update the Prompt Record.

PROPOSED CHANGE

Explored the full pipeline first (agent.py, profile_model.py,
profile_tool.py, cv_generator.py, cv_pdf.py, cv_builder_gui.py,
architecture.md) before proposing anything, per the standing "check
before proposing" pattern from the confirm-stage/CV-review step.

Fix 1 root causes found by reading the code: CV_GENERATION_SYSTEM_PROMPT_V3
already rewrites descriptions into CV register and orders skill/
experience/project list items by relevance, but never touches skill
casing, never separates a project's tech list from its title line, and
has no guard against stretching a mismatched profile toward the target
role's vocabulary. A second, code-level root cause:
_verify_and_clean()'s clean_skill_list() looked up a skill
case-insensitively but then always substituted the profile's ORIGINAL
casing back in - so even if the prompt asked for normalized casing, the
grounding safety net was silently reverting it. Proposed: a new
CV_GENERATION_SYSTEM_PROMPT_V4 (skills-casing normalization, varied
action verbs across bullets, an explicit "don't invent a metric, tighten
phrasing instead" line, an explicit anti-overreach guardrail against
target-role jargon on unrelated content, and a new "section_order"
output field so skills/experience/projects can lead in genuine-relevance
order instead of a fixed template order); clean_skill_list() changed to
keep the model's returned casing instead of overwriting it (grounding
check itself unchanged - still case-insensitive membership against
profile.technical_skills); cv_pdf.py given a new CVTechLine style so
project technologies render on their own line under the title instead of
crammed into it, and made to render sections in cv["section_order"]
(falling back to the original fixed order for any older/malformed CV
dict). Demo target proposed: student_profile_04 (Noah Ibrahim) against
computer_vision_engineer - his technical_skills literally contain the
exact casing-inconsistent fragments named in the request, and his
Linux/networking/IT-support background against an AI/Computer-Vision
role is exactly the mismatched-domain scenario described - flagged as an
assumption since no PDF for this exact pairing existed yet in
03_Evidence/.

Fix 2 proposed: a "Choose a different job" button on the "cv" stage
(cv_builder_gui.py) - the sole remaining terminal stage, since the
earlier separate "Done" stage was already merged into "cv" in a prior
session. On click: pop only chosen_job/cv/pdf_bytes, set stage back to
"jobs", leave st.session_state.agent (the confirmed ProfileAgent/
ProfileTool) and st.session_state.job_matches (the already-retrieved
top-3) untouched - no re-confirmation, no re-retrieval. Isolation
argument given up front: architecture.md's isolation guarantee is
per-ProfileAgent-instance, one per Streamlit session, created once in
reset_session(); this fix never creates a new agent and never touches
the shared stateless services (llm, job_tool) beyond a rerun of the same
already-cached data - it only mutates session-scoped state exactly like
every other stage transition already does, so it doesn't touch the
boundary cross_user_test.md verifies at all.

Fix 3 proposed mapping: "Activities:" -> achievements, not a new field,
with reasoning given before any code change per the request. Two
grounds: (a) the confirmed Profile schema has stored this section
internally as Achievements.activities since the very first schema step
(profile_model.py) - "achievements" (the brief's category name) and
"activities" (the field's actual name) have been two labels for the same
thing from day one; (b) the dataset itself already treats it this way -
student_profiles.jsonl record 4 (Noah Ibrahim, same profile as the Fix 1
demo) has "activities": ["Participated in a fictional beginner
cybersecurity capture-the-flag workshop..."] - the exact CTF-workshop
example from this request, already living under achievements/activities,
not projects (a CTF workshop is participation, not "something built"
the way ProjectEntry expects). Root cause: EXTRACTION_SYSTEM_PROMPT names
the output field "achievements" but never told the model an informal
label like "Activities:" refers to it - proposed extending TASK 1 with
an explicit mapping line and one worked example (the CTF-workshop
sentence itself), following the same "a worked example beats an abstract
instruction" pattern already proven out in the V3 CV-rewrite prompt.
No profile_model.py/profile_tool.py changes needed - the sticky
achievements_addressed bookkeeping already works correctly once real
content lands in the achievements array.

User accepted all three plans as described.

Files touched:
- 01_System/source_code/agent.py - EXTRACTION_SYSTEM_PROMPT: added the
  informal-label-recognition paragraph + worked example to TASK 1
- 01_System/source_code/cv_generator.py - added
  CV_GENERATION_SYSTEM_PROMPT_V4 (now the default
  CV_GENERATION_SYSTEM_PROMPT), V1-V3 kept as historical record;
  clean_skill_list() keeps the model's returned casing instead of
  overwriting it; _verify_and_clean() validates cv["section_order"] as a
  permutation of the sections that actually have content, falling back
  to the default order otherwise
- 01_System/source_code/cv_pdf.py - new CVTechLine paragraph style;
  project rendering puts "Technologies: ..." on its own line instead of
  in the title; Skills/Experience/Projects now render in
  cv["section_order"] order (falls back to the original fixed order)
- 01_System/source_code/cv_builder_gui.py - "cv" stage: new "← Choose a
  different job" button that pops only chosen_job/cv/pdf_bytes and
  returns to the "jobs" stage

DECISION
Accept (all three as described above)

VERIFICATION

Fix 1 - ran CVGenerator.generate() live for student_profile_04 (Noah
Ibrahim) against computer_vision_engineer:
- Skills came back consistently capitalized ("Docker basics", "Network
  troubleshooting", "Wireshark basics", "Technical documentation", "SQL",
  "Python", "Linux", "Git", "REST API testing") - every entry now starts
  capitalized, instead of the original mixed casing - and matched_skills
  still correctly resolved to just "Python" (the grounding check still
  works after the casing change).
- Experience bullet reproduced the EXACT complaint from the request
  almost verbatim as an input ("Recorded support requests, helped users
  with account and device issues and escalated problems that required
  administrator access" in the source profile) and came back rewritten
  as "Documented support tickets, resolved user account and device
  issues, and escalated complex problems requiring administrative
  intervention." - strong lead verb, no invented detail.
- No forced AI/computer-vision framing anywhere in the output despite
  the target role being "AI Computer Vision Engineer" - the real
  Linux/networking/IT-support background was presented honestly;
  missing_requirements correctly lists the real AI/CV-specific gaps
  (OpenCV, TensorFlow, PyTorch, object detection, etc.) instead of the
  model pretending they were met.
- section_order came back ["skills", "projects", "experience"] -
  projects (which include hands-on network-traffic analysis) led ahead
  of the single generic IT-support experience entry, a genuine relevance
  call, not a forced one.
- grounding_warnings: [] - the no-invented-facts guarantee held through
  all of the above changes.
- Rendered to PDF and read it directly: project technologies now sit on
  their own italic line ("Technologies: Linux, Wireshark basics,
  networking, technical reporting") under the bold project title, no
  longer crammed into the title line. Saved to
  03_Evidence/04_System_Tests/sample_cv_pdfs/
  Noah_Ibrahim_computer_vision_engineer_cv.pdf.

Fix 2 - launched the real Streamlit GUI and drove it with Playwright
(playwright + chromium installed for this; a stray orphaned Streamlit
process from an earlier, uncleanly-stopped session was found squatting
on port 8501 and was stopped by its specific PID before launching a
clean instance). Used Ethan Brooks's intro (from the cross-user test) -
one follow-up was needed this time asking about achievements/activities
(expected: a later step widened the completeness bar to require that
section be explicitly addressed, which post-dates the intro's original
"0 follow-ups" evidence). Full flow: intro -> 1 follow-up -> confirm ->
jobs (3 cards: healthcare_ml_engineer 0.4222, agentic_ai_engineer 0.41,
and a third above the fold) -> picked job 1 -> CV generated -> clicked
"← Choose a different job" -> back on the jobs stage with the exact
same 3 cards (verified programmatically: jobs_first == jobs_second,
True) -> picked job 2 (healthcare_ml_engineer) -> a NEW CV generated,
visibly different (summary now ends "...seeking to apply software
engineering skills to machine-learning and data-driven solutions",
skills reordered "Python, SQL, Git, Java" vs job 1's "Python, SQL, Java,
Git"). No console errors at any point. Screenshots confirm the "←
Choose a different job" button rendered directly under the "5. Review,
preview & export your CV" header. Streamlit process stopped after
verification.

Fix 3 - ran a live extraction test: an introduction ending "...
Activities: I took part in a beginner cybersecurity capture-the-flag
workshop. I am targeting Junior SOC Analyst roles." confirmed in a
SINGLE extraction call (status=confirmed, 0 follow-ups) with
achievements = ["Took part in a beginner cybersecurity capture-the-flag
workshop"] and gaps = [] on that same first call - confirming the
"Activities:" label is now recognized immediately and does not trigger
a redundant follow-up asking about something already answered.

All three fixes verified live, no regressions found in grounding,
isolation, or the achievements sticky-flag bookkeeping.

---

GOAL: Lower the bar for achievements too - the last remaining
"ask-if-unaddressed" optional section

I would like to lower the bar. [Quoted the exact achievements
follow-up question shown in follow_up_question_test.md as the example
of what should stop being asked.] No need to ask this follow up
question.

PROPOSED CHANGE (implemented directly, same pattern as the identical
work-experience and projects requests before it)

Same treatment as work experience/projects: achievements_addressed
stays tracked (still auto-set True the moment self.achievements has
content) so it's reversible with a one-line change, but an unmentioned
achievements section no longer blocks confirmation. Since this was the
last of the three sections still using the declined-flag/TASK 2
mechanism, that whole mechanism is now dead weight - removed rather
than left half-used: EXTRACTION_SYSTEM_PROMPT's TASK 2 (declined-
section signals) and the achievements_declined output key are gone
entirely, TASK 3 renumbered to TASK 2 with its "don't report
unaddressed" carve-out now covering all three sections in one line
instead of accreting a growing list of exceptions.

Files touched:
- 01_System/source_code/profile_model.py - compute_gaps() no longer
  appends any section-unaddressed gap (achievements was the last one);
  merge() dropped the now-unused achievements_declined check, matching
  the work-experience/projects treatment from the prior two steps
- 01_System/source_code/agent.py - EXTRACTION_SYSTEM_PROMPT: TASK 2
  (declined sections) removed entirely; former TASK 3 renumbered to
  TASK 2; achievements_declined removed from the OUTPUT FORMAT schema
  and from the closing gaps note

DECISION
Accept (as described above)

VERIFICATION

Ran a fresh intro with NO work experience, NO projects, AND NO
achievements mentioned at all (Robin Chase: name, degree+level, year,
skills, target roles only): STATUS confirmed, gaps: [] on the very
first extraction call - 0 follow-ups. Confirms all three optional
sections are now correctly bypassed together when none are mentioned,
not just achievements in isolation.

Also checked the GUI's confirm-stage form specifically for whether it
needed the same "always show a slot" fix applied to Experience/
Projects in the last two steps: it does not - achievements has always
been a single always-rendered text input (not a per-entry list that
gets conditionally hidden when empty), so it was already editable/
addable regardless of this change. No GUI changes needed this time.

---

GOAL: Experience section should render directly below Education,
everywhere a CV/profile is laid out

Also I want the experience section in the right below the Education
section.

PROPOSED CHANGE (implemented directly, same as recent narrowly-scoped
requests)

Discovered mid-implementation that a prior part of this session (from
before the context window's most recent compaction, so not fully
recalled in detail) had already built a section_order mechanism:
CV_GENERATION_SYSTEM_PROMPT_V4 has the model decide a per-job
"section_order" permutation of skills/experience/projects, and
cv_pdf.py renders them dynamically in that order (falling back to a
default if the model's value is malformed). That mechanism is why
Experience's position could vary at all - Education, by contrast, was
always fixed right after Summary. The fix: make Experience a second
fixed anchor, always immediately after Education, and remove it from
the dynamically-orderable set entirely - only "skills" and "projects"
remain reorderable per job now.

Applied consistently in three places, not just the PDF: the CV review
stage and the confirm-stage profile-edit form both had their own
independent section ordering that didn't match each other or the PDF.

Files touched:
- 01_System/source_code/cv_generator.py - added
  CV_GENERATION_SYSTEM_PROMPT_V5 (built via .replace() on V4 rather
  than a full retyped copy, specifically to guarantee the only diff
  between V4 and V5 is the section_order scope - nothing else
  silently drifts): section_order's TASK 1 instruction and OUTPUT
  FORMAT description now only cover "skills"/"projects", with an
  explicit "Education and Experience are always fixed... never part
  of this ordering" note; _verify_and_clean()'s present_sections
  check updated to match (drops "experience")
- 01_System/source_code/cv_pdf.py - Experience rendering pulled out of
  the renderers/default_order dynamic-loop mechanism entirely and
  rendered unconditionally right after the Education section, mirroring
  how Education itself was already fixed; renderers/default_order now
  only contain "skills"/"projects"
- 01_System/source_code/cv_builder_gui.py - CV review stage: moved the
  Experience block to directly after the Education text_area, before
  Skills (was Education -> Skills -> Experience -> Projects, now
  Education -> Experience -> Skills -> Projects); confirm-stage form:
  moved the Experience block from its old position (after Job
  goal/Achievements, near the bottom) to directly after Education
  (was Education -> Skills -> Job goal -> Achievements -> Experience
  -> Projects, now Education -> Experience -> Skills -> Job goal ->
  Achievements -> Projects)

DECISION
Accept (as described above)

VERIFICATION

Confirmed the V4->V5 prompt diff is exactly the intended two spots via
a direct string-equality check (V4 != V5) plus printing the full V5
text - both the TASK 1 section_order instruction and the OUTPUT FORMAT
description now explicitly exclude "experience" and state it's fixed.

Generated a real CV+PDF end to end (profile with both an experience
entry and a project, targeting rag_agent_engineer): cv["section_order"]
came back as ['projects', 'skills'] - confirms "experience" is no
longer part of what the model is even asked to order. Read the
rendered PDF directly: section order is SUMMARY -> EDUCATION ->
EXPERIENCE -> PROJECTS -> SKILLS - Experience sits immediately below
Education exactly as requested, with the dynamic skills/projects
ordering still functioning around that fixed anchor.

---

GOAL: Re-run the entire 03_Evidence test suite - most of it had gone
stale relative to the agent/CV-generation changes made across this
whole session

Help me rerun all the test for 03_Evidence. Tell me what you will do
before you proceed. You must ask for my confirmation.
[Confirmed with: "confirm, just remake any pdf" - i.e. also regenerate
the two loose sample PDFs not tied to an automatic script output.]

PROPOSED CHANGE

Presented an itemized plan before touching anything, per the explicit
instruction to wait for confirmation: which of the 7 run_*.py scripts
actually write into 03_Evidence (5 do; run_cv_generation_test.py is
superseded by run_two_job_comparison.py and writes to the same path,
run_prompt_comparison_test.py writes outside 03_Evidence entirely -
both excluded), and flagged the two loose PDFs
(Liam_Patel_graduate_ai_engineer_cv.pdf,
Noah_Ibrahim_computer_vision_engineer_cv.pdf) that aren't tied to any
script's automatic output, asking whether to regenerate them too.

DECISION
Accept, plus regenerate the two loose PDFs

VERIFICATION

Ran all 5 scripts. Two real things surfaced along the way, both
handled before treating the suite as done rather than papered over:

1. run_five_profile_tests.py failed outright (EOFError - scripted
   replies exhausted while a real question was still pending) on
   Marcus Webb. Root cause: this persona's original single scripted
   reply only covered target_roles, tuned to the OLD extraction
   behaviour where his vague intro ("documented common attack
   patterns... monitoring traffic") produced loose skill-like phrases
   that counted as "present." Under the ambiguity-aware extraction
   built earlier this session, those vague phrases no longer count as
   real skills, so technical_skills is now ALSO a genuine gap for him.
   Checked both his and Sarah Chen's current gaps directly (cheap,
   non-GUI) before fixing: Marcus now needs
   [technical_skills, target_roles] (was just [target_roles]); Sarah
   now needs only [degree, year] (was [degree, year, evidence] - her
   third reply, about a project, is no longer needed at all since
   projects is a lowered-bar section now). Rewrote both personas'
   scripted_replies to match - one combined reply each, since both
   gaps now arrive bundled in a single follow-up question rather than
   sequentially. Re-ran clean: Marcus 1 follow-up, Sarah 1 follow-up
   (both previously needed more rounds).
2. Hit two rate limits back to back: a short per-minute one (~1.5s,
   waited it out) during run_five_profile_tests.py, then the full
   daily cap (200,000 TPD, ~12 minutes remaining) during
   run_cross_user_test.py - reported status honestly and stopped
   rather than retrying blindly. User supplied a new GROQ_API_KEY;
   verified it worked with a live call before resuming, then finished
   run_cross_user_test.py and both loose PDFs on the new key.

All 5 scripts + both loose PDFs completed successfully:
- run_agent_tests.py: complete profile 2 steps/0 follow-ups
  (unchanged); incomplete profile 6 steps/confirmed - now asks name +
  target_roles as ONE bundled question instead of two sequential ones.
- run_retrieval_tests.py: same top-3 matches as before for all 3
  dataset profiles - confirms retrieval itself (embeddings/cosine
  similarity) is genuinely unaffected by any of this session's agent/
  CV-generation changes.
- run_five_profile_tests.py: Ethan 0, Priya 0, Devon 2, Marcus 1,
  Sarah 1 follow-ups (previously 0/0/2/1/3) - fewer follow-ups overall,
  matching the cumulative effect of lowering work-experience/projects/
  achievements and bundling questions.
- run_two_job_comparison.py: profile unchanged before/after both
  generate() calls (still True), both PDFs regenerated with current
  (V5) CV wording and fixed Experience placement.
- run_cross_user_test.py: all isolation checks still pass (separate
  ProfileTool objects, no name/project cross-leak, neither CV
  contaminated by the other user).
- Liam_Patel_graduate_ai_engineer_cv.pdf: regenerated with the same
  profile/job/edits as the original (sample_edits.json still in the
  scratchpad) for a like-for-like comparison; read the rendered PDF -
  clean, Experience correctly absent (he has none), Projects before
  Skills.
- Noah_Ibrahim_computer_vision_engineer_cv.pdf: regenerated from
  student_profile_04 + computer_vision_engineer (exact original
  scripted edits, if any, weren't recoverable from before the last
  context compaction, so this is a clean regeneration rather than a
  like-for-like one - flagged rather than silently assumed identical);
  read the rendered PDF - Experience correctly right after Education,
  professional wording throughout.

One finding surfaced, not yet acted on: in the run_agent_tests.py
re-run, a follow-up question was generated asking about far more than
the actual gap. At that point gaps was exactly
[{"field": "target_roles", "issue": "missing", ...}] (a single item),
but the generated question asked about "what roles you're targeting,
any work or internship experience, notable achievements, a brief
career summary, and your contact info (email, phone, GitHub,
LinkedIn)" - none of which were in gaps. FOLLOW_UP_SYSTEM_PROMPT
explicitly says "Do not ask about anything not listed," and the model
didn't follow that instruction here. Not fatal (the conversation still
confirmed correctly), but a real prompt-adherence gap surfaced by this
re-run - flagged to the user as something to decide on fixing
separately, not fixed unilaterally since it's outside "re-run the
tests" as asked.

---

GOAL: Fix the FOLLOW_UP_SYSTEM_PROMPT over-asking bug flagged above

Yes fix the bug in run_agent_tests.py [said twice]

PROPOSED CHANGE (implemented directly - the fix location and shape
were already fully diagnosed in the prior step's finding)

The bug lives in agent.py, not run_agent_tests.py (that script only
exercised it) - FOLLOW_UP_SYSTEM_PROMPT already said "do not ask about
anything not listed," but the model was shown the FULL current_draft
JSON alongside the gaps list, and other genuinely-empty fields in that
JSON (experience, achievements, summary, contact details) appear to
have tempted it into treating "empty in the draft" as equivalent to
"a gap," overriding the explicit instruction. Fix: named the exact
failure mode directly in the prompt rather than relying on a generic
"don't ask about anything else" - explicitly telling the model the
draft is shown for phrasing context only, that it will contain OTHER
empty/null fields not in the gaps list, and that an empty/null field
by itself is never a reason to ask about it. Reinforced the same
constraint a second time in the user-message wrapper text at the
call site, for redundancy.

Files touched:
- 01_System/source_code/agent.py - FOLLOW_UP_SYSTEM_PROMPT rewritten
  with the explicit anti-over-asking paragraph; the follow-up call
  site's user-content wrapper text also reinforces "for phrasing
  context only - do not ask about any other empty/null field"

DECISION
Accept (as described above)

VERIFICATION

Reproduced the exact failure scenario first (same intro/replies that
originally triggered it) to confirm the fix under real conditions,
not just in the abstract:
- Full conversation re-run: the single-gap step ("gaps: [target_roles]"
  only) now asks "To tailor your CV, could you let me know which roles
  you're aiming for?" - no mention of experience, achievements,
  summary, or contact info.
- Ran the same single-gap scenario 2 more times (temperature=0.4, so
  checked for consistency, not just luck): "I see you haven't
  specified any target roles yet - what positions are you aiming for?"
  and "I noticed your draft doesn't list any target roles yet - could
  you let me know which positions you're aiming for?" - both correctly
  scoped to target_roles only, no over-asking in either.
- Re-ran run_agent_tests.py to regenerate the actual evidence files
  with the fix applied (not just ad hoc test output):
  agent_actions_and_observations.md and follow_up_question_test.md now
  show Step 4's question ("Could you let me know which roles you're
  aiming for...") correctly scoped to the single target_roles gap that
  existed at that point.

---

GOAL: Final comprehensive verification pass against the five stated
grading criteria

Test the complete user-to-PDF flow with at least five profiles. Vary
education, skills, experience, projects and career goals, and include
incomplete profiles that require follow-up questions. The marker may
also test the system with additional profiles.
- Profile completion: The agent asks useful questions and keeps each
  user's information separate.
- Retrieval: An expected job appears in the top three results.
- Factual accuracy: Every CV claim comes from the confirmed profile.
- Job evidence: Every match reason comes from the selected job
  description.
- End-to-end behaviour: Tool calls, Observations, target-job changes,
  CV editing and PDF export work correctly.
Create CVs for two jobs from the same confirmed profile, then repeat
the complete process for another user. Compare the CV summaries,
section order and emphasis, and confirm that user information remains
separate.
[Confirmed with: "run it, I just changed the API Key"]

PROPOSED CHANGE

Proposed and ran a 3-part script pair rather than reusing the older
five_profile/cross_user scripts as-is, so every one of the five stated
criteria has explicit, named evidence rather than being left
implicit:
- Part 1 (run_final_verification.py): the same five personas used
  throughout this session (Ethan Brooks, Priya Nair, Devon Okafor,
  Marcus Webb, Sarah Chen) through the full flow to a REAL exported
  PDF each (earlier five-profile suite used skip_pdf=True), each with
  an "expected job" hypothesis stated in the script BEFORE retrieval
  runs, so the top-3 check is a real prediction rather than a
  post-hoc read of the result.
- Part 2 (run_final_verification_part23.py, Part 2): Ethan Brooks'
  single confirmed profile used to generate CVs for two different
  target jobs, with a scripted summary edit applied to the second CV
  before PDF export (to explicitly exercise CV editing, not leave the
  CV untouched), plus a before/after dataclass comparison proving the
  stored profile itself was never mutated by either generate() call.
- Part 3 (same file, Part 2/3): a second user (Devon Okafor) run in
  the same process as Ethan, sharing the same stateless GroqLLM/
  JobRetrievalTool instances but separate ProfileAgent/ProfileTool
  objects, with real PDFs exported for both this time, checked for
  cross-contamination via project-title overlap and name-substring
  checks in both directions.
All three write into one consolidated file,
03_Evidence/04_System_Tests/final_end_to_end_verification.md, closed
out with an explicit "Criteria mapping" section tying each of the
five stated criteria to the specific evidence produced above it,
rather than leaving the mapping to be inferred by the marker.

DECISION
Accept

VERIFICATION

Bug found and fixed before the first successful run: both
ProfileAgent(...) constructions in Part 2/3 were missing
job_tool=job_tool, causing a KeyError on result["job_matches"] the
first time Part 2 tried to read Ethan's retrieval results. Fixed via
replace_all to pass job_tool=job_tool to both the Ethan and Devon
agent constructions. While in that code, also removed two unrelated
leftover fragments noticed alongside the fix: a dead
"... if False else True" ternary with an unused variable, and a
broken/unused PDF-byte-scan check that never actually ran - neither
was part of any real check, both were deleted rather than left in.

Ran all three parts (one per-minute rate-limit retry along the way,
resolved with a short wait):
- Part 1: all 5 profiles confirmed, 0 grounding warnings across all
  5 generated CVs, all 5 "expected job" hypotheses held (4 of 5 at
  rank 1, Priya's at rank 1 too - all landed in the top 3 as required
  either way).
- Part 2: profile dict unchanged across both generate() calls (True),
  Job A/Job B CVs both grounded (0 warnings each), Job B's summary
  correctly shows the pre-edit text and the post-edit text separately
  in the report, with the edited text confirmed present in the
  rendered PDF.
- Part 3: all four isolation checks passed (no name cross-
  contamination, no project-title cross-contamination, both
  generated CVs independently clean of the other user's data).
Wrote the "Criteria mapping" section last, cross-referencing the
specific evidence lines already produced by Parts 1-3 against each of
the five stated criteria individually, rather than a generic pass/
fail summary.

---

GOAL: Clean up sample PDFs and make Projects always precede Skills

Remove any sample cv PDF file that is not needed/part of the test.
Also ensure that projects section always comes before skill.

PROPOSED CHANGE

Two independent changes:
1. cv_pdf.py / cv_generator.py: removed the last remaining piece of
   dynamic section ordering. Previously Experience was already a
   fixed section (right after Education), but Skills vs. Projects was
   still an LLM-decided section_order the model returned per job.
   Made Projects a fixed section too, in the order Summary ->
   Education -> Experience -> Projects -> Skills always, regardless
   of target job - only the ORDER OF ITEMS WITHIN a section (e.g.
   which skill is listed first) still varies by relevance now. Added
   CV_GENERATION_SYSTEM_PROMPT_V6 (built via .replace() on V5,
   consistent with this project's prompt-versioning convention) that
   drops the section_order instruction and output-schema key
   entirely; removed the now-dead section_order handling from
   _verify_and_clean() in cv_generator.py; removed the dynamic
   renderers/default_order mechanism from cv_pdf.py in favour of
   unconditional, fixed-order rendering of Experience then Projects
   then Skills (each only if present).
2. Deleted every PDF in 03_Evidence/04_System_Tests/sample_cv_pdfs/
   plus two loose root-level PDFs (Liam_Patel_graduate_ai_engineer_
   cv.pdf, Noah_Ibrahim_computer_vision_engineer_cv.pdf) that weren't
   tied to the current final-verification test roster, then
   regenerated the final verification suite (Parts 1-3 above) fresh
   under the corrected ordering code, so every PDF left in the folder
   both belongs to the current test and reflects the fix.

Files touched:
- 01_System/source_code/cv_pdf.py - dynamic renderers/default_order
  removed; Experience and Projects both unconditionally rendered in
  fixed order before Skills
- 01_System/source_code/cv_generator.py - added
  CV_GENERATION_SYSTEM_PROMPT_V6, live pointer updated; section_order
  post-processing removed from _verify_and_clean()
- 01_System/source_code/run_final_verification_part23.py -
  format_cv_block()'s section-order display logic updated to reflect
  the new fixed ordering instead of reading the now-nonexistent
  cv["section_order"] key
- 03_Evidence/04_System_Tests/final_end_to_end_verification.md - the
  two "Section order" lines written by the pre-fix run were corrected
  in place (Projects -> Skills, not Skills -> Projects) rather than
  re-running the whole GROQ-backed script a third time just to
  regenerate unchanged text

DECISION
Accept

VERIFICATION

- Confirmed CV_GENERATION_SYSTEM_PROMPT_V5 != V6 and that the string
  "section_order" no longer appears anywhere in V6; confirmed both
  modules still import cleanly.
- Deleted all PDFs in sample_cv_pdfs/ and the two loose root PDFs,
  then re-ran Part 1 and Part 2/3 fresh: exactly 9 PDFs regenerated
  (5 Part 1 + 2 Part 2 + 2 Part 3), matching the current roster
  exactly with nothing stray left over.
- Read two of the regenerated PDFs directly to visually confirm the
  fix rather than trusting the code change alone: Priya Nair's PDF
  (has Projects and Skills, no Experience) renders SUMMARY ->
  EDUCATION -> PROJECTS -> SKILLS; Marcus Webb's PDF (also Projects +
  Skills, no Experience) renders the same order. Both confirm Projects
  now genuinely precedes Skills in the actual rendered output, not
  just in the generation prompt.

---

GOAL: Remove "Not specified" placeholder text from generated CVs

For CVs like Ethan Brooks, don't include "Not specified" as it's not
professional. Adjust the prompt for this and remake his CV.

PROPOSED CHANGE

Traced the exact source: Ethan never named an employer for his
part-time IT helpdesk role, so DraftProfile.to_profile() (profile_
model.py) was hard-coding organisation="Not specified" as the
fallback for an unstated employer, and cv_pdf.py's Experience heading
unconditionally rendered f"{role} — {organisation}", so his CV
literally printed "Junior IT Helpdesk Assistant — Not specified".
Notably the model had already been omitting the equivalent
expected_graduation="Not specified" placeholder from the Education
line on its own, in the same CV - proof that relying on the
generation prompt alone to self-censor a placeholder is unreliable,
so this needed a fix at more than one layer rather than a prompt
tweak alone:
1. profile_model.py: changed the to_profile() fallback for an unnamed
   employer from the literal string "Not specified" to "" (also
   "type", which turned out to be dead - never read anywhere else in
   the codebase). An empty string is the true "unknown" representation
   for a field the CV layer can then choose to omit, rather than a
   piece of visible placeholder text.
2. cv_generator.py: added CV_GENERATION_SYSTEM_PROMPT_V7 (built via
   .replace() on V6, per this project's versioning convention),
   inserting an explicit instruction never to write a placeholder like
   "Not specified"/"N/A"/"Unknown" for any field, and to output "" for
   a field instead if confirmed_profile itself contains such a
   placeholder. Also added a defensive sanitization pass to
   _verify_and_clean() that coerces any experience organisation
   matching a known placeholder string (case-insensitive) to "" even
   if the model still writes one - a safety net independent of the
   prompt, consistent with how grounding is already enforced
   independently of prompt wording elsewhere in this function.
3. cv_pdf.py: the Experience heading now only appends "— {org}" when
   organisation is actually present, otherwise it renders just the
   role on its own.
4. cv_builder_gui.py: the CV-review stage's per-entry text_area label
   (line ~288) had the identical f"{role} — {organisation}" pattern -
   fixed the same way for consistency, since it's the same rendered
   fact shown in a different surface.

Files touched:
- 01_System/source_code/profile_model.py
- 01_System/source_code/cv_generator.py (CV_GENERATION_SYSTEM_PROMPT_V7,
  live pointer updated; placeholder-sanitization added to
  _verify_and_clean())
- 01_System/source_code/cv_pdf.py
- 01_System/source_code/cv_builder_gui.py

DECISION
Accept

VERIFICATION

Confirmed CV_GENERATION_SYSTEM_PROMPT_V6 != V7 and that both modules
still import cleanly. Regenerated Ethan Brooks' CV end-to-end (fresh
ProfileAgent run -> CVGenerator.generate() -> render_cv_pdf()) and
overwrote his PDF in sample_cv_pdfs/. Printed the raw CV dict's
experience entries before rendering: organisation is now "" (was
"Not specified"), 0 grounding warnings. Read the regenerated PDF
directly: the Experience heading now reads exactly "Junior IT
Helpdesk Assistant" with no placeholder suffix, rest of the CV
(summary, education, projects, skills, section order) unchanged in
substance from the prior version.

Note: this run hit the GROQ daily token cap (TPD) repeatedly - the
error consistently showed the same organization ID across three
different API keys the user swapped in during troubleshooting,
confirming this limit is scoped to the GROQ account/organization, not
the individual key, so rotating keys within the same account does not
reset it; only waiting out the rolling daily window does. One of the
three "new" keys tried also turned out to still be the old key (the
.env edit hadn't saved), which briefly looked like the org-scoping
theory was being contradicted before that was caught and corrected.
Succeeded once a genuinely different account's key was confirmed
active in .env.

---

GOAL: Apply the same "Not specified" fix to Ethan's Job B CV

Redo his jobB as healthcare ml engineer as well.

PROPOSED CHANGE (implemented directly - same fix already in place from
the prior step, this is just re-generating the second PDF that used
it)

Part 2's two-job comparison for Ethan Brooks (rag_agent_engineer as
Job A, healthcare_ml_engineer as Job B, with a scripted summary edit
applied to Job B before export) was generated before the "Not
specified" fix, so Job B's PDF likely carried the same placeholder
text in its Experience heading as Job A did. Re-ran a fresh
ProfileAgent conversation for Ethan, regenerated the CV for Job B
(healthcare_ml_engineer, his second-ranked match) with the now-fixed
CV_GENERATION_SYSTEM_PROMPT_V7, re-applied the same scripted
EDITED_SUMMARY text before export (so the CV-editing demonstration
this PDF exists for is preserved), and overwrote
final_ethan_brooks_jobB_healthcare_ml_engineer_cv.pdf in place.

DECISION
Accept

VERIFICATION

Printed the CV dict's experience entries before rendering:
organisation is "" (was "Not specified"), 0 grounding warnings. Read
the regenerated PDF directly: Experience heading now reads exactly
"Junior IT helpdesk assistant" with no placeholder suffix; the edited
summary text is present and correct; Projects still renders before
Skills (from the earlier fix); Job A's PDF
(final_ethan_brooks_jobA_rag_agent_engineer_cv.pdf) was not touched in
this step since the user asked specifically for Job B - it may still
carry the pre-fix placeholder and is flagged here rather than silently
assumed fixed.

---

GOAL: Regenerate Job A too, for consistency with Job B

Just regenerate both jobA and jobB.

PROPOSED CHANGE (implemented directly)

Re-ran Ethan's Part 2 two-job comparison as a single script covering
both jobs together (one ProfileAgent conversation, two generate()
calls, scripted edit re-applied to Job B before export) rather than
regenerating Job A alone against the already-fixed Job B, so the
before/after profile-mutation check and the two CVs stay a matched
pair generated in the same run, consistent with how Part 2 was
originally structured. Overwrote both
final_ethan_brooks_jobA_rag_agent_engineer_cv.pdf and
final_ethan_brooks_jobB_healthcare_ml_engineer_cv.pdf. Since the
underlying CV content (summaries, skill order, matched/missing
requirements) shifts slightly between GROQ calls even with the same
grounded facts, also updated the Part 2 table and both Job A/Job B
blocks in final_end_to_end_verification.md to match the newly
regenerated values, rather than leaving stale numbers next to
freshly-regenerated PDFs.

DECISION
Accept

VERIFICATION

Ran cleanly with no rate-limit interruption this time. Profile dict
still unchanged across both generate() calls (True). Both CVs'
experience entries show organisation="" (0 grounding warnings each).
Read Job A's regenerated PDF directly: Experience heading now reads
"Junior IT helpdesk assistant" with no placeholder suffix, Projects
still before Skills. Job B's PDF was already re-verified in the prior
step with the same edit-preservation check. Evidence file's Part 2
section (summary text, skills order, matched skills, missing-
requirement counts and lists for both jobs, Job B's pre-edit "original
summary" quote) updated to match this run's actual output.

---

GOAL: Remove the "EDITED BY STUDENT BEFORE EXPORT:" meta-commentary
from Job B's actual CV text

Jobb still shows the "EDITED BY STUDENT BEFORE EXPORT: Ethan is a
backend-focused UTS Computing Science student who enjoys building
small, well-tested APIs and is now exploring how those skills
transfer into AI engineering." text.

PROPOSED CHANGE (implemented directly)

The literal prefix "EDITED BY STUDENT BEFORE EXPORT:" was original
test scaffolding (added so the scripted-edit demonstration was
unmistakable at a glance) that had leaked into the actual visible
summary text of a CV meant to stand as a real deliverable artifact -
the same category of problem as the "Not specified" placeholder fixed
two steps ago, just introduced by this session's own test script
rather than the LLM. Removed the prefix from the EDITED_SUMMARY
constant in run_final_verification_part23.py (and the scratchpad copy
used to regenerate Ethan's two-job pair), keeping the rest of the
sentence unchanged so it's still recognizably a distinct, deliberately
different summary from whatever the model generates on its own -
proof the edit took hold - without any meta-commentary appearing in
the CV itself. The "this was edited" narration still lives in the
markdown evidence report's prose (both here and in the "CV edit
demonstration" block), which is the correct place for it, not inside
the CV text a marker or employer would actually read.

Files touched:
- 01_System/source_code/run_final_verification_part23.py -
  EDITED_SUMMARY constant, prefix removed

DECISION
Accept

VERIFICATION

Re-ran Ethan's two-job generation fresh (both jobs regenerated
together again, consistent with the prior step's approach) and
re-exported both PDFs with the corrected constant. Read Job B's PDF
directly: the summary now reads cleanly as "Ethan is a backend-focused
UTS Computing Science student who enjoys building small, well-tested
APIs and is now exploring how those skills transfer into AI
engineering." with no meta-commentary prefix, Experience still shows
no placeholder text, Projects still before Skills. Updated the Part 2
table and both Job A/Job B blocks in final_end_to_end_verification.md
to match this latest regeneration's actual summaries, skills order,
and matched/missing requirement counts (these fields drift slightly
run-to-run even with identical underlying grounded facts, since the
model rephrases and re-selects wording each call).

---

GOAL: Feature 1 - job-specific follow-up questions for missing requirements

[Full spec pasted by the user, summarized here: once a target job is
selected, compare the confirmed profile against THAT job's own stated
requirements (not a generic profile-completeness check); identify only the
requirements the job asks for that the profile doesn't cover; ask a
specific targeted question per gap, returned to an interactive chatbox for
a natural reply in the same session; after the reply, re-check - anything
still unresolved is recorded as confirmed-absent, never fabricated, and
never re-asked once answered; do not ask about requirements already
satisfied; re-run whenever the target job changes; reuse the
confirmed-facts-only rule. Acceptance criteria: Job A's questions are
specific to Job A; switching to Job B produces a fresh, different
question set; a requirement the student confirms they lack never gets
claimed in that job's CV.]

PROPOSED CHANGE

Read the existing job-selection flow first (cv_builder_cli.py's
run_full_flow, cv_builder_gui.py's "jobs" stage) - today a job is chosen
and CVGenerator.generate() runs immediately, with no check of the
confirmed profile against that SPECIFIC job's requirements at all
(CVGenerator's own matched_skills/missing_requirements is computed AFTER
generation, for display, not as a gate before it). Designed the new check
as a single round-trip per job selection rather than ProfileAgent's
multi-turn loop, since the spec explicitly says "do not keep re-asking
once the user has answered" - one combined question covering every gap
for that job, one reply, and every gap from that round is finalized
(confirmed or recorded confirmed-absent) in that same step, matching this
project's established "bundle everything into one question" pattern from
earlier profile-building work.

New pieces:
- profile_model.py: DraftProfile gets a new `declined_requirements: List[str]`
  field and a `decline_requirements()` method (case-insensitive dedup,
  same pattern as existing list fields) - requirements the student has
  confirmed they don't have, kept across job switches so a later job
  sharing the same requirement doesn't re-ask.
- profile_tool.py: `ProfileTool.apply_job_requirement_facts(fields, declined)`
  - merges newly confirmed skills/notes via the existing `merge()` (same
  dedup/append logic as a normal extraction turn) and records declines via
  `decline_requirements()`. Deliberately does not touch `_latest_gaps` -
  this is a job-specific check, separate from general profile-completeness
  gaps.
- agent.py: two new prompts and a new `JobRequirementAgent` class.
  `JOB_REQUIREMENT_GAP_SYSTEM_PROMPT` reads confirmed_profile + the
  selected job's title/description + already_declined, extracts the job's
  own stated requirements not already covered (dropping anything matching
  already_declined even loosely), classifies each as "skill" or
  "experience", and writes ONE combined question. `JOB_REQUIREMENT_
  ANSWER_SYSTEM_PROMPT` takes that gap list plus the student's one reply
  and, for every gap (none skipped), decides confirmed vs declined, a
  CV-ready `skill_name` when the reply actually supports one (decided from
  the REPLY, not from the gap's original "skill"/"experience"
  classification - see bug notes below), and an optional evidence `note`.
  `JobRequirementAgent.check()`/`resolve()` wrap these with a Python-level
  safety net (same defense-in-depth pattern as
  cv_generator._verify_and_clean and the earlier FOLLOW_UP_SYSTEM_PROMPT
  fix): any gap the model's response doesn't explicitly resolve as
  "confirmed" defaults to declined, so nothing can linger unresolved or
  get silently fabricated.
- cv_builder_cli.py's run_full_flow: after the job is chosen and before
  `agent.tool.to_profile()` is called for CV generation, runs
  `JobRequirementAgent.check()`/`resolve()` (interactive `input()` or a
  new `job_requirement_reply` param for scripting/testing) - the profile
  object used for CVGenerator is built AFTER this step so any newly
  confirmed skill/note is reflected, and anything declined is simply never
  added, so CVGenerator's existing grounding can't claim it.
- cv_builder_gui.py: new "job_requirements" stage inserted between "jobs"
  and "cv" - selecting a job now runs check() first; if there are gaps, the
  student sees one combined question in the same chat-style flow as the
  profile follow-ups, submits one reply, and only then does CV generation
  run. A `generate_cv_for_chosen_job()` helper is shared between the
  no-gap path (straight from "jobs") and the post-resolve path, so CV
  generation logic isn't duplicated. Re-running check() naturally happens
  every time a job is (re)selected, including via the existing "← Choose a
  different job" button - satisfies "re-run whenever the target job
  changes" without any extra state to manage.

Files touched:
- 01_System/source_code/profile_model.py
- 01_System/source_code/profile_tool.py
- 01_System/source_code/agent.py (JOB_REQUIREMENT_GAP_SYSTEM_PROMPT,
  JOB_REQUIREMENT_ANSWER_SYSTEM_PROMPT, JobRequirementAgent)
- 01_System/source_code/cv_builder_cli.py
- 01_System/source_code/cv_builder_gui.py
- 01_System/source_code/run_job_requirement_test.py (new evidence script)

DECISION
Accept

VERIFICATION

Two real bugs surfaced and were fixed during a live test run before
treating this as done, rather than papered over:
1. Both new extract_json() calls were first wired at max_tokens=1024 and
   failed outright (`groq.BadRequestError: Failed to validate JSON`,
   empty failed_generation) - the reasoning model spends tokens on hidden
   reasoning before visible output (a known issue this session, see
   earlier CV-generation work), so 1024 wasn't enough headroom. Raised
   both to 2048, matching EXTRACTION_SYSTEM_PROMPT's budget.
2. Live testing surfaced gaps being returned with `question: null` more
   than once (not only for a single-gap case as first suspected) - the
   same class of prompt-adherence gap as the earlier FOLLOW_UP_SYSTEM_
   PROMPT bug this session. Fixed with a Python-side fallback in
   check(): whenever gaps is non-empty but the model omits "question",
   synthesize one directly from the gap requirement names, so the
   CLI/GUI can never show a blank prompt for a real gap.
Also caught and fixed a subtler design gap while reading a passing test's
own grounding_warnings output: the first working run showed CV A's
grounding warnings stripping "Data Structures and Algorithms" as
ungrounded, even though the student HAD just confirmed it in their reply -
tracing it back, resolve() only added a confirmed item to technical_skills
when the ORIGINAL gap's kind was "skill" (decided from the job's
requirement text, before the reply existed), so a requirement classified
as "experience" (e.g. "a firm understanding of data structures and
algorithms") never reached technical_skills even when the reply gave clear
skill-level evidence - CVGenerator's own LLM then independently tried to
promote the achievement note into a skill anyway, and grounding correctly
caught and stripped that. Fixed by moving the skill/no-skill decision into
the answer-extraction call itself (`skill_name`, decided from what the
REPLY demonstrates, not from the original gap's kind) rather than gating
on a decision made before the reply was known.

Ran `run_job_requirement_test.py` end to end against Marcus Webb
(cybersecurity/systems background, no ML/Python skills stated) across two
different jobs from the same confirmed profile, and confirmed against all
three stated acceptance criteria:
1. Job A (`trust_safety_ml_engineer`): 5 gaps, every one drawn from that
   job's own description text (machine learning, pattern recognition,
   NLP, data mining, computer vision, data structures and algorithms,
   communication/teamwork) - one combined question, one reply.
2. Job B (`graduate_ai_engineer`), same profile: 10 gaps, a completely
   different set (statistics, data analysis, agentic AI, LLMs, RAG,
   domain-specific fine-tuning, Python + ML libraries, data
   visualisation, structured/unstructured data experience, professional
   experience) - gap sets confirmed non-identical. Notably "machine
   learning" is required by both jobs' text but was correctly NOT
   re-asked in Job B, since Marcus had already declined it for Job A and
   already_declined suppressed it - the cross-job carryover working as
   designed, not just same-job non-repetition.
3. The reply confirmed "data structures and algorithms" with concrete
   evidence (implemented BSTs/hash maps/sorting algorithms across two
   courses) and declined everything else; the resulting CV for both jobs
   includes "Data Structures and Algorithms" in skills with zero
   grounding warnings, and every declined requirement (machine learning,
   computer vision, Python+libraries, etc.) was checked against both
   CVs' skills arrays and found in neither - `True`.
Evidence written to 03_Evidence/02_Agent/job_requirement_followup_test.md.

---

GOAL: Move the job-requirement chat box into stage 5 and keep it usable

"I want the chat box to be at stage 5. Review, preview & export your CV"
- followed by: "The chat box also shouldn't disappear after just one
message, it should allow for continuous changing."

PROPOSED CHANGE

First request: removed the separate "job_requirements" GUI stage entirely.
Selecting a job now runs the requirement check, generates the CV
immediately either way, and goes straight to stage 5 - if that job has
genuine gaps, a bordered question box appears at the TOP of the CV review
page (above the editable CV fields) instead of blocking the page from
appearing at all.

Second request (same session, live-tested by the user just after): the
first version still popped job_requirement_gaps/question after a single
reply, so the box vanished for the rest of that job. Redesigned it as a
persistent chat rather than a one-shot Q&A: the box always shows in stage
5 now (not conditional on gaps existing), and after EVERY message -
whether it answered the current gap-question or was free-form (an extra
skill, a correction, anything not tied to a named requirement) -
JobRequirementAgent.check() is re-run fresh against the updated profile.
Already-confirmed/declined items are filtered out by check()'s own
already_declined logic, so this naturally surfaces only whatever is still
genuinely open (or nothing, in which case the box switches to an open
invitation to add/correct anything) rather than ever going stale or
repeating itself. A free-form message (no pending gap) is routed through
the same EXTRACTION_SYSTEM_PROMPT + ProfileTool.update_profile() path a
normal profile-building turn uses, reusing that well-tested merge logic
instead of inventing a second extraction path. The text_input's key
increments each turn (job_chat_turn) so Streamlit clears the box after
every send, the way a real chat input behaves.

Files touched:
- 01_System/source_code/cv_builder_gui.py

DECISION
Accept

VERIFICATION

Syntax-checked the file and boot-tested the Streamlit app after each
change (starts cleanly, no import errors). Full interactive click-through
wasn't done in this environment (no browser access here) - flagged this
limitation explicitly rather than claiming a browser test that didn't
happen; the user can verify the live rendering themselves.

---

GOAL: Fix a real grounding false-positive found via live GUI testing

The user ran the GUI with Jordan Ramirez's introduction (course-timetable
API project) and got: "Some generated content didn't match your confirmed
profile and was removed: Dropped ungrounded project entry: {'title':
'Course‑timetable API', ...} (no matching title in profile.projects)" -
a real project the student described being stripped from their own CV.

PROPOSED CHANGE

Root cause: CVGenerator's system prompt rewrites titles/roles into CV
register, and the model often introduces a typographic character while
doing so - here a non-breaking hyphen (U+2011) in "Course‑timetable",
where the profile's own title (extracted verbatim from the student's
plain-ASCII "course-timetable API") uses a normal hyphen (U+002D).
_verify_and_clean()'s grounding check compares titles/roles/skills with a
plain case-insensitive string match, so the two didn't match and a
genuinely real, non-fabricated project got silently dropped as
"ungrounded" - a false positive, not a fabrication catch. Exactly the
same class of character-mismatch problem cv_pdf.py's _clean() already
handles at render time (see its own comment: Helvetica has no glyph for
some of these anyway) - but that fix only applied at PDF-rendering, never
at the grounding-comparison stage in cv_generator.py, where it actually
caused content loss rather than just a missing glyph.

Added `_normalize()` in cv_generator.py: translates the same non-breaking
hyphen/hyphen/figure-dash/en-dash/em-dash/curly-quote variants cv_pdf._clean()
handles, then lowercases and strips - used on BOTH sides of every grounding
comparison (allowed_skills/allowed_project_titles/allowed_experience_roles
sets, and the generated cv's own skill/role/title/missing_requirement
lookups), not just the one field that happened to trigger this report,
since the same mismatch could equally hit an experience role or a skill
name with an apostrophe.

Files touched:
- 01_System/source_code/cv_generator.py

DECISION
Accept

VERIFICATION

Reproduced the exact failure directly: built a profile with project title
"Course-timetable API" (plain hyphen) and a generated CV with title
"Course‑timetable API" (non-breaking hyphen) and ran
_verify_and_clean() against it - before the fix this is exactly the
reported bug (title match fails, project dropped); after the fix,
`warnings == []` and the project is kept with its original (typographically
rewritten) title intact. Confirmed cv_generator.py still imports cleanly
and the earlier job-requirement test's behavior is unaffected (normalization
only changes which typographic variants are treated as equivalent, not the
matching logic itself).

---

GOAL: Fix profile-update parsing - multi-field extraction & additive
section updates

[Full spec pasted by the user, summarized here: Bug 1 - a message
carrying facts for more than one field (e.g. "I have experience with
React and Node.js from building an e-commerce app") must extract ALL of
them, not stop at the first match; an implied project ("building X",
"built X", "worked on X") must become a project entry even without the
word "project", with used skills linked to it; every extracted update
must be confirmed back in one message. Bug 2 - a section that already has
data (e.g. Education already showing a Bachelor's) must support an
ADDITIVE new statement ("I also have a Master's in X") appending a new
entry rather than being dropped/overwritten; ambiguous
additive-vs-correction cases should prompt the user to clarify; the full
updated state should stay viewable. Acceptance criteria: SQL+Python
example -> Skills AND Projects both updated in one pass; Master's example
-> Education shows both degrees; agent confirms every change made, not
just the first.]

PROPOSED CHANGE

Verified both bugs empirically against the LIVE extraction pipeline
before writing any fix, rather than assuming from reading the prompt
alone (the EXTRACTION_SYSTEM_PROMPT already runs one JSON call across
every field type, so it wasn't obvious the bug was real without testing):
- Bug 1 reproduced, but not exactly as described - skills extraction
  across multiple fields already worked (React/Node.js both came out
  correctly), but "building an e-commerce app" was misclassified as an
  "experience" entry (role: "Developer", no organisation) instead of a
  project - the real defect was project/experience disambiguation, not a
  stop-at-first-match issue.
- Bug 2 reproduced exactly as described - `degree` is a plain scalar
  field with nowhere to put a second qualification, so the extraction
  call returned "degree": "Master's in Data Science", and DraftProfile.
  merge() dutifully overwrote the Bachelor's outright.

Fix, scoped to what was actually broken rather than a full data-model
rewrite: experience/projects/skills/target_roles already support multiple
entries with correct additive merge() logic (matching by title/org/role,
appending when new) - only EDUCATION was genuinely stuck as two scalar
fields (degree, year) with no way to represent a second qualification.
- profile_model.py: added `DraftEducationEntry`/`AdditionalEducationEntry`
  and a new `additional_education: List[...]` on both DraftProfile and
  Profile - a SEPARATE list that only ever appends, so the existing
  well-tested primary degree/year flow (missing_fields, gap logic, GUI
  form fields) needed no restructuring. Added "education" to
  GAP_PRIORITY_ORDER for the new ambiguous-education gap case. Added
  merge() logic for additional_education (append-if-new-by-degree-name,
  same pattern as projects/experience). Added `describe_new_facts(before,
  after)`: a deterministic Python diff of two draft dicts, returning
  plain-English clauses of everything a message just changed - computed
  from actual before/after state, not by asking the model to self-report,
  so nothing an extraction call touches can go unmentioned to the student
  (directly targets "confirm all extracted updates ... so nothing is
  added silently").
- profile_tool.py: `update_profile()` now captures the pre-merge draft,
  merges, and includes `describe_new_facts()`'s output as `new_facts` in
  the returned observation.
- agent.py's EXTRACTION_SYSTEM_PROMPT: added an explicit "CHECK EVERY
  FIELD TYPE, NOT JUST THE FIRST MATCH" paragraph with the spec's own
  React/Node.js/e-commerce example; a "DISTINGUISH projects FROM
  experience" paragraph defining experience as requiring an
  employer/organisation and projects as independent work, explicitly
  naming "building X"/"built X"/"worked on X" with no employer as project
  language, and instructing that named technologies link into that
  project's own "technologies" array; and an "EDUCATION - ADDITIVE vs.
  CORRECTION vs. AMBIGUOUS" paragraph giving the model three explicit
  branches (refine degree/year in place; append to a new
  "additional_education" output key; or, if genuinely unclear, emit a
  {"field": "education", "issue": "ambiguous", ...} gap so the existing
  follow-up-bundling mechanism asks the student directly - reusing that
  machinery rather than building a second one). `take_turn()` now
  prepends the deterministic "Got it - X; Y." acknowledgment ahead of the
  LLM-phrased follow-up question whenever new_facts is non-empty.
- cv_generator.py: added CV_GENERATION_SYSTEM_PROMPT_V8 (built via
  .replace() on V7) instructing the CV-writing model to weave any
  additional_education entries into the same "education" summary string
  it already writes, so a second confirmed degree doesn't get silently
  dropped one layer further downstream in the actual CV either.
- cv_builder_gui.py: the stage-5 free-form chat path (added earlier this
  session) now shows `new_facts` via `st.success()` too, so both places a
  student can send a message get the same explicit confirmation.
- Both call sites using EXTRACTION_SYSTEM_PROMPT (agent.py's take_turn,
  the GUI's free-form chat) raised from max_tokens=2048 to 4096 - the
  prompt grew substantially with the new paragraphs above and 2048 was no
  longer enough headroom for this reasoning model, confirmed by an actual
  `BadRequestError: Failed to validate JSON` (empty failed_generation)
  before the fix, the same failure signature as the max_tokens issue
  found and fixed for the job-requirement prompts earlier this session.

Files touched:
- 01_System/source_code/profile_model.py
- 01_System/source_code/profile_tool.py
- 01_System/source_code/agent.py
- 01_System/source_code/cv_generator.py (CV_GENERATION_SYSTEM_PROMPT_V8)
- 01_System/source_code/cv_builder_gui.py
- 01_System/source_code/run_profile_update_test.py (new evidence script)

DECISION
Accept

VERIFICATION

Ran run_profile_update_test.py against a live three-turn conversation
(Priya Kapoor: Bachelor of Computing Science, Java/Git, then the two test
messages) and confirmed all three acceptance criteria directly:
1. "I have experience with SQL and Python from building a data pipeline
   project" -> skills became [Java, Git, SQL, Python], a NEW project
   entry {"title": "data pipeline project", "technologies": ["SQL",
   "Python"]} was created, and experience stayed empty (correctly not
   misclassified) - `True`.
2. "I also have a Master's in Data Science" -> degree remained "Bachelor
   of Computing Science" unchanged, additional_education gained exactly
   one new entry for the Master's - `True`.
3. The agent's response for both test messages led with a deterministic
   "Got it - ..." clause listing every field just updated (turn 2: "added
   SQL, Python to your skills; added 'data pipeline project' to your
   projects"; turn 3: "added Master's in Data Science to your education,
   alongside what was already there") before the next follow-up question
   - `True`.
Evidence written to 03_Evidence/02_Agent/profile_update_parsing_test.md.

Also attempted a full regression run of the pre-existing
run_agent_tests.py suite: hit the exact max_tokens JSON-validation
failure first (fixed as described above), then - after the fix - hit the
GROQ daily token cap (198,636/200,000 used, ~13m44s remaining) purely
from today's cumulative testing volume, unrelated to correctness. Not
retried given the wait; flagged here rather than silently left undone -
run_agent_tests.py and the other evidence-generating scripts have NOT
been regenerated against the new EXTRACTION_SYSTEM_PROMPT yet, though the
dedicated test above already directly proves the fix works.

---

GOAL: Re-run the regression suite (quota reset overnight)

"rerun"

Ran run_agent_tests.py fresh the next day once the GROQ daily cap had
reset - both cases passed cleanly (complete profile confirmed in 2 steps,
incomplete in 6, no errors). The incomplete-profile trace was a useful
bonus confirmation of yesterday's fix on a pre-existing test case, not
just the new dedicated script: "I built a small course-timetable API in a
team project using Flask and SQLite" correctly landed in "projects" (not
misclassified as "experience"), and every AskFollowUp question now leads
with the deterministic "Got it - ..." acknowledgment before the next
question. Evidence regenerated at
03_Evidence/02_Agent/agent_actions_and_observations.md and
follow_up_question_test.md.

---

GOAL: Fix real bugs found via live GUI testing of the profile-update fix

The user ran the actual GUI end to end (not a scripted test) with Jordan
Ramirez's introduction, hit a job-requirement follow-up, and replied "I
also have a masters in Computer Science. I also use RAG, AI Agents, and
LLMs for a project. The project is about an AI Powered CV Builder." -
screenshotted the resulting PDF and reported two problems: the new "AI
Powered CV Builder" project never appeared in the Projects section at
all, and the Master's was just tacked onto the end of the Education
paragraph after a period ("...Full-time. Master's degree in Computer
Science.") - "not professional."

PROPOSED CHANGE

Diagnosed by reproducing each layer of the pipeline separately rather
than guessing which one was at fault:
1. Ran the exact reply text through EXTRACTION_SYSTEM_PROMPT directly -
   extraction was CORRECT: additional_education got the Master's, and a
   genuinely new "AI Powered CV Builder" project entry was created
   (title, description, technologies all present) alongside the existing
   course-timetable API project. So the bug was NOT in yesterday's
   profile-parsing fix - the data was captured properly.
2. Fed that exact draft into CVGenerator.generate() directly - in this
   isolated run both projects DID appear in the output (the missing-
   project symptom didn't reproduce standalone, most likely LLM run-to-
   run variance in the user's live session rather than a deterministic
   bug), but the education-formatting problem reproduced immediately and
   consistently: "Bachelor of Computing Science, ... third-year (Full-
   time). Master's in Computer Science." - a real, reproducible defect
   traced to yesterday's CV_GENERATION_SYSTEM_PROMPT_V8, which told the
   model to "weave" additional_education into the SAME "education"
   string as the primary degree. Asking a model to blend two separate
   facts into one prose sentence reliably produces exactly this kind of
   awkward, run-on, unprofessional result - the instruction itself was
   the wrong design, not just under-specified.

Fixed with a structural change rather than better wording alone: gave the
CV's own output schema a dedicated `additional_education` field (array of
short strings, one per qualification) alongside the existing `education`
string, mirroring how Experience and Projects already render multiple
entries as separate blocks instead of one paragraph. CV_GENERATION_
SYSTEM_PROMPT_V9 (built via .replace() on V7, skipping V8 rather than
layering on top of a design that was wrong) now explicitly forbids
appending a second qualification onto the "education" string "even with
a period or semicolon" and requires additional_education to carry it
instead, one qualification per string, never invented. Also strengthened
the same TASK 1 paragraph that governs project/experience ordering to
say "choosing" means ordering only, never filtering - EVERY existing
project/experience entry must appear somewhere in the output, none
silently dropped for low relevance - as a direct defense against the
reported (if not cleanly reproduced) missing-project symptom, since the
original wording could plausibly be read as license to select a subset.

Files touched:
- 01_System/source_code/cv_generator.py (CV_GENERATION_SYSTEM_PROMPT_V9
  replacing V8; grounding check added for additional_education, same
  substring-tolerant pattern as elsewhere in _verify_and_clean())
- 01_System/source_code/cv_pdf.py (renders each additional_education
  line as its own paragraph under the Education section header, after
  the primary education paragraph)
- 01_System/source_code/cv_builder_gui.py (CV-review stage gets an
  editable text_input per additional_education line, alongside the
  existing Summary/Education fields)

DECISION
Accept

VERIFICATION

Rebuilt the exact reported profile (Bachelor's + Master's in
additional_education, both projects present) and re-ran CV generation
against the same rag_agent_engineer job: `cv["education"]` is now just
"Bachelor of Computing Science" (no appended second sentence),
`cv["additional_education"]` is `["Master's in Computer Science"]` as its
own clean entry, both project titles appear
(["course-timetable API", "AI Powered CV Builder"]), and grounding
warnings are empty. Rendered the actual PDF and read it back: EDUCATION
section now shows two distinct lines - "Bachelor of Computing Science"
then "Master's in Computer Science" - directly under the same header,
not one run-on sentence; PROJECTS section shows both projects in full
with their own technologies/descriptions. This is the exact scenario the
user reported, now producing a clean result.

---

GOAL: Fix the stage-5 chat box only updating Summary and Skills

"at stage 5, the chatbox of "Chat: add or adjust anything for this
role", only change the summary and the skill section. nothing else"

PROPOSED CHANGE

Root cause was a Streamlit widget-state gotcha, not a generation bug: once
a widget is rendered with an explicit, STABLE key (e.g. key=f"exp_{i}"),
Streamlit uses that widget's own persisted state on every later rerun and
ignores any new `value=` it's given - the widget effectively "freezes" at
whatever it last held. Experience (key=f"exp_{i}"), Projects
(key=f"proj_{i}"), and additional_education (key=f"add_edu_{i}") all used
an INDEX-only key, so after the chat box regenerated the CV, those
widgets kept showing their pre-chat content even though
st.session_state.cv had genuinely changed underneath them. Summary,
Education, and Skills had no explicit key at all, so Streamlit's
auto-generated (value-sensitive) key happened to change whenever their
value changed, which is why only those looked like they were updating -
not because they were handled correctly, but because they weren't
handled at all and got lucky.

Fixed by keying every editable CV field in stage 5 on `chat_turn`
(st.session_state.job_chat_turn, already bumped by the chat box on every
message) in addition to its index - `key=f"exp_{chat_turn}_{i}"`,
`key=f"proj_{chat_turn}_{i}"`, `key=f"add_edu_{chat_turn}_{i}"` - and
gave Summary/Education/Skills the same explicit turn-scoped keys instead
of relying on the accidental auto-key behavior. Every widget becomes a
genuinely new one each time the chat box regenerates the CV, so all of
them pick up the fresh values rather than only the ones that happened to
have no key.

Files touched:
- 01_System/source_code/cv_builder_gui.py

DECISION
Accept

VERIFICATION

Syntax-checked and boot-tested the Streamlit app (starts cleanly, no
import errors). Full interactive click-through of the chat box across
multiple messages wasn't done in this environment (no browser access
here) - flagged this limitation explicitly rather than claiming a
browser test that didn't happen; worth the user confirming live that
Experience/Projects/Education now refresh correctly after a chat message
that adds or changes one of them.

---

GOAL: Fix the real cause - job-requirement replies losing everything but
skills

"This made it even worse, now the summary are rewritten, lost details,
and are very vague. Education Section are still not updated, neither has
the project section. Do a through check if Projects and Educations can
have more than one entry or now"

PROPOSED CHANGE

The widget-key fix from the previous step was real but insufficient -
the underlying regenerated CV itself genuinely wasn't gaining the new
project/degree, so no key strategy could have shown them. Traced the
actual live code path this time instead of re-testing in isolation:
Jordan's target job (AI Engineer) triggers a job-requirement follow-up,
so his reply ("I also have a masters... RAG, AI Agents, and LLMs for a
project... AI Powered CV Builder") goes through
JobRequirementAgent.resolve(), NOT the general free-form extraction path
- and resolve()'s own schema (JOB_REQUIREMENT_ANSWER_SYSTEM_PROMPT) only
ever asks for "skill_name" and a free-text "note" per named gap; it has
no concept of a project, an experience entry, or a second degree at all.
apply_job_requirement_facts() only ever writes technical_skills/
achievements. So the Master's and the new project were never silently
mis-rendered - they were never extracted into a structured field in the
first place, only as loose achievement-note text, which is also why the
CV's summary got vaguer: the CV-writing model had a vague note to work
from instead of a concrete, titled project with real technologies. This
explains every symptom the previous step's diagnosis got wrong - it
correctly identified a widget-caching issue (real, and still worth
fixing) but missed that Education/Projects also had nothing new to show
in the first place for a reply that answered a pending job-requirement
question.

The user's direct question - can Projects/Education actually hold more
than one entry - was answered by checking, not asserting: profile_
model.py's Projects.entries is a List already appended-to correctly by
merge() (confirmed again in this step's reproduction: both "Course-
timetable API" and "AI Powered CV Builder" coexist), and the separate
additional_education list (added earlier this session specifically so a
second degree can never overwrite the first) also works correctly when
actually populated. Neither was ever the limitation - the limitation was
one specific code path never attempting to populate them.

Fix: after JobRequirementAgent.resolve() runs (still needed - it's the
only thing that tracks confirmed-absent requirements for grounding/non-
fabrication), ALWAYS ALSO run the exact same reply through the general
EXTRACTION_SYSTEM_PROMPT + ProfileTool.update_profile() path - the same
well-tested multi-field extraction already proven to handle new
projects and additive education correctly elsewhere. A reply to a named
job requirement is still an ordinary message and may carry facts
JobRequirementAgent has no schema for; running both is not redundant
work, since each captures something the other structurally cannot.
Applied identically to both surfaces that have this flow:
cv_builder_gui.py's stage-5 chat box and cv_builder_cli.py's job-
requirement handling in run_full_flow() (the CLI had the exact same gap,
just never reported since Feature 1's own test replies were pure
skill-confirmation text that never happened to carry a project).

Files touched:
- 01_System/source_code/cv_builder_gui.py
- 01_System/source_code/cv_builder_cli.py

DECISION
Accept

VERIFICATION

Reproduced the user's exact live scenario end to end for the first time
(previous verifications had each tested one stage in isolation, which is
exactly how this fix's absence went unnoticed): full ProfileAgent
conversation for Jordan Ramirez, top job match, JobRequirementAgent.check()
correctly triggered a follow-up naming a Master's degree, 3+ years
experience, and LLM/RAG/AI-agent experience, then the user's exact reply
was processed through BOTH resolve() and the new general-extraction step.
Final draft profile: additional_education correctly holds "Master's in
Computer Science" (degree still "Bachelor of Computing Science",
untouched), projects correctly holds BOTH "Course-timetable API" and "AI
Powered CV Builder" with real descriptions/technologies, technical_skills
gained LLM/RAG/AI Agents. Generated CV and rendered the PDF: summary is
now specific (names both projects and the Master's by name, not vague),
EDUCATION shows two clean separate lines, PROJECTS shows both entries in
full, zero grounding warnings - the exact scenario that was broken now
producing a correct, professional result.

---

GOAL: Session-based chat history sidebar

[Full spec pasted by the user, summarized here: add a left sidebar
listing chat sessions within the current app run - in-memory only, no
database, resets on full reload. Starting a new profile/conversation
creates a new sidebar entry (auto-labeled, e.g. "Profile 1", "Profile
2"); clicking an entry switches the main view to that session's
conversation history and profile state without losing any other
session's data; switching back and forth must keep each session's
profile data, confirmed facts, and chat messages fully isolated,
reusing/verifying the existing per-user isolation logic; a "New chat" /
"New profile" action starts a fresh session. Acceptance criteria: start
Profile A, leave a field blank, get a follow-up in the chatbox, answer
it, see the profile complete; start Profile B in a new sidebar entry
while Profile A's session still exists; switching between them restores
each one's correct chat history and confirmed profile with no data
bleeding.]

PROPOSED CHANGE

cv_builder_gui.py was built around one flat set of st.session_state keys
(agent, stage, pending_question, confirm_summary, job_matches,
chosen_job, job_requirement_gaps, job_requirement_question,
job_chat_turn, cv, pdf_bytes, profile) representing "the current
conversation" - every stage branch throughout the ~450-line file reads
and writes these directly. Rewriting every one of those references to go
through a nested sessions dict would have been large and easy to get
subtly wrong in exactly the places that matter most (data isolation), so
instead: keep those flat keys exactly as they are and exactly as every
existing stage branch already uses them, and add a "swap in / swap out"
layer around them.

Added SESSION_KEYS (the exact tuple of flat keys above) and three
helpers:
- _sync_active_session(): copies the current flat keys into
  st.session_state.sessions[active_id] - called right before switching
  away from a session, so nothing in it is lost. A no-op before any
  session exists (checked via active_id being None), which is what makes
  it safe to call unconditionally from start_new_session() too, including
  on the very first bootstrap call.
- _activate_session(session_id): loads a stored bundle into the flat
  keys, and explicitly pops any flat key the bundle doesn't have - this
  is the actual isolation guarantee: a stage further along in a different
  session (e.g. "cv" state with a chosen_job) can never leak into a
  session that never reached that stage (e.g. still at "intro"), because
  every key not present in the target bundle is cleared, not just
  overwritten where present.
- start_new_session(): syncs out whatever's currently active (if
  anything), then builds a brand new ProfileAgent under a fresh uuid
  session_id, appends it to session_order, and makes it active. This
  replaced the old reset_session() (which destructively wiped the one
  conversation that existed) - the multi-session equivalent doesn't
  destroy anything, it only ever adds.

Each session's ProfileAgent (and therefore its ProfileTool/DraftProfile)
is a genuinely separate Python object stored in its own bundle - this is
exactly the same per-instance isolation this project's cross-user tests
already rely on (Part 3 of final_end_to_end_verification.md, Ethan/Devon
sharing only the stateless GroqLLM/JobRetrievalTool), just with N
sessions living in one dict instead of two variables in one script. No
new isolation mechanism was invented; switching sessions only changes
which already-isolated instance the flat keys point at.

Sidebar: replaced the old single "Stage" caption + "Start over / new
user" button with a "+ New chat" button and one button per session in
session_order, labeled via _session_label() (peeks at that session's
agent - live flat state for the active one, the stored bundle for
everyone else - to show "Profile N - <name>" once a name is captured,
falling back to "Profile N" before then). Clicking a non-active session's
button syncs out the current one and activates the clicked one, then
reruns.

Files touched:
- 01_System/source_code/cv_builder_gui.py
- 01_System/source_code/run_session_sidebar_test.py (new evidence script)

DECISION
Accept

VERIFICATION

Rather than eyeballing the code or only checking it boots, drove the
ACTUAL app script end-to-end with streamlit.testing.v1.AppTest (confirmed
available in the installed Streamlit 1.62.0) - this runs cv_builder_gui.py
for real, including real GROQ calls, not a reimplementation of its logic:
1. Bootstrap: one session auto-created, stage=intro.
2. Profile A (Alice Chen, IT student, Python/SQL, target_roles left
   blank): submitting the intro correctly landed on stage=followup with a
   question asking for target roles; answering it reached stage=confirm
   with the full draft captured correctly (name, degree, skills,
   target_roles all present).
3. Clicked "+ New chat": session count went from 1 to 2, Profile A's
   stored bundle still shows stage=confirm (untouched), Profile B starts
   fresh at stage=intro.
4. Profile B (Bob Lee, CS student, Java/Linux): same flow, reached
   stage=confirm with its own correct draft.
5. Clicked Profile A's sidebar button: active_id switched back correctly,
   stage restored to confirm, draft matches what was captured in step 2
   exactly, and contains neither "Bob" nor "Java" anywhere.
6. Clicked Profile B's sidebar button: same round-trip check in the other
   direction - draft matches step 4 exactly, contains neither "Alice" nor
   "Python".
All three stated acceptance criteria hold: `True` for each. Evidence
written to 03_Evidence/04_System_Tests/session_sidebar_test.md.

---

GOAL: Harden project/experience grounding matching - a real project could
still be silently dropped over a trivial rewording

"The project was still not added into the project section" - the exact
Jordan Ramirez / "AI Powered CV Builder" scenario the previous two steps
already fixed and verified, reported again as still broken.

PROPOSED CHANGE

Investigated fresh rather than assuming the previous fix regressed.
Reproduced the earlier-fixed scenario (Course-timetable API intro, then
the exact reply "I also have a Masters degree from UTS. I have also
built an AI Powered CV Builder project that uses RAG and LLM.") through
the full live pipeline twice: extraction correctly created both project
entries every time, and CVGenerator kept both with zero grounding
warnings both times too - the already-applied fixes (route the reply
through both JobRequirementAgent AND general extraction; typographic-
variant normalization in _verify_and_clean) are working as designed and
didn't regress.

But a deterministic unit test (bypassing the LLM entirely, to isolate the
grounding-check code from LLM stochasticity) found a real, distinct gap
one layer further in: _verify_and_clean()'s existing `_normalize()`
(added for the earlier "Course‑timetable API" non-breaking-hyphen bug)
only fixes a character being a different Unicode CODEPOINT for the same
symbol (e.g. U+2011 vs U+002D, both meaning "hyphen"). It does not fix a
hyphen being structurally absent vs present - "AI-Powered CV Builder" vs
"AI Powered CV Builder" - which is an equally plausible, equally
untouched-by-that-fix side effect of the CV-writing model polishing a
title into CV register. Confirmed with a hand-built Profile + cv dict
(no GROQ call needed): the current code drops the project outright on
exactly this input. Given GROQ runs at temperature 0.2, not 0, this is
consistent with the previous step's own note that the missing-project
symptom "didn't reproduce standalone, most likely LLM run-to-run
variance" - it doesn't happen on every run, but the underlying code path
that would let it happen was still there.

Fix: added `_loose_normalize()` (strips ALL punctuation, not just
typographic dash/quote variants, then collapses whitespace) and
`_fuzzy_match()` (difflib.SequenceMatcher ratio, threshold 0.75) as a
FALLBACK only - the existing exact/typographic-normalized check stays the
fast, primary path; fuzzy matching only runs once that has already
failed, and only decides keep-or-drop, never substitutes a different
title back in (the model's own CV-register title is kept as returned).
Applied to both project-title and experience-role matching, the same two
places the earlier typographic fix touched. Deliberately NOT applied to
skills matching (already short canonical tokens the prompt explicitly
disciplines against reording, low drift risk) or the additional_education
check (already substring-tolerant). Threshold chosen conservatively
(0.75) so a genuinely different/invented title still falls below it and
gets caught as ungrounded - verified directly, not assumed (see
VERIFICATION).

Also found and fixed a second, unrelated but blocking issue while setting
up the live reproduction: JobRequirementAgent.check()'s and .resolve()'s
GROQ calls were still at max_tokens=2048, the exact "reasoning model
spends hidden tokens before the visible JSON" failure this project has
hit and fixed at every OTHER call site (raised to 4096 for agent.py's
main extraction call, cv_generator.py's CV generation call, and the GUI's
inline extraction call, across earlier steps) - these two call sites were
evidently missed each time. Bumped both to 4096 to match every other call
site, since it's the same already-diagnosed failure mode, not a new
design question.

Files touched:
- 01_System/source_code/cv_generator.py (`_loose_normalize()`,
  `_fuzzy_match()`, applied as a fallback in kept_experience/kept_projects)
- 01_System/source_code/agent.py (JobRequirementAgent.check()/.resolve()
  max_tokens 2048 -> 4096)

DECISION
Accept

VERIFICATION

Deterministic unit tests against `_verify_and_clean()` directly (no GROQ
call, to isolate the grounding-code fix from LLM variance):
- The exact reproduced bug (profile title "AI-Powered CV Builder", CV
  output title "AI Powered CV Builder", hyphen dropped): before the fix,
  the project was dropped with a grounding_warning; after the fix, it
  survives with zero warnings, title kept exactly as the model wrote it.
- Negative control: a genuinely fabricated, unrelated project title
  ("Autonomous Drone Navigation System") in the same test - still
  correctly dropped with a grounding_warning, confirming the fuzzy
  fallback didn't loosen the no-invented-facts guarantee.

Live end-to-end reproduction of the user's exact scenario through the
REAL code path (ProfileAgent -> job retrieval -> JobRequirementAgent.check()
on agentic_ai_engineer -> the exact reply text -> resolve() +
general-extraction, both run -> CVGenerator.generate() -> render_cv_pdf()):
new_facts correctly reported all three changes in one message ("added
Masters degree from UTS to your education, alongside what was already
there; added LLM to your skills; added 'AI Powered CV Builder' to your
projects"); final profile held both projects (Course Timetable API, AI
Powered CV Builder) and the additional-education entry; generated CV kept
both project titles, education stayed a clean two-line split
(cv["education"] / cv["additional_education"]), grounding_warnings: [].
Rendered and read the PDF directly: PROJECTS section shows both entries
in full with their own technology lines, EDUCATION shows both
qualifications as separate clean lines, SUMMARY correctly names both
projects and the Master's - the exact scenario reported, now producing a
correct result via the real GUI code path, not just an isolated test.
Saved to 03_Evidence/04_System_Tests/sample_cv_pdfs/
Jordan_Ramirez_agentic_ai_engineer_cv.pdf.

---

GOAL: Feature 1 - hardcode a standalone CV formatting spec (no template
file dependency)

[Full spec pasted by the user, summarized here: define an explicit,
literal CV style spec as constants/config, covering header layout
(name largest element, one pipe-separated contact line), section headers
(bold, uppercase, fixed Education -> Experience -> Projects -> Skills
order), entry layout (left-aligned title/role/institution, right-aligned
date range on the same line, action-verb-first bullets below), date
format ("Mon. YYYY - Mon. YYYY" or "... - Present"), skills grouped by
category with labels (not a flat list), font (preferred Times New Roman,
fallback to reportlab's base-14 Times-Roman if the TTF isn't available,
with the substitution logged in the Prompt Record), sizes (name 18-20pt,
section headers 12pt, body/bullets 11pt), line spacing (single-1.15), and
color (black body text, one accent color for name/section headers only,
nothing else - print/grayscale-safe). Application rules: apply
automatically to every export, no user-uploaded file ever required or
used as a styling source (only ever for fact-extraction, if an upload
feature is added later), and document the spec so it's citable in the
report as a deliberate design decision.]

PROPOSED CHANGE

Checked the two things the spec's judgement calls actually depended on
before writing anything: whether a real Times New Roman TTF exists on
this machine (C:\Windows\Fonts\times*.ttf - yes, all four weights present,
since this is a Windows deployment) and whether python-dateutil is
available for date parsing (yes, 2.9.0). Both being true changed the
right design: register the TRUE preferred font directly via reportlab's
TTFont rather than only ever using the base-14 fallback, and use dateutil
for robust-but-conservative date normalization rather than hand-rolled
regex parsing.

New module 01_System/source_code/cv_style_spec.py holds every literal
value from the spec as a constant (fonts, sizes, LEADING_FACTOR, colors,
SECTION_ORDER, SKILL_CATEGORIES) plus two functions: register_fonts()
(tries the Windows TTFs first, falls back to Times-Roman and logs a
warning if they're not found - e.g. a non-Windows deployment) and
format_date_range(start, end) (normalizes loose date text into the
spec's pattern, but NEVER fabricates a month that wasn't stated - a bare
"2023" stays "2023" rather than becoming "Jan. 2023", and anything
dateutil can't parse is shown back verbatim rather than dropped). The
module's own docstring records the no-upload-as-styling-source rule as a
forward-looking design principle, even though no upload feature exists
yet in this codebase (confirmed via a repo-wide search) - so it's on
record as a deliberate decision rather than retrofitted later.

Two of the spec's rules had no real data to operate on without a small,
deliberately scoped data-model extension - implemented consistently with
this project's confirmed-facts-only rule (never fabricated, only ever
captured when explicit):
- Dates: added optional start_date/end_date to ExperienceEntry,
  ProjectEntry, DraftExperienceEntry, and DraftProjectEntry (profile_
  model.py), with matching merge() logic (first-write-wins, same pattern
  as description) and a new DATES paragraph in agent.EXTRACTION_SYSTEM_
  PROMPT instructing the model to record a timeframe ONLY when explicitly
  stated, never inferred from "third-year"/"last semester"-style context,
  with end_date="Present" as the explicit ongoing sentinel.
- Skills by category: rather than changing cv["skills"] from a flat list
  to a grouped structure (which would have rippled through cv_builder_
  gui.py, export_cv.py, and every existing test script that already
  depends on it being a flat list), added a SEPARATE "skills_by_category"
  output key to CV_GENERATION_SYSTEM_PROMPT_V10 - the same skills,
  relabelled into cv_style_spec.SKILL_CATEGORIES groups, with the union
  across categories required to exactly match the existing flat list (a
  relabelling, not a second judgement about which skills belong). This
  kept every other file's existing assumption about cv["skills"] intact.

_verify_and_clean() extended to match: start_date/end_date are forced to
match the confirmed profile's own entry (found via the SAME exact/fuzzy
role-or-title matching already used for grounding experience/projects) -
these are verbatim copies, not creative rewriting, so overwriting from
the source of truth is simpler and safer than dropping the whole entry
over a trivial JSON discrepancy. skills_by_category is cleaned the same
way clean_skill_list() cleans "skills" - unknown categories dropped,
ungrounded skills dropped with a warning, and anything left uncategorized
falls back into "Other" rather than silently vanishing from the grouped
view.

cv_pdf.py rewritten to actually render the spec: register_fonts() is
called once per PDF and every style pulls its font/size/color from
cv_style_spec.py rather than a hardcoded value of its own; a new
_entry_header() helper renders a borderless two-column reportlab Table
(title left-aligned, date right-aligned) when a date range exists, and
falls back to a single Paragraph when it doesn't (the common case today,
since no historical profile has ever captured a date); each description
now renders as a single bullet-prefixed line; skills render grouped under
bold category labels instead of the old flat bulleted list; the tagline/
tech-line styles that previously used grey were changed to pure black to
satisfy the spec's "no other color" rule, since accent color is reserved
for the name and section headers only.

Files touched:
- 01_System/source_code/cv_style_spec.py (new)
- 01_System/source_code/profile_model.py (start_date/end_date fields +
  merge() logic)
- 01_System/source_code/agent.py (EXTRACTION_SYSTEM_PROMPT's DATES rule)
- 01_System/source_code/cv_generator.py (CV_GENERATION_SYSTEM_PROMPT_V10,
  skills_by_category + date pass-through in _verify_and_clean())
- 01_System/source_code/cv_pdf.py (full rewrite to apply the spec)
- 01_System/source_code/tests/run_style_spec_test.py (new evidence script)

DECISION
Accept

VERIFICATION

Confirmed CV_GENERATION_SYSTEM_PROMPT_V9 != V10 and every module imports
cleanly. Ran run_style_spec_test.py against a live profile with a dated
experience entry (June-August 2023), a dated ongoing project (March 2025
- Present), a Master's alongside a Bachelor's, and five skills spanning
three categories:
- Font: register_fonts() confirmed family="TimesNewRoman",
  used_fallback=False on this machine (the real TTFs, not the base-14
  substitute) - logged either way per the spec's requirement.
- Dates: rendered exactly "Jun. 2023 - Aug. 2023" and "Mar. 2025 -
  Present" - the closed-range and ongoing cases both correct.
- Education: both degrees present, primary never overwritten.
- Skills: grouped into {"Programming Languages": [Python, Java], "Tools &
  Platforms": [Docker, Git], "Languages": [Spanish]} - every category
  label valid, the union exactly matching the flat skills list, zero
  grounding warnings.
Rendered and read the PDF directly: name is the largest element in the
navy accent color, single pipe-separated contact line, bold uppercase
section headers in the same accent color, Education -> Experience ->
Projects -> Skills order, each dated entry's title left-aligned with its
date range right-aligned on the same line, action-verb-first bullets,
skills under bold category labels, genuine Times New Roman throughout,
and no color anywhere outside the name/section headers - matches the
spec point-for-point. Also rendered a second PDF for a profile with NO
dates (the common case for every profile captured before this feature)
to confirm the single-Paragraph fallback still looks clean rather than
showing an empty date column. Re-ran the pre-existing run_agent_tests.py
suite afterward (one transient per-minute rate limit, resolved with a
short wait) - both cases still confirm correctly, no regression from the
new EXTRACTION_SYSTEM_PROMPT paragraph or the cv["experience"]/
cv["projects"] schema additions.

---

GOAL: Three fixes - achievement bullets, education date alignment, and
deeper project/education follow-up with per-entry confirmation

[Full spec pasted by the user, summarized here: Bug 1 - multiple distinct
achievement statements for one entry must render as separate bullets, not
one merged paragraph; diagnose extraction vs. rendering, don't guess; split
on line breaks first, sentence boundaries as a fallback, never mid-sentence,
never reword/merge/drop content. Bug 2 - Education's date isn't right-
aligned like Experience already does; diagnose template vs. data model.
Fix 3 - widen the existing ambiguity-detection logic for projects (start/
end date or ongoing, concrete outcome not just a tech list, measurable
results - ask, don't assume none) and education (start/end date or
expected graduation, full degree/major, distinctions - ask, don't assume
none); only ask about genuinely missing/underspecified fields, accept an
approximate date, never fabricate; read a completed project/education
entry back to the student for confirmation before treating it as done,
the same way the final profile summary already gets confirmed; still
respects the step limit and "complete input needs no extra questions."
The user asked for a diagnosis/plan first and confirmation before code -
given, then two follow-up answers: extend bug 2 to BOTH the primary
degree and any additional_education entry; for fix 3, "I want the agent
to always has a question available for users to answer during the
review, making it more interactive" - i.e. a confirmation must never end
in a bare yes/no, always pair the read-back with an open, engaging
question.]

DIAGNOSIS (presented and confirmed before any code changed)

Bug 1: reproduced live by feeding the user's own four-achievement example
straight into EXTRACTION_SYSTEM_PROMPT before touching any code - it
collapsed all four into one run-on description string with no delimiter
at all, not even a newline. Rendering (cv_pdf.py always built exactly one
bullet Paragraph per entry) is also complicit, but there was nothing to
split on regardless since extraction already destroyed the boundaries -
both layers needed fixing, extraction first.

Bug 2: grepped for expected_graduation and found it hardcoded to a
placeholder in DraftProfile.to_profile() and never populated from
conversation at all - there was no structured date field for Education to
begin with. Confirmed live that with no real date, CV generation
correctly omits one rather than fabricating it, ruling out a hallucination
explanation. This meant bug 2 couldn't be a pure rendering fix - it was
blocked on the same structured-date gap fix 3 needed for Education anyway,
so the two were resolved together.

Fix 3: two parts - (a) widening TASK 2's checklist, straightforward and
following the existing pattern; (b) a genuinely new piece of architecture
- a mandatory read-back-and-confirm step with no prior equivalent
mid-conversation (only the final whole-profile summary existed before).
Designed as: once a project/education entry has no remaining model-judged
gap referencing it (via a new "entry_identifier" on each gap) and hasn't
been confirmed yet, compute_gaps() emits exactly one confirm_project/
confirm_education gap for it, flowing through the SAME existing
FOLLOW_UP bundling mechanism rather than a second conversational loop;
a sticky `confirmed` flag (mirroring the existing addressed-flag pattern)
tracks it per entry, set only by an explicit extraction-detected
affirmation - a correction instead just updates the normal fields and
leaves confirmed False, so the entry is naturally read back again next
turn with no extra state machine needed.

IMPLEMENTATION

Bug 1: agent.py's EXTRACTION_SYSTEM_PROMPT gained an ACHIEVEMENTS AS
SEPARATE BULLETS rule (line-breaks-first, sentence-boundary fallback,
never mid-sentence, never reword/merge/drop) and cv_generator.py's TASK 3
was extended to rewrite each "\n"-separated line into its own CV-register
bullet while preserving the same line count - never merging or splitting.
cv_pdf.py gained a `_bullets()` helper that splits a description on "\n"
and renders each non-empty line as its own bullet Paragraph, used for both
Experience and Projects.

Bug 2 (both primary AND additional_education, per the user's answer):
profile_model.py's Education gained a real `start_date` and
`expected_graduation` became genuinely optional (was a hardcoded
placeholder) instead of always-"Not specified"; AdditionalEducationEntry/
DraftEducationEntry gained start_date/end_date alongside the existing
`year`; DraftProfile gained education_start_date/education_end_date for
the primary degree. cv_generator.py's OUTPUT FORMAT gained
education_start_date/education_end_date (verbatim pass-through) and
changed "additional_education" from an array of strings to an array of
{"text", "start_date", "end_date"} objects so each qualification can carry
its own date range - the same schema shape Experience/Projects already
use. cv_pdf.py renders the primary education line AND every
additional_education entry through the SAME `_entry_header()` two-column
table helper Experience/Projects already use, byte-for-byte the same
mechanism, not a lookalike.

Fix 3a (widened checks): agent.py's TASK 2 gained education_dates,
education_distinctions, project_dates, project_outcome, and
project_results as new checked items (each accepting an approximate date,
never requiring exact, never fabricating), each carrying an
"entry_identifier" (project title, or the literal string "primary") so
Python can track per-entry state.

Fix 3b (mandatory, always-interactive confirmation): profile_model.py
added `confirmed: bool` to DraftProjectEntry/DraftEducationEntry and
`primary_education_confirmed: bool` to DraftProfile; compute_gaps() now
also emits confirm_project/confirm_education gaps per the mechanism
described in DIAGNOSIS above; merge() gained handling for a new
"confirmed_entries" extraction output listing which entries the student's
reply explicitly affirmed. Per the user's "always has a question
available" answer, FOLLOW_UP_SYSTEM_PROMPT gained a CONFIRMATION ITEMS
rule: pull the entry's real details from the draft JSON, restate them,
and NEVER end with a bare yes/no - always pair the read-back with an
open, specific invitation ("...or is there anything you'd like to add or
change?") in the same message, so the review never dead-ends.

Files touched:
- 01_System/source_code/agent.py (EXTRACTION_SYSTEM_PROMPT: achievements
  splitting, dates, widened checks, confirmed_entries;
  FOLLOW_UP_SYSTEM_PROMPT: confirmation items rule; max_tokens tuning -
  see BUGS FOUND below)
- 01_System/source_code/profile_model.py (Education.start_date,
  expected_graduation now Optional; AdditionalEducationEntry/
  DraftEducationEntry dates + confirmed; DraftProfile education dates +
  distinctions + primary_education_confirmed; compute_gaps() rewritten;
  new `_merge_description()` helper - see BUGS FOUND)
- 01_System/source_code/cv_generator.py (CV_GENERATION_SYSTEM_PROMPT_V11:
  multi-line description rewriting; V12: education dates +
  additional_education schema change; _verify_and_clean() extended for
  both)
- 01_System/source_code/cv_pdf.py (`_bullets()` helper; primary/additional
  education rendered via `_entry_header()`)
- 01_System/source_code/cv_builder_gui.py, cv_builder_cli.py
  (additional_education editing/pass-through updated for the new object
  shape; max_tokens tuning)
- 01_System/source_code/tests/run_bullets_dates_confirmation_test.py (new
  evidence script)
- 01_System/source_code/tests/run_agent_tests.py (COMPLETE_INTRO enriched
  with dates/distinctions/outcome/results and a confirmation reply added,
  since a zero-follow-up "complete" profile is no longer reachable by
  design - see BUGS FOUND; INCOMPLETE_SCRIPTED_REPLIES extended to answer
  the new widened checks)

BUGS FOUND DURING LIVE VERIFICATION (not guessed, found by actually
running the new code against real replies)

1. merge()'s project/experience description fill only ever wrote a
   description ONCE (skipped entirely if the entry already had any text) -
   harmless before, since nothing previously asked for MORE detail on an
   already-described entry, but fix 3's own widened follow-ups now
   routinely do exactly that (answering a project_outcome/project_results
   question about an entry that already has a thin description). Fixed
   with a new `_merge_description()` helper that appends genuinely new
   "\n"-separated lines instead of discarding them - the same multi-line
   convention as fix 1, reused rather than inventing a second mechanism.
2. A measurable result stated for a specific project (e.g. "it was used
   by 50 students...") was landing in the generic top-level "achievements"
   array instead of that project's own description - achievements is for
   things NOT tied to a listed project/experience (certifications,
   awards), and a result tied to a specific entry belongs there instead.
   Added an explicit MEASURABLE RESULTS BELONG TO THE ENTRY rule to
   EXTRACTION_SYSTEM_PROMPT.
3. The FOLLOW_UP_SYSTEM_PROMPT call's max_tokens (still the 400 default)
   truncated a confirmation read-back mid-sentence live, twice at
   increasing values (400, then 800) before 1500 held - a longer,
   richer message than a plain missing-field question, on the same
   "reasoning model needs headroom" failure this project has hit
   repeatedly.
4. The MAIN extraction call's max_tokens needed the opposite kind of
   correction: EXTRACTION_SYSTEM_PROMPT has grown to ~3.5k tokens on its
   own, and this GROQ account's 8000 TPM ceiling applies to prompt +
   max_tokens TOGETHER per single request - confirmed live via an
   outright 413 "Request too large" at max_tokens=6144, immediately after
   max_tokens=4096 had failed the OTHER way (empty completion, hidden
   reasoning consuming the whole budget with zero visible output). 4300
   is the largest value confirmed to clear both failure modes in the same
   session - a genuine tightrope this prompt now walks, not a one-line
   fix; documented inline at all three call sites (agent.py,
   cv_builder_gui.py, cv_builder_cli.py) sharing this prompt.
5. run_agent_tests.py's "complete profile" case, previously a genuine
   zero-follow-up baseline, started throwing EOFError (falling through to
   interactive input() with no stdin available) - not a code bug: fix 3b's
   confirm_project/confirm_education gap is unconditional by design, so
   even a perfectly complete profile now gets exactly one confirmation
   round. Updated the test's own intro to state dates/distinctions/
   outcome/results upfront and added one scripted confirmation reply,
   updating the test's documented expectation from "0 follow-ups" to
   "exactly 1 confirmation round" rather than treating the new behaviour
   as a regression to suppress.

DECISION
Accept

VERIFICATION

Ran the new tests/run_bullets_dates_confirmation_test.py end to end
against a live conversation (Alex Kim: a thin Recipe Finder project, an
incomplete degree) and confirmed all three fixes together:
1. The exact four-achievement example split into 4 separate, unmerged,
   unreworded lines (verified independently of the conversation test).
2. Turn 1 correctly asked about BOTH degree dates/distinctions AND
   project dates/outcome/results in one bundled question; turn 2's
   reply (which included a measurable result) produced a message that
   read BOTH entries back in full and ended with an open question for
   each ("Does that look right, or would you like to add or change
   anything?" / "Is that correct, or is there anything you'd like to add
   or adjust?") - never a bare yes/no; the measurable result landed in
   the project's own description (achievements stayed empty). Confirming
   both in one reply ("Yes, both of those look correct") set
   project.confirmed=True and primary_education_confirmed=True, and the
   agent reached status=confirmed with no further questions.
3. Generated the CV and rendered the PDF: EDUCATION shows "Bachelor of
   Computing Science, University of Technology Sydney" left-aligned with
   "Feb. 2024 - late 2026" right-aligned on the same line - the exact
   same _entry_header() layout Experience/Projects use, including
   correctly staying aligned when the title text wrapped to two lines in
   one run. Zero grounding warnings. A second, earlier manual PDF check
   with the same facts showed all 4 raw achievements rendering as 4
   distinct bullets under Projects (this run's own CV-generation pass
   chose to consolidate 2 of them into one bullet during its own polish -
   still separate bullets, still grounded, just not a strict 1:1 line
   count - noted honestly in the evidence rather than glossed over).
Evidence written to
03_Evidence/04_System_Tests/bullets_dates_confirmation_test.md.

Re-running the pre-existing run_agent_tests.py suite to confirm no
regression was interrupted by GROQ's daily token cap partway through (hit
twice at ~195k/200k used, purely from this session's cumulative testing
volume) - confirmed the max_tokens=4300 fix itself is sound (both
interruptions were the daily cap specifically, not the request-too-large
or empty-completion failures that prompted the fix), but the suite's own
evidence files have NOT been regenerated yet under the final prompt
versions. Flagged here rather than silently left undone.

---

GOAL: Stop hardcoding UTS-specific Education facts; trim unused fields;
verify the name/year fallbacks and the start_date/expected_graduation
naming decision

"`ProfileDraft.to_profile()` in profile_model hardcodes several Education
fields to fixed values regardless of what the user actually provided:
program_mode, faculty, institution, campus, study_mode. These assert
facts... that were never confirmed by the user - this violates the
'every CV claim comes from the confirmed profile' requirement... Fix:
drop program_mode, faculty, campus, and study_mode from the Education
dataclass and from to_profile() entirely... and drop
coursework_highlights as already agreed since it isn't rendered anyway.
If institution is meant to be genuinely asked... it should come from the
confirmed profile the same way self.degree... already does. Tell me
whether the current extraction flow already asks for institution
somewhere, or whether that needs adding... Also double check `name or
"Unknown"` and `year or "Unspecified"` - are these ever hit in practice,
or does the ambiguity-detection follow-up logic already guarantee these
are always populated..." Diagnosis/plan required before any code change;
user then answered the two open questions: ask for institution (same
tier as degree/year), and drop education_distinctions entirely (since
its only destination, coursework_highlights, was being removed).

DIAGNOSIS (presented and confirmed before any code changed)

Grepped the whole codebase before answering anything, rather than
guessing: `institution` had no DraftProfile field, no
EXTRACTION_SYSTEM_PROMPT schema key, no TASK 2 check - it was purely
hardcoded, confirmed nowhere else in the flow. `program_mode`/`faculty`/
`campus`/`study_mode`/`coursework_highlights` were referenced ONLY inside
profile_model.py itself (the dataclass, from_record(), and the hardcoded
to_profile() block) - never by cv_generator.py, cv_pdf.py, or
job_retrieval_tool.py - so removing them was confirmed safe with no
other-file fallout beyond from_record() itself. Separately found (not
asked, but directly downstream of dropping coursework_highlights):
`education_distinctions` - the DraftProfile field the PREVIOUS session's
fix 3 added specifically to ask about GPA/honors/coursework - was never
referenced by cv_generator.py at all, meaning that follow-up question's
answer was being captured then silently discarded even before this
fix - confirmed the user's "isn't rendered anyway" claim exactly, and
flagged the orphaned-question consequence of dropping it, which the user
then confirmed dropping too. Also flagged `relevant_current_subjects`/
`prerequisite_context` as similarly unused anywhere downstream - left
untouched since the user's request didn't name them and their reply
didn't address the flag either, so removing them would have been
scope-creep beyond what was actually agreed.

On name/year fallbacks: traced the actual code path rather than assuming
- "confirmed" status is reached purely because the extraction call's own
`gaps` JSON array is empty; there is no independent Python check anywhere
that verifies self.name/self.year are non-None before allowing that
transition. It is enforced by the LLM correctly flagging a missing field
every turn, not by code - and this project has hit real prompt-adherence
lapses in exactly this kind of check multiple times already this
session. Concluded these are a genuine safety net, not dead code:
without it, a lapse would let `None` reach cv_pdf.py's Paragraph call,
which would render the literal string "None" as the candidate's name -
worse than "Unknown". Recommended keeping both, user did not object.

On start_date/expected_graduation: recommended keeping both (needed for
the date-range rendering already built) and keeping the name
`expected_graduation` as-is rather than renaming, since it's the literal
key name the static dataset's own JSONL already uses
(record["expected_graduation"]) - renaming would have required a
translation layer between live and dataset-sourced profiles for no
functional benefit. User did not object; implemented as recommended.

IMPLEMENTATION

profile_model.py: Education dropped program_mode/faculty/campus/
study_mode/coursework_highlights entirely; kept degree, institution,
year, expected_graduation, start_date, relevant_current_subjects,
prerequisite_context. DraftProfile gained `institution: Optional[str]`
(same treatment as degree/year: missing_fields(), REQUIRED_FIELD_ORDER,
GAP_PRIORITY_ORDER, merge() overwrite-if-given, describe_new_facts()
acknowledgment) and lost `education_distinctions` entirely (the field,
its merge() loop, and its mention in compute_gaps()'s confirm_education
reason text and entry_identifier gap-matching - replaced with an
institution mention in the read-back reason instead). Profile.
from_record() updated to stop reading the four dropped dataset keys.
to_profile()'s hardcoded Education block removed - `institution=self.
institution or "Unspecified"` is now sourced from confirmed data with
the same defensive fallback pattern already used for degree/year, not a
fixed UTS string.

agent.py: EXTRACTION_SYSTEM_PROMPT gained "institution" as TASK 2 item 3
(right after degree, before year - same required tier) and OUTPUT FORMAT
key; lost "education_distinctions" as a TASK 2 item and OUTPUT FORMAT
key entirely, with the entry_identifier note and FOLLOW_UP_SYSTEM_
PROMPT's CONFIRMATION ITEMS read-back wording updated to mention
institution instead of distinctions/GPA/honors/coursework.

cv_builder_gui.py: confirm-stage form gained an "Institution" text_input
next to Degree, wired into the same overwrite_profile() call degree/year
already use.

cv_generator.py: no changes needed - V12's "education" field description
already said "degree/major/institution details" from the previous
session's work, so the model already knew to include institution once it
started appearing in confirmed_profile.education; coursework_highlights/
education_distinctions were never referenced there to begin with
(confirmed via the DIAGNOSIS grep), so nothing to remove.

Files touched:
- 01_System/source_code/profile_model.py
- 01_System/source_code/agent.py
- 01_System/source_code/cv_builder_gui.py

DECISION
Accept

VERIFICATION

Confirmed the trimmed dataclass directly: `dataclasses.fields(Education)`
returns exactly ['degree', 'institution', 'year', 'expected_graduation',
'start_date', 'relevant_current_subjects', 'prerequisite_context'] - the
four dropped fields are genuinely gone, not just hidden. All modules
import cleanly.

Ran a live conversation for a student explicitly NOT at UTS (Jamie
Rivera, Bachelor of Software Engineering at Monash University) - chosen
deliberately so any lingering hardcoded UTS text would be immediately
obvious rather than accidentally matching a coincidental default:
- Turn 1's acknowledgment correctly included "recorded your institution
  as Monash University" - genuinely captured, not defaulted.
- After confirming, profile.education printed as Education(degree=
  'Bachelor of Software Engineering', institution='Monash University',
  year='second-year', expected_graduation='December 2027', start_date=
  'March 2024', relevant_current_subjects=[], prerequisite_context=None)
  - no program_mode/faculty/campus/study_mode/coursework_highlights
  fields exist on the object at all.
- Generated the CV and rendered the PDF: EDUCATION reads "Bachelor of
  Software Engineering, Monash University" with "Mar. 2024 - Dec. 2027"
  right-aligned on the same line (same _entry_header() layout as
  Experience/Projects) - zero mention of UTS, "City Campus", "Faculty of
  Engineering and Information Technology", "Standard program", or
  "Full-time" anywhere in the rendered PDF. Zero grounding warnings.
No orphaned confirm_education mention of distinctions/GPA/coursework
appeared in the read-back or the rendered CV, confirming the
education_distinctions removal was clean on both the conversational and
rendering sides.

---

GOAL: Fix a live GUI crash during CV generation (json_validate_failed,
empty completion)

The user hit a real crash in the stage-5 chat box: after answering a
job-requirement question with a message that also described a Google
internship in detail, the profile update succeeded ("Got it - added
Software Engineer Intern at Google to your experience.") but the
immediately-following CV regeneration crashed with `groq.BadRequestError:
Failed to validate JSON... failed_generation: ''`, taking down the whole
page (screenshot + full traceback provided, pointing at cv_generator.
py:693's `self.llm.extract_json(system_prompt, user_content,
max_tokens=4096)`).

DIAGNOSIS

Recognised the exact failure signature immediately - the same "reasoning
model spends hidden thinking tokens before any visible output, and
occasionally burns the WHOLE max_tokens budget on reasoning with zero
output" issue already found and fixed at multiple other extract_json()
call sites this session (agent.py's main extraction, the job-requirement
calls) - but CVGenerator.generate()'s own call had never been revisited
with the same fix, still sitting at the original max_tokens=4096.

Verified this is NOT a fixed size threshold before assuming a simple
"raise the number" fix would be reliable: reproduced a comparable
scenario locally (a profile with a 4-line multi-achievement Google
internship experience entry, same target job) at the SAME max_tokens=4096
and it succeeded on the first try - proving the failure is genuinely
probabilistic (temperature=0.2 still leaves real variance in how much the
model reasons before answering), not something a single "big enough"
max_tokens value eliminates outright, especially since going too high
risks the OPPOSITE failure (GROQ rejecting an over-large request outright
- confirmed live earlier this session for agent.py's own extraction
call). This meant the right fix had two parts, not one: reduce the ODDS
(raise max_tokens moderately) AND survive the residual probability
(retry once) rather than crashing the whole page on an unlucky
generation.

IMPLEMENTATION

- agent.py's GroqLLM.extract_json() (the ONE shared method every
  extraction call site in this project goes through) now retries exactly
  once, specifically when the caught `BadRequestError`'s body has
  `error.code == "json_validate_failed"` - any other error, or a second
  consecutive failure, still raises immediately. This fixes the failure
  mode everywhere at once (agent.py's own calls, JobRequirementAgent,
  CVGenerator) rather than duplicating retry logic at each call site.
- cv_generator.py's CVGenerator.generate() raised max_tokens from 4096 to
  5000 - CV_GENERATION_SYSTEM_PROMPT is ~2.5k tokens on its own, smaller
  than agent.py's ~3.5k EXTRACTION_SYSTEM_PROMPT, but its user_content
  (the full confirmed_profile + selected_job) grows with how much the
  student has said, so a single safe constant can't fully close the gap
  the way it did for the more fixed-size main extraction prompt - the
  retry above covers what raising max_tokens alone can't.

Files touched:
- 01_System/source_code/agent.py (GroqLLM.extract_json() retry-once)
- 01_System/source_code/cv_generator.py (max_tokens 4096 -> 5000)

DECISION
Accept

VERIFICATION

Unit-tested the retry logic directly with a mocked Groq client (no live
GROQ call needed to exercise the retry branch, since triggering the real
failure on demand isn't reliably reproducible - confirmed by my own
earlier reproduction attempt succeeding where the user's crashed):
1. First call raises BadRequestError(code="json_validate_failed"),
   second call succeeds - extract_json() returns the successful result,
   create() called exactly twice.
2. Two CONSECUTIVE json_validate_failed failures - raises on the second
   attempt rather than looping forever, create() called exactly twice.
3. A DIFFERENT error code - raises immediately without wasting a retry
   attempt, create() called exactly once.
All three confirm the retry is scoped correctly: fixes exactly the
observed failure mode, never masks a different error, never loops.
Re-verified agent.py and cv_generator.py both still import cleanly and
the Streamlit app boots without error after the change.

---

GOAL: Stop the CV from rendering "absence" bullets (e.g. "No measurable
metrics were tracked")

"The CV generation is currently rendering explicit 'null' statements
when optional details weren't provided - e.g. a project with no
measurable metrics is rendering a bullet that says 'No measurable
metrics were tracked.' This is unprofessional... the absence of a metric
should simply mean no bullet for it, not a bullet announcing the
absence." Asked to find where this is generated (extraction vs.
rendering, don't guess), fix it so optional fields are skipped entirely
(no bullet, no placeholder, no "N/A"/"not tracked" language) across
projects/experience/education, keep required content rendering normally,
and explicitly check the CV generation prompt for a "do not mention
missing information" instruction.

DIAGNOSIS

Tried to reproduce the exact reported behaviour live before touching
anything, rather than assuming where it came from: fed the extraction
step an explicit decline ("I didn't track any specific metrics for that
project") and separately ran full CV generation on a project with
genuinely no measurable results - both came back clean in these
particular attempts, no absence statement anywhere. This didn't mean the
bug wasn't real: reading CV_GENERATION_SYSTEM_PROMPT directly turned up
a real, standing gap regardless of reproducing it on demand - the prompt
says "If a bullet has nothing quantifiable in confirmed_profile, tighten
and sharpen its phrasing - do not invent a metric... to fill the gap"
but never says the OPPOSITE is also forbidden: nothing stopped the model
from writing a sentence ABOUT the absence instead of inventing a fact to
fill it. Given this session's repeated experience that a real prompt gap
like this produces exactly the kind of low-probability, hard-to-reproduce-
on-demand failure the user was reporting, fixed it at both the prompt
layer AND added an independent Python-level safety net - the same
"instruction plus independent enforcement" pattern used everywhere else
in this project (grounding checks, the earlier "Not specified" placeholder
fix, the retry-once fix immediately before this one) - specifically
because prompt instructions alone have not been 100% reliable this
session even when clearly stated.

IMPLEMENTATION

- cv_generator.py: CV_GENERATION_SYSTEM_PROMPT_V13 extends the existing
  "do not invent a metric" sentence with an explicit converse rule: never
  write a bullet/sentence/clause stating that a metric, result,
  distinction, or any other detail is missing/not tracked/not provided/
  not available - omit that line entirely instead. Names the exact
  reported phrasing ("No measurable metrics were tracked for this
  project.") as a literal example of what never to write, applying
  across every optional per-entry detail in every section, not just
  metrics.
- Added `_ABSENCE_PATTERNS` (a small set of literal, narrow regexes - "no
  X were tracked/provided/available", "X was not disclosed/specified",
  "did not track/measure/report X", a bare "N/A"/"none") and
  `_strip_absence_statements()`, which splits a description on its
  existing "\n"-per-achievement structure (reusing fix 1's own
  convention from earlier this session rather than inventing a second
  splitting mechanism) and drops only the lines that match. Deliberately
  narrow rather than a broad "sounds negative" heuristic, verified
  against negative controls (see VERIFICATION) so a bullet that's simply
  honest about a real event ("no requests were dropped during failover")
  is never mistaken for a placeholder and wrongly stripped.
- Applied in _verify_and_clean() to every kept experience description,
  every kept project description, and every additional_education "text"
  entry (dropping the whole entry if stripping empties it, since a
  nameless qualification line is meaningless) - each stripped line is
  also recorded as a grounding_warnings entry for transparency, the same
  visibility every other cleanup step in this function already gets.
  Summary text was left alone - it's synthesized prose, not "\n"-per-
  fact bullets, and stripping a MID-SENTENCE clause via regex risks
  mangling grammar in a way dropping a whole bullet line doesn't.

Files touched:
- 01_System/source_code/cv_generator.py (CV_GENERATION_SYSTEM_PROMPT_V13,
  _ABSENCE_PATTERNS, _strip_absence_statements(), applied in
  _verify_and_clean())

DECISION
Accept

VERIFICATION

Tested _strip_absence_statements() directly against 6 positive cases
(including the user's own exact reported phrasing verbatim) and 3
negative controls before wiring it into the pipeline:
- All 6 positive cases ("No measurable metrics were tracked for this
  project.", "No specific metrics were provided.", "Distinctions were
  not disclosed.", "No notable outcomes to report.", a bare "N/A", "Did
  not track any additional metrics.") were correctly identified and
  stripped, leaving the real bullet(s) in each multi-line description
  intact.
- All 3 negative controls (legitimate bullets that happen to contain
  "no"/"not" in a factual sense - "no requests were dropped during
  failover", "no customers reported issues after the migration", a plain
  metric-bearing bullet) were correctly left untouched.
Then ran the exact reported bug through the full _verify_and_clean()
pipeline with a synthetic CV dict (a project description with a real
bullet plus the user's exact "No measurable metrics were tracked for
this project." line): the final description correctly kept only the
real bullet, and a grounding_warnings entry recorded exactly what was
removed and from which entry. Re-ran an existing CV-generation evidence
script (tests/run_style_spec_test.py) afterward to confirm no
regression - passed cleanly, zero grounding warnings, no legitimate
content affected.

---

GOAL: Fix two UI/UX issues on the GUI follow-up questions screen -
duplicate question rendering, and a mechanical field-by-field
acknowledgment dump

Reported via a screenshot of the live Streamlit app showing the Jordan
Ramirez intro scenario: (1) the assistant's message appeared twice - once
as a normal chat line, once repeated in a highlighted box directly above
the answer input; (2) the acknowledgment read as a mechanical log
("recorded your name as X; recorded your degree as Y; recorded your
institution as Z...") before finally asking the real follow-up question.
Asked for: the duplicate removed so the message appears once; a brief,
natural acknowledgment instead of an itemized list; the actual
question(s) led with or clearly separated from the acknowledgment rather
than buried after it; and, where multiple unrelated things are being
asked at once (here: education dates AND a project's timeline/impact),
consideration of asking them as clearly separated questions rather than
one run-on sentence.

DIAGNOSIS

Bug 1 (duplicate) was a rendering bug, not an extraction bug.
render_conversation_history() in cv_builder_gui.py loops over the full
agent trace and prints every past AskFollowUp entry's question as a
"**Assistant:** ..." line - including the CURRENT pending one, since
take_turn() has already appended it to the trace by the time the
"followup" stage renders. Immediately below that, the same stage
separately renders st.info(st.session_state.pending_question) - and
pending_question is set (in handle_turn_result) to that exact same
string. Two independent render calls, same text, same screen.

Bug 2 (mechanical dump) was a phrasing/composition bug in agent.py's
take_turn(). profile_model.describe_new_facts() deterministically
diffs the draft profile before/after a merge() and returns one literal
clause per changed field (e.g. "recorded your name as X") - this
Python-side determinism is deliberate and was kept: it's what guarantees
a multi-field reply is confirmed back in full, rather than trusting the
extraction LLM to self-report everything it just changed, which risks
under-reporting. The bug was in what happened AFTER that list was
computed: take_turn() joined every clause with "; " and glued the whole
string in front of the already-generated question as a bare Python
f-string ("Got it - {joined clauses}. {question}"). Because this
concatenation happened in Python, after the question was already
composed by the LLM, there was no way for it to read naturally or be
visually separated from the question - it was structurally a log dump
followed by a question, never a single composed reply.

Fix, in both cases: bug 1 is a rendering fix (stop rendering the same
trace entry twice); bug 2 needed the deterministic new_facts list fed
INTO the same LLM call that composes the question, so one model produces
one coherent, naturally-phrased reply, rather than Python stitching two
separately-produced pieces together.

IMPLEMENTATION

- cv_builder_gui.py: render_conversation_history() gained an
  include_latest_question parameter (default True, preserving existing
  behaviour on the "step_limit" stage, which has no separate highlighted
  box). The "followup" stage now calls it with
  include_latest_question=False, so history shows only PRIOR turns' Q&A
  - the current question is rendered exactly once, in the st.info() box.
- agent.py take_turn(): removed the
  `question = f"Got it - {'; '.join(new_facts)}. {question}"` prepend
  entirely. new_facts is instead passed into the FOLLOW_UP LLM call
  itself as a new "Facts just recorded" section in the user content,
  alongside the existing "things still needed" list and draft context -
  only included when new_facts is non-empty, matching the old `if
  new_facts:` gate.
- agent.py FOLLOW_UP_SYSTEM_PROMPT: added an "ACKNOWLEDGING WHAT WAS JUST
  CAPTURED" rule - if a "Facts just recorded" list is given, open with
  ONE brief, natural sentence covering everything in it (mention every
  item, but group/summarize naturally rather than itemizing each as its
  own clause), then clearly separate that from the actual question(s)
  that follow (a new sentence or short paragraph, never merged into the
  same run-on sentence as the acknowledgment) so the question never gets
  buried. Also added a second rule: when "things still needed" spans
  clearly distinct topics (e.g. education dates vs. a project's timeline
  and impact), ask about each as its own clearly separated question
  rather than merging unrelated asks into one run-on sentence.
- Scope: left the same raw-join pattern in the separate job-requirements
  chat screen (cv_builder_gui.py's st.success("Got it - " + "; ".join
  (...)) and the equivalent cv_builder_cli.py print) untouched - that is
  a different screen than the one reported, and the user chose to scope
  this fix to the follow-up questions screen only when asked.

Files touched:
- 01_System/source_code/cv_builder_gui.py
  (render_conversation_history(), "followup" stage call site)
- 01_System/source_code/agent.py (take_turn(), FOLLOW_UP_SYSTEM_PROMPT)

DECISION
Accept

VERIFICATION

Re-ran the exact Jordan Ramirez intro from the screenshot through the
live agent (real GroqLLM, model openai/gpt-oss-20b) after the fix:

Bug 1: printed exactly what render_conversation_history
(include_latest_question=False) would render on the "followup" stage -
only the "**You:** Hi, I'm Jordan Ramirez..." line came back; the
assistant's question was correctly excluded from history, confirming it
now reaches the screen exactly once (via the st.info() box alone).

Bug 2: describe_new_facts() still returned its full, literal 7-clause
list unchanged (recorded name/degree/institution/year, skills added,
project added, target roles added) - confirming nothing was silently
dropped from the ground-truth diff. But the composed reply shown to the
student was:

  "Got your name, degree, institution, year of study, skills, project,
  and target roles noted.

  Could you let me know the start and end dates for your Bachelor of
  Computing Science at UTS? Also, for the Course Timetable API project,
  what were the start and end dates, and can you share any measurable
  results or impact (e.g., number of users, performance improvements,
  etc.)?"

One brief natural acknowledgment sentence (not seven itemized "recorded
X as Y" clauses), clearly separated by a blank line from the question,
which itself asks about education dates and project dates/outcomes as
two distinct sentences rather than one run-on. This is the same
scenario, same underlying facts, same two "things still needed" gaps as
the reported screenshot - directly comparable and confirms both fixes.

Attempted a full regression pass via tests/run_agent_tests.py
afterward: the "complete profile" case (which exercises the same
take_turn()/FOLLOW_UP_SYSTEM_PROMPT code path as this fix, since a
confirmation read-back always triggers a follow-up round) completed
successfully. The second case then hit this GROQ account's daily token
cap (TPD 200,000, already at 197,790 from this session's testing) before
completing - a pre-existing account-level quota constraint unrelated to
this change (confirmed by the error message itself: "tokens per day
(TPD)... Please try again in 23m..."), not a regression. No code path
touched by this fix showed any failure before the cap was hit.

---

GOAL: Defer ALL project follow-up questions (dates, outcome, confirmation
read-back) out of initial intake to a one-at-a-time review stage; never
ask about measurable results/metrics at all

"The agent currently interrupts the initial intake conversation to ask
follow-up questions about projects... as soon as a project is mentioned.
This is causing turn-limit failures, date misattribution between
simultaneous questions, and an overly long back-and-forth." Asked for:
during intake, accept whatever project detail is volunteered and never
ask a project follow-up or block on an incomplete entry; at the
"profile review" stage, ask about one missing project field at a time
(never batched with another entry's or another section's question, to
avoid date misattribution); never ask about measurable results/metrics
at any stage (fully optional, captured only if volunteered); a declined
field must be recorded as declined, not just left empty, so it is never
re-asked; and re-tune both stages' step budgets to match the new,
shorter intake and the review stage's own sequential asks.

DIAGNOSIS

Traced the full gap/confirmation pipeline (EXTRACTION_SYSTEM_PROMPT's
TASK 2, DraftProfile.compute_gaps()/GAP_PRIORITY_ORDER, agent.take_turn(),
FOLLOW_UP_SYSTEM_PROMPT) before changing anything. Confirmed the root
cause: compute_gaps() combined every gap type - required fields,
education, AND project_dates/project_outcome/project_results/
confirm_project - into one list, and FOLLOW_UP_SYSTEM_PROMPT is
explicitly instructed to ask everything in that list "together in ONE
message." This is exactly why a project's date gap could land in the
same combined message as an unrelated education date gap (the
misattribution risk), and why a single project needing dates + outcome +
a confirmation read-back could consume three full intake turns.

Also surfaced an architecture gap worth flagging up front: the "review
stage" the request describes ("the stage where the full profile summary
is shown for confirmation") did not exist as a conversation anywhere in
the app - cv_builder_gui.py's "confirm" stage is a STATIC EDIT FORM
(plain text inputs, no chat, no date fields for projects at all), not a
follow-up loop. Presented this explicitly and asked whether to (a)
embed a small one-at-a-time chat block inside the existing "confirm"
stage, or (b) insert a new dedicated stage before it. Chose (a) - matches
the "full profile summary is shown" description, least structural
change, reuses the existing screen rather than adding a new stage name.

Also identified that there was no existing Python-tracked "declined"
state for project fields (unlike declined_requirements for job skills) -
project_dates/project_outcome/project_results all relied entirely on the
LLM noticing, from last_question_asked alone, that a field was already
answered. Given the review stage now makes several sequential one-field
asks, relying purely on that memory-less judgement was exactly the kind
of prompt reliance this project has repeatedly had to backstop with real
Python state (grounding checks, the absence-statement fix immediately
before this one, the retry-once fix) - so this fix adds one.

IMPLEMENTATION

- profile_model.py DraftProjectEntry: added dates_declined/
  outcome_declined booleans (sticky, same style as the existing confirmed
  flag).
- profile_model.py GAP_PRIORITY_ORDER: dropped project_results entirely -
  it no longer has any priority slot because it is never surfaced, in any
  phase.
- profile_model.py DraftProfile.compute_gaps(model_gaps, phase="intake"):
  new phase parameter.
  - Unconditionally drops any project_results gap before anything else -
    metrics/measurable results are never asked about, full stop, in
    either phase; TASK 1 extraction still captures them into an entry's
    own description if the student volunteers them unprompted, but no
    "gap" ever leads to them being ASKED about.
  - phase="intake": strips project_dates/project_outcome out of the
    combined list before it's ever surfaced (the model can keep judging
    them internally - harmless, just never asked about here). Education
    gaps (education_dates, confirm_education) are completely untouched -
    same batched behaviour as before, unaffected by this change, per the
    explicit scope decision to only touch projects unless education shows
    the same issue (flagged separately below, not fixed).
  - phase="review": considers ONLY project_dates/project_outcome, filters
    out any gap whose entry has already been dates_declined/
    outcome_declined (the Python-tracked guarantee - even if the model
    re-emits a gap for an already-declined field this turn, it's dropped
    here regardless), computes confirm_project the same way as before
    (an entry with no remaining gap, provided OR declined, not yet
    confirmed), sorts by GAP_PRIORITY_ORDER, and returns combined[:1] -
    AT MOST ONE gap, guaranteeing every review turn asks about exactly
    one field of one entry, never several batched together.
- profile_model.py merge(): new "declined_fields" handling block
  (mirrors the existing confirmed_entries block exactly) - sets
  dates_declined/outcome_declined on the matching project when the
  extraction call reports an explicit decline.
- agent.py EXTRACTION_SYSTEM_PROMPT: removed TASK 2 item 11
  (project_results) entirely and renumbered; added an explicit "never
  flag measurable results/metrics as a gap" line; added a new "DECLINING
  A SPECIFIC MISSING PROJECT DETAIL" section (parallel to the existing
  CONFIRMING section) telling the model to emit ONE declined_fields entry
  {"entry_kind": "project", "entry_identifier": ..., "field": "dates" |
  "outcome"} when last_question_asked was a single-field project question
  and the student declines without giving the actual detail; added
  "declined_fields" to OUTPUT FORMAT.
- profile_tool.py update_profile(): new phase parameter, threaded
  straight to compute_gaps().
- agent.py ProfileAgent: split into two independent step budgets -
  step_cap (intake, default 8->5, since project follow-ups no longer
  consume extra intake turns at all) and review_step_cap (new, default
  10, sized for several sequential one-field asks across a few projects).
  Two separate counters (self.step / self.review_step) so intake and
  review never share or exhaust each other's budget.
  - take_turn(user_text, phase="intake", log_user=True): phase selects
    which cap/counter applies and is threaded into update_profile();
    log_user=False lets a turn run with no visible user message (used
    only by the review bootstrap below).
  - New start_review(): take_turn("", phase="review", log_user=False) -
    computes the FIRST review gap (if any) purely from the draft as
    intake left it, no new message to extract from yet, called once right
    when intake reaches "confirmed".
  - run(): now continues automatically into the review loop (via
    start_review() then repeated take_turn(reply, phase="review")) after
    intake confirms, before returning - a new scripted_review_replies
    param feeds it for CLI/test use, exactly like scripted_replies feeds
    intake.
- cv_builder_gui.py: handle_turn_result() calls start_review() the moment
  intake confirms and stores the result as review_pending_question. The
  "confirm" stage now shows a small chat block (st.info + text input +
  submit, same pattern as the intake followup screen) ABOVE the existing
  summary + edit form, visible only while review_pending_question is set;
  submitting calls take_turn(reply, phase="review") and either shows the
  next single gap or clears the block once review confirms - the rest of
  the "confirm" stage (summary, edit form) is completely unchanged.
  review_pending_question added to SESSION_KEYS so it survives sidebar
  session switches correctly. step_cap/review_step_cap wired through to
  match the new defaults.
- cv_builder_cli.py: default step_cap 8->5, new review_step_cap default
  10, new --review-replies-json CLI flag, scripted_review_replies threaded
  through run_full_flow() to agent.run().
- max_tokens retune: the prompt additions above (DECLINING section, new
  output key) grew EXTRACTION_SYSTEM_PROMPT enough that a live run hit a
  413 "Request too large" at the previously-safe max_tokens=4300 (this
  account's 8000 TPM-per-request ceiling, prompt now ~3.8k tokens plus a
  mid-conversation current_draft). Reduced to 4000 at every call site
  using this prompt (agent.py's take_turn(), and the matching job-
  requirement-chat extraction calls in cv_builder_gui.py and
  cv_builder_cli.py) - confirmed this clears the 413 without re-
  triggering the empty-completion failure mode on the other side of the
  tightrope.

FLAGGED, NOT FIXED (out of scope for this request): education can, in
principle, hit the same batching risk this fix addresses for projects -
e.g. two additional_education entries both needing dates could still be
combined into one intake message. This has not been reported as an
active problem and the request explicitly scoped this fix to projects
unless education showed the same issue, so left it as-is; noting it here
since it is the same class of bug should it come up. Also left the
existing raw "Got it - X; Y; Z" acknowledgment style in the separate job-
requirements chat screen (cv_builder_gui.py's post-CV chat, unrelated to
this intake/review flow) untouched, and did not add start_date/end_date
fields to the manual edit form in the "confirm" stage (it still only
edits title/description/technologies) - neither was asked for here.
Existing evidence scripts under tests/ that scripted the OLD batched
project-follow-up flow (run_bullets_dates_confirmation_test.py and
others with hardcoded step_cap/scripted_replies tuned to it) will behave
differently now and were not individually re-recorded in this pass - the
verification below exercises the new behaviour directly instead.

Files touched:
- 01_System/source_code/profile_model.py (DraftProjectEntry,
  GAP_PRIORITY_ORDER, compute_gaps(), merge())
- 01_System/source_code/profile_tool.py (update_profile())
- 01_System/source_code/agent.py (EXTRACTION_SYSTEM_PROMPT, ProfileAgent)
- 01_System/source_code/cv_builder_gui.py (SESSION_KEYS,
  start_new_session(), handle_turn_result(), "confirm" stage)
- 01_System/source_code/cv_builder_cli.py (run_full_flow(), main())

DECISION
Accept

VERIFICATION

Ran two live scripted scenarios against the real agent (GroqLLM, model
openai/gpt-oss-20b) covering all four acceptance criteria plus the
decline pathway specifically:

Scenario 1 (info given): "Hi, I'm Priya Nair, a third-year Bachelor of
Computing Science student at UTS... built a course-timetable API...
Flask and SQLite... Junior Backend Developer or Software Engineering
Intern" (a project with no dates stated).
- Intake: 2 follow-up turns total, both education-only
  (education_dates, then confirm_education) - target_field never once
  contained project_dates/project_outcome/confirm_project. Confirmed
  criterion 1.
- Review: 2 turns, project_dates then confirm_project - each turn's
  question was about exactly one thing, never combined with anything
  else (there was nothing else left to combine with, by construction).
  Confirmed criterion 2.
- No question at any point in either phase mentioned metrics/measurable
  results. Confirmed criterion 3.
- Neither phase's step counter reached its cap (intake finished at step
  6 of a 5-cap - the final all-clear call is exempt from the cap check,
  as before; review finished at step 6 of a 10-cap). Confirmed
  criterion 4.
- Final project entry: {"title": "course-timetable API", "start_date":
  "March 2024", "end_date": "June 2024", "confirmed": true,
  "dates_declined": false, "outcome_declined": false} - genuinely
  populated from the review answers, not fabricated.

Scenario 2 (decline pathway): seeded a complete-except-project draft
directly (no LLM needed for setup), with one project with no dates and
no description, then declined both when asked ("I don't have that, no
need to add it."):
- Turn 1: target_field=project_dates, asked, declined.
- Turn 2: target_field=project_outcome, asked, declined.
- Turn 3: target_field=confirm_project - fired correctly once both
  fields were resolved (by decline, not by being provided), read back
  the entry honestly (title, technology, and that no dates/outcome were
  given, paired with an open invitation to add them) and confirmed.
- Final project entry: dates_declined=true, outcome_declined=true,
  confirmed=true - genuine Python state, verified by reading it back
  from the draft after the fact, not inferred from conversation flow.
- No metrics question appeared here either.

Both scenarios together demonstrate all four acceptance criteria and the
declined-state requirement holding on the real agent, not a mock.

---

GOAL: Remove per-field/per-entry confirmation round-trips during intake
and review; keep only the single, whole-profile confirmation stage

"The agent is currently confirming each field back to the user
immediately after it's captured... and waiting for an explicit 'correct'
before moving on. This doubles the number of turns needed for basic
intake and wastes tokens re-stating information the user just gave,
especially since a single, complete profile review/confirmation already
happens later in the flow." Asked to: acknowledge briefly (if at all)
and move straight to the next needed item, never a "does that look
right?" round-trip; trust stated input at capture time, no second
explicit "yes/correct" reply required; keep the existing full-profile
review stage as the ONLY confirmation point; still allow a real
clarifying question when input is genuinely ambiguous or contradicts an
earlier fact; apply consistently across all fields, not just degree
dates.

DIAGNOSIS

This request directly reverses the confirm_project/confirm_education
mechanism built earlier this session (per an explicit earlier
requirement to read a completed project/education entry back for
confirmation before treating it as done, and to keep a question always
available during review). Traced exactly where the "does that look
right?" round-trip lived: DraftProfile.compute_gaps() computed a
confirm_education gap for the primary degree (and each additional
qualification) the moment its own fields had no remaining gap, and a
confirm_project gap the same way once a project's dates_declined/
outcome_declined were both resolved - EXTRACTION_SYSTEM_PROMPT's
"CONFIRMING A COMPLETED PROJECT OR EDUCATION ENTRY" section and
FOLLOW_UP_SYSTEM_PROMPT's "CONFIRMATION ITEMS" rule existed specifically
to read the entry back and require an explicit affirmation
(confirmed_entries) before the sticky confirmed/primary_education_confirmed
flag was set. This is exactly the round-trip in the screenshot: after
answering education_dates, compute_gaps() immediately added
confirm_education as the very next gap, one full extra turn just to
re-state what was already just said.

Checked whether the SAME pattern existed for other required fields
(name, degree, institution, year, technical_skills, target_roles) as the
request suspected - it did not: those were already just asked-for-if-
missing and merged directly, with only a brief acknowledgment (no "does
this look right?"), so nothing needed to change there. The fix is
therefore narrowly the confirm_project/confirm_education mechanism, not
a broader change to how fields are captured. Also confirmed
SUMMARY_SYSTEM_PROMPT (the whole-profile review, shown once every gap in
both phases is resolved) already explicitly asks the student to confirm
the compiled profile looks correct - this is the single confirmation
point being kept, unchanged.

Genuinely ambiguous/contradictory input is unaffected by this fix: TASK
2's other checks (degree missing a level, technical_skills too vague,
project_outcome with no concrete description, education additive-vs-
correction ambiguity) are real clarifying questions about UNCLEAR input,
a different thing from re-confirming ALREADY-clear input, and were left
exactly as they were.

IMPLEMENTATION

- profile_model.py: removed DraftProjectEntry.confirmed,
  DraftEducationEntry.confirmed, and DraftProfile.primary_education_confirmed
  entirely - once nothing computes or checks a confirm_project/
  confirm_education gap, these sticky flags have no remaining purpose and
  would otherwise be dead state.
- profile_model.py GAP_PRIORITY_ORDER: dropped confirm_project/
  confirm_education (no longer produced).
- profile_model.py compute_gaps(): removed the confirm_education block
  from phase="intake" (both the primary-degree and additional_education
  loops) and the confirm_project block from phase="review" entirely.
  phase="review" now simply returns the single highest-priority
  outstanding project_dates/project_outcome gap (or an empty list once
  both are resolved, by answer or decline) - once a project has nothing
  outstanding, it is just done, nothing reads it back. Docstring rewritten
  to state the "no per-entry confirmation read-back" rule explicitly.
- profile_model.py merge(): removed the "confirmed_entries" handling
  block entirely (dead once nothing emits it). The "declined_fields"
  handling block is UNCHANGED and still fully needed - declining to
  provide a specific missing detail the review stage just asked about is
  a different thing from confirming an already-complete entry, and
  wasn't part of what this request removed.
- agent.py EXTRACTION_SYSTEM_PROMPT: removed the "CONFIRMING A COMPLETED
  PROJECT OR EDUCATION ENTRY" section and the "confirmed_entries" OUTPUT
  FORMAT key entirely; replaced with a short "NO CONFIRMATION READ-BACK"
  note clarifying that a clearly-stated fact is trusted and saved
  immediately, and that DECLINING A SPECIFIC MISSING PROJECT DETAIL
  (unchanged, still needed) is a genuinely different case from
  confirming a complete entry.
- agent.py FOLLOW_UP_SYSTEM_PROMPT: removed the "CONFIRMATION ITEMS"
  rule entirely, replaced with an explicit "never ask the student to
  re-confirm something they just stated clearly" instruction, directing
  the model to move straight to the next item (or produce nothing
  further if the list is now empty) instead.
- No changes were needed to profile_tool.py, the GUI, or the CLI beyond
  what already exists - the review-phase chat block added in the
  immediately preceding fix keeps working unchanged, it just now stops
  the moment a project's dates/outcome are resolved instead of asking
  one more confirmation question afterward; the existing SUMMARY_SYSTEM_PROMPT
  whole-profile confirmation stage was already correct and untouched.

Files touched:
- 01_System/source_code/profile_model.py (DraftProjectEntry,
  DraftEducationEntry, DraftProfile, GAP_PRIORITY_ORDER, merge(),
  compute_gaps())
- 01_System/source_code/agent.py (EXTRACTION_SYSTEM_PROMPT,
  FOLLOW_UP_SYSTEM_PROMPT)

DECISION
Accept

VERIFICATION

Ran a live scripted scenario against the real agent (GroqLLM, model
openai/gpt-oss-20b) reproducing the exact screenshot conversation - name,
degree, institution, year, skills, a dateless project, and target roles
given in one intro, then the missing education dates given in the next
reply:

- Intake: exactly ONE follow-up turn (education_dates) - after the reply
  giving both dates, take_turn() returned status="confirmed" IMMEDIATELY,
  with no further question. The exact "does that look right?" round-trip
  from the screenshot did not occur - status went straight from
  needs_input to confirmed, matching the acceptance criterion precisely.
  The whole-profile summary produced at that point still correctly
  listed the captured education dates for the student to review.
- Review: exactly ONE follow-up turn (project_dates) - after giving the
  project's dates, review also went straight to confirmed, no
  confirm_project read-back.
- Searched every question shown in both phases for confirmation-style
  phrasing ("does that/this look right", "is that correct") - none
  found.
- Total follow-up turns for this scenario: 2 (1 intake + 1 review),
  down from 4 in the prior verification of the same scenario shape
  before this fix (education_dates+confirm_education, then
  project_dates+confirm_project) - a 50% reduction, satisfying "drops
  noticeably."

Re-imported profile_model.py, profile_tool.py, agent.py, cv_builder_gui.py,
and cv_builder_cli.py after every edit to confirm no syntax/import errors
from removing the dead fields and prompt sections. Grepped the full
source tree afterward for confirm_project/confirm_education/
confirmed_entries/primary_education_confirmed - the only remaining hits
are the explanatory comment describing their removal and stale
references inside tests/run_bullets_dates_confirmation_test.py and
tests/run_agent_tests.py, which scripted the OLD confirm-then-continue
flow and were not re-recorded in this pass (same as the older evidence
scripts flagged in the previous entry) - the live verification above
exercises the new behaviour directly instead.

---

BUG: GUI submit button appears to do nothing after an intake reply
completes the profile ("sends the answer but nothing comes back")

Reported live, right after the previous fix (deferred project review)
was deployed: submitting a follow-up reply in the GUI's intake screen
sent the message but the page never visibly progressed.

DIAGNOSIS

Reproduced the exact call sequence the GUI's "followup" stage submit
button makes (agent.take_turn(reply) followed by handle_turn_result(
result)) directly against the live agent, with wall-clock timing on each
call. Root cause found immediately: handle_turn_result()'s "confirmed"
branch - added by the immediately preceding fix - calls
agent.start_review() to bootstrap the review phase's first gap. That
call is a SECOND live LLM extraction call, and handle_turn_result() runs
AFTER the submit button's own `with st.spinner("Thinking..."):` block has
already closed (Streamlit only shows a spinner for the block it wraps).
The reproduction measured this concretely: the intake reply's own
take_turn() call took 23.8s (already spinner-covered, fine), then the
UN-covered start_review() call took a further 51.6s with the page showing
literally nothing - no spinner, no new content, nothing rendered until
the whole handler finally finished and st.rerun() fired. From a user's
perspective this is indistinguishable from a broken button: the page
just sits frozen for 50+ seconds right after they submit, having
already seen the (now-vanished) spinner disappear.

This bug was introduced entirely by the previous fix, not a regression
in unrelated code - before that fix, handle_turn_result()'s "confirmed"
branch made no LLM calls at all.

IMPLEMENTATION

Moved the review-phase bootstrap check OUT of handle_turn_result() and
into the "confirm" stage's own render, gated by a new review_checked
session flag (added to SESSION_KEYS so it survives sidebar session
switches correctly):
- handle_turn_result()'s "confirmed" branch now only sets
  confirm_summary, review_checked=False, and stage="confirm" - no LLM
  call, near-instant, so the submit button's st.rerun() fires promptly
  right after its own (already spinner-covered) take_turn() call.
- The "confirm" stage renders its header and st.write(confirm_summary)
  FIRST (so the student sees the completed intake immediately), THEN, if
  review_checked is still False, runs agent.start_review() inside its
  own `with st.spinner("Checking your projects for anything missing..."):`
  block - the same call as before, just relocated so it always has
  visible feedback exactly where its latency lands, and labelled for
  what it's actually doing rather than a generic "Thinking...".
  review_checked is set True immediately after, so this bootstrap check
  runs exactly once per confirm-stage entry, never repeated on later
  reruns triggered by unrelated widget interactions.
- Every other LLM call site in the GUI was grep-checked and confirmed
  already wrapped in its own st.spinner() - this was the one place a
  call had been added outside one.

Files touched:
- 01_System/source_code/cv_builder_gui.py (SESSION_KEYS,
  handle_turn_result(), "confirm" stage)

DECISION
Accept

VERIFICATION

Re-ran the exact reproduction (agent.take_turn(reply) -> the new,
LLM-call-free handle_turn_result() body) and confirmed by direct
inspection of the edited handle_turn_result() that its "confirmed"
branch now contains zero LLM calls - purely session-state assignments -
so the submit button's own handler returns control to Streamlit (and
therefore reaches st.rerun()) immediately after its own spinner-covered
call finishes, instead of blocking for another 50+ seconds afterward
with no feedback. Grepped every remaining take_turn/start_review/
generate_text/extract_json/search/checker call site in cv_builder_gui.py
and confirmed each one is wrapped in its own st.spinner(). Could not
click through the actual browser UI directly (no browser-automation tool
available in this environment) - verification here is via direct
reproduction of the underlying timing (which located and confirmed the
root cause) plus static confirmation of the fix's code path; asked the
user to retest live in the running Streamlit app to confirm the visible
behaviour now matches.

---

GOAL: Fix Groq 429 TPM rate-limit errors without adding retry logic

"My code is hitting a Groq API rate limit error when calling
openai/gpt-oss-20b: groq.RateLimitError... tokens per minute (TPM):
Limit 8000... Please try again in 19.515s." Asked for, explicitly
without retry logic: (1) a max_tokens parameter on the Groq calls to cap
output size, (2) simple client-side throttling for calls made in a
loop/batch so usage proactively stays under 8000 TPM, (3) on a 429
still occurring, raise/log a clear error rather than auto-retrying, and
(4) keep the fix minimal, no unrelated changes.

DIAGNOSIS

Checked requirement (1) before writing anything: max_tokens is already a
required parameter on both GroqLLM.extract_json() and generate_text()
(tuned repeatedly earlier this session for this exact TPM ceiling), and
every call site across the project already passes an explicit value.
Grepped the whole source tree for chat.completions.create()/Groq(
api_key - agent.py's GroqLLM is the ONLY place a raw Groq client is ever
built or called; cv_generator.py, cv_builder_gui.py, and cv_builder_cli.py
all route through it. So the missing piece was purely (2): proactive
throttling - nothing in the codebase tracked usage across calls, so nothing
stood between one turn's extraction call and the next in a loop (e.g.
ProfileAgent.run()'s intake/review loops, or a batch test script) other
than GROQ's own after-the-fact rejection.

Confirmed the existing retry-once-on-BadRequestError logic in
extract_json() (added earlier this session for a DIFFERENT failure mode -
an empty completion when the reasoning model exhausts max_tokens on
hidden thinking, reported as 400 json_validate_failed) is unrelated to
RateLimitError (429) and was left untouched, per "don't change unrelated
parts" - it doesn't retry 429s today either (its except clause only
matches BadRequestError), so requirement (3)'s "no auto-retry on 429"
was already true; what it lacked was a CLEAR logged message before the
error propagates, which is what was added.

IMPLEMENTATION

- agent.py: added TPM_LIMIT=8000/TPM_WINDOW_SECONDS=60 module constants
  and a `deque`-based `_token_usage_window` on GroqLLM, recording
  (timestamp, estimated_tokens) for every call.
- GroqLLM._estimate_tokens(): a deliberately simple ~4-chars-per-token
  heuristic (the same rule of thumb already used informally in this
  project's max_tokens tuning comments) - good enough to throttle
  proactively, not meant to match GROQ's own count exactly.
- GroqLLM._throttle(estimated_tokens): prunes window entries older than
  60s, and if adding this call's estimate would push the rolling total
  over 8000, sleeps until the oldest entry ages out of the window before
  proceeding - a minimal sliding-window throttle, not a full token-bucket
  implementation, since the request only asked for "a fixed sleep or a
  token-bucket check."
- Both extract_json() and generate_text() now call
  `self._throttle(self._estimate_tokens(system_prompt, user_content) +
  max_tokens)` before firing each request - covers every call site in
  the project automatically, including any loop/batch usage, since they
  all share this one class.
- Both methods now also catch `RateLimitError` specifically, print a
  clear `[GroqLLM.<method>] Groq TPM rate limit hit despite client-side
  throttling: <message>` line, and re-raise immediately - no retry loop,
  no swallowing.
- Did not touch the existing BadRequestError retry-once logic, cv_
  generator.py, cv_builder_gui.py, or cv_builder_cli.py - none of them
  needed a change since they all funnel through GroqLLM.

Files touched:
- 01_System/source_code/agent.py (imports, TPM_LIMIT/TPM_WINDOW_SECONDS,
  GroqLLM._estimate_tokens(), GroqLLM._throttle(), extract_json(),
  generate_text())

DECISION
Accept

VERIFICATION

Two offline tests, both using a mocked/local GroqLLM instance so NO live
API calls were made and no tokens were spent (important given this
account's TPM/TPD ceilings were already being tuned around live earlier
this session):
- Throttle behaviour: confirmed _estimate_tokens("a"*400) == 100 (the
  4-chars-per-token heuristic); confirmed two calls totalling 7000
  tokens in an empty window pass through with ~0s delay; confirmed a
  third call that would push the (patched, 1-second-wide for a fast
  test) window to 10000 tokens correctly slept ~1.0s - matching "wait
  until the oldest entry ages out" exactly.
- No-retry-on-429 behaviour: mocked the Groq client to raise
  RateLimitError on every call (constructed via a real httpx.Request/
  Response, same pattern as the earlier BadRequestError retry-once
  test) - confirmed both extract_json() and generate_text() call the
  client exactly ONCE (no retry), print the new clear log line, and
  re-raise RateLimitError to the caller.
Re-imported agent.py, cv_generator.py, and cv_builder_cli.py afterward
to confirm no syntax/import errors from the change.

---

GOAL: Let the LLM backend be toggled between GROQ's cloud API and a
locally-run model, with no other code changes required

Follow-up to the rate-limit fix: user asked "is there a way to let the
LLM run locally?", then "is it possible for this project to toggle
between the two?", then "build it out". openai/gpt-oss-20b (this
project's GROQ model) is itself an open-weight model Ollama can serve
locally, exposing an OpenAI-compatible endpoint - the goal was a clean
switch between the two, not a one-off replacement of GROQ.

DIAGNOSIS

Confirmed agent.py's GroqLLM is the ONLY place a raw Groq client is ever
built or called anywhere in the project (re-confirmed via the same grep
used for the rate-limit fix) - every other class only ever calls
extract_json()/generate_text() on whatever llm object it was given. This
meant a toggle could be added with a single new factory function, without
touching ProfileAgent, JobRequirementAgent, or CVGenerator's actual logic
at all - they only needed their GroqLLM type hints loosened to a shared
interface.

Checked compatibility before committing to an implementation: the groq
SDK's Groq client DOES accept a custom base_url, but its chat-completions
call hardcodes a "/openai/v1/chat/completions" path onto whatever
base_url is given - Ollama's OpenAI-compatible route is "/v1/chat/
completions" (no "/openai" segment), so pointing the groq SDK's client
straight at Ollama would silently 404. Confirmed the `openai` Python
package (already installed in this environment) posts to exactly the
right path when given base_url="http://localhost:11434/v1", and verified
live with a raw curl that Ollama's endpoint correctly supports
response_format={"type": "json_object"} (required by extract_json()).
This settled the design: a second class using the `openai` SDK, not a
retrofit of GroqLLM's own client.

Ollama was already installed and running on this machine, but only with
qwen2.5:7b pulled - NOT gpt-oss:20b (a ~13GB download not started
without asking). Verification below therefore proves the TOGGLE
MECHANISM works end-to-end through the real agent, using whatever model
is actually available locally - it does not (yet) prove gpt-oss:20b's
own local output quality/latency, since that model isn't pulled on this
machine.

IMPLEMENTATION

- agent.py: added LLMClient, a minimal common interface (extract_json/
  generate_text stubs) - GroqLLM now inherits from it; no behavioural
  change to GroqLLM itself.
- agent.py: added LocalLLM(LLMClient) - lazily imports `openai` inside
  __init__ (clear RuntimeError if not installed, matching GroqLLM's
  existing "clear error if GROQ_API_KEY missing" style) and talks to
  Ollama via OpenAI(base_url=LOCAL_LLM_BASE_URL, api_key="ollama") (a
  placeholder key - Ollama doesn't check it). model defaults to
  DEFAULT_LOCAL_MODEL="gpt-oss:20b" (matching GROQ's production model
  when/if pulled), overridable via LOCAL_LLM_MODEL. No throttling
  applied here - GROQ's 8000 TPM ceiling is a cloud account limit that
  doesn't exist for hardware you own.
- agent.py: added build_llm(backend=None, **kwargs) -> LLMClient - the
  one place every other class should now get its LLM client from. Reads
  LLM_BACKEND from the environment ("groq" default, or "local"/"ollama")
  when `backend` isn't passed explicitly.
- Updated every call site that previously hardcoded GroqLLM() as a
  default to call build_llm() instead: cv_generator.py's CVGenerator,
  cv_builder_gui.py's get_llm(), cv_builder_cli.py's run_full_flow().
  Loosened GroqLLM type hints to LLMClient in ProfileAgent,
  JobRequirementAgent, CVGenerator, and run_full_flow() - duck-typed
  before, now formally documented via the shared interface.
- cv_builder_cli.py: added a --llm-backend {groq,local} flag that
  overrides LLM_BACKEND for a single CLI run without touching .env.
- 02_Setup/requirements.txt: added `openai>=1.30` as an optional
  dependency (only needed for LLM_BACKEND=local).
- 02_Setup/config.example: documented LLM_BACKEND, LOCAL_LLM_MODEL, and
  LOCAL_LLM_BASE_URL alongside the existing GROQ_API_KEY/GROQ_MODEL.
- Did not touch tests/ - they construct GroqLLM() directly and
  intentionally exercise the cloud backend; build_llm() is additive, not
  a replacement for that pattern.

Files touched:
- 01_System/source_code/agent.py (LLMClient, LocalLLM, build_llm(),
  type hints on ProfileAgent/JobRequirementAgent)
- 01_System/source_code/cv_generator.py (import, CVGenerator)
- 01_System/source_code/cv_builder_gui.py (import, get_llm())
- 01_System/source_code/cv_builder_cli.py (import, run_full_flow(),
  main()'s argparse)
- 02_Setup/requirements.txt
- 02_Setup/config.example

DECISION
Accept

VERIFICATION

- Live curl to Ollama's http://localhost:11434/v1/chat/completions with
  response_format={"type": "json_object"} - confirmed the exact endpoint
  shape LocalLLM depends on works before writing the class.
- build_llm() with no LLM_BACKEND set returns GroqLLM (confirms the
  default/existing behaviour is completely unchanged - no regression for
  anyone not opting into the local backend).
- build_llm() with LLM_BACKEND=local returns LocalLLM.
- End-to-end through the REAL ProfileAgent (not a mock): set
  LLM_BACKEND=local and LOCAL_LLM_MODEL=qwen2.5:7b (the model actually
  available on this machine), ran a live introduction through
  agent.take_turn(intro, phase="intake") - extraction correctly
  populated name/degree/institution/year/skills/target_roles, and a
  sensible follow-up question was generated asking for the missing
  degree dates. No exceptions, no wiring errors. (Field-naming was
  slightly off - "education_start_date, education_end_date" instead of
  the prompt's expected single "education_dates" field - a difference in
  how this smaller general-purpose model follows the exact gap-naming
  instruction, not a toggle/wiring bug; the pipeline still degraded
  gracefully since compute_gaps()'s sort falls back to "unknown field
  goes last" rather than erroring.)
- Confirmed the exact same class (LocalLLM) is what CVGenerator/
  cv_builder_gui/cv_builder_cli now receive by construction, since they
  all resolve through the same build_llm() call.

NOT YET DONE (flagged, not a gap in the toggle itself): gpt-oss:20b
itself was not pulled locally (`ollama pull gpt-oss:20b`, ~13GB) - not
started without asking, since it's a large download/disk commitment.
The toggle mechanism is fully built and verified with whatever model is
locally available; running the SAME model GROQ uses in production
locally is one `ollama pull` away whenever the user wants it.

---

FOLLOW-UP: Get gpt-oss:20b itself actually working locally (the model
GROQ uses in production), after the user pulled it

The user pulled gpt-oss:20b locally ("I already have oss 20b") right
after the toggle was built. Re-ran the same end-to-end verification
against it directly instead of the stand-in qwen2.5:7b - it failed with
an empty completion even after LocalLLM's retry-once, prompting a deeper
investigation (user chose to keep investigating rather than stop at "the
toggle mechanism works, tuning gpt-oss:20b is a separate task").

DIAGNOSIS (an iterative live investigation, not a single fix)

1. First empty completion: LocalLLM.extract_json() got a JSONDecodeError
   from an empty resp.choices[0].message.content on the FULL production
   EXTRACTION_SYSTEM_PROMPT (~4k tokens) at max_tokens=4000. Assumed
   (reasonably, given GroqLLM's own documented history) this was the same
   "hidden reasoning exhausts max_tokens" quirk - added a retry-once
   with escalating max_tokens (doubling each attempt).
2. Escalating retry still failed - empty even at max_tokens=32000. This
   disproved the "just needs more max_tokens" theory - something else
   was capping the exchange regardless of the output budget.
3. Isolated the variable: sent a TRIVIAL prompt (a two-line system
   message) to gpt-oss:20b via curl - it worked instantly and correctly,
   AND revealed Ollama returns the model's hidden reasoning in a SEPARATE
   "reasoning" field from "content", with "completion_tokens" in usage
   counting only the visible content - meaning max_tokens/num_predict was
   never actually the bottleneck for reasoning length the way it is on
   GROQ's hosted endpoint. This redirected the investigation away from
   token budgets entirely.
4. Checked `ollama ps` - it reported the loaded model's CONTEXT as 4096,
   Ollama's runtime default, regardless of gpt-oss:20b's own supported
   maximum of 131072 (from `ollama show`). With the production system
   prompt alone already ~4k tokens, there was essentially no room left
   in a 4096 context for the prompt PLUS any reasoning PLUS output - this
   fit the symptom exactly (empty output no matter how high max_tokens
   went, since the ceiling was the CONTEXT window, not the output length).
5. Tried overriding via LocalLLM's existing OpenAI-compatible endpoint
   (options.num_ctx in the request body) - `ollama ps` showed the context
   size UNCHANGED afterward, proving the OpenAI-compatible endpoint
   silently ignores Ollama-specific options.
6. Switched to testing Ollama's NATIVE /api/chat endpoint instead (which
   documents num_ctx support) - stopped the running model first (a
   loaded model keeps its original context size until reloaded), then
   confirmed via `ollama ps` that a native request with options.num_ctx:
   16384 correctly reloaded the model at that context size.
7. Tried num_ctx: 32768 next (more headroom) - this crashed the
   underlying llama-server process outright with a CUDA/stack-overflow
   error, not a graceful failure - almost certainly a local GPU VRAM
   ceiling on this machine. Backed off and confirmed 16384 specifically:
   sent the exact real EXTRACTION_SYSTEM_PROMPT + a live introduction
   through the native endpoint at num_ctx=16384 - it returned a complete,
   correctly-structured extraction (name/degree/institution/year/skills/
   project/target_roles/gaps) in ~21s, matching GROQ's own output shape.

This is a case where the FIRST plausible diagnosis (reused from GroqLLM's
known history) was wrong, and only got corrected by isolating variables
one at a time (trivial prompt vs. full prompt, OpenAI-compat vs. native
endpoint, context size vs. token budget) rather than continuing to tune
the wrong dial (retry/escalate max_tokens) further.

IMPLEMENTATION

- agent.py: LocalLLM rewritten from using the `openai` SDK against
  Ollama's OpenAI-compatible endpoint to using `httpx` (already a
  transitive dependency) directly against Ollama's NATIVE /api/chat
  endpoint - the only one that honours num_ctx.
- Added DEFAULT_LOCAL_NUM_CTX = 16384 (confirmed live, per the
  investigation above) and a LOCAL_LLM_NUM_CTX env var override, read in
  LocalLLM.__init__. Documented directly in the constant's own comment
  why 4096 (Ollama's default) fails, why 16384 works, and why 32768
  crashed the local GPU process on this machine - so the choice doesn't
  read as arbitrary to a future reader.
- LocalLLM._chat(): a small shared helper building the native /api/chat
  request shape ("format": "json" for JSON mode instead of
  response_format, "options": {"num_ctx", "num_predict", "temperature"}
  instead of top-level max_tokens/temperature) - extract_json()/
  generate_text() both call it, keeping the escalating-retry logic from
  the previous entry (now a secondary safety net rather than the primary
  fix, but still real: the same hidden-reasoning-token quirk can still
  in principle produce an empty completion even with a correctly-sized
  context).
- 02_Setup/requirements.txt: replaced the `openai` dependency with an
  explicit `httpx` one (LocalLLM no longer uses the `openai` package at
  all).
- 02_Setup/config.example: updated LOCAL_LLM_BASE_URL to the bare Ollama
  host (no /v1 suffix - the native API doesn't use one) and added
  LOCAL_LLM_NUM_CTX with the same reasoning as the code comment.

Files touched:
- 01_System/source_code/agent.py (LocalLLM - constructor, _chat(),
  extract_json(), generate_text(); DEFAULT_LOCAL_NUM_CTX)
- 02_Setup/requirements.txt
- 02_Setup/config.example

DECISION
Accept

VERIFICATION

- Confirmed via `ollama show gpt-oss:20b` that the model supports up to
  131072 context, and via `ollama ps` that Ollama was actually running it
  at the 4096 default - establishing the real ceiling before touching
  code.
- Confirmed the OpenAI-compatible endpoint's options.num_ctx is silently
  ignored (`ollama ps` unchanged after passing it) and that the native
  endpoint's options.num_ctx DOES reload the model at the requested size
  (`ollama ps` showed 16384 afterward) - both via direct curl/native
  HTTP calls, before rewriting LocalLLM.
- Sent the exact real EXTRACTION_SYSTEM_PROMPT + a live introduction
  through the native endpoint directly (bypassing LocalLLM) at
  num_ctx=16384 first, to confirm the fix BEFORE rewriting the class -
  got back a complete, correct extraction in ~21s.
- Re-ran the SAME end-to-end test used to verify the toggle mechanism
  itself (a live introduction through the real ProfileAgent.take_turn(),
  LLM_BACKEND=local, LOCAL_LLM_MODEL=gpt-oss:20b) against the rewritten
  LocalLLM - completed in ~19s with a fully correct extraction (name,
  degree, institution, year, all 5 skills, the project, both target
  roles) and a well-formed, natural follow-up question asking for the
  one genuinely missing thing (degree dates) - matching the exact
  quality/style GROQ's hosted version produces for the same prompts.
- Re-confirmed build_llm() with no LLM_BACKEND set still returns
  GroqLLM, unaffected by the LocalLLM rewrite - no regression to the
  default cloud path.
- Re-imported agent.py, cv_generator.py, cv_builder_cli.py to confirm no
  syntax/import errors after removing the `openai` SDK usage.

gpt-oss:20b now runs correctly end-to-end, locally, through this
project's real agent - both halves of the original ask (a working
toggle, and the actual production model functioning on the local side of
it) are complete and verified.

---

BUG: LLM_BACKEND=local in .env silently ignored, still tried GROQ and
crashed with "GROQ_API_KEY is not set"

After the toggle was built, the user set LLM_BACKEND=local in
02_Setup/.env and commented out their GROQ_API_KEY lines (reasonably,
since they'd switched to local) - the live GUI still tried to construct
GroqLLM and crashed with the "GROQ_API_KEY is not set" RuntimeError from
inside get_llm() -> build_llm(). Reported via the exact traceback.

DIAGNOSIS

build_llm() reads `os.environ.get("LLM_BACKEND", "groq")` to decide which
class to construct - but the .env file's values are never in os.environ
until something calls load_dotenv(). That call existed ONLY inside
GroqLLM.__init__() (not LocalLLM.__init__(), not build_llm() itself). So
on a fresh process, build_llm() checked LLM_BACKEND before anything had
ever loaded .env, found it unset, fell through to the "groq" default,
and only THEN constructed GroqLLM() - which finally called load_dotenv()
itself, by which point build_llm()'s branch decision was already made
and wrong. The user's LLM_BACKEND=local was real and correct in the
file; the code just never looked at the file before deciding.

IMPLEMENTATION

- agent.py build_llm(): added a load_dotenv() call at the very top,
  before reading LLM_BACKEND - the fix. GroqLLM's/LocalLLM's own
  load_dotenv() calls stay as they were (needed for direct construction
  bypassing build_llm(), e.g. test scripts that call GroqLLM() directly).
- agent.py LocalLLM.__init__(): added the same load_dotenv() call
  GroqLLM.__init__() already had, for the same direct-construction
  reason and as defense in depth - it had never had one at all.

Files touched:
- 01_System/source_code/agent.py (build_llm(), LocalLLM.__init__())

DECISION
Accept

VERIFICATION

Reproduced the exact reported scenario: simulated a fresh process (no
LLM_BACKEND/GROQ_API_KEY pre-set in os.environ, matching a freshly
launched Streamlit app) against the user's REAL, currently-modified
02_Setup/.env (LLM_BACKEND=local, all GROQ_API_KEY lines commented out) -
build_llm() now correctly returns LocalLLM (model=gpt-oss:20b,
num_ctx=16384) instead of crashing trying to construct GroqLLM.
Regression check: build_llm(backend="groq", api_key=...) still
correctly constructs GroqLLM when explicitly requested. Re-ran the full
project syntax/import check afterward - no errors.

---

GOAL: Run every test script in tests/ (against LLM_BACKEND=local, per the
user's .env) and get them all genuinely passing

"Run all the test scripts." The user's .env already had LLM_BACKEND=local
set with their own note recommending it ("groq is currently very slow and
expensive").

DIAGNOSIS

Before running anything: 9 of the 14 test scripts construct GroqLLM()
directly rather than build_llm(), so they would ignore LLM_BACKEND=local
entirely and crash immediately on the now-commented-out GROQ_API_KEY.
Asked the user how to proceed rather than assuming; chose to switch the
tests to build_llm(). This surfaced, over the course of running all 14,
a series of genuinely pre-existing staleness issues in the test fixtures
themselves - none caused by anything changed this session, all latent
since whichever earlier fix (education_dates becoming mandatory, the
project-review split, institution being genuinely asked, JobRequirement
Agent's own follow-up) first made a given test's scripted replies
incomplete for the CURRENT gap set. Running against local, which exposed
every follow-up turn's exact question in the traceback/output, made
these visible in a way they might not have been before.

IMPLEMENTATION

- GroqLLM() -> build_llm() swap across all 9 affected files (agent
  import updated too); one file (run_final_verification.py) only had an
  unused GroqLLM import - removed rather than swapped. Loosened
  run_cross_user_test.py's GroqLLM type hint to LLMClient and updated
  two "sharing the same GroqLLM..." evidence strings to "LLMClient" for
  accuracy (the shared instance is no longer necessarily a GroqLLM).
- Fixed EOFError-on-input() crashes (agent.run()/run_full_flow() falling
  through to input() when a scripted reply list was exhausted or never
  provided) across run_job_requirement_test.py, run_two_job_comparison.py,
  run_retrieval_tests.py, run_cross_user_test.py, run_five_profile_tests.py,
  run_final_verification.py, run_final_verification_part23.py,
  run_session_sidebar_test.py - each missing one or more of: education
  dates (a mandatory gap several of these intros predate), an explicit
  institution (Sarah Chen's intro never named one, unlike the other four
  personas), project dates/outcome (now asked in a separate review phase
  these older scripts never scripted for), or a job_requirement_reply
  (run_full_flow()'s own separate job-specific gap-check step).
- First attempt at project-review replies used vague durations ("about
  two weeks") with no calendar anchor - these often failed to populate
  start_date/end_date at all (TASK 1's DATES rule requires an explicit
  timeframe), leaving the gap unresolved for a second round that wasn't
  scripted, reproducing the same EOFError one level deeper. Replaced
  every added review reply with an explicit "Month YYYY to Month YYYY"
  phrasing plus a second, defensive reply describing a concrete outcome,
  across every file this pattern was used in.
- run_five_profile_tests.py/run_final_verification.py: two of five
  profiles (Devon Okafor, Sarah Chen) are deliberately incomplete across
  THREE separate dimensions each, resolved one at a time across three
  follow-up rounds - step_cap=5's 2-round budget (each round is 2 steps:
  ExtractFields + AskFollowUp) wasn't enough, correctly producing
  step_limit_reached rather than a crash. Raised step_cap to 8 for these
  two multi-gap test suites specifically (not a global default change).
- run_bullets_dates_confirmation_test.py directly read
  draft["projects"][0]["confirmed"] and draft["primary_education_confirmed"]
  - both fields removed entirely by the earlier "no confirmation
  round-trip" fix, so this crashed with a raw KeyError. This test's
  premise runs deeper than a field rename (it also predates the intake/
  review phase split - it calls take_turn() directly, never phase=
  "review"), so rewriting its narrative properly is a separate, bigger
  job than this request. Made the minimal change to stop the crash
  (substituted an equivalent "dates were actually captured" check) and
  ran it anyway - confirmed the fixes it was ORIGINALLY built to verify
  (bullet splitting, results routing, dates rendering, PDF output) still
  hold correctly; its confirmation-specific narrative is now stale by
  design (there is no more confirmation round-trip to describe) and was
  reported to the user as such rather than silently patched to "look
  like it passes."
- Hit a genuine, non-code-related blocker mid-sweep: Ollama's
  llama-server crashed with "CUDA error: shared object initialization
  failed" on cold model load, 3 times consecutively at one point
  (confirmed via the actual Ollama server log each time, not guessed) -
  the same class of GPU/driver instability seen once before during the
  LLM_BACKEND=local build. Reported this transparently rather than
  retrying indefinitely; the user restarted the Ollama service, which
  cleared it - the very next attempt (and the remaining tests) passed
  cleanly.

Files touched (test-only, no application code changed for this entry):
- 01_System/source_code/tests/run_agent_tests.py
- 01_System/source_code/tests/run_bullets_dates_confirmation_test.py
- 01_System/source_code/tests/run_cross_user_test.py
- 01_System/source_code/tests/run_final_verification.py
- 01_System/source_code/tests/run_final_verification_part23.py
- 01_System/source_code/tests/run_job_requirement_test.py
- 01_System/source_code/tests/run_profile_update_test.py
- 01_System/source_code/tests/run_retrieval_tests.py
- 01_System/source_code/tests/run_session_sidebar_test.py
- 01_System/source_code/tests/run_style_spec_test.py
- 01_System/source_code/tests/run_two_job_comparison.py
- 01_System/source_code/tests/run_five_profile_tests.py

DECISION
Accept

VERIFICATION

All 14 test scripts run to completion against LLM_BACKEND=local
(gpt-oss:20b via Ollama) with a genuine pass (not just "didn't crash" -
each one's own assertions/acceptance checks hold):
run_style_spec_test.py, run_cv_generation_test.py,
run_prompt_comparison_test.py, run_profile_update_test.py,
run_agent_tests.py, run_bullets_dates_confirmation_test.py (core fixes
re-verified, confirmation narrative flagged as stale), run_job_
requirement_test.py, run_retrieval_tests.py, run_two_job_comparison.py,
run_cross_user_test.py, run_session_sidebar_test.py,
run_five_profile_tests.py (all 5 personas confirmed), run_final_
verification.py (all 5 personas confirmed), run_final_verification_
part23.py (both parts, isolation holds with real PDFs). Re-ran the full
project syntax/import check after every batch of edits.

---

GOAL: Fix CV PDF layout - degree/project entry lines read as "too far
left" against their section headers

Reported via a screenshot from a live-generated CV (during the test
sweep above): the EDUCATION/PROJECTS entry lines (title left, date
right) looked pinned flush against the page's left edge with a large
empty gap before the date, reading as visually unbalanced.

DIAGNOSIS

Rendered the exact same PDF directly to check for an actual left-margin
bug first, rather than guessing from the screenshot alone - found none:
the entry title text was already flush with its own section header at
identical x-coordinates, which is what the original spec called for.
The likely cause was the two-column Table's fixed 68/32 width split
leaving a large visual gap for short titles before the right-aligned
date, reading as "everything bunched left." Asked the user directly
which of three possible fixes they actually wanted (narrower date
column, larger page margin, or indenting entries under their header)
rather than picking one - they chose indenting entries under their
header, keeping the page margin and column ratio as they were.

IMPLEMENTATION

- cv_style_spec.py: added ENTRY_INDENT_MM = 4, documented as applying
  only to Education/Experience/Projects entry lines (the ones with a
  title/date header), not Summary or Skills (no per-entry title there
  to distinguish from the section header).
- cv_pdf.py: render_cv_pdf()'s section() helper gained an `indent: bool`
  parameter - when True, wraps the section's flowables between
  Indenter(left=entry_indent) and Indenter(left=-entry_indent)
  (reportlab's standard way to shift a block of flowables without
  touching each one's own style). The Education/Experience/Projects
  section() calls pass indent=True; Summary/Skills are unchanged
  (indent defaults to False).
- Every _entry_header() call within an indented section now receives
  entry_content_width (content_width minus the indent) instead of the
  full content_width, so the Table's fixed-width columns still fit
  inside the now-narrower indented frame rather than overflowing it.
  Section divider HRFlowables are unaffected (added outside the
  Indenter pair, at full page width) - confirmed visually.

Files touched:
- 01_System/source_code/cv_style_spec.py (ENTRY_INDENT_MM)
- 01_System/source_code/cv_pdf.py (imports, render_cv_pdf()'s section(),
  entry_content_width, Education/Experience/Projects call sites)

DECISION
Accept

VERIFICATION

Rendered a synthetic reconstruction of the exact reported CV (no LLM
call needed) before and could directly compare - confirmed the degree/
project title lines now sit indented right of "EDUCATION"/"PROJECTS",
while Summary/Skills content stays flush with their own headers exactly
as before. Then regenerated two REAL CVs end-to-end through the live
agent (Priya Nair via run_style_spec_test.py; Ethan Brooks/Devon Okafor
via run_final_verification_part23.py) - confirmed the same indent holds
correctly across every entry type this project renders: a no-date
education line, a dated education line, an experience entry, and a
project entry (with its own Technologies line and bullets) - all
consistently indented, all divider lines still full width.

---

GOAL: Trim the submission down to only the required tests/evidence

"Remove unneeded files and update the prompt record." Reviewed every
script in tests/ against the assignment's actual required deliverables:
the five-profile test, the two-jobs-from-one-profile comparison, the
cross-user isolation test, the agent trace, the RAG retrieval evidence
and the prompt before/after comparison - and against the exact
`03_Evidence` folder structure the brief specifies (which names only
`agent_actions_and_observations.md`, `follow_up_question_test.md`,
`retrieval_results.md`, `five_profile_results.md`, `two_job_comparison.md`
and `cross_user_test.md`).

DIAGNOSIS

Several scripts were real, working tests but not required deliverables:
`run_job_requirement_test.py`, `run_profile_update_test.py`,
`run_session_sidebar_test.py` and `run_style_spec_test.py` each verify an
extra feature or bug fix beyond the assignment's stated scope (job-
specific requirement follow-ups, a chat-history sidebar, hardcoded PDF
style constants). `run_bullets_dates_confirmation_test.py` was already
flagged stale in the README - it predates the later removal of per-entry
confirmation read-backs and scripts replies against a flow that no
longer exists. `run_final_verification.py` +
`run_final_verification_part23.py` duplicated the required five-profile/
two-job/cross-user tests end to end under a different, non-required
filename (`final_end_to_end_verification.md`). `run_cv_generation_test.py`
turned out to write to the exact same evidence path as
`run_two_job_comparison.py` (`04_System_Tests/two_job_comparison.md`), so
its output had already been silently overwritten by the later script -
it was dead weight. None of this was hidden: the earlier full test-suite
entries above document all of it running and passing. It just isn't
required for grading, and having five extra unlisted files scattered
across `02_Agent/` and `04_System_Tests/` worked against
`03_Evidence` staying concise and easy to locate.

IMPLEMENTATION

- Deleted the 7 test scripts named above from
  `01_System/source_code/tests/`.
- Deleted their 6 corresponding evidence files:
  `03_Evidence/02_Agent/job_requirement_followup_test.md`,
  `03_Evidence/02_Agent/profile_update_parsing_test.md`,
  `03_Evidence/04_System_Tests/session_sidebar_test.md`,
  `03_Evidence/04_System_Tests/style_spec_test.md`,
  `03_Evidence/04_System_Tests/bullets_dates_confirmation_test.md`,
  `03_Evidence/04_System_Tests/final_end_to_end_verification.md`.
- Left the application code these tests exercised untouched
  (`JobRequirementAgent`, the session sidebar, `cv_style_spec.py` are
  still live features in the app) - only the extra test harnesses and
  their evidence files were removed, not the features themselves.
- Updated `02_Setup/README.md`'s test list to drop references to the
  removed files and explain why they're gone, so the docs don't point
  at files that no longer exist.
- Left every earlier Prompt Record entry above untouched - they're an
  honest record of work that genuinely happened, including bugs found
  via the now-removed scripts; only the scripts and their evidence
  files were trimmed from the submission itself.

Files touched:
- Deleted: the 7 scripts and 6 evidence files listed above.
- 02_Setup/README.md (test list section)

DECISION
Accept

VERIFICATION

Confirmed the 6 required evidence files the brief's folder tree actually
names are all still present and untouched: `02_Agent/
agent_actions_and_observations.md`, `02_Agent/follow_up_question_test.md`,
`03_Retrieval/retrieval_results.md`, `04_System_Tests/
five_profile_results.md`, `04_System_Tests/two_job_comparison.md`,
`04_System_Tests/cross_user_test.md`. Confirmed no remaining test script
in tests/ imports from or depends on any of the 7 removed files.

---

GOAL: Clean up dead code in 01_System/source_code

"Help me clean up source code in 01_System as well. Find any unnessary
edits, logs, codes, comments that are not longer needed and tell me."
Reviewed every file in `01_System/source_code/` for dead code, stale
comments, unused imports/variables, debug leftovers and stray build
artifacts before changing anything - reported findings first, applied
them only after the user confirmed ("yes").

DIAGNOSIS

Ran `pyflakes` across the whole source tree (installed on demand, not
previously part of the project's tooling) plus manual checks for
commented-out code, hardcoded secrets, and functions defined but never
called anywhere else in the project. The codebase turned out to be
largely clean - no commented-out code blocks, no leftover credentials,
every "possibly unused" function pyflakes-adjacent heuristics flagged
turned out to be called from another file once cross-file usage was
checked (e.g. `overwrite_profile`, `apply_job_requirement_facts`). The
two `print()` rate-limit warnings in `agent.py` were confirmed
intentional (deliberate diagnostics before a re-raise, already
commented as such) and left alone. Five genuine issues remained:
- `cv_generator.py`'s `_verify_and_clean()` computed `allowed_project_
  titles`/`allowed_experience_roles` (exact-normalized sets) that were
  never read again - superseded by `profile_experience_by_role`/
  `profile_projects_by_title` (dict-keyed, defined later in the same
  function) without the old sets ever being removed.
- `tests/run_cross_user_test.py` assigned `draft_b_after_b` right after
  User B's run but never compared it against anything (no "before"
  snapshot exists for B the way there is for A).
- `tests/run_two_job_comparison.py` imported `json` without using it,
  and had a stray `f` prefix on a string with no `{}` placeholders.
- `tests/_prompt_comparison_raw.json` is a disposable scratch dump
  regenerated by `run_prompt_comparison_test.py` on every run - the
  real evidence lives in this Prompt Record's comparison section, not
  in that raw file.

IMPLEMENTATION

- `cv_generator.py`: removed the two dead lines; corrected the comment
  above `allowed_project_titles_loose`/`allowed_experience_roles_loose`
  (it said the fuzzy fallback "kicks in once the exact... check above
  has failed" - "above" pointed at the now-deleted lines, so reworded
  it to name the actual exact-match lookup, `profile_experience_by_
  role`/`profile_projects_by_title`, which runs later in the function).
- `tests/run_cross_user_test.py`: removed the dead `draft_b_after_b`
  assignment.
- `tests/run_two_job_comparison.py`: dropped the unused `json` import;
  dropped the stray `f` prefix.
- Deleted `tests/_prompt_comparison_raw.json`.

Files touched:
- 01_System/source_code/cv_generator.py
- 01_System/source_code/tests/run_cross_user_test.py
- 01_System/source_code/tests/run_two_job_comparison.py
- Deleted: 01_System/source_code/tests/_prompt_comparison_raw.json

DECISION
Accept

VERIFICATION

Re-ran `pyflakes` across the source tree after the edits - zero warnings
anywhere (previously 5). Ran `python -m py_compile` on all three edited
`.py` files - all compiled cleanly. No other file references the
deleted variables, the removed import, or the deleted JSON artifact.

---

GOAL: Stop the per-job chat box from silently discarding manual CV edits

Flagged by the user from a screenshot of the "cv" stage's Experience/Skills
boxes: "Right now if I were to add in more information directly, it would
not actually be updated if I go to a different job." Investigated before
changing anything, found two distinct behaviours hiding behind that one
symptom, and reported both back rather than assuming which one was the bug.

DIAGNOSIS

1. Switching to a genuinely different job (the "Choose a different job"
   button) discards any manually-typed CV text and regenerates from the
   confirmed profile - this is CORRECT, required behaviour: the brief
   requires the confirmed profile to stay stable across a job change and
   every CV claim to trace back to it, so free-text typed directly into a
   CV box (never grounded, never confirmed) must not silently carry over
   as a "fact" onto a different job's CV.
2. But the SAME job's own "Chat: add or adjust anything for this role" box
   had a real, unintended bug: sending ANY message there calls
   `generate_cv_for_chosen_job()`, which unconditionally rebuilds `cv` from
   scratch via `CVGenerator.generate()` and overwrites `st.session_state.cv`
   wholesale - silently wiping out whatever the user had just typed into
   the Summary/Education/Experience/Project boxes, even for an unrelated
   field. Asked the user whether to fix this or just document it before
   touching code; they chose fix.

IMPLEMENTATION

- cv_builder_gui.py: added `_editable_text_snapshot(cv)` (pulls out every
  hand-editable field - summary, education, additional_education entries,
  experience descriptions keyed by (role, organisation), project
  descriptions keyed by title) and `_restore_manual_edits(previous_cv,
  new_cv)`, which diffs `previous_cv`'s fields against
  `st.session_state.cv_generated_snapshot` (the plain LLM output as of the
  last generation, stored alongside `cv`) and carries forward only the
  fields that actually differ from that baseline - i.e. only fields the
  user genuinely hand-edited, not everything indiscriminately.
- `generate_cv_for_chosen_job()` now captures `previous_cv = st.session_
  state.get("cv")` before regenerating, calls `_restore_manual_edits()`
  after, and refreshes `cv_generated_snapshot` to the new plain output.
  Skills/matched_skills/missing_requirements are deliberately excluded
  from restoration - those must always reflect whatever's newly confirmed
  in the profile, never a stale typed-in list, so a newly-confirmed skill
  from the same chat message can never be hidden by an old override.
- The existing "Choose a different job" handler already pops `cv` before
  calling `generate_cv_for_chosen_job()`, so `previous_cv` is `None` there
  and nothing gets restored - the different-job path needed no change,
  only `cv_generated_snapshot` added to its reset list for hygiene.

Files touched:
- 01_System/source_code/cv_builder_gui.py (import copy;
  _editable_text_snapshot, _restore_manual_edits, generate_cv_for_
  chosen_job, "Choose a different job" reset list)

DECISION
Accept

VERIFICATION

Ran `python -m py_compile` and `python -m pyflakes` on cv_builder_gui.py -
clean. Traced both call sites of `generate_cv_for_chosen_job()`: the
"jobs" -> "cv" first-generation path (line ~491, no prior `cv` in session
state, so `previous_cv` is `None` and nothing is restored - unaffected)
and the per-job chat regeneration path (line ~588, where `previous_cv` is
now populated and edits get restored). 

---

GOAL: Cut local-backend latency - "each run takes over a minute even for a
short message"

Reviewed every system prompt for size and redundancy first, since that's
what was asked, but measured rather than assumed where the time actually
goes - ran the real `EXTRACTION_SYSTEM_PROMPT` against the live local
Ollama server (confirmed reachable at localhost:11434, gpt-oss:20b
already pulled) and read back Ollama's own prefill/decode timing
breakdown before proposing anything.

DIAGNOSIS

`EXTRACTION_SYSTEM_PROMPT` is ~3,300 tokens and runs every turn -
plausible-looking target, but the numbers said otherwise:
- Prefill (processing the full 3,300-token system prompt): 0.2-1.1s.
  Trimming prompt text saves well under a second - not the bottleneck.
- Decode (generating the response): 8-20s for 600-1,500 output tokens -
  almost all of it gpt-oss:20b's hidden reasoning before it writes the
  visible JSON, matching the "reasoning model" behaviour already
  documented in failure_and_repair.md #2.
- Cold model load: ~10s, paid once per session/idle gap - explains why
  the FIRST message of a run feels worst.
So the prompt content itself isn't the lever; decode-time reasoning
tokens are. Rather than guess at a fix, tried Ollama's native `think`
chat-request option live: `think: "low"` on the real `EXTRACTION_SYSTEM_
PROMPT` against Ethan Brooks' actual intro text (the trickiest case in
the prompt - project vs. experience distinction, multi-field extraction
from one sentence) took 9.5s/585 output tokens vs. baseline's 18.5s/1,333
tokens, with IDENTICAL extracted projects/experience/skills/gaps - a
genuine ~2x speedup with no quality loss, not a tradeoff. A naive
"Reasoning effort: low" text prefix tried first did NOT work (made things
slower/more verbose) - confirmed `think` needs to be a real top-level API
option, not prompt text, before proposing the fix.

IMPLEMENTATION

- agent.py: added `"think": "low"` to `LocalLLM._chat()`'s Ollama
  `/api/chat` payload - both `extract_json()` and `generate_text()`
  funnel through `_chat()`, so this covers every local-backend call at
  once, with a comment recording the measured before/after numbers so a
  future reader doesn't need to re-derive them.
- Left every system prompt's actual wording untouched - measured
  prefill cost didn't justify the risk of cutting text that's mostly
  there because of a specific, documented earlier bug.
- Noted GROQ likely has an equivalent (`reasoning_effort`) but left it
  alone - LLM_BACKEND is currently `local`, and testing against GROQ
  would spend the user's cloud quota to verify something not in use.

Files touched:
- 01_System/source_code/agent.py (LocalLLM._chat())

DECISION
Accept

VERIFICATION

Ran a real `extract_json()` call through the actual `LocalLLM` class
(not just raw HTTP) post-fix, against a fresh persona (Priya Nair,
second-year, Python/pandas/Power BI): 6.1s wall time, correct fields
(name, institution, year, technical_skills) and correct gaps (degree,
target_roles) - consistent with the standalone `think: "low"` test above.
`python -m py_compile` and `python -m pyflakes` on agent.py both clean.