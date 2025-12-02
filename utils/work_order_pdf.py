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
    PageBreak,
)
from io import BytesIO
from datetime import datetime
from reportlab.lib.colors import green, red
from utils.helpers import safe_bool_convert, map_bool_display


def safe_paragraph(text, style, field_name=None):
    """Wrap Paragraph creation and log the value being passed."""
    import sys

    if text is None:
        text = ""
    try:
        para = Paragraph(str(text), style)
        # Debug log
        # print(
        #    f"[DEBUG] Paragraph created for '{field_name}': '{text}'", file=sys.stderr
        # )
        return para
    except Exception as e:
        print(
            f"[ERROR] Paragraph failed for '{field_name}': {repr(text)} -> {e}",
            file=sys.stderr,
        )
        # Return an empty paragraph so PDF still builds
        return Paragraph("", style)


def create_bool_paragraph(value, style):
    """Create a paragraph with colored check/X mark"""

    is_true = safe_bool_convert(value)

    if is_true:
        text = "✓"
        # Create a copy of the style with green color
        green_style = style.clone("GreenStyle")
        green_style.textColor = green
        return safe_paragraph(text, green_style)
    else:
        text = "✗"
        # Create a copy of the style with red color
        red_style = style.clone("RedStyle")
        red_style.textColor = red
        return safe_paragraph(text, red_style)


class WorkOrderPDF:
    def __init__(self, work_order_dict, company_info=None):
        self.work_order = work_order_dict
        self.company_info = company_info or {
            "name": "Awning Cleaning Industries - In House Cleaning Work Order"
        }
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        # Company name style - modern and prominent
        self.styles.add(
            ParagraphStyle(
                name="CompanyName",
                parent=self.styles["Normal"],
                fontSize=12,
                spaceAfter=0.1 * inch,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            )
        )

        # Work Order Number - extra prominent
        self.styles.add(
            ParagraphStyle(
                name="WONumber",
                parent=self.styles["Normal"],
                fontSize=16,
                fontName="Helvetica-Bold",
                alignment=TA_RIGHT,
                textColor=colors.HexColor("#d32f2f"),  # Strong red
                borderWidth=2,
                borderColor=colors.HexColor("#d32f2f"),
                borderPadding=6,
            )
        )

        # Field labels - refined and consistent
        self.styles.add(
            ParagraphStyle(
                name="SmallLabel",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=colors.HexColor("#424242"),  # Dark grey
                fontName="Helvetica",
                spaceBefore=1,
                spaceAfter=1,
            )
        )

        # Important labels (like Rush, Repairs) - standout
        self.styles.add(
            ParagraphStyle(
                name="ImportantLabel",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=colors.HexColor("#d32f2f"),  # Red
                fontName="Helvetica-Bold",
                spaceBefore=1,
                spaceAfter=1,
            )
        )

        # Values - clean and readable
        self.styles.add(
            ParagraphStyle(
                name="SmallValue",
                parent=self.styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#212121"),  # Rich black
                fontName="Helvetica",
                spaceBefore=1,
                spaceAfter=1,
            )
        )

        # Values - bold and prominent for source info
        self.styles.add(
            ParagraphStyle(
                name="SmallValueSource",
                parent=self.styles["Normal"],
                fontSize=11,  # slightly larger than default SmallValue
                textColor=colors.HexColor("#000000"),  # pure black for emphasis
                fontName="Helvetica-Bold",  # make it bold
                spaceBefore=1,
                spaceAfter=1,
            )
        )

        # Table headers - professional and clean
        self.styles.add(
            ParagraphStyle(
                name="TableHeader",
                parent=self.styles["Normal"],
                fontSize=9,
                textColor=colors.black,
                fontName="Helvetica-Bold",
                alignment=TA_CENTER,
                spaceBefore=2,
                spaceAfter=2,
            )
        )

        # Table cells - alternating friendly
        self.styles.add(
            ParagraphStyle(
                name="TableCell",
                parent=self.styles["Normal"],
                fontSize=8,
                textColor=colors.HexColor("#424242"),
                fontName="Helvetica",
                alignment=TA_CENTER,
                spaceBefore=1,
                spaceAfter=1,
            )
        )

        # Rush highlighting - urgent red
        self.styles.add(
            ParagraphStyle(
                name="RushHighlight",
                parent=self.styles["SmallValue"],
                textColor=colors.HexColor("#d32f2f"),
                fontName="Helvetica-Bold",
                borderWidth=1,
                borderColor=colors.HexColor("#ffcdd2"),  # Light red border
                borderPadding=2,
            )
        )

        # Condensed spacing for tight layouts
        self.styles.add(
            ParagraphStyle(
                name="Condensed",
                parent=self.styles["SmallValue"],
                spaceBefore=0.5,
                spaceAfter=0.5,
                fontSize=8,
            )
        )

        # Footer text - subtle and professional
        self.styles.add(
            ParagraphStyle(
                name="Footer",
                parent=self.styles["Normal"],
                fontSize=7,
                textColor=colors.HexColor("#212121"),  # Medium grey
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
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
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

    def _build_rush_table(self):
        """Build a 1-row, 3-column rush table with horizontal line below"""
        wo = self.work_order

        def rush_value(label, flag):
            """Return a Paragraph with optional red highlighting for 'Yes'"""
            # Convert to boolean using the safe helper
            is_rush = safe_bool_convert(flag)
            style = (
                self.styles["RushHighlight"] if is_rush else self.styles["SmallValue"]
            )
            return safe_paragraph(map_bool_display(flag), style)

        # Each column: [label, value] stacked vertically
        col1 = [
            safe_paragraph("Rush Order", self.styles["SmallLabel"]),
            rush_value("Rush Order", wo.get("RushOrder")),
        ]
        col2 = [
            safe_paragraph("Firm Rush", self.styles["SmallLabel"]),
            rush_value("Firm Rush", wo.get("FirmRush")),
        ]
        col3 = [
            safe_paragraph("Date Required", self.styles["SmallLabel"]),
            safe_paragraph(
                self._format_date(wo.get("DateRequired")), self.styles["SmallValue"]
            ),
        ]

        table_data = [[col1, col2, col3]]  # 1 row, 3 columns

        # Use a Table with nested flowables in cells
        rush_table = Table(table_data, colWidths=[2 * inch, 2 * inch, 2 * inch])
        rush_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    (
                        "LINEBELOW",
                        (0, 0),
                        (-1, 0),
                        1,
                        colors.black,
                    ),  # horizontal line under the row
                ]
            )
        )

        return [rush_table, Spacer(1, 0.1 * inch)]

    def _build_top_section(self):
        """Build a two-column header section with customer info on left and WO info on right"""
        wo = self.work_order
        customer = wo.get("customer", {})

        customer_zip = customer.get("ZipCode", "")
        if customer_zip:
            if customer_zip[-1] == "-":
                customer_zip = customer_zip.rstrip("-")

        customer_state = customer.get("State", "")
        if customer_state:
            customer_state = customer_state.upper()

        # --- LEFT: Customer Info ---
        left_data = [
            [
                safe_paragraph("Customer ID", self.styles["SmallLabel"]),
                safe_paragraph(str(wo.get("CustID", "")), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Name", self.styles["SmallLabel"]),
                safe_paragraph(customer.get("Name", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Contact", self.styles["SmallLabel"]),
                safe_paragraph(customer.get("Contact", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Address", self.styles["SmallLabel"]),
                safe_paragraph(customer.get("Address", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Address2", self.styles["SmallLabel"]),
                safe_paragraph(customer.get("Address2", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("City", self.styles["SmallLabel"]),
                safe_paragraph(customer.get("City", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("State", self.styles["SmallLabel"]),
                safe_paragraph(customer_state, self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Zip", self.styles["SmallLabel"]),
                safe_paragraph(customer_zip, self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Cell Phone", self.styles["SmallLabel"]),
                safe_paragraph(
                    customer.get("CellPhone", ""), self.styles["SmallValue"]
                ),
            ],
            [
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
            ],
            [
                safe_paragraph("Email", self.styles["SmallLabel"]),
                safe_paragraph(
                    customer.get("CleanEmail", ""), self.styles["SmallValue"]
                ),
            ],
        ]
        left_table = Table(left_data, colWidths=[1.0 * inch, 2.0 * inch])

        # --- RIGHT: Work Order Info ---
        cust = wo.get("customer", {})
        if cust.get("SourceZip"):
            if cust["SourceZip"][-1] == "-":
                cust["SourceZip"] = cust["SourceZip"].strip("-")
        if cust.get("SourceState"):
            cust["SourceState"] = cust["SourceState"].upper()

        # Extract values
        source_name = str(cust.get("Source") or "").strip()
        address_parts = [
            str(cust.get(field) or "").strip()
            for field in ["SourceAddress", "SourceCity", "SourceState", "SourceZip"]
            if cust.get(field)
        ]

        # Combine with newline
        if source_name and address_parts:
            source_str = source_name + "<br/>" + " ".join(address_parts)
        elif source_name:
            source_str = source_name
        elif address_parts:
            source_str = " ".join(address_parts)
        else:
            source_str = "N/A"

        right_data = [
            [
                safe_paragraph("Source", self.styles["SmallLabel"]),
                safe_paragraph(source_str, self.styles["SmallValueSource"]),
            ],
            [
                safe_paragraph("Date In", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(wo.get("DateIn")), self.styles["SmallValue"]
                ),
            ],
            [
                safe_paragraph("Storage", self.styles["SmallLabel"]),
                safe_paragraph(wo.get("StorageTime", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Rack No", self.styles["SmallLabel"]),
                safe_paragraph(wo.get("RackNo", ""), self.styles["SmallValue"]),
            ],
        ]

        right_table = Table(right_data, colWidths=[1.2 * inch, 2.0 * inch])

        # --- Final two-column layout ---
        header_table = Table(
            [[left_table, right_table]], colWidths=[3.2 * inch, 3.2 * inch]
        )
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        return [header_table, Spacer(1, 0.15 * inch)]

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
                safe_paragraph(
                    str(int(float(item.get("Qty", 0)))),  # Convert '1.0' → 1
                    self.styles["TableCell"],
                ),
                safe_paragraph(
                    str(item.get("Description", "")), self.styles["TableCell"]
                ),
                safe_paragraph(str(item.get("Material", "")), self.styles["TableCell"]),
                safe_paragraph(
                    (
                        str(item.get("Condition"))
                        if item.get("Condition") is not None
                        else ""
                    ),
                    self.styles["TableCell"],
                ),
                safe_paragraph(str(item.get("Color", "")), self.styles["TableCell"]),
                safe_paragraph(str(item.get("SizeWgt", "")), self.styles["TableCell"]),
                safe_paragraph(price, self.styles["TableCell"]),
            ]
            rows.append(row)

        # --- Define column widths ---
        col_widths = [
            0.5 * inch,
            1.8 * inch,
            0.9 * inch,
            0.9 * inch,
            0.9 * inch,
            1.0 * inch,
            1.0 * inch,
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
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        return [items_table, Spacer(1, 0.2 * inch)]

    def _build_footer(self):
        """Build footer with special instructions"""
        wo = self.work_order

        # --- Special Instructions with reasonable fixed height ---
        # Replace newlines with <br/> tags to preserve formatting in PDF
        special_instr_text = wo.get("SpecialInstructions", "")
        if special_instr_text:
            special_instr_text = special_instr_text.replace("\n", "<br/>")

        # Create a table for special instructions with a reasonable minimum height
        # If the text is longer, ReportLab will automatically flow to a second page
        special_instructions = [
            [
                safe_paragraph("Special<br/>Instructions", self.styles["SmallLabel"]),
                safe_paragraph(special_instr_text, self.styles["SmallValue"]),
            ]
        ]

        special_instructions_table = Table(
            special_instructions,
            colWidths=[1.0 * inch, 5.5 * inch],
            rowHeights=[1.0 * inch],  # Fixed reasonable height - will flow to page 2 if needed
        )
        special_instructions_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (1, 0), (1, -1), 2),
                    ("RIGHTPADDING", (1, 0), (1, -1), 2),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ]
            )
        )

        # --- Repairs section ---
        repair_footer = [
            [
                safe_paragraph("Repairs", self.styles["SmallLabel"]),
                create_bool_paragraph(
                    wo.get("RepairsNeeded"), self.styles["SmallValue"]
                ),
                safe_paragraph("See Repair", self.styles["SmallLabel"]),
                safe_paragraph(wo.get("SeeRepair", ""), self.styles["SmallValue"]),
                # safe_paragraph(
                #     "Repair First", self.styles["SmallLabel"]
                # ),  # should be removed?? maybe not for historical
                # safe_paragraph(wo.get("CleanFirstWO", ""), self.styles["SmallValue"]),
            ]
        ]

        repair_table = Table(
            repair_footer,
            colWidths=[
                0.8 * inch,
                1.2 * inch,
                0.8 * inch,
                1.0 * inch,
                0.8 * inch,
                1.0 * inch,
            ],
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

        # --- Status section ---
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
                0.7 * inch,
                1.0 * inch,
                0.7 * inch,
                1.0 * inch,
                1.0 * inch,
                1.2 * inch,
            ],
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

        # --- Completion section ---
        completion_footer = [
            [
                safe_paragraph("Date Completed", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(wo.get("DateCompleted", "")),
                    self.styles["SmallValue"],
                ),
                "",
                "",
                "",
                "",
            ]
        ]

        completion_table = Table(
            completion_footer,
            colWidths=[
                1.2 * inch,
                1.5 * inch,
                0.9 * inch,
                1.0 * inch,
                1.0 * inch,
                1.2 * inch,
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

        # --- Checkbox section ---
        bottom_footer = [
            [
                safe_paragraph("Approved:", self.styles["SmallLabel"]),
                "",
                safe_paragraph("Billed:", self.styles["SmallLabel"]),
                "",
                safe_paragraph("Updated:", self.styles["SmallLabel"]),
                "",
            ]
        ]

        checkbox_table = Table(
            bottom_footer,
            colWidths=[
                1.0 * inch,
                0.3 * inch,
                1.0 * inch,
                0.3 * inch,
                1.0 * inch,
                0.3 * inch,
            ],
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
            Spacer(1, 0.1 * inch),
            repair_table,
            Spacer(1, 0.05 * inch),
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
        story.extend(self._build_rush_table())
        story.extend(self._build_top_section())
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
