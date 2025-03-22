"""Config flow definition for PCA9685."""

import logging
from pathlib import Path
from typing import Any, ClassVar

import voluptuous as vol
from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_MODE,
    CONF_NAME,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import callback
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


class PCA9685LedSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding entities."""

    _pins: ClassVar[list[str]] = [str(i) for i in range(16)]

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> SubentryFlowResult:
        """User flow to add a new entities."""
        self._update_free_pins()

        if len(self._pins) == 0:
            return self.async_abort(reason="All pins are configured.")

        options = {}
        if len(self._pins) >= CONST_SIMPLE_LED_PINS:
            options["simple_light"] = "Simple light"
            options["number"] = "Number"
        if len(self._pins) >= CONST_RGB_LED_PINS:
            options["rgb_light"] = "RGB Light"
        if len(self._pins) >= CONST_RGBW_LED_PINS:
            options["rgbw_light"] = "RGBW Light"
        return self.async_show_menu(menu_options=options)

    def _generate_schema_simple_light(self) -> vol.Schema:
        """Generate schema for simple light."""
        pin_selector = [
            selector.SelectOptionDict(value=str(pin), label=str(pin))
            for pin in self._pins
        ]
        return vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Required(
                    CONF_PIN, default=str(self._pins[0])
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=pin_selector, mode=selector.SelectSelectorMode.DROPDOWN
                    ),
                ),
            }
        )

    def _generate_schema_number(self) -> vol.Schema:
        """Generate schema for number config."""
        return self._generate_schema_simple_light().extend(
            {
                vol.Optional(CONF_INVERT, default=False): selector.BooleanSelector(),
                vol.Optional(
                    CONF_MINIMUM, default=DEFAULT_MIN_VALUE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(
                    CONF_MAXIMUM, default=DEFAULT_MAX_VALUE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(
                    CONF_NORMALIZE_LOWER, default=DEFAULT_MIN_VALUE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(
                    CONF_NORMALIZE_UPPER, default=DEFAULT_MAX_VALUE
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_STEP, default=DEFAULT_STEP): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_MODE, default=MODE_SLIDER): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=MODE_BOX, label=MODE_BOX),
                            selector.SelectOptionDict(
                                value=MODE_SLIDER, label=MODE_SLIDER
                            ),
                            selector.SelectOptionDict(value=MODE_AUTO, label=MODE_AUTO),
                        ]
                    )
                ),
            }
        )

    def _generate_schema_rgb_light(self) -> vol.Schema:
        """Generate schema for RGB light."""
        pin_selector = [
            selector.SelectOptionDict(value=str(pin), label=str(pin))
            for pin in self._pins
        ]
        return vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Required(
                    CONF_PIN_RED, default=str(self._pins[0])
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=pin_selector, mode=selector.SelectSelectorMode.DROPDOWN
                    ),
                ),
                vol.Required(
                    CONF_PIN_GREEN, default=str(self._pins[1])
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=pin_selector, mode=selector.SelectSelectorMode.DROPDOWN
                    ),
                ),
                vol.Required(
                    CONF_PIN_BLUE, default=str(self._pins[2])
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=pin_selector, mode=selector.SelectSelectorMode.DROPDOWN
                    ),
                ),
            }
        )

    def _generate_schema_rgbw_light(self) -> vol.Schema:
        """Generate schema for RGBW light."""
        pin_selector = [
            selector.SelectOptionDict(value=str(pin), label=str(pin))
            for pin in self._pins
        ]
        return self._generate_schema_rgb_light().extend(
            {
                vol.Required(
                    CONF_PIN_WHITE, default=str(self._pins[3])
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=pin_selector, mode=selector.SelectSelectorMode.DROPDOWN
                    ),
                )
            }
        )

    def _update_free_pins(self) -> None:
        """Update list of pins that are free to use."""
        self._pins.clear()
        self._pins.extend([str(i) for i in range(16)])
        for pca in self.hass.config_entries.async_entries(DOMAIN):
            if pca.subentries and pca.entry_id == self.handler[0]:  # It's my parent PCA
                for entry in pca.subentries:
                    for pin in [
                        CONF_PIN,
                        CONF_PIN_RED,
                        CONF_PIN_GREEN,
                        CONF_PIN_BLUE,
                        CONF_PIN_WHITE,
                    ]:
                        if pca.subentries[entry].data.get(pin) is not None:
                            self._pins.remove(pca.subentries[entry].data[pin])

    def _check_pin_conflicts(self, user_input: dict[str, str]) -> dict[str, str]:
        """Check for conflicting pins."""
        err = {}
        if user_input.get(CONF_PIN) is not None:
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

    def _make_entity_title(self, user_input: dict[str, Any]) -> str:
        """Create a title for the entity."""
        title = user_input[CONF_NAME] + " @ pin "
        if user_input.get(CONF_PIN) is None:
            title += (
                user_input[CONF_PIN_RED]
                + ","
                + user_input[CONF_PIN_GREEN]
                + ","
                + user_input[CONF_PIN_BLUE]
            )
            if user_input.get(CONF_PIN_WHITE):
                title += "," + user_input[CONF_PIN_WHITE]
        else:
            title += user_input[CONF_PIN]
        return title

    async def async_step_simple_light(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a light."""
        if user_input is not None:
            user_input[CONF_TYPE] = Platform.LIGHT
            return self.async_create_entry(
                title=self._make_entity_title(user_input=user_input),
                data=user_input,
            )
        return self.async_show_form(
            step_id="simple_light", data_schema=self._generate_schema_simple_light()
        )

    async def async_step_number(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a light."""
        if user_input is not None:
            user_input[CONF_TYPE] = Platform.NUMBER
            return self.async_create_entry(
                title=self._make_entity_title(user_input=user_input),
                data=user_input,
            )

        return self.async_show_form(
            step_id="number", data_schema=self._generate_schema_number()
        )

    async def async_step_rgb_light(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a RGB light."""
        """Note that entities for RGBW lights are created with this code as well
        to keep the amount of double code minimal."""
        if user_input is not None:
            # Check for correct input
            err = self._check_pin_conflicts(user_input)

            if len(err):
                if user_input.get(CONF_PIN_WHITE):
                    schema = self._generate_schema_rgbw_light()
                else:
                    schema = self._generate_schema_rgb_light()
                return self.async_show_form(
                    step_id="rgb_light",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors=err,
                )
            user_input[CONF_TYPE] = Platform.LIGHT
            return self.async_create_entry(
                title=self._make_entity_title(user_input=user_input),
                data=user_input,
            )

        return self.async_show_form(
            step_id="rgb_light", data_schema=self._generate_schema_rgb_light()
        )

    async def async_step_rgbw_light(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> SubentryFlowResult:
        """Add a RGBW light."""
        """Note that the entity is create by async_step_rgb_light."""
        return self.async_show_form(
            step_id="rgb_light", data_schema=self._generate_schema_rgbw_light()
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Re-configure a subentry device."""
        errors = {}
        if user_input is not None:
            errors = self._check_pin_conflicts(user_input=user_input)

            if not errors:
                return self.async_update_and_abort(
                    entry=self._get_reconfigure_entry(),
                    subentry=self._get_reconfigure_subentry(),
                    data_updates=user_input,
                    title=self._make_entity_title(user_input=user_input),
                )
        self._update_free_pins()

        # Append also the current pins to the free-pins list
        # and generate entity specific schema
        data = self._get_reconfigure_subentry().data
        if data.get(CONF_PIN) is not None:
            self._pins.append(data[CONF_PIN])
            self._pins.sort(key=lambda a: int(a))
            if data[CONF_TYPE] == Platform.LIGHT:
                schema = self._generate_schema_simple_light()
            else:
                schema = self._generate_schema_number()
        else:
            self._pins.append(data[CONF_PIN_RED])
            self._pins.append(data[CONF_PIN_GREEN])
            self._pins.append(data[CONF_PIN_BLUE])
            if data.get(CONF_PIN_WHITE) is not None:
                self._pins.append(data[CONF_PIN_WHITE])
                self._pins.sort(key=lambda a: int(a))
                schema = self._generate_schema_rgbw_light()
            else:
                self._pins.sort(key=lambda a: int(a))
                schema = self._generate_schema_rgb_light()

        schema = self.add_suggested_values_to_schema(schema, data)

        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )


class PCA9685ConfigFlow(ConfigFlow, domain=DOMAIN):
    """PCA9685 device Config handler."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            # Check if the device was already configured.
            exists = False
            for pca in self.hass.config_entries.async_entries(DOMAIN):
                exists |= (pca.data[CONF_BUS] == user_input[CONF_BUS]) and (
                    pca.data[CONF_ADDR] == user_input[CONF_ADDR]
                )

            if not exists:
                return self.async_create_entry(
                    title="PCA9685 Device (address "
                    + str(int(user_input[CONF_ADDR]))
                    + " @ "
                    + user_input[CONF_BUS]
                    + ")",
                    data=user_input,
                )
            errors[CONF_ADDR] = "already_configured"

        return self.async_show_form(
            step_id="user",
            data_schema=await self._async_bus_scheme(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure the PCA9685 device."""
        errors = {}
        if user_input is not None:
            # Check if the device was already configured.
            exists = False
            for pca in self.hass.config_entries.async_entries(DOMAIN):
                exists |= (pca.data[CONF_BUS] == user_input[CONF_BUS]) and (
                    pca.data[CONF_ADDR] == user_input[CONF_ADDR]
                )

            if not exists:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )
            errors[CONF_ADDR] = "already_configured"

        schema = self.add_suggested_values_to_schema(
            await self._async_bus_scheme(), self._get_reconfigure_entry().data
        )

        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    async def _async_bus_scheme(self) -> vol.Schema:
        """Generate scheme for configuring the I2C bus."""

        def blocking_code() -> list[str]:
            return [str(bus) for bus in Path("/dev/").glob("i2c-*")]

        # First check if an I2C bus is available
        i2c_busses = await self.hass.async_add_executor_job(blocking_code)
        i2c_bus_selector = [
            selector.SelectOptionDict(value=bus, label=bus) for bus in i2c_busses
        ]
        # find out what adresses on this bus are already in use.
        # Set default to first not-used adress

        return vol.Schema(
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

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: ConfigEntry,  # noqa: ARG003
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            "add_entities": PCA9685LedSubentryFlowHandler,
        }
