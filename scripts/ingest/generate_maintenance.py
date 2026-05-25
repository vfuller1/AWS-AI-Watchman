"""
generate_maintenance.py — AWS AI Watchman
Generates 1 000 rows of synthetic maintenance service log records
and writes them as a CSV ready to upload to the Bronze S3 layer.

Usage:
    python generate_maintenance.py
    python generate_maintenance.py --rows 1000 --out-dir data
"""

import csv
import random
import argparse
from datetime import datetime, timedelta
from pathlib import Path

try:
    from faker import Faker
except ImportError:
    raise SystemExit("Run: pip install -r requirements.txt")

fake = Faker()
Faker.seed(42)
random.seed(42)

# ---------------------------------------------------------------------------
# Equipment fleet (same IDs as telemetry for cross-referencing)
# ---------------------------------------------------------------------------
EQUIPMENT_IDS = (
    [f"CAT-EX-{i:03d}" for i in range(1, 6)] +
    [f"GEN-BL-{i:03d}" for i in range(1, 4)] +
    [f"JD-BD-{i:03d}"  for i in range(1, 4)] +
    [f"KOM-FE-{i:03d}" for i in range(1, 4)] +
    [f"JLG-SL-{i:03d}" for i in range(1, 3)]
)

TECHNICIANS = [f"TECH-{i:03d}" for i in range(1, 20)]

# ---------------------------------------------------------------------------
# Fault library — realistic notes a technician would write
# ---------------------------------------------------------------------------
FAULTS = [
    {
        "error_code":  "E001",
        "fault":       "High engine coolant temperature",
        "notes":  [
            "Engine temp exceeded 240°F at idle. Radiator fins clogged with debris. Cleaned with compressed air and pressure-washed fins.",
            "Thermostat stuck closed. Replaced thermostat and refilled coolant system with 50/50 mix.",
            "Water pump impeller worn. Replaced water pump assembly; verified temp stabilised under load.",
        ],
        "resolution":  "Cooling system serviced; temp normalised to operating range",
        "parts":       "Thermostat, coolant (5L)",
    },
    {
        "error_code":  "E002",
        "fault":       "Low hydraulic pressure alarm",
        "notes":  [
            "Found weeping seal on hydraulic cylinder rod. Replaced rod seals; re-tested at full pressure — no leaks.",
            "Hydraulic pump output low. Replaced pump; set relief valve to 2800 PSI per spec.",
            "Suction line partially collapsed causing cavitation. Replaced suction hose; flushed hydraulic tank.",
        ],
        "resolution":  "Hydraulic system repaired and pressure restored to spec (2800 PSI)",
        "parts":       "Hydraulic pump seal kit, hose assembly",
    },
    {
        "error_code":  "E003",
        "fault":       "Low fuel level warning (< 15%)",
        "notes":  [
            "Unit ran dry on job site. Refuelled 45L diesel. Bled fuel system and confirmed restart.",
            "Fuel gauge sender faulty — showing low when tank at 40%. Replaced sender unit.",
            "Fuel filter heavily contaminated. Replaced filter; drained and cleaned fuel tank.",
        ],
        "resolution":  "Fuel system serviced; equipment returned to service",
        "parts":       "Fuel filter, sender unit",
    },
    {
        "error_code":  "E004",
        "fault":       "Intermittent sensor fault / signal loss",
        "notes":  [
            "CAN bus connector at engine ECU corroded. Cleaned and applied dielectric grease; fault cleared.",
            "Engine speed sensor harness chafed against frame. Re-routed and secured harness; sensor replaced.",
            "ECU firmware outdated causing false faults. Updated firmware to v4.2.1 per OEM bulletin.",
        ],
        "resolution":  "Sensor/wiring fault resolved; no further codes logged",
        "parts":       "Engine speed sensor, wiring loom repair kit",
    },
    {
        "error_code":  "E005",
        "fault":       "Filter maintenance overdue",
        "notes":  [
            "Air filter restriction indicator in red. Replaced primary and secondary air filters.",
            "Hydraulic return filter at bypass. Replaced filter element; flushed system.",
            "Engine oil and oil filter overdue (900h since last service). Completed full service: oil, filters, belts inspected.",
        ],
        "resolution":  "All filters replaced; equipment returned to PM schedule",
        "parts":       "Air filter kit, hydraulic filter, engine oil (15L)",
    },
    {
        "error_code":  "",
        "fault":       "Scheduled preventive maintenance",
        "notes":  [
            "Completed 500-hour PM: engine oil, filters, greased all fittings, inspected tracks.",
            "Annual inspection: checked all safety systems, replaced worn drive belt, lubed boom pivots.",
            "Pre-rental inspection: found cracked hose on return circuit — replaced before dispatch.",
        ],
        "resolution":  "PM completed; unit inspected and cleared for service",
        "parts":       "Engine oil (15L), filter kit, grease cartridges",
    },
]

FIELDNAMES = [
    "Record_ID", "Equipment_ID", "Service_Date", "Technician_ID",
    "Error_Code", "Fault_Description", "Technician_Notes",
    "Resolution", "Parts_Replaced", "Labor_Hours", "Total_Cost_USD",
    "Equipment_Operating_Hours", "Next_Service_Due_Hours",
]


def _record(record_id: int, start: datetime, days: int) -> dict:
    fault = random.choice(FAULTS)
    svc_date = start + timedelta(days=random.randint(0, days))
    op_hours = round(random.uniform(50, 18_000), 1)
    labor_hrs = round(random.uniform(0.5, 8.0), 1)
    parts_cost = round(random.uniform(25, 1_200), 2)
    labor_rate = 95  # $/hr
    total_cost = round(labor_hrs * labor_rate + parts_cost, 2)

    return {
        "Record_ID":                  f"SR-{record_id:06d}",
        "Equipment_ID":               random.choice(EQUIPMENT_IDS),
        "Service_Date":               svc_date.strftime("%Y-%m-%d"),
        "Technician_ID":              random.choice(TECHNICIANS),
        "Error_Code":                 fault["error_code"],
        "Fault_Description":          fault["fault"],
        "Technician_Notes":           random.choice(fault["notes"]),
        "Resolution":                 fault["resolution"],
        "Parts_Replaced":             fault["parts"],
        "Labor_Hours":                labor_hrs,
        "Total_Cost_USD":             total_cost,
        "Equipment_Operating_Hours":  op_hours,
        "Next_Service_Due_Hours":     round(op_hours + 500, 1),
    }


def generate(rows: int, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    start = datetime.now() - timedelta(days=365)
    outfile = out_dir / f"maintenance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for i in range(rows):
            writer.writerow(_record(i + 1, start, 365))
            if (i + 1) % 250 == 0:
                print(f"  {i + 1:>6,} / {rows:,} rows written…")

    return outfile


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic maintenance service records.")
    parser.add_argument("--rows",    type=int, default=1_000, help="Number of records (default 1000)")
    parser.add_argument("--out-dir", default="data",          help="Output directory (default: data/)")
    args = parser.parse_args()

    print(f"Generating {args.rows:,} maintenance records…")
    outfile = generate(args.rows, Path(args.out_dir))
    print(f"OK  Maintenance log written -> {outfile}")


if __name__ == "__main__":
    main()
