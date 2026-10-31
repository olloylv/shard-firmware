"""Single hit analysis of SHARD kits (used by make_kits.py).

    python3 tools/kits/analyse.py <shard_render> kit.snd [kit.snd ...]

For every channel (and channel 6 from the alt trigger) one hit is rendered
dry, after the channel strip. Measured:

  peak    peak level
  ring    seconds until the level stays 40 dB below the peak (hanging notes)
  hf      seconds the part above 3.5 kHz stays within 36 dB of the peak
  tone    strongest narrow peak above 1.5 kHz between 150 and 500 ms after the
          hit: (frequency, level re peak in dB, prominence in dB). A loud,
          prominent one is a whistle / long high note.
  punch   peak of the first 25 ms over the RMS of 25..150 ms (dB)
  feat    (with features=True) spectral and loudness features for the bank
          generator: band energy fractions, centroid, attack time, K-weighted
          loudness (loudest 100 ms), 2..5 kHz share (harshness), spectral
          flux (movement), dominant pitch below 1.2 kHz and how tonal it is

SPDX-License-Identifier: GPL-3.0-only
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
from scipy.signal import butter, sosfilt

RATE = 44140
SECONDS = 2.5
BLOCK = 64
RUNS = 7
_SOS_HP = butter(4, 3500, "highpass", fs=RATE, output="sos")

BANDS = [("sub", 20, 60), ("low", 60, 150), ("lowmid", 150, 400), ("mid", 400, 1500),
         ("himid", 1500, 5000), ("high", 5000, 12000), ("air", 12000, 22000)]


def _shelf(f0, gain_db, q=0.707):
    """RBJ high shelf as one sos section"""
    A = 10 ** (gain_db / 40)
    w = 2 * np.pi * f0 / RATE
    alpha = np.sin(w) / (2 * q)
    cw = np.cos(w)
    b0 = A * ((A + 1) + (A - 1) * cw + 2 * np.sqrt(A) * alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * cw)
    b2 = A * ((A + 1) + (A - 1) * cw - 2 * np.sqrt(A) * alpha)
    a0 = (A + 1) - (A - 1) * cw + 2 * np.sqrt(A) * alpha
    a1 = 2 * ((A - 1) - (A + 1) * cw)
    a2 = (A + 1) - (A - 1) * cw - 2 * np.sqrt(A) * alpha
    return np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]])


_SOS_K = np.vstack([butter(2, 40, "highpass", fs=RATE, output="sos"), _shelf(1600, 4.0)])


def features(x):
    """spectral / loudness features of one hit (starts at sample 64)"""
    x = x[64:]
    n = len(x)
    pk = np.max(np.abs(x)) + 1e-12
    seg = x[: int(0.4 * RATE)]
    # spectrum of the hit (energy weighted by the signal itself)
    N = 1 << int(np.ceil(np.log2(len(seg))))
    S = np.abs(np.fft.rfft(seg, N)) ** 2
    f = np.fft.rfftfreq(N, 1 / RATE)
    tot = np.sum(S) + 1e-20
    bands = {name: float(np.sum(S[(f >= lo) & (f < hi)]) / tot) for name, lo, hi in BANDS}
    centroid = float(np.sum(f * S) / tot)
    harsh = float(np.sum(S[(f >= 2000) & (f < 5000)]) / tot)
    # attack: 1 ms envelope to 90 % of its maximum
    w = 44
    e = np.sqrt(np.mean(x[: (min(n, RATE // 4) // w) * w].reshape(-1, w) ** 2, axis=1))
    attack = float(np.argmax(e >= 0.9 * e.max()) * w / RATE * 1000)
    # K-weighted loudness of the first 400 ms
    # loudest 100 ms window (percussive sounds are heard over ~100 ms)
    k = sosfilt(_SOS_K, seg) ** 2
    win, hop = int(0.1 * RATE), int(0.02 * RATE)
    loud = float(10 * np.log10(max(np.mean(k[i:i + win]) for i in range(0, max(1, len(k) - win), hop)) + 1e-12))
    # spectral flux over the first 300 ms (normalised): movement / detail
    fr = 1024
    frames = [x[i:i + fr] * np.hanning(fr) for i in range(0, int(0.3 * RATE) - fr, fr // 2)]
    mags = [np.abs(np.fft.rfft(a)) for a in frames]
    flux = 0.0
    for a, b in zip(mags, mags[1:]):
        na, nb = a / (np.linalg.norm(a) + 1e-12), b / (np.linalg.norm(b) + 1e-12)
        flux += float(np.sum((nb - na) ** 2))
    flux /= max(1, len(mags) - 1)
    # dominant pitch below 1.2 kHz, 20..250 ms after the hit
    t0, t1 = int(0.02 * RATE), int(0.25 * RATE)
    tseg = x[t0:t1]
    f0, tonal = 0.0, 0.0
    if len(tseg) > 2048 and np.max(np.abs(tseg)) > pk * 0.01:
        M = 16384
        P = np.abs(np.fft.rfft(tseg * np.hanning(len(tseg)), M))
        ff = np.fft.rfftfreq(M, 1 / RATE)
        sel = (ff > 30) & (ff < 1200)
        i = int(np.argmax(np.where(sel, P, 0)))
        if 0 < i < len(P) - 1:
            a, b, c = np.log(P[i - 1] + 1e-12), np.log(P[i] + 1e-12), np.log(P[i + 1] + 1e-12)
            d = 0.5 * (a - c) / (a - 2 * b + c + 1e-12)
            f0 = float((i + d) * RATE / M)
            band = P[(ff > f0 / 1.4) & (ff < f0 * 1.4)]
            tonal = float(20 * np.log10(P[i] / (np.median(band) + 1e-12)))
    return dict(bands=bands, centroid=centroid, harsh=harsh, attack=attack, loud=loud, flux=flux,
                f0=f0, tonal=tonal, dc=float(np.mean(x[: int(0.5 * RATE)]) / pk))


def _env(x, win=220):
    n = len(x) // win
    return np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1) + 1e-20)


def _last_above(env, thr, win=220):
    idx = np.nonzero(env > thr)[0]
    return 0.0 if len(idx) == 0 else (idx[-1] + 1) * win / RATE


def _tone(x, pk):
    a, b = int(0.15 * RATE), int(0.5 * RATE)
    seg = x[a:b]
    if np.max(np.abs(seg)) < pk * 10 ** (-60 / 20):
        return (0.0, -120.0, 0.0)
    n = 4096
    w = np.hanning(n)
    specs = [np.abs(np.fft.rfft(seg[i:i + n] * w)) for i in range(0, len(seg) - n, n // 2)]
    s = np.mean(specs, axis=0)
    f = np.fft.rfftfreq(n, 1 / RATE)
    band = f > 1500
    i = np.argmax(np.where(band, s, 0))
    lo, hi = np.searchsorted(f, f[i] / 1.5), np.searchsorted(f, min(f[i] * 1.5, RATE / 2 - 1))
    med = np.median(s[lo:hi]) + 1e-12
    amp = 2 * s[i] / np.sum(w)
    return (float(f[i]), float(20 * np.log10(amp / pk + 1e-12)), float(20 * np.log10(s[i] / med)))


def analyse(render, kit_path, with_features=False, alt_all=False):
    with tempfile.NamedTemporaryFile(suffix=".f32", delete=False) as t:
        tmp = t.name
    try:
        subprocess.run([render, "--hits12" if alt_all else "--hits", kit_path, str(SECONDS), tmp], check=True)
        data = np.fromfile(tmp, dtype=np.float32)
    finally:
        os.unlink(tmp)
    runs = 12 if alt_all else RUNS
    per = len(data) // runs
    res = []
    for r in range(runs):
        x = data[r * per:(r + 1) * per].astype(np.float64)
        pk = float(np.max(np.abs(x)))
        if pk < 1e-5:
            res.append(dict(peak=0.0, ring=0.0, hf=0.0, tone=(0.0, -120.0, 0.0), punch=0.0))
            continue
        env = _env(x)
        ring = _last_above(env, np.max(env) * 10 ** (-40 / 20))
        hf = _last_above(_env(sosfilt(_SOS_HP, x)), np.max(env) * 10 ** (-36 / 20))
        a = x[: int(0.025 * RATE)]
        b = x[int(0.025 * RATE): int(0.15 * RATE)]
        punch = 20 * np.log10(np.max(np.abs(a)) / (np.sqrt(np.mean(b ** 2)) + 1e-9) + 1e-9)
        d = dict(peak=pk, ring=ring, hf=hf, tone=_tone(x, pk), punch=float(punch))
        if with_features:
            d["feat"] = features(x)
        res.append(d)
    return res


if __name__ == "__main__":
    for p in sys.argv[2:]:
        m = analyse(sys.argv[1], p)
        print(os.path.basename(p))
        for i, c in enumerate(m):
            f, lvl, prom = c["tone"]
            print(f"  {'ch' + str(i + 1) if i < 6 else 'ch6o'}: peak {c['peak']:.2f} ring {c['ring']:.2f}s "
                  f"hf {c['hf']:.2f}s tone {f:6.0f}Hz {lvl:6.1f}dB prom {prom:5.1f} punch {c['punch']:5.1f}")
