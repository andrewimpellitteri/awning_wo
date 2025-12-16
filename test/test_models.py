import pytest
from models.user import User
from models.customer import Customer
from models.inventory import Inventory
from models.invite_token import InviteToken
from models.repair_order import RepairWorkOrder, RepairWorkOrderItem
from models.source import Source
from models.work_order import WorkOrder, WorkOrderItem
from models.work_order_file import WorkOrderFile
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
import secrets


# --- User Model Tests ---
@pytest.mark.unit
def test_create_user(app):
    """
    GIVEN a User model
    WHEN a new User is created
    THEN check the username, email, password, and role fields are defined correctly
    """
    with app.app_context():
        password = "testpassword"
        password_hash = generate_password_hash(password)
        user = User(
            username="testuser",
            email="test@test.com",
            password_hash=password_hash,
            role="admin",
        )

        assert user.username == "testuser"
        assert user.email == "test@test.com"
        assert user.password_hash is not None
        assert check_password_hash(user.password_hash, password)
        assert user.role == "admin"


@pytest.mark.unit
def test_user_repr(app):
    """
    GIVEN a User model
    WHEN the __repr__ method is called
    THEN it should return the correct string representation
    """
    with app.app_context():
        user = User(username="testuser", role="user")
        assert repr(user) == "<User testuser (user)>"


@pytest.mark.unit
def test_user_default_role(app):
    """
    GIVEN a User model
    WHEN a new User is created without a role
    THEN the default role should be 'user'
    """
    with app.app_context():
        user = User(
            username="testuser", email="test@test.com", password_hash="somehash"
        )
        db.session.add(user)
        db.session.commit()
        assert user.role == "user"


# --- Customer Model Tests ---


@pytest.mark.unit
def test_create_customer(app):
    """
    GIVEN a Customer model
    WHEN a new Customer is created
    THEN check the fields are defined correctly
    """
    with app.app_context():
        customer = Customer(
            CustID="12345",
            Name="Test Customer",
            Contact="John Doe",
            Address="123 Main St",
            City="Anytown",
            State="CA",
            ZipCode="12345",
            HomePhone="5551234567",
            EmailAddress="test@test.com#mailto:test@test.com",
        )
        assert customer.CustID == "12345"
        assert customer.Name == "Test Customer"
        assert customer.Contact == "John Doe"
        assert customer.Address == "123 Main St"
        assert customer.City == "Anytown"
        assert customer.State == "CA"
        assert customer.ZipCode == "12345"
        assert customer.HomePhone == "5551234567"
        assert customer.EmailAddress == "test@test.com#mailto:test@test.com"


@pytest.mark.unit
def test_customer_to_dict(app):
    """
    GIVEN a Customer model
    WHEN the to_dict method is called
    THEN it should return a dictionary representation of the customer
    """
    with app.app_context():
        customer = Customer(CustID="123", Name="Test")
        customer_dict = customer.to_dict()
        assert isinstance(customer_dict, dict)
        assert customer_dict["CustID"] == "123"
        assert customer_dict["Name"] == "Test"


@pytest.mark.unit
def test_customer_clean_email(app):
    """
    GIVEN a Customer model
    WHEN the clean_email method is called
    THEN it should remove the '#mailto:' suffix
    """
    with app.app_context():
        customer = Customer(EmailAddress="test@test.com#mailto:test@test.com")
        assert customer.clean_email() == "test@test.com"

        customer_no_suffix = Customer(EmailAddress="test@test.com")
        assert customer_no_suffix.clean_email() == "test@test.com"

        customer_none = Customer(EmailAddress=None)
        assert customer_none.clean_email() is None


@pytest.mark.unit
def test_customer_clean_phone(app):
    """
    GIVEN a Customer model
    WHEN the clean_phone method is called
    THEN it should format the phone number correctly
    """
    with app.app_context():
        customer = Customer(HomePhone="5551234567")
        assert customer.clean_phone("HomePhone") == "(555) 123-4567"

        customer_formatted = Customer(HomePhone="(555) 123-4567")
        assert customer_formatted.clean_phone("HomePhone") == "(555) 123-4567"

        customer_short = Customer(HomePhone="12345")
        assert customer_short.clean_phone("HomePhone") == "12345"

        customer_none = Customer(HomePhone=None)
        assert customer_none.clean_phone("HomePhone") is None


@pytest.mark.unit
def test_customer_get_full_address(app):
    """
    GIVEN a Customer model
    WHEN the get_full_address method is called
    THEN it should return a formatted address string
    """
    with app.app_context():
        customer = Customer(
            Address="123 Main St", City="Anytown", State="CA", ZipCode="12345"
        )
        assert customer.get_full_address() == "123 Main St\nAnytown, CA 12345"

        customer_no_addr = Customer(City="Anytown", State="CA", ZipCode="12345")
        assert customer_no_addr.get_full_address() == "Anytown, CA 12345"

        customer_none = Customer()
        assert customer_none.get_full_address() is None


@pytest.mark.unit
def test_customer_get_mailing_address(app):
    """
    GIVEN a Customer model
    WHEN the get_mailing_address method is called
    THEN it should return a formatted mailing address string
    """
    with app.app_context():
        customer = Customer(
            MailAddress="P.O. Box 123",
            MailCity="Anytown",
            MailState="CA",
            MailZip="12345",
        )
        assert customer.get_mailing_address() == "P.O. Box 123\nAnytown, CA 12345"

        customer_no_mail = Customer(Address="123 Main St")
        assert customer_no_mail.get_mailing_address() is None


@pytest.mark.unit
def test_customer_get_primary_phone(app):
    """
    GIVEN a Customer model
    WHEN the get_primary_phone method is called
    THEN it should return the first available phone number
    """
    with app.app_context():
        customer_cell = Customer(CellPhone="1112223333")
        assert customer_cell.get_primary_phone() == "(111) 222-3333"

        customer_home = Customer(HomePhone="4445556666", WorkPhone="7778889999")
        assert customer_home.get_primary_phone() == "(444) 555-6666"

        customer_work = Customer(WorkPhone="7778889999")
        assert customer_work.get_primary_phone() == "(777) 888-9999"

        customer_none = Customer()
        assert customer_none.get_primary_phone() is None


@pytest.mark.unit
def test_customer_repr(app):
    """
    GIVEN a Customer model
    WHEN the __repr__ method is called
    THEN it should return the correct string representation
    """
    with app.app_context():
        customer = Customer(CustID="123", Name="Test Customer")
        assert repr(customer) == "<Customer 123: Test Customer>"


# --- Inventory Model Tests ---


@pytest.mark.unit
def test_create_inventory_item(app):
    """
    GIVEN an Inventory model
    WHEN a new Inventory item is created
    THEN check the fields are defined correctly
    """
    with app.app_context():
        item = Inventory(
            InventoryKey="INV001",
            Description="Test Item",
            Material="Canvas",
            Condition="New",
            Color="Blue",
            SizeWgt="10x10",
            Price="100.00",
            CustID="123",
            Qty="5",
        )
        assert item.InventoryKey == "INV001"
        assert item.Description == "Test Item"
        assert item.Qty == "5"


@pytest.mark.unit
def test_inventory_to_dict(app):
    """
    GIVEN an Inventory model
    WHEN the to_dict method is called
    THEN it should return a dictionary representation of the item
    """
    with app.app_context():
        item = Inventory(InventoryKey="INV001", Description="Test Item")
        item_dict = item.to_dict()
        assert isinstance(item_dict, dict)
        assert item_dict["InventoryKey"] == "INV001"
        assert item_dict["Description"] == "Test Item"


@pytest.mark.unit
def test_inventory_repr(app):
    """
    GIVEN an Inventory model
    WHEN the __repr__ method is called
    THEN it should return the correct string representation
    """
    with app.app_context():
        item = Inventory(Description="Test Item", CustID="123")
        assert repr(item) == "<CustAwning Test Item (CustID=123)>"


# --- InviteToken Model Tests ---


@pytest.mark.unit
def test_create_invite_token(app):
    """
    GIVEN an InviteToken model
    WHEN a new InviteToken is created
    THEN check the fields are defined correctly
    """
    with app.app_context():
        token_str = secrets.token_urlsafe(16)
        token = InviteToken(token=token_str, role="manager")
        db.session.add(token)
        db.session.commit()
        assert token.token == token_str
        assert token.role == "manager"
        assert token.used is False


@pytest.mark.unit
def test_generate_token(app):
    """
    GIVEN an InviteToken model
    WHEN the generate_token static method is called
    THEN it should create a new token in the database
    """
    with app.app_context():
        db.session.query(InviteToken).delete()  # Clear existing tokens
        db.session.commit()

        invite = InviteToken.generate_token(role="admin")
        db.session.commit()

        assert invite is not None
        assert invite.id is not None
        assert invite.role == "admin"
        assert invite.used is False

        token_from_db = InviteToken.query.get(invite.id)
        assert token_from_db is not None
        assert token_from_db.token == invite.token


# --- RepairWorkOrder Model Tests ---


@pytest.mark.unit
def test_create_repair_work_order(app):
    """
    GIVEN a RepairWorkOrder model
    WHEN a new RepairWorkOrder is created
    THEN check the fields are defined correctly
    """
    with app.app_context():
        customer = Customer(CustID="50001", Name="Test Customer")
        db.session.add(customer)
        db.session.commit()

        repair_order = RepairWorkOrder(
            RepairOrderNo="RO001",
            CustID="50001",
            ROName="Test Repair",
            SOURCE="Walk-in",
            QUOTE="100.00",
        )
        assert repair_order.RepairOrderNo == "RO001"
        assert repair_order.CustID == "50001"
        assert repair_order.ROName == "Test Repair"
        assert repair_order.SOURCE == "Walk-in"
        assert repair_order.QUOTE == "100.00"


@pytest.mark.unit
def test_repair_work_order_to_dict(app):
    """
    GIVEN a RepairWorkOrder model
    WHEN the to_dict method is called
    THEN it should return a dictionary representation
    """
    with app.app_context():
        customer = Customer(CustID="50002", Name="Test Customer")
        db.session.add(customer)
        db.session.commit()

        repair_order = RepairWorkOrder(
            RepairOrderNo="RO002", CustID="50002", ROName="Test Repair"
        )
        order_dict = repair_order.to_dict()
        assert isinstance(order_dict, dict)
        assert order_dict["RepairOrderNo"] == "RO002"
        assert order_dict["CustID"] == "50002"
        assert order_dict["ROName"] == "Test Repair"


@pytest.mark.unit
def test_repair_work_order_repr(app):
    """
    GIVEN a RepairWorkOrder model
    WHEN the __repr__ method is called
    THEN it should return the correct string representation
    """
    with app.app_context():
        repair_order = RepairWorkOrder(RepairOrderNo="RO001", ROName="Test Repair")
        assert repr(repair_order) == "<RepairWorkOrder RO001: Test Repair>"


@pytest.mark.unit
def test_repair_work_order_str(app):
    """
    GIVEN a RepairWorkOrder model
    WHEN the __str__ method is called
    THEN it should return a formatted string
    """
    with app.app_context():
        repair_order = RepairWorkOrder(RepairOrderNo="RO001", ROName="Test Repair")
        assert str(repair_order) == "Repair Order RO001 - Test Repair"

        repair_order_no_name = RepairWorkOrder(RepairOrderNo="RO002")
        assert str(repair_order_no_name) == "Repair Order RO002 - Unnamed"


# --- RepairWorkOrderItem Model Tests ---


@pytest.mark.unit
def test_create_repair_work_order_item(app):
    """
    GIVEN a RepairWorkOrderItem model
    WHEN a new RepairWorkOrderItem is created
    THEN check the fields are defined correctly
    """
    with app.app_context():
        customer = Customer(CustID="50003", Name="Test Customer")
        db.session.add(customer)
        db.session.commit()

        repair_order = RepairWorkOrder(RepairOrderNo="RO003", CustID="50003")
        db.session.add(repair_order)
        db.session.commit()

        item = RepairWorkOrderItem(
            RepairOrderNo="RO003",
            CustID="50003",
            Description="Test Item",
            Material="Canvas",
            Qty="2",
            Price="50.00",
        )
        assert item.RepairOrderNo == "RO003"
        assert item.CustID == "50003"
        assert item.Description == "Test Item"
        assert item.Material == "Canvas"
        assert item.Qty == "2"


@pytest.mark.unit
def test_repair_work_order_item_to_dict(app):
    """
    GIVEN a RepairWorkOrderItem model
    WHEN the to_dict method is called
    THEN it should return a dictionary representation
    """
    with app.app_context():
        item = RepairWorkOrderItem(
            RepairOrderNo="RO001",
            CustID="12345",
            Description="Test Item",
            Material="Canvas",
        )
        item_dict = item.to_dict()
        assert isinstance(item_dict, dict)
        assert item_dict["RepairOrderNo"] == "RO001"
        assert item_dict["Description"] == "Test Item"
        assert item_dict["Material"] == "Canvas"


@pytest.mark.unit
def test_repair_work_order_item_repr(app):
    """
    GIVEN a RepairWorkOrderItem model
    WHEN the __repr__ method is called
    THEN it should return the correct string representation
    """
    with app.app_context():
        item = RepairWorkOrderItem(
            RepairOrderNo="RO001", Description="Test Item", Material="Canvas"
        )
        assert repr(item) == "<RepairWorkOrderItem RO001: Test Item>"


@pytest.mark.unit
def test_repair_work_order_item_str(app):
    """
    GIVEN a RepairWorkOrderItem model
    WHEN the __str__ method is called
    THEN it should return a formatted string
    """
    with app.app_context():
        item = RepairWorkOrderItem(
            RepairOrderNo="RO001", Description="Test Item", Material="Canvas", Qty="3"
        )
        assert str(item) == "Test Item (Canvas) - Qty: 3"


# --- Source Model Tests ---


@pytest.mark.unit
def test_create_source(app):
    """
    GIVEN a Source model
    WHEN a new Source is created
    THEN check the fields are defined correctly
    """
    with app.app_context():
        source = Source(
            SSource="Test Source",
            SourceAddress="123 Source St",
            SourceCity="Sourceville",
            SourceState="CA",
            SourceZip="12345",
            SourcePhone="5551234567",
            SourceEmail="source@test.com",
        )
        assert source.SSource == "Test Source"
        assert source.SourceAddress == "123 Source St"
        assert source.SourceCity == "Sourceville"
        assert source.SourceState == "CA"
        assert source.SourceZip == "12345"


@pytest.mark.unit
def test_source_to_dict(app):
    """
    GIVEN a Source model
    WHEN the to_dict method is called
    THEN it should return a dictionary representation
    """
    with app.app_context():
        source = Source(SSource="Test Source", SourceCity="Sourceville")
        source_dict = source.to_dict()
        assert isinstance(source_dict, dict)
        assert source_dict["SSource"] == "Test Source"
        assert source_dict["Name"] == "Test Source"
        assert source_dict["SourceCity"] == "Sourceville"


@pytest.mark.unit
def test_source_clean_email(app):
    """
    GIVEN a Source model
    WHEN the clean_email method is called
    THEN it should remove the '#mailto:' suffix
    """
    with app.app_context():
        source = Source(SourceEmail="test@test.com#mailto:test@test.com")
        assert source.clean_email() == "test@test.com"

        source_no_suffix = Source(SourceEmail="test@test.com")
        assert source_no_suffix.clean_email() == "test@test.com"

        source_none = Source(SourceEmail=None)
        assert source_none.clean_email() is None


@pytest.mark.unit
def test_source_clean_phone(app):
    """
    GIVEN a Source model
    WHEN the clean_phone method is called
    THEN it should format the phone number correctly
    """
    with app.app_context():
        source = Source(SourcePhone="5551234567")
        assert source.clean_phone() == "(555) 123-4567"

        source_formatted = Source(SourcePhone="(555) 123-4567")
        assert source_formatted.clean_phone() == "(555) 123-4567"

        source_short = Source(SourcePhone="12345")
        assert source_short.clean_phone() == "12345"

        source_none = Source(SourcePhone=None)
        assert source_none.clean_phone() is None


@pytest.mark.unit
def test_source_get_full_address(app):
    """
    GIVEN a Source model
    WHEN the get_full_address method is called
    THEN it should return a formatted address string
    """
    with app.app_context():
        source = Source(
            SourceAddress="123 Source St",
            SourceCity="Sourceville",
            SourceState="CA",
            SourceZip="12345",
        )
        assert source.get_full_address() == "123 Source St\nSourceville, CA 12345"

        source_no_addr = Source(
            SourceCity="Sourceville", SourceState="CA", SourceZip="12345"
        )
        assert source_no_addr.get_full_address() == "Sourceville, CA 12345"

        source_none = Source()
        assert source_none.get_full_address() is None


@pytest.mark.unit
def test_source_repr(app):
    """
    GIVEN a Source model
    WHEN the __repr__ method is called
    THEN it should return the correct string representation
    """
    with app.app_context():
        source = Source(SSource="Test Source")
        assert repr(source) == "<Source Test Source>"


# --- WorkOrder Model Tests ---


@pytest.mark.unit
def test_create_work_order(app):
    """
    GIVEN a WorkOrder model
    WHEN a new WorkOrder is created
    THEN check the fields are defined correctly
    """
    with app.app_context():
        customer = Customer(CustID="60001", Name="Test Customer")
        db.session.add(customer)
        db.session.commit()

        work_order = WorkOrder(
            WorkOrderNo="WO001",
            CustID="60001",
            WOName="Test Work Order",
            Storage="Yes",
            Quote="200.00",
        )
        assert work_order.WorkOrderNo == "WO001"
        assert work_order.CustID == "60001"
        assert work_order.WOName == "Test Work Order"
        assert work_order.Storage == "Yes"
        assert work_order.Quote == "200.00"


@pytest.mark.unit
def test_work_order_to_dict(app):
    """
    GIVEN a WorkOrder model
    WHEN the to_dict method is called
    THEN it should return a dictionary representation
    """
    with app.app_context():
        customer = Customer(CustID="60002", Name="Test Customer")
        db.session.add(customer)
        db.session.commit()

        work_order = WorkOrder(
            WorkOrderNo="WO002", CustID="60002", WOName="Test Work Order"
        )
        db.session.add(work_order)
        db.session.commit()

        order_dict = work_order.to_dict(include_items=False)
        assert isinstance(order_dict, dict)
        assert order_dict["WorkOrderNo"] == "WO002"
        assert order_dict["CustID"] == "60002"
        assert order_dict["WOName"] == "Test Work Order"
        assert "items" not in order_dict


@pytest.mark.unit
def test_work_order_to_dict_with_items(app):
    """
    GIVEN a WorkOrder model with items
    WHEN the to_dict method is called with include_items=True
    THEN it should include items in the dictionary
    """
    with app.app_context():
        customer = Customer(CustID="60003", Name="Test Customer")
        db.session.add(customer)
        db.session.commit()

        work_order = WorkOrder(WorkOrderNo="WO003", CustID="60003")
        db.session.add(work_order)
        db.session.commit()

        order_dict = work_order.to_dict(include_items=True)
        assert "items" in order_dict
        assert isinstance(order_dict["items"], list)


@pytest.mark.unit
def test_work_order_repr(app):
    """
    GIVEN a WorkOrder model
    WHEN the __repr__ method is called
    THEN it should return the correct string representation
    """
    with app.app_context():
        work_order = WorkOrder(WorkOrderNo="WO001", WOName="Test Work Order")
        assert repr(work_order) == "<WorkOrder WO001: Test Work Order>"


@pytest.mark.unit
def test_work_order_str(app):
    """
    GIVEN a WorkOrder model
    WHEN the __str__ method is called
    THEN it should return a formatted string
    """
    with app.app_context():
        work_order = WorkOrder(WorkOrderNo="WO001", WOName="Test Work Order")
        assert str(work_order) == "Work Order WO001 - Test Work Order"

        work_order_no_name = WorkOrder(WorkOrderNo="WO002")
        assert str(work_order_no_name) == "Work Order WO002 - Unnamed"


@pytest.mark.unit
def test_work_order_is_sail_order(app):
    """
    GIVEN a WorkOrder model
    WHEN the is_sail_order property is accessed
    THEN it should return True if ShipTo is in SAIL_ORDER_SOURCES
    """
    with app.app_context():
        app.config["SAIL_ORDER_SOURCES"] = ["Sail Source 1", "Sail Source 2"]

        work_order_sail = WorkOrder(
            WorkOrderNo="WO001", ShipTo="Sail Source 1", CustID="123"
        )
        assert work_order_sail.is_sail_order is True

        work_order_not_sail = WorkOrder(
            WorkOrderNo="WO002", ShipTo="Other Source", CustID="123"
        )
        assert work_order_not_sail.is_sail_order is False

        work_order_no_ship = WorkOrder(WorkOrderNo="WO003", CustID="123")
        assert work_order_no_ship.is_sail_order is False


@pytest.mark.unit
def test_work_order_get_sail_order_sources(app):
    """
    GIVEN a WorkOrder model
    WHEN the get_sail_order_sources class method is called
    THEN it should return the SAIL_ORDER_SOURCES from config
    """
    with app.app_context():
        app.config["SAIL_ORDER_SOURCES"] = ["Source 1", "Source 2"]
        sources = WorkOrder.get_sail_order_sources()
        assert sources == ["Source 1", "Source 2"]


@pytest.mark.unit
def test_work_order_is_cushion_default(app):
    """
    GIVEN a WorkOrder model
    WHEN a new WorkOrder is created without isCushion specified
    THEN the isCushion field should default to False
    """
    with app.app_context():
        customer = Customer(CustID="60009", Name="Test Customer")
        db.session.add(customer)
        db.session.commit()

        work_order = WorkOrder(
            WorkOrderNo="WO011",
            CustID="60009",
        )
        db.session.add(work_order)
        db.session.commit()

        assert work_order.isCushion is False


# --- WorkOrderItem Model Tests ---


@pytest.mark.unit
def test_create_work_order_item(app):
    """
    GIVEN a WorkOrderItem model
    WHEN a new WorkOrderItem is created
    THEN check the fields are defined correctly
    """
    with app.app_context():
        customer = Customer(CustID="60004", Name="Test Customer")
        db.session.add(customer)
        db.session.commit()

        work_order = WorkOrder(WorkOrderNo="WO004", CustID="60004")
        db.session.add(work_order)
        db.session.commit()

        item = WorkOrderItem(
            WorkOrderNo="WO004",
            CustID="60004",
            Description="Test Item",
            Material="Canvas",
            Qty="5",
            Price="100.00",
        )
        assert item.WorkOrderNo == "WO004"
        assert item.CustID == "60004"
        assert item.Description == "Test Item"
        assert item.Material == "Canvas"
        assert item.Qty == "5"


@pytest.mark.unit
def test_work_order_item_default_material(app):
    """
    GIVEN a WorkOrderItem model
    WHEN a new WorkOrderItem is created without Material and committed
    THEN it should default to 'Unknown'
    """
    with app.app_context():
        customer = Customer(CustID="60005", Name="Test Customer")
        db.session.add(customer)
        db.session.commit()

        work_order = WorkOrder(WorkOrderNo="WO005", CustID="60005")
        db.session.add(work_order)
        db.session.commit()

        item = WorkOrderItem(
            WorkOrderNo="WO005", CustID="60005", Description="Test Item"
        )
        db.session.add(item)
        db.session.commit()

        assert item.Material == "Unknown"


@pytest.mark.unit
def test_work_order_item_to_dict(app):
    """
    GIVEN a WorkOrderItem model
    WHEN the to_dict method is called
    THEN it should return a dictionary representation
    """
    with app.app_context():
        item = WorkOrderItem(
            WorkOrderNo="WO006",
            CustID="60006",
            Description="Test Item",
            Material="Canvas",
        )
        item_dict = item.to_dict()
        assert isinstance(item_dict, dict)
        assert item_dict["WorkOrderNo"] == "WO006"
        assert item_dict["Description"] == "Test Item"
        assert item_dict["Material"] == "Canvas"


@pytest.mark.unit
def test_work_order_item_repr(app):
    """
    GIVEN a WorkOrderItem model
    WHEN the __repr__ method is called
    THEN it should return the correct string representation
    """
    with app.app_context():
        item = WorkOrderItem(
            WorkOrderNo="WO007", Description="Test Item", Material="Canvas"
        )
        assert repr(item) == "<WorkOrderItem WO007: Test Item>"


@pytest.mark.unit
def test_work_order_item_str(app):
    """
    GIVEN a WorkOrderItem model
    WHEN the __str__ method is called
    THEN it should return a formatted string
    """
    with app.app_context():
        item = WorkOrderItem(
            WorkOrderNo="WO008", Description="Test Item", Material="Canvas", Qty="5"
        )
        assert str(item) == "Test Item (Canvas) - Qty: 5"


# --- WorkOrderFile Model Tests ---


@pytest.mark.unit
def test_create_work_order_file(app):
    """
    GIVEN a WorkOrderFile model
    WHEN a new WorkOrderFile is created
    THEN check the fields are defined correctly
    """
    with app.app_context():
        customer = Customer(CustID="60007", Name="Test Customer")
        db.session.add(customer)
        db.session.commit()

        work_order = WorkOrder(WorkOrderNo="WO009", CustID="60007")
        db.session.add(work_order)
        db.session.commit()

        file = WorkOrderFile(
            WorkOrderNo="WO009",
            filename="test.jpg",
            file_path="/uploads/test.jpg",
        )
        db.session.add(file)
        db.session.commit()

        assert file.WorkOrderNo == "WO009"
        assert file.filename == "test.jpg"
        assert file.file_path == "/uploads/test.jpg"
        assert file.uploaded_at is not None


@pytest.mark.unit
def test_work_order_file_to_dict(app):
    """
    GIVEN a WorkOrderFile model
    WHEN the to_dict method is called
    THEN it should return a dictionary representation
    """
    with app.app_context():
        customer = Customer(CustID="60008", Name="Test Customer")
        db.session.add(customer)
        db.session.commit()

        work_order = WorkOrder(WorkOrderNo="WO010", CustID="60008")
        db.session.add(work_order)
        db.session.commit()

        file = WorkOrderFile(
            WorkOrderNo="WO010",
            filename="test.jpg",
            file_path="/uploads/test.jpg",
        )
        db.session.add(file)
        db.session.commit()

        file_dict = file.to_dict()
        assert isinstance(file_dict, dict)
        assert file_dict["WorkOrderNo"] == "WO010"
        assert file_dict["filename"] == "test.jpg"
        assert file_dict["file_path"] == "/uploads/test.jpg"
        assert "uploaded_at" in file_dict
