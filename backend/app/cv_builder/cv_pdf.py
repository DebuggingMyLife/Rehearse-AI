from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Indenter, Paragraph, SimpleDocTemplate, Table, TableStyle

from cv_style_spec import (
    ACCENT_COLOR,
    BODY_COLOR,
    BODY_SIZE,
    BULLET_SIZE,
    ENTRY_INDENT_MM,
    LEADING_FACTOR,
    NAME_SIZE,
    SECTION_HEADER_SIZE,
    TAGLINE_SIZE,
    TECH_LINE_SIZE,
    format_date_range,
    register_fonts,
)
from profile_model import Profile


def _clean(text) -> str:
    """Reportlab's Paragraph parses text as mini-XML, and a font may lack a
    glyph for some Unicode punctuation the model tends to generate (notably
    U+2011 NON-BREAKING HYPHEN, which can render as a solid box). Escape XML
    specials and swap in safe equivalents before any text reaches a
    Paragraph."""
    text = escape(str(text))
    text = text.replace("‑", "-").replace("‐", "-")
    return text


def _build_styles():
    """Every size/color/spacing value here comes from cv_style_spec.py, the
    hardcoded formatting spec applied to every exported CV - see that
    module for the rationale behind each constant. This function owns only
    the reportlab-specific plumbing (ParagraphStyle objects); it defines no
    style values of its own."""
    fonts = register_fonts()
    styles = {}

    def add(name, **kwargs):
        styles[name] = ParagraphStyle(name=name, **kwargs)

    add(
        "CVName",
        fontName=fonts.bold,
        fontSize=NAME_SIZE,
        leading=NAME_SIZE * LEADING_FACTOR,
        textColor=colors.HexColor(ACCENT_COLOR),
        spaceAfter=2,
    )
    add(
        "CVTagline",
        fontName=fonts.family,
        fontSize=TAGLINE_SIZE,
        leading=TAGLINE_SIZE * LEADING_FACTOR,
        textColor=colors.HexColor(BODY_COLOR),
        spaceAfter=6,
    )
    add(
        "CVSectionHeader",
        fontName=fonts.bold,
        fontSize=SECTION_HEADER_SIZE,
        leading=SECTION_HEADER_SIZE * LEADING_FACTOR,
        textColor=colors.HexColor(ACCENT_COLOR),
        spaceBefore=14,
        spaceAfter=4,
    )
    add(
        "CVBody",
        fontName=fonts.family,
        fontSize=BODY_SIZE,
        leading=BODY_SIZE * LEADING_FACTOR,
        textColor=colors.HexColor(BODY_COLOR),
        spaceAfter=4,
    )
    add(
        "CVBullet",
        fontName=fonts.family,
        fontSize=BULLET_SIZE,
        leading=BULLET_SIZE * LEADING_FACTOR,
        textColor=colors.HexColor(BODY_COLOR),
        leftIndent=12,
        bulletIndent=0,
        spaceAfter=2,
    )
    add(
        "CVEntryTitle",
        fontName=fonts.bold,
        fontSize=BODY_SIZE,
        leading=BODY_SIZE * LEADING_FACTOR,
        textColor=colors.HexColor(BODY_COLOR),
    )
    add(
        "CVDateRange",
        fontName=fonts.family,
        fontSize=BODY_SIZE,
        leading=BODY_SIZE * LEADING_FACTOR,
        textColor=colors.HexColor(BODY_COLOR),
        alignment=2,  # TA_RIGHT
    )
    add(
        "CVTechLine",
        fontName=fonts.italic,
        fontSize=TECH_LINE_SIZE,
        leading=TECH_LINE_SIZE * LEADING_FACTOR,
        textColor=colors.HexColor(BODY_COLOR),
        spaceAfter=3,
    )
    return styles


def _bullets(description: str, styles: dict) -> list:
    """A description may hold multiple distinct achievements as separate
    "\\n"-joined lines (see agent.EXTRACTION_SYSTEM_PROMPT's ACHIEVEMENTS
    rule and cv_generator's matching TASK 3 note) - each line becomes its
    OWN bullet Paragraph, not one Paragraph with an embedded line break
    (which reportlab would render as a single run-on line anyway)."""
    lines = [line.strip() for line in description.split("\n") if line.strip()]
    return [Paragraph(_clean(f"• {line}"), styles["CVBullet"]) for line in lines]


def _entry_header(title: str, date_range: str, styles: dict, content_width: float):
    """Left-aligned title/role/institution, right-aligned date range on the
    same line - spec's "Entry layout" rule. A borderless two-column Table
    is the standard reportlab way to put independently-aligned text on one
    line; falls back to a single Paragraph when there's no date to show
    (most entries today, since dates are only ever recorded when a student
    explicitly states a timeframe - see agent.EXTRACTION_SYSTEM_PROMPT's
    DATES rule - never fabricated to fill this layout)."""
    if not date_range:
        return Paragraph(_clean(title), styles["CVEntryTitle"])
    table = Table(
        [[Paragraph(_clean(title), styles["CVEntryTitle"]), Paragraph(_clean(date_range), styles["CVDateRange"])]],
        colWidths=[content_width * 0.68, content_width * 0.32],
    )
    table.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def render_cv_pdf(cv: dict, profile: Profile, output_path: Path) -> None:
    styles = _build_styles()
    left_margin = right_margin = 20 * mm
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        leftMargin=left_margin,
        rightMargin=right_margin,
        title=f"{profile.contact.name} - CV",
    )
    content_width = A4[0] - left_margin - right_margin
    # Education/Experience/Projects entry lines are indented slightly right
    # of their section header (see cv_style_spec.ENTRY_INDENT_MM) - the
    # frame narrows by this amount for those sections, so _entry_header()'s
    # fixed-width Table needs the narrower width too, or it would overflow
    # the indented frame.
    entry_indent = ENTRY_INDENT_MM * mm
    entry_content_width = content_width - entry_indent
    story = []

    # Header: name as the single largest text element, one pipe-separated
    # contact line below it (links, phone, email - no "location" field
    # exists in this project's profile data, so it's simply omitted rather
    # than shown as a placeholder).
    story.append(Paragraph(_clean(profile.contact.name), styles["CVName"]))

    contact_bits = [b for b in [profile.contact.github, profile.contact.linkedin, profile.contact.phone, profile.contact.email] if b]
    if contact_bits:
        story.append(Paragraph(_clean(" | ".join(contact_bits)), styles["CVTagline"]))
    story.append(Paragraph(_clean(f"Target role: {cv['target_job_title']}"), styles["CVTagline"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(BODY_COLOR), spaceAfter=2))

    is_first_section = True

    def section(title: str, flowables: list, indent: bool = False) -> None:
        nonlocal is_first_section
        if not is_first_section:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor(BODY_COLOR), spaceBefore=10, spaceAfter=0))
        is_first_section = False
        story.append(Paragraph(_clean(title.upper()), styles["CVSectionHeader"]))
        if indent:
            story.append(Indenter(left=entry_indent))
        story.extend(flowables)
        if indent:
            story.append(Indenter(left=-entry_indent))

    section("Summary", [Paragraph(_clean(cv["summary"]), styles["CVBody"])])

    # Same left-title/right-date entry layout as Experience/Projects below -
    # degree/institution left-aligned, completion date (or a full range if a
    # start date was also captured) right-aligned on the same line. Each
    # additional qualification (e.g. a Master's alongside the primary
    # degree) gets its own such line rather than being folded into the same
    # sentence as the primary one - see cv_generator's "additional_education"
    # output key for why this is a separate field.
    primary_date_range = format_date_range(cv.get("education_start_date"), cv.get("education_end_date"))
    education_flowables = [_entry_header(cv["education"], primary_date_range, styles, entry_content_width)]
    for entry in cv.get("additional_education") or []:
        entry_date_range = format_date_range(entry.get("start_date"), entry.get("end_date"))
        education_flowables.append(_entry_header(entry["text"], entry_date_range, styles, entry_content_width))
    section("Education", education_flowables, indent=True)

    # Experience and Projects are both fixed sections now, always in this
    # order right after Education - neither is part of a dynamic
    # per-job section_order any more. Only Skills' own internal order (which
    # skill is listed first, and which category leads) still varies per job.
    if cv["experience"]:
        flowables = []
        for e in cv["experience"]:
            title = f"{e['role']} — {e['organisation']}" if e.get("organisation") else e["role"]
            date_range = format_date_range(e.get("start_date"), e.get("end_date"))
            flowables.append(_entry_header(title, date_range, styles, entry_content_width))
            flowables.extend(_bullets(e["description"], styles))
        section("Experience", flowables, indent=True)

    if cv["projects"]:
        flowables = []
        for p in cv["projects"]:
            date_range = format_date_range(p.get("start_date"), p.get("end_date"))
            flowables.append(_entry_header(p["title"], date_range, styles, entry_content_width))
            if p.get("technologies"):
                flowables.append(
                    Paragraph(_clean(f"Technologies: {', '.join(p['technologies'])}"), styles["CVTechLine"])
                )
            flowables.extend(_bullets(p["description"], styles))
        section("Projects", flowables, indent=True)

    if cv["skills"]:
        # Grouped by category with labels, not a flat list - see
        # cv_generator's "skills_by_category" output key. Falls back to a
        # single "Skills" bucket if that key is ever absent (e.g. a CV
        # generated before this feature existed), so nothing regresses.
        by_category = cv.get("skills_by_category") or {"Skills": cv["skills"]}
        skill_flowables = []
        for category, skills in by_category.items():
            if not skills:
                continue
            # _clean() escapes XML specials, so it must run on the category
            # name and skill list SEPARATELY - running it on the whole
            # string including the <b> tags would escape those too and
            # print them as literal text instead of rendering bold.
            skill_flowables.append(
                Paragraph(f"<b>{_clean(category)}:</b> {_clean(', '.join(skills))}", styles["CVBody"])
            )
        section("Skills", skill_flowables)

    doc.build(story)
