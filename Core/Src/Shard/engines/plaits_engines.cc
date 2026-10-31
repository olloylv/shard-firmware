// plaits_engines.cc - percussion engines built on Mutable Instruments Plaits DSP
//
// Copyright (C) 2026 SHARD contributors.
// SPDX-License-Identifier: GPL-3.0-only
//
// The DSP classes come from Plaits (MIT, Copyright Emilie Gillet), see
// Core/ThirdParty. Unlike the Plaits macro engines, the internal parameters
// of each drum model are exposed one by one here.

#include "engines.h"

#include "plaits/dsp/drums/analog_bass_drum.h"
#include "plaits/dsp/drums/analog_snare_drum.h"
#include "plaits/dsp/drums/hi_hat.h"
#include "plaits/dsp/drums/synthetic_bass_drum.h"
#include "plaits/dsp/drums/synthetic_snare_drum.h"
#include "plaits/dsp/fx/diffuser.h"
#include "plaits/dsp/fx/overdrive.h"
#include "plaits/dsp/noise/particle.h"
#include "plaits/dsp/physical_modelling/modal_voice.h"
#include "plaits/dsp/physical_modelling/string_voice.h"
#include "stmlib/utils/buffer_allocator.h"

namespace shard {

namespace {

inline void SoftLimit(float* out, float gain) {
  for (size_t i = 0; i < kBlock; ++i) {
    out[i] = stmlib::SoftClip(out[i] * gain);
  }
}

}  // namespace

// --- Analog bass drum (808 style bridged T) --------------------------------

class PlaitsAnalogBD : public Engine {
 public:
  void Init() override { bd_.Init(); od_.Init(); }
  void Render(const ShRenderIn& in, float* out) override {
    const float f0 = NoteToF0(in.note);
    bd_.Render(false, in.trigger, in.accent, f0,
               in.p[0], in.p[1], in.p[2], in.p[3], out, kBlock);
    for (size_t i = 0; i < kBlock; ++i) out[i] *= 2.0f;
    const float drive = in.p[4];
    if (drive > 0.01f) {
      od_.Process(0.5f + 0.5f * drive, out, kBlock);
    }
  }
 private:
  plaits::AnalogBassDrum bd_;
  plaits::Overdrive od_;
};

const ShEngineInfo kInfoPlaitsAnalogBD = {
  "aBD", "AnalogBD", "PLAITS",
  {
    SH_UNI("Ton", "Tone", 50),
    SH_UNI("Dec", "Decay", 64),
    SH_UNI("AFM", "AttackFM", 40),
    SH_UNI("SFM", "Self FM", 20),
    SH_UNI("Drv", "Drive", 0),
  },
  { 36, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- Synthetic bass drum ---------------------------------------------------

class PlaitsSynthBD : public Engine {
 public:
  void Init() override { bd_.Init(); }
  void Render(const ShRenderIn& in, float* out) override {
    bd_.Render(false, in.trigger, in.accent, NoteToF0(in.note),
               in.p[0], in.p[1], in.p[2], in.p[3], in.p[4], out, kBlock);
  }
 private:
  plaits::SyntheticBassDrum bd_;
};

const ShEngineInfo kInfoPlaitsSynthBD = {
  "sBD", "SynthBD", "PLAITS",
  {
    SH_UNI("Ton", "Tone", 64),
    SH_UNI("Dec", "Decay", 64),
    SH_UNI("Drt", "Dirt", 30),
    SH_UNI("FMA", "FM Amnt", 50),
    SH_UNI("FMD", "FM Decay", 40),
  },
  { 36, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- Analog snare drum -----------------------------------------------------

class PlaitsAnalogSD : public Engine {
 public:
  void Init() override { sd_.Init(); }
  void Render(const ShRenderIn& in, float* out) override {
    sd_.Render(false, in.trigger, in.accent, NoteToF0(in.note),
               in.p[0], in.p[1], in.p[2], out, kBlock);
  }
 private:
  plaits::AnalogSnareDrum sd_;
};

const ShEngineInfo kInfoPlaitsAnalogSD = {
  "aSD", "AnalogSD", "PLAITS",
  {
    SH_UNI("Ton", "Tone", 64),
    SH_UNI("Dec", "Decay", 50),
    SH_UNI("Snp", "Snappy", 70),
  },
  { 50, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- Synthetic snare drum --------------------------------------------------

class PlaitsSynthSD : public Engine {
 public:
  void Init() override { sd_.Init(); }
  void Render(const ShRenderIn& in, float* out) override {
    sd_.Render(false, in.trigger, in.accent, NoteToF0(in.note),
               in.p[0], in.p[1], in.p[2], out, kBlock);
  }
 private:
  plaits::SyntheticSnareDrum sd_;
};

const ShEngineInfo kInfoPlaitsSynthSD = {
  "sSD", "SynthSD", "PLAITS",
  {
    SH_UNI("FMA", "FM Amnt", 40),
    SH_UNI("Dec", "Decay", 50),
    SH_UNI("Snp", "Snappy", 70),
  },
  { 52, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- Hi hat (808 square cluster or ring modulated) -------------------------

static const char kHatTypes[][4] = { "808", "Rng" };

class PlaitsHat : public Engine {
 public:
  void Init() override { hh1_.Init(); hh2_.Init(); }
  void Render(const ShRenderIn& in, float* out) override {
    const float f0 = NoteToF0(in.note);
    // the alternative trigger opens the hat (slot 4 = open decay)
    const float decay = in.alt ? in.p[4] : in.p[1];
    if (in.idx[3] == 0) {
      hh1_.Render(false, in.trigger, in.accent, f0, in.p[0], decay, in.p[2],
                  temp_, temp_ + kBlock, out, kBlock);
    } else {
      hh2_.Render(false, in.trigger, in.accent, f0, in.p[0], decay, in.p[2],
                  temp_, temp_ + kBlock, out, kBlock);
    }
  }
 private:
  plaits::HiHat<plaits::SquareNoise, plaits::SwingVCA, true, false> hh1_;
  plaits::HiHat<plaits::RingModNoise, plaits::LinearVCA, false, true> hh2_;
  float temp_[2 * kBlock];
};

const ShEngineInfo kInfoPlaitsHat = {
  "pHH", "Hat", "PLAITS",
  {
    SH_UNI("Ton", "Tone", 64),
    SH_UNI("Dec", "Decay", 30),
    SH_UNI("Noi", "Noise", 40),
    SH_LIST("Typ", "Type", 0, 2, kHatTypes),
    SH_UNI("Opn", "OpenDec", 90),
  },
  { 70, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- Modal resonator (struck objects, bells, wood) -------------------------

class PlaitsModal : public Engine {
 public:
  void Init() override { voice_.Init(); }
  void Render(const ShRenderIn& in, float* out) override {
    for (size_t i = 0; i < kBlock; ++i) out[i] = aux_[i] = 0.0f;
    voice_.Render(false, in.trigger, in.accent, NoteToF0(in.note),
                  in.p[0], in.p[1], in.p[2], temp_, out, aux_, kBlock);
    // slot 3 mixes in the exciter (aux), like the Plaits AUX out
    const float exc = in.p[3];
    for (size_t i = 0; i < kBlock; ++i) out[i] += exc * aux_[i];
    SoftLimit(out, 1.0f);
  }
 private:
  plaits::ModalVoice voice_;
  float temp_[kBlock];
  float aux_[kBlock];
};

const ShEngineInfo kInfoPlaitsModal = {
  "Mdl", "Modal", "PLAITS",
  {
    SH_UNI("Str", "Structur", 64),
    SH_UNI("Bri", "Bright", 64),
    SH_UNI("Dmp", "Damping", 64),
    SH_UNI("Exc", "Exciter", 0),
  },
  { 60, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- Karplus-Strong string -------------------------------------------------

class PlaitsString : public Engine {
 public:
  void Init() override {
    stmlib::BufferAllocator allocator(buffer_, sizeof(buffer_));
    voice_.Init(&allocator);
  }
  void Render(const ShRenderIn& in, float* out) override {
    for (size_t i = 0; i < kBlock; ++i) out[i] = aux_[i] = 0.0f;
    voice_.Render(false, in.trigger, in.accent, NoteToF0(in.note),
                  in.p[0], in.p[1] * in.p[1], in.p[2], temp_, out, aux_, kBlock);
    const float exc = in.p[3];
    for (size_t i = 0; i < kBlock; ++i) out[i] += exc * aux_[i];
    SoftLimit(out, 2.0f);
  }
 private:
  plaits::StringVoice voice_;
  float temp_[kBlock];
  float aux_[kBlock];
  float buffer_[plaits::kDelayLineSize + plaits::kDelayLineSize / 4 + 8];
};

const ShEngineInfo kInfoPlaitsString = {
  "Str", "String", "PLAITS",
  {
    SH_UNI("Str", "Structur", 64),
    SH_UNI("Bri", "Bright", 80),
    SH_UNI("Dmp", "Damping", 70),
    SH_UNI("Exc", "Exciter", 0),
  },
  { 48, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- Particles (filtered dust through a diffuser) --------------------------

class PlaitsParticle : public Engine {
 public:
  void Init() override {
    for (int i = 0; i < kNumParticles; ++i) particle_[i].Init();
    diffuser_.Init(diffuser_buffer_);
    post_filter_.Init();
  }
  void Render(const ShRenderIn& in, float* out) override {
    using stmlib::SemitonesToRatio;
    const float f0 = NoteToF0(in.note);
    const float density_sqrt = NoteToF0(60.0f + in.p[0] * in.p[0] * 72.0f);
    const float density = density_sqrt * density_sqrt * (1.0f / kNumParticles);
    const float gain = 1.0f / density;
    const float morph = in.p[1];
    const float q_sqrt = SemitonesToRatio(morph >= 0.5f ? (morph - 0.5f) * 120.0f : 0.0f);
    const float q = 0.5f + q_sqrt * q_sqrt;
    const float spread = 48.0f * in.p[2] * in.p[2];
    const float raw_diffusion_sqrt = 2.0f * fabsf(morph - 0.5f);
    const float raw_diffusion = raw_diffusion_sqrt * raw_diffusion_sqrt;
    const float diffusion = morph < 0.5f ? raw_diffusion : 0.0f;

    for (size_t i = 0; i < kBlock; ++i) out[i] = aux_[i] = 0.0f;
    for (int i = 0; i < kNumParticles; ++i) {
      particle_[i].Render(in.trigger, density, gain, f0, spread, q, out, aux_, kBlock);
    }
    post_filter_.set_f_q<stmlib::FREQUENCY_DIRTY>(f0 < 0.49f ? f0 : 0.49f, 0.5f);
    post_filter_.Process<stmlib::FILTER_MODE_LOW_PASS>(out, out, kBlock);
    diffuser_.Process(0.8f * diffusion * diffusion, 0.5f * diffusion + 0.25f, out, kBlock);
    SoftLimit(out, 2.0f);
  }
 private:
  static const int kNumParticles = 6;
  plaits::Particle particle_[kNumParticles];
  plaits::Diffuser diffuser_;
  stmlib::Svf post_filter_;
  float aux_[kBlock];
  uint16_t diffuser_buffer_[8192];
};

const ShEngineInfo kInfoPlaitsParticle = {
  "Prt", "Particle", "PLAITS",
  {
    SH_UNI("Den", "Density", 64),
    SH_UNI("Res", "Reso/Dif", 64),
    SH_UNI("Spr", "Spread", 40),
  },
  { 72, SH_AEG_AD, 0, 25, 0, 127 },
};

SH_DEFINE_ENGINE_FACTORY(PlaitsAnalogBD)
SH_DEFINE_ENGINE_FACTORY(PlaitsSynthBD)
SH_DEFINE_ENGINE_FACTORY(PlaitsAnalogSD)
SH_DEFINE_ENGINE_FACTORY(PlaitsSynthSD)
SH_DEFINE_ENGINE_FACTORY(PlaitsHat)
SH_DEFINE_ENGINE_FACTORY(PlaitsModal)
SH_DEFINE_ENGINE_FACTORY(PlaitsString)
SH_DEFINE_ENGINE_FACTORY(PlaitsParticle)

}  // namespace shard
