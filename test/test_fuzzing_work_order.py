"""
Fuzzing tests for Work Order routes.

This test suite uses the Hypothesis library to generate a wide range of
unexpected and edge-case data to test the robustness of various routes for Work Orders.

The goal is to ensure that the application can handle malformed, invalid, or
unexpected data without crashing (i.e., returning a 500 Internal Server Error),
while also verifying semantic correctness where possible (e.g., no unintended DB changes).
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume, note
from models.work_order import WorkOrder, WorkOrderItem
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

# Define a profile with suppressed health checks and limited examples for CI
settings.register_profile(
    "ci",
    max_examples=20,
    deadline=2000,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
settings.load_profile("ci")

# --- Strategies for data generation ---

# Text strategy with broader alphabet, including potential injection chars
text_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),  # Avoid surrogates
    min_size=0,
    max_size=1024,  # Larger for overflow testing
)

# Date strategy: valid dates or invalid strings
date_strategy = st.one_of(
    st.dates(min_value=date(1900, 1, 1), max_value=date(2100, 12, 31)).map(
        lambda d: d.strftime("%Y-%m-%d")
    ),
    text_strategy,  # Invalid dates
)

# Boolean strategy: checkbox values, including invalids
boolean_strategy = st.one_of(
    st.just("on"),
    st.just(""),
    st.just("true"),
    st.just("false"),
    st.just("1"),
    st.just("0"),
    text_strategy,
)

# Integer strategy: valid ints or strings, including negatives/invalids
int_strategy = st.one_of(
    st.integers(min_value=-10000, max_value=10000).map(str),
    text_strategy,
)

# Float strategy for prices
float_strategy = st.one_of(
    st.floats(allow_nan=True, allow_infinity=True).map(str),
    text_strategy,
)

# Strategy for lists (e.g., new items)
list_strategy = st.lists(text_strategy, min_size=0, max_size=5)

# File strategy: generate fake files with content
file_strategy = st.builds(
    lambda content, filename: {"filename": filename, "content": content},
    st.binary(min_size=0, max_size=1024 * 1024),  # Up to 1MB
    text_strategy.filter(lambda x: "." in x),  # Fake filenames with extension
)

# Multi-file strategy
files_strategy = st.lists(file_strategy, min_size=0, max_size=3)


# Composite strategy for work order form data
@st.composite
def work_order_data_strategy(draw):
    data = {
        "CustID": draw(text_strategy),
        "WOName": draw(text_strategy),
        "StorageTime": draw(text_strategy),
        "RackNo": draw(text_strategy),
        "final_location": draw(text_strategy),
        "SpecialInstructions": draw(text_strategy),
        "RepairsNeeded": draw(boolean_strategy),
        "ReturnStatus": draw(text_strategy),
        "ShipTo": draw(text_strategy),
        "Quote": draw(text_strategy),
        "RushOrder": draw(boolean_strategy),
        "FirmRush": draw(boolean_strategy),
        "DateRequired": draw(date_strategy),
        "Clean": draw(date_strategy),
        "Treat": draw(date_strategy),
        "DateCompleted": draw(date_strategy),
        "SeeRepair": draw(text_strategy),
        # Item-related fields (fuzz lists for new/existing items)
        "new_item_description[]": draw(list_strategy),
        "new_item_material[]": draw(list_strategy),
        "new_item_qty[]": draw(st.lists(int_strategy, min_size=0, max_size=5)),
        "new_item_condition[]": draw(list_strategy),
        "new_item_color[]": draw(list_strategy),
        "new_item_size[]": draw(list_strategy),
        "new_item_price[]": draw(st.lists(float_strategy, min_size=0, max_size=5)),
        "selected_items[]": draw(
            st.lists(int_strategy, min_size=0, max_size=5)
        ),  # Inventory IDs
    }
    return data


# Fixture for transactional DB (rollback after each example)
@pytest.fixture(scope="function")
def transactional_db(app):
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        db.session.begin_nested()
        yield db.session
        db.session.rollback()
        transaction.rollback()
        connection.close()


def _setup_and_login(app, client):
    """Helper to set up base data and log in admin."""
    with app.app_context():
        # Clean up
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
    @given(data=st.builds(work_order_data_strategy), files=files_strategy)
    @settings(max_examples=50)
    def test_fuzz_create_work_order(self, app, client, transactional_db, data, files):
        """Fuzz test for creating a work order, including items and files."""
        setup_data = _setup_and_login(app, client)
        note(f"Input data: {data}")
        note(f"Files: {[f['filename'] for f in files]}")

        # Override CustID with valid one sometimes
        if random.random() > 0.5:
            data["CustID"] = setup_data["cust_id"]

        # Prepare multipart data
        form_data = data.copy()
        file_data = {
            f"files[{i}]": (BytesIO(file["content"]), file["filename"])
            for i, file in enumerate(files)
        }

        with app.app_context():
            response = client.post(
                "/work_orders/new",
                data={**form_data, **file_data},
                content_type="multipart/form-data",
            )
            assert response.status_code != 500

            # Semantic checks
            if response.status_code in (200, 302):  # Success/redirect
                wo = WorkOrder.query.filter_by(WOName=data.get("WOName")).first()
                assume(wo is not None)  # Filter invalid creations
                assert wo.CustID == data.get("CustID")  # Verify DB insertion
            else:
                # On failure, no DB change
                assert (
                    WorkOrder.query.filter_by(WOName=data.get("WOName")).first() is None
                )

    @given(data=st.builds(work_order_data_strategy), files=files_strategy)
    @settings(max_examples=50)
    def test_fuzz_edit_work_order(self, app, client, transactional_db, data, files):
        """Fuzz test for editing a work order, including items and files."""
        setup_data = _setup_and_login(app, client)
        with app.app_context():
            unique_wo_no = str(uuid.uuid4().int)[:10]
            wo = WorkOrder(
                WorkOrderNo=unique_wo_no,
                CustID=setup_data["cust_id"],
                WOName="Initial Name",
            )
            db.session.add(wo)
            db.session.commit()

            note(f"Input data: {data}")
            note(f"Files: {[f['filename'] for f in files]}")

            # Prepare multipart data
            form_data = data.copy()
            file_data = {
                f"files[{i}]": (BytesIO(file["content"]), file["filename"])
                for i, file in enumerate(files)
            }

            response = client.post(
                f"/work_orders/edit/{unique_wo_no}",
                data={**form_data, **file_data},
                content_type="multipart/form-data",
            )
            assert response.status_code != 500

            # Semantic checks
            updated_wo = WorkOrder.query.get(unique_wo_no)
            if response.status_code in (200, 302):
                # Check if updates applied (e.g., if valid)
                if "WOName" in data and data["WOName"]:
                    assert updated_wo.WOName == data["WOName"]
            else:
                # On failure, check no change
                assert updated_wo.WOName == "Initial Name"

    @given(work_order_no=text_strategy)
    def test_fuzz_view_work_order(self, app, client, transactional_db, work_order_no):
        """Fuzz test for viewing a work order."""
        _setup_and_login(app, client)
        with app.app_context():
            response = client.get(f"/work_orders/{work_order_no}")
            assert response.status_code in (200, 404)  # OK or Not Found, no 500

    @given(work_order_no=text_strategy, file_id=int_strategy)
    def test_fuzz_download_work_order_file(
        self, app, client, transactional_db, work_order_no, file_id
    ):
        """Fuzz test for downloading files."""
        _setup_and_login(app, client)
        with app.app_context():
            response = client.get(
                f"/work_orders/{work_order_no}/files/{file_id}/download"
            )
            assert response.status_code in (200, 302, 404)  # OK, redirect, or Not Found

    @given(work_order_no=text_strategy)
    def test_fuzz_delete_work_order(self, app, client, transactional_db, work_order_no):
        """Fuzz test for deleting a work order."""
        _setup_and_login(app, client)
        with app.app_context():
            response = client.post(f"/work_orders/delete/{work_order_no}")
            assert response.status_code in (302, 404)  # Redirect or Not Found, no 500

    @given(work_order_no=text_strategy)
    def test_fuzz_download_work_order_pdf(
        self, app, client, transactional_db, work_order_no
    ):
        """Fuzz test for downloading PDF."""
        _setup_and_login(app, client)
        with app.app_context():
            response = client.get(f"/work_orders/{work_order_no}/pdf/download")
            assert response.status_code in (200, 302, 404)  # OK, redirect, or Not Found
