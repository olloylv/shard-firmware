/*
 * sh_params.h - SHARD channel parameter layout
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * SHARD is a modified, unofficial firmware for the Erica Synths LXR Eurorack
 * module. It is not made, approved or supported by Erica Synths.
 *
 * Every one of the 6 channels has the same block of parameters. The engine
 * slots (SHP_E0 ... SHP_E28) are interpreted by the engine selected with
 * SHP_ENGINE; everything else (amp EG, filter, mixer, LFO) is the common
 * channel strip that is identical for all engines.
 *
 * All values are stored as uint8_t, like the original LXR parameters:
 *  - continuous parameters use 0..127
 *  - list parameters store the list index (0..count-1)
 */
#ifndef SH_PARAMS_H_
#define SH_PARAMS_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SH_NUM_CHANNELS        6
#define SH_NUM_ENGINE_PARAMS   29   /* E0..E28 */
#define SH_BLOCK_SIZE          64   /* = OUTPUT_DMA_SIZE (USE_BIG_SAMPLE_BUFFER) */
#define SH_SAMPLE_RATE         44140.0f

/* Local parameter index inside a channel block.
 * Menu sub pages:
 *   OSC: ENGINE TUNE FINE E0  E1  E2  E3  E4
 *   MOD: E5  ... E12
 *   FM : E13 ... E20
 *   SMP: E21 ... E28
 *   AEG: ATTACK DECAY SLOPE REPEAT DECAY_ALT VELVOL AEG_MODE
 *   FLT: FREQ RESO TYPE DRIVE
 *   MIX: VOL PAN SRATE DRIVE OUT BITS
 *   LFO: FREQ OFFSET WAVE RETRIG
 */
enum ShLocalParam
{
	SHP_ENGINE = 0,
	SHP_TUNE,          /* MIDI note 0..127 */
	SHP_FINE,          /* 64 = 0 cents, +-64 cents */
	SHP_E0,
	SHP_E_LAST = SHP_E0 + SH_NUM_ENGINE_PARAMS - 1,

	SHP_ATTACK,
	SHP_DECAY,
	SHP_SLOPE,
	SHP_REPEAT,        /* 0 = off, 1..n = number of clap style repeats */
	SHP_DECAY_ALT,     /* decay used by the alternative trigger (T7 -> channel 6) */
	SHP_VELVOL,        /* on/off: velocity scales volume */
	SHP_AEG_MODE,      /* list: 0 = AD, 1 = OFF (engine has its own envelope) */

	SHP_FILT_FREQ,
	SHP_FILT_RESO,
	SHP_FILT_TYPE,     /* list: OFF LP HP BP UBP NOT PEA LP2 */
	SHP_FILT_DRIVE,

	SHP_VOL,
	SHP_PAN,           /* 0..127, 63 = centre */
	SHP_SRATE,         /* sample rate reduction, 127 = full rate */
	SHP_DRIVE,         /* waveshaper amount */
	SHP_OUT,           /* list: output routing, see mixer.h */
	SHP_BITS,          /* 0 = off, then fewer and fewer bits */

	SHP_LFO_FREQ,
	SHP_LFO_OFFSET,
	SHP_LFO_WAVE,      /* list: SIN TRI SUP SDN SQR RND EUP EDN */
	SHP_LFO_RETRIG,    /* list: OFF, CH1..CH6 */

	SHP_LOCAL_COUNT
};

/* stride between two channel blocks in the global parameter array */
#define SH_CH_STRIDE 56
#if defined(__cplusplus)
static_assert(SHP_LOCAL_COUNT <= SH_CH_STRIDE, "channel block too large");
#else
_Static_assert(SHP_LOCAL_COUNT <= SH_CH_STRIDE, "channel block too large");
#endif

/* AEG modes */
enum { SH_AEG_AD = 0, SH_AEG_OFF, SH_NUM_AEG_MODES };

/* Filter types: index 0 is "off", 1.. map to filterTypeEnum of ResonantFilter.h */
#define SH_NUM_FILTER_TYPES 8

/* Modulation targets (CV matrix destinations).
 * A destination value is 0 (none) or 1 + ch * SH_MOD_TARGETS_PER_CH + t,
 * where t indexes sh_modTargetLocal[]. The special target SH_MODT_VOCT adds
 * exact 1V/oct pitch instead of modulating a stored parameter. */
#define SH_MOD_TARGETS_PER_CH 42
#define SH_MODT_VOCT 0xFF
#define SH_NUM_MOD_DESTS (1 + SH_NUM_CHANNELS * SH_MOD_TARGETS_PER_CH)
extern const uint8_t sh_modTargetLocal[SH_MOD_TARGETS_PER_CH];

static inline uint8_t sh_modDestChannel(uint8_t dest) { return (uint8_t)((dest - 1) / SH_MOD_TARGETS_PER_CH); }
static inline uint8_t sh_modDestLocal(uint8_t dest) { return sh_modTargetLocal[(dest - 1) % SH_MOD_TARGETS_PER_CH]; }
static inline uint8_t sh_modDestMake(uint8_t ch, uint8_t t) { return (uint8_t)(1 + ch * SH_MOD_TARGETS_PER_CH + t); }

#ifdef __cplusplus
}
#endif

#endif /* SH_PARAMS_H_ */
