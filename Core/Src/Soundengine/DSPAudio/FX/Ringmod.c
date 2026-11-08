/*
 * Ringmod.c - ring modulator for the FX bus, see Ringmod.h
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 */
#include "Soundengine/DSPAudio/FX/Ringmod.h"
#include "Soundengine/DSPAudio/FX/FxRamBuffer.h"

#include <math.h>

#define RM_SR 44140.f

enum { RW_SIN = 0, RW_TRI, RW_SAW, RW_REC, RW_NOISE, RW_PWM, RW_NUM };

static inline uint32_t rm_rand(Ringmod* rm)
{
	rm->rng = rm->rng * 1664525u + 1013904223u;
	return rm->rng;
}

static inline float rm_randf(Ringmod* rm)
{
	return (rm_rand(rm) >> 8) * (1.f / 16777216.f);
}

static inline int16_t sat16(float x)
{
	return (int16_t)(x > 32767.f ? 32767.f : (x < -32768.f ? -32768.f : x));
}

static void updateInc(Ringmod* rm)
{
	const float f = 20.f * exp2f(rm->freq * 8.f) * rm->jump;
	const float fr = f * exp2f(rm->spread * (1.f / 12.f));
	const float k = 4294967296.f / RM_SR;
	rm->incL = (uint32_t)(fminf(f, 15000.f) * k);
	rm->incR = (uint32_t)(fminf(fr, 15000.f) * k);
}

void Ringmod_init(Ringmod* rm)
{
	rm->freq = 0.5f;
	rm->bias = 0.f;
	rm->spread = 0.f;
	rm->random = 0.f;
	rm->jump = 1.f;
	rm->phaseL = rm->phaseR = 0;
	rm->rng = 0x2468ACEu;
	rm->noiseL = rm->noiseR = 0.f;
	rm->wave = RW_SIN;
	rm->pendingTrig = 0;
	updateInc(rm);
}

void Ringmod_setParams(Ringmod* rm, float freq, float bias, float spread, float random)
{
	rm->freq = freq;
	rm->bias = bias;
	rm->spread = spread;
	rm->random = random;
	if(random <= 0.f) rm->jump = 1.f;
	updateInc(rm);
}

void Ringmod_setWave(Ringmod* rm, uint8_t w)
{
	rm->wave = w < RW_NUM ? w : RW_SIN;
}

void Ringmod_trigger(Ringmod* rm)
{
	rm->pendingTrig = 1;
}

/* carrier value -1..1 for a phase; noise is handled by the caller */
static inline float carrier(uint8_t wave, uint32_t ph)
{
	const float x = (int32_t)ph * (1.f / 2147483648.f);   /* -1 .. 1 */
	switch(wave)
	{
	default:
	case RW_SIN:
	{
		const float y = 4.f * x * (1.f - fabsf(x));
		return 0.225f * (y * fabsf(y) - y) + y;
	}
	case RW_TRI: return 1.f - 2.f * fabsf(x);
	case RW_SAW: return x;
	case RW_REC: return x < 0.f ? -1.f : 1.f;
	case RW_PWM: return x < -0.5f ? 1.f : -1.f;
	}
}

void Ringmod_process(Ringmod* rm, int16_t* fxBuffer, int16_t* outL, int16_t* outR, uint16_t size, uint8_t channels, float dryWet)
{
	(void)outR;
	if(rm->pendingTrig)
	{
		rm->pendingTrig = 0;
		if(rm->random > 0.f)
		{
			/* +-2 octaves at full random */
			rm->jump = exp2f((rm_randf(rm) * 2.f - 1.f) * 2.f * rm->random);
			updateInc(rm);
		}
		rm->phaseL = rm->phaseR = 0;
	}

	const float b = rm->bias;
	const float norm = 1.f / (1.f + b);
	const uint8_t wave = rm->wave;
	int32_t* stereoOut = (int32_t*)outL;

	for(uint16_t i = 0; i < size; i++)
	{
		float mL, mR;
		const uint32_t oL = rm->phaseL, oR = rm->phaseR;
		rm->phaseL += rm->incL;
		rm->phaseR += rm->incR;
		if(wave == RW_NOISE)
		{
			/* new random value on every carrier period: band limited noise */
			if(rm->phaseL < oL) rm->noiseL = rm_randf(rm) * 2.f - 1.f;
			if(rm->phaseR < oR) rm->noiseR = rm_randf(rm) * 2.f - 1.f;
			mL = rm->noiseL;
			mR = rm->noiseR;
		}
		else
		{
			mL = carrier(wave, oL);
			mR = carrier(wave, oR);
		}
		/* 0 = ring, 1 = AM with full depth */
		mL = (mL + b) * norm;
		mR = (mR + b) * norm;

		const float inL = fxBuffer[i * 2];
		const float inR = channels == 2 ? fxBuffer[i * 2 + 1] : inL;
		const int16_t yL = sat16(inL + (inL * mL - inL) * dryWet);
		const int16_t yR = sat16(inR + (inR * mR - inR) * dryWet);

		if(channels == 2)
		{
			const int32_t x = __PKHBT(yL, yR, 16);
			*stereoOut = __QADD16(*stereoOut, x);
			stereoOut++;
		}
		else
		{
			*outL = (int16_t)__QADD16(*outL, yL);
			outL += 2;
		}
	}
}
