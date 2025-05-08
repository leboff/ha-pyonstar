"""The ha-onstar integration."""  # noqa: N999

from __future__ import annotations

import logging
import time
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyonstar import OnStar

from .const import (
    CONF_DEVICE_ID,
    CONF_TOTP_SECRET,
    CONF_VIN,
    DIAGNOSTICS_SCAN_INTERVAL,
    DOMAIN,
    LOCATION_SCAN_INTERVAL,
    PLATFORMS,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OnStar from a config entry."""
    _LOGGER.debug("Setting up OnStar integration")

    # Create OnStar API instance
    token_location = str(Path(hass.config.path(STORAGE_DIR)) / DOMAIN)
    _LOGGER.debug("OnStar token location: %s", token_location)

    # Log setup info without sensitive data
    _LOGGER.debug(
        "Initializing OnStar with device_id: %s, vin: %s",
        entry.data[CONF_DEVICE_ID],
        entry.data[CONF_VIN],
    )

    # Get an httpx client that handles SSL cert loading in an executor
    httpx_client = get_async_client(hass)

    onstar = OnStar(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        device_id=entry.data[CONF_DEVICE_ID],
        vin=entry.data[CONF_VIN],
        totp_secret=entry.data.get(CONF_TOTP_SECRET, ""),
        token_location=token_location,
        onstar_pin="",
        http_client=httpx_client,
    )

    # Create update coordinator
    _LOGGER.debug(
        "Creating OnStar data coordinator with %s second update interval", SCAN_INTERVAL
    )
    coordinator = OnStarDataUpdateCoordinator(hass, onstar)

    # Fetch initial data (only location, not diagnostics)
    _LOGGER.debug("Requesting initial location data from OnStar API")
    await coordinator.async_config_entry_first_refresh()

    # Register the vehicle as a device
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data[CONF_VIN])},
        name=entry.title,
        manufacturer="OnStar",
        model="Vehicle",
        sw_version="1.0",
    )
    _LOGGER.debug("Registered OnStar vehicle device: %s", device_entry.id)

    # Store coordinator in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "onstar": onstar,
        "device_id": device_entry.id,
    }

    # Set up all platforms
    _LOGGER.debug("Setting up platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("OnStar integration setup complete")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading OnStar integration")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Get the OnStar client instance
        onstar = hass.data[DOMAIN][entry.entry_id]["onstar"]

        # Close the OnStar client to release resources
        try:
            await onstar.close()
            _LOGGER.debug("OnStar client closed successfully")
        except Exception:
            _LOGGER.exception("Error closing OnStar client")

        # Remove entry data
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("OnStar integration unloaded successfully")
    else:
        _LOGGER.debug("Failed to unload all OnStar platforms")

    return unload_ok


class OnStarDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching OnStar data."""

    def __init__(self, hass: HomeAssistant, onstar: OnStar) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.onstar = onstar
        self.vehicle_data = {}
        self._last_diagnostics_update = 0
        self._last_location_update = 0
        self._diagnostics_data = None
        self._location_data = None

    async def fetch_diagnostics(self) -> Any:
        """Fetch diagnostic data from OnStar API."""
        diagnostics_items = [
            "LAST TRIP FUEL ECONOMY",
            "EV BATTERY LEVEL",
            "EV CHARGE STATE",
            "ENERGY EFFICIENCY",
            "HV BATTERY CHARGE COMPLETE TIME",
            "ODOMETER",
            "EV PLUG VOLTAGE",
            "CHARGER POWER LEVEL",
            "EV PLUG STATE",
            "TIRE PRESSURE",
            "GET CHARGE MODE",
            "VEHICLE RANGE",
        ]
        _LOGGER.debug("Requesting diagnostics with items: %s", diagnostics_items)
        try:
            # Get vehicle diagnostic data
            diagnostics = await self.onstar.diagnostics(
                options={"diagnostic_item": diagnostics_items}
            )
            _LOGGER.debug("Received diagnostics response: %s", diagnostics)

            self._diagnostics_data = diagnostics
            # Keep diagnostics data in self.data for backward compatibility
            if self.data:
                self.data["diagnostics"] = diagnostics
        except ClientError as err:
            _LOGGER.exception("Error in API communication when fetching diagnostics")
            msg = f"Error in API communication with OnStar: {err}"
            raise UpdateFailed(msg) from err
        except HomeAssistantError as err:
            _LOGGER.exception("Home Assistant error when fetching diagnostics")
            msg = f"Home Assistant error with OnStar: {err}"
            raise UpdateFailed(msg) from err
        except (ValueError, KeyError) as err:
            _LOGGER.exception("Invalid response when fetching diagnostics")
            msg = f"Invalid response from OnStar API: {err}"
            raise UpdateFailed(msg) from err
        else:
            return diagnostics

    async def get_diagnostics(self) -> Any:
        """Get diagnostic data, fetching only if needed based on rate limiting."""
        current_time = int(time.time())
        time_since_last_update = current_time - self._last_diagnostics_update

        if (
            not self._diagnostics_data
            or time_since_last_update > DIAGNOSTICS_SCAN_INTERVAL
        ):
            _LOGGER.debug(
                "Diagnostics data is stale (%s seconds old, limit: %s). "
                "Fetching new data",
                time_since_last_update,
                DIAGNOSTICS_SCAN_INTERVAL,
            )
            await self.fetch_diagnostics()
            self._last_diagnostics_update = current_time
        else:
            _LOGGER.debug(
                "Using cached diagnostics data (%s seconds old, limit: %s)",
                time_since_last_update,
                DIAGNOSTICS_SCAN_INTERVAL,
            )

        return self._diagnostics_data

    async def fetch_location(self) -> Any:
        """Fetch location data from OnStar API."""
        _LOGGER.debug("Requesting vehicle location")
        try:
            # Get vehicle location
            location = await self.onstar.location()
            _LOGGER.debug("Received location response: %s", location)

            self._location_data = location
            # Keep location data in self.data for backward compatibility
            if self.data:
                self.data["location"] = location
        except ClientError as err:
            _LOGGER.exception("Error in API communication when fetching location")
            msg = f"Error in API communication with OnStar: {err}"
            raise UpdateFailed(msg) from err
        except HomeAssistantError as err:
            _LOGGER.exception("Home Assistant error when fetching location")
            msg = f"Home Assistant error with OnStar: {err}"
            raise UpdateFailed(msg) from err
        except (ValueError, KeyError) as err:
            _LOGGER.exception("Invalid response when fetching location")
            msg = f"Invalid response from OnStar API: {err}"
            raise UpdateFailed(msg) from err
        else:
            return location

    async def get_location(self) -> Any:
        """Get location data, fetching only if needed based on rate limiting."""
        current_time = int(time.time())
        time_since_last_update = current_time - self._last_location_update

        if not self._location_data or time_since_last_update > LOCATION_SCAN_INTERVAL:
            _LOGGER.debug(
                "Location data is stale (%s seconds old, limit: %s). Fetching new data",
                time_since_last_update,
                LOCATION_SCAN_INTERVAL,
            )
            await self.fetch_location()
            self._last_location_update = current_time
        else:
            _LOGGER.debug(
                "Using cached location data (%s seconds old, limit: %s)",
                time_since_last_update,
                LOCATION_SCAN_INTERVAL,
            )

        return self._location_data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from OnStar."""
        _LOGGER.debug("Beginning OnStar data update")
        try:
            # Get vehicle account data first if needed
            await self.onstar.get_account_vehicles()

            # Get vehicle location using cache-aware method
            await self.get_location()

            # Also update diagnostics data on each cycle
            # Use get_diagnostics() to respect rate limiting
            await self.get_diagnostics()

            # Return combined data
            return {
                "location": self._location_data,
                "diagnostics": self._diagnostics_data,
            }
        except ClientError as err:
            _LOGGER.exception("Error in API communication with OnStar")
            msg = f"Error in API communication with OnStar: {err}"
            raise UpdateFailed(msg) from err
        except HomeAssistantError as err:
            _LOGGER.exception("Home Assistant error communicating with OnStar")
            msg = f"Home Assistant error with OnStar: {err}"
            raise UpdateFailed(msg) from err
        except (ValueError, KeyError) as err:
            _LOGGER.exception("Invalid response from OnStar API")
            msg = f"Invalid response from OnStar API: {err}"
            raise UpdateFailed(msg) from err
        else:
            _LOGGER.debug("OnStar data update completed successfully")
