from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ChastifyCoordinator, field


# The Chastify API requires durationSeconds for a freeze request.
# The documented default freeze duration is one hour.
# Use the freeze service when a specific duration
# is required.
FREEZE_BUTTON_DURATION_SECONDS = 3600

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        RefreshButton(coordinator, entry, "refresh"),
        FreezeButton(coordinator, entry),
        UnfreezeButton(coordinator, entry),
    ])


class ChastifyButton(CoordinatorEntity[ChastifyCoordinator], ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_my_lock")},
            "name": "Session",
            "manufacturer": "Chastify",
            "model": "Chastify Lock",
        }



class RefreshButton(ChastifyButton):
    _attr_name = "Refresh"
    _attr_icon = "mdi:refresh"

    def __init__(
        self,
        coordinator: ChastifyCoordinator,
        entry: ConfigEntry,
        unique_id_key: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_key}"

    @property
    def available(self) -> bool:
        return super().available

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()

class FreezeButton(ChastifyButton):
    _attr_name = "Freeze"
    _attr_icon = "mdi:snowflake"
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_freeze"
    async def async_press(self) -> None:
        await self.coordinator.api.async_freeze(FREEZE_BUTTON_DURATION_SECONDS)
        await self.coordinator.async_request_refresh()

class UnfreezeButton(ChastifyButton):
    _attr_name = "Unfreeze"
    _attr_icon = "mdi:snowflake-off"
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_unfreeze"
    async def async_press(self) -> None:
        await self.coordinator.api.async_unfreeze()
        await self.coordinator.async_request_refresh()
