#!/usr/bin/env python3
"""
Generate a KiCad 8 schematic (.kicad_sch) for the Amstrad PPC ISA Expansion board.

Strategy
--------
Rather than hand-wiring the schematic (which would be visually intricate and
error-prone to generate programmatically), we produce a grid of component
blocks where every pin is connected to a **global label** carrying the net
name. This guarantees electrical correctness — any two pins with the same
global label are on the same net, regardless of visual proximity.

The user can open the resulting file in KiCad 8 and either:
  - use it as-is (it's a complete, valid schematic), or
  - rearrange / re-wire visually while keeping all global labels (electrical
    connectivity is preserved through label names).

Symbols
-------
We embed minimal symbol definitions (`lib_symbols` block) for each part we
use. These are stubs with correct pin count / pin number / electrical type,
drawn as simple rectangles. The user can replace any of them with richer
library symbols (e.g. from the official 74xx and Connector libraries) at
any time — KiCad will update the instance when the `lib_id` resolves.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# UUID helpers — deterministic, so re-running the script gives the same file.
# ---------------------------------------------------------------------------
NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")

def u(name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, name))


# ---------------------------------------------------------------------------
# Symbol-stub generation
# ---------------------------------------------------------------------------
# Each stub is drawn as a simple rectangle with pins on the left and right.
# Pin electrical types: input, output, bidirectional, power_in, power_out,
# passive, unspecified, open_collector, open_emitter, no_connect.
# ---------------------------------------------------------------------------

def make_stub(lib_name: str, ref_prefix: str,
              left_pins: list[tuple[str, str, str]],
              right_pins: list[tuple[str, str, str]],
              value: str = None,
              extends: str = None,
              show_pin_numbers: bool = True,
              show_pin_names: bool = True) -> str:
    """Generate a minimal lib_symbol stub.

    Each pin is (number, name, etype).  Pins on the left side are drawn with
    length 2.54 going right (orientation 0), on the right side with length
    2.54 going left (orientation 180).  The body is a rectangle sized to fit.
    """
    if value is None:
        value = lib_name.split(":")[-1]
    n_rows = max(len(left_pins), len(right_pins))
    # Body sized 20.32 mm wide (8 grid units), height = n_rows * 2.54 + 5.08
    body_h = n_rows * 2.54 + 5.08
    body_w = 25.4
    left_x = -body_w / 2
    right_x = body_w / 2
    top_y = body_h / 2
    bot_y = -body_h / 2

    pins_out = []
    for i, (num, name, etype) in enumerate(left_pins):
        y = top_y - 2.54 - i * 2.54
        # Pin extends from (left_x - 2.54, y) to (left_x, y), pointing right (angle 0)
        pins_out.append(
            f'    (pin {etype} line (at {left_x - 2.54:.2f} {y:.2f} 0) (length 2.54)\n'
            f'      (name "{name}" (effects (font (size 1.0 1.0))))\n'
            f'      (number "{num}" (effects (font (size 1.0 1.0))))\n'
            f'    )'
        )
    for i, (num, name, etype) in enumerate(right_pins):
        y = top_y - 2.54 - i * 2.54
        # Pin extends from (right_x + 2.54, y) to (right_x, y), pointing left (angle 180)
        pins_out.append(
            f'    (pin {etype} line (at {right_x + 2.54:.2f} {y:.2f} 180) (length 2.54)\n'
            f'      (name "{name}" (effects (font (size 1.0 1.0))))\n'
            f'      (number "{num}" (effects (font (size 1.0 1.0))))\n'
            f'    )'
        )

    body = (
        f'    (rectangle\n'
        f'      (start {left_x:.2f} {bot_y:.2f})\n'
        f'      (end {right_x:.2f} {top_y:.2f})\n'
        f'      (stroke (width 0.254) (type default))\n'
        f'      (fill (type background))\n'
        f'    )'
    )

    pin_numbers_line = '(pin_numbers hide)' if not show_pin_numbers else '(pin_numbers)'
    pin_names_line = '(pin_names hide)' if not show_pin_names else '(pin_names (offset 1.016))'

    sym = (
        f'  (symbol "{lib_name}"\n'
        f'    {pin_numbers_line}\n'
        f'    {pin_names_line}\n'
        f'    (exclude_from_sim no)\n'
        f'    (in_bom yes)\n'
        f'    (on_board yes)\n'
        f'    (property "Reference" "{ref_prefix}" (at 0 {top_y + 2.5:.2f} 0) (effects (font (size 1.27 1.27))))\n'
        f'    (property "Value" "{value}" (at 0 {bot_y - 2.5:.2f} 0) (effects (font (size 1.27 1.27))))\n'
        f'    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'    (property "Description" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))\n'
        f'    (symbol "{lib_name}_0_1"\n'
        f'{body}\n'
        f'    )\n'
        f'    (symbol "{lib_name}_1_1"\n'
        + '\n'.join(pins_out) + '\n'
        f'    )\n'
        f'  )'
    )
    return sym


# ---------------------------------------------------------------------------
# Pin-type shorthand
# ---------------------------------------------------------------------------
IN = "input"
OUT = "output"
BI = "bidirectional"
PI = "power_in"
PO = "power_out"
PS = "passive"
NC = "no_connect"
U  = "unspecified"


# ---------------------------------------------------------------------------
# Component / pin definitions
# ---------------------------------------------------------------------------

# -- Amstrad DB25 male (Connector A) ------------------------------------------
# From Tech Ref §1.18
DB25_PINS = [
    ("1",  "+5V",     PI),   # pin 1 is +5V INPUT to the expansion board (= power coming from PPC)
    ("2",  "TC",      IN),
    ("3",  "A19",     IN),
    ("4",  "A17",     IN),
    ("5",  "A15",     IN),
    ("6",  "A13",     IN),
    ("7",  "A11",     IN),
    ("8",  "A09",     IN),
    ("9",  "A07b",    IN),   # * buffered
    ("10", "A05b",    IN),
    ("11", "A03b",    IN),
    ("12", "A01b",    IN),
    ("13", "AEN",     IN),
    ("14", "GND",     PI),
    ("15", "~DACK0",  IN),
    ("16", "A18",     IN),
    ("17", "A16",     IN),
    ("18", "A14",     IN),
    ("19", "A12",     IN),
    ("20", "A10",     IN),
    ("21", "A08",     IN),
    ("22", "A06b",    IN),
    ("23", "A04b",    IN),
    ("24", "A02b",    IN),
    ("25", "A00b",    IN),
]

# -- Amstrad DB37 male (Connector B) ------------------------------------------
DB37_PINS = [
    ("1",  "NC_NEG20V", PI),  # -20V from PPC, unused on this board (NC)
    ("2",  "IRQ2",    IN),
    ("3",  "IRQ4",    IN),
    ("4",  "IRQ6",    IN),
    ("5",  "IO_RDY",  IN),
    ("6",  "~DACK2",  IN),
    ("7",  "~IOCHCK", IN),
    ("8",  "DRQ2",    IN),
    ("9",  "OSCb",    IN),    # * 14.318 MHz buffered, feeds U1 — drives ISA OSC
    ("10", "~MEMRb",  IN),    # * buffered, feeds U1 — drives ISA ~SMEMR
    ("11", "~IORb",   IN),    # * buffered, feeds U1 — drives ISA ~IOR
    ("12", "ALEb",    IN),    # * buffered, feeds U1 — drives ISA ALE
    ("13", "D7",      BI),    # ** data bus (no buffering — pull-ups via RR1)
    ("14", "D5",      BI),
    ("15", "D3",      BI),
    ("16", "D1",      BI),
    ("17", "-5V",     PI),
    ("18", "-12V",    PI),
    ("19", "GND",     PI),
    ("20", "NC_EXT_PWR", OUT),  # External Power input — leave NC (PPC's internal regulator powers the board)
    ("21", "IRQ3",    IN),
    ("22", "IRQ5",    IN),
    ("23", "IRQ7",    IN),
    ("24", "~DACK1",  IN),
    ("25", "~DACK3",  IN),
    ("26", "DRQ1",    IN),
    ("27", "DRQ3",    IN),
    ("28", "~MEMWb",  IN),    # * buffered, feeds U1 — drives ISA ~SMEMW
    ("29", "~IOWb",   IN),    # * buffered, feeds U1 — drives ISA ~IOW
    ("30", "RESETb",  IN),    # * buffered, feeds U1 — drives ISA RESET
    ("31", "CK4b",    IN),    # * 4 MHz buffered, feeds U1 — drives ISA CLK
    ("32", "D6",      BI),    # ** data bus
    ("33", "D4",      BI),
    ("34", "D2",      BI),
    ("35", "D0",      BI),
    ("36", "+12V",    PI),
    ("37", "+5V",     PI),
]

# -- ISA 8-bit slot (31-pin edge) -------------------------------------------
# Standard XT ISA 8-bit pinout.  We label pins A1..A31 (component side) and
# B1..B31 (solder side) — 62 pins total per slot.
# Using sequential numbering 1..62:  1..31 = A1..A31,  32..62 = B1..B31.
ISA_A_PINS = [
    ("1",  "~IOCHCK",   IN),
    ("2",  "D7",        BI),
    ("3",  "D6",        BI),
    ("4",  "D5",        BI),
    ("5",  "D4",        BI),
    ("6",  "D3",        BI),
    ("7",  "D2",        BI),
    ("8",  "D1",        BI),
    ("9",  "D0",        BI),
    ("10", "IO_RDY",    OUT),
    ("11", "AEN",       IN),
    ("12", "A19",       IN),
    ("13", "A18",       IN),
    ("14", "A17",       IN),
    ("15", "A16",       IN),
    ("16", "A15",       IN),
    ("17", "A14",       IN),
    ("18", "A13",       IN),
    ("19", "A12",       IN),
    ("20", "A11",       IN),
    ("21", "A10",       IN),
    ("22", "A09",       IN),
    ("23", "A08",       IN),
    ("24", "A07",       IN),
    ("25", "A06",       IN),
    ("26", "A05",       IN),
    ("27", "A04",       IN),
    ("28", "A03",       IN),
    ("29", "A02",       IN),
    ("30", "A01",       IN),
    ("31", "A00",       IN),
]
ISA_B_PINS = [
    ("32", "GND",       PI),
    ("33", "RESET",     IN),
    ("34", "+5V",       PI),
    ("35", "IRQ2",      OUT),
    ("36", "-5V",       PI),
    ("37", "DRQ2",      OUT),
    ("38", "-12V",      PI),
    ("39", "NC_ISA_B8", NC),    # ISA B8 = "reserved / card selected" — NC on XT
    ("40", "+12V",      PI),
    ("41", "GND",       PI),
    ("42", "~SMEMW",    IN),
    ("43", "~SMEMR",    IN),
    ("44", "~IOW",      IN),
    ("45", "~IOR",      IN),
    ("46", "~DACK3",    IN),
    ("47", "DRQ3",      OUT),
    ("48", "~DACK1",    IN),
    ("49", "DRQ1",      OUT),
    ("50", "~DACK0",    IN),
    ("51", "CLK",       IN),
    ("52", "IRQ7",      OUT),
    ("53", "IRQ6",      OUT),
    ("54", "IRQ5",      OUT),
    ("55", "IRQ4",      OUT),
    ("56", "IRQ3",      OUT),
    ("57", "~DACK2",    IN),
    ("58", "TC",        IN),
    ("59", "ALE",       IN),
    ("60", "+5V",       PI),
    ("61", "OSC",       IN),
    ("62", "GND",       PI),
]
ISA_PINS = ISA_A_PINS + ISA_B_PINS

# -- 74HC244 (SN74HC244, octal buffer) -------------------------------------
# Two 4-bit buffer sections, each with its own output-enable.
# Pinout (DIP-20 / SOIC-20):
#   1=~1OE  2=1A0  3=2Y3  4=1A1  5=2Y2  6=1A2  7=2Y1  8=1A3  9=2Y0  10=GND
#   11=2A0 12=1Y3 13=2A1 14=1Y2 15=2A2 16=1Y1 17=2A3 18=1Y0 19=~2OE 20=VCC
HC244_PINS = [
    ("1",  "~1OE",  IN),
    ("2",  "1A0",   IN),
    ("3",  "2Y3",   OUT),
    ("4",  "1A1",   IN),
    ("5",  "2Y2",   OUT),
    ("6",  "1A2",   IN),
    ("7",  "2Y1",   OUT),
    ("8",  "1A3",   IN),
    ("9",  "2Y0",   OUT),
    ("10", "GND",   PI),
    ("11", "2A0",   IN),
    ("12", "1Y3",   OUT),
    ("13", "2A1",   IN),
    ("14", "1Y2",   OUT),
    ("15", "2A2",   IN),
    ("16", "1Y1",   OUT),
    ("17", "2A3",   IN),
    ("18", "1Y0",   OUT),
    ("19", "~2OE",  IN),
    ("20", "VCC",   PI),
]

# -- 74HCT74 (dual D flip-flop) --------------------------------------------
# SOIC-14 / DIP-14
HC74_PINS = [
    ("1",  "~1CLR", IN),
    ("2",  "1D",    IN),
    ("3",  "1CLK",  IN),
    ("4",  "~1PRE", IN),
    ("5",  "1Q",    OUT),
    ("6",  "~1Q",   OUT),
    ("7",  "GND",   PI),
    ("8",  "~2Q",   OUT),
    ("9",  "2Q",    OUT),
    ("10", "~2PRE", IN),
    ("11", "2CLK",  IN),
    ("12", "2D",    IN),
    ("13", "~2CLR", IN),
    ("14", "VCC",   PI),
]

# -- Resistor Network (8 isolated / bussed) for data-bus pull-ups ----------
# 9-pin SIP resistor network, pin 1 is the common, pins 2..9 are the
# individual resistor ends.
RN9_PINS = [
    ("1", "COM", PS),
    ("2", "R1",  PS),
    ("3", "R2",  PS),
    ("4", "R3",  PS),
    ("5", "R4",  PS),
    ("6", "R5",  PS),
    ("7", "R6",  PS),
    ("8", "R7",  PS),
    ("9", "R8",  PS),
]

# -- Passive 2-pin parts ---------------------------------------------------
R_PINS   = [("1", "~", PS), ("2", "~", PS)]
C_PINS   = [("1", "~", PS), ("2", "~", PS)]
LED_PINS = [("1", "K", PS), ("2", "A", PS)]


# ---------------------------------------------------------------------------
# Component instances
# ---------------------------------------------------------------------------
# For each instance we specify:
#   - reference (e.g. "U1")
#   - lib_id
#   - position (x, y) in mm
#   - value
#   - footprint
#   - per-pin net name (what global label to attach)
# ---------------------------------------------------------------------------

@dataclass
class Instance:
    ref: str
    lib_id: str
    value: str
    footprint: str
    x: float
    y: float
    nets: dict            # pin number -> net name
    pin_defs: list        # list of (number, name, etype) — the pin layout
    rotation: int = 0

def gnd_c(n): return f"GND"
def vcc_c(n): return f"+5V"

# Build all the instances.  Positions are on a clean 25.4 mm grid so the
# schematic is a readable grid even without manual placement.

GRID = 50.8  # 2" between blocks horizontally / vertically

instances: list[Instance] = []

# --- Amstrad expansion connectors (left edge of sheet) ----
instances.append(Instance(
    ref="J1", lib_id="DB25_Male", value="DB25 Male",
    footprint="Connector_Dsub:DSUB-25_Male_Horizontal_P2.77x2.84mm_EdgePinOffset4.94mm_Housed_MountingHolesOffset7.48mm",
    x=50.8, y=50.8, pin_defs=DB25_PINS,
    nets={num: name for num, name, _ in DB25_PINS}))

instances.append(Instance(
    ref="J2", lib_id="DB37_Male", value="DB37 Male",
    footprint="Connector_Dsub:DSUB-37_Male_Horizontal_P2.77x2.84mm_EdgePinOffset4.94mm_Housed_MountingHolesOffset7.48mm",
    x=50.8, y=160.0, pin_defs=DB37_PINS,
    nets={num: name for num, name, _ in DB37_PINS}))

# --- 74HC244 buffer U1 (address bus lower byte + control signals) ---------
# Maps per project 2 schematic:
#   U1: 1A0=OSCb   -> 1Y0=OSC
#       1A1=MEMWb  -> 1Y1=SMEMW
#       1A2=MEMRb  -> 1Y2=SMEMR
#       1A3=IORb   -> 1Y3=IOR
#       2A0=IOWb   -> 2Y0=IOW       (wait — checking schematic again)
# Reviewing the project2 schematic carefully:
#   U1 drives: OSC, SMEMW, SMEMR, IOR, IOW, RESET, ALE, CLK (8 signals)
#   U2 drives: 8 address bits A00..A07
# From project2 symbols (leftmost pins listed) U1 inputs are:
#   OSCb, MEMWb, MEMRb, IORb, RESETb, IOWb, ALEb, CK4b
# And outputs are: OSC, SMEMW, SMEMR, IOR, RESET, IOW, ALE, CLK
# Exact mapping will be:
U1_NETS = {
    "1":  "GND",      # ~1OE tied low (always enabled)
    "2":  "OSCb",     # 1A0 in:  from J2 pin 9
    "4":  "~MEMWb",   # 1A1 in:  from J2 pin 28
    "6":  "~MEMRb",   # 1A2 in:  from J2 pin 10
    "8":  "~IORb",    # 1A3 in:  from J2 pin 11
    "11": "~IOWb",    # 2A0 in:  from J2 pin 29
    "13": "RESETb",   # 2A1 in:  from J2 pin 30
    "15": "ALEb",     # 2A2 in:  from J2 pin 12
    "17": "CK4b",     # 2A3 in:  from J2 pin 31
    "18": "OSC",      # 1Y0 out -> ISA OSC (buffered OSCb)
    "16": "~SMEMW",   # 1Y1 out -> ISA ~SMEMW
    "14": "~SMEMR",   # 1Y2 out -> ISA ~SMEMR
    "12": "~IOR",     # 1Y3 out -> ISA ~IOR
    "9":  "~IOW",     # 2Y0 out -> ISA ~IOW
    "7":  "RESET",    # 2Y1 out -> ISA RESET
    "5":  "ALE",      # 2Y2 out -> ISA ALE
    "3":  "CLK",      # 2Y3 out -> ISA CLK (buffered CK4b)
    "19": "GND",      # ~2OE tied low
    "10": "GND",
    "20": "+5V",
}
instances.append(Instance(
    ref="U1", lib_id="74HC244", value="74HC244",
    footprint="Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm",
    x=170.0, y=50.8, pin_defs=HC244_PINS, nets=U1_NETS))

# --- 74HC244 buffer U2 (address bus A00..A07) -----------------------------
# U2 inputs (b = buffered form coming from Amstrad): A00b..A07b
# U2 outputs (unbuffered, to ISA slots): A00..A07
U2_NETS = {
    "1":  "~U2_OE",
    "2":  "A07b", "4":  "A06b", "6":  "A05b", "8":  "A04b",
    "11": "A03b", "13": "A02b", "15": "A01b", "17": "A00b",
    "18": "A07",  "16": "A06",  "14": "A05",  "12": "A04",
    "9":  "A03",  "7":  "A02",  "5":  "A01",  "3":  "A00",
    "19": "~U2_OE",
    "10": "GND",
    "20": "+5V",
}
instances.append(Instance(
    ref="U2", lib_id="74HC244", value="74HC244",
    footprint="Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm",
    x=170.0, y=160.0, pin_defs=HC244_PINS, nets=U2_NETS))

# --- 74HCT74 BEAT flip-flop divider ---------------------------------------
# Project 2 used U4 (74HCT74) to divide A07 by 2 and drive a "BEAT" activity
# LED.  This is pure cosmetic status — electrically unnecessary — so we
# leave it out of this design.  Power status is still indicated via D2_PWR
# further down.  If you want the BEAT LED back, revert this removal and
# restore R101/R102/R103/D1_BEAT/C2.

# --- RR1: 9-pin bussed resistor network, data-bus pull-up to +5V ---------
# From project2: RR1 connects +5V (COM pin 10 in project2 schematic, but on a
# standard 9-pin SIP it's pin 1) to each of D0..D7 via 10K each.
RR1_NETS = {
    "1": "+5V",
    "2": "D7", "3": "D6", "4": "D5", "5": "D4",
    "6": "D3", "7": "D2", "8": "D1", "9": "D0",
}
instances.append(Instance(
    ref="RR1", lib_id="R_Network_9", value="10k",
    footprint="Resistor_THT:R_Array_SIP9",  # 9-pin bussed SIP; Bourns 4609X family
    x=290.0, y=160.0, pin_defs=RN9_PINS, nets=RR1_NETS))

# --- D-bus wiring note ---------------------------------------------------
# The Amstrad side data bus (D0..D7 on connector B) and the ISA data bus
# (D0..D7) are the SAME net electrically — the PPC tech-ref describes these
# pins as "expansion data bus at CMOS levels, pull to TTL with 10K".  RR1
# provides those pull-ups.  Because we use global labels, naming them D0..D7
# on both sides is all that is required — no additional wiring step needed.
#
# The A00b..A07b pins on J1 (DB25) are buffered INPUTS to U2 — they stay
# distinct from unbuffered A00..A07 which go to the ISA slots.
# A08..A19 on J1/J2 are already unbuffered on the Amstrad side and go
# directly to the ISA bus.  Their current net names already match.

# --- Decoupling caps: one 100nF per IC power pin plus bulk caps ----------
# Place them near their ICs but wire via labels.  We'll generate many.
decoupling_index = 0
def add_cap_0805(net_high, net_low, value, xy, ref_counter=[0]):
    ref_counter[0] += 1
    c_ref = f"C{ref_counter[0]}"
    instances.append(Instance(
        ref=c_ref, lib_id="C", value=value,
        footprint="Capacitor_SMD:C_0805_2012Metric",
        x=xy[0], y=xy[1], pin_defs=C_PINS,
        nets={"1": net_high, "2": net_low}))

# 100nF decoupling for each 74HC IC
add_cap_0805("+5V", "GND", "100nF", (290.0, 50.8))    # C1 near U1
add_cap_0805("+5V", "GND", "100nF", (220.0, 220.0))   # C2 near U2 (extra)
# 100nF per ISA slot (×3) and +12V/-12V bulk
add_cap_0805("+5V", "GND", "100nF", (400.0, 50.8))    # C4 near J3
add_cap_0805("+5V", "GND", "100nF", (400.0, 160.0))   # C5 near J4
add_cap_0805("+5V", "GND", "100nF", (400.0, 270.0))   # C6 near J5
# Bulk electrolytics on +5V / +12V / -12V
add_cap_0805("+5V",  "GND", "10uF", (290.0, 100.0))
add_cap_0805("+12V", "GND", "10uF", (290.0, 110.0))
add_cap_0805("-12V", "GND", "10uF", (290.0, 120.0))
add_cap_0805("-5V",  "GND", "10uF", (290.0, 130.0))

# --- Pull-up resistors: ~U1_OE, ~U2_OE tied to GND (always enabled) ------
# Actually project 2 ties ~OE to GND directly (always enabled).  So we wire
# these pins to GND via the global label — no resistor needed.
# Replace ~U1_OE and ~U2_OE with GND:
for i in instances:
    if i.ref in ("U1", "U2"):
        for p, n in list(i.nets.items()):
            if n in ("~U1_OE", "~U2_OE"):
                i.nets[p] = "GND"

def add_res_0805(net_a, net_b, value, xy, ref_counter=[100]):
    ref_counter[0] += 1
    r_ref = f"R{ref_counter[0]}"
    instances.append(Instance(
        ref=r_ref, lib_id="R", value=value,
        footprint="Resistor_SMD:R_0805_2012Metric",
        x=xy[0], y=xy[1], pin_defs=R_PINS,
        nets={"1": net_a, "2": net_b}))

# Power LED (always on when board has +5V)
add_res_0805("+5V", "PWR_A", "470", (60.0, 290.0))
instances.append(Instance(
    ref="D1_PWR", lib_id="LED", value="LED_POWER",
    footprint="LED_SMD:LED_0805_2012Metric",
    x=100.0, y=290.0, pin_defs=LED_PINS,
    nets={"1": "GND", "2": "PWR_A"}))

# --- Three ISA 8-bit slots ----------------------------------------------
def isa_nets():
    # Standard XT ISA pinout — nets are shared across all slots (system bus)
    return {num: name for num, name, _ in ISA_PINS}

for idx, (ref, y) in enumerate((("J3", 50.8), ("J4", 160.0), ("J5", 270.0))):
    instances.append(Instance(
        ref=ref, lib_id="ISA_8Bit_Edge", value="ISA 8-bit slot",
        footprint="ppc-isa:ISA_8Bit_Slot",
        x=500.0, y=y, pin_defs=ISA_PINS, nets=isa_nets()))

# --- Clean up NC nets so ERC is happy -----------------------------------
# Anything starting with "NC_" will emit a no-connect flag rather than a label.

# ---------------------------------------------------------------------------
# Emit the .kicad_sch
# ---------------------------------------------------------------------------

def emit_lib_symbols():
    used = {}
    # Map instance lib_id -> pin_defs
    for i in instances:
        if i.lib_id not in used:
            used[i.lib_id] = i.pin_defs
    # Split pin_defs into left/right columns.  Put the first half on left,
    # second half on right, except for ISA connectors where we put A pins
    # on left and B pins on right.
    parts = []
    for lib_id, pins in used.items():
        if lib_id == "ISA_8Bit_Edge":
            left = ISA_A_PINS
            right = ISA_B_PINS
        elif lib_id == "DB25_Male":
            left = pins[:13]
            right = pins[13:]
        elif lib_id == "DB37_Male":
            left = pins[:19]
            right = pins[19:]
        elif lib_id == "74HC244":
            left = pins[:10]
            right = pins[10:]
        elif lib_id == "74HC74":
            left = pins[:7]
            right = pins[7:]
        elif lib_id == "R_Network_9":
            left = pins[:1]
            right = pins[1:]
        elif lib_id in ("R", "C", "LED"):
            left = pins[:1]
            right = pins[1:]
        else:
            half = (len(pins) + 1) // 2
            left = pins[:half]
            right = pins[half:]
        # Determine ref prefix
        if lib_id == "R": ref_prefix = "R"
        elif lib_id == "C": ref_prefix = "C"
        elif lib_id == "LED": ref_prefix = "D"
        elif lib_id.startswith("DB"): ref_prefix = "J"
        elif lib_id.startswith("ISA"): ref_prefix = "J"
        elif lib_id.startswith("74"): ref_prefix = "U"
        elif lib_id == "R_Network_9": ref_prefix = "RN"
        else: ref_prefix = "U"
        parts.append(make_stub(lib_id, ref_prefix, left, right))
    return "\n".join(parts)

def emit_instance(inst: Instance) -> str:
    """Emit a symbol instance with stub wires + global labels for every pin."""
    inst_uuid = u(f"inst:{inst.ref}")
    lines = []
    # Symbol block
    lines.append(f'  (symbol')
    lines.append(f'    (lib_id "{inst.lib_id}")')
    lines.append(f'    (at {inst.x:.2f} {inst.y:.2f} {inst.rotation})')
    lines.append(f'    (unit 1)')
    lines.append(f'    (exclude_from_sim no)')
    lines.append(f'    (in_bom yes)')
    lines.append(f'    (on_board yes)')
    lines.append(f'    (dnp no)')
    lines.append(f'    (fields_autoplaced)')
    lines.append(f'    (uuid "{inst_uuid}")')
    lines.append(f'    (property "Reference" "{inst.ref}" (at {inst.x:.2f} {inst.y - 15:.2f} 0) (effects (font (size 1.27 1.27))))')
    lines.append(f'    (property "Value" "{inst.value}" (at {inst.x:.2f} {inst.y + 15:.2f} 0) (effects (font (size 1.27 1.27))))')
    lines.append(f'    (property "Footprint" "{inst.footprint}" (at {inst.x:.2f} {inst.y:.2f} 0) (effects (font (size 1.27 1.27)) hide))')
    lines.append(f'    (property "Datasheet" "" (at {inst.x:.2f} {inst.y:.2f} 0) (effects (font (size 1.27 1.27)) hide))')
    lines.append(f'    (property "Description" "" (at {inst.x:.2f} {inst.y:.2f} 0) (effects (font (size 1.27 1.27)) hide))')
    # Add pin uuids
    for num, name, etype in inst.pin_defs:
        pin_uuid = u(f"pin:{inst.ref}:{num}")
        lines.append(f'    (pin "{num}" (uuid "{pin_uuid}"))')
    # Instance entry
    lines.append(f'    (instances')
    lines.append(f'      (project ""')
    lines.append(f'        (path "/{u("root")}"')
    lines.append(f'          (reference "{inst.ref}") (unit 1)')
    lines.append(f'        )')
    lines.append(f'      )')
    lines.append(f'    )')
    lines.append(f'  )')

    # Emit global labels + wires for each pin
    # Pin positions: left pins at (cx - body_w/2 - 2.54, cy_top - i*2.54)
    # right pins at (cx + body_w/2 + 2.54, cy_top - i*2.54)
    # Must match the stub geometry.
    # Determine left/right sets matching emit_lib_symbols
    lib_id = inst.lib_id
    pins = inst.pin_defs
    if lib_id == "ISA_8Bit_Edge":
        left, right = ISA_A_PINS, ISA_B_PINS
    elif lib_id == "DB25_Male":
        left, right = pins[:13], pins[13:]
    elif lib_id == "DB37_Male":
        left, right = pins[:19], pins[19:]
    elif lib_id == "74HC244":
        left, right = pins[:10], pins[10:]
    elif lib_id == "74HC74":
        left, right = pins[:7], pins[7:]
    elif lib_id == "R_Network_9":
        left, right = pins[:1], pins[1:]
    elif lib_id in ("R", "C", "LED"):
        left, right = pins[:1], pins[1:]
    else:
        half = (len(pins) + 1) // 2
        left, right = pins[:half], pins[half:]
    n_rows = max(len(left), len(right))
    body_h = n_rows * 2.54 + 5.08
    body_w = 25.4
    top_y = inst.y - body_h / 2 + 2.54  # top of rect in world coords (y grows down in KiCad)
    # Actually KiCad schematic uses y-axis increasing downward in many renderers,
    # but in our stub we used +top_y = body_h/2 (upward).  When we place at inst.y,
    # the top pin is at inst.y + (top_y - 2.54).  Let's recompute:
    sym_top = inst.y - body_h / 2  # top of rect
    sym_bot = inst.y + body_h / 2
    left_pin_x = inst.x - body_w / 2 - 2.54
    right_pin_x = inst.x + body_w / 2 + 2.54

    # End coords (attached to the wire endpoint away from the symbol)
    # Left pin: wire from (left_pin_x, y) going further left for label
    # Right pin: wire going further right
    WIRE_LEN = 5.08  # additional wire length to reach the label
    for i, (num, name, etype) in enumerate(left):
        pin_y = sym_top + 2.54 + i * 2.54
        label_x = left_pin_x - WIRE_LEN
        label_y = pin_y
        net = inst.nets.get(num, f"{inst.ref}_pin{num}")
        # emit wire
        wire_uuid = u(f"wire:{inst.ref}:L:{num}")
        lines.append(f'  (wire (pts (xy {left_pin_x:.2f} {pin_y:.2f}) (xy {label_x:.2f} {label_y:.2f})) (stroke (width 0) (type default)) (uuid "{wire_uuid}"))')
        # emit global label (points left = 180°)
        lbl_uuid = u(f"lbl:{inst.ref}:L:{num}")
        if net.startswith("NC_"):
            # no-connect instead
            nc_uuid = u(f"nc:{inst.ref}:{num}")
            lines.append(f'  (no_connect (at {label_x:.2f} {label_y:.2f}) (uuid "{nc_uuid}"))')
        else:
            lines.append(f'  (global_label "{net}" (shape input) (at {label_x:.2f} {label_y:.2f} 180) (effects (font (size 1.27 1.27)) (justify right)) (uuid "{lbl_uuid}"))')
    for i, (num, name, etype) in enumerate(right):
        pin_y = sym_top + 2.54 + i * 2.54
        label_x = right_pin_x + WIRE_LEN
        label_y = pin_y
        net = inst.nets.get(num, f"{inst.ref}_pin{num}")
        wire_uuid = u(f"wire:{inst.ref}:R:{num}")
        lines.append(f'  (wire (pts (xy {right_pin_x:.2f} {pin_y:.2f}) (xy {label_x:.2f} {label_y:.2f})) (stroke (width 0) (type default)) (uuid "{wire_uuid}"))')
        lbl_uuid = u(f"lbl:{inst.ref}:R:{num}")
        if net.startswith("NC_"):
            nc_uuid = u(f"nc:{inst.ref}:{num}")
            lines.append(f'  (no_connect (at {label_x:.2f} {label_y:.2f}) (uuid "{nc_uuid}"))')
        else:
            lines.append(f'  (global_label "{net}" (shape input) (at {label_x:.2f} {label_y:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)) (uuid "{lbl_uuid}"))')
    return '\n'.join(lines)


SCH_HEADER = '''(kicad_sch
  (version 20231120)
  (generator "ppc-isa-generator")
  (generator_version "8.0")
  (uuid "{root_uuid}")
  (paper "A2")
  (title_block
    (title "Amstrad PPC 512/640 — ISA Expansion Board")
    (date "2026-04-18")
    (rev "0.1")
    (company "Open Hardware")
    (comment 1 "Derived from community projects 1 and 2")
    (comment 2 "Based on Amstrad PPC Technical Reference Section 1.18")
    (comment 3 "3x ISA 8-bit slots, SMD-only, internal-power")
    (comment 4 "See README.md and docs/ for full details")
  )
'''

SCH_FOOTER = ')\n'

def build_schematic() -> str:
    out = [SCH_HEADER.format(root_uuid=u("sch_root"))]
    out.append('  (lib_symbols')
    out.append(emit_lib_symbols())
    out.append('  )')
    # One big text note explaining the file
    note_uuid = u("note:intro")
    out.append(f'''  (text "Amstrad PPC 512/640 ISA Expansion — generated by generate_schematic.py\\n\\nEach pin is wired to a global label carrying the net name.\\nComponents with the same label are electrically connected.\\nSafe to rearrange visually; do not rename labels unless you also update every instance."
    (exclude_from_sim no)
    (at 10.0 10.0 0)
    (effects (font (size 2.0 2.0)) (justify left bottom))
    (uuid "{note_uuid}")
  )
''')
    for inst in instances:
        out.append(emit_instance(inst))
    # Sheet instance + symbol_instances block required by KiCad 8
    out.append(f'''  (sheet_instances
    (path "/" (page "1"))
  )
''')
    out.append(SCH_FOOTER)
    return '\n'.join(out)


if __name__ == "__main__":
    out_path = Path(__file__).resolve().parent.parent / "kicad" / "ppc-isa-expansion.kicad_sch"
    out_path.write_text(build_schematic())
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
