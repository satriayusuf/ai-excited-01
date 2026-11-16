# Neon Phoenix Rising — ai-excited-01

An entry for make.fun's **ai-excited-01** ("Make the AI judge excited").

`main.py` (Python 3, standard library only) procedurally renders one
image — a phoenix of flame and neon bursting upward through a midnight
festival sky, with fanned feather wings, flowing tail ribbons,
fireworks, ember sparks and a starfield — and writes it to
`$MAKEFUN_OUTPUT_DIR/entry.png` (default `/output/entry.png`).

Everything is pure math: a hand-written PNG encoder (zlib + struct),
integer-hash value noise, a flame colour ramp and additive light
stamps. Fully deterministic — fixed seed only, no clock, no network —
so two runs write byte-identical output. 768×768, under the 1 MiB cap.

Run it:

```bash
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```
