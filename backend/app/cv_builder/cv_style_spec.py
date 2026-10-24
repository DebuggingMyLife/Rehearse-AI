"""Feature 1 - standalone CV formatting spec, hardcoded as constants/config.

This module is the single source of truth for how every exported CV PDF
looks. It is applied automatically by cv_pdf.py to EVERY profile's export -
there is no user-uploaded template file anywhere in this pipeline, and
there never should be: if a resume-upload feature is ever added to this
project, an uploaded PDF/DOCX may only be used to EXTRACT FACTS into a
profile (education, experience, skills, etc. - the same extraction path
agent.py already uses for a typed introduction), never as a source of
styling. That rule has nothing to enforce yet (no upload feature exists in
this codebase), but is recorded here deliberately so it is cited as a
design decision, not retrofitted after the fact once uploads exist.

Every value below is a deliberate, literal choice - documented inline so
it can be cited directly in the assessment report.
"""
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from dateutil import parser as _date_parser

logger = logging.getLogger(__name__)

# --- Font -------------------------------------------------------------
# Preferred: true Times New Roman, registered from the actual TTF files if
# they can be found on this machine (Windows ships them at
# C:\Windows\Fonts\times*.ttf - reportlab has no bundled equivalent, since
# Times New Roman is a Microsoft-licensed font it cannot embed by default).
# Fallback: reportlab's built-in base-14 "Times-Roman" family (metric-
# compatible with Times New Roman but not the same font file) - used
# automatically, with the substitution logged via the `logger` above AND
# written into 03_Evidence/01_Prompts/prompt_record.md by whichever caller
# first triggers the fallback, per this spec's explicit requirement to
# record the substitution rather than silently swap fonts.
PREFERRED_FONT_FAMILY = "Times New Roman"
FALLBACK_FONT_FAMILY = "Times-Roman"  # reportlab's base-14 standard name

# Candidate TTF locations for the preferred font, checked in order the
# first time cv_pdf.py renders a PDF. Windows-only (see above) - a
# non-Windows deployment falls back to FALLBACK_FONT_FAMILY every time,
# which is expected and is exactly the scenario this constant documents.
_WINDOWS_FONTS_DIR = Path(r"C:\Windows\Fonts")
TIMES_NEW_ROMAN_TTF_PATHS = {
    "regular": _WINDOWS_FONTS_DIR / "times.ttf",
    "bold": _WINDOWS_FONTS_DIR / "timesbd.ttf",
    "italic": _WINDOWS_FONTS_DIR / "timesi.ttf",
    "bold_italic": _WINDOWS_FONTS_DIR / "timesbi.ttf",
}

# --- Sizes (points) -----------------------------------------------------
NAME_SIZE = 19  # spec range: 18-20pt, bold
SECTION_HEADER_SIZE = 12  # bold, uppercase
BODY_SIZE = 11
BULLET_SIZE = 11
TAGLINE_SIZE = 10.5  # contact line + target-role line; same weight/color as body, slightly smaller to read as metadata rather than a CV claim
TECH_LINE_SIZE = 9.5  # "Technologies: ..." line under a project

# --- Layout: entry indent --------------------------------------------------
# Education/Experience/Projects entry lines (title left, date right - see
# cv_pdf._entry_header()) are indented slightly right of their own section
# header, rather than sharing its exact left edge - a short title (e.g. a
# single degree or project name) otherwise reads as pinned flush against the
# page margin with a large empty gap before the date, which can look
# unbalanced/too-far-left. Summary and Skills are unaffected - they have no
# per-entry title/date line to distinguish from their header.
ENTRY_INDENT_MM = 4

# --- Line spacing --------------------------------------------------------
# Spec: single to 1.15. Using 1.15 uniformly (the upper end of the allowed
# range) for readability; LEADING_FACTOR * font size = a style's `leading`.
LEADING_FACTOR = 1.15

# --- Color ----------------------------------------------------------------
# Spec: body text pure black; ONE accent color, used ONLY for the name and
# section headers, nowhere else - kept print/grayscale-safe.
BODY_COLOR = "#000000"
ACCENT_COLOR = "#1A2B4C"  # dark navy

# --- Section order ---------------------------------------------------------
# Fixed regardless of target job (see cv_generator.py's own TASK 1 note -
# only the ORDER OF ITEMS WITHIN a section varies by job relevance, never
# which section leads). Adjustable here in one place if that policy ever
# needs to change.
SECTION_ORDER = ("Education", "Experience", "Projects", "Skills")

# --- Skills: grouped by category, not a flat list --------------------------
# The category LABELS a generated CV may use - cv_generator.py's system
# prompt is given this exact list and instructed to sort the candidate's
# own confirmed skills into whichever of these genuinely fit (never
# inventing a skill, never splitting one skill across categories); "Other"
# is the required catch-all so a skill that doesn't cleanly fit anywhere
# else is never dropped or forced into the wrong bucket.
SKILL_CATEGORIES = (
    "Programming Languages",
    "Frameworks & Libraries",
    "Tools & Platforms",
    "Languages",
    "Other",
)

# --- Date format -----------------------------------------------------------
# Pattern: "Mon. YYYY - Mon. YYYY", or "... - Present" for an entry the
# student described as ongoing. Dates are NEVER fabricated: this whole
# project's extraction only ever records start_date/end_date on an
# experience/project entry when the student explicitly stated a timeframe
# (see agent.EXTRACTION_SYSTEM_PROMPT) - an entry with no stated dates
# simply renders no date range at all, rather than guessing one.
_ONGOING_WORDS = {"present", "ongoing", "current", "now"}


def _format_single_date(raw: str) -> str:
    """Best-effort normalization of one loose date string into "Mon. YYYY".
    Never raises and never invents a year that wasn't in the text - a
    bare "2023" stays "2023" (turning it into "Jan. 2023" would fabricate
    a month that was never stated), and anything dateutil can't parse is
    shown back verbatim rather than dropped."""
    raw = raw.strip()
    if re.fullmatch(r"\d{4}", raw):
        return raw
    try:
        parsed = _date_parser.parse(raw, default=datetime(1904, 1, 1))
    except (ValueError, OverflowError):
        return raw
    if parsed.year == 1904 and "1904" not in raw:
        # dateutil filled in the sentinel year because none was stated -
        # showing "Jan. 1904" would fabricate a year, so fall back to the
        # raw text instead.
        return raw
    return parsed.strftime("%b. %Y").replace(".", ".")  # e.g. "Jun. 2023"


def format_date_range(start: Optional[str], end: Optional[str]) -> str:
    """Renders this spec's date pattern from raw, ungrounded-if-fabricated
    start/end strings. Returns "" (never a placeholder like "Not specified")
    when neither is set - see cv_pdf.py's professional-placeholder rule."""
    start = (start or "").strip() or None
    end = (end or "").strip() or None
    if not start and not end:
        return ""
    if start and end:
        end_label = "Present" if end.lower() in _ONGOING_WORDS else _format_single_date(end)
        return f"{_format_single_date(start)} \u2013 {end_label}"
    return _format_single_date(start or end)


@dataclass
class FontRegistration:
    family: str  # the name to pass as fontName to a reportlab style
    bold: str
    italic: str
    bold_italic: str
    used_fallback: bool


def register_fonts() -> FontRegistration:
    """Attempts to register the true Times New Roman TTFs with reportlab;
    falls back to the base-14 Times-Roman family (metric-compatible, not
    the same font file) if the TTFs aren't found - e.g. on a non-Windows
    deployment. Logs the fallback per this spec's explicit requirement to
    record any font substitution rather than silently swap fonts."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    paths = TIMES_NEW_ROMAN_TTF_PATHS
    if all(p.exists() for p in paths.values()):
        try:
            pdfmetrics.registerFont(TTFont("TimesNewRoman", str(paths["regular"])))
            pdfmetrics.registerFont(TTFont("TimesNewRoman-Bold", str(paths["bold"])))
            pdfmetrics.registerFont(TTFont("TimesNewRoman-Italic", str(paths["italic"])))
            pdfmetrics.registerFont(TTFont("TimesNewRoman-BoldItalic", str(paths["bold_italic"])))
            return FontRegistration(
                family="TimesNewRoman",
                bold="TimesNewRoman-Bold",
                italic="TimesNewRoman-Italic",
                bold_italic="TimesNewRoman-BoldItalic",
                used_fallback=False,
            )
        except Exception:
            logger.warning("Found Times New Roman TTFs but failed to register them - falling back to Times-Roman.")

    logger.warning(
        "Times New Roman TTFs not found at %s - falling back to reportlab's built-in "
        "Times-Roman family (metric-compatible base-14 font, not the same file).",
        _WINDOWS_FONTS_DIR,
    )
    return FontRegistration(
        family="Times-Roman",
        bold="Times-Bold",
        italic="Times-Italic",
        bold_italic="Times-BoldItalic",
        used_fallback=True,
    )
