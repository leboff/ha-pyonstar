"""Config flow for the OnStar integration."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow as HAConfigFlow
from homeassistant.config_entries import OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult
    from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import STORAGE_DIR
from pyonstar import OnStar

from .const import (
    CONF_CHEATER_MODE,
    CONF_DEVICE_ID,
    CONF_PIN,
    CONF_TOTP_SECRET,
    CONF_VIN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Magic PIN to enable cheater mode
CHEATER_MODE_PIN = "VROOM"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(
            CONF_TOTP_SECRET,
            description="TOTP secret obtained when setting up MFA via OnStar",
        ): str,
        vol.Required(CONF_PIN, description="OnStar PIN (for remote commands)"): str,
    }
)


async def get_vehicles(hass: HomeAssistant, user_input: dict[str, Any]) -> list:
    """Retrieve vehicles from OnStar account."""
    # Generate a UUID4 for device_id
    device_id = str(uuid.uuid4())
    user_input[CONF_DEVICE_ID] = device_id

    token_location = str(Path(hass.config.path(STORAGE_DIR)) / DOMAIN)

    def check_vehicles(account_data: dict[str, Any]) -> dict[str, Any]:
        """Check if vehicles exist in account data."""
        if not account_data or "vehicles" not in account_data:
            msg = "No vehicles found in OnStar account"
            raise CannotConnectError(msg)
        return account_data

    try:
        onstar = OnStar(
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            device_id=device_id,
            vin="",  # Not needed for initial account access
            totp_secret=user_input[CONF_TOTP_SECRET],
            token_location=token_location,
            onstar_pin=user_input.get(CONF_PIN, ""),
        )
        # Get account vehicles
        account_vehicles = await onstar.get_account_vehicles()

        # Check vehicles using inner function
        check_vehicles(account_vehicles)

        # Extract the list of vehicles with relevant details using a list comprehension
        return [
            {
                "vin": vehicle["vin"],
                "name": f"{vehicle['year']} {vehicle['make']} {vehicle['model']}",
            }
            for vehicle in account_vehicles["vehicles"]["vehicle"]
        ]

    except Exception as ex:
        _LOGGER.exception("Error connecting to OnStar")
        raise CannotConnectError from ex


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # Check for cheater mode based on PIN
    if data.get(CONF_PIN) == CHEATER_MODE_PIN:
        data[CONF_CHEATER_MODE] = True
        # Set a real PIN for OnStar API calls (empty string is fine)
        actual_pin = ""
    else:
        data[CONF_CHEATER_MODE] = False
        actual_pin = data.get(CONF_PIN, "")

    token_location = str(Path(hass.config.path(STORAGE_DIR)) / DOMAIN)

    try:
        onstar = OnStar(
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            device_id=data[CONF_DEVICE_ID],
            vin=data[CONF_VIN],
            totp_secret=data[CONF_TOTP_SECRET],
            token_location=token_location,
            onstar_pin=actual_pin,
        )
        # Test connection by getting account vehicles
        await onstar.get_account_vehicles()
    except Exception as ex:
        _LOGGER.exception("Error connecting to OnStar")
        raise CannotConnectError from ex

    # Return info that you want to store in the config entry.
    title = f"OnStar Vehicle ({data[CONF_VIN]})"
    if data.get(CONF_CHEATER_MODE, False):
        title += " (Cheater Mode)"
    return {"title": title}


class ConfigFlow(HAConfigFlow, domain=DOMAIN):
    """Handle a config flow for OnStar."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data = {}
        self._vehicles = []

    @classmethod
    def async_get_options_flow(cls, config_entry: Any) -> OnStarOptionsFlow:
        """Get the options flow for this handler."""
        return OnStarOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step to collect credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Get vehicles from the account
                self._vehicles = await get_vehicles(self.hass, user_input)
                self._data = user_input

                # If we got vehicles, proceed to selection step
                return await self.async_step_select_vehicle()

            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_select_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to select a vehicle."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Merge the selected vehicle with existing data
                self._data.update(user_input)

                # Validate the input with the selected VIN
                info = await validate_input(self.hass, self._data)

                return self.async_create_entry(title=info["title"], data=self._data)

            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Create schema with vehicle options
        vehicle_schema = vol.Schema(
            {
                vol.Required(CONF_VIN): vol.In(
                    {vehicle["vin"]: vehicle["name"] for vehicle in self._vehicles}
                ),
            }
        )

        return self.async_show_form(
            step_id="select_vehicle",
            data_schema=vehicle_schema,
            errors=errors,
            description_placeholders={"vehicle_count": str(len(self._vehicles))},
        )


class OnStarOptionsFlow(OptionsFlow):
    """Handle OnStar options."""

    def __init__(self, config_entry: Any) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Check for cheater mode PIN
            if user_input.get(CONF_PIN) == CHEATER_MODE_PIN:
                user_input[CONF_CHEATER_MODE] = True
            else:
                user_input[CONF_CHEATER_MODE] = False

            # Update the config entry with the new settings
            return self.async_create_entry(title="", data=user_input)

        # Get current PIN
        current_pin = self.config_entry.data.get(CONF_PIN, "")

        # Show PIN in options but don't reveal if it's the special value
        options_schema = vol.Schema(
            {
                vol.Required(CONF_PIN, default=current_pin): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "vehicle_vin": self.config_entry.data.get(CONF_VIN, "Unknown")
            },
        )


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuthError(HomeAssistantError):
    """Error to indicate there is invalid auth."""
