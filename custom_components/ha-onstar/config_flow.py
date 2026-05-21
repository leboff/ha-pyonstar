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
from homeassistant.helpers.storage import STORAGE_DIR

from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult
    from homeassistant.core import HomeAssistant

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
        vol.Optional(CONF_PIN, description="OnStar PIN (for remote commands)"): str,
    }
)


async def get_vehicles(hass: HomeAssistant, user_input: dict[str, Any]) -> list:
    """Retrieve vehicles from OnStar account."""
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
            vin="",
            totp_secret=user_input[CONF_TOTP_SECRET],
            token_location=token_location,
            onstar_pin=user_input.get(CONF_PIN, ""),
        )

        account_vehicles = await onstar.get_account_vehicles()
        check_vehicles(account_vehicles)

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
    """Validate the user input allows us to connect."""
    if data.get(CONF_PIN) == CHEATER_MODE_PIN:
        data[CONF_CHEATER_MODE] = True
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

        await onstar.get_account_vehicles()

    except Exception as ex:
        _LOGGER.exception("Error connecting to OnStar")
        raise CannotConnectError from ex

    title = f"OnStar Vehicle ({data[CONF_VIN]})"
    if data.get(CONF_CHEATER_MODE, False):
        title += " (Cheater Mode)"

    return {"title": title}


async def validate_input_no_api(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Build config entry data without making a GM API call.

    Used when authentication succeeds via cached tokens but the GM vehicle
    listing API is unavailable (e.g. the v1 endpoint has been disabled).
    The integration will still operate normally for diagnostics and commands
    once the API is restored or updated.
    """
    if data.get(CONF_PIN) == CHEATER_MODE_PIN:
        data[CONF_CHEATER_MODE] = True
        data[CONF_PIN] = ""
    else:
        data[CONF_CHEATER_MODE] = False

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
                self._vehicles = await get_vehicles(self.hass, user_input)
                self._data = user_input
                return await self.async_step_select_vehicle()

            except CannotConnectError:
                # If a cached microsoft_tokens.json exists, authentication
                # likely succeeded but the GM vehicle listing API endpoint is
                # unavailable (e.g. deprecated v1 endpoint returning 404).
                # Fall back to manual VIN entry so setup can still complete.
                token_path = (
                    Path(self.hass.config.path(STORAGE_DIR))
                    / DOMAIN
                    / "microsoft_tokens.json"
                )
                if token_path.exists():
                    _LOGGER.info(
                        "GM vehicle listing API unavailable but cached tokens found "
                        "— falling back to manual VIN entry"
                    )
                    self._data = user_input  # device_id already set by get_vehicles()
                    return await self.async_step_manual_vin()

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
                self._data.update(user_input)
                info = await validate_input(self.hass, self._data)
                return self.async_create_entry(title=info["title"], data=self._data)

            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

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

    async def async_step_manual_vin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Fallback: manually enter VIN when the GM vehicle listing API is unavailable.

        Triggered automatically when microsoft_tokens.json exists (authentication
        succeeded) but the GM /account/vehicles endpoint is not reachable.
        The VIN can be found on the dashboard, driver-side door jamb, or vehicle
        registration.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._data.update(user_input)
                info = await validate_input_no_api(self.hass, self._data)
                return self.async_create_entry(title=info["title"], data=self._data)
            except Exception:
                _LOGGER.exception("Unexpected exception during manual VIN setup")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="manual_vin",
            data_schema=vol.Schema({vol.Required(CONF_VIN): str}),
            errors=errors,
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
            if user_input.get(CONF_PIN) == CHEATER_MODE_PIN:
                user_input[CONF_CHEATER_MODE] = True
            else:
                user_input[CONF_CHEATER_MODE] = False

            return self.async_create_entry(title="", data=user_input)

        current_pin = self.config_entry.data.get(CONF_PIN, "")

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
