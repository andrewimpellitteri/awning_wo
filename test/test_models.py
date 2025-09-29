import pytest
from models.user import User
from models.customer import Customer
from models.inventory import Inventory
from models.invite_token import InviteToken
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
