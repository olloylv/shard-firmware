/*
 * sh_bank.h - SHARD: kit banks
 *
 * Copyright (C) 2026 the SHARD authors
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of SHARD, a modified, unofficial firmware for the Erica
 * Synths LXR Eurorack module. See LICENSE and NOTICE.md in the root of the
 * repository.
 *
 * A bank is a folder /shard/prjNN (NN = 00..99) with up to 128 kit files and
 * its name in prj.nfo. One bank is held in RAM (mainParameters); loading a
 * bank reads all its kits from the card. The current bank number is kept in
 * /shard/bank.idx, the global settings stay in /shard/prj00/glo.cfg.
 */
#ifndef SH_BANK_H_
#define SH_BANK_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SH_NUM_BANKS 100

/* boot: read the bank number, create and enter its folder. Returns the bank. */
uint8_t sh_bankBoot(void);
uint8_t sh_bankCurrent(void);
const char* sh_bankFolder(void);

/* read a bank's name into savefileNames[bank][PROJECT_NAMES] ("Empty" if none) */
void sh_bankLoadName(uint8_t bank);

/* load all kits of a bank into RAM and activate kit <kitSlot>; 0 = ok */
int sh_bankLoad(uint8_t bank, uint8_t kitSlot);

/* write all kits in RAM and the name to a bank, which becomes the current one */
int sh_bankSave(uint8_t bank);

#ifdef __cplusplus
}
#endif

#endif /* SH_BANK_H_ */
