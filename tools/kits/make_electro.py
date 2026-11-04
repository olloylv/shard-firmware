#!/usr/bin/env python3
"""Build the SHARD electro bank (128 kits) with the machinery of make_kits.py.

    python3 tools/kits/make_electro.py <shard_render> <out dir> [bank number]

Writes <out dir>/shard/prjNN/*.snd and prj.nfo (bank 02 by default) and
<out dir>/bank.json. No demo WAVs.

Hard Detroit electro, 128-138 BPM. Channel roles in this bank
    1 kick     808 style: dense, short or medium (aBD tBD sBD GND EFM Zap)
    2 perc     cowbells, toms, blips (EFM Rng tBD aBD GND Zap Crs)
    3 fx       zaps, lasers, beep-beeps (Zap GND EFM Byt Crs)
    4 snare    tight, whip-cracking
    5 clap
    6 hats     closed hat, trigger 7 = open hat

The voices come mostly from the SHARD engines; the original LXR voices
(Drm Snr Hat) are a small share of the pools (bank_common.LXR_SHARE).
Kits are scored, tuned, balanced and mastered like the factory bank.

SPDX-License-Identifier: GPL-3.0-only
"""
import os
import sys

if len(sys.argv) < 3:
    sys.exit(__doc__)
BANK = int(sys.argv[3]) if len(sys.argv) > 3 else 2
sys.argv = sys.argv[:3]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_kits as mk  # noqa: E402
import bank_common as bc  # noqa: E402
from make_kits import mk as make, tp, aeg, ff, r, u, pick, mod_dest  # noqa: E402

FAM = "EL"


# =============================================================================
# archetypes
# =============================================================================
# ---------------------------------------------------------------- kick (808)
def e_k_abd808(g):
    return make("aBD", r(g, 28, 33), Ton=r(g, 15, 45), Dec=r(g, 32, 52), AFM=r(g, 10, 35), SFM=r(g, 5, 30),
                Drv=r(g, 30, 70))


def e_k_abd_short(g):
    return make("aBD", r(g, 30, 35), Ton=r(g, 30, 60), Dec=r(g, 22, 38), AFM=r(g, 30, 70), SFM=r(g, 10, 40),
                Drv=r(g, 30, 70))


def e_k_tbd808(g):
    return make("tBD", r(g, 28, 32), Swp=r(g, 25, 45), SwD=tp(u(g, .02, .05), .002, .25),
                Dec=tp(u(g, .4, .75), .04, 3), Hld=r(g, 0, 15), Clk=r(g, 10, 40), Drv=r(g, 10, 40))


def e_k_zap808(g):
    """a slower Zap sweep is a clean 808 boom"""
    return make("Zap", r(g, 24, 30), Dep=r(g, 30, 55), Tim=tp(u(g, .02, .05), .0005, .12), FB=r(g, 0, 10),
                Dec=tp(u(g, .35, .6), .005, 1.0), Dir="Dwn").set(drive=r(g, 0, 30))


ARCH_K = [e_k_abd808, e_k_abd_short, e_k_tbd808, mk.k_trx_tight, mk.k_sbd, mk.k_gnd, mk.k_efm, e_k_zap808,
          bc.lxr_kick]


# ---------------------------------------------------------------- perc
def e_p_efm_cowbell(g):
    """FM at a fifth (ratio 1.5) through a band pass: the 808 cowbell idea"""
    return make("EFM", r(g, 70, 78), Rat="1.5", Mod=r(g, 25, 55), MDc=tp(u(g, .03, .08), .003, 1.5),
                FB=r(g, 0, 20), Swp=0, SwD=0, Dec=tp(u(g, .08, .16), .02, 3), Noi=0).set(
        filt_type="bp", filt_freq=ff(u(g, 700, 1600)), filt_reso=r(g, 10, 35))


def e_p_rng_cowbell(g):
    return make("Rng", r(g, 60, 68), Spr=r(g, 0, 15), RM=r(g, 0, 25), Ton=r(g, 30, 55), Res=r(g, 30, 60),
                Wav="Sqr").gate(u(g, .08, .16)).set(filt_type="bp", filt_freq=ff(u(g, 800, 1600)), filt_reso=r(g, 5, 30))


def e_p_efm_tom(g):
    return make("EFM", r(g, 45, 58), Rat="1", Mod=r(g, 10, 30), MDc=tp(u(g, .01, .03), .003, 1.5), FB=r(g, 0, 15),
                Swp=r(g, 20, 40), SwD=tp(u(g, .02, .05), .002, .3), Dec=tp(u(g, .2, .35), .02, 3), Noi=r(g, 0, 8))


def e_p_gnd_tom(g):
    return make("GND", r(g, 46, 60), Wav="Sin", Swp=64 + r(g, 12, 30), SwD=tp(u(g, .03, .08), .002, 1)).gate(
        u(g, .15, .3), slope=r(g, 30, 45))


ARCH_P = [e_p_efm_cowbell, e_p_rng_cowbell, mk.p_trx_tom, mk.p_abd_tom, e_p_efm_tom, e_p_gnd_tom,
          mk.p_gnd_blip, mk.p_zap_blip, mk.p_crs_tone, bc.lxr_cowbell, bc.lxr_tom]


# ---------------------------------------------------------------- fx
def e_f_zap_down(g):
    return make("Zap", r(g, 64, 84), Dep=r(g, 70, 110), Tim=tp(u(g, .02, .08), .0005, .12), FB=r(g, 0, 40),
                Dec=tp(u(g, .1, .25), .005, 1.0), Dir="Dwn").hp(u(g, 300, 600))


def e_f_gnd_beep(g):
    """beep-beep: a short square or triangle, retriggered"""
    return make("GND", r(g, 76, 92), Wav=pick(g, "Sqr", "Tri"), Swp=64, SwD=0).set(
        aeg_mode="ad", attack=r(g, 0, 2), decay=aeg(u(g, .04, .08)), slope=r(g, 20, 35), repeat=r(g, 2, 3)).hp(
        u(g, 400, 800))


def e_f_efm_laser(g):
    return make("EFM", r(g, 64, 84), Rat=pick(g, "1", "2", "3"), Mod=r(g, 40, 90), MDc=tp(u(g, .02, .08), .003, 1.5),
                FB=r(g, 20, 60), Swp=r(g, 70, 110), SwD=tp(u(g, .02, .08), .002, .3), Dec=tp(u(g, .1, .22), .02, 3),
                Noi=0).hp(u(g, 300, 600))


def e_f_crs_beep(g):
    return make("Crs", r(g, 72, 90), Src="Sqr", Rat=r(g, 0, 20), Bit=r(g, 20, 60), Jit=0,
                Dec=tp(u(g, .06, .14), .005, 2.0), Glt=0).set(repeat=r(g, 0, 2)).hp(u(g, 300, 700))


def e_f_zap_up(g):
    return make("Zap", r(g, 58, 76), Dep=r(g, 50, 90), Tim=tp(u(g, .03, .09), .0005, .12), FB=r(g, 10, 50),
                Dec=tp(u(g, .1, .2), .005, 1.0), Dir=pick(g, "Up", "Bth")).hp(u(g, 300, 600))


ARCH_F = [mk.f_zap_laser, e_f_zap_down, e_f_zap_up, mk.f_gnd_zip, e_f_gnd_beep, e_f_efm_laser, mk.f_byt_chirp,
          e_f_crs_beep, bc.lxr_laser]


# ---------------------------------------------------------------- snare
def e_s_trx_whip(g):
    return make("tSD", r(g, 56, 64), Bdy=r(g, 60, 100), Snp=r(g, 100, 127), Dec=tp(u(g, .05, .09), .02, .8),
                NDc=tp(u(g, .12, .22), .02, 1), Swp=r(g, 30, 60), NTn=r(g, 40, 70)).set(
        filt_type="lp", filt_freq=ff(u(g, 9000, 12000)), filt_reso=r(g, 0, 20), drive=r(g, 10, 40))


ARCH_S = [e_s_trx_whip, mk.s_trx_tight, mk.s_asd_snap, mk.s_ssd, mk.s_efm, mk.s_gnd_noise, mk.s_crs, bc.lxr_snare]
ARCH_C = [mk.c_trx, mk.c_trx_tight, mk.c_pl, mk.c_crs, mk.c_cmb, bc.lxr_clap]
ARCH_H = [mk.h_trx, mk.h_trx_dark, mk.h_phh, mk.h_phh_ring, mk.h_crs, mk.h_rng, bc.lxr_hat]

ARCH_EL = dict(kick=ARCH_K, perc=ARCH_P, fx=ARCH_F, snare=ARCH_S, clap=ARCH_C, hats=ARCH_H)

# =============================================================================
# role targets
# =============================================================================
#             kick  perc  fx    snare clap  hats  open
mk.RING_MAX = [0.60, 0.40, 0.45, 0.32, 0.45, 0.14, 0.62]
mk.RING_MIN = [0.18, 0.04, 0.03, 0.06, 0.06, 0.02, 0.12]
mk.HF_MAX = [0.10, 0.30, 0.32, 0.30, 0.38, 0.14, 0.55]
mk.POOL_N = {"kick": 130, "perc": 140, "fx": 130, "snare": 110, "clap": 110, "hats": 90}
mk.POOL_KEEP = 110       # filter_pools keeps the best 64, spread over the engines
mk.POOL_PER_ARCH = 18
mk.ARCH = {FAM: ARCH_EL}
POOL_MAX_PENALTY = 3.0
_role_penalty = mk.role_penalty


def role_penalty(role, m, alt=None, vol=100):
    pen = _role_penalty(role, m, alt, vol)
    f = m["feat"]
    if role == "kick":
        pen += max(0.0, f["centroid"] - 300) / 60     # 808: round, not clicky
    elif role == "snare":
        b = f["bands"]
        pen += max(0.0, 0.4 - (b["himid"] + b["high"])) / 0.05   # whip: crack on top
    return pen


mk.role_penalty = role_penalty

# single hit loudness re kick, loudest in the groove re kick
mk.LOUD_TARGET = [0.0, -8.0, -10.0, -3.0, -5.0, -15.0]
mk.GROOVE_MAX = [0.0, -4.0, -5.0, 0.5, -1.0, -5.0]

# =============================================================================
# themes and grooves (straight 16ths: no swing beyond what the player adds)
# =============================================================================
mk.THEMES = {
    #              bpm range    fx weights                       movement
    "motorcity":  ((128, 132), {"cmp": 3, "drv": 1, "del": 1}, 1),
    "aquatic":    ((128, 134), {"del": 5, "cmp": 1}, 2),
    "robotic":    ((130, 136), {"cmp": 3, "glt": 1}, 1),
    "cyberwar":   ((134, 138), {"drv": 4, "glt": 1}, 2),
    "breaker":    ((130, 136), {"drv": 2, "cmp": 2}, 2),
    "laserbeam":  ((132, 138), {"del": 4, "glt": 1}, 3),
    "bassquake":  ((128, 134), {"drv": 3, "cmp": 1}, 1),
    "nightdrive": ((128, 132), {"del": 3, "cmp": 2}, 2),
}
THEME_ORDER = list(mk.THEMES)
mk.GROOVES = {   # kick, perc, fx, snare, clap, hats ('X' accent, 'o' open hat, 'r' ratchet)
    "motorcity":  ["X.....x...X.....", "..x.......x..x..", "......x.......x.", "....X.......X...", "....x.......x...", "x.x.x.x.x.x.x.xo"],
    "aquatic":    ["X.....X...x.....", "...x.....x...x..", "x.........x.....", "....X.......X...", "............x...", "x.xxx.xox.xxx.xo"],
    "robotic":    ["X..x......X..x..", ".x...x.x.x...x.x", "..x.......x.....", "....X.......X...", "....x.......x...", "xxxxxxxxxxxxxxxx"],
    "cyberwar":   ["X..x..x...X.x...", "..x...x...x..x..", "x.......r.......", "....X..x....X...", "....x.......x...", "xxoxxxxoxxoxxxxo"],
    "breaker":    ["X.....x.x.X.....", "..x..x....x..x..", "......x.......x.", "....X.......X..x", "....x.......x...", "x.x.x.xox.x.x.xo"],
    "laserbeam":  ["X.....x...X..x..", "...x..x....x...x", ".x.x......x.x...", "....X.......X...", "............x...", "x.xxx.xxx.xxx.xo"],
    "bassquake":  ["X..x....X.x.....", "....x.....x....x", "..x.......x.....", "....X.......X...", "....x.......x...", "x.x.x.x.x.x.x.x."],
    "nightdrive": ["X.....x...X.....", "..x...x...x...x.", "x...............", "....X.......X...", "....x.......x...", "xxoxxxoxxxoxxxox"],
}
mk.SCALES = {k: v for k, v in mk.SCALES.items() if k in ("minor", "phrygian", "dorian", "penta")}
SCALES = dict(mk.SCALES)

NAMES = ["Robot", "Cyber", "Laser", "Planet", "Orbit", "Neon", "Pulse", "Grid", "Matrix", "Vector",
         "Signal", "Modem", "Radar", "Sonar", "Quasar", "Pulsar", "Photon", "Proton", "Ion", "Plasma",
         "Ozone", "Metro", "Motor", "Turbo", "Chrome", "Silicn", "Diode", "Transr", "Relay", "Switch",
         "Static", "Volt", "Amp", "Ohm", "Watt", "Hertz", "Tesla", "Nova", "Comet", "Meteor",
         "Lunar", "Solar", "Astro", "Cosmo", "Rocket", "Shuttl", "Probe", "Drone", "Droid", "Cyborg",
         "Mech", "Servo", "Sensor", "Optic", "Prism", "Strobe", "Flash", "Spark", "Beam", "Ray",
         "Zapper", "Blastr", "Phaser", "Aqua", "Abyss", "Trench", "Tide", "Coral", "Kelp", "Hydro",
         "Depth", "Marine", "Bubble", "Pearl", "Reef", "Boom", "Break", "Pop", "Lock", "Funk",
         "Bounce", "Freak", "Scrtch", "Cut", "Tape", "Vinyl", "Deck", "Crate", "Bboy", "Cypher",
         "Floor", "Spin", "Glide", "Slide", "Code", "Data", "Byte", "Chip", "Ram", "Rom",
         "Disk", "Pixel", "Logic", "Binary", "Hex", "Bios", "Boot", "Kernel", "Node", "Link",
         "Xeno", "Zero", "Alpha", "Omega", "Delta", "Sigma", "Gamma", "Theta", "Kappa", "Zeta",
         "Night", "Dusk", "Shadow", "Ghost", "Phantm", "Mirage", "Vapor", "Cobalt"]
bc.check_names(FAM, NAMES)


# =============================================================================
# kit
# =============================================================================
def setup_movement(rng, kit, level):
    # fx: every zap a little different (S&H on a timbre parameter)
    prm = mk.engine_params(kit.ch[2])
    if prm:
        d = rng.choice(prm)
        kit.lfo_mod(2, mod_dest(2, engine_slot=d["slot"]), r(rng, 10, 25 + 5 * level), wave="rnd",
                    freq=r(rng, 50, 75))
    # lasers fly across the stereo field
    if level >= 2:
        src = kit.lfo_free(rng, avoid=(0,))
        if src is not None:
            kit.lfo_mod(src, mod_dest(2, "PAN"), r(rng, 25, 50), wave=pick(rng, "sqr", "tri", "rnd"),
                        freq=r(rng, 30, 50), target_ch=2)
    # hats: accents open the high pass; snare: accent to drive (the whip)
    kit.mod(5, 11 + 5, r(rng, 8, 18), mod_dest(5, "FILT_FREQ"))
    if rng.random() < 0.6:
        kit.mod(3, 11 + 3, r(rng, 12, 28), mod_dest(3, "DRIVE"))
    # perc: light S&H on its timbre (cowbells and toms stay put more often)
    prm = mk.engine_params(kit.ch[1])
    if prm and rng.random() < 0.3 + 0.15 * level:
        d = rng.choice(prm)
        src = 1 if 1 not in kit.lfo_used else kit.lfo_free(rng, avoid=(0,))
        if src is not None:
            kit.lfo_mod(src, mod_dest(1, engine_slot=d["slot"]), r(rng, 6, 16), wave="rnd", freq=r(rng, 45, 70),
                        target_ch=1)
    # robots: crushed fx
    if kit.theme in ("robotic", "cyberwar") or level >= 3:
        kit.ch[2].set(bits=max(kit.ch[2].s("bits"), r(rng, 20, 55)))
        if rng.random() < 0.4:
            kit.ch[2].set(srate=r(rng, 60, 100))


def stereo(kit, rng):
    side = pick(rng, -1, 1)
    kit.ch[0].set(pan=64)
    kit.ch[1].set(pan=64 + side * r(rng, 12, 26))
    kit.ch[2].set(pan=64 - side * r(rng, 14, 30))
    kit.ch[3].set(pan=r(rng, 62, 66))
    kit.ch[4].set(pan=64 + r(rng, -6, 6))
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
    if kit.fx["type"] == "del" and theme == "laserbeam":
        kit.ch[2].set(out="fx")                      # lasers into the ping-pong
    return kit


POOLS = None


def main():
    global POOLS
    bc.maybe_probe(ARCH_EL)
    POOLS = mk.build_pools(seed="electro2")
    bc.filter_pools(POOLS, POOL_MAX_PENALTY)
    bc.run_bank("electro2", FAM, BANK, b"ELECTRO ", build_kit)


if __name__ == "__main__":
    main()
