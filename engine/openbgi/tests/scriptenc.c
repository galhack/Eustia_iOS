/*
 * This file is part of OpenBGI (https://openbgi.net).
 * SPDX-License-Identifier: GPL-2.0-only
 *
 * tests/scriptenc.c - unit test of the script-encoding detection
 *                     (src/core/scriptenc.c, declared in inc/bgi/scriptenc.h);
 *                     built as bin/test_scriptenc by `make test`
 *
 * The classifier is fed hand-made dialogue samples: GBK punctuation, the
 * same punctuation in Shift-JIS, a mixture the thresholds must reject, and
 * binary noise.  The archive detector is given a scratch data01000.arc with
 * the compiled-script marker and a GBK sample after it.
 */
#include "bgi/scriptenc.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#ifdef _WIN32
#include <direct.h>
#define MakeDir(p) _mkdir(p)
#else
#define MakeDir(p) mkdir((p), 0755)
#endif

static int gFails; // the number of failed checks so far
#define CHECK(c)                                                  \
	do                                                            \
	{                                                             \
		if(!(c))                                                  \
		{                                                         \
			printf("  FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); \
			gFails++;                                             \
		}                                                         \
	} while(0)

// `n` copies of the two-byte code `pair`
static void Fill(uint8_t* buf, size_t n, uint16_t pair)
{
	size_t i;
	for(i = 0; i + 1 < n; i += 2)
	{
		buf[i] = (uint8_t)(pair >> 8);
		buf[i + 1] = (uint8_t)pair;
	}
}

static void TestClassify(void)
{
	static uint8_t buf[0x10000];
	size_t n = sizeof buf;
	Fill(buf, n, 0xA1B8); // 「 in GBK
	CHECK(ScriptEncoding_Classify(buf, n) == SCRIPTENC_GBK);
	Fill(buf, n, 0x8175); // 「 in Shift-JIS
	CHECK(ScriptEncoding_Classify(buf, n) == SCRIPTENC_SJIS);
	memset(buf, 0, n); // binary noise: no punctuation at all
	CHECK(ScriptEncoding_Classify(buf, n) == SCRIPTENC_UNKNOWN);
	{ // a few hits in a large buffer are noise, not a dialogue
		size_t i;
		memset(buf, 0, n);
		for(i = 0; i < 16; i++)
		{
			buf[i * 2] = 0xA1;
			buf[i * 2 + 1] = 0xB8;
		}
		CHECK(ScriptEncoding_Classify(buf, n) == SCRIPTENC_UNKNOWN);
	}
	CHECK(ScriptEncoding_Classify(NULL, 0) == SCRIPTENC_UNKNOWN);
	CHECK(ScriptEncoding_Classify(buf, 1) == SCRIPTENC_UNKNOWN);
}

static void TestDetect(void)
{
	const char* tmp = getenv("BGI_TEST_TMP");
	char dir[0x400], path[0x400];
	static uint8_t arc[0x20000];
	size_t markerLen = strlen(SCRIPTENC_MARKER);
	FILE* f;
	snprintf(dir, sizeof dir, "%s/bgi_test_scriptenc", tmp ? tmp : ".");
	snprintf(path, sizeof path, "%s/%s", dir, SCRIPTENC_ARCHIVE);
	remove(path);
	rmdir(dir);
	CHECK(MakeDir(dir) == 0);
	memset(arc, 0, sizeof arc);
	memcpy(arc, "PackFile    ", 12);
	memcpy(arc + 0x1000, SCRIPTENC_MARKER, markerLen);
	Fill(arc + 0x1000 + markerLen, sizeof arc - 0x1000 - markerLen, 0xA1B8);
	f = fopen(path, "wb");
	CHECK(f != NULL);
	if(f)
	{
		CHECK(fwrite(arc, 1, sizeof arc, f) == sizeof arc);
		CHECK(fclose(f) == 0);
	}
	CHECK(ScriptEncoding_Detect(dir) == SCRIPTENC_GBK);
	// without the marker there is no text to classify (the compressed path finds
	// nothing in this hand-made index either): the detector must not guess
	arc[0x1000] = 0;
	f = fopen(path, "wb");
	CHECK(f != NULL);
	if(f)
	{
		CHECK(fwrite(arc, 1, sizeof arc, f) == sizeof arc);
		CHECK(fclose(f) == 0);
	}
	CHECK(ScriptEncoding_Detect(dir) == SCRIPTENC_UNKNOWN);
	CHECK(ScriptEncoding_Detect("") == SCRIPTENC_UNKNOWN);
	CHECK(ScriptEncoding_Detect(NULL) == SCRIPTENC_UNKNOWN);
	snprintf(path, sizeof path, "%s/no-such-dir", tmp ? tmp : ".");
	CHECK(ScriptEncoding_Detect(path) == SCRIPTENC_UNKNOWN);
	snprintf(path, sizeof path, "%s/%s", dir, SCRIPTENC_ARCHIVE);
	remove(path);
	rmdir(dir);
}

int main(void)
{
	printf("classify\n");
	TestClassify();
	printf("detect\n");
	TestDetect();
	if(gFails)
	{
		printf("%d check(s) failed\n", gFails);
		return 1;
	}
	printf("ok\n");
	return 0;
}
