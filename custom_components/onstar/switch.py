"""Support for OnStar switches."""

from __future__ import annotations

import logging

from aiohttp import ClientError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the OnStar switch platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    onstar = data["onstar"]
    vin = entry.data["vin"]

    async_add_entities([OnStarRemoteStartSwitch(coordinator, onstar, vin)], True)


class OnStarRemoteStartSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an OnStar remote start switch."""

    _attr_has_entity_name = True
    _attr_name = "Remote Start"

    def __init__(self, coordinator, onstar, vin) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._onstar = onstar
        self._vin = vin
        self._attr_unique_id = f"{self._vin}_remote_start"
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs):
        """Turn on remote start."""
        try:
            result = await self._onstar.start()
            _LOGGER.debug("Remote start result: %s", result)
            if (
                result
                and "commandResponse" in result
                and result["commandResponse"]["status"] == "success"
            ):
                self._attr_is_on = True
                self.async_write_ha_state()
                return True
        except ClientError as err:
            _LOGGER.error("Error in API communication when starting engine: %s", err)
        except HomeAssistantError as err:
            _LOGGER.error("Error starting engine: %s", err)
        except (ValueError, KeyError) as err:
            _LOGGER.error("Invalid response when starting engine: %s", err)
        return False

    async def async_turn_off(self, **kwargs):
        """Turn off remote start."""
        try:
            result = await self._onstar.cancel_start()
            _LOGGER.debug("Cancel remote start result: %s", result)
            if (
                result
                and "commandResponse" in result
                and result["commandResponse"]["status"] == "success"
            ):
                self._attr_is_on = False
                self.async_write_ha_state()
                return True
        except ClientError as err:
            _LOGGER.error("Error in API communication when stopping engine: %s", err)
        except HomeAssistantError as err:
            _LOGGER.error("Error stopping engine: %s", err)
        except (ValueError, KeyError) as err:
            _LOGGER.error("Invalid response when stopping engine: %s", err)
        return False
