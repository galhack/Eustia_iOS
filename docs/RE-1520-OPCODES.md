# RE-1520-OPCODES — the opcodes the game uses that OpenBGI lacks

Status: the on-disk `data/BGI.exe` (1.520.6) is packed/encrypted and cannot be
disassembled (see `docs/RE-1520.md` §2). This document therefore recovers the
handlers from the **only unpacked Ethornell executable available**, the 1.647
build at `/path/to/subarashiki/data/BGI.exe`, and marks that clearly as
proxy evidence. All handler addresses below are VAs of that 1.647 image
(`ImageBase 0x400000`); they were dumped with `tools/re/optables.py -v`
(see `tools/re/handlers_1647.txt`).

Which of the 23 `--list-missing` opcodes matter: **two**.
`tools/re/mk_opset_1520.py` scans all 69 `._bp` programs of both the original
1.520.6 `system.arc`/`sysprg.arc` (`data/Original_file`) and the Chinese patch
versions. Only two opcodes print without a name in OpenBGI's tables (an
unnamed-but-defined opcode is exactly a profile opcode without a handler):

| opcode | used by | occurrences |
|---|---|---|
| `A0 23` (`snd.0x23`) | `scrsnd._bp` (sound commands) | 1 call site, both versions |
| `main 77` (`0x77`) | `dbgmngr._bp` (debug manager) | 2 call sites, both versions |

The other 21 (`main 7C`, `80 27 EA`, `81 F2`, `90 92`, `91 69 70 71 73 74 75 76
78 79 7A 7B 7C 7D BB`, `92 13`, `B0 22`) are referenced by **none** of the 69
programs (original or patched). They are listed at the end of this file with
their 1.647 handler addresses and observed stack shapes, for completeness only.

## Reading the disassembly

The 1.647 VM handlers are `int op(Thread_t* t)`, `t` at `[ebp+8]`; the helper
calls identifiable in every handler are:

| helper | meaning |
|---|---|
| `0x44b5d0` | `Thread_Pop(t)` — pop one 32-bit value, returned in `eax` |
| `0x44b530` / `0x44b550` | `RdU8(t)` / `RdU16(t)` — code-stream immediates (not used here) |
| `0x496b30` | `PopPtr(t)` — pop and translate a tagged pointer, real pointer in `eax` |
| `0x44b5f0` | `Thread_Push(t, esi)` — push the value in `esi` |
| `0x44b6e0` | `Thread_SetWait(t, obj)`; the handler then returns **2** (the thread waits) |

The script stack is pushed left to right, so the **last** script argument is
popped first. A handler returning 0 with no `Thread_Push` is stack-neutral
(consumes its arguments); one that pushes leaves a result.

---

## `A0 23` — the used sound opcode (equivalent to `A0 21` se_load_ex)

**1.647 handler: `0x48ff10`**

Script signature (derived from the pop order; identical to `A0 21`, whose
OpenBGI handler `Opcode_Snd_SeLoadEx` documents the arguments):

```
slot:int, arc:ptr, name:ptr, fadeInMs:int, gain16:int   →
```

- Waits for the load and returns **2** (`A0 20`/`A0 21` do the same); nothing is
  pushed.
- Pops, in order: `gain16` (× `1/65536` at `0x4f4d88` → double gain),
  `fadeInMs`, `name` (`PopPtr`), `arc` (`PopPtr`), `slot`.
- Allocates the same 0x670-byte wait object as `A0 20`/`A0 21`
  (constructor `0x4402e0`, vtable `0x4eda34`, size argument `0x670` from
  `0x4b401c`), calls `0x4a0f50(slot)` first (the SE-slot check), stores
  slot/fadeInMs/gain at object `+0x650/+0x654/+0x658`, then attaches the wait
  with `0x44b6e0` and returns 2.
- **The only difference from `A0 21`**: the second double stored at object
  `+0x660` is the constant `2.0` (from `0x4f4d40`) instead of `1.0` (`fld1` in
  `A0 20`/`A0 21`). The sound-loader queue path used by `A0 20`/`A0 21` takes
  only slot, buffer, fadeInMs and gain, so this field does not change the
  observable load; it is an unknown load-mode/loop field.

Observed call site, identical in the original 1.520.6 and patched
`scrsnd._bp` (decompiled source, `build/scratch/bpc/scrsnd._bp.bpc`):

```c
if (!l120) snd.se_load_ex(24 + p3, "data04xxx.arc", l100, 1, 1 << 16);
else       snd.0x23    (24 + p3, "data04xxx.arc", l100, 1, 1 << 16);   // 1 ms fade, gain 1.0
l11c = snd.se_play(24 + p3, l104, 64);
```

`l120` is an internal configuration flag (config word at global 1532 and a
sound-driver setting); both branches issue the same load. **Implement `A0 23`
exactly as `A0 21`:**

```c
static int Opcode_Snd_SeLoadEx2(Thread_t* t) // A0 23: slot, arc, name, fadeInMs, gain16 →
{
    int32_t gain16 = (int32_t)Thread_Pop(t);
    int fadeInMs = (int)Thread_Pop(t);
    const char* name = (const char*)PopPtr(t);
    const char* arc = (const char*)PopPtr(t);
    int slot = (int)Thread_Pop(t);
    CheckSeSlot(slot, t);
    Thread_SetWait(t, WaitSeLoad_New(t, slot, arc, name, fadeInMs, gain16 / 65536.0));
    return 2;
}
```

---

## `main 77` — the used base-table opcode (debug manager only)

**1.647 handler: `0x47d070`**

```
index:int → value
```

- Pops one int, calls `0x469700` (= `jmp 0x449520`), pushes the result.
- `0x449520` indexes a **jump table of 18 entries** (`index > 0x11` → −1):
  each entry reads one field of a global engine object
  `[0x572ee0] + 0x85c + index*0x28` (`0x85c, 0x884, 0x8ac, …`). It is an
  engine-statistics accessor (18 stats, 0x28 bytes per record).
- The game calls it only from `dbgmngr._bp` with indexes 0 and 16
  (`push_i8 0 … 0x77`, `push_i8 16 … 0x77`). `dbgmngr._bp` itself is loaded
  only when `debug.inf` exists next to the game (ipl: `sys.file_exists(0,
  "debug.inf")` and it is part of the quit condition).
- Safe implementation: `Thread_Pop(t); Thread_Push(t, 0); return 0;` (or return
  real counters). No game path depends on the value.

## `main 7C` — unused developer dialog

**1.647 handler: `0x47d400`** — pops two pointers, calls `0x470720`, pushes the
result. `0x470720` builds a `"%s\n"` list and shows a selection dialog whose
title is the Shift-JIS string `イベントを選択してください` ("select an event",
at `0x4ef3ac`) — a developer event-selector. **Referenced by no program.**
Stub: `PopPtr; PopPtr; Thread_Push(t, 0);`.

---

## The other 21 (unreferenced by any shipped program)

Handler addresses and the shape observed in the 1.647 proxy: `ints`/`ptrs` are
the number of `Thread_Pop` / `PopPtr` calls before the handler's first service
call; `→` means a `Thread_Push` follows (net stack effect). None of these is
referenced by the original or patched programs, so they are completeness items.

| opcode | 1.647 VA | ints | ptrs | pushes | first internal callee | note |
|---|---|---|---|---|---|---|
| `main 7C` | `0x47d400` | 0 | 2 | 1 | `0x470720` | developer "select event" dialog |
| `80 27` | `0x490da0` | 0 | 2 | 1 | `[0x4e3178]` (function pointer) | two pointers → result through a global callback |
| `80 EA` | `0x493410` | 0 | 1 | 0 | `0x47a550` | one path/string pointer, no result |
| `81 F2` | `0x4951b0` | 2 | 11 | 2 | `0x4b3e18` (alloc) | large SEH routine, two results; likely a multi-value query/format |
| `90 92` | `0x486470` | 1 | 0 | 0 | `0x46aa90` | one int, no result (neighbour `90 91` text_set_mode, `90 94` char interval: a text-mode setter) |
| `91 69` | `0x48b150` | 3 | 0 | 0 | `0x469ea0` | sibling of the cluster below |
| `91 70` | `0x48b1b0` | 6 | 0 | 1 | `0x469f80` | same cluster, result pushed |
| `91 71` | `0x48b230` | 1 | 0 | 0 | `0x469fa0` | same cluster |
| `91 73` | `0x48b260` | 2 | 1 | 1 | `0x469fb0` | same cluster |
| `91 74` | `0x48b2d0` | 2 | 0 | 0 | `0x46a020` | same cluster |
| `91 75` | `0x48b310` | 6 | 0 | 0 | `0x46a030` | same cluster |
| `91 76` | `0x48b3b0` | 6 | 0 | 0 | `0x46a050` | same cluster |
| `91 78` | `0x48b5e0` | 5 | 2 | 0 | `0x46a070` | same cluster |
| `91 79` | `0x48b850` | 3 | 1 | 0 | `0x46a090` | same cluster |
| `91 7A` | `0x48ba20` | 3 | 1 | 0 | `0x46a0a0` | same cluster |
| `91 7B` | `0x48bb00` | 5 | 1 | 0 | `0x46a0c0` | same cluster |
| `91 7C` | `0x48bd50` | 3 | 0 | 0 | `0x46a0e0` | same cluster |
| `91 7D` | `0x48bf50` | 4 | 0 | 0 | `0x46a0f0` | same cluster |
| `91 BB` | `0x48d420` | 4 | 0 | 1 | `0x474860` | between spr_panel_start (`91 BA`) and set_key_map (`91 BF`) |
| `92 13` | `0x48dd00` | 3 | 0 | 1 | `0x402620` | three ints → value |
| `B0 22` | `0x480dc0` | 1 | 0 | 1 | `0x46bf40` | one int → value (`B0 20..29` are environment/system strings and settings) |

Observation on the `91 69 .. 91 7D` cluster: their internal callees are the
*consecutive* functions `0x469ea0, 0x469f80, 0x469fa0, 0x469fb0, 0x46a020,
0x46a030, 0x46a050, 0x46a070, 0x46a090, 0x46a0a0, 0x46a0c0, 0x46a0e0,
0x46a0f0` in opcode order — one internal module of sibling parameter setters.
Their neighbours in the 1.647 table are `91 60..68` (effector create/delete/
show/set_vector/set_gradient/set_ripple/set_zoom) and `91 88` window_set_font,
so the cluster is most likely further effect/asset parameter setters of the
same module. Since no program uses them, no behaviour is inferred beyond the
stack shapes above; a real implementation needs the 1.647-service decompilation
(`0x469ea0 … 0x46a0f0`) if a future game uses them.

## Verification

- `tools/re/mk_opset_1520.py` prints the unnamed opcodes and their programs
  from the original and patched data (both give `0x77`/`snd.0x23` only).
- The 1.647 handler addresses were checked against `tools/re/handlers_1647.txt`
  (generated by `optables.py -v` from the same executable).
- The 1.647 `A0 21`/`A0 23` twin relationship is byte-for-byte visible in the
  two disassemblies in `build/scratch/handlers_23.txt`.
