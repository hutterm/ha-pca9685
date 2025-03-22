"""Support for numbers that can be controlled using PWM."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.number import (
    RestoreNumber,
)
from homeassistant.const import (
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_MODE,
    CONF_NAME,
    CONF_PIN,
    CONF_TYPE,
    Platform,
)
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    ATTR_FREQUENCY,
    ATTR_INVERT,
    CONF_INVERT,
    CONF_NORMALIZE_LOWER,
    CONF_NORMALIZE_UPPER,
    CONF_STEP,
    DOMAIN,
    PCA9685_DRIVERS,
)

if TYPE_CHECKING:
    from types import MappingProxyType

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .pca_driver import PCA9685Driver

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==PCA9685 device)."""
    pca_driver: PCA9685Driver = hass.data[DOMAIN][PCA9685_DRIVERS][
        config_entry.entry_id
    ]

    entities = [
        PwmNumber(
            config=entry.data,
            driver=pca_driver,
            unique_id=unique_id,
            config_unique_id=str(config_entry.unique_id),
        )
        for unique_id, entry in config_entry.subentries.items()
        if entry.data[CONF_TYPE] == Platform.NUMBER
    ]

    if len(entities) > 0:
        async_add_entities(entities)


class PwmNumber(RestoreNumber):
    """Representation of a simple  PWM output."""

    _attr_should_poll = False

    def __init__(
        self,
        config: MappingProxyType[str, Any],
        driver: PCA9685Driver,
        unique_id: str,
        config_unique_id: str,
    ) -> None:
        """Initialize one-color PWM LED."""
        self._driver = driver
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_unique_id)},
            name=DOMAIN.upper(),
            manufacturer="NXP",
            model="PCA9685",
        )
        self._attr_unique_id = unique_id
        self._config = config
        self._attr_native_min_value = config[CONF_MINIMUM]
        self._attr_native_max_value = config[CONF_MAXIMUM]
        self._attr_native_step = config[CONF_STEP]
        self._attr_mode = config[CONF_MODE]
        self._attr_native_value = config[CONF_MINIMUM]
        self._attr_name = config[CONF_NAME]
        self._pin = int(config[CONF_PIN])

    async def async_added_to_hass(self) -> None:
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        if last_data := await self.async_get_last_number_data():
            try:
                await self.async_set_native_value(float(last_data.native_value))
            except ValueError:
                _LOGGER.warning(
                    "Could not read value %s from last state data for %s!",
                    last_data.native_value,
                    self.name,
                )
        else:
            await self.async_set_native_value(self._config[CONF_MINIMUM])

    @property
    def frequency(self) -> int:
        """Return PWM frequency."""
        return self._driver.get_pwm_frequency()

    @property
    def invert(self) -> bool:
        """Return if output is inverted."""
        return self._config[CONF_INVERT]

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        attr = super().capability_attributes
        attr[ATTR_FREQUENCY] = self.frequency
        attr[ATTR_INVERT] = self.invert
        return attr

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        # Clip value to limits (don't know if this is required?)
        value = max(value, self._config[CONF_MINIMUM])
        value = min(value, self._config[CONF_MAXIMUM])

        # In case the invert bit is on, invert the value
        used_value = value
        if self._config[CONF_INVERT]:
            used_value = self._config[CONF_NORMALIZE_UPPER] - value
        used_value -= self._config[CONF_NORMALIZE_LOWER]
        # Scale range from N_L..N_U to 0..65535 (pca9685)
        range_pwm = 4095
        range_value = (
            self._config[CONF_NORMALIZE_UPPER] - self._config[CONF_NORMALIZE_LOWER]
        )

        # Scale to range of the driver
        scaled_value = round((used_value / range_value) * range_pwm)
        # Make sure it will fit in the 12-bits range of the pca9685
        scaled_value = min(range_pwm, scaled_value)
        scaled_value = max(0, scaled_value)
        # Set value to driver
        self._driver.set_pwm(led_num=self._pin, value=scaled_value)
        self._attr_native_value = value
        self.schedule_update_ha_state()
