/*
 * sh_update.h - firmware update from the SD card, started from the menu
 *
 * Copyright (C) 2026 SHARD contributors.
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * The update file is the same LXRE*.img the LXR updater (bootloader) reads, so
 * the hold-the-encoder-at-power-on update keeps working as a fallback.
 *
 * Steps:
 *  1. find LXRE*.img files in the root folder of the card
 *  2. check header (magic "LXRERIMG"), size and checksum of the chosen file
 *  3. copy the firmware into the staging area at the end of the flash
 *     (sectors 6-7, 0x08080000, never used by the firmware itself) and verify
 *  4. with interrupts off, run a small routine from RAM that erases the
 *     firmware sectors 1-5, copies the staging area there, verifies and resets
 *
 * The bootloader in sector 0 is never touched. If power fails during step 4,
 * the module starts the LXR updater (hold the encoder) and the same file can
 * be flashed from the card.
 */
#ifndef SH_UPDATE_H_
#define SH_UPDATE_H_

#include <stdint.h>

#define SHUPD_MAX_FILES 8

enum ShUpdateResult
{
	SHUPD_OK = 0,
	SHUPD_ERR_NO_CARD,
	SHUPD_ERR_OPEN,
	SHUPD_ERR_HEADER,
	SHUPD_ERR_SIZE,
	SHUPD_ERR_CHECKSUM,
	SHUPD_ERR_ERASE,
	SHUPD_ERR_PROGRAM,
	SHUPD_ERR_VERIFY,
};

/* look for update files, returns how many were found (max SHUPD_MAX_FILES) */
uint8_t shupd_scan(void);

/* name of file idx (8.3 or long name, as FatFs returns it) */
const char* shupd_fileName(uint8_t idx);

/* progress output, two LCD lines of 16 characters */
typedef void (*ShUpdateProgress)(const char* line1, const char* line2);

/* check and install file idx. Only returns on an error; on success the module
 * restarts with the new firmware. */
uint8_t shupd_install(uint8_t idx, ShUpdateProgress progress);

/* the whole update dialog on the LCD (blocking, keeps the audio running) */
void shupd_menu(void);

/* text for an error code (16 characters max) */
const char* shupd_errorText(uint8_t err);

#endif /* SH_UPDATE_H_ */
