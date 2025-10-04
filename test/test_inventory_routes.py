import pytest
from decimal import Decimal
from models.inventory import Inventory
from models.customer import Customer


@pytest.fixture
def test_customer(db):
    """Create a test customer"""
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
    return customer


class TestInventoryRoutes:
    """Test inventory route handlers"""

    def test_add_inventory_ajax_success(self, client, auth, test_customer):
        """Test AJAX inventory creation with decimal price"""
        auth.login()

        response = client.post('/inventory/add_ajax', data={
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

    def test_add_inventory_ajax_no_price(self, client, auth, test_customer):
        """Test AJAX inventory creation without price"""
        auth.login()

        response = client.post('/inventory/add_ajax', data={
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

    def test_edit_inventory_ajax_success(self, client, auth, test_customer, db):
        """Test AJAX inventory editing"""
        auth.login()

        # Create an inventory item first
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
        response = client.post(f'/inventory/edit_ajax/{inventory.InventoryKey}', data={
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

    def test_delete_inventory_ajax_success(self, client, auth, test_customer, db):
        """Test AJAX inventory deletion"""
        auth.login()

        # Create an inventory item
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
        response = client.post(f'/inventory/delete_ajax/{inventory.InventoryKey}')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert 'message' in json_data

        # Verify item is deleted from database
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