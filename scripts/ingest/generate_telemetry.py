"""
generate_telemetry.py — AWS AI Watchman
Generates synthetic IoT sensor telemetry for a heavy equipment fleet
and writes it as a CSV ready to upload to the Bronze S3 layer.

Usage:
    python generate_telemetry.py
    python generate_telemetry.py --rows 5000 --days 60 --out-dir data
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

# ---------------------------------------------------------------------------
# Fleet definition — mirrors United Rentals-style mixed equipment pool
# ---------------------------------------------------------------------------
FLEET = (
    [{"id": f"CAT-EX-{i:03d}", "type": "Excavator",  "brand": "Caterpillar"} for i in range(1, 6)] +
    [{"id": f"GEN-BL-{i:03d}", "type": "Boom Lift",  "brand": "Genie"}       for i in range(1, 4)] +
    [{"id": f"JD-BD-{i:03d}",  "type": "Bulldozer",  "brand": "John Deere"}  for i in range(1, 4)] +
    [{"id": f"KOM-FE-{i:03d}", "type": "Forklift",   "brand": "Komatsu"}     for i in range(1, 4)] +
    [{"id": f"JLG-SL-{i:03d}", "type": "Scissor Lift","brand": "JLG"}        for i in range(1, 3)]
)

# Error codes and their probability of appearing in a single reading
ERROR_WEIGHTS = {
    "":     0.84,   # Normal operation
    "E001": 0.05,   # High engine coolant temperature
    "E002": 0.04,   # Low hydraulic pressure
    "E003": 0.03,   # Low fuel (< 15 %)
    "E004": 0.02,   # Sensor fault / intermittent signal
    "E005": 0.02,   # Filter maintenance overdue
}

LOCATIONS = [f"YARD-{i:02d}" for i in range(1, 8)]


def _reading(equipment: dict, ts: datetime) -> dict:
    error = random.choices(list(ERROR_WEIGHTS), weights=list(ERROR_WEIGHTS.values()))[0]

    engine_temp        = random.uniform(230, 285) if error == "E001" else random.uniform(165, 220)
    hydraulic_pressure = random.uniform(900, 1500) if error == "E002" else random.uniform(2000, 3200)
    fuel_level         = random.uniform(2, 14)     if error == "E003" else random.uniform(15, 100)

    return {
        "Equipment_ID":           equipment["id"],
        "Equipment_Type":         equipment["type"],
        "Brand":                  equipment["brand"],
        "Timestamp":              ts.strftime("%Y-%m-%dT%H:%M:%S"),
        "Engine_Temp_F":          round(engine_temp, 1),
        "Hydraulic_Pressure_PSI": round(hydraulic_pressure, 1),
        "RPM":                    random.randint(600, 2200),
        "Fuel_Level_Pct":         round(fuel_level, 1),
        "Operating_Hours":        round(random.uniform(50, 18000), 1),
        "Battery_Voltage":        round(random.uniform(11.8, 14.5), 2),
        "Ambient_Temp_F":         round(random.uniform(10, 105), 1),
        "Location_ID":            random.choice(LOCATIONS),
        "Error_Code":             error,
    }


FIELDNAMES = [
    "Equipment_ID", "Equipment_Type", "Brand", "Timestamp",
    "Engine_Temp_F", "Hydraulic_Pressure_PSI", "RPM", "Fuel_Level_Pct",
    "Operating_Hours", "Battery_Voltage", "Ambient_Temp_F",
    "Location_ID", "Error_Code",
]


def generate(rows: int, days: int, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    start = datetime.now() - timedelta(days=days)
    outfile = out_dir / f"telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for i in range(rows):
            equipment = random.choice(FLEET)
            ts = start + timedelta(seconds=random.randint(0, days * 86_400))
            writer.writerow(_reading(equipment, ts))
            if (i + 1) % 250 == 0:
                print(f"  {i + 1:>6,} / {rows:,} rows written…")

    return outfile


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic fleet IoT telemetry.")
    parser.add_argument("--rows",    type=int, default=1_000, help="Number of sensor readings (default 1000)")
    parser.add_argument("--days",    type=int, default=30,    help="Time window in days (default 30)")
    parser.add_argument("--out-dir", default="data",          help="Output directory (default: data/)")
    args = parser.parse_args()

    print(f"Generating {args.rows:,} telemetry readings over {args.days} days…")
    outfile = generate(args.rows, args.days, Path(args.out_dir))
    print(f"OK  Telemetry written -> {outfile}")


if __name__ == "__main__":
    main()
