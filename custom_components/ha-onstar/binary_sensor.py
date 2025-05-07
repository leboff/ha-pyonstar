"""Support for OnStar binary sensors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: ConfigEntry,  # noqa: ARG001
    async_add_entities: AddEntitiesCallback,  # noqa: ARG001
) -> None:
    """Set up the OnStar binary sensor platform."""
    # Binary sensors are disabled in this simplified version
    return
