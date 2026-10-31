# Host (x86/ARM desktop) build of the SHARD sound engines, for listening tests.
#
#   cmake -S tools/host -B build/host && cmake --build build/host
#   build/host/shard_render out/          # one WAV per engine + a demo loop
#
# SPDX-License-Identifier: GPL-3.0-only
cmake_minimum_required(VERSION 3.16)
project(shard_host C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

set(ROOT ${CMAKE_CURRENT_LIST_DIR}/../..)
set(CORE ${ROOT}/Core)
set(DSP ${CORE}/Src/Soundengine/DSPAudio)

add_executable(shard_render
  render.cc
  host_stubs.c
  # SHARD
  ${CORE}/Src/Shard/sh_channel.c
  ${CORE}/Src/Shard/engines/engines.cc
  ${CORE}/Src/Shard/engines/lxr_engines.cc
  ${CORE}/Src/Shard/engines/plaits_engines.cc
  ${CORE}/Src/Shard/engines/md_engines.cc
  ${CORE}/Src/Shard/engines/idm_engines.cc
  # third party
  ${CORE}/ThirdParty/stmlib/dsp/units.cc
  ${CORE}/ThirdParty/stmlib/utils/random.cc
  ${CORE}/ThirdParty/plaits/resources.cc
  ${CORE}/ThirdParty/plaits/dsp/physical_modelling/modal_voice.cc
  ${CORE}/ThirdParty/plaits/dsp/physical_modelling/resonator.cc
  ${CORE}/ThirdParty/plaits/dsp/physical_modelling/string.cc
  ${CORE}/ThirdParty/plaits/dsp/physical_modelling/string_voice.cc
  # LXR DSP blocks
  ${DSP}/Oscillator.c
  ${DSP}/wavetable.c
  ${DSP}/Decay.c
  ${DSP}/SlopeEg2.c
  ${DSP}/ResonantFilter.c
  ${DSP}/distortion.c
  ${DSP}/transientGenerator.c
  ${DSP}/transientTables.c
  ${DSP}/snapEg.c
  ${DSP}/1PoleLp.c
  ${DSP}/BufferTools.c
  ${DSP}/dither.c
  ${DSP}/Samples.c
)
# stubs first so that "stm32f7xx_hal.h" and "main.h" resolve to the host versions
target_include_directories(shard_render PRIVATE
  ${CMAKE_CURRENT_LIST_DIR}/stubs
  ${CORE}/Inc
  ${CORE}/ThirdParty
  ${CORE}/Src/Shard/engines
)
target_compile_definitions(shard_render PRIVATE SHARD_HOST=1 TEST=1)
target_compile_options(shard_render PRIVATE
  $<$<COMPILE_LANGUAGE:C>:-Wno-unused-parameter -Wno-int-conversion -Wno-incompatible-pointer-types>
  $<$<COMPILE_LANGUAGE:CXX>:-fno-exceptions -fno-rtti -Wall>
)
target_link_libraries(shard_render PRIVATE m)
