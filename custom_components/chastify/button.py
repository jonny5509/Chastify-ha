from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChastifyCoordinator

FREEZE_BUTTON_DURATION_SECONDS = 3600


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    registry = er.async_get(hass)
    allowed = {
        "Refresh",
        "Refresh history",
        "Hygienic unlock",
        "Emergency unlock",
        "Archive",
        "Freeze",
        "Unfreeze",
    }
    for entity in list(registry.entities.values()):
        if entity.config_entry_id == entry.entry_id and entity.domain == "button":
            if (entity.original_name or entity.name or "") not in allowed:
                registry.async_remove(entity.entity_id)

    async_add_entities(
        [
            RefreshButton(coordinator, entry, "refresh"),
            RefreshHistoryButton(coordinator, entry),
            UnlockButton(coordinator, entry),
            EmergencyUnlockButton(coordinator, entry),
            ArchiveButton(coordinator, entry),
            FreezeButton(coordinator, entry),
            UnfreezeButton(coordinator, entry),
        ]
    )


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

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


class FreezeButton(ChastifyButton):
    _attr_name = "Freeze"
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_freeze"

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data)

    async def async_press(self) -> None:
        await self.coordinator.api.async_freeze(FREEZE_BUTTON_DURATION_SECONDS)
        await self.coordinator.async_request_refresh()


class UnfreezeButton(ChastifyButton):
    _attr_name = "Unfreeze"
    _attr_icon = "mdi:snowflake-off"

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_unfreeze"

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data)

    async def async_press(self) -> None:
        await self.coordinator.api.async_unfreeze()
        await self.coordinator.async_request_refresh()


class RefreshHistoryButton(ChastifyButton):
    _attr_name = "Refresh history"
    _attr_icon = "mdi:history"

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_history"

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


class UnlockButton(ChastifyButton):
    # Chastify's External API does not expose a generic "unlock" action.
    # The documented unlock-related action is hygienic_unlock.start.
    _attr_name = "Hygienic unlock"
    _attr_icon = "mdi:lock-open"

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_unlock"

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data)

    async def async_press(self) -> None:
        await self.coordinator.api.async_hygienic_unlock()
        await self.coordinator.async_request_refresh()


class EmergencyUnlockButton(ChastifyButton):
    _attr_name = "Emergency unlock"
    _attr_icon = "mdi:alert-octagon"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_emergency_unlock"

    @property
    def available(self) -> bool:
        return False

    async def async_press(self) -> None:
        return


class ArchiveButton(ChastifyButton):
    _attr_name = "Archive"
    _attr_icon = "mdi:archive"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_archive"

    @property
    def available(self) -> bool:
        return False

    async def async_press(self) -> None:
        return
