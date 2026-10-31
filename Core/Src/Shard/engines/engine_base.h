// engine_base.h - base class and helpers for SHARD sound engines
//
// Copyright (C) 2026 SHARD contributors.
// SPDX-License-Identifier: GPL-3.0-only

#ifndef SHARD_ENGINE_BASE_H_
#define SHARD_ENGINE_BASE_H_

#include <stddef.h>
#include <stdint.h>
#include <math.h>
#include <new>

#include "Shard/sh_engine.h"
#include "stmlib/dsp/dsp.h"
#include "stmlib/dsp/units.h"
#include "stmlib/utils/random.h"
#include "plaits/resources.h"

namespace shard {

const size_t kBlock = SH_BLOCK_SIZE;
const float kSampleRate = SH_SAMPLE_RATE;

class Engine {
 public:
  virtual void Init() = 0;
  virtual void Render(const ShRenderIn& in, float* out) = 0;
};

// MIDI note -> frequency normalised to the sample rate (like plaits::NoteToFrequency)
inline float NoteToF0(float note) {
  note -= 69.0f;
  CONSTRAIN(note, -128.0f, 127.0f);
  return (440.0f / kSampleRate) * stmlib::SemitonesToRatio(note);
}

// seconds -> per sample multiplier of an exponential decay that falls by
// 60 dB in t seconds
inline float DecayCoef(float t) {
  if (t < 0.0001f) t = 0.0001f;
  return expf(-6.9077553f / (t * kSampleRate));
}

// 0..1 parameter -> time in seconds, exponential between t_min and t_max
inline float ParamToTime(float p, float t_min, float t_max) {
  return t_min * powf(t_max / t_min, p);
}

// bipolar parameter (SH_PT_BI, stored 0..127, 64 = centre) -> -64..+63
inline float Bi(float p) { return p * 127.0f - 64.0f; }
// bipolar parameter -> -1..+1 (approximately)
inline float BiNorm(float p) { return Bi(p) * (1.0f / 64.0f); }

inline float Clamp01(float x) { return x < 0.0f ? 0.0f : (x > 1.0f ? 1.0f : x); }

inline float FastTanh(float x) {
  if (x < -3.0f) return -1.0f;
  if (x > 3.0f) return 1.0f;
  const float x2 = x * x;
  return x * (27.0f + x2) / (27.0f + 9.0f * x2);
}

// polynomial sine of a phase 0..1
inline float Sine(float phase) {
  return stmlib::InterpolateWrap(plaits::lut_sine, phase, 512.0f);
}

}  // namespace shard

// descriptor helpers
#define SH_UNI(s, l, d)        { s, l, SH_PT_UNI, d, 0, nullptr }
#define SH_BI(s, l, d)         { s, l, SH_PT_BI, d, 0, nullptr }
#define SH_ONOFF(s, l, d)      { s, l, SH_PT_ONOFF, d, 2, nullptr }
#define SH_LIST(s, l, d, n, t) { s, l, SH_PT_LIST, d, n, t }
#define SH_UNUSED              { "", "", SH_PT_NONE, 0, 0, nullptr }

#endif  // SHARD_ENGINE_BASE_H_
