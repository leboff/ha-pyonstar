# OnStar Integration for Home Assistant

This is a simplified version of the OnStar integration for Home Assistant designed to provide essential functionality with improved stability.

## Features

The integration currently supports:

- **Sensors**:
  - Odometer (kilometers)
  - EV Battery Level (percentage) - for electric vehicles only
  - EV Charge State - for electric vehicles only
  - EV Plug State - for electric vehicles only
  - EV Plug Voltage - for electric vehicles only
  - EV Charger Power Level - for electric vehicles only
  - EV Charge Complete Time - for electric vehicles only
  - EV Last Trip Efficiency - for electric vehicles only
  - EV Lifetime Efficiency - for electric vehicles only
  - EV Range - for electric vehicles only
  - Tire Pressure (all four tires) - for all vehicles

- **Controls**:
  - Lock/Unlock doors
  - Remote Start/Stop engine

- **Device Tracking**:
  - Vehicle location (GPS coordinates)

## Installation

### Option 1: HACS (Recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance.
2. Click on HACS in the sidebar.
3. Go to "Integrations".
4. Click the three dots in the top right corner and select "Custom repositories".
5. Add this repository URL: `https://github.com/leboff/ha-pyonstar`
6. Select "Integration" as the category.
7. Click "Add".
8. Search for "OnStar" in the HACS Integrations page.
9. Click "Install".
10. Restart Home Assistant.

### Option 2: Manual Installation

1. Copy the `custom_components/ha-onstar` folder to your Home Assistant's `custom_components` directory.
2. Restart Home Assistant.

## Setting up the Integration

1. Go to Configuration > Integrations > Add Integration and search for "OnStar".
2. Follow the on-screen instructions to complete the setup.
3. During vehicle selection, you'll have the option to enable "Cheater Mode" (see below).

## Configuration

During the setup, you will need to provide:
- OnStar username
- OnStar password
- Device ID (used to identify your device with OnStar)
- Vehicle VIN (Vehicle Identification Number)
- OnStar PIN (if required)
- TOTP Secret (if required for two-factor authentication)

### Cheater Mode

The integration includes a "Cheater Mode" option that can be enabled during setup or changed later in the integration's options:

- **Standard Mode**: The integration polls the OnStar API every 30 minutes to avoid rate limiting
- **Cheater Mode**: The integration polls the OnStar API every 2 minutes
  - If rate limiting (HTTP 429) occurs, the integration will automatically:
    1. Create a new device ID
    2. Delete existing tokens
    3. Re-authenticate with OnStar
    4. Continue polling with the new identity

To change Cheater Mode setting after initial setup:
1. Go to Configuration > Integrations
2. Find your OnStar integration
3. Click on "Configure" (gear icon)
4. Toggle the "Cheater Mode" option as desired

⚠️ **Warning**: Cheater Mode is intended for testing and development purposes. Excessive use of this feature may result in account limitations imposed by OnStar. Use at your own risk.

## Technical Details

The integration processes data from the OnStar API in the following format:

```json
{
  "commandResponse": {
    "status": "success",
    "body": {
      "diagnosticResponse": [
        {
          "name": "EV BATTERY LEVEL",
          "diagnosticElement": [
            {
              "name": "EV BATTERY LEVEL",
              "value": "75.1",
              "unit": "%"
            }
          ]
        },
        {
          "name": "ODOMETER",
          "diagnosticElement": [
            {
              "name": "ODOMETER",
              "value": "1911.77",
              "unit": "KM"
            }
          ]
        }
      ]
    }
  }
}
```

The integration requests diagnostic data for:
- ODOMETER
- Tire Pressure
- Various EV-specific data (for electric vehicles)

## Notes

This integration polls the OnStar API at regular intervals:
- In standard mode: Every 30 minutes
- In cheater mode: Every 2 minutes (with automatic rate limit handling)

## Future Development

This integration serves as a base to iterate upon. Future enhancements may include:
- Binary sensors for additional vehicle status information
- Additional command support as the OnStar API evolves
- UI improvements and automatic vehicle discovery