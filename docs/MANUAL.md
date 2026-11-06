# SHARD manual

*For firmware 0.5 and kit banks 00–04.*

SHARD is an **unofficial** firmware based on the open-source LXR firmware (GPL-3.0). It is not made,
approved or supported by Erica Synths.

The controls and the user interface are the same as in the original firmware. What changes are the
sound engines: any engine can be put on any of the six channels.

## Channels

- 6 identical channels. Triggers T1–T6 fire channels 1–6.
- Trigger T7 (the former open hi-hat input) is an alternative trigger for channel 6:
  - hi-hat engines (pHH, tHH) play open;
  - every other engine uses **AEG → DcA** (decay alt) instead of Decay.
- Buttons 1–6 select a channel; button 7 also opens channel 6.

Channel sub-pages:

| Button | Parameters |
|---|---|
| OSC | **Eng** (engine), Tun (note), Fin (±64 cents), engine parameters 1–5 |
| MOD / FM / SMP | engine parameters 6–29. Names come from the engine; empty slots can't be selected |
| AEG | Atk, Dec, Slp, Rep (clap retrigger for any engine), DcA, Vel (velocity → level), Mod (AD / off) |
| FLT | Frq, Res, Typ (off/LP/HP/BP/UBP/Nch/Pk/LP2), Drv, then the ring modulator: Rng, RFq, RSr |
| MIX | Vol, Pan, SR (sample rate), Drv, Out, **Bit** (bit crusher) |
| LFO | Frq, Ofs, Wav, Rtg (retrigger from channel 1–6) |

Channel signal chain: **engine → ring mod → filter → AEG → velocity → drive → volume → SR → Bit → pan and
output**. Engines with their own envelope (all Plaits drums, tBD/tSD/tCP/tHH, EFM, Zap, Crs) default to
AEG `Mod = off`, so the engine's internal envelope shapes the sound.

Filter drive also sets the filter's input gain: 0 is about −8 dB, 40 is unity.

Changing the engine from the panel loads that engine's defaults. Loading a kit keeps the stored
parameters as they are.

### Ring modulator (channel)

New in 0.5. Every channel has a ring modulator right after the engine (FLT page, slots 5–7):

| Knob | Parameter |
|---|---|
| `Rng` | amount: 0 = off, 127 = pure ring modulation; in between the dry signal is mixed in |
| `RFq` | frequency of the internal carrier, 20 Hz – 5.1 kHz (exponential) |
| `RSr` | carrier: `sin`, `tri`, `sqr` (internal), or `c1`–`c6`, the output of another channel |

The internal carrier restarts on every hit, so each hit sounds the same. With `c1`–`c6` the channel is
multiplied by the other channel's final output (after its AEG and volume): it only sounds while the
other channel sounds, and its envelope shapes this one. A channel rendered after this one is heard one
audio block late (1.45 ms); choosing the channel itself multiplies it by its own previous block.

Kits from older versions have 0 in these slots, so the ring modulator is off. `Rng` and `RFq` can be
morphed and are CV matrix destinations (at the end of the list, see below); a CV on `Rng` can open the
ring even when the knob is at 0.

### Accent inputs

The accent inputs are read as gates: if an accent input is high when its channel is triggered, the hit
has full velocity, otherwise half. Accents are also modulation sources (see below).

### MOD mode (CV matrix)

Each channel has **6 slots** (36 in total): source, amount, destination. Sources: CV1–5, LFO1–6,
accents 1–6. In MOD mode the encoder steps through the channel's pages: slots 1–2, 3–4, 5–6, then the
channel's LFO. In a new kit slots 1–5 already listen to CV1–CV5 and slot 6 to the channel's own LFO;
you only pick a destination and an amount.

Kits from older versions load unchanged: their three slots become slots 1–3, slots 4–6 are empty.

The destination list starts with the global targets:

| LCD | Modulates |
|---|---|
| `Mrp` | morph amount |
| `Mtg` | morph target kit (±127 kits) |
| `Msh` | morph sharpness |
| `Fwt` | FX dry/wet |
| `Fx1`–`Fx4` | parameters P1–P4 of the current effect |

Then come the channel parameters: `VO` (1 V/oct pitch), the engine parameters and the common strip (Atk,
Dec, Slp, filter Frq/Res/Drv, Vol, Pan, SR, Drv, Bit, LFO rate). The ring modulator targets added in 0.5
(`Rng` amount and `RFq` frequency, LCD `1rn` / `1rf`) come last, after channel 6's parameters, for all
six channels: that way the numbers of the older destinations, and the kits that use them, stay the
same. On the LCD a destination looks like
`3sw`: channel number and short name. While editing, the full name is shown, e.g. `C3 tBD  SweepDec`.

Empty engine slots are skipped while scrolling. If a destination points at a slot the current engine
doesn't have, the LCD shows `3--` / `(unused)`.

At 100 % amount `VO` uses the LXR calibration and semitone quantisation.

### Morph (PERF)

Four knobs on the PERF page:

| Knob | Function |
|---|---|
| `Mrp` | morph amount 0–255 |
| `Mtg` | target kit |
| `Alg` | morph algorithm |
| `Shp` | sharpness 0–127 |

Algorithms:

- `lin` — linear. Shp > 0 pushes the parameters **past** the target (up to 2× the difference): at the end
  of the travel the morph exaggerates whatever makes the target kit different.
- `snp` — S-curve around the middle. Higher Shp makes the transition narrower; at 127 the kit flips
  almost at once. Default: `snp`, Shp 48.
- `sct` — scatter: every parameter has its own switch point between 12 and 88 % of the travel. With high
  Shp parameters jump one after another, giving a stepped, broken-up morph.
- `stp` — the morph travel is quantised: Shp 0 = 16 steps, Shp 127 = 2 steps (an A/B switch).

List parameters (types, waveforms, engine) switch where their curve passes the middle. The channel output
(Out) is not morphed. The morph also acts on the FX: P1–P4 and dry/wet smoothly, the effect type and
other switches along the same curve.

Mrp, Mtg and Shp can be modulated from the CV matrix (see above). "Save morph" stores the kit using the
same curve.

## Engines

| # | Eng | Family | Parameters |
|---|---|---|---|
| 0 | Drm | LXR | original LXR Drum: Wav, PWM / PDc, PSl, PAm / FMA, FMF, FMW, Mod / TrW, TrV, TrF |
| 1 | Snr | LXR | LXR Snare (noise filter inside the engine: NFF/NFR/NFT) |
| 2 | Cym | LXR | LXR Cymbal (3-op FM) |
| 3 | Hat | LXR | LXR HiHat (open = T7 + DcA) |
| 4 | aBD | Plaits | analogue kick: Ton, Dec, AFM, SFM, Drv |
| 5 | sBD | Plaits | synthetic kick: Ton, Dec, Drt, FMA, FMD |
| 6 | aSD | Plaits | analogue snare: Ton, Dec, Snp |
| 7 | sSD | Plaits | synthetic snare: FMA, Dec, Snp |
| 8 | pHH | Plaits | hi-hat: Ton, Dec, Noi, Typ (808/Rng), Opn (decay for T7) |
| 9 | Mdl | Plaits | modal resonator: Str, Bri, Dmp, Exc |
| 10 | Str | Plaits | Karplus-Strong string: Str, Bri, Dmp, Exc |
| 11 | Prt | Plaits | particles: Den, Res, Spr |
| 12 | tBD | MD-style | Swp, SwD, Dec, Hld, Clk, Drv |
| 13 | tSD | MD-style | Bdy, Snp, Dec, NDc, Swp, NTn |
| 14 | tCP | MD-style | clap: Dec, Spc, Num, Q, Rnd |
| 15 | tHH | MD-style | Ton, Dec, Mtl, Opn, Res |
| 16 | EFM | MD-style | 2-op FM: Rat, Mod, MDc, FB, Swp, SwD, Dec, Noi |
| 17 | GND | MD-style | Wav (Sin/Tri/Saw/Sqr/Noi/Imp/S&H), Swp, SwD |
| 18 | Zap | IDM | Dep, Tim, FB, Dec, Dir |
| 19 | Crs | IDM | Src, Rat, Bit, Jit, Dec, Glt |
| 20 | Byt | IDM | bytebeat: Frm, A, B, Rst |
| 21 | Rng | IDM | ring-modulated cluster: Spr, RM, Ton, Res, Wav |
| 22 | Cmb | IDM | comb: Exc, FB (±), Dmp, Bur, Rat, Mx2 |

For Mdl and Str, `Dmp` sets the decay length: higher is longer.

The engine number is stored in the kit, so new engines are only ever added at the end of the list
(`Core/Src/Shard/engines/engines.h`).

The Plaits code is taken from the Mutable Instruments repository (MIT) almost unchanged; only the sample
rate was adjusted. The MD-style engines are original code written from the published descriptions of the
Elektron Machinedrum machines; no Elektron code was used, and SHARD is not affiliated with Elektron.

## FX bus

FX types: `off`, `drv` (distortion), `glt` (glitch), `cmp` (compressor), `del` (delay), `rng` (ring
modulator, new in 0.5). The type numbers of older kits are unchanged: `glt` stays where the ring
modulator was in the LXR firmware, `rng` is appended at the end.

### Glitch (`glt`)

A beat repeat triggered by the hits of channels routed to the FX bus (Out = FX). With probability Chance
a hit starts an event: the next slice of length Len is recorded and played through, then the slice
replaces the input and repeats Rep times using one of these actions: repeat, reverse, octave down,
octave up, ratchet (every repeat half as long), tape stop, random pitch steps. Variety 0 allows only
repeat; every step up adds the next action.

| Knob | Parameter |
|---|---|
| `len` (P1) | slice length 15–300 ms |
| `chc` (P2) | chance per hit |
| `var` (P3) | set of actions |
| `rep` (P4) | number of repeats 1–8 |

The glitch shares the delay buffer (only one effect runs at a time).

### Ring modulator (`rng`)

| Knob | Parameter |
|---|---|
| `wav` | carrier: Sin, Tri, Saw, Rec (square), Noi (noise, a new random value every period), PWM (25 % pulse) |
| `frq` (P1) | carrier frequency 20 Hz – 5.1 kHz |
| `am` (P2) | 0 = ring modulation, 127 = amplitude modulation (the dry signal comes through) |
| `spr` (P3) | the right carrier is detuned up to +1 semitone: stereo beating |
| `rnd` (P4) | on every hit of an FX bus channel the carrier jumps by up to ±2 octaves around `frq` |

The carrier restarts on every hit of an FX bus channel. P1–P4 and dry/wet can be modulated from the CV
matrix (`Fx1`–`Fx4`, `Fwt`) and follow the morph.

## Kit banks

New in 0.5. The card holds up to 100 banks of 128 kits, `/shard/prj00` … `/shard/prj99`. One bank is in
RAM at a time. The LOAD/SAVE button steps through:

**Load Kit → Save Kit → Save Morph → Load Bank → Save Bank** (and back to Load Kit).

- **Load Bank** shows `Bank` and the bank number with its name (from `prj.nfo`, `Empty` if there is
  none). Loading reads all 128 kits from the card (progress on the LCD) and then activates the kit
  slot that was playing.
- **Save Bank** writes all 128 kits in RAM and the name to the selected bank, which becomes the current
  one. Use it to copy a bank or to save your edits of several kits at once.
- The current bank is stored in `/shard/bank.idx` and comes back at power-on. Global settings always
  stay in `/shard/prj00/glo.cfg`.
- Kit load/save works inside the current bank as before.

Banks shipped with 0.5:

| Bank | Name | Contents | Channel roles (1–6, T7) |
|---|---|---|---|
| 00 | `SHARD05` | factory bank 0.5 (MD / PL / ID / HY groups) | kick, perc/tom, FX, snare, clap, closed hat, open hat |
| 01 | `TECHNO` | techno with rumble, atmosphere and pumping kicks | kick, rumble, atmosphere, rim/snare, clap, closed hat, open hat |
| 02 | `ELECTRO` | hard Detroit electro, 808-style kicks | kick, perc (cowbells, toms, blips), FX (zaps, lasers), snare, clap, closed hat, open hat |
| 03 | `PSY` | dark / forest psytrance, rolling bass | kick, rolling bass, psychedelic FX, rim, clap, closed hat, dark open hat |
| 04 | `INDSTRL` | hard industrial | overdriven kick, rumble, metal/noise, snare, clap, closed hat, open hat |

The text lists `BANK_00` … `BANK_04` in the release describe every kit (engines, FX, key, tempo and
character). In banks 01–04 "pump" means the rumble/bass/atmosphere ducks on every kick (its LFO is
retriggered by channel 1).

### Bank 00 (factory bank)

The factory bank 0.5 has 128 kits, grouped by the engine family that dominates the kit (at least 4 of
6 channels):

| Slots | Group | Engines |
|---|---|---|
| 0–31 | `MD…` | tBD tSD tCP tHH EFM GND |
| 32–63 | `PL…` | aBD sBD aSD sSD pHH Mdl Str Prt |
| 64–111 | `ID…` | Zap Crs Byt Rng Cmb — the wildest part |
| 112–127 | `HY…` | hybrids, a free mix of MD/PL/ID |

The original LXR voices (Drm, Snr, Cym, Hat) are still available as engines but are not used in the
factory bank.

Channel roles are the same in every kit: 1 kick, 2 percussion/tom, 3 FX (metal, zaps, glitch),
4 snare, 5 clap, 6 closed hat, T7 = open hat on channel 6.

### Installing the banks

1. Unzip `shard_banks_v0.5.zip`.
2. Copy the `shard` folder to the root of the SD card. If the card already has a `shard` folder, the
   kits in `shard/prj00` … `shard/prj04` are replaced; back up your own banks first (or move them to
   other numbers, `prj05` and up).
3. Load a bank with **Load Bank**, then kits as usual (LOAD).

### How the banks are built

`tools/kits/make_kits.py` generates bank 00; `make_techno.py` (01), `make_electro.py` (02),
`make_psy.py` (03) and `make_industrial.py` (04) build on it and on `bank_common.py`. `bank_txt.py`
writes the kit lists. For bank 00:

1. **Voice pools.** Every group and role has a set of archetypes with parameters in seconds, semitones
   and hertz, converted to engine values. Each archetype is rendered many times with random variations
   within its ranges, and every variant is measured as a single hit (`tools/kits/analyse.py`): length,
   high-frequency tail, whistling, band energies, centroid, attack, loudness (K-weighted, loudest
   100 ms), crest factor and pitch. The role score keeps only what sits in its place in the mix: kicks
   need sub and low end with a fast attack, hats live above 5 kHz without low mids, snares need body
   plus noise without air on top, and so on. Voices that are too quiet or too spiky are dropped.
2. **Kit.** Voices come from the group's pool (up to two guests from other groups). The kit gets a theme
   (tempo, groove, FX, movement) and a key: pitched voices are retuned to scale degrees (kick to the
   tonic, tom to tonic or fifth, FX to scale degrees). Mixing: single-hit loudness of each role relative
   to the kick, high-pass on everything but the kick, channel drive as a soft clipper for spiky noise
   voices, stereo image (kick and snare in the centre, percussion and FX to the sides).
3. **Detail.** S&H LFO on the FX channel's timbre (every hit slightly different), FX pan movement,
   accents open the hats' high-pass, accent on snare drive, light S&H on percussion timbre; in the
   fracture/micro themes and the ID group also crush, ratchets and random pitch steps. Slow LFOs on the FX
   bus parameters. The delay is matched to the kit's tempo.
4. **Check and master.** Every kit is checked again with single hits (with all modulation), anything
   ringing or whistling is shortened. In the groove no channel is louder than its target relative to the
   kick. The kit level is set by the loudness of the kick hit (all kits are balanced against it); groove
   peaks stay at or below −0.6 dBFS without clipping.

```sh
cmake -S tools/host -B build/host && cmake --build build/host
python3 tools/kits/make_kits.py build/host/shard_render out/   # out/shard/prj00/*.snd -> SD card root
```

The other generators take the same two arguments and write `out/shard/prj01` … `prj04`.

## SD card

SHARD keeps its kits, banks and global settings in a separate `/shard` folder, apart from the LXR
kits: banks in `/shard/prj00` … `/shard/prj99`, the current bank number in `/shard/bank.idx`, global
settings in `/shard/prj00/glo.cfg`. An empty slot gets a SHARD init kit.

The kit format version is stored in parameter 0 (`SH_KIT_VERSION`).

## Firmware update

**From the menu (SHARD 0.1 and later):**

1. Copy `LXRE_SHARD_V<version>.img` to the root of the SD card.
2. Open the global menu (SHIFT + SAVE/LOAD), page 1, item **Upd**, press the encoder.
3. Select the file with the encoder, press, then press again to confirm.

The firmware checks the header and checksum and writes the image to the upper half of the flash (sectors
6–7). It verifies what was written and only then, running from ITCM, copies it over the application area
(sectors 1–5) and restarts the module. The bootloader in sector 0 is never touched. If anything is wrong
before the copy starts, the firmware shows an error and keeps running.

**Fallback:** as in the original firmware. Hold the encoder at power-on until "LXR Updater" appears; the
bootloader flashes the `LXRE*.img` file itself. This also works if power was lost during a menu update.

Limit: the firmware image can be up to 480 KB. The 0.5 image is about 300 KB.

## Screensaver

Global menu, item `ssv`: off / 2m / 5m / 30s / 10s (time without touching any control; default 2m). It
shows six vertical level meters for the channels across both LCD lines; the group slowly drifts sideways
to avoid burn-in. Any button, the encoder, or turning a knob by 2+ steps brings the menu back; a single
step (jitter of an endless pot) doesn't reset the timer.

## Output stage

New in 0.5. The channels and the FX return are summed in floating point (no 16-bit clipping inside the
mix), then a soft limiter (transparent up to about −1 dBFS, a tanh shoulder above) and the two DACs run
with 24-bit samples instead of 16. The sample rate stays 44.1 kHz: the engines and the CPU budget are
built around it. Loud kits that used to clip hard now saturate softly; quiet passages have a lower
noise floor.

## CPU load

Global menu → **CPU**: peak load of the audio block in percent (updated when the display is redrawn).

By instruction count, a typical engine plus the channel strip costs about as much as the original LXR
Drum. Mdl and Prt are about 3× heavier.

## Building

```sh
cmake --preset release && cmake --build --preset release      # build/release/LXRE_SHARD_V<version>.img
cmake -S tools/host -B build/host && cmake --build build/host  # desktop engine renderer
build/host/shard_render out/                                    # a WAV per engine + demo_loop.wav
```

The firmware needs the Arm GNU Toolchain with C++ (`arm-none-eabi-g++`); Arm's official toolchain has it.

## Code layout

| Path | Contents |
|---|---|
| `Core/Inc/Shard/sh_params.h` | channel parameter layout |
| `Core/Src/Shard/sh_channel.c` | channel strip (ring mod, filter, AEG, drive, SR, Bit, LFO, modulation, morph) |
| `Core/Src/Shard/sh_bridge.c` | glue to the menu, kits, CV matrix, CPU meter |
| `Core/Src/Shard/sh_ui.c` | parameter names and values for the LCD |
| `Core/Src/Shard/sh_morph.c` | morph curves (lin/snp/sct/stp) |
| `Core/Src/Shard/sh_update.c` | update from the menu |
| `Core/Src/Shard/engines/` | engines (C++) and the registry |
| `Core/Src/Shard/sh_bank.c` | kit banks |
| `Core/Src/Soundengine/DSPAudio/mixer.c` | float mix bus, soft limiter, 24-bit output |
| `Core/Src/Soundengine/DSPAudio/FX/Glitch.c` | glitch effect |
| `Core/Src/Soundengine/DSPAudio/FX/Ringmod.c` | ring modulator effect |
| `Core/ThirdParty/` | subset of Plaits and stmlib (MIT) |
| `tools/host/` | desktop build of the engines and WAV renderer |
| `tools/kits/` | factory bank generator and single-hit analysis |

To add an engine:

1. A class derived from `shard::Engine` with `Init()` and `Render()`.
2. A parameter description `ShEngineInfo kInfo<Name>`.
3. `SH_DEFINE_ENGINE_FACTORY(<Name>)`.
4. Append the name to the end of `SH_ENGINE_LIST`.
