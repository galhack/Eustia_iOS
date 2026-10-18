/*
 * This file is part of OpenBGI (https://openbgi.net).
 * SPDX-License-Identifier: GPL-2.0-only
 *
 * scriptenc.c - which encoding the compiled scripts use (inc/bgi/scriptenc.h)
 *
 * A game directory is read, never executed: the first
 * BurikoCompiledScriptVer1.00 marker of data01000.arc is located and the
 * bytes after it are classified as GBK or Shift-JIS by the codes the text
 * uses for its punctuation.  See inc/bgi/scriptenc.h for why that works.
 *
 * The sample is looked for in the raw archive first: a translation patch
 * rebuilds the archive with the scripts stored plainly, so the text starts
 * right after the index and one read is enough.  The original releases store
 * the scripts DSC-compressed, so when no plain marker is found the first
 * entries are decoded with the archive reader and searched again; a script
 * archive's entries are the scripts (the first ones are aiy00010, ...), so a
 * handful of them is all the sample needs.
 */
#include "bgi/scriptenc.h"
#include "bgi/arcread.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// the byte pairs counted per encoding (see ScriptEncoding_Classify)
static const uint16_t kGbkPairs[] = {0xA1B8, 0xA1B9, 0xA1A2, 0xA1A3};                      // 「」、。
static const uint16_t kSjisPairs[] = {0x8175, 0x8176, 0x8141, 0x8142, 0x82A0, 0x82A2, 0x82A4}; // 「」、。あいう

static int InPairs(uint16_t pair, const uint16_t* list, size_t n)
{
	size_t i;
	for(i = 0; i < n; i++)
		if(list[i] == pair)
			return 1;
	return 0;
}

/* count the pairs over the sample, stepping two bytes after a hit so the
 * second byte of a character is not read again as a lead byte */
ScriptEncoding_t ScriptEncoding_Classify(const uint8_t* sample, size_t n)
{
	size_t i = 0;
	unsigned gbk = 0, sjis = 0, minimum;
	if(!sample || n < 2)
		return SCRIPTENC_UNKNOWN;
	while(i + 1 < n)
	{
		uint16_t pair = (uint16_t)(sample[i] << 8 | sample[i + 1]);
		if(InPairs(pair, kGbkPairs, BGI_COUNTOF(kGbkPairs)))
			gbk++, i += 2;
		else if(InPairs(pair, kSjisPairs, BGI_COUNTOF(kSjisPairs)))
			sjis++, i += 2;
		else
			i++;
	}
	// random binary noise gives about one hit per 64 KiB per pair; a real dialogue sample gives thousands
	minimum = (unsigned)((n / 65536) * 12);
	if(minimum < 32)
		minimum = 32;
	if(gbk >= minimum && gbk > sjis * 4)
		return SCRIPTENC_GBK;
	if(sjis >= minimum && sjis > gbk * 4)
		return SCRIPTENC_SJIS;
	return SCRIPTENC_UNKNOWN;
}

// a byte string in a buffer, or NULL
static const uint8_t* FindBytes(const uint8_t* hay, size_t n, const char* needle)
{
	size_t m = strlen(needle), i;
	if(m == 0 || n < m)
		return NULL;
	for(i = 0; i + m <= n; i++)
		if(memcmp(hay + i, needle, m) == 0)
			return hay + i;
	return NULL;
}

// classify the text after the first marker of `data`; UNKNOWN when it holds no marker or no decisive sample
static ScriptEncoding_t ClassifyMarked(const uint8_t* data, size_t size)
{
	const uint8_t* marker = FindBytes(data, size, SCRIPTENC_MARKER);
	size_t start, sample;
	if(!marker)
		return SCRIPTENC_UNKNOWN;
	start = (size_t)(marker - data) + strlen(SCRIPTENC_MARKER);
	sample = size - start < SCRIPTENC_SAMPLE ? size - start : SCRIPTENC_SAMPLE;
	return ScriptEncoding_Classify(data + start, sample);
}

// the scripts stored plainly: one read of the start of the archive
static ScriptEncoding_t DetectPlain(const char* path)
{
	FILE* f = fopen(path, "rb");
	uint8_t* buf;
	size_t got;
	ScriptEncoding_t enc;
	if(!f)
		return SCRIPTENC_UNKNOWN;
	buf = (uint8_t*)malloc(SCRIPTENC_SCAN);
	if(!buf)
	{
		fclose(f);
		return SCRIPTENC_UNKNOWN;
	}
	got = fread(buf, 1, SCRIPTENC_SCAN, f);
	fclose(f);
	enc = ClassifyMarked(buf, got);
	free(buf);
	return enc;
}

// the scripts stored DSC-compressed (the original releases): decode what the index lists
static ScriptEncoding_t DetectCompressed(const char* path)
{
	ArcRead_t* a;
	uint32_t i;
	ScriptEncoding_t enc = SCRIPTENC_UNKNOWN;
	FILE* probe = fopen(path, "rb");
	if(!probe)
		return SCRIPTENC_UNKNOWN; // no archive: nothing to say (and no message)
	fclose(probe);
	a = ArcRead_Open(path); // prints to stderr when the file is not an archive
	if(!a)
		return SCRIPTENC_UNKNOWN;
	for(i = 0; i < a->count && i < 256 && enc == SCRIPTENC_UNKNOWN; i++)
	{
		uint32_t size = 0;
		int wasDsc = 0;
		uint8_t* data = ArcRead_Load(a, &a->entries[i], &size, &wasDsc);
		if(!data)
			continue;
		enc = ClassifyMarked(data, size);
		BGI_Free(data);
	}
	ArcRead_Close(a);
	return enc;
}

ScriptEncoding_t ScriptEncoding_Detect(const char* gameDir)
{
	char path[0x400];
	ScriptEncoding_t enc;
	if(!gameDir || !gameDir[0])
		return SCRIPTENC_UNKNOWN;
	if(gameDir[strlen(gameDir) - 1] == '/')
		snprintf(path, sizeof path, "%s%s", gameDir, SCRIPTENC_ARCHIVE);
	else
		snprintf(path, sizeof path, "%s/%s", gameDir, SCRIPTENC_ARCHIVE);
	enc = DetectPlain(path);
	if(enc == SCRIPTENC_UNKNOWN)
		enc = DetectCompressed(path);
	return enc;
}
