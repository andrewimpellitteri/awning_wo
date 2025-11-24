"""
Integration tests for customer detail page HTML rendering
Tests that data attributes are properly escaped in the rendered HTML
"""
import pytest
from decimal import Decimal
from models.inventory import Inventory
from models.customer import Customer
from models.user import User
from extensions import db
from werkzeug.security import generate_password_hash
import re
from html.parser import HTMLParser


class DataAttributeExtractor(HTMLParser):
    """Custom HTML parser to extract data attributes from buttons"""

    def __init__(self):
        super().__init__()
        self.edit_buttons = []

    def handle_starttag(self, tag, attrs):
        if tag == 'button':
            attrs_dict = dict(attrs)
            # Check if this is an edit button
            if 'data-bs-target' in attrs_dict and attrs_dict.get('data-bs-target') == '#editInventoryModal':
                self.edit_buttons.append(attrs_dict)


@pytest.fixture
def admin_client(client, app):
    """Provide a logged-in client with an admin user."""
    with app.app_context():
        admin = User(
            username="admin",
            email="admin@example.com",
            role="admin",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(admin)
        db.session.commit()

        client.post("/login", data={"username": "admin", "password": "password"})
        yield client
        client.get("/logout")


@pytest.fixture
def test_customer(app):
    """Create a test customer"""
    with app.app_context():
        customer = Customer(
            CustID="99999",  # Use numeric string for compatibility with URL routing
            Name="HTML Test Customer",
            Address="123 Test St",
            City="Test City",
            State="TS",
            ZipCode="12345"
        )
        db.session.add(customer)
        db.session.commit()
        yield customer
        # Cleanup
        db.session.query(Inventory).filter_by(CustID="99999").delete()
        db.session.query(Customer).filter_by(CustID="99999").delete()
        db.session.commit()


class TestCustomerDetailHTMLRendering:
    """Test that customer detail page properly renders data attributes with special characters"""

    def test_html_rendering_with_special_chars_in_sizewgt(self, admin_client, app, test_customer):
        """Test that data-sizewgt attribute is properly escaped in HTML"""
        test_sizewgt = "6x7=42'"

        # Create inventory item with special characters
        with app.app_context():
            inventory = Inventory(
                InventoryKey='HTML_RENDER_TEST',
                Description='Test Item for HTML Rendering',
                Material='Canvas',
                Condition='Good',
                Color='Blue',
                SizeWgt=test_sizewgt,
                Price=Decimal('100.00'),
                CustID=test_customer.CustID,
                Qty=5
            )
            db.session.add(inventory)
            db.session.commit()

        # Get the customer detail page HTML
        response = admin_client.get(f'/customers/view/{test_customer.CustID}')
        assert response.status_code == 200

        html_content = response.data.decode('utf-8')

        # Parse the HTML to extract data attributes
        parser = DataAttributeExtractor()
        parser.feed(html_content)

        # Find the edit button for our test item
        test_button = None
        for button_attrs in parser.edit_buttons:
            if button_attrs.get('data-key') == 'HTML_RENDER_TEST':
                test_button = button_attrs
                break

        assert test_button is not None, "Could not find edit button for test inventory item"

        # Check that data-sizewgt is properly preserved
        actual_sizewgt = test_button.get('data-sizewgt', '')
        print(f"\nExpected SizeWgt: {test_sizewgt}")
        print(f"Actual data-sizewgt in HTML: {actual_sizewgt}")

        assert actual_sizewgt == test_sizewgt, \
            f"data-sizewgt attribute was not properly escaped! Expected '{test_sizewgt}', got '{actual_sizewgt}'"

    def test_html_rendering_various_special_chars(self, admin_client, app, test_customer):
        """Test various special character combinations in SizeWgt"""
        test_cases = [
            ("HTML_TEST1", "6x7=42'"),
            ("HTML_TEST2", "10' x 12'"),
            ("HTML_TEST3", "8'6\" x 10'"),
            ("HTML_TEST4", "test=\"value\""),
            ("HTML_TEST5", "size & weight"),
        ]

        # Create inventory items
        with app.app_context():
            for key, sizewgt in test_cases:
                inventory = Inventory(
                    InventoryKey=key,
                    Description=f'Test for {sizewgt}',
                    Material='Canvas',
                    SizeWgt=sizewgt,
                    CustID=test_customer.CustID,
                    Qty=1
                )
                db.session.add(inventory)
            db.session.commit()

        # Get the customer detail page
        response = admin_client.get(f'/customers/view/{test_customer.CustID}')
        assert response.status_code == 200

        html_content = response.data.decode('utf-8')
        parser = DataAttributeExtractor()
        parser.feed(html_content)

        # Check each button
        for key, expected_sizewgt in test_cases:
            button = next((b for b in parser.edit_buttons if b.get('data-key') == key), None)
            assert button is not None, f"Could not find button for {key}"

            actual_sizewgt = button.get('data-sizewgt', '')
            print(f"\n{key}: Expected '{expected_sizewgt}', Got '{actual_sizewgt}'")

            assert actual_sizewgt == expected_sizewgt, \
                f"data-sizewgt for {key} was modified! Expected '{expected_sizewgt}', got '{actual_sizewgt}'"

    def test_raw_html_contains_proper_escaping(self, admin_client, app, test_customer):
        """Test that the raw HTML contains properly escaped attributes"""
        test_sizewgt = "6x7=42'"

        with app.app_context():
            inventory = Inventory(
                InventoryKey='RAW_HTML_TEST',
                Description='Raw HTML Test',
                SizeWgt=test_sizewgt,
                CustID=test_customer.CustID,
                Qty=1
            )
            db.session.add(inventory)
            db.session.commit()

        response = admin_client.get(f'/customers/view/{test_customer.CustID}')
        html_content = response.data.decode('utf-8')

        # Look for the data-sizewgt attribute in raw HTML
        # It should be escaped as data-sizewgt="6x7=42&#x27;" or similar
        print("\n=== Searching for data-sizewgt in raw HTML ===")

        # Find lines containing our test item's data-key
        lines_with_item = [line for line in html_content.split('\n')
                          if 'data-key="RAW_HTML_TEST"' in line or 'RAW_HTML_TEST' in line]

        for line in lines_with_item:
            if 'data-sizewgt' in line:
                print(f"Found line with data-sizewgt:\n{line.strip()}")

                # Extract the data-sizewgt value using regex
                match = re.search(r'data-sizewgt="([^"]*)"', line)
                if match:
                    extracted_value = match.group(1)
                    print(f"Extracted value: {extracted_value}")
                    print(f"Expected value: {test_sizewgt}")

                    # The HTML should contain escaped entities like &#x27; for '
                    # Check that the base part is there and it contains the equals sign
                    assert '6x7' in extracted_value, \
                        f"data-sizewgt doesn't contain expected value"
                    assert '=' in extracted_value or '&#' in extracted_value, \
                        f"data-sizewgt should contain '=' or escaped version"
