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


class RepairOrderPDF:
    def __init__(self, repair_order_dict, company_info=None):
        self.repair_order = repair_order_dict
        self.company_info = company_info or {
            "name": "Awning Cleaning Industries - In House Repair Work Order"
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

        # Repair Order Number - extra prominent
        self.styles.add(
            ParagraphStyle(
                name="RONumber",
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

    def _calculate_dynamic_instruction_rows(self, items_count):
        """Calculate number of instruction rows based on items count"""
        # Base calculation: fewer items = more instruction space
        if items_count <= 3:
            return 10  # Lots of space for few items
        elif items_count <= 6:
            return 4  # Moderate space
        elif items_count <= 10:
            return 3  # Less space but still reasonable
        else:
            return 2  # Minimum space for many items

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

    def _build_header_with_ro_number(self):
        """Build header with repair order number prominently displayed with blue background and hline"""
        ro_number = "RO#" + str(self.repair_order.get("RepairOrderNo", ""))

        # Create a table for the header layout
        header_data = [
            [
                safe_paragraph(self.company_info["name"], self.styles["CompanyName"]),
                "",
                safe_paragraph(
                    ro_number,
                    ParagraphStyle(
                        name="RONumber",
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
                        colors.lightgreen,
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
        ro = self.repair_order

        def rush_value(label, flag):
            """Return a Paragraph with optional red highlighting for 'Yes'"""
            style = (
                self.styles["RushHighlight"]
                if flag == "1"
                else self.styles["SmallValue"]
            )
            return safe_paragraph("Yes" if flag == "1" else "No", style)

        # Each column: [label, value] stacked vertically
        col1 = [
            safe_paragraph("Rush Order", self.styles["SmallLabel"]),
            rush_value("Rush Order", ro.get("RushOrder")),
        ]
        col2 = [
            safe_paragraph("Firm Rush", self.styles["SmallLabel"]),
            rush_value("Firm Rush", ro.get("FirmRush")),
        ]
        col3 = [
            safe_paragraph("Date Required", self.styles["SmallLabel"]),
            safe_paragraph(
                self._format_date(ro.get("DateRequired")), self.styles["SmallValue"]
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
        """Build a two-column header section with customer info on left and RO info on right"""
        ro = self.repair_order
        customer = ro.get("customer", {})

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
                safe_paragraph(str(ro.get("CustID", "")), self.styles["SmallValue"]),
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
                    customer.get("EmailAddress", ""), self.styles["SmallValue"]
                ),
            ],
        ]
        left_table = Table(left_data, colWidths=[1.0 * inch, 2.0 * inch])

        # --- RIGHT: Repair Order Info ---
        # Build source information from SOURCE field

        cust = ro.get("customer", {})
        if cust.get("SourceZip"):
            if cust["SourceZip"][-1] == "-":
                cust["SourceZip"] = cust["SourceZip"].strip("-")
        if cust.get("SourceState"):
            cust["SourceState"] = cust["SourceState"].upper()
        safe_values = [
            str(cust.get(field) or "").strip()
            for field in [
                "Source",
                "SourceAddress",
                "SourceCity",
                "SourceState",
                "SourceZip",
            ]
            if cust.get(field)
        ]
        source_str = " ".join(safe_values) if safe_values else "N/A"

        right_data = [
            [
                safe_paragraph("Source", self.styles["SmallLabel"]),
                safe_paragraph(source_str, self.styles["SmallValueSource"]),
            ],
            [
                safe_paragraph("WO Date", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(ro.get("WO_DATE")), self.styles["SmallValue"]
                ),
            ],
            [
                safe_paragraph("Date In", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(ro.get("DateIn")), self.styles["SmallValue"]
                ),
            ],
            [
                safe_paragraph("Date to Sub", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(ro.get("DATE_TO_SUB")), self.styles["SmallValue"]
                ),
            ],
            [
                safe_paragraph("Storage", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("STORAGE", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Rack No", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("RackNo", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Item Type", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("ITEM_TYPE", ""), self.styles["SmallValue"]),
            ],
            [
                safe_paragraph("Type of Repair", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("TYPE_OF_REPAIR", ""), self.styles["SmallValue"]),
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
        items = self.repair_order.get("items", [])

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
                    str(item.get("Condition", "")), self.styles["TableCell"]
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
        """Build footer with dynamic special instructions and repair-specific fields"""
        ro = self.repair_order
        items_count = len(ro.get("items", []))

        # Calculate dynamic number of instruction rows
        instruction_rows = self._calculate_dynamic_instruction_rows(items_count)

        # --- Special Instructions with dynamic rows ---
        special_instructions = [
            [
                safe_paragraph("Special<br/>Instructions", self.styles["SmallLabel"]),
                safe_paragraph(
                    ro.get("SPECIALINSTRUCTIONS", ""), self.styles["SmallValue"]
                ),
            ]
        ]

        # Add calculated number of blank rows
        for _ in range(instruction_rows):
            special_instructions.append(
                ["", safe_paragraph("", self.styles["SmallValue"])]
            )

        special_instructions_table = Table(
            special_instructions,
            colWidths=[1.0 * inch, 5.5 * inch],
            rowHeights=[0.3 * inch] + [0.25 * inch] * instruction_rows,
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

        # --- Repair-specific section ---
        repair_footer = [
            [
                safe_paragraph("Quote", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("QUOTE", ""), self.styles["SmallValue"]),
                safe_paragraph("Quote By", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("QUOTE_BY", ""), self.styles["SmallValue"]),
                safe_paragraph("Approved", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("APPROVED", ""), self.styles["SmallValue"]),
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

        # --- Clean section (repair-specific fields) ---
        clean_footer = [
            [
                safe_paragraph("Clean", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(ro.get("CLEAN", "")), self.styles["SmallValue"]
                ),
                safe_paragraph("See Clean", self.styles["SmallLabel"]),
                safe_paragraph(
                    str(int(float(ro.get("SEECLEAN", 0) or 0))),
                    self.styles["SmallValue"],
                ),
                safe_paragraph("Clean First", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("CLEANFIRST", ""), self.styles["SmallValue"]),
            ]
        ]

        clean_table = Table(
            clean_footer,
            colWidths=[
                0.7 * inch,
                1.0 * inch,
                0.8 * inch,
                1.0 * inch,
                0.8 * inch,
                1.0 * inch,
            ],
        )
        clean_table.setStyle(
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

        # --- Status and completion section ---
        status_footer = [
            [
                safe_paragraph("Repairs Done By", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("REPAIRSDONEBY", ""), self.styles["SmallValue"]),
                safe_paragraph("Customer Price", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("CUSTOMERPRICE", ""), self.styles["SmallValue"]),
                safe_paragraph("Return Status", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("RETURNSTATUS", ""), self.styles["SmallValue"]),
            ]
        ]

        status_table = Table(
            status_footer,
            colWidths=[
                1.0 * inch,
                1.0 * inch,
                1.0 * inch,
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
                    self._format_date(ro.get("DateCompleted", "")),
                    self.styles["SmallValue"],
                ),
                safe_paragraph("Return Date", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(ro.get("RETURNDATE", "")),
                    self.styles["SmallValue"],
                ),
                safe_paragraph("Date Out", self.styles["SmallLabel"]),
                safe_paragraph(
                    self._format_date(ro.get("DATEOUT", "")),
                    self.styles["SmallValue"],
                ),
            ]
        ]

        completion_table = Table(
            completion_footer,
            colWidths=[
                1.2 * inch,
                1.2 * inch,
                1.0 * inch,
                1.0 * inch,
                0.8 * inch,
                1.0 * inch,
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

        # --- Material List section ---
        material_list = [
            [
                safe_paragraph("Material<br/>List", self.styles["SmallLabel"]),
                safe_paragraph(ro.get("MaterialList", ""), self.styles["SmallValue"]),
            ]
        ]

        material_table = Table(
            material_list,
            colWidths=[1.0 * inch, 5.5 * inch],
            rowHeights=[0.3 * inch],
        )
        material_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (1, 0), (1, -1), 2),
                    ("RIGHTPADDING", (1, 0), (1, -1), 2),
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
            clean_table,
            Spacer(1, 0.05 * inch),
            status_table,
            Spacer(1, 0.05 * inch),
            completion_table,
            Spacer(1, 0.1 * inch),
            material_table,
            Spacer(1, 0.1 * inch),
            checkbox_table,
        ]

    def generate_pdf(self, filename=None):
        """Generate the PDF document"""
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
        story.extend(self._build_header_with_ro_number())
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


def generate_repair_order_pdf(repair_order, company_info=None, filename=None):
    """Generate a repair order PDF that matches the original format"""
    pdf = RepairOrderPDF(repair_order, company_info)
    return pdf.generate_pdf(filename)
