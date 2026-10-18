#!/usr/bin/env python3
"""Small static-analysis helper for 32-bit x86 PE images (the BGI/Ethornell
executables of the games and of OpenBGI's survey).

Commands:
  pe.py EXE str TEXT            find a Shift-JIS/ASCII string, its VA and the
                                instructions that reference it
  pe.py EXE dis VA [N]          disassemble N instructions from VA
  pe.py EXE refs VA             instructions whose immediate/displacement is VA
  pe.py EXE dword VA [N]        read N dwords at VA
  pe.py EXE func VA             disassemble from the function start containing
                                VA (heuristic: previous int3 padding) to ret
  pe.py EXE sections            the section table (RVA/raw size/entropy)
  pe.py EXE info                the headers and data directories

The image is used through its memory-mapped form (pefile's
get_memory_mapped_image), so VAs are the ones a disassembler shows and every
RVA below SizeOfImage can be read.  Section selection is robust: the helper
used to require a ".text" section, which the packed Ethornell 1.520 build
does not have, so the code section is now found by characteristics and by the
entry point instead.
"""
import math
import struct
import sys

import capstone
import pefile


def _entropy(data):
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = float(len(data))
    e = 0.0
    for c in counts:
        if c:
            p = c / n
            e -= p * math.log2(p)
    return e


class Image:
    def __init__(self, path):
        self.path = path
        self.pe = pefile.PE(path)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.mem = self.pe.get_memory_mapped_image()
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        self.md.detail = False
        self.linker = (self.pe.OPTIONAL_HEADER.MajorLinkerVersion,
                       self.pe.OPTIONAL_HEADER.MinorLinkerVersion)
        entry = self.base + self.pe.OPTIONAL_HEADER.AddressOfEntryPoint

        # the code area: the executable section holding the entry point, else
        # the largest executable section, else the section at the entry RVA
        exe = [s for s in self.pe.sections if s.Characteristics & 0x20000000]
        sec = None
        for s in exe:
            lo = self.base + s.VirtualAddress
            if lo <= entry < lo + max(s.Misc_VirtualSize, s.SizeOfRawData):
                sec = s
                break
        if sec is None and exe:
            sec = max(exe, key=lambda s: s.Misc_VirtualSize)
        if sec is None and self.pe.sections:
            sec = max(self.pe.sections, key=lambda s: s.Misc_VirtualSize)
        self.code_section = sec
        if sec is not None:
            self.text_start = self.base + sec.VirtualAddress
            self.text_end = self.text_start + max(sec.Misc_VirtualSize, sec.SizeOfRawData)
        else:  # no sections at all: the whole image
            self.text_start = self.base
            self.text_end = self.base + len(self.mem)

    # ---- reading -------------------------------------------------------------

    def bytes_at(self, va, n):
        """`n` bytes at VA; short when the VA is outside the image."""
        off = va - self.base
        if off < 0:
            return b""
        return self.mem[off:off + n]

    def dwords_at(self, va, n):
        return list(struct.unpack("<%dI" % n, self.bytes_at(va, 4 * n).ljust(4 * n, b"\0")))

    def find_bytes(self, needle):
        """VAs of every occurrence of `needle` in the image."""
        out, start = [], 0
        while True:
            i = self.mem.find(needle, start)
            if i < 0:
                return out
            out.append(self.base + i)
            start = i + 1

    def find_string(self, text, encodings=("cp932", "ascii")):
        """VAs of the NUL-terminated strings equal to `text` first, then of
        occurrences inside a longer string (a fallback for a message that
        begins with a shared prefix).  An empty list is a normal answer when
        the text is not in the image (the packed 1.520 build has no readable
        message strings at all)."""
        equal, inner = [], []
        for enc in encodings:
            try:
                needle = text.encode(enc)
            except UnicodeEncodeError:
                continue
            for va in self.find_bytes(needle):
                off = va - self.base
                s = off
                while s > 0 and self.mem[s - 1] != 0:
                    s -= 1
                if s == off:
                    if va not in equal:
                        equal.append(va)
                elif va not in inner:
                    inner.append(va)
        return equal + inner

    def read_cstring(self, va, limit=0x400):
        off = va - self.base
        end = self.mem.find(b"\0", off, off + limit)
        if end < 0:
            end = off + limit
        return self.mem[off:end]

    # ---- references ----------------------------------------------------------

    def code_refs(self, va):
        """Raw scan of the code section for the little-endian VA (push/mov/cmp
        operands): a superset of the real references (data that happens to
        equal the VA is included)."""
        needle = struct.pack("<I", va & 0xFFFFFFFF)
        lo, hi = self.text_start - self.base, self.text_end - self.base
        out, start = [], lo
        while True:
            i = self.mem.find(needle, start, hi)
            if i < 0:
                return out
            out.append(self.base + i)
            start = i + 1

    def callers(self, target):
        """Every E8 rel32 call in the code section whose destination is
        `target` (direct calls only; indirect calls are not found)."""
        lo, hi = self.text_start - self.base, self.text_end - self.base
        out, i = [], lo
        while True:
            i = self.mem.find(b"\xe8", i, hi)
            if i < 0:
                return out
            rel = struct.unpack_from("<i", self.mem, i + 1)[0]
            if self.base + i + 5 + rel == target:
                out.append(self.base + i)
            i += 1

    # ---- disassembly ---------------------------------------------------------

    def dis(self, va, count=40):
        code = self.bytes_at(va, count * 15)
        lines = []
        for ins in self.md.disasm(code, va):
            lines.append("%08x  %-24s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
            if len(lines) >= count:
                break
        return lines

    def dis_to_ret(self, va, limit=400):
        """Disassemble from `va` through the first ret/int3 (a function body).
        Returns the lines."""
        lines = []
        for ins in self.md.disasm(self.bytes_at(va, limit * 15), va):
            lines.append("%08x  %-24s %s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
            if len(lines) >= limit:
                break
            if ins.mnemonic.startswith("ret") or ins.mnemonic == "int3":
                break
        return lines

    def func_start(self, va):
        """Walk back to a likely function start: after 0xCC padding."""
        p = va
        while p > self.text_start:
            if self.mem[p - 1 - self.base] == 0xCC:
                return p
            p -= 1
        return va

    def func(self, va, limit=2000):
        start = self.func_start(va)
        lines = []
        for ins in self.md.disasm(self.bytes_at(start, limit * 15), start):
            lines.append("%08x  %s %s" % (ins.address, ins.mnemonic, ins.op_str))
            if ins.mnemonic == "int3" or len(lines) >= limit:
                break
        return lines

    def sections(self):
        return list(self.pe.sections)


def instr_containing(img, ref_va):
    """Find the instruction that contains the byte at ref_va."""
    for back in range(1, 12):
        start = ref_va - back
        for ins in img.md.disasm(img.bytes_at(start, 16), start):
            if ins.address <= ref_va < ins.address + ins.size:
                return ins
            break
    return None


def main():
    img = Image(sys.argv[1])
    cmd = sys.argv[2]
    if cmd == "str":
        text = sys.argv[3]
        for va in img.find_string(text):
            print("string %08x: %r" % (va, img.read_cstring(va)))
            for r in img.code_refs(va):
                ins = instr_containing(img, r)
                desc = "%08x %s %s" % (ins.address, ins.mnemonic, ins.op_str) if ins else "%08x ?" % r
                print("  ref %s" % desc)
    elif cmd == "dis":
        va = int(sys.argv[3], 16)
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 40
        print("\n".join(img.dis(va, n)))
    elif cmd == "refs":
        va = int(sys.argv[3], 16)
        for r in img.code_refs(va):
            ins = instr_containing(img, r)
            print("%08x %s %s" % (ins.address, ins.mnemonic, ins.op_str) if ins else "%08x ?" % r)
    elif cmd == "dword":
        va = int(sys.argv[3], 16)
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 16
        for i, v in enumerate(img.dwords_at(va, n)):
            print("%08x: %08x" % (va + 4 * i, v))
    elif cmd == "func":
        print("\n".join(img.func(int(sys.argv[3], 16))))
    elif cmd == "sections":
        for s in img.sections():
            print("%-10s rva %08x raw %08x+%08x virt %08x entropy %.2f char %08x"
                  % (s.Name.rstrip(b"\0").decode("latin-1"), s.VirtualAddress, s.PointerToRawData,
                     s.SizeOfRawData, s.Misc_VirtualSize, _entropy(s.get_data()), s.Characteristics))
    elif cmd == "info":
        o = img.pe.OPTIONAL_HEADER
        print("base %08x entry %08x image %08x linker %d.%d sections %d"
              % (img.base, img.base + o.AddressOfEntryPoint, o.SizeOfImage,
                 img.linker[0], img.linker[1], img.pe.FILE_HEADER.NumberOfSections))
        names = ("export", "import", "resource", "exception", "security", "basereloc", "debug", "arch",
                 "globalptr", "tls", "loadcfg", "boundimp", "iat", "delayimp", "com", "reserved")
        for i, d in enumerate(o.DATA_DIRECTORY):
            if d.VirtualAddress or d.Size:
                print("  %-9s rva %08x size %08x" % (names[i] if i < len(names) else i, d.VirtualAddress, d.Size))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
