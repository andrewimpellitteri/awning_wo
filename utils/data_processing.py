"""
Data processing utilities for analytics dashboard.
Handles parsing of size/weight data from various formats with comprehensive edge case handling.
"""

import re
import pandas as pd
from typing import Union, Tuple


def clean_numeric_string(value: Union[str, float, int, None]) -> float:
    """
    Clean currency strings to float.

    Handles formats:
    - "$1,234.56" -> 1234.56
    - "1234.56" -> 1234.56
    - "Approved" -> 0.0
    - None, "", empty -> 0.0

    Args:
        value: String, number, or None to clean

    Returns:
        Float value, or 0.0 if invalid
    """
    if pd.isna(value) or value in ["", None, "Approved"]:
        return 0.0
    try:
        cleaned = str(value).replace("$", "").replace(",", "").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0


def clean_sail_weight(value: Union[str, float, int, None]) -> float:
    """
    Parse sail weight strings.

    Handles formats:
    - "30#" -> 30.0
    - "45#" -> 45.0
    - "95#" -> 95.0
    - Empty, None, "." -> 0.0

    Args:
        value: Sail weight string with # suffix

    Returns:
        Float weight value, or 0.0 if invalid
    """
    if pd.isna(value) or str(value).strip() in ["", "."]:
        return 0.0

    val_str = str(value).strip()
    match = re.match(r"^([\d.]+)#$", val_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def _feet_inches_to_feet(dim_str: str) -> float:
    """
    Convert feet-inches notation to decimal feet.

    Examples:
    - "10'6\"" -> 10.5
    - "8'9\"" -> 8.75
    - "10'" -> 10.0
    - "6\"" -> 0.5
    - "10" -> 10.0

    Args:
        dim_str: Dimension string with feet and/or inches

    Returns:
        Decimal feet value
    """
    dim_str = dim_str.strip()

    # Handle feet and inches: 10'6"
    if "'" in dim_str:
        parts = dim_str.split("'")
        try:
            feet = float(parts[0])
        except ValueError:
            feet = 0.0

        inches = 0.0
        if len(parts) > 1 and parts[1]:
            inches_str = parts[1].replace('"', '').strip()
            if inches_str:
                try:
                    inches = float(inches_str) / 12.0
                except ValueError:
                    inches = 0.0
        return feet + inches

    # Handle inches only: 6"
    elif '"' in dim_str:
        inches_str = dim_str.replace('"', '').strip()
        try:
            return float(inches_str) / 12.0
        except ValueError:
            return 0.0

    # Handle plain number
    else:
        try:
            return float(dim_str)
        except ValueError:
            return 0.0


def _extract_calculated_value(value_str: str) -> Tuple[float, bool]:
    """
    Extract pre-calculated square footage from strings with '=' notation.

    Handles:
    - "8x10=80'" -> (80.0, True)
    - "10'10x10'11=118.26'" -> (118.26, True)
    - "8'9wide=90.00 ea." -> (90.0, True)
    - "7x10=70'??/1400'" -> (70.0, True)

    Args:
        value_str: String potentially containing calculated value

    Returns:
        Tuple of (calculated_value, found_value)
    """
    if '=' not in value_str:
        return 0.0, False

    parts = value_str.split('=')
    if len(parts) < 2:
        return 0.0, False

    # Get the part after '='
    after_equals = parts[1].strip()

    # Extract numeric value (handle cases like "80'", "90.00 ea.", "70'??/1400'")
    # First try to get number before any special chars or slashes
    match = re.match(r"^([\d.]+)", after_equals)
    if match:
        try:
            return float(match.group(1)), True
        except ValueError:
            return 0.0, False

    return 0.0, False


def _parse_dimension_string(value_str: str) -> float:
    """
    Parse dimension strings with 'x' notation.

    Handles complex formats:
    - "8x10" -> 80.0
    - "10'6\"x8'3\"" -> 86.625
    - "~10x6" -> 60.0 (approximations)
    - "10'10x10'11=118.26'" -> 118.26 (uses calculated)
    - "10x6-cutouts=55'" -> 55.0 (uses calculated)
    - "10'10x10'2-wings=120'" -> 120.0
    - "24'9x15+13'5x5'5=584.73'" -> 584.73

    Args:
        value_str: Dimension string to parse

    Returns:
        Square footage value
    """
    # First check for pre-calculated value (most accurate)
    calc_val, found = _extract_calculated_value(value_str)
    if found and calc_val > 0:
        return calc_val

    # Remove approximation markers
    cleaned = value_str.replace('~', '').strip()

    # Handle complex expressions with + (multiple sections)
    if '+' in cleaned and '=' not in cleaned:
        # Try to sum multiple dimensions: "10x5+2x3"
        sections = cleaned.split('+')
        total = 0.0
        for section in sections:
            section = section.strip()
            # Remove descriptive text after dimensions
            section = re.sub(r'[-a-zA-Z]+$', '', section)
            if 'x' in section:
                section_val = _parse_single_dimension(section)
                total += section_val
        if total > 0:
            return total

    # Handle dimensions with modifiers (-, wings, cutouts, etc)
    # Remove descriptive suffixes but preserve the dimension
    cleaned = re.sub(r'[-+][a-zA-Z]+$', '', cleaned)

    # Parse single dimension
    return _parse_single_dimension(cleaned)


def _parse_single_dimension(dim_str: str) -> float:
    """
    Parse a single dimension expression like "10'6\"x8'3\"".

    Args:
        dim_str: Single dimension string

    Returns:
        Square footage
    """
    # Match patterns like: 10'6"x8'3" or 10x8 or 10'x8' or 10"x6"
    # Allow optional whitespace around 'x'
    match = re.match(r'^([\d\'\"]+)\s*x\s*([\d\'\"]+)', dim_str.lower())

    if match:
        length_str = match.group(1)
        width_str = match.group(2)

        length = _feet_inches_to_feet(length_str)
        width = _feet_inches_to_feet(width_str)

        return round(length * width, 2)

    return 0.0


def _parse_circular_dimension(value_str: str) -> float:
    """
    Parse circular/round awning dimensions.

    Handles:
    - "4'8R=68.48'" -> 68.48
    - "7'R=153.86'" -> 153.86
    - "5'2R=83.93'" -> 83.93
    - "4'R=50.24'" -> 50.24
    - "14' round=153.86'" -> 153.86
    - "4'9 R = 70.84'" -> 70.84

    Args:
        value_str: String with circular dimension notation

    Returns:
        Square footage (area)
    """
    # Check for pre-calculated value (most accurate for circles)
    calc_val, found = _extract_calculated_value(value_str)
    if found and calc_val > 0:
        return calc_val

    # If no pre-calculated, try to calculate from radius/diameter
    # Match patterns like "4'8R" or "14' round"
    match = re.match(r"^([\d'\"]+)\s*(?:R|round)", value_str, re.IGNORECASE)
    if match:
        dim = _feet_inches_to_feet(match.group(1))
        # Assume dimension is radius, calculate area: π * r²
        import math
        return round(math.pi * (dim ** 2), 2)

    return 0.0


def _parse_yardage(value_str: str) -> float:
    """
    Parse yardage measurements.

    Handles:
    - "44 yds." -> 44.0
    - "33 yds." -> 33.0
    - "55 yds" -> 55.0

    Args:
        value_str: String with yardage

    Returns:
        Yardage value
    """
    match = re.match(r"^([\d.]+)\s*yds?\.?", value_str, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def _parse_simple_footage(value_str: str) -> float:
    """
    Parse simple footage values.

    Handles:
    - "25'" -> 25.0
    - "318.13'" -> 318.13
    - "11.5'" -> 11.5
    - "137'" -> 137.0
    - "100'?" -> 100.0 (with question mark)
    - "10'/15.00" -> 10.0 (with price suffix)

    Args:
        value_str: String with simple footage

    Returns:
        Footage value
    """
    # Match footage with optional trailing characters
    match = re.match(r"^([\d.]+)'", value_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def _parse_ea_price(value_str: str) -> float:
    """
    Parse "each" pricing that sometimes represents size.

    Handles:
    - "16.00 ea." -> 16.0
    - "35.00 ea." -> 35.0
    - "$49 ea." -> 49.0

    Note: These might be prices, not sizes. Context matters.
    For now, we extract the numeric value.

    Args:
        value_str: String with "ea." notation

    Returns:
        Numeric value
    """
    # Remove currency symbols and extract number
    cleaned = value_str.replace('$', '').strip()
    match = re.match(r"^([\d.]+)\s*(?:ea\.?)", cleaned, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def _parse_parentheses_notation(value_str: str) -> float:
    """
    Parse dimensions in parentheses with optional pre-calculated value.

    Handles:
    - "(10x11'4) AP 150.76'" -> 150.76
    - "(30'6x16'9) 527'" -> 527.0
    - "(6x8) 49'" -> 49.0
    - "(19'5x13'8) 266.16'" -> 266.16

    Args:
        value_str: String with parentheses notation

    Returns:
        Square footage
    """
    # Try to extract pre-calculated value after parentheses
    # Pattern: (dimensions) [optional text] number
    match = re.match(r'^\([^)]+\)\s*(?:[A-Z\s]+)?\s*([\d.]+)', value_str, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass

    # If no pre-calculated, try to extract dimensions from parentheses
    paren_match = re.match(r'^\(([^)]+)\)', value_str)
    if paren_match:
        inner = paren_match.group(1)
        # Try to parse the inner dimension
        return _parse_dimension_string(inner)

    return 0.0


def _parse_pound_notation(value_str: str) -> float:
    """
    Parse pound notation (different from sail weights).

    Handles:
    - "52 lb." -> 52.0
    - "48 lb." -> 48.0
    - "37 lb." -> 37.0

    Note: These might be weights, not sizes. Context matters.

    Args:
        value_str: String with "lb." notation

    Returns:
        Numeric value
    """
    match = re.match(r"^([\d.]+)\s*lb\.?", value_str, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0


def clean_square_footage(value: Union[str, float, int, None]) -> float:
    """
    Parse size strings from various formats into square footage.

    Comprehensive parser that handles:
    - Sail weights: "30#" -> 30.0
    - Dimensions: "8x10" -> 80.0, "10'6\"x8'3\"" -> 86.625
    - Pre-calculated: "8x10=80'" -> 80.0
    - Approximations: "~10x6" -> 60.0
    - Complex expressions: "10x5+2x3" (sums multiple sections)
    - Circular: "4'8R=68.48'" -> 68.48, "14' round=153.86'" -> 153.86
    - Modifiers: "10x6-cutouts=55'" -> 55.0
    - Yardage: "44 yds." -> 44.0
    - Simple footage: "25'" -> 25.0, "318.13'" -> 318.13
    - Each notation: "16.00 ea." -> 16.0
    - Plain numbers: "100" -> 100.0
    - Invalid/empty: "", ".", "na", "*" -> 0.0

    Args:
        value: Size/weight string from database

    Returns:
        Float square footage value, 0.0 if invalid
    """
    # Handle null/empty/invalid
    if pd.isna(value) or value in ["", ".", "na", "n/a", "N/A", None, "*", "?"]:
        return 0.0

    val = str(value).strip()

    # Quick check for sail weights (ends with #)
    if val.endswith('#'):
        return clean_sail_weight(val)

    # Remove currency symbols, approximation markers, and common prefixes
    val = val.replace('$', '').replace('~', '').strip()

    # Remove unit markers at end that interfere with parsing
    # But preserve them for specific parsers
    val_for_parsing = val

    # Check for parentheses notation first (most specific)
    if val.startswith('('):
        result = _parse_parentheses_notation(val)
        if result > 0:
            return result

    # Check for circular/round dimensions (R notation or "round")
    # Look for patterns like "4'8R=", "4'R=", "round="
    if re.search(r'R\s*=|round', val, re.IGNORECASE):
        result = _parse_circular_dimension(val)
        if result > 0:
            return result

    # Check for pound notation (lb.)
    if 'lb' in val.lower():
        result = _parse_pound_notation(val)
        if result > 0:
            return result

    # Check for yardage
    if 'yd' in val.lower():
        result = _parse_yardage(val)
        if result > 0:
            return result

    # Check for dimensions (contains 'x')
    if 'x' in val.lower():
        result = _parse_dimension_string(val)
        if result > 0:
            return result

    # Check for simple footage (contains ')
    # Do this before "ea" check since some have both
    if "'" in val:
        result = _parse_simple_footage(val)
        if result > 0:
            return result

    # Check for "ea." notation (might be price, might be size)
    if 'ea' in val.lower():
        result = _parse_ea_price(val)
        if result > 0:
            return result

    # Try plain number (after removing units)
    val_clean = re.sub(r'\s*(ea\.?|pcs?|each)\s*$', '', val, flags=re.IGNORECASE)
    val_clean = val_clean.strip("'\"")
    try:
        result = float(val_clean)
        if result > 0:
            return result
    except ValueError:
        pass

    # If all else fails, return 0.0
    return 0.0


def identify_product_type(sizewgt: Union[str, None]) -> str:
    """
    Identify whether an item is a Sail or Awning based on size/weight notation.

    Rules:
    - If contains '#' -> Sail
    - Otherwise -> Awning

    Args:
        sizewgt: Size/weight string from database

    Returns:
        "Sail" or "Awning"
    """
    if pd.isna(sizewgt):
        return "Awning"

    val = str(sizewgt).strip()
    return "Sail" if "#" in val else "Awning"


def parse_work_order_items(
    items_df: pd.DataFrame,
    detect_outliers: bool = True,
    outlier_threshold: float = 10000.0,
    replace_with_mean: bool = True
) -> pd.DataFrame:
    """
    Process a DataFrame of work order items, parsing sizes and identifying product types.

    Adds columns:
    - price_numeric: Cleaned price as float
    - product_type: "Sail" or "Awning"
    - qty_numeric: Cleaned quantity as float
    - sqft: Total square footage (qty * parsed size) - ONLY for Awnings, 0.0 for Sails
    - is_outlier: Boolean flag for extreme outliers (if detect_outliers=True)

    Note: Sails are excluded from square footage calculations. They are identified by
    the presence of '#' in the sizewgt field.

    Outlier Detection:
    - Automatically detects extreme outliers above the threshold (default 10,000 sqft)
    - These are likely data entry errors (e.g., "29x11319'" should be "29x11.319'")
    - Can optionally replace outliers with the mean value of similar-sized items

    Args:
        items_df: DataFrame with columns: workorderno, custid, qty, sizewgt, price
        detect_outliers: Whether to detect and flag outliers (default: True)
        outlier_threshold: Square footage threshold for outlier detection (default: 10,000)
        replace_with_mean: Whether to replace outliers with mean (default: True)

    Returns:
        DataFrame with additional computed columns
    """
    df = items_df.copy()

    # Clean price column
    df['price_numeric'] = df['price'].apply(clean_numeric_string)

    # Identify product type
    df['sizewgt'] = df['sizewgt'].astype(str)
    df['product_type'] = df['sizewgt'].apply(identify_product_type)

    # Clean quantity
    df['qty_numeric'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0)

    # Calculate square footage - ONLY for Awnings, exclude Sails
    df['sqft'] = df.apply(
        lambda row: (
            row['qty_numeric'] * clean_square_footage(row['sizewgt'])
            if row['product_type'] == 'Awning'
            else 0.0
        ),
        axis=1
    )

    # Outlier detection and replacement
    if detect_outliers:
        # Flag outliers
        df['is_outlier'] = (df['sqft'] > outlier_threshold) & (df['product_type'] == 'Awning')

        if replace_with_mean and df['is_outlier'].any():
            # Calculate mean from non-outlier awnings with sqft > 0
            non_outlier_awnings = df[
                (df['product_type'] == 'Awning') &
                (df['sqft'] > 0) &
                (~df['is_outlier'])
            ]

            if len(non_outlier_awnings) > 0:
                mean_sqft = non_outlier_awnings['sqft'].mean()

                # Replace outliers with mean
                df.loc[df['is_outlier'], 'sqft'] = mean_sqft

                # Log replacement (optional - could be removed for production)
                n_outliers = df['is_outlier'].sum()
                if n_outliers > 0:
                    print(f"[INFO] Replaced {n_outliers} outliers (>{outlier_threshold:,.0f} sqft) with mean: {mean_sqft:,.2f} sqft")
    else:
        df['is_outlier'] = False

    return df
