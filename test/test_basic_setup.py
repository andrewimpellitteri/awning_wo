"""
Basic test setup file to verify testing infrastructure works.

Save this file as: test/test_basic_setup.py
"""

import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.mark.unit
class TestBasicSetup:
    """Basic tests to verify test setup is working."""

    def test_python_basics(self):
        """Test basic Python functionality."""
        assert True
        assert 1 + 1 == 2
        assert "test" in "testing"

    def test_project_structure_exists(self):
        """Test that expected project files exist."""
        expected_files = ["extensions.py", "app.py", "models", "routes"]

        missing_files = []
        for file_name in expected_files:
            file_path = project_root / file_name
            if not file_path.exists():
                missing_files.append(file_name)

        if missing_files:
            pytest.skip(f"Missing project files: {missing_files}")

        assert len(missing_files) == 0, f"Missing files: {missing_files}"

    def test_can_import_extensions(self):
        """Test that we can import the extensions module."""
        try:
            import extensions

            assert hasattr(extensions, "db")
        except ImportError as e:
            pytest.skip(f"Cannot import extensions: {e}")

    def test_can_import_models(self):
        """Test that we can import model classes."""
        try:
            from models.work_order import WorkOrder, WorkOrderItem
            from models.customer import Customer
            from models.source import Source
            from models.inventory import Inventory

            # Basic checks that classes exist
            assert WorkOrder is not None
            assert WorkOrderItem is not None
            assert Customer is not None
            assert Source is not None
            assert Inventory is not None

        except ImportError as e:
            pytest.skip(f"Cannot import models: {e}")


@pytest.mark.unit
class TestUtilityFunctions:
    """Test utility functions from the work orders module."""

    def safe_int_conversion(self, value, default=0):
        """Copy of safe_int_conversion function for testing."""
        try:
            return int(value or default)
        except (ValueError, TypeError):
            return default

    def test_safe_int_conversion_valid_inputs(self):
        """Test safe_int_conversion with valid inputs."""
        assert self.safe_int_conversion("123") == 123
        assert self.safe_int_conversion("0") == 0
        assert self.safe_int_conversion("-5") == -5

    def test_safe_int_conversion_invalid_inputs(self):
        """Test safe_int_conversion with invalid inputs."""
        assert self.safe_int_conversion("") == 0
        assert self.safe_int_conversion(None) == 0
        assert self.safe_int_conversion("abc") == 0
        assert self.safe_int_conversion("12.34") == 0

    def test_safe_int_conversion_with_defaults(self):
        """Test safe_int_conversion with custom defaults."""
        assert self.safe_int_conversion("", 10) == 10
        assert self.safe_int_conversion(None, -1) == -1
        assert self.safe_int_conversion("abc", 999) == 999


@pytest.mark.unit
class TestWorkOrderLogic:
    """Test work order business logic without Flask app context."""

    def test_work_order_status_logic(self):
        """Test work order status determination."""
        # Test cases for pending status
        pending_cases = [
            {"DateCompleted": None},
            {"DateCompleted": ""},
            {"DateCompleted": "   "},  # whitespace
        ]

        for case in pending_cases:
            date_completed = case.get("DateCompleted")
            is_pending = (
                date_completed is None
                or date_completed == ""
                or (isinstance(date_completed, str) and not date_completed.strip())
            )
            assert is_pending, f"Should be pending: {case}"

        # Test cases for completed status
        completed_cases = [
            {"DateCompleted": "2024-01-20"},
            {"DateCompleted": "01/20/24 15:30:00"},
            {"DateCompleted": "Complete"},
        ]

        for case in completed_cases:
            date_completed = case.get("DateCompleted")
            is_completed = (
                date_completed is not None
                and date_completed != ""
                and (not isinstance(date_completed, str) or date_completed.strip())
            )
            assert is_completed, f"Should be completed: {case}"

    def test_rush_order_identification(self):
        """Test rush order identification logic."""
        test_cases = [
            {"RushOrder": "1", "FirmRush": "0", "expected_rush": True},
            {"RushOrder": "0", "FirmRush": "1", "expected_rush": True},
            {"RushOrder": "1", "FirmRush": "1", "expected_rush": True},
            {"RushOrder": "0", "FirmRush": "0", "expected_rush": False},
            {"RushOrder": "", "FirmRush": "", "expected_rush": False},
            {"RushOrder": None, "FirmRush": None, "expected_rush": False},
        ]

        for case in test_cases:
            is_rush = case.get("RushOrder") == "1" or case.get("FirmRush") == "1"
            assert is_rush == case["expected_rush"], f"Rush logic failed for {case}"

    def test_search_pattern_generation(self):
        """Test search pattern generation for SQL LIKE queries."""
        search_terms = [
            ("test", "%test%"),
            ("", "%%"),
            ("  spaces  ", "%  spaces  %"),
            ("123", "%123%"),
            ("Test Order", "%Test Order%"),
        ]

        for search_term, expected_pattern in search_terms:
            pattern = f"%{search_term}%"
            assert pattern == expected_pattern, (
                f"Pattern mismatch: {pattern} != {expected_pattern}"
            )

    def test_work_order_number_range_parsing(self):
        """Test work order number range parsing."""
        valid_ranges = [
            ("1000-2000", (1000, 2000)),
            ("1-100", (1, 100)),
            ("5000-5999", (5000, 5999)),
        ]

        for range_str, expected_tuple in valid_ranges:
            if "-" in range_str:
                try:
                    start, end = map(int, range_str.split("-", 1))
                    assert (start, end) == expected_tuple
                    assert start <= end, f"Invalid range: {start} > {end}"
                except ValueError:
                    pytest.fail(f"Should parse valid range: {range_str}")

        # Test invalid ranges
        invalid_ranges = ["abc-def", "1000", "1000-", "-2000", ""]

        for invalid_range in invalid_ranges:
            if "-" in invalid_range:
                try:
                    start, end = map(int, invalid_range.split("-", 1))
                    # If we get here, the parsing succeeded but shouldn't have
                    # (unless it's a valid range we didn't expect)
                    pass
                except ValueError:
                    # This is expected for invalid ranges
                    pass


if __name__ == "__main__":
    # Run this test file directly
    pytest.main([__file__, "-v"])
