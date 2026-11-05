#!/usr/bin/env python3
"""Build the SHARD psytrance bank (128 kits) with the machinery of make_kits.py.

    python3 tools/kits/make_psy.py <shard_render> <out dir> [bank number]

Writes <out dir>/shard/prjNN/*.snd and prj.nfo (bank 03 by default) and
<out dir>/bank.json. No demo WAVs.

Dark and forest psytrance, 148-160 BPM: dense, heavy, nocturnal. Four
themes of 32 kits:
    forest    148-152  organic: bubbles, creaks, wet wood
    swamp     148-154  viscous and low: squelch, gurgle, quack
    dark      152-160  hard, metallic: scrape, clang, noise
    twilight  148-152  dark acid: resonant filter sweeps
Channel roles
    1 kick     short and hard (0.15-0.3 s), dense click, saturated, body on
               the key root at 45-62 Hz (keys F# to B)
    2 bass     rolling K-B-B-B: three tight 16ths after every kick, through a
               resonant low pass with a short filter envelope (an LFO
               restarted by every bass hit), saturated, -3 dB re kick, tuned
               exactly to the root (measured, replaced if it doesn't track),
               ducked by the kick
    3 fx       dense, alive: bubbles, squelch, quacks, acid sweeps, metal
               scrape, organic creaks; strong S&H on timbre and filter,
               mostly into delay or glitch
    4 rim      dark, short, low-mid; played rarely
    5 clap     dark, short, an accent once a bar
    6 hats     closed 16ths, crisp but not bright; trigger 7 = a dark noisy
               open hat through a low pass, at most once a bar

Voices come mostly from the SHARD engines; the original LXR voices are a
small share of the pools (bank_common.LXR_SHARE).

SPDX-License-Identifier: GPL-3.0-only
"""
import os
import sys

if len(sys.argv) < 3:
    sys.exit(__doc__)
BANK = int(sys.argv[3]) if len(sys.argv) > 3 else 3
sys.argv = sys.argv[:3]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_kits as mk  # noqa: E402
import bank_common as bc  # noqa: E402
from analyse import analyse  # noqa: E402
from make_kits import mk as make, tp, aeg, ff, r, u, pick, clamp, mod_dest  # noqa: E402

FAM = "PS"
THEME_ORDER = ["forest", "swamp", "dark", "twilight"]
KICK_RANGE = (30, 35)      # F#1..B1: the kick body at 46-62 Hz
BASS_RANGE = (30, 41)


# =============================================================================
# archetypes
# =============================================================================
# ---------------------------------------------------------------- kick
def ps_k_abd(g):
    return make("aBD", r(g, 30, 35), Ton=r(g, 45, 80), Dec=r(g, 15, 30), AFM=r(g, 50, 100), SFM=r(g, 20, 60),
                Drv=r(g, 70, 127)).set(drive=r(g, 15, 45))


def ps_k_tbd(g):
    return make("tBD", r(g, 30, 34), Swp=r(g, 50, 75), SwD=tp(u(g, .008, .02), .002, .25), Dec=tp(u(g, .15, .28), .04, 3),
                Hld=r(g, 0, 15), Clk=r(g, 60, 110), Drv=r(g, 60, 110)).set(drive=r(g, 15, 45))


def ps_k_sbd(g):
    return make("sBD", r(g, 30, 35), Ton=r(g, 45, 80), Dec=r(g, 28, 48), Drt=r(g, 30, 80), FMA=r(g, 30, 80),
                FMD=r(g, 10, 30)).set(drive=r(g, 15, 45))


def ps_k_tight(g):
    return mk.k_trx_tight(g).set(drive=r(g, 20, 50))


def ps_k_gnd(g):
    return make("GND", r(g, 30, 35), Wav="Sin", Swp=64 + r(g, 40, 60), SwD=tp(u(g, .008, .02), .002, 1.0)).set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .16, .26)), slope=r(g, 40, 55), drive=r(g, 40, 70))


def ps_k_zap(g):
    return make("Zap", r(g, 26, 31), Dep=r(g, 60, 90), Tim=tp(u(g, .003, .008), .0005, .12), FB=r(g, 5, 25),
                Dec=tp(u(g, .16, .28), .005, 1.0), Dir="Dwn").set(drive=r(g, 30, 60))


def ps_k_drm(g):
    return bc.lxr_kick_short(g).set(drive=r(g, 25, 55))


ARCH_K = [ps_k_abd, ps_k_tbd, ps_k_sbd, ps_k_tight, ps_k_gnd, ps_k_zap, ps_k_drm]


# ---------------------------------------------------------------- bass
def _bass(c, g, lp=(150, 380)):
    """a tight note through a resonant low pass, saturated"""
    return c.set(filt_type="lp", filt_freq=ff(u(g, *lp)), filt_reso=r(g, 45, 85), drive=r(g, 25, 60),
                 aeg_mode="ad", attack=0, decay=aeg(u(g, .08, .12)), slope=r(g, 35, 50))


def ps_b_gnd_saw(g):
    return _bass(make("GND", r(g, 30, 41), Wav="Saw", Swp=64, SwD=0), g)


def ps_b_gnd_sqr(g):
    return _bass(make("GND", r(g, 30, 41), Wav="Sqr", Swp=64, SwD=0), g)


def ps_b_crs(g):
    return _bass(make("Crs", r(g, 30, 41), Src=pick(g, "Saw", "Sqr"), Rat=0, Bit=r(g, 0, 8), Jit=0,
                      Dec=tp(u(g, .1, .2), .005, 2.0), Glt=0), g)


def ps_b_efm(g):
    return _bass(make("EFM", r(g, 30, 41), Rat=pick(g, "1", "0.5"), Mod=r(g, 25, 60),
                      MDc=tp(u(g, .02, .06), .003, 1.5), FB=r(g, 10, 50), Swp=0, SwD=0, Dec=tp(u(g, .1, .2), .02, 3),
                      Noi=0), g, (180, 450))


def ps_b_abd(g):
    return _bass(make("aBD", r(g, 32, 41), Ton=r(g, 10, 40), Dec=r(g, 20, 35), AFM=r(g, 0, 20), SFM=r(g, 10, 40),
                      Drv=r(g, 60, 110)), g, (180, 450))


def ps_b_drm(g):
    return _bass(make("Drm", r(g, 30, 41), Wav=pick(g, "Saw", "Rec"), PDc=r(g, 10, 30), PSl=64, PAm=r(g, 0, 10),
                      FMA=r(g, 10, 35), FMF=64 + pick(g, 0, 12, -12), FMW="Sin", Mod="FM "), g)


ARCH_B = [ps_b_gnd_saw, ps_b_gnd_sqr, ps_b_crs, ps_b_efm, ps_b_abd, ps_b_drm]


# ---------------------------------------------------------------- fx
def _tex(c, g, ftype=("bp", "lp"), freq=(400, 1800), reso=(50, 95), t=(.18, .4)):
    """a texture through a resonant filter, long enough to move"""
    return c.set(filt_type=pick(g, *ftype), filt_freq=ff(u(g, *freq)), filt_reso=r(g, *reso),
                 aeg_mode="ad", attack=r(g, 0, 4), decay=aeg(u(g, *t)), slope=r(g, 25, 40))


# forest: organic
def ps_f_prt_bubble(g):
    return _tex(make("Prt", r(g, 55, 75), Den=r(g, 20, 60), Res=r(g, 70, 115), Spr=r(g, 10, 60)), g,
                ("bp",), (500, 2000), (40, 80))


def ps_f_crs_creak(g):
    """jittery FM noise through a band pass: wood under strain"""
    return _tex(make("Crs", r(g, 44, 60), Src="FM", Rat=r(g, 20, 80), Bit=r(g, 0, 30), Jit=r(g, 30, 90),
                     Dec=tp(u(g, .3, .6), .005, 2.0), Glt=r(g, 0, 30)), g, ("bp",), (600, 2000), (40, 80))


def ps_f_gnd_sh(g):
    """random steps through a resonant band pass: burbling"""
    return _tex(make("GND", r(g, 50, 70), Wav="S&H", Swp=64, SwD=0), g, ("bp", "lp"), (500, 1600), (60, 95))


def ps_f_cmb_wood(g):
    return _tex(make("Cmb", r(g, 45, 62), Exc=pick(g, "Noi", "Saw"), FB=r(g, 105, 124), Dmp=r(g, 30, 80),
                     Bur=r(g, 60, 127), Rat=r(g, 20, 80)), g, ("bp", "lp"), (500, 2200), (20, 60))


def ps_f_byt_bubble(g):
    return _tex(make("Byt", r(g, 48, 66), Frm=r(g, 0, 7), A=r(g, 0, 127), B=r(g, 0, 127), Rst=1), g,
                ("bp",), (400, 1600), (60, 100))


# swamp: squelch, gurgle, quack
def ps_f_gnd_squelch(g):
    return _tex(make("GND", r(g, 44, 58), Wav=pick(g, "Saw", "Sqr"), Swp=64, SwD=0), g,
                ("lp", "bp"), (500, 1600), (80, 110))


def ps_f_crs_quack(g):
    return _tex(make("Crs", r(g, 36, 52), Src=pick(g, "Saw", "Sqr", "FM"), Rat=r(g, 0, 40), Bit=r(g, 0, 30), Jit=0,
                     Dec=tp(u(g, .3, .6), .005, 2.0), Glt=0), g, ("bp", "lp"), (350, 1300), (75, 105))


def ps_f_efm_gurgle(g):
    return _tex(make("EFM", r(g, 36, 52), Rat=pick(g, "1.5", "2", "3"), Mod=r(g, 50, 100),
                     MDc=tp(u(g, .1, .3), .003, 1.5), FB=r(g, 40, 90), Swp=0, SwD=0, Dec=tp(u(g, .3, .6), .02, 3),
                     Noi=r(g, 0, 20)), g, ("bp", "lp"), (350, 1400), (60, 100))


def ps_f_zap_bloop(g):
    return _tex(make("Zap", r(g, 42, 56), Dep=r(g, 30, 70), Tim=tp(u(g, .03, .08), .0005, .12), FB=r(g, 40, 90),
                     Dec=tp(u(g, .2, .4), .005, 1.0), Dir=pick(g, "Up", "Bth")), g, ("lp", "bp"), (400, 1500), (40, 80))


# dark: metal, scrape, noise
def ps_f_efm_clang(g):
    return _tex(make("EFM", r(g, 45, 62), Rat=pick(g, "5.2", "7", "3.5", "2.7"), Mod=r(g, 70, 120),
                     MDc=tp(u(g, .05, .2), .003, 1.5), FB=r(g, 50, 110), Swp=r(g, 0, 20), SwD=tp(u(g, .01, .03), .002, .3),
                     Dec=tp(u(g, .2, .5), .02, 3), Noi=r(g, 10, 40)), g, ("lp", "bp"), (1000, 3000), (20, 60))


def ps_f_cmb_metal(g):
    return _tex(make("Cmb", r(g, 50, 66), Exc=pick(g, "Noi", "Saw"), FB=r(g, 112, 126), Dmp=r(g, 5, 40),
                     Bur=r(g, 60, 127), Rat=r(g, 40, 110)), g, ("lp", "bp"), (1200, 3000), (20, 60))


def ps_f_gnd_noise(g):
    return _tex(make("GND", r(g, 50, 70), Wav="Noi", Swp=64, SwD=0), g, ("bp",), (700, 2500), (60, 100)).set(
        bits=r(g, 20, 60))


def ps_f_prt_scrape(g):
    return _tex(make("Prt", r(g, 60, 80), Den=r(g, 80, 127), Res=r(g, 30, 80), Spr=r(g, 60, 127)), g,
                ("bp", "lp"), (800, 2800), (30, 70))


def ps_f_crs_grind(g):
    return _tex(make("Crs", r(g, 40, 56), Src=pick(g, "Noi", "FM"), Rat=r(g, 30, 90), Bit=r(g, 40, 100),
                     Jit=r(g, 20, 80), Dec=tp(u(g, .3, .6), .005, 2.0), Glt=r(g, 20, 80)), g, ("lp", "bp"),
                (800, 2500), (30, 70))


# twilight: dark acid
def ps_f_acid_saw(g):
    return _tex(make("GND", r(g, 46, 60), Wav="Saw", Swp=64, SwD=0), g, ("lp",), (600, 2000), (95, 118),
                (.2, .45))


def ps_f_acid_sqr(g):
    return _tex(make("GND", r(g, 46, 60), Wav="Sqr", Swp=64, SwD=0), g, ("lp",), (600, 2000), (95, 118),
                (.2, .45))


def ps_f_acid_crs(g):
    return _tex(make("Crs", r(g, 46, 60), Src=pick(g, "Saw", "Sqr"), Rat=0, Bit=r(g, 0, 25), Jit=0,
                     Dec=tp(u(g, .3, .6), .005, 2.0), Glt=0), g, ("lp",), (600, 2000), (90, 115), (.2, .45))


def ps_f_acid_drm(g):
    return _tex(make("Drm", r(g, 46, 60), Wav=pick(g, "Saw", "Rec"), PDc=0, PAm=0, FMA=r(g, 0, 30),
                     FMF=64 + pick(g, 0, 12, 7), FMW="Saw", Mod="FM "), g, ("lp",), (600, 2000), (95, 118), (.2, .45))


ARCH_FX = dict(
    forest=[ps_f_prt_bubble, ps_f_crs_creak, ps_f_gnd_sh, ps_f_cmb_wood, ps_f_byt_bubble, ps_f_zap_bloop],
    swamp=[ps_f_gnd_squelch, ps_f_crs_quack, ps_f_efm_gurgle, ps_f_gnd_sh, ps_f_zap_bloop, ps_f_byt_bubble],
    dark=[ps_f_efm_clang, ps_f_cmb_metal, ps_f_gnd_noise, ps_f_prt_scrape, ps_f_crs_grind, ps_f_crs_creak],
    twilight=[ps_f_acid_saw, ps_f_acid_sqr, ps_f_acid_crs, ps_f_acid_drm, ps_f_gnd_squelch, ps_f_crs_quack],
)
FILTER_ENV = ("squelch", "quack", "acid")      # fx archetypes that get a filter envelope


# ---------------------------------------------------------------- rim
def _dark(c, g, lo=2500, hi=5000):
    return c.set(filt_type="lp", filt_freq=ff(u(g, lo, hi)), filt_reso=r(g, 0, 25))


def _rim(c, g):
    """band pass in the low mids: dark, no body boom, no air"""
    return c.set(filt_type="bp", filt_freq=ff(u(g, 1500, 2800)), filt_reso=r(g, 10, 35))


def ps_r_tsd(g):
    return _rim(make("tSD", r(g, 66, 80), Bdy=r(g, 60, 110), Snp=r(g, 30, 80), Dec=tp(u(g, .03, .07), .02, .8),
                      NDc=tp(u(g, .04, .08), .02, 1), Swp=r(g, 30, 70), NTn=r(g, 40, 90)), g)


def ps_r_efm(g):
    return _rim(make("EFM", r(g, 62, 78), Rat=pick(g, "2", "3", "3.5"), Mod=r(g, 30, 70),
                      MDc=tp(u(g, .005, .02), .003, 1.5), FB=r(g, 0, 40), Swp=r(g, 0, 20), SwD=tp(u(g, .005, .015), .002, .3),
                      Dec=tp(u(g, .05, .1), .02, 3), Noi=r(g, 20, 60)), g)


def ps_r_trx_rim(g):
    return _rim(mk.p_trx_rim(g), g)


def ps_r_asd(g):
    return _dark(mk.s_asd_snap(g), g, 2200, 4000).set(decay=aeg(u(g, .08, .14)), aeg_mode="ad", attack=0, slope=35)


def ps_r_ssd(g):
    return _dark(mk.s_ssd(g), g, 3000, 5500)


def ps_r_snr(g):
    return _dark(bc.lxr_snare(g), g, 3000, 5500).set(decay=aeg(u(g, .08, .14)))


ARCH_S = [ps_r_tsd, ps_r_efm, ps_r_trx_rim, ps_r_asd, ps_r_ssd, ps_r_snr]


# ---------------------------------------------------------------- clap
def ps_c_trx(g):
    return _dark(mk.c_trx_tight(g), g, 2500, 5000)


def ps_c_pl(g):
    return _dark(mk.c_pl(g), g, 2500, 5000)


def ps_c_crs(g):
    return _dark(mk.c_crs(g), g, 2500, 5000)


def ps_c_snr(g):
    return bc.lxr_clap(g).set(filt_type="bp", filt_freq=ff(u(g, 900, 1800)), filt_reso=r(g, 10, 35),
                              decay=aeg(u(g, .1, .18)))


ARCH_C = [ps_c_trx, ps_c_pl, ps_c_crs, ps_c_snr]


# ---------------------------------------------------------------- hats
def _hat(c, g):
    """closed: short; open (T7): a dark noisy shhh through the band pass"""
    return c.set(filt_type="bp", filt_freq=ff(u(g, 6500, 9000)), filt_reso=r(g, 0, 20), aeg_mode="ad", attack=0,
                 decay=aeg(u(g, .03, .055)), decay_alt=aeg(u(g, .18, .28)), slope=r(g, 15, 25))


def ps_h_trx(g):
    return _hat(make("tHH", r(g, 60, 80), Opn=r(g, 60, 95)), g)


def ps_h_phh(g):
    return _hat(make("pHH", r(g, 60, 90)), g)


def ps_h_gnd(g):
    return _hat(make("GND", r(g, 70, 90), Wav="Noi", Swp=64, SwD=0), g)


def ps_h_crs(g):
    return _hat(make("Crs", r(g, 70, 95), Src="Noi", Rat=r(g, 0, 60), Bit=r(g, 0, 40), Jit=r(g, 0, 40),
                     Dec=tp(u(g, .3, .6), .005, 2.0), Glt=0), g)


def ps_h_rng(g):
    return _hat(mk.h_rng(g), g).set(filt_freq=ff(u(g, 5000, 7000)))


def ps_h_lxr(g):
    return _hat(bc.lxr_hat(g), g)


ARCH_H = [ps_h_trx, ps_h_phh, ps_h_gnd, ps_h_crs, ps_h_rng, ps_h_lxr]

ARCH_PS = dict(kick=ARCH_K, perc=ARCH_B, snare=ARCH_S, clap=ARCH_C, hats=ARCH_H)

# =============================================================================
# role targets (single hits)
# =============================================================================
#             kick  bass  fx    rim   clap  hats  open
mk.RING_MAX = [0.30, 0.12, 0.60, 0.15, 0.25, 0.08, 0.30]
mk.RING_MIN = [0.15, 0.08, 0.15, 0.04, 0.07, 0.02, 0.12]
mk.HF_MAX = [0.08, 0.02, 0.15, 0.12, 0.15, 0.25, 0.30]
mk.CREST_MAX.update(perc=12, fx=16, snare=15, clap=15, hats=17)
mk.AVAIL_MIN.update(perc=-18, fx=-30, snare=-32, clap=-30, hats=-34)
mk.POOL_N = {"kick": 120, "perc": 140, "fx": 150, "snare": 130, "clap": 110, "hats": 130}
mk.POOL_KEEP = 110       # filter_pools keeps the best 64, spread over the engines
mk.POOL_PER_ARCH = 18
mk.ARCH = {FAM: ARCH_PS, **{FAM + t: {"fx": a} for t, a in ARCH_FX.items()}}
POOL_MAX_PENALTY = {"kick": 3.0, "perc": 3.0, "fx": 3.0, "snare": 5.0, "clap": 5.0, "hats": 5.0}


def role_penalty(role, m, alt=None, vol=100):
    f = m["feat"]
    b = f["bands"]
    fq, lvl, prom = m["tone"]
    sl = b["sub"] + b["low"]
    pen = bc.base_penalty(role, m, vol)
    if role == "perc":           # the notes join up: a continuous low end
        pen += max(0.0, 0.09 - m["ring"]) / 0.01
    if role == "kick":           # hard, short, dense click, saturated body at 45-62 Hz
        if lvl > mk.TONE_LEVEL and prom > mk.TONE_PROM:
            pen += 5.0
        pen += mk.out_of(f["f0"], 44, 64, 3)
        pen += mk.out_of(sl, 0.6, 0.97, 0.03)            # not only sub: some body above
        pen += mk.out_of(b["lowmid"] + b["mid"], 0.02, 0.3, 0.01)
        pen += mk.out_of(f["centroid"], 60, 400, 40)
        pen += max(0.0, b["himid"] - 0.06) / 0.02
        pen += max(0.0, f["attack"] - 6) / 2
        pen += max(0.0, 5 - m["punch"]) / 1.5
    elif role == "perc":         # bass: low, pitched, tight, weighty
        pen += bc.out_of_whistle(fq, lvl, prom, 500)
        pen += mk.out_of(f["centroid"], 60, 150, 15)
        pen += mk.out_of(sl, 0.7, 1.0, 0.03)
        pen += max(0.0, 0.25 - b["sub"]) / 0.05             # sub weight
        pen += max(0.0, b["himid"] + b["high"] + b["air"] - 0.03) / 0.01
        pen += mk.out_of(f["f0"], 42, 90, 4)              # the exact pitch is checked per kit
    elif role == "fx":           # dense mid textures, no beeps, no pure tones
        pen += bc.out_of_whistle(fq, lvl, prom, 1500)
        pen += mk.out_of(f["centroid"], 300, 3000, 150)
        pen += max(0.0, sl - 0.25) / 0.03
        pen += max(0.0, b["air"] - 0.04) / 0.01
        pen += max(0.0, f["tonal"] - 45) / 3            # rich, resonant: fine; a pure tone: not
        pen += max(0.0, f["harsh"] - 0.5) / 0.05
        pen -= min(f["flux"], 0.6) * 3
    elif role == "snare":        # rim: dark, short, low-mid
        pen += bc.out_of_whistle(fq, lvl, prom, 1500)
        pen += mk.out_of(f["centroid"], 1500, 4000, 200)
        pen += max(0.0, b["sub"] - 0.03) / 0.02
        pen += max(0.0, b["air"] - 0.04) / 0.01
        pen += max(0.0, f["attack"] - 4) / 2
        pen += max(0.0, f["harsh"] - 0.6) / 0.05
    elif role == "clap":         # dark, short
        pen += max(0.0, sl - 0.04) / 0.02
        pen += mk.out_of(f["centroid"], 1200, 3500, 200)
        pen += max(0.0, b["air"] - 0.05) / 0.01
        pen += max(0.0, f["harsh"] - 0.75) / 0.05
    elif role == "hats":         # crisp, not bright; open: dark shhh
        pen += max(0.0, sl + b["lowmid"] + b["mid"] - 0.06) / 0.02
        pen += mk.out_of(f["centroid"], 7000, 11000, 400)
        pen += max(0.0, f["harsh"] - 0.35) / 0.05
        if alt is not None:
            pen += mk.out_of(alt["ring"], 0.15, mk.RING_MAX[6], 0.03)
            pen += max(0.0, alt["hf"] - mk.HF_MAX[6]) / 0.05
            if "feat" in alt:
                pen += max(0.0, alt["feat"]["centroid"] - 10000) / 400
    return pen


mk.role_penalty = role_penalty

# single hit loudness re kick, loudest in the groove re kick
mk.LOUD_TARGET = [0.0, -3.0, -9.0, -10.0, -8.0, -15.0]
mk.GROOVE_MAX = [0.0, 4.0, -2.0, -6.0, -5.0, -6.0]     # bass: three hits for every kick
mk.MAKEUP_MAX = [24, 50, 40, 40, 40, 24]

# =============================================================================
# themes and grooves: no open hat on every off beat, no clap on 2 and 4
# =============================================================================
mk.THEMES = {
    #             bpm range    fx weights                                movement
    "forest":   ((148, 152), {"del": 3, "glt": 2, "cmp": 1}, 3),
    "swamp":    ((148, 154), {"del": 3, "glt": 1, "cmp": 1, "drv": 1}, 3),
    "dark":     ((152, 160), {"glt": 3, "del": 2, "drv": 1}, 3),
    "twilight": ((148, 152), {"del": 3, "glt": 2, "drv": 1}, 3),
}
mk.GROOVES = {   # kick, bass, fx, rim, clap, hats ('X' accent, 'o' open hat)
    "forest":   ["X...X...X...X...", ".xxx.xxx.xxx.xxx", "x.xxx.x..xx.x.xx", "..........x....x", "............x...", "xxXxxxXxxxXxxxXo"],
    "swamp":    ["X...X...X...X...", ".xxx.xxx.xxx.xxx", "xx.x.xx.x.xx.x.x", "..........x.....", "............x...", "xXxxxXxxxXxxxXxx"],
    "dark":     ["X...X...X...X...", ".xxx.xxx.xxx.xxx", "xxx.xx.xxx.xx.xx", "......x...x....x", "............x...", "xxxXxxxXxxxXxxoX"],
    "twilight": ["X...X...X...X...", ".xxx.xxx.xxx.xxx", "x..xx.x.x..xx.x.", "..........x....x", "............x...", "xxXxxxXxxxXxxxXx"],
}
# the stress groove of bank_common, for this bank: every 16th on the FX,
# accented rim and clap on the kick, open hats on the off beats
bc.STRESS = ["X...X...X...X...", ".xxx.xxx.xxx.xxx", "xXxxxXxxxXxxxXxx", "..x.X.x...x.X.x.", "....X.......X..x",
             "xxoxxxoxxxoxxxox"]
# and the busy groove the other banks are checked with, in case a player
# takes a psy kit there
bc.EXTRA_STRESS = [["X...X...X...X...", ".xxx.xxx.xxx.xxx", "x.x..x.x..x.x..x", "....X.......X...", "....x.......x..x",
                    "xxoxxxoxxxoxxxox"]]
SCALES = {k: v for k, v in mk.SCALES.items() if k in ("minor", "phrygian", "hijaz")}
THEME_SCALES = {"forest": ["minor", "phrygian"], "swamp": ["phrygian", "minor"], "dark": ["phrygian", "hijaz"],
                "twilight": ["phrygian", "minor"]}
ROOTS = list(range(KICK_RANGE[0] % 12, KICK_RANGE[1] % 12 + 1))     # F# G G# A A# B

NAMES = ["Mycel", "Hypha", "Sporal", "Lichn", "Mosswd", "Peat", "Humus", "Loam", "Bracken", "Thicket",
         "Hazel", "Alder", "Rowan", "Yew", "Hemlok", "Spruce", "Larch", "Juniper", "Mistle", "Bramble",
         "Burdock", "Henbane", "Belldon", "Datura", "Wolfsb", "Hellbr", "Fungal", "Puffbl", "Morel", "Amanit",
         "Psilo", "Truffle", "Rootsy", "Undrwd", "Deepwd", "Taiga", "Wildwd", "Elfwd", "Barrow", "Cairn",
         "Dolmen", "Menhir", "Ogham", "Druid", "Seidr", "Galdr", "Wyrd", "Norn", "Huldra", "Leshy",
         "Kikimr", "Vodyan", "Rusalk", "Domovy", "Bolotn", "Upyr", "Navka", "Mavka", "Likho", "Koshch",
         "Bayun", "Chort", "Bogart", "Bogle", "Wisp", "Kelpie", "Grendl", "Wendig", "Golem", "Revenan",
         "Lich", "Banshe", "Dybbuk", "Incub", "Succub", "Strigo", "Lamia", "Harpy", "Gorgon", "Hydra",
         "Kraken", "Leviat", "Behemo", "Abaddn", "Azazel", "Belial", "Moloch", "Baphom", "Lilith", "Samael",
         "Nyx", "Erebus", "Tartar", "Styx", "Lethe", "Acheron", "Cocyt", "Hades", "Orcus", "Mictln",
         "Xibalb", "Naraka", "Yomi", "Duat", "Sheol", "Gehenn", "Limbo", "Purgat", "Ossuar", "Cataco",
         "Sepulc", "Morgue", "Gallow", "Pyre", "Shroud", "Coffin", "Hearse", "Requie", "Vesper", "Matins",
         "Lauds", "Compln", "Noctrn", "Midnit", "Witchr", "Sabbat", "Samhan", "Walpur"]
bc.check_names(FAM, NAMES)


# =============================================================================
# kit
# =============================================================================
def tune_root(kit, ch, meta, lo, hi):
    """put a voice on the root of the key inside [lo, hi] (exact: fine tune)"""
    if meta["f0"] <= 0:
        return None
    c = kit.ch[ch]
    cur = mk.hz_to_midi(meta["f0"])
    tgt = mk.nearest_scale(cur, kit.key[0], [0], lo, hi)
    shift = round(tgt - cur)
    frac = (tgt - cur) - shift
    old = c.s("tune")
    c.set(tune=old + shift, fine=clamp(64 + frac * 100))
    return old, tgt


NO_SH = ("Dec", "MDc", "SwD", "Dmp", "Opn", "Tim")     # decay-like: random values would cut the texture short


def sh_params(c):
    no = NO_SH + (("FB",) if c.engine == "Cmb" else ())   # the comb's feedback is its length
    return [p for p in mk.engine_params(c) if p["short"] not in no]


def setup_movement(rng, kit, level):
    bpm = kit.bpm
    # the pump: the bass ducks on every kick (saw up retriggered by channel 1)
    kit.lfo_mod(1, mod_dest(1, "VOL"), r(rng, 12, 24), wave="sup", freq=bc.pump_freq(bpm, 1.0), retrig=1)
    kit.notes.append("pump")
    # the bass growl: a filter envelope from the clap channel's LFO,
    # restarted by every bass hit
    kit.lfo_mod(4, mod_dest(1, "FILT_FREQ"), r(rng, 18, 34), wave="xdn", freq=bc.lfo_param(u(rng, 2.5, 4.5)),
                retrig=2, target_ch=1)
    kit.notes.append("growl")
    fx = kit.ch[2]
    # fx: strong S&H on the timbre, and on the filter or a filter envelope
    prm = sh_params(fx)
    if prm:
        d = rng.choice(prm)
        kit.lfo_mod(2, mod_dest(2, engine_slot=d["slot"]), r(rng, 25, 50), wave="rnd", freq=r(rng, 55, 80))
    if any(k in fx.arch for k in FILTER_ENV):
        kit.lfo_mod(3, mod_dest(2, "FILT_FREQ"), r(rng, 30, 55), wave="xdn", freq=bc.lfo_param(u(rng, 1.2, 2.5)),
                    retrig=3, target_ch=2)
        kit.notes.append("acid" if "acid" in fx.arch else "quack")
    else:
        kit.lfo_mod(3, mod_dest(2, "FILT_FREQ"), r(rng, 20, 40), wave="rnd", freq=r(rng, 55, 80), target_ch=2)
    if prm and len(prm) > 1 and rng.random() < 0.6:
        d2 = rng.choice([p for p in prm if p != d])
        kit.lfo_mod(5, mod_dest(2, engine_slot=d2["slot"]), r(rng, 15, 35), wave=pick(rng, "rnd", "tri"),
                    freq=r(rng, 30, 60), target_ch=2)
    if kit.theme == "dark":
        fx.set(bits=max(fx.s("bits"), r(rng, 15, 45)))
    # rim: accent to drive (hats stay as they are: an accent on their filter
    # makes them bright)
    if rng.random() < 0.5:
        kit.mod(3, 11 + 3, r(rng, 10, 22), mod_dest(3, "DRIVE"))


def stereo(kit, rng):
    side = pick(rng, -1, 1)
    kit.ch[0].set(pan=64)
    kit.ch[1].set(pan=64)                                  # bass: centre
    kit.ch[2].set(pan=64 - side * r(rng, 8, 22))
    kit.ch[3].set(pan=64 + side * r(rng, 8, 18))
    kit.ch[4].set(pan=64 + r(rng, -6, 6))
    kit.ch[5].set(pan=64 - side * r(rng, 6, 14))


def build_kit(rng, i):
    theme = THEME_ORDER[i % len(THEME_ORDER)]
    bpm = r(rng, *mk.THEMES[theme][0])
    level = mk.THEMES[theme][2]
    kit = bc.new_kit(FAM, NAMES[i], FAM, theme, bpm)
    src = [FAM, FAM, FAM + theme, FAM, FAM, FAM]
    voices, _ = bc.choose_voices(rng, POOLS, src)
    kit.ch = [c for c, _ in voices]
    metas = [m for _, m in voices]
    if kit.ch[0].s("filt_type") == 0:
        kit.ch[0].hp(20)                                  # an asymmetric kick on every beat adds up to DC
    scale = rng.choice(THEME_SCALES[theme])
    kit.key = (rng.choice(ROOTS), SCALES[scale])
    kit.keyname = mk.NOTE_NAMES[kit.key[0]] + " " + scale
    # kick and bass on the root (kick body at 45-62 Hz); the rest by make_kits
    masked = [dict(m) for m in metas]
    masked[0]["f0"] = masked[1]["f0"] = 0
    kit.tuned = mk.tune_voices(kit, masked, rng)
    t = tune_root(kit, 0, metas[0], *KICK_RANGE)
    if t:
        kit.tuned[0] = t
    kit.bass = tune_root(kit, 1, metas[1], *BASS_RANGE)
    stereo(kit, rng)
    setup_movement(rng, kit, level)
    mk.setup_fx(rng, kit, level)
    if kit.fx["type"] in ("del", "glt"):
        kit.ch[2].set(out="fx")                           # the textures into delay / glitch
    if kit.ch[1].s("out") == mk.OUTS["fx"] and kit.fx["type"] != "cmp":
        kit.ch[1].set(out="st1")                          # no delay / glitch / drive on the bass
    return kit


BASS_LOUD = (-4.0, -2.0)    # bass single hit re kick (dB)
BASS_DRIVE_MAX = 70


def bass_level(kit, path):
    """the groove guard may pull a rolling bass under its target: bring it
    back to -2..-4 dB re kick (volume first, then saturation)"""
    for _ in range(6):
        kit.write(path)
        m = analyse(mk.RENDER, path, with_features=True)
        if "feat" not in m[0] or "feat" not in m[1]:
            return
        rel = m[1]["feat"]["loud"] - m[0]["feat"]["loud"]
        if BASS_LOUD[0] <= rel <= BASS_LOUD[1]:
            return
        c = kit.ch[1]
        err = -3.0 - rel
        want = c.s("vol") * 10 ** (err / 20)
        if want <= 127:
            c.set(vol=max(8, want))
        else:
            d0 = c.s("drive")
            need = mk.drive_gain(d0) * want / 127
            c.set(vol=127, drive=min(BASS_DRIVE_MAX, max(d0, mk.drive_for(need))))
            if d0 >= BASS_DRIVE_MAX:
                return


def level_kit(kit, path):
    """bass level and mastering together: the pump adds to the bass volume,
    so scaling the whole kit doesn't keep the bass in proportion; master,
    then put the bass back, until both hold"""
    for _ in range(4):
        bass_level(kit, path)
        bc.clean_master(kit, path)
        kit.write(path)
        m = analyse(mk.RENDER, path, with_features=True)
        if "feat" in m[0] and "feat" in m[1] and \
                BASS_LOUD[0] - 0.3 <= m[1]["feat"]["loud"] - m[0]["feat"]["loud"] <= BASS_LOUD[1] + 0.3:
            return


BASS_TOL = 0.2     # semitones


def bass_error(kit, path):
    """pitch of the bass against its target note. A short note doesn't show
    its pitch exactly, so it is measured as a long note: the same voice with
    a long amp EG and engine decay, open filter, without modulation."""
    if kit.bass is None:
        return None
    c = kit.ch[1].copy()
    c.set(aeg_mode="ad", attack=0, decay=aeg(0.8), slope=40)
    for k in ("Dec", "Dmp"):
        if mk.has(c.engine, k):
            c.p(**{k: 110})
    probe = mk.Kit("PITCH", "", "", 120)
    probe.ch = [mk.Channel("GND").set(vol=0), c] + [mk.Channel("GND").set(vol=0)] * 4
    probe.write(path + ".pitch")
    m = analyse(mk.RENDER, path + ".pitch", with_features=True)
    os.unlink(path + ".pitch")
    f0 = m[1]["feat"]["f0"] if "feat" in m[1] else 0
    if f0 <= 0:
        return None
    return mk.hz_to_midi(f0) - kit.bass[1]


def after_retune(kit, path, rng):
    """the bass must sit on the root: measure, correct tune and fine, or take
    another pool bass until one does"""
    pool = POOLS[FAM]["perc"]
    tried = 0
    while True:
        err = bass_error(kit, path)
        for _ in range(3):
            if err is None or abs(err) <= BASS_TOL or abs(err) > 3:
                break
            c = kit.ch[1]
            shift = round(err)
            c.set(tune=c.s("tune") - shift, fine=clamp(c.s("fine") - (err - shift) * 100))
            err = bass_error(kit, path)
        if err is not None and abs(err) <= BASS_TOL:
            kit.extra = dict(bass_err=round(err, 3), bass_arch=kit.ch[1].arch)
            return 0
        tried += 1
        if tried > 12:
            print(f"  {kit.name}: bass not in key ({err})", flush=True)
            kit.extra = dict(bass_err=err, bass_arch=kit.ch[1].arch)
            return 1
        # another bass: keep the strip settings of this kit (pan, out, LFO)
        c, pen, m = pool[rng.randrange(len(pool))]
        old = kit.ch[1]
        new = c.copy()
        for k in ("PAN", "OUT", "LFO_WAVE", "LFO_FREQ", "LFO_RETRIG", "LFO_OFFSET"):
            new.block[mk.L[k]] = old.block[mk.L[k]]
        kit.ch[1] = new
        kit.bass = tune_root(kit, 1, m, *BASS_RANGE)


POOLS = None


def main():
    global POOLS
    if os.environ.get("PROBE"):
        role = os.environ["PROBE"]
        archs = ARCH_FX[role] if role in ARCH_FX else ARCH_PS[role]
        bc.probe(archs, "fx" if role in ARCH_FX else role)
        return
    POOLS = mk.build_pools(seed="psy3v2")
    bc.filter_pools(POOLS, POOL_MAX_PENALTY)
    bc.run_bank("psy3v2", FAM, BANK, b"PSY     ", build_kit, after_retune, level_kit)


if __name__ == "__main__":
    main()
