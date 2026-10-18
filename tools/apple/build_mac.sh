#!/bin/sh
# Build the Mac application (Mac Catalyst), signed to run locally, and zip it.
#
#   tools/apple/build_mac.sh
#
# The result is build/Eustia-mac.zip with Eustia.app inside (and the .app
# itself in build/Eustia-mac.app); no game data goes into it.  The app is
# ad-hoc signed: on another Mac, open it the first time with right-click >
# Open (or allow it in System Settings > Privacy & Security), since it is not
# notarised.
#
# Environment overrides:
#   DEVELOPER_DIR       Xcode to use (default /Applications/Xcode.app/Contents/Developer)
#   EUSTIA_TEAM         Apple Developer team id, for an XcodeGen project run
#   EUSTIA_SWIFT_FLAGS  extra OTHER_SWIFT_FLAGS (see gen_project.sh)
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
export CLANG_MODULE_CACHE_PATH="${CLANG_MODULE_CACHE_PATH:-$ROOT/build/ModuleCache}"
mkdir -p "$CLANG_MODULE_CACHE_PATH"

"$ROOT/tools/apple/gen_project.sh" > /dev/null

LOG="$ROOT/build/mac-build.log"
mkdir -p "$ROOT/build"
if ! xcodebuild -project "$ROOT/app/Eustia.xcodeproj" -scheme Eustia -configuration Release \
	-destination 'generic/platform=macOS,variant=Mac Catalyst' -derivedDataPath "$ROOT/build/dd-mac" \
	build > "$LOG" 2>&1; then
	grep -E "error:" "$LOG" | head -20 >&2 || true
	echo "build failed; full log: $LOG" >&2
	exit 1
fi
grep -E "BUILD" "$LOG" | tail -1

BUILT="$ROOT/build/dd-mac/Build/Products/Release-maccatalyst/Eustia.app"
APP="$ROOT/build/Eustia-mac.app"
ZIP="$ROOT/build/Eustia-mac.zip"
rm -rf "$APP" "$ZIP"
ditto "$BUILT" "$APP"
ditto -c -k --keepParent "$APP" "$ZIP"
echo "wrote ${ZIP#$ROOT/} (app: ${APP#$ROOT/})"
