import html
import io
from datetime import datetime
from typing import Any, Sequence
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class PDFReportGenerator:
    def _build_elements(
        self,
        line_id: str,
        records: Sequence[dict[str, Any]],
        is_multi_line: bool | None = None,
    ) -> list[Any]:
        elements: list[Any] = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            name="TitleStyle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=12,
        )
        elements.append(Paragraph("Lihat.id Poultry Counter - Production Report", title_style))
        escaped_line_id = html.escape(str(line_id))
        elements.append(
            Paragraph(
                f"Line ID: <b>{escaped_line_id}</b> | Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles["Normal"],
            )
        )
        elements.append(Spacer(1, 16))

        # Summary
        total_count = sum((r.get("count") or 0) for r in records)
        avg_rate = (
            round(sum((r.get("rate_per_min") or 0) for r in records) / len(records), 1)
            if records
            else 0
        )

        summary_data = [
            ["Metric", "Value"],
            ["Total Birds Counted", str(total_count)],
            ["Average Speed (chickens/min)", f"{avg_rate} cpm"],
            ["Total Intervals", str(len(records))],
        ]
        summary_table = Table(summary_data, colWidths=[200, 200])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0284c7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ]
            )
        )
        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        if is_multi_line is None:
            is_multi_line = str(line_id).lower() in ("semua lini", "all") or any(
                r.get("line_id") for r in records
            )

        # Details Table
        if is_multi_line:
            table_data = [["Interval Start", "Line", "Count", "Speed (cpm)", "Status"]]
            col_widths = [120, 90, 80, 90, 80]
        else:
            table_data = [["Interval Start", "Count", "Speed (cpm)", "Status"]]
            col_widths = [180, 100, 120, 100]

        for r in records[:50]:  # limit for PDF layout
            ws = r.get("window_start")
            if hasattr(ws, "strftime"):
                ws_str = ws.strftime("%Y-%m-%d %H:%M")
            elif ws is not None:
                ws_str = str(ws)
            else:
                ws_str = ""
            cnt = r.get("count") or 0
            rate = r.get("rate_per_min") or 0
            status = r.get("status") or "NORMAL"
            if is_multi_line:
                line_val = str(r.get("line_id") or line_id)
                table_data.append(
                    [
                        ws_str,
                        line_val,
                        str(cnt),
                        str(round(rate, 1)),
                        str(status),
                    ]
                )
            else:
                table_data.append(
                    [
                        ws_str,
                        str(cnt),
                        str(round(rate, 1)),
                        str(status),
                    ]
                )

        records_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        records_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ]
            )
        )
        elements.append(records_table)

        if len(records) > 50:
            elements.append(Spacer(1, 8))
            footnote_style = ParagraphStyle(
                name="FootnoteStyle",
                parent=styles["Italic"],
                fontSize=8,
                textColor=colors.HexColor("#64748b"),
            )
            elements.append(
                Paragraph(
                    "<i>Note: Showing first 50 intervals. Full data can be exported via XLSX.</i>",
                    footnote_style,
                )
            )

        return elements

    def generate_line_report(self, line_id: str, records: Sequence[dict[str, Any]]) -> bytes:
        is_multi_line = str(line_id).lower() in ("semua lini", "all") or any(
            r.get("line_id") for r in records
        )
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )
        elements = self._build_elements(line_id=line_id, records=records, is_multi_line=is_multi_line)
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
