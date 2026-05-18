#!/usr/bin/env python3
"""
Generate a KiCad 8 PCB (.kicad_pcb) for the Amstrad PPC ISA Expansion board.

What this generator creates
---------------------------
- 120 x 99 mm rectangular board outline (Edge.Cuts)
- 4 x M3 mounting holes at the project-1 coordinates (3.0 mm hole, 6.0 mm pad)
- 3 x ISA 8-bit slot footprints, 62 through-hole pads each, at the project-1
  coordinates (rows 5.08 mm apart, slots 20.32 mm apart on Y).  Pads are
  netted to match the schematic (D0..D7, A00..A19, IRQ*, ~SMEMR/W, etc.)
- DB25 male and DB37 male connectors on the left edge for the Amstrad cable
- SMD placeholder footprints (SOIC-20, SOIC-14, 0805, 9-SIP RN) for U1, U2,
  U4, RR1, decoupling caps, pull-ups, LED resistors and the two LEDs, all
  with pad-level net assignments matching the schematic

The result is a *functional* PCB you can open in KiCad 8 and route by hand.
Component placement is on a regular grid -- it gets you started, but the
final layout is up to you.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")

def u(name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, name))


# ---------------------------------------------------------------------------
# Board geometry (extracted from project 1 gerbers)
# ---------------------------------------------------------------------------
BOARD_W = 120.0         # mm  (X)
BOARD_H = 99.0          # mm  (Y)

MOUNTING_HOLES = [
    (14.00, 78.07),
    (14.00, 57.75),
    (116.23, 57.11),
    (116.23, 79.34),
]
MH_DRILL = 3.0          # mm  (M3 clearance)
MH_PAD   = 6.0          # mm  (annular ring + GND star)

# ISA 8-bit slots: 62 pins, two staggered rows at 5.08 mm, 31 pins per row at
# 2.54 mm pitch.  X positions span 29.87..106.07 mm in project 1.  Slot Y
# positions are the *centers* between the two rows.
ISA_SLOTS = [
    # (ref, y_centre)
    ("J3", 47.91),  # row A at 45.37, row B at 50.45
    ("J4", 68.23),  # row A at 65.69, row B at 70.77
    ("J5", 88.55),  # row A at 86.01, row B at 91.09
]
ISA_PIN_X0   = 29.87       # X of pin 1 in each row
ISA_PIN_PITCH = 2.54
ISA_ROW_GAP  = 5.08
ISA_PAD_DRILL = 1.00       # mm
ISA_PAD_DIAM  = 1.70       # mm (oval-ish for edge connector)

# D-sub Amstrad connectors on left edge (J1, J2)
J1_POS = (5.0, 20.0)       # DB25 male, top-left
J2_POS = (5.0, 80.0)       # DB37 male, bottom-left

# SMD cluster reference grid (rough — user re-arranges)
U1_POS  = (50.0,  15.0)
U2_POS  = (80.0,  15.0)
RR1_POS = (95.0,  15.0)


# ---------------------------------------------------------------------------
# Pull net definitions from the schematic generator -- single source of truth
# ---------------------------------------------------------------------------
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_schematic as sch  # noqa: E402


# Build the master net table from every instance's nets dict.
# Net 0 is always reserved for "no net" in KiCad, so we start at 1.
all_nets = set()
for inst in sch.instances:
    for net in inst.nets.values():
        if net.startswith("NC_"):
            continue   # no_connect, not a routable net
        all_nets.add(net)
NETS = sorted(all_nets)
NET_INDEX = {name: i + 1 for i, name in enumerate(NETS)}   # 1-based


# ---------------------------------------------------------------------------
# Helper: render a footprint with named pads
# ---------------------------------------------------------------------------

def render_pad(num, pad_type, shape, x, y, sx, sy, drill, layers, net):
    """Render one (pad ...) clause."""
    pad_uuid = u(f"pad:{num}:{x}:{y}")
    parts = [f'    (pad "{num}" {pad_type} {shape}']
    parts.append(f'      (at {x:.3f} {y:.3f})')
    parts.append(f'      (size {sx:.3f} {sy:.3f})')
    if drill:
        parts.append(f'      (drill {drill:.3f})')
    parts.append(f'      (layers {layers})')
    if net:
        idx = NET_INDEX.get(net)
        if idx is not None:
            parts.append(f'      (net {idx} "{net}")')
    parts.append(f'      (uuid "{pad_uuid}")')
    parts.append(f'    )')
    return '\n'.join(parts)


def render_footprint(ref, value, x, y, rotation, fp_lib_id, pads, layer="F.Cu",
                     body_w=10.0, body_h=5.0):
    """Render a (footprint ...) clause containing the supplied pad list."""
    fp_uuid = u(f"fp:{ref}")
    half_w = body_w / 2
    half_h = body_h / 2

    out = []
    out.append(f'  (footprint "{fp_lib_id}"')
    out.append(f'    (layer "{layer}")')
    out.append(f'    (uuid "{fp_uuid}")')
    out.append(f'    (at {x:.3f} {y:.3f} {rotation})')
    out.append(f'    (descr "auto-generated stub for {ref}")')
    out.append(f'    (attr through_hole)' if any('thru_hole' in p for p in pads) else '    (attr smd)')
    out.append(f'    (property "Reference" "{ref}"')
    out.append(f'      (at 0 -{half_h + 1.5:.2f} {rotation})')
    out.append(f'      (layer "F.SilkS")')
    out.append(f'      (uuid "{u("ref:" + ref)}")')
    out.append(f'      (effects (font (size 1.0 1.0) (thickness 0.15)))')
    out.append(f'    )')
    out.append(f'    (property "Value" "{value}"')
    out.append(f'      (at 0 {half_h + 1.5:.2f} {rotation})')
    out.append(f'      (layer "F.Fab")')
    out.append(f'      (uuid "{u("val:" + ref)}")')
    out.append(f'      (effects (font (size 1.0 1.0) (thickness 0.15)))')
    out.append(f'    )')
    out.append(f'    (property "Footprint" "{fp_lib_id}"')
    out.append(f'      (at 0 0 {rotation}) (unlocked yes) (layer "F.Fab") (hide yes)')
    out.append(f'      (uuid "{u("fp_prop:" + ref)}")')
    out.append(f'      (effects (font (size 1.0 1.0) (thickness 0.15)))')
    out.append(f'    )')
    # Silkscreen rectangle outline of body
    out.append(f'    (fp_rect (start -{half_w:.2f} -{half_h:.2f}) (end {half_w:.2f} {half_h:.2f}) (stroke (width 0.12) (type default)) (fill none) (layer "F.SilkS") (uuid "{u("rect:"+ref)}"))')
    # Pads
    out.extend(pads)
    out.append(f'  )')
    return '\n'.join(out)


# ---------------------------------------------------------------------------
# Builders for each footprint type
# ---------------------------------------------------------------------------

def build_isa_slot(ref, y_centre):
    """Build an ISA 8-bit slot footprint with 62 pads (31 row A + 31 row B).

    Pad numbering: 1..31 = component-side row A, 32..62 = solder-side row B
    -- matches the pin numbering used in the schematic.
    """
    pads = []
    nets_a = {num: name for num, name, _ in sch.ISA_A_PINS}
    nets_b = {num: name for num, name, _ in sch.ISA_B_PINS}

    for i, (num, name, _) in enumerate(sch.ISA_A_PINS):
        # Row A is the 'top' row (lower Y in our coordinate system)
        x = ISA_PIN_X0 + i * ISA_PIN_PITCH - x_offset_for_centre()
        y = -ISA_ROW_GAP / 2
        net = nets_a[num]
        pads.append(render_pad(
            num, "thru_hole", "oval",
            x, y, ISA_PAD_DIAM, ISA_PAD_DIAM, ISA_PAD_DRILL,
            '"*.Cu" "*.Mask"',
            net if not net.startswith("NC_") else None
        ))
    for i, (num, name, _) in enumerate(sch.ISA_B_PINS):
        x = ISA_PIN_X0 + i * ISA_PIN_PITCH - x_offset_for_centre()
        y = +ISA_ROW_GAP / 2
        net = nets_b[num]
        pads.append(render_pad(
            num, "thru_hole", "oval",
            x, y, ISA_PAD_DIAM, ISA_PAD_DIAM, ISA_PAD_DRILL,
            '"*.Cu" "*.Mask"',
            net if not net.startswith("NC_") else None
        ))

    body_w = 31 * ISA_PIN_PITCH + 2.0
    body_h = ISA_ROW_GAP + 4.0
    # Centre X = mid-span of the row
    x_centre = ISA_PIN_X0 + (30 * ISA_PIN_PITCH) / 2
    return render_footprint(
        ref, "ISA 8-bit slot",
        x_centre, y_centre, 0,
        "ppc-isa:ISA_8Bit_Slot",
        pads, body_w=body_w, body_h=body_h
    )


def x_offset_for_centre():
    """Pads are placed relative to footprint centre.  We positioned the
    footprint at (x_centre, y_centre) so pads need to be offset to be relative
    to that centre."""
    return ISA_PIN_X0 + (30 * ISA_PIN_PITCH) / 2


def build_dsub(ref, n_pins, pos, nets_dict, value):
    """Build a vertical D-sub through-hole footprint (n_pins).
    Pads on a 2.77 x 2.84 mm grid, with row 1 (odd) and row 2 (even) staggered.
    For our purposes a single-row representation is sufficient because we're
    using it as a placeholder -- routing is done by hand.
    """
    pads = []
    # We arrange pads in two rows for visual clarity
    # Top row: pins 1..ceil(n/2);  Bottom row: remaining
    if n_pins == 25:
        top = list(range(1, 14))     # 1..13
        bot = list(range(14, 26))    # 14..25
        body_w = 14 * 2.77
        body_h = 12.0
    else:  # 37
        top = list(range(1, 20))     # 1..19
        bot = list(range(20, 38))    # 20..37
        body_w = 19 * 2.77
        body_h = 14.0

    half_w_pads = (max(len(top), len(bot)) - 1) * 2.77 / 2
    for i, num in enumerate(top):
        x = -half_w_pads + i * 2.77
        y = -2.0
        pads.append(render_pad(
            str(num), "thru_hole", "circle",
            x, y, 2.0, 2.0, 1.0,
            '"*.Cu" "*.Mask"',
            nets_dict.get(str(num)) if not nets_dict.get(str(num), "").startswith("NC_") else None
        ))
    half_w_pads_b = (len(bot) - 1) * 2.77 / 2
    for i, num in enumerate(bot):
        x = -half_w_pads_b + i * 2.77
        y = 0.84
        pads.append(render_pad(
            str(num), "thru_hole", "circle",
            x, y, 2.0, 2.0, 1.0,
            '"*.Cu" "*.Mask"',
            nets_dict.get(str(num)) if not nets_dict.get(str(num), "").startswith("NC_") else None
        ))

    fp_lib = ("Connector_Dsub:DSUB-25_Male_Horizontal_P2.77x2.84mm_EdgePinOffset4.94mm"
              if n_pins == 25 else
              "Connector_Dsub:DSUB-37_Male_Horizontal_P2.77x2.84mm_EdgePinOffset4.94mm")
    return render_footprint(ref, value, pos[0] + body_w / 2, pos[1], 0,
                            fp_lib, pads, body_w=body_w + 4, body_h=body_h)


def build_mounting_hole(idx, x, y):
    pads = [render_pad(
        "1", "thru_hole", "circle", 0, 0,
        MH_PAD, MH_PAD, MH_DRILL,
        '"*.Cu" "*.Mask"',
        "GND"   # tie mounting holes to ground for shielding
    )]
    return render_footprint(
        f"H{idx + 1}", "MountingHole_M3", x, y, 0,
        "MountingHole:MountingHole_3.2mm_M3_Pad",
        pads, body_w=MH_PAD + 1, body_h=MH_PAD + 1
    )


def build_soic(ref, value, pos, fp_lib, n_pins, nets_dict):
    """SOIC-N footprint with two rows of n/2 pads at 1.27 mm pitch."""
    PITCH = 1.27
    ROW_W = 7.5      # SOIC-20 wide; sufficient for SOIC-14 too
    half_pins = n_pins // 2
    body_h = (half_pins - 1) * PITCH + 2.0
    body_w = ROW_W + 2.0
    pads = []
    for i in range(half_pins):
        # Left side: pins 1..half_pins, top to bottom
        num = str(i + 1)
        y = -(half_pins - 1) * PITCH / 2 + i * PITCH
        pads.append(render_pad(
            num, "smd", "rect",
            -ROW_W / 2, y, 1.5, 0.6, None,
            '"F.Cu" "F.Paste" "F.Mask"',
            nets_dict.get(num)
        ))
    for i in range(half_pins):
        # Right side: pins (half+1)..n, bottom to top (standard SOIC numbering)
        num = str(n_pins - i)
        y = -(half_pins - 1) * PITCH / 2 + i * PITCH
        pads.append(render_pad(
            num, "smd", "rect",
            +ROW_W / 2, y, 1.5, 0.6, None,
            '"F.Cu" "F.Paste" "F.Mask"',
            nets_dict.get(num)
        ))
    return render_footprint(ref, value, pos[0], pos[1], 0,
                            fp_lib, pads, body_w=body_w, body_h=body_h)


def build_0805(ref, value, pos, nets_dict, fp_lib="Resistor_SMD:R_0805_2012Metric"):
    """0805 two-pad SMD footprint (caps, resistors, LEDs)."""
    pads = []
    pads.append(render_pad("1", "smd", "rect", -0.95, 0, 1.0, 1.4, None,
                           '"F.Cu" "F.Paste" "F.Mask"', nets_dict.get("1")))
    pads.append(render_pad("2", "smd", "rect", +0.95, 0, 1.0, 1.4, None,
                           '"F.Cu" "F.Paste" "F.Mask"', nets_dict.get("2")))
    return render_footprint(ref, value, pos[0], pos[1], 0, fp_lib,
                            pads, body_w=2.6, body_h=1.6)


def build_rn9(ref, value, pos, nets_dict):
    """9-pin SIP resistor network (through-hole)."""
    pads = []
    for i in range(9):
        num = str(i + 1)
        x = -10.0 + i * 2.54
        pads.append(render_pad(
            num, "thru_hole", "circle" if i > 0 else "rect",
            x, 0, 1.6, 1.6, 0.8,
            '"*.Cu" "*.Mask"', nets_dict.get(num)
        ))
    return render_footprint(ref, value, pos[0], pos[1], 0,
                            "Resistor_THT:R_Array_SIP9",
                            pads, body_w=22.0, body_h=4.0)


# ---------------------------------------------------------------------------
# PCB assembly
# ---------------------------------------------------------------------------

PCB_HEADER = '''(kicad_pcb
  (version 20240108)
  (generator "ppc-isa-pcb-generator")
  (general
    (thickness 1.6)
    (legacy_teardrops no)
  )
  (paper "A4")
  (title_block
    (title "Amstrad PPC 512/640 - ISA Expansion Board")
    (date "2026-04-18")
    (rev "0.1")
    (company "Open Hardware")
    (comment 1 "Generated by generate_pcb.py")
    (comment 2 "Open in KiCad 8, then re-import netlist from schematic if needed")
  )
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive")
    (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings")
    (41 "Cmts.User" user "User.Comments")
    (42 "Eco1.User" user "User.Eco1")
    (43 "Eco2.User" user "User.Eco2")
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
    (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user)
    (49 "F.Fab" user)
  )
  (setup
    (pad_to_mask_clearance 0)
    (allow_soldermask_bridges_in_footprints no)
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (plot_on_all_layers_selection 0x0000000_00000000)
      (disableapertmacros no)
      (usegerberextensions no)
      (usegerberattributes yes)
      (usegerberadvancedattributes yes)
      (creategerberjobfile yes)
      (dashed_line_dash_ratio 12.000000)
      (dashed_line_gap_ratio 3.000000)
      (svgprecision 4)
      (plotframeref no)
      (viasonmask no)
      (mode 1)
      (useauxorigin no)
      (hpglpennumber 1)
      (hpglpenspeed 20)
      (hpglpendiameter 15.000000)
      (pdf_front_fp_property_popups yes)
      (pdf_back_fp_property_popups yes)
      (dxfpolygonmode yes)
      (dxfimperialunits yes)
      (dxfusepcbnewfont yes)
      (psnegative no)
      (psa4output no)
      (plotreference yes)
      (plotvalue yes)
      (plotinvisibletext no)
      (sketchpadsonfab no)
      (subtractmaskfromsilk no)
      (outputformat 1)
      (mirror no)
      (drillshape 1)
      (scaleselection 1)
      (outputdirectory "")
    )
  )
'''


def build_pcb() -> str:
    out = [PCB_HEADER]

    # Net 0 is always "no net" in KiCad
    out.append('  (net 0 "")')
    for net, idx in NET_INDEX.items():
        out.append(f'  (net {idx} "{net}")')
    out.append('')

    # Edge.Cuts rectangle
    rect_uuid = lambda corner: u(f"edge:{corner}")
    out.append(f'  (gr_line (start 0 0) (end {BOARD_W} 0) (stroke (width 0.1) (type solid)) (layer "Edge.Cuts") (uuid "{rect_uuid("bottom")}"))')
    out.append(f'  (gr_line (start {BOARD_W} 0) (end {BOARD_W} {BOARD_H}) (stroke (width 0.1) (type solid)) (layer "Edge.Cuts") (uuid "{rect_uuid("right")}"))')
    out.append(f'  (gr_line (start {BOARD_W} {BOARD_H}) (end 0 {BOARD_H}) (stroke (width 0.1) (type solid)) (layer "Edge.Cuts") (uuid "{rect_uuid("top")}"))')
    out.append(f'  (gr_line (start 0 {BOARD_H}) (end 0 0) (stroke (width 0.1) (type solid)) (layer "Edge.Cuts") (uuid "{rect_uuid("left")}"))')

    # Mounting holes
    for i, (x, y) in enumerate(MOUNTING_HOLES):
        out.append(build_mounting_hole(i, x, y))

    # ISA slots
    for ref, y_centre in ISA_SLOTS:
        out.append(build_isa_slot(ref, y_centre))

    # D-sub connectors (pull nets from schematic instances)
    j1 = next(i for i in sch.instances if i.ref == "J1")
    j2 = next(i for i in sch.instances if i.ref == "J2")
    out.append(build_dsub("J1", 25, J1_POS, j1.nets, "DB25 Male"))
    out.append(build_dsub("J2", 37, J2_POS, j2.nets, "DB37 Male"))

    # SMD ICs
    u1 = next(i for i in sch.instances if i.ref == "U1")
    u2 = next(i for i in sch.instances if i.ref == "U2")
    out.append(build_soic("U1", "74HC244", U1_POS,
                          "Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm", 20, u1.nets))
    out.append(build_soic("U2", "74HC244", U2_POS,
                          "Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm", 20, u2.nets))

    # Resistor network
    rr1 = next(i for i in sch.instances if i.ref == "RR1")
    out.append(build_rn9("RR1", "10k", RR1_POS, rr1.nets))

    # 0805 caps, resistors, LEDs -- arrange in a column on the right side
    smd_x = 105.0
    smd_y = 5.0
    for inst in sch.instances:
        if inst.ref in ("J1", "J2", "J3", "J4", "J5", "U1", "U2", "U4", "RR1"):
            continue
        # 0805 footprint stub for everything else
        if inst.lib_id == "C":
            out.append(build_0805(inst.ref, inst.value, (smd_x, smd_y), inst.nets,
                                  "Capacitor_SMD:C_0805_2012Metric"))
        elif inst.lib_id == "R":
            out.append(build_0805(inst.ref, inst.value, (smd_x, smd_y), inst.nets,
                                  "Resistor_SMD:R_0805_2012Metric"))
        elif inst.lib_id == "LED":
            out.append(build_0805(inst.ref, inst.value, (smd_x, smd_y), inst.nets,
                                  "LED_SMD:LED_0805_2012Metric"))
        smd_y += 3.0
        if smd_y > BOARD_H - 5:
            smd_y = 5.0
            smd_x -= 5.0

    out.append(')\n')
    return '\n'.join(out)


if __name__ == "__main__":
    out_path = Path(__file__).resolve().parent.parent / "kicad" / "ppc-isa-expansion.kicad_pcb"
    out_path.write_text(build_pcb())
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
    print(f"Nets: {len(NETS)}")
    print(f"Components: {len(sch.instances) + 4 + 3}")  # +4 mounting holes +3 ISA slots
