import pandas as pd
import os
from flask import current_app
from models.customer import Customer
from models.work_order import WorkOrder, WorkOrderItem
from models.repair_order import RepairOrder, RepairOrderItem
from models.inventory import InventoryItem
from models.source import Source
from models.reference import Material, Color, Condition
from models.progress import ProgressTracking
from models.photo import Photo
from app import db

class CSVHandler:
    """Handle CSV import/export operations"""
    
    def __init__(self):
        self.csv_path = current_app.config.get('CSV_DATA_PATH', 'data')
    
    def import_all_csvs(self):
        """Import all CSV files from the data directory"""
        try:
            # Import reference data first
            self.import_reference_data()
            
            # Import main data
            self.import_sources()
            self.import_customers()
            self.import_inventory()
            self.import_work_orders()
            self.import_repair_orders()
            self.import_progress()
            self.import_photos()
            
            db.session.commit()
            return True, "All CSV files imported successfully"
        
        except Exception as e:
            db.session.rollback()
            return False, f"Error importing CSV files: {str(e)}"
    
    def import_reference_data(self):
        """Import materials, colors, and conditions"""
        # Materials
        materials_file = os.path.join(self.csv_path, 'tblMaterial.csv')
        if os.path.exists(materials_file):
            df = pd.read_csv(materials_file)
            for _, row in df.iterrows():
                if not Material.query.filter_by(name=row['Material']).first():
                    material = Material(name=row['Material'])
                    db.session.add(material)
        
        # Colors
        colors_file = os.path.join(self.csv_path, 'tblColor.csv')
        if os.path.exists(colors_file):
            df = pd.read_csv(colors_file)
            for _, row in df.iterrows():
                if not Color.query.filter_by(name=row['Color']).first():
                    color = Color(name=row['Color'])
                    db.session.add(color)
        
        # Conditions
        conditions_file = os.path.join(self.csv_path, 'tblCondition.csv')
        if os.path.exists(conditions_file):
            df = pd.read_csv(conditions_file)
            for _, row in df.iterrows():
                if not Condition.query.filter_by(name=row['Condition']).first():
                    condition = Condition(name=row['Condition'])
                    db.session.add(condition)
    
    def import_sources(self):
        """Import source companies"""
        sources_file = os.path.join(self.csv_path, 'tblSource.csv')
        if not os.path.exists(sources_file):
            return
        
        df = pd.read_csv(sources_file)
        for _, row in df.iterrows():
            if not Source.query.filter_by(name=row.get('SSource', '')).first():
                source = Source(
                    name=row.get('SSource', ''),
                    address=row.get('SourceAddress', ''),
                    city=row.get('SourceCity', ''),
                    state=row.get('SourceState', ''),
                    zip_code=row.get('SourceZip', ''),
                    phone=row.get('SourcePhone', ''),
                    fax=row.get('SourceFax', ''),
                    email=row.get('SourceEmail', '')
                )
                db.session.add(source)
    
    def import_customers(self):
        """Import customers"""
        customers_file = os.path.join(self.csv_path, 'tblCustomers.csv')
        if not os.path.exists(customers_file):
            return
        
        df = pd.read_csv(customers_file)
        for _, row in df.iterrows():
            if not Customer.query.filter_by(id=row.get('CustID')).first():
                # Find source if exists
                source = None
                if row.get('Source'):
                    source = Source.query.filter_by(name=row.get('Source')).first()
                
                customer = Customer(
                    id=row.get('CustID'),
                    name=row.get('Name', ''),
                    contact=row.get('Contact', ''),
                    address=row.get('Address', ''),
                    address2=row.get('Address2', ''),
                    city=row.get('City', ''),
                    state=row.get('State', ''),
                    zip_code=row.get('ZipCode', ''),
                    home_phone=row.get('HomePhone', ''),
                    work_phone=row.get('WorkPhone', ''),
                    cell_phone=row.get('CellPhone', ''),
                    email_address=row.get('EmailAddress', ''),
                    mail_address=row.get('MailAddress', ''),
                    mail_city=row.get('MailCity', ''),
                    mail_state=row.get('MailState', ''),
                    mail_zip=row.get('MailZip', ''),
                    source_id=source.id if source else None
                )
                db.session.add(customer)
    
    def import_inventory(self):
        """Import customer inventory"""
        inventory_file = os.path.join(self.csv_path, 'tblCustAwngs.csv')
        if not os.path.exists(inventory_file):
            return
        
        df = pd.read_csv(inventory_file)
        for _, row in df.iterrows():
            inventory_item = InventoryItem(
                customer_id=row.get('CustID'),
                description=row.get('Description', ''),
                material=row.get('Material', ''),
                condition=row.get('Condition', ''),
                color=row.get('Color', ''),
                size_weight=row.get('SizeWgt', ''),
                price=row.get('Price'),
                qty=row.get('Qty', 1),
                inventory_key=row.get('InventoryKey', '')
            )
            db.session.add(inventory_item)
    
    def import_work_orders(self):
        """Import work orders"""
        wo_file = os.path.join(self.csv_path, 'tblCustWorkOrderDetail.csv')
        if not os.path.exists(wo_file):
            return
        
        df = pd.read_csv(wo_file)
        for _, row in df.iterrows():
            if not WorkOrder.query.filter_by(work_order_no=row.get('WorkOrderNo')).first():
                work_order = WorkOrder(
                    work_order_no=row.get('WorkOrderNo', ''),
                    customer_id=row.get('CustID'),
                    wo_name=row.get('WOName', ''),
                    storage=row.get('Storage', ''),
                    storage_time=row.get('StorageTime', ''),
                    rack_number=row.get('Rack#', ''),
                    special_instructions=row.get('SpecialInstructions', ''),
                    repairs_needed=row.get('RepairsNeeded', ''),
                    see_repair=bool(row.get('SeeRepair')),
                    return_status=row.get('ReturnStatus', ''),
                    date_completed=pd.to_datetime(row.get('DateCompleted'), errors='coerce'),
                    date_in=pd.to_datetime(row.get('DateIn'), errors='coerce'),
                    date_required=pd.to_datetime(row.get('DateRequired'), errors='coerce'),
                    quote=row.get('Quote'),
                    clean=bool(row.get('Clean')),
                    treat=bool(row.get('Treat')),
                    rush_order=bool(row.get('RushOrder')),
                    firm_rush=bool(row.get('FirmRush')),
                    clean_first_wo=bool(row.get('CleanFirstWO')),
                    ship_to=row.get('ShipTo', '')
                )
                db.session.add(work_order)
        
        # Import work order items
        wo_items_file = os.path.join(self.csv_path, 'tblOrdDetCustAwngs.csv')
        if os.path.exists(wo_items_file):
            df = pd.read_csv(wo_items_file)
            for _, row in df.iterrows():
                work_order = WorkOrder.query.filter_by(work_order_no=row.get('WorkOrderNo')).first()
                if work_order:
                    wo_item = WorkOrderItem(
                        work_order_id=work_order.id,
                        customer_id=row.get('CustID'),
                        qty=row.get('Qty', 1),
                        description=row.get('Description', ''),
                        material=row.get('Material', ''),
                        condition=row.get('Condition', ''),
                        color=row.get('Color', ''),
                        size_weight=row.get('SizeWgt', ''),
                        price=row.get('Price')
                    )
                    db.session.add(wo_item)
    
    def import_repair_orders(self):
        """Import repair orders"""
        ro_file = os.path.join(self.csv_path, 'tblRepairWorkOrderDetail.csv')
        if not os.path.exists(ro_file):
            return
        
        df = pd.read_csv(ro_file)
        for _, row in df.iterrows():
            if not RepairOrder.query.filter_by(repair_order_no=row.get('RepairOrderNo')).first():
                repair_order = RepairOrder(
                    repair_order_no=row.get('RepairOrderNo', ''),
                    customer_id=row.get('CustID'),
                    ro_name=row.get('ROName', ''),
                    source=row.get('SOURCE', ''),
                    wo_date=pd.to_datetime(row.get('WO DATE'), errors='coerce'),
                    date_to_sub=pd.to_datetime(row.get('DATE TO SUB'), errors='coerce'),
                    date_required=pd.to_datetime(row.get('DateRequired'), errors='coerce'),
                    date_in=pd.to_datetime(row.get('DateIn'), errors='coerce'),
                    date_completed=pd.to_datetime(row.get('DateCompleted'), errors='coerce'),
                    date_out=pd.to_datetime(row.get('DATEOUT'), errors='coerce'),
                    return_date=pd.to_datetime(row.get('RETURNDATE'), errors='coerce'),
                    rush_order=bool(row.get('RushOrder')),
                    firm_rush=bool(row.get('FirmRush')),
                    quote=row.get('QUOTE'),
                    quote_by=row.get('QUOTE  BY', ''),
                    approved=bool(row.get('APPROVED')),
                    rack_number=row.get('RACK#', ''),
                    storage=row.get('STORAGE', ''),
                    location=row.get('LOCATION', ''),
                    item_type=row.get('ITEM TYPE', ''),
                    type_of_repair=row.get('TYPE OF REPAIR', ''),
                    special_instructions=row.get('SPECIALINSTRUCTIONS', ''),
                    repairs_done_by=row.get('REPAIRSDONEBY', ''),
                    material_list=row.get('MaterialList', ''),
                    customer_price=row.get('CUSTOMERPRICE'),
                    clean=bool(row.get('CLEAN')),
                    see_clean=bool(row.get('SEECLEAN')),
                    clean_first=bool(row.get('CLEANFIRST')),
                    return_status=row.get('RETURNSTATUS', '')
                )
                db.session.add(repair_order)
        
        # Import repair order items
        ro_items_file = os.path.join(self.csv_path, 'tblRepOrdDetCustAwngs.csv')
        if os.path.exists(ro_items_file):
            df = pd.read_csv(ro_items_file)
            for _, row in df.iterrows():
                repair_order = RepairOrder.query.filter_by(repair_order_no=row.get('RepairOrderNo')).first()
                if repair_order:
                    ro_item = RepairOrderItem(
                        repair_order_id=repair_order.id,
                        customer_id=row.get('CustID'),
                        qty=row.get('Qty', 1),
                        description=row.get('Description', ''),
                        material=row.get('Material', ''),
                        condition=row.get('Condition', ''),
                        color=row.get('Color', ''),
                        size_weight=row.get('SizeWgt', ''),
                        price=row.get('Price')
                    )
                    db.session.add(ro_item)
    
    def import_progress(self):
        """Import progress tracking"""
        progress_file = os.path.join(self.csv_path, 'tblProgress.csv')
        if not os.path.exists(progress_file):
            return
        
        df = pd.read_csv(progress_file)
        for _, row in df.iterrows():
            work_order = WorkOrder.query.filter_by(work_order_no=row.get('PgrsWorkOrderNo')).first()
            
            progress = ProgressTracking(
                customer_id=row.get('CustID'),
                work_order_id=work_order.id if work_order else None,
                pgrs_work_order_no=row.get('PgrsWorkOrderNo', ''),
                pgrs_name=row.get('PgrsName', ''),
                pgrs_date_in=pd.to_datetime(row.get('PgrsDateIn'), errors='coerce'),
                pgrs_date_updated=pd.to_datetime(row.get('PgrsDateUptd'), errors='coerce'),
                pgrs_source=row.get('PgrsSource', ''),
                wo_quote=row.get('WO_Quote'),
                on_deck_clean=bool(row.get('OnDeckClean')),
                tub=bool(row.get('Tub')),
                clean=bool(row.get('Clean')),
                treat=bool(row.get('Treat')),
                wrap_clean=bool(row.get('WrapClean')),
                notes_clean=row.get('NotesClean', ''),
                pgrs_repair_order_no=row.get('PgrsRepairOrderNo', ''),
                repair_quote=row.get('Repair_Quote'),
                on_deck_repair=bool(row.get('OnDeckRepair')),
                in_process=bool(row.get('InProcess')),
                wrap_repair=bool(row.get('WrapRepair')),
                repair_notes=row.get('Repair_Notes', '')
            )
            db.session.add(progress)
    
    def import_photos(self):
        """Import photo records"""
        photos_file = os.path.join(self.csv_path, 'tblPhotos.csv')
        if not os.path.exists(photos_file):
            return
        
        df = pd.read_csv(photos_file)
        for _, row in df.iterrows():
            photo = Photo(
                customer_id=row.get('CustID'),
                filename=row.get('Link', ''),  # Using Link as filename
                original_filename=row.get('Link', ''),
                file_path=row.get('Link', ''),
                photo_date=pd.to_datetime(row.get('PhotoDate'), errors='coerce'),
                notes=row.get('Notes', '')
            )
            db.session.add(photo)
    
    def export_to_csv(self, model_class, filename):
        """Export model data to CSV"""
        try:
            # Get all records
            records = model_class.query.all()
            
            if not records:
                return False, "No data to export"
            
            # Convert to dict if method exists
            if hasattr(records[0], 'to_dict'):
                data = [record.to_dict() for record in records]
            else:
                # Fallback to basic conversion
                data = []
                for record in records:
                    record_dict = {}
                    for column in record.__table__.columns:
                        value = getattr(record, column.name)
                        if value is not None:
                            record_dict[column.name] = str(value)
                        else:
                            record_dict[column.name] = ''
                    data.append(record_dict)
            
            # Create DataFrame and save
            df = pd.DataFrame(data)
            export_path = os.path.join(self.csv_path, filename)
            df.to_csv(export_path, index=False)
            
            return True, f"Data exported to {export_path}"
        
        except Exception as e:
            return False, f"Error exporting data: {str(e)}"
