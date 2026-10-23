"""Extract plain text from a CV (PDF or DOCX). Never log the extracted text."""

import io
import re
from pathlib import Path

import pdfplumber
from docx import Document

SUPPORTED_SUFFIXES = {".pdf", ".docx"}
MIN_CV_CHARS = 50


class CVParseError(ValueError):
    pass


def parse_cv(data: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise CVParseError("Unsupported file type. Upload a PDF or DOCX.")
    try:
        text = _parse_pdf(data) if suffix == ".pdf" else _parse_docx(data)
    except CVParseError:
        raise
    except Exception as exc:
        raise CVParseError(f"Could not read the file ({type(exc).__name__}). Is it a valid {suffix}?") from exc

    text = normalise(text)
    if len(text) < MIN_CV_CHARS:
        hint = (" It may be a scanned image; OCR isn't supported, so export a text-based PDF or DOCX."
                if suffix == ".pdf" else "")
        raise CVParseError(f"Almost no text was found in the CV.{hint}")
    return text


def _parse_pdf(data: bytes) -> str:
    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text(x_tolerance=1.5, y_tolerance=3) or "")
    return "\n\n".join(pages)


def _parse_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    blocks: list[str] = []
    # Walk the body in document order so tables (common in CV templates) stay in place.
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            blocks.append("".join(t.text or "" for t in child.iter() if t.tag.endswith("}t")))
        elif tag == "tbl":
            for row in child.iter():
                if row.tag.endswith("}tr"):
                    cells = []
                    for cell in row.iterchildren():
                        if cell.tag.endswith("}tc"):
                            cells.append(" ".join(
                                "".join(t.text or "" for t in p.iter() if t.tag.endswith("}t"))
                                for p in cell.iter() if p.tag.endswith("}p")
                            ).strip())
                    blocks.append(" | ".join(c for c in cells if c))
    return "\n".join(blocks)


def normalise(text: str) -> str:
    text = text.replace(" ", " ").replace("​", "")
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    # pdfplumber emits "(cid:N)" for glyphs without a unicode mapping. In CVs these are
    # almost always bullets or icons.
    text = re.sub(r"^\s*\(cid:\d+\)\s*", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"\(cid:\d+\)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
