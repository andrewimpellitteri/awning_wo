
from app import create_app
from extensions import db
from models.work_order import WorkOrder
from datetime import date
import json

def reproduce():
    app = create_app()
    with app.app_context():
        # Setup: Create a dummy WorkOrder with isCushion=True
        wo = WorkOrder(
            WorkOrderNo="TEST-CUSHION-1",
            CustID="999",
            WOName="Cushion Test",
            DateIn=date.today(),
            isCushion=True
        )
        db.session.add(wo)
        db.session.commit()
        
        print(f"Created WorkOrder {wo.WorkOrderNo} with isCushion={wo.isCushion}")
        
        # Test 1: Check to_dict
        data = wo.to_dict()
        if "isCushion" not in data:
            print("FAILURE: 'isCushion' is MISSING from to_dict() output.")
        else:
            print(f"SUCCESS: 'isCushion' is present in to_dict(): {data['isCushion']}")
            
        # Test 2: Check API filtering (mocking request)
        # We need to check how api_work_orders handles filtering. 
        # Since we can't easily call the route without a full client setup in this simple script,
        # we will inspect the WorkOrder.query behavior if possible, or just rely on to_dict finding.
        
        # Cleanup
        db.session.delete(wo)
        db.session.commit()

if __name__ == "__main__":
    reproduce()
