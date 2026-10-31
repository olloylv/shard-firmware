// engines.h - list of all SHARD engines
//
// Copyright (C) 2026 SHARD contributors.
// SPDX-License-Identifier: GPL-3.0-only

#ifndef SHARD_ENGINES_H_
#define SHARD_ENGINES_H_

#include "engine_base.h"

namespace shard {

// Every channel owns one block of this size; the selected engine is
// constructed into it with placement new.
const size_t kEngineStorage = 17 * 1024;

typedef Engine* (*EngineFactory)(void* mem);

#define SH_DEFINE_ENGINE_FACTORY(T)                                  \
  static_assert(sizeof(T) <= kEngineStorage, #T " is too large");     \
  Engine* Create##T(void* mem) { return new (mem) T(); }

#define SH_DECLARE_ENGINE(T)              \
  extern const ShEngineInfo kInfo##T;     \
  Engine* Create##T(void* mem);

// The order of this list is the order of the ENG parameter, which is stored in
// kits. Only append new engines at the end of their group's free range
// (see engines.cc).
#define SH_ENGINE_LIST(X)          \
  /* LXR classics */               \
  X(LxrDrum)                       \
  X(LxrSnare)                      \
  X(LxrCymbal)                     \
  X(LxrHat)                        \
  /* Plaits */                     \
  X(PlaitsAnalogBD)                \
  X(PlaitsSynthBD)                 \
  X(PlaitsAnalogSD)                \
  X(PlaitsSynthSD)                 \
  X(PlaitsHat)                     \
  X(PlaitsModal)                   \
  X(PlaitsString)                  \
  X(PlaitsParticle)                \
  /* Machinedrum style */          \
  X(TrxBD)                         \
  X(TrxSD)                         \
  X(TrxClap)                       \
  X(TrxHat)                        \
  X(Efm)                           \
  X(Gnd)                           \
  /* IDM / glitch */               \
  X(Zap)                           \
  X(Crush)                         \
  X(Byte)                          \
  X(Ring)                          \
  X(Comb)

SH_ENGINE_LIST(SH_DECLARE_ENGINE)

}  // namespace shard

#endif  // SHARD_ENGINES_H_
