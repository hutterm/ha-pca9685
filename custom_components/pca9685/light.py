"""Support for LED lights that can be controlled using PWM."""

import logging
from datetime import timedelta

import homeassistant.util.color as color_util
import homeassistant.util.dt as dt_util
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_TYPE,
    STATE_ON,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_PIN,
    CONF_PIN_BLUE,
    CONF_PIN_GREEN,
    CONF_PIN_RED,
    CONF_PIN_WHITE,
    CONST_PCA_INT_MULTIPLIER,
    CONST_RGBW_LED_PINS,
    DEFAULT_BRIGHTNESS,
    DEFAULT_COLOR,
    DOMAIN,
    PCA9685_DRIVERS,
)
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

    entities = []
    for unique_id, entry in config_entry.subentries.items():
        if entry.data[CONF_TYPE] == Platform.LIGHT:
            if entry.data.get(CONF_PIN) is not None:
                entities.append(
                    PwmSimpleLed(
                        driver=pca_driver,
                        pin=int(entry.data[CONF_PIN]),
                        name=entry.data[CONF_NAME],
                        unique_id=unique_id,
                        config_unique_id=str(config_entry.unique_id),
                    )
                )
            else:
                pin_white = entry.data.get(CONF_PIN_WHITE, None)
                if pin_white is not None:
                    pin_white = int(pin_white)
                entities.append(
                    PwmRgbwLed(
                        driver=pca_driver,
                        name=entry.data[CONF_NAME],
                        pin_red=int(entry.data[CONF_PIN_RED]),
                        pin_green=int(entry.data[CONF_PIN_GREEN]),
                        pin_blue=int(entry.data[CONF_PIN_BLUE]),
                        pin_white=pin_white,
                        unique_id=unique_id,
                        config_unique_id=str(config_entry.unique_id),
                    )
                )

    async_add_entities(entities)


class PwmSimpleLed(LightEntity, RestoreEntity):
    """Representation of a simple one-color PWM LED."""

    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(
        self,
        driver: PCA9685Driver,
        name: str,
        unique_id: str,
        config_unique_id: str,
        pin: int = 0,
    ) -> None:
        """Initialize one-color PWM LED."""
        self._driver: PCA9685Driver = driver
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_unique_id)},
            name=DOMAIN.upper(),
            manufacturer="NXP",
            model="PCA9685",
        )
        self._attr_unique_id = unique_id
        self._attr_is_on = False
        self._attr_brightness = DEFAULT_BRIGHTNESS
        self._attr_supported_features |= LightEntityFeature.TRANSITION
        self._pin: int = pin
        self._attr_name = name
        self._transition_step_time = timedelta(
            milliseconds=150
        )  # Transition step time in ms
        self._transition_lister: CALLBACK_TYPE | None = None
        self._transition_start = dt_util.utcnow().replace(microsecond=0)
        self._transition_end = self._transition_start
        self._transition_begin_brightness: int = 0
        self._transition_end_brightness: int = 0
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    async def async_added_to_hass(self) -> None:
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            self._attr_is_on = last_state.state == STATE_ON
            self._attr_brightness = last_state.attributes.get(
                "brightness", DEFAULT_BRIGHTNESS
            )

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_turn_on(self, **kwargs: ConfigType) -> None:
        """Turn on a led."""
        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_TRANSITION in kwargs:
            transition_time: timedelta = kwargs[ATTR_TRANSITION]
            await self._async_start_transition(
                brightness=_from_hass_brightness(self._attr_brightness),
                duration=timedelta(seconds=transition_time),
            )
        else:
            self._driver.set_pwm(
                led_num=self._pin, value=_from_hass_brightness(self._attr_brightness)
            )

        self._attr_is_on = True
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: ConfigType) -> None:
        """Turn off a LED."""
        if self.is_on:
            if ATTR_TRANSITION in kwargs:
                transition_time = kwargs[ATTR_TRANSITION]
                await self._async_start_transition(
                    brightness=0, duration=timedelta(seconds=transition_time)
                )
            else:
                self._driver.set_pwm(led_num=self._pin, value=0)

        self._attr_is_on = False
        self.schedule_update_ha_state()

    async def _async_start_transition(
        self, brightness: int, duration: timedelta
    ) -> None:
        """Start light transitio."""
        # First check if a transition was in progress; in that case stop it.
        if self._transition_lister:
            self._transition_lister()
        # initialize relevant values
        self._transition_begin_brightness = self._driver.get_pwm(self._pin)
        if self._transition_begin_brightness != brightness:
            self._transition_start = dt_util.utcnow()
            self._transition_end = self._transition_start + duration
            self._transition_end_brightness = brightness
            # Start transition cycles.
            self._transition_lister = async_track_time_interval(
                self.hass, self._async_step_transition, self._transition_step_time
            )

    @callback
    async def _async_step_transition(self, args: None = None) -> None:  # noqa: ARG002
        """Cycle for transition of output."""
        # Calculate switch off time, and if in the future, add a lister to hass
        now = dt_util.utcnow()
        if now > self._transition_end:
            self._driver.set_pwm(
                led_num=self._pin, value=self._transition_end_brightness
            )
            if self._transition_lister:
                self._transition_lister()  # Stop cycling
        else:
            elapsed: float = (now - self._transition_start).total_seconds()
            total_transition: float = (
                self._transition_end - self._transition_start
            ).total_seconds()
            target_brightness = int(
                self._transition_begin_brightness
                + (
                    (
                        (
                            self._transition_end_brightness
                            - self._transition_begin_brightness
                        )
                        * elapsed
                    )
                    / total_transition
                )
            )
            self._driver.set_pwm(led_num=self._pin, value=target_brightness)


class PwmRgbwLed(PwmSimpleLed):
    """Representation of a RGB(W) PWM LED."""

    def __init__(  # noqa: PLR0913
        self,
        driver: PCA9685Driver,
        name: str,
        unique_id: str,
        config_unique_id: str,
        pin_red: int,
        pin_green: int,
        pin_blue: int,
        pin_white: int | None = None,
    ) -> None:
        """Initialize a RGB(W) PWM LED."""
        super().__init__(
            driver=driver,
            name=name,
            unique_id=unique_id,
            config_unique_id=config_unique_id,
        )
        self._attr_color_mode = ColorMode.HS
        self._attr_supported_color_modes: set[ColorMode] = {self._attr_color_mode}
        self._attr_hs_color = DEFAULT_COLOR
        _LOGGER.debug("color: %s", self._attr_hs_color)
        self._pins: list[int] = [pin_red, pin_green, pin_blue]
        if pin_white is not None:
            self._pins.append(pin_white)
        self._transition_begin_brightness: list[int] = []
        self._transition_end_brightness: list[int] = []

    async def async_added_to_hass(self) -> None:
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            self._attr_hs_color = last_state.attributes.get("hs_color", DEFAULT_COLOR)
            if (
                self._attr_hs_color is None
            ):  # If HA was forcefully closed, hs_color might contain None
                self._attr_hs_color = DEFAULT_COLOR

    async def async_turn_on(self, **kwargs: ConfigType) -> None:
        """Turn on a LED."""
        if ATTR_HS_COLOR in kwargs:
            self._attr_hs_color = kwargs[ATTR_HS_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        color = list(color_util.color_hs_to_RGB(*self._attr_hs_color))
        if len(self._pins) == CONST_RGBW_LED_PINS:
            color = list(color_util.color_rgb_to_rgbw(color[0], color[1], color[2]))
        brightness = _from_hass_brightness(self._attr_brightness)
        max_value = float(max(color))
        for i in range(len(color)):
            color[i] = int((color[i] / max_value) * brightness)
            _LOGGER.debug("Set color [%d] to value %d", i, color[i])

        if ATTR_TRANSITION in kwargs:
            transition_time: timedelta = kwargs[ATTR_TRANSITION]
            await self._async_start_transition(
                brightness=color,
                duration=timedelta(seconds=transition_time),
            )
        else:
            for i in range(len(self._pins)):
                self._driver.set_pwm(led_num=self._pins[i], value=color[i])

        self._attr_is_on = True
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: ConfigType) -> None:
        """Turn off a LED."""
        if self.is_on:
            color = [0, 0, 0]
            if len(self._pins) == CONST_RGBW_LED_PINS:
                color.append(0)
            if ATTR_TRANSITION in kwargs:
                transition_time = kwargs[ATTR_TRANSITION]
                await self._async_start_transition(
                    brightness=color, duration=timedelta(seconds=transition_time)
                )
            else:
                for i in range(len(self._pins)):
                    self._driver.set_pwm(led_num=self._pins[i], value=0)

        self._attr_is_on = False
        self.schedule_update_ha_state()

    async def _async_start_transition(
        self, brightness: list[int], duration: timedelta
    ) -> None:
        """Start light transitio."""
        # First check if a transition was in progress; in that case stop it.
        if self._transition_lister:
            self._transition_lister()
        # initialize relevant values
        self._transition_begin_brightness.clear()
        color_is_different = False
        for i in range(len(self._pins)):
            self._transition_begin_brightness.append(
                self._driver.get_pwm(self._pins[i])
            )
            if self._transition_begin_brightness[i] != brightness[i]:
                color_is_different = True

        if color_is_different:
            self._transition_start = dt_util.utcnow()
            self._transition_end = self._transition_start + duration
            self._transition_end_brightness = brightness
            # Start transition cycles.
            self._transition_lister = async_track_time_interval(
                self.hass, self._async_step_transition, self._transition_step_time
            )

    @callback
    async def _async_step_transition(self, args: None = None) -> None:  # noqa: ARG002
        """Cycle for transition of output."""
        # Calculate switch off time, and if in the future, add a lister to hass
        now = dt_util.utcnow()
        if now > self._transition_end:
            for i in range(len(self._pins)):
                self._driver.set_pwm(
                    led_num=self._pins[i], value=self._transition_end_brightness[i]
                )
            if self._transition_lister:
                self._transition_lister()  # Stop cycling
        else:
            elapsed: float = (now - self._transition_start).total_seconds()
            total_transition: float = (
                self._transition_end - self._transition_start
            ).total_seconds()
            for i in range(len(self._pins)):
                target_brightness = int(
                    self._transition_begin_brightness[i]
                    + (
                        (
                            (
                                self._transition_end_brightness[i]
                                - self._transition_begin_brightness[i]
                            )
                            * elapsed
                        )
                        / total_transition
                    )
                )
                self._driver.set_pwm(led_num=self._pins[i], value=target_brightness)


def _from_hass_brightness(brightness: int | None) -> int:
    """Convert Home Assistant  units (0..256) to 0..4096."""
    if brightness:
        return brightness * CONST_PCA_INT_MULTIPLIER
    return 0
