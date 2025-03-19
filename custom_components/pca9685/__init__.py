"""The pca9685 PWM component."""

from re import A
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import logging

from custom_components.pca9685.const import CONF_ADDR, CONF_BUS, CONF_FREQUENCY
from .pca_driver import PCA9685Driver
from .const import (
    DOMAIN,
    PCA9685_DRIVERS,
)


_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PCA9685 from a config entry."""
    _LOGGER.info(
        "Entry info from setup_entry:%s with id %s", entry.data, entry.entry_id
    )

    # Create PCA driver for this platform
    pca_driver = PCA9685Driver(
        address=entry.data[CONF_ADDR], i2c_bus=entry.data[CONF_BUS]
    )
    pca_driver.set_pwm_frequency(entry.data[CONF_FREQUENCY])

    pca9685_data = hass.data.setdefault(DOMAIN, {})
    if PCA9685_DRIVERS not in pca9685_data:
        pca9685_data[PCA9685_DRIVERS] = {}
    # XXX ToDo: check if bus & address already used in another driver?
    pca9685_data[PCA9685_DRIVERS][entry.entry_id] = pca_driver

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
