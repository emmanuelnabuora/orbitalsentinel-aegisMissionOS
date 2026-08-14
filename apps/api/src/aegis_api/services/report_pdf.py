"""Render a report snapshot to PDF in the AEGIS visual language.

Deterministic layout via reportlab (available offline; no headless browser).
Colors mirror the product palette so exported documents are recognizably AEGIS.
"""

import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from aegis_api.models.report import Report

_NAVY = colors.HexColor("#0B1220")
_MIDNIGHT = colors.HexColor("#111827")
_ORBITAL = colors.HexColor("#2563EB")
_LINE = colors.HexColor("#1F2A44")
_INK = colors.HexColor("#E5E7EB")
_INK_MUTED = colors.HexColor("#9CA3AF")


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "AegisTitle",
            parent=base["Title"],
            textColor=_INK,
            fontName="Helvetica-Bold",
            fontSize=20,
            spaceAfter=4,
            alignment=TA_LEFT,
        ),
        "eyebrow": ParagraphStyle(
            "AegisEyebrow",
            parent=base["Normal"],
            textColor=_ORBITAL,
            fontName="Helvetica-Bold",
            fontSize=8,
            spaceAfter=2,
            leading=10,
        ),
        "meta": ParagraphStyle(
            "AegisMeta",
            parent=base["Normal"],
            textColor=_INK_MUTED,
            fontName="Helvetica",
            fontSize=8,
            spaceAfter=12,
        ),
        "summary": ParagraphStyle(
            "AegisSummary",
            parent=base["Normal"],
            textColor=_INK,
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            spaceAfter=14,
        ),
        "heading": ParagraphStyle(
            "AegisHeading",
            parent=base["Heading2"],
            textColor=_INK,
            fontName="Helvetica-Bold",
            fontSize=12,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "AegisBody",
            parent=base["Normal"],
            textColor=_INK,
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceAfter=8,
        ),
    }


def render_report_pdf(report: Report) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        title=report.title,
        author="AEGIS MissionOS",
    )
    s = _styles()
    story: list = []

    story.append(Paragraph("AEGIS MISSIONOS · ORBITALSENTINEL", s["eyebrow"]))
    story.append(Paragraph(report.title, s["title"]))
    story.append(
        Paragraph(
            f"{report.kind.value.replace('_', ' ').title()} · generated "
            f"{report.created_at.strftime('%Y-%m-%d %H:%M UTC')} · via {report.provider}",
            s["meta"],
        )
    )

    content = report.content
    if content.get("summary"):
        story.append(Paragraph(content["summary"], s["summary"]))

    for section in content.get("sections", []):
        story.append(Paragraph(section["heading"], s["heading"]))
        if section.get("body"):
            story.append(Paragraph(section["body"], s["body"]))
        if section.get("rows"):
            columns = section.get("columns") or []
            data = ([columns] if columns else []) + section["rows"]
            table = Table(data, repeatRows=1 if columns else 0, hAlign="LEFT")
            style = [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), _INK),
                ("BACKGROUND", (0, 0), (-1, -1), _MIDNIGHT),
                ("GRID", (0, 0), (-1, -1), 0.4, _LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
            if columns:
                style += [
                    ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), _INK_MUTED),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 7.5),
                ]
            table.setStyle(TableStyle(style))
            story.append(table)
            story.append(Spacer(1, 8))

    doc.build(story)
    return buf.getvalue()
