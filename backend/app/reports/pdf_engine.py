"""
PDF export engine using ReportLab.

Generates professional PDF reports with company-branded headers, footers,
logos, color schemes, tables, and charts support.
"""

import os
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape, letter, legal
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.frames import Frame
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate

from app.reports.constants import DEFAULT_TEMPLATE_CONFIG

# ---------------------------------------------------------------------------
# Page Size Map
# ---------------------------------------------------------------------------

PAGE_SIZE_MAP = {
    "A4": A4,
    "Letter": letter,
    "Legal": legal,
}


class PDFReportEngine:
    """
    Professional PDF report generator using ReportLab.

    Supports branded headers/footers, tables, charts placeholders,
    multi-page documents with automatic pagination.
    """

    def __init__(self, template_config: Optional[Dict[str, Any]] = None):
        self.config = {**DEFAULT_TEMPLATE_CONFIG, **(template_config or {})}
        self.colors = self._build_colors()
        self.styles = self._build_styles()
        self.logo_path: Optional[str] = None

    def _build_colors(self) -> Dict[str, colors.Color]:
        """Build ReportLab color objects from hex config."""

        def hex_to_color(hex_str: str) -> colors.Color:
            hex_str = hex_str.lstrip("#")
            r, g, b = int(hex_str[0:2], 16) / 255, int(hex_str[2:4], 16) / 255, int(hex_str[4:6], 16) / 255
            return colors.Color(r, g, b)

        return {
            "primary": hex_to_color(self.config.get("primary_color", "#2563EB")),
            "secondary": hex_to_color(self.config.get("secondary_color", "#1E40AF")),
            "accent": hex_to_color(self.config.get("accent_color", "#3B82F6")),
            "text": hex_to_color(self.config.get("text_color", "#1F2937")),
            "light_bg": hex_to_color(self.config.get("light_bg", "#F3F4F6")),
            "white": hex_to_color(self.config.get("white", "#FFFFFF")),
        }

    def _build_styles(self) -> Dict[str, ParagraphStyle]:
        """Build paragraph styles from template config."""
        font = self.config.get("font_family", "Helvetica")
        text_color = self.colors["text"]
        primary = self.colors["primary"]

        return {
            "title": ParagraphStyle(
                "CustomTitle",
                fontName=f"{font}-Bold",
                fontSize=self.config.get("title_font_size", 18),
                textColor=primary,
                spaceAfter=16,
                leading=22,
            ),
            "subtitle": ParagraphStyle(
                "CustomSubtitle",
                fontName=font,
                fontSize=self.config.get("subtitle_font_size", 12),
                textColor=text_color,
                spaceAfter=12,
                leading=16,
            ),
            "heading1": ParagraphStyle(
                "CustomH1",
                fontName=f"{font}-Bold",
                fontSize=14,
                textColor=primary,
                spaceAfter=10,
                spaceBefore=12,
                leading=18,
            ),
            "heading2": ParagraphStyle(
                "CustomH2",
                fontName=f"{font}-Bold",
                fontSize=12,
                textColor=text_color,
                spaceAfter=8,
                spaceBefore=10,
                leading=15,
            ),
            "body": ParagraphStyle(
                "CustomBody",
                fontName=font,
                fontSize=self.config.get("body_font_size", 9),
                textColor=text_color,
                spaceAfter=6,
                leading=12,
            ),
            "body_small": ParagraphStyle(
                "CustomBodySmall",
                fontName=font,
                fontSize=8,
                textColor=text_color,
                spaceAfter=4,
                leading=10,
            ),
            "right_aligned": ParagraphStyle(
                "CustomRight",
                fontName=font,
                fontSize=8,
                textColor=text_color,
                alignment=TA_RIGHT,
            ),
            "center_aligned": ParagraphStyle(
                "CustomCenter",
                fontName=font,
                fontSize=8,
                textColor=text_color,
                alignment=TA_CENTER,
            ),
            "footer": ParagraphStyle(
                "CustomFooter",
                fontName=font,
                fontSize=8,
                textColor=colors.grey,
                alignment=TA_CENTER,
            ),
            "table_header": ParagraphStyle(
                "CustomTableHeader",
                fontName=f"{font}-Bold",
                fontSize=9,
                textColor=self.colors["white"],
                alignment=TA_LEFT,
            ),
            "table_cell": ParagraphStyle(
                "CustomTableCell",
                fontName=font,
                fontSize=8,
                textColor=text_color,
                alignment=TA_LEFT,
            ),
        }

    def set_logo(self, logo_path: Optional[str]) -> None:
        """Set company logo path for header branding."""
        self.logo_path = logo_path

    # ------------------------------------------------------------------
    # Header / Footer Drawing
    # ------------------------------------------------------------------

    def _header_footer(self, canvas, doc):
        """Draw branded header and footer on each page."""
        canvas.saveState()
        page_width, page_height = PAGE_SIZE_MAP.get(
            self.config.get("page_size", "A4"), A4
        )

        # --- Header ---
        header_top = page_height - 36

        if self.config.get("header_line", True):
            canvas.setStrokeColor(self.colors["primary"])
            canvas.setLineWidth(1.5)
            canvas.line(36, header_top - 4, page_width - 36, header_top - 4)

        # Logo
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                logo_w = self.config.get("logo_width", 120) * mm / 4
                logo_h = self.config.get("logo_height", 40) * mm / 4
                canvas.drawImage(
                    self.logo_path,
                    36,
                    header_top - logo_h - 6,
                    width=logo_w,
                    height=logo_h,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception:
                pass  # Logo hatasi sessizce gec

        # Report title in header
        title_text = getattr(doc, "_report_title", "Report")
        canvas.setFont(f"{self.config.get('font_family', 'Helvetica')}-Bold", 10)
        canvas.setFillColor(self.colors["primary"])
        canvas.drawString(160, header_top - 15, title_text)

        # Generated at
        if self.config.get("show_generated_at", True):
            canvas.setFont(self.config.get("font_family", "Helvetica"), 7)
            canvas.setFillColor(colors.grey)
            gen_text = f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            canvas.drawRightString(page_width - 36, header_top - 15, gen_text)

        # --- Footer ---
        footer_bottom = 30

        if self.config.get("footer_line", True):
            canvas.setStrokeColor(self.colors["light_bg"])
            canvas.setLineWidth(0.5)
            canvas.line(36, footer_bottom + 12, page_width - 36, footer_bottom + 12)

        footer_text = self.config.get("footer_text", "Generated by Report Engine")
        canvas.setFont(self.config.get("font_family", "Helvetica"), 7)
        canvas.setFillColor(colors.grey)

        # Footer text (left)
        canvas.drawString(36, footer_bottom, footer_text)

        # Page numbers (right)
        if self.config.get("show_page_numbers", True):
            page_num = f"Page {canvas.getPageNumber()}"
            canvas.drawRightString(page_width - 36, footer_bottom, page_num)

        # Watermark
        if self.config.get("watermark_text"):
            canvas.setFont(f"{self.config.get('font_family', 'Helvetica')}-Bold", 40)
            canvas.setFillColor(colors.Color(0.85, 0.85, 0.85, alpha=0.3))
            canvas.saveState()
            canvas.translate(page_width / 2, page_height / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, self.config["watermark_text"])
            canvas.restoreState()

        canvas.restoreState()

    # ------------------------------------------------------------------
    # Build Document
    # ------------------------------------------------------------------

    def generate(
        self,
        output_path: str,
        title: str,
        subtitle: Optional[str] = None,
        sections: Optional[List[Dict[str, Any]]] = None,
        tables: Optional[List[Dict[str, Any]]] = None,
        summary_stats: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Generate a complete PDF report.

        Args:
            output_path: Full file path for the output PDF.
            title: Report title.
            subtitle: Optional subtitle text.
            sections: List of text sections [{"heading": str, "content": str}].
            tables: List of tables [{"title": str, "headers": [...], "rows": [[...]]}].
            summary_stats: List of key-value stat pairs [{"label": str, "value": str}].

        Returns:
            output_path on success.
        """
        page_size_key = self.config.get("page_size", "A4")
        orientation_key = self.config.get("orientation", "portrait")
        page_size = PAGE_SIZE_MAP.get(page_size_key, A4)
        if orientation_key == "landscape":
            page_size = landscape(page_size)

        # Build document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=page_size,
            topMargin=self.config.get("margin_top", 72),
            bottomMargin=self.config.get("margin_bottom", 72),
            leftMargin=self.config.get("margin_left", 72),
            rightMargin=self.config.get("margin_right", 72),
            title=title,
            author="Report Engine",
        )

        # Store title for header callback
        doc._report_title = title

        story: List[Any] = []

        # --- Title ---
        story.append(Paragraph(title, self.styles["title"]))
        if subtitle:
            story.append(Paragraph(subtitle, self.styles["subtitle"]))
        story.append(Spacer(1, 12))

        # --- Summary Stats ---
        if summary_stats:
            story.append(self._build_stats_table(summary_stats))
            story.append(Spacer(1, 16))

        # --- Sections ---
        if sections:
            for section in sections:
                story.append(self._render_section(section))

        # --- Tables ---
        if tables:
            for table_data in tables:
                story.append(self._render_table(table_data))
                story.append(Spacer(1, 12))

        # Build with header/footer
        doc.build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        return output_path

    def _build_stats_table(self, stats: List[Dict[str, Any]]) -> Table:
        """Build a summary statistics row as a colored table."""
        data = [[s["label"] for s in stats], [s["value"] for s in stats]]

        col_count = len(stats)
        col_width = (A4[0] - 144) / col_count  # minus margins

        t = Table(data, colWidths=[col_width] * col_count)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.colors["primary"]),
                    ("TEXTCOLOR", (0, 0), (-1, 0), self.colors["white"]),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), f"{self.config.get('font_family', 'Helvetica')}-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 8),
                    ("FONTNAME", (0, 1), (-1, 1), f"{self.config.get('font_family', 'Helvetica')}-Bold"),
                    ("FONTSIZE", (0, 1), (-1, 1), 12),
                    ("TEXTCOLOR", (0, 1), (-1, 1), self.colors["primary"]),
                    ("BACKGROUND", (0, 1), (-1, 1), self.colors["light_bg"]),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, self.colors["light_bg"]),
                ]
            )
        )
        return t

    def _render_section(self, section: Dict[str, Any]) -> List[Any]:
        """Render a text section with heading and paragraphs."""
        elements: List[Any] = []
        heading = section.get("heading")
        content = section.get("content", "")

        if heading:
            elements.append(Paragraph(heading, self.styles["heading1"]))

        if isinstance(content, list):
            for para in content:
                elements.append(Paragraph(str(para), self.styles["body"]))
        elif content:
            elements.append(Paragraph(str(content), self.styles["body"]))

        elements.append(Spacer(1, 8))
        return elements

    def _render_table(self, table_data: Dict[str, Any]) -> List[Any]:
        """Render a data table with headers and rows."""
        elements: List[Any] = []

        title = table_data.get("title")
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])

        if title:
            elements.append(Paragraph(title, self.styles["heading2"]))

        if not headers or not rows:
            elements.append(Paragraph("No data available.", self.styles["body_small"]))
            return elements

        # Build table data
        data = [headers] + rows

        # Calculate column widths
        page_width = PAGE_SIZE_MAP.get(self.config.get("page_size", "A4"), A4)[0]
        usable_width = page_width - self.config.get("margin_left", 72) - self.config.get("margin_right", 72)
        col_count = len(headers)
        col_width = usable_width / col_count

        # Wrap cell content in Paragraphs for text wrapping
        styled_data = []
        for i, row in enumerate(data):
            styled_row = []
            for cell in row:
                if i == 0:
                    styled_row.append(Paragraph(str(cell), self.styles["table_header"]))
                else:
                    styled_row.append(Paragraph(str(cell), self.styles["table_cell"]))
            styled_data.append(styled_row)

        t = Table(styled_data, colWidths=[col_width] * col_count, repeatRows=1)

        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), self.colors["primary"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), self.colors["white"]),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, 0), f"{self.config.get('font_family', 'Helvetica')}-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, self.colors["light_bg"]),
        ]

        # Alternate row colors
        for i in range(1, len(styled_data)):
            if i % 2 == 0:
                style_commands.append(
                    ("BACKGROUND", (0, i), (-1, i), self.colors["light_bg"])
                )

        t.setStyle(TableStyle(style_commands))
        elements.append(t)
        elements.append(Spacer(1, 8))

        return elements

    def generate_from_buffer(
        self,
        **kwargs: Any,
    ) -> BytesIO:
        """Generate PDF into a BytesIO buffer instead of a file."""
        buffer = BytesIO()
        # Save original path, override temporarily
        original_path = kwargs.pop("output_path", None)

        page_size_key = self.config.get("page_size", "A4")
        orientation_key = self.config.get("orientation", "portrait")
        page_size = PAGE_SIZE_MAP.get(page_size_key, A4)
        if orientation_key == "landscape":
            page_size = landscape(page_size)

        doc = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            topMargin=self.config.get("margin_top", 72),
            bottomMargin=self.config.get("margin_bottom", 72),
            leftMargin=self.config.get("margin_left", 72),
            rightMargin=self.config.get("margin_right", 72),
            title=kwargs.get("title", "Report"),
        )
        doc._report_title = kwargs.get("title", "Report")

        story: List[Any] = []
        title = kwargs.get("title", "Report")
        subtitle = kwargs.get("subtitle")
        sections = kwargs.get("sections")
        tables = kwargs.get("tables")
        summary_stats = kwargs.get("summary_stats")

        story.append(Paragraph(title, self.styles["title"]))
        if subtitle:
            story.append(Paragraph(subtitle, self.styles["subtitle"]))
        story.append(Spacer(1, 12))

        if summary_stats:
            story.append(self._build_stats_table(summary_stats))
            story.append(Spacer(1, 16))

        if sections:
            for section in sections:
                story.extend(self._render_section(section))

        if tables:
            for table_data in tables:
                story.extend(self._render_table(table_data))

        doc.build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        buffer.seek(0)
        return buffer
