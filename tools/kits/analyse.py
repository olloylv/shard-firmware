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


def analyse(render, kit_path):
    with tempfile.NamedTemporaryFile(suffix=".f32", delete=False) as t:
        tmp = t.name
    try:
        subprocess.run([render, "--hits", kit_path, str(SECONDS), tmp], check=True)
        data = np.fromfile(tmp, dtype=np.float32)
    finally:
        os.unlink(tmp)
    per = len(data) // RUNS
    res = []
    for r in range(RUNS):
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
        res.append(dict(peak=pk, ring=ring, hf=hf, tone=_tone(x, pk), punch=float(punch)))
    return res


if __name__ == "__main__":
    for p in sys.argv[2:]:
        m = analyse(sys.argv[1], p)
        print(os.path.basename(p))
        for i, c in enumerate(m):
            f, lvl, prom = c["tone"]
            print(f"  {'ch' + str(i + 1) if i < 6 else 'ch6o'}: peak {c['peak']:.2f} ring {c['ring']:.2f}s "
                  f"hf {c['hf']:.2f}s tone {f:6.0f}Hz {lvl:6.1f}dB prom {prom:5.1f} punch {c['punch']:5.1f}")
