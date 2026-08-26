from __future__ import annotations

import io
import re
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


GREEN = colors.HexColor("#087F5B")
INK = colors.HexColor("#10241C")
MUTED = colors.HexColor("#607068")
LINE = colors.HexColor("#DCE7E1")
SOFT = colors.HexColor("#E8F5EF")


def _clean_inline(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 — \2", value)
    value = value.replace("**", "").replace("`", "")
    return escape(value.strip())


def _page(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 18 * mm, A4[0] - 18 * mm, 18 * mm)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(GREEN)
    canvas.drawString(18 * mm, 11 * mm, "THE COMPANY · VERSION 2.0")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(A4[0] - 18 * mm, 11 * mm, f"{document.page}")
    canvas.restoreState()


def markdown_to_pdf(markdown_text: str, *, document_title: str) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=24 * mm,
        title=document_title,
        author="The Research Desk",
    )
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=27,
            textColor=INK,
            spaceAfter=11,
        ),
        "h2": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=GREEN,
            spaceBefore=13,
            spaceAfter=7,
        ),
        "h3": ParagraphStyle(
            "Subsection",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=INK,
            spaceBefore=9,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.4,
            leading=12,
            textColor=INK,
            spaceAfter=4,
        ),
        "note": ParagraphStyle(
            "Note",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=7.8,
            leading=11,
            textColor=MUTED,
            leftIndent=8,
            borderColor=GREEN,
            borderWidth=0,
            borderPadding=7,
            backColor=SOFT,
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.4,
            leading=12,
            leftIndent=11,
            firstLineIndent=-6,
            bulletIndent=2,
            textColor=INK,
            spaceAfter=3,
        ),
        "table": ParagraphStyle(
            "TableCell",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=6.4,
            leading=8,
            textColor=INK,
        ),
    }

    story = []
    lines = markdown_text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if line.startswith("|") and index + 1 < len(lines) and set(lines[index + 1].replace("|", "").replace("-", "").replace(":", "").strip()) == set():
            raw_rows = [line]
            index += 2
            while index < len(lines) and lines[index].startswith("|"):
                raw_rows.append(lines[index])
                index += 1
            rows = []
            for raw in raw_rows:
                cells = [cell.strip() for cell in raw.strip("|").split("|")]
                rows.append([Paragraph(_clean_inline(cell), styles["table"]) for cell in cells])
            width = (A4[0] - 36 * mm) / max(len(rows[0]), 1)
            table = Table(rows, colWidths=[width] * len(rows[0]), repeatRows=1, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), .35, LINE),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F9F7")]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.extend([table, Spacer(1, 7)])
            continue
        if line.startswith("# "):
            story.append(Paragraph(_clean_inline(line[2:]), styles["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(_clean_inline(line[3:]), styles["h2"]))
        elif line.startswith("### "):
            story.append(Paragraph(_clean_inline(line[4:]), styles["h3"]))
        elif line.startswith("> "):
            story.append(Paragraph(_clean_inline(line[2:]), styles["note"]))
        elif line.startswith("- "):
            story.append(Paragraph("• " + _clean_inline(line[2:]), styles["bullet"]))
        elif line.strip() == "---":
            story.append(PageBreak())
        elif line.strip():
            story.append(Paragraph(_clean_inline(line), styles["body"]))
        index += 1

    document.build(story, onFirstPage=_page, onLaterPages=_page)
    return buffer.getvalue()
