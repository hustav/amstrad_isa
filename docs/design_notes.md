# Design notes - PPC ISA Expansion

This document captures the *why* behind specific schematic decisions that
might not be obvious from the netlist alone.  When in doubt about an
electrical choice, the answer almost always lives here.

## The two 74HC244 buffers

The Amstrad PPC sends some address and control signals onto the
expansion connector through its own 74HC244 (the chip labelled IC102 in
the PPC's main schematic).  Those signals are marked with a `b` suffix
in our netlist (`A00b..A07b`, `OSCb`, `MEMRb`, etc.) - the `b` stands
for *buffered on the PPC side*.

Our board has to **re-buffer** them before sending them onto the ISA
bus, because the loaded capacitance of three ISA slots plus their cards
is way above what the PPC's single buffer is rated for.

| Buffer | Inputs (from Amstrad) | Outputs (to ISA) |
| --- | --- | --- |
| U1 (74HC244 SOIC-20) | OSCb, CK4b, MEMRb, MEMWb, IORb, IOWb, ALEb, RESETb | OSC, CLK, ~SMEMR, ~SMEMW, ~IOR, ~IOW, ALE, RESET |
| U2 (74HC244 SOIC-20) | A07b, A06b, A05b, A04b, A03b, A02b, A01b, A00b | A07, A06, A05, A04, A03, A02, A01, A00 |

The other 12 address bits (A08..A19) are *not* buffered on the PPC side,
so we let them pass straight through from the DB25 to the ISA slots.

Both buffers have their `~OE` pins tied to GND - the buffers are
permanently enabled.  This is identical to project 2's topology.

## The data bus is unbuffered

D0..D7 on connector B pin 13-16 and 32-35 come out of the PPC at CMOS
levels.  Per the PPC tech-ref note: "to interface with TTL devices,
each line should be pulled up to +5V via a 10K resistor".  That's the
only "buffering" the data bus gets - 10K pull-ups via the `RR1` SIP
resistor network.

The data bus is bidirectional, so a real transceiver (like a 74HC245)
would be needed to drive it from the ISA side back to the PPC side.
**Project 2 also omits this, and so do we** - the assumption being that
ISA peripherals will source enough drive to overcome the pull-ups when
they need to read data back to the host.  For a flash-based XT-IDE
this works in practice; for a fully loaded slot of three active cards
you may want to add a 74HC245 in a future revision.

## The BEAT LED (removed)

Project 2 had a 74HCT74 dual flip-flop (U4) configured as a toggle,
clocked by A07, driving a "BEAT" LED through a 470 ohm resistor.  The
result was a heartbeat that flickered whenever the CPU was active.

**We do not carry this over.**  It's purely cosmetic - the board works
identically without it.  Dropping U4 saves one SOIC-14, two 1K
pull-ups (`~1CLR_BEAT`, `~1PRE_BEAT`), the 470R series resistor, the
LED itself, and one decoupling cap.

If you want to restore it later, look at the git history for the
`U4_NETS` table and the commented removal block in
`scripts/generate_schematic.py` - everything needed is self-contained
and easy to add back.

## Power LED

`D1_PWR` connects from +5V through 470 ohm to GND.  Whenever the PPC
is on and the cable is plugged in, this lights.

## Ground star

The four mounting holes are pad-and-plated through-hole, all tied to
GND.  This serves three purposes:

1. Mechanical mounting (M3 screws into the PPC chassis)
2. Electrical bond to chassis ground
3. Star-ground point distribution to reduce loop area on the SMD layer

## Net classes

- **Default**: 0.25 mm tracks, 0.2 mm clearance
- **Power**: 0.5 mm tracks, 0.3 mm clearance, applied to +5V/+12V/-5V/-12V/GND

These are conservative for a low-current digital board and are well
within JLCPCB / OSH Park / PCBWay capabilities at standard pricing.

## Notes on the routed PCB

The committed `.kicad_pcb` has been routed by hand on top of the
generator's skeleton.  A few things worth knowing if you intend to fork
or re-spin it:

- **Ground pours** are present on the back copper layer; the front copper
  layer relies on traces only.
- **Stitching vias** along the board edges are sparse - add more if you
  are chasing EMI compliance.
- **Silkscreen labels** are the auto-generated reference designators and
  values; feel free to polish before sending to fab.
- If you re-run `generate_pcb.py` the skeleton is rewritten and the
  routing is lost - back up the `.kicad_pcb` first.

## Footprint substitutions

KiCad 8 does not ship a dedicated ISA 8-bit card-edge socket in its
standard libraries, so this project includes a custom one in
`kicad/ppc-isa.pretty/ISA_8Bit_Slot.kicad_mod`.  The library is
registered in `kicad/fp-lib-table` as the project-local library
`ppc-isa`, so the three ISA slots resolve as `ppc-isa:ISA_8Bit_Slot`.

If you don't have one of the other footprints installed, equivalent
options are:

| Generated footprint | Drop-in alternative |
| --- | --- |
| `ppc-isa:ISA_8Bit_Slot` | Any 2x31 0.1" pin socket (the actual part is a 62-way card-edge socket such as TE 5352155-1 or equivalent).  For prototyping, a 2x31 pin socket works - the pad pattern is identical |
| `Connector_Dsub:DSUB-25_Male_Horizontal_P2.77x2.84mm_EdgePinOffset4.94mm` | Any horizontal-mount DB25 male (right-angle PCB version) |
| `Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm` | The wide-body SOIC-20; the narrow-body SOIC-20 (300 mil) also fits with manual landpattern adjustment |
| `Resistor_THT:R_Array_SIP9` | Bourns 4609X / Yageo equivalents - check pin 1 orientation |
