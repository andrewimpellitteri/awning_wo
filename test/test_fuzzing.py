"""
Fuzzing tests for Work Order and Repair Order routes.

This test suite uses the Hypothesis library to generate a wide range of
unexpected and edge-case data to test the robustness of the create and edit
routes for Work Orders and Repair Orders.

The goal is to ensure that the application can handle malformed, invalid, or
unexpected data without crashing (i.e., returning a 500 Internal Server Error).
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume, note
from models.work_order import WorkOrder, WorkOrderItem
from models.repair_order import RepairWorkOrder
from models.customer import Customer
from models.source import Source
from extensions import db
from werkzeug.security import generate_password_hash
from models.user import User
from datetime import date
import uuid
from io import BytesIO
import random

# If hypothesis is not installed, you can install it with:
# pip install hypothesis

# Define a health check to avoid database errors with too many connections
settings.register_profile(
    "ci",
    max_examples=10,
    deadline=2000,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
)
settings.load_profile("ci")

# --- Strategies for data generation ---

# Strategy for generating a variety of text strings
text_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{}|;:',./<>? `~",
    min_size=0,
    max_size=255,
)

# Strategy for generating dates as strings in YYYY-MM-DD format
date_strategy = st.dates(min_value=date(1990, 1, 1), max_value=date(2030, 12, 31)).map(
    lambda d: d.strftime("%Y-%m-%d")
)

# Strategy for generating boolean-like values (checkboxes)
boolean_strategy = st.one_of(st.just("on"), st.just(""))


def _setup_and_login(app, client):
    """Helper function to set up base data and log in admin for each fuzzed example."""
    with app.app_context():
        # Ensure a clean state for admin, customer, source for each example
        db.session.query(User).filter_by(username="fuzz_admin").delete()
        db.session.query(Customer).filter_by(CustID="FUZZ_CUST").delete()
        db.session.query(Source).filter_by(SSource="FUZZ_SRC").delete()
        db.session.commit()

        admin = User(
            username="fuzz_admin",
            email="fuzz@example.com",
            password_hash=generate_password_hash("fuzzpassword"),
            role="admin",
        )
        customer = Customer(CustID="FUZZ_CUST", Name="Fuzz Customer")
        source = Source(SSource="FUZZ_SRC")
        db.session.add_all([admin, customer, source])
        db.session.commit()

    client.post("/login", data={"username": "fuzz_admin", "password": "fuzzpassword"})
    return {"cust_id": "FUZZ_CUST", "source_id": "FUZZ_SRC"}


# --- Fuzzing Tests for Work Orders ---


class TestWorkOrderFuzzing:
    @given(
        WOName=text_strategy,
        StorageTime=text_strategy,
        RackNo=text_strategy,
        final_location=text_strategy,
        SpecialInstructions=text_strategy,
        RepairsNeeded=boolean_strategy,
        ReturnStatus=text_strategy,
        ShipTo=text_strategy,
        Quote=text_strategy,
        RushOrder=boolean_strategy,
        FirmRush=boolean_strategy,
        DateRequired=st.one_of(date_strategy, text_strategy),
        Clean=st.one_of(date_strategy, text_strategy),
        Treat=st.one_of(date_strategy, text_strategy),
        DateCompleted=st.one_of(date_strategy, text_strategy),
    )
    def test_fuzz_create_work_order(
        self,
        client,
        app,
        WOName,
        StorageTime,
        RackNo,
        final_location,
        SpecialInstructions,
        RepairsNeeded,
        ReturnStatus,
        ShipTo,
        Quote,
        RushOrder,
        FirmRush,
        DateRequired,
        Clean,
        Treat,
        DateCompleted,
    ):
        """Fuzz test for creating a work order."""
        setup_data = _setup_and_login(app, client)
        with app.app_context():
            data = {
                "CustID": setup_data["cust_id"],
                "WOName": WOName,
                "StorageTime": StorageTime,
                "RackNo": RackNo,
                "final_location": final_location,
                "SpecialInstructions": SpecialInstructions,
                "RepairsNeeded": RepairsNeeded,
                "ReturnStatus": ReturnStatus,
                "ShipTo": ShipTo,
                "Quote": Quote,
                "RushOrder": RushOrder,
                "FirmRush": FirmRush,
                "DateRequired": DateRequired,
                "Clean": Clean,
                "Treat": Treat,
                "DateCompleted": DateCompleted,
            }
            response = client.post("/work_orders/new", data=data)
            assert response.status_code != 500

    @given(
        WOName=text_strategy,
        StorageTime=text_strategy,
        RackNo=text_strategy,
        final_location=text_strategy,
        SpecialInstructions=text_strategy,
        RepairsNeeded=boolean_strategy,
        ReturnStatus=text_strategy,
        ShipTo=text_strategy,
        Quote=text_strategy,
        RushOrder=boolean_strategy,
        FirmRush=boolean_strategy,
        DateRequired=st.one_of(date_strategy, text_strategy),
        Clean=st.one_of(date_strategy, text_strategy),
        Treat=st.one_of(date_strategy, text_strategy),
        DateCompleted=st.one_of(date_strategy, text_strategy),
    )
    def test_fuzz_edit_work_order(
        self,
        client,
        app,
        WOName,
        StorageTime,
        RackNo,
        final_location,
        SpecialInstructions,
        RepairsNeeded,
        ReturnStatus,
        ShipTo,
        Quote,
        RushOrder,
        FirmRush,
        DateRequired,
        Clean,
        Treat,
        DateCompleted,
    ):
        """Fuzz test for editing a work order."""
        setup_data = _setup_and_login(app, client)
        with app.app_context():
            unique_wo_no = str(uuid.uuid4().int)[:10]  # Generate a unique WO number
            # Create a work order to edit first
            wo = WorkOrder(
                WorkOrderNo=unique_wo_no, CustID=setup_data["cust_id"], WOName="Initial Name"
            )
            db.session.add(wo)
            db.session.commit()

            data = {
                "CustID": setup_data["cust_id"],
                "WOName": WOName,
                "StorageTime": StorageTime,
                "RackNo": RackNo,
                "final_location": final_location,
                "SpecialInstructions": SpecialInstructions,
                "RepairsNeeded": RepairsNeeded,
                "ReturnStatus": ReturnStatus,
                "ShipTo": ShipTo,
                "Quote": Quote,
                "RushOrder": RushOrder,
                "FirmRush": FirmRush,
                "DateRequired": DateRequired,
                "Clean": Clean,
                "Treat": Treat,
                "DateCompleted": DateCompleted,
            }
            response = client.post(f"/work_orders/edit/{unique_wo_no}", data=data)
            assert response.status_code != 500

    @given(work_order_no=text_strategy)
    def test_fuzz_view_work_order(self, app, client, work_order_no):
        """Fuzz test for viewing a work order."""
        _setup_and_login(app, client)
        with app.app_context():
            response = client.get(f"/work_orders/{work_order_no}")
            assert response.status_code in (200, 404)  # OK or Not Found, no 500

    @given(work_order_no=text_strategy, file_id=st.one_of(
        st.integers(min_value=-10000, max_value=10000).map(str),
        text_strategy,
    ))
    def test_fuzz_download_work_order_file(
        self, app, client, work_order_no, file_id
    ):
        """Fuzz test for downloading files."""
        _setup_and_login(app, client)
        with app.app_context():
            response = client.get(
                f"/work_orders/{work_order_no}/files/{file_id}/download"
            )
            assert response.status_code in (
                200,
                302,
                308,
                404,
            )  # OK, redirect, permanent redirect, or Not Found

    @given(work_order_no=text_strategy)
    def test_fuzz_delete_work_order(self, app, client, work_order_no):
        """Fuzz test for deleting a work order."""
        _setup_and_login(app, client)
        with app.app_context():
            response = client.post(f"/work_orders/delete/{work_order_no}")
            assert response.status_code in (302, 404)  # Redirect or Not Found, no 500

    @given(work_order_no=text_strategy)
    def test_fuzz_download_work_order_pdf(
        self, app, client, work_order_no
    ):
        """Fuzz test for downloading PDF."""
        _setup_and_login(app, client)
        with app.app_context():
            response = client.get(f"/work_orders/{work_order_no}/pdf/download")
            assert response.status_code in (200, 302, 308, 404)  # OK, redirect, permanent redirect, or Not Found


# --- Fuzzing Tests for Repair Orders ---


class TestRepairOrderFuzzing:
    @given(
        ROName=text_strategy,
        SOURCE=text_strategy,
        WO_DATE=st.one_of(date_strategy, text_strategy),
        DATE_TO_SUB=st.one_of(date_strategy, text_strategy),
        DateRequired=st.one_of(date_strategy, text_strategy),
        RushOrder=boolean_strategy,
        FirmRush=boolean_strategy,
        QUOTE=boolean_strategy,
        QUOTE_BY=text_strategy,
        APPROVED=boolean_strategy,
        RackNo=text_strategy,
        STORAGE=text_strategy,
        SPECIALINSTRUCTIONS=text_strategy,
        CLEAN=boolean_strategy,
        SEECLEAN=text_strategy,
        REPAIRSDONEBY=text_strategy,
        DateCompleted=st.one_of(date_strategy, text_strategy),
        MaterialList=text_strategy,
        CUSTOMERPRICE=text_strategy,
        RETURNSTATUS=text_strategy,
        RETURNDATE=st.one_of(date_strategy, text_strategy),
        LOCATION=text_strategy,
        final_location=text_strategy,
        DATEOUT=st.one_of(date_strategy, text_strategy),
    )
    def test_fuzz_create_repair_order(
        self,
        client,
        app,
        ROName,
        SOURCE,
        WO_DATE,
        DATE_TO_SUB,
        DateRequired,
        RushOrder,
        FirmRush,
        QUOTE,
        QUOTE_BY,
        APPROVED,
        RackNo,
        STORAGE,
        SPECIALINSTRUCTIONS,
        CLEAN,
        SEECLEAN,
        REPAIRSDONEBY,
        DateCompleted,
        MaterialList,
        CUSTOMERPRICE,
        RETURNSTATUS,
        RETURNDATE,
        LOCATION,
        final_location,
        DATEOUT,
    ):
        """Fuzz test for creating a repair order."""
        setup_data = _setup_and_login(app, client)
        with app.app_context():
            data = {
                "CustID": setup_data["cust_id"],
                "ROName": ROName,
                "SOURCE": SOURCE,
                "WO_DATE": WO_DATE,
                "DATE_TO_SUB": DATE_TO_SUB,
                "DateRequired": DateRequired,
                "RushOrder": RushOrder,
                "FirmRush": FirmRush,
                "QUOTE": QUOTE,
                "QUOTE_BY": QUOTE_BY,
                "APPROVED": APPROVED,
                "RackNo": RackNo,
                "STORAGE": STORAGE,
                "SPECIALINSTRUCTIONS": SPECIALINSTRUCTIONS,
                "CLEAN": CLEAN,
                "SEECLEAN": SEECLEAN,
                "REPAIRSDONEBY": REPAIRSDONEBY,
                "DateCompleted": DateCompleted,
                "MaterialList": MaterialList,
                "CUSTOMERPRICE": CUSTOMERPRICE,
                "RETURNSTATUS": RETURNSTATUS,
                "RETURNDATE": RETURNDATE,
                "LOCATION": LOCATION,
                "final_location": final_location,
                "DATEOUT": DATEOUT,
            }
            response = client.post("/repair_work_orders/new", data=data)
            assert response.status_code != 500

    @given(
        ROName=text_strategy,
        SOURCE=text_strategy,
        WO_DATE=st.one_of(date_strategy, text_strategy),
        DATE_TO_SUB=st.one_of(date_strategy, text_strategy),
        DateRequired=st.one_of(date_strategy, text_strategy),
        RushOrder=boolean_strategy,
        FirmRush=boolean_strategy,
        QUOTE=boolean_strategy,
        QUOTE_BY=text_strategy,
        APPROVED=boolean_strategy,
        RackNo=text_strategy,
        STORAGE=text_strategy,
        SPECIALINSTRUCTIONS=text_strategy,
        CLEAN=boolean_strategy,
        SEECLEAN=text_strategy,
        REPAIRSDONEBY=text_strategy,
        DateCompleted=st.one_of(date_strategy, text_strategy),
        MaterialList=text_strategy,
        CUSTOMERPRICE=text_strategy,
        RETURNSTATUS=text_strategy,
        RETURNDATE=st.one_of(date_strategy, text_strategy),
        LOCATION=text_strategy,
        final_location=text_strategy,
        DATEOUT=st.one_of(date_strategy, text_strategy),
    )
    def test_fuzz_edit_repair_order(
        self,
        client,
        app,
        ROName,
        SOURCE,
        WO_DATE,
        DATE_TO_SUB,
        DateRequired,
        RushOrder,
        FirmRush,
        QUOTE,
        QUOTE_BY,
        APPROVED,
        RackNo,
        STORAGE,
        SPECIALINSTRUCTIONS,
        CLEAN,
        SEECLEAN,
        REPAIRSDONEBY,
        DateCompleted,
        MaterialList,
        CUSTOMERPRICE,
        RETURNSTATUS,
        RETURNDATE,
        LOCATION,
        final_location,
        DATEOUT,
    ):
        """Fuzz test for editing a repair order."""
        setup_data = _setup_and_login(app, client)
        with app.app_context():
            unique_ro_no = str(uuid.uuid4().int)[:10]  # Generate a unique RO number
            # Create a repair order to edit first
            ro = RepairWorkOrder(
                RepairOrderNo=unique_ro_no, CustID=setup_data["cust_id"], ROName="Initial Name"
            )
            db.session.add(ro)
            db.session.commit()

            data = {
                "CustID": setup_data["cust_id"],
                "ROName": ROName,
                "SOURCE": SOURCE,
                "WO_DATE": WO_DATE,
                "DATE_TO_SUB": DATE_TO_SUB,
                "DateRequired": DateRequired,
                "RushOrder": RushOrder,
                "FirmRush": FirmRush,
                "QUOTE": QUOTE,
                "QUOTE_BY": QUOTE_BY,
                "APPROVED": APPROVED,
                "RackNo": RackNo,
                "STORAGE": STORAGE,
                "SPECIALINSTRUCTIONS": SPECIALINSTRUCTIONS,
                "CLEAN": CLEAN,
                "SEECLEAN": SEECLEAN,
                "REPAIRSDONEBY": REPAIRSDONEBY,
                "DateCompleted": DateCompleted,
                "MaterialList": MaterialList,
                "CUSTOMERPRICE": CUSTOMERPRICE,
                "RETURNSTATUS": RETURNSTATUS,
                "RETURNDATE": RETURNDATE,
                "LOCATION": LOCATION,
                "final_location": final_location,
                "DATEOUT": DATEOUT,
            }
            response = client.post(
                f"/repair_work_orders/{unique_ro_no}/edit", data=data
            )
            assert response.status_code != 500
