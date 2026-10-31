/*
 * sh_bridge.h - glue between the LXR firmware (menu, presets, CV inputs,
 *               mixer) and the SHARD channels
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 */
#ifndef SH_BRIDGE_H_
#define SH_BRIDGE_H_

#include <stdint.h>

#define SHARD_NAME "SHARD"

/* folder on the SD card for SHARD kits, projects and settings */
#define SH_SD_ROOT "/shard"

/* kit format version, stored in parameter 0 (PAR_NONE) of every kit */
#define SH_KIT_VERSION 2

/* a sound parameter was changed (menu, morph, kit load). fromUser = 1 when it
 * was edited on the front panel; changing the engine by hand then loads the
 * engine's default values into the channel. */
void sh_paramChanged(uint16_t paramNr, uint8_t fromUser);

/* 1 for the audio routing parameter of a channel (never morphed) */
uint8_t sh_isRoutingParam(uint16_t paramNr);

/* push all FX parameters of the current kit to the FX bus */
void sh_applyKit(void);

/* fill the sound section of a kit with the SHARD init kit */
void sh_buildInitKit(uint8_t* para);

/* CV matrix, once per audio block (called from CV_process) */
void sh_cvProcess(void);

/* kit number the morph currently points to (morph target + CV) */
uint8_t sh_morphKitNr(void);

/* value of a sound parameter in the current morph (used by "save morph") */
uint8_t sh_morphParamValue(uint16_t paramNr);

/* check a kit after loading it; converts older kit formats */
void sh_kitFixup(uint8_t* para);

/* audio CPU load */
void sh_cpuBlockStart(void);
void sh_cpuBlockEnd(void);
uint8_t sh_cpuLoadPercent(void);

/* index of an engine by its short name, 0 if not found */
uint8_t sh_engineFind(const char* shortName);

#endif /* SH_BRIDGE_H_ */
