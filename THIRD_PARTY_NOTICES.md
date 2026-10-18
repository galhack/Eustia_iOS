# Third-party components

| Component | Where | License |
|---|---|---|
| OpenBGI (Cytlan and contributors), upstream commit in `engine/UPSTREAM_COMMIT` | `engine/openbgi/` | GPL-2.0-only |
| pl_mpeg (Dominic Szablewski) | `engine/openbgi/src/os/apple/third_party/pl_mpeg.h` | MIT |
| stb_vorbis (Sean Barrett) | `engine/openbgi/src/snd/stb_vorbis.c` | Public domain / MIT |
| CompressedBG algorithm, after GARbro's `ImageCBG.cs` / `ImageCBG2.cs` (morkt) | `engine/openbgi/src/core/cbg.c`, `cbg2.c` | MIT (original); the C port is GPL-2.0 with this project |

The Apple back end (`engine/openbgi/src/os/apple/`) and the application shell
(`app/`) are part of this project and are released under GPL-2.0.

If the Enigma Virtual Box reader (`app/Sources/Native/evb.c`) is kept, it follows
the file layout documented by the `evbunpack` tool; its code and aPLib decoder
are written for this project.

## The game

No part of the game **秽翼的尤斯蒂娅** (Aiyoku no Eustia, © August) is included
in this repository: the executable, the `.arc` archives, the scripts, images,
music, voices and movies are not here, and they are never bundled into the
application or the release artifacts. You need to buy the game and use your own
files. The Chinese translation patch that a copy of the game may carry belongs
to its respective authors; this project only reads the files a player already
has and does not distribute them.
