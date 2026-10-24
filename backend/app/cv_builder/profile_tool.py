from dataclasses import asdict
from typing import List

from .profile_model import DraftProfile, Profile, describe_new_facts


class ProfileTool:
    """The agent's one tool for reading/writing profile state.

    Every call returns an Observation: the current draft profile (as a
    plain dict), the list of required fields still missing by simple
    presence (missing_fields - kept for backward compatibility/structural
    bookkeeping), and gaps - DraftProfile.compute_gaps()'s combination of the
    extraction call's own ambiguity/presence judgement with the
    deterministically-tracked section-coverage state (work experience /
    projects / achievements). gaps is what actually drives the agent's
    follow-up decisions.
    """

    def __init__(self):
        self._draft = DraftProfile()
        self._latest_gaps: List[dict] = []

    def _observation(self) -> dict:
        return {
            "draft": asdict(self._draft),
            "missing_fields": self._draft.missing_fields(),
            "gaps": self._latest_gaps,
        }

    def read_profile(self) -> dict:
        return self._observation()

    def update_profile(self, extracted_fields: dict, phase: str = "intake") -> dict:
        before = asdict(self._draft)
        self._draft.merge(extracted_fields)
        self._latest_gaps = self._draft.compute_gaps(extracted_fields.get("gaps", []), phase=phase)
        observation = self._observation()
        # Computed from the actual before/after draft dicts, not from the
        # extraction call's own self-report - see describe_new_facts() for
        # why: it guarantees every field a message touched gets surfaced to
        # the student, not just whichever one an LLM might mention first.
        observation["new_facts"] = describe_new_facts(before, observation["draft"])
        return observation

    def overwrite_profile(self, fields: dict) -> dict:
        """Direct-replace write path for a human correcting/completing their
        own profile (e.g. a GUI edit form) - unlike update_profile()/merge(),
        which only ever adds to existing extraction results. Clears any
        outstanding gaps from prior auto-extraction: once a human has
        directly edited the profile, stale LLM-judged gaps about the
        pre-edit content no longer apply."""
        self._draft.overwrite(**fields)
        self._latest_gaps = []
        return self._observation()

    def apply_job_requirement_facts(self, fields: dict, declined: List[str]) -> dict:
        """Write path for JobRequirementAgent.resolve(): newly confirmed
        skills/achievements are merged in exactly like a normal extraction
        turn (merge()'s existing dedup/append logic), and everything the
        student didn't confirm for this job is recorded as declined via
        decline_requirements() - never fabricated, never re-asked about
        again. Does not touch _latest_gaps; this is a job-specific check,
        separate from the general profile-completeness gaps."""
        self._draft.merge(fields)
        self._draft.decline_requirements(declined)
        return self._observation()

    def to_profile(self, document_id: str) -> Profile:
        return self._draft.to_profile(document_id)
