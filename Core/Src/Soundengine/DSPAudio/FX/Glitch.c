/*
 * Glitch.c - SHARD glitch FX, see Glitch.h
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 */
#include "Soundengine/DSPAudio/FX/Glitch.h"
#include "Soundengine/DSPAudio/FX/FxRamBuffer.h"

#include <math.h>

#define G_FRAMES ((FX_BUFFER_SIZE + 1) / 2)    /* stereo frames in the FX buffer */
#define G_MASK (G_FRAMES - 1)
#define G_RAMP (1.f / 64.f)

enum { G_IDLE = 0, G_CAPTURE, G_PLAY, G_RELEASE };
enum { A_STUTTER = 0, A_REVERSE, A_OCT_DOWN, A_OCT_UP, A_RATCHET, A_TAPESTOP, A_RANDPITCH, A_NUM };

static inline uint32_t g_rand(Glitch* g)
{
	g->rng = g->rng * 1664525u + 1013904223u;
	return g->rng >> 8;
}

static inline float g_randf(Glitch* g)
{
	return (g_rand(g) & 0xFFFF) * (1.f / 65536.f);
}

void Glitch_init(Glitch* g)
{
	g->len = 0.4f; g->chance = 0.5f; g->variety = 0.5f; g->repeats = 0.3f;
	g->pendingTrig = 0;
	g->write = 0;
	g->rng = 0x1234567u;
	g->state = G_IDLE;
	g->gain = 0.f;
}

void Glitch_setParams(Glitch* g, float len, float chance, float variety, float repeats)
{
	g->len = len; g->chance = chance; g->variety = variety; g->repeats = repeats;
}

void Glitch_trigger(Glitch* g)
{
	g->pendingTrig = 1;
}

static void startRep(Glitch* g)
{
	const float L = (float)g->sliceLen;
	g->posInRep = 0.f;
	switch(g->action)
	{
	default:
	case A_STUTTER:  g->speed = 1.f;  g->pos = 0.f; g->repLen = L; break;
	case A_REVERSE:  g->speed = -1.f; g->pos = L - 1.f; g->repLen = L; break;
	case A_OCT_DOWN: g->speed = 0.5f; g->pos = 0.f; g->repLen = L; break;
	case A_OCT_UP:   g->speed = 2.f;  g->pos = 0.f; g->repLen = L; break;
	case A_RATCHET:
	{
		/* every repeat half as long as the one before */
		float l = L;
		for(uint8_t i = 0; i < g->repIdx && l > 512.f; i++) l *= 0.5f;
		g->speed = 1.f; g->pos = 0.f; g->repLen = l;
		break;
	}
	case A_TAPESTOP: g->pos = 0.f; g->repLen = L; break;   /* speed set per sample */
	case A_RANDPITCH:
	{
		const int semis = (int)(g_rand(g) % 25) - 12;
		g->speed = exp2f(semis * (1.f / 12.f));
		g->pos = 0.f; g->repLen = L;
		break;
	}
	}
}

static void startPlayback(Glitch* g)
{
	/* the palette grows with Variety: 0 = stutter only */
	const uint8_t n = (uint8_t)(1 + g->variety * (A_NUM - 1) + 0.5f);
	g->action = (uint8_t)(g_rand(g) % (n > A_NUM ? A_NUM : n));
	g->repsLeft = (uint8_t)(1 + g->repeats * 7.f + 0.5f);
	if(g->action == A_RATCHET && g->repsLeft < 3) g->repsLeft = 3;
	g->repIdx = 0;
	g->state = G_PLAY;
	startRep(g);
}

static inline float readSlice(const Glitch* g, float p, uint8_t c)
{
	const float L = (float)g->sliceLen;
	while(p >= L) p -= L;
	while(p < 0.f) p += L;
	const uint32_t i = (uint32_t)p;
	const float frac = p - (float)i;
	const uint32_t a = (g->start + i) & G_MASK;
	const uint32_t b = (g->start + i + 1) & G_MASK;
	const float va = (float)FX_BUFFER[a * 2 + c];
	const float vb = (float)FX_BUFFER[b * 2 + c];
	return va + (vb - va) * frac;
}

static inline int16_t sat16(float x)
{
	return (int16_t)(x > 32767.f ? 32767.f : (x < -32768.f ? -32768.f : x));
}

void Glitch_process(Glitch* g, int16_t* fxBuffer, int16_t* outL, int16_t* outR, uint16_t size, uint8_t channels, float dryWet)
{
	(void)outR;
	if(g->pendingTrig)
	{
		g->pendingTrig = 0;
		if(g->state == G_IDLE && g_randf(g) < g->chance)
		{
			g->state = G_CAPTURE;
			g->start = g->write;
			g->captured = 0;
			uint32_t l = (uint32_t)(660.f + g->len * g->len * 12600.f);   /* ~15 .. 300 ms */
			if(l > G_FRAMES - 1024) l = G_FRAMES - 1024;
			g->sliceLen = l;
		}
	}

	int32_t* stereoOut = (int32_t*)outL;
	for(uint16_t i = 0; i < size; i++)
	{
		const float inL = fxBuffer[i * 2];
		const float inR = channels == 2 ? fxBuffer[i * 2 + 1] : inL;

		/* the slice must stay intact while it plays */
		if(g->state != G_PLAY)
		{
			FX_BUFFER[g->write * 2] = (__fp16)inL;
			FX_BUFFER[g->write * 2 + 1] = (__fp16)inR;
			g->write = (g->write + 1) & G_MASK;
		}

		float glL = 0.f, glR = 0.f;
		switch(g->state)
		{
		case G_CAPTURE:
			if(++g->captured >= g->sliceLen) startPlayback(g);
			break;

		case G_PLAY:
		{
			if(g->action == A_TAPESTOP)
			{
				const float total = g->repLen * (g->repIdx + g->repsLeft);
				const float done = g->repLen * g->repIdx + g->posInRep;
				g->speed = 1.f - done / total;
			}
			const float fade = g->repLen < 256.f ? g->repLen * 0.25f : 64.f;
			float env = 1.f;
			if(g->posInRep < fade) env = g->posInRep / fade;
			else if(g->repLen - g->posInRep < fade) env = (g->repLen - g->posInRep) / fade;
			glL = readSlice(g, g->pos, 0) * env;
			glR = readSlice(g, g->pos, 1) * env;
			g->pos += g->speed;
			g->posInRep += 1.f;
			if(g->posInRep >= g->repLen)
			{
				g->repIdx++;
				if(--g->repsLeft == 0) g->state = G_RELEASE;
				else startRep(g);
			}
			break;
		}

		default:
			break;
		}

		/* crossfade between the input and the glitch */
		if(g->state == G_PLAY) { g->gain += G_RAMP; if(g->gain > 1.f) g->gain = 1.f; }
		else if(g->gain > 0.f) { g->gain -= G_RAMP; if(g->gain <= 0.f) { g->gain = 0.f; if(g->state == G_RELEASE) g->state = G_IDLE; } }
		else if(g->state == G_RELEASE) g->state = G_IDLE;

		const float wL = inL + (glL - inL) * g->gain;
		const float wR = inR + (glR - inR) * g->gain;
		const int16_t oL = sat16(inL + (wL - inL) * dryWet);
		const int16_t oR = sat16(inR + (wR - inR) * dryWet);

		if(channels == 2)
		{
			const int32_t x = __PKHBT(oL, oR, 16);
			*stereoOut = __QADD16(*stereoOut, x);
			stereoOut++;
		}
		else
		{
			*outL = (int16_t)__QADD16(*outL, oL);
			outL += 2;
		}
	}
}
