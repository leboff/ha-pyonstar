"""Support for OnStar device tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the OnStar device tracker platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    vin = entry.data["vin"]

    async_add_entities([OnStarDeviceTracker(coordinator, vin)], update_before_add=True)


class OnStarDeviceTracker(CoordinatorEntity, TrackerEntity):
    """OnStar device tracker."""

    _attr_has_entity_name = True
    _attr_name = "Location"

    def __init__(self, coordinator: DataUpdateCoordinator, vin: str) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self._vin = vin
        self._attr_unique_id = f"{self._vin}_location"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._vin)},
            "name": f"OnStar Vehicle ({self._vin})",
            "manufacturer": "OnStar",
            "model": "Vehicle",
        }

    @property
    def source_type(self) -> SourceType:
        """Return the source type, in this case a GPS."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        if (
            self.coordinator.data
            and "location" in self.coordinator.data
            and self.coordinator.data["location"]
            and "commandResponse" in self.coordinator.data["location"]
            and "body" in self.coordinator.data["location"]["commandResponse"]
        ):
            body = self.coordinator.data["location"]["commandResponse"]["body"]
            if "location" in body and "latitude" in body["location"]:
                return float(body["location"]["latitude"])
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        if (
            self.coordinator.data
            and "location" in self.coordinator.data
            and self.coordinator.data["location"]
            and "commandResponse" in self.coordinator.data["location"]
            and "body" in self.coordinator.data["location"]["commandResponse"]
        ):
            body = self.coordinator.data["location"]["commandResponse"]["body"]
            if "location" in body and "longitude" in body["location"]:
                return float(body["location"]["longitude"])
        return None
