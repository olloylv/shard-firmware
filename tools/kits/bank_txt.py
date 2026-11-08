#!/usr/bin/env python3
"""Write BANK.txt (the kit list shipped with a kit bank) from bank.json.

    python3 tools/kits/bank_txt.py <out dir> [firmware version] [bank version] [title] [file name]

<out dir> is the folder make_kits.py (or make_techno.py, make_electro.py,
make_psy.py, make_industrial.py) wrote to; the list goes to
<out dir>/<file name> (BANK.txt by default).
"""
import json
import os
import sys

OUT = sys.argv[1]
FW = sys.argv[2] if len(sys.argv) > 2 else "0.5"
BANK = sys.argv[3] if len(sys.argv) > 3 else "0.5"
TITLE = sys.argv[4] if len(sys.argv) > 4 else "factory bank"
NAME = sys.argv[5] if len(sys.argv) > 5 else "BANK.txt"

THEME = {
    "precision": "precise, dry, glued by the compressor",
    "chrome": "metallic, ping-pong delay in time",
    "fracture": "broken, glitch, ratchets",
    "liquid": "fluid, delay with moving filter",
    "crunch": "tube-driven bus",
    "micro": "micro detail, clicks, crush",
    "torque": "hard fold/clip",
    "spatial": "wide stereo, movement",
    "warehouse": "rumble, bus saturation",
    "dub": "dub delay on rumble and atmos",
    "hypnotic": "rolling rumble, glue",
    "industrial": "driven bus, hard",
    "deep": "dark, delay",
    "peak": "big room glue",
    "acidwash": "crushed atmos, restless",
    "minimal": "sparse, dry",
    # electro
    "motorcity": "classic Detroit, glued",
    "aquatic": "deep, delay",
    "robotic": "dry, crushed FX",
    "cyberwar": "hard, driven bus",
    "breaker": "broken beat, saturation",
    "laserbeam": "lasers into the ping-pong delay",
    "bassquake": "808 weight, driven bus",
    "nightdrive": "smooth, delay and glue",
    # psy
    "forest": "organic: bubbles, creaks, wet wood",
    "swamp": "viscous, low: squelch, gurgle, quack",
    "dark": "hard, metallic: scrape, clang, noise",
    "goa": "melodic FX in key, delay",
    "twilight": "dark acid: resonant filter sweeps",
    # industrial
    "ironworks": "hard clipped bus",
    "noisewall": "noise, drive and glitch",
    "ritual": "tribal, delay",
    "assembly": "machine groove, glue",
    "voltage": "glitch, crushed metal",
    "furnace": "hard fold/clip",
    "concrete": "dry, delay and glue",
    "corrosion": "glitch, ratchets, crush",
}
FX = {"del": "delay", "drv": "drive", "glt": "glitch", "cmp": "comp", "rng": "ring", "off": "-"}
GROUP = {
    "MD": "0-31  MD - Machinedrum-inspired engines (tBD tSD tCP tHH EFM GND)",
    "PL": "32-63  PL - Plaits engines (aBD sBD aSD sSD pHH Mdl Str Prt)",
    "ID": "64-111  ID - IDM/glitch engines (Zap Crs Byt Rng Cmb)",
    "HY": "112-127  HY - hybrids of MD/PL/ID",
    "TK": "0-127  TK - techno: kick, rumble, atmos, rim/snare, clap, hats",
    "EL": "0-127  EL - electro: 808 kick, percussion, FX, snare, clap, hats",
    "PS": "0-127  PS - dark/forest psytrance: kick, rolling bass, psychedelic FX, rim, clap, hats",
    "IN": "0-127  IN - industrial: overdriven kick, rumble, metal/noise, snare, clap, hats",
}
# per bank family: channel roles, and which roles sit on scale degrees
ROLES = {
    None: (["Channel roles: 1 kick, 2 percussion/tom, 3 FX, 4 snare, 5 clap,",
            "6 closed hat; T7 = open hat on channel 6."], "tom", "FX"),
    "TK": (["Channel roles: 1 kick, 2 rumble, 3 atmosphere, 4 rim/snare, 5 clap,",
            "6 closed hat; T7 = open hat on channel 6. 'pump': rumble and atmosphere",
            "duck on every kick (their LFOs are retriggered by channel 1)."], "rumble", "atmosphere"),
    "EL": (["Channel roles: 1 kick (808 style), 2 percussion (cowbells, toms, blips),",
            "3 FX (zaps, lasers, beeps), 4 snare, 5 clap, 6 closed hat;",
            "T7 = open hat on channel 6."], "percussion", "FX"),
    "PS": (["Channel roles: 1 kick, 2 rolling bass (K-B-B-B: the three 16ths after",
            "every kick), 3 psychedelic FX, 4 rim (use it rarely), 5 clap (an accent,",
            "once a bar), 6 closed hat (16ths); T7 = dark open hat, at most once a bar.",
            "'pump': the bass ducks on every kick (its LFO is retriggered by channel 1).",
            "'growl': a filter envelope on the bass (an LFO restarted by every bass hit).",
            "'quack' / 'acid': the same on the FX filter; the other FX get S&H on the",
            "filter instead."], None, "FX"),
    "IN": (["Channel roles: 1 overdriven kick, 2 rumble, 3 metal/noise, 4 snare,",
            "5 clap, 6 closed hat; T7 = open hat on channel 6. 'pump': the rumble ducks",
            "on every kick (its LFO is retriggered by channel 1)."], "rumble", "metal"),
}
NO_DEMO = {"EL", "PS", "IN"}
BPM_COLUMN = {"EL", "PS", "IN"}     # the genre banks list every kit's tempo

with open(os.path.join(OUT, "bank.json")) as f:
    kits = json.load(f)
fams = set(k["family"] for k in kits)
BANK_FAM = fams.pop() if len(fams) == 1 and next(iter(fams)) in ROLES else None
roles, tuned2, tuned3 = ROLES[BANK_FAM]
if tuned2:
    key_text = ["Every kit has its own key (column 'key'): the kick sits on the tonic, the " + tuned2,
                "and " + tuned3 + " on scale degrees. Levels are balanced against the kick, all kits play"]
else:
    key_text = ["Every kit has its own key (column 'key'): the kick and the bass sit on the",
                "tonic (the bass is measured and fine tuned to it), the " + tuned3 + " on scale degrees.",
                "Levels are balanced against the kick, all kits play"]
folders = sorted(d for d in os.listdir(os.path.join(OUT, "shard")) if d.startswith("prj")) \
    if os.path.isdir(os.path.join(OUT, "shard")) else ["prj00"]
FOLDER = folders[0] if folders else "prj00"

out = [
    f"SHARD {TITLE} v{BANK}, {len(kits)} kits (firmware v{FW})",
    "",
    "Installation: copy the shard folder from this archive to the root of the SD",
    f"card. Existing kits in /shard/{FOLDER} (bank {FOLDER[3:]}) are replaced, so back up",
    "your own first.",
    "",
    *roles,
    "",
    *key_text,
    "at the same level. CV matrix: slot 1 = V/Oct (CV1), slot 2 = Decay (CV2), both",
    "at amount 0; slots 3-6 hold the internal movement (S&H on timbre, accents,",
    "LFOs on the FX bus).",
    "",
    ("slot name     bpm engines (1-6)             FX     key           character" if BANK_FAM in BPM_COLUMN else
     "slot name     engines (1-6)             FX     key           character"),
]
cur = None
for k in kits:
    if k["family"] != cur:
        cur = k["family"]
        out += ["", GROUP[cur], "-" * len(GROUP[cur])]
    mods = (" | " + ", ".join(k["notes"])) if k["notes"] else ""
    engines = " ".join(f"{e:3s}" for e in k["engines"])
    bpm = f"{k['bpm']:3d} " if BANK_FAM in BPM_COLUMN else ""
    out.append(f"{k['slot']:3d}  {k['name']:8s} {bpm}{engines}  {FX[k['fx']]:6s} {k['key']:13s} "
               f"{THEME[k['theme']]}{mods}")
out += [
    "",
    "lfN->fxM: the LFO of channel N moves parameter M of the effect (fwt = dry/wet).",
    *([] if BANK_FAM in NO_DEMO else ["demo/: the groove of every fourth kit, 2 bars, CV inputs at 0 V."]),
]
with open(os.path.join(OUT, NAME), "w", encoding="ascii") as f:
    f.write("\n".join(out) + "\n")
print(f"{len(kits)} kits listed in {os.path.join(OUT, NAME)}")
