"""Support for OnStar switches."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
    from pyonstar import OnStar
from homeassistant.exceptions import HomeAssistantError
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

    async_add_entities(
        [OnStarRemoteStartSwitch(coordinator, onstar, vin)], update_before_add=False
    )


class OnStarRemoteStartSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an OnStar remote start switch."""

    _attr_has_entity_name = True
    _attr_name = "Remote Start"

    def __init__(
        self, coordinator: DataUpdateCoordinator, onstar: OnStar, vin: str
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._onstar = onstar
        self._vin = vin
        self._attr_unique_id = f"{self._vin}_remote_start"
        self._attr_is_on = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._vin)},
            "name": f"OnStar Vehicle ({self._vin})",
            "manufacturer": "OnStar",
            "model": "Vehicle",
        }

    async def async_turn_on(self, **kwargs: Any) -> bool:  # noqa: ARG002
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
        except ClientError:
            _LOGGER.exception("Error in API communication when starting engine")
        except HomeAssistantError:
            _LOGGER.exception("Error starting engine")
        except (ValueError, KeyError):
            _LOGGER.exception("Invalid response when starting engine")
        return False

    async def async_turn_off(self, **kwargs: Any) -> bool:  # noqa: ARG002
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
        except ClientError:
            _LOGGER.exception("Error in API communication when stopping engine")
        except HomeAssistantError:
            _LOGGER.exception("Error stopping engine")
        except (ValueError, KeyError):
            _LOGGER.exception("Invalid response when stopping engine")
        return False
