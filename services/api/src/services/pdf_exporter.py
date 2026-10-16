import io
from datetime import datetime
from typing import Any, Sequence
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class PDFReportGenerator:
    def generate_line_report(self, line_id: str, records: Sequence[dict[str, Any]]) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )
        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            name="TitleStyle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=12,
        )
        elements.append(Paragraph("Lihat.id Poultry Counter - Production Report", title_style))
        elements.append(
            Paragraph(
                f"Line ID: <b>{line_id}</b> | Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
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

        # Details Table
        table_data = [["Interval Start", "Count", "Speed (cpm)", "Status"]]
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
            table_data.append(
                [
                    ws_str,
                    str(cnt),
                    str(round(rate, 1)),
                    str(status),
                ]
            )

        records_table = Table(table_data, colWidths=[180, 100, 120, 100])
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

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
