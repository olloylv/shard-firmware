/*
 * Cc2Text.c
 *
 * Created: 16.02.2013 14:34:59
 *  Author: Julian
 *
 * Copyright (C) 2012-2026 Erica Synths
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of the LXR firmware. It is licensed under the GNU General
 * Public License version 3, with the additional permission and terms in
 * NOTICE.md. See LICENSE and NOTICE.md in the root of the repository.
 */ 
#include "menu/CcNr2Text.h"
/*
 * SHARD: the LXR mod target tables (one fixed list of targets per voice) are
 * gone. A CV matrix destination is now a channel plus one of the parameters
 * in sh_modTargetLocal[] (Shard/sh_params.h); the menu draws them with
 * shui_modDest*() from Shard/sh_ui.c. The functions below are kept for the
 * remaining callers.
 */
#include "menu/CcNr2Text.h"
#include "menu/menu.h"
#include "Shard/sh_params.h"

const ModTarg modTargets[] = { { TEXT_EMPTY, PAR_NONE } };
const ModTargetVoiceOffset modTargetVoiceOffsets[6] = { { 0, 0 } };
uint8_t paramToModTarget[END_OF_SOUND_PARAMETERS];

uint8_t getModTargetGapIndex(uint8_t modTargetIdx) { (void)modTargetIdx; return 0; }
uint8_t getModTargetIdxFromGapIdx(uint8_t v, uint8_t gapidx) { (void)v; (void)gapidx; return 0; }
uint8_t getNumModTargets() { return SH_NUM_MOD_DESTS; }
void paramToModTargetInit() { }

uint8_t voiceFromModTargValue(uint8_t val)
{
	if(val == 0 || val >= SH_NUM_MOD_DESTS) return 0;
	return (uint8_t)(sh_modDestChannel(val) + 1);
}
