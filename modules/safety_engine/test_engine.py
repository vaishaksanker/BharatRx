"""
test_engine.py
--------------
Run this to prove your module works without Namita, Keshav or Vaishak.

    python -m modules.safety_engine.test_engine

Run it from the BharatRx root folder (the one containing modules/ and data/).
"""

import json
import glob
from pathlib import Path

from .engine import analyse

DEMO_DIR = Path(__file__).resolve().parents[2] / "data" / "demo"

COLOUR = {"HIGH": "\033[91m", "MEDIUM": "\033[93m", "LOW": "\033[92m"}
RESET = "\033[0m"


def run_one(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    patient = data["patient"]
    prescription = data["prescription"]

    report = analyse(patient, prescription)

    print("=" * 72)
    print(f"FILE     : {Path(path).name}")
    print(f"SCENARIO : {data.get('_scenario', '-')}")
    print(f"PATIENT  : {patient['name']}, {patient['age']}y {patient['gender']}")
    print(f"           conditions : {patient['diseases'] or 'none'}")
    print(f"           allergies  : {patient['allergies'] or 'none'}")
    print(f"           on         : {patient['current_medicines'] or 'none'}")
    print(f"NEW RX   : {prescription}")
    print("-" * 72)
    c = COLOUR.get(report["overall_risk"], "")
    print(f"OVERALL  : {c}{report['overall_risk']}{RESET}   score {report['risk_score']}/100   "
          f"({report['counts']['high']} high, {report['counts']['medium']} medium)")
    print("-" * 72)

    for med in report["medicines"]:
        c = COLOUR.get(med["severity"], "")
        print(f"  {c}[{med['severity']:<6}]{RESET} {med['name']:<18} {med['status']}")

    if report["alerts"]:
        print()
        for i, a in enumerate(report["alerts"], 1):
            c = COLOUR.get(a["severity"], "")
            print(f"  {i}. {c}{a['severity']}{RESET}  {a['category']}")
            print(f"     {a['title']}")
            print(f"     Why    : {a['reason']}")
            print(f"     Action : {a['recommendation']}")
            print()
    print()

    return report


def main():
    files = sorted(glob.glob(str(DEMO_DIR / "patient*.json")))
    if not files:
        print(f"No demo files found in {DEMO_DIR}")
        return
    for f in files:
        run_one(f)
    print("All demo patients processed.")


if __name__ == "__main__":
    main()
