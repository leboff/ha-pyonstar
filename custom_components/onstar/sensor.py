"""Support for OnStar sensors."""

from __future__ import annotations

import logging

from aiohttp import ClientError

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the OnStar sensor platform."""
    _LOGGER.debug("Setting up OnStar sensor platform")
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    vin = entry.data["vin"]

    # Request diagnostics data initially to determine if this is an EV
    _LOGGER.debug("Making initial diagnostics request to set up sensors")
    try:
        await coordinator.get_diagnostics()
    except ClientError as err:
        _LOGGER.warning(
            "API communication error during initial diagnostics: %s. Will try again later",
            err,
        )
    except HomeAssistantError as err:
        _LOGGER.warning(
            "Home Assistant error during initial diagnostics: %s. Will try again later",
            err,
        )
    except (ValueError, KeyError) as err:
        _LOGGER.warning(
            "Invalid response during initial diagnostics: %s. Will try again later", err
        )

    sensors = [
        OnStarOdometerSensor(coordinator, vin),
    ]
    _LOGGER.debug("Created odometer sensor for vehicle: %s", vin)

    # Add EV-specific sensors if the vehicle has an EV powertrain
    is_ev = _is_electric_vehicle(coordinator)
    _LOGGER.debug("Vehicle %s is electric: %s", vin, is_ev)

    if is_ev:
        sensors.append(OnStarBatteryLevelSensor(coordinator, vin))
        _LOGGER.debug("Created EV battery level sensor for vehicle: %s", vin)

    _LOGGER.debug("Adding %s OnStar sensors", len(sensors))
    async_add_entities(sensors, True)


def _is_electric_vehicle(coordinator) -> bool:
    """Determine if the vehicle is an EV based on the diagnostics data."""
    _LOGGER.debug("Checking if vehicle is electric")
    if (
        coordinator.data is None
        or "diagnostics" not in coordinator.data
        or coordinator.data["diagnostics"] is None
    ):
        _LOGGER.debug("No diagnostics data available yet to determine EV status")
        return False

    if (
        "commandResponse" in coordinator.data["diagnostics"]
        and "body" in coordinator.data["diagnostics"]["commandResponse"]
        and "diagnosticResponse"
        in coordinator.data["diagnostics"]["commandResponse"]["body"]
    ):
        diagnostics = coordinator.data["diagnostics"]["commandResponse"]["body"][
            "diagnosticResponse"
        ]
        _LOGGER.debug("Diagnostic response: %s", diagnostics)
        for diagnostic in diagnostics:
            if diagnostic.get("name") == "EV BATTERY LEVEL":
                _LOGGER.debug("Found EV BATTERY LEVEL, vehicle is electric")
                return True
    _LOGGER.debug("No EV data found, vehicle is not electric")
    return False


class OnStarSensor(CoordinatorEntity, SensorEntity):
    """Representation of an OnStar sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, vin, sensor_type) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._vin = vin
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{self._vin}_{sensor_type}"
        _LOGGER.debug("Initialized OnStar sensor: %s", self._attr_unique_id)

    async def _get_diagnostics(self):
        """Get diagnostics data, fetching if needed."""
        try:
            return await self.coordinator.get_diagnostics()
        except ClientError as err:
            _LOGGER.error("API communication error getting diagnostics: %s", err)
            return None
        except HomeAssistantError as err:
            _LOGGER.error("Home Assistant error getting diagnostics: %s", err)
            return None
        except (ValueError, KeyError) as err:
            _LOGGER.error("Invalid response error getting diagnostics: %s", err)
            return None


class OnStarOdometerSensor(OnStarSensor):
    """Representation of an OnStar odometer sensor."""

    _attr_name = "Odometer"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, vin) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "odometer")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self):
        """Return the odometer reading."""
        _LOGGER.debug("Getting odometer value for: %s", self._vin)
        if (
            self.coordinator.data is None
            or "diagnostics" not in self.coordinator.data
            or self.coordinator.data["diagnostics"] is None
        ):
            _LOGGER.debug("No diagnostics data available for odometer")
            return None

        if (
            "commandResponse" in self.coordinator.data["diagnostics"]
            and "body" in self.coordinator.data["diagnostics"]["commandResponse"]
            and "diagnosticResponse"
            in self.coordinator.data["diagnostics"]["commandResponse"]["body"]
        ):
            diagnostics = self.coordinator.data["diagnostics"]["commandResponse"][
                "body"
            ]["diagnosticResponse"]
            _LOGGER.debug("Processing diagnostics for odometer: %s", diagnostics)
            for diagnostic in diagnostics:
                if diagnostic.get("name") == "ODOMETER" and diagnostic.get(
                    "diagnosticElement"
                ):
                    elements = diagnostic.get("diagnosticElement")
                    if elements and "value" in elements[0]:
                        value = float(elements[0]["value"])
                        _LOGGER.debug(
                            "Found odometer value: %s %s",
                            value,
                            self._attr_native_unit_of_measurement,
                        )
                        return value
            _LOGGER.debug("No odometer data found in diagnostics")
        else:
            _LOGGER.debug("Diagnostic data structure is incorrect for odometer")
        return None


class OnStarBatteryLevelSensor(OnStarSensor):
    """Representation of an OnStar EV battery level sensor."""

    _attr_name = "Battery Level"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, vin) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "battery_level")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self):
        """Return the battery level."""
        _LOGGER.debug("Getting battery level for: %s", self._vin)
        if (
            self.coordinator.data is None
            or "diagnostics" not in self.coordinator.data
            or self.coordinator.data["diagnostics"] is None
        ):
            _LOGGER.debug("No diagnostics data available for battery level")
            return None

        if (
            "commandResponse" in self.coordinator.data["diagnostics"]
            and "body" in self.coordinator.data["diagnostics"]["commandResponse"]
            and "diagnosticResponse"
            in self.coordinator.data["diagnostics"]["commandResponse"]["body"]
        ):
            diagnostics = self.coordinator.data["diagnostics"]["commandResponse"][
                "body"
            ]["diagnosticResponse"]
            _LOGGER.debug("Processing diagnostics for battery level: %s", diagnostics)
            for diagnostic in diagnostics:
                if diagnostic.get("name") == "EV BATTERY LEVEL" and diagnostic.get(
                    "diagnosticElement"
                ):
                    elements = diagnostic.get("diagnosticElement")
                    if elements and "value" in elements[0]:
                        value = float(elements[0]["value"])
                        _LOGGER.debug("Found battery level: %s%s", value, "%")
                        return value
            _LOGGER.debug("No battery level data found in diagnostics")
        else:
            _LOGGER.debug("Diagnostic data structure is incorrect for battery level")
        return None
