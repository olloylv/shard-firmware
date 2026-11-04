#!/usr/bin/env python3
"""Build the SHARD psytrance bank (128 kits) with the machinery of make_kits.py.

    python3 tools/kits/make_psy.py <shard_render> <out dir> [bank number]

Writes <out dir>/shard/prjNN/*.snd and prj.nfo (bank 03 by default) and
<out dir>/bank.json. No demo WAVs.

140-158 BPM, four themes of 32 kits: forest, swamp, dark, goa.
Channel roles in this bank
    1 kick     short and dense
    2 bass     the rolling off-beat bass (K-B-B-B): short pitched notes
               through a low pass, tuned exactly to the root of the kit's
               key (measured; voices that don't tune are replaced), ducked
               by the kick like the TECHNO rumble
    3 fx       psychedelic: forest = organic, bubbles, drops, wood;
               swamp = squelch and quack (filter envelopes from a retriggered
               LFO); dark = metal, noise, glitch; goa = melodic, in key
    4 snare    snare / rim
    5 clap
    6 hats     closed hat, trigger 7 = open hat

Voices come mostly from the SHARD engines; the original LXR voices are a
small share of the pools (bank_common.LXR_SHARE).

SPDX-License-Identifier: GPL-3.0-only
"""
import math
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
THEME_ORDER = ["forest", "swamp", "dark", "goa"]


# =============================================================================
# archetypes
# =============================================================================
# ---------------------------------------------------------------- kick
def ps_k_abd(g):
    return make("aBD", r(g, 30, 35), Ton=r(g, 40, 70), Dec=r(g, 18, 32), AFM=r(g, 40, 80), SFM=r(g, 10, 40),
                Drv=r(g, 30, 80))


def ps_k_tbd(g):
    return make("tBD", r(g, 30, 34), Swp=r(g, 50, 70), SwD=tp(u(g, .008, .02), .002, .25), Dec=tp(u(g, .18, .3), .04, 3),
                Hld=r(g, 0, 10), Clk=r(g, 50, 90), Drv=r(g, 30, 70))


def ps_k_gnd(g):
    return make("GND", r(g, 30, 36), Wav="Sin", Swp=64 + r(g, 35, 60), SwD=tp(u(g, .008, .025), .002, 1.0)).set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .18, .28)), slope=r(g, 35, 55), drive=r(g, 20, 50))


def ps_k_efm(g):
    return make("EFM", r(g, 29, 34), Rat=pick(g, "1", "0.5"), Mod=r(g, 20, 45), MDc=tp(u(g, .004, .012), .003, 1.5),
                FB=r(g, 0, 25), Swp=r(g, 80, 110), SwD=tp(u(g, .008, .02), .002, .3), Dec=tp(u(g, .18, .3), .02, 3),
                Noi=r(g, 0, 10))


def ps_k_zap(g):
    return make("Zap", r(g, 25, 31), Dep=r(g, 60, 90), Tim=tp(u(g, .003, .008), .0005, .12), FB=r(g, 0, 15),
                Dec=tp(u(g, .2, .32), .005, 1.0), Dir="Dwn").set(drive=r(g, 20, 50))


ARCH_K = [ps_k_abd, ps_k_tbd, mk.k_trx_tight, ps_k_gnd, ps_k_efm, ps_k_zap, mk.k_abd_punch, bc.lxr_kick_short]


# ---------------------------------------------------------------- bass
def _bass(c, g, lp=(250, 700), t=(.07, .13)):
    """short note through a resonant low pass"""
    return c.set(filt_type="lp", filt_freq=ff(u(g, *lp)), filt_reso=r(g, 15, 60), drive=r(g, 10, 45),
                 aeg_mode="ad", attack=r(g, 0, 2), decay=aeg(u(g, *t)), slope=r(g, 30, 45))


def ps_b_gnd_saw(g):
    return _bass(make("GND", r(g, 33, 45), Wav="Saw", Swp=64, SwD=0), g)


def ps_b_gnd_sqr(g):
    return _bass(make("GND", r(g, 33, 45), Wav="Sqr", Swp=64, SwD=0), g, (200, 600))


def ps_b_crs(g):
    return _bass(make("Crs", r(g, 33, 45), Src=pick(g, "Saw", "Sqr"), Rat=0, Bit=r(g, 0, 12), Jit=0,
                      Dec=tp(u(g, .1, .2), .005, 2.0), Glt=0), g)


def ps_b_efm(g):
    return _bass(make("EFM", r(g, 33, 45), Rat=pick(g, "1", "0.5", "2"), Mod=r(g, 20, 55),
                      MDc=tp(u(g, .01, .04), .003, 1.5), FB=r(g, 0, 30), Swp=0, SwD=0, Dec=tp(u(g, .1, .2), .02, 3),
                      Noi=0), g, (300, 900))


def ps_b_abd(g):
    return _bass(make("aBD", r(g, 36, 46), Ton=r(g, 0, 25), Dec=r(g, 15, 30), AFM=r(g, 0, 20), SFM=r(g, 0, 25),
                      Drv=r(g, 30, 80)), g, (200, 500))


def ps_b_str(g):
    return _bass(make("Str", r(g, 33, 45), Str=r(g, 0, 40), Bri=r(g, 20, 60), Dmp=r(g, 20, 50), Exc=r(g, 40, 100)),
                 g, (300, 800))


def lxr_bass(g):
    return _bass(make("Drm", r(g, 33, 45), Wav=pick(g, "Saw", "Rec"), PDc=r(g, 10, 30), PSl=64, PAm=r(g, 0, 12),
                      FMA=r(g, 0, 25), FMF=64 + pick(g, 0, 12, -12), FMW="Sin", Mod="FM "), g)


ARCH_B = [ps_b_gnd_saw, ps_b_gnd_sqr, ps_b_crs, ps_b_efm, ps_b_abd, ps_b_str, lxr_bass]


# ---------------------------------------------------------------- fx: forest
def ps_f_prt_bubble(g):
    return make("Prt", r(g, 60, 84), Den=r(g, 10, 40), Res=r(g, 60, 110), Spr=r(g, 0, 50)).gate(u(g, .1, .25)).set(
        filt_type="bp", filt_freq=ff(u(g, 600, 2500)), filt_reso=r(g, 10, 40))


def ps_f_mdl_drip(g):
    return make("Mdl", r(g, 70, 88), Str=r(g, 0, 30), Bri=r(g, 60, 100), Dmp=r(g, 10, 30), Exc=r(g, 0, 20)).gate(
        u(g, .08, .18))


def ps_f_zap_drop(g):
    """a short upward sweep: a water drop"""
    return make("Zap", r(g, 60, 80), Dep=r(g, 30, 60), Tim=tp(u(g, .01, .03), .0005, .12), FB=r(g, 0, 20),
                Dec=tp(u(g, .05, .12), .005, 1.0), Dir="Up").hp(u(g, 250, 500))


def ps_f_str_twang(g):
    return make("Str", r(g, 55, 72), Str=r(g, 30, 90), Bri=r(g, 30, 70), Dmp=r(g, 20, 45), Exc=r(g, 0, 40)).gate(
        u(g, .12, .25)).hp(u(g, 200, 400))


def ps_f_byt_bubble(g):
    return make("Byt", r(g, 55, 75), Frm=r(g, 0, 7), A=r(g, 0, 127), B=r(g, 0, 127), Rst=1).gate(u(g, .06, .15)).set(
        filt_type="bp", filt_freq=ff(u(g, 500, 2000)), filt_reso=r(g, 40, 80))


ARCH_FOREST = [mk.f_prt_grain, ps_f_prt_bubble, mk.p_mdl_wood, ps_f_mdl_drip, ps_f_zap_drop, mk.p_cmb_hollow,
               ps_f_str_twang, ps_f_byt_bubble]


# ---------------------------------------------------------------- fx: swamp (quack = arch name)
def _quack(c, g):
    return c.set(filt_type=pick(g, "bp", "lp", "lp"), filt_freq=ff(u(g, 350, 1100)), filt_reso=r(g, 70, 105),
                 aeg_mode="ad", attack=r(g, 0, 3), decay=aeg(u(g, .12, .25)), slope=r(g, 25, 40))


def ps_f_quack_gnd(g):
    return _quack(make("GND", r(g, 45, 62), Wav=pick(g, "Saw", "Sqr"), Swp=64, SwD=0), g)


def ps_f_quack_crs(g):
    return _quack(make("Crs", r(g, 45, 62), Src=pick(g, "Saw", "Sqr"), Rat=r(g, 0, 30), Bit=r(g, 0, 40), Jit=0,
                       Dec=tp(u(g, .2, .4), .005, 2.0), Glt=0), g)


def ps_f_quack_efm(g):
    return _quack(make("EFM", r(g, 45, 62), Rat=pick(g, "2", "3", "1.5"), Mod=r(g, 40, 90),
                       MDc=tp(u(g, .05, .2), .003, 1.5), FB=r(g, 20, 70), Swp=0, SwD=0,
                       Dec=tp(u(g, .2, .4), .02, 3), Noi=0), g)


def ps_f_quack_byt(g):
    return _quack(make("Byt", r(g, 48, 66), Frm=r(g, 0, 7), A=r(g, 0, 127), B=r(g, 0, 127), Rst=1), g)


def ps_f_zap_bloop(g):
    return make("Zap", r(g, 48, 62), Dep=r(g, 30, 60), Tim=tp(u(g, .02, .06), .0005, .12), FB=r(g, 30, 70),
                Dec=tp(u(g, .08, .18), .005, 1.0), Dir=pick(g, "Up", "Bth")).hp(u(g, 200, 400))


def ps_f_mdl_gurgle(g):
    return make("Mdl", r(g, 50, 62), Str=r(g, 20, 70), Bri=r(g, 20, 50), Dmp=r(g, 20, 40), Exc=r(g, 30, 90)).set(
        filt_type="bp", filt_freq=ff(u(g, 400, 1200)), filt_reso=r(g, 40, 80)).gate(u(g, .12, .25))


ARCH_SWAMP = [ps_f_quack_gnd, ps_f_quack_crs, ps_f_quack_efm, ps_f_quack_byt, ps_f_zap_bloop, mk.f_gnd_sh,
              ps_f_mdl_gurgle]


# ---------------------------------------------------------------- fx: dark
def ps_f_prt_scrape(g):
    return make("Prt", r(g, 80, 100), Den=r(g, 80, 127), Res=r(g, 20, 70), Spr=r(g, 60, 127)).gate(
        u(g, .08, .2)).hp(u(g, 600, 1500))


def ps_f_gnd_noise(g):
    return make("GND", r(g, 60, 80), Wav="Noi", Swp=64, SwD=0).set(
        filt_type="bp", filt_freq=ff(u(g, 800, 3000)), filt_reso=r(g, 50, 90), aeg_mode="ad", attack=0,
        decay=aeg(u(g, .06, .15)), slope=r(g, 25, 40), bits=r(g, 20, 60))


def ps_f_efm_dark(g):
    return make("EFM", r(g, 55, 72), Rat=pick(g, "5.2", "7", "3.5", "2.7"), Mod=r(g, 60, 110),
                MDc=tp(u(g, .01, .05), .003, 1.5), FB=r(g, 30, 90), Swp=r(g, 0, 30), SwD=tp(u(g, .005, .02), .002, .3),
                Dec=tp(u(g, .1, .25), .02, 3), Noi=r(g, 0, 30)).set(
        filt_type="lp", filt_freq=ff(u(g, 2500, 6000)), filt_reso=r(g, 10, 50))


ARCH_DARK = [ps_f_efm_dark, mk.f_cmb_metal, mk.f_rng_metal, mk.f_crs_glitch, ps_f_prt_scrape, ps_f_gnd_noise,
             mk.f_gnd_zip, bc.lxr_cym_metal]


# ---------------------------------------------------------------- fx: goa (melodic)
def ps_f_gnd_lead(g):
    return make("GND", r(g, 60, 76), Wav=pick(g, "Saw", "Sqr"), Swp=64, SwD=0).set(
        filt_type="lp", filt_freq=ff(u(g, 1500, 4000)), filt_reso=r(g, 30, 60), aeg_mode="ad", attack=r(g, 0, 3),
        decay=aeg(u(g, .08, .18)), slope=r(g, 25, 40))


def ps_f_efm_pluck(g):
    return make("EFM", r(g, 60, 76), Rat=pick(g, "1", "2", "3"), Mod=r(g, 30, 70), MDc=tp(u(g, .02, .06), .003, 1.5),
                FB=r(g, 0, 30), Swp=0, SwD=0, Dec=tp(u(g, .1, .2), .02, 3), Noi=0).hp(u(g, 200, 400))


def ps_f_crs_arp(g):
    return make("Crs", r(g, 62, 76), Src="Sqr", Rat=r(g, 0, 15), Bit=r(g, 0, 20), Jit=0,
                Dec=tp(u(g, .08, .15), .005, 2.0), Glt=0).hp(u(g, 200, 400))


ARCH_GOA = [mk.p_efm_bell, mk.f_mdl_chime, mk.p_str_pluck, ps_f_gnd_lead, ps_f_efm_pluck, ps_f_crs_arp,
            mk.p_rng_bell, bc.lxr_blip]


# ---------------------------------------------------------------- snare / rim
def s_rim(g):
    return make("tSD", r(g, 62, 74), Bdy=r(g, 90, 127), Snp=r(g, 0, 30), Dec=tp(u(g, .02, .06), .02, .8),
                NDc=tp(u(g, .02, .05), .02, 1), Swp=r(g, 30, 70), NTn=r(g, 80, 120)).hp(u(g, 250, 450))


def s_efm_rim(g):
    return make("EFM", r(g, 64, 76), Rat=pick(g, "2", "3", "3.5"), Mod=r(g, 30, 70), MDc=tp(u(g, .005, .02), .003, 1.5),
                FB=r(g, 0, 30), Swp=r(g, 0, 20), SwD=tp(u(g, .005, .015), .002, .3), Dec=tp(u(g, .05, .1), .02, 3),
                Noi=r(g, 20, 50)).hp(u(g, 250, 450))


ARCH_S = [s_rim, s_efm_rim, mk.p_trx_rim, mk.s_trx_tight, mk.s_asd_snap, mk.s_ssd, mk.s_crs, bc.lxr_snare]
ARCH_C = [mk.c_trx, mk.c_trx_tight, mk.c_pl, mk.c_crs, mk.c_spray, bc.lxr_clap]
ARCH_H = [mk.h_trx, mk.h_phh, mk.h_phh_ring, mk.h_crs, mk.h_rng, mk.h_byt, bc.lxr_hat]

ARCH_PS = dict(kick=ARCH_K, perc=ARCH_B, snare=ARCH_S, clap=ARCH_C, hats=ARCH_H)
ARCH_FX = dict(forest=ARCH_FOREST, swamp=ARCH_SWAMP, dark=ARCH_DARK, goa=ARCH_GOA)

# =============================================================================
# role targets
# =============================================================================
#             kick  bass  fx    snare clap  hats  open
mk.RING_MAX = [0.40, 0.22, 0.60, 0.30, 0.42, 0.12, 0.50]
mk.RING_MIN = [0.12, 0.05, 0.04, 0.03, 0.06, 0.02, 0.12]
mk.HF_MAX = [0.10, 0.04, 0.40, 0.30, 0.36, 0.12, 0.50]
mk.CREST_MAX.update(perc=12, fx=16)
mk.AVAIL_MIN.update(perc=-24, fx=-30, snare=-30)
mk.POOL_N = {"kick": 110, "perc": 140, "fx": 110, "snare": 110, "clap": 110, "hats": 90}
mk.POOL_KEEP = 110       # filter_pools keeps the best 64, spread over the engines
mk.POOL_PER_ARCH = 18
mk.ARCH = {FAM: ARCH_PS, **{FAM + t: {"fx": a} for t, a in ARCH_FX.items()}}
POOL_MAX_PENALTY = 3.0
_role_penalty = mk.role_penalty


def rim_penalty(m, vol):
    """rims are short and mid pitched: scored on their own terms"""
    f = m["feat"]
    b = f["bands"]
    fq, lvl, prom = m["tone"]
    pen = bc.base_penalty("snare", m, vol)
    pen += bc.out_of_whistle(fq, lvl, prom, 1500)
    pen += max(0.0, b["sub"] + b["low"] - 0.03) / 0.02
    pen += mk.out_of(f["centroid"], 500, 4000, 300)
    pen += max(0.0, f["attack"] - 3) / 2
    return pen


def role_penalty(role, m, alt=None, vol=100):
    if role == "snare":
        return min(_role_penalty(role, m, alt, vol), rim_penalty(m, vol))
    if role not in ("perc", "fx"):
        pen = _role_penalty(role, m, alt, vol)
        if role == "kick":
            pen += max(0.0, m["ring"] - 0.32) / 0.04     # psy kicks leave room for the bass
        return pen
    f = m["feat"]
    b = f["bands"]
    pen = bc.base_penalty(role, m, vol)
    fq, lvl, prom = m["tone"]
    sl = b["sub"] + b["low"]
    if role == "perc":                                   # bass: low, pitched, no click
        pen += bc.out_of_whistle(fq, lvl, prom, 500)
        pen += mk.out_of(sl, 0.45, 1.0, 0.04)
        pen += mk.out_of(f["centroid"], 50, 420, 40)
        pen += max(0.0, b["himid"] + b["high"] + b["air"] - 0.05) / 0.01
        pen += mk.out_of(f["f0"], 40, 130, 5)
        pen += max(0.0, 7 - f["tonal"]) / 2            # short notes: the exact pitch is checked per kit
    else:                                                # fx: mid band, no whistle, movement welcome
        pen += bc.out_of_whistle(fq, lvl, prom, 1500)
        pen += max(0.0, sl - 0.15) / 0.03
        pen += mk.out_of(f["centroid"], 250, 7000, 300)
        pen += max(0.0, b["air"] - 0.10) / 0.02
        pen += max(0.0, f["harsh"] - 0.5) / 0.05
        pen -= min(f["flux"], 0.6) * 3
    return pen


mk.role_penalty = role_penalty

# single hit loudness re kick, loudest in the groove re kick
mk.LOUD_TARGET = [0.0, -5.0, -11.0, -6.0, -6.0, -14.0]
mk.GROOVE_MAX = [0.0, 0.0, -6.0, -2.0, -2.0, -4.0]
mk.MAKEUP_MAX = [20, 40, 30, 40, 40, 24]

# =============================================================================
# themes and grooves
# =============================================================================
mk.THEMES = {
    #           bpm range    fx weights                         movement
    "forest":  ((145, 152), {"del": 3, "glt": 1, "cmp": 1}, 3),
    "swamp":   ((140, 148), {"del": 2, "cmp": 2, "drv": 1}, 3),
    "dark":    ((148, 158), {"glt": 3, "drv": 2, "cmp": 1}, 3),
    "goa":     ((140, 146), {"del": 5, "cmp": 1}, 2),
}
mk.GROOVES = {   # kick, bass, fx, snare, clap, hats
    "forest": ["X...X...X...X...", ".xxx.xxx.xxx.xxx", "x..x..x...x.x..x", "......x.......x.", "....x.......x...", "x.ox.xoxx.oxx.ox"],
    "swamp":  ["X...X...X...X...", ".xxx.xxx.xxx.xxx", "..x...x...x..x..", "...x.......x....", "....x.......x...", "xxoxxxoxxxoxxxox"],
    "dark":   ["X...X...X...X...", ".xxx.xxx.xxx.xxx", "x.x..x.xx..x.x..", "..x.......x...x.", "....x.......x...", "xxoxxxoxxxoxxxox"],
    "goa":    ["X...X...X...X...", ".xxx.xxx.xxx.xxx", "x.x.x.x.x.x.x.x.", "....x.......x...", "....x.......x...", "x.o.x.o.x.o.x.o."],
}
ALL_SCALES = dict(mk.SCALES)
THEME_SCALES = {
    "forest": ["minor", "dorian", "phrygian"],
    "swamp": ["phrygian", "minor"],
    "dark": ["phrygian", "minor", "hijaz"],
    "goa": ["hijaz", "phrygian", "minor"],
}

NAMES = ["Fungi", "Spore", "Moss", "Fern", "Lichen", "Myco", "Root", "Bark", "Canopy", "Sap",
         "Thorn", "Vine", "Leaf", "Seed", "Bloom", "Pollen", "Petal", "Hollow", "Grove", "Glade",
         "Cedar", "Pine", "Birch", "Willow", "Oak", "Elder", "Ivy", "Nettle", "Sprout", "Tendrl",
         "Shroom", "Cap", "Bog", "Marsh", "Mire", "Fen", "Swamp", "Toad", "Frog", "Newt",
         "Leech", "Reed", "Algae", "Slime", "Ooze", "Muck", "Silt", "Gator", "Heron", "Murk",
         "Bayou", "Sludge", "Croak", "Gloop", "Squelc", "Fester", "Rot", "Mold", "Damp", "Brine",
         "Abyss", "Void", "Nether", "Crypt", "Raven", "Wraith", "Shade", "Grim", "Hex", "Rune",
         "Omen", "Specter", "Ghoul", "Demon", "Nightm", "Venom", "Fang", "Talon", "Skull", "Bone",
         "Ash", "Ember", "Cinder", "Doom", "Chaos", "Rift", "Vortex", "Eclips", "Umbra", "Pit",
         "Lotus", "Mantra", "Chakra", "Karma", "Shiva", "Ganesh", "Temple", "Mandal", "Sitar", "Tabla",
         "Incens", "Saffrn", "Sun", "Moon", "Star", "Nebula", "Cosmic", "Astral", "Prana", "Yantra",
         "Om", "Nirvan", "Dharma", "Vedic", "Sutra", "Mystic", "Oracle", "Shaman", "Totem", "Spirit",
         "Trance", "Dream", "Vision", "Fractl", "Spiral", "Helix", "Prism", "Kaleid"]
bc.check_names(FAM, NAMES)


# =============================================================================
# kit
# =============================================================================
def tune_bass(kit, meta):
    """bass on the root of the key, nearest octave (exact: fine tune)"""
    if meta["f0"] <= 0:
        return None
    c = kit.ch[1]
    cur = mk.hz_to_midi(meta["f0"])
    tgt = mk.nearest_scale(cur, kit.key[0], [0], int(cur) - 7, int(cur) + 7)
    shift = round(tgt - cur)
    frac = (tgt - cur) - shift
    old = c.s("tune")
    c.set(tune=old + shift, fine=clamp(64 + frac * 100))
    return old, tgt


def setup_movement(rng, kit, level):
    bpm = kit.bpm
    # the pump: the bass ducks on every kick (saw up retriggered by channel 1)
    kit.lfo_mod(1, mod_dest(1, "VOL"), r(rng, 18, 32), wave="sup", freq=bc.pump_freq(bpm, 1.0), retrig=1)
    kit.notes.append("pump")
    # the bass filter rolls slowly over 4 or 8 bars (LFO of the clap channel)
    kit.lfo_mod(4, mod_dest(1, "FILT_FREQ"), r(rng, 6, 16), wave=pick(rng, "tri", "sin"),
                freq=bc.lfo_param(bpm / 60.0 / pick(rng, 16, 32)), target_ch=1)
    fx = kit.ch[2]
    if "quack" in fx.arch:
        # filter envelope: a falling LFO restarted by every fx hit
        kit.lfo_mod(2, mod_dest(2, "FILT_FREQ"), r(rng, 30, 55), wave="xdn", freq=bc.lfo_param(u(rng, 1.5, 3.0)),
                    retrig=3)
        kit.notes.append("quack")
    elif kit.theme == "goa":
        kit.lfo_mod(2, mod_dest(2, "FILT_FREQ"), r(rng, 10, 25), wave=pick(rng, "tri", "sin"),
                    freq=bc.lfo_param(bpm / 60.0 / pick(rng, 4, 8)))
    else:
        prm = mk.engine_params(fx)
        if prm:
            d = rng.choice(prm)
            kit.lfo_mod(2, mod_dest(2, engine_slot=d["slot"]), r(rng, 12, 35), wave="rnd", freq=r(rng, 50, 75))
    # fx wanders in the stereo field
    src = kit.lfo_free(rng, avoid=(0,))
    if src is not None:
        kit.lfo_mod(src, mod_dest(2, "PAN"), r(rng, 25, 55), wave=pick(rng, "tri", "sin", "rnd"),
                    freq=r(rng, 25, 50), target_ch=2)
    if kit.theme == "dark":
        fx.set(bits=max(fx.s("bits"), r(rng, 15, 50)))
    # hats: accents open the high pass; snare: accent to drive
    kit.mod(5, 11 + 5, r(rng, 8, 18), mod_dest(5, "FILT_FREQ"))
    if rng.random() < 0.5:
        kit.mod(3, 11 + 3, r(rng, 12, 25), mod_dest(3, "DRIVE"))


def stereo(kit, rng):
    side = pick(rng, -1, 1)
    kit.ch[0].set(pan=64)
    kit.ch[1].set(pan=64)                                  # bass: centre
    kit.ch[2].set(pan=64 - side * r(rng, 10, 26))
    kit.ch[3].set(pan=64 + side * r(rng, 4, 14))
    kit.ch[4].set(pan=64 + r(rng, -4, 4))
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
    scales = {k: ALL_SCALES[k] for k in THEME_SCALES[theme]}
    bc.set_key(kit, rng, scales)
    # the bass is tuned separately (root only, checked after the retune check)
    masked = [dict(m) for m in metas]
    masked[1]["f0"] = 0
    kit.tuned = mk.tune_voices(kit, masked, rng)
    kit.bass = tune_bass(kit, metas[1])
    stereo(kit, rng)
    setup_movement(rng, kit, level)
    mk.setup_fx(rng, kit, level)
    if kit.ch[1].s("out") == mk.OUTS["fx"] and kit.fx["type"] != "cmp":
        kit.ch[1].set(out="st1")                          # no delay / glitch / drive on the bass
    return kit


BASS_TOL = 0.2     # semitones


def bass_error(kit, path):
    """pitch of the bass against its target note. A short note doesn't show
    its pitch exactly, so it is measured as a long note: the same voice with
    a long amp EG and engine decay, without modulation."""
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
        kit.bass = tune_bass(kit, m)


POOLS = None


def main():
    global POOLS
    if os.environ.get("PROBE"):
        role = os.environ["PROBE"]
        archs = ARCH_FX[role] if role in ARCH_FX else ARCH_PS[role]
        bc.probe(archs, "fx" if role in ARCH_FX else role)
        return
    POOLS = mk.build_pools(seed="psy3")
    # goa: melodic voices first (re-sorted with the tonal rule)
    for t in ARCH_FX:
        items = POOLS[FAM + t]["fx"]
        if t == "goa":
            items = [(c, p + max(0.0, 15 - m["tonal"]) / 3, m) for c, p, m in items]
            items.sort(key=lambda x: x[1])
        POOLS[FAM + t]["fx"] = items
    bc.filter_pools(POOLS, POOL_MAX_PENALTY)
    bc.run_bank("psy3", FAM, BANK, b"PSY     ", build_kit, after_retune)


if __name__ == "__main__":
    main()
