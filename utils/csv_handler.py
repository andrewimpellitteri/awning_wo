import pandas as pd
import os
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
    Numeric,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

# Model Definitions (based on schema)


class Material(Base):
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)


class Color(Base):
    __tablename__ = "colors"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)


class Condition(Base):
    __tablename__ = "conditions"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)


class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    zip_code = Column(String)
    phone = Column(String)
    fax = Column(String)
    email = Column(String)


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    contact = Column(String)
    address = Column(String)
    address2 = Column(String)
    city = Column(String)
    state = Column(String)
    zip_code = Column(String)
    home_phone = Column(String)
    work_phone = Column(String)
    cell_phone = Column(String)
    email_address = Column(String)
    mail_address = Column(String)
    mail_city = Column(String)
    mail_state = Column(String)
    mail_zip = Column(String)
    source_id = Column(Integer, ForeignKey("sources.id"))


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    description = Column(String)
    material = Column(String)
    condition = Column(String)
    color = Column(String)
    size_weight = Column(String)
    price = Column(Float)
    qty = Column(Integer)
    inventory_key = Column(Integer, unique=True)


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id = Column(Integer, primary_key=True)
    work_order_no = Column(String, unique=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    wo_name = Column(String)
    storage = Column(String)
    storage_time = Column(String)
    rack_number = Column(String)
    special_instructions = Column(String)
    repairs_needed = Column(String)
    see_repair = Column(Boolean)
    return_status = Column(String)
    date_completed = Column(DateTime)
    date_in = Column(DateTime)
    date_required = Column(DateTime)
    quote = Column(Numeric(10, 2))
    clean = Column(DateTime)  # Corrected to DateTime based on data
    treat = Column(DateTime)  # Corrected to DateTime based on data
    rush_order = Column(Boolean)
    firm_rush = Column(Boolean)
    clean_first_wo = Column(Boolean)
    ship_to = Column(String)


class WorkOrderItem(Base):
    __tablename__ = "work_order_items"
    id = Column(Integer, primary_key=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"))
    qty = Column(Integer)
    description = Column(String)
    material = Column(String)
    condition = Column(String)
    color = Column(String)
    size_weight = Column(String)
    price = Column(Float)


class RepairOrder(Base):
    __tablename__ = "repair_orders"
    id = Column(Integer, primary_key=True)
    repair_order_no = Column(Integer, unique=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    ro_name = Column(String)
    source = Column(String)
    wo_date = Column(DateTime)
    date_to_sub = Column(DateTime)
    date_required = Column(DateTime)
    date_in = Column(DateTime)
    date_completed = Column(DateTime)
    date_out = Column(DateTime)
    return_date = Column(DateTime)
    rush_order = Column(Boolean)
    firm_rush = Column(Boolean)
    quote = Column(String)
    quote_by = Column(String)
    approved = Column(Boolean)
    rack_number = Column(String)
    storage = Column(String)
    location = Column(String)
    item_type = Column(String)
    type_of_repair = Column(String)
    special_instructions = Column(String)
    repairs_done_by = Column(String)
    material_list = Column(String)
    customer_price = Column(Float)
    clean = Column(Boolean)  # Kept as Boolean based on code, but verify data if needed
    see_clean = Column(Boolean)
    clean_first = Column(Boolean)
    return_status = Column(String)


class RepairOrderItem(Base):
    __tablename__ = "repair_order_items"
    id = Column(Integer, primary_key=True)
    repair_order_id = Column(Integer, ForeignKey("repair_orders.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"))
    qty = Column(Integer)
    description = Column(String)
    material = Column(String)
    condition = Column(String)
    color = Column(String)
    size_weight = Column(String)
    price = Column(Float)


class ProgressTracking(Base):
    __tablename__ = "progress_tracking"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    work_order_id = Column(Integer, ForeignKey("work_orders.id"))
    pgrs_work_order_no = Column(String)
    pgrs_name = Column(String)
    pgrs_date_in = Column(DateTime)
    pgrs_date_updated = Column(DateTime)
    pgrs_source = Column(String)
    wo_quote = Column(String)
    on_deck_clean = Column(Boolean)
    tub = Column(Boolean)
    clean = Column(Boolean)
    treat = Column(Boolean)
    wrap_clean = Column(Boolean)
    notes_clean = Column(String)
    pgrs_repair_order_no = Column(String)
    repair_quote = Column(String)
    on_deck_repair = Column(Boolean)
    in_process = Column(Boolean)
    wrap_repair = Column(Boolean)
    repair_notes = Column(String)


class Photo(Base):
    __tablename__ = "photos"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    filename = Column(String, unique=True)
    original_filename = Column(String)
    file_path = Column(String)
    photo_date = Column(DateTime)
    notes = Column(String)


# CSV Handler Class (rewritten with corrections)


class CSVHandler:
    def __init__(self, csv_path="csv_export"):  # Adjust path as needed
        self.csv_path = csv_path
        os.makedirs(self.csv_path, exist_ok=True)

    def _load_csv(self, filename):
        file_path = os.path.join(self.csv_path, filename)
        if not os.path.exists(file_path):
            print(f"[WARN] File not found: {file_path}")
            return None
        try:
            return pd.read_csv(file_path, keep_default_na=False, na_values=[""])
        except Exception as e:
            print(f"[ERROR] Failed to read {filename}: {e}")
            return None

    def _get_value(self, row, key, default=None):
        value = row.get(key)
        # Check for NaN or empty string
        if pd.isna(value) or value == "":
            return default
        return value

    def _get_boolean_value(self, row, key, default=False):
        value = self._get_value(row, key, default)
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in ["true", "1", "t", "y", "yes"]:
                return True
            if value_lower in ["false", "0", "f", "n", "no"]:
                return False
        return bool(value) if isinstance(value, (int, float, bool)) else default

    def _parse_date(self, value, default=None):
        if pd.isna(value) or value is None:
            return default
        try:
            # Handle formats like 'MM/DD/YY HH:MM:SS' or others
            return pd.to_datetime(value, errors="coerce")
        except Exception as e:
            print(f"[WARN] Invalid date format: {value}, error: {e}")
            return default

    def import_all_csvs(self, session):
        try:
            self.import_reference_data(session)
            self.import_sources(session)
            self.import_customers(session)
            self.import_inventory(session)
            self.import_work_orders(session)
            self.import_repair_orders(session)
            self.import_progress(session)
            self.import_photos(session)
            session.commit()
            print("All CSV files imported successfully")
        except Exception as e:
            session.rollback()
            print(f"[ERROR] Import failed: {e}")

    def import_reference_data(self, session):
        reference_configs = [
            {"filename": "tblMaterial.csv", "model": Material, "colname": "Material"},
            {"filename": "tblColor.csv", "model": Color, "colname": "Color"},
            {
                "filename": "tblCondition.csv",
                "model": Condition,
                "colname": "Condition",
            },
        ]
        for config in reference_configs:
            df = self._load_csv(config["filename"])
            if df is None:
                continue
            for _, row in df.iterrows():
                name = self._get_value(row, config["colname"])
                if (
                    name
                    and not session.query(config["model"]).filter_by(name=name).first()
                ):
                    session.add(config["model"](name=name))

    def import_sources(self, session):
        df = self._load_csv("tblSource.csv")
        if df is None:
            return
        for _, row in df.iterrows():
            name = self._get_value(row, "SSource")
            if not name or session.query(Source).filter_by(name=name).first():
                print("Can't find source.")
                continue
            source = Source(
                name=name,
                address=self._get_value(row, "SourceAddress"),
                city=self._get_value(row, "SourceCity"),
                state=self._get_value(row, "SourceState"),
                zip_code=self._get_value(row, "SourceZip"),
                phone=self._get_value(row, "SourcePhone"),
                fax=self._get_value(row, "SourceFax"),
                email=self._get_value(row, "SourceEmail"),
            )
            session.add(source)

    def import_customers(self, session):
        df = self._load_csv("tblCustomers.csv")
        if df is None:
            return
        for _, row in df.iterrows():
            cust_id = self._get_value(row, "CustID")
            if not cust_id or session.query(Customer).filter_by(id=cust_id).first():
                print("can't get cust")
                continue
            src_name = self._get_value(row, "Source")
            source = (
                session.query(Source).filter_by(name=src_name).first()
                if src_name
                else None
            )
            customer = Customer(
                id=cust_id,
                name=self._get_value(row, "Name", "Unnamed Customer"),
                contact=self._get_value(row, "Contact"),
                address=self._get_value(row, "Address"),
                address2=self._get_value(row, "Address2"),
                city=self._get_value(row, "City"),
                state=self._get_value(row, "State"),
                zip_code=self._get_value(row, "ZipCode"),
                home_phone=self._get_value(row, "HomePhone"),
                work_phone=self._get_value(row, "WorkPhone"),
                cell_phone=self._get_value(row, "CellPhone"),
                email_address=self._get_value(row, "EmailAddress"),
                mail_address=self._get_value(row, "MailAddress"),
                mail_city=self._get_value(row, "MailCity"),
                mail_state=self._get_value(row, "MailState"),
                mail_zip=self._get_value(row, "MailZip"),
                source_id=source.id if source else None,
            )
            session.add(customer)

    def import_inventory(self, session):
        df = self._load_csv("tblCustAwngs.csv")
        if df is None:
            return
        for _, row in df.iterrows():
            inventory_key = self._get_value(row, "InventoryKey")
            if (
                not inventory_key
                or session.query(InventoryItem)
                .filter_by(inventory_key=inventory_key)
                .first()
            ):
                print("can't get inv row")
                continue
            inventory_item = InventoryItem(
                customer_id=self._get_value(row, "CustID"),
                description=self._get_value(row, "Description"),
                material=self._get_value(row, "Material"),
                condition=self._get_value(row, "Condition"),
                color=self._get_value(row, "Color"),
                size_weight=self._get_value(row, "SizeWgt"),
                price=self._get_value(row, "Price"),
                qty=self._get_value(row, "Qty", 1),
                inventory_key=inventory_key,
            )
            session.add(inventory_item)

    def import_work_orders(self, session):
        df = self._load_csv("tblCustWorkOrderDetail.csv")
        if df is None:
            return

        batch_size = 1000
        for i in range(0, len(df), batch_size):
            batch = df[i : i + batch_size]
            for _, row in batch.iterrows():
                wo_no = self._get_value(row, "WorkOrderNo")
                if pd.isna(wo_no) or not str(wo_no).strip():
                    print(f"[SKIP] Work order with empty WorkOrderNo")
                    continue

                customer_id = self._get_value(row, "CustID")
                if customer_id is None or pd.isna(customer_id):
                    print(f"[SKIP] Work order {wo_no} has missing CustID")
                    continue

                try:
                    customer_id = int(
                        float(customer_id)
                    )  # Handle float representations
                except (ValueError, TypeError):
                    print(
                        f"[SKIP] Work order {wo_no} has invalid CustID: {customer_id}"
                    )
                    continue

                # Skip if work order already exists
                if session.query(WorkOrder).filter_by(work_order_no=str(wo_no)).first():
                    continue

                # Skip if customer does not exist
                if not session.query(Customer).filter_by(id=customer_id).first():
                    print(
                        f"[SKIP] Work order {wo_no}: customer {customer_id} not found"
                    )
                    continue

                # Safe parsing of numeric fields
                quote = self._get_value(row, "Quote")
                try:
                    quote_to_insert = float(quote) if not pd.isna(quote) else None
                except ValueError:
                    quote_to_insert = None

                work_order = WorkOrder(
                    work_order_no=str(wo_no),
                    customer_id=customer_id,
                    wo_name=self._get_value(row, "WOName"),
                    storage=self._get_value(row, "Storage"),
                    storage_time=self._get_value(row, "StorageTime"),
                    rack_number=self._get_value(row, "Rack#"),
                    special_instructions=self._get_value(row, "SpecialInstructions"),
                    repairs_needed=self._get_value(row, "RepairsNeeded"),
                    see_repair=self._get_boolean_value(row, "SeeRepair"),
                    return_status=self._get_value(row, "ReturnStatus"),
                    date_completed=self._parse_date(row.get("DateCompleted")),
                    date_in=self._parse_date(row.get("DateIn")),
                    date_required=self._parse_date(row.get("DateRequired")),
                    quote=quote_to_insert,
                    clean=self._parse_date(row.get("Clean")),
                    treat=self._parse_date(row.get("Treat")),
                    rush_order=self._get_boolean_value(row, "RushOrder"),
                    firm_rush=self._get_boolean_value(row, "FirmRush"),
                    clean_first_wo=self._get_boolean_value(row, "CleanFirstWO"),
                    ship_to=self._get_value(row, "ShipTo"),
                )
                session.add(work_order)
            session.commit()

        # ---- Work Order Items ----
        df_items = self._load_csv("tblOrdDetCustAwngs.csv")
        if df_items is None:
            return

        for i in range(0, len(df_items), batch_size):
            batch = df_items[i : i + batch_size]
            for _, row in batch.iterrows():
                wo_no = self._get_value(row, "WorkOrderNo")
                if pd.isna(wo_no) or not str(wo_no).strip():
                    print("no wo no")
                    continue

                customer_id = self._get_value(row, "CustID")
                if customer_id is None or pd.isna(customer_id):
                    print(f"[SKIP] Work order item {wo_no} missing CustID")
                    continue

                try:
                    customer_id = int(customer_id)
                except ValueError:
                    print(
                        f"[SKIP] Work order item {wo_no} has invalid CustID: {customer_id}"
                    )
                    continue

                work_order = (
                    session.query(WorkOrder).filter_by(work_order_no=str(wo_no)).first()
                )
                if not work_order:
                    print(f"[SKIP] Work order item {wo_no} not found in DB")
                    continue

                if not session.query(Customer).filter_by(id=customer_id).first():
                    print(
                        f"[SKIP] Work order item {wo_no}: customer {customer_id} not found"
                    )
                    continue

                qty = self._get_value(row, "Qty", 1)
                if not isinstance(qty, (int, float)) or pd.isna(qty):
                    qty = 1
                else:
                    qty = int(qty)

                price = self._get_value(row, "Price")
                try:
                    price = float(price) if not pd.isna(price) else None
                except ValueError:
                    price = None

                wo_item = WorkOrderItem(
                    work_order_id=work_order.id,
                    customer_id=customer_id,
                    qty=qty,
                    description=self._get_value(row, "Description"),
                    material=self._get_value(row, "Material"),
                    condition=self._get_value(row, "Condition"),
                    color=self._get_value(row, "Color"),
                    size_weight=self._get_value(row, "SizeWgt"),
                    price=price,
                )
                session.add(wo_item)
            session.commit()

    def import_repair_orders(self, session):
        df = self._load_csv("tblRepairWorkOrderDetail.csv")
        if df is None:
            return
        for _, row in df.iterrows():
            ro_no = self._get_value(row, "RepairOrderNo")
            if (
                not ro_no
                or session.query(RepairOrder).filter_by(repair_order_no=ro_no).first()
            ):
                continue
            repair_order = RepairOrder(
                repair_order_no=ro_no,
                customer_id=self._get_value(row, "CustID"),
                ro_name=self._get_value(row, "ROName"),
                source=self._get_value(row, "SOURCE"),
                wo_date=self._parse_date(row.get("WO DATE")),
                date_to_sub=self._parse_date(row.get("DATE TO SUB")),
                date_required=self._parse_date(row.get("DateRequired")),
                date_in=self._parse_date(row.get("DateIn")),
                date_completed=self._parse_date(row.get("DateCompleted")),
                date_out=self._parse_date(row.get("DATEOUT")),
                return_date=self._parse_date(row.get("RETURNDATE")),
                rush_order=self._get_boolean_value(row, "RushOrder"),
                firm_rush=self._get_boolean_value(row, "FirmRush"),
                quote=self._get_value(row, "QUOTE"),
                quote_by=self._get_value(row, "QUOTE  BY"),
                approved=self._get_boolean_value(row, "APPROVED"),
                rack_number=self._get_value(row, "RACK#"),
                storage=self._get_value(row, "STORAGE"),
                location=self._get_value(row, "LOCATION"),
                item_type=self._get_value(row, "ITEM TYPE"),
                type_of_repair=self._get_value(row, "TYPE OF REPAIR"),
                special_instructions=self._get_value(row, "SPECIALINSTRUCTIONS"),
                repairs_done_by=self._get_value(row, "REPAIRSDONEBY"),
                material_list=self._get_value(row, "MaterialList"),
                customer_price=self._get_value(row, "CUSTOMERPRICE"),
                clean=self._get_boolean_value(row, "CLEAN"),
                see_clean=self._get_boolean_value(row, "SEECLEAN"),
                clean_first=self._get_boolean_value(row, "CLEANFIRST"),
                return_status=self._get_value(row, "RETURNSTATUS"),
            )
            session.add(repair_order)

        df_items = self._load_csv("tblRepOrdDetCustAwngs.csv")
        if df_items is None:
            return
        for _, row in df_items.iterrows():
            repair_order = (
                session.query(RepairOrder)
                .filter_by(repair_order_no=self._get_value(row, "RepairOrderNo"))
                .first()
            )
            if repair_order:
                qty = self._get_value(row, "Qty", 1)
                if not isinstance(qty, (int, float)):
                    qty = 1
                else:
                    qty = int(qty)
                ro_item = RepairOrderItem(
                    repair_order_id=repair_order.id,
                    customer_id=self._get_value(row, "CustID"),
                    qty=qty,
                    description=self._get_value(row, "Description"),
                    material=self._get_value(row, "Material"),
                    condition=self._get_value(row, "Condition"),
                    color=self._get_value(row, "Color"),
                    size_weight=self._get_value(row, "SizeWgt"),
                    price=self._get_value(row, "Price"),
                )
                session.add(ro_item)

    def import_progress(self, session):
        df = self._load_csv("tblProgress.csv")
        if df is None:
            return
        for _, row in df.iterrows():
            work_order = (
                session.query(WorkOrder)
                .filter_by(work_order_no=self._get_value(row, "PgrsWorkOrderNo"))
                .first()
            )
            progress = ProgressTracking(
                customer_id=self._get_value(row, "CustID"),
                work_order_id=work_order.id if work_order else None,
                pgrs_work_order_no=self._get_value(row, "PgrsWorkOrderNo"),
                pgrs_name=self._get_value(row, "PgrsName"),
                pgrs_date_in=self._parse_date(row.get("PgrsDateIn")),
                pgrs_date_updated=self._parse_date(row.get("PgrsDateUptd")),
                pgrs_source=self._get_value(row, "PgrsSource"),
                wo_quote=self._get_value(row, "WO_Quote"),
                on_deck_clean=self._get_boolean_value(row, "OnDeckClean"),
                tub=self._get_boolean_value(row, "Tub"),
                clean=self._get_boolean_value(row, "Clean"),
                treat=self._get_boolean_value(row, "Treat"),
                wrap_clean=self._get_boolean_value(row, "WrapClean"),
                notes_clean=self._get_value(row, "NotesClean"),
                pgrs_repair_order_no=self._get_value(row, "PgrsRepairOrderNo"),
                repair_quote=self._get_value(row, "Repair_Quote"),
                on_deck_repair=self._get_boolean_value(row, "OnDeckRepair"),
                in_process=self._get_boolean_value(row, "InProcess"),
                wrap_repair=self._get_boolean_value(row, "WrapRepair"),
                repair_notes=self._get_value(row, "Repair_Notes"),
            )
            session.add(progress)

    def import_photos(self, session):
        df = self._load_csv("tblPhotos.csv")
        if df is None:
            return
        for _, row in df.iterrows():
            link = self._get_value(row, "Link")
            if not link or session.query(Photo).filter_by(filename=link).first():
                continue
            photo = Photo(
                customer_id=self._get_value(row, "CustID"),
                filename=link,
                original_filename=link,
                file_path=link,
                photo_date=self._parse_date(row.get("PhotoDate")),
                notes=self._get_value(row, "Notes"),
            )
            session.add(photo)


if __name__ == "__main__":
    engine = create_engine("sqlite:///awning.db", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    handler = CSVHandler(csv_path="csv_export")  # Set to your CSV directory
    handler.import_all_csvs(session)
    session.close()
    print("Database file 'awning.db' created successfully.")
