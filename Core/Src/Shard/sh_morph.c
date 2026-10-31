/*
 * sh_morph.c - SHARD kit morph curves, see sh_morph.h
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 */
#include "Shard/sh_morph.h"

#include <math.h>

static uint8_t mAmount;
static uint8_t mAlg;
static int32_t mSlope;      /* Q8 slope of the S-curve (snp, sct) */
static int16_t mGlobal;     /* position shared by all parameters (lin, snp, stp) */

static inline int32_t clampi(int32_t x, int32_t lo, int32_t hi) { return x < lo ? lo : (x > hi ? hi : x); }

/* S-curve around the middle with slope mSlope; keeps 0 -> 0 and 255 -> 255 */
static inline int16_t snap(int32_t x)
{
	return (int16_t)clampi(128 + (((x - 128) * mSlope) >> 8), 0, 255);
}

void sh_morphSetup(uint8_t amount, uint8_t alg, uint8_t shp)
{
	if(shp > 127) shp = 127;
	mAmount = amount;
	mAlg = alg < SH_NUM_MORPH_ALGS ? alg : SH_MORPH_LIN;
	/* slope of the S-curve: doubles every 32 steps, 1 .. ~15.6 */
	mSlope = (int32_t)(256.f * exp2f(shp * (1.f / 32.f)));

	switch(mAlg)
	{
	default:
	case SH_MORPH_LIN:
		/* up to 2x past the target at the far end */
		mGlobal = (int16_t)((int32_t)amount * (256 + 2 * shp) >> 8);
		break;
	case SH_MORPH_SNAP:
		mGlobal = snap(amount);
		break;
	case SH_MORPH_SCATTER:
		mGlobal = amount;   /* per parameter, see sh_morphPos() */
		break;
	case SH_MORPH_STEPS:
	{
		const int32_t n = 2 + (127 - shp) / 9;      /* 16 .. 2 levels */
		const int32_t q = (amount * (n - 1) + 127) / 255;
		mGlobal = (int16_t)(q * 255 / (n - 1));
		break;
	}
	}
}

uint8_t sh_morphActive(void)
{
	return mAmount != 0;
}

int16_t sh_morphPos(uint16_t paramNr)
{
	if(mAlg != SH_MORPH_SCATTER) return mGlobal;
	if(mAmount == 0) return 0;
	if(mAmount == 255) return 255;
	/* switch point of this parameter, 32 .. 223 */
	const uint32_t h = ((uint32_t)paramNr * 2654435761u) >> 24;
	const int32_t th = 32 + (int32_t)(h * 3 / 4);
	const int32_t m = mAmount;
	/* warp so that the switch point lands in the middle, then sharpen */
	const int32_t w = m <= th ? m * 128 / th : 128 + (m - th) * 127 / (255 - th);
	return snap(w);
}

uint8_t sh_morphContinuous(uint8_t src, uint8_t dst, uint16_t paramNr, uint8_t maxValue)
{
	const int32_t pos = sh_morphPos(paramNr);
	const int32_t num = ((int32_t)dst - src) * pos;
	const int32_t v = src + (num >= 0 ? (num + 127) / 255 : -((-num + 127) / 255));
	return (uint8_t)clampi(v, 0, maxValue);
}
