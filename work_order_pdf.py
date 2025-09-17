from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from io import BytesIO
from datetime import datetime


def safe_paragraph(text, style, field_name=None):
    """Wrap Paragraph creation and log the value being passed."""
    import sys

    if text is None:
        text = ""
    try:
        para = Paragraph(str(text), style)
        # Debug log
        print(
            f"[DEBUG] Paragraph created for '{field_name}': '{text}'", file=sys.stderr
        )
        return para
    except Exception as e:
        print(
            f"[ERROR] Paragraph failed for '{field_name}': {repr(text)} -> {e}",
            file=sys.stderr,
        )
        # Return an empty paragraph so PDF still builds
        return Paragraph("", style)


class WorkOrderPDF:
    def __init__(self, work_order_dict, company_info=None):
        self.work_order = work_order_dict
        self.company_info = company_info or {
            "name": "Awning Cleaning Industries - In House Cleaning Work Order"
        }
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        # Company name style - larger and centered
        self.styles.add(
            ParagraphStyle(
                name="CompanyName",
                parent=self.styles["Normal"],
                fontSize=12,
                spaceAfter=0.1 * inch,
                alignment=TA_CENTER,
                textColor=colors.black,
                fontName="Helvetica-Bold",
            )
        )

        # Small labels for field names
        self.styles.add(
            ParagraphStyle(
                name="SmallLabel",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=colors.black,
                fontName="Helvetica",
            )
        )

        # Values - slightly larger than labels
        self.styles.add(
            ParagraphStyle(
                name="SmallValue",
                parent=self.styles["Normal"],
                fontSize=9,
                textColor=colors.black,
                fontName="Helvetica-Bold",
            )
        )

        # Table header style
        self.styles.add(
            ParagraphStyle(
                name="TableHeader",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=colors.black,
                fontName="Helvetica-Bold",
                alignment=TA_CENTER,
            )
        )

        # Table cell style
        self.styles.add(
            ParagraphStyle(
                name="TableCell",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=colors.black,
                fontName="Helvetica",
                alignment=TA_CENTER,
            )
        )

    def _format_date(self, date_str):
        if not date_str:
            return ""
        try:
            # Handle string input
            if isinstance(date_str, str):
                # Try to parse MM/DD/YY HH:MM:SS
                try:
                    date_obj = datetime.strptime(date_str, "%m/%d/%y %H:%M:%S")
                    return date_obj.strftime("%m/%d/%y")
                except ValueError:
                    # If it doesn't match, just return raw
                    return date_str

            # Handle datetime input directly
            if isinstance(date_str, datetime):
                return date_str.strftime("%m/%d/%y")

            return str(date_str)

        except Exception:
            return str(date_str)

    def _build_header_with_wo_number(self):
        """Build header with work order number prominently displayed with blue background and hline"""
        wo_number = "WO#" + str(self.work_order.get("WorkOrderNo", ""))

        # Create a table for the header layout
        header_data = [
            [
                safe_paragraph(self.company_info["name"], self.styles["CompanyName"]),
                "",
                safe_paragraph(
                    wo_number,
                    ParagraphStyle(
                        name="WONumber",
                        parent=self.styles["Normal"],
                        fontSize=14,
                        fontName="Helvetica-Bold",
                        alignment=TA_RIGHT,
                    ),
                ),
            ]
        ]

        header_table = Table(header_data, colWidths=[4 * inch, 1 * inch, 2 * inch])
        header_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.lightblue,
                    ),  # Blue background
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),  # White text
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (0, 0), "CENTER"),
                    ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    (
                        "LINEBELOW",
                        (0, 0),
                        (-1, 0),
                        1,
                        colors.black,
                    ),  # Horizontal line below
                ]
            )
        )

        return [header_table, Spacer(1, 0.1 * inch)]

    def _build_top_section(self):
        """Build a clean, professional top section with dates and customer info"""
        wo = self.work_order
        customer = wo.get("customer", {})

        # --- Top row: Date & Order Info ---
        date_order_data = [
            [
                safe_paragraph("Customer ID", self.styles["SmallLabel"]),
                safe_paragraph(str(wo.get("CustID", "")), self.styles["SmallValue"]),
                safe_paragraph("Rush Order", self.styles["SmallLabel"]),
                safe_paragraph(
                    "Yes" if wo.get("RushOrder") == "1" else "No",
                    self.styles["SmallValue"],
                ),
            ],
            [
                safe_paragraph("Date Required", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(wo.get("DateRequired")), self.styles["SmallValue"]
                ),
                safe_paragraph("Firm Rush", self.styles["SmallLabel"]),
                safe_paragraph(
                    "Yes" if wo.get("FirmRush") == "1" else "No",
                    self.styles["SmallValue"],
                ),
            ],
        ]

        date_order_table = Table(
            date_order_data, colWidths=[1.2 * inch, 2 * inch, 1.2 * inch, 2 * inch]
        )
        date_order_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("ALIGN", (3, 0), (3, -1), "LEFT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        # --- Customer Address ---
        address_data = [
            [
                safe_paragraph("Name", self.styles["SmallLabel"]),
                safe_paragraph(customer.get("Name", ""), self.styles["SmallValue"]),
                safe_paragraph("Contact", self.styles["SmallLabel"]),
                safe_paragraph(customer.get("Contact", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Address", self.styles["SmallLabel"]),
                safe_paragraph(customer.get("Address", ""), self.styles["SmallValue"]),
                safe_paragraph("Address2", self.styles["SmallLabel"]),
                safe_paragraph(customer.get("Address2", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("City", self.styles["SmallLabel"]),
                safe_paragraph(customer.get("City", ""), self.styles["SmallValue"]),
                safe_paragraph("State", self.styles["SmallLabel"]),
                safe_paragraph(
                    customer.get("State", "").upper(), self.styles["SmallValue"]
                ),
            ],
            [
                safe_paragraph("Zip", self.styles["SmallLabel"]),
                safe_paragraph(
                    customer.get("ZipCode", "").strip("-"), self.styles["SmallValue"]
                ),
                "",
                "",
            ],
        ]

        address_table = Table(
            address_data, colWidths=[1 * inch, 2.2 * inch, 1 * inch, 2.2 * inch]
        )
        address_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        # --- Phone & Email ---
        phone_data = [
            [
                safe_paragraph("Cell Phone", self.styles["SmallLabel"]),
                safe_paragraph(
                    customer.get("CellPhone", ""), self.styles["SmallValue"]
                ),
                safe_paragraph("Home Phone", self.styles["SmallLabel"]),
                safe_paragraph(
                    customer.get("HomePhone", ""), self.styles["SmallValue"]
                ),
            ],
            [
                safe_paragraph("Work Phone", self.styles["SmallLabel"]),
                safe_paragraph(
                    customer.get("WorkPhone", ""), self.styles["SmallValue"]
                ),
                safe_paragraph("Email", self.styles["SmallLabel"]),
                safe_paragraph(
                    customer.get("EmailAddress", ""), self.styles["SmallValue"]
                ),
            ],
        ]

        phone_table = Table(
            phone_data, colWidths=[1 * inch, 2 * inch, 1 * inch, 2 * inch]
        )
        phone_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        return [
            date_order_table,
            Spacer(1, 0.1 * inch),
            address_table,
            Spacer(1, 0.1 * inch),
            phone_table,
            Spacer(1, 0.2 * inch),
        ]

    def _build_middle_section(self):
        """Build a clean, professional middle section with work order details"""
        wo = self.work_order

        # --- Combine left & right info in one table ---
        middle_data = [
            [
                safe_paragraph("StorageRack#", self.styles["SmallLabel"]),
                safe_paragraph(wo.get("Storage", ""), self.styles["SmallValue"]),
                safe_paragraph("Rack No", self.styles["SmallLabel"]),
                safe_paragraph(wo.get("RackNo", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Storage", self.styles["SmallLabel"]),
                safe_paragraph(wo.get("StorageTime", ""), self.styles["SmallValue"]),
                safe_paragraph("Date In", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(wo.get("DateIn")), self.styles["SmallValue"]
                ),
            ],
        ]

        middle_table = Table(
            middle_data, colWidths=[1.2 * inch, 2.0 * inch, 1.2 * inch, 2.0 * inch]
        )
        middle_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("ALIGN", (3, 0), (3, -1), "LEFT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        return [middle_table, Spacer(1, 0.15 * inch)]

    def _build_source_line(self):
        """Build the source line"""
        wo = self.work_order

        cust = wo.get("customer", {})

        source_fields = [
            "Source",
            "SourceAddress",
            "SourceCity",
            "SourceState",
            "SourceZip",
        ]

        # Convert all to strings, strip whitespace, ignore empty/None values
        safe_values = [
            str(cust.get(field) or "").strip()
            for field in source_fields
            if cust.get(field)
        ]
        source_str = " ".join(safe_values)

        # Final fallback
        if not source_str:
            source_str = "N/A"

        # Make sure Paragraph always gets a plain string
        source_para = safe_paragraph(source_str, self.styles["SmallValue"])

        source_data = [
            [
                safe_paragraph("Source:", self.styles["SmallLabel"]),
                source_para,
            ]
        ]

        source_table = Table(source_data, colWidths=[0.8 * inch, 1.5 * inch])
        source_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        return [source_table, Spacer(1, 0.1 * inch)]

    def _build_items_table(self):
        """Build a clean, professional items table"""
        items = self.work_order.get("items", [])

        # --- Table headers ---
        headers = [
            safe_paragraph("Qty", self.styles["TableHeader"]),
            safe_paragraph("Description", self.styles["TableHeader"]),
            safe_paragraph("Material", self.styles["TableHeader"]),
            safe_paragraph("Condition", self.styles["TableHeader"]),
            safe_paragraph("Color", self.styles["TableHeader"]),
            safe_paragraph("Size/Wgt", self.styles["TableHeader"]),
            safe_paragraph("Price", self.styles["TableHeader"]),
        ]

        # --- Build rows ---
        rows = [headers]
        for item in items:
            # Format price
            price = ""
            if item.get("Price"):
                try:
                    price_val = str(item.get("Price"))
                    if "=" in price_val:
                        price = price_val  # Preserve D=153.86' style
                    else:
                        price = f"${float(price_val):.2f}"
                except:
                    price = str(item.get("Price"))

            row = [
                safe_paragraph(str(item.get("Qty", "")), self.styles["TableCell"]),
                safe_paragraph(
                    str(item.get("Description", "")), self.styles["TableCell"]
                ),
                safe_paragraph(str(item.get("Material", "")), self.styles["TableCell"]),
                safe_paragraph(
                    str(item.get("Condition", "")), self.styles["TableCell"]
                ),
                safe_paragraph(str(item.get("Color", "")), self.styles["TableCell"]),
                safe_paragraph(str(item.get("SizeWgt", "")), self.styles["TableCell"]),
                safe_paragraph(price, self.styles["TableCell"]),
            ]
            rows.append(row)

        # --- Define column widths ---
        col_widths = [
            0.6 * inch,
            2.2 * inch,
            1.0 * inch,
            1.0 * inch,
            1.0 * inch,
            1.2 * inch,
            1.2 * inch,
        ]

        items_table = Table(rows, colWidths=col_widths, repeatRows=1)
        items_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 1), (0, -1), "RIGHT"),  # Qty right
                    ("ALIGN", (5, 1), (5, -1), "RIGHT"),  # Size/Wgt right
                    ("ALIGN", (6, 1), (6, -1), "RIGHT"),  # Price right
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),  # header
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("LINEABOVE", (0, 0), (-1, 0), 1, colors.black),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
                    (
                        "GRID",
                        (0, 1),
                        (-1, -1),
                        0.25,
                        colors.grey,
                    ),  # light grid for body
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.whitesmoke],
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        return [items_table, Spacer(1, 0.2 * inch)]

    def _build_footer(self):
        """Build footer with professional layout and space for notes"""
        wo = self.work_order

        # --- Special Instructions (no box, just blank space for notes) ---
        special_instructions = [
            [
                safe_paragraph("Special<br/>Instructions", self.styles["SmallLabel"]),
                safe_paragraph(
                    wo.get("SpecialInstructions", ""), self.styles["SmallValue"]
                ),
            ]
        ]
        # Add extra blank rows for notes
        for _ in range(6):
            special_instructions.append(
                ["", safe_paragraph("", self.styles["SmallValue"])]
            )

        special_instructions_table = Table(
            special_instructions,
            colWidths=[
                1.0 * inch,  # Reduced from 1.2
                5.5 * inch,  # Increased writing space, fits within page margins
            ],
            rowHeights=[0.3 * inch] + [0.25 * inch] * 6,
        )
        special_instructions_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (1, 0), (1, -1), 2),
                    ("RIGHTPADDING", (1, 0), (1, -1), 2),
                ]
            )
        )

        # --- Repairs / Status Footer (Split into two rows for better fit) ---
        # First row - Repairs section
        repair_footer = [
            [
                safe_paragraph("Repairs", self.styles["SmallLabel"]),
                safe_paragraph(wo.get("RepairsNeeded", ""), self.styles["SmallValue"]),
                safe_paragraph("See Repair", self.styles["SmallLabel"]),
                safe_paragraph(wo.get("SeeRepair", ""), self.styles["SmallValue"]),
                safe_paragraph("Repair First", self.styles["SmallLabel"]),
                safe_paragraph(wo.get("CleanFirstWO", ""), self.styles["SmallValue"]),
            ]
        ]

        repair_table = Table(
            repair_footer,
            colWidths=[
                0.8 * inch,  # Repairs
                1.2 * inch,  # Value
                0.8 * inch,  # See Repair
                1.0 * inch,  # Value
                0.8 * inch,  # Repair First
                1.0 * inch,  # Value
            ],  # Total: ~5.6 inches
        )
        repair_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        # Second row - Status section
        status_footer = [
            [
                safe_paragraph("Clean", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(wo.get("Clean", "")), self.styles["SmallValue"]
                ),
                safe_paragraph("Treat", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(wo.get("Treat", "")), self.styles["SmallValue"]
                ),
                safe_paragraph("Return Status", self.styles["SmallLabel"]),
                safe_paragraph(wo.get("ReturnStatus", ""), self.styles["SmallValue"]),
            ]
        ]

        status_table = Table(
            status_footer,
            colWidths=[
                0.7 * inch,  # Clean
                1.0 * inch,  # Date
                0.7 * inch,  # Treat
                1.0 * inch,  # Date
                1.0 * inch,  # Return Status
                1.2 * inch,  # Value
            ],  # Total: ~5.6 inches
        )
        status_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        # Third row - Date Completed (separate for better spacing)
        completion_footer = [
            [
                safe_paragraph("Date Completed", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(wo.get("DateCompleted", "")),
                    self.styles["SmallValue"],
                ),
                "",  # Empty cells for alignment
                "",
                "",
                "",
            ]
        ]

        completion_table = Table(
            completion_footer,
            colWidths=[
                1.2 * inch,  # Date Completed
                1.5 * inch,  # Value
                0.9 * inch,  # Empty
                1.0 * inch,  # Empty
                1.0 * inch,  # Empty
                1.2 * inch,  # Empty
            ],
        )
        completion_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        # --- Checkbox row ---
        bottom_footer = [
            [
                safe_paragraph("Approved:", self.styles["SmallLabel"]),
                "",  # checkbox
                safe_paragraph("Billed:", self.styles["SmallLabel"]),
                "",  # checkbox
                safe_paragraph("Updated:", self.styles["SmallLabel"]),
                "",  # checkbox
            ]
        ]

        checkbox_table = Table(
            bottom_footer,
            colWidths=[
                1.0 * inch,  # Reduced from 1.2
                0.3 * inch,
                1.0 * inch,  # Reduced from 1.2
                0.3 * inch,
                1.0 * inch,  # Reduced from 1.2
                0.3 * inch,
            ],  # Total: 3.9 inches
            rowHeights=0.25 * inch,
        )
        checkbox_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("BOX", (1, 0), (1, 0), 1, colors.black),
                    ("BOX", (3, 0), (3, 0), 1, colors.black),
                    ("BOX", (5, 0), (5, 0), 1, colors.black),
                ]
            )
        )

        return [
            Spacer(1, 0.2 * inch),
            special_instructions_table,
            Spacer(1, 0.1 * inch),  # Slightly less space
            repair_table,
            Spacer(1, 0.05 * inch),  # Small gap between related sections
            status_table,
            Spacer(1, 0.05 * inch),
            completion_table,
            Spacer(1, 0.1 * inch),
            checkbox_table,
        ]

    def generate_pdf(self, filename=None):
        buffer = None
        if filename:
            doc = SimpleDocTemplate(
                filename,
                pagesize=letter,
                rightMargin=0.5 * inch,
                leftMargin=0.5 * inch,
                topMargin=0.4 * inch,
                bottomMargin=0.4 * inch,
            )
        else:
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=0.5 * inch,
                leftMargin=0.5 * inch,
                topMargin=0.4 * inch,
                bottomMargin=0.4 * inch,
            )

        story = []
        story.extend(self._build_header_with_wo_number())
        story.extend(self._build_top_section())
        story.extend(self._build_middle_section())
        story.extend(self._build_source_line())
        story.extend(self._build_items_table())
        story.extend(self._build_footer())

        doc.build(story)
        if filename:
            return filename
        else:
            buffer.seek(0)
            return buffer


def generate_work_order_pdf(work_order, company_info=None, filename=None):
    """Generate a work order PDF that matches the original format"""
    pdf = WorkOrderPDF(work_order, company_info)
    return pdf.generate_pdf(filename)
