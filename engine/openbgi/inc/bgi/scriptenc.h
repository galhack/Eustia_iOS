/*
 * This file is part of OpenBGI (https://openbgi.net).
 * SPDX-License-Identifier: GPL-2.0-only
 *
 * scriptenc.h - the text encoding of the game's compiled scripts
 *               (src/core/scriptenc.c)
 *
 * The original releases store the dialogue of a BurikoCompiledScriptVer1.00
 * container as Shift-JIS; translation patches keep the container and the byte
 * layout and store GBK (the Chinese patches) or the same Shift-JIS.  The
 * engine cannot tell from the archive names - a translated game directory
 * looks exactly like the original one - so the extracted text is sampled and
 * the punctuation it uses decides.  The Apple host uses this to switch the
 * text decoder of the font backend (inc/bgi/apple_host.h, "chinese"); the
 * same detection backs --list= style tools or a launcher's language guess.
 */
#ifndef BGI_SCRIPTENC_H_
#define BGI_SCRIPTENC_H_

#include "bgi/common.h"

typedef enum ScriptEncoding
{
	SCRIPTENC_UNKNOWN = 0, // not enough of a sample to tell
	SCRIPTENC_SJIS = 1,    // the original Japanese scripts
	SCRIPTENC_GBK = 2      // the Chinese patch
} ScriptEncoding_t;

#define SCRIPTENC_ARCHIVE "data01000.arc"          // where the scripts (and their text) live
#define SCRIPTENC_MARKER  "BurikoCompiledScriptVer1.00" // the compiled-script container announced at the start of every script
#define SCRIPTENC_SCAN    (8u << 20)               // bytes read in search of the marker and the sample
#define SCRIPTENC_SAMPLE  (2u << 20)               // bytes classified

/* Classify a byte sample by the two-byte codes it uses for the dialogue
 * punctuation: GBK has 「」、。 at A1 B8 / A1 B9 / A1 A2 / A1 A3, Shift-JIS
 * the same characters at 81 75 / 81 76 / 81 41 / 81 42 (and its kana at
 * 82 A0 / 82 A2 / 82 A4).  Binary tables hit a given pair about once per
 * 64 KiB, a real dialogue sample thousands of times, so a clear and
 * size-scaled lead is required. */
ScriptEncoding_t ScriptEncoding_Classify(const uint8_t* sample, size_t n);

/* The encoding of the scripts in `gameDir`'s data01000.arc; UNKNOWN when the
 * archive cannot be read or the sample is ambiguous.  `gameDir` may end with
 * a '/'. */
ScriptEncoding_t ScriptEncoding_Detect(const char* gameDir);

#endif // BGI_SCRIPTENC_H_
