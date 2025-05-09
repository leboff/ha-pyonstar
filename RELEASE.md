# Release Process

This document outlines the process for creating new releases of the ha-onstar integration.

## Automated Release Process

Releases are now automated! Here's how to create a new release:

1. Update version and changelog:
   ```bash
   python scripts/bump_version.py [major|minor|patch]
   ```

2. Edit the generated changelog entry in `CHANGELOG.md` with the actual changes.

3. Commit the changes:
   ```bash
   git add custom_components/ha-onstar/const.py custom_components/ha-onstar/manifest.json CHANGELOG.md
   git commit -m "Bump version to x.y.z"
   ```

4. Create and push a tag:
   ```bash
   git tag -a vx.y.z -m "Release vx.y.z"
   git push origin main
   git push origin vx.y.z
   ```

5. The GitHub Actions workflow will automatically:
   - Create a GitHub release from the tag
   - Extract the changelog for that version
   - Create a zip file of the integration
   - Attach it to the release

That's it! No need to manually create releases anymore.

## Installation Instructions for Users

These installation instructions are automatically included in each release:

### HACS Installation (Recommended)

1. Add this repository as a custom repository in HACS:
   - Go to HACS in Home Assistant
   - Click on "Integrations"
   - Click the three dots in the top right and select "Custom repositories"
   - Enter the repository URL and select "Integration" as the category
   - Click "Add"

2. Install the "OnStar" integration from HACS

### Manual Installation

1. Download the `ha-onstar.zip` file from the latest release
2. Unzip the file
3. Copy the `ha-onstar` folder to your Home Assistant's `custom_components` directory
4. Restart Home Assistant
5. Add the integration through the Home Assistant UI: Configuration -> Integrations -> Add Integration -> OnStar