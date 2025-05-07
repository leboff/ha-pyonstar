"""Helper functions for the OnStar integration."""

from __future__ import annotations

import logging
from typing import Any, Optional, TypeVar, cast

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


def get_nested_value(
    data: dict[str, Any], path: list[str], default: Optional[T] = None
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
    diagnostics: list[dict[str, Any]], name: str, default: Optional[T] = None
) -> Any | T:
    """
    Get a specific diagnostic value by name from a diagnostic response.

    Args:
        diagnostics: The diagnostic response list
        name: The name of the diagnostic to find
        default: The value to return if the diagnostic isn't found

    Returns:
        The value of the diagnostic or the default if not found
    """
    if diagnostics is None:
        return default

    for diagnostic in diagnostics:
        if diagnostic.get("name") == name and diagnostic.get("diagnosticElement"):
            elements = diagnostic.get("diagnosticElement")
            if elements and "value" in elements[0]:
                return elements[0]["value"]

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
    location: dict[str, Any], field: str, default: Optional[T] = None
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
