#!/bin/sh
# Build an unsigned .ipa for Sideloadly / AltStore, which sign it with your
# own Apple ID when they install it.
#
#   tools/apple/build_ipa.sh [ios|visionos]     (default ios)
#
# The result is build/Eustia-<platform>.ipa (a few MB: the app and the engine,
# no game data).  Signing is left to Sideloadly, so no team id is needed here.
#
# Environment overrides:
#   DEVELOPER_DIR       Xcode to use (default /Applications/Xcode.app/Contents/Developer)
#   EUSTIA_TEAM         Apple Developer team id, for an XcodeGen project run
#   EUSTIA_SWIFT_FLAGS  extra OTHER_SWIFT_FLAGS (see gen_project.sh)
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLATFORM="${1:-ios}"
case "$PLATFORM" in
	ios) DEST="generic/platform=iOS"; PRODUCTS="Release-iphoneos" ;;
	visionos) DEST="generic/platform=visionOS"; PRODUCTS="Release-xros" ;;
	*) echo "usage: $0 [ios|visionos]" >&2; exit 2 ;;
esac
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
export CLANG_MODULE_CACHE_PATH="${CLANG_MODULE_CACHE_PATH:-$ROOT/build/ModuleCache}"
mkdir -p "$CLANG_MODULE_CACHE_PATH"

"$ROOT/tools/apple/gen_project.sh" > /dev/null

LOG="$ROOT/build/ipa-$PLATFORM-build.log"
mkdir -p "$ROOT/build"
if ! xcodebuild -project "$ROOT/app/Eustia.xcodeproj" -scheme Eustia -configuration Release \
	-destination "$DEST" -derivedDataPath "$ROOT/build/dd-ipa" \
	CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY= build > "$LOG" 2>&1; then
	grep -E "error:" "$LOG" | head -20 >&2 || true
	echo "build failed; full log: $LOG" >&2
	exit 1
fi
grep -E "BUILD" "$LOG" | tail -1

STAGE="$ROOT/build/ipa-$PLATFORM"
rm -rf "$STAGE"
mkdir -p "$STAGE/Payload"
cp -R "$ROOT/build/dd-ipa/Build/Products/$PRODUCTS/Eustia.app" "$STAGE/Payload/"
OUT="$ROOT/build/Eustia-$PLATFORM.ipa"
rm -f "$OUT"
(cd "$STAGE" && zip -qry "$OUT" Payload)
echo "wrote ${OUT#$ROOT/}"
