from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BASE_DIR = Path(__file__).resolve().parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

DARK = colors.HexColor("#07111F")
PANEL = colors.HexColor("#10233A")
CYAN = colors.HexColor("#61D4FF")
TEAL = colors.HexColor("#4EE4C7")
RED = colors.HexColor("#FF748C")
MUTED = colors.HexColor("#63798D")
LIGHT = colors.HexColor("#F5FAFE")
LINE = colors.HexColor("#D8E3EC")


def _safe_text(value: object) -> str:
    """Convert values to PDF-safe plain text."""

    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bar_table(
    label: str,
    value: float,
    maximum: float,
    color: colors.Color,
) -> Table:
    """Build a lightweight horizontal bar without external chart libraries."""

    normalized = max(0.0, min(float(value) / maximum, 1.0))
    total_width = 118 * mm
    filled_width = max(2 * mm, total_width * normalized)
    empty_width = max(1 * mm, total_width - filled_width)

    bar = Table(
        [["", ""]],
        colWidths=[filled_width, empty_width],
        rowHeights=[5 * mm],
    )
    bar.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), color),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#E9EFF4")),
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    label_table = Table(
        [[label, f"{value:.1f}"]],
        colWidths=[118 * mm, 24 * mm],
    )
    label_table.setStyle(
        TableStyle(
            [
                ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    return Table(
        [[label_table], [bar]],
        colWidths=[142 * mm],
        style=[
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ],
    )


def generate_pdf_report(
    output_path: Path,
    profile_name: str,
    user_data: dict,
    personalization: dict,
    result: dict,
    next_checkin: str,
) -> Path:
    """Generate a self-contained PDF wellness report with simple charts."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Digital Wellness Analysis Report",
        author="Digital Wellness Analyzer",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=25,
        textColor=DARK,
        alignment=TA_LEFT,
        spaceAfter=5 * mm,
    )

    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=MUTED,
        spaceAfter=5 * mm,
    )

    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=DARK,
        spaceBefore=3 * mm,
        spaceAfter=3 * mm,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#26384A"),
        spaceAfter=2.5 * mm,
    )

    small_style = ParagraphStyle(
        "Small",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=MUTED,
    )

    story = []

    story.append(
        Paragraph(
            "Digital Wellness Analyzer",
            title_style,
        )
    )
    story.append(
        Paragraph(
            "AI-powered digital behavior report - classification, explainability, estimation, clustering, and personalized actions.",
            subtitle_style,
        )
    )

    classification = result["classification"]
    risk_score = (
        classification["calibrated_risk_score"]
        * 100.0
    )

    status_color = (
        RED
        if classification["risk_class"] == 1
        else TEAL
    )

    summary_data = [
        [
            "Profile",
            _safe_text(profile_name),
            "Digital Wellness Status",
            _safe_text(
                classification["wellness_status"]
            ),
        ],
        [
            "Model Risk Score",
            f"{risk_score:.1f}%",
            "Behavior Cluster",
            f"Cluster {result['cluster']['cluster_id']}",
        ],
        [
            "Estimated Weekend Use",
            f"{result['projected_weekend_screen_time']:.1f} hours",
            "Next Check-in",
            _safe_text(next_checkin),
        ],
    ]

    summary = Table(
        summary_data,
        colWidths=[35 * mm, 47 * mm, 40 * mm, 48 * mm],
    )
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
                ("TEXTCOLOR", (3, 0), (3, 0), status_color),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(summary)
    story.append(Spacer(1, 5 * mm))

    story.append(
        Paragraph(
            "Classification Chart",
            heading_style,
        )
    )

    story.append(
        _bar_table(
            "Higher-risk model score (%)",
            risk_score,
            100.0,
            status_color,
        )
    )
    story.append(
        _bar_table(
            "Lower-risk share (%)",
            100.0 - risk_score,
            100.0,
            TEAL,
        )
    )

    story.append(
        Paragraph(
            "Reported Digital Time",
            heading_style,
        )
    )

    for label, value in result[
        "balance_breakdown"
    ]["usage_hours"].items():
        story.append(
            _bar_table(
                f"{label} (hours)",
                float(value),
                16.0,
                CYAN,
            )
        )

    story.append(
        Paragraph(
            "Why the Model Reached This Result",
            heading_style,
        )
    )

    explanation_rows = [
        ["Feature", "SHAP", "Direction"]
    ]

    for item in result["explanation"]:
        explanation_rows.append(
            [
                _safe_text(
                    item["feature"].replace(
                        "_",
                        " ",
                    ).title()
                ),
                f"{item['shap_value']:+.4f}",
                _safe_text(item["direction"]),
            ]
        )

    explanation_table = Table(
        explanation_rows,
        colWidths=[55 * mm, 25 * mm, 90 * mm],
        repeatRows=1,
    )
    explanation_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PANEL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(explanation_table)

    story.append(
        Paragraph(
            "Personalized Recommendations",
            heading_style,
        )
    )

    for index, recommendation in enumerate(
        result["recommendations"],
        start=1,
    ):
        story.append(
            Paragraph(
                f"<b>{index}.</b> {_safe_text(recommendation)}",
                body_style,
            )
        )

    activity = result["activity_replacements"]

    story.append(
        Paragraph(
            "Smart Activity Replacement",
            heading_style,
        )
    )

    context_text = (
        f"Role: {activity['occupation']} | "
        f"Available time: {activity['available_time']} | "
        f"Goal: {activity['goal']} | "
        f"Preference: {activity['activity_preference']} | "
        f"Peak scrolling time: {activity['peak_usage_time']}"
    )
    story.append(
        Paragraph(
            _safe_text(context_text),
            small_style,
        )
    )
    story.append(Spacer(1, 2 * mm))

    for item in activity["suggestions"]:
        story.append(
            Paragraph(
                f"<b>{_safe_text(item['category'])}:</b> {_safe_text(item['activity'])}",
                body_style,
            )
        )

    story.append(
        Paragraph(
            "Focus Software Suggestions",
            heading_style,
        )
    )

    focus_cell_style = ParagraphStyle(
        "FocusCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=6.8,
        leading=8.6,
        textColor=DARK,
    )

    focus_header_style = ParagraphStyle(
        "FocusHeader",
        parent=focus_cell_style,
        fontName="Helvetica-Bold",
        textColor=DARK,
    )

    focus_rows = [
        [
            Paragraph("Tool", focus_header_style),
            Paragraph("Best for", focus_header_style),
            Paragraph("Why suggested", focus_header_style),
        ]
    ]

    for tool in activity["focus_tools"]:
        focus_rows.append(
            [
                Paragraph(
                    _safe_text(tool["name"]),
                    focus_cell_style,
                ),
                Paragraph(
                    _safe_text(tool["best_for"]),
                    focus_cell_style,
                ),
                Paragraph(
                    _safe_text(tool["why"]),
                    focus_cell_style,
                ),
            ]
        )

    focus_table = Table(
        focus_rows,
        colWidths=[24 * mm, 52 * mm, 94 * mm],
        repeatRows=1,
    )
    focus_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF7FB")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(focus_table)

    story.append(
        KeepTogether(
            [
                Paragraph(
                    "Today's Challenge",
                    heading_style,
                ),
                Paragraph(
                    _safe_text(
                        activity["daily_challenge"]
                    ),
                    body_style,
                ),
            ]
        )
    )


    if result.get("friendly_coach_message"):
        story.append(
            Paragraph(
                "Friendly Coaching Note",
                heading_style,
            )
        )
        story.append(
            Paragraph(
                _safe_text(result["friendly_coach_message"]),
                body_style,
            )
        )

    if result.get("productive_digital"):
        productive = result["productive_digital"]
        story.append(
            Paragraph(
                "Purposeful Digital Use",
                heading_style,
            )
        )
        story.append(
            Paragraph(
                _safe_text(
                    f"Purposeful study/work screen time: {productive['purposeful_hours']:.1f} h/day "
                    f"({productive['purposeful_share']:.1f}% of reported daily screen time). "
                    f"{productive['message']}"
                ),
                body_style,
            )
        )

    if result.get("exercise_context"):
        exercise = result["exercise_context"]
        story.append(
            Paragraph(
                "Exercise and Weekly Activity Context",
                heading_style,
            )
        )
        story.append(
            Paragraph(
                _safe_text(
                    f"Planned exercise: {exercise['days_per_week']} days/week, "
                    f"{exercise['minutes_per_session']} minutes/session, "
                    f"{exercise['weekly_minutes']} minutes/week. "
                    f"{exercise['progress_label']} {exercise['impact_note']}"
                ),
                body_style,
            )
        )

    if result.get("weekly_plan"):
        story.append(
            Paragraph(
                "Weekly Plan",
                heading_style,
            )
        )
        for day in result["weekly_plan"]:
            blocks = "; ".join(day["blocks"])
            story.append(
                Paragraph(
                    f"<b>{_safe_text(day['day'])}:</b> {_safe_text(blocks)}",
                    body_style,
                )
            )

    if result.get("ergonomic_guidance"):
        story.append(
            Paragraph(
                "Healthier Digital Work / Study Setup",
                heading_style,
            )
        )
        for item in result["ergonomic_guidance"]:
            story.append(
                Paragraph(
                    f"<b>{_safe_text(item['title'])}:</b> {_safe_text(item['text'])}",
                    body_style,
                )
            )

    story.append(
        Paragraph(
            "Important Note",
            heading_style,
        )
    )
    story.append(
        Paragraph(
            _safe_text(result["disclaimer"]),
            small_style,
        )
    )

    document.build(story)
    return output_path
