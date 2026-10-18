# Apple builds (`tools/apple`)

One XcodeGen project, `app/Eustia.xcodeproj`, builds the application for
iPhone / iPad (iOS 17+), Apple Vision Pro (visionOS 1+) and Mac
(Mac Catalyst 14+).  The engine sources are compiled into the app
from `engine/openbgi/src`; no game data or artwork is bundled.

## Requirements

* Xcode 27 (tested 27.1) with the iOS and visionOS SDKs.
* Nothing else: XcodeGen 2.46.0 is cached in `build/tools/xcodegen` or
  downloaded there on the first run.

## Generate the project

```sh
EUSTIA_TEAM=HM588ACCT5 tools/apple/gen_project.sh
```

`EUSTIA_TEAM` is the Apple Developer team id for device builds; without it
the one-line `app/.team` file is used (git-ignored), and the Mac build needs
no team at all (it is signed ad-hoc).

## Build

Everything at once (clean Debug builds of all three destinations, then the
three packages):

```sh
tools/apple/verify_all.sh
```

Or one at a time:

```sh
# Mac Catalyst app -> build/Eustia-mac.app and build/Eustia-mac.zip
tools/apple/build_mac.sh

# unsigned IPA for Sideloadly/AltStore -> build/Eustia-ios.ipa
tools/apple/build_ipa.sh ios
# also: build/Eustia-visionos.ipa
```

The IPA is unsigned and contains only the app and the engine (a few MB):
Sideloadly signs it with the player's own Apple ID.  The Mac app is ad-hoc
signed, so on another Mac open it once with right-click > Open.

Direct Xcode builds work too:

```sh
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
xcodebuild -project app/Eustia.xcodeproj -scheme Eustia -configuration Debug \
  -destination 'platform=macOS,variant=Mac Catalyst' build
xcodebuild -project app/Eustia.xcodeproj -scheme Eustia -configuration Debug \
  -destination 'generic/platform=iOS Simulator' build
```

## Environment overrides

| Variable | Meaning |
| --- | --- |
| `EUSTIA_TEAM` | Apple Developer team id (`org.local.eustia.$EUSTIA_TEAM` is the bundle id). |
| `DEVELOPER_DIR` | Xcode to use, default `/Applications/Xcode.app/Contents/Developer`. |
| `EUSTIA_SWIFT_FLAGS` | Extra `OTHER_SWIFT_FLAGS`; empty by default.  A restricted build sandbox that cannot run the compiler's macro sandbox uses `EUSTIA_SWIFT_FLAGS="-disable-sandbox"`. |
| `CLANG_MODULE_CACHE_PATH` | Module cache; the scripts default it to `build/ModuleCache`. |

## Icons

`tools/apple/make_icons.py` draws the neutral app icon (a pale feather on a
dark night-blue gradient) from scratch with the Python standard library and
writes the iOS and visionOS asset catalogs.  It uses nothing from the
game; rerun it only when the icon should change:

```sh
python3 tools/apple/make_icons.py
```

## Runtime data

The launcher finds the game folder (`system.arc`, `sysprg.arc`, `sysgrp.arc`,
`data01000.arc`) in the app's Documents (Finder file sharing / Files app), in
`Documents/Game`, or — on the Mac — in the folder chosen with
`选择游戏目录…` (nothing is copied there).  Network transfers land in
`Documents/Game`; `python3 tools/push_data.py` sends a game folder from a Mac.
Saves and `BGI.gdb` live in `Application Support/Eustia/save`, seeded from the
game folder's `BGI.gdb` on the first run; the game data itself is never
written to.

The app passes the script encoding of the detected copy to the engine
(`AppleHostConfig_t.chinese`: GBK for the Chinese patch, Shift-JIS for the
original).  The launcher also offers a manual language switch in case a data
set has mixed or unusual scripts.

## Unattended runs and debug aids

The launcher and the engine screen understand these environment variables
(they do nothing in a normal launch):

| Variable | Meaning |
| --- | --- |
| `EUSTIA_GAME_DIR` | use this data folder instead of searching Documents (simulator/Mac runs). |
| `EUSTIA_AUTOSTART=zh\|ja` | skip the launcher and start the engine in that language. |
| `EUSTIA_SCRIPT` | input script after the engine starts: `wait S`, `move X Y`, `click X Y`, `rclick X Y`, `key VK`, `wheel D`, `shot NAME`. Screenshots and the engine's stderr go to `Documents/Debug` (or `Application Support/Eustia/Debug` on the Mac). |
| `EUSTIA_ENGINE_ARGS` | extra `Engine_Main` arguments (normally none; the engine detects the game). |

Example (simulator, game data on the host):

```sh
SIMCTL_CHILD_EUSTIA_GAME_DIR=/path/to/data \
SIMCTL_CHILD_EUSTIA_AUTOSTART=zh \
xcrun simctl launch <device> org.local.eustia.$EUSTIA_TEAM
```
