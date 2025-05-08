"""Constants for the OnStar integration."""

from homeassistant.const import Platform

DOMAIN = "ha-onstar"

# Configuration constants
CONF_DEVICE_ID = "device_id"
CONF_VIN = "vin"
CONF_TOTP_SECRET = "totp_secret"  # noqa: S105

# Platforms
PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Refresh interval for updating data
SCAN_INTERVAL = 120  # seconds (2 minutes)

# Refresh interval for diagnostics data (which is rate limited)
# 30 minutes between diagnostics calls to avoid rate limiting
DIAGNOSTICS_SCAN_INTERVAL = 120  # seconds (2 minutes)

# Refresh interval for location data (which might be rate limited)
LOCATION_SCAN_INTERVAL = 120  # seconds (2 minutes)

# Default values
DEFAULT_NAME = "ha-onstar"
