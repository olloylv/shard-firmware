#!/usr/bin/env python3
"""Build the SHARD factory kit bank.

    python3 tools/kits/make_kits.py <shard_render> <out dir>

Writes <out dir>/shard/prj00/NN-NAME.snd (the module's kit files) and, for each
kit, renders a genre pattern with the desktop build to measure the channel
levels; channel volumes are then adjusted so that all kits are gain staged the
same way (kick loudest, hats quieter). Demo WAVs are written to <out dir>/demo.

Channel roles are the same in every kit:
    1 kick   2 snare   3 clap   4 perc / tom   5 perc / metal / fx
    6 hats   (trigger 7 = open hat on channel 6)

SPDX-License-Identifier: GPL-3.0-only
"""
import json
import os
import random
import subprocess
import sys

RENDER = sys.argv[1]
OUT = sys.argv[2]
WORK = os.path.join(OUT, "_work")
os.makedirs(WORK, exist_ok=True)

subprocess.run([RENDER, "--dump", os.path.join(WORK, "engines.json")], check=True)
T = json.load(open(os.path.join(WORK, "engines.json")))
ENG = {e["short"]: e for e in T["engines"]}
L = T["local"]
STRIDE = T["stride"]
BASE = T["par_ch_base"]
P = T["par"]

FILTER = {"off": 0, "lp": 1, "hp": 2, "bp": 3, "ubp": 4, "notch": 5, "peak": 6, "lp2": 7}
OUTS = {"st1": 0, "st2": 1, "l1": 2, "r1": 3, "l2": 4, "r2": 5, "fx": 6}
LFO = {"sin": 0, "tri": 1, "sup": 2, "sdn": 3, "sqr": 4, "rnd": 5, "xup": 6, "xdn": 7}
FX = {"off": 0, "drv": 1, "rng": 2, "cmp": 3, "del": 4}

# --- CV matrix destinations --------------------------------------------------
MT = T["mod_target_local"]
MTPC = T["mod_targets_per_ch"]
VOCT = 0xFF


def mod_dest(ch, local=None, engine_slot=None, voct=False):
    if voct:
        t = MT.index(VOCT)
    elif engine_slot is not None:
        t = MT.index(L["E0"] + engine_slot)
    else:
        t = MT.index(L[local])
    return 1 + ch * MTPC + t


def eslot(engine, short):
    for p in ENG[engine]["params"]:
        if p["short"] == short:
            return p
    raise KeyError(f"{engine} has no parameter {short}")


# --- channel / kit model -------------------------------------------------------
class Channel:
    def __init__(self, engine, tune=None, **strip):
        self.engine = engine
        self.block = list(ENG[engine]["defaults"])
        if tune is not None:
            self.block[L["TUNE"]] = tune
        self.set(**strip)
        self.role = None

    def p(self, **kw):
        """engine parameters by short name (lists: index or label)"""
        for k, v in kw.items():
            d = eslot(self.engine, k)
            if isinstance(v, str):
                v = [x.strip().lower() for x in d["labels"]].index(v.lower())
            self.block[L["E0"] + d["slot"]] = int(max(0, min(127, v)))
        return self

    def set(self, **kw):
        for k, v in kw.items():
            key = k.upper()
            if key == "FILT_TYPE" and isinstance(v, str):
                v = FILTER[v]
            if key == "OUT" and isinstance(v, str):
                v = OUTS[v]
            if key == "LFO_WAVE" and isinstance(v, str):
                v = LFO[v]
            if key == "AEG_MODE" and isinstance(v, str):
                v = 0 if v == "ad" else 1
            self.block[L[key]] = int(max(0, min(127, v)))
        return self


class Kit:
    def __init__(self, name, genre, bpm):
        self.name = name[:8]
        self.genre = genre
        self.bpm = bpm
        self.ch = []
        self.fx = {"type": "off", "routing": "st1", "drywet": 50, "p": [64, 64, 64, 64],
                   "dist": 0, "ratio": 3, "wave": 0, "delay": 0}
        self.cv = []   # (ch, slot 0..2, src, amount, dest)

    def params(self):
        par = [0] * T["end_of_sound"]
        par[0] = 1   # SH_KIT_VERSION
        for i, c in enumerate(self.ch):
            for k, v in enumerate(c.block):
                par[BASE + i * STRIDE + k] = v
        f = self.fx
        par[P["FX_TYPE"]] = FX[f["type"]]
        par[P["FX_ROUTING"]] = OUTS[f["routing"]]
        par[P["FX_DRY_WET"]] = f["drywet"]
        par[P["FX_DIST_TYPE"]] = f["dist"]
        for i in range(4):
            par[P["FX_P1"] + i] = f["p"][i]
        par[P["FX_RATIO"]] = f["ratio"]
        par[P["FX_WAVE"]] = f["wave"]
        par[P["FX_DELAY_TYPE"]] = f["delay"]
        # CV matrix: slot 1 and 2 of every channel are ready for the CV inputs
        # (amount 0, so they do nothing until the amount is raised)
        for ch in range(6):
            for s in range(3):
                i = ch * 3 + s
                par[P["CV_SRC_1"] + i] = ch % 5
                par[P["CV_MOD_AMT_1"] + i] = 0
                par[P["CV_DEST_1"] + i] = 0
            par[P["CV_DEST_1"] + ch * 3] = mod_dest(ch, voct=True)
            par[P["CV_DEST_1"] + ch * 3 + 1] = mod_dest(ch, "DECAY")
        for ch, slot, src, amt, dest in self.cv:
            i = ch * 3 + slot
            par[P["CV_SRC_1"] + i] = src
            par[P["CV_MOD_AMT_1"] + i] = amt
            par[P["CV_DEST_1"] + i] = dest
        return par

    def lfo_mod(self, ch, dest, amount, wave="rnd", freq=40, slot=2):
        """internal movement: channel LFO -> parameter (CV matrix slot 3)"""
        c = self.ch[ch]
        c.set(lfo_wave=wave, lfo_freq=freq)
        self.cv.append((ch, slot, 5 + ch, amount, dest))

    def write(self, path):
        name = self.name.ljust(8)[:8].encode("ascii")
        with open(path, "wb") as f:
            f.write(name)
            f.write(bytes(self.params()))


def r(rng, lo, hi):
    return rng.randint(lo, hi)


# =============================================================================
# role recipes
# =============================================================================
def kick(rng, style):
    if style == "808":
        return Channel("aBD", r(rng, 29, 36)).p(Ton=r(rng, 25, 60), Dec=r(rng, 70, 110),
                                                AFM=r(rng, 20, 60), SFM=r(rng, 10, 40), Drv=r(rng, 0, 30))
    if style == "909":
        return Channel("tBD", r(rng, 30, 36)).p(Swp=r(rng, 40, 62), SwD=r(rng, 22, 45), Dec=r(rng, 38, 62),
                                                Hld=r(rng, 0, 20), Clk=r(rng, 30, 70), Drv=r(rng, 15, 45))
    if style == "rumble":
        return Channel("tBD", r(rng, 28, 33)).p(Swp=r(rng, 30, 50), SwD=r(rng, 30, 50), Dec=r(rng, 70, 95),
                                                Hld=r(rng, 10, 40), Clk=r(rng, 10, 40), Drv=r(rng, 40, 80))
    if style == "synth":
        return Channel("sBD", r(rng, 30, 38)).p(Ton=r(rng, 40, 80), Dec=r(rng, 40, 80), Drt=r(rng, 10, 60),
                                                FMA=r(rng, 30, 80), FMD=r(rng, 20, 60))
    if style == "dirty":
        return Channel("sBD", r(rng, 29, 35)).p(Ton=r(rng, 60, 100), Dec=r(rng, 50, 80), Drt=r(rng, 60, 110),
                                                FMA=r(rng, 50, 100), FMD=r(rng, 30, 70)).set(drive=r(rng, 30, 70))
    if style == "lxr":
        return Channel("Drm", r(rng, 33, 40)).p(Wav="Sin", PDc=r(rng, 25, 45), PSl=r(rng, 40, 70),
                                               PAm=r(rng, 35, 60), FMA=0, TrW="Kik", TrV=r(rng, 30, 70),
                                               TrF=r(rng, 20, 40)).set(decay=r(rng, 26, 40), slope=r(rng, 20, 40))
    if style == "click":
        return Channel("tBD", r(rng, 34, 40)).p(Swp=r(rng, 55, 80), SwD=r(rng, 10, 25), Dec=r(rng, 20, 38),
                                                Hld=0, Clk=r(rng, 60, 100), Drv=r(rng, 0, 30))
    if style == "efm":
        return Channel("EFM", r(rng, 30, 36)).p(Rat="1", Mod=r(rng, 20, 50), MDc=r(rng, 15, 35), FB=r(rng, 0, 30),
                                                Swp=r(rng, 50, 80), SwD=r(rng, 20, 40), Dec=r(rng, 40, 70), Noi=0)
    raise ValueError(style)


def snare(rng, style):
    if style == "808":
        return Channel("aSD", r(rng, 48, 56)).p(Ton=r(rng, 40, 80), Dec=r(rng, 30, 60), Snp=r(rng, 60, 100))
    if style == "909":
        return Channel("tSD", r(rng, 50, 57)).p(Bdy=r(rng, 70, 100), Snp=r(rng, 80, 115), Dec=r(rng, 30, 50),
                                                NDc=r(rng, 40, 65), Swp=r(rng, 25, 50), NTn=r(rng, 60, 90))
    if style == "synth":
        return Channel("sSD", r(rng, 48, 58)).p(FMA=r(rng, 20, 70), Dec=r(rng, 35, 65), Snp=r(rng, 50, 100))
    if style == "noise":
        return Channel("Crs", r(rng, 55, 70)).p(Src="Noi", Rat=r(rng, 20, 60), Bit=r(rng, 40, 90),
                                               Jit=r(rng, 0, 40), Dec=r(rng, 45, 70), Glt=0)
    if style == "lxr":
        return Channel("Snr", r(rng, 50, 58)).p(Wav="Tri", Noi=r(rng, 90, 120), NFF=r(rng, 80, 110),
                                               NFR=r(rng, 10, 40), NFT="HP", PDc=r(rng, 30, 50), PAm=r(rng, 20, 40),
                                               Mix=r(rng, 60, 95)).set(decay=r(rng, 16, 28), slope=r(rng, 20, 40))
    if style == "rim":
        return Channel("Mdl", r(rng, 64, 76)).p(Str=r(rng, 10, 40), Bri=r(rng, 70, 110), Dmp=r(rng, 20, 45), Exc=r(rng, 20, 60))
    if style == "efm":
        return Channel("EFM", r(rng, 52, 60)).p(Rat=rng.choice(["1.4", "2.7", "3.1", "5.2"]), Mod=r(rng, 60, 100),
                                                MDc=r(rng, 25, 45), FB=r(rng, 20, 60), Swp=r(rng, 20, 45),
                                                SwD=r(rng, 20, 35), Dec=r(rng, 30, 50), Noi=r(rng, 60, 110))
    raise ValueError(style)


def clap(rng, style):
    if style == "909":
        return Channel("tCP", r(rng, 88, 100)).p(Dec=r(rng, 35, 60), Spc=r(rng, 35, 60), Num=r(rng, 2, 4),
                                                 Q=r(rng, 15, 45), Rnd=r(rng, 15, 45))
    if style == "tight":
        return Channel("tCP", r(rng, 94, 108)).p(Dec=r(rng, 15, 35), Spc=r(rng, 20, 40), Num=r(rng, 1, 3),
                                                 Q=r(rng, 30, 60), Rnd=r(rng, 0, 30))
    if style == "wide":
        return Channel("tCP", r(rng, 82, 96)).p(Dec=r(rng, 60, 90), Spc=r(rng, 55, 80), Num=r(rng, 4, 7),
                                                Q=r(rng, 10, 30), Rnd=r(rng, 40, 80))
    if style == "lxr":
        return Channel("Snr", r(rng, 60, 70)).p(Wav="Noi", Noi=r(rng, 100, 127), NFF=r(rng, 80, 100), NFR=r(rng, 0, 20),
                                               NFT="BP", Mix=r(rng, 100, 127)).set(repeat=r(rng, 2, 4), attack=r(rng, 6, 14), drive=r(rng, 30, 60),
                                                                                    decay=r(rng, 22, 34), slope=25)
    raise ValueError(style)


def hats(rng, style):
    if style == "808":
        return Channel("pHH", r(rng, 66, 80)).p(Ton=r(rng, 50, 90), Dec=r(rng, 15, 35), Noi=r(rng, 20, 60),
                                                Typ="808", Opn=r(rng, 75, 100))
    if style == "ring":
        return Channel("pHH", r(rng, 70, 84)).p(Ton=r(rng, 60, 100), Dec=r(rng, 10, 30), Noi=r(rng, 10, 50),
                                                Typ="Rng", Opn=r(rng, 70, 95))
    if style == "909":
        return Channel("tHH", r(rng, 76, 90)).p(Ton=r(rng, 55, 85), Dec=r(rng, 12, 30), Mtl=r(rng, 60, 100),
                                                Opn=r(rng, 70, 95), Res=r(rng, 10, 40))
    if style == "noise":
        return Channel("tHH", r(rng, 80, 96)).p(Ton=r(rng, 70, 100), Dec=r(rng, 14, 28), Mtl=r(rng, 0, 30),
                                                Opn=r(rng, 60, 85), Res=r(rng, 0, 30))
    if style == "lxr":
        return Channel("Hat", r(rng, 80, 92)).p(Wav="Rec", MF1=r(rng, 85, 105), MF2=r(rng, 95, 120), MG1=r(rng, 70, 110),
                                               MG2=r(rng, 50, 100), MW1="Rec", MW2="Rec").set(
            decay=r(rng, 4, 10), decay_alt=r(rng, 30, 45), filt_type="hp", filt_freq=r(rng, 68, 85), slope=20)
    if style == "crush":
        return Channel("Crs", r(rng, 80, 100)).p(Src="Noi", Rat=r(rng, 5, 30), Bit=r(rng, 50, 100), Jit=r(rng, 10, 50),
                                                Dec=r(rng, 15, 35), Glt=r(rng, 0, 30)).set(decay_alt=40)
    raise ValueError(style)


def perc(rng, style):
    """channels 4/5: toms, cowbells, rims, metals, zaps, glitches, ..."""
    if style == "tom":
        return Channel("aBD", r(rng, 43, 55)).p(Ton=r(rng, 40, 80), Dec=r(rng, 45, 75), AFM=r(rng, 10, 40),
                                                SFM=r(rng, 0, 20), Drv=0)
    if style == "tom909":
        return Channel("tBD", r(rng, 45, 57)).p(Swp=r(rng, 20, 40), SwD=r(rng, 30, 50), Dec=r(rng, 40, 60),
                                                Hld=0, Clk=r(rng, 10, 30), Drv=r(rng, 0, 20))
    if style == "cowbell":
        return Channel("Rng", r(rng, 70, 78)).p(Spr=r(rng, 0, 20), RM=r(rng, 0, 30), Ton=r(rng, 70, 95),
                                                Res=r(rng, 40, 80), Wav="Sqr").set(decay=r(rng, 14, 24), slope=25)
    if style == "metal":
        return Channel("Rng", r(rng, 60, 80)).p(Spr=r(rng, 80, 127), RM=r(rng, 80, 127), Ton=r(rng, 85, 115),
                                                Res=r(rng, 10, 50), Wav="Sqr").set(decay=r(rng, 28, 50), slope=30)
    if style == "bell":
        return Channel("Mdl", r(rng, 66, 84)).p(Str=r(rng, 70, 110), Bri=r(rng, 60, 100), Dmp=r(rng, 60, 95), Exc=r(rng, 0, 30))
    if style == "wood":
        return Channel("Mdl", r(rng, 60, 76)).p(Str=r(rng, 0, 30), Bri=r(rng, 40, 80), Dmp=r(rng, 15, 40), Exc=r(rng, 20, 60))
    if style == "pluck":
        return Channel("Str", r(rng, 45, 64)).p(Str=r(rng, 20, 80), Bri=r(rng, 50, 100), Dmp=r(rng, 40, 80), Exc=r(rng, 0, 30))
    if style == "efmperc":
        return Channel("EFM", r(rng, 55, 75)).p(Rat=rng.choice(["2.7", "3.1", "3.5", "5.2", "7", "11"]), Mod=r(rng, 40, 90),
                                                MDc=r(rng, 15, 40), FB=r(rng, 0, 50), Swp=r(rng, 0, 30),
                                                SwD=r(rng, 10, 30), Dec=r(rng, 20, 45), Noi=r(rng, 0, 30))
    if style == "zap":
        return Channel("Zap", r(rng, 36, 60)).p(Dep=r(rng, 70, 115), Tim=r(rng, 15, 50), FB=r(rng, 0, 60),
                                                Dec=r(rng, 40, 80), Dir=rng.choice(["Dwn", "Dwn", "Up", "Bth"]))
    if style == "laser":
        return Channel("Zap", r(rng, 60, 80)).p(Dep=r(rng, 40, 80), Tim=r(rng, 40, 75), FB=r(rng, 20, 70),
                                                Dec=r(rng, 50, 80), Dir="Dwn")
    if style == "glitch":
        return Channel("Crs", r(rng, 40, 80)).p(Src=rng.choice(["Sqr", "Saw", "FM"]), Rat=r(rng, 40, 90),
                                                Bit=r(rng, 70, 115), Jit=r(rng, 30, 90), Dec=r(rng, 30, 60), Glt=r(rng, 30, 90))
    if style == "byte":
        return Channel("Byt", r(rng, 48, 72)).p(Frm=r(rng, 0, 7), A=r(rng, 0, 127), B=r(rng, 0, 127),
                                                Rst=1).set(decay=r(rng, 12, 30), slope=20)
    if style == "comb":
        return Channel("Cmb", r(rng, 40, 70)).p(Exc=rng.choice(["Imp", "Noi", "Clk"]), FB=r(rng, 110, 124),
                                                Dmp=r(rng, 10, 60), Bur=r(rng, 5, 40), Rat=r(rng, 0, 127),
                                                Mx2=r(rng, 20, 80)).set(decay=r(rng, 30, 52))
    if style == "particle":
        return Channel("Prt", r(rng, 70, 96)).p(Den=r(rng, 40, 90), Res=r(rng, 60, 110), Spr=r(rng, 20, 80)).set(
            decay=r(rng, 14, 32), slope=20)
    if style == "gnd":
        return Channel("GND", r(rng, 60, 90)).p(Wav=rng.choice(["Imp", "S&H", "Sqr"]), Swp=r(rng, 30, 100),
                                                SwD=r(rng, 10, 40)).set(decay=r(rng, 6, 20), slope=20)
    if style == "lxrtom":
        return Channel("Drm", r(rng, 45, 58)).p(Wav="Sin", PDc=r(rng, 30, 50), PAm=r(rng, 25, 45), FMA=r(rng, 0, 30),
                                               FMF=r(rng, 64, 90), TrW="Tom", TrV=r(rng, 20, 50)).set(decay=r(rng, 26, 40), slope=30)
    if style == "rim":
        return snare(rng, "rim")
    if style == "cym":
        return Channel("Cym", r(rng, 68, 80)).p(Wav="Sin", MF1=r(rng, 80, 100), MF2=r(rng, 95, 115), MG1=r(rng, 70, 110),
                                               MG2=r(rng, 50, 90), MW1="Rec", MW2="Tri").set(
            decay=r(rng, 55, 75), filt_type="hp", filt_freq=r(rng, 62, 78), slope=30)
    if style == "ride":
        return Channel("Rng", r(rng, 72, 86)).p(Spr=r(rng, 90, 127), RM=r(rng, 90, 127), Ton=r(rng, 95, 120),
                                                Res=r(rng, 5, 30), Wav="Sqr").set(decay=r(rng, 50, 70), slope=35,
                                                                                   filt_type="hp", filt_freq=r(rng, 60, 75))
    raise ValueError(style)


# =============================================================================
# genres
# =============================================================================
WORDS = {
    "EL": ["Drexc", "Cybrt", "Plnet", "Nmbr", "Clear", "Model", "Robot", "Bass", "Optic", "Zone",
           "Sharp", "Moto", "Lazr", "Vandr", "Ultra", "Grid", "Spcr", "Krome", "Pulse", "Rfrnc"],
    "TK": ["Warhs", "Basmt", "Tresr", "Strob", "Iron", "Hypno", "Loop", "Rumbl", "Acid", "Berg",
           "Steel", "Tunnl", "Drone", "Night", "Pound", "Ritul", "Fog", "Volt", "Pit", "Mono"],
    "ID": ["Glich", "Skwee", "Fract", "Splnt", "Shard", "Brkcr", "Corrp", "Micro", "Pixel", "Dust",
           "Sprng", "Wires", "Ctrl", "Bleep", "Shrap", "Melt", "Nerve", "Prism", "Chip", "Ether"],
    "MN": ["Click", "Wood", "Dub", "Echo", "Dry", "Pulse", "Tiny", "Deep", "Room", "Felt",
           "Drip", "Pebbl", "Grain", "Minim", "Tape", "Moss", "Chord", "Space", "Haze", "Soft"],
    "IN": ["Grind", "Rust", "Press", "Fact", "Hammr", "Slag", "Bunkr", "Chain", "Mach", "Ebm",
           "Sirn", "Furn", "Anvil", "Steam", "Crush", "Riot", "Smog", "Weld", "Drill", "Burn"],
    "BR": ["Amen", "Jungl", "Breka", "Roll", "Think", "Dread", "Step", "Ruff", "Atmos", "Liqd",
           "Neuro", "Ragga", "Hrdcr", "Dark", "Speed", "Chop", "Tekst", "Swing", "Sub", "Funky"],
}

PATTERNS = {   # kick, snare, clap, perc4, perc5, hats ('o' = open hat via trigger 7)
    "EL": ["X..x..x...X..x..", "....X.......X...", "....x.......x..x", "......x.....x.x.", "..x.......x....x", "xxxoxxxxxxxoxxxx"],
    "TK": ["X...X...X...X...", "...x.......x..x.", "....x.......x...", "..x...x...x..xx.", "x.x.x.x.x.x.x.x.", "..o...o...o...o."],
    "ID": ["X..x.r....X.x...", "....X..x...rX...", "......x.......x.", "..x.x....x.xr...", "r..x..x.x...x..r", "xx.xxrx.xo.xxrxo"],
    "MN": ["X...X...X...X...", "............x...", "....x.......x...", "..x.....x..x....", "...x..x....x..x.", "x.x.x.x.x.x.x.xo"],
    "IN": ["X..xX...X..xX...", "....X.......X...", "....x.......x...", "x...x.x.x...x.x.", "..x...x...x...x.", "xxoxxxoxxxoxxxox"],
    "BR": ["X.........X.....", "....X.......X...", "......x.......x.", "..x..x....x..x..", ".......x.x....x.", "x.xxx.xxx.xxxox."],
}


def drive_fx(rng, hard=False):
    """FX bus distortion. P1..P4 of the LXR distortion: tube = drive, colour,
    tone, level; fold = drive, offset, tone, level; clip (RAT) = drive,
    feedback, tone, level. Offset and feedback stay low: the fold offset is
    a DC shift and the RAT feedback self-oscillates on silence."""
    dist = rng.choice([0, 0, 1, 2]) if not hard else rng.choice([0, 1, 2, 2])
    drive = r(rng, 30, 70) if not hard else r(rng, 55, 100)
    # fold: small offset only; clip: no feedback (it self-oscillates at high drive)
    p1 = r(rng, 20, 80) if dist == 0 else 0
    return dict(dist=dist, p=[drive, p1, r(rng, 40, 90), r(rng, 55, 85)])


def electro(rng, i):
    k = Kit(f"EL{WORDS['EL'][i]}", "EL", r(rng, 122, 136))
    k.ch = [kick(rng, rng.choice(["808", "808", "synth", "lxr"])),
            snare(rng, rng.choice(["808", "808", "synth", "lxr"])),
            clap(rng, rng.choice(["909", "wide", "lxr"])),
            perc(rng, rng.choice(["tom", "lxrtom", "cowbell", "zap"])),
            perc(rng, rng.choice(["cowbell", "laser", "zap", "bell", "efmperc"])),
            hats(rng, rng.choice(["808", "808", "lxr", "ring"]))]
    k.ch[0].set(pan=64)
    k.ch[3].set(pan=r(rng, 40, 56))
    k.ch[4].set(pan=r(rng, 72, 90))
    k.ch[5].set(pan=r(rng, 56, 72))
    # electro: delay on clap + perc 5
    if rng.random() < 0.8:
        k.fx.update(type="del", drywet=r(rng, 25, 45), p=[r(rng, 70, 110), r(rng, 60, 100), r(rng, 40, 80), r(rng, 40, 75)],
                    delay=rng.choice([0, 1]))
        k.ch[2].set(out="fx")
        k.ch[4].set(out="fx")
    else:
        k.fx.update(type="rng", drywet=r(rng, 40, 70), p=[r(rng, 20, 90), 64, 64, 64], wave=rng.choice([0, 1, 3]))
        k.ch[4].set(out="fx")
    return k


def techno(rng, i):
    k = Kit(f"TK{WORDS['TK'][i]}", "TK", r(rng, 128, 140))
    k.ch = [kick(rng, rng.choice(["909", "909", "rumble", "synth"])),
            snare(rng, rng.choice(["909", "rim", "noise"])),
            clap(rng, rng.choice(["909", "tight", "909"])),
            perc(rng, rng.choice(["tom909", "efmperc", "wood", "cowbell"])),
            perc(rng, rng.choice(["ride", "metal", "efmperc", "particle"])),
            hats(rng, rng.choice(["909", "909", "noise", "ring"]))]
    k.ch[3].set(pan=r(rng, 40, 56))
    k.ch[4].set(pan=r(rng, 70, 88))
    if rng.random() < 0.5:
        # dub techno style delay on perc and clap
        k.fx.update(type="del", drywet=r(rng, 30, 55), p=[r(rng, 75, 115), r(rng, 80, 120), r(rng, 20, 60), r(rng, 55, 90)],
                    delay=1)
        k.ch[2].set(out="fx")
        k.ch[3].set(out="fx")
    else:
        # distorted percussion bus
        k.fx.update(type="drv", drywet=r(rng, 50, 90), **drive_fx(rng))
        k.ch[3].set(out="fx")
        k.ch[4].set(out="fx")
    if rng.random() < 0.5:   # moving filter on the metal channel
        k.ch[4].set(filt_type="hp", filt_freq=r(rng, 60, 90), filt_reso=r(rng, 20, 60))
        k.lfo_mod(4, mod_dest(4, "FILT_FREQ"), r(rng, 15, 35), wave="tri", freq=r(rng, 15, 30))
    return k


def idm(rng, i):
    k = Kit(f"ID{WORDS['ID'][i]}", "ID", r(rng, 140, 170))
    k.ch = [kick(rng, rng.choice(["click", "efm", "synth", "dirty"])),
            snare(rng, rng.choice(["noise", "efm", "rim", "synth"])),
            perc(rng, rng.choice(["glitch", "byte", "zap", "comb"])),
            perc(rng, rng.choice(["comb", "zap", "byte", "gnd", "bell"])),
            perc(rng, rng.choice(["glitch", "particle", "laser", "metal", "comb"])),
            hats(rng, rng.choice(["crush", "noise", "ring", "808"]))]
    for c in range(1, 6):
        k.ch[c].set(pan=r(rng, 24, 104))
    # bit and sample rate damage
    for c in rng.sample(range(6), 2):
        k.ch[c].set(bits=r(rng, 40, 90))
    k.ch[rng.randrange(1, 6)].set(srate=r(rng, 60, 105))
    # clap-style repeats as ratchets
    k.ch[rng.randrange(2, 5)].set(repeat=r(rng, 2, 6), attack=r(rng, 3, 10))
    # random LFO movement
    for c in rng.sample(range(1, 6), 2):
        target = rng.choice(["BITS", "FILT_FREQ", "DECAY", "PAN", "SRATE"])
        if target == "FILT_FREQ":
            k.ch[c].set(filt_type=rng.choice(["lp", "bp", "hp"]), filt_freq=r(rng, 50, 90), filt_reso=r(rng, 30, 80))
        k.lfo_mod(c, mod_dest(c, target), r(rng, 20, 45), wave=rng.choice(["rnd", "sqr", "xdn", "tri"]), freq=r(rng, 30, 70))
    if rng.random() < 0.5:
        k.fx.update(type="rng", drywet=r(rng, 30, 70), p=[r(rng, 10, 120), 64, 64, 64], wave=rng.choice([0, 2, 3, 5]))
    else:
        k.fx.update(type="del", drywet=r(rng, 30, 60), p=[r(rng, 10, 60), r(rng, 10, 60), r(rng, 50, 100), r(rng, 60, 100)],
                    delay=1)
    for c in rng.sample(range(2, 5), 2):
        k.ch[c].set(out="fx")
    return k


def minimal(rng, i):
    k = Kit(f"MN{WORDS['MN'][i]}", "MN", r(rng, 120, 128))
    k.ch = [kick(rng, rng.choice(["909", "click", "808"])),
            snare(rng, rng.choice(["rim", "rim", "synth"])),
            clap(rng, rng.choice(["tight", "909"])),
            perc(rng, rng.choice(["wood", "bell", "pluck"])),
            perc(rng, rng.choice(["particle", "wood", "comb", "pluck"])),
            hats(rng, rng.choice(["808", "noise", "ring"]))]
    k.ch[0].p(**({"Dec": r(rng, 30, 50)} if k.ch[0].engine == "tBD" else {}))
    k.ch[3].set(pan=r(rng, 36, 54))
    k.ch[4].set(pan=r(rng, 74, 92))
    k.fx.update(type="del", drywet=r(rng, 35, 60), p=[r(rng, 80, 120), r(rng, 90, 127), r(rng, 15, 50), r(rng, 65, 95)],
                delay=1)
    k.ch[2].set(out="fx")
    k.ch[3].set(out="fx")
    if rng.random() < 0.5:
        k.ch[4].set(out="fx")
    k.lfo_mod(3, mod_dest(3, "PAN"), r(rng, 15, 35), wave="sin", freq=r(rng, 10, 25))
    return k


def industrial(rng, i):
    k = Kit(f"IN{WORDS['IN'][i]}", "IN", r(rng, 118, 132))
    k.ch = [kick(rng, rng.choice(["dirty", "rumble", "909"])),
            snare(rng, rng.choice(["noise", "909", "lxr", "efm"])),
            clap(rng, rng.choice(["wide", "909", "lxr"])),
            perc(rng, rng.choice(["metal", "tom909", "efmperc", "comb"])),
            perc(rng, rng.choice(["metal", "glitch", "laser", "ride"])),
            hats(rng, rng.choice(["noise", "crush", "909"]))]
    k.ch[0].set(drive=r(rng, 30, 70))
    k.ch[1].set(drive=r(rng, 30, 80))
    k.ch[3].set(pan=r(rng, 36, 56))
    k.ch[4].set(pan=r(rng, 72, 92))
    k.fx.update(type="drv", drywet=r(rng, 60, 100), **drive_fx(rng, hard=True))
    for c in (1, 2, 3):
        k.ch[c].set(out="fx")
    if rng.random() < 0.5:
        k.ch[4].set(bits=r(rng, 30, 70))
    return k


def breaks(rng, i):
    k = Kit(f"BR{WORDS['BR'][i]}", "BR", r(rng, 165, 175))
    k.ch = [kick(rng, rng.choice(["909", "808", "lxr"])),
            snare(rng, rng.choice(["808", "909", "lxr"])),
            clap(rng, rng.choice(["tight", "909"])),
            perc(rng, rng.choice(["tom", "lxrtom", "wood"])),
            perc(rng, rng.choice(["ride", "cym", "particle"])),
            hats(rng, rng.choice(["808", "909", "lxr"]))]
    # jungle snares: tuned up, snappy
    k.ch[1].set(tune=min(127, k.ch[1].block[L["TUNE"]] + r(rng, 3, 9)))
    k.ch[0].set(decay=30)
    k.ch[3].set(pan=r(rng, 40, 56))
    k.ch[4].set(pan=r(rng, 70, 90))
    k.fx.update(type="cmp", drywet=100, ratio=r(rng, 2, 4), p=[r(rng, 0, 20), r(rng, 20, 60), r(rng, 60, 90), r(rng, 20, 50)])
    for c in (0, 1, 2):
        k.ch[c].set(out="fx")
    return k


def classic(rng, i):
    """the original LXR voices, for slots 120..127"""
    names = ["Classic", "Analog", "Punch", "Metal", "Snap", "Boom", "Tin", "Retro"]
    k = Kit(f"LX{names[i]}"[:8], "LX", r(rng, 120, 135))
    k.ch = [kick(rng, "lxr"), snare(rng, "lxr"), clap(rng, "lxr"), perc(rng, "lxrtom"), perc(rng, "cym"), hats(rng, "lxr")]
    k.ch[3].set(pan=r(rng, 40, 56))
    k.ch[4].set(pan=r(rng, 72, 90))
    if i % 2:
        k.fx.update(type="del", drywet=r(rng, 25, 45), p=[r(rng, 70, 110), r(rng, 60, 100), r(rng, 40, 80), r(rng, 40, 70)])
        k.ch[2].set(out="fx")
    return k


WORDS["LX"] = []
PATTERNS["LX"] = ["X...x.....X.x...", "....X.......X...", "............x..x", "......x.......x.", "x...............", "x.x.x.x.x.x.x.xo"]

GENRES = [("EL", electro), ("TK", techno), ("ID", idm), ("MN", minimal), ("IN", industrial), ("BR", breaks)]

# loudness targets per channel (peak, linear) and how far the RMS may push it down
TARGET_PEAK = [0.85, 0.60, 0.50, 0.45, 0.40, 0.32]


def render(kit, path_snd, wav=""):
    pat = os.path.join(WORK, f"pat_{kit.genre}.txt")
    with open(pat, "w") as f:
        f.write("\n".join(PATTERNS[kit.genre]) + "\n")
    met = os.path.join(WORK, "metrics.json")
    kit.write(path_snd)
    subprocess.run([RENDER, "--kit", path_snd, pat, str(kit.bpm), "2", wav, met], check=True)
    return json.load(open(met))


def file_name(slot, name):
    clean = "".join(c if c.isalnum() else "_" for c in name)
    return f"{slot:02d}-{clean[:5]}.snd" if slot < 100 else f"{slot:03d}-{clean[:4]}.snd"


def main():
    kit_dir = os.path.join(OUT, "shard", "prj00")
    demo_dir = os.path.join(OUT, "demo")
    os.makedirs(kit_dir, exist_ok=True)
    os.makedirs(demo_dir, exist_ok=True)
    slot = 0
    report = []
    for code, fn in GENRES + [("LX", classic)]:
        for i in range(20 if code != "LX" else 8):
            rng = random.Random(f"{code}-{i}")
            kit = fn(rng, i)
            path = os.path.join(kit_dir, file_name(slot, kit.name))
            # gain staging on the channel volumes; quiet engines that are
            # already at full volume get some of the channel drive as make-up gain
            for _ in range(4):
                m = render(kit, path)
                for c in range(6):
                    pk = m["peak"][c]
                    vol = kit.ch[c].block[L["VOL"]]
                    if pk < 1e-4:
                        continue
                    new = int(round(vol * TARGET_PEAK[c] / pk))
                    if new > 127 and pk < 0.75 * TARGET_PEAK[c]:
                        drv = kit.ch[c].block[L["DRIVE"]]
                        kit.ch[c].set(drive=min(90, drv + 25))
                    kit.ch[c].set(vol=max(20, min(127, new)))
            m = render(kit, path, os.path.join(demo_dir, f"{slot:03d}_{kit.name}.wav") if i < 3 else "")
            report.append((slot, kit.name, kit.bpm, [c.engine for c in kit.ch], m["mix_peak"],
                           [round(x, 2) for x in m["peak"]], kit.fx["type"], m["tail"]))
            slot += 1
    with open(os.path.join(OUT, "bank.txt"), "w") as f:
        for s, name, bpm, engines, mp, peaks, fx, tail in report:
            f.write(f"{s:3d} {name:8s} {bpm:3d}bpm  {' '.join(f'{e:3s}' for e in engines)}  fx={fx:3s}  "
                    f"mix={mp:.2f} tail={tail:.4f} peaks={peaks}\n")
    print(f"{slot} kits written to {kit_dir}")


main()
