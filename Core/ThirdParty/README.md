# Third-party DSP code

| Directory | Origin | Licence |
|---|---|---|
| `plaits/` | Mutable Instruments Plaits, <https://github.com/pichenettes/eurorack> (subset: drums, physical modelling, particles) | MIT, see file headers |
| `stmlib/` | Mutable Instruments stmlib, <https://github.com/pichenettes/stmlib> (subset: dsp and utils) | MIT, see `stmlib/LICENSE` |

Both are Copyright Emilie Gillet. The MIT licence is compatible with the GPL-3.0 licence of
this firmware. Files are copied unchanged except where marked "SHARD modification"
(`plaits/dsp/dsp.h`: sample rate; `plaits/resources.cc`: only the lookup tables used here).
