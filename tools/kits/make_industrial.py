#!/usr/bin/env python3
"""Build the SHARD industrial bank (128 kits) with the machinery of make_kits.py.

    python3 tools/kits/make_industrial.py <shard_render> <out dir> [bank number]

Writes <out dir>/shard/prjNN/*.snd and prj.nfo (bank 04 by default) and
<out dir>/bank.json. No demo WAVs.

Hard industrial, 135-150 BPM. Channel roles in this bank
    1 kick     overdriven: engine drive, strip drive, distorted FM
    2 rumble   low droning tail on the off beats through a resonant low pass
               and drive, tuned to the key, ducked by the kick (as TECHNO)
    3 metal    metal hits and noise: FM metal, combs, ring clusters, crushed
               noise, scraping particles, glitch
    4 snare    hard, driven
    5 clap
    6 hats     closed hat, trigger 7 = open hat

Voices come mostly from the SHARD engines; the original LXR voices are a
small share of the pools (bank_common.LXR_SHARE).

SPDX-License-Identifier: GPL-3.0-only
"""
import os
import sys

if len(sys.argv) < 3:
    sys.exit(__doc__)
BANK = int(sys.argv[3]) if len(sys.argv) > 3 else 4
sys.argv = sys.argv[:3]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_kits as mk  # noqa: E402
import bank_common as bc  # noqa: E402
from make_kits import mk as make, tp, aeg, ff, r, u, pick, mod_dest  # noqa: E402

FAM = "IN"


# =============================================================================
# archetypes
# =============================================================================
# ---------------------------------------------------------------- kick
def in_k_abd(g):
    return make("aBD", r(g, 29, 34), Ton=r(g, 40, 80), Dec=r(g, 30, 55), AFM=r(g, 50, 100), SFM=r(g, 30, 80),
                Drv=r(g, 90, 127)).set(drive=r(g, 20, 60))


def in_k_tbd(g):
    return make("tBD", r(g, 29, 33), Swp=r(g, 45, 65), SwD=tp(u(g, .012, .03), .002, .25), Dec=tp(u(g, .35, .6), .04, 3),
                Hld=r(g, 10, 35), Clk=r(g, 50, 100), Drv=r(g, 90, 127)).set(drive=r(g, 10, 50))


def in_k_sbd(g):
    return make("sBD", r(g, 29, 34), Ton=r(g, 50, 90), Dec=r(g, 30, 50), Drt=r(g, 70, 127), FMA=r(g, 50, 110),
                FMD=r(g, 15, 40)).set(drive=r(g, 20, 50))


def in_k_gnd(g):
    return make("GND", r(g, 30, 35), Wav=pick(g, "Sin", "Tri"), Swp=64 + r(g, 35, 60),
                SwD=tp(u(g, .01, .03), .002, 1.0)).set(aeg_mode="ad", attack=0, decay=aeg(u(g, .3, .5)),
                                                         slope=r(g, 30, 50), drive=r(g, 60, 100))


def in_k_efm(g):
    return make("EFM", r(g, 28, 33), Rat=pick(g, "1", "0.5"), Mod=r(g, 30, 60), MDc=tp(u(g, .006, .02), .003, 1.5),
                FB=r(g, 40, 90), Swp=r(g, 80, 110), SwD=tp(u(g, .01, .03), .002, .3), Dec=tp(u(g, .3, .55), .02, 3),
                Noi=r(g, 0, 15)).set(drive=r(g, 30, 60))


def in_k_zap(g):
    return make("Zap", r(g, 24, 30), Dep=r(g, 50, 80), Tim=tp(u(g, .005, .02), .0005, .12), FB=r(g, 20, 50),
                Dec=tp(u(g, .3, .55), .005, 1.0), Dir="Dwn").set(drive=r(g, 40, 80))


def in_k_crs(g):
    return mk.k_crs_fm(g).set(drive=r(g, 60, 95))


ARCH_K = [in_k_abd, in_k_tbd, in_k_sbd, in_k_gnd, in_k_efm, in_k_zap, in_k_crs, bc.lxr_kick_fm]


# ---------------------------------------------------------------- rumble
def in_r_crs(g):
    c = make("Crs", r(g, 30, 40), Src=pick(g, "Saw", "Sqr", "FM"), Rat=r(g, 0, 30), Bit=r(g, 0, 40), Jit=r(g, 0, 15),
             Dec=tp(u(g, .4, .8), .005, 2.0), Glt=0)
    return bc._rumble(c, g, (120, 380)).set(aeg_mode="ad", attack=r(g, 3, 10), decay=aeg(u(g, .22, .4)),
                                            slope=r(g, 25, 45))


def in_r_efm(g):
    c = make("EFM", r(g, 30, 40), Rat=pick(g, "0.5", "1"), Mod=r(g, 30, 70), MDc=tp(u(g, .1, .4), .003, 1.5),
             FB=r(g, 40, 90), Swp=0, SwD=0, Dec=tp(u(g, .4, .8), .02, 3), Noi=0)
    return bc._rumble(c, g, (130, 400)).set(aeg_mode="ad", attack=r(g, 3, 10), decay=aeg(u(g, .22, .38)),
                                            slope=r(g, 25, 45))


def in_r_gnd(g):
    c = make("GND", r(g, 30, 40), Wav=pick(g, "Saw", "Sqr"), Swp=64 - r(g, 0, 10), SwD=tp(u(g, .1, .4), .002, 1))
    return bc._rumble(c, g, (110, 320)).set(aeg_mode="ad", attack=r(g, 3, 10), decay=aeg(u(g, .22, .38)),
                                            slope=r(g, 25, 45))


ARCH_R = [bc.r_abd_tail, bc.r_trx_tail, bc.r_str_low, bc.r_mdl_low, bc.r_gnd_thump, in_r_crs, in_r_efm, in_r_gnd]


# ---------------------------------------------------------------- metal and noise
def in_f_gnd_noise(g):
    return make("GND", r(g, 60, 80), Wav="Noi", Swp=64, SwD=0).set(
        filt_type="bp", filt_freq=ff(u(g, 900, 4000)), filt_reso=r(g, 40, 90), aeg_mode="ad", attack=0,
        decay=aeg(u(g, .06, .16)), slope=r(g, 25, 40), bits=r(g, 30, 80))


def in_f_prt_scrape(g):
    return make("Prt", r(g, 80, 100), Den=r(g, 80, 127), Res=r(g, 20, 70), Spr=r(g, 60, 127)).gate(
        u(g, .08, .2)).hp(u(g, 600, 1500))


def in_f_crs_noise(g):
    return make("Crs", r(g, 60, 84), Src="Noi", Rat=r(g, 30, 90), Bit=r(g, 50, 110), Jit=r(g, 30, 100),
                Dec=tp(u(g, .08, .18), .005, 2.0), Glt=r(g, 30, 100)).hp(u(g, 400, 900))


def in_f_efm_anvil(g):
    """inharmonic FM through a low pass: a struck plate rather than a bell"""
    return make("EFM", r(g, 55, 72), Rat=pick(g, "5.2", "7", "3.5", "2.7", " 11"), Mod=r(g, 70, 120),
                MDc=tp(u(g, .01, .05), .003, 1.5), FB=r(g, 40, 100), Swp=r(g, 0, 30), SwD=tp(u(g, .005, .02), .002, .3),
                Dec=tp(u(g, .1, .25), .02, 3), Noi=r(g, 10, 50)).set(
        filt_type="lp", filt_freq=ff(u(g, 3000, 7000)), filt_reso=r(g, 10, 40), drive=r(g, 10, 40))


ARCH_F = [mk.f_efm_metal, in_f_efm_anvil, mk.f_cmb_metal, mk.f_rng_metal, mk.f_crs_glitch, mk.f_gnd_sh,
          in_f_gnd_noise, in_f_prt_scrape, in_f_crs_noise, bc.lxr_cym_metal]


# ---------------------------------------------------------------- snare
def in_s_tsd(g):
    return make("tSD", r(g, 52, 60), Bdy=r(g, 80, 127), Snp=r(g, 80, 127), Dec=tp(u(g, .08, .15), .02, .8),
                NDc=tp(u(g, .12, .25), .02, 1), Swp=r(g, 30, 60), NTn=r(g, 30, 70)).set(
        drive=r(g, 40, 80), filt_type="lp", filt_freq=ff(u(g, 7000, 10000)), filt_reso=r(g, 0, 20))


def in_s_asd(g):
    return mk.s_asd_snap(g).set(drive=r(g, 40, 80))


def in_s_crs(g):
    return mk.s_crs(g).set(drive=r(g, 30, 70))


ARCH_S = [in_s_tsd, in_s_asd, in_s_crs, mk.s_cmb, mk.s_crs_fm, mk.s_efm, mk.s_byt, bc.lxr_snare_hard]
ARCH_C = [mk.c_trx, mk.c_crs, mk.c_spray, mk.c_cmb, mk.c_pl, bc.lxr_clap]
ARCH_H = [mk.h_trx, mk.h_trx_dark, mk.h_crs, mk.h_rng, mk.h_byt, mk.h_phh_ring, bc.lxr_hat]

ARCH_IN = dict(kick=ARCH_K, perc=ARCH_R, fx=ARCH_F, snare=ARCH_S, clap=ARCH_C, hats=ARCH_H)

# =============================================================================
# role targets
# =============================================================================
#             kick  rumb  metal snare clap  hats  open
mk.RING_MAX = [0.65, 0.80, 0.60, 0.38, 0.45, 0.16, 0.62]
mk.RING_MIN = [0.20, 0.15, 0.04, 0.06, 0.06, 0.02, 0.12]
mk.HF_MAX = [0.16, 0.08, 0.40, 0.34, 0.38, 0.16, 0.55]
mk.CREST_MAX.update(perc=12, fx=16)
mk.AVAIL_MIN.update(perc=-26, fx=-30)
mk.POOL_N = {"kick": 120, "perc": 120, "fx": 140, "snare": 120, "clap": 110, "hats": 90}
mk.POOL_KEEP = 110       # filter_pools keeps the best 64, spread over the engines
mk.POOL_PER_ARCH = 18
mk.ARCH = {FAM: ARCH_IN}
POOL_MAX_PENALTY = 3.0
_role_penalty = mk.role_penalty


def role_penalty(role, m, alt=None, vol=100):
    if role not in ("kick", "perc", "fx"):
        return _role_penalty(role, m, alt, vol)
    f = m["feat"]
    b = f["bands"]
    pen = bc.base_penalty(role, m, vol)
    fq, lvl, prom = m["tone"]
    sl = b["sub"] + b["low"]
    if role == "kick":                                  # overdriven: some grit above the body
        if lvl > mk.TONE_LEVEL and prom > mk.TONE_PROM:
            pen += 5.0
        pen += mk.out_of(sl, 0.5, 1.0, 0.05)
        pen += mk.out_of(f["centroid"], 45, 700, 60)
        pen += max(0.0, f["attack"] - 9) / 2
        pen += max(0.0, b["himid"] - 0.12) / 0.02
        pen += mk.out_of(f["f0"], 38, 80, 6)
        pen += max(0.0, 3 - m["punch"]) / 2
        pen += mk.out_of(b["lowmid"] + b["mid"], 0.03, 0.4, 0.02)
    elif role == "perc":                                # rumble
        pen += bc.rumble_penalty(m)
    else:                                               # metal / noise: no low end, no whistle
        pen += bc.out_of_whistle(fq, lvl, prom, 1500)
        pen += max(0.0, sl - 0.06) / 0.03
        pen += mk.out_of(f["centroid"], 500, 9500, 400)
        pen += max(0.0, b["air"] - 0.15) / 0.02
        pen += max(0.0, f["harsh"] - 0.7) / 0.05
        pen -= min(f["flux"], 0.6) * 3
    return pen


mk.role_penalty = role_penalty


def problems(m):
    """make_kits.problems, but low pitched rumble tails are allowed"""
    bad = []
    for k in range(7):
        c = m[k]
        if c["peak"] < 1e-4:
            continue
        why = []
        if c["ring"] > mk.RING_MAX[k]:
            why.append(f"ring {c['ring']:.2f}")
        elif c["ring"] < mk.RING_MIN[k] * 0.7:
            why.append(f"short {c['ring']:.2f}")
        if c["hf"] > mk.HF_MAX[k]:
            why.append(f"hf {c['hf']:.2f}")
        f, lvl, prom = c["tone"]
        if k < 6 and lvl > mk.TONE_LEVEL and prom > mk.TONE_PROM:
            why.append(f"tone {f:.0f}Hz {lvl:.0f}dB")
        if why:
            bad.append((k, why))
    return bad


mk.problems = problems

# single hit loudness re kick, loudest in the groove re kick
mk.LOUD_TARGET = [0.0, -7.0, -11.0, -4.0, -5.0, -15.0]
mk.GROOVE_MAX = [0.0, -3.0, -6.0, 0.0, -1.0, -5.0]
mk.MAKEUP_MAX = [20, 40, 30, 40, 40, 24]
mk.CLIP_MAX = [0, 30, 40, 55, 55, 30]

# =============================================================================
# themes and grooves
# =============================================================================
mk.THEMES = {
    #             bpm range    fx weights                         movement
    "ironworks": ((135, 140), {"drv": 4, "cmp": 1}, 1),
    "noisewall": ((140, 146), {"drv": 3, "glt": 2}, 2),
    "ritual":    ((135, 142), {"del": 3, "drv": 1}, 2),
    "assembly":  ((138, 144), {"cmp": 3, "drv": 2}, 1),
    "voltage":   ((142, 150), {"glt": 3, "drv": 2}, 3),
    "furnace":   ((140, 148), {"drv": 5}, 1),
    "concrete":  ((136, 142), {"cmp": 2, "del": 2}, 2),
    "corrosion": ((144, 150), {"glt": 2, "drv": 2, "del": 1}, 3),
}
HARD_DRIVE = ("ironworks", "noisewall", "furnace", "voltage")
THEME_ORDER = list(mk.THEMES)
mk.GROOVES = {   # kick, rumble, metal, snare, clap, hats
    "ironworks": ["X...X...X...X...", "..x...x...x...x.", "x.....x...x.....", "....X.......X...", "....x.......x...", "x.x.x.x.x.x.x.xo"],
    "noisewall": ["X...X...X..xX...", ".x.x.x.x.x.x.x.x", "x.x.x.x.x.x.x.x.", "....X.......X..x", "....x.......x...", "xxxxxxxxxxxxxxxx"],
    "ritual":    ["X...X...X...X...", "..xx..xx..xx..xx", "x.......x.......", "......x.......x.", "............x...", "..o...o...o...o."],
    "assembly":  ["X...X...X...X...", "..x...x...x...x.", "...x..x....x..x.", "....X.......X...", "....x.......x...", "xxoxxxoxxxoxxxox"],
    "voltage":   ["X..xX...X..xX.x.", ".x.x.x.x.x.x.x.x", "r...x..r..x...x.", "....X..x....X...", "....x.......x...", "xxrxxxoxxxrxxxox"],
    "furnace":   ["X...X...X...X...", ".xx..xx..xx..xx.", "x...x...x...x...", "....X.......X...", "....x.......x...", "x.xox.xox.xox.xo"],
    "concrete":  ["X...X...X...X...", "..x...x...x..xx.", "x.......x.....x.", "..x.......x.....", "....x.......x...", "x.x.x.o.x.x.x.o."],
    "corrosion": ["X..xX...X...X..x", ".x.x.x.x.x.x.x.x", "x..r..x...r..x..", "....X..x...rX...", "....x.......x...", "xx.xxrx.xo.xxrxo"],
}
SCALES = {k: v for k, v in mk.SCALES.items() if k in ("minor", "phrygian", "hijaz")}

NAMES = ["Scrap", "Rebar", "Sheet", "Flange", "Bracket", "Chisel", "Hammer", "Mallet", "Pliers", "Wrench",
         "Saw", "Grindr", "Drill", "Press", "Stamp", "Punch", "Shear", "Bender", "Roller", "Hoist",
         "Pulley", "Chain", "Hook", "Gear", "Cog", "Ratchet", "Spring", "Valve", "Gasket", "Nozzle",
         "Hose", "Pipe", "Duct", "Flue", "Stack", "Chimney", "Soot", "Slag", "Scoria", "Clinker",
         "Coke", "Tar", "Pitch", "Oil", "Grease", "Sludge", "Acid", "Lye", "Bleach", "Toxin",
         "Fume", "Smog", "Haze", "Dust", "Grit", "Gravel", "Rubble", "Ruin", "Wreck", "Debris",
         "Shrapnl", "Bullet", "Casing", "Shell", "Siren", "Alarm", "Klaxon", "Horn", "Buzzer", "Bell",
         "Gong", "Clang", "Clank", "Thud", "Crash", "Smash", "Crush", "Grind", "Shred", "Rip",
         "Tear", "Split", "Crack", "Snap", "Break", "Burst", "Rupture", "Erode", "Decay", "Oxide",
         "Patina", "Verdig", "Pitted", "Scorch", "Burn", "Weldr", "Torch", "Spark", "Flare", "Glare",
         "Static", "Hum", "Drone", "Throb", "Pound", "Stomp", "March", "Drill2", "Order", "Ritual",
         "Cult", "Relic", "Altar", "Monk", "Chant", "Dirge", "Requim", "Tomb", "Vault", "Bunker",
         "Barrak", "Hangar", "Silo", "Dock", "Gantry", "Crane", "Rig", "Pylon"]
bc.check_names(FAM, NAMES)


# =============================================================================
# kit
# =============================================================================
def setup_movement(rng, kit, level):
    # the pump: rumble (and sometimes metal) duck on every kick
    kit.lfo_mod(1, mod_dest(1, "VOL"), r(rng, 22, 38), wave="sup", freq=bc.pump_freq(kit.bpm), retrig=1)
    kit.notes.append("pump")
    # metal: per hit S&H on its timbre
    prm = mk.engine_params(kit.ch[2])
    if prm:
        d = rng.choice(prm)
        kit.lfo_mod(2, mod_dest(2, engine_slot=d["slot"]), r(rng, 12, 30 + 5 * level), wave="rnd",
                    freq=r(rng, 50, 80))
    # rumble breathes (LFO of the clap channel)
    if rng.random() < 0.4 + 0.2 * level:
        kit.lfo_mod(4, mod_dest(1, "FILT_FREQ"), r(rng, 8, 18), wave=pick(rng, "tri", "sin"), freq=r(rng, 10, 18),
                    target_ch=1)
    if level >= 2:
        src = kit.lfo_free(rng, avoid=(0,))
        if src is not None:
            kit.lfo_mod(src, mod_dest(2, "PAN"), r(rng, 25, 55), wave=pick(rng, "sqr", "rnd", "tri"),
                        freq=r(rng, 30, 55), target_ch=2)
    # hats: accents open the high pass; snare: accent to drive
    kit.mod(5, 11 + 5, r(rng, 8, 18), mod_dest(5, "FILT_FREQ"))
    if rng.random() < 0.6:
        kit.mod(3, 11 + 3, r(rng, 15, 30), mod_dest(3, "DRIVE"))
    # crushed metal
    if level >= 2 or rng.random() < 0.4:
        kit.ch[2].set(bits=max(kit.ch[2].s("bits"), r(rng, 20, 60)))
        if rng.random() < 0.5:
            kit.ch[2].set(srate=r(rng, 60, 110))
    if level >= 3 and kit.ch[4].s("repeat") == 0 and rng.random() < 0.5:
        kit.ch[4].set(repeat=r(rng, 2, 4), attack=r(rng, 1, 4))


def stereo(kit, rng):
    side = pick(rng, -1, 1)
    kit.ch[0].set(pan=64)
    kit.ch[1].set(pan=64 + side * r(rng, 0, 6))
    kit.ch[2].set(pan=64 - side * r(rng, 14, 30))
    kit.ch[3].set(pan=r(rng, 62, 66))
    kit.ch[4].set(pan=64 + side * r(rng, 0, 8))
    kit.ch[5].set(pan=64 - side * r(rng, 6, 14))


def build_kit(rng, i):
    theme = THEME_ORDER[i % len(THEME_ORDER)]
    bpm = r(rng, *mk.THEMES[theme][0])
    level = mk.THEMES[theme][2]
    kit = bc.new_kit(FAM, NAMES[i], FAM, theme, bpm)
    voices, _ = bc.choose_voices(rng, POOLS, [FAM] * 6)
    kit.ch = [c for c, _ in voices]
    metas = [m for _, m in voices]
    bc.set_key(kit, rng, SCALES)
    kit.tuned = mk.tune_voices(kit, metas, rng)
    stereo(kit, rng)
    setup_movement(rng, kit, level)
    mk.setup_fx(rng, kit, level)
    f = kit.fx
    if f["type"] == "drv" and theme in HARD_DRIVE:
        # the hard fold / clip of the factory 'torque' theme
        dist = rng.choice([0, 0, 1, 2])
        f.update(drywet=r(rng, 60, 100), dist=dist,
                 p=[r(rng, 55, 95), r(rng, 30, 80) if dist == 0 else 0, r(rng, 50, 85), r(rng, 60, 85)])
    if f["type"] == "del":
        kit.ch[1].set(out="fx")                       # dub-style rumble into the delay
    return kit


POOLS = None


def main():
    global POOLS
    bc.maybe_probe(ARCH_IN)
    POOLS = mk.build_pools(seed="industrial4")
    bc.filter_pools(POOLS, POOL_MAX_PENALTY)
    bc.run_bank("industrial4", FAM, BANK, b"INDSTRL ", build_kit)


if __name__ == "__main__":
    main()
