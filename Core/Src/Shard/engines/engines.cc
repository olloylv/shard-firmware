// engines.cc - engine registry and per channel engine storage
//
// Copyright (C) 2026 SHARD contributors.
// SPDX-License-Identifier: GPL-3.0-only

#include "engines.h"

#include <string.h>

namespace shard {

namespace {

struct Entry {
  const ShEngineInfo* info;
  EngineFactory create;
};

#define SH_ENGINE_ENTRY(T) { &kInfo##T, &Create##T },
const Entry kEngines[] = { SH_ENGINE_LIST(SH_ENGINE_ENTRY) };
#undef SH_ENGINE_ENTRY

const uint8_t kNumEngines = sizeof(kEngines) / sizeof(kEngines[0]);

// one storage block per channel; the active engine lives here
alignas(8) uint8_t storage[SH_NUM_CHANNELS][kEngineStorage];
Engine* engine[SH_NUM_CHANNELS];
uint8_t current[SH_NUM_CHANNELS] = { 0xff, 0xff, 0xff, 0xff, 0xff, 0xff };

}  // namespace

}  // namespace shard

using namespace shard;

extern "C" {

uint8_t sh_engineCount(void) { return kNumEngines; }

const ShEngineInfo* sh_engineInfo(uint8_t type) {
  return kEngines[type < kNumEngines ? type : 0].info;
}

void sh_engineSelect(uint8_t ch, uint8_t type) {
  if (ch >= SH_NUM_CHANNELS) return;
  if (type >= kNumEngines) type = 0;
  // engines have trivial destructors, the storage is simply reused
  memset(storage[ch], 0, kEngineStorage);
  engine[ch] = kEngines[type].create(storage[ch]);
  engine[ch]->Init();
  current[ch] = type;
}

uint8_t sh_engineCurrent(uint8_t ch) { return current[ch]; }

void sh_engineRender(uint8_t ch, const ShRenderIn* in, float* out) {
  Engine* e = engine[ch];
  if (!e) {
    for (size_t i = 0; i < kBlock; ++i) out[i] = 0.0f;
    return;
  }
  e->Render(*in, out);
}

void sh_engineApplyDefaults(uint8_t type, uint8_t* block, uint8_t withStrip) {
  const ShEngineInfo* info = sh_engineInfo(type);
  for (int i = 0; i < SH_NUM_ENGINE_PARAMS; ++i) {
    block[SHP_E0 + i] = info->params[i].type == SH_PT_NONE ? 0 : info->params[i].def;
  }
  if (!withStrip) return;
  const ShEngineDefaults& d = info->defaults;
  if (d.tune != 0xff) block[SHP_TUNE] = d.tune;
  block[SHP_FINE] = 64;
  if (d.aegMode != 0xff) block[SHP_AEG_MODE] = d.aegMode;
  if (d.attack != 0xff) block[SHP_ATTACK] = d.attack;
  if (d.decay != 0xff) block[SHP_DECAY] = d.decay;
  if (d.filterType != 0xff) block[SHP_FILT_TYPE] = d.filterType;
  if (d.filterFreq != 0xff) block[SHP_FILT_FREQ] = d.filterFreq;
}

// no exceptions / RTTI on the module: abort on a pure virtual call
void __cxa_pure_virtual(void) { while (1) { } }

}  // extern "C"
