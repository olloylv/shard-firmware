#!/usr/bin/env python3
"""Draw the manual's diagrams as standalone SVG files.

    python3 tools/docs/make_diagrams.py docs/img

cv-matrix.svg  sources -> 36 slots -> destinations
fx-path.svg    channel outputs, FX bus and output stage

The files carry their own white background, so they read on light and dark
GitHub themes alike.
"""
import os
import sys

FONT = "font-family=\"-apple-system,Segoe UI,Helvetica,Arial,sans-serif\""
RAMP = {  # fill, stroke, title, subtitle
    "teal":   ("#E1F5EE", "#0F6E56", "#085041", "#0F6E56"),
    "purple": ("#EEEDFE", "#534AB7", "#3C3489", "#534AB7"),
    "gray":   ("#F1EFE8", "#888780", "#2C2C2A", "#5F5E5A"),
}
LINE = "#5F5E5A"


def box(x, y, w, h, title, sub=None, ramp="gray", rx=8, extra=()):
    f, s, t, st = RAMP[ramp]
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{f}" stroke="{s}" stroke-width="0.8"/>']
    cx = x + w / 2
    lines = [(title, 14, 500, t)] + ([(sub, 12, 400, st)] if sub else []) + [(e, 12, 400, st) for e in extra]
    y0 = y + h / 2 - (len(lines) - 1) * 10
    for i, (txt, size, weight, col) in enumerate(lines):
        out.append(f'<text x="{cx}" y="{y0 + i * 20}" text-anchor="middle" dominant-baseline="central" '
                   f'font-size="{size}" font-weight="{weight}" fill="{col}">{txt}</text>')
    return "\n".join(out)


def arrow(d):
    return f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="1.2" marker-end="url(#a)"/>'


def svg(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" {FONT} role="img">
<title>{title}</title>
<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
<path d="M2 1L8 5L2 9" fill="none" stroke="{LINE}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>
<rect x="0" y="0" width="{w}" height="{h}" rx="12" fill="#FFFFFF"/>
{body}
</svg>
"""


def cv_matrix():
    b = []
    for i, (t, s) in enumerate([("CV 1–5", "cv1–cv5, jacks"), ("LFO 1–6", "lf1–lf6, one per channel"),
                                ("Accents 1–6", "ac1–ac6, gates")]):
        y = 76 + i * 66
        b.append(box(40, y, 170, 56, t, s, "teal"))
        b.append(arrow(f"M210 {y + 28} L246 {y + 28}"))
    b.append(box(250, 40, 170, 260, "36 slots", "6 per channel", "gray",
                 extra=("source · amount · dest", "amount 0–100", "bipolar around the knob")))
    dests = [("Global", "Mrp Mtg Msh Fwt Fx1–4"), ("Engine, ch 1–6", "VO pitch, params 1–14"),
             ("Strip, ch 1–6", "AEG, filter, mix, LFO"), ("Ring, ch 1–6", "Rng RFq, end of list")]
    for i, (t, s) in enumerate(dests):
        y = 40 + i * 68
        b.append(arrow(f"M420 {y + 28} L466 {y + 28}"))
        b.append(box(470, y, 170, 56, t, s, "purple"))
    return svg(680, 340, "SHARD CV matrix", "\n".join(b))


def fx_path():
    b = []
    b.append(box(230, 40, 220, 56, "Channels 1–6", "MIX page, Out per channel"))
    b.append(arrow("M290 96 L290 116 L160 116 L160 134"))
    b.append(arrow("M390 96 L390 116 L520 116 L520 134"))
    b.append(box(60, 136, 200, 56, "Direct outs", "St1 St2 L1 R1 L2 R2"))
    b.append(box(420, 136, 200, 56, "FX send", "Out = FX, stereo sum", "purple"))
    b.append(arrow("M520 192 L520 218"))
    b.append(f'<rect x="340" y="220" width="300" height="140" rx="12" fill="none" stroke="#888780" '
             f'stroke-width="0.8" stroke-dasharray="4 4"/>')
    b.append(f'<text x="490" y="244" text-anchor="middle" dominant-baseline="central" font-size="14" '
             f'font-weight="500" fill="#2C2C2A">FX bus: one type at a time</text>')
    f, s, t, _ = RAMP["purple"]
    for i, n in enumerate(["drv", "glt", "cmp", "del", "rng"]):
        x = 358 + i * 56
        b.append(f'<rect x="{x}" y="262" width="48" height="32" rx="4" fill="{f}" stroke="{s}" stroke-width="0.8"/>')
        b.append(f'<text x="{x + 24}" y="278" text-anchor="middle" dominant-baseline="central" font-size="12" fill="{t}">{n}</text>')
    for y, txt in ((318, "P1–P4 + type/wave"), (338, "CV: Fwt, Fx1–Fx4 · morph")):
        b.append(f'<text x="490" y="{y}" text-anchor="middle" dominant-baseline="central" font-size="12" fill="#5F5E5A">{txt}</text>')
    b.append(arrow("M520 360 L520 390"))
    b.append(box(420, 392, 200, 56, "Dry/wet + FX out", "return to the chosen pair", "purple"))
    b.append(arrow("M160 192 L160 486"))
    b.append(arrow("M520 448 L520 486"))
    b.append(box(100, 488, 480, 56, "Float mix bus", "direct outs + FX return, no clipping", "teal"))
    b.append(arrow("M340 544 L340 572"))
    b.append(box(230, 574, 220, 56, "Soft limiter", "clean up to −1 dBFS", "teal"))
    b.append(arrow("M340 630 L340 658"))
    b.append(box(230, 660, 220, 56, "DAC 1 · DAC 2", "24 bit, 44.1 kHz", "teal"))
    return svg(680, 740, "SHARD FX bus and output stage", "\n".join(b))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/img"
    os.makedirs(out, exist_ok=True)
    for name, fn in (("cv-matrix.svg", cv_matrix), ("fx-path.svg", fx_path)):
        with open(os.path.join(out, name), "w") as f:
            f.write(fn())
        print(os.path.join(out, name))
