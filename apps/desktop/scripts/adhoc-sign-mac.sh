#!/usr/bin/env bash
# Ad-hoc signs a packaged .app so macOS will open it.
#
#   apps/desktop/scripts/adhoc-sign-mac.sh "release/mac-arm64/Resume Builder.app"
#
# Electron ships with a linker-signed ad-hoc signature over its own binary.
# Packaging replaces the Info.plist, adds an asar and copies the API and TeX
# into Resources, none of which that signature covers — so the bundle arrives
# with a signature that no longer describes it. Gatekeeper does not report that
# as an unsigned app; it reports "damaged and can't be opened", and the
# right-click-to-Open escape hatch does not apply. Re-sealing the bundle here
# turns that back into the ordinary unidentified-developer prompt.
#
# This runs as its own step rather than an electron-builder hook. afterPack
# fires *before* electron-builder flips Electron's fuses, and flipping a fuse
# rewrites the binary and invalidates whatever signature the hook just made.
# afterSign never fires at all when no identity is found. So the app is built
# with --dir, signed here, and handed back with --prepackaged.
set -euo pipefail

app="${1:?usage: adhoc-sign-mac.sh <path to .app>}"

if [ ! -d "$app" ]; then
	echo "No app bundle at $app" >&2
	exit 1
fi

# --deep is deprecated for real signing identities, where each nested binary
# wants its own explicit pass. For an ad-hoc seal that we are not notarising it
# is still the one command that covers the Frameworks, the helper apps and the
# sidecars under Resources in the right order.
codesign --force --deep --sign - "$app"

# A broken seal is the whole bug, so prove the new one holds rather than
# trusting that codesign exited zero.
codesign --verify --deep --strict --verbose=2 "$app"

echo "Ad-hoc signed $app"
