/*
 * sh_bank.c - SHARD: kit banks
 *
 * Copyright (C) 2026 the SHARD authors
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * This file is part of SHARD, a modified, unofficial firmware for the Erica
 * Synths LXR Eurorack module. See LICENSE and NOTICE.md in the root of the
 * repository.
 */
#include "Shard/sh_bank.h"
#include "Shard/sh_bridge.h"

#include "Preset/PresetManager.h"
#include "menu/menu.h"
#include "Parameters.h"
#include "lcd.h"
#include "../../Middlewares/Third_Party/FatFs/src/ff.h"

#include <stdio.h>
#include <string.h>


static uint8_t current;
static char folder[24];
static FIL bankFile;

static void makeFolder(uint8_t bank, char* out)
{
	sprintf(out, SH_SD_ROOT "/prj%02u", (unsigned)bank);
}

static int enterFolder(uint8_t bank)
{
	FILINFO fno;
	char path[24];
	makeFolder(bank, path);
	if(f_stat(path, &fno) != FR_OK && f_mkdir(path) != FR_OK) return -1;
	if(f_chdir(path) != FR_OK) return -1;
	strcpy(folder, path);
	current = bank;
	return 0;
}

static void saveIndex(void)
{
	UINT n;
	if(f_open(&bankFile, SH_SD_ROOT "/bank.idx", FA_CREATE_ALWAYS | FA_WRITE) != FR_OK) return;
	f_write(&bankFile, &current, 1, &n);
	f_close(&bankFile);
}

uint8_t sh_bankBoot(void)
{
	uint8_t bank = 0;
	UINT n = 0;
	char path[24];
	FILINFO fno;
	/* the global settings live in bank 00: it always exists */
	makeFolder(0, path);
	if(f_stat(path, &fno) != FR_OK) f_mkdir(path);
	if(f_open(&bankFile, SH_SD_ROOT "/bank.idx", FA_OPEN_EXISTING | FA_READ) == FR_OK)
	{
		if(f_read(&bankFile, &bank, 1, &n) != FR_OK || n != 1 || bank >= SH_NUM_BANKS) bank = 0;
		f_close(&bankFile);
	}
	if(enterFolder(bank) != 0) enterFolder(0);
	return current;
}

uint8_t sh_bankCurrent(void) { return current; }
const char* sh_bankFolder(void) { return folder; }

void sh_bankLoadName(uint8_t bank)
{
	char path[40];
	char* name = savefileNames[bank][PROJECT_NAMES];
	UINT n = 0;
	makeFolder(bank, path);
	strcat(path, "/prj.nfo");
	if(f_open(&bankFile, path, FA_OPEN_EXISTING | FA_READ) == FR_OK)
	{
		f_read(&bankFile, name, 8, &n);
		f_close(&bankFile);
	}
	if(n != 8 || preset_isNameEmpty(name)) sprintf(name, "Empty");
}

static void progress(const char* what, uint8_t bank, int i)
{
	char line[17];
	if(i == 0)
	{
		lcd_clear();
		lcd_home();
		sprintf(line, "%s bank %02u", what, (unsigned)bank);
		lcd_string(line);
	}
	if((i & 7) == 0)
	{
		sprintf(line, "%3d%%", i * 100 / NUM_KIT_SLOTS);
		lcd_setcursor(0, 2);
		lcd_string(line);
	}
}

int sh_bankLoad(uint8_t bank, uint8_t kitSlot)
{
	if(bank >= SH_NUM_BANKS) return -1;
	lcd_process_display_interrupt = 0;
	if(enterFolder(bank) != 0)
	{
		lcd_process_display_interrupt = 1;
		return -1;
	}
	for(int i = 0; i < NUM_KIT_SLOTS; i++)
	{
		progress("Load", bank, i);
		preset_loadDrumsetSD((uint8_t)i);
	}
	saveIndex();
	sh_bankLoadName(bank);
	if(kitSlot >= NUM_KIT_SLOTS) kitSlot = 0;
	preset_loadDrumsetRam(kitSlot, 0, 1);
	menu_loadedPresetNr[CURRENT_KIT] = kitSlot;
	menu_selectedPresetNr[SAVE_TYPE_KIT] = kitSlot;
	lcd_process_display_interrupt = 1;
	return 0;
}

int sh_bankSave(uint8_t bank)
{
	if(bank >= SH_NUM_BANKS) return -1;
	lcd_process_display_interrupt = 0;
	if(enterFolder(bank) != 0)
	{
		lcd_process_display_interrupt = 1;
		return -1;
	}
	int err = 0;
	for(int i = 0; i < NUM_KIT_SLOTS; i++)
	{
		progress("Save", bank, i);
		if(preset_saveDrumsetSD((uint8_t)i, 0) != FR_OK) err = -1;
	}
	UINT n;
	if(f_open(&bankFile, "prj.nfo", FA_CREATE_ALWAYS | FA_WRITE) == FR_OK)
	{
		f_write(&bankFile, savefileNames[bank][PROJECT_NAMES], 8, &n);
		f_close(&bankFile);
	}
	saveIndex();
	lcd_process_display_interrupt = 1;
	return err;
}
