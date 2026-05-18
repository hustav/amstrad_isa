#!/usr/bin/env python3
"""Generate a BOM CSV from the schematic generator's instance list."""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_schematic as sch  # noqa: E402


# Columns: Ref, Qty, Value, Footprint, Description, Notes
PART_INFO = {
    # lib_id                          -> (description,                  notes)
    "DB25_Male":    ("D-sub 25-pin male, right-angle PCB mount",         "mates with Amstrad Expansion Connector A"),
    "DB37_Male":    ("D-sub 37-pin male, right-angle PCB mount",         "mates with Amstrad Expansion Connector B"),
    "ISA_8Bit_Edge":("XT 8-bit ISA slot (62-pin card-edge socket)",      "2x31 on 2.54 mm pitch; 5.08 mm between rows"),
    "74HC244":      ("Octal bus buffer / line driver, non-inverting",    "SOIC-20 wide body; any 74HC244 or 74HCT244 works"),
    "74HC74":       ("Dual D positive-edge-triggered flip-flop",         "SOIC-14; 74HCT74 or 74HC74 both acceptable"),
    "R_Network_9":  ("9-pin SIP resistor network (8 bussed resistors)",  "10K value; Bourns 4609X-101-103 or equivalent"),
    "R":            ("Chip resistor",                                    "0805 (2012 metric); +/-1% or 5% is fine"),
    "C":            ("Chip capacitor, X7R ceramic",                      "0805; 50V rating"),
    "LED":          ("Chip LED",                                         "0805; choose visible colour (green/red/amber)"),
}


def group_by_value() -> list[tuple]:
    """Group instances by (lib_id, value, footprint) and list the refs."""
    groups = defaultdict(list)
    for inst in sch.instances:
        key = (inst.lib_id, inst.value, inst.footprint)
        groups[key].append(inst.ref)
    rows = []
    for (lib_id, value, footprint), refs in sorted(
            groups.items(),
            key=lambda k: (k[0][0], k[0][1])):
        desc, notes = PART_INFO.get(lib_id, ("", ""))
        rows.append({
            "References": ", ".join(sorted(refs)),
            "Quantity": len(refs),
            "Value": value,
            "Footprint": footprint,
            "Description": desc,
            "Notes": notes,
        })
    return rows


def main():
    out_path = Path(__file__).resolve().parent.parent / "docs" / "BOM.csv"
    rows = group_by_value()
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "References", "Quantity", "Value", "Footprint", "Description", "Notes"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out_path}  ({len(rows)} line items)")
    total = sum(r["Quantity"] for r in rows)
    print(f"Total components: {total}")


if __name__ == "__main__":
    main()
