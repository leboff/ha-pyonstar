# OnStar Integration for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

![OnStar Logo](/onstar_logo.png)

This integration provides connectivity to the OnStar API for General Motors vehicles in Home Assistant.

## Features

- View vehicle location on a map
- Track vehicle diagnostics (tire pressure, fuel economy, battery level, etc.)

## Installation

### HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed.
2. Click on HACS in the sidebar.
3. Click on Integrations.
4. Click the three dots in the top right and select "Custom repositories."
5. Enter the repository URL and select "Integration" as the category.
6. Click "Add."
7. Search for "OnStar" in HACS and install it.

### Manual Installation

1. Download the latest `ha-onstar.zip` file from the [releases page][releases].
2. Extract the zip file.
3. Copy the `ha-onstar` folder to your Home Assistant's `custom_components` directory.
4. Restart Home Assistant.

## Configuration

1. In the Home Assistant UI, go to Configuration -> Integrations.
2. Click the "+" button to add a new integration.
3. Search for "OnStar" and select it.
4. Follow the configuration steps to add your OnStar account and vehicle.


## Credits


Special thanks to:
- [BigThunderSR/OnStarJS](https://github.com/BigThunderSR/OnStarJS) - NodeJS Library for making OnStar API requests
- [samrum/OnStarJS](https://github.com/samrum/OnStarJS) - Original OnStarJS library

---

[releases]: https://github.com/leboff/ha-pyonstar/releases
[releases-shield]: https://img.shields.io/github/release/leboff/ha-pyonstar.svg?style=for-the-badge
[commits]: https://github.com/leboff/ha-pyonstar/commits/main
[commits-shield]: https://img.shields.io/github/commit-activity/y/leboff/ha-pyonstar.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/leboff/ha-pyonstar.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-@leboff-blue.svg?style=for-the-badge
[user_profile]: https://github.com/leboff
[hacs]: https://github.com/custom-components/hacs
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/leboff
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge