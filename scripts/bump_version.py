#!/usr/bin/env python3
# ruff: noqa: T201
"""Script to bump the current version."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONST_FILE = ROOT / "custom_components" / "ha-onstar" / "const.py"
MANIFEST_FILE = ROOT / "custom_components" / "ha-onstar" / "manifest.json"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"
EXPECTED_ARG_COUNT = 2


def bump_version(version_type: str) -> int:
    """Bump version based on version_type (major, minor, patch)."""
    # Read current version from const.py
    const_content = CONST_FILE.read_text()
    version_match = re.search(r'VERSION = "([0-9\.]+)"', const_content)
    if not version_match:
        print("Error: Could not find version in const.py")
        return 1

    current_version = version_match.group(1)
    major, minor, patch = map(int, current_version.split("."))

    # Bump version
    if version_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif version_type == "minor":
        minor += 1
        patch = 0
    elif version_type == "patch":
        patch += 1
    else:
        print(f"Invalid version type: {version_type}. Use 'major', 'minor', or 'patch'")
        return 1

    new_version = f"{major}.{minor}.{patch}"
    print(f"Bumping version from {current_version} to {new_version}")

    # Update version in const.py
    new_const_content = re.sub(
        r'VERSION = "([0-9\.]+)"', f'VERSION = "{new_version}"', const_content
    )
    CONST_FILE.write_text(new_const_content)

    # Update version in manifest.json
    with Path.open(MANIFEST_FILE) as f:
        manifest = json.load(f)

    manifest["version"] = new_version

    with Path.open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    # Update CHANGELOG.md
    changelog_content = CHANGELOG_FILE.read_text()
    new_changelog_entry = f"\n## {new_version}\n\n_Changes go here_\n\n"
    new_changelog_content = changelog_content.replace(
        "# Changelog\n", f"# Changelog\n{new_changelog_entry}"
    )
    CHANGELOG_FILE.write_text(new_changelog_content)

    print(f"Version bumped to {new_version}")
    print("Don't forget to update the changelog entry!")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != EXPECTED_ARG_COUNT or sys.argv[1] not in [
        "major",
        "minor",
        "patch",
    ]:
        print("Usage: python bump_version.py [major|minor|patch]")
        sys.exit(1)

    sys.exit(bump_version(sys.argv[1]))
