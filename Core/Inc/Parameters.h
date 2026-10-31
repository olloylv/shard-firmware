/*
 * Parameters.h
 *
 * Created: 27.07.2012 16:48:46
 *  Author: Julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */ 


#ifndef PARAMETERS_H_
#define PARAMETERS_H_

#define FOLLOW_PATTERN 0x2
#define FOLLOW_BAR 0x1

#define NUM_KIT_SLOTS 128 //64

#include "stm32f7xx_hal.h"

#include "Shard/sh_params.h"

/* SHARD parameter map
 *
 * The sound section starts with 6 identical channel blocks (see
 * Shard/sh_params.h for the layout of a block), followed by the FX bus and the
 * CV matrix. Everything from END_OF_SOUND_PARAMETERS on is unchanged from the
 * LXR firmware.
 */
#define PAR_CH_BASE 1
#define PAR_CH(ch, local) (PAR_CH_BASE + (ch) * SH_CH_STRIDE + (local))
#define PAR_CH_END PAR_CH(SH_NUM_CHANNELS, 0)

/* is paramNr inside the channel blocks; if so return channel and local index */
static inline uint8_t par_isChannelParam(uint16_t paramNr, uint8_t* ch, uint8_t* local)
{
	if(paramNr < PAR_CH_BASE || paramNr >= PAR_CH_END) return 0;
	const uint16_t rel = (uint16_t)(paramNr - PAR_CH_BASE);
	*ch = (uint8_t)(rel / SH_CH_STRIDE);
	*local = (uint8_t)(rel % SH_CH_STRIDE);
	return *local < SHP_LOCAL_COUNT;
}

enum ParamEnums
{
	PAR_NONE = 0,

	/* 1 .. PAR_CH_END-1: channel blocks */

	PAR_FX_TYPE = PAR_CH_END,
	PAR_FX_ROUTING,
	PAR_FX_DRY_WET,
	PAR_FX_DIST_TYPE,
	PAR_FX_P1,
	PAR_FX_P2,
	PAR_FX_P3,
	PAR_FX_P4,
	PAR_FX_RATIO,
	PAR_FX_WAVE,
	PAR_FX_REVERB_TYPE,
	PAR_FX_DELAY_TYPE,
	PAR_MORPH_KIT_DEST,
/*ATTENTION kit load routine ignores everything following PAR_CV_DEST_1, when CV saving is set to global!!!!*/
	PAR_CV_DEST_1,
	PAR_CV_DEST_2,
	PAR_CV_DEST_3,
	PAR_CV_DEST_4,
	PAR_CV_DEST_5,
	PAR_CV_DEST_6,
	PAR_CV_DEST_7,
	PAR_CV_DEST_8,
	PAR_CV_DEST_9,
	PAR_CV_DEST_10,
	PAR_CV_DEST_11,
	PAR_CV_DEST_12,
	PAR_CV_DEST_13,
	PAR_CV_DEST_14,
	PAR_CV_DEST_15,
	PAR_CV_DEST_16,
	PAR_CV_DEST_17,
	PAR_CV_DEST_18,
	PAR_CV_MOD_AMT_1,
	PAR_CV_MOD_AMT_2,
	PAR_CV_MOD_AMT_3,
	PAR_CV_MOD_AMT_4,
	PAR_CV_MOD_AMT_5,
	PAR_CV_MOD_AMT_6,
	PAR_CV_MOD_AMT_7,
	PAR_CV_MOD_AMT_8,
	PAR_CV_MOD_AMT_9,
	PAR_CV_MOD_AMT_10,
	PAR_CV_MOD_AMT_11,
	PAR_CV_MOD_AMT_12,
	PAR_CV_MOD_AMT_13,
	PAR_CV_MOD_AMT_14,
	PAR_CV_MOD_AMT_15,
	PAR_CV_MOD_AMT_16,
	PAR_CV_MOD_AMT_17,
	PAR_CV_MOD_AMT_18,
	PAR_CV_SRC_1,
	PAR_CV_SRC_2,
	PAR_CV_SRC_3,
	PAR_CV_SRC_4,
	PAR_CV_SRC_5,
	PAR_CV_SRC_6,
	PAR_CV_SRC_7,
	PAR_CV_SRC_8,
	PAR_CV_SRC_9,
	PAR_CV_SRC_10,
	PAR_CV_SRC_11,
	PAR_CV_SRC_12,
	PAR_CV_SRC_13,
	PAR_CV_SRC_14,
	PAR_CV_SRC_15,
	PAR_CV_SRC_16,
	PAR_CV_SRC_17,
	PAR_CV_SRC_18,
	//#########################################
	//######## End of sound Parameters ########
	//#########################################
	//all parameters in this section are only there to be referenced from the menu
	//they are not saved anywhere
	END_OF_SOUND_PARAMETERS,
	PAR_ROLL= END_OF_SOUND_PARAMETERS,
	PAR_MORPH,

	PAR_ACTIVE_STEP, 					/*230*/
	PAR_STEP_VOLUME,
	PAR_STEP_PROB,
	PAR_STEP_NOTE,
	
	PAR_EUKLID_LENGTH,
	PAR_EUKLID_STEPS,
	PAR_EUKLID_ROTATION,
	
	PAR_AUTOM_TRACK,
	
	// these are now indices into modTargets
	PAR_P1_DEST,
	PAR_P2_DEST,
	
	PAR_P1_VAL,							/*240*/
	PAR_P2_VAL,
	
	PAR_SHUFFLE,

	PAR_UNUSED,				// auto -> switch kits with pattern, off -> pattern change won't change kit
	PAR_PATTERN_NEXT,				//  - UNUSED
	
	PAR_TRACK_LENGTH,
	
	UNUSED_PAR_GLO_SAT,						//  - global saturation
	PAR_POS_Y,						//  - UNUSED
	PAR_FLUX,						//  - UNUSED
	PAR_SOM_FREQ,					//  - UNUSED
	PAR_TRACK_ROTATION,				// **PATROT

	PAR_STEP_FLAM,
	PAR_STEP_SHIFT,

	
	//#########################################
	//######## Global Parameters ##############
	//#########################################
	PAR_SH_UPDATE,					// SHARD: firmware update from the SD card (menu action)
	PAR_SH_CPU,						// SHARD: audio CPU load display
	PAR_SH_MORPH_ALG,				// SHARD: morph algorithm (sh_morph.h)
	PAR_SH_MORPH_SHP,				// SHARD: morph sharpness
	PAR_BEGINNING_OF_GLOBALS, //a placeholder to mark the beginning of the global var space not present in morph and not needed in the seq
	//global params
	PAR_BPM = PAR_BEGINNING_OF_GLOBALS,	/*250*/
	

	
	PAR_MIDI_CHAN_1,
	PAR_MIDI_CHAN_2,
	PAR_MIDI_CHAN_3,
	PAR_MIDI_CHAN_4,
	PAR_MIDI_CHAN_5,
	PAR_MIDI_CHAN_6,

	PAR_CV_SAVE,							// bool - UNUSED
	PAR_FOLLOW,							// bool
	
	
	PAR_QUANTISATION,					// UNUSED
	
	PAR_SCREENSAVER_ON_OFF,				// bool /*260*/
	PAR_MIDI_MODE,						// unused now
	PAR_MIDI_CHAN_7,
	PAR_MIDI_ROUTING,
	PAR_MIDI_FILT_TX,
	PAR_MIDI_FILT_RX,
	//prescaler control for trigger IO extension
	PAR_PRESCALER_CLOCK_IN,
	PAR_PRESCALER_CLOCK_OUT1,
	PAR_PRESCALER_CLOCK_OUT2,			//  - UNUSED
	PAR_TRIG_GATE_MODE,					//  - UNUSED

	PAR_BAR_RESET_MODE,					// bool 0 or 1   /*270*/
	PAR_MIDI_CHAN_GLOBAL,				// global midi channel
	// midi note - This is a note value that is sent when the track triggers, if it's 0 it means that
		// it will trigger the note that is specified on the step (PAR_STEP_NOTE). If it is non-zero then
		// PAR_STEP_NOTE is ignored and this note is sent instead
	//moved to globals

	PAR_MIDI_NOTE1,
	PAR_MIDI_NOTE2,
	PAR_MIDI_NOTE3,
	PAR_MIDI_NOTE4,
	PAR_MIDI_NOTE5,
	PAR_MIDI_NOTE6,
	PAR_MIDI_NOTE7,

	PAR_PATTERN_MODE,

	PAR_MORPH_TARGET, //which kit to morph to

	NUM_PARAMS	
};




#endif /* PARAMETERS_H_ */
