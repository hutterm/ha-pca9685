# Home Assistant PCA9685 PWM custom integration

**This is a spin-off from an original Home Assistant integration which was removed in Home Assistant Core 2022.4. The original rpi_gpi_pwm was stored [here](https://github.com/RedMeKool/HA-Raspberry-pi-GPIO-PWM/) but due to changes in 2022.7.5 support for pca9685 PWM devices was dropped. This module brings back  support for the pca9685 PWM LED driver in a separate component. As of Home Assitant version 2024.10.4 we also implemented an own driver to prevent upgrading users from dependency issues.**

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

[![Discord][discord-shield]][discord]
[![Community Forum][forum-shield]][forum]

**Description.**

The pca9685 component allows to control multiple lights using pulse-width modulation, for example LED strips. It supports one-color, RGB and RGBW LEDs driven by pca9685 devices. A PWM output can also be configured as a number. Connection to the pca9685 devices is made via the I2C bus.

For more details about the pca9685 I2C PWM LED controller you can find the datasheets here:
- [PCA9685](https://www.nxp.com/docs/en/data-sheet/PCA9685.pdf)

**This integration can set up the following platforms.**

Platform | Description
-- | --
`light` | Write LED signal to digital PWM outputs.
`number` | Writes signal represented by a number to PWM outputs.




### HACS (Preferred)
1. [Add](http://homeassistant.local:8123/hacs/integrations) the custom integration repository: https://github.com/domectrl/ha-pca9685
2. Select `PCA9685` in the Integration tab and click `download`
3. Restart Home Assistant
4. Done!

### Manual
1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `pca9685`.
1. Download _all_ the files from the `custom_components//` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Restart Home Assistant

## Configuration via user interface:
* In the user interface go to "Configuration" -> "Integrations" click "+" and search for "PCA9685"
* For a description of the configuration parameters, see Configuration parameters

## YAML Configuration

This integration can no longer be configured via YAML. Use the config flow function instead. 
### Configuration parameters

***Generic settings:***
- I2C bus: Select the I2C bus where the PCA9685 is connected. Use tools like i2cdetect to find the right bus.
  > default: first bus found in the system
- I2C address: I2C address of the LED driver
  > default: 0x40 (decimal 64)
- frequency: The PWM frequency. 
  > default: 200 Hz

***Choosing entities:***
In the next menu, one can choose what entities to add. The possible entities shown depend on the amount of pins left without a function. If all pins are occupied, or if the user presses the 'Finish' button, the integration will be added.

***Light specific settings:***
- name: Name of the Light to create.
  > default: empty 
- pin(s): Select the pins to be used for your entity. 
  Note that the numbering of the pins starts from 0 up to 15. Only the pins not yet occupied by other entities can be selected.
  > default: first / next pin available

***number specific settings:***
- name: Name of the Number to create.
  > default: empty 
- pin: The pin connected to the number. Numbering starts from 0 up to 15.
  > default: first / next pin available
- invert: Invert signal of the PWM generator
  > default: false
- minimum: Minimal value of the number.
  > default: 0
- maximum: Maximal value of the number. 
  > default: 100
- normalize_lower: Lower value to normalize the output of the PWM signal on. 
  > default: 0
- normalize_upper: Upper value to normalize the output of the PWM output on.
  > default: 100

These last four parameters might require a little more explanation:
- The minimum/maximum define the range one can select on this number, for example 0..100%.
- The 'normalize' parameters define at what range the output of the PWM normalizes. The PCA9685 registers can be programmed with a range of 0..4095. In normal cases, the the output register of the PCA9685 is set to 0 for value 0, and 4095 for value 100. If the normalize value is for example to 10..60, it will set the register value 0 for each value <10. Above 10, it will start raising the register, up to 4095 for value 60. Above 60, the register value will remain 4095.
- Using a negative value for the normalize_lower parameter, will clip the output to the register. This way, someone can assure that the value of the register will be always for larger than, for example, 10%. Using a larger-than-maximum value will clip the output to the register on the upper side.

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

***

[commits-shield]: https://img.shields.io/github/commit-activity/y/domectrl/ha-pca9685.svg?style=for-the-badge
[commits]: https://github.com/domectrl/ha-pca9685/commits/main
[hacs]: https://hacs.xyz/
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/domectrl/ha-pca9685.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-domectrl-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/domectrl/ha-pca9685.svg?style=for-the-badge
[releases]: https://github.com/domectrl/ha-pca9685/releases
