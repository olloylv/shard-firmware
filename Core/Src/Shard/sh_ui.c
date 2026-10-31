/*
 * sh_ui.c - SHARD menu helpers
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 */
#include "Shard/sh_ui.h"
#include "Shard/sh_engine.h"
#include "Shard/sh_bridge.h"
#include "Parameters.h"

#include <string.h>

extern uint8_t activeParameters[];

typedef struct
{
	char shortName[4];
	char longName[9];
	char cat[4];
	uint8_t type;           /* ShParamType or one of the special types below */
	uint8_t max;
	const char (*labels)[4];
} StripParam;

enum { SPT_NOTE = 100, SPT_ENGINE };

static const char aegModes[][4]   = { "AD ", "off" };
static const char filterNames[][4] = { "off", "LP ", "HP ", "BP ", "UBP", "Nch", "Pk ", "LP2" };
static const char outNames[][4]    = { "St1", "St2", "L1 ", "R1 ", "L2 ", "R2 ", "FX " };
static const char lfoWaves[][4]    = { "sin", "tri", "sup", "sdn", "sqr", "rnd", "xup", "xdn" };
static const char retrigNames[][4] = { "off", "c1 ", "c2 ", "c3 ", "c4 ", "c5 ", "c6 " };
static const char noteNames[][3]   = { "C ", "C#", "D ", "D#", "E ", "F ", "F#", "G ", "G#", "A ", "A#", "B " };

/* strip parameters, indexed by local parameter number (engine slots excluded) */
static const StripParam stripParams[SHP_LOCAL_COUNT] =
{
	[SHP_ENGINE]     = { "Eng", "Engine",   "OSC", SPT_ENGINE, 0, 0 },
	[SHP_TUNE]       = { "Tun", "Tune",     "OSC", SPT_NOTE, 127, 0 },
	[SHP_FINE]       = { "Fin", "Fine",     "OSC", SH_PT_BI, 127, 0 },
	[SHP_ATTACK]     = { "Atk", "Attack",   "AEG", SH_PT_UNI, 127, 0 },
	[SHP_DECAY]      = { "Dec", "Decay",    "AEG", SH_PT_UNI, 127, 0 },
	[SHP_SLOPE]      = { "Slp", "Slope",    "AEG", SH_PT_UNI, 127, 0 },
	[SHP_REPEAT]     = { "Rep", "Repeat",   "AEG", SH_PT_UNI, 15, 0 },
	[SHP_DECAY_ALT]  = { "DcA", "DecayAlt", "AEG", SH_PT_UNI, 127, 0 },
	[SHP_VELVOL]     = { "Vel", "VelToVol", "AEG", SH_PT_ONOFF, 1, 0 },
	[SHP_AEG_MODE]   = { "Mod", "Mode",     "AEG", SH_PT_LIST, 1, aegModes },
	[SHP_FILT_FREQ]  = { "Frq", "Cutoff",   "FLT", SH_PT_UNI, 127, 0 },
	[SHP_FILT_RESO]  = { "Res", "Reso",     "FLT", SH_PT_UNI, 127, 0 },
	[SHP_FILT_TYPE]  = { "Typ", "Type",     "FLT", SH_PT_LIST, SH_NUM_FILTER_TYPES - 1, filterNames },
	[SHP_FILT_DRIVE] = { "Drv", "Drive",    "FLT", SH_PT_UNI, 127, 0 },
	[SHP_VOL]        = { "Vol", "Volume",   "MIX", SH_PT_UNI, 127, 0 },
	[SHP_PAN]        = { "Pan", "Pan",      "MIX", SH_PT_BI, 127, 0 },
	[SHP_SRATE]      = { "SR ", "SampRate", "MIX", SH_PT_UNI, 127, 0 },
	[SHP_DRIVE]      = { "Drv", "Drive",    "MIX", SH_PT_UNI, 127, 0 },
	[SHP_OUT]        = { "Out", "Output",   "MIX", SH_PT_LIST, 6, outNames },
	[SHP_BITS]       = { "Bit", "BitCrush", "MIX", SH_PT_UNI, 127, 0 },
	[SHP_LFO_FREQ]   = { "Frq", "LFO Freq", "LFO", SH_PT_UNI, 127, 0 },
	[SHP_LFO_OFFSET] = { "Ofs", "LFO Phas", "LFO", SH_PT_UNI, 127, 0 },
	[SHP_LFO_WAVE]   = { "Wav", "LFO Wave", "LFO", SH_PT_LIST, 7, lfoWaves },
	[SHP_LFO_RETRIG] = { "Rtg", "Retrig",   "LFO", SH_PT_LIST, 6, retrigNames },
};

//------------------------------------------------------------------------
static void putNum(char* out3, int v)
{
	/* right aligned, 3 characters, -99..999 */
	char b[4] = "   ";
	uint8_t neg = v < 0;
	if(neg) v = -v;
	int i = 2;
	do { b[i--] = (char)('0' + v % 10); v /= 10; } while(v && i >= 0);
	if(neg && i >= 0) b[i] = '-';
	memcpy(out3, b, 3);
}

static void putNote(char* out3, uint8_t note)
{
	memcpy(out3, noteNames[note % 12], 2);
	const int oct = note / 12 - 1;
	out3[2] = oct < 0 ? '-' : (char)('0' + oct);
}

static void putText(char* dst, const char* src, uint8_t n)
{
	uint8_t i = 0;
	for(; i < n && src[i]; i++) dst[i] = src[i];
	for(; i < n; i++) dst[i] = ' ';
}

//------------------------------------------------------------------------
/* description of a channel parameter: either an engine slot or a strip param */
typedef struct
{
	uint8_t ch, local;
	const ShParamDesc* engine;   /* engine slot, or NULL */
	const StripParam* strip;     /* strip param, or NULL */
	const ShEngineInfo* info;
} ParInfo;

static uint8_t lookup(uint16_t parNr, ParInfo* pi)
{
	uint8_t ch, local;
	if(!par_isChannelParam(parNr, &ch, &local)) return 0;
	pi->ch = ch;
	pi->local = local;
	pi->info = sh_engineInfo(activeParameters[PAR_CH(ch, SHP_ENGINE)]);
	if(local >= SHP_E0 && local <= SHP_E_LAST)
	{
		pi->engine = &pi->info->params[local - SHP_E0];
		pi->strip = 0;
	}
	else
	{
		pi->engine = 0;
		pi->strip = &stripParams[local];
	}
	return 1;
}

uint8_t shui_handles(uint16_t parNr)
{
	uint8_t ch, local;
	return par_isChannelParam(parNr, &ch, &local)
		|| parNr == PAR_SH_UPDATE || parNr == PAR_SH_CPU;
}

uint8_t shui_isUsed(uint16_t parNr)
{
	ParInfo pi;
	if(!lookup(parNr, &pi)) return 1;
	if(pi.engine) return pi.engine->type != SH_PT_NONE;
	return 1;
}

//------------------------------------------------------------------------
void shui_shortName(uint16_t parNr, char* out3)
{
	/* lower case like the LXR names; the menu capitalises the selected one */
	if(parNr == PAR_SH_UPDATE) { memcpy(out3, "upd", 3); return; }
	if(parNr == PAR_SH_CPU) { memcpy(out3, "cpu", 3); return; }
	ParInfo pi;
	if(!lookup(parNr, &pi)) { memcpy(out3, "   ", 3); return; }
	putText(out3, pi.engine ? pi.engine->shortName : pi.strip->shortName, 3);
	for(uint8_t i = 0; i < 3; i++)
		if(out3[i] >= 'A' && out3[i] <= 'Z') out3[i] = (char)(out3[i] + 32);
}

void shui_editTop(uint16_t parNr, char* row16)
{
	memset(row16, ' ', 16);
	if(parNr == PAR_SH_UPDATE) { memcpy(row16, "Firmware Update", 15); return; }
	if(parNr == PAR_SH_CPU) { memcpy(row16, "Audio CPU load", 14); return; }
	ParInfo pi;
	if(!lookup(parNr, &pi)) return;
	/* "C1 aBD  Decay   " or "C1 FLT  Cutoff  " */
	row16[0] = 'C';
	row16[1] = (char)('1' + pi.ch);
	if(pi.engine)
	{
		putText(&row16[3], pi.info->shortName, 3);
		putText(&row16[8], pi.engine->longName, 8);
	}
	else
	{
		putText(&row16[3], pi.strip->cat, 3);
		putText(&row16[8], pi.strip->longName, 8);
	}
}

//------------------------------------------------------------------------
static void formatTyped(uint8_t type, uint8_t value, uint8_t count, const char (*labels)[4], char* out3)
{
	switch(type)
	{
	case SH_PT_BI:    putNum(out3, (int)value - 64); break;
	case SH_PT_ONOFF: memcpy(out3, value ? "on " : "off", 3); break;
	case SH_PT_LIST:
		if(labels && value < count) putText(out3, labels[value], 3);
		else putNum(out3, value);
		break;
	case SH_PT_NONE:  memcpy(out3, "   ", 3); break;
	default:          putNum(out3, value); break;
	}
}

void shui_valueShort(uint16_t parNr, uint8_t value, char* out3)
{
	if(parNr == PAR_SH_UPDATE) { memcpy(out3, "go ", 3); return; }
	if(parNr == PAR_SH_CPU) { putNum(out3, sh_cpuLoadPercent()); return; }
	ParInfo pi;
	if(!lookup(parNr, &pi)) { memcpy(out3, "   ", 3); return; }
	if(pi.engine)
	{
		formatTyped(pi.engine->type, value, pi.engine->count, pi.engine->labels, out3);
		return;
	}
	switch(pi.strip->type)
	{
	case SPT_ENGINE: putText(out3, sh_engineInfo(value)->shortName, 3); break;
	case SPT_NOTE:   putNote(out3, value); break;
	default:
		formatTyped(pi.strip->type, value, (uint8_t)(pi.strip->max + 1), pi.strip->labels, out3);
		break;
	}
}

void shui_editBottom(uint16_t parNr, uint8_t value, char* row16)
{
	memset(row16, ' ', 16);
	if(parNr == PAR_SH_UPDATE) { memcpy(row16, "push encoder", 12); return; }
	ParInfo pi;
	if(lookup(parNr, &pi) && pi.strip && pi.strip->type == SPT_ENGINE)
	{
		/* "PLAITS   AnalogBD" */
		const ShEngineInfo* info = sh_engineInfo(value);
		putText(&row16[0], info->family, 7);
		putText(&row16[8], info->longName, 8);
		return;
	}
	shui_valueShort(parNr, value, &row16[13]);
}

//------------------------------------------------------------------------
uint8_t shui_maxValue(uint16_t parNr)
{
	if(parNr == PAR_SH_UPDATE || parNr == PAR_SH_CPU) return 0;
	ParInfo pi;
	if(!lookup(parNr, &pi)) return 127;
	if(pi.engine)
	{
		switch(pi.engine->type)
		{
		case SH_PT_LIST:  return (uint8_t)(pi.engine->count - 1);
		case SH_PT_ONOFF: return 1;
		case SH_PT_NONE:  return 0;
		default:          return 127;
		}
	}
	if(pi.strip->type == SPT_ENGINE) return (uint8_t)(sh_engineCount() - 1);
	return pi.strip->max;
}

//------------------------------------------------------------------------
void shui_modDestShort(uint8_t dest, char* out3)
{
	if(dest == 0 || dest >= SH_NUM_MOD_DESTS) { memcpy(out3, "off", 3); return; }
	const uint8_t ch = sh_modDestChannel(dest);
	const uint8_t local = sh_modDestLocal(dest);
	/* first character: channel number, then two letters of the name */
	out3[0] = (char)('1' + ch);
	if(local == SH_MODT_VOCT) { memcpy(&out3[1], "VO", 2); return; }
	char name[3];
	shui_shortName(PAR_CH(ch, local), name);
	out3[1] = name[0];
	out3[2] = name[1] == ' ' ? name[2] : name[1];
}

void shui_modDestFull(uint8_t dest, char* row16)
{
	memset(row16, ' ', 16);
	if(dest == 0 || dest >= SH_NUM_MOD_DESTS) { memcpy(row16, "off", 3); return; }
	const uint8_t ch = sh_modDestChannel(dest);
	const uint8_t local = sh_modDestLocal(dest);
	if(local == SH_MODT_VOCT)
	{
		row16[0] = 'C'; row16[1] = (char)('1' + ch);
		memcpy(&row16[3], "PITCH", 5);
		memcpy(&row16[8], "1V/Oct", 6);
		return;
	}
	char top[16];
	shui_editTop(PAR_CH(ch, local), top);
	memcpy(row16, top, 16);
}
