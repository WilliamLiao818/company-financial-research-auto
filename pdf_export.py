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


def _ascii(value: object) -> str:
    return str(value).replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")


def _fmt_billions(value: object) -> str:
    return "-" if value is None or value != value else f"${float(value) / 1e9:,.1f}B"


def _fmt_percent(value: object) -> str:
    return "-" if value is None or value != value else f"{float(value):.1%}"


def _bar_chart(labels: list[str], series: list[tuple[str, list[float], colors.Color]], *, height: int = 175, suffix: str = "") -> Drawing:
    width = 470
    drawing = Drawing(width, height)
    left, bottom, top = 48, 34, height - 28
    plot_width, plot_height = width - left - 12, top - bottom
    values = [float(value) for _, items, _ in series for value in items if value is not None]
    minimum = min([0, *values])
    maximum = max([1, *values])
    padding = (maximum - minimum) * .16 or 1
    maximum += padding
    minimum -= padding if minimum < 0 else 0
    span = maximum - minimum
    for step in range(5):
        value = minimum + span * step / 4
        y = bottom + plot_height * step / 4
        drawing.add(Line(left, y, width - 8, y, strokeColor=colors.HexColor("#E6EFEA"), strokeWidth=.55))
        drawing.add(String(left - 6, y - 2, f"{value:,.0f}{suffix}", fontName="Helvetica", fontSize=6.4, fillColor=MUTED, textAnchor="end"))
    zero_y = bottom + plot_height * (0 - minimum) / span
    drawing.add(Line(left, zero_y, width - 8, zero_y, strokeColor=colors.HexColor("#A8BBB1"), strokeWidth=.8))
    group_width = plot_width / max(len(labels), 1)
    bar_width = min(23, group_width / max(len(series) + .7, 2))
    for label_index, label in enumerate(labels):
        center = left + group_width * (label_index + .5)
        for series_index, (_, items, color) in enumerate(series):
            value = float(items[label_index]) if label_index < len(items) and items[label_index] is not None else 0
            value_y = bottom + plot_height * (value - minimum) / span
            bar_height = max(abs(value_y - zero_y), .7)
            x = center + (series_index - (len(series) - 1) / 2) * (bar_width + 4) - bar_width / 2
            drawing.add(Rect(x, min(zero_y, value_y), bar_width, bar_height, fillColor=color, strokeColor=None, rx=2, ry=2))
        drawing.add(String(center, 13, _ascii(label)[:18], fontName="Helvetica", fontSize=6.7, fillColor=MUTED, textAnchor="middle"))
    legend_x = left
    for name, _, color in series:
        drawing.add(Rect(legend_x, height - 13, 7, 7, fillColor=color, strokeColor=None, rx=2, ry=2))
        drawing.add(String(legend_x + 11, height - 12, _ascii(name), fontName="Helvetica", fontSize=7, fillColor=MUTED))
        legend_x += 128
    return drawing


def _line_chart(labels: list[str], series: list[tuple[str, list[float], colors.Color]], *, height: int = 180, suffix: str = "") -> Drawing:
    width = 470
    drawing = Drawing(width, height)
    left, bottom, top = 48, 34, height - 30
    plot_width, plot_height = width - left - 16, top - bottom
    values = [float(value) for _, items, _ in series for value in items if value is not None]
    minimum = min(values or [0])
    maximum = max(values or [1])
    padding = (maximum - minimum) * .18 or 1
    minimum = min(0, minimum - padding)
    maximum += padding
    span = maximum - minimum
    for step in range(5):
        value = minimum + span * step / 4
        y = bottom + plot_height * step / 4
        drawing.add(Line(left, y, width - 8, y, strokeColor=colors.HexColor("#E6EFEA"), strokeWidth=.55))
        drawing.add(String(left - 6, y - 2, f"{value:,.0f}{suffix}", fontName="Helvetica", fontSize=6.4, fillColor=MUTED, textAnchor="end"))
    for name, items, color in series:
        points = []
        for index, raw in enumerate(items):
            value = float(raw)
            x = left + (plot_width * index / max(len(labels) - 1, 1))
            y = bottom + plot_height * (value - minimum) / span
            points.append((x, y))
        for first, second in zip(points, points[1:]):
            drawing.add(Line(first[0], first[1], second[0], second[1], strokeColor=color, strokeWidth=2.3))
        for x, y in points:
            drawing.add(Rect(x - 2.4, y - 2.4, 4.8, 4.8, fillColor=color, strokeColor=colors.white, strokeWidth=.6, rx=2.4, ry=2.4))
        if points:
            drawing.add(String(points[-1][0] + 5, points[-1][1] - 2, _ascii(name), fontName="Helvetica-Bold", fontSize=6.8, fillColor=color))
    for index, label in enumerate(labels):
        x = left + (plot_width * index / max(len(labels) - 1, 1))
        drawing.add(String(x, 13, _ascii(label), fontName="Helvetica", fontSize=6.7, fillColor=MUTED, textAnchor="middle"))
    return drawing


def _horizontal_bars(labels: list[str], values: list[float], *, height: int = 180, color: colors.Color = GREEN, suffix: str = "") -> Drawing:
    width = 470
    drawing = Drawing(width, height)
    left, right, top = 145, 40, height - 22
    maximum = max([1, *[abs(float(value)) for value in values]])
    row_height = (top - 18) / max(len(labels), 1)
    for index, (label, value) in enumerate(zip(labels, values)):
        y = top - row_height * (index + .65)
        drawing.add(String(left - 8, y + 2, _ascii(label)[:28], fontName="Helvetica", fontSize=7.1, fillColor=INK, textAnchor="end"))
        drawing.add(Rect(left, y, width - left - right, 10, fillColor=colors.HexColor("#EDF4F0"), strokeColor=None, rx=5, ry=5))
        drawing.add(Rect(left, y, (width - left - right) * abs(float(value)) / maximum, 10, fillColor=color, strokeColor=None, rx=5, ry=5))
        drawing.add(String(width - right + 5, y + 2, f"{value:,.1f}{suffix}", fontName="Helvetica-Bold", fontSize=7, fillColor=INK))
    return drawing


def _competitive_matrix(profile: dict[str, object]) -> Table:
    dimensions = list(profile["competitive_dimensions"])
    rows = [[Paragraph("Company", _table_style(True)), *[Paragraph(escape(_ascii(item)), _table_style(True)) for item in dimensions]]]
    for company_name, scores in profile["competitive_scores"].items():
        rows.append([Paragraph(escape(_ascii(company_name)), _table_style(False)), *[Paragraph(f"{int(score)} / 5", _table_style(False)) for score in scores]])
    available = A4[0] - 36 * mm
    table = Table(rows, colWidths=[available * .18] + [available * .82 / len(dimensions)] * len(dimensions), repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8F6")]),
        ("GRID", (0, 0), (-1, -1), .4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _table_style(header: bool) -> ParagraphStyle:
    return ParagraphStyle(
        "MatrixHeader" if header else "MatrixCell",
        parent=getSampleStyleSheet()["BodyText"],
        fontName="Helvetica-Bold" if header else "Helvetica",
        fontSize=5.8 if header else 6.5,
        leading=7.2 if header else 8,
        textColor=colors.white if header else INK,
        alignment=0,
    )


def _metric_cards(items: list[tuple[str, str]]) -> Table:
    style = getSampleStyleSheet()["BodyText"]
    cells = [Paragraph(f"<font size='6.7' color='#607068'>{escape(_ascii(label.upper()))}</font><br/><font size='15' color='#087F5B'><b>{escape(_ascii(value))}</b></font>", style) for label, value in items]
    table = Table([cells], colWidths=[(A4[0] - 36 * mm) / len(cells)] * len(cells))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white), ("BOX", (0, 0), (-1, -1), .55, LINE),
        ("INNERGRID", (0, 0), (-1, -1), .55, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return table


def _two_columns(left_items, right_items, styles, *, left_title: str, right_title: str) -> Table:
    left = [Paragraph(escape(_ascii(left_title.upper())), styles["eyebrow"])]
    right = [Paragraph(escape(_ascii(right_title.upper())), styles["eyebrow"])]
    for item in left_items:
        left.append(Paragraph("• " + escape(_ascii(item)), styles["bullet"]))
    for item in right_items:
        right.append(Paragraph("• " + escape(_ascii(item)), styles["bullet"]))
    table = Table([[left, right]], colWidths=[(A4[0] - 40 * mm) / 2] * 2, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white), ("BOX", (0, 0), (-1, -1), .5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), .5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 11), ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
    ]))
    return table


def _report_page(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 6.8)
    canvas.setFillColor(GREEN)
    canvas.drawString(18 * mm, A4[1] - 11 * mm, "THE COMPANY | INSTITUTIONAL RESEARCH ARCHITECTURE")
    canvas.setFont("Helvetica", 6.8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 11 * mm, _ascii(getattr(document, "report_ticker", "")))
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 18 * mm, A4[0] - 18 * mm, 18 * mm)
    canvas.setFont("Helvetica", 6.8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 11 * mm, "PUBLIC-SOURCE RESEARCH SUPPORT | NOT A RATING OR TARGET PRICE")
    canvas.drawRightString(A4[0] - 18 * mm, 11 * mm, f"{document.page}")
    canvas.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle("ResearchBody", parent=base["BodyText"], fontName="Helvetica", fontSize=8.8, leading=13, textColor=INK, spaceAfter=6)
    return {
        "title": ParagraphStyle("ResearchTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=27, leading=31, textColor=INK, spaceAfter=7),
        "deck": ParagraphStyle("ResearchDeck", parent=body, fontSize=10.2, leading=15, textColor=MUTED, spaceAfter=13),
        "page": ParagraphStyle("PageTitle", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=INK, spaceBefore=3, spaceAfter=11),
        "h2": ParagraphStyle("ResearchH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=GREEN, spaceBefore=10, spaceAfter=7),
        "h3": ParagraphStyle("ResearchH3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=9.4, leading=12, textColor=INK, spaceBefore=7, spaceAfter=4),
        "body": body,
        "bullet": ParagraphStyle("ResearchBullet", parent=body, leftIndent=12, firstLineIndent=-7, spaceAfter=4),
        "note": ParagraphStyle("ResearchNote", parent=body, borderPadding=10, backColor=SOFT, textColor=INK, spaceAfter=10),
        "eyebrow": ParagraphStyle("ResearchEyebrow", parent=body, fontName="Helvetica-Bold", fontSize=6.8, leading=9, textColor=GREEN, tracking=.8, spaceAfter=6),
        "source": ParagraphStyle("ResearchSource", parent=body, fontSize=6.7, leading=9.5, textColor=MUTED, spaceAfter=3),
    }


def build_company_pdf(company, summary: dict[str, object], profile: dict[str, object], signals, bridge, *, ticker: str, peers=None, scenarios=None) -> bytes:
    """Create a 12-page, chart-led company research report with explicit evidence boundaries."""
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=24 * mm,
        title=f"The Company | {ticker}",
        author="The Research Desk",
    )
    document.report_ticker = ticker
    styles = _styles()
    years = [str(int(value)) for value in company["fiscal_year"].tolist()]
    revenue = [float(value) / 1e9 for value in company["revenue"].fillna(0)]
    operating_income = [float(value) / 1e9 for value in company["operating_income"].fillna(0)]
    net_income = [float(value) / 1e9 for value in company["net_income"].fillna(0)]
    cfo = [float(value) / 1e9 for value in company["operating_cash_flow"].fillna(0)]
    capex = [float(value) / 1e9 for value in company["capex"].fillna(0)]
    fcf = [float(value) / 1e9 for value in company["free_cash_flow"].fillna(0)]
    op_margin = [float(value) * 100 for value in company["operating_margin"].fillna(0)]
    net_margin = [float(value) * 100 for value in company["net_margin"].fillna(0)]
    fcf_margin = [float(value) * 100 for value in company["fcf_margin"].fillna(0)]
    capex_intensity = [float(value) * 100 for value in company["capex_intensity"].fillna(0)]
    assets = [float(value) / 1e9 for value in company["assets"].fillna(0)]
    liabilities = [float(value) / 1e9 for value in company["liabilities"].fillna(0)]
    fiscal_year = int(summary["fiscal_year"])
    latest_revenue = float(summary["revenue"]) / 1e9
    latest_op_income = float(company.iloc[-1]["operating_income"]) / 1e9
    latest_fcf = float(summary["free_cash_flow"]) / 1e9
    if scenarios is None:
        defaults = profile["scenario_defaults"]
        scenario_rows = []
        for case in ["bear", "base", "bull"]:
            growth = float(defaults[f"{case}_growth"])
            margin = float(defaults[f"{case}_margin"])
            projected_revenue = float(summary["revenue"]) * (1 + growth) ** int(defaults["years"])
            scenario_rows.append({"case": case.title(), "revenue": projected_revenue, "operating_income": projected_revenue * margin, "growth": growth, "margin": margin, "years": int(defaults["years"])})
        scenarios = scenario_rows
    scenario_records = scenarios.to_dict("records") if hasattr(scenarios, "to_dict") else list(scenarios)

    story = []
    # 1 | Cover and executive view
    story.extend([
        Spacer(1, 8),
        Paragraph("THE COMPANY | FUNDAMENTALS, ACCOUNTING QUALITY & SCENARIOS", styles["eyebrow"]),
        Paragraph(escape(_ascii(summary["company"])), styles["title"]),
        Paragraph(f"{escape(_ascii(ticker))} | FY{fiscal_year} | Public-source company research with explicit facts, calculations, judgments and review boundaries.", styles["deck"]),
        _metric_cards([
            ("Revenue", _fmt_billions(summary.get("revenue"))),
            ("Revenue growth", _fmt_percent(summary.get("revenue_growth"))),
            ("Operating margin", _fmt_percent(summary.get("operating_margin"))),
            ("Simple FCF", _fmt_billions(summary.get("free_cash_flow"))),
        ]),
        Paragraph("Executive view", styles["h2"]),
        Paragraph("<b>Core thesis.</b> " + escape(_ascii(profile["research_thesis"])), styles["note"]),
        Paragraph("<b>Counter-thesis.</b> " + escape(_ascii(profile["counter_thesis"])), styles["note"]),
        Paragraph("What the latest year says", styles["h2"]),
        Paragraph(
            f"Revenue changed {_fmt_percent(summary.get('revenue_growth'))} year over year, operating margin reached {_fmt_percent(summary.get('operating_margin'))}, capex represented {_fmt_percent(summary.get('capex_intensity'))} of revenue and simple FCF was {_fmt_billions(summary.get('free_cash_flow'))}. These observations frame the debate; they do not determine a rating or target price.",
            styles["body"],
        ),
    ])

    # 2 | Pivotal questions
    story.extend([PageBreak(), Paragraph("Pivotal questions and differentiated view", styles["page"]), Paragraph("The research process begins with falsifiable questions. Each question links an operating driver to the evidence that would strengthen or weaken the view.", styles["deck"])])
    for index, question in enumerate(profile["key_questions"], start=1):
        story.append(Paragraph(f"<b>{index:02d}. {escape(_ascii(question))}</b>", styles["note"]))
    story.append(Paragraph("Priority diligence", styles["h2"]))
    for item in profile["diligence_questions"]:
        story.append(Paragraph("• " + escape(_ascii(item)), styles["bullet"]))
    story.append(Paragraph("Decision rule", styles["h2"]))
    story.append(Paragraph("A conclusion is retained only while the operating evidence, cash economics and competitive position remain mutually consistent. A strong headline metric does not override a contradictory cash-flow or balance-sheet signal.", styles["body"]))

    # 3 | Business and moat
    story.extend([PageBreak(), Paragraph("Business model and moat", styles["page"]), Paragraph(escape(_ascii(profile["business_model"])), styles["note"]), Paragraph("Growth engines", styles["h2"])])
    for item in profile["growth_engines"]:
        story.append(Paragraph("• " + escape(_ascii(item)), styles["bullet"]))
    story.append(Paragraph("Competitive durability", styles["h2"]))
    moat_rows = []
    for label, explanation in profile["moat_factors"]:
        moat_rows.append([Paragraph(f"<b>{escape(_ascii(label))}</b>", styles["body"]), Paragraph(escape(_ascii(explanation)), styles["body"])])
    moat_table = Table(moat_rows, colWidths=[42 * mm, A4[0] - 82 * mm], hAlign="LEFT")
    moat_table.setStyle(TableStyle([("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F4F8F6")]), ("BOX", (0, 0), (-1, -1), .45, LINE), ("INNERGRID", (0, 0), (-1, -1), .35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.extend([moat_table, Paragraph("Operating indicators", styles["h2"]), Paragraph(" • ".join(escape(_ascii(item)) for item in profile["key_kpis"]), styles["body"])])

    # 4 | Earnings
    story.extend([PageBreak(), Paragraph("Earnings trajectory", styles["page"]), Paragraph("Scale, growth and operating profit are shown before valuation so the direction of the underlying business remains distinct from market assumptions.", styles["deck"]), Paragraph("Revenue and operating income", styles["h2"]), _bar_chart(years, [("Revenue | USD B", revenue, GREEN), ("Operating income | USD B", operating_income, colors.HexColor("#76B89D"))], height=205), Paragraph("Net income progression", styles["h2"]), _line_chart(years, [("Net income", net_income, colors.HexColor("#173F32"))], height=170), Paragraph("Interpretation", styles["h2"]), Paragraph("Revenue growth should be reconciled to price, volume, mix, acquisitions and currency. Operating income adds the cost structure, but not the investment intensity required to sustain the growth path.", styles["body"])])

    # 5 | Margins
    story.extend([PageBreak(), Paragraph("Margins and operating leverage", styles["page"]), Paragraph("Margin direction is assessed together with reinvestment intensity. A rising accounting margin can coexist with weakening economic cash returns when infrastructure commitments accelerate.", styles["deck"]), Paragraph("Profit and cash margins", styles["h2"]), _line_chart(years, [("Operating margin", op_margin, GREEN), ("Net margin", net_margin, colors.HexColor("#173F32")), ("FCF margin", fcf_margin, colors.HexColor("#76B89D"))], height=220, suffix="%"), Paragraph("Capex intensity", styles["h2"]), _bar_chart(years, [("Capex / revenue", capex_intensity, colors.HexColor("#D97706"))], height=175, suffix="%"), Paragraph("Research implication", styles["h2"]), Paragraph("The key question is not whether margin is high in isolation, but whether incremental revenue produces operating profit and cash returns after the required capital base is recognized consistently.", styles["body"])])

    # 6 | Cash and balance sheet
    story.extend([PageBreak(), Paragraph("Cash generation and financial capacity", styles["page"]), Paragraph("Operating cash flow, reported capital expenditure and simple FCF are presented together. Balance-sheet scale is then used to test how much financial capacity supports the investment cycle.", styles["deck"]), Paragraph("Cash-flow bridge by fiscal year", styles["h2"]), _bar_chart(years, [("Operating cash flow", cfo, GREEN), ("Capex", capex, colors.HexColor("#D97706")), ("Simple FCF", fcf, colors.HexColor("#76B89D"))], height=210), Paragraph("Assets and liabilities", styles["h2"]), _line_chart(years, [("Assets", assets, GREEN), ("Liabilities", liabilities, colors.HexColor("#8AA89A"))], height=180), Paragraph("Boundary", styles["h2"]), Paragraph("Total liabilities / assets is a structure indicator, not net debt, liquidity or a credit conclusion. A full review requires debt maturities, commitments, leases, cash availability and financing terms.", styles["body"])])

    # 7 | Accounting quality
    story.extend([PageBreak(), Paragraph("Accounting quality and noise filter", styles["page"]), Paragraph("Signals identify classification, timing and evidence issues that may change the analytical interpretation of reported performance. They do not allege misconduct.", styles["deck"])])
    if signals.empty:
        story.append(Paragraph("No deterministic signal was triggered. This does not establish accounting quality; the primary filing remains the decision source.", styles["note"]))
    else:
        for row in signals.itertuples(index=False):
            story.append(Paragraph(f"<b>{escape(_ascii(row.signal))}</b><br/>{escape(_ascii(row.observation))}<br/><font color='#607068'>Implication: {escape(_ascii(row.analytical_implication))}<br/>Required review: {escape(_ascii(row.required_review))}</font>", styles["note"]))
    if len(bridge) > 1:
        story.extend([Paragraph("Reported-to-analytical cash-flow bridge", styles["h2"]), _horizontal_bars([_ascii(value) for value in bridge["step"]], [float(value) for value in bridge["amount_usd_billions"]], height=145, suffix="B"), Paragraph("The adjustment is an analytical view, not a restatement. Definitions must remain consistent across periods and peers.", styles["body"])])

    # 8 | Peers
    story.extend([PageBreak(), Paragraph("Peer benchmarking and competitive position", styles["page"]), Paragraph("Reported peer metrics and a transparent competitive rubric answer different questions. The first is observed; the second is analyst judgment and must remain revisable.", styles["deck"])])
    if peers is not None and len(peers) > 1:
        peer_records = peers.to_dict("records") if hasattr(peers, "to_dict") else list(peers)
        labels = [record["ticker"] for record in peer_records]
        story.extend([Paragraph("Latest reported operating comparison", styles["h2"]), _bar_chart(labels, [("Revenue growth", [float(record.get("revenue_growth") or 0) * 100 for record in peer_records], GREEN), ("Operating margin", [float(record.get("operating_margin") or 0) * 100 for record in peer_records], colors.HexColor("#173F32")), ("FCF margin", [float(record.get("fcf_margin") or 0) * 100 for record in peer_records], colors.HexColor("#76B89D"))], height=190, suffix="%")])
    story.extend([Paragraph("Competitive rubric | 1 to 5", styles["h2"]), _competitive_matrix(profile), Spacer(1, 6), Paragraph("Scores are explicit analytical judgments designed to expose assumptions. They are not reported facts, ratings or market-share estimates.", styles["source"])])

    # 9 | Operating scenarios
    story.extend([PageBreak(), Paragraph("Operating scenarios", styles["page"]), Paragraph("Bear, base and bull cases isolate the operating assumptions that matter most. They are not forecasts and do not imply probabilities.", styles["deck"]), Paragraph("Illustrative revenue outcome", styles["h2"]), _bar_chart([record["case"] for record in scenario_records], [("Revenue | USD B", [float(record["revenue"]) / 1e9 for record in scenario_records], GREEN), ("Operating income | USD B", [float(record["operating_income"]) / 1e9 for record in scenario_records], colors.HexColor("#76B89D"))], height=220), Paragraph("Assumptions", styles["h2"])])
    scenario_rows = [[Paragraph("Case", _table_style(True)), Paragraph("Revenue CAGR", _table_style(True)), Paragraph("Operating margin", _table_style(True)), Paragraph("Horizon", _table_style(True))]]
    for record in scenario_records:
        scenario_rows.append([Paragraph(escape(_ascii(record["case"])), _table_style(False)), Paragraph(f"{float(record['growth']):.1%}", _table_style(False)), Paragraph(f"{float(record['margin']):.1%}", _table_style(False)), Paragraph(f"{int(record['years'])} years", _table_style(False))])
    scenario_table = Table(scenario_rows, colWidths=[(A4[0] - 36 * mm) / 4] * 4)
    scenario_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), GREEN), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8F6")]), ("GRID", (0, 0), (-1, -1), .4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.extend([scenario_table, Paragraph("What would change the case", styles["h2"]), Paragraph("The scenarios should move only when new evidence changes demand, pricing, operating leverage, capacity requirements or competitive intensity. A share-price move alone does not change the operating case.", styles["body"])])

    # 10 | Valuation framework
    valuation_labels = ["Revenue | 6x", "Revenue | 8x", "Revenue | 10x", "Operating income | 15x", "Operating income | 20x", "Operating income | 25x", "Simple FCF | 20x", "Simple FCF | 25x"]
    valuation_values = [latest_revenue * 6, latest_revenue * 8, latest_revenue * 10, latest_op_income * 15, latest_op_income * 20, latest_op_income * 25, latest_fcf * 20, latest_fcf * 25]
    story.extend([PageBreak(), Paragraph("Valuation framework", styles["page"]), Paragraph("The framework shows transparent enterprise- or equity-value proxies from selected reported metrics and illustrative multiples. It deliberately stops before a target price because net debt, share count, dilution, market price and a complete forecast have not been established in this report.", styles["deck"]), Paragraph("Illustrative value proxies | USD billions", styles["h2"]), _horizontal_bars(valuation_labels, valuation_values, height=275, suffix="B"), Paragraph("Use with discipline", styles["h2"]), Paragraph("A multiple is an assumption, not evidence. The appropriate range depends on growth durability, margin structure, reinvestment needs, cash conversion, balance-sheet risk and peer comparability. The webpage valuation lab exposes user-selected assumptions separately from reported facts.", styles["body"]), Paragraph("No rating, target price or expected return is produced.", styles["note"])])

    # 11 | Catalysts and risks
    story.extend([PageBreak(), Paragraph("Catalysts, risks and monitoring agenda", styles["page"]), Paragraph("A useful research view is falsifiable and updateable. The monitoring agenda connects each thesis driver to evidence that can confirm, weaken or reject it.", styles["deck"]), _two_columns(profile["catalysts"], profile["risks"], styles, left_title="Potential catalysts", right_title="Downside risks"), Paragraph("Monitoring dashboard", styles["h2"])])
    for label, signal in profile["monitoring_signals"]:
        story.append(Paragraph(f"<b>{escape(_ascii(label))}:</b> {escape(_ascii(signal))}", styles["note"]))
    story.append(Paragraph("Update cadence", styles["h2"]))
    story.append(Paragraph("Refresh after each annual filing, material earnings release, major capital-allocation change or new evidence that directly affects demand, margins, investment intensity, accounting classification or competitive position.", styles["body"]))

    # 12 | Evidence, methods and disclosures
    story.extend([PageBreak(), Paragraph("Evidence, methodology and disclosures", styles["page"]), Paragraph("The report keeps source facts, deterministic calculations, analytical judgments and user assumptions distinct so every conclusion can be traced and challenged.", styles["deck"]), Paragraph("Core formulas", styles["h2"])])
    formulas = [
        "Revenue growth = Revenue_t / Revenue_(t-1) - 1",
        "Operating margin = Operating income / Revenue",
        "Simple FCF = Operating cash flow - Capital expenditure",
        "FCF margin = Simple FCF / Revenue",
        "Capex intensity = Capital expenditure / Revenue",
        "Cash conversion = Operating cash flow / Net income",
    ]
    for item in formulas:
        story.append(Paragraph("• " + escape(_ascii(item)), styles["bullet"]))
    story.extend([Paragraph("Evidence hierarchy", styles["h2"]), Paragraph("1. Original filing and filing note. 2. Structured filing fact with accession metadata. 3. Deterministic calculation. 4. Explicit analytical judgment. 5. User-selected scenario assumption.", styles["body"]), Paragraph("Primary sources", styles["h2"]), Paragraph("Company filing: " + escape(_ascii(profile["source_url"])), styles["source"]), Paragraph("Structured facts: " + escape(_ascii(summary.get("source_url", ""))), styles["source"]), Paragraph("Research boundary", styles["h2"]), Paragraph("This report uses public-source data and deterministic rules. Missing values remain missing. Accounting-quality signals identify review work and do not allege misconduct. Competitive scores and scenarios are explicit judgments or assumptions. The report is informational and does not provide a rating, target price, transaction instruction or individually tailored advice.", styles["note"]), Paragraph("Generated by The Company | Version 2.0", styles["source"])])

    document.build(story, onFirstPage=_report_page, onLaterPages=_report_page)
    return buffer.getvalue()
