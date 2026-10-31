/*
 * sh_morph.h - SHARD kit morph curves
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * The morph moves every sound parameter from the live kit (source) towards
 * the morph target kit. How far each parameter has moved for a given morph
 * amount depends on the algorithm:
 *
 *   lin  linear. Sharpness pushes past the target (up to 2x the difference),
 *        so the far end of the morph exaggerates what the target changes.
 *   snp  S-curve around the middle. Sharpness narrows the transition, at 127
 *        the kit flips almost at once.
 *   sct  scatter: every parameter has its own switch point between 12 % and
 *        88 %. Sharpness turns the soft transitions into jumps.
 *   stp  the morph amount moves in steps. Sharpness 0 = 16 steps,
 *        127 = 2 steps (a plain A/B switch).
 *
 * List parameters (engine, types, waveforms) switch where their curve passes
 * the middle.
 */
#ifndef SH_MORPH_H_
#define SH_MORPH_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum { SH_MORPH_LIN = 0, SH_MORPH_SNAP, SH_MORPH_SCATTER, SH_MORPH_STEPS, SH_NUM_MORPH_ALGS };

#define SH_MORPH_DEFAULT_ALG SH_MORPH_SNAP
#define SH_MORPH_DEFAULT_SHP 48

/* set the morph state for the coming audio block */
void sh_morphSetup(uint8_t amount, uint8_t alg, uint8_t sharpness);

/* 0 when the morph is off */
uint8_t sh_morphActive(void);

/* how far parameter paramNr has moved: 0 = source, 255 = target, more than
 * 255 = past the target (lin with sharpness) */
int16_t sh_morphPos(uint16_t paramNr);

/* morphed values */
uint8_t sh_morphContinuous(uint8_t src, uint8_t dst, uint16_t paramNr, uint8_t maxValue);
static inline uint8_t sh_morphStepped(uint8_t src, uint8_t dst, uint16_t paramNr)
{
	return sh_morphPos(paramNr) >= 128 ? dst : src;
}

#ifdef __cplusplus
}
#endif

#endif /* SH_MORPH_H_ */
