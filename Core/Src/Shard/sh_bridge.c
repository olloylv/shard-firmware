/*
 * sh_bridge.c - glue between the LXR firmware and the SHARD channels
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 */
#include "Shard/sh_bridge.h"
#include "Shard/sh_channel.h"
#include "Shard/sh_engine.h"
#include "Shard/sh_morph.h"
#include "Parameters.h"

#include <string.h>

#ifndef SHARD_HOST
#include "stm32f7xx_hal.h"
#include "IO/adcPots.h"
#include "Soundengine/TriggerProcessor.h"
#include "Soundengine/MIDI/MidiParser.h"
#endif
#include "Soundengine/FxBus.h"

#ifdef SHARD_HOST
/* desktop render: CV inputs at 0 V (no modulation), accents from the velocity */
static inline float adc_getCvValue(uint8_t i) { (void)i; return 0.5f; }
static inline uint8_t Trigger_getAccent(uint8_t ch) { return (uint8_t)(sh_lastVelocity(ch) * 127.f); }
#endif

extern uint8_t activeParameters[];
extern uint8_t mainParameters[NUM_KIT_SLOTS][END_OF_SOUND_PARAMETERS];

/* FX parameters that are morphed and modulated every audio block */
static const uint16_t fxCont[5] = { PAR_FX_DRY_WET, PAR_FX_P1, PAR_FX_P2, PAR_FX_P3, PAR_FX_P4 };
static float fxLast[5] = { -1.f, -1.f, -1.f, -1.f, -1.f };
static volatile uint8_t morphKitNr;

static uint8_t isContFx(uint16_t paramNr)
{
	return paramNr == PAR_FX_DRY_WET || (paramNr >= PAR_FX_P1 && paramNr <= PAR_FX_P4);
}

//------------------------------------------------------------------------
uint8_t sh_engineFind(const char* shortName)
{
	for(uint8_t i = 0; i < sh_engineCount(); i++)
		if(!strncmp(sh_engineInfo(i)->shortName, shortName, 3)) return i;
	return 0;
}

//------------------------------------------------------------------------
void sh_paramChanged(uint16_t paramNr, uint8_t fromUser)
{
	uint8_t ch, local;
	if(par_isChannelParam(paramNr, &ch, &local))
	{
		/* the strips read activeParameters themselves; only an engine change
		 * on the front panel needs work: load that engine's defaults */
		if(local == SHP_ENGINE && fromUser)
			sh_engineApplyDefaults(activeParameters[paramNr], &activeParameters[PAR_CH(ch, 0)], 1);
		return;
	}
#ifndef SHARD_HOST
	/* dry/wet and P1..P4 are applied by the audio block (morph + CV) */
	if(paramNr >= PAR_FX_TYPE && paramNr <= PAR_FX_DELAY_TYPE && !isContFx(paramNr))
		midiParser_setFxParam(paramNr, activeParameters[paramNr]);
#endif
	/* CV matrix parameters are read every block by sh_cvProcess() */
}

uint8_t sh_isRoutingParam(uint16_t paramNr)
{
	uint8_t ch, local;
	return par_isChannelParam(paramNr, &ch, &local) && local == SHP_OUT;
}

void sh_applyKit(void)
{
#ifndef SHARD_HOST
	for(uint16_t p = PAR_FX_TYPE; p <= PAR_FX_DELAY_TYPE; p++)
		if(!isContFx(p)) midiParser_setFxParam(p, activeParameters[p]);
#endif
	for(uint8_t i = 0; i < 5; i++) fxLast[i] = -1.f;
}

//------------------------------------------------------------------------
/* channel targets of kit format 1 (42 per channel, no global targets) */
static const uint8_t modTargetLocalV1[42] =
{
	SH_MODT_VOCT,
	SHP_E0 + 0,  SHP_E0 + 1,  SHP_E0 + 2,  SHP_E0 + 3,  SHP_E0 + 4,
	SHP_E0 + 5,  SHP_E0 + 6,  SHP_E0 + 7,  SHP_E0 + 8,  SHP_E0 + 9,
	SHP_E0 + 10, SHP_E0 + 11, SHP_E0 + 12, SHP_E0 + 13, SHP_E0 + 14,
	SHP_E0 + 15, SHP_E0 + 16, SHP_E0 + 17, SHP_E0 + 18, SHP_E0 + 19,
	SHP_E0 + 20, SHP_E0 + 21, SHP_E0 + 22, SHP_E0 + 23, SHP_E0 + 24,
	SHP_E0 + 25, SHP_E0 + 26, SHP_E0 + 27, SHP_E0 + 28,
	SHP_ATTACK, SHP_DECAY, SHP_SLOPE,
	SHP_FILT_FREQ, SHP_FILT_RESO, SHP_FILT_DRIVE,
	SHP_VOL, SHP_PAN, SHP_SRATE, SHP_DRIVE, SHP_BITS,
	SHP_LFO_FREQ,
};

void sh_kitFixup(uint8_t* para)
{
	if(para[PAR_NONE] < 2)
	{
		/* format 1 -> 2: new CV destination numbers */
		for(uint8_t i = 0; i < 18; i++)
		{
			const uint8_t d = para[PAR_CV_DEST_1 + i];
			uint8_t nd = 0;
			if(d >= 1 && d <= SH_NUM_CHANNELS * 42)
			{
				const uint8_t ch = (uint8_t)((d - 1) / 42);
				const uint8_t local = modTargetLocalV1[(d - 1) % 42];
				for(uint8_t t = 0; t < SH_MOD_TARGETS_PER_CH; t++)
					if(sh_modTargetLocal[t] == local) { nd = sh_modDestMake(ch, t); break; }
			}
			para[PAR_CV_DEST_1 + i] = nd;
		}
		para[PAR_NONE] = SH_KIT_VERSION;
	}
	for(uint8_t i = 0; i < SH_NUM_CV_SLOTS; i++)
	{
		if(para[PAR_CVS_DEST(i)] >= SH_NUM_MOD_DESTS) para[PAR_CVS_DEST(i)] = 0;
		if(para[PAR_CVS_AMT(i)] > 100) para[PAR_CVS_AMT(i)] = 100;
		if(para[PAR_CVS_SRC(i)] > 16) para[PAR_CVS_SRC(i)] = 0;
	}
}

//------------------------------------------------------------------------
void sh_buildInitKit(uint8_t* para)
{
	/* channel roles: 1 kick, 2 perc/tom, 3 fx, 4 snare, 5 clap, 6 hats (T7 = open) */
	static const char* const engines[SH_NUM_CHANNELS] = { "tBD", "EFM", "Crs", "aSD", "tCP", "pHH" };
	memset(para, 0, END_OF_SOUND_PARAMETERS);
	para[PAR_NONE] = SH_KIT_VERSION;
	for(uint8_t ch = 0; ch < SH_NUM_CHANNELS; ch++)
		sh_channelDefaults(&para[PAR_CH(ch, 0)], sh_engineFind(engines[ch]));
	/* EFM as a metallic perc on channel 2 */
	para[PAR_CH(1, SHP_TUNE)] = 64;
	para[PAR_CH(1, SHP_E0 + 0)] = 10;
	/* FX bus off */
	para[PAR_FX_TYPE] = 0;
	para[PAR_FX_DRY_WET] = 50;
	para[PAR_FX_P1] = para[PAR_FX_P2] = para[PAR_FX_P3] = para[PAR_FX_P4] = 64;
	/* CV matrix: all slots off; per channel CV1..5 and the channel LFO as sources */
	for(uint8_t ch = 0; ch < SH_NUM_CHANNELS; ch++)
		for(uint8_t k = 0; k < SH_CV_SLOTS_PER_CH; k++)
		{
			const uint8_t i = (uint8_t)SH_CV_SLOT(ch, k);
			para[PAR_CVS_DEST(i)] = 0;
			para[PAR_CVS_AMT(i)] = 0;
			para[PAR_CVS_SRC(i)] = (uint8_t)(k < 5 ? k : 5 + ch);
		}
}

//------------------------------------------------------------------------
/* CV input (0..1, 1 = +5 V) to semitones, using the per octave calibration of
 * the LXR firmware (floatCvToFreq) */
static float cvToSemitones(float val)
{
	static const float calibration[6] = { 0.0039f, 0.2031f, 0.403320f, 0.601074f, 0.798340f, 0.982421f };
	val += (1.f / 60.f) / 3.f;
	uint8_t oct = 0;
	while(oct < 4 && val >= calibration[oct + 1]) oct++;
	const float steps = (calibration[oct + 1] - calibration[oct]) / 12.f;
	return oct * 12.f + (val - calibration[oct]) / steps;
}

static inline float clampf01(float x) { return x < 0.f ? 0.f : (x > 1.f ? 1.f : x); }

/* morph and the continuous FX parameters, once per audio block */
static void morphAndFxBlock(const float* g)
{
	const uint8_t amount = (uint8_t)(clampf01(activeParameters[PAR_MORPH] / 255.f + g[SH_MODG_MORPH]) * 255.f + 0.5f);
	const float tm = g[SH_MODG_MTARGET] * 127.f;
	int target = activeParameters[PAR_MORPH_TARGET] + (int)(tm < 0.f ? tm - 0.5f : tm + 0.5f);
	target = target < 0 ? 0 : (target >= NUM_KIT_SLOTS ? NUM_KIT_SLOTS - 1 : target);
	const uint8_t shp = (uint8_t)(clampf01(activeParameters[PAR_SH_MORPH_SHP] / 127.f + g[SH_MODG_MSHAPE]) * 127.f + 0.5f);

	sh_morphSetup(amount, activeParameters[PAR_SH_MORPH_ALG], shp);
	morphKitNr = (uint8_t)target;
	const uint8_t* kit = mainParameters[target];
	sh_channelsMorph(amount ? &kit[PAR_CH_BASE] : 0);

	for(uint8_t k = 0; k < 5; k++)
	{
		const uint16_t par = fxCont[k];
		const uint8_t maxv = k == 0 ? 100 : 127;
		const uint8_t base = amount ? sh_morphContinuous(activeParameters[par], kit[par], par, maxv) : activeParameters[par];
		const float v = clampf01(base / (float)maxv + g[SH_MODG_FX_WET + k]);
		const float d = v - fxLast[k];
		if(d > 0.002f || d < -0.002f)
		{
			fxLast[k] = v;
			if(k == 0) fxBus.dryWet = v;
			else FxBus_setParameter((uint8_t)(k - 1), v);
		}
	}
}

uint8_t sh_morphKitNr(void)
{
	return morphKitNr;
}

uint8_t sh_morphParamValue(uint16_t paramNr)
{
	const uint8_t src = activeParameters[paramNr];
	/* the CV matrix is not morphed */
	if(!sh_morphActive() || paramNr >= PAR_CV_DEST_1) return src;
	const uint8_t* kit = mainParameters[morphKitNr];
	const uint8_t dst = kit[paramNr];
	uint8_t ch, local;
	if(par_isChannelParam(paramNr, &ch, &local))
	{
		if(local == SHP_OUT) return src;
		const uint16_t e = PAR_CH(ch, SHP_ENGINE);
		if(activeParameters[e] != kit[e])
			return sh_morphStepped(0, 1, e) ? dst : src;
		if(sh_isSteppedLocal(local, activeParameters[e]))
			return sh_morphStepped(src, dst, paramNr);
		return sh_morphContinuous(src, dst, paramNr, 127);
	}
	if(isContFx(paramNr))
		return sh_morphContinuous(src, dst, paramNr, paramNr == PAR_FX_DRY_WET ? 100 : 127);
	return sh_morphStepped(src, dst, paramNr);
}

void sh_cvProcess(void)
{
	float g[SH_MOD_GLOBALS] = { 0 };
	for(uint8_t i = 0; i < SH_NUM_CV_SLOTS; i++)
	{
		const uint8_t amt = activeParameters[PAR_CVS_AMT(i)];
		const uint8_t dest = activeParameters[PAR_CVS_DEST(i)];
		if(amt == 0 || dest == 0 || dest >= SH_NUM_MOD_DESTS) continue;
		const float amount = amt / 100.f;

		const uint8_t src = activeParameters[PAR_CVS_SRC(i)];
		float cv;
		if(src < 5)       cv = adc_getCvValue(src);
		else if(src < 11) cv = sh_lfoValue((uint8_t)(src - 5));
		else              cv = Trigger_getAccent((uint8_t)(src - 11)) / 127.f;

		if(sh_modDestIsGlobal(dest))
		{
			/* bipolar around the stored value */
			g[sh_modDestGlobal(dest)] += amount * (cv * 2.f - 1.f);
			continue;
		}

		const uint8_t ch = sh_modDestChannel(dest);
		const uint8_t local = sh_modDestLocal(dest);
		if(local == SH_MODT_VOCT)
		{
			/* 100 % = exact, quantised 1 V/oct; less scales the range */
			float semis = cvToSemitones(cv);
			if(amt >= 100) semis = (float)(int)(semis + 0.5f);
			sh_modAddPitch(ch, semis * amount);
		}
		else
		{
			/* bipolar around the stored value, as in the LXR firmware */
			sh_modAdd(ch, local, amount * (cv * 2.f - 1.f));
		}
	}
	morphAndFxBlock(g);
}

//------------------------------------------------------------------------
static uint32_t cpuStart;
static float cpuLoad;      /* smoothed, 0..1 */
static float cpuPeak;

void sh_cpuBlockStart(void)
{
#ifndef SHARD_HOST
	cpuStart = DWT->CYCCNT;
#endif
}

void sh_cpuBlockEnd(void)
{
#ifndef SHARD_HOST
	const uint32_t cycles = DWT->CYCCNT - cpuStart;
	/* cycles available for one block */
	const float budget = (float)SystemCoreClock * SH_BLOCK_SIZE / SH_SAMPLE_RATE;
	const float load = cycles / budget;
	cpuLoad += 0.01f * (load - cpuLoad);
	if(load > cpuPeak) cpuPeak = load;
	else cpuPeak *= 0.9995f;
#endif
}

uint8_t sh_cpuLoadPercent(void)
{
	/* show the decaying peak, that's what matters for dropouts */
	float v = cpuPeak > cpuLoad ? cpuPeak : cpuLoad;
	v *= 100.f;
	return (uint8_t)(v > 255.f ? 255.f : v);
}
