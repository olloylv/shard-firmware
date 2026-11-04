"""Shared parts of the genre bank generators (make_electro.py, make_psy.py,
make_industrial.py), on top of make_kits.py like make_techno.py.

    import make_kits as mk          # after sys.argv = [script, render, out]
    import bank_common as bc

What is here
    - unit helpers for the LFO rate
    - archetypes of the original LXR voices (Drm, Snr, Cym, Hat), which the
      factory and techno banks don't use, and the techno rumble archetypes
    - a voice chooser that never repeats a kit's combination of voices: two
      kits of a bank share at most MAX_SHARED of their six pool voices
    - the bank main loop (retune check, fixes, balance, groove guard,
      mastering), the same steps as make_techno.py, without demo WAVs

SPDX-License-Identifier: GPL-3.0-only
"""
import json
import math
import os
import random
import subprocess

import make_kits as mk
from analyse import analyse
from make_kits import Channel, mk as make, tp, aeg, ff, r, u, pick, clamp  # noqa: F401


# =============================================================================
# helpers
# =============================================================================
def lfo_param(hz):
    """LFO rate parameter for a frequency in Hz (sh_channel.c: f = x^3 * 200 Hz)"""
    x = (max(hz, 1e-4) / 200.0) ** (1 / 3)
    return clamp((x - 0.0078125) / (1 - 0.0078125) * 127)


def pump_freq(bpm, beats=1.15):
    """LFO rate for a saw that lasts <beats> beats (the kick pump)"""
    return lfo_param(bpm / 60.0 / beats)


def out_of_whistle(fq, lvl, prom, above):
    """sustained tones above <above> Hz are whistles; low pitched tails are fine"""
    return 5.0 if (fq > above and lvl > mk.TONE_LEVEL and prom > mk.TONE_PROM) else 0.0


def base_penalty(role, m, vol):
    """the part of make_kits.role_penalty every role shares: available level,
    crest, length, high frequency tail, DC"""
    f = m["feat"]
    k = mk.ROLES.index(role)
    pen = 0.0
    avail = f["loud"] + 20 * math.log10(127 / max(vol, 1))
    pen += max(0.0, mk.AVAIL_MIN[role] - avail) / 3
    crest = 20 * math.log10(m["peak"] + 1e-9) - f["loud"]
    pen += max(0.0, crest - mk.CREST_MAX[role]) / 2
    pen += mk.out_of(m["ring"], mk.RING_MIN[k], mk.RING_MAX[k], 0.05)
    pen += max(0.0, m["hf"] - mk.HF_MAX[k]) / 0.05
    pen += max(0.0, abs(f["dc"]) - 0.03) * 50
    return pen


# =============================================================================
# LXR voice archetypes (strip AEG shapes them: the engines have no amp EG)
# =============================================================================
def lxr_kick(g):
    """LXR drum as an 808: sine with a pitch EG, kick transient"""
    return make("Drm", r(g, 28, 34), Wav="Sin", PDc=r(g, 25, 50), PSl=r(g, 50, 80), PAm=r(g, 35, 60),
                TrW=pick(g, "Kik", "Kk2", "Clk"), TrV=r(g, 15, 60), TrF=r(g, 20, 40)).set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .3, .55)), slope=r(g, 35, 55))


def lxr_kick_short(g):
    return make("Drm", r(g, 29, 35), Wav="Sin", PDc=r(g, 20, 40), PSl=r(g, 55, 85), PAm=r(g, 45, 70),
                TrW=pick(g, "Kik", "Clk", "Ck2"), TrV=r(g, 30, 80), TrF=r(g, 20, 45)).set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .18, .3)), slope=r(g, 40, 60))


def lxr_kick_fm(g):
    """LXR drum with some FM from the second oscillator: a dirtier 808"""
    return make("Drm", r(g, 28, 33), Wav="Sin", PDc=r(g, 25, 50), PSl=r(g, 50, 80), PAm=r(g, 35, 60),
                FMA=r(g, 10, 35), FMF=64 + pick(g, 0, 12, 7, -12), FMW="Sin", Mod="FM ",
                TrW=pick(g, "Kik", "Kk2"), TrV=r(g, 20, 60), TrF=r(g, 20, 40)).set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .3, .5)), slope=r(g, 35, 55), drive=r(g, 10, 45))


def lxr_tom(g):
    return make("Drm", r(g, 45, 60), Wav=pick(g, "Sin", "Tri"), PDc=r(g, 25, 45), PSl=r(g, 55, 80),
                PAm=r(g, 20, 40), TrW=pick(g, "Tom", "Clk", "Tik"), TrV=r(g, 10, 50), TrF=r(g, 20, 45)).set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .15, .3)), slope=r(g, 30, 50))


def lxr_cowbell(g):
    """808 style: two squares a fifth apart mixed (Mix mode), band pass"""
    return make("Drm", r(g, 70, 76), Wav="Rec", PDc=0, PAm=0, FMA=r(g, 50, 70), FMF=64 + pick(g, 7, 7, 6, 8),
                FMW="Rec", Mod="Mix", TrW="Tik", TrV=r(g, 0, 30)).set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .1, .2)), slope=r(g, 25, 45), filt_type="bp",
        filt_freq=ff(u(g, 900, 1800)), filt_reso=r(g, 10, 40))


def lxr_blip(g):
    return make("Drm", r(g, 62, 80), Wav=pick(g, "Tri", "Sin", "Rec"), PDc=r(g, 10, 30), PSl=r(g, 40, 90),
                PAm=r(g, 30, 60)).set(aeg_mode="ad", attack=0, decay=aeg(u(g, .05, .12)), slope=r(g, 25, 45)).hp(
        u(g, 200, 400))


def lxr_laser(g):
    """big fast pitch drop: pew"""
    return make("Drm", r(g, 60, 80), Wav=pick(g, "Sin", "Tri", "Saw"), PDc=r(g, 30, 60), PSl=r(g, 30, 100),
                PAm=r(g, 70, 110), FMA=r(g, 0, 40), FMF=64 + r(g, -12, 19), Mod="FM ").set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .1, .22)), slope=r(g, 20, 40)).hp(u(g, 300, 700))


def lxr_snare(g):
    """LXR snare: pitched body with a pitch EG and filtered noise, snap transient"""
    return make("Snr", r(g, 52, 62), Wav=pick(g, "Sin", "Tri"), Noi=r(g, 90, 127), NFF=r(g, 70, 110),
                NFR=r(g, 5, 35), NFT=pick(g, "HP ", "BP ", "UBP"), PDc=r(g, 20, 40), PSl=r(g, 50, 80),
                PAm=r(g, 15, 40), Mix=r(g, 75, 110), TrW=pick(g, "Snp", "Snr", "Clk"), TrV=r(g, 30, 90),
                TrF=r(g, 20, 50)).set(aeg_mode="ad", attack=0, decay=aeg(u(g, .12, .22)), slope=r(g, 30, 50)).hp(
        u(g, 120, 200))


def lxr_snare_hard(g):
    return lxr_snare(g).set(drive=r(g, 30, 70), decay=aeg(u(g, .1, .2)))


def lxr_clap(g):
    """LXR snare noise only, retriggered like a clap"""
    return make("Snr", r(g, 60, 70), Wav="Sin", Noi=r(g, 90, 127), NFF=r(g, 75, 105), NFR=r(g, 10, 40),
                NFT=pick(g, "BP ", "HP "), PAm=0, Mix=127, TrW=pick(g, "Clp", "Snp"), TrV=r(g, 20, 60)).set(
        aeg_mode="ad", attack=r(g, 2, 6), decay=aeg(u(g, .14, .24)), slope=r(g, 20, 35), repeat=r(g, 2, 4),
        filt_type="bp", filt_freq=ff(u(g, 1100, 2400)), filt_reso=r(g, 10, 35))


def lxr_hat(g):
    """LXR hihat: three square FM cluster; open = T7 with the strip's decay alt"""
    return make("Hat", r(g, 80, 96), Wav=pick(g, "Rec", "Sin"), MF1=r(g, 80, 100), MF2=r(g, 95, 115),
                MG1=r(g, 60, 100), MG2=r(g, 40, 80), MW1="Rec", MW2="Rec", TrW=pick(g, "Hat", "Tik"),
                TrV=r(g, 0, 40)).set(aeg_mode="ad", attack=0, decay=aeg(u(g, .03, .06)),
                                     decay_alt=aeg(u(g, .25, .42)), slope=r(g, 15, 25)).hp(u(g, 6000, 9000))


def lxr_cym_metal(g):
    """LXR cymbal as a short metallic clang"""
    return make("Cym", r(g, 62, 80), Wav=pick(g, "Sin", "Rec", "Tri"), MF1=r(g, 70, 110), MF2=r(g, 80, 120),
                MG1=r(g, 50, 110), MG2=r(g, 30, 90), MW1=pick(g, "Rec", "Saw"), MW2=pick(g, "Sin", "Rec"),
                TrW=pick(g, "Clk", "Tik", "Rim"), TrV=r(g, 0, 50)).set(
        aeg_mode="ad", attack=0, decay=aeg(u(g, .08, .2)), slope=r(g, 25, 45)).hp(u(g, 400, 900))


# =============================================================================
# the techno rumble (make_techno.py), shared by INDUSTRIAL
# =============================================================================
def _rumble(c, g, lp=(140, 420)):
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
    c = make("GND", r(g, 40, 60), Wav="Noi", Swp=64, SwD=0)
    return c.set(filt_type="lp", filt_freq=ff(u(g, 60, 140)), filt_reso=r(g, 85, 110), drive=r(g, 30, 70),
                 aeg_mode="ad", attack=r(g, 1, 6), decay=aeg(u(g, .2, .35)), slope=r(g, 30, 45))


def rumble_penalty(m):
    """techno rumble: low, warm, no click (on top of base_penalty)"""
    f = m["feat"]
    b = f["bands"]
    fq, lvl, prom = m["tone"]
    pen = out_of_whistle(fq, lvl, prom, 500)
    pen += mk.out_of(b["sub"] + b["low"], 0.45, 1.0, 0.04)
    pen += mk.out_of(f["centroid"], 50, 380, 40)
    pen += max(0.0, b["himid"] + b["high"] + b["air"] - 0.04) / 0.01
    pen += max(0.0, f["harsh"] - 0.4) / 0.05
    return pen


# =============================================================================
# voice choice: no repeated combinations
# =============================================================================
MAX_SHARED = 3      # two kits share at most this many pool voices
USED = {}           # (family, role, index) -> times used
ENG_USED = {}       # (role, engine) -> times used
KITS = []           # voice keys of the kits built so far
ENGINE_SPREAD = 6.0  # an engine that was used this often in a role gets half the weight


def _weights(items, fam, role, avoid, uses):
    w = []
    for idx, (c, pen, m) in enumerate(items):
        n = USED.get((fam, role, idx), 0)
        x = 0.0 if (n >= uses or (fam, role, idx) in avoid) else (1.0 / (1.0 + max(pen, 0.0))) * (0.35 if n else 1.0)
        # spread the roles over all the engines in the pool
        x /= 1.0 + ENG_USED.get((role, c.engine), 0) / ENGINE_SPREAD
        w.append(x)
    return w


def choose_voices(rng, pools, src, tries=60, uses=2):
    """one voice per role from pools[src[k]][role]; src: family per role.
    Each pool voice is used at most <uses> times while there are unused
    ones; the kit's voices may not repeat more than MAX_SHARED voices of
    any earlier kit. Returns [(channel, slim measurement)] and the keys."""
    best = None
    for t in range(tries):
        keys = []
        for k, role in enumerate(mk.ROLES):
            fam = src[k]
            items = pools[fam][role]
            w = _weights(items, fam, role, (), uses)
            if sum(w) == 0:
                w = [1.0 / (1.0 + max(p, 0.0)) for _, p, _ in items]
            idx = rng.choices(range(len(items)), w)[0]
            keys.append((fam, role, idx))
        shared = max((sum(a == b for a, b in zip(keys, prev)) for prev in KITS), default=0)
        if best is None or shared < best[0]:
            best = (shared, keys)
        if shared <= MAX_SHARED:
            break
    keys = best[1]
    for key in keys:
        USED[key] = USED.get(key, 0) + 1
        fam, role, idx = key
        e = (role, pools[fam][role][idx][0].engine)
        ENG_USED[e] = ENG_USED.get(e, 0) + 1
    KITS.append(keys)
    out = []
    for fam, role, idx in keys:
        c, pen, m = pools[fam][role][idx]
        out.append((c.copy(), m))
    return out, keys


LXR_ENGINES = {"Drm", "Snr", "Cym", "Hat"}
LXR_SHARE = 0.15    # the original LXR voices are a seasoning: at most this share of a pool
ENGINE_SHARE = 0.4  # no engine fills more than this share of a pool


def filter_pools(pools, max_penalty, keep_min=8, keep_max=64):
    for fam, roles in pools.items():
        for role, items in roles.items():
            good = [x for x in items if x[1] <= max_penalty]
            good = good if len(good) >= keep_min else items[:keep_min]
            # SHARD engines first: keep the LXR voices to a small share
            size = min(len(good), keep_max)
            lxr_max = max(1, int(size * LXR_SHARE))
            eng_max = max(4, int(size * ENGINE_SHARE))
            kept, n_lxr, n_eng = [], 0, {}
            for x in good:
                e = x[0].engine
                if n_eng.get(e, 0) >= eng_max:
                    continue
                if e in LXR_ENGINES:
                    if n_lxr >= lxr_max:
                        continue
                    n_lxr += 1
                n_eng[e] = n_eng.get(e, 0) + 1
                kept.append(x)
            roles[role] = kept[:keep_max]
            engs = {}
            for c, _, _ in roles[role]:
                engs[c.engine] = engs.get(c.engine, 0) + 1
            print(f"pool {fam:9s} {role:5s}: {len(roles[role]):3d} voices  "
                  + " ".join(f"{e}:{n}" for e, n in sorted(engs.items(), key=lambda x: -x[1])), flush=True)


def probe(archs, role, n=12, seed="probe"):
    """design aid (PROBE=<role>): render n variants of every archetype of a
    role and print how well they fit it"""
    import statistics as st
    tmp = os.path.join(mk.WORK, "probe.snd")
    for a in archs:
        rng = random.Random(f"{seed}-{a.__name__}")
        cands = [a(rng) for _ in range(n)]
        rows = []
        for i in range(0, n, 6):
            group = cands[i:i + 6]
            mk.write_blocks(group + [Channel("GND").set(vol=0)] * (6 - len(group)), tmp)
            m = analyse(mk.RENDER, tmp, with_features=True, alt_all=True)
            for j, c in enumerate(group):
                alt = m[6 + j] if role == "hats" else None
                rows.append((mk.role_penalty(role, m[j], alt, c.s("vol")), m[j]))
        pens = sorted(p for p, _ in rows)
        med = lambda f: st.median(f(x) for _, x in rows)  # noqa: E731
        print(f"{a.__name__:18s} pen min {pens[0]:6.2f} med {st.median(pens):6.2f}  "
              f"ring {med(lambda x: x['ring']):.2f} hf {med(lambda x: x['hf']):.2f} "
              f"cen {med(lambda x: x['feat']['centroid']):6.0f} loud {med(lambda x: x['feat']['loud']):6.1f} "
              f"f0 {med(lambda x: x['feat']['f0']):6.1f} ton {med(lambda x: x['feat']['tonal']):5.1f} "
              f"sl {med(lambda x: x['feat']['bands']['sub'] + x['feat']['bands']['low']):.2f} "
              f"harsh {med(lambda x: x['feat']['harsh']):.2f}", flush=True)


def maybe_probe(arch_by_role):
    role = os.environ.get("PROBE")
    if not role:
        return
    archs = arch_by_role[role]
    probe(archs, role.split(":")[0] if ":" in role else role)
    raise SystemExit(0)


# =============================================================================
# the bank loop
# =============================================================================
# a dense groove on top of the theme's: every channel busy, accents, so a kit
# stays clean when it is played harder than its theme groove
STRESS = ["X...X...X...X...", ".xxx.xxx.xxx.xxx", "x.x..x.x..x.x..x", "....X.......X...", "....x.......x..x",
          "xxoxxxoxxxoxxxox"]


def _merge(a, b):
    out = []
    for x, y in zip(a, b):
        for c in "Xorx":
            if c in (x, y):
                out.append(c)
                break
        else:
            out.append(".")
    return "".join(out)


def stress_groove(kit, path, merge=True):
    pat = os.path.join(mk.WORK, "stress.txt")
    with open(pat, "w") as f:
        f.write("\n".join(_merge(a, b) if merge else b for a, b in zip(mk.GROOVES[kit.theme], STRESS)) + "\n")
    met = os.path.join(mk.WORK, "stress.json")
    kit.write(path)
    subprocess.run([mk.RENDER, "--kit", path, pat, str(kit.bpm), "2", "", met], check=True)
    return json.load(open(met))


DC_MAX = 0.008      # mean of the groove output (full scale 1): the tube drive is asymmetric
PEAK_MAX = 0.92     # groove and stress peaks: some headroom for other patterns


def groove_dc(wav):
    import wave
    import numpy as np
    w = wave.open(wav)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2) / 32768
    return float(np.max(np.abs(x.mean(axis=0))))


def clean_master(kit, path):
    """mk.master, then: no DC from the tube drive bus, and neither the theme
    groove, the dense stress groove nor the stress groove alone clips (all
    channels scaled together: the balance stays)"""
    m = mk.master(kit, path)
    wav = os.path.join(mk.WORK, "groove.wav")
    f = kit.fx
    for _ in range(6):
        m["dc"] = groove_dc(wav)
        if m["dc"] <= DC_MAX or f["type"] != "drv":
            break
        if f["dist"] == 0 and f["p"][0] > 20:
            f["p"][0] = int(f["p"][0] * 0.7)          # less tube drive
        else:
            f["dist"], f["p"][1] = 2, 0               # symmetric clipper, no offset
        m = mk.render_groove(kit, path, wav)
    for it in range(16):
        s1 = stress_groove(kit, path, merge=True)
        s2 = stress_groove(kit, path, merge=False)
        peak = max(m["out_peak"], s1["out_peak"], s2["out_peak"])
        if not (m["clip"] or s1["clip"] or s2["clip"]) and peak <= PEAK_MAX + 0.02:
            break
        g = min(0.97, PEAK_MAX / max(peak, 1e-3))
        for c in kit.ch:
            c.set(vol=max(4, c.s("vol") * g))
        if it >= 6 and f["type"] in ("drv", "cmp"):
            f["p"][3] = max(10, int(f["p"][3] * 0.85))  # a saturating bus keeps its level: turn the bus down
        m = mk.render_groove(kit, path, wav)
    m["dc"] = groove_dc(wav)
    m["stress_peak"] = max(s1["out_peak"], s2["out_peak"])
    m["stress_clip"] = s1["clip"] + s2["clip"]
    return m


def run_bank(seed, family, bank, nfo, build_kit, after_retune=None):
    """build 128 kits: build_kit(rng, i) -> Kit (voices from choose_voices);
    after_retune(kit, path, rng) may replace voices that didn't tune."""
    assert len(nfo) == 8
    kit_dir = os.path.join(mk.OUT, "shard", f"prj{bank:02d}")
    os.makedirs(kit_dir, exist_ok=True)
    only = set(int(x) for x in os.environ.get("ONLY", "").split(",") if x)
    first = int(os.environ.get("FIRST", "0"))
    report_path = os.path.join(mk.OUT, "bank.json")
    report = json.load(open(report_path)) if ((first or only) and os.path.exists(report_path)) else []
    report = [x for x in report if x["slot"] < first or (only and x["slot"] not in only)]
    if not only and not first:
        for f in os.listdir(kit_dir):
            os.unlink(os.path.join(kit_dir, f))
    log = []
    names = set()
    for i in range(128):
        rng = random.Random(f"{seed}-{i}")
        kit = build_kit(rng, i)
        assert kit.name not in names, kit.name
        names.add(kit.name)
        if (only and i not in only) or i < first:
            continue
        path = os.path.join(kit_dir, mk.file_name(i, kit.name))
        undone = mk.retune_check(kit, path)
        if after_retune:
            undone += after_retune(kit, path, rng)
        fixed = mk.fix_kit(kit, path, log)
        mk.balance(kit, path)
        mk.groove_guard(kit, path)
        m = clean_master(kit, path)
        kit.write(path)
        kick = analyse(mk.RENDER, path, with_features=True)[0]
        kick_loud = kick["feat"]["loud"] if "feat" in kick else None
        rep = dict(slot=i, name=kit.name, family=family, theme=kit.theme, bpm=kit.bpm, key=kit.keyname,
                   engines=[c.engine for c in kit.ch], archs=[c.arch for c in kit.ch], fx=kit.fx["type"],
                   out=m["out_peak"], clip=m["clip"], tail=m["tail"], fixed=fixed,
                   stress_out=m["stress_peak"], stress_clip=m["stress_clip"], kick_loud=kick_loud, dc=m["dc"],
                   tuned=len(kit.tuned) - undone, notes=kit.notes, vols=[c.s("vol") for c in kit.ch])
        rep.update(getattr(kit, "extra", {}))
        report = [x for x in report if x["slot"] != i] + [rep]
        report.sort(key=lambda x: x["slot"])
        print(f"{i:3d} {kit.name:8s} {kit.theme:10s} {kit.bpm:3d} {kit.keyname:12s} "
              f"{' '.join(c.engine for c in kit.ch)} fx={kit.fx['type']} fix={fixed} tuned={rep['tuned']} "
              f"out={m['out_peak']:.2f} clip={m['clip']} stress={m['stress_peak']:.2f}/{m['stress_clip']}", flush=True)
        with open(report_path, "w") as f:
            json.dump(report, f, indent=1)
    with open(os.path.join(kit_dir, "prj.nfo"), "wb") as f:
        f.write(nfo)
    with open(os.path.join(mk.OUT, "fixlog.txt"), "a") as f:
        f.write("\n".join(log) + "\n")
    print(f"{len(report)} kits in {kit_dir}")


def new_kit(prefix, name, family, theme, bpm):
    return mk.Kit((prefix + name)[:8], family, theme, bpm)


def set_key(kit, rng, scales):
    kit.key = (rng.randrange(12), rng.choice(list(scales.values())))
    kit.keyname = mk.NOTE_NAMES[kit.key[0]] + " " + [k for k, v in scales.items() if v == kit.key[1]][0]


def check_names(prefix, names):
    full = [(prefix + n)[:8] for n in names]
    assert len(names) >= 128 and len(set(full[:128])) == 128, \
        [n for n in full if full.count(n) > 1]
    assert all(n.isascii() and n.isalnum() for n in names[:128])
