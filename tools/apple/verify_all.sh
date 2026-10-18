#!/bin/sh
# Clean-build the whole Apple port and cut the release packages.
#
#   tools/apple/verify_all.sh
#
# Does, in order: remove the build products and module cache, regenerate the
# Xcode project, Debug-build Mac Catalyst + iOS Simulator + visionOS
# Simulator, then cut build/Eustia-ios.ipa, build/Eustia-visionos.ipa,
# build/Eustia-mac.app and build/Eustia-mac.zip.  Fails on the first error.
# Nothing is copied into the app: the packages contain the engine and the
# shell only.
#
# Environment overrides (see README.md):
#   DEVELOPER_DIR, EUSTIA_TEAM, EUSTIA_SWIFT_FLAGS, CLANG_MODULE_CACHE_PATH
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
export CLANG_MODULE_CACHE_PATH="${CLANG_MODULE_CACHE_PATH:-$ROOT/build/ModuleCache}"

echo "== cleaning build products =="
rm -rf "$ROOT"/build/dd-* "$ROOT/build/ModuleCache" "$ROOT/build/ipa-"*
mkdir -p "$ROOT/build" "$CLANG_MODULE_CACHE_PATH"

echo "== generating project =="
"$ROOT/tools/apple/gen_project.sh"

echo "== Debug builds (Mac Catalyst, iOS Simulator, visionOS Simulator) =="
for spec in \
	"platform=macOS,variant=Mac Catalyst:mac" \
	"generic/platform=iOS Simulator:iossim" \
	"generic/platform=visionOS Simulator:visionsim"
do
	dest="${spec%:*}"
	name="${spec##*:}"
	log="$ROOT/build/verify-$name.log"
	echo "-- $name"
	if ! xcodebuild -project "$ROOT/app/Eustia.xcodeproj" -scheme Eustia -configuration Debug \
		-destination "$dest" -derivedDataPath "$ROOT/build/dd-$name" \
		build > "$log" 2>&1; then
		grep -aE "error:" "$log" | head -20 >&2 || true
		echo "FAILED: $name (log: $log)" >&2
		exit 1
	fi
	grep -a "BUILD SUCCEEDED" "$log" | tail -1
done

echo "== iOS package =="
"$ROOT/tools/apple/build_ipa.sh" ios

echo "== visionOS package =="
"$ROOT/tools/apple/build_ipa.sh" visionos

echo "== Mac package =="
"$ROOT/tools/apple/build_mac.sh"

echo "== artifacts =="
cd "$ROOT"
ls -lh build/Eustia-ios.ipa build/Eustia-visionos.ipa build/Eustia-mac.zip
shasum -a 256 build/Eustia-ios.ipa build/Eustia-visionos.ipa build/Eustia-mac.zip
