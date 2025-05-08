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

## Configuration

During the setup, you will need to provide:
- OnStar username
- OnStar password
- Device ID (used to identify your device with OnStar)
- Vehicle VIN (Vehicle Identification Number)
- OnStar PIN (if required)
- TOTP Secret (if required for two-factor authentication)

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
- Diagnostic data is requested every 2 minutes
- Location data is requested every 2 minutes

## Future Development

This integration serves as a base to iterate upon. Future enhancements may include:
- Binary sensors for additional vehicle status information
- Additional command support as the OnStar API evolves
- UI improvements and automatic vehicle discovery