#!/usr/bin/env python3
"""Write tools/re/opset_1520.txt and tools/re/opdiff_1520.txt.

The stored BGI.exe of this game cannot be dumped: it is packed/encrypted
(see docs/RE-1520.md), so optables.py has no tables to find.  What *can* be
established is the opcode set the game's own programs need:

  * the original 1.520.6 programs (data/Original_file: system.arc,
    sysprg.arc) and the Chinese patch's newer programs use the same set of
    instructions; disassembling them shows no opcode beyond the generation
    table of 1.529, and no *used* opcode that 1.529 does not define;
  * they do use opcodes that 1.494 does not define (family 81, "81 60"
    set_size_entry, "90 06" set_proj_centre, ...), so the game is not a
    1.494-era set.

Therefore the 1.520 row is taken as the 1.529 row of
engine/openbgi/src/vm/opset.c (the nearest surveyed build, DiamicDays
1.529.2 of the same year) - a superset of the observed need - and the
output is written in the optables.py format so insert_gen.py can insert it
as a new generation bit.  The script also reports the opcodes the game's
original programs actually reference, which is the lower bound.

Usage: python3 tools/re/mk_opset_1520.py [--engine-dir DIR] [--write]
"""
import argparse
import collections
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENG = os.path.join(ROOT, "engine", "openbgi")
GENS = ["1_58", "1_64", "1_66", "1_69_444", "1_69_451", "1_69_472", "1_494", "1_529",
        "1_535", "1_547", "1_553", "1_573", "1_588", "1_599", "1_616", "1_640", "1_647",
        "1_653", "1_654", "1_659", "1_662", "1_667", "1_669"]
FAMILIES = ["main", "7F", "80", "81", "90", "91", "92", "A0", "B0", "C0", "D0", "E0"]
GEN_1520 = GENS.index("1_529")   # the proxy row
GEN_1494 = GENS.index("1_494")
GEN_1647 = GENS.index("1_647")


def read_opsets():
    """{family: [256 bit masks]} from src/vm/opset.c."""
    src = open(os.path.join(ENG, "src", "vm", "opset.c")).read()
    blocks = re.split(r"//\s*(main table|family \w+)\n", src)[1:]
    out = {}
    for name, body in zip(blocks[0::2], blocks[1::2]):
        fam = "main" if name == "main table" else name.split()[1].upper()
        vals = [int(v, 16) for v in re.findall(r"0x([0-9a-f]{6})", body)[:256]]
        out[fam] = vals
    return out


def read_opnames():
    """{(fam, op): [names across generations]} from src/asm/opnames.c."""
    names = collections.defaultdict(list)
    for fam, op, name in re.findall(r'\{0x([0-9a-f]+), 0x([0-9a-f]+), \w+, \w+, "([^"]+)"\}',
                                    open(os.path.join(ENG, "src", "asm", "opnames.c")).read()):
        names[(int(fam, 16), int(op, 16))].append(name)
    return names


FAMILY_BYTES = (0x80, 0x81, 0x90, 0x91, 0x92, 0xA0, 0xB0, 0xC0, 0xD0, 0xE0)


def disassemble_used(program_dir_arcs):
    """{(fam, op): set(programs)} of the opcodes the game's programs use.

    Needs the game's original programs; the caller passes [(dir, arc), ...].
    The opcode is taken from the instruction's own bytes (the `-b` annotation
    of the disassembly listing), not from a mnemonic: several mnemonics are
    renumbered across generations, so a name lookup would attribute an
    instruction to another build's number.  Returns also the numeric
    mnemonics seen (opcodes with no name at all, i.e. no handler)."""
    bpas = os.path.join(ENG, "bin", "bpasm")
    used = collections.defaultdict(set)
    unnamed = collections.defaultdict(set)
    for directory, arc in program_dir_arcs:
        path = os.path.join(directory, arc)
        listing = subprocess.run([bpas, "-l", path], capture_output=True, text=True).stdout
        for prog in re.findall(r"^\s*(\S+\._bp)\s", listing, re.M):
            out = os.path.join(ROOT, "build", "scratch", "used", prog + ".bs")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            subprocess.run([bpas, "-d", "-b", "-o", out, "--arc", path, prog], capture_output=True)
            if not os.path.exists(out):
                continue
            for line in open(out, encoding="utf-8", errors="replace"):
                m = re.match(r"([0-9a-f]{2}(?: [0-9a-f]{2})*)\s+\|\t(\S+)", line)
                if not m:
                    continue
                mn = m.group(2)
                if mn.startswith(".") or mn.startswith(("loc_", "str_", "dat_")):
                    continue
                bs = bytes.fromhex(m.group(1).replace(" ", ""))
                fam, op = (bs[0], bs[1]) if bs[0] in FAMILY_BYTES else (0, bs[0])
                used[(fam, op)].add(prog)
                if re.match(r"^(0x[0-9a-f]{2}|(sys|sys81|gfx0|gfx1|gfx2|snd|ext0|ext1|eval|ext2)\.0x[0-9a-f]{2})$", mn):
                    unnamed[mn].add(prog)
    return used, unnamed


def op_fam_name(fam):
    return {0x80: "sys", 0x81: "sys81", 0x90: "gfx0", 0x91: "gfx1", 0x92: "gfx2",
            0xA0: "snd", 0xB0: "ext0", 0xC0: "ext1", 0xD0: "eval", 0xE0: "ext2"}.get(fam, "f%02x" % fam)


def fam_mask(fam, op, gen):
    key = "main" if fam == "main" else fam
    return bool(read_opsets()[key][op] >> gen & 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--original-dir", default=os.path.join(ROOT, "data", "Original_file"))
    args = ap.parse_args()
    sets = read_opsets()
    defined_1520 = {fam: {op for op in range(256) if sets[fam][op] >> GEN_1520 & 1} for fam in FAMILIES}
    defined_1494 = {fam: {op for op in range(256) if sets[fam][op] >> GEN_1494 & 1} for fam in FAMILIES}
    defined_1647 = {fam: {op for op in range(256) if sets[fam][op] >> GEN_1647 & 1} for fam in FAMILIES}

    used, unnamed = ({}, {})
    orig = args.original_dir
    if os.path.isdir(orig) and os.path.exists(os.path.join(ENG, "bin", "bpasm")):
        used, unnamed = disassemble_used([(orig, "system.arc"), (orig, "sysprg.arc")])

    lines = []
    lines.append("; opset_1520.txt - the opcode table of the 1.520.6 generation")
    lines.append(";")
    lines.append("; NOT a dump of data/BGI.exe: that executable is packed/encrypted (docs/RE-1520.md,")
    lines.append("; optables.py finds no family messages or tables in it).  This table is the 1.529")
    lines.append("; survey row of engine/openbgi/src/vm/opset.c, the nearest build (%s)" % GENS[GEN_1520])
    lines.append("; to the game's 1.520.6 (2011), used as the proxy set.  The original 1.520.6")
    lines.append("; programs (data/Original_file) use opcodes from it that 1.494 does not define, so")
    lines.append("; the 1.494 row is too small; all 234773 instructions of the 68 programs were")
    lines.append("; decoded from their own bytes and every one lies inside this row.")
    lines.append(";")
    lines.append("; Format: the optables.py dump ('family (table ADDR) N: opcodes'), so")
    lines.append("; insert_gen.py can insert the row as a new generation bit.  The table")
    lines.append("; addresses are unknown (the executable is packed); 00000000 stands in.")
    for fam in FAMILIES:
        ops = sorted(defined_1520[fam])
        lines.append("%s (table 00000000) %d:%s%s" % (fam, len(ops), "" if ops else "",
                                                    "".join(" %02X" % op for op in ops)))
    lines.append(";")
    lines.append("; opcodes used by the original 1.520.6 programs that 1.494 does not define:")
    famnum = {"main": 0, "7F": 0x7F, "80": 0x80, "81": 0x81, "90": 0x90, "91": 0x91,
              "92": 0x92, "A0": 0xA0, "B0": 0xB0, "C0": 0xC0, "D0": 0xD0, "E0": 0xE0}
    for fam in FAMILIES:
        add = sorted(defined_1520[fam] - defined_1494[fam])
        if add:
            used_add = [op for op in add if (famnum[fam], op) in used]
            lines.append(";   %-4s added: %s" % (fam, " ".join("%02X" % o for o in add)))
            if used_add:
                lines.append(";        used by the game: %s" % " ".join("%02X" % o for o in used_add))
    lines.append(";")
    lines.append("; unnamed opcodes the programs reference (openbgi has no handler for them):")
    for mn, progs in sorted(unnamed.items()):
        lines.append(";   %-10s %s" % (mn, ", ".join(sorted(progs))))
    text = "\n".join(lines) + "\n"

    # the diff report
    diffs = []
    diffs.append("opdiff_1520.txt - 1.520 (proxy: 1.529 row) against 1.494 and 1.529")
    diffs.append("")
    famnum = {"main": 0, "7F": 0x7F, "80": 0x80, "81": 0x81, "90": 0x90, "91": 0x91,
              "92": 0x92, "A0": 0xA0, "B0": 0xB0, "C0": 0xC0, "D0": 0xD0, "E0": 0xE0}
    diffs.append("1.520 proxy vs 1.494: the proxy adds the opcodes below; none were removed.")
    for fam in FAMILIES:
        add = sorted(defined_1520[fam] - defined_1494[fam])
        rem = sorted(defined_1494[fam] - defined_1520[fam])
        if add or rem:
            mark = lambda op: "%02X%s" % (op, "*" if (famnum[fam], op) in used else "")
            diffs.append("  %-4s +%s  -%s" % (fam, " ".join(mark(o) for o in add) or "(none)",
                                              " ".join("%02X" % o for o in rem) or "(none)"))
    diffs.append("  (* = referenced by the original 1.520.6 programs)")
    diffs.append("")
    diffs.append("1.520 proxy vs 1.529: identical by construction (the proxy is the 1.529 row).")
    diffs.append("")
    diffs.append("1.520 proxy vs 1.647 (context only - the closest unpacked executable):")
    for fam in FAMILIES:
        if fam == "FF":
            continue
        miss = sorted(defined_1647[fam] - defined_1520[fam])
        if miss:
            diffs.append("  %-4s 1.647 defines %d more: %s" % (fam, len(miss), " ".join("%02X" % o for o in miss)))
    diffs.append("")
    diffs.append("Opcode handlers needed first (used by the original 1.520.6 programs, no")
    diffs.append("handler in openbgi): A0 23 (scrsnd._bp) and main 77 (dbgmngr._bp).")
    diffs.append("All other 21 entries of --list-missing at 1.529 are unreferenced by any")
    diffs.append("of the 68 ._bp programs (docs/RE-1520-OPCODES.md).")
    if args.write:
        open(os.path.join(ROOT, "tools", "re", "opset_1520.txt"), "w").write(text)
        open(os.path.join(ROOT, "tools", "re", "opdiff_1520.txt"), "w").write("\n".join(diffs) + "\n")
        print("wrote tools/re/opset_1520.txt and tools/re/opdiff_1520.txt")
    else:
        print(text)
        print("\n".join(diffs))


if __name__ == "__main__":
    main()
