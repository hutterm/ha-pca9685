"""Config flow definition for PCA9685."""

import logging
from pathlib import Path
from typing import Any, ClassVar

import voluptuous as vol
from homeassistant.components.light import ColorMode
from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
)
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_ENTITIES,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_MODE,
    CONF_NAME,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    Platform,
)
from homeassistant.helpers import selector

from .const import (
    CONF_ADDR,
    CONF_BUS,
    CONF_FREQUENCY,
    CONF_INVERT,
    CONF_NORMALIZE_LOWER,
    CONF_NORMALIZE_UPPER,
    CONF_PIN,
    CONF_PIN_BLUE,
    CONF_PIN_GREEN,
    CONF_PIN_RED,
    CONF_PIN_WHITE,
    CONF_STEP,
    CONST_ADDR_MAX,
    CONST_ADDR_MIN,
    CONST_PWM_FREQ_MAX,
    CONST_PWM_FREQ_MIN,
    CONST_RGB_LED_PINS,
    CONST_RGBW_LED_PINS,
    CONST_SIMPLE_LED_PINS,
    DEFAULT_ADDR,
    DEFAULT_FREQ,
    DOMAIN,
    MODE_AUTO,
    MODE_BOX,
    MODE_SLIDER,
)

_LOGGER = logging.getLogger(__name__)


class PCA9685ConfigFlow(ConfigFlow, domain=DOMAIN):
    """PCA9685 device Config handler."""

    VERSION = 1
    _available_pins: ClassVar[list[int]] = list(range(16))
    config_data: ClassVar[dict[str, Any]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Invoke when a user initiates a flow via the user interface."""
        if user_input and user_input.get(CONF_BUS):
            _LOGGER.info(
                "ConfigFlow: i2c bus: %s, type %s",
                str(user_input[CONF_BUS]),
                type(user_input[CONF_BUS]),
            )
            # Reset pin list when new config flow starts
            self._available_pins.clear()
            self._available_pins.extend(range(16))
            self.config_data[CONF_BUS] = user_input[CONF_BUS]
            self.config_data[CONF_ADDR] = int(user_input[CONF_ADDR])
            self.config_data[CONF_FREQUENCY] = user_input[CONF_FREQUENCY]
            self.config_data[CONF_ENTITIES] = []
            return await self.async_show_entity_menu(user_input)

        def blocking_code() -> list[str]:
            return [str(bus) for bus in Path("/dev/").glob("i2c-*")]

        # First check if an I2C bus is available
        i2c_busses = await self.hass.async_add_executor_job(blocking_code)
        i2c_bus_selector = [
            selector.SelectOptionDict(value=bus, label=bus) for bus in i2c_busses
        ]

        errors: dict[str, str] = {}
        if not len(i2c_busses):
            errors["base"] = "No I2C bus found, please configure system first."
            return self.async_abort(
                reason="Cannot find I2C-bus; first configure your system. "
                "Check it in Settings->System->Hardware->All hardware"
            )

        ctrl_scheme = vol.Schema(
            {
                vol.Optional(CONF_BUS, default=i2c_busses[0]): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=i2c_bus_selector),
                ),
                vol.Optional(CONF_ADDR, default=DEFAULT_ADDR): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=CONST_ADDR_MIN,
                        max=CONST_ADDR_MAX,
                        mode=selector.NumberSelectorMode.BOX,
                        step=1,
                    ),
                ),
                vol.Optional(
                    CONF_FREQUENCY, default=DEFAULT_FREQ
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=CONST_PWM_FREQ_MIN,
                        max=CONST_PWM_FREQ_MAX,
                        mode=selector.NumberSelectorMode.BOX,
                        step=1,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=ctrl_scheme,
            errors=errors,
        )

    async def async_show_entity_menu(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Show menu to configure entities."""
        # We know the about the bus, now we have to define the lights & numbers
        pins = len(self._available_pins)
        if pins == 0:
            return self.async_create_entry(
                title="PCA9685 Device ("
                + self.config_data[CONF_BUS]
                + " address "
                + str(int(self.config_data[CONF_ADDR]))
                + ")",
                data=self.config_data,
            )

        options = {}
        if pins >= CONST_SIMPLE_LED_PINS:
            options["add_light_brightness"] = "Add a simple single-color LED"
            options["add_number_brightness"] = "Add a PWM controllable Number"
        if pins >= CONST_RGB_LED_PINS:
            options["add_light_rgb"] = "Add a RGB LED"
        if pins >= CONST_RGBW_LED_PINS:
            options["add_light_rgbw"] = "Add a RGBW LED"

        options["ready"] = "Finish"
        return self.async_show_menu(menu_options=options)

    async def async_step_add_light_brightness(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a light."""
        return await self.async_add_entity(
            entity_type=Platform.LIGHT, user_input=user_input
        )

    async def async_step_add_number_brightness(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a number."""
        return await self.async_add_entity(
            entity_type=Platform.NUMBER, user_input=user_input
        )

    async def async_step_add_light_rgb(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a light."""
        return await self.async_add_entity(
            entity_type=Platform.LIGHT, user_input=user_input, color=ColorMode.RGB
        )

    async def async_step_add_light_rgbw(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a light."""
        return await self.async_add_entity(
            entity_type=Platform.LIGHT, user_input=user_input, color=ColorMode.RGBW
        )

    async def async_add_entity(
        self,
        entity_type: str,
        user_input: dict[str, Any] | None = None,
        color: ColorMode = ColorMode.BRIGHTNESS,
    ) -> ConfigFlowResult:
        """Add a number or light entity."""
        pin_selector = [
            selector.SelectOptionDict(value=str(pin), label=str(pin))
            for pin in self._available_pins
        ]
        cfg_scheme = {}
        if color == ColorMode.BRIGHTNESS:
            cfg_scheme = vol.Schema(
                {
                    vol.Required(CONF_NAME): selector.TextSelector(),
                    vol.Required(
                        CONF_PIN, default=str(self._available_pins[0])
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=pin_selector),
                    ),
                }
            )
        else:
            cfg_scheme = vol.Schema(
                {
                    vol.Required(CONF_NAME): selector.TextSelector(),
                    vol.Required(
                        CONF_PIN_RED, default=str(self._available_pins[0])
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=pin_selector),
                    ),
                    vol.Required(
                        CONF_PIN_GREEN, default=str(self._available_pins[1])
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=pin_selector),
                    ),
                    vol.Required(
                        CONF_PIN_BLUE, default=str(self._available_pins[2])
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=pin_selector),
                    ),
                }
            )
        if entity_type == Platform.NUMBER:
            cfg_scheme = cfg_scheme.extend(
                {
                    vol.Optional(
                        CONF_INVERT, default=False
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_MINIMUM, default=DEFAULT_MIN_VALUE
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_MAXIMUM, default=DEFAULT_MAX_VALUE
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_NORMALIZE_LOWER, default=DEFAULT_MIN_VALUE
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_NORMALIZE_UPPER, default=DEFAULT_MAX_VALUE
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_STEP, default=DEFAULT_STEP
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                    vol.Optional(
                        CONF_MODE, default=MODE_SLIDER
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=MODE_BOX, label=MODE_BOX
                                ),
                                selector.SelectOptionDict(
                                    value=MODE_SLIDER, label=MODE_SLIDER
                                ),
                                selector.SelectOptionDict(
                                    value=MODE_AUTO, label=MODE_AUTO
                                ),
                            ]
                        )
                    ),
                }
            )
        if color == ColorMode.RGBW:
            cfg_scheme = cfg_scheme.extend(
                {
                    vol.Required(
                        CONF_PIN_WHITE, default=str(self._available_pins[3])
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=pin_selector),
                    ),
                }
            )

        if user_input is None:
            return self.async_show_form(
                step_id="add_" + entity_type + "_" + color.lower(),
                data_schema=cfg_scheme,
            )
        # Set first part of the unique ID
        user_input[CONF_UNIQUE_ID] = (
            "PCA9685_"
            + str(self.config_data[CONF_BUS])
            + "_"
            + str(self.config_data[CONF_ADDR])
            + "_"
            + user_input[CONF_NAME]
            + "_"
        )
        if color != ColorMode.BRIGHTNESS:
            # Check if not selected equal pin numbers
            err = self._check_pin_conflicts(user_input)

            if len(err):
                return self.async_show_form(
                    step_id="add_light_" + color.lower(),
                    data_schema=self.add_suggested_values_to_schema(
                        cfg_scheme, user_input
                    ),
                    errors=err,
                )
            # Add pins to unique ID
            user_input[CONF_UNIQUE_ID] += (
                str(user_input[CONF_PIN_RED])
                + str(user_input[CONF_PIN_GREEN])
                + str(user_input[CONF_PIN_GREEN])
            )
            # Remove used pins from list of available and change type of pin to int.
            user_input[CONF_PIN_RED] = int(user_input[CONF_PIN_RED])
            self._available_pins.remove(user_input[CONF_PIN_RED])
            user_input[CONF_PIN_GREEN] = int(user_input[CONF_PIN_GREEN])
            self._available_pins.remove(user_input[CONF_PIN_GREEN])
            user_input[CONF_PIN_BLUE] = int(user_input[CONF_PIN_BLUE])
            self._available_pins.remove(user_input[CONF_PIN_BLUE])
            if user_input.get(CONF_PIN_WHITE):
                user_input[CONF_PIN_WHITE] = int(user_input[CONF_PIN_WHITE])
                self._available_pins.remove(user_input[CONF_PIN_WHITE])
                user_input[CONF_UNIQUE_ID] += str(user_input[CONF_PIN_WHITE])
        else:
            # Remove used pins from list of available
            user_input[CONF_PIN] = int(user_input[CONF_PIN])
            self._available_pins.remove(int(user_input[CONF_PIN]))
            user_input[CONF_UNIQUE_ID] += str(user_input[CONF_PIN])
        user_input[CONF_TYPE] = entity_type

        self.config_data[CONF_ENTITIES].append(user_input)
        return await self.async_show_entity_menu(user_input=user_input)

    def _check_pin_conflicts(self, user_input: dict[str, str]) -> dict[str, str]:
        """Check for conflicting pins."""
        err = {}
        if user_input[CONF_PIN_RED] == user_input[CONF_PIN_GREEN]:
            err[CONF_PIN_GREEN] = "Green light uses same pin number as red light!"
        if user_input[CONF_PIN_RED] == user_input[CONF_PIN_BLUE]:
            err[CONF_PIN_BLUE] = "Blue light uses same pin number as red light!"
        if user_input[CONF_PIN_GREEN] == user_input[CONF_PIN_BLUE]:
            err[CONF_PIN_GREEN] = "Blue light uses same pin number as green light!"
        if user_input.get(CONF_PIN_WHITE):
            if user_input[CONF_PIN_RED] == user_input[CONF_PIN_WHITE]:
                err[CONF_PIN_RED] = "White light uses same number as red light!"
            if user_input[CONF_PIN_GREEN] == user_input[CONF_PIN_WHITE]:
                err[CONF_PIN_GREEN] = "White light uses same number as green light!"
            if user_input[CONF_PIN_BLUE] == user_input[CONF_PIN_WHITE]:
                err[CONF_PIN_BLUE] = "White light uses same number as blue light!"
        return err

    async def async_step_ready(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Ready selecting outputs."""
        # User tells: config is ready, create entry now
        _LOGGER.info(
            "In PCA9685Config / Creaate now / config_input: %s!", str(self.config_data)
        )
        return self.async_create_entry(
            title="PCA9685 Device ("
            + self.config_data[CONF_BUS]
            + " address "
            + str(int(self.config_data[CONF_ADDR]))
            + ")",
            data=self.config_data,
        )
