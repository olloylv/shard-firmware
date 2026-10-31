#!/usr/bin/env python3
"""Build the SHARD factory kit bank.

    python3 tools/kits/make_kits.py <shard_render> <out dir>

Writes <out dir>/shard/prj00/NNN-NAME.snd (the module's kit files),
<out dir>/bank.txt and demo WAVs in <out dir>/demo.

The bank is grouped by the engines that dominate a kit:

      0 -  31  MD     Machinedrum style engines (tBD tSD tCP tHH EFM GND)
     32 -  63  PL     Plaits engines (aBD sBD aSD sSD pHH Mdl Str Prt)
     64 - 111  ID     IDM / glitch engines (Zap Crs Byt Rng Cmb), the wild part
    112 - 127  HY     hybrids, free mix of MD, PL and ID

The original LXR voices are not used in the bank (they are still engines).

At least four of the six channels of a kit come from its family. Channel
roles are the same in every kit:
    1 kick   2 perc / tom   3 fx / metal / glitch   4 snare   5 clap
    6 closed hat   (trigger 7 = open hat on channel 6)

Every kit is checked with single hits of each channel (tools/kits/analyse.py):
sounds that ring too long, high tones that sustain (whistles) and long high
frequency tails are shortened until they pass. Then the channel volumes are
gain staged with a rendered pattern.

SPDX-License-Identifier: GPL-3.0-only
"""
import json
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyse import analyse  # noqa: E402

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
FX = {"off": 0, "drv": 1, "glt": 2, "cmp": 3, "del": 4}

FAMILY = {
    "MD": {"tBD", "tSD", "tCP", "tHH", "EFM", "GND"},
    "PL": {"aBD", "sBD", "aSD", "sSD", "pHH", "Mdl", "Str", "Prt"},
    "ID": {"Zap", "Crs", "Byt", "Rng", "Cmb"},
    "LX": {"Drm", "Snr", "Cym", "Hat"},   # not used in the bank
}

# --- CV matrix destinations --------------------------------------------------
MT = T["mod_target_local"]
MTPC = T["mod_targets_per_ch"]
MCB = T["mod_ch_base"]
VOCT = 0xFF
GLOBAL = {"mrp": 1, "mtg": 2, "msh": 3, "fwt": 4, "fx1": 5, "fx2": 6, "fx3": 7, "fx4": 8}


def mod_dest(ch, local=None, engine_slot=None, voct=False):
    if voct:
        t = MT.index(VOCT)
    elif engine_slot is not None:
        t = MT.index(L["E0"] + engine_slot)
    else:
        t = MT.index(L[local])
    return MCB + ch * MTPC + t


def eslot(engine, short):
    for p in ENG[engine]["params"]:
        if p["short"] == short:
            return p
    raise KeyError(f"{engine} has no parameter {short}")


def has(engine, short):
    return any(p["short"] == short for p in ENG[engine]["params"])


# --- channel / kit model -------------------------------------------------------
class Channel:
    def __init__(self, engine, tune=None, **strip):
        self.engine = engine
        self.block = list(ENG[engine]["defaults"])
        if tune is not None:
            self.block[L["TUNE"]] = tune
        self.set(**strip)

    def p(self, **kw):
        """engine parameters by short name (lists: index or label)"""
        for k, v in kw.items():
            d = eslot(self.engine, k)
            if isinstance(v, str):
                v = [x.strip().lower() for x in d["labels"]].index(v.strip().lower())
            self.block[L["E0"] + d["slot"]] = int(max(0, min(127, v)))
        return self

    def get(self, k):
        return self.block[L["E0"] + eslot(self.engine, k)["slot"]]

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

    def s(self, k):
        return self.block[L[k.upper()]]

    def aeg_on(self):
        return self.block[L["AEG_MODE"]] == 0


class Kit:
    def __init__(self, name, family, flavor, bpm):
        self.name = name[:8]
        self.family = family
        self.flavor = flavor
        self.bpm = bpm
        self.ch = []
        self.fx = {"type": "off", "routing": "st1", "drywet": 50, "p": [64, 64, 64, 64],
                   "dist": 0, "ratio": 3, "wave": 0, "delay": 0}
        self.cv = []   # (ch, slot 0..5, src, amount, dest)
        self.lfo_used = set()
        self.notes = []

    def params(self):
        par = [0] * T["end_of_sound"]
        par[0] = 2   # SH_KIT_VERSION
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
        # CV matrix, 6 slots per channel. Slot 1 = V/Oct and slot 2 = decay,
        # both at amount 0, ready for the CV inputs; slots 3..6 are used for
        # internal movement. Unused slots keep CV1..5 / the channel LFO as
        # source so only destination and amount have to be set.
        for ch in range(6):
            for s in range(6):
                self._slot(par, ch, s, s if s < 5 else 5 + ch, 0, 0)
            self._slot(par, ch, 0, 0, 0, mod_dest(ch, voct=True))
            self._slot(par, ch, 1, 1, 0, mod_dest(ch, "DECAY"))
        for ch, slot, src, amt, dest in self.cv:
            self._slot(par, ch, slot, src, amt, dest)
        return par

    @staticmethod
    def _slot(par, ch, s, src, amt, dest):
        i = ch * 3 + s if s < 3 else 18 + ch * 3 + s - 3
        if i < 18:
            par[P["CV_SRC_1"] + i], par[P["CV_MOD_AMT_1"] + i], par[P["CV_DEST_1"] + i] = src, amt, dest
        else:
            i -= 18
            par[P["CV2_SRC_1"] + i], par[P["CV2_AMT_1"] + i], par[P["CV2_DEST_1"] + i] = src, amt, dest

    def mod(self, ch, src, amount, dest):
        """CV matrix entry in a free internal slot (3..6) of channel ch"""
        used = {c[1] for c in self.cv if c[0] == ch}
        for s in range(2, 6):
            if s not in used:
                self.cv.append((ch, s, src, amount, dest))
                return True
        return False

    def set_lfo(self, ch, wave="rnd", freq=40, retrig=0):
        if ch not in self.lfo_used:
            self.ch[ch].set(lfo_wave=wave, lfo_freq=freq, lfo_retrig=retrig)
            self.lfo_used.add(ch)

    def lfo_mod(self, ch, dest, amount, wave="rnd", freq=40, retrig=0, target_ch=None):
        """LFO of channel ch -> any destination, entered on target_ch (default ch)"""
        self.set_lfo(ch, wave, freq, retrig)
        return self.mod(ch if target_ch is None else target_ch, 5 + ch, amount, dest)

    def lfo_free(self, rng, avoid=()):
        free = [c for c in range(6) if c not in self.lfo_used and c not in avoid]
        return rng.choice(free) if free else None

    def write(self, path):
        name = self.name.ljust(8)[:8].encode("ascii")
        with open(path, "wb") as f:
            f.write(name)
            f.write(bytes(self.params()))


def r(rng, lo, hi):
    return rng.randint(lo, hi)


def pick(rng, *opts):
    return rng.choice(opts)


# =============================================================================
# role recipes, per family. Everything is tuned short and punchy; the check
# after building a kit shortens whatever still rings.
# =============================================================================
# ---- MD style ---------------------------------------------------------------
def md_kick(rng, style):
    if style == "punch":
        return Channel("tBD", r(rng, 31, 36)).p(Swp=r(rng, 50, 72), SwD=r(rng, 18, 32), Dec=r(rng, 30, 48),
                                                Hld=r(rng, 0, 12), Clk=r(rng, 50, 90), Drv=r(rng, 25, 55))
    if style == "click":
        return Channel("tBD", r(rng, 34, 40)).p(Swp=r(rng, 60, 85), SwD=r(rng, 8, 20), Dec=r(rng, 18, 32),
                                                Hld=0, Clk=r(rng, 80, 120), Drv=r(rng, 10, 40))
    if style == "heavy":
        return Channel("tBD", r(rng, 29, 33)).p(Swp=r(rng, 45, 62), SwD=r(rng, 22, 38), Dec=r(rng, 45, 62),
                                                Hld=r(rng, 10, 30), Clk=r(rng, 40, 70), Drv=r(rng, 60, 100)).set(drive=r(rng, 10, 40))
    if style == "efm":
        return Channel("EFM", r(rng, 30, 36)).p(Rat=pick(rng, "1", "0.5"), Mod=r(rng, 25, 55), MDc=r(rng, 10, 25),
                                                FB=r(rng, 0, 25), Swp=r(rng, 55, 85), SwD=r(rng, 15, 30),
                                                Dec=r(rng, 30, 50), Noi=0)
    if style == "gnd":
        return Channel("GND", r(rng, 33, 40)).p(Wav="Sin", Swp=r(rng, 70, 110), SwD=r(rng, 12, 28)).set(
            decay=r(rng, 16, 26), slope=r(rng, 30, 50), drive=r(rng, 20, 50))
    raise ValueError(style)


def md_snare(rng, style):
    if style == "909":
        return Channel("tSD", r(rng, 50, 57)).p(Bdy=r(rng, 60, 95), Snp=r(rng, 85, 120), Dec=r(rng, 22, 38),
                                                NDc=r(rng, 30, 50), Swp=r(rng, 30, 55), NTn=r(rng, 60, 95))
    if style == "tight":
        return Channel("tSD", r(rng, 54, 62)).p(Bdy=r(rng, 40, 70), Snp=r(rng, 100, 127), Dec=r(rng, 12, 24),
                                                NDc=r(rng, 18, 32), Swp=r(rng, 40, 70), NTn=r(rng, 80, 110)).set(drive=r(rng, 10, 40))
    if style == "efm":
        return Channel("EFM", r(rng, 50, 60)).p(Rat=pick(rng, "1.4", "2.7", "3.1", "5.2"), Mod=r(rng, 60, 100),
                                                MDc=r(rng, 15, 30), FB=r(rng, 20, 60), Swp=r(rng, 20, 45),
                                                SwD=r(rng, 15, 30), Dec=r(rng, 20, 35), Noi=r(rng, 70, 115))
    if style == "gnd":
        return Channel("GND", r(rng, 60, 80)).p(Wav="Noi", Swp=r(rng, 40, 80), SwD=r(rng, 10, 25)).set(
            decay=r(rng, 12, 20), slope=r(rng, 20, 40), filt_type="bp", filt_freq=r(rng, 70, 90), filt_reso=r(rng, 10, 40))
    raise ValueError(style)


def md_clap(rng, style):
    if style == "909":
        return Channel("tCP", r(rng, 90, 100)).p(Dec=r(rng, 25, 45), Spc=r(rng, 35, 55), Num=r(rng, 2, 3),
                                                 Q=r(rng, 15, 45), Rnd=r(rng, 15, 40))
    if style == "tight":
        return Channel("tCP", r(rng, 96, 110)).p(Dec=r(rng, 12, 26), Spc=r(rng, 20, 35), Num=r(rng, 1, 3),
                                                 Q=r(rng, 30, 60), Rnd=r(rng, 0, 25))
    if style == "crowd":
        return Channel("tCP", r(rng, 84, 96)).p(Dec=r(rng, 30, 50), Spc=r(rng, 50, 70), Num=r(rng, 4, 6),
                                                Q=r(rng, 10, 30), Rnd=r(rng, 40, 80))
    raise ValueError(style)


def md_perc(rng, style):
    if style == "tom":
        return Channel("tBD", r(rng, 43, 55)).p(Swp=r(rng, 25, 45), SwD=r(rng, 20, 35), Dec=r(rng, 25, 40),
                                                Hld=0, Clk=r(rng, 20, 50), Drv=r(rng, 0, 30))
    if style == "efmwood":
        return Channel("EFM", r(rng, 58, 72)).p(Rat=pick(rng, "2", "3", "4", "5"), Mod=r(rng, 30, 70),
                                                MDc=r(rng, 8, 18), FB=r(rng, 0, 30), Swp=r(rng, 10, 30),
                                                SwD=r(rng, 8, 20), Dec=r(rng, 12, 24), Noi=r(rng, 0, 20))
    if style == "efmmetal":
        return Channel("EFM", r(rng, 55, 70)).p(Rat=pick(rng, "2.7", "3.1", "3.5", "5.2", "7", " 11"), Mod=r(rng, 60, 110),
                                                MDc=r(rng, 10, 25), FB=r(rng, 30, 80), Swp=r(rng, 0, 30),
                                                SwD=r(rng, 10, 25), Dec=r(rng, 12, 26), Noi=r(rng, 0, 40))
    if style == "blip":
        return Channel("GND", r(rng, 55, 80)).p(Wav=pick(rng, "Sqr", "Tri", "Saw", "Imp"), Swp=r(rng, 30, 100),
                                                SwD=r(rng, 6, 20)).set(decay=r(rng, 6, 14), slope=r(rng, 10, 30))
    if style == "rim":
        return Channel("tSD", r(rng, 66, 76)).p(Bdy=r(rng, 90, 127), Snp=r(rng, 0, 30), Dec=r(rng, 5, 12),
                                                NDc=r(rng, 5, 12), Swp=r(rng, 40, 80), NTn=r(rng, 90, 120))
    if style == "shaker":
        return Channel("tHH", r(rng, 70, 84)).p(Ton=r(rng, 40, 70), Dec=r(rng, 16, 30), Mtl=r(rng, 0, 30),
                                                Opn=60, Res=r(rng, 0, 30)).set(attack=r(rng, 8, 20))
    raise ValueError(style)


def md_hats(rng, style):
    if style == "bright":
        return Channel("tHH", r(rng, 78, 92)).p(Ton=r(rng, 60, 90), Dec=r(rng, 8, 20), Mtl=r(rng, 60, 100),
                                                Opn=r(rng, 55, 75), Res=r(rng, 10, 40))
    if style == "dark":
        return Channel("tHH", r(rng, 70, 82)).p(Ton=r(rng, 40, 65), Dec=r(rng, 10, 22), Mtl=r(rng, 30, 70),
                                                Opn=r(rng, 55, 72), Res=r(rng, 0, 25))
    if style == "noise":
        return Channel("tHH", r(rng, 82, 96)).p(Ton=r(rng, 70, 100), Dec=r(rng, 8, 18), Mtl=r(rng, 0, 25),
                                                Opn=r(rng, 50, 70), Res=r(rng, 0, 20))
    raise ValueError(style)


# ---- Plaits -----------------------------------------------------------------
def pl_kick(rng, style):
    if style == "808":
        return Channel("aBD", r(rng, 30, 36)).p(Ton=r(rng, 35, 70), Dec=r(rng, 40, 70), AFM=r(rng, 30, 70),
                                                SFM=r(rng, 20, 50), Drv=r(rng, 20, 60))
    if style == "punch":
        return Channel("aBD", r(rng, 32, 38)).p(Ton=r(rng, 55, 90), Dec=r(rng, 25, 45), AFM=r(rng, 50, 90),
                                                SFM=r(rng, 30, 70), Drv=r(rng, 50, 100))
    if style == "synth":
        return Channel("sBD", r(rng, 31, 38)).p(Ton=r(rng, 45, 85), Dec=r(rng, 30, 55), Drt=r(rng, 20, 60),
                                                FMA=r(rng, 40, 90), FMD=r(rng, 15, 40))
    if style == "dirty":
        return Channel("sBD", r(rng, 29, 35)).p(Ton=r(rng, 60, 100), Dec=r(rng, 35, 60), Drt=r(rng, 70, 115),
                                                FMA=r(rng, 50, 100), FMD=r(rng, 20, 50)).set(drive=r(rng, 30, 60))
    raise ValueError(style)


def pl_snare(rng, style):
    if style == "analog":
        return Channel("aSD", r(rng, 48, 58)).p(Ton=r(rng, 40, 85), Dec=r(rng, 20, 45), Snp=r(rng, 70, 110))
    if style == "synth":
        return Channel("sSD", r(rng, 50, 60)).p(FMA=r(rng, 30, 80), Dec=r(rng, 20, 45), Snp=r(rng, 60, 110))
    if style == "snap":
        return Channel("sSD", r(rng, 56, 66)).p(FMA=r(rng, 10, 40), Dec=r(rng, 12, 28), Snp=r(rng, 100, 127)).set(drive=r(rng, 20, 50))
    raise ValueError(style)


def pl_clap(rng, style):
    # Plaits has no clap: a snappy snare with the strip's clap repeats
    eng = "sSD" if style == "synth" else "aSD"
    c = Channel(eng, r(rng, 62, 74)).set(aeg_mode="ad", attack=r(rng, 2, 6), decay=r(rng, 16, 26),
                                          slope=r(rng, 20, 35), repeat=r(rng, 2, 4))
    if eng == "aSD":
        c.p(Ton=r(rng, 10, 40), Dec=r(rng, 30, 50), Snp=127)
    else:
        c.p(FMA=r(rng, 0, 20), Dec=r(rng, 30, 50), Snp=127)
    return c.set(filt_type="bp", filt_freq=r(rng, 72, 92), filt_reso=r(rng, 10, 35))


def pl_perc(rng, style):
    if style == "tom":
        return Channel("aBD", r(rng, 43, 55)).p(Ton=r(rng, 40, 80), Dec=r(rng, 30, 50), AFM=r(rng, 10, 40),
                                                SFM=r(rng, 0, 20), Drv=r(rng, 0, 30))
    if style == "wood":
        return Channel("Mdl", r(rng, 60, 74)).p(Str=r(rng, 0, 25), Bri=r(rng, 40, 75), Dmp=r(rng, 10, 30), Exc=r(rng, 30, 70))
    if style == "rim":
        return Channel("Mdl", r(rng, 66, 78)).p(Str=r(rng, 10, 35), Bri=r(rng, 70, 105), Dmp=r(rng, 8, 25), Exc=r(rng, 40, 80))
    if style == "metal":
        return Channel("Mdl", r(rng, 58, 72)).p(Str=r(rng, 80, 120), Bri=r(rng, 60, 95), Dmp=r(rng, 20, 40),
                                                Exc=r(rng, 0, 30)).set(aeg_mode="ad", decay=r(rng, 10, 18), slope=20)
    if style == "pluck":
        return Channel("Str", r(rng, 43, 60)).p(Str=r(rng, 30, 80), Bri=r(rng, 40, 85), Dmp=r(rng, 15, 40),
                                                Exc=r(rng, 0, 30)).set(aeg_mode="ad", decay=r(rng, 12, 22), slope=25)
    if style == "particle":
        return Channel("Prt", r(rng, 66, 90)).p(Den=r(rng, 40, 90), Res=r(rng, 40, 90), Spr=r(rng, 20, 70)).set(
            decay=r(rng, 8, 18), slope=20)
    raise ValueError(style)


def pl_hats(rng, style):
    if style == "808":
        return Channel("pHH", r(rng, 66, 80)).p(Ton=r(rng, 50, 90), Dec=r(rng, 10, 25), Noi=r(rng, 30, 70),
                                                Typ="808", Opn=r(rng, 55, 75))
    if style == "ring":
        return Channel("pHH", r(rng, 70, 84)).p(Ton=r(rng, 60, 100), Dec=r(rng, 8, 22), Noi=r(rng, 30, 70),
                                                Typ="Rng", Opn=r(rng, 55, 72))
    raise ValueError(style)


# ---- IDM / glitch -----------------------------------------------------------
def id_kick(rng, style):
    if style == "zap":
        return Channel("Zap", r(rng, 26, 33)).p(Dep=r(rng, 60, 95), Tim=r(rng, 10, 25), FB=r(rng, 0, 30),
                                                Dec=r(rng, 30, 50), Dir="Dwn").set(drive=r(rng, 20, 60))
    if style == "crush":
        return Channel("Crs", r(rng, 30, 38)).p(Src=pick(rng, "Sqr", "FM"), Rat=r(rng, 80, 120), Bit=r(rng, 10, 50),
                                                Jit=0, Dec=r(rng, 25, 45), Glt=0).set(
            aeg_mode="ad", decay=r(rng, 18, 28), slope=r(rng, 30, 50), filt_type="lp", filt_freq=r(rng, 50, 75))
    if style == "byte":
        return Channel("Byt", r(rng, 24, 34)).p(Frm=r(rng, 0, 7), A=r(rng, 0, 40), B=r(rng, 0, 40), Rst=1).set(
            decay=r(rng, 14, 24), slope=r(rng, 40, 60), filt_type="lp", filt_freq=r(rng, 40, 62), filt_reso=r(rng, 20, 50),
            drive=r(rng, 20, 60))
    if style == "fmthud":
        return Channel("Crs", r(rng, 26, 34)).p(Src="FM", Rat=r(rng, 90, 127), Bit=r(rng, 0, 30), Jit=r(rng, 0, 20),
                                                Dec=r(rng, 30, 50), Glt=0).set(
            aeg_mode="ad", decay=r(rng, 16, 26), slope=r(rng, 35, 55), filt_type="lp", filt_freq=r(rng, 45, 68),
            filt_reso=r(rng, 30, 70), drive=r(rng, 30, 80))
    raise ValueError(style)


def id_snare(rng, style):
    if style == "noise":
        return Channel("Crs", r(rng, 55, 72)).p(Src="Noi", Rat=r(rng, 30, 70), Bit=r(rng, 40, 90),
                                               Jit=r(rng, 0, 40), Dec=r(rng, 25, 45), Glt=r(rng, 0, 20))
    if style == "comb":
        return Channel("Cmb", r(rng, 50, 62)).p(Exc="Noi", FB=r(rng, 100, 116), Dmp=r(rng, 40, 80), Bur=r(rng, 30, 70),
                                               Rat=r(rng, 0, 127), Mx2=r(rng, 20, 60)).set(decay=r(rng, 14, 24))
    if style == "zap":
        return Channel("Zap", r(rng, 48, 60)).p(Dep=r(rng, 40, 80), Tim=r(rng, 5, 20), FB=r(rng, 60, 110),
                                                Dec=r(rng, 20, 35), Dir="Dwn").set(filt_type="hp", filt_freq=r(rng, 40, 60))
    if style == "byte":
        return Channel("Byt", r(rng, 50, 70)).p(Frm=r(rng, 0, 7), A=r(rng, 40, 127), B=r(rng, 40, 127), Rst=1).set(
            decay=r(rng, 10, 18), slope=20, filt_type="bp", filt_freq=r(rng, 65, 90), filt_reso=r(rng, 10, 40),
            bits=r(rng, 30, 80))
    if style == "shred":
        return Channel("Crs", r(rng, 50, 70)).p(Src=pick(rng, "Noi", "Saw"), Rat=r(rng, 10, 60), Bit=r(rng, 80, 127),
                                                Jit=r(rng, 60, 127), Dec=r(rng, 25, 40), Glt=r(rng, 40, 110)).set(
            repeat=r(rng, 0, 3), attack=r(rng, 0, 4))
    raise ValueError(style)


def id_clap(rng, style):
    if style == "crush":
        return Channel("Crs", r(rng, 70, 90)).p(Src="Noi", Rat=r(rng, 40, 90), Bit=r(rng, 50, 100), Jit=r(rng, 20, 60),
                                               Dec=r(rng, 30, 50), Glt=0).set(
            aeg_mode="ad", attack=r(rng, 2, 6), decay=r(rng, 16, 26), repeat=r(rng, 2, 5),
            filt_type="bp", filt_freq=r(rng, 72, 92), filt_reso=r(rng, 10, 40))
    if style == "comb":
        return Channel("Cmb", r(rng, 60, 80)).p(Exc="Clk", FB=r(rng, 96, 112), Dmp=r(rng, 50, 90), Bur=r(rng, 40, 80),
                                               Rat=r(rng, 40, 127), Mx2=r(rng, 40, 80)).set(decay=r(rng, 14, 22), repeat=r(rng, 2, 4))
    if style == "spray":
        return Channel("Crs", r(rng, 72, 96)).p(Src="Noi", Rat=r(rng, 0, 40), Bit=r(rng, 60, 120), Jit=r(rng, 40, 127),
                                               Dec=r(rng, 30, 50), Glt=r(rng, 30, 90)).set(
            aeg_mode="ad", attack=r(rng, 1, 4), decay=r(rng, 14, 24), repeat=r(rng, 4, 9),
            filt_type="hp", filt_freq=r(rng, 55, 80))
    raise ValueError(style)


def id_perc(rng, style):
    if style == "byte":
        return Channel("Byt", r(rng, 46, 70)).p(Frm=r(rng, 0, 7), A=r(rng, 0, 127), B=r(rng, 0, 127),
                                                Rst=1).set(decay=r(rng, 6, 16), slope=r(rng, 10, 30))
    if style == "comb":
        # FB is bipolar (64 = none); below 64 the comb sounds hollow
        return Channel("Cmb", r(rng, 38, 60)).p(Exc=pick(rng, "Imp", "Clk"), FB=pick(rng, r(rng, 104, 120), r(rng, 8, 24)),
                                                Dmp=r(rng, 30, 80), Bur=r(rng, 5, 30), Rat=r(rng, 0, 127),
                                                Mx2=r(rng, 20, 80)).set(decay=r(rng, 12, 22))
    if style == "zap":
        return Channel("Zap", r(rng, 40, 58)).p(Dep=r(rng, 60, 110), Tim=r(rng, 8, 30), FB=r(rng, 0, 60),
                                                Dec=r(rng, 15, 30), Dir=pick(rng, "Dwn", "Up", "Bth"))
    if style == "glitch":
        return Channel("Crs", r(rng, 44, 76)).p(Src=pick(rng, "Sqr", "Saw", "FM"), Rat=r(rng, 40, 100),
                                                Bit=r(rng, 70, 120), Jit=r(rng, 30, 100), Dec=r(rng, 12, 28), Glt=r(rng, 30, 100))
    if style == "metal":
        return Channel("Rng", r(rng, 56, 72)).p(Spr=r(rng, 70, 127), RM=r(rng, 70, 127), Ton=r(rng, 60, 95),
                                                Res=r(rng, 10, 40), Wav=pick(rng, "Sqr", "Sin")).set(decay=r(rng, 8, 16), slope=25)
    if style == "cowbell":
        return Channel("Rng", r(rng, 66, 74)).p(Spr=r(rng, 0, 20), RM=r(rng, 0, 30), Ton=r(rng, 60, 85),
                                                Res=r(rng, 30, 60), Wav="Sqr").set(decay=r(rng, 8, 14), slope=25)
    if style == "blip":
        return Channel("Zap", r(rng, 60, 84)).p(Dep=r(rng, 20, 60), Tim=r(rng, 2, 10), FB=r(rng, 0, 40),
                                                Dec=r(rng, 6, 14), Dir=pick(rng, "Up", "Dwn")).set(bits=r(rng, 0, 70))
    if style == "laser":
        return Channel("Zap", r(rng, 56, 76)).p(Dep=r(rng, 80, 127), Tim=r(rng, 15, 35), FB=r(rng, 40, 100),
                                                Dec=r(rng, 14, 26), Dir=pick(rng, "Dwn", "Bth"))
    raise ValueError(style)


def id_hats(rng, style):
    if style == "crush":
        return Channel("Crs", r(rng, 84, 100)).p(Src="Noi", Rat=r(rng, 5, 35), Bit=r(rng, 40, 100), Jit=r(rng, 10, 50),
                                                Dec=100, Glt=r(rng, 0, 30)).set(
            aeg_mode="ad", decay=r(rng, 3, 7), decay_alt=r(rng, 18, 28), slope=20, filt_type="hp", filt_freq=r(rng, 70, 90))
    if style == "ring":
        return Channel("Rng", r(rng, 84, 100)).p(Spr=r(rng, 90, 127), RM=r(rng, 90, 127), Ton=r(rng, 90, 120),
                                                Res=r(rng, 0, 20), Wav="Sqr").set(
            decay=r(rng, 3, 7), decay_alt=r(rng, 16, 26), slope=20, filt_type="hp", filt_freq=r(rng, 72, 92))
    if style == "bytehat":
        return Channel("Byt", r(rng, 90, 110)).p(Frm=r(rng, 0, 7), A=r(rng, 60, 127), B=r(rng, 60, 127), Rst=1).set(
            decay=r(rng, 2, 5), decay_alt=r(rng, 14, 22), slope=15, filt_type="hp", filt_freq=r(rng, 78, 96))
    raise ValueError(style)


ROLES = {
    "MD": dict(kick=(md_kick, ["punch", "click", "heavy", "efm", "gnd"]),
               snare=(md_snare, ["909", "tight", "efm", "gnd"]),
               clap=(md_clap, ["909", "tight", "crowd"]),
               perc4=(md_perc, ["tom", "efmwood", "blip", "rim"]),
               perc5=(md_perc, ["efmmetal", "blip", "rim", "shaker", "efmwood"]),
               hats=(md_hats, ["bright", "dark", "noise"])),
    "PL": dict(kick=(pl_kick, ["808", "punch", "synth", "dirty"]),
               snare=(pl_snare, ["analog", "synth", "snap"]),
               clap=(pl_clap, ["analog", "synth"]),
               perc4=(pl_perc, ["tom", "wood", "rim", "pluck"]),
               perc5=(pl_perc, ["metal", "particle", "rim", "wood", "pluck"]),
               hats=(pl_hats, ["808", "ring"])),
    "ID": dict(kick=(id_kick, ["zap", "crush", "byte", "zap", "fmthud"]),
               snare=(id_snare, ["noise", "comb", "zap", "byte", "shred"]),
               clap=(id_clap, ["crush", "comb", "spray"]),
               perc4=(id_perc, ["byte", "comb", "zap", "cowbell", "glitch", "blip"]),
               perc5=(id_perc, ["glitch", "metal", "byte", "comb", "zap", "blip", "laser"]),
               hats=(id_hats, ["crush", "ring", "bytehat"])),
}
ROLE_ORDER = ["kick", "perc4", "perc5", "snare", "clap", "hats"]   # = channels 1..6


def make_role(rng, family, role):
    fn, styles = ROLES[family][role]
    return fn(rng, rng.choice(styles))


# =============================================================================
# flavors: tempo, pattern and FX character; spread over every family
# =============================================================================
FLAVORS = ["drive", "electro", "broken", "space", "metal", "breaks", "tight", "warp"]
ID_FLAVORS = ["broken", "chaos", "warp", "micro", "broken", "chaos", "drive", "micro"]
BPM = {"drive": (128, 138), "electro": (122, 134), "broken": (140, 170), "space": (118, 128),
       "metal": (120, 134), "breaks": (164, 176), "tight": (124, 132), "warp": (130, 150),
       "chaos": (150, 180), "micro": (100, 124)}
PATTERNS = {   # kick, perc/tom, fx, snare, clap, hats ('o' = open hat via trigger 7, 'r' = ratchet)
    "drive":   ["X...X...X...X...", "..x...x...x..xx.", "x.x.x.x.x.x.x.x.", "...x.......x..x.", "....x.......x...", "..o...o...o...o."],
    "electro": ["X..x..x...X..x..", "......x.....x.x.", "..x.......x....x", "....X.......X...", "....x.......x..x", "xxxoxxxxxxxoxxxx"],
    "broken":  ["X..x.r....X.x...", "..x.x....x.xr...", "r..x..x.x...x..r", "....X..x...rX...", "......x.......x.", "xx.xxrx.xo.xxrxo"],
    "space":   ["X...X...X...X...", "..x.....x..x....", "...x..x....x..x.", "............x...", "....x.......x...", "x.x.x.x.x.x.x.xo"],
    "metal":   ["X..xX...X..xX...", "x...x.x.x...x.x.", "..x...x...x...x.", "....X.......X...", "....x.......x...", "xxoxxxoxxxoxxxox"],
    "breaks":  ["X.........X.....", "..x..x....x..x..", ".......x.x....x.", "....X.......X...", "......x.......x.", "x.xxx.xxx.xxxox."],
    "tight":   ["X...X...X...X..x", "..x...x..x...x..", ".x...x...x...x..", "....X.......X...", "....x.......x...", "xxxxxxxxxxxxxxxo"],
    "warp":    ["X..x...x..X..x..", "x.x..xr..x..x.x.", "..r...x...r...x.", "....X.....x.X...", "...x.......x....", "x.xox.xxx.xox.xx"],
    "chaos":   ["X.r..x.X..rx..x.", "rx.x.rx..xr.x.rx", "x.rr.x.xr..rx.r.", "..x.X.r...xX.r..", ".r...x..r.x...xr", "rxxoxrxrxoxrxxrr"],
    "micro":   ["X.....x...X..x..", ".x..x.x..x..xr..", "x.r..x...rx..x..", "....x..x....X..r", "..x.....r.....x.", "x.xxrxx.xxrox.xr"],
}


def drive_fx(rng, hard=False):
    """LXR distortion: P1 drive, P2 colour (tube) / offset (fold) / feedback
    (clip), P3 tone, P4 level. Fold offset and clip feedback stay 0: the
    offset is a DC shift and the RAT feedback self-oscillates."""
    dist = rng.choice([0, 1, 2]) if hard else rng.choice([0, 0, 1, 2])
    drive = r(rng, 55, 110) if hard else r(rng, 30, 80)
    p2 = r(rng, 20, 90) if dist == 0 else 0
    return dict(dist=dist, p=[drive, p2, r(rng, 35, 85), r(rng, 55, 85)])


def setup_fx(rng, kit):
    """FX bus: type, which channels go through it, and LFO movement on it"""
    fl = kit.flavor
    weights = {
        "drive":   {"drv": 3, "cmp": 2, "del": 2, "glt": 2},
        "electro": {"del": 3, "glt": 2, "drv": 1, "cmp": 1},
        "broken":  {"glt": 4, "del": 2, "drv": 2},
        "space":   {"del": 5, "glt": 1},
        "metal":   {"drv": 5, "glt": 2, "cmp": 1},
        "breaks":  {"cmp": 3, "drv": 2, "glt": 2, "del": 1},
        "tight":   {"cmp": 3, "drv": 2, "del": 2, "glt": 1},
        "warp":    {"del": 3, "glt": 3, "drv": 2},
        "chaos":   {"glt": 6, "drv": 2, "del": 1},
        "micro":   {"glt": 3, "del": 3, "drv": 1},
    }[fl]
    types = list(weights)
    t = rng.choices(types, [weights[x] for x in types])[0]
    f = kit.fx
    f["type"] = t
    if t == "del":
        # short to medium times, feedback below runaway, darker repeats
        f.update(drywet=r(rng, 25, 55), delay=rng.choice([0, 1, 1]),
                 p=[r(rng, 40, 110), r(rng, 40, 110), r(rng, 20, 65), r(rng, 30, 70)])
        sends = rng.sample([1, 2, 3, 4], r(rng, 1, 3))
    elif t == "drv":
        f.update(drywet=r(rng, 50, 100), **drive_fx(rng, hard=fl in ("metal", "drive")))
        sends = rng.sample([0, 1, 2, 3, 4], r(rng, 2, 4))
    elif t == "glt":
        # beat repeat on the hits of the channels that go through it:
        # P1 slice length, P2 chance per hit, P3 variety, P4 repeats
        wild = fl in ("chaos", "broken", "micro")
        f.update(drywet=r(rng, 80, 100), p=[r(rng, 20, 95), r(rng, 45, 110) if wild else r(rng, 25, 70),
                                            r(rng, 50, 127) if wild else r(rng, 10, 80), r(rng, 15, 90)])
        sends = rng.sample([1, 2, 3, 4, 5], r(rng, 2, 4))
    else:  # cmp: glue on the drums, with a bit of pump
        # slow-ish attack lets the transients through: punch, not squash
        f.update(drywet=100, ratio=r(rng, 2, 5), p=[r(rng, 25, 60), r(rng, 15, 50), r(rng, 55, 90), r(rng, 40, 70)])
        sends = [0, 3, 4] + rng.sample([1, 2], r(rng, 0, 2))
    for c in sends:
        kit.ch[c].set(out="fx")

    # movement on the FX bus from a free channel LFO (the new global targets)
    if t != "cmp" and rng.random() < 0.75:
        ch = kit.lfo_free(rng)
        if ch is not None:
            if t == "del":
                dest, amt = rng.choice([("fx3", r(rng, 20, 45)), ("fx1", r(rng, 3, 10)), ("fwt", r(rng, 20, 40)),
                                        ("fx4", r(rng, 10, 25))])
            elif t == "drv":
                dest, amt = rng.choice([("fx1", r(rng, 20, 45)), ("fx3", r(rng, 25, 50))])
            else:
                dest, amt = rng.choice([("fx1", r(rng, 20, 50)), ("fx2", r(rng, 20, 50)), ("fx3", r(rng, 30, 60))])
            wave = rng.choice(["tri", "sin", "rnd", "sdn", "sqr"])
            retrig = rng.choice([0, 0, 1, 2])
            kit.lfo_mod(ch, GLOBAL[dest], amt, wave=wave, freq=r(rng, 12, 45), retrig=retrig)
            kit.notes.append(f"lf{ch + 1}->{dest}")


def setup_movement(rng, kit):
    """channel movement: bit/sample rate damage, ratchets, LFOs, accents"""
    fl = kit.flavor
    wild = kit.family == "ID"
    if fl in ("broken", "warp", "chaos", "micro") or (wild and rng.random() < 0.8):
        for c in rng.sample(range(6), 3 if wild else 2):
            kit.ch[c].set(bits=r(rng, 40, 100 if wild else 90))
        for c in rng.sample(range(1, 6), 2 if wild else 1):
            kit.ch[c].set(srate=r(rng, 50 if wild else 60, 105))
    if fl in ("broken", "warp", "chaos") and rng.random() < (0.9 if wild else 0.6):
        for c in rng.sample(range(2, 6), 2 if wild else 1):
            kit.ch[c].set(repeat=r(rng, 2, 8 if wild else 5), attack=r(rng, 1, 8))

    targets = ["BITS", "FILT_FREQ", "DECAY", "PAN", "SRATE", "DRIVE", "TUNE"]
    n = r(rng, 3, 5) if wild else (2 if fl in ("broken", "warp") else r(rng, 1, 2))
    for _ in range(n):
        c = rng.randrange(1, 6) if rng.random() < 0.8 else 0
        kind = rng.random()
        src_ch = c if rng.random() < 0.6 else rng.randrange(6)     # sometimes another channel's LFO
        if kind < 0.45:
            # LFO on one of the engine's own parameters
            prm = [p for p in ENG[kit.ch[c].engine]["params"] if p["type"] in (1, 2) and p["slot"] < 14]
            if not prm:
                continue
            d = rng.choice(prm)
            dest = mod_dest(c, engine_slot=d["slot"])
            fast = wild and rng.random() < 0.35
            kit.lfo_mod(src_ch, dest, r(rng, 15, 50 if wild else 35),
                        wave=rng.choice(["rnd", "sqr", "tri", "sin", "xdn"]),
                        freq=r(rng, 70, 95) if fast else r(rng, 25, 65), target_ch=c)
        elif kind < 0.65 and wild:
            # random pitch steps (sample and hold LFO on V/Oct)
            kit.lfo_mod(src_ch, mod_dest(c, voct=True), r(rng, 8, 25), wave="rnd", freq=r(rng, 30, 60), target_ch=c)
        elif kind < 0.8:
            # accent of the channel itself pushes a parameter
            t = rng.choice(["DECAY", "FILT_FREQ", "BITS", "DRIVE"])
            if t == "DECAY" and (not kit.ch[c].aeg_on() or c == 5):
                t = "DRIVE"
            kit.mod(c, 11 + c, r(rng, 20, 50), mod_dest(c, t))
        else:
            t = rng.choice(targets[:-1])
            if t == "FILT_FREQ":
                kit.ch[c].set(filt_type=rng.choice(["lp", "bp", "hp"]), filt_freq=r(rng, 55, 90), filt_reso=r(rng, 20, 60))
            if t == "DECAY" and (not kit.ch[c].aeg_on() or c == 5):
                t = "PAN"
            kit.lfo_mod(src_ch, mod_dest(c, t), r(rng, 15, 45), wave=rng.choice(["rnd", "sqr", "xdn", "tri", "sin"]),
                        freq=r(rng, 25, 65), target_ch=c)
    if fl == "metal":
        kit.ch[0].set(drive=max(kit.ch[0].s("drive"), r(rng, 20, 60)))
        kit.ch[3].set(drive=max(kit.ch[3].s("drive"), r(rng, 30, 70)))


# =============================================================================
# kits per family
# =============================================================================
NAMES = {
    "MD": ["Anvil", "Bolt", "Crank", "Diode", "Gauge", "Hertz", "Ingot", "Joule", "Kiln", "Lathe",
           "Motor", "Nitro", "Ohm", "Piston", "Quartz", "Rivet", "Servo", "Torque", "Unit", "Valve",
           "Watt", "Xenon", "Yoke", "Zinc", "Alloy", "Brass", "Coil", "Drill", "Edge", "Flint",
           "Grid", "Hinge"],
    "PL": ["Glass", "Reed", "Tide", "Moss", "Flare", "Prism", "Wave", "Fern", "Opal", "Drift",
           "Pulse", "Grain", "Shell", "Bloom", "Mist", "Ripple", "Chime", "Stone", "Ember", "Frost",
           "Petal", "Silk", "Rain", "Dune", "Lumen", "Spore", "Coral", "Pine", "Haze", "Bead",
           "Wisp", "Mica"],
    "ID": ["Glitch", "Shard", "Splint", "Fract", "Corrupt", "Pixel", "Micro", "Nerve", "Shrap", "Melt",
           "Bleep", "Wires", "Ctrl", "Chip", "Ether", "Dust", "Sprng", "Skwee", "Brkcr", "Spike",
           "Static", "Byte", "Loop", "Stutter", "Hash", "Null", "Parse", "Fault", "Jitter", "Alias",
           "Bitrot", "Hex", "Rupture", "Vortex", "Fizz", "Mangle", "Scrape", "Swarm", "Twitch", "Warble",
           "Crackle", "Datamosh", "Overflow", "Tangle", "Smear", "Kink", "Flux", "Zigzag"],
    "HY": ["Hybrid", "Mutant", "Splice", "Chimera", "Fusion", "Blend", "Cross", "Graft", "Weave", "Mosaic",
           "Patch", "Remix", "Morph", "Collage", "Bridge", "Union"],
}


def build_kit(rng, family, i):
    flavor = (ID_FLAVORS if family == "ID" else FLAVORS)[i % len(FLAVORS)]
    bpm = r(rng, *BPM[flavor])
    name = (family + NAMES[family][i])[:8]
    kit = Kit(name, family, flavor, bpm)
    if family == "HY":
        fams = ["MD", "PL", "ID"]
        kit.ch = [make_role(rng, rng.choice(fams), role) for role in ROLE_ORDER]
    else:
        # up to two guest channels from other families, never the kick
        guests = set(rng.sample([1, 2, 3, 4, 5], rng.choice([0, 1, 1, 2, 2])))
        others = [f for f in ("MD", "PL", "ID") if f != family]
        kit.ch = [make_role(rng, rng.choice(others) if k in guests else family, role)
                  for k, role in enumerate(ROLE_ORDER)]
    # stereo picture
    kit.ch[1].set(pan=r(rng, 36, 56))
    kit.ch[2].set(pan=r(rng, 72, 92))
    kit.ch[5].set(pan=r(rng, 54, 74))
    setup_movement(rng, kit)
    setup_fx(rng, kit)
    return kit


# =============================================================================
# checks: shorten what rings, whistles or hangs
# =============================================================================
#          kick  perc4 perc5 snare clap  hats  open
RING_MAX = [0.55, 0.45, 0.45, 0.40, 0.45, 0.14, 0.60]
HF_MAX = [0.10, 0.32, 0.32, 0.32, 0.38, 0.14, 0.55]
RING_MIN = [0.18, 0.04, 0.03, 0.09, 0.06, 0.02, 0.12]
TONE_LEVEL = -42.0      # dB re peak, narrow peak above 1.5 kHz after 150 ms
TONE_PROM = 18.0

DECAY_PARAMS = ["Dec", "NDc", "SwD", "MDc"]


def problems(m):
    bad = []
    for k in range(7):
        c = m[k]
        if c["peak"] < 1e-4:
            continue
        why = []
        if c["ring"] > RING_MAX[k]:
            why.append(f"ring {c['ring']:.2f}")
        elif c["ring"] < RING_MIN[k]:
            why.append(f"short {c['ring']:.2f}")
        if c["hf"] > HF_MAX[k]:
            why.append(f"hf {c['hf']:.2f}")
        f, lvl, prom = c["tone"]
        if k < 6 and lvl > TONE_LEVEL and prom > TONE_PROM:
            why.append(f"tone {f:.0f}Hz {lvl:.0f}dB")
        if why:
            bad.append((k, why))
    return bad


def shorten(c, alt, attempt):
    """make one channel shorter; later attempts use the amp EG as a gate"""
    e = c.engine
    if alt:
        if has(e, "Opn"):
            c.p(Opn=int(c.get("Opn") * 0.8))
        if c.aeg_on():
            c.set(decay_alt=max(4, int(c.s("decay_alt") * 0.8)))
        else:
            c.set(aeg_mode="ad", attack=0, decay=40, decay_alt=26, slope=20)
        return
    if attempt >= 3:
        # gate with the amp EG
        if not c.aeg_on():
            c.set(aeg_mode="ad", attack=0, decay=24, slope=25)
        else:
            c.set(decay=max(3, int(c.s("decay") * 0.75)))
        return
    if c.aeg_on():
        c.set(decay=max(3, int(c.s("decay") * 0.8)))
    for k in DECAY_PARAMS:
        if has(e, k):
            c.p(**{k: int(c.get(k) * 0.8)})
    if e in ("Mdl", "Str"):
        c.p(Dmp=min(127, c.get("Dmp") + 12))
    if e == "Cmb":
        c.p(FB=int(64 + (c.get("FB") - 64) * 0.9))
    if e == "Zap":
        c.p(FB=int(c.get("FB") * 0.8))


def lengthen(c, alt):
    e = c.engine
    if alt:
        if has(e, "Opn"):
            c.p(Opn=min(127, int(c.get("Opn") * 1.15) + 2))
        if c.aeg_on():
            c.set(decay_alt=min(127, int(c.s("decay_alt") * 1.25) + 2))
            if has(e, "Dec"):
                c.p(Dec=min(127, int(c.get("Dec") * 1.15) + 3))
        return
    if c.aeg_on():
        c.set(decay=min(127, int(c.s("decay") * 1.25) + 2))
    for k in ("Dec", "NDc"):
        if has(e, k):
            c.p(**{k: min(127, int(c.get(k) * 1.25) + 3)})
    if e in ("Mdl", "Str"):
        c.p(Dmp=max(0, c.get("Dmp") - 8))
    if e == "Cmb":
        c.p(FB=int(max(2, min(125, 64 + (c.get("FB") - 64) * 1.08))))


def fix_kit(kit, path, log):
    for attempt in range(8):
        kit.write(path)
        bad = problems(analyse(RENDER, path))
        if not bad:
            return attempt
        for k, why in bad:
            if attempt == 0 or attempt == 7:
                log.append(f"  {kit.name} ch{k + 1 if k < 6 else '6o'}: {', '.join(why)}")
            if attempt >= 2 and not why[0].startswith("short"):
                # internal modulation can stretch a sound (LFO on decay etc.):
                # take it away from a channel that keeps failing
                ch = min(k, 5)
                before = len(kit.cv)
                kit.cv = [e for e in kit.cv if not (e[4] >= MCB and (e[4] - MCB) // MTPC == ch)]
                if len(kit.cv) != before:
                    continue
            if why[0].startswith("short"):
                lengthen(kit.ch[min(k, 5)], k == 6)
            else:
                shorten(kit.ch[min(k, 5)], k == 6, attempt)
    return -1


# =============================================================================
TARGET_PEAK = [0.85, 0.48, 0.42, 0.60, 0.52, 0.32]


def render(kit, path_snd, wav=""):
    pat = os.path.join(WORK, f"pat_{kit.flavor}.txt")
    with open(pat, "w") as f:
        f.write("\n".join(PATTERNS[kit.flavor]) + "\n")
    met = os.path.join(WORK, "metrics.json")
    kit.write(path_snd)
    subprocess.run([RENDER, "--kit", path_snd, pat, str(kit.bpm), "2", wav, met], check=True)
    return json.load(open(met))


def file_name(slot, name):
    clean = "".join(c if c.isalnum() else "_" for c in name)
    return f"{slot:02d}-{clean[:5]}.snd" if slot < 100 else f"{slot:03d}-{clean[:4]}.snd"


GROUPS = [("MD", 32), ("PL", 32), ("ID", 48), ("HY", 16)]


def family_count(kit):
    fams = {f: sum(c.engine in FAMILY[f] for c in kit.ch) for f in FAMILY}
    return fams


def main():
    kit_dir = os.path.join(OUT, "shard", "prj00")
    demo_dir = os.path.join(OUT, "demo")
    os.makedirs(kit_dir, exist_ok=True)
    os.makedirs(demo_dir, exist_ok=True)
    for f in os.listdir(kit_dir):
        os.unlink(os.path.join(kit_dir, f))
    only = set(int(x) for x in os.environ.get("ONLY", "").split(",") if x)
    slot = 0
    report, log = [], []
    for family, count in GROUPS:
        for i in range(count):
            if only and slot not in only:
                slot += 1
                continue
            rng = random.Random(f"shard3-{family}-{i}")
            kit = build_kit(rng, family, i)
            if family != "HY":
                assert family_count(kit)[family] >= 4, kit.name
            path = os.path.join(kit_dir, file_name(slot, kit.name))
            fixed = fix_kit(kit, path, log)
            # gain staging on the channel volumes; quiet engines that are
            # already at full volume get some channel drive as make-up gain
            for _ in range(4):
                m = render(kit, path)
                for c in range(6):
                    pk = m["peak"][c]
                    vol = kit.ch[c].s("vol")
                    if pk < 1e-4:
                        continue
                    new = int(round(vol * TARGET_PEAK[c] / pk))
                    if new > 127 and pk < 0.75 * TARGET_PEAK[c]:
                        kit.ch[c].set(drive=min(90, kit.ch[c].s("drive") + 25))
                    kit.ch[c].set(vol=max(20, min(127, new)))
            # output stage: no clipping on the outputs, peaks around -1 dB;
            # the compressor / distortion level makes up for what the FX eats
            for _ in range(8):
                m = render(kit, path)
                op, clip = m["out_peak"], m["clip"]
                if clip > 0 or op > 0.97:
                    scale = (0.85 if clip > 20 else 0.92) * min(1.0, 0.95 / op)
                elif op < 0.78:
                    if kit.fx["type"] in ("cmp", "drv") and kit.fx["p"][3] < 127:
                        kit.fx["p"][3] = min(127, kit.fx["p"][3] + 15)
                    scale = min(0.9 / max(op, 1e-3), 1.4)
                else:
                    break
                for c in kit.ch:
                    c.set(vol=max(10, min(127, int(round(c.s("vol") * scale)))))
            wav = os.path.join(demo_dir, f"{slot:03d}_{kit.name}.wav") if i % 4 == 0 else ""
            m = render(kit, path, wav)
            fam = family_count(kit)
            report.append(dict(slot=slot, name=kit.name, family=family, flavor=kit.flavor, bpm=kit.bpm,
                               engines=[c.engine for c in kit.ch], fx=kit.fx["type"], mix=m["out_peak"], clip=m["clip"],
                               tail=m["tail"], peaks=[round(x, 2) for x in m["peak"]], fixed=fixed,
                               notes=kit.notes, fam=fam))
            print(f"{slot:3d} {kit.name:8s} {family} {kit.flavor:7s} {' '.join(c.engine for c in kit.ch)} "
                  f"fx={kit.fx['type']} fix={fixed} out={m['out_peak']:.2f} clip={m['clip']} tail={m['tail']:.4f}", flush=True)
            slot += 1
    with open(os.path.join(OUT, "bank.txt"), "w") as f:
        for k in report:
            f.write(f"{k['slot']:3d} {k['name']:8s} {k['family']} {k['flavor']:7s} {k['bpm']:3d}bpm  "
                    f"{' '.join(f'{e:3s}' for e in k['engines'])}  fx={k['fx']:3s} {' '.join(k['notes'])}  "
                    f"out={k['mix']:.2f} clip={k['clip']} tail={k['tail']:.4f} fix={k['fixed']} peaks={k['peaks']}\n")
    with open(os.path.join(OUT, "bank.json"), "w") as f:
        json.dump(report, f, indent=1)
    with open(os.path.join(OUT, "fixlog.txt"), "w") as f:
        f.write("\n".join(log) + "\n")
    print(f"{len(report)} kits written to {kit_dir}")


main()
