"""Support for OnStar sensors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, runtime_checkable

from aiohttp import ClientError
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPressure,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .helpers import (
    calculate_next_occurrence_timestamp,
    get_diagnostic_response,
    get_diagnostic_value,
)

_LOGGER = logging.getLogger(__name__)


@runtime_checkable
class OnStarCoordinator(Protocol):
    """Protocol for the OnStar coordinator."""

    async def get_diagnostics(self) -> Any:
        """Get diagnostic data."""
        ...


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
            "API communication error during initial diagnostics: %s. "
            "Will try again later",
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

    sensors: list[OnStarSensor] = [
        OnStarOdometerSensor(coordinator, vin),
    ]
    _LOGGER.debug("Created odometer sensor for vehicle: %s", vin)

    # Add EV-specific sensors if the vehicle has an EV powertrain
    is_ev = _is_electric_vehicle(coordinator)
    _LOGGER.debug("Vehicle %s is electric: %s", vin, is_ev)

    if is_ev:
        sensors.extend(
            [
                OnStarBatteryLevelSensor(coordinator, vin),
                OnStarChargeStateSensor(coordinator, vin),
                OnStarPlugStateSensor(coordinator, vin),
                OnStarPlugVoltageSensor(coordinator, vin),
                OnStarChargerPowerLevelSensor(coordinator, vin),
                OnStarChargeCompleteTimeSensor(coordinator, vin),
                OnStarLastTripEfficiencySensor(coordinator, vin),
                OnStarLifetimeEfficiencySensor(coordinator, vin),
                OnStarEvRangeSensor(coordinator, vin),
            ]
        )
        _LOGGER.debug("Created EV-specific sensors for vehicle: %s", vin)

    # Add tire pressure sensors for all vehicles
    sensors.extend(
        [
            OnStarTirePressureSensor(coordinator, vin, "lf", "Left Front"),
            OnStarTirePressureSensor(coordinator, vin, "rf", "Right Front"),
            OnStarTirePressureSensor(coordinator, vin, "lr", "Left Rear"),
            OnStarTirePressureSensor(coordinator, vin, "rr", "Right Rear"),
        ]
    )
    _LOGGER.debug("Created tire pressure sensors for vehicle: %s", vin)

    _LOGGER.debug("Adding %s OnStar sensors", len(sensors))
    async_add_entities(sensors, update_before_add=False)


def _is_electric_vehicle(coordinator: DataUpdateCoordinator) -> bool:
    """Determine if the vehicle is an EV based on the diagnostics data."""
    _LOGGER.debug("Checking if vehicle is electric")

    diagnostics = get_diagnostic_response(coordinator.data)
    if diagnostics is None:
        _LOGGER.debug("No diagnostics data available yet to determine EV status")
        return False

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

    def __init__(
        self, coordinator: DataUpdateCoordinator, vin: str, sensor_type: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._vin = vin
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{self._vin}_{sensor_type}"
        _LOGGER.debug("Initialized OnStar sensor: %s", self._attr_unique_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._vin)},
            "name": f"OnStar Vehicle ({self._vin})",
            "manufacturer": "OnStar",
            "model": "Vehicle",
        }

    async def _get_diagnostics(self) -> Any:
        """Get diagnostics data, fetching if needed."""
        try:
            return await self.coordinator.get_diagnostics()  # type: ignore[attr-defined]
        except ClientError:
            _LOGGER.exception("API communication error getting diagnostics")
            return None
        except HomeAssistantError:
            _LOGGER.exception("Home Assistant error getting diagnostics")
            return None
        except (ValueError, KeyError):
            _LOGGER.exception("Invalid response error getting diagnostics")
            return None


class OnStarOdometerSensor(OnStarSensor):
    """Representation of an OnStar odometer sensor."""

    _attr_name = "Odometer"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: DataUpdateCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "odometer")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self) -> float | None:
        """Return the odometer reading."""
        _LOGGER.debug("Getting odometer value for: %s", self._vin)

        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            _LOGGER.debug("No diagnostics data available for odometer")
            return None

        value = get_diagnostic_value(diagnostics, "ODOMETER")

        if value is None:
            _LOGGER.debug("No odometer data found in diagnostics")
            return None

        try:
            float_value = float(value)
            _LOGGER.debug(
                "Found odometer value: %s %s",
                float_value,
                self._attr_native_unit_of_measurement,
            )
        except (ValueError, TypeError):
            _LOGGER.debug("Could not convert odometer value to float: %s", value)
            return None
        else:
            return float_value


class OnStarBatteryLevelSensor(OnStarSensor):
    """Representation of an OnStar EV battery level sensor."""

    _attr_name = "Battery Level"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DataUpdateCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "battery_level")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self) -> float | None:
        """Return the battery level."""
        _LOGGER.debug("Getting battery level for: %s", self._vin)

        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            _LOGGER.debug("No diagnostics data available for battery level")
            return None

        value = get_diagnostic_value(diagnostics, "EV BATTERY LEVEL")

        if value is None:
            _LOGGER.debug("No battery level data found in diagnostics")
            return None

        try:
            float_value = float(value)
            _LOGGER.debug("Found battery level: %s%s", float_value, "%")
        except (ValueError, TypeError):
            _LOGGER.debug("Could not convert battery level to float: %s", value)
            return None
        else:
            return float_value


class OnStarChargeStateSensor(OnStarSensor):
    """Representation of an OnStar EV charge state sensor."""

    _attr_name = "Charge State"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = [
        "charging",
        "not_charging",
        "fully_charged",
        "unknown",
    ]

    def __init__(self, coordinator: DataUpdateCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "charge_state")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self) -> str | None:
        """Return the charge state."""
        _LOGGER.debug("Getting charge state for: %s", self._vin)

        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            _LOGGER.debug("No diagnostics data available for charge state")
            return None

        value = get_diagnostic_value(diagnostics, "EV CHARGE STATE")

        if value is None:
            _LOGGER.debug("No charge state data found in diagnostics")
            return None

        _LOGGER.debug("Found charge state: %s", value)
        # Use dictionary lookup instead of consecutive if statements
        state_map = {
            "charging": "charging",
            "fully_charged": "fully_charged",
            "not_charging": "not_charging",
        }
        return state_map.get(value, "unknown")


class OnStarPlugStateSensor(OnStarSensor):
    """Representation of an OnStar EV plug state sensor."""

    _attr_name = "Plug State"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["plugged", "unplugged", "unknown"]

    def __init__(self, coordinator: DataUpdateCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "plug_state")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self) -> str | None:
        """Return the plug state."""
        _LOGGER.debug("Getting plug state for: %s", self._vin)

        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            _LOGGER.debug("No diagnostics data available for plug state")
            return None

        value = get_diagnostic_value(diagnostics, "EV PLUG STATE")

        if value is None:
            _LOGGER.debug("No plug state data found in diagnostics")
            return None

        _LOGGER.debug("Found plug state: %s", value)
        # Use dictionary lookup instead of consecutive if statements
        state_map = {"plugged": "plugged", "unplugged": "unplugged"}
        return state_map.get(value, "unknown")


class OnStarPlugVoltageSensor(OnStarSensor):
    """Representation of an OnStar EV plug voltage sensor."""

    _attr_name = "Plug Voltage"
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DataUpdateCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "plug_voltage")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self) -> float | None:
        """Return the plug voltage."""
        _LOGGER.debug("Getting plug voltage for: %s", self._vin)

        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            _LOGGER.debug("No diagnostics data available for plug voltage")
            return None

        value = get_diagnostic_value(diagnostics, "EV PLUG VOLTAGE")

        if value is None:
            _LOGGER.debug("No plug voltage data found in diagnostics")
            return None

        try:
            float_value = float(value)
            _LOGGER.debug("Found plug voltage: %s V", float_value)
        except (ValueError, TypeError):
            _LOGGER.debug("Could not convert plug voltage to float: %s", value)
            return None
        else:
            return float_value


class OnStarChargerPowerLevelSensor(OnStarSensor):
    """Representation of an OnStar charger power level sensor."""

    _attr_name = "Charger Power Level"
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, coordinator: DataUpdateCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "charger_power_level")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self) -> str | None:
        """Return the charger power level."""
        _LOGGER.debug("Getting charger power level for: %s", self._vin)

        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            _LOGGER.debug("No diagnostics data available for charger power level")
            return None

        value = get_diagnostic_value(diagnostics, "CHARGER POWER LEVEL")

        if value is None:
            _LOGGER.debug("No charger power level data found in diagnostics")
            return None

        _LOGGER.debug("Found charger power level: %s", value)
        return value


class OnStarChargeCompleteTimeSensor(OnStarSensor):
    """Representation of an OnStar charge complete time sensor."""

    _attr_name = "Charge Complete Time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: DataUpdateCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "charge_complete_time")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self) -> datetime | None:
        """Return the charge complete time as a datetime object."""
        _LOGGER.debug("Getting charge complete time for: %s", self._vin)

        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            _LOGGER.debug("No diagnostics data available for charge complete time")
            return None

        day = get_diagnostic_value(
            diagnostics,
            "HV BATTERY CHARGE COMPLETE TIME",
            "HV BATTERY CHARGE COMPLETE DAY",
        )
        hour = get_diagnostic_value(
            diagnostics,
            "HV BATTERY CHARGE COMPLETE TIME",
            "HV BATTERY CHARGE COMPLETE HOUR",
        )
        minute = get_diagnostic_value(
            diagnostics,
            "HV BATTERY CHARGE COMPLETE TIME",
            "HV BATTERY CHARGE COMPLETE MINUTE",
        )

        if day is None or hour is None or minute is None:
            _LOGGER.debug("Missing day/hour/minute for charge complete time")
            return None

        # Return the datetime object directly for timestamp sensors
        return calculate_next_occurrence_timestamp(day, hour, minute)


class OnStarLastTripEfficiencySensor(OnStarSensor):
    """Representation of an OnStar last trip efficiency sensor."""

    _attr_name = "Last Trip Efficiency"
    _attr_native_unit_of_measurement = "kmple"  # kilometers per liter equivalent
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DataUpdateCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "last_trip_efficiency")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self) -> float | None:
        """Return the last trip efficiency."""
        _LOGGER.debug("Getting last trip efficiency for: %s", self._vin)

        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            _LOGGER.debug("No diagnostics data available for last trip efficiency")
            return None

        value = get_diagnostic_value(diagnostics, "LAST TRIP ELECTRIC ECON")

        if value is None:
            _LOGGER.debug("No last trip efficiency data found in diagnostics")
            return None

        try:
            float_value = float(value)
            _LOGGER.debug("Found last trip efficiency: %s kmple", float_value)
        except (ValueError, TypeError):
            _LOGGER.debug("Could not convert last trip efficiency to float: %s", value)
            return None
        else:
            return float_value


class OnStarLifetimeEfficiencySensor(OnStarSensor):
    """Representation of an OnStar lifetime efficiency sensor."""

    _attr_name = "Lifetime Efficiency"
    _attr_native_unit_of_measurement = "kWh/100km"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DataUpdateCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "lifetime_efficiency")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self) -> float | None:
        """Return the lifetime efficiency."""
        _LOGGER.debug("Getting lifetime efficiency for: %s", self._vin)

        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            _LOGGER.debug("No diagnostics data available for lifetime efficiency")
            return None

        value = get_diagnostic_value(
            diagnostics, "ENERGY EFFICIENCY", "LIFETIME EFFICIENCY"
        )

        if value is None:
            _LOGGER.debug("No lifetime efficiency data found in diagnostics")
            return None

        try:
            float_value = float(value)
            _LOGGER.debug("Found lifetime efficiency: %s kWh/100km", float_value)
        except (ValueError, TypeError):
            _LOGGER.debug("Could not convert lifetime efficiency to float: %s", value)
            return None
        else:
            return float_value


class OnStarTirePressureSensor(OnStarSensor):
    """Representation of an OnStar tire pressure sensor."""

    _attr_native_unit_of_measurement = UnitOfPressure.KPA
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        vin: str,
        position: str,
        position_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, f"tire_pressure_{position}")
        self._position = position.upper()
        self._attr_name = f"Tire Pressure {position_name}"

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self) -> float | None:
        """Return the tire pressure."""
        _LOGGER.debug("Getting tire pressure for %s: %s", self._position, self._vin)

        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            _LOGGER.debug("No diagnostics data available for tire pressure")
            return None

        value = get_diagnostic_value(
            diagnostics, "TIRE PRESSURE", f"TIRE PRESSURE {self._position}"
        )

        if value is None:
            _LOGGER.debug(
                "No tire pressure data found for %s in diagnostics", self._position
            )
            return None

        try:
            float_value = float(value)
            _LOGGER.debug(
                "Found tire pressure for %s: %s kPa", self._position, float_value
            )
        except (ValueError, TypeError):
            _LOGGER.debug("Could not convert tire pressure to float: %s", value)
            return None
        else:
            return float_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the tire pressure sensor."""
        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            return {}

        status = None
        for diagnostic in diagnostics:
            if diagnostic.get("name") == "TIRE PRESSURE":
                for element in diagnostic.get("diagnosticElement", []):
                    if element.get("name") == f"TIRE PRESSURE {self._position}":
                        status = element.get("message")

        if status is None:
            return {}

        return {"status": status}


class OnStarEvRangeSensor(OnStarSensor):
    """Representation of an OnStar EV range sensor."""

    _attr_name = "EV Range"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DataUpdateCoordinator, vin: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vin, "ev_range")

    async def async_update(self) -> None:
        """Update the sensor."""
        await self._get_diagnostics()
        await super().async_update()

    @property
    def native_value(self) -> float | None:
        """Return the EV range."""
        _LOGGER.debug("Getting EV range for: %s", self._vin)

        diagnostics = get_diagnostic_response(self.coordinator.data)
        if diagnostics is None:
            _LOGGER.debug("No diagnostics data available for EV range")
            return None

        value = get_diagnostic_value(diagnostics, "VEHICLE RANGE", "EV RANGE")

        if value is None:
            _LOGGER.debug("No EV range data found in diagnostics")
            return None

        try:
            float_value = float(value)
            _LOGGER.debug("Found EV range: %s km", float_value)
        except (ValueError, TypeError):
            _LOGGER.debug("Could not convert EV range to float: %s", value)
            return None
        else:
            return float_value
