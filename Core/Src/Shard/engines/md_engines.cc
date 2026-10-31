// md_engines.cc - Machinedrum inspired engines (TRX, EFM, GND)
//
// Copyright (C) 2026 SHARD contributors.
// SPDX-License-Identifier: GPL-3.0-only
//
// These are original implementations written from the published behaviour of
// the Machinedrum machine families; no Elektron code is used.

#include "engines.h"
#include "stmlib/dsp/filter.h"

namespace shard {

using stmlib::Random;
using stmlib::SemitonesToRatio;

namespace {

inline float WhiteNoise() { return 2.0f * Random::GetFloat() - 1.0f; }

// simple exponential decay envelope
struct DecayEnv {
  float value;
  float coef;
  void Init() { value = 0.0f; coef = 0.999f; }
  void Trigger(float v) { value = v; }
  void SetTime(float seconds) { coef = DecayCoef(seconds); }
  inline float Next() { value *= coef; return value; }
};

}  // namespace

// --- TRX BD: sine kick with pitch sweep, hold, click and drive ---------------

class TrxBD : public Engine {
 public:
  void Init() override {
    phase_ = 0.0f; amp_.Init(); pitch_.Init(); click_.Init(); hold_ = 0;
    click_lp_ = 0.0f;
  }
  void Render(const ShRenderIn& in, float* out) override {
    const float f0 = NoteToF0(in.note);
    const float sweep_semis = in.p[0] * 60.0f;
    pitch_.SetTime(ParamToTime(in.p[1], 0.002f, 0.25f));
    amp_.SetTime(ParamToTime(in.p[2], 0.04f, 3.0f));
    const int hold_samples = static_cast<int>(in.p[3] * in.p[3] * 0.12f * kSampleRate);
    const float click = in.p[4];
    const float drive = 1.0f + in.p[5] * in.p[5] * 12.0f;
    const float drive_norm = 1.0f / FastTanh(drive);
    click_.SetTime(0.004f);

    if (in.trigger) {
      phase_ = 0.0f;
      amp_.Trigger(0.6f + 0.4f * in.accent);
      pitch_.Trigger(1.0f);
      click_.Trigger(1.0f);
      hold_ = hold_samples;
    }
    for (size_t i = 0; i < kBlock; ++i) {
      const float p = pitch_.Next();
      float f = f0 * SemitonesToRatio(sweep_semis * p);
      if (f > 0.45f) f = 0.45f;
      phase_ += f;
      if (phase_ >= 1.0f) phase_ -= 1.0f;
      float a;
      if (hold_ > 0) { --hold_; a = amp_.value; } else { a = amp_.Next(); }
      float s = Sine(phase_) * a;
      // click: high passed noise burst
      const float n = WhiteNoise() * click_.Next();
      click_lp_ += 0.3f * (n - click_lp_);
      s += click * 1.5f * (n - click_lp_);
      out[i] = FastTanh(s * drive) * drive_norm;
    }
  }
 private:
  float phase_;
  DecayEnv amp_, pitch_, click_;
  int hold_;
  float click_lp_;
};

const ShEngineInfo kInfoTrxBD = {
  "tBD", "TRX-BD", "MD-STYLE",
  {
    SH_UNI("Swp", "Sweep", 50),
    SH_UNI("SwD", "SweepDec", 40),
    SH_UNI("Dec", "Decay", 60),
    SH_UNI("Hld", "Hold", 0),
    SH_UNI("Clk", "Click", 40),
    SH_UNI("Drv", "Drive", 20),
  },
  { 33, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- TRX SD: two detuned sines with sweep + band passed noise ----------------

class TrxSD : public Engine {
 public:
  void Init() override {
    phase1_ = phase2_ = 0.0f;
    body_.Init(); noise_.Init(); pitch_.Init();
    noise_filter_.Init();
  }
  void Render(const ShRenderIn& in, float* out) override {
    const float f0 = NoteToF0(in.note);
    const float body_level = in.p[0];
    const float snap_level = in.p[1];
    body_.SetTime(ParamToTime(in.p[2], 0.02f, 0.8f));
    noise_.SetTime(ParamToTime(in.p[3], 0.02f, 1.0f));
    const float sweep = in.p[4] * 24.0f;
    pitch_.SetTime(0.012f);
    float nf = 0.02f * SemitonesToRatio(in.p[5] * 60.0f);
    if (nf > 0.45f) nf = 0.45f;
    noise_filter_.set_f_q<stmlib::FREQUENCY_FAST>(nf, 0.8f);

    if (in.trigger) {
      const float a = 0.6f + 0.4f * in.accent;
      phase1_ = phase2_ = 0.0f;
      body_.Trigger(a); noise_.Trigger(a); pitch_.Trigger(1.0f);
    }
    for (size_t i = 0; i < kBlock; ++i) {
      const float pr = SemitonesToRatio(sweep * pitch_.Next());
      phase1_ += f0 * pr; if (phase1_ >= 1.0f) phase1_ -= 1.0f;
      phase2_ += f0 * pr * 1.47f; if (phase2_ >= 1.0f) phase2_ -= 1.0f;
      const float b = body_.Next();
      const float body = (Sine(phase1_) + 0.6f * Sine(phase2_)) * 0.6f * b;
      const float n = noise_filter_.Process<stmlib::FILTER_MODE_HIGH_PASS>(WhiteNoise());
      out[i] = 0.75f * (body * body_level + n * noise_.Next() * snap_level);
    }
  }
 private:
  float phase1_, phase2_;
  DecayEnv body_, noise_, pitch_;
  stmlib::Svf noise_filter_;
};

const ShEngineInfo kInfoTrxSD = {
  "tSD", "TRX-SD", "MD-STYLE",
  {
    SH_UNI("Bdy", "Body", 90),
    SH_UNI("Snp", "Snappy", 90),
    SH_UNI("Dec", "BodyDec", 40),
    SH_UNI("NDc", "NoiseDec", 50),
    SH_UNI("Swp", "Sweep", 40),
    SH_UNI("NTn", "NoiseTon", 70),
  },
  { 52, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- TRX CP: multi burst hand clap -------------------------------------------

static const char kClapCounts[][4] = { "  1", "  2", "  3", "  4", "  5", "  6", "  7", "  8" };

class TrxClap : public Engine {
 public:
  void Init() override {
    env_ = 0.0f; tail_.Init(); bursts_left_ = 0; counter_ = 0; filter_.Init();
  }
  void Render(const ShRenderIn& in, float* out) override {
    tail_.SetTime(ParamToTime(in.p[0], 0.05f, 1.5f));
    const float spacing = ParamToTime(in.p[1], 0.003f, 0.04f) * kSampleRate;
    const int num = in.idx[2] + 1;
    const float jitter = in.p[4];
    const float burst_coef = DecayCoef(spacing / kSampleRate * 1.2f);
    float fc = NoteToF0(in.note);
    if (fc > 0.4f) fc = 0.4f;
    filter_.set_f_q<stmlib::FREQUENCY_FAST>(fc, 0.7f + in.p[3] * 4.0f);

    if (in.trigger) {
      level_ = 0.6f + 0.4f * in.accent;
      bursts_left_ = num;
      counter_ = 0;
      tail_.Trigger(0.0f);
    }
    for (size_t i = 0; i < kBlock; ++i) {
      if (bursts_left_ > 0 && --counter_ <= 0) {
        --bursts_left_;
        env_ = level_;
        const float j = 1.0f + jitter * (Random::GetFloat() - 0.5f);
        counter_ = static_cast<int>(spacing * j);
        if (bursts_left_ == 0) tail_.Trigger(level_ * 0.8f);
      }
      env_ *= burst_coef;
      const float e = env_ + tail_.Next();
      const float n = filter_.Process<stmlib::FILTER_MODE_BAND_PASS>(WhiteNoise());
      out[i] = n * e * 1.4f;
    }
  }
 private:
  float env_, level_;
  DecayEnv tail_;
  int bursts_left_, counter_;
  stmlib::Svf filter_;
};

const ShEngineInfo kInfoTrxClap = {
  "tCP", "TRX-CP", "MD-STYLE",
  {
    SH_UNI("Dec", "Decay", 50),
    SH_UNI("Spc", "Spacing", 50),
    SH_LIST("Num", "Claps", 3, 8, kClapCounts),
    SH_UNI("Q", "Reso", 30),
    SH_UNI("Rnd", "Random", 30),
  },
  { 96, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- TRX HH: six square oscillators (808 ratios) + noise ---------------------

class TrxHat : public Engine {
 public:
  void Init() override {
    for (int i = 0; i < 6; ++i) phase_[i] = Random::GetFloat();
    amp_.Init(); bp_.Init(); hp_.Init();
  }
  void Render(const ShRenderIn& in, float* out) override {
    static const float kRatios[6] = { 1.0f, 1.304f, 1.466f, 1.787f, 1.932f, 2.536f };
    const float f0 = NoteToF0(in.note) * 0.25f;
    float fc = 0.08f * SemitonesToRatio(in.p[0] * 36.0f);
    if (fc > 0.45f) fc = 0.45f;
    bp_.set_f_q<stmlib::FREQUENCY_FAST>(fc, 1.0f + in.p[4] * 4.0f);
    hp_.set_f_q<stmlib::FREQUENCY_FAST>(fc * 0.8f, 0.7f);
    amp_.SetTime(ParamToTime(in.alt ? in.p[3] : in.p[1], 0.01f, 1.5f));
    const float metal = in.p[2];

    if (in.trigger) amp_.Trigger(0.6f + 0.4f * in.accent);
    float inc[6];
    for (int k = 0; k < 6; ++k) {
      inc[k] = f0 * kRatios[k];
      if (inc[k] > 0.49f) inc[k] = 0.49f;
    }
    for (size_t i = 0; i < kBlock; ++i) {
      float sq = 0.0f;
      for (int k = 0; k < 6; ++k) {
        phase_[k] += inc[k];
        if (phase_[k] >= 1.0f) phase_[k] -= 1.0f;
        sq += phase_[k] < 0.5f ? 1.0f : -1.0f;
      }
      const float x = metal * sq * (1.0f / 6.0f) + (1.0f - metal) * WhiteNoise();
      float y = bp_.Process<stmlib::FILTER_MODE_BAND_PASS>(x);
      y = hp_.Process<stmlib::FILTER_MODE_HIGH_PASS>(y);
      out[i] = y * amp_.Next() * 2.0f;
    }
  }
 private:
  float phase_[6];
  DecayEnv amp_;
  stmlib::Svf bp_, hp_;
};

const ShEngineInfo kInfoTrxHat = {
  "tHH", "TRX-HH", "MD-STYLE",
  {
    SH_UNI("Ton", "Tone", 64),
    SH_UNI("Dec", "Decay", 25),
    SH_UNI("Mtl", "Metal", 80),
    SH_UNI("Opn", "OpenDec", 85),
    SH_UNI("Res", "Reso", 20),
  },
  { 80, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- EFM: two operator FM percussion -----------------------------------------

static const char kEfmRatios[][4] = {
  "0.5", "  1", "1.4", "1.5", "  2", "2.7", "  3", "3.1",
  "3.5", "  4", "5.2", "  5", "  6", "  7", "  8", " 11",
};
static const float kEfmRatioValues[] = {
  0.5f, 1.0f, 1.41421f, 1.5f, 2.0f, 2.7183f, 3.0f, 3.14159f,
  3.5f, 4.0f, 5.19f, 5.0f, 6.0f, 7.0f, 8.0f, 11.0f,
};

class Efm : public Engine {
 public:
  void Init() override {
    phase_c_ = phase_m_ = 0.0f; fb_state_ = 0.0f;
    amp_.Init(); mod_.Init(); pitch_.Init();
  }
  void Render(const ShRenderIn& in, float* out) override {
    const float f0 = NoteToF0(in.note);
    const float ratio = kEfmRatioValues[in.idx[0] & 15];
    const float index = in.p[1] * in.p[1] * 6.0f;
    mod_.SetTime(ParamToTime(in.p[2], 0.003f, 1.5f));
    const float fb = in.p[3] * 0.9f;
    const float sweep = in.p[4] * 48.0f;
    pitch_.SetTime(ParamToTime(in.p[5], 0.002f, 0.3f));
    amp_.SetTime(ParamToTime(in.p[6], 0.02f, 3.0f));
    const float noise = in.p[7];

    if (in.trigger) {
      const float a = 0.6f + 0.4f * in.accent;
      phase_c_ = phase_m_ = 0.0f;
      amp_.Trigger(a); mod_.Trigger(1.0f); pitch_.Trigger(1.0f);
    }
    for (size_t i = 0; i < kBlock; ++i) {
      float fc = f0 * SemitonesToRatio(sweep * pitch_.Next());
      if (fc > 0.45f) fc = 0.45f;
      phase_m_ += fc * ratio;
      while (phase_m_ >= 1.0f) phase_m_ -= 1.0f;
      phase_c_ += fc;
      if (phase_c_ >= 1.0f) phase_c_ -= 1.0f;
      float m = Sine(phase_m_ + fb * fb_state_);
      fb_state_ = m;
      m += noise * WhiteNoise();
      const float pm = index * mod_.Next() * m;
      float ph = phase_c_ + pm;
      ph -= floorf(ph);
      out[i] = Sine(ph) * amp_.Next();
    }
  }
 private:
  float phase_c_, phase_m_, fb_state_;
  DecayEnv amp_, mod_, pitch_;
};

const ShEngineInfo kInfoEfm = {
  "EFM", "EFM", "MD-STYLE",
  {
    SH_LIST("Rat", "Ratio", 4, 16, kEfmRatios),
    SH_UNI("Mod", "FM Index", 60),
    SH_UNI("MDc", "ModDecay", 40),
    SH_UNI("FB", "Feedback", 0),
    SH_UNI("Swp", "Sweep", 30),
    SH_UNI("SwD", "SweepDec", 30),
    SH_UNI("Dec", "Decay", 50),
    SH_UNI("Noi", "Noise", 0),
  },
  { 45, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- GND: raw generators (sine, tri, saw, square, noise, impulse, S&H) --------

static const char kGndWaves[][4] = { "Sin", "Tri", "Saw", "Sqr", "Noi", "Imp", "S&H" };

class Gnd : public Engine {
 public:
  void Init() override { phase_ = 0.0f; pitch_.Init(); sh_ = 0.0f; }
  void Render(const ShRenderIn& in, float* out) override {
    const float f0 = NoteToF0(in.note);
    const float sweep = BiNorm(in.p[1]) * 48.0f;
    pitch_.SetTime(ParamToTime(in.p[2], 0.002f, 1.0f));
    const uint8_t wave = in.idx[0];
    if (in.trigger) { phase_ = 0.0f; pitch_.Trigger(1.0f); }
    for (size_t i = 0; i < kBlock; ++i) {
      float f = f0 * SemitonesToRatio(sweep * pitch_.Next());
      if (f > 0.49f) f = 0.49f;
      phase_ += f;
      const bool wrap = phase_ >= 1.0f;
      if (wrap) phase_ -= 1.0f;
      float s;
      switch (wave) {
        case 0: s = Sine(phase_); break;
        case 1: s = phase_ < 0.5f ? 4.0f * phase_ - 1.0f : 3.0f - 4.0f * phase_; break;
        case 2: s = 2.0f * phase_ - 1.0f; break;
        case 3: s = phase_ < 0.5f ? 0.8f : -0.8f; break;
        case 4: s = WhiteNoise(); break;
        case 5: s = wrap ? 1.0f : 0.0f; break;
        default: if (wrap) sh_ = WhiteNoise(); s = sh_; break;
      }
      out[i] = s;
    }
  }
 private:
  float phase_, sh_;
  DecayEnv pitch_;
};

const ShEngineInfo kInfoGnd = {
  "GND", "GND", "MD-STYLE",
  {
    SH_LIST("Wav", "Waveform", 0, 7, kGndWaves),
    SH_BI("Swp", "Sweep", 64),
    SH_UNI("SwD", "SweepDec", 40),
  },
  { 48, SH_AEG_AD, 0, 20, 0, 127 },
};

SH_DEFINE_ENGINE_FACTORY(TrxBD)
SH_DEFINE_ENGINE_FACTORY(TrxSD)
SH_DEFINE_ENGINE_FACTORY(TrxClap)
SH_DEFINE_ENGINE_FACTORY(TrxHat)
SH_DEFINE_ENGINE_FACTORY(Efm)
SH_DEFINE_ENGINE_FACTORY(Gnd)

}  // namespace shard
