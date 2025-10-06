import pytest
from decimal import Decimal
from models.inventory import Inventory
from models.customer import Customer
from models.user import User
from extensions import db
from werkzeug.security import generate_password_hash


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
def regular_client(client, app):
    """Provide a logged-in client with a regular user."""
    with app.app_context():
        user = User(
            username="user",
            email="user@example.com",
            role="user",
            password_hash=generate_password_hash("password"),
        )
        db.session.add(user)
        db.session.commit()

        client.post("/login", data={"username": "user", "password": "password"})
        yield client
        client.get("/logout")


@pytest.fixture
def test_customer(app):
    """Create a test customer"""
    with app.app_context():
        customer = Customer(
            CustID="TEST001",
            Name="Test Customer",
            Address="123 Test St",
            City="Test City",
            State="TS",
            ZipCode="12345"
        )
        db.session.add(customer)
        db.session.commit()
        yield customer
        # Cleanup
        db.session.query(Customer).filter_by(CustID="TEST001").delete()
        db.session.commit()


class TestInventoryRoutes:
    """Test inventory route handlers"""

    def test_add_inventory_ajax_success(self, admin_client, test_customer):
        """Test AJAX inventory creation with decimal price"""
        response = admin_client.post('/inventory/add_ajax', data={
            'CustID': test_customer.CustID,
            'Description': 'Test Awning',
            'Material': 'Canvas',
            'Condition': 'Good',
            'Color': 'Blue',
            'SizeWgt': '10x10',
            'Price': '99.99',
            'Qty': '5'
        })

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert 'item' in json_data

        # Verify the item data is properly serialized
        item = json_data['item']
        assert item['Description'] == 'Test Awning'
        assert item['Material'] == 'Canvas'
        assert item['Color'] == 'Blue'
        assert item['Condition'] == 'Good'
        assert item['SizeWgt'] == '10x10'
        assert item['Price'] == 99.99  # Should be float, not Decimal
        assert item['Qty'] == 5
        assert item['CustID'] == test_customer.CustID
        assert 'InventoryKey' in item

    def test_add_inventory_ajax_no_price(self, admin_client, test_customer):
        """Test AJAX inventory creation without price"""
        response = admin_client.post('/inventory/add_ajax', data={
            'CustID': test_customer.CustID,
            'Description': 'Test Awning No Price',
            'Material': 'Vinyl',
            'Qty': '3'
        })

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True

        item = json_data['item']
        assert item['Price'] is None  # Should handle None properly

    def test_add_inventory_ajax_empty_string_price(self, admin_client, test_customer):
        """Test AJAX inventory creation with empty string price"""
        response = admin_client.post('/inventory/add_ajax', data={
            'CustID': test_customer.CustID,
            'Description': 'Staysail',
            'Material': '',
            'Condition': 'Poor',
            'Color': '',
            'SizeWgt': '67#',
            'Price': '',  # Empty string should be converted to None
            'Qty': '1'
        })

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True

        item = json_data['item']
        assert item['Price'] is None  # Empty string should be converted to None
        assert item['Description'] == 'Staysail'

    def test_edit_inventory_ajax_success(self, admin_client, app, test_customer):
        """Test AJAX inventory editing"""
        # Create an inventory item first
        with app.app_context():
            inventory = Inventory(
                InventoryKey='TEST123',
                Description='Original Description',
                Material='Canvas',
                Condition='Good',
                Color='Red',
                SizeWgt='8x8',
                Price=Decimal('75.50'),
                CustID=test_customer.CustID,
                Qty=3
            )
            db.session.add(inventory)
            db.session.commit()

        # Edit the item
        response = admin_client.post(f'/inventory/edit_ajax/TEST123', data={
            'Description': 'Updated Description',
            'Material': 'Vinyl',
            'Condition': 'Excellent',
            'Color': 'Blue',
            'SizeWgt': '10x12',
            'Price': '125.99',
            'Qty': '7'
        })

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True

        # Verify updated data
        item = json_data['item']
        assert item['Description'] == 'Updated Description'
        assert item['Material'] == 'Vinyl'
        assert item['Color'] == 'Blue'
        assert item['Condition'] == 'Excellent'
        assert item['SizeWgt'] == '10x12'
        assert item['Price'] == 125.99  # Should be float
        assert item['Qty'] == 7

    def test_delete_inventory_ajax_success(self, admin_client, app, test_customer):
        """Test AJAX inventory deletion"""
        # Create an inventory item
        with app.app_context():
            inventory = Inventory(
                InventoryKey='DELETE123',
                Description='Item to Delete',
                Material='Canvas',
                CustID=test_customer.CustID,
                Qty=1
            )
            db.session.add(inventory)
            db.session.commit()

        # Delete the item
        response = admin_client.post(f'/inventory/delete_ajax/DELETE123')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert 'message' in json_data

        # Verify item is deleted from database
        with app.app_context():
            deleted_item = Inventory.query.get('DELETE123')
            assert deleted_item is None

    def test_inventory_model_to_dict_with_decimal(self):
        """Test that to_dict properly converts Decimal to float"""
        item = Inventory(
            InventoryKey='DICT_TEST',
            Description='Test Item',
            Material='Canvas',
            Condition='Good',
            Color='Blue',
            SizeWgt='10x10',
            Price=Decimal('99.99'),
            CustID='CUST001',
            Qty=5
        )

        result = item.to_dict()

        # Verify Price is converted to float
        assert isinstance(result['Price'], float)
        assert result['Price'] == 99.99

        # Verify it's JSON serializable
        import json
        json_str = json.dumps(result)  # Should not raise exception
        assert json_str is not None

    def test_inventory_model_to_dict_with_none_price(self):
        """Test that to_dict handles None price properly"""
        item = Inventory(
            InventoryKey='DICT_TEST2',
            Description='Test Item',
            Price=None,
            CustID='CUST001',
            Qty=1
        )

        result = item.to_dict()
        assert result['Price'] is None

        # Verify it's JSON serializable
        import json
        json_str = json.dumps(result)
        assert json_str is not None




class TestInventoryAPI:
    """Test inventory API endpoints"""

    def test_api_search_inventory(self, admin_client, app, test_customer):
        """Test inventory search API"""
        with app.app_context():
            item = Inventory(
                InventoryKey='API001',
                Description='Blue Canvas Awning',
                Material='Canvas',
                Color='Blue',
                CustID=test_customer.CustID,
                Qty=5
            )
            db.session.add(item)
            db.session.commit()

        response = admin_client.get('/inventory/api/search?q=Blue')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(item['description'] == 'Blue Canvas Awning' for item in data)

    def test_api_search_inventory_by_customer(self, admin_client, app, test_customer):
        """Test inventory search API filtered by customer"""
        with app.app_context():
            item = Inventory(
                InventoryKey='API002',
                Description='Customer Specific Item',
                CustID=test_customer.CustID,
                Qty=1
            )
            db.session.add(item)
            db.session.commit()

        response = admin_client.get(f'/inventory/api/search?cust_id={test_customer.CustID}')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert all(item['cust_id'] == test_customer.CustID for item in data)

    def test_api_customer_inventory(self, admin_client, app, test_customer):
        """Test getting all inventory for a customer"""
        with app.app_context():
            item1 = Inventory(
                InventoryKey='CUST001',
                Description='Item 1',
                CustID=test_customer.CustID,
                Qty=1
            )
            item2 = Inventory(
                InventoryKey='CUST002',
                Description='Item 2',
                CustID=test_customer.CustID,
                Qty=2
            )
            db.session.add_all([item1, item2])
            db.session.commit()

        response = admin_client.get(f'/inventory/api/customer/{test_customer.CustID}')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_api_bulk_update_inventory(self, admin_client, app, test_customer):
        """Test bulk updating inventory quantities"""
        with app.app_context():
            item1 = Inventory(InventoryKey='BULK001', Description='Item 1', CustID=test_customer.CustID, Qty='5')
            item2 = Inventory(InventoryKey='BULK002', Description='Item 2', CustID=test_customer.CustID, Qty='10')
            db.session.add_all([item1, item2])
            db.session.commit()

        updates = [
            {'inventory_key': 'BULK001', 'qty': 15},
            {'inventory_key': 'BULK002', 'qty': 25}
        ]

        response = admin_client.post('/inventory/api/bulk_update',
                                     json=updates,
                                     content_type='application/json')
        assert response.status_code == 200
        data = response.get_json()
        assert 'message' in data

        # Verify updates
        with app.app_context():
            item1 = Inventory.query.get('BULK001')
            item2 = Inventory.query.get('BULK002')
            # Qty is stored as string in format, but may be int after bulk update
            assert str(item1.Qty) == '15'
            assert str(item2.Qty) == '25'


class TestInventoryAuthorization:
    """Test inventory authorization"""

    def test_regular_user_cannot_create_inventory(self, regular_client):
        """Test that regular users cannot create inventory"""
        response = regular_client.post('/inventory/new', data={
            'Description': 'Unauthorized Item',
            'Qty': '1'
        })
        assert response.status_code == 403

    def test_regular_user_cannot_edit_inventory(self, regular_client, app, test_customer):
        """Test that regular users cannot edit inventory"""
        with app.app_context():
            item = Inventory(
                InventoryKey='AUTH001',
                Description='Item',
                CustID=test_customer.CustID,
                Qty=1
            )
            db.session.add(item)
            db.session.commit()

        response = regular_client.post('/inventory/edit/AUTH001', data={
            'Description': 'Updated',
            'Qty': '5'
        })
        assert response.status_code == 403

    def test_regular_user_cannot_add_ajax(self, regular_client, test_customer):
        """Test that regular users cannot add inventory via AJAX"""
        response = regular_client.post('/inventory/add_ajax', data={
            'CustID': test_customer.CustID,
            'Description': 'Unauthorized',
            'Qty': '1'
        })
        assert response.status_code == 403

    def test_regular_user_cannot_edit_ajax(self, regular_client, app, test_customer):
        """Test that regular users cannot edit inventory via AJAX"""
        with app.app_context():
            item = Inventory(
                InventoryKey='AUTH002',
                Description='Item',
                CustID=test_customer.CustID,
                Qty=1
            )
            db.session.add(item)
            db.session.commit()

        response = regular_client.post('/inventory/edit_ajax/AUTH002', data={
            'Description': 'Updated',
            'Qty': '5'
        })
        assert response.status_code == 403

    def test_regular_user_cannot_delete_ajax(self, regular_client, app, test_customer):
        """Test that regular users cannot delete inventory via AJAX"""
        with app.app_context():
            item = Inventory(
                InventoryKey='AUTH003',
                Description='Item',
                CustID=test_customer.CustID,
                Qty=1
            )
            db.session.add(item)
            db.session.commit()

        response = regular_client.post('/inventory/delete_ajax/AUTH003')
        assert response.status_code == 403

