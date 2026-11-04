#!/usr/bin/env python3
"""Write BANK.txt (the kit list shipped with the factory bank) from bank.json.

    python3 tools/kits/bank_txt.py <out dir> [firmware version] [bank version] [title]

<out dir> is the folder make_kits.py wrote to.
"""
import json
import os
import sys

OUT = sys.argv[1]
FW = sys.argv[2] if len(sys.argv) > 2 else "0.4"
BANK = sys.argv[3] if len(sys.argv) > 3 else "0.5"
TITLE = sys.argv[4] if len(sys.argv) > 4 else "factory bank"

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
}
FX = {"del": "delay", "drv": "drive", "glt": "glitch", "cmp": "comp", "off": "-"}
GROUP = {
    "MD": "0-31  MD - Machinedrum-inspired engines (tBD tSD tCP tHH EFM GND)",
    "PL": "32-63  PL - Plaits engines (aBD sBD aSD sSD pHH Mdl Str Prt)",
    "ID": "64-111  ID - IDM/glitch engines (Zap Crs Byt Rng Cmb)",
    "HY": "112-127  HY - hybrids of MD/PL/ID",
    "TK": "0-127  TK - techno: kick, rumble, atmos, rim/snare, clap, hats",
}

with open(os.path.join(OUT, "bank.json")) as f:
    kits = json.load(f)
techno = all(k["family"] == "TK" for k in kits)
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
    *(["Channel roles: 1 kick, 2 rumble, 3 atmosphere, 4 rim/snare, 5 clap,",
       "6 closed hat; T7 = open hat on channel 6. 'pump': rumble and atmosphere",
       "duck on every kick (their LFOs are retriggered by channel 1)."]
      if techno else
      ["Channel roles: 1 kick, 2 percussion/tom, 3 FX, 4 snare, 5 clap,",
       "6 closed hat; T7 = open hat on channel 6."]),
    "",
    "Every kit has its own key (column 'key'): the kick sits on the tonic, the "
    + ("rumble" if techno else "tom"),
    "and " + ("atmosphere" if techno else "FX") + " on scale degrees. Levels are balanced against the kick, all kits play",
    "at the same level. CV matrix: slot 1 = V/Oct (CV1), slot 2 = Decay (CV2), both",
    "at amount 0; slots 3-6 hold the internal movement (S&H on timbre, accents,",
    "LFOs on the FX bus).",
    "",
    "slot name     engines (1-6)             FX     key           character",
]
cur = None
for k in kits:
    if k["family"] != cur:
        cur = k["family"]
        out += ["", GROUP[cur], "-" * len(GROUP[cur])]
    mods = (" | " + ", ".join(k["notes"])) if k["notes"] else ""
    engines = " ".join(f"{e:3s}" for e in k["engines"])
    out.append(f"{k['slot']:3d}  {k['name']:8s} {engines}  {FX[k['fx']]:6s} {k['key']:13s} "
               f"{THEME[k['theme']]}{mods}")
out += [
    "",
    "lfN->fxM: the LFO of channel N moves parameter M of the effect (fwt = dry/wet).",
    "demo/: the groove of every fourth kit, 2 bars, CV inputs at 0 V.",
]
with open(os.path.join(OUT, "BANK.txt"), "w", encoding="ascii") as f:
    f.write("\n".join(out) + "\n")
print(f"{len(kits)} kits listed in {os.path.join(OUT, 'BANK.txt')}")
