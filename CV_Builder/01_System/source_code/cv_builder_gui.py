import copy
import json
import tempfile
import uuid
from pathlib import Path

import streamlit as st

from agent import EXTRACTION_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT, LLMClient, JobRequirementAgent, ProfileAgent, build_llm
from cv_generator import CVGenerator
from cv_pdf import render_cv_pdf
from job_retrieval_tool import JobRetrievalTool
from profile_model import DraftExperienceEntry, DraftProjectEntry

st.set_page_config(page_title="AI CV Builder", layout="centered")

# One "session" (sidebar entry) is exactly this bundle of state - kept as
# flat st.session_state keys, precisely as they were before multi-session
# support existed, rather than nested under a sessions dict everywhere in
# the stage logic below. Only the sidebar and the switch/new-session
# helpers need to know these flat keys represent "whichever session is
# currently active" - every existing stage branch keeps reading/writing
# them exactly as before and needs no changes at all.
SESSION_KEYS = (
    "agent",
    "stage",
    "pending_question",
    "confirm_summary",
    "review_pending_question",
    "review_checked",
    "job_matches",
    "chosen_job",
    "job_requirement_gaps",
    "job_requirement_question",
    "job_chat_turn",
    "cv",
    "pdf_bytes",
    "profile",
)


@st.cache_resource
def get_llm() -> LLMClient:
    return build_llm()


@st.cache_resource
def get_job_tool() -> JobRetrievalTool:
    return JobRetrievalTool()


def _sync_active_session() -> None:
    """Copies the current flat session_state keys into the active session's
    stored bundle in st.session_state.sessions - called right before
    switching away from it (to a different sidebar entry, or when starting
    a new one), so nothing done in it is lost. A no-op before any session
    exists yet (the very first call, during bootstrap)."""
    active_id = st.session_state.get("active_id")
    if active_id is None:
        return
    st.session_state.sessions[active_id] = {
        key: st.session_state[key] for key in SESSION_KEYS if key in st.session_state
    }


def _activate_session(session_id: str) -> None:
    """Loads a stored session bundle into the flat keys the rest of the
    script reads/writes, clearing any flat key that bundle doesn't have (so
    a later stage from a different session can never leak into this one).
    Each session's ProfileAgent/ProfileTool lives entirely inside its own
    bundle - the same per-instance isolation already verified for separate
    users in 03_Evidence/04_System_Tests/cross_user_test.md - so switching
    sidebar entries can never mix two profiles' data; this just changes
    which already-isolated instance the flat keys point at."""
    bundle = st.session_state.sessions.get(session_id, {})
    for key in SESSION_KEYS:
        if key in bundle:
            st.session_state[key] = bundle[key]
        else:
            st.session_state.pop(key, None)
    st.session_state.active_id = session_id


def start_new_session() -> None:
    """Starts a brand new profile conversation as a NEW sidebar entry,
    leaving every existing session's data exactly as it was - local,
    in-memory only (st.session_state), reset on a full app reload, no
    database involved. job_tool is intentionally not passed to
    ProfileAgent: job retrieval happens explicitly from the confirm-stage's
    button, against the corrected profile, not automatically inside
    take_turn()."""
    _sync_active_session()
    st.session_state.setdefault("sessions", {})
    st.session_state.setdefault("session_order", [])
    session_id = uuid.uuid4().hex
    st.session_state.sessions[session_id] = {}
    st.session_state.session_order.append(session_id)
    st.session_state.active_id = session_id
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)
    st.session_state.agent = ProfileAgent(get_llm(), step_cap=5, review_step_cap=10)
    st.session_state.stage = "intro"


def _session_agent(session_id: str):
    """The live ProfileAgent for any session, active or not - the active
    session's is only ever in the flat st.session_state.agent (not yet
    synced into its bundle); every other session's lives in its stored
    bundle."""
    if session_id == st.session_state.active_id:
        return st.session_state.get("agent")
    return st.session_state.sessions.get(session_id, {}).get("agent")


def _session_label(session_id: str, index: int) -> str:
    agent = _session_agent(session_id)
    name = agent.tool.read_profile()["draft"].get("name") if agent else None
    return f"Profile {index + 1} - {name}" if name else f"Profile {index + 1}"


def _editable_text_snapshot(cv: dict) -> dict:
    """Snapshot of every free-text field the "cv" stage lets a user hand-edit,
    keyed so it can be matched back onto a freshly regenerated CV for the
    same job - see _restore_manual_edits()."""
    return {
        "summary": cv.get("summary", ""),
        "education": cv.get("education", ""),
        "additional_education": [e.get("text", "") for e in cv.get("additional_education") or []],
        "experience": {
            (e.get("role", ""), e.get("organisation", "")): e.get("description", "")
            for e in cv.get("experience") or []
        },
        "projects": {p.get("title", ""): p.get("description", "") for p in cv.get("projects") or []},
    }


def _restore_manual_edits(previous_cv: dict, new_cv: dict) -> None:
    """Carries forward any field the user hand-edited on `previous_cv` onto
    the freshly regenerated `new_cv` for the SAME job, so sending a message
    in the per-job chat box no longer silently wipes out text typed into the
    Summary/Education/Experience/Project boxes above it. Only fields that
    actually differ from what was last auto-generated (cv_generated_snapshot)
    are carried forward - an untouched field still gets the fresh LLM output,
    so a chat message that adds a new confirmed fact still updates anything
    the user hasn't personally rewritten. Switching to a genuinely different
    job clears "cv" first (see the "Choose a different job" button below),
    so `previous_cv` is None there and nothing gets carried forward - the new
    job's CV starts clean, as the confirmed-profile-stays-stable requirement
    needs."""
    baseline = st.session_state.get("cv_generated_snapshot")
    if baseline is None:
        return
    prev_edits = _editable_text_snapshot(previous_cv)
    base_edits = _editable_text_snapshot(baseline)

    if prev_edits["summary"] != base_edits["summary"]:
        new_cv["summary"] = prev_edits["summary"]
    if prev_edits["education"] != base_edits["education"]:
        new_cv["education"] = prev_edits["education"]

    for i, entry in enumerate(new_cv.get("additional_education") or []):
        if i < len(prev_edits["additional_education"]) and i < len(base_edits["additional_education"]):
            if prev_edits["additional_education"][i] != base_edits["additional_education"][i]:
                entry["text"] = prev_edits["additional_education"][i]

    for entry in new_cv.get("experience") or []:
        key = (entry.get("role", ""), entry.get("organisation", ""))
        if key in prev_edits["experience"] and prev_edits["experience"][key] != base_edits["experience"].get(key):
            entry["description"] = prev_edits["experience"][key]

    for entry in new_cv.get("projects") or []:
        title = entry.get("title", "")
        if title in prev_edits["projects"] and prev_edits["projects"][title] != base_edits["projects"].get(title):
            entry["description"] = prev_edits["projects"][title]


def generate_cv_for_chosen_job(chosen_job: dict) -> None:
    """Shared by both paths into the "cv" stage: a job with no requirement
    gaps (straight from "jobs"), and a job whose gaps were just resolved
    (from "job_requirements"). Builds the profile fresh so any skill/note
    confirmed in the requirement check is reflected in the CV. Skills,
    matched_skills and missing_requirements are always the fresh values from
    this generation, never carried over - those must keep tracing straight
    to the confirmed profile, not to whatever was last typed into a box."""
    previous_cv = st.session_state.get("cv")
    profile = st.session_state.agent.tool.to_profile(document_id=f"gui_{uuid.uuid4().hex[:8]}")
    with st.spinner("Generating your tailored CV..."):
        cv = CVGenerator(llm=get_llm()).generate(profile, chosen_job)
    if previous_cv is not None:
        _restore_manual_edits(previous_cv, cv)
    st.session_state.chosen_job = chosen_job
    st.session_state.profile = profile
    st.session_state.cv = cv
    st.session_state.cv_generated_snapshot = copy.deepcopy(cv)
    st.session_state.pop("pdf_bytes", None)


if "session_order" not in st.session_state:
    start_new_session()


def handle_turn_result(result: dict) -> None:
    if result["status"] == "needs_input":
        st.session_state.pending_question = result["question"]
        st.session_state.stage = "followup"
    elif result["status"] == "confirmed":
        st.session_state.confirm_summary = result["summary"]
        # The review-phase bootstrap check (start_review()) is deliberately
        # NOT run here: it's another live LLM call, and this function runs
        # AFTER the submit button's own spinner block has already closed -
        # calling it here left the page showing no feedback at all for the
        # full duration of that second call (measured 50+ seconds live),
        # which is exactly what looked like the submit button "not working."
        # review_checked=False defers it to the "confirm" stage's own
        # render, where it gets its own spinner right where the delay is.
        st.session_state.review_checked = False
        st.session_state.stage = "confirm"
    else:
        st.session_state.stage = "step_limit"


def render_conversation_history(include_latest_question: bool = True) -> None:
    """Renders the user/assistant Q&A trace. When include_latest_question is
    False, the most recent AskFollowUp entry is skipped - used on the
    "followup" stage, where that same question is already shown once,
    highlighted, directly below (see st.info(pending_question)) with the
    answer box beneath it. Without this, the current question rendered
    twice: once here, once in that box."""
    trace = st.session_state.agent.trace
    last_ask_index = None
    if not include_latest_question:
        for i in range(len(trace) - 1, -1, -1):
            if trace[i].get("action") == "AskFollowUp":
                last_ask_index = i
                break
    for i, entry in enumerate(trace):
        if entry["role"] == "user":
            st.markdown(f"**You:** {entry['text']}")
        elif entry.get("action") == "AskFollowUp":
            if i == last_ask_index:
                continue
            st.markdown(f"**Assistant:** {entry['observation']['question']}")


with st.sidebar:
    st.subheader("Sessions")
    st.caption("Local to this app run only - no database, resets on a full reload.")
    if st.button("+ New chat", type="primary", use_container_width=True):
        start_new_session()
        st.rerun()
    st.divider()
    for i, sid in enumerate(st.session_state.session_order):
        is_active = sid == st.session_state.active_id
        if st.button(
            _session_label(sid, i),
            key=f"session_btn_{sid}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            if not is_active:
                _sync_active_session()
                _activate_session(sid)
                st.rerun()
    st.divider()
    st.caption(f"Stage: `{st.session_state.stage}`")

st.title("AI-Powered CV Builder")

stage = st.session_state.stage

if stage == "intro":
    st.header("1. Tell us about yourself")
    st.caption("Education, skills, projects/experience, and the kind of roles you're after.")
    intro_text = st.text_area("Introduction", height=150, key="intro_text")
    submitted = st.button("Submit", type="primary")
    if submitted and intro_text.strip():
        with st.spinner("Reading your introduction..."):
            result = st.session_state.agent.take_turn(intro_text.strip())
        handle_turn_result(result)
        st.rerun()
    elif submitted:
        st.warning("Please enter an introduction first.")

elif stage == "followup":
    st.header("2. A couple of follow-up questions")
    render_conversation_history(include_latest_question=False)
    st.info(st.session_state.pending_question)
    reply = st.text_input("Your answer", key=f"reply_{len(st.session_state.agent.trace)}")
    submitted = st.button("Submit answer", type="primary")
    if submitted and reply.strip():
        with st.spinner("Thinking..."):
            result = st.session_state.agent.take_turn(reply.strip())
        handle_turn_result(result)
        st.rerun()
    elif submitted:
        st.warning("Please enter an answer first.")

elif stage == "step_limit":
    st.header("Could not complete your profile")
    st.error(
        "The conversation went on too long without gathering everything required. "
        "Start over and try a more complete introduction."
    )
    render_conversation_history()

elif stage == "confirm":
    st.header("3. Confirm your profile")
    st.write(st.session_state.confirm_summary)

    if not st.session_state.get("review_checked", False):
        # Runs once, right after intake confirms (see handle_turn_result()) -
        # the header/summary above are already rendered by the time this
        # spinner shows, so the delay is visibly attached to "checking your
        # projects" rather than looking like the previous submit did nothing.
        with st.spinner("Checking your projects for anything missing..."):
            review_result = st.session_state.agent.start_review()
        st.session_state.review_checked = True
        st.session_state.review_pending_question = (
            review_result["question"] if review_result["status"] == "needs_input" else None
        )

    if st.session_state.get("review_pending_question"):
        with st.container(border=True):
            st.caption(
                "One of your projects is missing a detail - answer below, or say you don't have it "
                "and it'll be left off."
            )
            st.info(st.session_state.review_pending_question)
            review_reply = st.text_input(
                "Your answer", key=f"review_reply_{len(st.session_state.agent.trace)}"
            )
            review_submitted = st.button("Submit answer", type="primary", key="review_submit")
            if review_submitted and review_reply.strip():
                with st.spinner("Thinking..."):
                    review_result = st.session_state.agent.take_turn(review_reply.strip(), phase="review")
                if review_result["status"] == "needs_input":
                    st.session_state.review_pending_question = review_result["question"]
                else:
                    st.session_state.review_pending_question = None
                    if review_result["status"] == "confirmed":
                        st.session_state.confirm_summary = review_result["summary"]
                st.rerun()
            elif review_submitted:
                st.warning("Please enter an answer first.")

    draft = st.session_state.agent.tool.read_profile()["draft"]

    with st.form("edit_profile_form"):
        st.subheader("Edit your profile")
        st.caption("Correct anything wrong, or fill in what the introduction didn't cover.")

        st.markdown("**Contact details**")
        name = st.text_input("Name", value=draft["name"] or "")
        c1, c2 = st.columns(2)
        with c1:
            email = st.text_input("Email", value=draft.get("email") or "")
            github = st.text_input("GitHub", value=draft.get("github") or "")
        with c2:
            phone = st.text_input("Phone", value=draft.get("phone") or "")
            linkedin = st.text_input("LinkedIn", value=draft.get("linkedin") or "")

        st.markdown("**Education**")
        e1, e2 = st.columns(2)
        with e1:
            degree = st.text_input("Degree", value=draft["degree"] or "")
            institution = st.text_input("Institution", value=draft.get("institution") or "")
        with e2:
            year = st.text_input("Year of study", value=draft["year"] or "")

        # Work experience is never required by the conversation (an
        # unmentioned work history is just treated as none), so this section
        # always shows at least one slot - blank if nothing was mentioned -
        # rather than disappearing entirely, giving a place to add it later
        # even though the agent never asked. Positioned right after Education
        # (not further down with the other optional sections) to match the
        # same fixed placement used in the CV review stage and the exported
        # PDF.
        edited_experience = []
        st.markdown("**Experience**")
        experience_rows = draft["experience"] or [{"role": "", "organisation": "", "description": ""}]
        if not draft["experience"]:
            st.caption("No work experience was mentioned - leave blank if you don't have any, or fill in to add one.")
        for i, exp in enumerate(experience_rows):
            st.caption(f"Experience {i + 1}")
            role = st.text_input(f"Role {i + 1}", value=exp.get("role") or "", key=f"pf_exp_role_{i}")
            org = st.text_input(f"Organisation {i + 1}", value=exp.get("organisation") or "", key=f"pf_exp_org_{i}")
            desc = st.text_area(f"Description {i + 1}", value=exp.get("description") or "", key=f"pf_exp_desc_{i}")
            if role.strip() or org.strip() or desc.strip():
                edited_experience.append({"role": role, "organisation": org, "description": desc})

        st.markdown("**Skills**")
        skills_line = st.text_input("Technical skills (comma-separated)", value=", ".join(draft["technical_skills"]))

        st.markdown("**Job goal**")
        roles_line = st.text_input("Target roles (comma-separated)", value=", ".join(draft["target_roles"]))
        summary_text = st.text_area("Career summary", value=draft["summary"] or "")

        st.markdown("**Achievements**")
        achievements_line = st.text_input(
            "Achievements/activities (comma-separated)", value=", ".join(draft.get("achievements", []))
        )

        # Projects, like experience, is never required by the conversation
        # (an unmentioned project list is just treated as none), so this
        # section always shows at least one slot rather than disappearing.
        edited_projects = []
        st.markdown("**Projects**")
        project_rows = draft["projects"] or [{"title": "", "description": "", "technologies": []}]
        if not draft["projects"]:
            st.caption("No projects were mentioned - leave blank if you don't have any, or fill in to add one.")
        for i, proj in enumerate(project_rows):
            st.caption(f"Project {i + 1}")
            title = st.text_input(f"Title {i + 1}", value=proj.get("title") or "", key=f"pf_proj_title_{i}")
            tech_line = st.text_input(
                f"Technologies {i + 1} (comma-separated)",
                value=", ".join(proj.get("technologies", [])),
                key=f"pf_proj_tech_{i}",
            )
            desc = st.text_area(f"Description {i + 1}", value=proj.get("description") or "", key=f"pf_proj_desc_{i}")
            if title.strip():
                edited_projects.append(
                    {
                        "title": title,
                        "description": desc,
                        "technologies": [t.strip() for t in tech_line.split(",") if t.strip()],
                    }
                )

        col_save, col_confirm = st.columns(2)
        with col_save:
            save_clicked = st.form_submit_button("Save changes")
        with col_confirm:
            confirm_clicked = st.form_submit_button("Confirm & find matching jobs", type="primary")

    if save_clicked or confirm_clicked:
        st.session_state.agent.tool.overwrite_profile(
            {
                "name": name.strip() or None,
                "email": email.strip() or None,
                "phone": phone.strip() or None,
                "github": github.strip() or None,
                "linkedin": linkedin.strip() or None,
                "degree": degree.strip() or None,
                "institution": institution.strip() or None,
                "year": year.strip() or None,
                "technical_skills": [s.strip() for s in skills_line.split(",") if s.strip()],
                "target_roles": [r.strip() for r in roles_line.split(",") if r.strip()],
                "summary": summary_text.strip() or None,
                "achievements": [a.strip() for a in achievements_line.split(",") if a.strip()],
                "experience": [DraftExperienceEntry(**e) for e in edited_experience],
                "projects": [DraftProjectEntry(**p) for p in edited_projects],
            }
        )

    if save_clicked:
        new_draft = st.session_state.agent.tool.read_profile()["draft"]
        with st.spinner("Updating summary..."):
            st.session_state.confirm_summary = st.session_state.agent.llm.generate_text(
                SUMMARY_SYSTEM_PROMPT, json.dumps(new_draft)
            )
        st.rerun()

    if confirm_clicked:
        profile_obj = st.session_state.agent.tool.to_profile(document_id=f"gui_{uuid.uuid4().hex[:8]}")
        with st.spinner("Finding matching jobs..."):
            matches = get_job_tool().search(profile_obj, top_k=3)
        st.session_state.job_matches = matches
        st.session_state.stage = "jobs"
        st.rerun()

elif stage == "jobs":
    st.header("4. Pick a target job")
    st.caption("Top 3 matches for your profile, most relevant first.")
    for i, m in enumerate(st.session_state.job_matches):
        with st.container(border=True):
            st.markdown(f"**{m['title']}**  ·  `{m['document_id']}`  ·  score {m['score']}")
            st.caption(m["excerpt"])
            if st.button("Select this job", key=f"job_{i}"):
                job_tool = get_job_tool()
                chosen_job = job_tool.get_job_by_id(m["document_id"])
                checker = JobRequirementAgent(get_llm(), st.session_state.agent.tool)
                with st.spinner("Checking this role's specific requirements against your profile..."):
                    check_result = checker.check(chosen_job)
                if check_result["status"] == "needs_input":
                    st.session_state.job_requirement_gaps = check_result["gaps"]
                    st.session_state.job_requirement_question = check_result["question"]
                else:
                    st.session_state.pop("job_requirement_gaps", None)
                    st.session_state.pop("job_requirement_question", None)
                st.session_state.job_chat_turn = 0
                generate_cv_for_chosen_job(chosen_job)
                st.session_state.stage = "cv"
                st.rerun()

elif stage == "cv":
    st.header("5. Review, preview & export your CV")

    if st.button("← Choose a different job"):
        # Only reset the job-specific CV state - the confirmed profile
        # (st.session_state.agent) and the already-retrieved top-3
        # (st.session_state.job_matches) are left untouched, so no
        # re-confirmation or re-retrieval happens.
        for key in (
            "chosen_job", "cv", "cv_generated_snapshot", "pdf_bytes",
            "job_requirement_gaps", "job_requirement_question", "job_chat_turn",
        ):
            st.session_state.pop(key, None)
        st.session_state.stage = "jobs"
        st.rerun()

    with st.container(border=True):
        st.subheader("Chat: add or adjust anything for this role")
        if st.session_state.get("job_requirement_question"):
            st.caption(
                f"The {st.session_state.chosen_job['title']} listing asks for a few things your "
                "profile doesn't currently show - answer honestly, since anything you don't "
                "confirm won't appear on this CV."
            )
            st.info(st.session_state.job_requirement_question)
        else:
            st.caption(
                f"No open questions for the {st.session_state.chosen_job['title']} role right now, "
                "but you can keep sending messages here anytime - an extra skill, a correction, "
                "more detail - each one updates your CV."
            )
        chat_turn = st.session_state.get("job_chat_turn", 0)
        reply = st.text_input("Your message", key=f"job_chat_input_{chat_turn}")
        submitted = st.button("Send", type="primary", key=f"job_chat_submit_{chat_turn}")
        if submitted and reply.strip():
            agent = st.session_state.agent
            pending_gaps = st.session_state.get("job_requirement_gaps")

            if pending_gaps:
                # Resolves the NAMED requirement gaps specifically (grounds
                # each one as confirmed or confirmed-absent) - but
                # JobRequirementAgent only ever writes to technical_skills/
                # achievements, so on its own it would silently lose
                # anything richer a reply happens to also contain (a new
                # project, a second degree, a new experience entry).
                checker = JobRequirementAgent(get_llm(), agent.tool)
                with st.spinner("Thinking..."):
                    resolution = checker.resolve(pending_gaps, reply.strip())
                if resolution["confirmed_skills"]:
                    st.toast(f"Confirmed: {', '.join(resolution['confirmed_skills'])}")

            # ALWAYS also run the same reply through general extraction - a
            # reply to a named requirement is still an ordinary message and
            # may carry facts JobRequirementAgent has no schema for at all.
            # This is what actually captures a new project, a second
            # degree, or a new experience entry mentioned in the same
            # breath as answering the job-specific question - skipping it
            # is exactly what silently dropped those before.
            with st.spinner("Updating your profile..."):
                extracted = agent.llm.extract_json(
                    EXTRACTION_SYSTEM_PROMPT,
                    json.dumps(
                        {
                            "current_draft": agent.tool.read_profile()["draft"],
                            "last_question_asked": st.session_state.get("job_requirement_question"),
                            "latest_message": reply.strip(),
                        }
                    ),
                    # See agent.py's take_turn() for the max_tokens tightrope
                    # this now walks between truncated output and GROQ
                    # rejecting an over-large request outright.
                    max_tokens=4000,
                )
                update_observation = agent.tool.update_profile(extracted)
            if update_observation["new_facts"]:
                st.success("Got it — " + "; ".join(update_observation["new_facts"]) + ".")

            checker = JobRequirementAgent(get_llm(), agent.tool)
            # Re-check this job's requirements fresh against the updated
            # profile - already-confirmed/declined items are filtered out
            # by JobRequirementAgent itself, so this naturally surfaces only
            # whatever is still genuinely open, letting the chat keep
            # working across any number of messages instead of vanishing
            # after the first one.
            with st.spinner("Re-checking this role's requirements..."):
                check_result = checker.check(st.session_state.chosen_job)
            if check_result["status"] == "needs_input":
                st.session_state.job_requirement_gaps = check_result["gaps"]
                st.session_state.job_requirement_question = check_result["question"]
            else:
                st.session_state.pop("job_requirement_gaps", None)
                st.session_state.pop("job_requirement_question", None)
            st.session_state.job_chat_turn = chat_turn + 1
            generate_cv_for_chosen_job(st.session_state.chosen_job)
            st.rerun()
        elif submitted:
            st.warning("Please enter a message first.")

    cv = st.session_state.cv

    if cv["grounding_warnings"]:
        st.warning(
            "Some generated content didn't match your confirmed profile and was removed:\n"
            + "\n".join(f"- {w}" for w in cv["grounding_warnings"])
        )

    # Every widget below is keyed on chat_turn (bumped each time the chat box
    # regenerates the CV) so a message that adds/changes an Experience,
    # Project, or additional_education entry always shows up - a widget with
    # a STABLE key ignores any new value= it's given on rerun once it exists
    # (Streamlit keeps the widget's own prior state instead), which is
    # exactly what silently froze those sections after the first chat
    # message. Summary/Education/Skills happened to look fine before this
    # fix only because they had no explicit key at all (an auto-generated,
    # value-sensitive key sidesteps the problem by accident) - keyed
    # explicitly now too, for the same guarantee rather than relying on that.
    chat_turn = st.session_state.get("job_chat_turn", 0)

    st.caption(
        "Editing a field below only changes THIS CV - it doesn't get added to your "
        "confirmed profile, so it won't carry over if you pick a different job. To add "
        "something permanently, mention it in the chat box above instead."
    )
    cv["summary"] = st.text_area("Summary", value=cv["summary"], height=100, key=f"cv_summary_{chat_turn}")
    cv["education"] = st.text_area("Education", value=cv["education"], height=80, key=f"cv_education_{chat_turn}")
    for i, entry in enumerate(cv.get("additional_education") or []):
        entry["text"] = st.text_input(
            f"Additional qualification {i + 1}", value=entry["text"], key=f"add_edu_{chat_turn}_{i}"
        )

    if cv["experience"]:
        st.subheader("Experience")
        for i, exp in enumerate(cv["experience"]):
            title = f"{exp['role']} — {exp['organisation']}" if exp.get("organisation") else exp["role"]
            exp["description"] = st.text_area(title, value=exp["description"], key=f"exp_{chat_turn}_{i}")

    skills_line = st.text_input(
        "Skills (comma-separated)", value=", ".join(cv["skills"]), key=f"cv_skills_{chat_turn}"
    )
    cv["skills"] = [s.strip() for s in skills_line.split(",") if s.strip()]

    if cv["projects"]:
        st.subheader("Projects")
        for i, proj in enumerate(cv["projects"]):
            proj["description"] = st.text_area(proj["title"], value=proj["description"], key=f"proj_{chat_turn}_{i}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Matched skills")
        st.write(", ".join(cv["matched_skills"]) or "(none)")
    with col2:
        st.subheader("Missing requirements")
        st.write(", ".join(cv["missing_requirements"]) or "(none)")

    if st.button("Generate / update PDF preview", type="primary"):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        render_cv_pdf(cv, st.session_state.profile, tmp_path)
        st.session_state.pdf_bytes = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)

    if st.session_state.get("pdf_bytes"):
        st.subheader("Preview")
        st.caption("Edit a field above and click the button again to refresh this preview.")
        st.pdf(st.session_state.pdf_bytes, height=600)
        safe_name = (st.session_state.profile.contact.name or "candidate").replace(" ", "_")
        st.download_button(
            "Download PDF",
            data=st.session_state.pdf_bytes,
            file_name=f"{safe_name}_cv.pdf",
            mime="application/pdf",
        )
