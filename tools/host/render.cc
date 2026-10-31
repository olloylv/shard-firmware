// render.cc - render every SHARD engine to a WAV file on a desktop computer
//
//   shard_render <out dir>
//
// Writes <engine>.wav (a few hits with different velocities, the alternative
// trigger and a transposed hit), demo_loop.wav (all six channels playing a
// pattern) and prints the host CPU time per engine relative to the LXR Drum.
//
// SPDX-License-Identifier: GPL-3.0-only

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <string>
#include <vector>
#include <chrono>
#include <algorithm>
#include <cstdlib>
#include <cmath>

extern "C" {
#include "Shard/sh_channel.h"
#include "Shard/sh_engine.h"
}

namespace {

const int kRate = 44140;
const int kBlock = SH_BLOCK_SIZE;

uint8_t params[SH_NUM_CHANNELS * SH_CH_STRIDE];

void WriteWav(const std::string& path, const std::vector<int16_t>& data, int channels) {
  FILE* f = fopen(path.c_str(), "wb");
  if (!f) { perror(path.c_str()); return; }
  const uint32_t bytes = data.size() * 2;
  auto u32 = [&](uint32_t v) { fwrite(&v, 4, 1, f); };
  auto u16 = [&](uint16_t v) { fwrite(&v, 2, 1, f); };
  fwrite("RIFF", 1, 4, f); u32(36 + bytes); fwrite("WAVEfmt ", 1, 8, f);
  u32(16); u16(1); u16(channels); u32(kRate); u32(kRate * 2 * channels); u16(2 * channels); u16(16);
  fwrite("data", 1, 4, f); u32(bytes);
  fwrite(data.data(), 2, data.size(), f);
  fclose(f);
}

uint8_t* Block(int ch) { return &params[ch * SH_CH_STRIDE]; }

std::string SafeName(const char* s) {
  std::string r;
  for (const char* p = s; *p; ++p) {
    char c = *p;
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) r += c;
    else if (c == '-' || c == ' ' || c == '.') r += '_';
  }
  return r;
}

struct Hit { double t; int ch; int vel; int alt; int transpose; };

// renders a list of hits on all channels; returns interleaved stereo
std::vector<int16_t> Render(const std::vector<Hit>& hits, double seconds, double* cpu_seconds) {
  const int blocks = static_cast<int>(seconds * kRate / kBlock);
  std::vector<int16_t> out;
  out.reserve(blocks * kBlock * 2);
  size_t next = 0;
  uint8_t base_tune[SH_NUM_CHANNELS];
  for (int ch = 0; ch < SH_NUM_CHANNELS; ++ch) base_tune[ch] = Block(ch)[SHP_TUNE];
  double cpu = 0.0;
  for (int b = 0; b < blocks; ++b) {
    const double t = static_cast<double>(b) * kBlock / kRate;
    while (next < hits.size() && hits[next].t <= t) {
      const Hit& h = hits[next++];
      Block(h.ch)[SHP_TUNE] = static_cast<uint8_t>(base_tune[h.ch] + h.transpose);
      sh_trigger(h.ch, h.vel, h.alt);
    }
    float mix_l[kBlock] = { 0 }, mix_r[kBlock] = { 0 };
    auto start = std::chrono::steady_clock::now();
    sh_beginBlock();
    for (int ch = 0; ch < SH_NUM_CHANNELS; ++ch) {
      int16_t buf[kBlock];
      sh_channelRender(ch, buf);
      float l, r;
      sh_channelPan(ch, &l, &r);
      for (int i = 0; i < kBlock; ++i) { mix_l[i] += buf[i] * l; mix_r[i] += buf[i] * r; }
    }
    cpu += std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    for (int i = 0; i < kBlock; ++i) {
      auto clip = [](float x) { return static_cast<int16_t>(x > 32767 ? 32767 : (x < -32768 ? -32768 : x)); };
      out.push_back(clip(mix_l[i]));
      out.push_back(clip(mix_r[i]));
    }
  }
  if (cpu_seconds) *cpu_seconds = cpu;
  return out;
}

void SilenceAll() {
  for (int ch = 0; ch < SH_NUM_CHANNELS; ++ch) {
    sh_channelDefaults(Block(ch), 0);
    Block(ch)[SHP_VOL] = 0;
  }
}

}  // namespace

// raw engine output level, before the strip
void AnalyseEngines() {
  for (int e = 0; e < sh_engineCount(); ++e) {
    uint8_t b[SH_CH_STRIDE];
    sh_channelDefaults(b, static_cast<uint8_t>(e));
    const ShEngineInfo* info = sh_engineInfo(static_cast<uint8_t>(e));
    sh_engineSelect(0, static_cast<uint8_t>(e));
    ShRenderIn in;
    memset(&in, 0, sizeof(in));
    in.note = b[SHP_TUNE];
    for (int i = 0; i < SH_NUM_ENGINE_PARAMS; ++i) {
      const ShParamDesc& d = info->params[i];
      const int cnt = d.type == SH_PT_ONOFF ? 2 : d.count;
      if (d.type == SH_PT_LIST || d.type == SH_PT_ONOFF) {
        in.idx[i] = b[SHP_E0 + i];
        in.p[i] = cnt > 1 ? b[SHP_E0 + i] / float(cnt - 1) : 0;
      } else {
        in.p[i] = b[SHP_E0 + i] / 127.0f;
      }
    }
    in.accent = 1.0f;
    float peak = 0, sum = 0; int count = 0;
    for (int blk = 0; blk < kRate / kBlock; ++blk) {
      in.trigger = blk == 0;
      float out[kBlock];
      sh_engineRender(0, &in, out);
      for (int i = 0; i < kBlock; ++i) {
        peak = std::max(peak, std::fabs(out[i]));
        if (blk < kRate / kBlock / 4) { sum += out[i] * out[i]; ++count; }
      }
    }
    printf("raw %-4s peak %6.2f  rms(250ms) %6.3f\n", info->shortName, peak, std::sqrt(sum / count));
  }
}

int main(int argc, char** argv) {
  const std::string dir = argc > 1 ? argv[1] : ".";
  if (dir == "--levels") { AnalyseEngines(); return 0; }
  if (dir == "--bench" && argc > 3) {
    // render one channel for N seconds, a hit every 125 ms (for instruction counting)
    const int e = atoi(argv[2]);
    const double seconds = atof(argv[3]);
    SilenceAll();
    sh_channelDefaults(Block(0), static_cast<uint8_t>(e));
    sh_channelsInit(params);
    const int blocks = static_cast<int>(seconds * kRate / kBlock);
    int16_t buf[kBlock];
    long acc = 0;
    for (int b = 0; b < blocks; ++b) {
      if (b % 86 == 0) sh_trigger(0, 100, 0);
      sh_beginBlock();
      sh_channelRender(0, buf);
      acc += buf[0];
    }
    printf("%ld\n", acc);
    return 0;
  }
  SilenceAll();
  sh_channelsInit(params);

  // --- one file per engine ---
  const int n = sh_engineCount();
  std::vector<double> cpu(n);
  for (int e = 0; e < n; ++e) {
    SilenceAll();
    sh_channelDefaults(Block(0), static_cast<uint8_t>(e));
    sh_channelsInit(params);
    std::vector<Hit> hits = {
      { 0.00, 0, 127, 0, 0 }, { 0.60, 0, 70, 0, 0 }, { 1.20, 0, 127, 1, 0 },
      { 2.00, 0, 127, 0, 7 }, { 2.25, 0, 100, 0, -5 }, { 2.50, 0, 127, 0, 0 },
    };
    const ShEngineInfo* info = sh_engineInfo(static_cast<uint8_t>(e));
    auto audio = Render(hits, 3.5, &cpu[e]);
    char num[8]; snprintf(num, sizeof(num), "%02d_", e);
    WriteWav(dir + "/" + num +
             SafeName(info->longName) + ".wav", audio, 2);

    // sanity: peak level and silence
    int peak = 0;
    for (int16_t s : audio) peak = std::max(peak, std::abs(static_cast<int>(s)));
    printf("%-3d %-4s %-9s peak %5.1f%%  host cpu %.3f ms/s\n", e, info->shortName,
           info->longName, peak * 100.0 / 32767, cpu[e] / 3.5 * 1000.0);
  }

  // --- demo loop: an IDM style pattern on six channels ---
  {
    const char* eng[SH_NUM_CHANNELS] = { "tBD", "EFM", "Zap", "Crs", "pHH", "Cmb" };
    for (int ch = 0; ch < SH_NUM_CHANNELS; ++ch) {
      uint8_t type = 0;
      for (int e = 0; e < n; ++e) if (!strcmp(sh_engineInfo(e)->shortName, eng[ch])) type = e;
      sh_channelDefaults(Block(ch), type);
    }
    Block(1)[SHP_TUNE] = 58; Block(1)[SHP_E0 + 0] = 10; Block(1)[SHP_E0 + 7] = 70;  // EFM snare-ish
    Block(1)[SHP_REPEAT] = 2;
    Block(2)[SHP_PAN] = 30; Block(3)[SHP_PAN] = 100; Block(5)[SHP_PAN] = 90;
    Block(3)[SHP_BITS] = 40;
    Block(5)[SHP_TUNE] = 67;
    sh_channelsInit(params);
    const double step = 60.0 / 140.0 / 4.0;
    const char* pat[SH_NUM_CHANNELS] = {
      "x...x.....x.x...",
      "....x.......x..x",
      "..x....x.x....x.",
      ".x..x..xx.x...xx",
      "x.xxx.xxx.x.xxxx",
      "...x.....x...x..",
    };
    std::vector<Hit> hits;
    uint32_t rnd = 1;
    for (int bar = 0; bar < 4; ++bar) {
      for (int s = 0; s < 16; ++s) {
        for (int ch = 0; ch < SH_NUM_CHANNELS; ++ch) {
          if (pat[ch][s] != 'x') continue;
          rnd = rnd * 1664525u + 1013904223u;
          const int vel = 70 + (rnd >> 24) % 58;
          const int transpose = (ch == 2 || ch == 5) ? static_cast<int>((rnd >> 16) % 12) - 6 : 0;
          const int alt = (ch == 4 && s % 8 == 6) ? 1 : 0;
          hits.push_back({ (bar * 16 + s) * step, ch, vel, alt, transpose });
          // ratchet on the last bar
          if (bar == 3 && ch == 3 && s >= 12) {
            hits.push_back({ (bar * 16 + s) * step + step / 3, ch, vel - 20, 0, 0 });
            hits.push_back({ (bar * 16 + s) * step + 2 * step / 3, ch, vel - 30, 0, 0 });
          }
        }
      }
    }
    std::sort(hits.begin(), hits.end(), [](const Hit& a, const Hit& b) { return a.t < b.t; });
    double c;
    auto audio = Render(hits, 64 * step + 1.0, &c);
    WriteWav(dir + "/demo_loop.wav", audio, 2);
    printf("demo loop: host cpu %.3f ms per second of audio (6 channels)\n", c / (64 * step + 1.0) * 1000.0);
  }
  return 0;
}
