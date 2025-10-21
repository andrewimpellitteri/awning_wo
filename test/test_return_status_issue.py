"""
Test for issue #127 - ReturnStatus field not saving
"""
import pytest
from models.work_order import WorkOrder
from models.repair_order import RepairWorkOrder
from models.customer import Customer
from extensions import db
from datetime import date


def test_work_order_return_status_save(client, app):
    """Test that ReturnStatus field saves correctly for work orders"""
    with app.app_context():
        # Create a test customer first
        customer = Customer(
            CustID="999991",
            Name="Test Customer",
            Source="Test Source"
        )
        db.session.add(customer)
        db.session.commit()

        # Create a work order with ReturnStatus
        wo = WorkOrder(
            WorkOrderNo="999991",
            CustID="999991",
            WOName="Test Work Order",
            ReturnStatus="Ship",
            DateIn=date.today()
        )
        db.session.add(wo)
        db.session.commit()

        # Retrieve the work order and verify ReturnStatus was saved
        saved_wo = WorkOrder.query.filter_by(WorkOrderNo="999991").first()
        assert saved_wo is not None, "Work order was not saved"
        assert saved_wo.ReturnStatus == "Ship", f"ReturnStatus was not saved correctly. Expected 'Ship', got '{saved_wo.ReturnStatus}'"

        # Update ReturnStatus
        saved_wo.ReturnStatus = "Pickup"
        db.session.commit()

        # Retrieve again and verify update
        updated_wo = WorkOrder.query.filter_by(WorkOrderNo="999991").first()
        assert updated_wo.ReturnStatus == "Pickup", f"ReturnStatus was not updated correctly. Expected 'Pickup', got '{updated_wo.ReturnStatus}'"

        # Cleanup
        db.session.delete(updated_wo)
        db.session.delete(customer)
        db.session.commit()


def test_repair_order_return_status_save(client, app):
    """Test that RETURNSTATUS field saves correctly for repair orders"""
    with app.app_context():
        # Create a test customer first
        customer = Customer(
            CustID="999992",
            Name="Test Customer 2",
            Source="Test Source"
        )
        db.session.add(customer)
        db.session.commit()

        # Create a repair order with RETURNSTATUS
        ro = RepairWorkOrder(
            RepairOrderNo="999991",
            CustID="999992",
            ROName="Test Repair Order",
            RETURNSTATUS="Deliver",
            DateIn=date.today()
        )
        db.session.add(ro)
        db.session.commit()

        # Retrieve the repair order and verify RETURNSTATUS was saved
        saved_ro = RepairWorkOrder.query.filter_by(RepairOrderNo="999991").first()
        assert saved_ro is not None, "Repair order was not saved"
        assert saved_ro.RETURNSTATUS == "Deliver", f"RETURNSTATUS was not saved correctly. Expected 'Deliver', got '{saved_ro.RETURNSTATUS}'"

        # Update RETURNSTATUS
        saved_ro.RETURNSTATUS = "Re-Hang"
        db.session.commit()

        # Retrieve again and verify update
        updated_ro = RepairWorkOrder.query.filter_by(RepairOrderNo="999991").first()
        assert updated_ro.RETURNSTATUS == "Re-Hang", f"RETURNSTATUS was not updated correctly. Expected 'Re-Hang', got '{updated_ro.RETURNSTATUS}'"

        # Cleanup
        db.session.delete(updated_ro)
        db.session.delete(customer)
        db.session.commit()


def test_work_order_form_submission(client, app, login_admin):
    """Test that ReturnStatus is saved when submitting the work order form"""
    with app.app_context():
        # Create a test customer first
        customer = Customer(
            CustID="999993",
            Name="Test Customer 3",
            Source="Test Source"
        )
        db.session.add(customer)
        db.session.commit()

    # Submit the work order create form with ReturnStatus
    response = client.post('/work_orders/new', data={
        'CustID': '999993',
        'WOName': 'Form Test WO',
        'ReturnStatus': 'Ship',
        'DateIn': date.today().strftime('%Y-%m-%d')
    }, follow_redirects=True)

    assert response.status_code == 200

    with app.app_context():
        # Find the created work order
        wo = WorkOrder.query.filter_by(WOName='Form Test WO').first()
        assert wo is not None, "Work order was not created"
        assert wo.ReturnStatus == 'Ship', f"ReturnStatus was not saved from form. Expected 'Ship', got '{wo.ReturnStatus}'"

        # Test editing the work order
        response = client.post(f'/work_orders/edit/{wo.WorkOrderNo}', data={
            'CustID': '999993',
            'WOName': 'Form Test WO',
            'ReturnStatus': 'Pickup',
            'DateIn': date.today().strftime('%Y-%m-%d')
        }, follow_redirects=True)

        assert response.status_code == 200

        # Verify the update
        updated_wo = WorkOrder.query.filter_by(WorkOrderNo=wo.WorkOrderNo).first()
        assert updated_wo.ReturnStatus == 'Pickup', f"ReturnStatus was not updated from edit form. Expected 'Pickup', got '{updated_wo.ReturnStatus}'"

        # Cleanup
        db.session.delete(updated_wo)
        db.session.delete(customer)
        db.session.commit()
