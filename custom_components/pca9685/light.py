"""Support for LED lights that can be controlled using PWM."""

import logging
from typing import ClassVar

import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util
import voluptuous as vol
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from pwmled import Color
from pwmled.driver.pca9685 import Pca9685Driver
from pwmled.led import SimpleLed
from pwmled.led.rgb import RgbLed
from pwmled.led.rgbw import RgbwLed

from .const import (
    CONF_FREQUENCY,
    CONF_LEDS,
    CONF_PINS,
    CONST_MAX_INTENSITY,
    CONST_RGB_LED_PINS,
    CONST_RGBW_LED_PINS,
    CONST_SIMPLE_LED_PINS,
    DEFAULT_BRIGHTNESS,
    DEFAULT_COLOR,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_LEDS): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Required(CONF_PINS): vol.All(cv.ensure_list, [cv.positive_int]),
                    vol.Optional(CONF_FREQUENCY): cv.positive_int,
                    vol.Optional(CONF_ADDRESS): cv.byte,
                }
            ],
        )
    }
)


def setup_platform(
    hass: HomeAssistant,  # noqa: ARG001
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,  # noqa: ARG001
) -> None:
    """Set up the PWM LED lights."""
    leds = []
    for led_conf in config[CONF_LEDS]:
        pins = led_conf[CONF_PINS]
        opt_args = {}
        if CONF_FREQUENCY in led_conf:
            opt_args["freq"] = led_conf[CONF_FREQUENCY]
        if CONF_ADDRESS in led_conf:
            opt_args["address"] = led_conf[CONF_ADDRESS]
        driver = Pca9685Driver(pins, **opt_args)

        name = led_conf[CONF_NAME]
        if len(pins) == CONST_SIMPLE_LED_PINS:
            led = PwmSimpleLed(SimpleLed(driver), name)
        elif len(pins) == CONST_RGB_LED_PINS:
            led = PwmRgbLed(RgbLed(driver), name)
        elif len(pins) == CONST_RGBW_LED_PINS:
            led = PwmRgbLed(RgbwLed(driver), name)
        else:
            _LOGGER.error("Invalid led type")
            return
        leds.append(led)

    add_entities(leds)


class PwmSimpleLed(LightEntity, RestoreEntity):
    """Representation of a simple one-color PWM LED."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes: ClassVar[dict[ColorMode.HS]] = {ColorMode.BRIGHTNESS}

    def __init__(self, led: SimpleLed, name: str) -> None:
        """Initialize one-color PWM LED."""
        self._led = led
        self._name = name
        self._is_on = False
        self._brightness = DEFAULT_BRIGHTNESS
        self._attr_supported_features |= LightEntityFeature.TRANSITION

    async def async_added_to_hass(self) -> None:
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            self._is_on = last_state.state == STATE_ON
            self._brightness = last_state.attributes.get(
                "brightness", DEFAULT_BRIGHTNESS
            )

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the group."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._is_on

    @property
    def brightness(self) -> int:
        """Return the brightness property."""
        return self._brightness

    def turn_on(self, **kwargs: ConfigType) -> None:
        """Turn on a led."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_TRANSITION in kwargs:
            transition_time = kwargs[ATTR_TRANSITION]
            self._led.transition(
                transition_time,
                is_on=True,
                brightness=_from_hass_brightness(self._brightness),
            )
        else:
            self._led.set(
                is_on=True, brightness=_from_hass_brightness(self._brightness)
            )

        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: ConfigType) -> None:
        """Turn off a LED."""
        if self.is_on:
            if ATTR_TRANSITION in kwargs:
                transition_time = kwargs[ATTR_TRANSITION]
                self._led.transition(transition_time, is_on=False)
            else:
                self._led.off()

        self._is_on = False
        self.schedule_update_ha_state()


class PwmRgbLed(PwmSimpleLed):
    """Representation of a RGB(W) PWM LED."""

    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes: ClassVar[dict[ColorMode.HS]] = {ColorMode.HS}

    def __init__(self, led: RgbLed | RgbwLed, name: str) -> None:
        """Initialize a RGB(W) PWM LED."""
        super().__init__(led, name)
        self._color = DEFAULT_COLOR

    async def async_added_to_hass(self) -> None:
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            self._color = last_state.attributes.get("hs_color", DEFAULT_COLOR)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the color property."""
        return self._color

    def turn_on(self, **kwargs: ConfigType) -> None:
        """Turn on a LED."""
        if ATTR_HS_COLOR in kwargs:
            self._color = kwargs[ATTR_HS_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_TRANSITION in kwargs:
            transition_time = kwargs[ATTR_TRANSITION]
            self._led.transition(
                transition_time,
                is_on=True,
                brightness=_from_hass_brightness(self._brightness),
                color=_from_hass_color(self._color),
            )
        else:
            self._led.set(
                is_on=True,
                brightness=_from_hass_brightness(self._brightness),
                color=_from_hass_color(self._color),
            )

        self._is_on = True
        self.schedule_update_ha_state()


def _from_hass_brightness(brightness: int) -> int:
    """Convert Home Assistant brightness units to percentage."""
    return brightness / CONST_MAX_INTENSITY


def _from_hass_color(color: list) -> Color:
    """Convert Home Assistant RGB list to Color tuple."""
    rgb = color_util.color_hs_to_RGB(*color)
    return Color(*tuple(rgb))
