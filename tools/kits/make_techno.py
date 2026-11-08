#!/usr/bin/env python3
"""Build the SHARD techno bank (128 kits) with the machinery of make_kits.py.

    python3 tools/kits/make_techno.py <shard_render> <out dir> [bank number]

Writes <out dir>/shard/prjNN/*.snd and prj.nfo (bank 01 by default),
<out dir>/bank.json and demo WAVs in <out dir>/demo.

Channel roles in this bank
    1 kick     long, pumping techno kicks (aBD, tBD, sBD)
    2 rumble   low tonal tail on the off beats: low voices through a resonant
               low pass and drive, tuned to the key, ducked by the kick
    3 atmos    dark textures: particles, modal and string drones, filtered
               noise and comb air, slow filter motion, sent to the delay
    4 snare    rims and tight snares
    5 clap
    6 hats     closed hat, trigger 7 = open hat

The pump: the LFOs of the rumble and atmos channels are saw ups retriggered
by channel 1, a little longer than a beat, modulating the channel volume, so
the level dips on every kick and comes back (sidechain style).

Kits are scored, tuned, balanced and mastered like the factory bank (see
make_kits.py); the role targets below are the techno ones.

SPDX-License-Identifier: GPL-3.0-only
"""
import json
import math
import os
import random
import sys

if len(sys.argv) < 3:
    sys.exit(__doc__)
BANK = int(sys.argv[3]) if len(sys.argv) > 3 else 1
sys.argv = sys.argv[:3]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_kits as mk  # noqa: E402
from make_kits import Channel, Kit, mk as make, tp, aeg, ff, bi, u, r, pick, clamp, mod_dest  # noqa: E402
from analyse import analyse  # noqa: E402

RENDER, OUT = mk.RENDER, mk.OUT


# =============================================================================
# archetypes
# =============================================================================
# ---------------------------------------------------------------- kick
def k_abd_long(g):
    return make("aBD", r(g, 28, 33), Ton=r(g, 15, 45), Dec=r(g, 45, 70), AFM=r(g, 20, 60), SFM=r(g, 10, 40),
                Drv=r(g, 20, 70))


def k_abd_hard(g):
    return make("aBD", r(g, 29, 34), Ton=r(g, 30, 60), Dec=r(g, 40, 60), AFM=r(g, 50, 90), SFM=r(g, 20, 50),
                Drv=r(g, 70, 110)).set(drive=r(g, 5, 30))


def k_trx_long(g):
    return make("tBD", r(g, 28, 32), Swp=r(g, 35, 55), SwD=tp(u(g, .015, .04), .002, .25), Dec=tp(u(g, .5, .9), .04, 3),
                Hld=r(g, 5, 25), Clk=r(g, 20, 60), Drv=r(g, 30, 70))


def k_trx_punch(g):
    return make("tBD", r(g, 29, 33), Swp=r(g, 45, 65), SwD=tp(u(g, .01, .025), .002, .25), Dec=tp(u(g, .4, .65), .04, 3),
                Hld=r(g, 10, 30), Clk=r(g, 50, 90), Drv=r(g, 50, 90))


def k_sbd_deep(g):
    return make("sBD", r(g, 28, 33), Ton=r(g, 20, 50), Dec=r(g, 45, 65), Drt=r(g, 0, 30), FMA=r(g, 20, 60),
                FMD=r(g, 10, 30))


# ---------------------------------------------------------------- rumble
def _rumble(c, g, lp=(140, 420)):
    """low pass with some resonance, strip drive, short enough for 8ths"""
    return c.set(filt_type="lp", filt_freq=ff(u(g, *lp)), filt_reso=r(g, 15, 60), drive=r(g, 20, 60))


def r_abd_tail(g):
    c = make("aBD", r(g, 28, 38), Ton=r(g, 5, 30), Dec=r(g, 60, 90), AFM=r(g, 0, 25), SFM=r(g, 0, 20), Drv=r(g, 60, 110))
    return _rumble(c, g).set(aeg_mode="ad", attack=r(g, 2, 8), decay=aeg(u(g, .22, .4)), slope=r(g, 25, 45))


def r_trx_tail(g):
    c = make("tBD", r(g, 30, 40), Swp=r(g, 10, 30), SwD=tp(u(g, .02, .06), .002, .25), Dec=tp(u(g, .7, 1.2), .04, 3),
             Hld=r(g, 20, 50), Clk=r(g, 0, 20), Drv=r(g, 60, 100))
    return _rumble(c, g).set(aeg_mode="ad", attack=r(g, 3, 10), decay=aeg(u(g, .22, .38)), slope=r(g, 25, 45))


def r_str_low(g):
    c = make("Str", r(g, 30, 42), Str=r(g, 0, 40), Bri=r(g, 10, 40), Dmp=r(g, 55, 90), Exc=r(g, 40, 100))
    return _rumble(c, g, (180, 500)).gate(u(g, .25, .42), slope=r(g, 25, 40))


def r_mdl_low(g):
    c = make("Mdl", r(g, 30, 42), Str=r(g, 10, 50), Bri=r(g, 10, 35), Dmp=r(g, 50, 85), Exc=r(g, 30, 90))
    return _rumble(c, g, (160, 450)).gate(u(g, .25, .42), slope=r(g, 25, 40))


def r_gnd_thump(g):
    """noise into a resonant low pass: a thump at the filter pitch"""
    c = make("GND", r(g, 40, 60), Wav="Noi", Swp=64, SwD=0)
    return c.set(filt_type="lp", filt_freq=ff(u(g, 60, 140)), filt_reso=r(g, 85, 110), drive=r(g, 30, 70),
                 aeg_mode="ad", attack=r(g, 1, 6), decay=aeg(u(g, .2, .35)), slope=r(g, 30, 45))


# ---------------------------------------------------------------- atmos
def a_prt_dust(g):
    return make("Prt", r(g, 55, 80), Den=r(g, 20, 60), Res=r(g, 30, 75), Spr=r(g, 40, 100)).set(
        filt_type="bp", filt_freq=ff(u(g, 900, 3500)), filt_reso=r(g, 10, 40)).gate(u(g, .7, 1.3), slope=r(g, 20, 35))


def a_mdl_drone(g):
    return make("Mdl", r(g, 52, 70), Str=r(g, 40, 100), Bri=r(g, 15, 50), Dmp=r(g, 65, 95), Exc=r(g, 40, 90)).set(
        filt_type="lp", filt_freq=ff(u(g, 1800, 4500)), filt_reso=r(g, 0, 30)).gate(u(g, .9, 1.4), slope=r(g, 20, 35))


def a_str_pad(g):
    return make("Str", r(g, 50, 66), Str=r(g, 40, 110), Bri=r(g, 15, 45), Dmp=r(g, 70, 100), Exc=r(g, 60, 110)).set(
        filt_type="lp", filt_freq=ff(u(g, 1500, 4000)), filt_reso=r(g, 0, 25)).gate(u(g, .9, 1.4), slope=r(g, 20, 35))


def a_gnd_wind(g):
    """filtered noise that swells in and dies away"""
    return make("GND", r(g, 50, 70), Wav="Noi", Swp=64, SwD=0).set(
        filt_type="bp", filt_freq=ff(u(g, 500, 1800)), filt_reso=r(g, 40, 80),
        aeg_mode="ad", attack=r(g, 25, 45), decay=aeg(u(g, .6, 1.0)), slope=r(g, 20, 35))


def a_cmb_air(g):
    return make("Cmb", r(g, 48, 64), Exc="Noi", FB=r(g, 108, 120), Dmp=r(g, 30, 60), Bur=r(g, 60, 110),
                Rat=r(g, 0, 127), Mx2=r(g, 20, 60)).set(
        filt_type="lp", filt_freq=ff(u(g, 1500, 3500)), filt_reso=r(g, 0, 20)).gate(u(g, .7, 1.2), slope=r(g, 20, 35))


# ---------------------------------------------------------------- snare / rim
def s_rim(g):
    return make("tSD", r(g, 62, 74), Bdy=r(g, 90, 127), Snp=r(g, 0, 30), Dec=tp(u(g, .02, .06), .02, .8),
                NDc=tp(u(g, .02, .05), .02, 1), Swp=r(g, 30, 70), NTn=r(g, 80, 120)).hp(u(g, 250, 450))


def s_efm_rim(g):
    return make("EFM", r(g, 64, 76), Rat=pick(g, "2", "3", "3.5"), Mod=r(g, 30, 70), MDc=tp(u(g, .005, .02), .003, 1.5),
                FB=r(g, 0, 30), Swp=r(g, 0, 20), SwD=tp(u(g, .005, .015), .002, .3), Dec=tp(u(g, .05, .1), .02, 3),
                Noi=r(g, 20, 50)).hp(u(g, 250, 450))


ARCH_TK = dict(
    kick=[k_abd_long, k_abd_hard, k_trx_long, k_trx_punch, k_sbd_deep],
    perc=[r_abd_tail, r_trx_tail, r_str_low, r_mdl_low, r_gnd_thump],
    fx=[a_prt_dust, a_mdl_drone, a_str_pad, a_gnd_wind, a_cmb_air],
    snare=[s_rim, s_efm_rim, mk.s_trx_tight, mk.s_asd_snap, mk.s_ssd],
    clap=[mk.c_trx, mk.c_trx_tight, mk.c_pl],
    hats=[mk.h_trx, mk.h_trx_dark, mk.h_phh, mk.h_phh_ring],
)


# =============================================================================
# role targets (the factory bank's, with the rumble and atmos roles)
# =============================================================================
#             kick  rumb  atmos snare clap  hats  open
mk.RING_MAX = [0.75, 0.80, 1.60, 0.38, 0.45, 0.14, 0.62]
mk.RING_MIN = [0.25, 0.15, 0.40, 0.04, 0.06, 0.02, 0.12]
mk.HF_MAX = [0.10, 0.08, 0.45, 0.32, 0.38, 0.14, 0.55]
mk.CREST_MAX.update(perc=12, fx=17)
mk.AVAIL_MIN.update(perc=-26, fx=-34)
mk.POOL_N = {"kick": 70, "perc": 80, "fx": 80, "snare": 60, "clap": 42, "hats": 48}
mk.POOL_KEEP = 32
mk.ARCH = {"TK": ARCH_TK}
mk.POOL_PER_ARCH = 8
POOL_MAX_PENALTY = 3.0
_role_penalty = mk.role_penalty


def role_penalty(role, m, alt=None, vol=100):
    if role not in ("perc", "fx"):
        return _role_penalty(role, m, alt, vol)
    f = m["feat"]
    b = f["bands"]
    k = mk.ROLES.index(role)
    pen = 0.0
    avail = f["loud"] + 20 * math.log10(127 / max(vol, 1))
    pen += max(0.0, mk.AVAIL_MIN[role] - avail) / 3
    crest = 20 * math.log10(m["peak"] + 1e-9) - f["loud"]
    pen += max(0.0, crest - mk.CREST_MAX[role]) / 2
    pen += mk.out_of(m["ring"], mk.RING_MIN[k], mk.RING_MAX[k], 0.05)
    pen += max(0.0, m["hf"] - mk.HF_MAX[k]) / 0.05
    pen += max(0.0, abs(f["dc"]) - 0.03) * 50
    fq, lvl, prom = m["tone"]
    sl = b["sub"] + b["low"]
    if role == "perc":                               # rumble: low, warm, no click
        pen += out_of_whistle(fq, lvl, prom, 500)
        pen += mk.out_of(sl, 0.45, 1.0, 0.04)
        pen += mk.out_of(f["centroid"], 50, 380, 40)
        pen += max(0.0, b["himid"] + b["high"] + b["air"] - 0.04) / 0.01
        pen += max(0.0, f["harsh"] - 0.4) / 0.05
    else:                                            # atmos: mid band texture, dark top, no whistle
        pen += out_of_whistle(fq, lvl, prom, 1200)
        pen += max(0.0, sl - 0.12) / 0.03
        pen += mk.out_of(f["centroid"], 300, 4000, 300)
        pen += max(0.0, b["air"] - 0.08) / 0.02
        pen += max(0.0, f["harsh"] - 0.35) / 0.05
        pen -= min(f["flux"], 0.6) * 3               # movement inside the sound is welcome
    return pen


def out_of_whistle(fq, lvl, prom, above):
    """sustained tones above <above> Hz are whistles; low pitched tails are fine"""
    return 5.0 if (fq > above and lvl > mk.TONE_LEVEL and prom > mk.TONE_PROM) else 0.0


mk.role_penalty = role_penalty


def problems(m):
    """make_kits.problems, but low pitched rumble and atmos tails are allowed"""
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
        limit = {1: 500, 2: 1200}.get(k, 0)
        if k < 6 and f > limit and lvl > mk.TONE_LEVEL and prom > mk.TONE_PROM:
            why.append(f"tone {f:.0f}Hz {lvl:.0f}dB")
        if why:
            bad.append((k, why))
    return bad


mk.problems = problems

# single hit loudness re kick, loudest in the groove re kick
mk.LOUD_TARGET = [0.0, -7.0, -14.0, -5.0, -5.0, -15.0]
mk.GROOVE_MAX = [0.0, -3.0, -8.0, 0.0, -1.0, -5.0]
mk.MAKEUP_MAX = [20, 40, 30, 40, 40, 24]
mk.CLIP_MAX = [0, 30, 30, 55, 55, 30]

# =============================================================================
# themes and grooves
# =============================================================================
mk.THEMES = {
    #              bpm range    fx weights                         movement
    "warehouse":  ((128, 134), {"drv": 3, "cmp": 2, "del": 1}, 1),
    "dub":        ((120, 126), {"del": 6}, 2),
    "hypnotic":   ((126, 132), {"cmp": 3, "del": 2}, 2),
    "industrial": ((132, 140), {"drv": 5, "glt": 1}, 1),
    "deep":       ((122, 128), {"del": 4, "cmp": 1}, 2),
    "peak":       ((130, 136), {"cmp": 4, "drv": 1}, 1),
    "acidwash":   ((128, 134), {"del": 2, "drv": 2, "glt": 1}, 3),
    "minimal":    ((124, 130), {"cmp": 2, "del": 3}, 2),
}
THEME_ORDER = ["warehouse", "dub", "hypnotic", "industrial", "deep", "peak", "acidwash", "minimal"]
mk.GROOVES = {   # kick, rumble, atmos, snare, clap, hats ('X' accent, 'o' open hat)
    "warehouse":  ["X...X...X...X...", "..x...x...x...x.", "x...............", "..........x.....", "....x.......x...", "xxoxxxoxxxoxxxox"],
    "dub":        ["X...X...X...X...", "..x...x...x..xx.", "x.......x.......", "...x......x..x..", "............x...", "..o...o...o...o."],
    "hypnotic":   ["X...X...X...X...", ".xx..xx..xx..xx.", "x...............", "......x.......x.", "....x.......x...", "x.xox.xox.xox.xo"],
    "industrial": ["X...X...X..xX...", ".x.x.x.x.x.x.x.x", "x.......x.......", "..x.......x..x..", "....x.......x...", "xxxxxxxxxxxxxxxo"],
    "deep":       ["X...X...X...X...", "..x...x...x...x.", "x...............", "......x.........", "....x.......x...", "..o...o...o.x.o."],
    "peak":       ["X...X...X...X...", "..xx..xx..xx..xx", "x...............", "...x.......x....", "....x.......x...", "xxoxxxoxxxoxxxox"],
    "acidwash":   ["X...X...X...X...", "..x..x.x..x..x.x", "x.....x.........", "..x.....x...x...", "....x.......x...", "x.xox.xxx.xox.xx"],
    "minimal":    ["X...X...X...X...", "...x...x...x...x", "x...............", ".x.....x..x.....", "............x...", "x.x.x.o.x.x.x.o."],
}
mk.SCALES = {k: v for k, v in mk.SCALES.items() if k in ("minor", "phrygian", "dorian")}

NAMES = ["Basalt", "Bunker", "Carbon", "Cellar", "Chrome", "Concrt", "Conveyr", "Crane", "Depot", "Diesel",
         "Docks", "Dredge", "Engine", "Factory", "Ferro", "Forge", "Foundry", "Freight", "Furnace", "Gantry",
         "Girder", "Granite", "Graphit", "Grind", "Hangar", "Harbor", "Haul", "Hull", "Hydrlc", "Iron",
         "Kiln", "Lathe", "Lever", "Loader", "Magnet", "Mantle", "Meltdwn", "Metro", "Mill", "Mine",
         "Monolth", "Motor", "Nickel", "Night", "Nocturn", "Obsidn", "Offset", "Orbit", "Outpost", "Pylon",
         "Piston", "Pit", "Plant", "Plate", "Port", "Press", "Pulse", "Pump", "Quarry", "Radial",
         "Rail", "Reactor", "Relay", "Rivet", "Rotor", "Rust", "Sector", "Shaft", "Shift", "Silo",
         "Slab", "Smelter", "Smoke", "Socket", "Solder", "Spindle", "Steam", "Steel", "Strobe", "Subway",
         "Sulfur", "Switch", "Tanker", "Tension", "Terminl", "Thrust", "Tide", "Titan", "Torque", "Tower",
         "Track", "Transit", "Trench", "Tunnel", "Turbine", "Uranium", "Vault", "Vector", "Vent", "Volt",
         "Warden", "Warp", "Weld", "Wharf", "Winch", "Wire", "Yard", "Zinc", "Abyss", "Anvil",
         "Arc", "Ash", "Axis", "Ballast", "Beacon", "Blast", "Bolt", "Boiler", "Breaker", "Cable",
         "Cast", "Cinder", "Circuit", "Clamp", "Coil", "Core", "Crank", "Crucibl"]
assert len(NAMES) >= 128


def pump_freq(bpm):
    """LFO parameter for a period of 1.15 beats (sh_channel.c: f = x^3 * 200 Hz)"""
    f = bpm / 60.0 / 1.15
    x = (f / 200.0) ** (1 / 3)
    return clamp((x - 0.0078125) / (1 - 0.0078125) * 127)


def setup_movement(rng, kit, level):
    # the pump: rumble and atmos duck on every kick
    kit.lfo_mod(1, mod_dest(1, "VOL"), r(rng, 22, 38), wave="sup", freq=pump_freq(kit.bpm), retrig=1)
    kit.lfo_mod(2, mod_dest(2, "VOL"), r(rng, 15, 30), wave="sup", freq=pump_freq(kit.bpm), retrig=1)
    kit.notes.append("pump")
    # atmos: slow filter drift (LFO of the snare channel), some S&H grain on its timbre
    kit.lfo_mod(3, mod_dest(2, "FILT_FREQ"), r(rng, 10, 25), wave=pick(rng, "tri", "sin"), freq=r(rng, 8, 14),
                target_ch=2)
    prm = mk.engine_params(kit.ch[2])
    if prm and level >= 2:
        d = rng.choice(prm)
        kit.lfo_mod(5, mod_dest(2, engine_slot=d["slot"]), r(rng, 6, 15), wave="rnd", freq=r(rng, 40, 60),
                    target_ch=2)
    # rumble breathes: slow movement of its low pass (LFO of the clap channel)
    if rng.random() < 0.5 + 0.2 * level:
        kit.lfo_mod(4, mod_dest(1, "FILT_FREQ"), r(rng, 8, 18), wave=pick(rng, "tri", "sin"), freq=r(rng, 10, 18),
                    target_ch=1)
    # hats: accents open the high pass; snare: accent to drive
    kit.mod(5, 11 + 5, r(rng, 8, 18), mod_dest(5, "FILT_FREQ"))
    if rng.random() < 0.5:
        kit.mod(3, 11 + 3, r(rng, 12, 25), mod_dest(3, "DRIVE"))
    if level >= 3:
        # the acid wash themes: crushed atmos
        kit.ch[2].set(bits=max(kit.ch[2].s("bits"), r(rng, 20, 50)))


def stereo(kit, rng):
    side = pick(rng, -1, 1)
    kit.ch[0].set(pan=64)
    kit.ch[1].set(pan=64 + side * r(rng, 0, 6))              # rumble: centre, it is bass
    kit.ch[2].set(pan=64 - side * r(rng, 14, 30))
    kit.ch[3].set(pan=64 + side * r(rng, 6, 18))
    kit.ch[4].set(pan=64 + r(rng, -4, 4))
    kit.ch[5].set(pan=64 - side * r(rng, 6, 14))


def build_kit(rng, pools, i):
    theme = THEME_ORDER[i % len(THEME_ORDER)]
    bpm = r(rng, *mk.THEMES[theme][0])
    level = mk.THEMES[theme][2]
    kit = Kit(("TK" + NAMES[i])[:8], "TK", theme, bpm)
    metas = []
    for role in mk.ROLES:
        c, m = mk.choose(rng, pools, "TK", role)
        kit.ch.append(c)
        metas.append(m)
    kit.key = (rng.randrange(12), rng.choice(list(mk.SCALES.values())))
    kit.keyname = mk.NOTE_NAMES[kit.key[0]] + " " + [k for k, v in mk.SCALES.items() if v == kit.key[1]][0]
    kit.tuned = mk.tune_voices(kit, metas, rng)
    stereo(kit, rng)
    setup_movement(rng, kit, level)
    mk.setup_fx(rng, kit, level)
    # rumble always into the delay when there is one: dub techno tail
    if kit.fx["type"] == "del":
        kit.ch[1].set(out="fx")
    return kit


def main():
    pools = mk.build_pools(seed="techno1")
    # only voices that fit their role well (at least 8 per role)
    for role, items in pools["TK"].items():
        good = [x for x in items if x[1] <= POOL_MAX_PENALTY]
        pools["TK"][role] = good if len(good) >= 8 else items[:8]
        print(f"pool {role:5s}: {len(pools['TK'][role])} voices", flush=True)
    kit_dir = os.path.join(OUT, "shard", f"prj{BANK:02d}")
    demo_dir = os.path.join(OUT, "demo")
    os.makedirs(kit_dir, exist_ok=True)
    os.makedirs(demo_dir, exist_ok=True)
    only = set(int(x) for x in os.environ.get("ONLY", "").split(",") if x)
    first = int(os.environ.get("FIRST", "0"))
    report_path = os.path.join(OUT, "bank.json")
    report = json.load(open(report_path)) if (first and os.path.exists(report_path)) else []
    report = [x for x in report if x["slot"] < first]
    if not only and not first:
        for f in os.listdir(kit_dir):
            os.unlink(os.path.join(kit_dir, f))
    log = []
    for i in range(128):
        rng = random.Random(f"techno1-{i}")
        kit = build_kit(rng, pools, i)
        if (only and i not in only) or i < first:
            continue
        path = os.path.join(kit_dir, mk.file_name(i, kit.name))
        undone = mk.retune_check(kit, path)
        fixed = mk.fix_kit(kit, path, log)
        mk.balance(kit, path)
        mk.groove_guard(kit, path)
        m = mk.master(kit, path)
        wav = os.path.join(demo_dir, f"{i:03d}_{kit.name}.wav") if (i % 4 == 0 or only) else ""
        if wav:
            m = mk.render_groove(kit, path, wav)
        kit.write(path)
        rep = dict(slot=i, name=kit.name, family="TK", theme=kit.theme, bpm=kit.bpm, key=kit.keyname,
                   engines=[c.engine for c in kit.ch], archs=[c.arch for c in kit.ch], fx=kit.fx["type"],
                   out=m["out_peak"], clip=m["clip"], tail=m["tail"], fixed=fixed,
                   tuned=len(kit.tuned) - undone, notes=kit.notes)
        report.append(rep)
        print(f"{i:3d} {kit.name:8s} {kit.theme:10s} {kit.keyname:12s} {' '.join(c.engine for c in kit.ch)} "
              f"fx={kit.fx['type']} fix={fixed} tuned={rep['tuned']} out={m['out_peak']:.2f} clip={m['clip']}",
              flush=True)
        with open(report_path, "w") as f:
            json.dump(report, f, indent=1)
    with open(os.path.join(kit_dir, "prj.nfo"), "wb") as f:
        f.write(b"TECHNO  ")
    with open(os.path.join(OUT, "fixlog.txt"), "a") as f:
        f.write("\n".join(log) + "\n")
    print(f"{len(report)} kits in {kit_dir}")


if __name__ == "__main__":
    main()
