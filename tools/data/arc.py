#!/usr/bin/env python3
"""BGI / Ethornell resource archives and the formats stored in them.

No game data is bundled here: point the tool at a copy of the game's
``data`` directory.  Standard library only.

Formats (openbgi: src/core/arc.c, src/core/dsc.c, inc/bgi/codec.h,
inc/bgi/bfmovie.h, inc/bgi/scn.h, src/snd/bw/source.c):

  PackFile           16-byte header ("PackFile    " + u32 entry count at +12),
                     32-byte entries: name[16], u32 offset, u32 size; the
                     offsets count from the end of the index
                     (16 + count * 32).
  BURIKO ARC20       same header, 0x80-byte entries: name[0x60], u32 offset
                     at +0x60, u32 size at +0x64 (1.573 on; not used by
                     this game).
  DSC FORMAT 1.00    0x20-byte header (magic[16], u32 key at +0x10,
                     u32 outSize +0x14, u32 decCount +0x18), 512 obfuscated
                     code lengths at +0x20, an MSB-first Huffman bit stream
                     at +0x220.  Literal symbols 0x000..0x0FF; 0x100..0x1FF
                     are a back reference: low byte + 2 is the length, the
                     next 12 bits the distance, copy from out - distance - 2.
  CompressedBG___    0x30-byte header: u16 w +0x10, u16 h +0x12, u32 bpp
                     +0x14, u32 interLen +0x20, u32 key +0x24, u32 encLen
                     +0x28, u8 sum +0x2c, u8 xor +0x2d, u16 version +0x2e
                     (version 2 = the v2 coding; anything else is v1).
  BW audio           0x40-byte header "bw  ": u32 codec at +0x10
                     (0 PCM, 1 ADPCM, 2 Huffman, 3 Vorbis), u32 rate,
                     u8 channels, ...;  see inc/bgi/snd/bw.h.
  BF_Movie_______    frame sequence (16-byte magic, type, frames, fps,
                     width/height, 32 bpp).
  BurikoCompiledScriptVer1.00   scenario container.
  "._bp" programs    16-byte header (code offset 0x10, size, two zero
                     words) followed by the bytecode area (inc/bgi/asm.h).

Usage::

  python3 tools/data/arc.py list  data/data01000.arc
  python3 tools/data/arc.py extract data/system.arc ipl._bp -o /tmp
        [--raw]            keep the stored bytes (no DSC decode)
  python3 tools/data/arc.py cat data/system.arc ipl._bp -o /tmp/ipl._bp
  python3 tools/data/arc.py scan data/*.arc [--json out.json] [--mpeg]
        classify every entry from its (DSC-decoded) header and print a
        survey; --mpeg also searches every payload for MPEG-1 pack
        headers (00 00 01 BA), which is how the movies are found
"""
import argparse
import glob
import json
import os
import struct
import sys

PACKFILE_MAGIC = b"PackFile    "
ARC20_MAGIC = b"BURIKO ARC20"
DSC_MAGIC = b"DSC FORMAT 1.00\0"   # 16 bytes incl. the NUL, as memcmp compares
CBG_MAGIC = b"CompressedBG___\0"   # 16 bytes incl. the NUL
BFMOVIE_MAGIC = b"BF_Movie_______\0" # 16 bytes incl. the NUL
SCN_MAGIC = b"BurikoCompiledScriptVer1.00"
BW_MAGIC = b"bw  "
SDC_MAGIC = b"SDC FORMAT 1.00"
DCFS_MAGIC = b"DCFS FORMAT 1.00"


# ---- the archive index ------------------------------------------------------

class ArcEntry:
    __slots__ = ("name", "offset", "size")

    def __init__(self, name, offset, size):
        self.name, self.offset, self.size = name, offset, size


class Archive:
    """A PackFile / ARC20 archive: its index and random access to the
    stored bytes.  `data_base` is the file offset the entry offsets count
    from."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            hdr = f.read(16)
            if len(hdr) != 16:
                raise ValueError("%s: shorter than 16 bytes" % path)
            if hdr[:12] == PACKFILE_MAGIC:
                self.format, rec_size, name_size = "PackFile", 32, 16
            elif hdr[:12] == ARC20_MAGIC:
                self.format, rec_size, name_size = "ARC20", 0x80, 0x60
            else:
                raise ValueError("%s: not a BGI archive (%r)" % (path, hdr[:12]))
            (self.count,) = struct.unpack_from("<I", hdr, 12)
            raw = f.read(self.count * rec_size)
            self.entries = []
            for i in range(self.count):
                rec = raw[i * rec_size:(i + 1) * rec_size]
                name = rec[:name_size].split(b"\0", 1)[0].decode("cp932", "replace")
                off, size = struct.unpack_from("<II", rec, name_size)
                self.entries.append(ArcEntry(name, off, size))
            self.data_base = 16 + self.count * rec_size
            self._f = open(path, "rb")
        self.by_name = {e.name.lower(): e for e in self.entries}

    def entry(self, name):
        return self.by_name.get(name.lower())

    def read(self, entry):
        """The stored bytes of an entry (DSC still compressed)."""
        self._f.seek(self.data_base + entry.offset)
        return self._f.read(entry.size)

    def read_head(self, entry, n):
        self._f.seek(self.data_base + entry.offset)
        return self._f.read(n)

    def close(self):
        self._f.close()

    def __iter__(self):
        return iter(self.entries)


# ---- DSC FORMAT 1.00 -------------------------------------------------------

def _hash_step(key):
    """BGI_HashUpdate (src/core/hash.c): one 15-bit output, key stepped."""
    lo = 20021 * (key & 0xFFFF)
    hi = (20021 * (key >> 16) + 346 * key) & 0xFFFFFFFF
    hi = (hi + (lo >> 16)) & 0xFFFF
    key = ((hi << 16) + (lo & 0xFFFF) + 1) & 0xFFFFFFFF
    return hi & 0x7FFF, key


def _hash_bytes(key, n):
    out = bytearray(n)
    for i in range(n):
        v, key = _hash_step(key)
        out[i] = v & 0xFF
    return out


def is_dsc(data):
    return data[:16] == DSC_MAGIC


def dsc_out_size(data):
    return struct.unpack_from("<I", data, 0x14)[0]


def dsc_decode(data, limit=None):
    """Decompress a DSC FORMAT 1.00 stream; returns the bytes (outSize).

    Mirrors DscBuildTree / DscDecodeStream (src/core/dsc.c): the 512 code
    lengths are de-obfuscated with the hash generator seeded by the
    header's key, the canonical tree is laid out level by level (leaves
    sorted by (length, symbol); every unused slot becomes an internal
    node with the next two fresh ids), and the symbols are read
    MSB-first."""
    if not is_dsc(data):
        raise ValueError("not a DSC stream")
    key, out_size, dec_count = struct.unpack_from("<III", data, 0x10)
    lens = data[0x20:0x20 + 512]
    mask = _hash_bytes(key, 512)
    leaves = []
    for i in range(512):
        length = (lens[i] - mask[i]) & 0xFF
        if length:
            leaves.append((length, i))
    leaves.sort()

    # node id -> ("leaf", symbol) or ("int", child0, child1); ids are handed
    # out in allocation order, the root being 0, as in the C layout
    nodes = {"count": 1}
    nodes[0] = None
    level = [0]        # node ids on the current level
    next_free = 1
    depth = 0
    pos = 0
    while pos < len(leaves):
        used = 0
        nxt = []
        while pos < len(leaves) and leaves[pos][0] == depth:
            nodes[level[used]] = ("leaf", leaves[pos][1])
            used += 1
            pos += 1
        remaining = len(level) - used
        for _ in range(remaining):
            node = level[used]
            nodes[node] = ("int", next_free, next_free + 1)
            nxt.extend((next_free, next_free + 1))
            next_free += 2
            used += 1
        nodes["count"] = next_free
        level = nxt
        depth += 1
        if depth > 600:
            raise ValueError("bad DSC code lengths")
    nr_nodes = nodes["count"]
    kid = [None] * nr_nodes
    val = [0] * nr_nodes
    for n in range(nr_nodes):
        e = nodes[n]
        if e is None:
            raise ValueError("DSC tree has a hole at node %d" % n)
        if e[0] == "int":
            kid[n] = (e[1], e[2])
        else:
            val[n] = e[1]

    src = data[0x220:]
    bitpos = 0

    def bit():
        nonlocal bitpos
        i = bitpos >> 3
        b = (src[i] >> (7 - (bitpos & 7))) & 1 if i < len(src) else 0
        bitpos += 1
        return b

    out = bytearray()
    for _ in range(dec_count):
        if limit is not None and len(out) >= limit:
            return bytes(out)
        node = 0
        while kid[node] is not None:
            node = kid[node][bit()]
        code = val[node]
        if code >> 8 == 1:
            # back reference: 12 more bits of distance, MSB first
            dist = 0
            for _ in range(12):
                dist = (dist << 1) | bit()
            count = (code & 0xFF) + 2
            start = len(out) - dist - 2
            if start < 0:
                raise ValueError("DSC back reference before the start")
            for k in range(count):
                out.append(out[start + k])
        else:
            out.append(code & 0xFF)
    if limit is None and len(out) != out_size:
        raise ValueError("DSC size mismatch: %d != %d" % (len(out), out_size))
    return bytes(out)


def maybe_dsc(data):
    """(decoded bytes, True) for a DSC entry, (data, False) otherwise."""
    if is_dsc(data):
        return dsc_decode(data), True
    return data, False


# ---- classification ---------------------------------------------------------

# BW codec ids (inc/bgi/snd/bw.h)
BW_CODECS = {0: "PCM", 1: "ADPCM", 2: "Huffman", 3: "Vorbis"}


def classify(data):
    """A one-line description of a stored entry, from its decoded header."""
    if len(data) >= 16 and data[:12] == PACKFILE_MAGIC:
        return "nested PackFile"
    if len(data) >= 0x30 and data[:16] == CBG_MAGIC:
        w, h, bpp = struct.unpack_from("<HHI", data, 0x10)
        ver = struct.unpack_from("<H", data, 0x2E)[0]
        return "CBG v%d %dx%d %dbpp" % (2 if ver == 2 else 1, w, h, bpp)
    if len(data) >= 0x40 and data[:4] == BW_MAGIC:
        codec, rate = struct.unpack_from("<II", data, 0x10)
        ch = data[0x18] if len(data) > 0x18 else 0
        return "BW %s %dHz %dch" % (BW_CODECS.get(codec, "codec%d" % codec), rate, ch)
    if len(data) >= 16 and data[:16] == BFMOVIE_MAGIC:
        # bfmovie.h: type +0x10, frames +0x14, fps +0x18, w +0x1c, h +0x20
        try:
            typ, frames, fps, w, h = struct.unpack_from("<IIIII", data, 0x10)
            return "BF_Movie type 0x%x %dx%d %d frames @%dfps" % (typ, w, h, frames, fps)
        except struct.error:
            return "BF_Movie"
    if len(data) >= 28 and data[:27] == SCN_MAGIC:
        return "BurikoCompiledScriptVer1.00"
    if len(data) >= 16 and data[:4] == b"\0\0\1\xba":
        return "MPEG-1 program stream"
    if len(data) >= 4 and data[:4] == b"bw  ":
        return "BW (short?)"
    if len(data) >= 8 and data[:4] == b"\x89PNG":
        return "PNG"
    if len(data) >= 2 and data[:2] == b"BM":
        return "BMP"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if len(data) >= 16 and data[:4] == SDC_MAGIC[:4]:
        return "SDC"
    if len(data) >= 16 and data[:4] == DCFS_MAGIC[:4]:
        return "DCFS"
    if len(data) >= 0x10:
        # a "._bp" program: header word 0 == 0x10 and the size fits
        hdr = struct.unpack_from("<IIII", data, 0)
        if hdr[0] == 0x10 and hdr[1] + 0x10 <= len(data) and hdr[2] == 0 and hdr[3] == 0:
            return "Buriko program (._bp)"
    if len(data) >= 4 and data[:2] in (b"\x1f\x8b",):
        return "gzip"
    return "data"


# ---- the commands -----------------------------------------------------------

def cmd_list(args):
    for path in args.arcs:
        a = Archive(path)
        print("%s: %d entries (%s)" % (path, a.count, a.format))
        for e in a:
            print("  %-20s %10d bytes at 0x%08x" % (e.name, e.size, e.offset))


def cmd_extract(args):
    out = args.out or "."
    os.makedirs(out, exist_ok=True)
    for path in args.arcs:
        a = Archive(path)
        for e in a:
            if args.name and e.name.lower() != args.name.lower():
                continue
            data = a.read(e)
            if not args.raw:
                try:
                    data, dsc = maybe_dsc(data)
                except ValueError as ex:
                    print("%s:%s: DSC decode failed (%s), keeping stored bytes" % (path, e.name, ex))
            dst = os.path.join(out, e.name)
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            print("wrote %s (%d bytes)" % (dst, len(data)))


def _mpeg_offsets(data):
    """Offsets of MPEG-1 pack headers (00 00 01 BA) in `data`."""
    out, start = [], 0
    while True:
        i = data.find(b"\0\0\1\xba", start)
        if i < 0:
            return out
        out.append(i)
        start = i + 4
        if len(out) >= 8:
            return out


def cmd_scan(args):
    report = {"arcs": {}, "totals": {}, "movies": [], "dsc_entries": 0, "errors": []}
    for path in sorted(args.arcs):
        try:
            a = Archive(path)
        except ValueError as ex:
            report["errors"].append(str(ex))
            continue
        kinds = {}
        arc_movies = []
        for e in a:
            try:
                raw = a.read(e)
            except OSError as ex:
                report["errors"].append("%s:%s: %s" % (path, e.name, ex))
                continue
            data, dsc = maybe_dsc(raw) if not args.no_dsc else (raw, False)
            if dsc:
                report["dsc_entries"] += 1
            kind = classify(data)
            base = kind.split()[0]
            kinds[base] = kinds.get(base, 0) + 1
            if base == "MPEG-1":
                arc_movies.append({"name": e.name, "size": e.size, "packs": _mpeg_offsets(data)[:3]})
            elif base == "BF_Movie":
                arc_movies.append({"name": e.name, "size": e.size, "kind": "BF_Movie", "desc": kind})
            elif args.mpeg and e.size > 0x1000:
                # a movie may also be wrapped: look into bigger unknown entries
                if base in ("data", "BW", "BurikoCompiledScriptVer1.00"):
                    offs = _mpeg_offsets(data[:0x10000])
                    if offs:
                        arc_movies.append({"name": e.name, "size": e.size, "kind": base, "packs": offs[:3]})
            # keep the CBG resolution histogram
            if base == "CBG":
                res = kind.split()[1] if " " in kind else "?"
                key = "CBG " + res
                kinds[key] = kinds.get(key, 0) + 1
                kinds[base] -= 1
        if arc_movies:
            report["movies"].extend([dict(m, arc=os.path.basename(path)) for m in arc_movies])
        report["arcs"][os.path.basename(path)] = {"entries": a.count, "format": a.format, "kinds": kinds}
        for k, v in kinds.items():
            report["totals"][k] = report["totals"].get(k, 0) + v
        a.close()
    print(json.dumps({k: report[k] for k in ("totals",)}, indent=1, sort_keys=True))
    if report["movies"]:
        print("movies:")
        for m in report["movies"]:
            print("  %s:%s %d bytes %s" % (m["arc"], m["name"], m["size"], m.get("desc") or m.get("kind") or ""))
    if report["errors"]:
        print("errors:", len(report["errors"]), file=sys.stderr)
        for e in report["errors"][:20]:
            print("  " + e, file=sys.stderr)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=1, sort_keys=True)
        print("wrote " + args.json)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("arcs", nargs="+")
    p = sub.add_parser("extract")
    p.add_argument("arcs", nargs="+")
    p.add_argument("--name", default=None, help="only this entry")
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--raw", action="store_true")
    p = sub.add_parser("scan")
    p.add_argument("arcs", nargs="+")
    p.add_argument("--json", default=None)
    p.add_argument("--mpeg", action="store_true", help="also probe large entries for MPEG pack headers")
    p.add_argument("--no-dsc", action="store_true")
    args = ap.parse_args()
    {"list": cmd_list, "extract": cmd_extract, "scan": cmd_scan}[args.cmd](args)


if __name__ == "__main__":
    main()
