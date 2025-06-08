# Changelog

## 0.4.0

- Handle auth redirects


## 0.3.0

- Fixed incorrect kmple to MPGe conversion factor in efficiency sensors
- Added parallel execution of location and diagnostics updates to improve reliability
- Added support for battery preconditioning status and cabin preconditioning temperature sensors
- Added support for projected EV range at target charge level
- Added support for lifetime energy used sensor
- Added support for lifetime MPGe sensor
- Added support for electric economy sensor


## 0.2.2

- Completion Time Fix
- Added support for EV range sensor
- Added support for charger power level sensor
- Added support for plug voltage sensor
- Added support for plug state sensor
- Added support for charge state sensor
- Added support for battery level sensor
- Added support for odometer sensor
- Added support for tire pressure sensors


## 0.2.1

- Bumped pyonstar version


## 0.2.0

- Updated README with additional credits for OnStarJS libraries
- Fixed linting issues in bump_version.py script
- Improved code quality with specific ruff noqa rules
- Used Path.open() instead of builtin open() for file operations

## 0.1.1

HACS Support

- Added HACS manifest and configuration
- Created proper README with badges and installation instructions
- Added GitHub Actions workflows for validation
- Fixed domain consistency throughout the codebase

## 0.1.0

Initial release

- OnStar integration with basic vehicle data
- Support for vehicle location and diagnostics
