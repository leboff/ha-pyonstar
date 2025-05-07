"""Config flow for the OnStar integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pyonstar import OnStar
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import STORAGE_DIR

from .const import CONF_DEVICE_ID, CONF_ONSTAR_PIN, CONF_TOTP_SECRET, CONF_VIN, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_VIN): str,
        vol.Optional(CONF_ONSTAR_PIN): str,
        vol.Optional(CONF_TOTP_SECRET): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    token_location = str(Path(hass.config.path(STORAGE_DIR)) / DOMAIN)

    try:
        onstar = OnStar(
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            device_id=data[CONF_DEVICE_ID],
            vin=data[CONF_VIN],
            onstar_pin=data.get(CONF_ONSTAR_PIN),
            totp_secret=data.get(CONF_TOTP_SECRET),
            token_location=token_location,
        )
        # Test connection by getting account vehicles
        await onstar.get_account_vehicles()
    except Exception as ex:
        _LOGGER.error("Error connecting to OnStar: %s", ex)
        raise CannotConnect from ex

    # Return info that you want to store in the config entry.
    return {"title": f"OnStar Vehicle ({data[CONF_VIN]})"}


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OnStar."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
