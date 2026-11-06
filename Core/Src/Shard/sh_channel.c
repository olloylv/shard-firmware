/*
 * sh_channel.c - SHARD channel strip
 *
 * Copyright (C) 2026 SHARD contributors, based on the LXR firmware
 * (C) 2012-2026 Erica Synths.
 * SPDX-License-Identifier: GPL-3.0-only
 *
 * The strip reuses the LXR DSP blocks (SVF, SlopeEg2, distortion, one pole
 * smoothing, sample rate reduction) in the order of the original voices, so
 * the classic engines sound as before and every new engine gets the same
 * processing.
 */
#include "Shard/sh_channel.h"
#include "Shard/sh_morph.h"
#include "Shard/sh_engine.h"

#include <math.h>
#include <string.h>

#include "Soundengine/DSPAudio/SlopeEg2.h"
#include "Soundengine/DSPAudio/ResonantFilter.h"
#include "Soundengine/DSPAudio/distortion.h"
#include "Soundengine/DSPAudio/1PoleLp.h"
#include "Soundengine/DSPAudio/BufferTools.h"
#include "Soundengine/DSPAudio/random.h"
#include "Soundengine/FxBus.h"

#define SH_LFO_SR (SH_SAMPLE_RATE / (float)SH_BLOCK_SIZE)
#define SH_LFO_MAX_F 200.f

/* the parameters of a channel that the CV matrix can reach */
const uint8_t sh_modTargetLocal[SH_MOD_TARGETS_PER_CH] =
{
	SH_MODT_VOCT,
	SHP_E0 + 0,  SHP_E0 + 1,  SHP_E0 + 2,  SHP_E0 + 3,  SHP_E0 + 4,
	SHP_E0 + 5,  SHP_E0 + 6,  SHP_E0 + 7,  SHP_E0 + 8,  SHP_E0 + 9,
	SHP_E0 + 10, SHP_E0 + 11, SHP_E0 + 12, SHP_E0 + 13,
	SHP_ATTACK, SHP_DECAY, SHP_SLOPE,
	SHP_FILT_FREQ, SHP_FILT_RESO, SHP_FILT_DRIVE,
	SHP_VOL, SHP_PAN, SHP_SRATE, SHP_DRIVE, SHP_BITS,
	SHP_LFO_FREQ,
};

/* channel targets added in 0.5, numbered after all of the above */
const uint8_t sh_modExtLocal[SH_MOD_EXT_PER_CH] = { SHP_RING_AMT, SHP_RING_FREQ };

typedef struct
{
	uint32_t phase;
	uint32_t phaseInc;
	float value;
	float rnd;
} ShLfo;

typedef struct
{
	/* amp EG */
	SlopeEg2 aeg;
	float gainNow, gainLast;
	uint8_t altActive;

	ResonantFilter filter;
	Distortion dist;
	OnePoleFilter volSmooth;

	float panL, panR;

	float decimRate, decimCnt;
	int16_t decimHold;
	uint8_t bitShift;

	ShLfo lfo;

	/* ring modulator carrier */
	uint32_t ringPhase, ringInc;

	float velocity;
	float pitchMod;
	float mod[SHP_LOCAL_COUNT];
	float last[SHP_LOCAL_COUNT];      /* change detection of effective values */

	volatile uint8_t trigPending;
	volatile uint8_t trigAlt;
	volatile uint8_t trigVel;
} ShChannel;

static ShChannel channels[SH_NUM_CHANNELS];
static uint8_t* paramBase;
static const uint8_t* morphTarget;
static uint8_t meterOn;
static uint16_t meterPeak[SH_NUM_CHANNELS];
/* last output block of every channel, carrier of the ring modulators.
 * Channels rendered later in the block deliver the previous block (1.45 ms). */
static int16_t lastOut[SH_NUM_CHANNELS][SH_BLOCK_SIZE];

static inline uint8_t* block(uint8_t ch) { return paramBase + ch * SH_CH_STRIDE; }

static inline float clamp01(float x) { return x < 0.f ? 0.f : (x > 1.f ? 1.f : x); }

static inline uint8_t toItg(float x) { return (uint8_t)(clamp01(x) * 127.f + 0.5f); }

/* exponential full range filter frequency, as valueShaperF2F(f, FILTER_SHAPER) */
static inline float filterShape(float v)
{
	const float shape = -0.9f;
	const float k = 2 * shape / (1.0001f - shape);
	return (1 + k) * v / (1 + k * fabsf(v));
}

//------------------------------------------------------------------------
static float lfo_calc(ShLfo* lfo, uint8_t waveform)
{
	const uint32_t old = lfo->phase;
	lfo->phase += lfo->phaseInc;
	const uint8_t overflow = old > lfo->phase;
	const float x = lfo->phase / 4294967296.f;
	switch(waveform)
	{
	default:
	case 0: return 0.5f + 0.5f * sinf(x * 6.2831853f);
	case 1: return 1.f - fabsf(x * 2.f - 1.f);
	case 2: return x;
	case 3: return 1.f - x;
	case 4: return lfo->phase > 0x7fffffff ? 1.f : 0.f;
	case 5:
		if(overflow) lfo->rnd = GetRngValue() / 4294967296.f;
		return lfo->rnd;
	case 6: return x * x * x;
	case 7: { const float y = 1.f - x; return y * y * y; }
	}
}

//------------------------------------------------------------------------
static void channel_init(uint8_t ch)
{
	ShChannel* c = &channels[ch];
	memset(c, 0, sizeof(*c));
	slopeEg2_init(&c->aeg);
	SVF_init(&c->filter);
	initOnePole(&c->volSmooth);
	setOnePoleCoef(&c->volSmooth, 0.01);
	initOnePole(&c->dist.DriveParamFilter);
	setOnePoleCoef(&c->dist.DriveParamFilter, 0.01);
	setDistortionShape(&c->dist, 0.f);
	c->decimRate = 1.f;
	c->panL = c->panR = 0.7071f;
	for(int i = 0; i < SHP_LOCAL_COUNT; i++) c->last[i] = -1.f;
}

void sh_channelsInit(uint8_t* params)
{
	paramBase = params;
	for(uint8_t ch = 0; ch < SH_NUM_CHANNELS; ch++)
	{
		channel_init(ch);
		sh_engineSelect(ch, block(ch)[SHP_ENGINE]);
	}
}

//------------------------------------------------------------------------
void sh_channelDefaults(uint8_t* b, uint8_t engine)
{
	memset(b, 0, SH_CH_STRIDE);
	b[SHP_ENGINE]     = engine;
	b[SHP_TUNE]       = 60;
	b[SHP_FINE]       = 64;
	b[SHP_ATTACK]     = 0;
	b[SHP_DECAY]      = 30;
	b[SHP_SLOPE]      = 30;
	b[SHP_REPEAT]     = 0;
	b[SHP_DECAY_ALT]  = 45;
	b[SHP_VELVOL]     = 1;
	b[SHP_AEG_MODE]   = SH_AEG_AD;
	b[SHP_FILT_FREQ]  = 127;
	b[SHP_FILT_RESO]  = 0;
	b[SHP_FILT_TYPE]  = 0;
	b[SHP_FILT_DRIVE] = 0;
	b[SHP_VOL]        = 100;
	b[SHP_PAN]        = 64;
	b[SHP_SRATE]      = 127;
	b[SHP_DRIVE]      = 0;
	b[SHP_OUT]        = 0;
	b[SHP_BITS]       = 0;
	b[SHP_LFO_FREQ]   = 30;
	b[SHP_LFO_OFFSET] = 0;
	b[SHP_LFO_WAVE]   = 0;
	b[SHP_LFO_RETRIG] = 0;
	b[SHP_RING_AMT]   = 0;
	b[SHP_RING_FREQ]  = 64;
	b[SHP_RING_SRC]   = SH_RING_SIN;
	sh_engineApplyDefaults(engine, b, 1);
}

//------------------------------------------------------------------------
void sh_trigger(uint8_t ch, uint8_t vel, uint8_t alt)
{
	if(ch >= SH_NUM_CHANNELS) return;
	channels[ch].trigVel = vel;
	channels[ch].trigAlt = alt;
	channels[ch].trigPending = 1;
	/* the glitch FX starts its events on hits of the channels it hears */
	if(block(ch)[SHP_OUT] == 6)   /* MIXER_ROUTING_FX_BUS */
		FxBus_onTrigger();
}

//------------------------------------------------------------------------
void sh_beginBlock(void)
{
	for(uint8_t ch = 0; ch < SH_NUM_CHANNELS; ch++)
	{
		ShChannel* c = &channels[ch];
		memset(c->mod, 0, sizeof(c->mod));
		c->pitchMod = 0.f;
		c->lfo.value = lfo_calc(&c->lfo, block(ch)[SHP_LFO_WAVE]);
	}
}

void sh_modAdd(uint8_t ch, uint8_t local, float amount)
{
	if(ch >= SH_NUM_CHANNELS || local >= SHP_LOCAL_COUNT) return;
	channels[ch].mod[local] += amount;
}

void sh_modAddPitch(uint8_t ch, float semitones)
{
	if(ch >= SH_NUM_CHANNELS) return;
	channels[ch].pitchMod += semitones;
}

float sh_lfoValue(uint8_t ch) { return channels[ch].lfo.value; }
float sh_lastVelocity(uint8_t ch) { return channels[ch].velocity; }
uint8_t sh_channelActive(uint8_t ch) { return channels[ch].aeg.state != EG_STOPPED; }

uint8_t sh_channelRouting(uint8_t ch) { return block(ch)[SHP_OUT]; }

void sh_channelPan(uint8_t ch, float* left, float* right)
{
	*left = channels[ch].panL;
	*right = channels[ch].panR;
}

//------------------------------------------------------------------------
/* effective value of a continuous parameter, 0..1 */
static inline float eff(const ShChannel* c, const uint8_t* p, uint8_t local)
{
	return clamp01(p[local] * (1.f / 127.f) + c->mod[local]);
}

/* returns 1 if the effective value changed since the last block */
static inline uint8_t changed(ShChannel* c, uint8_t local, float v)
{
	if(v == c->last[local]) return 0;
	c->last[local] = v;
	return 1;
}

static void updateStrip(uint8_t ch, ShChannel* c, const uint8_t* p)
{
	float v;

	v = eff(c, p, SHP_ATTACK);
	if(changed(c, SHP_ATTACK, v)) slopeEg2_setAttack(&c->aeg, toItg(v), 0);

	/* decay or decay alt, depending on the last trigger */
	v = eff(c, p, SHP_DECAY);
	const float vAlt = eff(c, p, SHP_DECAY_ALT);
	const uint8_t decayChanged = changed(c, SHP_DECAY, v);
	const uint8_t altChanged = changed(c, SHP_DECAY_ALT, vAlt);
	if(c->altActive ? altChanged : decayChanged)
		c->aeg.decay = slopeEg2_calcDecay(toItg(c->altActive ? vAlt : v));

	v = eff(c, p, SHP_SLOPE);
	if(changed(c, SHP_SLOPE, v)) slopeEg2_setSlope(&c->aeg, toItg(v));

	c->aeg.repeat = p[SHP_REPEAT];

	v = eff(c, p, SHP_FILT_FREQ);
	if(changed(c, SHP_FILT_FREQ, v)) SVF_directSetFilterValue(&c->filter, filterShape(v));
	v = eff(c, p, SHP_FILT_RESO);
	if(changed(c, SHP_FILT_RESO, v)) SVF_setReso(&c->filter, v);
	v = eff(c, p, SHP_FILT_DRIVE);
	if(changed(c, SHP_FILT_DRIVE, v)) SVF_setDrive(&c->filter, v);

	v = eff(c, p, SHP_PAN);
	if(changed(c, SHP_PAN, v))
	{
		c->panL = sqrtf(1.f - v);
		c->panR = sqrtf(v);
	}

	v = eff(c, p, SHP_DRIVE);
	if(changed(c, SHP_DRIVE, v)) setDistortionShape(&c->dist, v);

	v = eff(c, p, SHP_SRATE);
	if(changed(c, SHP_SRATE, v))
	{
		/* valueShaperF2F(v, -0.7) as in the original firmware */
		const float k = 2 * -0.7f / (1.0001f + 0.7f);
		c->decimRate = (1 + k) * v / (1 + k * fabsf(v));
	}

	v = eff(c, p, SHP_BITS);
	if(changed(c, SHP_BITS, v))
	{
		/* 0 = off (16 bit), 127 = 2 bit */
		c->bitShift = (uint8_t)((toItg(v) * 14 + 63) / 127);
	}

	v = eff(c, p, SHP_LFO_FREQ);
	if(changed(c, SHP_LFO_FREQ, v))
	{
		float f = 0.0078125f + v * (1.f - 0.0078125f);
		f = f * f * f * SH_LFO_MAX_F;
		c->lfo.phaseInc = (uint32_t)(f / SH_LFO_SR * 4294967295.f);
	}

	v = eff(c, p, SHP_RING_FREQ);
	if(changed(c, SHP_RING_FREQ, v))
	{
		/* 20 Hz .. 5.12 kHz, 8 octaves */
		const float f = 20.f * exp2f(v * 8.f);
		c->ringInc = (uint32_t)(f / SH_SAMPLE_RATE * 4294967295.f);
	}
}

//------------------------------------------------------------------------
/* ring modulator: out = x * ((1 - a) + a * carrier) */
static void ringMod(ShChannel* c, uint8_t ch, const uint8_t* p, float* out)
{
	const float a = eff(c, p, SHP_RING_AMT);   /* CV can open the ring */
	if(a <= 0.f) return;
	const float dry = 1.f - a;
	const uint8_t src = p[SHP_RING_SRC];
	if(src >= SH_RING_CH1)
	{
		const uint8_t sc = (uint8_t)(src - SH_RING_CH1);
		if(sc >= SH_NUM_CHANNELS) return;
		const int16_t* m = lastOut[sc];
		const float g = a * (1.f / 32768.f);
		for(uint8_t i = 0; i < SH_BLOCK_SIZE; i++)
			out[i] *= dry + g * m[i];
		(void)ch;
		return;
	}
	uint32_t ph = c->ringPhase;
	const uint32_t inc = c->ringInc;
	for(uint8_t i = 0; i < SH_BLOCK_SIZE; i++)
	{
		/* x in -1..1 over one period */
		const float x = (int32_t)ph * (1.f / 2147483648.f);
		float m;
		switch(src)
		{
		default:
		case SH_RING_SIN:
		{
			/* parabolic sine with one correction step */
			const float y = 4.f * x * (1.f - fabsf(x));
			m = 0.225f * (y * fabsf(y) - y) + y;
			break;
		}
		case SH_RING_TRI:
			m = 1.f - 2.f * fabsf(x);
			break;
		case SH_RING_SQR:
			m = x < 0.f ? -1.f : 1.f;
			break;
		}
		out[i] *= dry + a * m;
		ph += inc;
	}
	c->ringPhase = ph;
}

//------------------------------------------------------------------------
static void handleTrigger(uint8_t ch, ShChannel* c, const uint8_t* p, ShRenderIn* in)
{
	if(!c->trigPending) return;
	c->trigPending = 0;
	const uint8_t alt = c->trigAlt;
	c->velocity = c->trigVel / 127.f;

	/* decay for this hit */
	if(alt != c->altActive)
	{
		c->altActive = alt;
		c->aeg.decay = slopeEg2_calcDecay(toItg(eff(c, p, alt ? SHP_DECAY_ALT : SHP_DECAY)));
	}
	slopeEg2_trigger(&c->aeg);
	SVF_reset(&c->filter);
	c->ringPhase = 0;   /* the same carrier phase on every hit */

	/* LFO retrigger: every LFO that listens to this channel */
	for(uint8_t i = 0; i < SH_NUM_CHANNELS; i++)
	{
		const uint8_t* pi = block(i);
		if(pi[SHP_LFO_RETRIG] == ch + 1)
			channels[i].lfo.phase = (uint32_t)(pi[SHP_LFO_OFFSET] / 127.f * 4294967295.f);
	}

	in->trigger = 1;
	in->alt = alt;
	in->accent = c->velocity;
}

//------------------------------------------------------------------------
void sh_channelsMorph(const uint8_t* target)
{
	morphTarget = target;
}

void sh_meterEnable(uint8_t on)
{
	meterOn = on;
}

uint16_t sh_meterTake(uint8_t ch)
{
	const uint16_t v = meterPeak[ch];
	meterPeak[ch] = 0;
	return v;
}

static uint8_t isSteppedLocal(uint8_t local, const ShEngineInfo* info)
{
	switch(local)
	{
	case SHP_ENGINE: case SHP_AEG_MODE: case SHP_FILT_TYPE: case SHP_OUT:
	case SHP_LFO_WAVE: case SHP_LFO_RETRIG: case SHP_VELVOL: case SHP_REPEAT:
	case SHP_RING_SRC:
		return 1;
	default:
		break;
	}
	if(local >= SHP_E0 && local <= SHP_E_LAST)
	{
		const uint8_t t = info->params[local - SHP_E0].type;
		return t == SH_PT_LIST || t == SH_PT_ONOFF;
	}
	return 0;
}

uint8_t sh_isSteppedLocal(uint8_t local, uint8_t engine)
{
	return isSteppedLocal(local, sh_engineInfo(engine < sh_engineCount() ? engine : 0));
}

/* morphed view of a channel block between the live kit and the morph
 * target, using the curves of sh_morph.c */
static void morphView(uint8_t ch, const uint8_t* src, const uint8_t* dst, uint8_t* view)
{
	const uint16_t base = (uint16_t)(1 + ch * SH_CH_STRIDE);   /* = PAR_CH(ch, 0) */
	if(src[SHP_ENGINE] != dst[SHP_ENGINE])
	{
		/* different engines: the whole block switches with the engine */
		memcpy(view, sh_morphStepped(0, 1, base + SHP_ENGINE) ? dst : src, SH_CH_STRIDE);
	}
	else
	{
		const ShEngineInfo* info = sh_engineInfo(src[SHP_ENGINE]);
		for(uint8_t i = 0; i < SHP_LOCAL_COUNT; i++)
		{
			if(src[i] == dst[i])
				view[i] = src[i];
			else if(isSteppedLocal(i, info))
				view[i] = sh_morphStepped(src[i], dst[i], (uint16_t)(base + i));
			else
				view[i] = sh_morphContinuous(src[i], dst[i], (uint16_t)(base + i), 127);
		}
	}
	/* audio routing is never morphed */
	view[SHP_OUT] = src[SHP_OUT];
}

//------------------------------------------------------------------------
void sh_channelRender(uint8_t ch, int16_t* buf)
{
	ShChannel* c = &channels[ch];
	const uint8_t* p = block(ch);
	uint8_t view[SH_CH_STRIDE];
	if(morphTarget && sh_morphActive())
	{
		morphView(ch, p, morphTarget + ch * SH_CH_STRIDE, view);
		p = view;
	}

	/* engine change (front panel or kit load); unknown numbers (kit from a
	 * newer firmware) fall back to engine 0 */
	const uint8_t engine = p[SHP_ENGINE] < sh_engineCount() ? p[SHP_ENGINE] : 0;
	if(engine != sh_engineCurrent(ch))
		sh_engineSelect(ch, engine);

	updateStrip(ch, c, p);

	ShRenderIn in;
	in.trigger = 0;
	in.alt = c->altActive;
	in.accent = c->velocity;
	handleTrigger(ch, c, p, &in);

	/* pitch */
	in.note = p[SHP_TUNE] + (p[SHP_FINE] - 64) * 0.01f + c->pitchMod;

	/* engine parameters */
	const ShEngineInfo* info = sh_engineInfo(sh_engineCurrent(ch));
	for(uint8_t i = 0; i < SH_NUM_ENGINE_PARAMS; i++)
	{
		const ShParamDesc* d = &info->params[i];
		const uint8_t local = (uint8_t)(SHP_E0 + i);
		if(d->type == SH_PT_LIST || d->type == SH_PT_ONOFF)
		{
			const uint8_t n = d->type == SH_PT_ONOFF ? 2 : d->count;
			uint8_t idx = p[local];
			if(c->mod[local] != 0.f && n > 1)
			{
				const float x = clamp01(idx / (float)(n - 1) + c->mod[local]);
				idx = (uint8_t)(x * (n - 1) + 0.5f);
			}
			if(idx >= n) idx = (uint8_t)(n - 1);
			in.idx[i] = idx;
			in.p[i] = n > 1 ? idx / (float)(n - 1) : 0.f;
		}
		else
		{
			in.idx[i] = 0;
			in.p[i] = eff(c, p, local);
		}
	}

	/* engine */
	float out[SH_BLOCK_SIZE];
	sh_engineRender(ch, &in, out);
	ringMod(c, ch, p, out);
	for(uint8_t i = 0; i < SH_BLOCK_SIZE; i++)
	{
		float x = out[i] * 32767.f;
		x = x > 32767.f ? 32767.f : (x < -32768.f ? -32768.f : x);
		buf[i] = (int16_t)x;
	}

	/* filter */
	const uint8_t ftype = p[SHP_FILT_TYPE];
	if(ftype > 0 && ftype < SH_NUM_FILTER_TYPES)
	{
		SVF_recalcFreq(&c->filter);
		SVF_calcBlockZDF(&c->filter, ftype, buf, SH_BLOCK_SIZE);
	}

	/* amp EG (interpolated per block, as AMP_EG_SYNC == 0 in the LXR voices) */
	if(p[SHP_AEG_MODE] == SH_AEG_AD)
	{
		if(c->aeg.attack == 1 && (c->aeg.state == EG_A || c->aeg.state == EG_REPEAT))
		{
			c->gainNow = (float)slopeEg2_calc(&c->aeg);
			c->gainLast = c->gainNow;
		}
		else
		{
			c->gainLast = c->gainNow;
			c->gainNow = (float)slopeEg2_calc(&c->aeg);
		}
		bufferTool_addGainInterpolated(buf, c->gainNow, c->gainLast, SH_BLOCK_SIZE);
	}
	else
	{
		/* keep the EG running for sh_channelActive(), but don't apply it */
		slopeEg2_calc(&c->aeg);
		c->gainNow = c->gainLast = 1.f;
	}

	/* velocity */
	if(p[SHP_VELVOL])
		bufferTool_addGain(buf, c->velocity, SH_BLOCK_SIZE);

	/* drive */
	calcDistBlockFiltered(&c->dist, buf, SH_BLOCK_SIZE);

	/* volume */
	const float vol = eff(c, p, SHP_VOL);
	for(uint8_t i = 0; i < SH_BLOCK_SIZE; i++)
		buf[i] = (int16_t)(buf[i] * calcOnePole(&c->volSmooth, vol));

	/* sample rate reduction */
	if(c->decimRate < 0.999f)
	{
		for(uint8_t i = 0; i < SH_BLOCK_SIZE; i++)
		{
			c->decimCnt += c->decimRate;
			if(c->decimCnt >= 1.f)
			{
				c->decimCnt -= 1.f;
				c->decimHold = buf[i];
			}
			buf[i] = c->decimHold;
		}
	}

	/* bit reduction */
	if(c->bitShift)
	{
		const uint8_t s = c->bitShift;
		for(uint8_t i = 0; i < SH_BLOCK_SIZE; i++)
			buf[i] = (int16_t)((buf[i] >> s) << s);
	}

	/* carrier for the ring modulators */
	memcpy(lastOut[ch], buf, sizeof(lastOut[ch]));

	/* level meter for the screensaver */
	if(meterOn)
	{
		uint16_t pk = meterPeak[ch];
		for(uint8_t i = 0; i < SH_BLOCK_SIZE; i += 4)
		{
			const int16_t x = buf[i];
			const uint16_t a = (uint16_t)(x < 0 ? -x : x);
			if(a > pk) pk = a;
		}
		meterPeak[ch] = pk;
	}
}
