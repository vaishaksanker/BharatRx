"""
duplicate_checker.py
--------------------
SAFETY CHECK 4 of 5: Duplicate therapy.

Question: "Is the same active ingredient being given twice under
different names?"

This is the most India-relevant check in the whole engine. Indian
prescribing is brand-heavy, so "Dolo 650 + Crocin" or "Combiflam + Dolo"
looks like two different medicines to a patient but is a double dose of
paracetamol.
"""

from .utils import to_generics


def check(patient, prescription):
    alerts = []

    current = patient.get("current_medicines", []) or []

    # Build a map:  generic name -> every raw name that contains it
    # e.g. {"Paracetamol": ["Dolo 650", "Combiflam"]}
    seen = {}

    def record(raw_name, source):
        for generic in to_generics(raw_name):
            seen.setdefault(generic, [])
            seen[generic].append({"name": raw_name, "source": source})

    for med in current:
        record(med, "current")
    for med in prescription:
        record(med, "prescription")

    # Now: any generic that appears more than once is a duplicate
    for generic, entries in seen.items():
        if len(entries) < 2:
            continue

        # Only alert if at least one of them is newly prescribed.
        # If both are existing medicines, the doctor already knows.
        if not any(e["source"] == "prescription" for e in entries):
            continue

        names = [e["name"] for e in entries]

        alerts.append({
            "medicine": names[-1],
            "generic": generic,
            "severity": "MEDIUM",
            "category": "Duplicate Therapy",
            "title": f"{generic} appears more than once",
            "reason": (
                f"{' and '.join(names)} {'both' if len(names) == 2 else 'all'} contain {generic}. "
                f"Taking them together may exceed the maximum safe daily dose."
            ),
            "recommendation": (
                f"Use only one {generic}-containing product unless the "
                f"prescriber has specifically intended both."
            ),
            "triggered_by": ", ".join(names[:-1]),
        })

    return alerts
