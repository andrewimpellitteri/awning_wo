"""
Tests for utility helper functions.
"""

import pytest
from utils.helpers import format_date_from_str
from datetime import datetime


class TestFormatDateFromString:
    def test_format_date_from_str_mm_dd_yy_hh_mm_ss(self):
        """Test that the format_date_from_str function correctly parses MM/DD/YY HH:MM:SS."""
        date_str = "01/20/24 14:30:00"
        expected_date = datetime(2024, 1, 20, 14, 30)
        assert format_date_from_str(date_str) == expected_date

    def test_format_date_from_str_yyyy_mm_dd(self):
        """Test that the format_date_from_str function correctly parses YYYY-MM-DD."""
        date_str = "2024-01-20"
        expected_date = datetime(2024, 1, 20)
        assert format_date_from_str(date_str) == expected_date

    def test_format_date_from_str_none(self):
        """Test that the format_date_from_str function correctly handles None."""
        assert format_date_from_str(None) is None

    def test_format_date_from_str_empty(self):
        """Test that the format_date_from_str function correctly handles an empty string."""
        assert format_date_from_str("") is None


from utils.helpers import safe_date_sort_key, initialize_queue_positions_for_unassigned
from models.work_order import WorkOrder
from extensions import db

class TestSafeDateSortKey:
    def test_safe_date_sort_key_with_none(self):
        """Test that safe_date_sort_key handles None dates."""
        assert safe_date_sort_key(None) == datetime.min

    def test_safe_date_sort_key_with_datetime(self):
        """Test that safe_date_sort_key handles datetime objects."""
        now = datetime.now()
        assert safe_date_sort_key(now) == now

    def test_safe_date_sort_key_with_string(self):
        """Test that safe_date_sort_key handles string dates."""
        date_str = "2024-01-20"
        expected_date = datetime(2024, 1, 20)
        assert safe_date_sort_key(date_str) == expected_date


class TestInitializeQueuePositions:
    def test_initialize_queue_positions(self, app):
        """Test that initialize_queue_positions_for_unassigned assigns correct positions."""
        with app.app_context():
            wo1 = WorkOrder(WorkOrderNo="1001", queue_position=1)
            wo2 = WorkOrder(WorkOrderNo="1002", queue_position=None)
            wo3 = WorkOrder(WorkOrderNo="1003", queue_position=0)
            wo4 = WorkOrder(WorkOrderNo="1004", queue_position=None)

            db.session.add_all([wo1, wo2, wo3, wo4])
            db.session.commit()

            initialize_queue_positions_for_unassigned()

            assert WorkOrder.query.get("1001").queue_position == 1
            assert WorkOrder.query.get("1002").queue_position == 2
            assert WorkOrder.query.get("1003").queue_position == 0
            assert WorkOrder.query.get("1004").queue_position == 3

            db.session.query(WorkOrder).delete()
            db.session.commit()
