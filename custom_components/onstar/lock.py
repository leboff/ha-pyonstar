"""Support for OnStar locks."""

from __future__ import annotations

import logging

from aiohttp import ClientError

from homeassistant.components.lock import LockEntity
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
    """Set up the OnStar lock platform."""
    _LOGGER.debug("Setting up OnStar lock platform")
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    onstar = data["onstar"]
    vin = entry.data["vin"]

    _LOGGER.debug("Creating door lock entity for vehicle: %s", vin)
    async_add_entities(
        [
            OnStarDoorLock(coordinator, onstar, vin),
        ],
        True,
    )


class OnStarDoorLock(CoordinatorEntity, LockEntity):
    """Representation of an OnStar door lock."""

    _attr_has_entity_name = True
    _attr_name = "Doors"

    def __init__(self, coordinator, onstar, vin) -> None:
        """Initialize the lock."""
        super().__init__(coordinator)
        self._onstar = onstar
        self._vin = vin
        self._attr_unique_id = f"{self._vin}_door_lock"
        self._attr_is_locked = None
        _LOGGER.debug("Initialized OnStar door lock: %s", self._attr_unique_id)

    async def async_lock(self, **kwargs):
        """Lock the vehicle doors."""
        _LOGGER.debug("Sending lock command for: %s", self._vin)
        try:
            result = await self._onstar.lock_door()
            _LOGGER.debug("Lock result: %s", result)
            if (
                result
                and "commandResponse" in result
                and result["commandResponse"]["status"] == "success"
            ):
                self._attr_is_locked = True
                self.async_write_ha_state()
                _LOGGER.debug("Successfully locked doors for: %s", self._vin)
                return True
            _LOGGER.debug("Failed to lock doors, invalid response: %s", result)
        except ClientError as err:
            _LOGGER.error("Error in API communication when locking doors: %s", err)
        except HomeAssistantError as err:
            _LOGGER.error("Error locking doors: %s", err)
        except (ValueError, KeyError) as err:
            _LOGGER.error("Invalid response when locking doors: %s", err)
        return False

    async def async_unlock(self, **kwargs):
        """Unlock the vehicle doors."""
        _LOGGER.debug("Sending unlock command for: %s", self._vin)
        try:
            result = await self._onstar.unlock_door()
            _LOGGER.debug("Unlock result: %s", result)
            if (
                result
                and "commandResponse" in result
                and result["commandResponse"]["status"] == "success"
            ):
                self._attr_is_locked = False
                self.async_write_ha_state()
                _LOGGER.debug("Successfully unlocked doors for: %s", self._vin)
                return True
            _LOGGER.debug("Failed to unlock doors, invalid response: %s", result)
        except ClientError as err:
            _LOGGER.error("Error in API communication when unlocking doors: %s", err)
        except HomeAssistantError as err:
            _LOGGER.error("Error unlocking doors: %s", err)
        except (ValueError, KeyError) as err:
            _LOGGER.error("Invalid response when unlocking doors: %s", err)
        return False

    async def async_update(self):
        """Update the lock state."""
        _LOGGER.debug("Updating lock state for: %s", self._vin)
        try:
            # We could try to get the door lock state from diagnostics if available
            # For now, we're just tracking the state based on lock/unlock commands
            _LOGGER.debug(
                "Lock state tracking only based on commands, no direct state available"
            )
        except ClientError as err:
            _LOGGER.error(
                "Error in API communication when updating lock state: %s", err
            )
        except HomeAssistantError as err:
            _LOGGER.error("Error updating lock state: %s", err)
