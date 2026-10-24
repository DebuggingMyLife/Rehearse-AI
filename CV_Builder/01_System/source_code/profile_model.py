from dataclasses import dataclass, field
from typing import List, Optional


def _merge_description(existing: Optional[str], new: str) -> str:
    """Appends any genuinely new "\\n"-separated line(s) from `new` onto
    `existing`, rather than overwriting or discarding them - a later turn
    that adds outcome detail to an already-described experience or project
    entry (e.g. answering a review-stage project_outcome follow-up, or the
    student volunteering measurable results unprompted) must land as an
    ADDITIONAL bullet, not be silently dropped just because the entry
    already had some description. Case-insensitive
    dedup against existing lines, same as every other list-merge in this
    file, so re-stating something already captured doesn't duplicate it."""
    existing_lines = [line.strip() for line in (existing or "").split("\n") if line.strip()]
    existing_lower = {line.lower() for line in existing_lines}
    for line in (l.strip() for l in new.split("\n") if l.strip()):
        if line.lower() not in existing_lower:
            existing_lines.append(line)
            existing_lower.add(line.lower())
    return "\n".join(existing_lines)


@dataclass
class ContactDetails:
    name: str
    github: Optional[str] = None
    linkedin: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class Education:
    # program_mode/faculty/campus/study_mode were dropped - they were
    # hardcoded to a single UTS-specific value for every user-submitted
    # profile regardless of what the student actually said, which is
    # exactly the kind of unconfirmed claim this project's grounding rules
    # exist to prevent. institution is genuinely asked now (same tier as
    # degree/year - see DraftProfile.institution) rather than assumed.
    degree: str
    institution: str
    year: str
    # expected_graduation doubles as the completion/end date once one is
    # captured (see DraftProfile.education_end_date) - genuinely optional
    # now rather than a hardcoded placeholder string, so cv_pdf.py can tell
    # "no date given" apart from "a real date". start_date is new: same
    # never-fabricated rule as ExperienceEntry/ProjectEntry's own dates.
    expected_graduation: Optional[str] = None
    start_date: Optional[str] = None
    relevant_current_subjects: List[str] = field(default_factory=list)
    prerequisite_context: Optional[str] = None


@dataclass
class SkillEvidence:
    skill: str
    source: str


@dataclass
class Skills:
    technical_skills: List[str] = field(default_factory=list)
    evidence: List[SkillEvidence] = field(default_factory=list)


@dataclass
class ExperienceEntry:
    role: str
    organisation: str
    type: str
    description: str
    # Raw text as stated (e.g. "June 2023", "2022") - never fabricated if
    # not mentioned. cv_pdf.format_date_range() normalizes these into the
    # spec's "Mon. YYYY - Mon. YYYY" display format at render time; left
    # None here rather than guessed. end_date="Present" signals ongoing.
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass
class Experience:
    entries: List[ExperienceEntry] = field(default_factory=list)


@dataclass
class ProjectEntry:
    title: str
    context: str
    description: str
    technologies: List[str] = field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass
class Projects:
    entries: List[ProjectEntry] = field(default_factory=list)


@dataclass
class Achievements:
    activities: List[str] = field(default_factory=list)


@dataclass
class JobGoal:
    target_roles: List[str] = field(default_factory=list)
    availability: Optional[str] = None
    work_rights: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class AdditionalEducationEntry:
    """A qualification beyond the primary one on Education - e.g. a second,
    later degree ("also completed a Master's in X"). Kept separate from
    Education itself rather than turning `education` into a list, so the
    existing single-primary-degree flow (missing_fields/gap logic, the GUI's
    degree/year form fields, CV generation's single "education" string)
    needs no restructuring - this only ever ADDS entries, never replaces
    the primary."""

    degree: str
    year: Optional[str] = None
    # Same never-fabricated rule as every other date field in this project -
    # only ever set when the student explicitly states a timeframe for THIS
    # qualification. `year` (above) predates these and stays for the simple
    # single-value case; start_date/end_date carry a full range when given.
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass
class Profile:
    document_id: str
    profile_type: str
    dataset_scope: str
    contact: ContactDetails
    education: Education
    skills: Skills
    experience: Experience
    projects: Projects
    achievements: Achievements
    job_goal: JobGoal
    additional_education: List[AdditionalEducationEntry] = field(default_factory=list)

    @classmethod
    def from_record(cls, record: dict) -> "Profile":
        links = record.get("links", {})
        return cls(
            document_id=record["document_id"],
            profile_type=record["profile_type"],
            dataset_scope=record["dataset_scope"],
            contact=ContactDetails(
                name=record["name"],
                github=links.get("github"),
                linkedin=links.get("linkedin"),
            ),
            education=Education(
                degree=record["degree"],
                institution=record["institution"],
                year=record["year"],
                expected_graduation=record["expected_graduation"],
                start_date=record.get("start_date"),
                relevant_current_subjects=record.get("relevant_current_subjects", []),
                prerequisite_context=record.get("prerequisite_context"),
            ),
            skills=Skills(
                technical_skills=record.get("technical_skills", []),
                evidence=[
                    SkillEvidence(skill=e["skill"], source=e["source"])
                    for e in record.get("skill_evidence", [])
                ],
            ),
            experience=Experience(
                entries=[
                    ExperienceEntry(
                        role=e["role"],
                        organisation=e["organisation"],
                        type=e["type"],
                        description=e["description"],
                    )
                    for e in record.get("experience", [])
                ]
            ),
            projects=Projects(
                entries=[
                    ProjectEntry(
                        title=p["title"],
                        context=p["context"],
                        description=p["description"],
                        technologies=p.get("technologies", []),
                    )
                    for p in record.get("projects", [])
                ]
            ),
            achievements=Achievements(activities=record.get("activities", [])),
            job_goal=JobGoal(
                target_roles=record.get("target_roles", []),
                availability=record.get("availability"),
                work_rights=record.get("work_rights"),
                summary=record.get("summary"),
            ),
        )


@dataclass
class DraftProjectEntry:
    title: str
    description: Optional[str] = None
    technologies: List[str] = field(default_factory=list)
    # Raw text as stated, only ever set when the student explicitly gives a
    # timeframe (e.g. "from March to June 2024") - never guessed. See
    # ExperienceEntry's matching fields for how these reach the CV/PDF.
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    # True once the student has explicitly declined to give a detail the
    # review stage specifically asked about (see compute_gaps()'s
    # phase="review" and merge()'s "declined_fields" handling) - a genuine
    # Python-tracked flag rather than relying on the LLM noticing from
    # last_question_asked alone that a field was already answered, since
    # the review stage's one-gap-per-turn loop makes several sequential
    # asks where that kind of memory-less judgement is exactly the sort of
    # prompt reliance this project has repeatedly had to backstop. Never
    # reset once True.
    dates_declined: bool = False
    outcome_declined: bool = False


@dataclass
class DraftExperienceEntry:
    # Optional, not required: an entry can start out identified only by
    # organisation (e.g. "I worked at Accenture") before the role is known,
    # then get refined by a later turn - see DraftProfile.merge().
    role: Optional[str] = None
    organisation: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass
class DraftEducationEntry:
    """A qualification beyond the primary degree/year fields - see
    AdditionalEducationEntry (the confirmed-Profile equivalent) for why this
    is a separate list rather than turning degree/year into one."""

    degree: str
    year: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


# Order determines which missing field the agent asks about first.
REQUIRED_FIELD_ORDER = ["name", "degree", "institution", "year", "technical_skills", "evidence", "target_roles"]

# Priority order for the gaps produced by the extraction/completeness prompt,
# most important first - see DraftProfile.compute_gaps(). There is no
# confirm_project/confirm_education entry: a stated fact is trusted the
# moment it's captured, never read back and re-confirmed in isolation - the
# single, whole-profile review stage (SUMMARY_SYSTEM_PROMPT, shown once
# every other gap is resolved) is the only point corrections happen.
# project_dates/project_outcome are only ever surfaced during
# compute_gaps()'s phase="review" pass (see its docstring) - during intake
# they're computed by the model but filtered out before reaching this
# ordering. project_results (measurable results/metrics) has no entry here
# at all: it is never asked about, at any phase - fully optional, captured
# only if the student volunteers it unprompted.
GAP_PRIORITY_ORDER = [
    "name", "degree", "institution", "year", "education", "education_dates",
    "technical_skills", "experience", "project_dates", "project_outcome",
    "projects", "target_roles", "achievements",
]


@dataclass
class DraftProfile:
    """The subset of Profile an agent can plausibly fill in from a free-text
    introduction. institution is asked for directly (same tier as degree/
    year) rather than assumed - a hardcoded single institution for every
    live user was exactly the kind of unconfirmed claim this project's
    grounding rules exist to prevent."""

    name: Optional[str] = None
    degree: Optional[str] = None
    institution: Optional[str] = None
    year: Optional[str] = None
    # Primary degree's own timeframe - never fabricated, same rule as every
    # other date field in this project. education_end_date doubles as an
    # expected-graduation date when the degree is still in progress.
    education_start_date: Optional[str] = None
    education_end_date: Optional[str] = None
    # A SEPARATE qualification from the primary degree/year above - e.g. "I
    # also have a Master's in Data Science" while degree already holds a
    # Bachelor's. Never overwrites degree/year; only ever appended to. See
    # merge()'s additive-vs-correction handling.
    additional_education: List[DraftEducationEntry] = field(default_factory=list)
    technical_skills: List[str] = field(default_factory=list)
    projects: List[DraftProjectEntry] = field(default_factory=list)
    experience: List[DraftExperienceEntry] = field(default_factory=list)
    target_roles: List[str] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)
    summary: Optional[str] = None

    # Sticky flags: an empty list is ambiguous on its own (never asked about vs
    # explicitly confirmed empty), so this can't be derived from list content
    # alone. Set True by merge() the moment either real content exists OR the
    # extraction call signals the student explicitly declined the section -
    # and, once True, never reset, so a later turn's fresh gaps judgement
    # (which only sees current_draft + the latest message, not the full
    # conversation) can't re-flag something already resolved several turns
    # ago.
    work_experience_addressed: bool = False
    projects_addressed: bool = False
    achievements_addressed: bool = False

    # Requirement names a job-specific requirement check has already asked
    # about and the student confirmed they don't have (see
    # agent.JobRequirementAgent) - kept case-insensitively unique and never
    # cleared, so a later job that happens to share the same requirement
    # doesn't re-ask about something already answered.
    declined_requirements: List[str] = field(default_factory=list)

    # email/phone/github/linkedin are never populated by extraction/merge() -
    # only ever set via direct user edit (e.g. the GUI's confirm-stage form),
    # so they add no new hallucination surface. Not part of
    # missing_fields()/REQUIRED_FIELD_ORDER either: a free introduction was
    # never expected to state a phone number.
    email: Optional[str] = None
    phone: Optional[str] = None
    github: Optional[str] = None
    linkedin: Optional[str] = None

    def missing_fields(self) -> List[str]:
        missing = []
        if not self.name:
            missing.append("name")
        if not self.degree:
            missing.append("degree")
        if not self.institution:
            missing.append("institution")
        if not self.year:
            missing.append("year")
        if not self.technical_skills:
            missing.append("technical_skills")
        if not self.projects and not self.experience:
            missing.append("evidence")
        if not self.target_roles:
            missing.append("target_roles")
        return sorted(missing, key=REQUIRED_FIELD_ORDER.index)

    def merge(self, fields: dict) -> None:
        # Scalars overwrite rather than fill-only-if-empty: the extraction
        # prompt is instructed to only return a non-null value here when the
        # latest message adds something new, which now includes REFINING an
        # already-present-but-ambiguous value (e.g. "Computing Science" ->
        # "Bachelor of Computing Science"), not just filling a first-time gap.
        if fields.get("name"):
            self.name = str(fields["name"]).strip()
        if fields.get("degree"):
            self.degree = str(fields["degree"]).strip()
        if fields.get("institution"):
            self.institution = str(fields["institution"]).strip()
        if fields.get("year"):
            self.year = str(fields["year"]).strip()
        if fields.get("education_start_date"):
            self.education_start_date = str(fields["education_start_date"]).strip()
        if fields.get("education_end_date"):
            self.education_end_date = str(fields["education_end_date"]).strip()
        if fields.get("summary"):
            self.summary = str(fields["summary"]).strip()

        # additional_education only ever appends - unlike degree/year above,
        # a genuinely separate qualification (e.g. a Master's alongside an
        # existing Bachelor's) must never overwrite anything. The extraction
        # prompt is instructed to route a new degree statement here instead
        # of into degree/year whenever it reads as additive rather than a
        # refinement/correction of the existing one.
        existing_additional_degrees = {e.degree.lower() for e in self.additional_education}
        for entry in fields.get("additional_education") or []:
            degree = str(entry.get("degree") or "").strip()
            if not degree:
                continue
            year = entry.get("year")
            year = str(year).strip() if year else None
            start_date = entry.get("start_date")
            start_date = str(start_date).strip() if start_date else None
            end_date = entry.get("end_date")
            end_date = str(end_date).strip() if end_date else None
            if degree.lower() in existing_additional_degrees:
                existing = next(e for e in self.additional_education if e.degree.lower() == degree.lower())
                if year and not existing.year:
                    existing.year = year
                if start_date and not existing.start_date:
                    existing.start_date = start_date
                if end_date and not existing.end_date:
                    existing.end_date = end_date
            else:
                self.additional_education.append(
                    DraftEducationEntry(degree=degree, year=year, start_date=start_date, end_date=end_date)
                )
                existing_additional_degrees.add(degree.lower())

        existing_skills = {s.lower() for s in self.technical_skills}
        for skill in fields.get("technical_skills") or []:
            skill = str(skill).strip()
            if skill and skill.lower() not in existing_skills:
                self.technical_skills.append(skill)
                existing_skills.add(skill.lower())

        existing_roles = {r.lower() for r in self.target_roles}
        for role in fields.get("target_roles") or []:
            role = str(role).strip()
            if role and role.lower() not in existing_roles:
                self.target_roles.append(role)
                existing_roles.add(role.lower())

        # Projects/experience below match an incoming entry against an
        # existing one by identifier (title / organisation / role) and fill
        # in whatever the existing entry was still missing, rather than
        # blindly appending - otherwise a later turn adding a description to
        # an already-mentioned project/job creates a spurious duplicate
        # entry instead of completing the original one.
        existing_projects_by_title = {p.title.lower(): p for p in self.projects}
        for proj in fields.get("projects") or []:
            title = str(proj.get("title") or "").strip()
            if not title:
                continue
            description = proj.get("description")
            technologies = proj.get("technologies") or []
            start_date = proj.get("start_date")
            end_date = proj.get("end_date")
            existing = existing_projects_by_title.get(title.lower())
            if existing:
                if description:
                    existing.description = _merge_description(existing.description, description)
                if start_date and not existing.start_date:
                    existing.start_date = start_date
                if end_date and not existing.end_date:
                    existing.end_date = end_date
                existing_tech = {t.lower() for t in existing.technologies}
                for tech in technologies:
                    if tech.lower() not in existing_tech:
                        existing.technologies.append(tech)
                        existing_tech.add(tech.lower())
            else:
                new_entry = DraftProjectEntry(
                    title=title, description=description, technologies=list(technologies),
                    start_date=start_date, end_date=end_date,
                )
                self.projects.append(new_entry)
                existing_projects_by_title[title.lower()] = new_entry

        existing_experience_by_org = {e.organisation.lower(): e for e in self.experience if e.organisation}
        existing_experience_by_role = {e.role.lower(): e for e in self.experience if e.role}
        for exp in fields.get("experience") or []:
            role = str(exp.get("role") or "").strip() or None
            organisation = str(exp.get("organisation") or "").strip() or None
            description = exp.get("description")
            start_date = exp.get("start_date")
            end_date = exp.get("end_date")
            if not role and not organisation:
                continue
            existing = existing_experience_by_org.get(organisation.lower()) if organisation else None
            if existing is None and role:
                existing = existing_experience_by_role.get(role.lower())
            if existing:
                if role and not existing.role:
                    existing.role = role
                if organisation and not existing.organisation:
                    existing.organisation = organisation
                if description:
                    existing.description = _merge_description(existing.description, description)
                if start_date and not existing.start_date:
                    existing.start_date = start_date
                if end_date and not existing.end_date:
                    existing.end_date = end_date
            else:
                new_entry = DraftExperienceEntry(
                    role=role, organisation=organisation, description=description,
                    start_date=start_date, end_date=end_date,
                )
                self.experience.append(new_entry)
                if organisation:
                    existing_experience_by_org[organisation.lower()] = new_entry
                if role:
                    existing_experience_by_role[role.lower()] = new_entry

        existing_achievements = {a.lower() for a in self.achievements}
        for achievement in fields.get("achievements") or []:
            achievement = str(achievement).strip()
            if achievement and achievement.lower() not in existing_achievements:
                self.achievements.append(achievement)
                existing_achievements.add(achievement.lower())

        # Per-field decline, for the review stage's one-gap-at-a-time asks
        # (see compute_gaps()'s phase="review"): only ever set True by an
        # explicit decline named here - a genuine Python guarantee the field
        # is never re-asked, rather than relying on the model noticing
        # across turns on its own. There is no per-entry "confirmed" flag or
        # read-back to affirm any more: a stated fact is trusted the moment
        # it's captured, and the single whole-profile review stage is the
        # only point the student explicitly confirms anything.
        for decline in fields.get("declined_fields") or []:
            if decline.get("entry_kind") != "project":
                continue
            identifier = str(decline.get("entry_identifier") or "").strip().lower()
            field_name = decline.get("field")
            if not identifier:
                continue
            for p in self.projects:
                if p.title.lower() == identifier:
                    if field_name == "dates":
                        p.dates_declined = True
                    elif field_name == "outcome":
                        p.outcome_declined = True

        # Sticky "addressed" bookkeeping - see the field comments above for why
        # this can't just be derived fresh from list content on every call.
        # All three now only track "has content" - the extraction prompt no
        # longer emits a decline signal for any of them, since an unmentioned
        # work history, project list, or achievements list is simply treated
        # as none - see compute_gaps().
        if self.experience:
            self.work_experience_addressed = True
        if self.projects:
            self.projects_addressed = True
        if self.achievements:
            self.achievements_addressed = True

    def compute_gaps(self, model_gaps: list, phase: str = "intake") -> list:
        """Combines the extraction call's own ambiguity/presence judgements
        (name, degree, year, technical_skills, target_roles, and thin
        existing project/experience/education entries) with section-coverage
        gaps this class tracks deterministically. Returns one ordered list,
        most important first - except in phase="review" (see below), which
        returns at most ONE.

        Work experience, projects, AND achievements are all deliberately NOT
        included here (lowered bar, for now): if any of the three is never
        mentioned, it's just treated as none rather than blocking
        confirmation - work_experience_addressed/projects_addressed/
        achievements_addressed are still tracked (still auto-set True the
        moment the corresponding list has content) so any of the three can
        be reinstated with a one-line change if the bar goes back up, but an
        unmentioned work history, project list, or achievements list no
        longer forces a follow-up. Any of them can still be added later via
        direct profile edit (e.g. the GUI's confirm-stage form).

        PHASES: project_dates/project_outcome are never surfaced during
        phase="intake" - they are deferred entirely to a later phase="review"
        pass (see the GUI's "confirm" stage), because batching them into
        intake's single combined follow-up message both extended intake well
        past its step budget and, when a project's date gap landed in the
        same combined message as an unrelated education date gap, risked the
        two answers being conflated. education_dates is NOT deferred - it
        keeps behaving exactly as before, in both phases. project_results
        (measurable results/metrics) is dropped unconditionally, in every
        phase - it is never asked about, full stop; only ever captured if
        the student volunteers it unprompted (extraction's TASK 1 still
        captures it into an entry's description if freely given - this only
        concerns "gaps" that lead to it being ASKED about).

        NO PER-ENTRY CONFIRMATION READ-BACK: a stated fact - a date, an
        outcome, anything - is trusted and saved the moment it's captured,
        never read back and re-confirmed in isolation ("does that look
        right?"). The only point the student explicitly confirms anything is
        the single, whole-profile review stage once every gap (in both
        phases) is resolved (see SUMMARY_SYSTEM_PROMPT) - that is where a
        correction happens, not after every individual answer. This also
        means once a project's dates_declined/outcome_declined are both
        resolved (given or declined), that project simply has no more gaps -
        there is nothing further to ask about it.

        In phase="review", ONLY project_dates/project_outcome are
        considered, and the returned list has AT MOST ONE ITEM - the single
        highest-priority outstanding project gap - so the review stage's
        caller (see agent.take_turn()) always asks about exactly one project
        field of one entry per turn, never several entries or fields batched
        together. A project's dates_declined/outcome_declined (see merge()'s
        "declined_fields" handling) permanently removes that specific field
        from consideration for that entry, even if the model re-emits a gap
        for it this turn - a genuine Python guarantee, not reliance on the
        model remembering across turns."""
        model_gaps = [g for g in model_gaps if g.get("field") != "project_results"]

        if phase == "intake":
            combined = [g for g in model_gaps if g.get("field") not in ("project_dates", "project_outcome")]
            combined.sort(
                key=lambda g: GAP_PRIORITY_ORDER.index(g["field"]) if g.get("field") in GAP_PRIORITY_ORDER else len(GAP_PRIORITY_ORDER)
            )
            return combined

        # phase == "review"
        declined_titles = {
            "dates": {p.title.lower() for p in self.projects if p.dates_declined},
            "outcome": {p.title.lower() for p in self.projects if p.outcome_declined},
        }

        def _is_declined(g: dict) -> bool:
            key = "dates" if g["field"] == "project_dates" else "outcome"
            return (g.get("entry_identifier") or "").lower() in declined_titles[key]

        combined = [
            g for g in model_gaps if g.get("field") in ("project_dates", "project_outcome") and not _is_declined(g)
        ]
        combined.sort(
            key=lambda g: GAP_PRIORITY_ORDER.index(g["field"]) if g.get("field") in GAP_PRIORITY_ORDER else len(GAP_PRIORITY_ORDER)
        )
        return combined[:1]

    def decline_requirements(self, requirements: List[str]) -> None:
        """Records job-specific requirements the student has confirmed they
        don't have, so JobRequirementAgent never asks about them again and
        CV generation never fabricates them - the same confirmed-facts-only
        rule as everything else on this profile, just for absence rather
        than presence."""
        existing = {r.lower() for r in self.declined_requirements}
        for req in requirements:
            req = str(req).strip()
            if req and req.lower() not in existing:
                self.declined_requirements.append(req)
                existing.add(req.lower())

    def overwrite(self, **fields) -> None:
        """Direct replacement, unlike merge() which only ever adds to existing
        data. This is the write path for a human correcting/completing their
        own profile (e.g. the GUI's confirm-stage form) - the user is the
        ground truth here, not an extraction pipeline, so they can replace or
        clear a field outright. Silently ignores unknown keys. Marks the
        optional sections addressed regardless of whether they end up empty -
        a human who has directly reviewed the form has addressed every
        section by definition, whether or not they chose to fill it in."""
        for key, value in fields.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.work_experience_addressed = True
        self.projects_addressed = True
        self.achievements_addressed = True

    def to_profile(self, document_id: str) -> Profile:
        return Profile(
            document_id=document_id,
            profile_type="user_submitted",
            dataset_scope="live_intake",
            contact=ContactDetails(
                name=self.name or "Unknown",
                email=self.email,
                phone=self.phone,
                github=self.github,
                linkedin=self.linkedin,
            ),
            education=Education(
                degree=self.degree or "Unspecified",
                institution=self.institution or "Unspecified",
                year=self.year or "Unspecified",
                expected_graduation=self.education_end_date,
                start_date=self.education_start_date,
            ),
            skills=Skills(technical_skills=self.technical_skills),
            experience=Experience(
                entries=[
                    ExperienceEntry(
                        role=e.role or "Not specified",
                        organisation=e.organisation or "",
                        type="",
                        description=e.description or "",
                        start_date=e.start_date,
                        end_date=e.end_date,
                    )
                    for e in self.experience
                ]
            ),
            projects=Projects(
                entries=[
                    ProjectEntry(
                        title=p.title,
                        context="User-submitted introduction",
                        description=p.description or "",
                        technologies=p.technologies,
                        start_date=p.start_date,
                        end_date=p.end_date,
                    )
                    for p in self.projects
                ]
            ),
            achievements=Achievements(activities=self.achievements),
            job_goal=JobGoal(target_roles=self.target_roles, summary=self.summary),
            additional_education=[
                AdditionalEducationEntry(degree=e.degree, year=e.year, start_date=e.start_date, end_date=e.end_date)
                for e in self.additional_education
            ],
        )


def describe_new_facts(before: dict, after: dict) -> List[str]:
    """Deterministically diffs two draft-profile dicts (as produced by
    asdict(DraftProfile), i.e. ProfileTool observation "draft" values taken
    before and after one merge()) and describes what's genuinely new in
    `after`, as a list of plain-English clauses.

    This exists so the student is told about EVERY field a single message
    updated, not just whichever one an LLM happens to mention first when
    asked to summarize itself - the diff is computed here in Python against
    the actual merged data, not by asking the model to recall its own
    output, so it can't under-report or hallucinate a change that didn't
    happen."""
    clauses: List[str] = []

    if after.get("name") and after.get("name") != before.get("name"):
        clauses.append(f"recorded your name as {after['name']}")

    if after.get("degree") and after.get("degree") != before.get("degree"):
        clauses.append(f"recorded your degree as {after['degree']}")

    if after.get("institution") and after.get("institution") != before.get("institution"):
        clauses.append(f"recorded your institution as {after['institution']}")

    if after.get("year") and after.get("year") != before.get("year"):
        clauses.append(f"recorded your year of study as {after['year']}")

    if after.get("education_start_date") and after.get("education_start_date") != before.get("education_start_date"):
        clauses.append(f"recorded your degree's start date as {after['education_start_date']}")

    if after.get("education_end_date") and after.get("education_end_date") != before.get("education_end_date"):
        clauses.append(f"recorded your degree's (expected) end date as {after['education_end_date']}")

    before_extra_degrees = {e["degree"].lower() for e in before.get("additional_education", [])}
    new_extra_degrees = [
        e["degree"] for e in after.get("additional_education", []) if e["degree"].lower() not in before_extra_degrees
    ]
    if new_extra_degrees:
        clauses.append(f"added {', '.join(new_extra_degrees)} to your education, alongside what was already there")

    before_skills = {s.lower() for s in before.get("technical_skills", [])}
    new_skills = [s for s in after.get("technical_skills", []) if s.lower() not in before_skills]
    if new_skills:
        clauses.append(f"added {', '.join(new_skills)} to your skills")

    before_project_titles = {p["title"].lower() for p in before.get("projects", [])}
    new_projects = [p["title"] for p in after.get("projects", []) if p["title"].lower() not in before_project_titles]
    if new_projects:
        clauses.append(f"added {', '.join(repr(t) for t in new_projects)} to your projects")

    def _exp_key(e: dict) -> tuple:
        return (e.get("role") or "").lower(), (e.get("organisation") or "").lower()

    before_exp_keys = {_exp_key(e) for e in before.get("experience", [])}
    new_exp = [e for e in after.get("experience", []) if _exp_key(e) not in before_exp_keys]
    if new_exp:
        labels = [
            e["role"] + (f" at {e['organisation']}" if e.get("organisation") else "") for e in new_exp if e.get("role")
        ]
        if labels:
            clauses.append(f"added {', '.join(labels)} to your experience")

    before_roles = {r.lower() for r in before.get("target_roles", [])}
    new_roles = [r for r in after.get("target_roles", []) if r.lower() not in before_roles]
    if new_roles:
        clauses.append(f"added {', '.join(new_roles)} to your target roles")

    before_achievements = {a.lower() for a in before.get("achievements", [])}
    new_achievements = [a for a in after.get("achievements", []) if a.lower() not in before_achievements]
    if new_achievements:
        clauses.append(f"added {len(new_achievements)} new achievement(s)/activity(ies)")

    return clauses
