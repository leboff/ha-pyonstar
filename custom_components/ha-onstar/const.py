"""Constants for the OnStar integration."""

from homeassistant.const import (
    Platform,
)

DOMAIN = "ha-onstar"
VERSION = "0.3.0"

# Configuration constants
CONF_DEVICE_ID = "device_id"
CONF_VIN = "vin"
CONF_TOTP_SECRET = "totp_secret"  # noqa: S105
CONF_CHEATER_MODE = "cheater_mode"
CONF_PIN = "onstar_pin"

# Custom units
MPGE = "MPGe"
KILOWATT_HOURS_PER_100MI = "kWh/100mi"

# Unit conversion constants
KMPLE_TO_MPGE = 2.352  # Convert kmple to MPGe (miles per gallon equivalent)
KWH_PER_100KM_TO_KWH_PER_100MI = 1.609344  # Convert kWh/100km to kWh/100mi

# Platforms
PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Refresh interval for updating data
SCAN_INTERVAL = 1800  # seconds (30 minutes)

# Refresh interval for diagnostics data (which is rate limited)
# 30 minutes between diagnostics calls to avoid rate limiting
DIAGNOSTICS_SCAN_INTERVAL = 1800  # seconds (30 minutes)

# Refresh interval for location data (which might be rate limited)
LOCATION_SCAN_INTERVAL = 1800  # seconds (30 minutes)

# Cheater mode settings
CHEATER_MODE_SCAN_INTERVAL = 120  # seconds (2 minutes)

# Rate limit handling
STANDARD_MODE_BACKOFF_TIME = 86400  # seconds (24 hours)

# Default values
DEFAULT_NAME = "ha-onstar"
