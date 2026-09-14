"""
store.py
--------
The filing cabinet.

Saves each prescription to a file, and later tells you which of those
medicines the patient is STILL taking today.

No SQL, no server, no install. One JSON file per patient, stored in
data/patients/. That is enough for a hackathon and easy to explain.

Three public functions:
    save_prescription(...)     write a visit to the file
    get_active_medicines(...)  read back only what is still running
    load_patient(...)          read the whole record
"""

import json
from datetime import date, timedelta
from pathlib import Path

# data/patients/  sits two levels above this file's folder
# parents[0]=patient_history  [1]=modules  [2]=BharatRx
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PATIENT_DIR = PROJECT_ROOT / "data" / "patients"


def _file_for(patient_id):
    """Build the path to one patient's file, e.g. data/patients/P001.json"""
    # Ensure the folder exists. exist_ok=True means "don't complain if
    # it's already there".
    PATIENT_DIR.mkdir(parents=True, exist_ok=True)
    return PATIENT_DIR / f"{patient_id}.json"


def load_patient(patient_id):
    """
    Read a patient's whole record.

    Returns an empty template if the patient has never been seen before,
    so callers never have to handle a None.
    """
    path = _file_for(patient_id)

    if not path.exists():
        return {
            "patient_id": patient_id,
            "name": None,
            "age": None,
            "gender": None,
            "pregnant": False,
            "diseases": [],
            "allergies": [],
            "prescriptions": [],
        }

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_patient(record):
    """Write a whole patient record back to disk."""
    path = _file_for(record["patient_id"])
    with open(path, "w", encoding="utf-8") as f:
        # indent=2 makes the file readable when you open it in VS Code.
        json.dump(record, f, indent=2, ensure_ascii=False)
    return path


def update_profile(patient_id, name=None, age=None, gender=None,
                   pregnant=None, diseases=None, allergies=None):
    """
    Update the slow-changing parts of a patient: age, conditions, allergies.

    Only the values you pass are changed. Passing nothing for a field
    leaves whatever was already stored.
    """
    record = load_patient(patient_id)

    if name is not None:
        record["name"] = name
    if age is not None:
        record["age"] = age
    if gender is not None:
        record["gender"] = gender
    if pregnant is not None:
        record["pregnant"] = pregnant
    if diseases is not None:
        record["diseases"] = diseases
    if allergies is not None:
        record["allergies"] = allergies

    save_patient(record)
    return record


def save_prescription(patient_id, medicines, duration_days=30, visit_date=None):
    """
    Append one visit to the patient's history.

    medicines     : list of names, e.g. ["Glycomet 500"]
    duration_days : how long the course runs. 5 for an antibiotic,
                    365 for a long-term diabetes medicine.
    visit_date    : defaults to today. Pass a date to backdate a visit
                    (useful for building demo data).
    """
    if visit_date is None:
        visit_date = date.today()

    record = load_patient(patient_id)

    record["prescriptions"].append({
        # isoformat() turns a date into text like "2026-01-15",
        # because JSON cannot store a date object directly.
        "date": visit_date.isoformat(),
        "medicines": list(medicines),
        "duration_days": duration_days,
    })

    save_patient(record)
    return record


def get_active_medicines(patient_id, on_date=None):
    """
    THE IMPORTANT ONE.

    Returns only the medicines the patient is still taking on a given
    date - not everything they have ever been prescribed.

    How it decides:
        start = the prescription date
        end   = start + duration_days
        active if   start <= on_date <= end

    Example. Today is 20 August 2026.
        Glycomet, 15 Jan, 365 days  -> ends 15 Jan 2027  -> ACTIVE
        Azee,      3 Mar,   5 days  -> ended  8 Mar 2026 -> finished

    Without this, the engine would be handed a five-day antibiotic from
    six months ago and would flag interactions that no longer exist.
    """
    if on_date is None:
        on_date = date.today()

    record = load_patient(patient_id)
    active = []

    for entry in record["prescriptions"]:
        # fromisoformat() turns "2026-01-15" back into a real date
        start = date.fromisoformat(entry["date"])
        end = start + timedelta(days=entry.get("duration_days", 30))

        if start <= on_date <= end:
            for med in entry["medicines"]:
                if med not in active:      # avoid listing the same drug twice
                    active.append(med)

    return active


def build_engine_input(patient_id, new_prescription, on_date=None):
    """
    Convenience function: assemble exactly what the safety engine wants.

    This is the bridge between the filing cabinet and the calculator.
    It reads the stored profile and active medicines, then hands back a
    dict in the shape analyse() already expects.
    """
    record = load_patient(patient_id)

    patient = {
        "name": record.get("name"),
        "age": record.get("age"),
        "gender": record.get("gender"),
        "pregnant": record.get("pregnant", False),
        "diseases": record.get("diseases", []),
        "allergies": record.get("allergies", []),
        "current_medicines": get_active_medicines(patient_id, on_date),
    }

    return patient, list(new_prescription)
