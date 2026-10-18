# Aiyoku no Eustia (BGI/Ethornell 1.520.6) — engine port notes

This document records what `engine/openbgi` (OpenBGI + the Apple back end)
needs beyond upstream to run 秽翼的尤斯蒂娅 / Aiyoku no Eustia, the Chinese
patch (GBK) data of this release, and the state of the verification.  The
reverse-engineering evidence is in `docs/RE-1520.md` and
`docs/RE-1520-OPCODES.md` (produced by the re-analyst teammate) and is not
repeated here.

## Build and test

```
cd engine/openbgi
make PLATFORM=apple CC=clang VORBIS=stb -j8 bin/openbgi-hosttest
BGI_TEST_TMP=/tmp ./bin/test_games        # profiles, games.json, 1.520 entry
BGI_TEST_TMP=/tmp ./bin/test_scriptenc    # the GBK / Shift-JIS detector
make PLATFORM=apple CC=clang VORBIS=stb -j8 test   # all bin/test_*; every one passes
```

Headless run (the Apple host, a scripted pointer, PNG screenshots):

```
bin/openbgi-hosttest GAME_DIR --save=/tmp/save1 --seconds=40 \
  --script="wait 20 click 640 330 wait 8 shot /tmp/title.png"
```

`GAME_DIR` must not be `data/` itself: the engine's game directory is where
`UserData\` and `BGI.gdb` are read and written, so point the host at a
symlink tree with its own `--save` directory (this is how all runs below
were made: `/tmp/game-test*`).  The engine never writes into the game
directory under the Apple host (see "games.json" below).

## What changed against upstream

| file | change |
|---|---|
| `inc/bgi/version.h`, `src/core/version.c`, `src/vm/opset.c` | the `GEN_1_520` generation and its profile |
| `src/vm/ops_snd.c`, `src/vm/ops_base.c`, `src/asm/opnames.c`, `src/asm/opstack.c` | `A0 23` `se_load_ex2`, main `77` `watch_value`, main `7C` `debug_select` |
| `inc/bgi/scriptenc.h`, `src/core/scriptenc.c` | the script text encoding detector |
| `inc/bgi/strutil.h`, `src/core/strutil.c`, `src/gfx/text/layout_h.c` | `TEXT_GBK`: GBK character boundaries, letters, spacing, kinsoku |
| `src/vm/ops_base.c` | `6C` decodes in the current text encoding (not blindly Shift-JIS) |
| `inc/bgi/apple_host.h`, `src/os/apple/host.c` | the encoding plumbing (`scriptEncoding`, auto-detection), no `games.json` write, real argv0 |
| `src/os/apple/font.c` | GBK two-byte decoding of font codes, Heiti-family Chinese faces with a glyph cascade, GBK message-box text |
| `src/sys/engine.c` | `BGI_NO_GAMES_JSON` keeps the default games.json from being written |
| `tools/apple/hosttest.c` | `--sjis`, `--movie` reads PackFile archives too |
| `Makefile` | `LIB_OBJ` no longer contains the host's `main` (the tests link again on `PLATFORM=apple`) |
| `tests/games.c`, `tests/scriptenc.c` | the new invariants below |

## GEN_1_520

The shipped `data/BGI.exe` is Alpha-ROM packed, so its opcode table cannot be
dumped.  The proxy row is the 1.529 set:

* every opcode the shipped programs (original and patched `system.arc` /
  `sysprg.arc`) use is defined by the 1.529 row;
* the *original* 1.520.6 `ipl._bp` itself uses `81 60` set_size_entry and
  `90 06` set_proj_centre, which the survey records from 1.529 on;
* (The `BGIError.txt` found in some installs is a different failure: a run
  that died registering `system.arc : sse990000` with `A0 20` under
  Wine/CrossOver, i.e. a sound-bank problem, not an undefined instruction.)

`GEN_1_520` is placed **after** `GEN_1_529` in `EngineGen_t` on purpose: all
range and `gen >= GEN_1_529` behaviour gates then cover it, which is what the
data needs, while the profile keeps its own name and parameters
(`{"1.520", GEN_1_520, 169, LAYOUT_C, BOOT_B}`).  `src/vm/opset.c` was
edited once by hand for this (bit 8 = old bit 7, old bits 8..22 shifted up);
`tests/games.c` checks the invariant (every family/opcode has
`bit(1.520) == bit(1.529)`).

The game requests `sys81.set_size_entry(7, 1280, 960)` and then
`sys.set_display_mode(6, 1, 0)`; entry 6 is 1280×720 in the 1.494+ size table
and is the windowed mode, entry 7 is only the 4:3/fullscreen fallback.  The
game is natively **1280×720** (every background/UI CBG is 1280×720; the
movies and some CGs are 1280×960 and are shown letter-boxed).  Do not
"fix" the 1280×720 client: app input coordinates are client pixels.

## The VM layout: LAYOUT_C (this contradicts the first RE reading)

`docs/RE-1520.md` reads the `push_i32` constants of the shipped programs as
`tag 8 << 25` / `tag 0xA << 25` pointers and suggests `LAYOUT_B`.  The
runtime says otherwise, and the save path is the test:

* config screens: layout B and C render **byte-identical** screenshots
  (`/tmp/ab_sysB.png` = `/tmp/ab_sysC.png`, md5
  `d3a64f1c93310fedf995e3d78ed479b5`); the title, first scene and prologue
  are identical too, so the constants are not exercised there (most
  likely they are sizes — 0x10000000 = 256 MB — not pointers);
* save path: with `LAYOUT_B`, opening SAVE fails at once —
  `userdata._bp` IP `$102E`, `80 9D` ring_get, "Attempted to access an
  invalid pointer [ $2800D668 ]".  With `LAYOUT_C`, saving slot 1 writes
  `UserData/AiyokunoEustia000.sud` and the slot shows its thumbnail, date and
  comment (`/tmp/cp_s2.png`), and a later run loads it (`/tmp/L1.png`,
  `/tmp/loaded.png`).

`userdata._bp` also settles the heap limit: it allocates
`(500 + 1) * 0x162D4 = 45,508,836` bytes with `80 20` for the save buffer,
so a 32 MB limit is a script error; `LAYOUT_C`'s 64 MB is required.  The
1.520 profile is therefore `LAYOUT_C`, like 1.529.

## Opcodes

`docs/RE-1520-OPCODES.md` shows that of the 23 opcodes the 1.529 profile
defines without a handler, only two are referenced by the game's programs:

* `A0 23` (`snd.0x23`) — `scrsnd._bp`; a twin of `A0 21` se_load_ex
  (the 1.647 proxy handler differs only in one field the loader ignores).
  Implemented as `Opcode_Snd_SeLoadEx2` and named `se_load_ex2`.
* main `77` — `dbgmngr._bp` (debug overlay only); an engine-statistics
  accessor.  Implemented as `Opcode_WatchValue`, pushes 0.
* main `7C` — referenced by nothing; the original's developer event-selector
  dialog.  Implemented as `Opcode_DebugSelect`, pushes 0, for completeness.

`--list-missing` under the 1.520 profile is down from 23 to 20; the rest are
opcode-set completeness items that no shipped program executes.

## GBK text

The Chinese patch replaces the compiled scripts and stores **plain GBK** in
the same `BurikoCompiledScriptVer1.00` containers.  Two things are needed:

1. **Detection** (`inc/bgi/scriptenc.h`): sample `data01000.arc`.  A patch
   archive stores the text plainly, so the bytes after the first
   `BurikoCompiledScriptVer1.00` marker are classified by their punctuation
   (`A1B8 A1B9 A1A2 A1A3` = GBK `「」、。` vs `8175 8176 8141 8142` = the
   Shift-JIS forms, plus kana).  The original release stores the scripts
   DSC-compressed, so when no plain marker is found the first entries are
   decoded through `ArcRead` and sampled; that is how the original data is
   recognized as Shift-JIS.
2. **Character boundaries** (`TEXT_GBK` in `src/core/strutil.c`): the
   engine's text layer split strings with Shift-JIS rules, which treats GBK
   leads 0xA1..0xDF (most common hanzi) as half-width katakana.  The Apple
   host calls `Text_SetEncoding(TEXT_GBK)` when the scripts are GBK; the
   splitter, `6C` getchar, the ideographic space, kinsoku (with a GBK
   punctuation set) and the font-code byte strings then all use GBK's rules.
   The Apple font back end decodes the two-byte codes through the system's
   GBK table and prints them with a Heiti-family face (PingFang SC, then
   STHeiti SC / Hiragino Sans GB with a Core Text cascade list).  There is
   no `font.ttf` in this patch.

Verified both ways: `/tmp/gbk_scene2.png` (CN, "艾莉斯递过来的布包中，装着
尚温的鸡肉香草派。") and `/tmp/jp_scene.png` (a tree built from
`data/Original_file`: "あらゆるものが不条理に彩られている。").

## Apple host API

`inc/bgi/apple_host.h` grew one field and one getter; existing names and
signatures are unchanged:

```c
enum {
    APPLE_HOST_ENCODING_AUTO = 0, // detect from data01000.arc
    APPLE_HOST_ENCODING_SJIS = 1, // force the original
    APPLE_HOST_ENCODING_GBK  = 2  // force the Chinese patch
};
typedef struct AppleHostConfig {
    ...
    int chinese;        // nonzero: force GBK (legacy switch, tests)
    ...
    int scriptEncoding; // APPLE_HOST_ENCODING_*; AUTO is what an app wants
} AppleHostConfig_t;

int AppleHost_ScriptEncoding(void); // SJIS/GBK actually in use, AUTO before start
```

With `scriptEncoding = APPLE_HOST_ENCODING_AUTO` and `chinese = 0` the host
samples the game and logs `bgi: script text is GBK, the Chinese patch
(detected)` (or Shift-JIS).  An unreadable/ambiguous sample stays Shift-JIS.
The launcher can stop guessing in Swift and just show
`AppleHost_ScriptEncoding()`.

## games.json and the read-only game directory

The engine knows the game by itself now: `kDefaultGames` contains
`{"AiyokunoEustia", "1.520", "AiyokunoEustia_Product"}` (the product name is
what the boot program's anti-tamper `80 E8` + streq checks, and what names
`UserData\`).  With no `games.json` anywhere, detection still works:
`bgi: engine profile 1.520 selected for this game` with a read-only game
directory (verified with `chmod 555`, `/tmp/ro_title.png`).

The Apple host also keeps the engine from writing the default `games.json`
into the game directory: `BGI_NO_GAMES_JSON=1` is set before
`Engine_Main` (`src/sys/engine.c` honours it) and `OS_SetArgv0` now gets the
real executable path so the "beside the binary" probe cannot fall back to
the game directory (it used to, because the current directory is the game
directory).  `data/` stays untouched by app runs.

## Verified evidence (macOS host)

| what | screenshot / log |
|---|---|
| title, built-in detection, no games.json | `/tmp/builtin1.png` |
| prologue (GBK auto), first real scene with sprites and Chinese dialogue | `/tmp/auto_scene.png`, `/tmp/gbk_scene2.png` |
| original Japanese data (Shift-JIS auto) | `/tmp/jp_scene.png` |
| read-only game directory | `/tmp/ro_title.png` |
| config screens (layout B == C) | `/tmp/ab_cfgB.png`, `/tmp/ab_sysB.png`, `/tmp/ab_sysC.png` |
| save slot written | `/tmp/cp_s2.png` (`/tmp/saveC_pristine/UserData/AiyokunoEustia000.sud`) |
| load menu reads the save back | `/tmp/L1.png` |
| loaded game state | `/tmp/loaded.png` |
| movie (MPEG-1 in `data02840.arc`) | `/tmp/movietest/movie2.png` |
| long click-through, no "undefined"/"not implemented" | `/tmp/long1.png`, `/tmp/long.log` |
| lead's independent validation: dialog, save, cross-session load, audio | `/tmp/v_dialog.png`, `/tmp/w_savedone.png`, `/tmp/y_loaded.png` |

Movie note: `data02840.arc` holds the 8 MPEG-1 movies (the OP is
`movie.mpg`, 1280×720, 128 s; the game archives store MPEG-1, not BF_Movie).
`hosttest --movie=data02840.arc:movie.mpg --seconds=4` decodes it through
the back end's player and writes `movieN.png` (`/tmp/movietest/movie2.png`).
The standalone test used to hand the player a hardcoded 1280×960 rectangle,
which squashed a 1280×720 stream; it now takes `--size=WxH`, default
1280×720, matching the game's client mode (`bgi: movie ... 1280 x 720`).
In the game the script chooses the rectangle with the display mode, which
is what the `set_size_entry(7, 1280, 960)` call is for.

## Known remaining gaps

* 20 profile-defined opcodes still have no handler; none is referenced by the
  shipped programs (`docs/RE-1520-OPCODES.md` lists them, with 1.647 proxy
  handler addresses, for completeness).
* Child windows (`B0 1x`) and the text-entry objects (`B0 2x`) do not exist
  in the Apple back end; the screens that need them (input dialogs) fall
  back to the engine's "could not create" path.  The config, save/load,
  backlog and message screens used by this game do not need them.
* The full 4:3/fullscreen path (`set_size_entry(7)`, display mode 7,
  letter-boxing) was not exercised here — the app shell should test it on
  iPad/visionOS.
* A complete playthrough has not been done; the verified stretch is the cold
  open, the first dialogue scene, config screens, save and load.
* Fresh-launch title menu: with saves already in the save directory, a fresh
  process still shows only START / CONFIGURATION / EXIT; CONTINUE and DATA
  LOAD appear only in the same session after saving and returning to the
  title.  In-game LOAD works either way and lists the saves correctly, so
  this is only the title's "save exists" flag (`title._bp` calls into
  `userdata._bp` at startup for it); not investigated further.  The app
  shell's launcher can offer "continue" itself (it can see the save dir).
