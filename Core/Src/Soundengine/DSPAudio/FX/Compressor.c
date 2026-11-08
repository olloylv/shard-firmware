/*
 * Compressor.c
 *
 *  Created on: Aug 27, 2020
 *      Author: julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */

#include "Soundengine/DSPAudio/FX/Compressor.h"
#include "math.h"
#include "main.h"


enum
{
	RATIO_1,
	RATIO_2,
	RATIO_3,
	RATIO_4,
	RATIO_6,
	RATIO_8
};

static const double DC_OFFSET = 1.0E-25;

void Compressor_init(Compressor *c)
{
	c->attack = 0.1;
	c->release = 300;

	//c->filter = 0.0;
	c->env = 0.0;
	c->tresh = 3;
	c->markupGain = 1.0f;

}

//att/release, time in ms to reach 63% of final value
void Compressor_setAttack(Compressor *c, float a)
{
	c->attack = 0.03f + a *100.f; //[ms]
	c->attack = exp( -1000.0 / ( c->attack * REAL_FS ) );
}
void Compressor_setTreshold(Compressor *c, float t)
{
	c->tresh = -96 + t*96; //[-96:0]dB
}

void Compressor_setGain(Compressor *c, float g)
{
	c->markupGain = 1.f + g*2;
}
void Compressor_setRelease(Compressor *c, float r)
{
	c->release = 25+r*175.f; //[ms]
	c->release = exp( -1000.0 / ( c->release * REAL_FS ) );
}

void Compressor_setRatio(Compressor *c, uint8_t r)
{
	switch(r)
	{
	default:
	case RATIO_1:
		c->ratio = 1.0f;
		break;

	case RATIO_2:
		c->ratio = 0.5f;
		break;
	case RATIO_3:
		c->ratio = 1.f/3.f;
		break;
	case RATIO_4:
		c->ratio = 0.25f;
		break;
	case RATIO_6:
		c->ratio = 1.f/6.f;
		break;
	case RATIO_8:
		c->ratio = 0.125f;
		break;
	}
}

/* SHARD 0.5: the gain computer runs in float with fast log2/exp2 instead of
 * double logf/expf per sample (about 1/6 of the audio block on the STM32).
 * Same curve: dB domain, peak detector, attack/release on the over-threshold
 * level. Error of the approximations about 0.01 dB. */
#define DB_PER_LOG2 6.0205999f		/* 20 * log10(2) */

static inline float fastLog2(float x)
{
	union { float f; uint32_t i; } v = { x };
	const float e = (float)(int32_t)((v.i >> 23) & 0xFF) - 127.f;
	v.i = (v.i & 0x007FFFFF) | 0x3F800000;	/* mantissa in [1,2) */
	const float m = v.f;
	/* log2(m) on [1,2), 3rd order minimax */
	return e + ((0.15392465f * m - 1.0295584f) * m + 3.010851f) * m - 2.1338866f;
}

static inline float fastExp2(float x)
{
	if(x < -60.f) return 0.f;
	if(x > 60.f) x = 60.f;
	const float fl = floorf(x);
	const float f = x - fl;					/* [0,1) */
	/* 2^f on [0,1), 3rd order */
	const float p = ((0.07902041f * f + 0.22412837f) * f + 0.69683624f) * f + 0.99981246f;
	union { float f; uint32_t i; } v;
	v.i = (uint32_t)((int32_t)fl + 127) << 23;
	return p * v.f;
}

void Compressor_process(Compressor *c, int16_t *fxBuffer,int16_t* outL, int16_t* outR, uint16_t size,  uint8_t channels, float dryWet)
{
	(void)outR;
	int32_t* stereoOut = (int32_t*)outL;
	const float tresh = c->tresh;
	const float att = c->attack;
	const float rel = c->release;
	const float slope = (c->ratio - 1.f) * (1.f / DB_PER_LOG2);	/* dB -> log2 of the gain */
	const float makeup = c->markupGain;
	float env = (float)c->env;

	for(uint8_t i = 0; i < size; i++)
	{
		const int16_t l = fxBuffer[i*2];
		const int16_t r = channels == 2 ? fxBuffer[i*2+1] : l;
		const float in = channels == 2 ? (l + r) * (0.5f / 32768.f) : l * (1.f / 32768.f);
		const float peakdB = DB_PER_LOG2 * fastLog2(fabsf(in) + (float)DC_OFFSET);
		float overdB = peakdB - tresh;
		if(overdB < 0.f) overdB = 0.f;

		/* attack or release */
		const float coeff = overdB > env ? att : rel;
		env = overdB + coeff * (env - overdB);

		const float g = (env > 1e-4f ? fastExp2(env * slope) : 1.f) * makeup;

		if(channels == 2)
		{
			const int16_t wl = (int16_t)__SSAT((int32_t)(l * g), 16);
			const int16_t wr = (int16_t)__SSAT((int32_t)(r * g), 16);
			const int32_t x = __PKHBT(l + __SSAT((int32_t)((wl - l) * dryWet), 16), r + __SSAT((int32_t)((wr - r) * dryWet), 16), 16);
			*stereoOut = __QADD16(*stereoOut, x);
			stereoOut++;
		}
		else
		{
			const int16_t wl = (int16_t)__SSAT((int32_t)(l * g), 16);
			const int16_t dw = (int16_t)(l + __SSAT((int32_t)((wl - l) * dryWet), 16));
			*outL = (int16_t)__QADD16(*outL, dw);
			outL += 2;
		}
	}
	c->env = env;
}

