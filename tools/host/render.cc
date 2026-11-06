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
#include "Shard/sh_bridge.h"
#include "Parameters.h"
#include "Soundengine/FxBus.h"
#include "Soundengine/DSPAudio/mixer.h"

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

// ---------------------------------------------------------------------------
// kit files: --dump (engine/param tables as JSON) and --kit (render a kit)
// ---------------------------------------------------------------------------
void DumpJson(const char* path) {
  FILE* f = fopen(path, "w");
  auto str = [&](const char* t, int n) {
    fputc('"', f);
    for (int i = 0; i < n && t[i]; ++i) fputc(t[i] == '"' ? '\'' : t[i], f);
    fputc('"', f);
  };
  fprintf(f, "{\"par_ch_base\": %d, \"stride\": %d, \"end_of_sound\": %d, \"num_params\": %d,\n",
          PAR_CH_BASE, SH_CH_STRIDE, END_OF_SOUND_PARAMETERS, NUM_PARAMS);
  fprintf(f, " \"par\": {\"FX_TYPE\": %d, \"FX_ROUTING\": %d, \"FX_DRY_WET\": %d, \"FX_DIST_TYPE\": %d, "
             "\"FX_P1\": %d, \"FX_RATIO\": %d, \"FX_WAVE\": %d, \"FX_DELAY_TYPE\": %d, \"MORPH_KIT_DEST\": %d, "
             "\"CV_DEST_1\": %d, \"CV_MOD_AMT_1\": %d, \"CV_SRC_1\": %d, "
             "\"CV2_DEST_1\": %d, \"CV2_AMT_1\": %d, \"CV2_SRC_1\": %d},\n",
          PAR_FX_TYPE, PAR_FX_ROUTING, PAR_FX_DRY_WET, PAR_FX_DIST_TYPE, PAR_FX_P1, PAR_FX_RATIO, PAR_FX_WAVE,
          PAR_FX_DELAY_TYPE, PAR_MORPH_KIT_DEST, PAR_CV_DEST_1, PAR_CV_MOD_AMT_1, PAR_CV_SRC_1,
          PAR_CV2_DEST_1, PAR_CV2_AMT_1, PAR_CV2_SRC_1);
  fprintf(f, " \"local\": {\"ENGINE\": %d, \"TUNE\": %d, \"FINE\": %d, \"E0\": %d, \"ATTACK\": %d, \"DECAY\": %d, "
             "\"SLOPE\": %d, \"REPEAT\": %d, \"DECAY_ALT\": %d, \"VELVOL\": %d, \"AEG_MODE\": %d, \"FILT_FREQ\": %d, "
             "\"FILT_RESO\": %d, \"FILT_TYPE\": %d, \"FILT_DRIVE\": %d, \"VOL\": %d, \"PAN\": %d, \"SRATE\": %d, "
             "\"DRIVE\": %d, \"OUT\": %d, \"BITS\": %d, \"LFO_FREQ\": %d, \"LFO_OFFSET\": %d, \"LFO_WAVE\": %d, "
             "\"LFO_RETRIG\": %d},\n",
          SHP_ENGINE, SHP_TUNE, SHP_FINE, SHP_E0, SHP_ATTACK, SHP_DECAY, SHP_SLOPE, SHP_REPEAT, SHP_DECAY_ALT,
          SHP_VELVOL, SHP_AEG_MODE, SHP_FILT_FREQ, SHP_FILT_RESO, SHP_FILT_TYPE, SHP_FILT_DRIVE, SHP_VOL, SHP_PAN,
          SHP_SRATE, SHP_DRIVE, SHP_OUT, SHP_BITS, SHP_LFO_FREQ, SHP_LFO_OFFSET, SHP_LFO_WAVE, SHP_LFO_RETRIG);
  fprintf(f, " \"mod_ch_base\": %d, \"mod_globals\": %d,\n", SH_MOD_CH_BASE, SH_MOD_GLOBALS);
  fprintf(f, " \"mod_targets_per_ch\": %d, \"mod_target_local\": [", SH_MOD_TARGETS_PER_CH);
  for (int i = 0; i < SH_MOD_TARGETS_PER_CH; ++i) fprintf(f, "%s%d", i ? ", " : "", sh_modTargetLocal[i]);
  fprintf(f, "],\n \"engines\": [\n");
  for (int e = 0; e < sh_engineCount(); ++e) {
    const ShEngineInfo* info = sh_engineInfo(e);
    uint8_t b[SH_CH_STRIDE];
    sh_channelDefaults(b, e);
    fprintf(f, "  {\"index\": %d, \"short\": ", e); str(info->shortName, 3);
    fprintf(f, ", \"long\": "); str(info->longName, 8);
    fprintf(f, ", \"defaults\": [");
    for (int i = 0; i < SH_CH_STRIDE; ++i) fprintf(f, "%s%d", i ? "," : "", b[i]);
    fprintf(f, "], \"params\": [");
    bool first = true;
    for (int i = 0; i < SH_NUM_ENGINE_PARAMS; ++i) {
      const ShParamDesc& d = info->params[i];
      if (d.type == SH_PT_NONE) continue;
      fprintf(f, "%s{\"slot\": %d, \"short\": ", first ? "" : ", ", i); str(d.shortName, 3);
      fprintf(f, ", \"type\": %d, \"def\": %d, \"count\": %d, \"labels\": [", d.type, d.def, d.count);
      if (d.type == SH_PT_LIST)
        for (int k = 0; k < d.count; ++k) { if (k) fputc(',', f); str(d.labels[k], 3); }
      fprintf(f, "]}");
      first = false;
    }
    fprintf(f, "]}%s\n", e + 1 < sh_engineCount() ? "," : "");
  }
  fprintf(f, " ]\n}\n");
  fclose(f);
}

// sh_bridge.c (CV matrix, morph, FX modulation) works on these
extern "C" {
uint8_t activeParameters[NUM_PARAMS];
uint8_t mainParameters[NUM_KIT_SLOTS][END_OF_SOUND_PARAMETERS];
}
#define kitParams activeParameters

void ApplyFx(uint16_t p, uint8_t value) {
  const float flt = value / 127.f;
  switch (p) {
    case PAR_FX_TYPE: fxBus.fxType = value; FxBus_updateParameter(); break;
    case PAR_FX_ROUTING: fxBus.audioRouting = value; break;
    case PAR_FX_DRY_WET: fxBus.dryWet = value / 100.f; break;
    case PAR_FX_DIST_TYPE: fxBus.distortion.distortionType = value; break;
    case PAR_FX_P1: FxBus_setParameter(0, flt); break;
    case PAR_FX_P2: FxBus_setParameter(1, flt); break;
    case PAR_FX_P3: FxBus_setParameter(2, flt); break;
    case PAR_FX_P4: FxBus_setParameter(3, flt); break;
    case PAR_FX_RATIO: Compressor_setRatio(&fxBus.compressor, value); break;
    case PAR_FX_WAVE: break;
    case PAR_FX_DELAY_TYPE: fxBus.delay.delayType = value; break;
    default: break;
  }
}

// adds a mono block to the float output buses (interleaved stereo) or to the 16 bit
// FX send, according to a routing value; as mixer_addFloat() in the firmware (0.5)
void Route(uint8_t dest, float pl, float pr, const int16_t* d, float* a, float* b, int16_t* fx) {
  auto sat = [](int16_t& o, float v) {
    float x = o + static_cast<float>(static_cast<int16_t>(v));
    o = static_cast<int16_t>(x > 32767 ? 32767 : (x < -32768 ? -32768 : x));
  };
  for (int i = 0; i < kBlock; ++i) {
    switch (dest) {
      case MIXER_ROUTING_DAC1_STEREO: b[2 * i] += d[i] * pl; b[2 * i + 1] += d[i] * pr; break;
      case MIXER_ROUTING_DAC2_STEREO: a[2 * i] += d[i] * pl; a[2 * i + 1] += d[i] * pr; break;
      case MIXER_ROUTING_DAC1_L: b[2 * i] += d[i]; break;
      case MIXER_ROUTING_DAC1_R: b[2 * i + 1] += d[i]; break;
      case MIXER_ROUTING_DAC2_L: a[2 * i] += d[i]; break;
      case MIXER_ROUTING_DAC2_R: a[2 * i + 1] += d[i]; break;
      default: sat(fx[2 * i], d[i] * pl); sat(fx[2 * i + 1], d[i] * pr); break;
    }
  }
}

// the output soft limiter of the firmware (mixer.c, SH_LIMIT_KNEE): input and output
// normalised to full scale = 1
float SoftLimit(float x) {
  const float knee = 0.89f, a = std::fabs(x);
  if (a <= knee) return x;
  const float y = knee + (1.f - knee) * std::tanh((a - knee) / (1.f - knee));
  return x < 0 ? -y : y;
}

// pattern: 6 lines of 16 steps; '.' rest, 'x' hit, 'X' accent, 'o' alt trigger (channel 6),
// 'r' ratchet (3 hits per step)
int RenderKit(const char* kitPath, const char* patPath, double bpm, int bars, const char* outPath,
              const char* metricsPath) {
  FILE* f = fopen(kitPath, "rb");
  if (!f) { perror(kitPath); return 1; }
  char name[9] = { 0 };
  if (fread(name, 1, 8, f) != 8 || fread(kitParams, 1, END_OF_SOUND_PARAMETERS, f) != END_OF_SOUND_PARAMETERS) {
    fprintf(stderr, "short kit file\n"); return 1;
  }
  fclose(f);
  // <patPath> is either 6 lines of step patterns or, if it ends in ".ev", a list of
  // events "<seconds> <channel 0-5> <velocity> <alt>" (e.g. converted from MIDI)
  const std::string pp(patPath);
  const bool events = pp.size() > 3 && pp.compare(pp.size() - 3, 3, ".ev") == 0;
  struct Ev { double t; int ch; int vel; int alt; };
  std::vector<Ev> ev;
  std::vector<std::string> pat;
  FILE* pf = fopen(patPath, "r");
  if (!pf) { perror(patPath); return 1; }
  char line[256];
  while (fgets(line, sizeof(line), pf)) {
    if (events) {
      Ev e;
      if (sscanf(line, "%lf %d %d %d", &e.t, &e.ch, &e.vel, &e.alt) == 4 && e.ch >= 0 && e.ch < SH_NUM_CHANNELS)
        ev.push_back(e);
      continue;
    }
    if (pat.size() >= 6) break;
    std::string l(line);
    while (!l.empty() && (l.back() == '\n' || l.back() == '\r')) l.pop_back();
    if (!l.empty()) pat.push_back(l);
  }
  fclose(pf);
  while (pat.size() < 6) pat.push_back(events ? "" : "................");

  FxBus_init();
  sh_channelsInit(&kitParams[PAR_CH_BASE]);
  for (uint16_t p = PAR_FX_TYPE; p <= PAR_FX_DELAY_TYPE; ++p) ApplyFx(p, kitParams[p]);

  const double step = 60.0 / bpm / 4.0;
  const int steps = events ? 0 : bars * 16;
  double endT = steps * step;
  for (const Ev& e : ev) endT = std::max(endT, e.t);
  const int blocks = static_cast<int>((endT + 1.5) * kRate / kBlock);
  std::vector<int16_t> out;
  double peak[SH_NUM_CHANNELS] = { 0 }, sq[SH_NUM_CHANNELS] = { 0 };
  double mixPeak = 0, outPeak = 0;
  long n = 0, clips = 0;
  for (int s = 0; s < steps; ++s)
    for (int ch = 0; ch < SH_NUM_CHANNELS; ++ch) {
      const std::string& l = pat[ch];
      if (l.empty()) continue;
      const char c = l[s % l.size()];
      const double t = s * step;
      if (c == 'x') ev.push_back({ t, ch, 90, 0 });
      else if (c == 'X') ev.push_back({ t, ch, 127, 0 });
      else if (c == 'o') ev.push_back({ t, ch, 110, 1 });
      else if (c == 'r') for (int k = 0; k < 3; ++k) ev.push_back({ t + k * step / 3, ch, 100 - k * 15, 0 });
    }
  std::sort(ev.begin(), ev.end(), [](const Ev& a, const Ev& b) { return a.t < b.t; });
  size_t next = 0;
  for (int bl = 0; bl < blocks; ++bl) {
    const double t = static_cast<double>(bl) * kBlock / kRate;
    while (next < ev.size() && ev[next].t <= t) {
      sh_trigger(ev[next].ch, ev[next].vel, ev[next].alt);
      ++next;
    }
    float a[2 * kBlock] = { 0 }, b[2 * kBlock] = { 0 };
    int16_t fx[2 * kBlock] = { 0 }, ra[2 * kBlock] = { 0 }, rb[2 * kBlock] = { 0 };
    sh_beginBlock();
    sh_cvProcess();
    for (int ch = 0; ch < SH_NUM_CHANNELS; ++ch) {
      int16_t buf[kBlock];
      sh_channelRender(ch, buf);
      for (int i = 0; i < kBlock; ++i) {
        const double v = buf[i] / 32768.0;
        peak[ch] = std::max(peak[ch], std::fabs(v));
        sq[ch] += v * v;
      }
      float pl, pr;
      sh_channelPan(ch, &pl, &pr);
      Route(sh_channelRouting(ch), pl, pr, buf, a, b, fx);
    }
    FxBus_process(fx, &ra[0], &ra[1], &rb[0], &rb[1], kBlock);
    for (int i = 0; i < 2 * kBlock; ++i) {
      // bus level before the limiter; 'clip' counts the samples that would have
      // clipped on the 16 bit bus (now rounded off by the limiter)
      const float va = a[i] + ra[i], vb = b[i] + rb[i];
      const float pa = std::fabs(va), pb = std::fabs(vb);
      outPeak = std::max(outPeak, std::max(pa, pb) / 32768.0);
      clips += (pa >= 32767) + (pb >= 32767);
      float x = (SoftLimit(va / 32768.f) + SoftLimit(vb / 32768.f)) * 0.8f * 32768.f;
      x = x > 32767 ? 32767 : (x < -32768 ? -32768 : x);
      mixPeak = std::max(mixPeak, std::fabs(x) / 32768.0);
      out.push_back(static_cast<int16_t>(x));
    }
    n += kBlock;
  }
  if (outPath && *outPath) WriteWav(outPath, out, 2);
  if (metricsPath && *metricsPath) {
    FILE* m = fopen(metricsPath, "w");
    // level of the last 0.3 s, well after the last hit: kits must go quiet
    double tail = 0;
    const size_t tn = static_cast<size_t>(0.3 * kRate) * 2;
    for (size_t i = out.size() - tn; i < out.size(); ++i) tail += (out[i] / 32768.0) * (out[i] / 32768.0);
    tail = std::sqrt(tail / tn);
    fprintf(m, "{\"name\": \"%s\", \"tail\": %.5f, \"mix_peak\": %.4f, \"out_peak\": %.4f, \"clip\": %ld, \"peak\": [",
            name, tail, mixPeak, outPeak, clips);
    for (int ch = 0; ch < SH_NUM_CHANNELS; ++ch) fprintf(m, "%s%.4f", ch ? ", " : "", peak[ch]);
    fprintf(m, "], \"rms\": [");
    for (int ch = 0; ch < SH_NUM_CHANNELS; ++ch) fprintf(m, "%s%.5f", ch ? ", " : "", std::sqrt(sq[ch] / n));
    fprintf(m, "]}\n");
    fclose(m);
  }
  return 0;
}

// single hits of every channel of a kit (dry, after the strip), for the bank
// checks: 7 runs (channels 1..6, then channel 6 from the alt trigger) of
// <seconds> each, written as raw float32 to <out>
int RenderHits(const char* kitPath, double seconds, const char* outPath, bool altAll = false) {
  FILE* f = fopen(kitPath, "rb");
  if (!f) { perror(kitPath); return 1; }
  char name[9] = { 0 };
  if (fread(name, 1, 8, f) != 8 || fread(kitParams, 1, END_OF_SOUND_PARAMETERS, f) != END_OF_SOUND_PARAMETERS) {
    fprintf(stderr, "short kit file\n"); return 1;
  }
  fclose(f);
  FILE* o = fopen(outPath, "wb");
  if (!o) { perror(outPath); return 1; }
  const int blocks = static_cast<int>(seconds * kRate / kBlock);
  const int runs = altAll ? 12 : 7;
  for (int run = 0; run < runs; ++run) {
    const int ch = run < 6 ? run : (altAll ? run - 6 : 5);
    sh_channelsInit(&kitParams[PAR_CH_BASE]);
    for (int bl = 0; bl < blocks; ++bl) {
      if (bl == 1) sh_trigger(static_cast<uint8_t>(ch), 110, run >= 6);
      sh_beginBlock();
      sh_cvProcess();
      int16_t buf[kBlock];
      float fb[kBlock];
      for (int c = 0; c < SH_NUM_CHANNELS; ++c) {
        sh_channelRender(static_cast<uint8_t>(c), buf);
        if (c == ch) for (int i = 0; i < kBlock; ++i) fb[i] = buf[i] / 32768.f;
      }
      fwrite(fb, sizeof(float), kBlock, o);
    }
  }
  fclose(o);
  return 0;
}

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
  if (dir == "--dump" && argc > 2) { DumpJson(argv[2]); return 0; }
  if (dir == "--kit" && argc > 7) {
    // --kit <kit.snd> <pattern.txt|events.ev> <bpm> <bars> <out.wav|""> <metrics.json|"">
    return RenderKit(argv[2], argv[3], atof(argv[4]), atoi(argv[5]), argv[6], argv[7]);
  }
  if (dir == "--hits" && argc > 4) return RenderHits(argv[2], atof(argv[3]), argv[4]);
  // all six channels, then all six from the alternative trigger
  if (dir == "--hits12" && argc > 4) return RenderHits(argv[2], atof(argv[3]), argv[4], true);
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
