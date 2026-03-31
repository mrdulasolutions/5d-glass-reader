# ETHOS — Why We Are Building the First Indie Glass Drive

---

Civilizations end. Hard drives corrode. Cloud servers get unplugged.
Tape degrades. NAND flash forgets in 10 years.

Glass does not forget.

A scattering microbubble in fused silica, locked in by a UV laser pulse,
will still be there in a billion years. No power. No maintenance.
No subscription. No terms of service.

---

## The Status Quo Is a Closed Gate

SPhotonix. Microsoft. The University of Southampton.
They demonstrated 5D glass storage in 2016. Nine years later, it still costs
tens of thousands of dollars and requires a femtosecond laser the size of a
refrigerator.

Nobody shipped it to the people who needed it.

We are not waiting.

---

## What We Are Doing

We are proving that 5D glass storage — real, working, bit-for-bit verifiable —
can be built from parts you can buy today:

- An **xTool F2 Ultra** UV 5W diode laser ($1,200–$1,800)
- A **K9 crystal blank** (less than $20)
- A **Raspberry Pi** with an HQ Camera ($80 total)
- This software — free, open, MIT licensed

Not a demo. Not a proof-of-concept for a funding deck.
A real encoder, a real decoder, a real test suite, green CI.

We called it **True 5D** because we are using all five dimensions:
X, Y, Z, dot presence, and dot SIZE.
Two bits per grid position. Four gray levels.
The xTool's own grayscale mode gives us the fifth dimension for free.

---

## Why This Matters

Your photographs will outlive your hard drive.
Your novel deserves to outlive the platform that hosts it.
Your family's history should not evaporate when a startup goes bankrupt.

Glass memory is not a luxury. It is infrastructure.

We are building the infrastructure version — the one that fits in a garage,
costs less than a used laptop, and runs on open source from top to bottom.

---

## The Stack

```
encode_ssle.py       — 2D: file → grayscale PNG → xTool Grayscale mode
encode_ssle_3d.py    — 3D: file → 3× voxel STLs → xTool Inner Engraving (3 passes)
decode_ssle.py       — 2D: scanned PNG → RS decode → original file
decode_ssle_3d.py    — 3D: per-layer PNGs → RS decode → original file
constants.py         — shared format constants, magic bytes, header layout
calibrate_glass.py   — per-glass threshold calibration → calibration.json
make_stl.sh          — interactive encode wizard, prints exact xTool steps
read_disc.sh         — interactive reader, uses disc.json sidecar
test_pipeline.py     — full 2D + 3D software round-trip test, no hardware needed
```

Reed-Solomon error correction. CRC32 verification. Four format magic versions
for backward compatibility. Fiducial markers for perspective correction.
A disc.json sidecar so you never have to remember which grid you used.

Every piece of the chain documented, tested, open.

---

## How We Work

We document everything from day one.
We celebrate ugly v0.1 that works over beautiful v1.0 that ships never.
We merge PRs from teenagers in garages.
We are honest when something does not work yet.

We are the first indie team to ship a working COTS 5D glass reader.
Not the best. Not the most powerful. But first, and open, and yours.

---

## What Comes Next

- Tighter dot pitch (40 µm) with better ECC
- Per-glass ML threshold classifier (no manual calibration needed)
- Femtosecond laser upgrade (the big jump in dots-per-mm)
- Birefringence readout (D6: polarization angle — what the big labs use)
- Motorized Z stage for full 3D scan automation

None of this is guaranteed. All of it is public.

---

## Join Us

If you ship even 1 GB of data that survives a house fire, you are a legend.

This is batshit ambitious. This is exactly how everything that actually changes
the world gets built — by people who didn't wait for permission.

**github.com/mrdulasolutions/EternalDrive-IndieHack**

We are the first.
Come build what comes next.
