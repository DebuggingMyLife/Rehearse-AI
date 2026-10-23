"""Session export to PDF with ReportLab (pure Python, no external services or system libs)."""

import io
import os
from datetime import datetime
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from ..models import InterviewSession
from ..schemas.api import as_utc
from .summary import best_attempt, scored_attempts, session_stats

# Bitstream Vera ships with ReportLab and covers more characters (curly quotes, bullets,
# accented names) than the built-in Helvetica.
_FONT_DIR = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
pdfmetrics.registerFont(TTFont("Vera", os.path.join(_FONT_DIR, "Vera.ttf")))
pdfmetrics.registerFont(TTFont("Vera-Bold", os.path.join(_FONT_DIR, "VeraBd.ttf")))
pdfmetrics.registerFont(TTFont("Vera-Italic", os.path.join(_FONT_DIR, "VeraIt.ttf")))
pdfmetrics.registerFont(TTFont("Vera-BoldItalic", os.path.join(_FONT_DIR, "VeraBI.ttf")))
pdfmetrics.registerFontFamily("Vera", normal="Vera", bold="Vera-Bold", italic="Vera-Italic",
                              boldItalic="Vera-BoldItalic")

# Characters Vera lacks, mapped to close equivalents.
_REPLACE = {"→": "->", "←": "<-", "✓": "+", "✗": "x", "≥": ">=", "≤": "<="}

ACCENT = colors.HexColor("#2f5bd3")
MUTED = colors.HexColor("#6b6b66")
SCORE_LABEL = {1: "Weak", 2: "Needs work", 3: "Fair", 4: "Good", 5: "Excellent"}


def _t(text) -> str:
    s = str(text or "")
    for a, b in _REPLACE.items():
        s = s.replace(a, b)
    return escape(s)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["BodyText"], fontName="Vera", fontSize=9.5, leading=13.5,
                          alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("title", parent=body, fontName="Vera-Bold", fontSize=20, leading=24, spaceAfter=4),
        "h1": ParagraphStyle("h1", parent=body, fontName="Vera-Bold", fontSize=14, leading=18, spaceBefore=10,
                             spaceAfter=6, textColor=ACCENT),
        "h2": ParagraphStyle("h2", parent=body, fontName="Vera-Bold", fontSize=11.5, leading=15, spaceBefore=8,
                             spaceAfter=4),
        "h3": ParagraphStyle("h3", parent=body, fontName="Vera-Bold", fontSize=9.5, leading=13, spaceBefore=6,
                             spaceAfter=2),
        "body": body,
        "muted": ParagraphStyle("muted", parent=body, textColor=MUTED, fontSize=8.5, leading=12),
        "quote": ParagraphStyle("quote", parent=body, fontName="Vera-Italic", textColor=MUTED, leftIndent=8),
        "example": ParagraphStyle("example", parent=body, leftIndent=8, borderPadding=6, backColor="#f1f1ee"),
    }


def _bullets(items: list[str], st, numbered: bool = False) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(i, st["body"]), leftIndent=12) for i in items],
        bulletType="1" if numbered else "bullet", start="1" if numbered else None,
        bulletFontName="Vera", bulletFontSize=8, leftIndent=12,
    )


def build_session_pdf(session: InterviewSession) -> bytes:
    st = _styles()
    stats = session_stats(session)
    summary = session.summary_json or {}
    story: list = []

    story.append(Paragraph("RehearseAI: mock interview report", st["title"]))
    created = as_utc(session.created_at).astimezone()
    story.append(Paragraph(
        f"Session of {created:%d %B %Y} · CV: {_t(session.cv_filename)} · exported {datetime.now():%d %B %Y %H:%M}",
        st["muted"]))
    role = session.job_description.strip().splitlines()[0][:150] if session.job_description.strip() else ""
    if role:
        story.append(Paragraph(f"Role: {_t(role)}", st["body"]))
    story.append(Spacer(1, 4 * mm))

    # Overview table
    d = stats["delivery"]
    rows = [
        ["Questions answered", f"{stats['questions_answered']} of {stats['questions_total']}"],
        ["Average best score", f"{stats['avg_best_score']}/5" if stats["avg_best_score"] is not None else "-"],
        ["Scored attempts", str(stats["attempts_scored"])],
        ["Average pace", f"{d['avg_wpm']} wpm" if d["avg_wpm"] else "-"],
        ["Filler words", f"{d['fillers_per_min']} per minute" if d["fillers_per_min"] is not None else "-"],
        ["Pauses over 2 s", f"{d['avg_long_pauses']} per answer" if d["avg_long_pauses"] is not None else "-"],
    ]
    table = Table([[Paragraph(_t(a), st["muted"]), Paragraph(_t(b), st["body"])] for a, b in rows],
                  colWidths=[45 * mm, 120 * mm])
    table.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#ddddd8")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(table)

    if summary:
        story.append(Paragraph("Session summary", st["h1"]))
        story.append(Paragraph(_t(summary.get("overall", "")), st["body"]))
        if summary.get("top_priorities"):
            story.append(Paragraph("Most important things to work on", st["h2"]))
            story.append(_bullets([
                f"<b>{_t(p['title'])}</b>: {_t(p['why'])} <i>Practise:</i> {_t(p['how_to_practise'])}"
                for p in summary["top_priorities"]], st, numbered=True))
        if summary.get("recurring_strengths"):
            story.append(Paragraph("Recurring strengths", st["h2"]))
            story.append(_bullets([_t(s) for s in summary["recurring_strengths"]], st))
        if summary.get("recurring_weaknesses"):
            story.append(Paragraph("Recurring weaknesses", st["h2"]))
            story.append(_bullets([_t(s) for s in summary["recurring_weaknesses"]], st))

    story.append(Paragraph("Questions and best attempts", st["h1"]))
    for q in session.questions:
        best = best_attempt(q)
        header = [Paragraph(f"Q{q.position}. {_t(q.text)}", st["h2"]),
                  Paragraph(f"{_t(q.type.value.replace('_', '-'))} · {_t(q.difficulty.value)}", st["muted"])]
        if best is None:
            story.append(KeepTogether(header + [Paragraph("Not answered.", st["muted"])]))
            continue
        scores = " -> ".join(str(a.score) for a in scored_attempts(q))
        header.append(Paragraph(
            f"<b>Best score {best.score}/5 ({SCORE_LABEL[best.score]})</b> · attempt {best.attempt_number}"
            + (f" · scores over attempts: {scores}" if len(scored_attempts(q)) > 1 else "")
            + (f" · {round(best.wpm)} wpm, {best.filler_count} fillers, {best.long_pause_count} long pauses"
               if best.wpm is not None else ""), st["body"]))
        story.append(KeepTogether(header))

        fb = best.feedback_json or {}
        cov = (best.scoring_json or {}).get("rubric_coverage", [])
        if cov:
            story.append(Paragraph("Rubric coverage", st["h3"]))
            story.append(_bullets([("[covered] " if c["covered"] else "[missing] ") + _t(c["point"]) for c in cov], st))
        if fb.get("what_you_did_well"):
            story.append(Paragraph("What you did well", st["h3"]))
            story.append(_bullets([
                _t(p["point"]) + (f' <i>"{_t(p["quote"])}"</i>' if p.get("quote") and p.get("quote_verified", True)
                                   else "") for p in fb["what_you_did_well"]], st))
        if fb.get("what_could_be_improved"):
            story.append(Paragraph("What could be improved", st["h3"]))
            story.append(_bullets([_t(p) for p in fb["what_could_be_improved"]], st, numbered=True))
        if fb.get("missed_opportunities"):
            story.append(Paragraph("Missed opportunities from your CV", st["h3"]))
            story.append(_bullets([_t(p) for p in fb["missed_opportunities"]], st))
        star = fb.get("structure_feedback")
        if star:
            story.append(Paragraph("STAR structure", st["h3"]))
            story.append(_bullets([f"<b>{k.title()}</b>: {_t(star[k]['comment'] if isinstance(star[k], dict) else star[k])}"
                                   for k in ("situation", "task", "action", "result")], st))
            story.append(Paragraph(_t(star.get("overall", "")), st["body"]))
        if fb.get("example_stronger_answer"):
            story.append(Paragraph("Example of a stronger answer", st["h3"]))
            story.append(Paragraph(_t(fb["example_stronger_answer"]), st["example"]))
        if best.transcript:
            story.append(Paragraph("Your answer (transcript)", st["h3"]))
            story.append(Paragraph(_t(best.transcript), st["quote"]))
        story.append(Spacer(1, 3 * mm))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Vera", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, "Generated locally by RehearseAI. Feedback is AI-generated; use your judgement.")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title="RehearseAI mock interview report", author="RehearseAI")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
