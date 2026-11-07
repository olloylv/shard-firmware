#!/usr/bin/env python3
"""One-page SHARD quick reference (A4 PDF).

    python3 tools/docs/make_quickref.py SHARD_quickref.pdf

Needs reportlab and the DejaVu fonts (fonts-dejavu-core).
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Table, TableStyle, Spacer, FrameBreak)
import sys

D = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("C", D + "DejaVuSansCondensed.ttf"))
pdfmetrics.registerFont(TTFont("CB", D + "DejaVuSansCondensed-Bold.ttf"))
pdfmetrics.registerFont(TTFont("M", D + "DejaVuSansMono.ttf"))
from reportlab.lib.fonts import addMapping
addMapping("C", 0, 0, "C"); addMapping("C", 1, 0, "CB")
addMapping("C", 0, 1, "C"); addMapping("C", 1, 1, "CB")

ACC = colors.HexColor("#C2410C")
INK = colors.HexColor("#1F2328")
MUTED = colors.HexColor("#5B6168")
RULE = colors.HexColor("#D9DCE0")
BAND = colors.HexColor("#F3F4F6")

FS = 7.8
body = ParagraphStyle("b", fontName="C", fontSize=FS, leading=FS * 1.28, textColor=INK, spaceAfter=1.6)
bul = ParagraphStyle("bl", parent=body, leftIndent=7, bulletIndent=0, spaceAfter=0.8)
h2 = ParagraphStyle("h2", fontName="CB", fontSize=9.2, leading=11, textColor=ACC, spaceBefore=5, spaceAfter=2.2)
cell = ParagraphStyle("c", parent=body, spaceAfter=0, leading=FS * 1.2)
cellb = ParagraphStyle("cb", parent=cell, fontName="CB")
title = ParagraphStyle("t", fontName="CB", fontSize=21, leading=23, textColor=INK)
sub = ParagraphStyle("s", fontName="C", fontSize=8.6, leading=11, textColor=MUTED)

def P(t, s=body): return Paragraph(t, s)
def B(t): return Paragraph(t, bul, bulletText="•")
def code(t): return f'<font name="M" size="{FS-0.6}">{t}</font>'

def table(rows, widths, head=True, bold_first=True):
    data = []
    for i, r in enumerate(rows):
        data.append([Paragraph(c, cellb if ((head and i == 0) or (bold_first and j == 0)) else cell)
                     for j, c in enumerate(r)])
    t = Table(data, colWidths=widths)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 2.5), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
          ("TOPPADDING", (0, 0), (-1, -1), 1.3), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
          ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE)]
    if head:
        st += [("BACKGROUND", (0, 0), (-1, 0), BAND), ("LINEBELOW", (0, 0), (-1, 0), 0.7, INK)]
    t.setStyle(TableStyle(st))
    return t

W, H = A4
M = 11 * mm
GAP = 6 * mm
HEAD_H = 19 * mm
colw = (W - 2 * M - GAP) / 2
top = H - M - HEAD_H

def deco(c, doc):
    c.saveState()
    c.setFillColor(ACC); c.rect(M, H - M - HEAD_H + 2 * mm, 2.2 * mm, HEAD_H - 4 * mm, stroke=0, fill=1)
    c.setStrokeColor(RULE); c.setLineWidth(0.5)
    c.line(M, top - 1 * mm, W - M, top - 1 * mm)
    c.line(M + colw + GAP / 2, M + 6 * mm, M + colw + GAP / 2, top - 4 * mm)
    c.setFont("C", 6.6); c.setFillColor(MUTED)
    c.drawString(M, M, "SHARD v" + VERSION + " · unofficial firmware based on the open-source LXR firmware (GPL-3.0) · "
                 "not made or supported by Erica Synths · Plaits code by Mutable Instruments (MIT)")
    c.restoreState()

frames = [Frame(M + 5 * mm, top, W - 2 * M - 5 * mm, HEAD_H, id="head", leftPadding=0, rightPadding=0, topPadding=1, bottomPadding=0),
          Frame(M, M + 5 * mm, colw, top - M - 7 * mm, id="L", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0),
          Frame(M + colw + GAP, M + 5 * mm, colw, top - M - 7 * mm, id="R", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)]

VERSION = "0.5"
out = sys.argv[1]
doc = BaseDocTemplate(out, pagesize=A4, leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M,
                      title="SHARD v" + VERSION + " quick reference", author="SHARD")
doc.addPageTemplates([PageTemplate(id="p", frames=frames, onPage=deco)])

s = []
s += [P("SHARD <font name='C' size='13' color='#5B6168'>v" + VERSION + " · custom firmware for the Erica Synths LXR Eurorack</font>", title),
      P("LXR panel and menus, but instead of fixed voices there are 23 engines, any of them on any of the 6 channels. "
        "A common channel strip with ring mod, a CV matrix that reaches any parameter of any channel, 100 kit banks, firmware update from the SD card menu.", sub),
      FrameBreak()]

# ---------- LEFT ----------
s += [P("Channels and triggers", h2),
      B("6 identical channels. <b>T1–T6</b> fire channels 1–6."),
      B("<b>T7</b> is a second trigger for channel 6: hat engines (pHH, tHH, Hat) play open, "
        "all other engines use <b>DcA</b> instead of Decay."),
      B("Buttons <b>1–6</b> select a channel (7 also opens channel 6)."),
      B("Accent inputs are gates: high at the trigger = full velocity, otherwise half."),
      P("Channel pages (EDIT)", h2),
      table([["Page", "Parameters"],
             ["OSC", "<b>Eng</b> engine, Tun note, Fin ±64 cents, engine parameters 1–5"],
             ["MOD/FM/SMP", "engine parameters 6–29; names come from the engine, empty slots are skipped"],
             ["AEG", "Atk, Dec, Slp, Rep (clap retrigger), DcA, Vel (velocity → level), Mod: AD / off"],
             ["FLT", "Frq, Res, Typ (off/LP/HP/BP/UBP/Nch/Pk/LP2), Drv (40 = unity gain) · ring: <b>Rng</b> amount, RFq 20 Hz–5 kHz, RSr sin/tri/sqr or c1–c6 (another channel)"],
             ["MIX", "Vol, Pan, SR (sample rate), Drv, <b>Out</b> (St1, St2, L1, R1, L2, R2, <b>FX</b>), <b>Bit</b>"],
             ["LFO", "Frq, Ofs, Wav, Rtg (retrigger from channel 1–6)"]],
            [22 * mm, colw - 22 * mm]),
      Spacer(1, 3),
      P("Channel chain: <b>engine → ring → filter → AEG → velocity → drive → volume → SR → Bit → pan/output</b>."),
      B("Changing the engine on the panel loads its defaults; loading a kit keeps the stored parameters."),
      B("Engines with their own envelope (Plaits drums, tBD, tSD, EFM, Zap, Crs) default to AEG <b>Mod = off</b>."),

      P("MOD: CV matrix", h2),
      B("<b>6 slots per channel</b> (36): source, amount (0–100), destination. The encoder steps through slots 1–2, 3–4, 5–6 and the channel LFO."),
      B("Sources: <b>cv1–5</b>, <b>lf1–6</b> (channel LFOs), <b>ac1–6</b> (accents)."),
      B("Destinations start with the global ones: <b>Mrp</b> morph amount, <b>Mtg</b> target kit, <b>Msh</b> sharpness, "
        "<b>Fwt</b> FX dry/wet, <b>Fx1–Fx4</b> effect P1–P4."),
      B("Then the parameters of <b>any</b> channel: " + code("3sw") + " = channel 3, Sweep. Empty engine slots are skipped."),
      B("<b>VO</b>: 1 V/oct pitch; at 100 % amount calibrated and quantised to semitones."),
      B("Ring amount / freq of channels 1–6 (" + code("1rn") + ", " + code("1rf") + ") come last, after channel 6."),

      P("PERF: morph", h2),
      B("Knobs: <b>Mrp</b> amount · <b>Mtg</b> target kit · <b>Alg</b> algorithm · <b>Shp</b> sharpness. "
        "Channels and FX are morphed; lists and the engine switch along the same curve."),
      table([["Alg", "How the morph moves (Shp 0–127)"],
             ["lin", "linear; Shp pushes past the target, up to 2× the difference"],
             ["snp", "S-curve, Shp narrows the transition to a jump (default Shp 48)"],
             ["sct", "every parameter has its own switch point at 12–88 %; high Shp = broken up"],
             ["stp", "steps: Shp 0 = 16, Shp 127 = 2 (A/B)"]],
            [10 * mm, colw - 10 * mm]),
      Spacer(1, 2),

      P("FX: shared effect bus", h2),
      B("Types: <b>off · drv</b> (tube/fold/clip) <b>· glt · cmp · del</b> (Del / Ping-pong) <b>· rng</b>."),
      B("<b>glt</b>: glitch triggered by hits of channels with Out = FX: <b>len</b> slice 15–300 ms, <b>chc</b> chance, "
        "<b>var</b> set of actions (repeat, reverse, ±octave, ratchet, tape stop, pitch steps), <b>rep</b> 1–8 repeats."),
      B("<b>rng</b>: ring mod. <b>wav</b> carrier (Sin/Tri/Saw/Rec/Noi/PWM), <b>frq</b> 20 Hz–5 kHz, <b>am</b> ring → AM, "
        "<b>spr</b> stereo detune, <b>rnd</b> random carrier jump per hit."),
      B("Only <b>channels with MIX → Out = FX</b> reach the effect. The banks already set this."),
      B("drv clip / fold: keep P2 = 0, otherwise high drive can self-oscillate."),
      ]
s.append(FrameBreak())

# ---------- RIGHT ----------
eng = [["#", "Eng", "What it is"],
       ["", "<b>LXR</b>", "<font color='#5B6168'>original LXR voices</font>"],
       ["0", "Drm", "LXR Drum: waveform, PWM, pitch envelope, FM, transient"],
       ["1", "Snr", "LXR Snare with its own noise filter"],
       ["2", "Cym", "LXR Cymbal, 3-operator FM"],
       ["3", "Hat", "LXR HiHat (open via T7 + DcA)"],
       ["", "<b>Plaits</b>", "<font color='#5B6168'>Mutable Instruments code</font>"],
       ["4", "aBD", "analogue kick: Ton, Dec, AFM, SFM, Drv"],
       ["5", "sBD", "synthetic kick: Ton, Dec, Drt, FMA, FMD"],
       ["6", "aSD", "analogue snare: Ton, Dec, Snp"],
       ["7", "sSD", "synthetic snare: FMA, Dec, Snp"],
       ["8", "pHH", "hat 808 / ring, Opn = decay for T7"],
       ["9", "Mdl", "modal resonator: Str, Bri, Dmp · <font color='#C2410C'>heavy</font>"],
       ["10", "Str", "Karplus-Strong string"],
       ["11", "Prt", "particles: Den, Res, Spr · <font color='#C2410C'>heavy</font>"],
       ["", "<b>MD-style</b>", "<font color='#5B6168'>inspired by the Machinedrum machines</font>"],
       ["12", "tBD", "kick: Swp, SwD, Dec, Hld, Clk, Drv"],
       ["13", "tSD", "snare: Bdy, Snp, Dec, NDc, Swp, NTn"],
       ["14", "tCP", "clap: Dec, Spc, Num, Q, Rnd"],
       ["15", "tHH", "hat: Ton, Dec, Mtl, Opn, Res"],
       ["16", "EFM", "2-op FM percussion: Rat, Mod, MDc, FB, Swp, Noi"],
       ["17", "GND", "Sin/Tri/Saw/Sqr/Noi/Imp/S&amp;H with sweep"],
       ["", "<b>IDM</b>", "<font color='#5B6168'>glitch engines written for SHARD</font>"],
       ["18", "Zap", "laser zap: Dep, Tim, FB, Dec, Dir"],
       ["19", "Crs", "crush source: Src, Rat, Bit, Jit, Dec, Glt"],
       ["20", "Byt", "bytebeat: formula Frm, A, B, Rst"],
       ["21", "Rng", "ring-modulated cluster"],
       ["22", "Cmb", "comb resonator: Exc, FB ±, Dmp, Bur, Rat, Mx2"]]
et = table(eng, [6 * mm, 16 * mm, colw - 22 * mm], bold_first=False)
fam_rows = [i for i, r in enumerate(eng) if r[0] == "" and i > 0]
et.setStyle(TableStyle([("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FBEDE5")) for i in fam_rows] +
                       [("FONTNAME", (1, 1), (1, -1), "CB")]))
s += [P("Engines (23)", h2), et]

s += [
      P("Kit banks · SD card", h2),
      B("LOAD/SAVE steps: <b>Load Kit → Save Kit → Save Morph → Load Bank → Save Bank</b>. Up to 100 banks of 128 kits in "
        + code("/shard/prj00…99") + "; the last bank comes back at power-on. LXR kits are not touched."),
      table([["Bank", "Contents · channel roles 1–6 (T7 = open hat on 6)"],
             ["00", "<b>SHARD05</b> factory: MD 0–31, PL 32–63, ID 64–111, HY 112–127 · kick, perc, FX, snare, clap, hat"],
             ["01", "<b>TECHNO</b> · kick, rumble, atmosphere, rim/snare, clap, hat"],
             ["02", "<b>ELECTRO</b> Detroit · 808 kick, perc, zaps, snare, clap, hat"],
             ["03", "<b>PSY</b> dark/forest · kick, rolling bass, FX, rim, clap, hat"],
             ["04", "<b>INDSTRL</b> · driven kick, rumble, metal, snare, clap, hat"]],
            [9 * mm, colw - 9 * mm]),
      Spacer(1, 2),
      P("Every kit in a key, levels balanced against the kick. Output: float mix bus, soft limiter."),

      P("Global menu · SHIFT + SAVE/LOAD", h2),
      B("<b>cpu</b>: peak load of the audio block, %. Init kit ≈ 47 %; 4–5 channels of Mdl/Prt ≈ 98 %."),
      B("<b>upd</b>: firmware update. Put " + code("LXRE_SHARD_Vx.x.img") +
        " in the SD root → upd → pick the file with the encoder → press, then press again to confirm."),
      B("Fallback: hold the encoder at power-on until \"LXR Updater\"; the bootloader flashes " + code("LXRE*.img") + "."),
      B("<b>ssv</b>: screensaver off/2m/5m/30s/10s, level meters of the six channels."),
      P("Cheat sheet", h2),
      B("AEG Dec: 20 ≈ 0.27 s · 30 ≈ 0.45 s · 50 ≈ 0.9 s · 80 ≈ 2.5 s · 90 ≈ 3.5 s."),
      B("Silent channel → check Out, Vol and the filter (HP on hats/cymbals)."),
      B("No effect → Out = FX and FX type not off."),
      ]

doc.build(s)
