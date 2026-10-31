/*
 * sh_engine.h - SHARD sound engine registry (C interface)
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 */
#ifndef SH_ENGINE_H_
#define SH_ENGINE_H_

#include <stdint.h>
#include "Shard/sh_params.h"

#ifdef __cplusplus
extern "C" {
#endif

/* parameter display / range types */
enum ShParamType
{
	SH_PT_NONE = 0,   /* unused slot */
	SH_PT_UNI,        /* 0..127 */
	SH_PT_BI,         /* 0..127 shown as -63..+64 */
	SH_PT_LIST,       /* 0..count-1 with 3 letter labels */
	SH_PT_ONOFF,      /* 0/1 */
};

typedef struct ShParamDesc
{
	char shortName[4];        /* 3 letters for the LCD overview */
	char longName[9];         /* up to 8 letters for edit mode */
	uint8_t type;             /* ShParamType */
	uint8_t def;              /* default value */
	uint8_t count;            /* SH_PT_LIST: number of entries */
	const char (*labels)[4];  /* SH_PT_LIST: 3 letter labels */
} ShParamDesc;

/* Values a engine sets in the common channel strip when it is selected
 * from the front panel (not when a kit is loaded). 0xFF = leave alone. */
typedef struct ShEngineDefaults
{
	uint8_t tune;
	uint8_t aegMode;
	uint8_t attack;
	uint8_t decay;
	uint8_t filterType;
	uint8_t filterFreq;
} ShEngineDefaults;

typedef struct ShEngineInfo
{
	char shortName[4];        /* shown as the ENG value, e.g. "aBD" */
	char longName[9];         /* edit mode, e.g. "PlaitBD" */
	char family[9];           /* category, e.g. "PLAITS" */
	ShParamDesc params[SH_NUM_ENGINE_PARAMS];
	ShEngineDefaults defaults;
} ShEngineInfo;

/* per block input for an engine */
typedef struct ShRenderIn
{
	float note;                         /* MIDI note incl. tune/fine/CV */
	float p[SH_NUM_ENGINE_PARAMS];      /* effective (modulated) values 0..1 */
	uint8_t idx[SH_NUM_ENGINE_PARAMS];  /* list index for SH_PT_LIST / ONOFF */
	float accent;                       /* trigger velocity 0..1 */
	uint8_t trigger;                    /* 1 = triggered at the start of this block */
	uint8_t alt;                        /* 1 = trigger came from the alternative input */
} ShRenderIn;

uint8_t sh_engineCount(void);
const ShEngineInfo* sh_engineInfo(uint8_t type);

/* (re)create the engine of a channel; called from the audio context */
void sh_engineSelect(uint8_t ch, uint8_t type);
uint8_t sh_engineCurrent(uint8_t ch);

/* render SH_BLOCK_SIZE samples, output roughly -1..1 */
void sh_engineRender(uint8_t ch, const ShRenderIn* in, float* out);

/* write the engine's parameter defaults into a channel block (used by the UI
 * when the engine is changed by hand). If withStrip is set the strip values
 * from ShEngineDefaults are written too. */
void sh_engineApplyDefaults(uint8_t type, uint8_t* block, uint8_t withStrip);

#ifdef __cplusplus
}
#endif

#endif /* SH_ENGINE_H_ */
