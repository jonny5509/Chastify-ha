from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ChastifyApiError
from .const import DOMAIN
from .coordinator import ChastifyCoordinator

FREEZE_BUTTON_DURATION_SECONDS = 3600
ADD_DAY_SECONDS = 86400
ADD_HOUR_SECONDS = 3600


async def _async_api_call(func, *args) -> None:
    """Convert Chastify API failures into user-visible Home Assistant errors."""
    try:
        await func(*args)
    except ChastifyApiError as err:
        raise HomeAssistantError(f"Chastify API error: {err}") from err


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
        "Clear calendar history",
        "Hygienic unlock",
        "Add 1 day",
        "Add 1 hour",
        "Subtract 1 day",
        "Subtract 1 hour",
        "Freeze",
        "Unfreeze",
        "Test daily congratulations",
        "Test session-end congratulations",
    }
    for entity in list(registry.entities.values()):
        if entity.config_entry_id == entry.entry_id and entity.domain == "button":
            if (entity.original_name or entity.name or "") not in allowed:
                registry.async_remove(entity.entity_id)

    async_add_entities(
        [
            RefreshButton(coordinator, entry, "refresh"),
            RefreshHistoryButton(coordinator, entry),
            ClearCalendarHistoryButton(coordinator, entry),
            UnlockButton(coordinator, entry),
            AddOneDayButton(coordinator, entry),
            AddOneHourButton(coordinator, entry),
            SubtractOneDayButton(coordinator, entry),
            SubtractOneHourButton(coordinator, entry),
            FreezeButton(coordinator, entry),
            UnfreezeButton(coordinator, entry),
            TestDailyNotificationButton(hass, entry),
            TestSessionEndNotificationButton(hass, entry),
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
        await _async_api_call(self.coordinator.api.async_freeze, FREEZE_BUTTON_DURATION_SECONDS)
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
        await _async_api_call(self.coordinator.api.async_unfreeze)
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
        await _async_api_call(self.coordinator.api.async_hygienic_unlock)
        await self.coordinator.async_request_refresh()


class AddOneDayButton(ChastifyButton):
    _attr_name = "Add 1 day"
    _attr_icon = "mdi:calendar-plus"

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_add_1_day"

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data)

    async def async_press(self) -> None:
        await _async_api_call(self.coordinator.api.async_apply_time, ADD_DAY_SECONDS)
        await self.coordinator.async_request_refresh()


class AddOneHourButton(ChastifyButton):
    _attr_name = "Add 1 hour"
    _attr_icon = "mdi:clock-plus"

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_add_1_hour"

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data)

    async def async_press(self) -> None:
        await _async_api_call(self.coordinator.api.async_apply_time, ADD_HOUR_SECONDS)
        await self.coordinator.async_request_refresh()


class SubtractOneDayButton(ChastifyButton):
    _attr_name = "Subtract 1 day"
    _attr_icon = "mdi:calendar-minus"

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_subtract_1_day"

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data)

    async def async_press(self) -> None:
        await _async_api_call(self.coordinator.api.async_apply_time, -ADD_DAY_SECONDS)
        await self.coordinator.async_request_refresh()


class SubtractOneHourButton(ChastifyButton):
    _attr_name = "Subtract 1 hour"
    _attr_icon = "mdi:clock-minus"

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_subtract_1_hour"

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data)

    async def async_press(self) -> None:
        await _async_api_call(self.coordinator.api.async_apply_time, -ADD_HOUR_SECONDS)
        await self.coordinator.async_request_refresh()


class ClearCalendarHistoryButton(ChastifyButton):
    """Clear completed local calendar history without touching the active session."""

    _attr_name = "Clear calendar history"
    _attr_icon = "mdi:calendar-remove"

    def __init__(self, coordinator: ChastifyCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_clear_calendar_history"

    async def async_press(self) -> None:
        calendar = self.hass.data.get(DOMAIN, {}).get(self._entry_id, {}).get("calendar")
        if calendar is None:
            raise HomeAssistantError("Chastify calendar is not available")
        await calendar.async_clear_history()



class TestNotificationButton(ButtonEntity):
    """Send a sample Chastify congratulations notification without changing session state."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry_id = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_my_lock")},
            "name": "Session",
            "manufacturer": "Chastify",
            "model": "Chastify Lock",
        }


class TestDailyNotificationButton(TestNotificationButton):
    """Test the daily congratulations notification."""

    _attr_name = "Test daily congratulations"
    _attr_icon = "mdi:party-popper"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}_test_daily_notification"

    async def async_press(self) -> None:
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "🎉 Chastify daily notification test",
                "message": "Test successful! This is an example of the daily congratulations notification. Your session and notification schedule have not been changed.",
                "notification_id": f"chastify_{self._entry_id}_test_daily",
            },
            blocking=True,
        )


class TestSessionEndNotificationButton(TestNotificationButton):
    """Test the session-end congratulations notification."""

    _attr_name = "Test session-end congratulations"
    _attr_icon = "mdi:party-popper"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}_test_session_end_notification"

    async def async_press(self) -> None:
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "🎉 Chastify session-end notification test",
                "message": "Test successful! This is an example of the session-end congratulations notification. Your session and notification schedule have not been changed.",
                "notification_id": f"chastify_{self._entry_id}_test_session_end",
            },
            blocking=True,
        )
