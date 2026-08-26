from __future__ import annotations

import io
import re
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Line, Rect, String
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
    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 - \2", value)
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


def _bar_chart(labels: list[str], series: list[tuple[str, list[float], colors.Color]], *, height: int = 150) -> Drawing:
    width = 470
    drawing = Drawing(width, height)
    left, bottom, top = 42, 30, height - 20
    plot_width, plot_height = width - left - 12, top - bottom
    values = [float(value) for _, items, _ in series for value in items if value is not None]
    minimum = min([0, *values])
    maximum = max([1, *values])
    span = maximum - minimum
    zero_y = bottom + plot_height * (0 - minimum) / span
    drawing.add(Line(left, zero_y, width - 8, zero_y, strokeColor=LINE, strokeWidth=.8))
    group_width = plot_width / max(len(labels), 1)
    bar_width = min(24, group_width / max(len(series) + 1, 2))
    for label_index, label in enumerate(labels):
        center = left + group_width * (label_index + .5)
        for series_index, (_, items, color) in enumerate(series):
            value = float(items[label_index]) if label_index < len(items) and items[label_index] is not None else 0
            value_y = bottom + plot_height * (value - minimum) / span
            bar_height = abs(value_y - zero_y)
            x = center + (series_index - (len(series) - 1) / 2) * (bar_width + 4) - bar_width / 2
            drawing.add(Rect(x, min(zero_y, value_y), bar_width, bar_height, fillColor=color, strokeColor=None, rx=2, ry=2))
        drawing.add(String(center, 11, str(label), fontName="Helvetica", fontSize=7, fillColor=MUTED, textAnchor="middle"))
    legend_x = left
    for name, _, color in series:
        drawing.add(Rect(legend_x, height - 11, 7, 7, fillColor=color, strokeColor=None, rx=2, ry=2))
        drawing.add(String(legend_x + 11, height - 10, name, fontName="Helvetica", fontSize=7, fillColor=MUTED))
        legend_x += 110
    return drawing


def _metric_cards(items: list[tuple[str, str]]) -> Table:
    style = getSampleStyleSheet()["BodyText"]
    cells = [
        Paragraph(
            f"<font size='7' color='#607068'>{escape(label.upper())}</font><br/><font size='15' color='#087F5B'><b>{escape(value)}</b></font>",
            style,
        )
        for label, value in items
    ]
    table = Table([cells], colWidths=[(A4[0] - 36 * mm) / len(cells)] * len(cells))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), .5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), .5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return table


def build_company_pdf(company, summary: dict[str, object], profile: dict[str, object], signals, bridge, *, ticker: str) -> bytes:
    """Create an answer-first, chart-led company brief without raw-data tables."""
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=24 * mm,
        title=f"The Company · {ticker}",
        author="The Research Desk",
    )
    base = getSampleStyleSheet()
    title = ParagraphStyle("CompanyTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=25, leading=29, textColor=INK, spaceAfter=6)
    deck = ParagraphStyle("Deck", parent=base["BodyText"], fontName="Helvetica", fontSize=10, leading=15, textColor=MUTED, spaceAfter=14)
    h2 = ParagraphStyle("CompanyH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=GREEN, spaceBefore=15, spaceAfter=7)
    body = ParagraphStyle("CompanyBody", parent=base["BodyText"], fontName="Helvetica", fontSize=8.8, leading=13, textColor=INK, spaceAfter=6)
    bullet = ParagraphStyle("CompanyBullet", parent=body, leftIndent=12, firstLineIndent=-7)
    note = ParagraphStyle("CompanyNote", parent=body, borderPadding=9, backColor=SOFT, textColor=INK, spaceAfter=10)
    kicker = ParagraphStyle("Kicker", parent=body, fontName="Helvetica-Bold", fontSize=7, textColor=GREEN, spaceAfter=7)
    source_style = ParagraphStyle("Source", parent=body, fontSize=7, textColor=MUTED)

    fiscal_year = int(summary["fiscal_year"])
    fmt_billions = lambda value: "-" if value is None or value != value else f"${value / 1e9:,.1f}B"
    fmt_percent = lambda value: "-" if value is None or value != value else f"{value:.1%}"
    years = [str(int(value)) for value in company["fiscal_year"].tolist()]
    revenue_values = [float(value) / 1e9 for value in company["revenue"].fillna(0)]
    fcf_values = [float(value) / 1e9 for value in company["free_cash_flow"].fillna(0)]
    margin_values = [float(value) * 100 for value in company["operating_margin"].fillna(0)]

    story = [
        Paragraph("THE COMPANY · FUNDAMENTALS & ACCOUNTING QUALITY", kicker),
        Paragraph(escape(str(summary["company"])), title),
        Paragraph(f"{ticker} · FY{fiscal_year} · An answer-first brief that separates reported facts, deterministic calculations and analytical judgment.", deck),
        _metric_cards([
            ("Revenue", fmt_billions(summary.get("revenue"))),
            ("Operating margin", fmt_percent(summary.get("operating_margin"))),
            ("Simple FCF", fmt_billions(summary.get("free_cash_flow"))),
            ("Capex / revenue", fmt_percent(summary.get("capex_intensity"))),
        ]),
        Paragraph("Executive answer", h2),
        Paragraph("<b>Thesis.</b> " + escape(str(profile["research_thesis"])), note),
        Paragraph("<b>Counter-thesis.</b> " + escape(str(profile["counter_thesis"])), note),
        Paragraph("Performance trajectory", h2),
        Paragraph("Scale and cash generation are shown on a consistent fiscal-year basis. The chart is a diagnostic starting point, not a conclusion about quality.", body),
        _bar_chart(years, [("Revenue · USD B", revenue_values, GREEN), ("Simple FCF · USD B", fcf_values, colors.HexColor("#76B89D"))]),
        Spacer(1, 5),
        _bar_chart(years, [("Operating margin · %", margin_values, colors.HexColor("#173F32"))], height=125),
        Paragraph("Business economics", h2),
        Paragraph(escape(str(profile["business_model"])), body),
    ]
    for item in profile["growth_engines"]:
        story.append(Paragraph("• " + escape(str(item)), bullet))
    story.append(Paragraph("Accounting quality & normalization", h2))
    if signals.empty:
        story.append(Paragraph("No deterministic signal was triggered. This does not establish accounting quality; the primary filing remains the decision source.", note))
    else:
        for row in signals.itertuples(index=False):
            story.append(Paragraph(f"<b>{escape(str(row.signal))}</b><br/>{escape(str(row.observation))}<br/><font color='#607068'>{escape(str(row.analytical_implication))}</font>", note))
    if len(bridge) > 1:
        story.extend([
            Paragraph("Reported-to-analytical cash-flow bridge", h2),
            Paragraph("A classification adjustment can change the analytical view of cash generation without changing reported cash flow.", body),
            _bar_chart([str(value) for value in bridge["step"]], [("USD B", [float(value) for value in bridge["amount_usd_billions"]], GREEN)], height=140),
        ])
    story.append(Paragraph("Priority diligence", h2))
    for item in profile["diligence_questions"]:
        story.append(Paragraph("• " + escape(str(item)), bullet))
    story.extend([
        Paragraph("Research boundary", h2),
        Paragraph("This report is based on public-source data and deterministic rules. Missing values remain missing. Accounting-quality signals identify review work and do not allege misconduct. The report does not provide a rating, target price or transaction instruction.", body),
        Paragraph("Primary source: " + escape(str(profile["source_url"])), source_style),
    ])
    document.build(story, onFirstPage=_page, onLaterPages=_page)
    return buffer.getvalue()
