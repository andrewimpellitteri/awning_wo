from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from io import BytesIO
from datetime import datetime


class WorkOrderPDF:
    def __init__(self, work_order_dict, company_info=None):
        self.work_order = work_order_dict
        self.company_info = company_info or {
            "name": "Awning Cleaning Industries - In House Cleaning Work Order"
        }
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        self.styles.add(
            ParagraphStyle(
                name="CompanyName",
                parent=self.styles["Normal"],
                fontSize=14,
                spaceAfter=0.02 * inch,
                alignment=TA_CENTER,
                textColor=colors.black,
                fontName="Helvetica-Bold",
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SmallLabel",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=colors.black,
                fontName="Helvetica-Bold",
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SmallValue",
                parent=self.styles["Normal"],
                fontSize=9,
                textColor=colors.black,
                fontName="Helvetica",
            )
        )

    def _format_date(self, date_str):
        if not date_str:
            return ""
        try:
            if isinstance(date_str, str) and len(date_str) >= 10:
                date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                return date_obj.strftime("%m/%d/%Y")
            return str(date_str)
        except Exception:
            return str(date_str)

    def _build_header(self):
        return [
            Paragraph(self.company_info["name"], self.styles["CompanyName"]),
            Spacer(1, 0.15 * inch),
        ]

    def _build_customer_info_section(self):
        wo = self.work_order
        customer = wo.get("customer", {})
        source = wo.get("source", {})

        # --- Customer block ---
        cust_data = [
            [
                Paragraph("Customer", self.styles["SmallLabel"]),
                Paragraph(customer.get("Name", ""), self.styles["SmallValue"]),
                Paragraph("Phone", self.styles["SmallLabel"]),
                Paragraph(customer.get("PrimaryPhone", ""), self.styles["SmallValue"]),
            ],
            [
                Paragraph("Address", self.styles["SmallLabel"]),
                Paragraph(customer.get("FullAddress", ""), self.styles["SmallValue"]),
                Paragraph("Email", self.styles["SmallLabel"]),
                Paragraph(customer.get("Email", ""), self.styles["SmallValue"]),
            ],
        ]
        cust_table = Table(
            cust_data, colWidths=[1 * inch, 2.5 * inch, 1 * inch, 2.5 * inch]
        )
        cust_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )

        # --- Source block ---
        src_data = [
            [
                Paragraph("Source", self.styles["SmallLabel"]),
                Paragraph(source.get("Name", ""), self.styles["SmallValue"]),
                Paragraph("Phone", self.styles["SmallLabel"]),
                Paragraph(source.get("Phone", ""), self.styles["SmallValue"]),
            ],
            [
                Paragraph("Address", self.styles["SmallLabel"]),
                Paragraph(source.get("FullAddress", ""), self.styles["SmallValue"]),
                Paragraph("Email", self.styles["SmallLabel"]),
                Paragraph(source.get("Email", ""), self.styles["SmallValue"]),
            ],
        ]
        src_table = Table(
            src_data, colWidths=[1 * inch, 2.5 * inch, 1 * inch, 2.5 * inch]
        )
        src_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )

        return [
            Paragraph("Customer Information", self.styles["SmallLabel"]),
            Spacer(1, 0.05 * inch),
            cust_table,
            Spacer(1, 0.15 * inch),
            Paragraph("Source Information", self.styles["SmallLabel"]),
            Spacer(1, 0.05 * inch),
            src_table,
            Spacer(1, 0.15 * inch),
        ]

    def _build_work_order_info_section(self):
        wo = self.work_order
        data = [
            [
                Paragraph("Work Order Number", self.styles["SmallLabel"]),
                Paragraph(str(wo.get("WorkOrderNo", "")), self.styles["SmallValue"]),
                Paragraph("Customer ID", self.styles["SmallLabel"]),
                Paragraph(str(wo.get("CustID", "")), self.styles["SmallValue"]),
            ],
            [
                Paragraph("Storage", self.styles["SmallLabel"]),
                Paragraph(wo.get("Storage", ""), self.styles["SmallValue"]),
                Paragraph("Storage Time", self.styles["SmallLabel"]),
                Paragraph(wo.get("StorageTime", ""), self.styles["SmallValue"]),
            ],
            [
                Paragraph("Rack #", self.styles["SmallLabel"]),
                Paragraph(wo.get("RackNo", ""), self.styles["SmallValue"]),
                Paragraph("Source", self.styles["SmallLabel"]),
                Paragraph(wo.get("Source", ""), self.styles["SmallValue"]),
            ],
            [
                Paragraph("Special Instructions", self.styles["SmallLabel"]),
                Paragraph(wo.get("SpecialInstructions", ""), self.styles["SmallValue"]),
                "",
                "",
            ],
            [
                Paragraph("Repairs Needed", self.styles["SmallLabel"]),
                Paragraph(wo.get("Repairs", "-"), self.styles["SmallValue"]),
                "",
                "",
            ],
            [
                Paragraph("Date Required", self.styles["SmallLabel"]),
                Paragraph(
                    self._format_date(wo.get("DateRequired")), self.styles["SmallValue"]
                ),
                Paragraph("Date In", self.styles["SmallLabel"]),
                Paragraph(
                    self._format_date(wo.get("DateIn")), self.styles["SmallValue"]
                ),
            ],
            [
                Paragraph("Date Completed", self.styles["SmallLabel"]),
                Paragraph(
                    self._format_date(wo.get("DateCompleted")),
                    self.styles["SmallValue"],
                ),
                Paragraph("Clean", self.styles["SmallLabel"]),
                Paragraph(
                    self._format_date(wo.get("Clean")), self.styles["SmallValue"]
                ),
            ],
            [
                Paragraph("Treat", self.styles["SmallLabel"]),
                Paragraph(
                    self._format_date(wo.get("Treat")), self.styles["SmallValue"]
                ),
                Paragraph("Clean First WO", self.styles["SmallLabel"]),
                Paragraph(
                    "Yes" if wo.get("CleanFirstWO") == "1" else "No",
                    self.styles["SmallValue"],
                ),
            ],
            [
                Paragraph("Rush Order", self.styles["SmallLabel"]),
                Paragraph(
                    "Yes" if wo.get("RushOrder") == "1" else "No",
                    self.styles["SmallValue"],
                ),
                Paragraph("Firm Rush", self.styles["SmallLabel"]),
                Paragraph(
                    "Yes" if wo.get("FirmRush") == "1" else "No",
                    self.styles["SmallValue"],
                ),
            ],
        ]
        table = Table(data, colWidths=[1.2 * inch, 2 * inch, 1.2 * inch, 2 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return [
            Paragraph("Work Order Information", self.styles["SmallLabel"]),
            Spacer(1, 0.05 * inch),
            table,
            Spacer(1, 0.15 * inch),
        ]

    def _build_items_section(self):
        items = self.work_order.get("items", [])
        header = [
            Paragraph("Qty", self.styles["SmallLabel"]),
            Paragraph("Description", self.styles["SmallLabel"]),
            Paragraph("Material", self.styles["SmallLabel"]),
            Paragraph("Condition", self.styles["SmallLabel"]),
            Paragraph("Color", self.styles["SmallLabel"]),
            Paragraph("Size/Wgt", self.styles["SmallLabel"]),
            Paragraph("Price", self.styles["SmallLabel"]),
        ]
        rows = []
        for item in items:
            price = ""
            if item.get("Price"):
                try:
                    price = f"${float(item['Price']):.2f}"
                except:
                    price = str(item["Price"])
            rows.append(
                [
                    str(item.get("Qty", "")),
                    str(item.get("Description", "")),
                    str(item.get("Material", "")),
                    str(item.get("Condition", "")),
                    str(item.get("Color", "")),
                    str(item.get("SizeWgt", "")),
                    price,
                ]
            )
        while len(rows) < 12:
            rows.append([""] * 7)
        table = Table(
            [header] + rows,
            colWidths=[
                0.4 * inch,
                1.4 * inch,
                0.7 * inch,
                0.7 * inch,
                0.8 * inch,
                1.2 * inch,
                0.8 * inch,
            ],
        )
        table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ]
            )
        )
        return [
            Paragraph("Order Items", self.styles["SmallLabel"]),
            Spacer(1, 0.05 * inch),
            table,
        ]

    def generate_pdf(self, filename=None):
        buffer = None
        if filename:
            doc = SimpleDocTemplate(
                filename,
                pagesize=letter,
                rightMargin=0.5 * inch,
                leftMargin=0.5 * inch,
                topMargin=0.5 * inch,
                bottomMargin=0.5 * inch,
            )
        else:
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=0.5 * inch,
                leftMargin=0.5 * inch,
                topMargin=0.5 * inch,
                bottomMargin=0.5 * inch,
            )

        story = []
        story += self._build_header()
        story += self._build_customer_info_section()
        story += self._build_work_order_info_section()
        story += self._build_items_section()

        doc.build(story)
        if filename:
            return filename
        else:
            buffer.seek(0)
            return buffer


def generate_work_order_pdf(work_order, company_info=None, filename=None):
    pdf = WorkOrderPDF(work_order, company_info)
    return pdf.generate_pdf(filename)
