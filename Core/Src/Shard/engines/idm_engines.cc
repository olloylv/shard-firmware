// idm_engines.cc - glitch / IDM oriented engines
//
// Copyright (C) 2026 SHARD contributors.
// SPDX-License-Identifier: GPL-3.0-only

#include "engines.h"
#include "stmlib/dsp/filter.h"

namespace shard {

using stmlib::Random;
using stmlib::SemitonesToRatio;

namespace {

inline float WhiteNoise() { return 2.0f * Random::GetFloat() - 1.0f; }

struct DecayEnv {
  float value, coef;
  void Init() { value = 0.0f; coef = 0.999f; }
  void Trigger(float v) { value = v; }
  void SetTime(float s) { coef = DecayCoef(s); }
  inline float Next() { value *= coef; return value; }
};

// one pole DC blocker
struct DcBlock {
  float x1, y1;
  void Init() { x1 = y1 = 0.0f; }
  inline float Process(float x) { y1 = x - x1 + 0.995f * y1; x1 = x; return y1; }
};

}  // namespace

// --- ZAP: very fast exponential pitch sweep with feedback FM -----------------

static const char kZapDirs[][4] = { "Dwn", "Up ", "Bth" };

class Zap : public Engine {
 public:
  void Init() override { phase_ = 0.0f; fb_ = 0.0f; amp_.Init(); sweep_.Init(); }
  void Render(const ShRenderIn& in, float* out) override {
    const float f0 = NoteToF0(in.note);
    const float depth = in.p[0] * 96.0f;               // up to 8 octaves
    sweep_.SetTime(ParamToTime(in.p[1], 0.0005f, 0.12f));
    const float fb = in.p[2] * in.p[2] * 1.5f;
    amp_.SetTime(ParamToTime(in.p[3], 0.005f, 1.0f));
    const uint8_t dir = in.idx[4];
    if (in.trigger) {
      phase_ = 0.0f;
      amp_.Trigger(0.6f + 0.4f * in.accent);
      sweep_.Trigger(1.0f);
    }
    for (size_t i = 0; i < kBlock; ++i) {
      const float e = sweep_.Next();
      float semis;
      if (dir == 0) semis = depth * e;
      else if (dir == 1) semis = -depth * e;
      else semis = depth * (2.0f * e - 1.0f) * e;
      float f = f0 * SemitonesToRatio(semis);
      if (f > 0.45f) f = 0.45f;
      phase_ += f;
      if (phase_ >= 1.0f) phase_ -= 1.0f;
      float ph = phase_ + fb * fb_;
      ph -= floorf(ph);
      const float s = Sine(ph);
      fb_ = 0.5f * (fb_ + s);
      out[i] = s * amp_.Next();
    }
  }
 private:
  float phase_, fb_;
  DecayEnv amp_, sweep_;
};

const ShEngineInfo kInfoZap = {
  "Zap", "Zap", "IDM",
  {
    SH_UNI("Dep", "Depth", 90),
    SH_UNI("Tim", "SwpTime", 30),
    SH_UNI("FB", "Feedback", 30),
    SH_UNI("Dec", "Decay", 70),
    SH_LIST("Dir", "Directn", 0, 3, kZapDirs),
  },
  { 40, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- CRUSH: source -> sample&hold with jitter -> bit reduction ---------------

static const char kCrushSources[][4] = { "Noi", "Sqr", "Saw", "FM " };

class Crush : public Engine {
 public:
  void Init() override {
    phase_ = mphase_ = 0.0f; hold_ = 0.0f; clock_ = 0.0f; next_ = 1.0f;
    amp_.Init();
  }
  void Render(const ShRenderIn& in, float* out) override {
    const float f0 = NoteToF0(in.note);
    // resampling rate: 44.1k down to ~150 Hz
    const float rate = SemitonesToRatio(-in.p[1] * 96.0f);
    const float bits = 1.0f + (1.0f - in.p[2]) * 15.0f;
    const float levels = powf(2.0f, bits - 1.0f);
    const float jitter = in.p[3];
    amp_.SetTime(ParamToTime(in.p[4], 0.005f, 2.0f));
    const float glitch = in.p[5] * in.p[5];
    const uint8_t src = in.idx[0];
    if (in.trigger) {
      amp_.Trigger(0.6f + 0.4f * in.accent);
      phase_ = 0.0f;
    }
    for (size_t i = 0; i < kBlock; ++i) {
      phase_ += f0 > 0.45f ? 0.45f : f0;
      if (phase_ >= 1.0f) phase_ -= 1.0f;
      float s;
      switch (src) {
        case 0: s = WhiteNoise(); break;
        case 1: s = phase_ < 0.5f ? 0.8f : -0.8f; break;
        case 2: s = 2.0f * phase_ - 1.0f; break;
        default: {
          mphase_ += f0 * 3.17f;
          mphase_ -= floorf(mphase_);
          float ph = phase_ + 0.8f * Sine(mphase_);
          ph -= floorf(ph);
          s = Sine(ph);
        } break;
      }
      clock_ += rate;
      if (clock_ >= next_) {
        clock_ -= next_;
        next_ = 1.0f + jitter * 4.0f * Random::GetFloat();
        // glitch: sometimes keep the old sample (stutter)
        if (Random::GetFloat() >= glitch) hold_ = s;
      }
      float q = floorf(hold_ * levels + 0.5f) / levels;
      out[i] = q * amp_.Next();
    }
  }
 private:
  float phase_, mphase_, hold_, clock_, next_;
  DecayEnv amp_;
};

const ShEngineInfo kInfoCrush = {
  "Crs", "Crush", "IDM",
  {
    SH_LIST("Src", "Source", 0, 4, kCrushSources),
    SH_UNI("Rat", "Rate Red", 50),
    SH_UNI("Bit", "BitRed", 60),
    SH_UNI("Jit", "Jitter", 20),
    SH_UNI("Dec", "Decay", 70),
    SH_UNI("Glt", "Glitch", 0),
  },
  { 60, SH_AEG_OFF, 0, 127, 0, 127 },
};

// --- BYTE: bytebeat formulas, the note sets the playback speed ----------------

static const char kByteFormulas[][4] = { "F1 ", "F2 ", "F3 ", "F4 ", "F5 ", "F6 ", "F7 ", "F8 " };

class Byte : public Engine {
 public:
  void Init() override { t_ = 0.0f; dc_.Init(); }
  void Render(const ShRenderIn& in, float* out) override {
    // at note 60 the counter runs at 8 kHz, the classic bytebeat rate
    const float inc = (8000.0f / kSampleRate) * SemitonesToRatio(in.note - 60.0f);
    const uint32_t a = 1 + static_cast<uint32_t>(in.p[1] * 15.0f);
    const uint32_t b = 1 + static_cast<uint32_t>(in.p[2] * 15.0f);
    const uint8_t formula = in.idx[0];
    if (in.trigger && in.idx[3]) t_ = 0.0f;
    for (size_t i = 0; i < kBlock; ++i) {
      t_ += inc;
      if (t_ > 16777216.0f) t_ -= 16777216.0f;
      const uint32_t t = static_cast<uint32_t>(t_);
      uint32_t v;
      switch (formula) {
        case 0: v = t * ((t >> a) | (t >> (b + 4))); break;
        case 1: v = (t * a) & (t >> (b + 2)); break;
        case 2: v = t * (((t >> 12) | (t >> 8)) & (63 & (t >> (a & 7)))); break;
        case 3: v = (t >> a) ^ (t >> b) ^ (t * (a + b)); break;
        case 4: v = (t * (t >> (a + 3)) | (t >> (b + 1))) ^ (t >> 7); break;
        case 5: v = (t & (t >> a)) * (b + 1); break;
        case 6: v = ((t * a) % (b * 32 + 1)) ^ (t >> 4); break;
        default: v = (t >> (a & 7)) * ((t >> (b & 7)) % 7 + 1) | (t >> 6); break;
      }
      const float s = (static_cast<float>(v & 0xff) - 128.0f) * (1.0f / 128.0f);
      out[i] = dc_.Process(s) * 0.8f;
    }
  }
 private:
  float t_;
  DcBlock dc_;
};

const ShEngineInfo kInfoByte = {
  "Byt", "Bytebeat", "IDM",
  {
    SH_LIST("Frm", "Formula", 0, 8, kByteFormulas),
    SH_UNI("A", "Param A", 40),
    SH_UNI("B", "Param B", 60),
    SH_ONOFF("Rst", "Reset", 1),
  },
  { 60, SH_AEG_AD, 0, 25, 0, 127 },
};

// --- RING: six oscillators, ring modulated in pairs, band passed --------------

static const char kRingWaves[][4] = { "Sqr", "Sin" };

class Ring : public Engine {
 public:
  void Init() override {
    for (int i = 0; i < 6; ++i) phase_[i] = Random::GetFloat();
    bp_.Init();
  }
  void Render(const ShRenderIn& in, float* out) override {
    static const float kHarm[6] = { 1.0f, 2.0f, 3.0f, 4.0f, 5.0f, 6.0f };
    static const float kMetal[6] = { 1.0f, 1.483f, 1.932f, 2.546f, 3.17f, 4.07f };
    const float f0 = NoteToF0(in.note);
    const float spread = in.p[0];
    const float ring = in.p[1];
    float fc = 0.01f * SemitonesToRatio(in.p[2] * 72.0f);
    if (fc > 0.45f) fc = 0.45f;
    bp_.set_f_q<stmlib::FREQUENCY_FAST>(fc, 0.6f + in.p[3] * 8.0f);
    const bool sine = in.idx[4];
    float inc[6];
    for (int k = 0; k < 6; ++k) {
      inc[k] = f0 * (kHarm[k] + spread * (kMetal[k] - kHarm[k]));
      if (inc[k] > 0.49f) inc[k] = 0.49f;
    }
    for (size_t i = 0; i < kBlock; ++i) {
      float o[6];
      for (int k = 0; k < 6; ++k) {
        phase_[k] += inc[k];
        if (phase_[k] >= 1.0f) phase_[k] -= 1.0f;
        o[k] = sine ? Sine(phase_[k]) : (phase_[k] < 0.5f ? 1.0f : -1.0f);
      }
      const float rm = o[0] * o[1] + o[2] * o[3] + o[4] * o[5];
      const float sum = o[0] + o[1] + o[2] + o[3] + o[4] + o[5];
      const float x = (ring * rm + (1.0f - ring) * sum * 0.5f) * 0.33f;
      out[i] = bp_.Process<stmlib::FILTER_MODE_BAND_PASS>(x) * 0.85f;
    }
  }
 private:
  float phase_[6];
  stmlib::Svf bp_;
};

const ShEngineInfo kInfoRing = {
  "Rng", "RingClst", "IDM",
  {
    SH_UNI("Spr", "Spread", 90),
    SH_UNI("RM", "RingMix", 90),
    SH_UNI("Ton", "Tone", 80),
    SH_UNI("Res", "Reso", 30),
    SH_LIST("Wav", "Waveform", 0, 2, kRingWaves),
  },
  { 60, SH_AEG_AD, 0, 22, 0, 127 },
};

// --- COMB: exciter into two tuned comb filters with feedback ------------------

static const char kCombExciters[][4] = { "Imp", "Noi", "Clk", "Saw" };

class Comb : public Engine {
 public:
  void Init() override {
    for (size_t i = 0; i < kSize; ++i) d1_[i] = d2_[i] = 0.0f;
    w_ = 0; lp1_ = lp2_ = 0.0f; burst_ = 0; burst_phase_ = 0.0f; dc_.Init();
  }
  void Render(const ShRenderIn& in, float* out) override {
    const float f0 = NoteToF0(in.note);
    float delay1 = 1.0f / (f0 > 0.0005f ? f0 : 0.0005f);
    if (delay1 > kSize - 4) delay1 = kSize - 4;
    if (delay1 < 2.0f) delay1 = 2.0f;
    const float ratio = 1.0f + in.p[4] * 2.3f;     // second comb, inharmonic
    float delay2 = delay1 / ratio;
    if (delay2 < 2.0f) delay2 = 2.0f;
    float fb = BiNorm(in.p[1]) * 0.995f;
    if (fb > 0.995f) fb = 0.995f;  // bipolar feedback
    const float damp = 1.0f - in.p[2] * 0.95f;
    const int burst_len = 1 + static_cast<int>(in.p[3] * in.p[3] * 0.03f * kSampleRate);
    const float mix2 = in.p[5];
    const uint8_t exc = in.idx[0];
    if (in.trigger) {
      burst_ = burst_len;
      burst_total_ = burst_len;
      level_ = 0.5f + 0.5f * in.accent;
      burst_phase_ = 0.0f;
    }
    for (size_t i = 0; i < kBlock; ++i) {
      float x = 0.0f;
      if (burst_ > 0) {
        const float env = static_cast<float>(burst_) / burst_total_;
        switch (exc) {
          case 0: x = (burst_ == burst_total_) ? 1.0f : 0.0f; break;
          case 1: x = WhiteNoise() * env; break;
          case 2: x = (burst_ > burst_total_ - 3) ? 1.0f : -0.3f * env; break;
          default:
            burst_phase_ += f0 * 2.0f;
            burst_phase_ -= floorf(burst_phase_);
            x = (2.0f * burst_phase_ - 1.0f) * env;
            break;
        }
        x *= level_ * 3.0f;
        --burst_;
      }
      const float y1 = Read(d1_, delay1);
      const float y2 = Read(d2_, delay2);
      lp1_ += damp * (y1 - lp1_);
      lp2_ += damp * (y2 - lp2_);
      d1_[w_] = x + fb * lp1_;
      d2_[w_] = x + fb * lp2_;
      w_ = (w_ + 1) & (kSize - 1);
      out[i] = stmlib::SoftClip(dc_.Process(y1 + mix2 * y2) * 0.7f);
    }
  }
 private:
  static const size_t kSize = 2048;   // ~21 Hz lowest pitch
  inline float Read(const float* d, float delay) const {
    const float r = static_cast<float>(w_) - delay + kSize;
    const int32_t i = static_cast<int32_t>(r);
    const float frac = r - i;
    const float a = d[i & (kSize - 1)];
    const float b = d[(i + 1) & (kSize - 1)];
    return a + (b - a) * frac;
  }
  float d1_[kSize], d2_[kSize];
  size_t w_;
  float lp1_, lp2_;
  int burst_, burst_total_;
  float burst_phase_, level_;
  DcBlock dc_;
};

const ShEngineInfo kInfoComb = {
  "Cmb", "Comb", "IDM",
  {
    SH_LIST("Exc", "Exciter", 1, 4, kCombExciters),
    SH_BI("FB", "Feedback", 122),
    SH_UNI("Dmp", "Damping", 30),
    SH_UNI("Bur", "BurstLen", 20),
    SH_UNI("Rat", "Ratio2", 40),
    SH_UNI("Mx2", "Comb2Mix", 50),
  },
  { 48, SH_AEG_AD, 0, 45, 0, 127 },
};

SH_DEFINE_ENGINE_FACTORY(Zap)
SH_DEFINE_ENGINE_FACTORY(Crush)
SH_DEFINE_ENGINE_FACTORY(Byte)
SH_DEFINE_ENGINE_FACTORY(Ring)
SH_DEFINE_ENGINE_FACTORY(Comb)

}  // namespace shard
