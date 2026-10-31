/*
 * sh_channel.h - SHARD channel strip: engine -> filter -> amp EG -> velocity
 *                -> drive -> volume -> sample rate / bit reduction
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 */
#ifndef SH_CHANNEL_H_
#define SH_CHANNEL_H_

#include <stdint.h>
#include "Shard/sh_params.h"

#ifdef __cplusplus
extern "C" {
#endif

/* params points to the parameter block of channel 1; channel n starts at
 * params + n * SH_CH_STRIDE */
void sh_channelsInit(uint8_t* params);

/* fill a channel block with the defaults of the strip and of an engine */
void sh_channelDefaults(uint8_t* block, uint8_t engine);

/* called from the trigger inputs (any context). vel 0..127 */
void sh_trigger(uint8_t ch, uint8_t vel, uint8_t alt);

/* --- per audio block, in this order ------------------------------------ */
/* 1. clear modulation, advance LFOs */
void sh_beginBlock(void);
/* 2. modulation sources add to targets (CV matrix etc.) */
void sh_modAdd(uint8_t ch, uint8_t local, float amount);   /* amount in 0..1 units of the parameter range */
void sh_modAddPitch(uint8_t ch, float semitones);
/* 3. render one channel; buf receives SH_BLOCK_SIZE samples after the strip */
void sh_channelRender(uint8_t ch, int16_t* buf);

/* morph towards another kit: target points to channel 1 of that kit's
 * parameters (same layout as the live ones), amount 0..255, 0 = off */
/* morph target: channel 1 block of the target kit, or NULL. The amount and
 * curve are set with sh_morphSetup() (sh_morph.h). */
void sh_channelsMorph(const uint8_t* target);

/* peak level meter (screensaver): enable, then read and reset per frame */
void sh_meterEnable(uint8_t on);

/* 1 for list parameters (switch instead of interpolating when morphing) */
uint8_t sh_isSteppedLocal(uint8_t local, uint8_t engine);
uint16_t sh_meterTake(uint8_t ch);

/* mixer helpers */
uint8_t sh_channelRouting(uint8_t ch);
void sh_channelPan(uint8_t ch, float* left, float* right);

/* mod sources */
float sh_lfoValue(uint8_t ch);      /* 0..1 */
float sh_lastVelocity(uint8_t ch);  /* 0..1 */

/* for the UI: is the amp EG of this channel still running */
uint8_t sh_channelActive(uint8_t ch);

#ifdef __cplusplus
}
#endif

#endif /* SH_CHANNEL_H_ */
