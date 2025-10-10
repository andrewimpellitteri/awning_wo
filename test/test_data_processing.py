"""
Unit tests for data_processing utility functions.
Tests all edge cases for parsing size/weight data.
"""

import pytest
import pandas as pd
from utils.data_processing import (
    clean_numeric_string,
    clean_sail_weight,
    clean_square_footage,
    identify_product_type,
    parse_work_order_items,
    _feet_inches_to_feet,
    _extract_calculated_value,
    _parse_dimension_string,
    _parse_circular_dimension,
    _parse_yardage,
    _parse_simple_footage,
    _parse_ea_price,
)


@pytest.mark.unit
class TestCleanNumericString:
    """Test clean_numeric_string function."""

    def test_clean_currency(self):
        assert clean_numeric_string("$1,234.56") == 1234.56
        assert clean_numeric_string("$100") == 100.0
        assert clean_numeric_string("$10,000.00") == 10000.0

    def test_clean_plain_numbers(self):
        assert clean_numeric_string("1234.56") == 1234.56
        assert clean_numeric_string("100") == 100.0
        assert clean_numeric_string(100) == 100.0
        assert clean_numeric_string(123.45) == 123.45

    def test_clean_special_values(self):
        assert clean_numeric_string("Approved") == 0.0
        assert clean_numeric_string("") == 0.0
        assert clean_numeric_string(None) == 0.0
        assert clean_numeric_string(pd.NA) == 0.0

    def test_clean_invalid(self):
        assert clean_numeric_string("abc") == 0.0
        assert clean_numeric_string("$") == 0.0


@pytest.mark.unit
class TestCleanSailWeight:
    """Test clean_sail_weight function."""

    def test_valid_sail_weights(self):
        assert clean_sail_weight("30#") == 30.0
        assert clean_sail_weight("40#") == 40.0
        assert clean_sail_weight("95#") == 95.0
        assert clean_sail_weight("7#") == 7.0
        assert clean_sail_weight("2#") == 2.0

    def test_decimal_sail_weights(self):
        assert clean_sail_weight("30.5#") == 30.5
        assert clean_sail_weight("45.25#") == 45.25

    def test_invalid_sail_weights(self):
        assert clean_sail_weight("") == 0.0
        assert clean_sail_weight(".") == 0.0
        assert clean_sail_weight(None) == 0.0
        assert clean_sail_weight("30") == 0.0  # Missing #
        assert clean_sail_weight("#30") == 0.0  # Wrong position


@pytest.mark.unit
class TestFeetInchesToFeet:
    """Test _feet_inches_to_feet conversion."""

    def test_feet_and_inches(self):
        assert _feet_inches_to_feet("10'6\"") == 10.5
        assert _feet_inches_to_feet("8'9\"") == 8.75
        assert _feet_inches_to_feet("10'0\"") == 10.0
        assert _feet_inches_to_feet("0'6\"") == 0.5

    def test_feet_only(self):
        assert _feet_inches_to_feet("10'") == 10.0
        assert _feet_inches_to_feet("25'") == 25.0

    def test_inches_only(self):
        assert _feet_inches_to_feet('6"') == 0.5
        assert _feet_inches_to_feet('12"') == 1.0
        assert _feet_inches_to_feet('3"') == 0.25

    def test_plain_numbers(self):
        assert _feet_inches_to_feet("10") == 10.0
        assert _feet_inches_to_feet("5.5") == 5.5


@pytest.mark.unit
class TestExtractCalculatedValue:
    """Test _extract_calculated_value function."""

    def test_simple_calculated(self):
        assert _extract_calculated_value("8x10=80'") == (80.0, True)
        assert _extract_calculated_value("10'10x10'11=118.26'") == (118.26, True)

    def test_calculated_with_text(self):
        assert _extract_calculated_value("8'9wide=90.00 ea.") == (90.0, True)
        assert _extract_calculated_value("7x10=70'??/1400'") == (70.0, True)

    def test_no_calculated(self):
        assert _extract_calculated_value("8x10") == (0.0, False)
        assert _extract_calculated_value("10'6\"") == (0.0, False)


@pytest.mark.unit
class TestParseDimensionString:
    """Test _parse_dimension_string function."""

    def test_simple_dimensions(self):
        assert _parse_dimension_string("8x10") == 80.0
        assert _parse_dimension_string("10x10") == 100.0
        assert _parse_dimension_string("5x4") == 20.0

    def test_feet_dimensions(self):
        assert _parse_dimension_string("10'x10'") == 100.0
        assert _parse_dimension_string("8'6\"x10'") == 85.0

    def test_approximations(self):
        assert _parse_dimension_string("~10x6") == 60.0
        assert _parse_dimension_string("~8x10") == 80.0

    def test_precalculated_dimensions(self):
        assert _parse_dimension_string("10'10x10'11=118.26'") == 118.26
        assert _parse_dimension_string("8x10=80'") == 80.0

    def test_dimensions_with_modifiers(self):
        # These should use pre-calculated values
        assert _parse_dimension_string("10x6-cutouts=55'") == 55.0
        assert _parse_dimension_string("10'10x10'2-wings=120'") == 120.0

    def test_complex_dimensions(self):
        # Multiple sections added together (when no = present)
        result = _parse_dimension_string("10x5+2x3")
        assert result == 56.0  # 50 + 6


@pytest.mark.unit
class TestParseCircularDimension:
    """Test _parse_circular_dimension function."""

    def test_circular_with_calculated(self):
        assert _parse_circular_dimension("4'8R=68.48'") == 68.48
        assert _parse_circular_dimension("7'R=153.86'") == 153.86
        assert _parse_circular_dimension("14' round=153.86'") == 153.86

    def test_circular_without_calculated(self):
        # When no pre-calculated, should calculate from radius
        import math

        result = _parse_circular_dimension("4'R")
        expected = round(math.pi * (4**2), 2)
        assert abs(result - expected) < 0.01


@pytest.mark.unit
class TestParseYardage:
    """Test _parse_yardage function."""

    def test_yardage_formats(self):
        assert _parse_yardage("44 yds.") == 44.0
        assert _parse_yardage("33 yds") == 33.0
        assert _parse_yardage("55 yds.") == 55.0
        assert _parse_yardage("11 yd") == 11.0

    def test_decimal_yardage(self):
        assert _parse_yardage("44.5 yds") == 44.5


@pytest.mark.unit
class TestParseSimpleFootage:
    """Test _parse_simple_footage function."""

    def test_simple_footage(self):
        assert _parse_simple_footage("25'") == 25.0
        assert _parse_simple_footage("318.13'") == 318.13
        assert _parse_simple_footage("11.5'") == 11.5
        assert _parse_simple_footage("137'") == 137.0


@pytest.mark.unit
class TestParseEaPrice:
    """Test _parse_ea_price function."""

    def test_ea_notation(self):
        assert _parse_ea_price("16.00 ea.") == 16.0
        assert _parse_ea_price("35.00 ea") == 35.0
        assert _parse_ea_price("$49 ea.") == 49.0


@pytest.mark.unit
class TestCleanSquareFootage:
    """Test clean_square_footage comprehensive function."""

    def test_sail_weights(self):
        assert clean_square_footage("30#") == 30.0
        assert clean_square_footage("40#") == 40.0
        assert clean_square_footage("95#") == 95.0

    def test_simple_dimensions(self):
        assert clean_square_footage("8x10") == 80.0
        assert clean_square_footage("10x10") == 100.0

    def test_feet_inches_dimensions(self):
        assert clean_square_footage("10'6\"x8'3\"") == pytest.approx(86.625, 0.01)
        assert clean_square_footage("10'x10'") == 100.0

    def test_precalculated_dimensions(self):
        assert clean_square_footage("10'10x10'11=118.26'") == 118.26
        assert clean_square_footage("8x10=80'") == 80.0
        assert clean_square_footage("100'4\"x16'10=1688.72'") == 1688.72

    def test_approximations(self):
        assert clean_square_footage("~10x6") == 60.0
        assert clean_square_footage("~8'2x4'8-wings=55.13'") == 55.13

    def test_circular_dimensions(self):
        assert clean_square_footage("4'8R=68.48'") == 68.48
        assert clean_square_footage("7'R=153.86'") == 153.86
        assert clean_square_footage("14' round=153.86'") == 153.86

    def test_yardage(self):
        assert clean_square_footage("44 yds.") == 44.0
        assert clean_square_footage("33 yds") == 33.0

    def test_simple_footage(self):
        assert clean_square_footage("25'") == 25.0
        assert clean_square_footage("318.13'") == 318.13
        assert clean_square_footage("11.5'") == 11.5

    def test_ea_notation(self):
        assert clean_square_footage("16.00 ea.") == 16.0
        assert clean_square_footage("35.00 ea.") == 35.0

    def test_plain_numbers(self):
        assert clean_square_footage("100") == 100.0
        assert clean_square_footage("50.5") == 50.5

    def test_invalid_empty(self):
        assert clean_square_footage("") == 0.0
        assert clean_square_footage(".") == 0.0
        assert clean_square_footage("na") == 0.0
        assert clean_square_footage("n/a") == 0.0
        assert clean_square_footage(None) == 0.0
        assert clean_square_footage("*") == 0.0
        assert clean_square_footage("?") == 0.0

    def test_complex_with_modifiers(self):
        # Test strings with wings, cutouts, flaps, etc.
        assert clean_square_footage("9'7x9'7+flaps=96.78'") == 96.78
        assert clean_square_footage("7'3x4'5+wings=49'") == 49.0
        assert clean_square_footage("~19x10-cutouts=80'") == 80.0

    def test_database_samples(self):
        """Test actual samples from the database."""
        # From query results
        assert clean_square_footage("10'10x10=108.3'") == 108.3
        assert clean_square_footage("10'10x10'10-hole=108.29'") == 108.29
        assert clean_square_footage("10'10x11'10=128.12'") == 128.12
        assert clean_square_footage("10'11x7'2=78.3'") == 78.3
        assert clean_square_footage("10'/15.00") == 10.0  # Simple footage
        assert clean_square_footage("~10'/15.00") == 10.0
        assert clean_square_footage("4'9R=70.84'") == 70.84
        assert clean_square_footage("4'6R=63.59'") == 63.59


@pytest.mark.unit
class TestIdentifyProductType:
    """Test identify_product_type function."""

    def test_sail_identification(self):
        assert identify_product_type("30#") == "Sail"
        assert identify_product_type("40#") == "Sail"
        assert identify_product_type("95#") == "Sail"

    def test_awning_identification(self):
        assert identify_product_type("8x10") == "Awning"
        assert identify_product_type("10'x10'") == "Awning"
        assert identify_product_type("44 yds.") == "Awning"
        assert identify_product_type("25'") == "Awning"

    def test_null_identification(self):
        assert identify_product_type(None) == "Awning"
        assert identify_product_type("") == "Awning"


@pytest.mark.unit
class TestParseWorkOrderItems:
    """Test parse_work_order_items DataFrame processing."""

    def test_parse_work_order_items_dataframe(self):
        # Create sample DataFrame
        data = {
            "workorderno": ["WO001", "WO001", "WO002"],
            "custid": [1, 1, 2],
            "qty": [2, 1, 3],
            "sizewgt": ["30#", "8x10", "44 yds."],
            "price": ["$50.00", "$100.00", "$25.00"],
        }
        df = pd.DataFrame(data)

        # Process
        result = parse_work_order_items(df)

        # Check columns added
        assert "price_numeric" in result.columns
        assert "product_type" in result.columns
        assert "qty_numeric" in result.columns
        assert "sqft" in result.columns

        # Check values
        assert result.iloc[0]["price_numeric"] == 50.0
        assert result.iloc[0]["product_type"] == "Sail"
        assert result.iloc[0]["qty_numeric"] == 2
        assert result.iloc[0]["sqft"] == 0.0  # Sails excluded from sqft calculation

        assert result.iloc[1]["product_type"] == "Awning"
        assert result.iloc[1]["sqft"] == 80.0  # 1 * 80

        assert result.iloc[2]["sqft"] == 132.0  # 3 * 44

    def test_parse_with_missing_values(self):
        data = {
            "workorderno": ["WO001"],
            "custid": [1],
            "qty": [None],
            "sizewgt": [""],
            "price": [None],
        }
        df = pd.DataFrame(data)

        result = parse_work_order_items(df)

        assert result.iloc[0]["price_numeric"] == 0.0
        assert result.iloc[0]["qty_numeric"] == 0.0
        assert result.iloc[0]["sqft"] == 0.0


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and unusual patterns."""

    def test_multiple_operators(self):
        # Multiplication and division
        assert clean_square_footage("10'10x2'8=28.92'-5.16=23.76'") == 28.92

    def test_question_marks(self):
        assert clean_square_footage("100'?") == 100.0
        assert clean_square_footage("~1000'") == 1000.0

    def test_slashes_and_alternatives(self):
        assert clean_square_footage("10'10x3'10=41.48'/45.63") == 41.48

    def test_caps_and_faces(self):
        assert clean_square_footage("~10'10x10+caps=140.23'") == 140.23
        assert clean_square_footage("10'10x12'5+faces=167.11'") == 167.11

    def test_whitespace_variations(self):
        assert clean_square_footage(" 8x10 ") == 80.0
        assert clean_square_footage("8 x 10") == 80.0
        assert clean_square_footage("  30#  ") == 30.0

    def test_case_insensitivity(self):
        assert clean_square_footage("44 YDS") == 44.0
        assert clean_square_footage("44 Yds") == 44.0
        assert clean_square_footage("16.00 EA") == 16.0

    def test_mixed_formats(self):
        # Combined dimensions
        assert clean_square_footage("24'9x15+13'5x5'5=584.73'") == 584.73
        assert clean_square_footage("11'3x10'1+19'2x22'9=579.54'") == 579.54
