# Changelog

## Factory bank 0.5 — 2026-11-01

- All 128 kits rebuilt. Voices are picked from scored pools: every candidate is rendered and measured as
  a single hit (length, high-frequency tail, whistling, bands, centroid, attack, loudness, crest factor,
  pitch) and has to fit its role in the mix.
- Every kit has a theme (tempo, groove, FX, movement) and a key; pitched voices are tuned to the scale.
- Loudness of every role is balanced against the kick; drive is used as make-up gain and soft clipper;
  the groove is checked so no channel sticks out; kits are levelled by the kick, peaks ≤ −0.6 dBFS,
  no clipping.
- Takes the filter's input gain into account (filter drive 40 = unity).
- Groups: `MD` 0–31, `PL` 32–63, `ID` 64–111, `HY` 112–127.

## 0.4 — 2026-11-01

- CV matrix: 6 slots per channel (36 in total). MOD pages for slots 1–2, 3–4, 5–6 and the LFO. Older
  kits load unchanged (their slots become 1–3).
- Fixed reading past the MOD page table when scrolling in MOD mode.
- New FX type `glt` (glitch / beat repeat) replaces the ring modulator: length, chance, variety, repeats.
- Screensaver: timeouts off/2m/5m/30s/10s; a single pot step (jitter) no longer resets it; `idl`
  diagnostics on the global page; the global page refreshes live.
- Bank 0.4: fixed channel roles (1 kick, 2 perc/tom, 3 FX, 4 snare, 5 clap, 6 closed hat, T7 open hat),
  no LXR-engine kits, 48 IDM kits.

## 0.3

- CV matrix: global destinations first (morph amount/target/sharpness, FX dry/wet, FX P1–P4), then
  27 destinations per channel; unused engine slots are skipped while scrolling. Kit format 2; older kits
  are converted on load.
- Morph algorithms `lin`/`snp`/`sct`/`stp` with a sharpness knob on the PERF page; morph follows CV every
  audio block and also applies to the FX bus and "save morph".
- Screensaver with six channel level meters.
- Factory bank grouped by dominant engine family.

## 0.2

- LXR Cymbal/HiHat: FM restored as in the original voices.
- String engine +6 dB, AEG decay defaults matched to measured times, decay alt default 45.
- Tube distortion FX: DC offset removed.
- Desktop renderer: FX bus, kit files, engine table dump.
- First factory bank generator (128 kits).

## 0.1

- Six identical channels with freely assignable engines and a common strip (filter, AEG, drive, sample
  rate, bit crusher, LFO).
- 23 engines: LXR classics, Plaits percussion, Machinedrum-inspired, IDM/glitch.
- CV matrix can target any parameter of any channel and 1 V/oct.
- Morph inside the channel strips.
- Kits and projects in `/shard` on the SD card.
- Firmware update from the global menu; the LXR bootloader stays as fallback.
- CPU load display; the start-up screen marks the firmware as modified.
- Desktop render harness (`tools/host`).
