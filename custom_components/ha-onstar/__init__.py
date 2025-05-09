"""The ha-onstar integration."""  # noqa: N999

from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from aiohttp import ClientError
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyonstar import OnStar

from .const import (
    CHEATER_MODE_SCAN_INTERVAL,
    CONF_CHEATER_MODE,
    CONF_TOTP_SECRET,
    CONF_VIN,
    DIAGNOSTICS_SCAN_INTERVAL,
    DOMAIN,
    LOCATION_SCAN_INTERVAL,
    PLATFORMS,
    SCAN_INTERVAL,
    STANDARD_MODE_BACKOFF_TIME,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Constants
RATE_LIMIT_STATUS_CODE = 429
PERIODIC_RESET_SECONDS = 3600  # 1 hour


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OnStar from a config entry."""
    _LOGGER.debug("Setting up OnStar integration")

    # Create OnStar API instance
    token_location = str(Path(hass.config.path(STORAGE_DIR)) / DOMAIN)
    _LOGGER.debug("OnStar token location: %s", token_location)
    new_uuid = str(uuid.uuid4())
    # Log setup info without sensitive data
    _LOGGER.debug(
        "Initializing OnStar with device_id: %s, vin: %s",
        new_uuid,
        entry.data[CONF_VIN],
    )

    # Get an httpx client that handles SSL cert loading in an executor
    httpx_client = get_async_client(hass)

    onstar = OnStar(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        device_id=new_uuid,
        vin=entry.data[CONF_VIN],
        totp_secret=entry.data.get(CONF_TOTP_SECRET, ""),
        token_location=token_location,
        onstar_pin="",
        http_client=httpx_client,
    )

    # Check if cheater mode is enabled and set appropriate interval
    cheater_mode = entry.data.get(CONF_CHEATER_MODE, False)
    update_interval = CHEATER_MODE_SCAN_INTERVAL if cheater_mode else SCAN_INTERVAL
    _LOGGER.debug(
        "Creating OnStar data coordinator with %s second update interval "
        "(Cheater Mode: %s)",
        update_interval,
        cheater_mode,
    )

    # Create update coordinator
    coordinator = OnStarDataUpdateCoordinator(
        hass, onstar, entry, token_location, cheater_mode=cheater_mode
    )

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

    # Register an update listener to handle options updates
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Handling options update for entry: %s", entry.entry_id)

    # Check if cheater mode changed from options form
    if entry.options and CONF_CHEATER_MODE in entry.options:
        cheater_mode = entry.options[CONF_CHEATER_MODE]

        # Update entry data with the new cheater mode setting
        data = {**entry.data}
        data[CONF_CHEATER_MODE] = cheater_mode

        # Update the entry title to reflect the current mode
        title = f"OnStar Vehicle ({data[CONF_VIN]})"
        if cheater_mode:
            title += " (Cheater Mode)"

        hass.config_entries.async_update_entry(entry, data=data, title=title)

        # Update the coordinator's cheater mode and update interval
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        if coordinator.cheater_mode != cheater_mode:
            _LOGGER.info(
                "Changing OnStar polling mode to: %s",
                "Cheater Mode" if cheater_mode else "Standard Mode",
            )
            coordinator.cheater_mode = cheater_mode

            # Update the coordinator's update interval
            update_interval = (
                CHEATER_MODE_SCAN_INTERVAL if cheater_mode else SCAN_INTERVAL
            )
            coordinator.update_interval = timedelta(seconds=update_interval)

            # Request an immediate refresh to apply the new settings
            await coordinator.async_refresh()


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
        except (ClientError, HomeAssistantError):
            _LOGGER.exception("Error closing OnStar client")

        # Remove entry data
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("OnStar integration unloaded successfully")
    else:
        _LOGGER.debug("Failed to unload all OnStar platforms")

    return unload_ok


class OnStarDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching OnStar data."""

    def __init__(
        self,
        hass: HomeAssistant,
        onstar: OnStar,
        entry: ConfigEntry,
        token_location: str,
        *,
        cheater_mode: bool = False,
    ) -> None:
        """Initialize the coordinator."""
        # Determine update interval based on cheater mode
        update_interval = CHEATER_MODE_SCAN_INTERVAL if cheater_mode else SCAN_INTERVAL

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.onstar = onstar
        self.entry = entry
        self.token_location = token_location
        self.cheater_mode = cheater_mode
        self.vehicle_data = {}
        self._last_diagnostics_update = 0
        self._last_location_update = 0
        self._diagnostics_data = None
        self._location_data = None

        # Rate limit detection
        self._diagnostics_backoff_until = 0
        self._location_backoff_until = 0

    async def recreate_onstar_client(self) -> None:
        """Create a new OnStar client with a new device ID."""
        _LOGGER.warning(
            "Recreating OnStar client with new device ID due to rate limiting"
        )

        # Generate a new device ID
        new_device_id = str(uuid.uuid4())
        _LOGGER.debug("Generated new device ID: %s", new_device_id)

        # Get an HTTP client
        httpx_client = get_async_client(self.hass)

        # Close the existing client
        try:
            await self.onstar.close()
        except (ClientError, HomeAssistantError) as err:
            _LOGGER.warning("Error closing existing OnStar client: %s", err)

        # Create a new OnStar client
        self.onstar = OnStar(
            username=self.entry.data[CONF_USERNAME],
            password=self.entry.data[CONF_PASSWORD],
            device_id=new_device_id,
            vin=self.entry.data[CONF_VIN],
            totp_secret=self.entry.data.get(CONF_TOTP_SECRET, ""),
            token_location=self.token_location,
            onstar_pin="",
            http_client=httpx_client,
        )

        # Update the stored device ID in hass.data
        self.hass.data[DOMAIN][self.entry.entry_id]["onstar"] = self.onstar

        await self.onstar.force_token_refresh()
        response = await self.onstar.get_account_vehicles()
        _LOGGER.debug("Response from get_account_vehicles: %s", response)
        _LOGGER.info(
            "Successfully recreated OnStar client with new device ID for vehicle: %s",
            self.entry.data[CONF_VIN],
        )

    async def _handle_rate_limit(
        self,
        endpoint_name: str,
        cached_data: Any,
    ) -> Any:
        """
        Handle rate limiting errors centrally.

        Args:
            endpoint_name: Name of the endpoint being called (for logging)
            cached_data: Cached data to return if not retrying

        Returns:
            Either cached data or the result of retrying

        """
        current_time = time.time()

        if self.cheater_mode:
            # Cheater mode: try to work around rate limiting
            _LOGGER.warning(
                "Rate limited (%s) on %s endpoint "
                "(Cheater Mode enabled, attempting workaround)",
                RATE_LIMIT_STATUS_CODE,
                endpoint_name,
            )

            await self.recreate_onstar_client()

        # Standard mode: back off for 24 hours
        backoff_until = current_time + STANDARD_MODE_BACKOFF_TIME

        # Update the appropriate backoff timestamp
        if endpoint_name == "diagnostics":
            self._diagnostics_backoff_until = backoff_until
        elif endpoint_name == "location":
            self._location_backoff_until = backoff_until

        _LOGGER.warning(
            "Rate limited (%s) on %s endpoint. Backing off for 24 hours until %s",
            RATE_LIMIT_STATUS_CODE,
            endpoint_name,
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(backoff_until)),
        )

        # Return cached data regardless of mode
        return cached_data

    async def _fetch_endpoint_data(
        self,
        endpoint_name: str,
        cached_data: Any,
        api_method: Callable[..., Coroutine[Any, Any, Any]],
        backoff_until: float,
        **api_kwargs: Any,
    ) -> Any:
        """
        Fetch data from API endpoint with common error handling and rate limit.

        Args:
            endpoint_name: Name of the endpoint (for logging)
            cached_data: Currently cached data to return if in backoff
            api_method: OnStar API method to call
            backoff_until: Timestamp until which we're backing off
            api_kwargs: Additional keyword arguments to pass to the API method

        Returns:
            The API response data

        """
        # Check if we're in backoff period
        current_time = time.time()
        if not self.cheater_mode and current_time < backoff_until:
            _LOGGER.debug(
                "In %s backoff period. Skipping fetch until %s",
                endpoint_name,
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(backoff_until)),
            )
            return cached_data

        # Use more specific logging message depending on endpoint
        if endpoint_name == "location":
            _LOGGER.debug("Requesting vehicle location")
        elif endpoint_name == "diagnostics":
            # Skip detailed diagnostics items logging here as
            # it's done in fetch_diagnostics
            _LOGGER.debug("Requesting vehicle diagnostics")
        else:
            _LOGGER.debug("Requesting %s data", endpoint_name)

        try:
            # Call the API method with provided kwargs
            response = await api_method(**api_kwargs)
            _LOGGER.debug("Received %s response: %s", endpoint_name, response)

        except httpx.HTTPStatusError as err:
            if err.response.status_code == RATE_LIMIT_STATUS_CODE:
                # Handle rate limiting
                return await self._handle_rate_limit(endpoint_name, cached_data)
            # Other HTTP errors should still fail
            _LOGGER.exception("HTTP error when fetching %s", endpoint_name)
            msg = f"HTTP error with OnStar {endpoint_name}: {err}"
            raise UpdateFailed(msg) from err
        except ClientError as err:
            _LOGGER.exception(
                "Error in API communication when fetching %s", endpoint_name
            )
            msg = f"Error in API communication with OnStar: {err}"
            raise UpdateFailed(msg) from err
        except HomeAssistantError as err:
            _LOGGER.exception("Home Assistant error when fetching %s", endpoint_name)
            msg = f"Home Assistant error with OnStar: {err}"
            raise UpdateFailed(msg) from err
        except (ValueError, KeyError) as err:
            _LOGGER.exception("Invalid response when fetching %s", endpoint_name)
            msg = f"Invalid response from OnStar API: {err}"
            raise UpdateFailed(msg) from err
        else:
            return response

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

        response = await self._fetch_endpoint_data(
            endpoint_name="diagnostics",
            cached_data=self._diagnostics_data,
            api_method=self.onstar.diagnostics,
            backoff_until=self._diagnostics_backoff_until,
            options={"diagnostic_item": diagnostics_items},
        )

        self._diagnostics_data = response
        # Keep diagnostics data in self.data for backward compatibility
        if self.data:
            self.data["diagnostics"] = response

        return response

    async def fetch_location(self) -> Any:
        """Fetch location data from OnStar API."""
        response = await self._fetch_endpoint_data(
            endpoint_name="location",
            cached_data=self._location_data,
            api_method=self.onstar.location,
            backoff_until=self._location_backoff_until,
        )

        self._location_data = response
        # Keep location data in self.data for backward compatibility
        if self.data:
            self.data["location"] = response

        return response

    async def get_diagnostics(self) -> Any:
        """Get diagnostic data, fetching only if needed based on rate limiting."""
        current_time = int(time.time())
        time_since_last_update = current_time - self._last_diagnostics_update

        interval = (
            CHEATER_MODE_SCAN_INTERVAL
            if self.cheater_mode
            else DIAGNOSTICS_SCAN_INTERVAL
        )

        if not self._diagnostics_data or time_since_last_update > interval:
            _LOGGER.debug(
                "Diagnostics data is stale (%s seconds old, limit: %s). "
                "Fetching new data",
                time_since_last_update,
                interval,
            )
            await self.fetch_diagnostics()
            self._last_diagnostics_update = current_time
        else:
            _LOGGER.debug(
                "Using cached diagnostics data (%s seconds old, limit: %s)",
                time_since_last_update,
                interval,
            )

        return self._diagnostics_data

    async def get_location(self) -> Any:
        """Get location data, fetching only if needed based on rate limiting."""
        current_time = int(time.time())
        time_since_last_update = current_time - self._last_location_update

        interval = (
            CHEATER_MODE_SCAN_INTERVAL if self.cheater_mode else LOCATION_SCAN_INTERVAL
        )

        if not self._location_data or time_since_last_update > interval:
            _LOGGER.debug(
                "Location data is stale (%s seconds old, limit: %s). Fetching new data",
                time_since_last_update,
                interval,
            )
            await self.fetch_location()
            self._last_location_update = current_time
        else:
            _LOGGER.debug(
                "Using cached location data (%s seconds old, limit: %s)",
                time_since_last_update,
                interval,
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
