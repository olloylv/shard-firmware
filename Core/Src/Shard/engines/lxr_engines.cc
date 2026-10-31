// lxr_engines.cc - the original LXR voices as freely assignable engines
//
// Copyright (C) 2012-2026 Erica Synths (original voice code),
//           (C) 2026 SHARD contributors (engine wrapper).
// SPDX-License-Identifier: GPL-3.0-only
//
// The oscillator, pitch EG, snap EG and transient code is the unchanged LXR
// C code. What used to be part of every voice (filter, amp EG, drive, volume)
// now lives in the common channel strip (sh_channel.c), which keeps the order
// osc -> filter -> amp EG -> drive of the original voices.

#include "engines.h"

extern "C" {
#include "Soundengine/DSPAudio/Oscillator.h"
#include "Soundengine/DSPAudio/Decay.h"
#include "Soundengine/DSPAudio/snapEg.h"
#include "Soundengine/DSPAudio/transientGenerator.h"
#include "Soundengine/DSPAudio/transientTables.h"
#include "Soundengine/DSPAudio/ResonantFilter.h"
#include "Soundengine/DSPAudio/BufferTools.h"
}

namespace shard {

namespace {

const char kLxrWaves[][4] = { "Sin", "Tri", "Saw", "Rec", "Noi", "PWM" };
const char kLxrTransients[][4] = {
  "Snp", "Ofs", "Clk", "Ck2", "Tik", "Kik", "Rim", "Drp",
  "Hat", "Clp", "Kk2", "Snr", "Tom", "Sp2",
};
const char kLxrMixModes[][4] = { "FM ", "Mix" };
const char kLxrFilterTypes[][4] = { "LP ", "HP ", "BP ", "UBP", "Nch", "Pk ", "LP2" };

inline float NoteToHz(float note) {
  return 440.0f * stmlib::SemitonesToRatio(note - 69.0f);
}

void InitOsc(OscInfo* osc, uint8_t waveform) {
  osc->output = 0;
  osc->phaseInc = 0;
  osc->phase = 0;
  osc->freq = 440.0f;
  osc->waveform = waveform;
  osc->tableOffset = 0;
  osc->pitchMod = 1.0f;
  osc->fmMod = 0.0f;
  osc->modNodeValue = 1.0f;
  osc->cvFreq = -1.0f;      // no CV path: pitch comes in as note
  osc->midiFreq = 60 << 8 | 64;
  osc->baseNote = 63;
  osc->startPhase = 0;
}

// the phase reset on trigger of the original voices
void ResetOscPhase(OscInfo* osc, float offset) {
  if (osc->waveform == SINE) {
    osc->phase = 1024 + static_cast<uint32_t>(((0x3ffu << 20) - 1024) * offset);
  } else if (osc->waveform > SINE && osc->waveform <= REC) {
    osc->phase = static_cast<uint32_t>((0xffu << 22) * offset);
  } else {
    osc->phase = 0;
  }
}

inline uint8_t ToItg(float p) {
  int v = static_cast<int>(p * 127.0f + 0.5f);
  return static_cast<uint8_t>(v < 0 ? 0 : (v > 127 ? 127 : v));
}

inline uint8_t Wave(uint8_t idx) { return idx < NUM_OSC_WAVEFORMS ? idx : 0; }

// transient sample frequency mapping of the original firmware (1/4 .. 4)
inline float TransientPitch(float p) {
  return 1.0f + ((p * 127.0f / 33.9f) - 0.75f);
}

inline void ToFloat(const int16_t* in, float* out) {
  for (size_t i = 0; i < kBlock; ++i) out[i] = in[i] * (1.0f / 32768.0f);
}

}  // namespace

// --- LXR Drum: FM / mix oscillator pair with pitch EG ------------------------
// slots: OSC  E0 wave, E1 pwm
//        MOD  E5 pitch decay, E6 pitch slope, E7 pitch mod amount
//        FM   E13 fm amount, E14 mod freq, E15 mod wave, E16 fm/mix
//        SMP  E21 transient wave, E22 transient vol, E23 transient freq

class LxrDrum : public Engine {
 public:
  void Init() override {
    InitOsc(&osc_, TRI);
    InitOsc(&mod_osc_, SINE);
    DecayEg_init(&pitch_eg_);
    DecayEg_setSlope(&pitch_eg_, 64);
    SnapEg_init(&snap_);
    transient_init(&trans_);
    for (int i = 0; i < SH_NUM_ENGINE_PARAMS; ++i) last_[i] = -1.0f;
  }

  void Render(const ShRenderIn& in, float* out) override {
    Update(in);
    if (in.trigger) {
      float offset = 1.0f;
      if (trans_.waveform == 1) offset -= trans_.volume;
      ResetOscPhase(&osc_, offset);
      ResetOscPhase(&mod_osc_, 1.0f);
      DecayEg_trigger(&pitch_eg_);
      transient_trigger(&trans_);
      SnapEg_trigger(&snap_);
    }
    // async part (once per block, as in calcDrumVoiceAsync)
    const float eg = DecayEg_calc(&pitch_eg_);
    osc_.pitchMod = 1.0f + eg * pitch_amount_;
    if (trans_.waveform == 0) {
      osc_.pitchMod += SnapEg_calc(&snap_, trans_.pitch) * trans_.volume;
    }
    osc_.fmMod = fm_amount_ * eg;
    osc_.freq = NoteToHz(in.note);
    mod_osc_.freq = NoteToHz(in.note + mod_offset_);
    osc_setFreq(&osc_);
    osc_setFreq(&mod_osc_);

    // sync part (as in calcDrumVoiceSyncBlock, up to the filter)
    int16_t buf[kBlock], mod[kBlock];
    calcNextOscSampleBlock(&mod_osc_, mod, kBlock, fm_amount_, pwm_);
    if (mix_) {
      calcNextOscSampleBlock(&osc_, buf, kBlock, 1.0f - fm_amount_, pwm_);
      bufferTool_addBuffersSaturating(buf, mod, kBlock);
    } else {
      calcNextOscSampleFmBlock(&osc_, mod, buf, kBlock, 1.0f, pwm_);
    }
    transient_calcBlock(&trans_, mod, kBlock);
    bufferTool_addBuffersSaturating(buf, mod, kBlock);
    ToFloat(buf, out);
  }

 private:
  void Update(const ShRenderIn& in) {
    osc_.waveform = Wave(in.idx[0]);
    pwm_ = in.p[1];
    if (in.p[5] != last_[5]) { last_[5] = in.p[5]; DecayEg_setDecay(&pitch_eg_, ToItg(in.p[5])); }
    if (in.p[6] != last_[6]) { last_[6] = in.p[6]; DecayEg_setSlope(&pitch_eg_, ToItg(in.p[6])); }
    pitch_amount_ = in.p[7] * in.p[7] * 32.0f;   // calcPitchModAmount()
    fm_amount_ = in.p[13];
    mod_offset_ = Bi(in.p[14]);
    mod_osc_.waveform = Wave(in.idx[15]);
    mix_ = in.idx[16] != 0;
    transient_setWaveform(&trans_, in.idx[21]);
    trans_.volume = in.p[22];
    trans_.pitch = TransientPitch(in.p[23]);
  }

  OscInfo osc_, mod_osc_;
  DecayEg pitch_eg_;
  SnapEg snap_;
  TransientGenerator trans_;
  float pitch_amount_ = 0.0f, fm_amount_ = 0.0f, pwm_ = 0.5f, mod_offset_ = 0.0f;
  bool mix_ = false;
  float last_[SH_NUM_ENGINE_PARAMS];
};

const ShEngineInfo kInfoLxrDrum = {
  "Drm", "LXR Drum", "LXR",
  {
    SH_LIST("Wav", "Waveform", 0, 6, kLxrWaves),
    SH_UNI("PWM", "PWM", 64),
    SH_UNUSED, SH_UNUSED, SH_UNUSED,
    /* MOD */
    SH_UNI("PDc", "PitchDec", 40),
    SH_BI("PSl", "PitchSlp", 64),
    SH_UNI("PAm", "PitchMod", 40),
    SH_UNUSED, SH_UNUSED, SH_UNUSED, SH_UNUSED, SH_UNUSED,
    /* FM */
    SH_UNI("FMA", "FM Amnt", 0),
    SH_BI("FMF", "FM Freq", 64),
    SH_LIST("FMW", "FM Wave", 0, 6, kLxrWaves),
    SH_LIST("Mod", "Mode", 0, 2, kLxrMixModes),
    SH_UNUSED, SH_UNUSED, SH_UNUSED, SH_UNUSED,
    /* SMP */
    SH_LIST("TrW", "TransWav", 0, 14, kLxrTransients),
    SH_UNI("TrV", "TransVol", 0),
    SH_UNI("TrF", "TransFrq", 26),
  },
  { 36, SH_AEG_AD, 0, 32, 0, 127 },
};

// --- LXR Snare: oscillator + filtered noise ---------------------------------
// The snare filtered only its noise part, so the engine keeps that filter
// (E2 freq, E3 reso, E4 type); the strip filter defaults to off.
// slots: OSC E0 wave, E1 noise freq, E2 noise filter freq, E3 reso, E4 type
//        MOD E5 pitch decay, E6 slope, E7 amount, E8 mix, E9 pwm
//        SMP E21..E23 transient

class LxrSnare : public Engine {
 public:
  void Init() override {
    InitOsc(&osc_, SINE);
    InitOsc(&noise_osc_, NOISE);
    DecayEg_init(&pitch_eg_);
    DecayEg_setSlope(&pitch_eg_, 64);
    SnapEg_init(&snap_);
    transient_init(&trans_);
    SVF_init(&filter_);
    for (int i = 0; i < SH_NUM_ENGINE_PARAMS; ++i) last_[i] = -1.0f;
  }

  void Render(const ShRenderIn& in, float* out) override {
    osc_.waveform = Wave(in.idx[0]);
    noise_osc_.freq = in.p[1] * 22000.0f;
    if (in.p[2] != last_[2]) {
      last_[2] = in.p[2];
      // valueShaperF2F(f, FILTER_SHAPER = -0.9)
      const float k = 2.0f * -0.9f / (1.0001f + 0.9f);
      const float v = in.p[2];
      SVF_directSetFilterValue(&filter_, (1.0f + k) * v / (1.0f + k * fabsf(v)));
    }
    if (in.p[3] != last_[3]) { last_[3] = in.p[3]; SVF_setReso(&filter_, in.p[3]); }
    const uint8_t ftype = static_cast<uint8_t>(in.idx[4] + 1);
    if (in.p[5] != last_[5]) { last_[5] = in.p[5]; DecayEg_setDecay(&pitch_eg_, ToItg(in.p[5])); }
    if (in.p[6] != last_[6]) { last_[6] = in.p[6]; DecayEg_setSlope(&pitch_eg_, ToItg(in.p[6])); }
    const float pitch_amount = in.p[7] * in.p[7] * 32.0f;
    const float mix = in.p[8];
    const float pwm = in.p[9];
    transient_setWaveform(&trans_, in.idx[21]);
    trans_.volume = in.p[22];
    trans_.pitch = TransientPitch(in.p[23]);

    if (in.trigger) {
      float offset = 1.0f;
      if (trans_.waveform == 1) offset -= trans_.volume;
      ResetOscPhase(&osc_, offset);
      DecayEg_trigger(&pitch_eg_);
      transient_trigger(&trans_);
      SnapEg_trigger(&snap_);
    }
    const float eg = DecayEg_calc(&pitch_eg_);
    osc_.pitchMod = 1.0f + eg * pitch_amount;
    if (trans_.waveform == 0) {
      osc_.pitchMod += SnapEg_calc(&snap_, trans_.pitch) * trans_.volume;
    }
    osc_.freq = NoteToHz(in.note);
    osc_setFreq(&osc_);
    osc_setFreq(&noise_osc_);

    int16_t noise[kBlock], tone[kBlock], trans[kBlock];
    calcNoiseBlock(&noise_osc_, noise, kBlock, 0.9f);
    SVF_calcBlockZDF(&filter_, ftype, noise, kBlock);
    calcNextOscSampleBlock(&osc_, tone, kBlock, 1.0f - mix, pwm);
    transient_calcBlock(&trans_, trans, kBlock);
    for (size_t i = 0; i < kBlock; ++i) {
      out[i] = (noise[i] * mix + tone[i] + trans[i]) * (1.0f / 32768.0f);
    }
  }

 private:
  OscInfo osc_, noise_osc_;
  DecayEg pitch_eg_;
  SnapEg snap_;
  TransientGenerator trans_;
  ResonantFilter filter_;
  float last_[SH_NUM_ENGINE_PARAMS];
};

const ShEngineInfo kInfoLxrSnare = {
  "Snr", "LXR Snr", "LXR",
  {
    SH_LIST("Wav", "Waveform", 0, 6, kLxrWaves),
    SH_UNI("Noi", "NoiseFrq", 100),
    SH_UNI("NFF", "NoiseFlt", 90),
    SH_UNI("NFR", "NoiseRes", 20),
    SH_LIST("NFT", "NFltType", 1, 7, kLxrFilterTypes),
    /* MOD */
    SH_UNI("PDc", "PitchDec", 40),
    SH_BI("PSl", "PitchSlp", 64),
    SH_UNI("PAm", "PitchMod", 30),
    SH_UNI("Mix", "NoiseMix", 64),
    SH_UNI("PWM", "PWM", 64),
    SH_UNUSED, SH_UNUSED, SH_UNUSED,
    /* FM (unused) */
    SH_UNUSED, SH_UNUSED, SH_UNUSED, SH_UNUSED,
    SH_UNUSED, SH_UNUSED, SH_UNUSED, SH_UNUSED,
    /* SMP */
    SH_LIST("TrW", "TransWav", 0, 14, kLxrTransients),
    SH_UNI("TrV", "TransVol", 0),
    SH_UNI("TrF", "TransFrq", 26),
  },
  { 52, SH_AEG_AD, 0, 22, 0, 127 },
};

// --- LXR Cymbal / HiHat: three oscillator FM cluster -------------------------
// slots: OSC E0 wave, E1 pwm
//        FM  E13 mod freq 1, E14 mod freq 2, E15 gain 1, E16 gain 2,
//            E17 wave 2, E18 wave 3
//        SMP E21..E23 transient

class LxrMetal : public Engine {
 public:
  void Init() override {
    InitOsc(&osc_, SINE);
    InitOsc(&mod1_, SINE);
    InitOsc(&mod2_, SINE);
    osc_.fmMod = 1.0f;   // as CymbalVoice.c / HiHat.c: the carrier is fully FM modulated
    SnapEg_init(&snap_);
    transient_init(&trans_);
  }

  void Render(const ShRenderIn& in, float* out) override {
    osc_.waveform = Wave(in.idx[0]);
    const float pwm = in.p[1];
    const float off1 = Bi(in.p[13]);
    const float off2 = Bi(in.p[14]);
    const float gain1 = in.p[15];
    const float gain2 = in.p[16];
    mod1_.waveform = Wave(in.idx[17]);
    mod2_.waveform = Wave(in.idx[18]);
    transient_setWaveform(&trans_, in.idx[21]);
    trans_.volume = in.p[22];
    trans_.pitch = TransientPitch(in.p[23]);

    if (in.trigger) {
      float offset = 1.0f;
      if (trans_.waveform == 1) offset -= trans_.volume;
      ResetOscPhase(&osc_, offset);
      mod1_.phase = 0;
      mod2_.phase = 0;
      transient_trigger(&trans_);
      SnapEg_trigger(&snap_);
    }
    osc_.pitchMod = 1.0f;
    if (trans_.waveform == 0) {
      osc_.pitchMod = 1.0f + SnapEg_calc(&snap_, trans_.pitch) * trans_.volume;
    }
    osc_.freq = NoteToHz(in.note);
    mod1_.freq = NoteToHz(in.note + off1);
    mod2_.freq = NoteToHz(in.note + off2);
    osc_setFreq(&osc_);
    osc_setFreq(&mod1_);
    osc_setFreq(&mod2_);

    int16_t buf[kBlock], m1[kBlock], m2[kBlock];
    calcNextOscSampleBlock(&mod1_, m1, kBlock, gain1, pwm);
    calcNextOscSampleBlock(&mod2_, m2, kBlock, gain2, pwm);
    bufferTool_addBuffersSaturating(m1, m2, kBlock);
    calcNextOscSampleFmBlock(&osc_, m1, buf, kBlock, 0.5f, pwm);
    transient_calcBlock(&trans_, m1, kBlock);
    bufferTool_addBuffersSaturating(buf, m1, kBlock);
    ToFloat(buf, out);
  }

 private:
  OscInfo osc_, mod1_, mod2_;
  SnapEg snap_;
  TransientGenerator trans_;
};

class LxrCymbal : public LxrMetal {};
class LxrHat : public LxrMetal {};

#define LXR_METAL_PARAMS(w2, w3)                         \
    SH_LIST("Wav", "Waveform", 0, 6, kLxrWaves),         \
    SH_UNI("PWM", "PWM", 64),                            \
    SH_UNUSED, SH_UNUSED, SH_UNUSED,                     \
    SH_UNUSED, SH_UNUSED, SH_UNUSED, SH_UNUSED,          \
    SH_UNUSED, SH_UNUSED, SH_UNUSED, SH_UNUSED,          \
    SH_BI("MF1", "ModFreq1", 88),                        \
    SH_BI("MF2", "ModFreq2", 101),                       \
    SH_UNI("MG1", "ModGain1", 80),                       \
    SH_UNI("MG2", "ModGain2", 60),                       \
    SH_LIST("MW1", "ModWave1", w2, 6, kLxrWaves),        \
    SH_LIST("MW2", "ModWave2", w3, 6, kLxrWaves),        \
    SH_UNUSED, SH_UNUSED,                                \
    SH_LIST("TrW", "TransWav", 0, 14, kLxrTransients),   \
    SH_UNI("TrV", "TransVol", 0),                        \
    SH_UNI("TrF", "TransFrq", 26)

const ShEngineInfo kInfoLxrCymbal = {
  "Cym", "LXR Cym", "LXR",
  { LXR_METAL_PARAMS(3, 0) },
  { 72, SH_AEG_AD, 0, 62, 0, 127 },
};

const ShEngineInfo kInfoLxrHat = {
  "Hat", "LXR Hat", "LXR",
  { LXR_METAL_PARAMS(3, 3) },
  { 84, SH_AEG_AD, 0, 8, 0, 127 },
};
#undef LXR_METAL_PARAMS

SH_DEFINE_ENGINE_FACTORY(LxrDrum)
SH_DEFINE_ENGINE_FACTORY(LxrSnare)
SH_DEFINE_ENGINE_FACTORY(LxrCymbal)
SH_DEFINE_ENGINE_FACTORY(LxrHat)

}  // namespace shard
