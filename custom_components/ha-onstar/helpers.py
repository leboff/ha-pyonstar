"""Helper functions for the OnStar integration."""

from __future__ import annotations

import logging
import zoneinfo  # For timezone support
from datetime import datetime, timedelta
from typing import Any, TypeVar

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

# Mapping of day names to weekday numbers (0=Monday, 6=Sunday in ISO)
_DAYS_MAP = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}


def get_nested_value(
    data: dict[str, Any], path: list[str], default: T | None = None
) -> Any | T:
    """
    Safely access a nested value in a dictionary using a path of keys.

    Args:
        data: The dictionary to access
        path: A list of keys defining the path to the desired value
        default: The value to return if the path doesn't exist

    Returns:
        The value at the specified path or the default if not found

    """
    if data is None:
        return default

    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]

    return current


def get_diagnostic_response(data: dict[str, Any]) -> list[dict[str, Any]] | None:
    """
    Get the diagnostic response data from OnStar API response.

    Args:
        data: The OnStar coordinator data

    Returns:
        The diagnostic response data or None if not available

    """
    if data is None or "diagnostics" not in data or data["diagnostics"] is None:
        _LOGGER.debug("No diagnostics data available")
        return None

    diagnostics = get_nested_value(
        data["diagnostics"], ["commandResponse", "body", "diagnosticResponse"]
    )

    if not isinstance(diagnostics, list):
        _LOGGER.debug("Diagnostic response is not a list or is missing")
        return None

    return diagnostics


def get_diagnostic_value(
    diagnostics: list[dict[str, Any]],
    name: str,
    element_name: str | None = None,
    default: T | None = None,
) -> Any | T:
    """
    Get a specific diagnostic value by name from a diagnostic response.

    Args:
        diagnostics: The diagnostic response list
        name: The name of the diagnostic category to find
        element_name: The name of the specific
            element to find (defaults to name if None)
        default: The value to return if the diagnostic isn't found

    Returns:
        The value of the diagnostic or the default if not found

    """
    if diagnostics is None:
        return default

    # Use name as element_name if not provided
    if element_name is None:
        element_name = name

    # Find the diagnostic category
    for diagnostic in diagnostics:
        if diagnostic.get("name") == name:
            elements = diagnostic.get("diagnosticElement", [])
            # Look through all elements for the specific one
            for element in elements:
                if element.get("name") == element_name and "value" in element:
                    return element["value"]

    return default


def get_location_data(data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Get the location data from OnStar API response.

    Args:
        data: The OnStar coordinator data

    Returns:
        The location data or None if not available

    """
    if data is None or "location" not in data or data["location"] is None:
        _LOGGER.debug("No location data available")
        return None

    location = get_nested_value(
        data["location"], ["commandResponse", "body", "location"]
    )

    if not isinstance(location, dict):
        _LOGGER.debug("Location data is not a dictionary or is missing")
        return None

    return location


def get_location_value(
    location: dict[str, Any], field: str, default: T | None = None
) -> Any | T:
    """
    Get a specific location value by field name.

    Args:
        location: The location data dictionary
        field: The field name to retrieve
        default: The value to return if the field isn't found

    Returns:
        The value of the field or the default if not found

    """
    if location is None or field not in location:
        return default

    return location[field]


def calculate_next_occurrence_timestamp(
    day: str, hour: str, minute: str
) -> datetime | None:
    """
    Calculate the datetime for the next occurrence of a specified day and time.

    Args:
        day: The day of week (Monday, Tuesday, etc.)
        hour: The hour (0-23)
        minute: The minute (0-59)

    Returns:
        A datetime object with timezone information or None if the input is invalid

    """
    try:
        # Get current date in local timezone
        now = datetime.now(tz=zoneinfo.ZoneInfo("localtime"))

        # Parse the day of week to integer (0=Monday, 6=Sunday)
        target_weekday = _DAYS_MAP.get(day)
        if target_weekday is None:
            _LOGGER.debug("Invalid day name: %s", day)
            return None

        # Calculate days until the target day
        days_ahead = target_weekday - now.weekday()
        if days_ahead < 0:  # Target day already happened this week
            days_ahead += 7

        # If it's the same day, check if the time has already passed
        if days_ahead == 0 and (
            now.hour > int(hour)
            or (now.hour == int(hour) and now.minute >= int(minute))
        ):
            days_ahead = 7  # Target time already passed today, use next week

        # Calculate the target date
        target_date = datetime(
            now.year, now.month, now.day, tzinfo=zoneinfo.ZoneInfo("localtime")
        ).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=days_ahead
        )

        # Set the target time
        target_datetime = target_date.replace(hour=int(hour), minute=int(minute))

        _LOGGER.debug("Calculated next occurrence: %s", target_datetime)
    except (ValueError, TypeError) as err:
        _LOGGER.debug("Error calculating timestamp: %s", err)
        return None
    else:
        return target_datetime
