/*
 * Ringmod.h - ring modulator for the FX bus
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * SHARD 0.5 brings the ring modulator of the LXR back as FX type "rng"
 * (appended after "del", so kits with the glitch FX keep it). New code:
 *
 *   Wave  carrier: sine, triangle, saw, square, noise, pulse (25 %)
 *   P1    Freq    20 Hz .. 5.1 kHz, exponential
 *   P2    AM      0 = ring modulation, 127 = amplitude modulation
 *   P3    Spread  right carrier detuned up to +1 semitone (stereo beating)
 *   P4    Random  each hit of an FX bus channel jumps the carrier by up to
 *                 +-2 octaves around Freq
 */
#ifndef INC_SOUNDENGINE_DSPAUDIO_FX_RINGMOD_H_
#define INC_SOUNDENGINE_DSPAUDIO_FX_RINGMOD_H_

#include <stdint.h>

typedef struct RingmodStruct
{
	float freq, bias, spread, random;
	float jump;               /* carrier factor of the last random jump */
	uint32_t phaseL, phaseR;
	uint32_t incL, incR;
	uint32_t rng;
	float noiseL, noiseR;     /* sample & hold noise carrier */
	uint8_t wave;
	volatile uint8_t pendingTrig;
} Ringmod;

void Ringmod_init(Ringmod* rm);
void Ringmod_setParams(Ringmod* rm, float freq, float bias, float spread, float random);
void Ringmod_setWave(Ringmod* rm, uint8_t w);
void Ringmod_trigger(Ringmod* rm);
void Ringmod_process(Ringmod* rm, int16_t* fxBuffer, int16_t* outL, int16_t* outR, uint16_t size, uint8_t channels, float dryWet);

#endif /* INC_SOUNDENGINE_DSPAUDIO_FX_RINGMOD_H_ */
