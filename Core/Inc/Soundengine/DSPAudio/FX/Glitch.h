/*
 * Glitch.h - SHARD glitch FX for the FX bus (replaces the ring modulator)
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * Trigger driven beat repeat. When a channel that is routed to the FX bus is
 * triggered, a glitch event starts with probability "Chance": the next
 * "Length" of audio is recorded while it plays through, then the recorded
 * slice replaces the input and is played back "Repeats" times, with an action
 * picked from the palette selected by "Variety":
 *
 *   stutter, reverse, octave down, octave up, ratchet (every repeat half as
 *   long), tape stop, random pitch steps
 *
 * Variety 0 only stutters, every step up adds the next action. The FX buffer
 * of the delay is reused (only one FX runs at a time).
 *
 *   P1 Length   15 .. 300 ms
 *   P2 Chance   0 .. 100 % per trigger
 *   P3 Variety  palette size
 *   P4 Repeats  1 .. 8
 */
#ifndef GLITCH_H_
#define GLITCH_H_

#include <stdint.h>

typedef struct GlitchStruct
{
	float len, chance, variety, repeats;   /* parameters 0..1 */
	volatile uint8_t pendingTrig;

	uint32_t write;        /* frame write position */
	uint32_t rng;

	uint8_t state;         /* 0 idle, 1 capture, 2 playback */
	uint32_t start;        /* first frame of the slice */
	uint32_t sliceLen;     /* frames */
	uint32_t captured;
	uint8_t action;
	uint8_t repsLeft;
	uint8_t repIdx;
	float pos, speed, repLen, posInRep;
	float gain;            /* crossfade dry -> glitch */
} Glitch;

void Glitch_init(Glitch* g);
void Glitch_setParams(Glitch* g, float len, float chance, float variety, float repeats);
/* from the trigger handler: a channel routed to the FX bus was triggered */
void Glitch_trigger(Glitch* g);
void Glitch_process(Glitch* g, int16_t* fxBuffer, int16_t* outL, int16_t* outR, uint16_t size, uint8_t channels, float dryWet);

#endif /* GLITCH_H_ */
