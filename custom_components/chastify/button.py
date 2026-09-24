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
    async_add_entities(
        [
            RefreshButton(coordinator, entry, "my_lock", "My Lock", "refresh"),
            RefreshButton(coordinator, entry, "keyholder", "Keyholder", "keyholder_refresh"),
            FreezeButton(coordinator, entry, "wearer"),
            UnfreezeButton(coordinator, entry, "wearer"),
            FreezeButton(coordinator, entry, "keyholder"),
            UnfreezeButton(coordinator, entry, "keyholder"),
        ]
    )


class ChastifyButton(CoordinatorEntity[ChastifyCoordinator], ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry, device_id: str = "my_lock", device_name: str = "My Lock") -> None:
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{device_id}")},
            "name": device_name,
            "manufacturer": "Chastify",
            "model": "Chastify Lock" if device_id == "my_lock" else "Chastify Keyholder",
        }


def _session_role(data: dict[str, Any]) -> str | None:
    payload = data.get("data", data)
    if not isinstance(payload, dict):
        return None

    for key in ("role", "userRole", "sessionRole"):
        value = payload.get(key)
        if isinstance(value, str):
            return value.strip().lower()

    lock_data = payload.get("lockData")
    if isinstance(lock_data, dict):
        for key in ("role", "userRole", "sessionRole"):
            value = lock_data.get(key)
            if isinstance(value, str):
                return value.strip().lower()

    return None


class RefreshButton(ChastifyButton):
    _attr_name = "Refresh"
    _attr_icon = "mdi:refresh"

    def __init__(
        self,
        coordinator: ChastifyCoordinator,
        entry: ConfigEntry,
        device_id: str,
        device_name: str,
        unique_id_key: str,
    ) -> None:
        super().__init__(coordinator, entry, device_id, device_name)
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_key}"

    @property
    def available(self) -> bool:
        return super().available

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


class FreezeButton(ChastifyButton):
    def __init__(
        self,
        coordinator: ChastifyCoordinator,
        entry: ConfigEntry,
        role: str,
    ) -> None:
        super().__init__(coordinator, entry, "my_lock" if role == "wearer" else "keyholder", "My Lock" if role == "wearer" else "Keyholder")
        self._role = role
        label = "My Lock" if role == "wearer" else "Keyholder"
        self._attr_name = f"{label} - Freeze"
        self._attr_icon = "mdi:snowflake"
        self._attr_unique_id = f"{entry.entry_id}_{role}_freeze"

    @property
    def available(self) -> bool:
        return super().available and _session_role(self.coordinator.data) == self._role

    async def async_press(self) -> None:
        await self.coordinator.api.async_freeze(FREEZE_BUTTON_DURATION_SECONDS)
        await self.coordinator.async_request_refresh()


class UnfreezeButton(ChastifyButton):
    def __init__(
        self,
        coordinator: ChastifyCoordinator,
        entry: ConfigEntry,
        role: str,
    ) -> None:
        super().__init__(coordinator, entry, "my_lock" if role == "wearer" else "keyholder", "My Lock" if role == "wearer" else "Keyholder")
        self._role = role
        label = "My Lock" if role == "wearer" else "Keyholder"
        self._attr_name = f"{label} - Unfreeze"
        self._attr_icon = "mdi:snowflake-off"
        self._attr_unique_id = f"{entry.entry_id}_{role}_unfreeze"

    @property
    def available(self) -> bool:
        return super().available and _session_role(self.coordinator.data) == self._role

    async def async_press(self) -> None:
        await self.coordinator.api.async_unfreeze()
        await self.coordinator.async_request_refresh()
