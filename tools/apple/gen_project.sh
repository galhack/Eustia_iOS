#!/bin/sh
# Generate app/Eustia.xcodeproj from app/project.yml with XcodeGen.
#
#   EUSTIA_TEAM=<your team id> tools/apple/gen_project.sh
#
# Without EUSTIA_TEAM the team id is read from app/.team (one line, not in
# git) when that file exists; the Mac build needs none (it is signed ad-hoc).
# XcodeGen comes from build/tools (cached or downloaded on first use) or PATH.
#
# Environment overrides:
#   EUSTIA_TEAM         Apple Developer team id for device builds
#   EUSTIA_SWIFT_FLAGS  extra OTHER_SWIFT_FLAGS (empty by default; a restricted
#                       build sandbox uses "-disable-sandbox")
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

XG="$(command -v xcodegen || true)"
if [ -z "$XG" ]; then
	XG="$ROOT/build/tools/xcodegen/bin/xcodegen"
	if [ ! -x "$XG" ]; then
		mkdir -p "$ROOT/build/tools"
		echo "downloading XcodeGen 2.46.0 into build/tools..." >&2
		curl -sL -o "$ROOT/build/tools/xcodegen.zip" \
			https://github.com/yonaskolb/XcodeGen/releases/download/2.46.0/xcodegen.zip
		unzip -q -o "$ROOT/build/tools/xcodegen.zip" -d "$ROOT/build/tools"
	fi
fi

if [ -z "${EUSTIA_TEAM:-}" ] && [ -f "$ROOT/app/.team" ]; then
	EUSTIA_TEAM="$(tr -d ' \n' < "$ROOT/app/.team")"
fi
export EUSTIA_TEAM="${EUSTIA_TEAM:-}"
export EUSTIA_SWIFT_FLAGS="${EUSTIA_SWIFT_FLAGS:-}"

"$XG" generate --spec "$ROOT/app/project.yml" --project "$ROOT/app"
