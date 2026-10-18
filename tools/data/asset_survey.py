#!/usr/bin/env python3
"""Asset survey of a BGI/Ethornell game's data directory.

Reads only the index and the first bytes of every archive entry (plus, for
DSC-compressed entries, enough of the stream to decode a short prefix), so
it runs over a multi-GB installation in a few seconds.  Reports:

  * the picture containers actually used: CompressedBG version 1 / 2 and
    the resolution / bpp histogram (the task's "is every image v1?"),
  * the audio containers (BW) by codec / rate / channels, and the loop
    flags of the music (head/loop pairs),
  * movie candidates: BF_Movie frame sequences and MPEG-1 program streams,
    both as archive entries and as loose .dat files,
  * the other entry kinds (scenario, ._bp programs, nested archives).

Usage: python3 tools/data/asset_survey.py GAME_DATA_DIR [--json OUT]
"""
import argparse
import collections
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arc  # noqa: E402

CBG_MAGIC = b"CompressedBG___\0"
BW_MAGIC = b"bw  "
BFMOVIE_MAGIC = b"BF_Movie_______\0"
SCN_MAGIC = b"BurikoCompiledScriptVer1.00"
MPEG_PACK = b"\0\0\1\xba"


def bw_fields(h):
    """BwHeader_t (inc/bgi/snd/bw.h) at offset 0 of `h`, or None."""
    if len(h) < 0x40 or h[4:8] != BW_MAGIC:
        return None
    return {
        "headerSize": struct.unpack_from("<I", h, 0)[0],
        "dataSize": struct.unpack_from("<I", h, 8)[0],
        "frames": struct.unpack_from("<I", h, 12)[0],
        "rate": struct.unpack_from("<I", h, 16)[0],
        "channels": struct.unpack_from("<I", h, 20)[0],
        "loopFlag": struct.unpack_from("<I", h, 24)[0],
        "loopStart": struct.unpack_from("<I", h, 28)[0],
        "codec": struct.unpack_from("<I", h, 0x30)[0],
    }


CODECS = {0: "ADPCM4", 1: "PCM16", 2: "Huffman-ADPCM", 3: "Vorbis"}


def classify(data):
    """(kind, detail dict) for a stored/decoded entry header."""
    h = data
    if len(h) >= 0x30 and h[:16] == CBG_MAGIC:
        w, ht, bpp = struct.unpack_from("<HHI", h, 0x10)
        ver = struct.unpack_from("<H", h, 0x2E)[0]
        return "CBG", {"version": 2 if ver == 2 else 1, "w": w, "h": ht, "bpp": bpp}
    b = bw_fields(h)
    if b is not None:
        b["kind"] = CODECS.get(b["codec"], "codec%d" % b["codec"])
        return "BW", b
    if len(h) >= 16 and h[:16] == BFMOVIE_MAGIC:
        return "BF_Movie", {}
    if len(h) >= 28 and h[:27] == SCN_MAGIC:
        return "scenario", {}
    if len(h) >= 4 and h[:4] == MPEG_PACK:
        return "MPEG", {}
    if len(h) >= 16 and h[:12] == arc.PACKFILE_MAGIC:
        return "PackFile", {}
    if len(h) >= 16 and h[:12] == arc.ARC20_MAGIC:
        return "ARC20", {}
    # a "._bp" program: header word 0 == 0x10, size + 0x10 fits
    if len(h) >= 16:
        w0, w1, w2, w3 = struct.unpack_from("<IIII", h, 0)
        if w0 == 0x10 and w2 == 0 and w3 == 0:
            return "program", {"code_size": w1}
    # a raw picture (RawImageHeader, inc/bgi/codec.h): u16 w, u16 h, u32 bpp,
    # then w*h*bpp/8 pixels - what a CompressedBG decodes to and what the
    # DSC-compressed UI parts of sysgrp.arc hold
    if len(h) >= 0x10:
        w, ht, bpp = struct.unpack_from("<HHI", h, 0)
        if 1 <= w <= 4096 and 1 <= ht <= 4096 and bpp in (8, 24, 32):
            return "raw-image", {"w": w, "h": ht, "bpp": bpp}
    return "other", {}


def survey(data_dir, max_arc_bytes=None):
    rep = {
        "data_dir": data_dir,
        "archives": {},
        "cgbs": collections.Counter(),
        "cbg_res": collections.Counter(),
        "cbg_bpp": collections.Counter(),
        "audio": collections.Counter(),
        "audio_rate_ch": collections.Counter(),
        "music_entries": collections.Counter(),
        "kinds": collections.Counter(),
        "movies": [],
        "dat_files": {},
        "errors": [],
    }
    arcs = sorted(f for f in os.listdir(data_dir) if f.lower().endswith(".arc"))
    for name in arcs:
        path = os.path.join(data_dir, name)
        try:
            a = arc.Archive(path)
        except (ValueError, OSError) as ex:
            rep["errors"].append(str(ex))
            continue
        kinds = collections.Counter()
        for e in a:
            try:
                head = a.read_head(e, 0x1000)
            except OSError as ex:
                rep["errors"].append("%s:%s: %s" % (name, e.name, ex))
                continue
            if head[:16] == arc.DSC_MAGIC:
                try:
                    head = arc.dsc_decode(head, 0x80)
                except ValueError as ex:
                    rep["errors"].append("%s:%s: DSC prefix: %s" % (name, e.name, ex))
                    kinds["dsc-broken"] += 1
                    continue
                kind, detail = classify(head)
                detail["dsc"] = True
            else:
                kind, detail = classify(head)
            kinds[kind] += 1
            if kind == "CBG":
                rep["cgbs"]["v%d" % detail["version"]] += 1
                rep["cbg_res"]["%dx%d" % (detail["w"], detail["h"])] += 1
                rep["cbg_bpp"]["%dbpp" % detail["bpp"]] += 1
            elif kind == "BW":
                rep["audio"][detail["kind"]] += 1
                rep["audio_rate_ch"]["%dHz/%dch" % (detail["rate"], detail["channels"])] += 1
                if "head" in e.name.lower() or "loop" in e.name.lower():
                    rep["music_entries"][os.path.splitext(name)[0] + ":" + e.name] += 1
            elif kind in ("MPEG", "BF_Movie"):
                rep["movies"].append({"arc": name, "name": e.name, "size": e.size,
                                      "kind": kind, "detail": detail})
        rep["archives"][name] = {"entries": a.count, "kinds": dict(kinds)}
        rep["kinds"].update(kinds)
        a.close()
        if max_arc_bytes and a.data_base > max_arc_bytes:
            break
    # loose .dat files (the movies of the later engines live in data*.arc; a
    # .dat here is checked for MPEG pack headers and a BGI header)
    for name in sorted(f for f in os.listdir(data_dir) if f.lower().endswith(".dat")):
        path = os.path.join(data_dir, name)
        size = os.path.getsize(path)
        info = {"size": size}
        with open(path, "rb") as f:
            head = f.read(0x40)
            info["head"] = head[:16].hex()
            if head[:16] == CBG_MAGIC:
                info["kind"] = "CBG"
            else:
                # search the whole file for the first MPEG pack header
                f.seek(0)
                data = f.read()
                i = data.find(MPEG_PACK)
                if i >= 0:
                    info["kind"] = "MPEG"
                    info["first_pack"] = i
                    info["packs"] = data.count(MPEG_PACK)
                elif head[4:8] == BW_MAGIC:
                    info["kind"] = "BW"
                elif head[:27] == SCN_MAGIC:
                    info["kind"] = "scenario"
                elif head[:16] == arc.DSC_MAGIC:
                    info["kind"] = "DSC"
                else:
                    info["kind"] = "other"
        rep["dat_files"][name] = info
        if info["kind"] == "MPEG":
            rep["movies"].append({"arc": name, "name": "".join(name), "size": size,
                                  "kind": "MPEG", "detail": info})
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data_dir")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    rep = survey(args.data_dir)
    print("archives: %d, entries: %s" % (len(rep["archives"]), sum(a["entries"] for a in rep["archives"].values())))
    print("\nentry kinds:")
    for k, v in rep["kinds"].most_common():
        print("  %-12s %6d" % (k, v))
    print("\nCompressedBG: %s" % dict(rep["cgbs"]))
    print("CBG bpp:      %s" % dict(rep["cbg_bpp"]))
    print("CBG res:      %s" % dict(rep["cbg_res"].most_common(12)))
    print("\nBW audio:     %s" % dict(rep["audio"]))
    print("BW rate/ch:   %s" % dict(rep["audio_rate_ch"]))
    print("BW head/loop entries: %d" % sum(rep["music_entries"].values()))
    print("\nmovies: %d" % len(rep["movies"]))
    for m in rep["movies"]:
        print("  %s:%s %d bytes %s %s" % (m["arc"], m["name"], m["size"], m["kind"], m.get("detail", "")))
    for k, v in rep["dat_files"].items():
        print("  .dat %s: %s" % (k, v))
    if rep["errors"]:
        print("\nerrors: %d" % len(rep["errors"]), file=sys.stderr)
        for e in rep["errors"][:20]:
            print("  " + e, file=sys.stderr)
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"kinds": dict(rep["kinds"]), "cgbs": dict(rep["cgbs"]),
                       "cbg_res": dict(rep["cbg_res"]), "cbg_bpp": dict(rep["cbg_bpp"]),
                       "audio": dict(rep["audio"]), "audio_rate_ch": dict(rep["audio_rate_ch"]),
                       "movies": rep["movies"], "dat_files": rep["dat_files"],
                       "archives": rep["archives"], "errors": rep["errors"]}, f, indent=1)
        print("wrote " + args.json)


if __name__ == "__main__":
    main()
