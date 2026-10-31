/*
 * sh_ui.h - SHARD menu helpers: names, value texts and ranges of the channel
 *           parameters, which depend on the engine selected on a channel.
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 */
#ifndef SH_UI_H_
#define SH_UI_H_

#include <stdint.h>

/* 1 if the parameter is drawn by the SHARD helpers (dtype DTYPE_SH) */
uint8_t shui_handles(uint16_t parNr);

/* 0 for engine slots the current engine doesn't use (shown blank, not selectable) */
uint8_t shui_isUsed(uint16_t parNr);

/* 3 character short name, not terminated */
void shui_shortName(uint16_t parNr, char* out3);

/* edit mode: 16 character top row (category + long name) */
void shui_editTop(uint16_t parNr, char* row16);

/* 3 character value text, not terminated */
void shui_valueShort(uint16_t parNr, uint8_t value, char* out3);

/* edit mode: 16 character bottom row */
void shui_editBottom(uint16_t parNr, uint8_t value, char* row16);

/* largest allowed value */
uint8_t shui_maxValue(uint16_t parNr);

/* CV matrix destination texts (value of PAR_CV_DEST_x) */
void shui_modDestShort(uint8_t dest, char* out3);
void shui_modDestFull(uint8_t dest, char* row16);

/* 1 if the destination can be selected (global, V/Oct or a slot in use) */
uint8_t shui_modDestValid(uint8_t dest);
/* move |inc| selectable destinations up or down, skipping unused slots */
uint8_t shui_modDestStep(uint8_t cur, int16_t inc);

#endif /* SH_UI_H_ */
