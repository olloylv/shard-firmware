#!/usr/bin/env python3
"""Build the SHARD factory kit bank.

    python3 tools/kits/make_kits.py <shard_render> <out dir>

Writes <out dir>/shard/prj00/NNN-NAME.snd (the module's kit files),
<out dir>/bank.json, fixlog.txt and demo WAVs in <out dir>/demo.
The kit list BANK.txt is written from bank.json by bank_txt.py.

How the bank is made
--------------------
1. Voice pools. For every engine family and channel role there is a set of
   hand designed archetypes (parameters given in seconds, semitones and Hz and
   converted to the engine's 0..127 values). Each archetype is rendered many
   times with random variation inside its ranges. Every candidate is rendered
   as a single hit and measured (tools/kits/analyse.py): length, high
   frequency tail, sustained high tones, band energies, centroid, attack,
   loudness, pitch. A role specific score keeps the candidates that sit where
   that role belongs in a mix (a kick that is mostly sub and low with a fast
   attack, hats above 5 kHz with nothing in the low mids, ...). Then the best
   diverse ones form the pool.
2. Kits. A kit takes its voices from the pool of its family (up to two guests
   from other families), gets a theme (tempo, groove, FX and how much it moves),
   a key: pitched voices are retuned to notes of the key, and a mix: single
   hit loudness per role, high pass cleanup of everything but the kick, a
   stereo picture, tasteful internal modulation (S&H, accents, LFOs on the FX
   bus) and the FX bus.
3. Checks. Every kit is checked again with single hits (with its modulation);
   anything that rings, whistles or hangs is shortened. Finally the kit is
   rendered with its groove and its output level normalised without clipping.

Groups (dominant engine family, at least four of six channels):

      0 -  31  MD     Machinedrum style engines (tBD tSD tCP tHH EFM GND)
     32 -  63  PL     Plaits engines (aBD sBD aSD sSD pHH Mdl Str Prt)
     64 - 111  ID     IDM / glitch engines (Zap Crs Byt Rng Cmb)
    112 - 127  HY     hybrids

Channel roles:
    1 kick   2 perc / tom   3 fx   4 snare   5 clap   6 closed hat
    (trigger 7 = open hat on channel 6)

SPDX-License-Identifier: GPL-3.0-only
"""
import json
import math
import os
import random
import subprocess
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyse import analyse, _SOS_K  # noqa: E402
from scipy.signal import sosfilt  # noqa: E402

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
RATE = 44140

FILTER = {"off": 0, "lp": 1, "hp": 2, "bp": 3, "ubp": 4, "notch": 5, "peak": 6, "lp2": 7}
OUTS = {"st1": 0, "st2": 1, "l1": 2, "r1": 3, "l2": 4, "r2": 5, "fx": 6}
LFO = {"sin": 0, "tri": 1, "sup": 2, "sdn": 3, "sqr": 4, "rnd": 5, "xup": 6, "xdn": 7}
FX = {"off": 0, "drv": 1, "glt": 2, "cmp": 3, "del": 4, "rng": 5}

FAMILY = {
    "MD": {"tBD", "tSD", "tCP", "tHH", "EFM", "GND"},
    "PL": {"aBD", "sBD", "aSD", "sSD", "pHH", "Mdl", "Str", "Prt"},
    "ID": {"Zap", "Crs", "Byt", "Rng", "Cmb"},
}
ROLES = ["kick", "perc", "fx", "snare", "clap", "hats"]          # = channels 1..6

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


# =============================================================================
# unit helpers: the engines take 0..127, the designs are in real units
# =============================================================================
def clamp(v, lo=0, hi=127):
    return int(max(lo, min(hi, round(v))))


def tp(t, lo, hi):
    """time in seconds -> parameter of ParamToTime(p, lo, hi)"""
    return clamp(math.log(max(t, lo) / lo) / math.log(hi / lo) * 127)


_AEG = [(0, 0.0), (3, .04), (6, .075), (10, .125), (15, .194), (20, .269), (25, .349), (30, .439), (40, .648),
        (50, .912), (60, 1.26), (80, 2.39)]


def aeg(t):
    """strip AEG decay for a -40 dB time in seconds (measured)"""
    for (v0, t0), (v1, t1) in zip(_AEG, _AEG[1:]):
        if t <= t1:
            return clamp(v0 + (v1 - v0) * (t - t0) / (t1 - t0))
    return 80


def ff(hz):
    """strip filter cutoff in Hz -> parameter (filterShape of sh_channel.c)"""
    y = min(hz / (0.45 * RATE), 0.999)
    return clamp(y / (0.053 + 0.947 * y) * 127)


def bi(x):
    """-1..1 -> bipolar parameter (64 = 0)"""
    return clamp(64 + x * 63)


def u(rng, lo, hi):
    return rng.uniform(lo, hi)


def r(rng, lo, hi):
    return rng.randint(lo, hi)


def pick(rng, *opts):
    return rng.choice(opts)


def eslot(engine, short):
    for p in ENG[engine]["params"]:
        if p["short"] == short:
            return p
    raise KeyError(f"{engine} has no parameter {short}")


def has(engine, short):
    return any(p["short"] == short for p in ENG[engine]["params"])


# =============================================================================
# channel / kit model
# =============================================================================
class Channel:
    def __init__(self, engine, tune=None, **strip):
        self.engine = engine
        self.block = list(ENG[engine]["defaults"])
        self.arch = ""
        if tune is not None:
            self.block[L["TUNE"]] = clamp(tune)
        self.set(**strip)

    def p(self, **kw):
        for k, v in kw.items():
            d = eslot(self.engine, k)
            if isinstance(v, str):
                v = [x.strip().lower() for x in d["labels"]].index(v.strip().lower())
            self.block[L["E0"] + d["slot"]] = clamp(v)
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
            self.block[L[key]] = clamp(v)
        # the strip filter's input gain is 0.4 + drive^2 * 6: 40 = unity
        if self.block[L["FILT_TYPE"]] != 0 and self.block[L["FILT_DRIVE"]] == 0:
            self.block[L["FILT_DRIVE"]] = 40
        return self

    def s(self, k):
        return self.block[L[k.upper()]]

    def aeg_on(self):
        return self.block[L["AEG_MODE"]] == 0

    def gate(self, t, slope=25):
        """amp EG as a gate of length t (s)"""
        return self.set(aeg_mode="ad", attack=0, decay=aeg(t), slope=slope)

    def hp(self, hz, reso=0):
        return self.set(filt_type="hp", filt_freq=ff(hz), filt_reso=reso)

    def copy(self):
        c = Channel(self.engine)
        c.block = list(self.block)
        c.arch = self.arch
        return c


class Kit:
    def __init__(self, name, family, theme, bpm):
        self.name = name[:8]
        self.family = family
        self.theme = theme
        self.bpm = bpm
        self.ch = []
        self.fx = {"type": "off", "routing": "st1", "drywet": 50, "p": [64, 64, 64, 64],
                   "dist": 0, "ratio": 3, "wave": 0, "delay": 0}
        self.cv = []   # (ch, slot 0..5, src, amount, dest)
        self.lfo_used = set()
        self.notes = []
        self.key = None

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
        # CV matrix, 6 slots per channel. Slot 1 = V/Oct (CV1) and slot 2 =
        # decay (CV2) at amount 0, ready for the CV inputs; slots 3..6 hold the
        # internal movement, free ones keep CV3..5 / the channel LFO as source.
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
        self.set_lfo(ch, wave, freq, retrig)
        return self.mod(ch if target_ch is None else target_ch, 5 + ch, amount, dest)

    def lfo_free(self, rng, avoid=()):
        free = [c for c in range(6) if c not in self.lfo_used and c not in avoid]
        return rng.choice(free) if free else None

    def write(self, path):
        with open(path, "wb") as f:
            f.write(self.name.ljust(8)[:8].encode("ascii"))
            f.write(bytes(self.params()))


def write_blocks(blocks, path):
    """a kit file with the given channel blocks, nothing else (pool tests)"""
    k = Kit("POOL", "", "", 120)
    k.ch = blocks
    k.cv = []
    k.write(path)


# =============================================================================
# archetypes. Times are -60 dB times of the engine envelopes unless noted;
# gate() / aeg() take -40 dB times of the strip EG.
# =============================================================================
def mk(engine, tune, **params):
    return Channel(engine, tune).p(**params)


# ---------------------------------------------------------------- kick
def k_trx_sub(g):
    return mk("tBD", r(g, 28, 33), Swp=r(g, 38, 58), SwD=tp(u(g, .012, .035), .002, .25), Dec=tp(u(g, .45, .8), .04, 3),
              Hld=r(g, 0, 12), Clk=r(g, 25, 60), Drv=r(g, 15, 40))


def k_trx_tight(g):
    return mk("tBD", r(g, 31, 36), Swp=r(g, 50, 75), SwD=tp(u(g, .006, .014), .002, .25), Dec=tp(u(g, .22, .4), .04, 3),
              Hld=0, Clk=r(g, 60, 110), Drv=r(g, 20, 50))


def k_trx_hard(g):
    return mk("tBD", r(g, 29, 33), Swp=r(g, 45, 60), SwD=tp(u(g, .015, .03), .002, .25), Dec=tp(u(g, .4, .7), .04, 3),
              Hld=r(g, 8, 25), Clk=r(g, 40, 80), Drv=r(g, 60, 95)).set(drive=r(g, 0, 25))


def k_efm(g):
    return mk("EFM", r(g, 28, 34), Rat=pick(g, "1", "0.5"), Mod=r(g, 15, 40), MDc=tp(u(g, .005, .02), .003, 1.5),
              FB=r(g, 0, 25), Swp=r(g, 70, 100), SwD=tp(u(g, .01, .03), .002, .3), Dec=tp(u(g, .3, .6), .02, 3), Noi=r(g, 0, 8))


def k_gnd(g):
    return mk("GND", r(g, 30, 36), Wav="Sin", Swp=64 + r(g, 30, 55), SwD=tp(u(g, .01, .04), .002, 1.0)).set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .3, .5)), slope=r(g, 30, 50), drive=r(g, 10, 40))


def k_abd(g):
    return mk("aBD", r(g, 29, 35), Ton=r(g, 25, 60), Dec=r(g, 30, 55), AFM=r(g, 30, 75), SFM=r(g, 10, 45), Drv=r(g, 10, 50))


def k_abd_punch(g):
    return mk("aBD", r(g, 30, 36), Ton=r(g, 50, 85), Dec=r(g, 25, 40), AFM=r(g, 60, 100), SFM=r(g, 20, 60), Drv=r(g, 40, 90))


def k_sbd(g):
    return mk("sBD", r(g, 30, 36), Ton=r(g, 35, 75), Dec=r(g, 30, 55), Drt=r(g, 5, 35), FMA=r(g, 30, 75), FMD=r(g, 10, 35))


def k_sbd_dirt(g):
    return mk("sBD", r(g, 29, 34), Ton=r(g, 50, 90), Dec=r(g, 30, 50), Drt=r(g, 50, 100), FMA=r(g, 50, 100),
              FMD=r(g, 15, 40)).set(drive=r(g, 10, 40))


def k_zap(g):
    return mk("Zap", r(g, 24, 30), Dep=r(g, 45, 75), Tim=tp(u(g, .008, .03), .0005, .12), FB=r(g, 0, 25),
              Dec=tp(u(g, .35, .7), .005, 1.0), Dir="Dwn").set(drive=r(g, 10, 40))


def k_zap_click(g):
    return mk("Zap", r(g, 25, 31), Dep=r(g, 60, 90), Tim=tp(u(g, .002, .006), .0005, .12), FB=r(g, 0, 15),
              Dec=tp(u(g, .3, .55), .005, 1.0), Dir="Dwn").set(drive=r(g, 20, 50))


def k_crs_fm(g):
    return mk("Crs", r(g, 24, 30), Src="FM", Rat=r(g, 0, 15), Bit=r(g, 0, 20), Jit=0, Dec=tp(u(g, .35, .6), .005, 2.0),
              Glt=0).set(aeg_mode="ad", attack=0, decay=aeg(u(g, .3, .45)), slope=r(g, 35, 55), filt_type="lp",
                         filt_freq=ff(u(g, 110, 260)), filt_reso=r(g, 20, 50), drive=r(g, 30, 70))


def k_byt(g):
    return mk("Byt", r(g, 22, 30), Frm=r(g, 0, 7), A=r(g, 0, 40), B=r(g, 0, 40), Rst=1).set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .25, .4)), slope=r(g, 35, 55), filt_type="lp",
        filt_freq=ff(u(g, 120, 300)), filt_reso=r(g, 20, 50), drive=r(g, 30, 60))


# ---------------------------------------------------------------- perc / tom
def p_trx_tom(g):
    return mk("tBD", r(g, 45, 60), Swp=r(g, 18, 35), SwD=tp(u(g, .02, .06), .002, .25), Dec=tp(u(g, .25, .5), .04, 3),
              Hld=0, Clk=r(g, 15, 45), Drv=r(g, 0, 25))


def p_efm_wood(g):
    return mk("EFM", r(g, 55, 70), Rat=pick(g, "2", "3", "4", "5"), Mod=r(g, 25, 60), MDc=tp(u(g, .008, .03), .003, 1.5),
              FB=r(g, 0, 25), Swp=r(g, 0, 20), SwD=tp(u(g, .005, .02), .002, .3), Dec=tp(u(g, .08, .18), .02, 3),
              Noi=r(g, 0, 15))


def p_efm_bell(g):
    return mk("EFM", r(g, 60, 76), Rat=pick(g, "2.7", "3.5", "5.2", "7"), Mod=r(g, 40, 80),
              MDc=tp(u(g, .02, .08), .003, 1.5), FB=r(g, 10, 40), Swp=0, SwD=0, Dec=tp(u(g, .12, .25), .02, 3), Noi=0)


def p_gnd_blip(g):
    return mk("GND", r(g, 60, 80), Wav=pick(g, "Tri", "Sqr"), Swp=bi(u(g, -.6, .6)), SwD=tp(u(g, .005, .03), .002, 1)).gate(
        u(g, .05, .12))


def p_trx_rim(g):
    return mk("tSD", r(g, 64, 76), Bdy=r(g, 90, 127), Snp=r(g, 0, 25), Dec=tp(u(g, .02, .05), .02, .8),
              NDc=tp(u(g, .02, .04), .02, 1), Swp=r(g, 30, 70), NTn=r(g, 90, 120))


def p_abd_tom(g):
    return mk("aBD", r(g, 45, 60), Ton=r(g, 35, 70), Dec=r(g, 30, 50), AFM=r(g, 15, 45), SFM=r(g, 0, 20), Drv=r(g, 0, 25))


def p_mdl_wood(g):
    return mk("Mdl", r(g, 58, 72), Str=r(g, 0, 25), Bri=r(g, 35, 70), Dmp=r(g, 10, 35), Exc=r(g, 30, 80))


def p_mdl_glass(g):
    return mk("Mdl", r(g, 60, 74), Str=r(g, 60, 100), Bri=r(g, 35, 70), Dmp=r(g, 25, 45), Exc=r(g, 0, 30)).gate(
        u(g, .12, .25))


def p_str_pluck(g):
    return mk("Str", r(g, 45, 62), Str=r(g, 20, 70), Bri=r(g, 40, 80), Dmp=r(g, 20, 45), Exc=r(g, 0, 30)).gate(
        u(g, .12, .25))


def p_rng_bell(g):
    return mk("Rng", r(g, 56, 66), Spr=r(g, 0, 20), RM=r(g, 0, 30), Ton=r(g, 40, 65), Res=r(g, 30, 60), Wav="Sqr").gate(
        u(g, .06, .14))


def p_cmb_hollow(g):
    fb = pick(g, r(g, 10, 26), r(g, 100, 118))
    return mk("Cmb", r(g, 40, 58), Exc=pick(g, "Imp", "Clk"), FB=fb, Dmp=r(g, 20, 60), Bur=r(g, 5, 25),
              Rat=r(g, 0, 127), Mx2=r(g, 20, 70)).gate(u(g, .12, .25))


def p_zap_blip(g):
    return mk("Zap", r(g, 55, 75), Dep=r(g, 25, 55), Tim=tp(u(g, .003, .012), .0005, .12), FB=r(g, 0, 30),
              Dec=tp(u(g, .06, .15), .005, 1.0), Dir=pick(g, "Up", "Dwn"))


def p_byt_tick(g):
    return mk("Byt", r(g, 50, 70), Frm=r(g, 0, 7), A=r(g, 0, 127), B=r(g, 0, 127), Rst=1).gate(u(g, .04, .1)).hp(
        u(g, 200, 500))


def p_crs_tone(g):
    return mk("Crs", r(g, 55, 70), Src=pick(g, "Sqr", "Saw"), Rat=r(g, 10, 40), Bit=r(g, 30, 70), Jit=r(g, 0, 20),
              Dec=tp(u(g, .08, .18), .005, 2.0), Glt=r(g, 0, 20))


# ---------------------------------------------------------------- fx (the detail channel)
def f_efm_metal(g):
    return mk("EFM", r(g, 60, 80), Rat=pick(g, "5.2", "7", " 11", "3.5", "8"), Mod=r(g, 70, 127),
              MDc=tp(u(g, .005, .03), .003, 1.5), FB=r(g, 40, 100), Swp=r(g, 0, 40), SwD=tp(u(g, .003, .02), .002, .3),
              Dec=tp(u(g, .08, .25), .02, 3), Noi=r(g, 0, 40)).hp(u(g, 300, 700))


def f_gnd_zip(g):
    return mk("GND", r(g, 70, 90), Wav=pick(g, "Saw", "Sqr"), Swp=bi(pick(g, -1, 1) * u(g, .6, 1)),
              SwD=tp(u(g, .01, .06), .002, 1)).gate(u(g, .06, .15)).set(bits=r(g, 0, 60)).hp(u(g, 200, 500))


def f_gnd_sh(g):
    return mk("GND", r(g, 60, 90), Wav="S&H", Swp=bi(u(g, -.3, .3)), SwD=tp(.05, .002, 1)).gate(u(g, .05, .12)).hp(
        u(g, 300, 800))


def f_prt_grain(g):
    return mk("Prt", r(g, 70, 96), Den=r(g, 30, 80), Res=r(g, 50, 100), Spr=r(g, 20, 80)).gate(u(g, .08, .2)).hp(
        u(g, 300, 700))


def f_mdl_chime(g):
    return mk("Mdl", r(g, 72, 88), Str=r(g, 70, 120), Bri=r(g, 70, 110), Dmp=r(g, 30, 50), Exc=r(g, 0, 20)).gate(
        u(g, .1, .2))


def f_ssd_fm(g):
    return mk("sSD", r(g, 70, 90), FMA=r(g, 60, 110), Dec=r(g, 15, 30), Snp=r(g, 20, 60)).hp(u(g, 300, 700))


def f_str_buzz(g):
    return mk("Str", r(g, 60, 80), Str=r(g, 80, 127), Bri=r(g, 80, 120), Dmp=r(g, 20, 40), Exc=r(g, 0, 40)).gate(
        u(g, .08, .18))


def f_zap_laser(g):
    return mk("Zap", r(g, 60, 84), Dep=r(g, 60, 110), Tim=tp(u(g, .01, .05), .0005, .12), FB=r(g, 20, 90),
              Dec=tp(u(g, .08, .2), .005, 1.0), Dir=pick(g, "Dwn", "Up", "Bth"))


def f_crs_glitch(g):
    return mk("Crs", r(g, 50, 80), Src=pick(g, "Sqr", "Saw", "FM"), Rat=r(g, 40, 90), Bit=r(g, 60, 110),
              Jit=r(g, 40, 110), Dec=tp(u(g, .08, .2), .005, 2.0), Glt=r(g, 40, 110)).hp(u(g, 200, 600))


def f_byt_chirp(g):
    return mk("Byt", r(g, 60, 90), Frm=r(g, 0, 7), A=r(g, 0, 127), B=r(g, 0, 127), Rst=1).gate(u(g, .05, .15)).set(
        bits=r(g, 0, 50)).hp(u(g, 300, 800))


def f_cmb_metal(g):
    return mk("Cmb", r(g, 60, 80), Exc=pick(g, "Imp", "Clk", "Saw"), FB=r(g, 108, 122), Dmp=r(g, 10, 40),
              Bur=r(g, 5, 30), Rat=r(g, 30, 127), Mx2=r(g, 40, 90)).gate(u(g, .1, .2))


def f_rng_metal(g):
    return mk("Rng", r(g, 56, 72), Spr=r(g, 70, 127), RM=r(g, 70, 127), Ton=r(g, 45, 75), Res=r(g, 10, 40),
              Wav=pick(g, "Sqr", "Sin")).gate(u(g, .06, .15))


# ---------------------------------------------------------------- snare
def s_trx(g):
    return mk("tSD", r(g, 50, 58), Bdy=r(g, 75, 115), Snp=r(g, 75, 110), Dec=tp(u(g, .08, .18), .02, .8),
              NDc=tp(u(g, .14, .3), .02, 1), Swp=r(g, 20, 50), NTn=r(g, 35, 60)).set(
        filt_type="lp", filt_freq=ff(u(g, 8000, 12000)), filt_reso=r(g, 0, 20))


def s_trx_tight(g):
    return mk("tSD", r(g, 54, 62), Bdy=r(g, 70, 110), Snp=r(g, 70, 110), Dec=tp(u(g, .05, .1), .02, .8),
              NDc=tp(u(g, .1, .18), .02, 1), Swp=r(g, 40, 70), NTn=r(g, 30, 60)).set(
        drive=r(g, 10, 40), filt_type="lp", filt_freq=ff(u(g, 7000, 11000)), filt_reso=r(g, 0, 25))


def s_efm(g):
    return mk("EFM", r(g, 50, 60), Rat=pick(g, "1.4", "2.7", "3.1", "5.2"), Mod=r(g, 50, 90),
              MDc=tp(u(g, .02, .06), .003, 1.5), FB=r(g, 20, 60), Swp=r(g, 30, 60), SwD=tp(u(g, .01, .03), .002, .3),
              Dec=tp(u(g, .14, .26), .02, 3), Noi=r(g, 75, 105)).set(
        filt_type="lp", filt_freq=ff(u(g, 7000, 11000)), filt_reso=r(g, 0, 25))


def s_gnd_noise(g):
    return mk("GND", r(g, 60, 80), Wav="Noi", Swp=64, SwD=0).gate(u(g, .15, .25)).set(
        filt_type="bp", filt_freq=ff(u(g, 1500, 3200)), filt_reso=r(g, 10, 40))


def s_asd(g):
    return mk("aSD", r(g, 48, 58), Ton=r(g, 40, 80), Dec=r(g, 25, 50), Snp=r(g, 70, 110)).hp(u(g, 100, 150))


def s_ssd(g):
    return mk("sSD", r(g, 50, 60), FMA=r(g, 20, 60), Dec=r(g, 25, 50), Snp=r(g, 60, 110)).hp(u(g, 100, 150))


def s_asd_snap(g):
    return mk("aSD", r(g, 54, 62), Ton=r(g, 60, 95), Dec=r(g, 15, 32), Snp=r(g, 100, 127)).set(drive=r(g, 15, 45)).hp(
        u(g, 140, 200))


def s_crs(g):
    return mk("Crs", r(g, 55, 70), Src="Noi", Rat=r(g, 10, 40), Bit=r(g, 20, 60), Jit=r(g, 0, 30),
              Dec=tp(u(g, .15, .3), .005, 2.0), Glt=r(g, 0, 20)).hp(u(g, 150, 250))


def s_cmb(g):
    return mk("Cmb", r(g, 50, 62), Exc="Noi", FB=r(g, 112, 124), Dmp=r(g, 20, 50), Bur=r(g, 50, 90),
              Rat=r(g, 0, 127), Mx2=r(g, 20, 60)).gate(u(g, .18, .3)).hp(u(g, 120, 180))


def s_crs_fm(g):
    return mk("Crs", r(g, 58, 70), Src="FM", Rat=r(g, 20, 50), Bit=r(g, 30, 60), Jit=r(g, 10, 40),
              Dec=tp(u(g, .14, .24), .005, 2.0), Glt=r(g, 10, 40)).hp(u(g, 150, 250))


def s_byt(g):
    return mk("Byt", r(g, 60, 76), Frm=r(g, 0, 7), A=r(g, 40, 127), B=r(g, 40, 127), Rst=1).gate(u(g, .14, .24)).set(
        filt_type="bp", filt_freq=ff(u(g, 1800, 4000)), filt_reso=r(g, 0, 20), drive=r(g, 30, 60))


# ---------------------------------------------------------------- clap
def c_trx(g):
    return mk("tCP", r(g, 88, 100), Dec=tp(u(g, .2, .45), .05, 1.5), Spc=tp(u(g, .006, .014), .003, .04),
              Num=r(g, 2, 4), Q=r(g, 15, 45), Rnd=r(g, 10, 40)).hp(u(g, 400, 800))


def c_trx_tight(g):
    return mk("tCP", r(g, 94, 108), Dec=tp(u(g, .12, .25), .05, 1.5), Spc=tp(u(g, .004, .008), .003, .04),
              Num=r(g, 1, 2), Q=r(g, 30, 60), Rnd=r(g, 0, 25)).hp(u(g, 600, 1000))


def c_pl(g):
    eng = pick(g, "aSD", "sSD")
    c = Channel(eng, r(g, 62, 74))
    c.p(Ton=r(g, 10, 40), Dec=r(g, 30, 50), Snp=127) if eng == "aSD" else c.p(FMA=r(g, 0, 20), Dec=r(g, 30, 50), Snp=127)
    return c.set(aeg_mode="ad", attack=r(g, 2, 6), decay=aeg(u(g, .15, .25)), slope=r(g, 20, 35), repeat=r(g, 2, 4),
                 filt_type="bp", filt_freq=ff(u(g, 1100, 2200)), filt_reso=r(g, 10, 35))


def c_crs(g):
    return mk("Crs", r(g, 70, 90), Src="Noi", Rat=r(g, 20, 70), Bit=r(g, 40, 90), Jit=r(g, 10, 50),
              Dec=tp(.3, .005, 2.0), Glt=0).set(aeg_mode="ad", attack=r(g, 2, 6), decay=aeg(u(g, .14, .24)),
                                                repeat=r(g, 2, 5), filt_type="bp", filt_freq=ff(u(g, 1200, 2600)),
                                                filt_reso=r(g, 10, 40))


def c_spray(g):
    return mk("Crs", r(g, 72, 96), Src="Noi", Rat=r(g, 0, 40), Bit=r(g, 50, 110), Jit=r(g, 40, 110),
              Dec=tp(.3, .005, 2.0), Glt=r(g, 20, 80)).set(aeg_mode="ad", attack=r(g, 1, 4), decay=aeg(u(g, .14, .22)),
                                                           repeat=r(g, 4, 8)).hp(u(g, 700, 1400))


def c_cmb(g):
    return mk("Cmb", r(g, 60, 80), Exc="Clk", FB=r(g, 112, 122), Dmp=r(g, 50, 90), Bur=r(g, 40, 80),
              Rat=r(g, 40, 127), Mx2=r(g, 40, 80)).gate(u(g, .15, .24)).set(repeat=r(g, 2, 4)).hp(u(g, 400, 800))


# ---------------------------------------------------------------- hats (alt trigger = open)
def h_trx(g):
    return mk("tHH", r(g, 76, 92), Ton=r(g, 55, 95), Dec=tp(u(g, .03, .07), .01, 1.5), Mtl=r(g, 50, 110),
              Opn=tp(u(g, .3, .55), .01, 1.5), Res=r(g, 5, 40)).hp(u(g, 5000, 8000))


def h_trx_dark(g):
    return mk("tHH", r(g, 70, 84), Ton=r(g, 35, 60), Dec=tp(u(g, .03, .08), .01, 1.5), Mtl=r(g, 20, 60),
              Opn=tp(u(g, .3, .5), .01, 1.5), Res=r(g, 0, 25)).hp(u(g, 3500, 5000))


def h_phh(g):
    return mk("pHH", r(g, 66, 82), Ton=r(g, 50, 90), Dec=r(g, 10, 25), Noi=r(g, 30, 70), Typ="808",
              Opn=r(g, 50, 72)).hp(u(g, 4500, 7500))


def h_phh_ring(g):
    return mk("pHH", r(g, 70, 84), Ton=r(g, 60, 100), Dec=r(g, 8, 22), Noi=r(g, 30, 70), Typ="Rng",
              Opn=r(g, 50, 70)).hp(u(g, 5000, 8000))


def h_crs(g):
    return mk("Crs", r(g, 84, 100), Src="Noi", Rat=r(g, 5, 35), Bit=r(g, 30, 90), Jit=r(g, 10, 50), Dec=100,
              Glt=r(g, 0, 30)).set(aeg_mode="ad", attack=0, decay=aeg(u(g, .03, .07)), decay_alt=aeg(u(g, .25, .45)),
                                   slope=20).hp(u(g, 5000, 8000))


def h_rng(g):
    return mk("Rng", r(g, 84, 100), Spr=r(g, 90, 127), RM=r(g, 90, 127), Ton=r(g, 90, 120), Res=r(g, 0, 20),
              Wav="Sqr").set(aeg_mode="ad", attack=0, decay=aeg(u(g, .03, .06)), decay_alt=aeg(u(g, .25, .4)),
                             slope=20).hp(u(g, 6000, 9000))


def h_byt(g):
    return mk("Byt", r(g, 90, 110), Frm=r(g, 0, 7), A=r(g, 60, 127), B=r(g, 60, 127), Rst=1).set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .025, .05)), decay_alt=aeg(u(g, .2, .35)), slope=15).hp(u(g, 6000, 9500))


ARCH = {
    "MD": dict(kick=[k_trx_sub, k_trx_tight, k_trx_hard, k_efm, k_gnd],
               perc=[p_trx_tom, p_efm_wood, p_efm_bell, p_gnd_blip, p_trx_rim],
               fx=[f_efm_metal, f_gnd_zip, f_gnd_sh, f_efm_metal],
               snare=[s_trx, s_trx_tight, s_efm, s_gnd_noise],
               clap=[c_trx, c_trx_tight],
               hats=[h_trx, h_trx_dark]),
    "PL": dict(kick=[k_abd, k_abd_punch, k_sbd, k_sbd_dirt],
               perc=[p_abd_tom, p_mdl_wood, p_mdl_glass, p_str_pluck],
               fx=[f_prt_grain, f_mdl_chime, f_ssd_fm, f_str_buzz],
               snare=[s_asd, s_ssd, s_asd_snap],
               clap=[c_pl],
               hats=[h_phh, h_phh_ring]),
    "ID": dict(kick=[k_zap, k_zap_click, k_crs_fm, k_byt],
               perc=[p_rng_bell, p_cmb_hollow, p_zap_blip, p_byt_tick, p_crs_tone],
               fx=[f_zap_laser, f_crs_glitch, f_byt_chirp, f_cmb_metal, f_rng_metal],
               snare=[s_crs, s_cmb, s_crs_fm, s_byt],
               clap=[c_crs, c_spray, c_cmb],
               hats=[h_crs, h_rng]),
}

# =============================================================================
# role scoring (lower is better)
# =============================================================================
#             kick  perc  fx    snare clap  hats  open
RING_MAX = [0.55, 0.45, 0.45, 0.38, 0.45, 0.14, 0.62]
RING_MIN = [0.18, 0.04, 0.03, 0.09, 0.06, 0.02, 0.12]
HF_MAX = [0.10, 0.32, 0.32, 0.32, 0.38, 0.14, 0.55]
TONE_LEVEL = -42.0
TONE_PROM = 18.0


def out_of(x, lo, hi, scale):
    if x < lo:
        return (lo - x) / scale
    if x > hi:
        return (x - hi) / scale
    return 0.0


# loudest single hit loudness a voice reaches at full volume (dB, K-weighted);
# quieter voices would need so much make-up gain that they distort
CREST_MAX = {"kick": 9, "perc": 14, "fx": 15, "snare": 13.5, "clap": 14.5, "hats": 16}
AVAIL_MIN = {"kick": -12, "perc": -26, "fx": -28, "snare": -22, "clap": -24, "hats": -30}


def role_penalty(role, m, alt=None, vol=100):
    """how far a measured hit is from where its role belongs (0 = ideal)"""
    f = m["feat"]
    b = f["bands"]
    pen = 0.0
    avail = f["loud"] + 20 * math.log10(127 / max(vol, 1))
    pen += max(0.0, AVAIL_MIN[role] - avail) / 3
    # spiky voices (peaks far above their loudness) make a kit quiet
    crest = 20 * math.log10(m["peak"] + 1e-9) - f["loud"]
    pen += max(0.0, crest - CREST_MAX[role]) / 2
    k = ROLES.index(role)
    pen += out_of(m["ring"], RING_MIN[k], RING_MAX[k], 0.05)
    pen += max(0.0, m["hf"] - HF_MAX[k]) / 0.05
    fq, lvl, prom = m["tone"]
    if lvl > TONE_LEVEL and prom > TONE_PROM:
        pen += 5.0                                   # whistle
    pen += max(0.0, abs(f["dc"]) - 0.03) * 50
    sl = b["sub"] + b["low"]
    if role == "kick":
        pen += out_of(sl, 0.6, 1.0, 0.05)
        pen += out_of(f["centroid"], 45, 500, 60)
        pen += max(0.0, f["attack"] - 9) / 2
        pen += max(0.0, b["himid"] - 0.05) / 0.02
        pen += out_of(f["f0"], 38, 80, 6)
        pen += max(0.0, 4 - m["punch"]) / 2
    elif role == "perc":
        pen += max(0.0, b["sub"] - 0.05) / 0.02
        pen += max(0.0, sl - 0.6) / 0.05
        pen += out_of(f["centroid"], 100, 3500, 200)
        pen += max(0.0, f["harsh"] - 0.5) / 0.05
        pen += max(0.0, f["attack"] - 6) / 3
    elif role == "fx":
        pen += max(0.0, sl - 0.05) / 0.03
        pen += out_of(f["centroid"], 500, 9000, 400)
        pen += max(0.0, f["harsh"] - 0.5) / 0.05
        pen -= min(f["flux"], 0.6) * 3               # movement inside the hit is welcome
    elif role == "snare":
        pen += max(0.0, b["sub"] - 0.03) / 0.02
        pen += out_of(f["centroid"], 700, 5500, 300)
        pen += out_of(b["lowmid"] + b["mid"], 0.08, 0.6, 0.05)
        pen += max(0.0, 0.3 - (b["himid"] + b["high"] + b["air"])) / 0.05
        pen += max(0.0, f["attack"] - 5) / 2
        pen += max(0.0, f["harsh"] - 0.6) / 0.05
        pen += max(0.0, b["air"] - 0.25) / 0.05
    elif role == "clap":
        pen += max(0.0, sl - 0.04) / 0.02
        pen += out_of(f["centroid"], 900, 5000, 300)
        pen += max(0.0, f["harsh"] - 0.75) / 0.05
    elif role == "hats":
        pen += max(0.0, sl + b["lowmid"] + b["mid"] - 0.06) / 0.02
        pen += max(0.0, 5000 - f["centroid"]) / 500
        pen += max(0.0, f["harsh"] - 0.3) / 0.05
        if alt is not None:
            pen += out_of(alt["ring"], 0.22, RING_MAX[6], 0.05)
            pen += max(0.0, alt["hf"] - HF_MAX[6]) / 0.05
    return pen


# =============================================================================
# pools
# =============================================================================
POOL_N = {"kick": 42, "perc": 48, "fx": 54, "snare": 42, "clap": 36, "hats": 36}
POOL_KEEP = 14
POOL_PER_ARCH = 4


def build_pools(seed="shard5"):
    cache = os.path.join(WORK, "pools.json")
    if os.path.exists(cache):
        raw = json.load(open(cache))
        pools = {}
        for fam, roles in raw.items():
            pools[fam] = {}
            for role, items in roles.items():
                lst = []
                for it in items:
                    c = Channel(it["engine"])
                    c.block = it["block"]
                    c.arch = it["arch"]
                    lst.append((c, it["pen"], it["m"]))
                pools[fam][role] = lst
        return pools

    pools = {}
    tmp = os.path.join(WORK, "pool.snd")
    for fam, roles in ARCH.items():
        pools[fam] = {}
        for role, archs in roles.items():
            rng = random.Random(f"{seed}-{fam}-{role}")
            cands = []
            for n in range(POOL_N[role]):
                a = archs[n % len(archs)]
                c = a(rng)
                c.arch = a.__name__
                cands.append(c)
            scored = []
            for i in range(0, len(cands), 6):
                group = cands[i:i + 6]
                blocks = group + [Channel("GND").set(vol=0)] * (6 - len(group))
                write_blocks(blocks, tmp)
                m = analyse(RENDER, tmp, with_features=True, alt_all=True)
                for j, c in enumerate(group):
                    alt = m[6 + j] if role == "hats" else None
                    pen = role_penalty(role, m[j], alt, c.s("vol"))
                    scored.append((c, pen, slim(m[j])))
            scored.sort(key=lambda x: x[1])
            # keep the best, at most 4 of one archetype
            keep, per_arch = [], {}
            for c, pen, m in scored:
                if per_arch.get(c.arch, 0) >= POOL_PER_ARCH:
                    continue
                keep.append((c, pen, m))
                per_arch[c.arch] = per_arch.get(c.arch, 0) + 1
                if len(keep) >= POOL_KEEP:
                    break
            pools[fam][role] = keep
            print(f"pool {fam} {role:5s}: best {keep[0][1]:.2f} worst kept {keep[-1][1]:.2f} "
                  f"archs {sorted(set(c.arch for c, _, _ in keep))}", flush=True)
    json.dump({fam: {role: [dict(engine=c.engine, block=c.block, arch=c.arch, pen=pen, m=m) for c, pen, m in items]
                     for role, items in roles.items()} for fam, roles in pools.items()}, open(cache, "w"))
    return pools


def slim(m):
    f = m["feat"]
    return dict(ring=m["ring"], f0=f["f0"], tonal=f["tonal"], loud=f["loud"], centroid=f["centroid"],
                peak=m["peak"])


# =============================================================================
# themes, grooves, keys
# =============================================================================
THEMES = {
    #            bpm range   fx weights                                  movement
    "precision": ((120, 128), {"cmp": 4, "drv": 1, "del": 1}, 1),
    "chrome":    ((124, 134), {"del": 4, "glt": 1}, 2),
    "fracture":  ((140, 168), {"glt": 5, "del": 1, "drv": 1}, 3),
    "liquid":    ((110, 124), {"del": 5}, 2),
    "crunch":    ((126, 136), {"drv": 5, "cmp": 1}, 1),
    "micro":     ((100, 118), {"glt": 3, "del": 2}, 3),
    "torque":    ((128, 140), {"drv": 4, "glt": 1}, 2),
    "spatial":   ((118, 128), {"del": 4, "glt": 1}, 3),
}
THEME_ORDER = ["precision", "chrome", "fracture", "liquid", "crunch", "micro", "torque", "spatial"]
ID_THEME_ORDER = ["fracture", "micro", "chrome", "torque", "fracture", "spatial", "micro", "liquid"]

GROOVES = {   # kick, perc, fx, snare, clap, hats ('X' accent, 'o' open hat, 'r' ratchet)
    "precision": ["X...X...X...X...", "..x.....x.x.....", ".......x......x.", "....X.......X...", "....x.......x...", "x.x.x.x.x.x.x.xo"],
    "chrome":    ["X..x..x...X.....", "...x......x..x..", "x.....x.x.....x.", "....X.......X...", "............x..x", "xxxoxxxxxxxoxxxx"],
    "fracture":  ["X..x.r....X.x...", "..x.x....x.xr...", "r..x..x.x...x..r", "....X..x...rX...", "......x.......x.", "xx.xxrx.xo.xxrxo"],
    "liquid":    ["X.....x...X.....", "....x.....x..x..", "..x.......x....x", "....X.......X...", "...........x....", "x.xxx.xox.xxx.xo"],
    "crunch":    ["X..xX...X..xX...", "x...x.x.x...x.x.", "..x...x...x...x.", "....X.......X...", "....x.......x...", "xxoxxxoxxxoxxxox"],
    "micro":     ["X.....x...X..x..", ".x..x.x..x..xr..", "x.r..x...rx..x..", "....x..x....X..r", "..x.....r.....x.", "x.xxrxx.xxrox.xr"],
    "torque":    ["X...X...X...X..x", "..x...x..x...x..", ".x...x...x...x..", "....X.......X...", "....x.......x...", "xxxxxxxxxxxxxxxo"],
    "spatial":   ["X..x...x..X..x..", "x.x..xr..x..x.x.", "..r...x...r...x.", "....X.....x.X...", "...x.......x....", "x.xox.xxx.xox.xx"],
}

SCALES = {
    "minor":    [0, 2, 3, 5, 7, 8, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "dorian":   [0, 2, 3, 5, 7, 9, 10],
    "penta":    [0, 3, 5, 7, 10],
    "hijaz":    [0, 1, 4, 5, 7, 8, 10],
}
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# single hit loudness of every role relative to the kick (dB)
LOUD_TARGET = [0.0, -8.0, -9.0, -2.0, -5.0, -15.0]


def hz_to_midi(hz):
    return 69 + 12 * math.log2(hz / 440.0)


def nearest_scale(midi, root, scale, lo=None, hi=None):
    best = None
    for o in range(-2, 10):
        for d in scale:
            n = root + 12 * o + d
            if lo is not None and (n < lo or n > hi):
                continue
            if best is None or abs(n - midi) < abs(best - midi):
                best = n
    return best


# =============================================================================
# kit assembly
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

USED = {}   # pool candidate -> times used in the bank


def choose(rng, pools, fam, role):
    """a pool voice, better ones more likely, each used at most twice"""
    items = pools[fam][role]
    weights = []
    for idx, (c, pen, m) in enumerate(items):
        n = USED.get((fam, role, idx), 0)
        w = 0.0 if n >= 2 else (1.0 / (1.0 + max(pen, 0.0))) * (0.35 if n else 1.0)
        weights.append(w)
    if sum(weights) == 0:
        weights = [1.0] * len(items)
    idx = rng.choices(range(len(items)), weights)[0]
    USED[(fam, role, idx)] = USED.get((fam, role, idx), 0) + 1
    c, pen, m = items[idx]
    return c.copy(), m


def tune_voices(kit, metas, rng):
    """retune pitched voices to the kit's key; returns {ch: (old tune, target midi)}"""
    root, scale = kit.key
    changes = {}
    for ch, (c, m) in enumerate(zip(kit.ch, metas)):
        if m["f0"] <= 0 or m["tonal"] < 15:
            continue
        if ch == 5 or ch == 4:
            continue                                  # hats, claps: noise
        if ch == 3 and m["tonal"] < 22:
            continue                                  # snare: only clearly pitched bodies
        cur = hz_to_midi(m["f0"])
        if ch == 0:
            tgt = nearest_scale(cur, root, [0], 26, 40)          # kick on the root
        elif ch == 1:
            tgt = nearest_scale(cur, root, [0, 7] + scale[2:3], int(cur) - 7, int(cur) + 7)
        else:
            tgt = nearest_scale(cur, root, scale, int(cur) - 6, int(cur) + 6)
        if tgt is None:
            continue
        shift = round(tgt - cur)
        frac = (tgt - cur) - shift
        old = c.s("tune")
        c.set(tune=old + shift)
        if abs(frac) > 0.02:
            c.set(fine=clamp(64 + frac * 100))
        changes[ch] = (old, tgt)
    return changes


def stereo(kit, rng):
    side = pick(rng, -1, 1)
    kit.ch[0].set(pan=64)
    kit.ch[3].set(pan=r(rng, 62, 66))
    kit.ch[4].set(pan=64 + side * r(rng, 0, 6))
    kit.ch[1].set(pan=64 + side * r(rng, 14, 26))
    kit.ch[2].set(pan=64 - side * r(rng, 16, 30))
    kit.ch[5].set(pan=64 - side * r(rng, 6, 14))


def delay_params(rng, kit, pingpong):
    """musical delay time for the kit tempo: P1 time, P2 range (see Delay.c)"""
    beat = 60.0 / kit.bpm
    div = pick(rng, 0.5, 0.75, 0.375, 0.25) if pingpong else pick(rng, 0.75, 0.5, 0.375, 1.0)
    t = beat * div
    smax = 15728 if pingpong else 32767
    while t * RATE > smax * 0.98:
        t /= 2
    samples = t * RATE
    # samples = mn + (mx - mn) * time * range with range = 1: mn = 882
    p1 = (samples - 882) / (smax - 882)
    return clamp(p1 * 127), 127


def setup_fx(rng, kit, level):
    weights = THEMES[kit.theme][1]
    t = rng.choices(list(weights), list(weights.values()))[0]
    f = kit.fx
    f["type"] = t
    if t == "del":
        pp = rng.random() < 0.6
        p1, p2 = delay_params(rng, kit, pp)
        f.update(drywet=r(rng, 22, 40), delay=1 if pp else 0,
                 p=[p1, p2, r(rng, 35, 70), r(rng, 30, 60)])
        sends = [2] + rng.sample([1, 4], r(rng, 1, 2))
    elif t == "drv":
        hard = kit.theme == "torque"
        dist = rng.choice([0, 0, 1, 2]) if hard else 0
        f.update(drywet=r(rng, 40, 75) if not hard else r(rng, 60, 100), dist=dist,
                 p=[r(rng, 30, 60) if not hard else r(rng, 55, 95), r(rng, 30, 80) if dist == 0 else 0,
                    r(rng, 50, 85), r(rng, 60, 85)])
        sends = [0, 3] + rng.sample([1, 2, 4], r(rng, 1, 2)) if not hard else rng.sample([1, 2, 3, 4], 3)
    elif t == "glt":
        wild = kit.theme in ("fracture", "micro") or kit.family == "ID"
        f.update(drywet=100, p=[r(rng, 25, 85), r(rng, 40, 85) if wild else r(rng, 20, 50),
                                r(rng, 50, 127) if wild else r(rng, 10, 70), r(rng, 15, 75)])
        sends = [2] + rng.sample([1, 4, 5], r(rng, 1, 2))
    else:  # cmp glue: slow-ish attack keeps the transients
        f.update(drywet=100, ratio=r(rng, 1, 3), p=[r(rng, 30, 60), r(rng, 15, 45), r(rng, 60, 90), r(rng, 45, 70)])
        sends = [0, 3, 4] + rng.sample([1, 2], r(rng, 0, 2))
    for c in sends:
        kit.ch[c].set(out="fx")
    # slow movement on the bus
    if t != "cmp" and rng.random() < 0.4 + 0.15 * level:
        ch = kit.lfo_free(rng, avoid=(0,))
        if ch is not None:
            if t == "del":
                dest, amt = rng.choice([("fx3", r(rng, 15, 35)), ("fwt", r(rng, 15, 30)), ("fx4", r(rng, 8, 18))])
            elif t == "drv":
                dest, amt = rng.choice([("fx1", r(rng, 15, 35)), ("fx3", r(rng, 15, 35))])
            else:
                dest, amt = rng.choice([("fx2", r(rng, 20, 45)), ("fx3", r(rng, 25, 55)), ("fx1", r(rng, 15, 35))])
            kit.lfo_mod(ch, GLOBAL[dest], amt, wave=rng.choice(["tri", "sin", "rnd"]), freq=r(rng, 14, 32),
                        retrig=rng.choice([0, 0, 1]))
            kit.notes.append(f"lf{ch + 1}->{dest}")


def engine_params(c, kinds=(1, 2)):
    return [p for p in ENG[c.engine]["params"] if p["type"] in kinds and p["slot"] < 14]


def setup_movement(rng, kit, level):
    """detail: S&H micro variation, accents, stereo motion, ratchets, crush"""
    wild = kit.family == "ID"
    fx = kit.ch[2]
    # fx channel: per hit random timbre (fast S&H LFO), sometimes moving pan
    prm = engine_params(fx)
    if prm:
        d = rng.choice(prm)
        kit.lfo_mod(2, mod_dest(2, engine_slot=d["slot"]), r(rng, 12, 30 if not wild else 45), wave="rnd",
                    freq=r(rng, 55, 80))
    if level >= 2:
        src = kit.lfo_free(rng, avoid=(0,))
        if src is not None:
            kit.lfo_mod(src, mod_dest(2, "PAN"), r(rng, 25, 55), wave=pick(rng, "sqr", "tri", "rnd"),
                        freq=r(rng, 30, 55), target_ch=2)
    # hats: accents open the high pass a little, sometimes S&H on the tone
    kit.mod(5, 11 + 5, r(rng, 8, 18), mod_dest(5, "FILT_FREQ"))
    if level >= 2:
        prm = engine_params(kit.ch[5])
        if prm:
            d = prm[0]
            kit.lfo_mod(2 if 2 in kit.lfo_used else 5, mod_dest(5, engine_slot=d["slot"]), r(rng, 6, 14),
                        wave="rnd", freq=r(rng, 50, 70), target_ch=5)
    # perc: subtle S&H on its timbre
    prm = engine_params(kit.ch[1])
    if prm and rng.random() < 0.5 + 0.15 * level:
        d = rng.choice(prm)
        src = 1 if 1 not in kit.lfo_used else (2 if 2 in kit.lfo_used else 1)
        kit.lfo_mod(src, mod_dest(1, engine_slot=d["slot"]), r(rng, 8, 20), wave="rnd", freq=r(rng, 45, 70),
                    target_ch=1)
    # snare: accent pushes the drive
    if rng.random() < 0.5:
        kit.mod(3, 11 + 3, r(rng, 15, 30), mod_dest(3, "DRIVE"))
    # crush / ratchets for the restless themes and the IDM group
    if level >= 3 or wild:
        kit.ch[2].set(bits=max(kit.ch[2].s("bits"), r(rng, 30, 70)))
        if rng.random() < 0.6:
            kit.ch[2].set(srate=r(rng, 70, 110))
        c = pick(rng, 2, 4)
        if kit.ch[c].s("repeat") == 0 and rng.random() < 0.6:
            kit.ch[c].set(repeat=r(rng, 2, 4), attack=r(rng, 1, 4))
    if wild and rng.random() < 0.6:
        # random pitch steps on the fx channel (S&H on V/Oct)
        kit.lfo_mod(2, mod_dest(2, voct=True), r(rng, 6, 14), wave="rnd", freq=r(rng, 40, 60))


def build_kit(rng, pools, family, i):
    order = ID_THEME_ORDER if family == "ID" else THEME_ORDER
    theme = order[i % len(order)]
    bpm = r(rng, *THEMES[theme][0])
    level = THEMES[theme][2]
    kit = Kit((family + NAMES[family][i])[:8], family, theme, bpm)
    fams = ["MD", "PL", "ID"]
    if family == "HY":
        src = [rng.choice(fams) for _ in ROLES]
    else:
        guests = set(rng.sample([1, 2, 3, 4, 5], rng.choice([0, 1, 1, 2])))
        src = [rng.choice([f for f in fams if f != family]) if k in guests else family for k in range(6)]
    metas = []
    for k, role in enumerate(ROLES):
        c, m = choose(rng, pools, src[k], role)
        kit.ch.append(c)
        metas.append(m)
    kit.key = (rng.randrange(12), rng.choice(list(SCALES.values())))
    kit.keyname = NOTE_NAMES[kit.key[0]] + " " + [k for k, v in SCALES.items() if v == kit.key[1]][0]
    kit.tuned = tune_voices(kit, metas, rng)
    stereo(kit, rng)
    setup_movement(rng, kit, level)
    setup_fx(rng, kit, level)
    return kit


# =============================================================================
# checks and mix
# =============================================================================
def problems(m):
    bad = []
    for k in range(7):
        c = m[k]
        if c["peak"] < 1e-4:
            continue
        why = []
        if c["ring"] > RING_MAX[k]:
            why.append(f"ring {c['ring']:.2f}")
        elif c["ring"] < RING_MIN[k] * 0.7:
            why.append(f"short {c['ring']:.2f}")
        if c["hf"] > HF_MAX[k]:
            why.append(f"hf {c['hf']:.2f}")
        f, lvl, prom = c["tone"]
        if k < 6 and lvl > TONE_LEVEL and prom > TONE_PROM:
            why.append(f"tone {f:.0f}Hz {lvl:.0f}dB")
        if why:
            bad.append((k, why))
    return bad


def shorten(c, alt):
    if alt:
        if has(c.engine, "Opn"):
            c.p(Opn=int(c.get("Opn") * 0.85))
        if c.aeg_on():
            c.set(decay_alt=max(4, int(c.s("decay_alt") * 0.85)))
        return
    if c.aeg_on():
        c.set(decay=max(2, int(c.s("decay") * 0.85)))
    else:
        c.set(aeg_mode="ad", attack=0, decay=aeg(0.4), slope=25)


def lengthen(c, alt):
    if alt:
        if has(c.engine, "Opn"):
            c.p(Opn=min(127, int(c.get("Opn") * 1.12) + 2))
        if c.aeg_on():
            c.set(decay_alt=min(100, int(c.s("decay_alt") * 1.2) + 2))
        return
    if c.aeg_on():
        c.set(decay=min(100, int(c.s("decay") * 1.2) + 2))


def fix_kit(kit, path, log):
    for attempt in range(8):
        kit.write(path)
        bad = problems(analyse(RENDER, path))
        if not bad:
            return attempt
        for k, why in bad:
            if attempt in (0, 7):
                log.append(f"  {kit.name} ch{k + 1 if k < 6 else '6o'}: {', '.join(why)}")
            ch = min(k, 5)
            if why[0].startswith("short"):
                lengthen(kit.ch[ch], k == 6)
                continue
            if attempt >= 1:
                # internal modulation can stretch a sound: take it away first
                before = len(kit.cv)
                kit.cv = [e for e in kit.cv if not (e[4] >= MCB and (e[4] - MCB) // MTPC == ch)]
                if len(kit.cv) != before:
                    continue
            shorten(kit.ch[ch], k == 6)
    return -1


def retune_check(kit, path):
    """undo retuning where the engine doesn't follow the tune parameter"""
    if not kit.tuned:
        return 0
    kit.write(path)
    m = analyse(RENDER, path, with_features=True)
    undone = 0
    for ch, (old, tgt) in kit.tuned.items():
        f0 = m[ch]["feat"]["f0"] if "feat" in m[ch] else 0   # silent after retuning: undo
        if f0 <= 0 or abs(hz_to_midi(f0) - tgt) > 0.6:
            kit.ch[ch].set(tune=old, fine=64)
            undone += 1
    return undone


def drive_gain(d):
    """small signal gain of the strip drive (distortion.c waveshaper)"""
    sh = d / 127 - 0.0078125
    return 1 + 2 * sh / (1 - sh) if d > 0 else 1.0


def drive_for(g):
    """smallest drive with at least gain g (capped)"""
    for d in range(0, 91):
        if drive_gain(d) >= g:
            return d
    return 90


MAKEUP_MAX = [20, 40, 40, 40, 40, 24]     # strip drive allowed as make-up gain, per role
CLIP_MAX = [0, 40, 40, 55, 55, 30]        # strip drive allowed as peak control (soft clip)


def balance(kit, path):
    """single hit loudness per role (K-weighted, LOUD_TARGET relative to the
    kick). Channels may use some strip drive as make-up gain; a voice that is
    still too quiet stays quieter instead of being driven into distortion."""
    for _ in range(5):
        kit.write(path)
        m = analyse(RENDER, path, with_features=True)
        loud = [x["feat"]["loud"] if x["peak"] > 1e-4 else None for x in m[:6]]
        if loud[0] is None:
            return
        # the reference level: kick at volume 110 unless another role can't keep up
        cand = [loud[0] + 20 * math.log10(110 / max(kit.ch[0].s("vol"), 1)) - LOUD_TARGET[0]]
        for c in range(1, 6):
            if loud[c] is None:
                continue
            ch = kit.ch[c]
            room = 20 * math.log10(127 / max(ch.s("vol"), 1)) + \
                20 * math.log10(drive_gain(max(ch.s("drive"), MAKEUP_MAX[c])) / drive_gain(ch.s("drive")))
            # a role may pull the reference down by up to 9 dB: the balance
            # matters more than the last dB of level
            cand.append(min(cand[0], max(cand[0] - 9, loud[c] + room - LOUD_TARGET[c])))
        l0 = min(cand)
        done = True
        # peak control: noisy voices whose peaks stand far above their loudness
        # (crest) get the strip drive as a soft clipper; the loudness match
        # below compensates the level
        kick_crest = 20 * math.log10(m[0]["peak"] + 1e-9) - loud[0]
        for c in range(1, 6):
            if loud[c] is None:
                continue
            crest = 20 * math.log10(m[c]["peak"] + 1e-9) - loud[c]
            ch = kit.ch[c]
            if crest > kick_crest + 4 and ch.s("drive") < CLIP_MAX[c]:
                ch.set(drive=min(CLIP_MAX[c], ch.s("drive") + 12))
                done = False
        for c in range(6):
            if loud[c] is None:
                continue
            ch = kit.ch[c]
            err = l0 + LOUD_TARGET[c] - loud[c]
            if abs(err) > 0.7:
                done = False
            want = ch.s("vol") * 10 ** (err / 20)
            if want <= 127:
                ch.set(vol=max(8, want))
            else:
                d0 = ch.s("drive")
                need = drive_gain(d0) * want / 127
                d = min(max(d0, MAKEUP_MAX[c]), drive_for(need))
                ch.set(vol=127, drive=max(d0, d))
        if done:
            return


def render_groove(kit, path, wav):
    pat = os.path.join(WORK, f"groove_{kit.theme}.txt")
    with open(pat, "w") as f:
        f.write("\n".join(GROOVES[kit.theme]) + "\n")
    met = os.path.join(WORK, "metrics.json")
    kit.write(path)
    subprocess.run([RENDER, "--kit", path, pat, str(kit.bpm), "2", wav, met], check=True)
    return json.load(open(met))


def wav_loudness(path):
    w = wave.open(path)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2).astype(np.float64) / 32768
    k = sosfilt(_SOS_K, x, axis=0)
    return 10 * np.log10(np.mean(k ** 2) + 1e-12)


GROOVE_MAX = [0.0, -4.0, -4.0, 1.0, -1.0, -5.0]   # loudest a channel may be in the groove, re kick


def solo_loud(kit, path, ch):
    pat = ["." * 16] * 6
    pat[ch] = GROOVES[kit.theme][ch]
    pf = os.path.join(WORK, "solo.txt")
    with open(pf, "w") as f:
        f.write("\n".join(pat) + "\n")
    wav = os.path.join(WORK, "solo.wav")
    subprocess.run([RENDER, "--kit", path, pf, str(kit.bpm), "2", wav, ""], check=True)
    return wav_loudness(wav)


def groove_guard(kit, path):
    """single hits can fool the balance (random engines, modulation): in the
    groove no channel may get louder than GROOVE_MAX relative to the kick"""
    for it in range(4):
        kit.write(path)
        lk = solo_loud(kit, path, 0)
        ok = True
        for c in range(1, 6):
            lc = solo_loud(kit, path, c)
            over = lc - lk - GROOVE_MAX[c]
            if over > 0.5:
                ok = False
                kit.ch[c].set(vol=max(6, kit.ch[c].s("vol") * 10 ** (-over / 20)))
                # a saturating FX bus keeps its level when the input drops
                if it >= 1 and kit.ch[c].s("out") == OUTS["fx"] and kit.fx["type"] in ("drv", "cmp"):
                    kit.fx["p"][3] = max(20, kit.fx["p"][3] - int(over * 4))
        if ok:
            return


KICK_LOUD = -10.0            # single hit loudness of the kick at the output (dB, K-weighted, 100 ms)
MAX_OUT_PEAK = 0.93          # groove peak limit (-0.6 dB)


def master(kit, path):
    """level the kit: all kits balanced to the kick, so the kick's single hit
    loudness sets the level of every kit; the groove must not clip"""
    wav = os.path.join(WORK, "groove.wav")
    m = None
    for _ in range(4):
        kit.write(path)
        h = analyse(RENDER, path, with_features=True)
        g = 10 ** ((KICK_LOUD - h[0]["feat"]["loud"]) / 20)
        m = render_groove(kit, path, wav)
        if m["clip"]:
            g = min(g, 0.85)
        g = min(g, MAX_OUT_PEAK / max(m["out_peak"], 1e-3))
        if 0.98 < g < 1.02 and not m["clip"]:
            break
        if g > 1 and max(c.s("vol") for c in kit.ch) >= 127:
            break
        top = max(c.s("vol") for c in kit.ch)
        if top * g > 127:
            g = 127 / top
        for c in kit.ch:
            c.set(vol=max(6, min(127, c.s("vol") * g)))
    for _ in range(4):
        m = render_groove(kit, path, wav)
        if not m["clip"] and m["out_peak"] <= 0.97:
            return m
        for c in kit.ch:
            c.set(vol=max(6, c.s("vol") * 0.9))
    return m


# =============================================================================
def file_name(slot, name):
    clean = "".join(c if c.isalnum() else "_" for c in name)
    return f"{slot:02d}-{clean[:5]}.snd" if slot < 100 else f"{slot:03d}-{clean[:4]}.snd"


GROUPS = [("MD", 32), ("PL", 32), ("ID", 48), ("HY", 16)]


def family_count(kit):
    return {f: sum(c.engine in FAMILY[f] for c in kit.ch) for f in FAMILY}


def main():
    pools = build_pools()
    kit_dir = os.path.join(OUT, "shard", "prj00")
    demo_dir = os.path.join(OUT, "demo")
    os.makedirs(kit_dir, exist_ok=True)
    os.makedirs(demo_dir, exist_ok=True)
    only = set(int(x) for x in os.environ.get("ONLY", "").split(",") if x)
    if not only:
        for f in os.listdir(kit_dir):
            os.unlink(os.path.join(kit_dir, f))
    slot = 0
    report, log = [], []
    for family, count in GROUPS:
        for i in range(count):
            rng = random.Random(f"shard5-{family}-{i}")
            kit = build_kit(rng, pools, family, i)
            if only and slot not in only:
                slot += 1
                continue
            if family != "HY":
                assert family_count(kit)[family] >= 4, kit.name
            path = os.path.join(kit_dir, file_name(slot, kit.name))
            undone = retune_check(kit, path)
            fixed = fix_kit(kit, path, log)
            balance(kit, path)
            groove_guard(kit, path)
            m = master(kit, path)
            wav = os.path.join(demo_dir, f"{slot:03d}_{kit.name}.wav") if (i % 4 == 0 or only) else ""
            if wav:
                m = render_groove(kit, path, wav)
            kit.write(path)
            rep = dict(slot=slot, name=kit.name, family=family, theme=kit.theme, bpm=kit.bpm, key=kit.keyname,
                       engines=[c.engine for c in kit.ch], archs=[c.arch for c in kit.ch], fx=kit.fx["type"],
                       out=m["out_peak"], clip=m["clip"], tail=m["tail"], fixed=fixed,
                       tuned=len(kit.tuned) - undone, notes=kit.notes, fam=family_count(kit))
            report.append(rep)
            print(f"{slot:3d} {kit.name:8s} {family} {kit.theme:9s} {kit.keyname:12s} "
                  f"{' '.join(c.engine for c in kit.ch)} fx={kit.fx['type']} fix={fixed} tuned={rep['tuned']} "
                  f"out={m['out_peak']:.2f} clip={m['clip']}", flush=True)
            slot += 1
    with open(os.path.join(OUT, "bank.json"), "w") as f:
        json.dump(report, f, indent=1)
    with open(os.path.join(OUT, "fixlog.txt"), "w") as f:
        f.write("\n".join(log) + "\n")
    print(f"{len(report)} kits written to {kit_dir}")


if __name__ == "__main__":
    main()
