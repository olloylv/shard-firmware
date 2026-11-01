# SHARD — custom firmware for the Erica Synths LXR Eurorack module

> **Unofficial, modified firmware.** SHARD is based on the open-source LXR firmware. It is not made,
> approved or supported by Erica Synths, and Erica Synths provides no support for modules running it.
> Installing it is at your own risk. The original firmware can be restored at any time (see below).

SHARD keeps the LXR's panel, menus and workflow and replaces the sound engines: **any of 23 engines can
be put on any of the six channels.**

- **23 engines** — the LXR classics (Drum, Snare, Cymbal, HiHat), Mutable Instruments Plaits percussion
  and physical models (analogue/synthetic kick and snare, hat, modal resonator, string, particles),
  Machinedrum-inspired engines (tBD, tSD, tCP, tHH, EFM, GND) and IDM/glitch engines (Zap, Crush,
  bytebeat, ring cluster, comb).
- **A common channel strip** on every channel: multimode filter with drive, AD envelope with clap
  retrigger, drive, sample-rate reduction, bit crusher, pan, LFO.
- **CV matrix with 6 slots per channel** (36 in total). Sources: CV1–5, LFO1–6, accents. Destinations:
  morph amount/target/sharpness, FX dry/wet and P1–P4, 1 V/oct and every channel parameter.
- **Kit morphing with four curves** (linear with overshoot, S-curve, scatter, stepped) and a sharpness
  knob; morph is CV-controllable.
- **Glitch FX**: a trigger-driven beat repeat (stutter, reverse, octave, ratchet, tape stop, random pitch)
  instead of the ring modulator.
- **Firmware update from the menu** — no power cycling, the bootloader stays as a fallback.
- **Screensaver** with live channel level meters, CPU load display.
- **Factory bank 0.5**: 128 kits grouped by engine family (MD-style, Plaits, IDM, hybrids), mixed and
  levelled against the kick, every kit in a key.

Documentation: **[manual (English)](docs/MANUAL.md)** · **[руководство (русский)](docs/MANUAL.ru.md)** ·
[changelog](CHANGELOG.md)

## Downloads

Get the files from the [Releases](../../releases) page:

| File | What it is |
|---|---|
| `LXRE_SHARD_V<version>.img` | firmware update file |
| `shard_bank_v<version>.zip` | factory bank: the `shard` folder for the SD card, `BANK.txt` (list of kits) and audio demos |
| `SHARD_quickref_v<version>.pdf` | one-page quick reference (Russian) |

## Installing

### First installation (from the original firmware)

1. Copy `LXRE_SHARD_V0.4.img` to the root folder of a FAT32 SD card. Delete any other `LXRE*.img` files
   from the card.
2. Unzip `shard_bank_v0.5.zip` and copy its `shard` folder to the root of the same card.
3. With the module powered off, insert the card, hold down the encoder button and power on. Keep holding
   until "LXR Updater" appears.
4. Wait for "Update OK!". The module restarts; the start-up screen shows `SHARD v0.4` / `custom LXR fw`.

SHARD keeps its kits, projects and settings in the `/shard` folder of the card. The original LXR kits
on the card are not touched.

### Updating SHARD

1. Copy the new `LXRE_SHARD_V<version>.img` to the root of the SD card.
2. Global menu (SHIFT + SAVE/LOAD), page 1, **Upd**, press the encoder.
3. Select the file, press, press again to confirm. The module restarts with the new firmware.

The bootloader update (step 3 of the first installation) works for SHARD updates too.

### Going back to the original firmware

Download the official LXR Eurorack firmware from Erica Synths, copy its `LXRE*.img` to the card (and
remove the SHARD image), then hold the encoder at power-on as above. The bootloader is never changed by
SHARD, so this always works. The `/shard` folder can stay on the card.

## Building from source

You need [CMake](https://cmake.org/download/) 3.21+, [Ninja](https://ninja-build.org/), the
[Arm GNU Toolchain](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads)
(`arm-none-eabi-gcc` **and** `arm-none-eabi-g++`, tested with 14.3.rel1) and
[Python 3](https://www.python.org/downloads/), all on `PATH`.

- macOS: `brew install cmake ninja && brew install --cask gcc-arm-embedded`. Don't use
  `brew install arm-none-eabi-gcc`: it lacks the C library and C++.
- Windows: `winget install Kitware.CMake Ninja-build.Ninja Python.Python.3.12` plus Arm's installer
  (tick "Add path to environment variable").
- Linux: `sudo apt install cmake ninja-build python3` plus Arm's toolchain, with its `bin` folder on `PATH`.

```sh
cmake --preset release
cmake --build --preset release
```

The update file is written to `build/release/LXRE_SHARD_V<version>.img`. The SHARD version is set by
`SHARD_VERSION` in [CMakeLists.txt](CMakeLists.txt) and shown on the start-up screen.

| Option | Effect |
|---|---|
| `cmake --preset debug` | Debug build (`-O3 -g3`, `DEBUG` defined) in `build/debug/` |
| `-DARM_TOOLCHAIN_DIR=<bin folder>` | Use a toolchain that isn't on `PATH` |
| `-DLXR_ITCM_OPT=-O2` | Lower optimisation for code in the 16 KB ITCM, if a change or compiler makes it overflow at `-O3` |
| `-DLXR_GENERATE_LISTING=ON` | Also write a disassembly listing (`.list`) |

To start from scratch (e.g. after switching compilers), delete the `build/` folder.

### Desktop renderer and factory bank

The engines, channel strip and FX also build for the desktop, which renders WAV files and generates the
factory bank:

```sh
cmake -S tools/host -B build/host && cmake --build build/host
build/host/shard_render out/                                  # a WAV per engine + demo loop
python3 tools/kits/make_kits.py build/host/shard_render out/  # factory bank -> out/shard/prj00/
```

`make_kits.py` needs `numpy` and `scipy`.

### Programming with a debug probe

Not needed for updates. With an ST-Link and [OpenOCD](https://openocd.org/) on `PATH`:

```sh
cmake --build --preset release --target flash        # firmware only, bootloader untouched
```

For blank devices, configure with the Eurorack bootloader, either from source
(`-DLXR_BOOTLOADER_DIR=path/to/LXR_V2_STM32F765_Bootloader`, built with `LXR_BOOTLOADER_EURORACK`) or
prebuilt (`-DLXR_BOOTLOADER_HEX=path/to/LXR_V2_Eurorack_Bootloader.hex`). The build then also writes
`LXRE_SHARD_V<version>_full.hex/.bin` (whole flash from 0x08000000) and enables the `flash_full` target.

> **Warning:** `flash_full` overwrites the bootloader and asks you to type `yes` first (or set
> `LXR_CONFIRM_BOOTLOADER_OVERWRITE=yes`). If it is interrupted, the module can only be recovered with a
> debug probe.

## Memory map

| Region | Address | Size | Contents |
|---|---|---|---|
| FLASH | 0x08000000 | 32 KB | Bootloader (sector 0) |
| FLASH | 0x08008000 | 992 KB | This firmware; sectors 6–7 are also used to stage menu updates |
| ITCM | 0x00000000 | 16 KB | `IN_ITCM_RAM` DSP code, flash copy routine |
| DTCM | 0x20000000 | 128 KB | `INDTCM`/`INDTCMZ` data, DMA buffers, stack |
| RAM | 0x20020000 | 384 KB | `.data`, `.bss`, heap, engine storage |

## Source layout

| Path | Contents |
|---|---|
| `Core/Src/Shard/`, `Core/Inc/Shard/` | SHARD: channel strip, menu glue, morph, CV matrix, update from menu |
| `Core/Src/Shard/engines/` | sound engines (C++) and the engine registry |
| `Core/ThirdParty/` | subset of Mutable Instruments Plaits and stmlib (MIT) |
| `Core/Src/`, `Core/Inc/` | original LXR firmware: UI, presets, FX bus, MIDI, I/O |
| `tools/host/` | desktop build and WAV renderer |
| `tools/kits/` | factory bank generator and analysis |
| `docs/` | manuals |

Originally an STM32CubeIDE project; the CubeMX `.ioc` was removed because regenerating code from it
overwrites application code. Pins, clocks and peripherals live in `Core/Inc/main.h`, `Core/Src/main.c`
and `Core/Src/stm32f7xx_hal_msp.c`. Source files are listed explicitly in the `CMakeLists.txt` files;
add new files there.

## Licence and trademarks

SHARD is free software under the [GNU GPL version 3](LICENSE) (GPL-3.0-only) with the additional
permission and terms in [NOTICE.md](NOTICE.md), like the LXR firmware it is based on
(Copyright (C) 2012-2026 Erica Synths).

"Erica Synths", "LXR" and "LXR-02" are trademarks of Erica Synths and are used here only to state
compatibility. The LXR hardware is not covered by any licence in this repository. "Machinedrum" and
"Elektron" are trademarks of Elektron Music Machines; SHARD is not affiliated with Elektron, and its
MD-style engines contain no Elektron code. Plaits and stmlib are by Emilie Gillet (Mutable Instruments),
MIT licence. Other third-party components keep their own licences, see
[NOTICE.md](NOTICE.md#third-party-components).
