#!/usr/bin/env python3
"""Recover the opcode tables of a BGI/Ethornell executable.

Each family dispatcher (the function that reports "未定義の…命令 $90%02X")
reads the sub-opcode byte and loads `[eax*4 + TABLE]`; a NULL slot is an
undefined instruction.  Prints the defined opcodes of every family in the
optables.py dump format, and with -v the handler address of each.

The original script crashed (`struct.error` in `pe.code_refs` after
`string_va` returned None) on executables that do not carry the message
strings, e.g. the packed Ethornell 1.520.6 build of this game, whose sections
are compressed/encrypted and whose text has no readable strings at all.  It
now:

  * searches the family messages in CP932 and ASCII, then in the message
    prefixes ("$80", "$90%02X", ...), and reports a family it cannot find;
  * validates a candidate table (inside the image, dword-aligned, 256
    entries, every non-zero entry inside the code section) and keeps the
    candidate with the most defined slots;
  * exits 0 with a clear diagnosis for a packed image, so it can be part of a
    batch.

usage: optables.py EXE [-v] [-o OUT]
       optables.py EXE -t FAMILY=ADDR ...   # explicit tables (for a packed exe)
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import Image, instr_containing  # noqa: E402

FAMILIES = {
    "main": ("未定義の基本命令", "$FF"),          # the base table lives behind the $FF user op
    "80": ("$80%02X",),
    "81": ("$81%02X",),
    "90": ("$90%02X",),
    "91": ("$91%02X",),
    "92": ("$92%02X",),
    "A0": ("$A0%02X",),
    "B0": ("$B0%02X",),
    "C0": ("$C0%02X",),
    "D0": ("$D0%02X",),
    "E0": ("$E0%02X",),
    "FF": ("ユーザー定義命令 $FF",),
}


def string_vas(img, patterns):
    """VAs of the family message strings, best match first: a NUL-terminated
    occurrence of one of `patterns` (CP932 or ASCII), then an occurrence
    inside a longer string.  Empty when the executable carries no such text
    (e.g. it is packed)."""
    exact, inner = [], []
    for text in patterns:
        for enc in ("cp932", "ascii"):
            try:
                needle = text.encode(enc)
            except UnicodeEncodeError:
                continue
            starts = 0
            while True:
                i = img.mem.find(needle, starts)
                if i < 0:
                    break
                off = i
                s = off
                while s > 0 and img.mem[s - 1] != 0:
                    s -= 1
                va = img.base + s      # the start of the NUL-terminated string
                if s == off:
                    if va not in exact:
                        exact.append(va)
                elif va not in inner:
                    inner.append(va)
                starts = i + 1
    return exact + inner


def table_of(img, ref_ins_va):
    """Search back from the message push for a `[reg*4 + imm32]` table load."""
    for back in range(0x10, 0x80):
        lines = img.dis(ref_ins_va - back, 40)
        for ln in lines:
            m = re.search(r"\[(?:e\w\w)\*4 \+ (0x[0-9a-f]+)\]", ln)
            if m and int(ln.split()[0], 16) < ref_ins_va:
                return int(m.group(1), 16)
    return None


def valid_table(img, va):
    """The 256 entries at VA when it looks like a dispatcher table; None
    otherwise (outside the image, unaligned, or entries outside the code)."""
    if va is None or (va - img.base) < 0 or va % 4:
        return None
    entries = img.dwords_at(va, 256)
    defined = [i for i, e in enumerate(entries) if e]
    lo, hi = img.text_start, img.text_end
    for i in defined:
        if not (lo <= entries[i] < hi):
            return None
    return entries


def tables(img):
    """{family: (table_va, 256 entries)} for the families found."""
    out = {}
    for fam, patterns in FAMILIES.items():
        best = None
        for sva in string_vas(img, patterns):
            for ref in img.code_refs(sva):
                ins = instr_containing(img, ref)
                if not ins:
                    continue
                t = table_of(img, ins.address)
                entries = valid_table(img, t)
                if entries is None:
                    continue
                n = sum(1 for e in entries if e)
                if best is None or n > best[0]:
                    best = (n, t, entries)
        if best:
            out[fam] = (best[1], best[2])
    return out


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    opts = [a for a in sys.argv[1:] if a.startswith("-")]
    if not argv:
        sys.exit(__doc__)
    img = Image(argv[0])
    verbose = "-v" in opts
    out_path = None
    for i, a in enumerate(sys.argv):
        if a == "-o" and i + 1 < len(sys.argv):
            out_path = sys.argv[i + 1]
    explicit = {}
    for a in sys.argv:
        m = re.match(r"-t(\w+)=(0x[0-9a-f]+)", a)
        if m:
            explicit[m.group(1)] = int(m.group(2), 16)
    found = tables(img)
    if explicit:
        for fam, va in explicit.items():
            entries = valid_table(img, va)
            if entries is None:
                print("%s: table %#x is not a valid dispatcher table" % (fam, va), file=sys.stderr)
            else:
                found[fam] = (va, entries)
    if not found:
        print("%s: no opcode tables found - the executable carries none of the family messages"
              % argv[0], file=sys.stderr)
        print("(a packed/encrypted build, e.g. BGI/Ethornell 1.520.6 of Aiyoku no Eustia, has no"
              " readable code or message strings; see docs/RE-1520.md)", file=sys.stderr)
        missing = [f for f in FAMILIES if f not in found]
        print("families not found: %s" % " ".join(missing), file=sys.stderr)
        return 0
    lines = []
    for fam in FAMILIES:
        if fam not in found:
            print("warning: family %s not found (no message string in the image)" % fam, file=sys.stderr)
            continue
        t, entries = found[fam]
        defined = [i for i, e in enumerate(entries) if e]
        lines.append("%s (table %08x) %d: %s" % (fam, t, len(defined),
                                                  " ".join("%02X" % i for i in defined)))
        if verbose:
            for i in defined:
                lines.append("    %s %02X -> %08x" % (fam, i, entries[i]))
    text = "\n".join(lines) + "\n"
    if out_path:
        open(out_path, "w").write(text)
        print("wrote %s (%d families)" % (out_path, len(found)))
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
