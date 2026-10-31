/*
 * sh_update.c - firmware update from the SD card, started from the menu
 *
 * Copyright (C) 2026 SHARD contributors.
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * See Shard/sh_update.h for the procedure. Flash layout of the STM32F765VG
 * (1 MB, single bank):
 *
 *   sector 0     0x08000000  32 KB  LXR bootloader (never touched)
 *   sector 1-3   0x08008000  96 KB  \
 *   sector 4     0x08020000 128 KB   > firmware, max 480 KB
 *   sector 5     0x08040000 256 KB  /
 *   sector 6-7   0x08080000 512 KB  staging area for the update
 */
#include "Shard/sh_update.h"
#include "Shard/sh_bridge.h"

#include <string.h>
#include <stdio.h>

#include "main.h"
#include "fatfs.h"
#include "lcd.h"
#include "encoder.h"
#include "Soundengine/config.h"
#include "Soundengine/cs4344_cs5343.h"

#define APP_ADDRESS      0x08008000u
#define APP_MAX_SIZE     (0x08080000u - APP_ADDRESS)   /* sectors 1-5: 480 KB */
#define STAGE_ADDRESS    0x08080000u
#define HEADER_SIZE      16
#define IMAGE_MAGIC      "LXRERIMG"
#define CHUNK            2048

extern TIM_HandleTypeDef htim2;

static char fileNames[SHUPD_MAX_FILES][13];
static uint8_t numFiles;
static FIL file;
static uint8_t chunk[CHUNK] __attribute__((aligned(4)));

//------------------------------------------------------------------------
uint8_t shupd_scan(void)
{
	DIR dir;
	FILINFO fno;
	numFiles = 0;
	FRESULT res = f_findfirst(&dir, &fno, "/", "LXRE*.IMG");
	while(res == FR_OK && fno.fname[0] && numFiles < SHUPD_MAX_FILES)
	{
		if(!(fno.fattrib & AM_DIR))
		{
			memcpy(fileNames[numFiles], fno.fname, sizeof(fileNames[0]) - 1);
			fileNames[numFiles][12] = 0;
			numFiles++;
		}
		res = f_findnext(&dir, &fno);
	}
	f_closedir(&dir);
	return numFiles;
}

const char* shupd_fileName(uint8_t idx)
{
	return idx < numFiles ? fileNames[idx] : "";
}

const char* shupd_errorText(uint8_t err)
{
	switch(err)
	{
	case SHUPD_OK:            return "ok";
	case SHUPD_ERR_NO_CARD:   return "no SD card";
	case SHUPD_ERR_OPEN:      return "can't open file";
	case SHUPD_ERR_HEADER:    return "not an LXR image";
	case SHUPD_ERR_SIZE:      return "wrong size";
	case SHUPD_ERR_CHECKSUM:  return "checksum error";
	case SHUPD_ERR_ERASE:     return "erase error";
	case SHUPD_ERR_PROGRAM:   return "write error";
	case SHUPD_ERR_VERIFY:    return "verify error";
	default:                  return "error";
	}
}

//------------------------------------------------------------------------
/* single bank mode and no write protection on sectors 1-7 */
static uint8_t flashLayoutOk(void)
{
	const uint32_t optcr = FLASH->OPTCR;
#ifdef FLASH_OPTCR_nDBANK
	if(!(optcr & FLASH_OPTCR_nDBANK)) return 0;      /* dual bank: other sector map */
#endif
	const uint32_t nwrp = (optcr & FLASH_OPTCR_nWRP) >> FLASH_OPTCR_nWRP_Pos;
	return (nwrp & 0xFE) == 0xFE;                     /* 1 = not protected */
}

static uint8_t eraseSector(uint32_t sector)
{
	FLASH_EraseInitTypeDef erase;
	uint32_t badSector = 0;
	erase.TypeErase = FLASH_TYPEERASE_SECTORS;
	erase.Sector = sector;
	erase.NbSectors = 1;
	erase.VoltageRange = FLASH_VOLTAGE_RANGE_3;
	return HAL_FLASHEx_Erase(&erase, &badSector) == HAL_OK;
}

static void show(ShUpdateProgress progress, const char* l1, const char* l2)
{
	if(progress) progress(l1, l2);
}

//------------------------------------------------------------------------
/* Runs from ITCM with interrupts off: erase sectors 1-5, copy the staging
 * area to the firmware area, reset. Must not call anything in flash. */
__attribute__((section(".itcm_text"), noinline, noreturn))
static void copyStagingAndReset(uint32_t size)
{
	volatile FLASH_TypeDef* const flash = FLASH;

	/* wait, unlock */
	while(flash->SR & FLASH_SR_BSY) { }
	if(flash->CR & FLASH_CR_LOCK)
	{
		flash->KEYR = 0x45670123u;
		flash->KEYR = 0xCDEF89ABu;
	}
	flash->SR = FLASH_SR_EOP | FLASH_SR_OPERR | FLASH_SR_WRPERR | FLASH_SR_PGAERR | FLASH_SR_PGPERR | FLASH_SR_ERSERR;

	/* erase sectors 1..5 (x32 parallelism) */
	for(uint32_t sector = 1; sector <= 5; sector++)
	{
		flash->CR = FLASH_CR_PSIZE_1 | FLASH_CR_SER | (sector << FLASH_CR_SNB_Pos);
		flash->CR |= FLASH_CR_STRT;
		__DSB();
		while(flash->SR & FLASH_SR_BSY) { }
	}
	flash->CR = 0;

	/* program word by word */
	volatile uint32_t* dst = (volatile uint32_t*)APP_ADDRESS;
	const volatile uint32_t* src = (const volatile uint32_t*)STAGE_ADDRESS;
	const uint32_t words = (size + 3) / 4;
	flash->CR = FLASH_CR_PSIZE_1 | FLASH_CR_PG;
	for(uint32_t i = 0; i < words; i++)
	{
		dst[i] = src[i];
		__DSB();
		while(flash->SR & FLASH_SR_BSY) { }
	}
	flash->CR = FLASH_CR_LOCK;
	__DSB();

	/* system reset */
	SCB->AIRCR = (0x5FAUL << SCB_AIRCR_VECTKEY_Pos) | SCB_AIRCR_SYSRESETREQ_Msk;
	__DSB();
	while(1) { }
}

//------------------------------------------------------------------------
uint8_t shupd_install(uint8_t idx, ShUpdateProgress progress)
{
	if(idx >= numFiles) return SHUPD_ERR_OPEN;
	if(!flashLayoutOk()) return SHUPD_ERR_ERASE;

	char path[16];
	snprintf(path, sizeof(path), "/%s", fileNames[idx]);

	/* --- 1. header and checksum, nothing written yet ------------------- */
	show(progress, "Checking file", fileNames[idx]);
	if(f_open(&file, path, FA_OPEN_EXISTING | FA_READ) != FR_OK) return SHUPD_ERR_OPEN;

	UINT n = 0;
	uint8_t header[HEADER_SIZE];
	if(f_read(&file, header, HEADER_SIZE, &n) != FR_OK || n != HEADER_SIZE || memcmp(header, IMAGE_MAGIC, 8))
	{
		f_close(&file);
		return SHUPD_ERR_HEADER;
	}
	const uint32_t size = header[8] | (header[9] << 8) | (header[10] << 16) | ((uint32_t)header[11] << 24);
	const uint8_t checksum = header[12];
	if(size == 0 || size > APP_MAX_SIZE || f_size(&file) != size + HEADER_SIZE)
	{
		f_close(&file);
		return SHUPD_ERR_SIZE;
	}
	uint32_t sum = 0;
	for(uint32_t done = 0; done < size; done += n)
	{
		if(f_read(&file, chunk, CHUNK, &n) != FR_OK || n == 0) { f_close(&file); return SHUPD_ERR_OPEN; }
		for(UINT i = 0; i < n; i++) sum += chunk[i];
	}
	if((uint8_t)(0xFF - (sum & 0xFF)) != checksum)
	{
		f_close(&file);
		return SHUPD_ERR_CHECKSUM;
	}

	/* --- 2. stop audio ------------------------------------------------- */
	HAL_TIM_Base_Stop_IT(&htim2);
	memset(dma_buffer, 0, sizeof(dma_buffer));
	memset(dma_buffer2, 0, sizeof(dma_buffer2));

	/* --- 3. staging area: erase, write, verify ------------------------- */
	show(progress, "Erasing staging", "please wait");
	HAL_FLASH_Unlock();
	if(!eraseSector(FLASH_SECTOR_6) || !eraseSector(FLASH_SECTOR_7))
	{
		HAL_FLASH_Lock();
		f_close(&file);
		return SHUPD_ERR_ERASE;
	}

	f_lseek(&file, HEADER_SIZE);
	char line[17];
	uint32_t address = STAGE_ADDRESS;
	for(uint32_t done = 0; done < size; done += n)
	{
		if(f_read(&file, chunk, CHUNK, &n) != FR_OK || n == 0)
		{
			HAL_FLASH_Lock();
			f_close(&file);
			return SHUPD_ERR_OPEN;
		}
		/* pad the last word with 0xFF */
		for(UINT i = n; i < ((n + 3u) & ~3u); i++) chunk[i] = 0xFF;
		for(UINT i = 0; i < n; i += 4)
		{
			uint32_t w;
			memcpy(&w, &chunk[i], 4);
			if(HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, address, w) != HAL_OK)
			{
				HAL_FLASH_Lock();
				f_close(&file);
				return SHUPD_ERR_PROGRAM;
			}
			address += 4;
		}
		snprintf(line, sizeof(line), "%3lu%%", (unsigned long)((done + n) * 100 / size));
		show(progress, "Writing", line);
	}
	HAL_FLASH_Lock();
	f_close(&file);

	/* the D-cache may hold the erased contents */
	SCB_CleanInvalidateDCache();
	sum = 0;
	for(uint32_t i = 0; i < size; i++) sum += *(const volatile uint8_t*)(STAGE_ADDRESS + i);
	if((uint8_t)(0xFF - (sum & 0xFF)) != checksum) return SHUPD_ERR_VERIFY;

	/* --- 4. point of no return ----------------------------------------- */
	show(progress, "Installing...", "don't power off");
	HAL_Delay(200);
	__disable_irq();
	SCB_DisableDCache();
	SCB_DisableICache();
	copyStagingAndReset(size);
}

//------------------------------------------------------------------------
// Menu: choose a file with the encoder, push twice to install
//------------------------------------------------------------------------
#include "Soundengine/Soundengine.h"

static void lcdLines(const char* l1, const char* l2)
{
	char b1[17], b2[17];
	snprintf(b1, sizeof(b1), "%-16s", l1);
	snprintf(b2, sizeof(b2), "%-16s", l2);
	lcd_home();
	lcd_string(b1);
	lcd_setcursor(0, 2);
	lcd_string(b2);
}

/* keeps the audio running while the menu waits for the user */
static void idle(void)
{
	soundengine_process();
}

static void waitRelease(void)
{
	while(encode_readButton()) idle();
}

/* 1 = pushed, 0 = turned */
static uint8_t waitPushOrTurn(int8_t* inc)
{
	while(1)
	{
		idle();
		const int8_t i = encode_read4();
		if(i) { *inc = i; return 0; }
		if(encode_readButton()) { waitRelease(); return 1; }
	}
}

void shupd_menu(void)
{
	lcd_clear();
	lcdLines("Firmware update", "scanning SD...");
	const uint8_t n = shupd_scan();
	waitRelease();
	if(!n)
	{
		lcdLines("No LXRE*.IMG", "on the SD card");
		for(uint32_t t = HAL_GetTick(); HAL_GetTick() - t < 2000; ) idle();
		return;
	}

	uint8_t sel = 0;    /* 0..n-1 files, n = cancel */
	while(1)
	{
		lcdLines("Update: turn,", sel < n ? shupd_fileName(sel) : "<cancel>");
		int8_t inc = 0;
		if(!waitPushOrTurn(&inc))
		{
			sel = (uint8_t)((sel + n + 1 + inc) % (n + 1));
			continue;
		}
		if(sel == n) return;

		/* confirm */
		lcdLines(shupd_fileName(sel), "push=install");
		if(!waitPushOrTurn(&inc)) continue;

		const uint8_t err = shupd_install(sel, lcdLines);
		/* only returns on an error */
		lcd_clear();
		lcdLines("Update failed:", shupd_errorText(err));
		for(uint32_t t = HAL_GetTick(); HAL_GetTick() - t < 3000; ) idle();
		return;
	}
}
