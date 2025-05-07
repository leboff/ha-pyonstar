# OnStar Integration for Home Assistant

This is a simplified version of the OnStar integration for Home Assistant designed to provide essential functionality with improved stability.

## Features

The integration currently supports:

- **Sensors**:
  - Odometer (kilometers)
  - EV Battery Level (percentage) - for electric vehicles only

- **Controls**:
  - Lock/Unlock doors

## Installation

1. Copy this custom component to your Home Assistant's `custom_components` folder.
2. Restart Home Assistant.
3. Go to Configuration > Integrations > Add Integration and search for "OnStar".
4. Follow the on-screen instructions to complete the setup.

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
- EV BATTERY LEVEL (for electric vehicles)

## Notes

This is a simplified version of the OnStar integration, focusing on stability and core functionality. Binary sensors and additional sensors have been removed to improve reliability.

## Future Development

This simplified version serves as a base to iterate upon. Future enhancements may include:
- Adding back binary sensors once data retrieval is confirmed to be stable
- Adding additional sensor types as needed
- Improving command reliability and response handling