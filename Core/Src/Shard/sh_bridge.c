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
#include "Parameters.h"

#include <string.h>

#ifndef SHARD_HOST
#include "stm32f7xx_hal.h"
#include "IO/adcPots.h"
#include "Soundengine/TriggerProcessor.h"
#include "Soundengine/MIDI/MidiParser.h"
#include "Soundengine/ModMatrix_Processor.h"
#endif

extern uint8_t activeParameters[];

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
	if(paramNr >= PAR_FX_TYPE && paramNr <= PAR_FX_DELAY_TYPE)
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
		midiParser_setFxParam(p, activeParameters[p]);
#endif
}

//------------------------------------------------------------------------
void sh_buildInitKit(uint8_t* para)
{
	static const char* const engines[SH_NUM_CHANNELS] = { "tBD", "aSD", "EFM", "tCP", "Crs", "pHH" };
	memset(para, 0, END_OF_SOUND_PARAMETERS);
	para[PAR_NONE] = SH_KIT_VERSION;
	for(uint8_t ch = 0; ch < SH_NUM_CHANNELS; ch++)
		sh_channelDefaults(&para[PAR_CH(ch, 0)], sh_engineFind(engines[ch]));
	/* EFM as a metallic perc on channel 3 */
	para[PAR_CH(2, SHP_TUNE)] = 64;
	para[PAR_CH(2, SHP_E0 + 0)] = 10;
	/* FX bus off */
	para[PAR_FX_TYPE] = 0;
	para[PAR_FX_DRY_WET] = 50;
	para[PAR_FX_P1] = para[PAR_FX_P2] = para[PAR_FX_P3] = para[PAR_FX_P4] = 64;
	/* CV matrix: all slots off, CV1..5 as sources */
	for(uint8_t i = 0; i < 18; i++)
	{
		para[PAR_CV_DEST_1 + i] = 0;
		para[PAR_CV_MOD_AMT_1 + i] = 0;
		para[PAR_CV_SRC_1 + i] = (uint8_t)(i % 5);
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

void sh_cvProcess(void)
{
#ifndef SHARD_HOST
	for(uint8_t i = 0; i < NUM_MOD_SLOTS; i++)
	{
		const uint8_t amt = activeParameters[PAR_CV_MOD_AMT_1 + i];
		const uint8_t dest = activeParameters[PAR_CV_DEST_1 + i];
		if(amt == 0 || dest == 0 || dest >= SH_NUM_MOD_DESTS) continue;
		const float amount = amt / 100.f;

		const uint8_t src = activeParameters[PAR_CV_SRC_1 + i];
		float cv;
		if(src < 5)       cv = adc_getCvValue(src);
		else if(src < 11) cv = sh_lfoValue((uint8_t)(src - 5));
		else              cv = Trigger_getAccent((uint8_t)(src - 11)) / 127.f;

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
#endif
}

//------------------------------------------------------------------------
void sh_morphSet(const uint8_t* targetKit, uint8_t amount)
{
	sh_channelsMorph(targetKit ? &targetKit[PAR_CH_BASE] : 0, amount);
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
