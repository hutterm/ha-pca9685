"""Driver code for PCA9685 LED driver."""

import logging
import re
from pathlib import Path
from types import MappingProxyType
from .const import CONST_PWM_FREQ_MIN, CONST_PWM_FREQ_MAX
from smbus3 import SMBus

_LOGGER = logging.getLogger(__name__)

SIMULATE = True


class PCA9685Error(Exception):
    """Something goes wrong with the pca9685 driver."""


class Registers:
    """Registers of the pca9685."""

    MODE_1 = 0x00
    MODE_2 = 0x01
    LED_STRIP_START = 0x06  # LED0 ON Low Byte
    PRE_SCALE = 0xFE


class Mode1:
    """Mode of use 1."""

    RESTART = 7
    EXTCLK = 6
    AI = 5
    SLEEP = 4
    SUB1 = 3
    SUB2 = 2
    SUB3 = 1
    ALLCALL = 0


class Mode2:
    """Mode of use 2."""

    INVRT = 4
    OCH = 3
    OUTDRV = 2
    OUTNE_1 = 1
    OUTNE_0 = 0


def value_low(val: int) -> int:
    """Value of lower byte."""
    return val & 0xFF


def value_high(val: int) -> int:
    """Value of higher byte."""
    return (val >> 8) & 0xFF


class PCA9685Driver:
    """Device class controlling the PCA9685."""

    ranges = MappingProxyType(
        {
            "pwm_frequency": (CONST_PWM_FREQ_MIN, CONST_PWM_FREQ_MAX),
            "led_number": (0, 15),
            "led_value": (0, 4095),
            "register_value": (0, 255),
        }
    )

    def __init__(self, address: int, i2c_bus: SMBus | int | None = None) -> None:
        """
        Create the PCA9685 driver.

        :param address: I2C address of the device. Check with `i2cdetect -y 1`
        :param i2c_bus: SMBus to use or number of the I2C bus in the linux machine.
                        See /dev/i2c-*. Use None to autodetect the first available.
        """
        if not SIMULATE:
            if i2c_bus is None:
                bus_list = self.get_i2c_bus_numbers()
                if len(bus_list) < 1:
                    msg = "Cannot determine I2C bus number"
                    raise PCA9685Error(msg)
                i2c_bus = SMBus(bus_list[0])
            if isinstance(i2c_bus, int | str):
                i2c_bus = SMBus(i2c_bus)
            self.__bus: SMBus = i2c_bus

        self.__address: int = address
        self.__oscillator_clock = 25000000

    @staticmethod
    def get_i2c_bus_numbers() -> list[int]:
        """Search all the available I2C busses in the system."""
        res = []
        for bus in Path("/dev/").glob("i2c-*"):
            r = re.match(r"/dev/i2c-([\\d]){1,2}", str(bus))
            if r:
                res.append(int(r.group(1)))
        return res

    @property
    def mode_1(self) -> int:
        """Returns the Mode 1 register value."""
        return self.read(Registers.MODE_1)

    @property
    def bus(self) -> SMBus:
        """Returns the bus instance."""
        return self.__bus

    def get_led_register_from_name(self, name: str) -> int:
        """
        Parse the name for led number.

        :param name: attribute name, like: led_1
        """
        res = re.match("^led_([0-9]{1,2})$", name)
        if res is None:
            msg = f"Unknown attribute: '{name}'"
            raise AttributeError(msg)
        led_num = int(res.group(1))
        self.__check_range("led_number", led_num)
        return self.calc_led_register(led_num)

    def calc_led_register(self, led_num: int) -> int:
        """
        Calculate register number for LED pin.

        :param led_num: the led number, typically 0-15
        """
        start = Registers.LED_STRIP_START + 2
        return start + (led_num * 4)

    def __check_range(self, option: str, value: int) -> None:
        r = self.ranges[option]
        if value < r[0]:
            msg = f"{option} must be greater than {r[0]}, got {value}"
            raise PCA9685Error(msg)
        if value > r[1]:
            msg = f"{option} must be less than {r[1]}, got {value}"
            raise PCA9685Error(msg)

    def set_pwm(self, led_num: int, value: int) -> None:
        """
        Set PWM value for the specified LED.

        :param led_num: LED number (0-15)
        :param value: the 12 bit value (0-4095)
        """
        self.__check_range("led_number", led_num)
        self.__check_range("led_value", value)

        register_low = self.calc_led_register(led_num)
        self.write(register_low, value_low(value))
        self.write(register_low + 1, value_high(value))

    def __get_led_value(self, register_low: int) -> int:
        low = self.read(register_low)
        high = self.read(register_low + 1)
        return low + (high * 256)

    def get_pwm(self, led_num: int) -> int:
        """Get LED PWM value."""
        self.__check_range("led_number", led_num)
        register_low = self.calc_led_register(led_num)
        return self.__get_led_value(register_low)

    def sleep(self) -> None:
        """Send the controller to sleep."""
        _LOGGER.debug("Sleep the controller")
        self.write(Registers.MODE_1, self.mode_1 | (1 << Mode1.SLEEP))

    def wake(self) -> None:
        """Wake up the controller."""
        _LOGGER.debug("Wake up the controller")
        self.write(Registers.MODE_1, self.mode_1 & (255 - (1 << Mode1.SLEEP)))

    def write(self, reg: int, value: int) -> None:
        """
        Write raw byte value to the specified register.

        :param reg: the register number (0-69, 250-255)
        :param value: byte value
        """
        # TODO(antonv): check reg: 0-69, 250-255  # noqa: FIX002, TD003
        self.__check_range("register_value", value)
        _LOGGER.debug("Write %d to register %d", value, reg)
        if not SIMULATE:
            self.__bus.write_byte_data(self.__address, reg, value)

    def read(self, reg: int) -> int:
        """
        Read data from register.

        :param reg: the register number (0-69, 250-255)
        """
        if SIMULATE:
            return 0
        return self.__bus.read_byte_data(self.__address, reg)

    def calc_pre_scale(self, frequency: int) -> int:
        """
        Calculate the controller's PRE_SCALE value.

        Value accoring to PCA9685 datasheet.

        :param frequency: source frequency value in Hz
        """
        return int(round(self.__oscillator_clock / (4096.0 * frequency)) - 1)

    def set_pwm_frequency(self, value: int) -> None:
        """
        Set the frequency for all PWM output.

        :param value: the frequency in Hz
        """
        self.__check_range("pwm_frequency", value)
        reg_val = self.calc_pre_scale(value)
        _LOGGER.debug("Calculated prescale value is %d", reg_val)
        self.sleep()
        self.write(Registers.PRE_SCALE, reg_val)
        self.wake()

    def calc_frequency(self, prescale: int) -> int:
        """
        Calculate the frequency by the controller's prescale.

        Values like specified by the PCA9685 datasheet.

        :param prescale: the prescale value of the controller
        """
        return int(round(self.__oscillator_clock / ((prescale + 1) * 4096.0)))

    def get_pwm_frequency(self) -> int:
        """Get the frequency for PWM output."""
        return self.calc_frequency(self.read(Registers.PRE_SCALE))
