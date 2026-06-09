"""
Version constants for InfusionFox.

Calendar versioning (CalVer): YYYY.MM.DD reflects the date of the most
recent release. Bump when shipping a tagged release. The footer of the
app displays this value as a content-currency signal to clinicians,
who care more about "is this current?" than "is this v1 or v2?".
"""

# Tagged release date (CalVer). Bump on each release.
APP_VERSION = "2026.06.09"

# Public source URL. Displayed in the footer alongside the version.
SOURCE_URL = "https://github.com/infusionfox/infusionfox"

# License identifier (SPDX). Displayed alongside version in the footer.
LICENSE_SPDX = "AGPL-3.0"
