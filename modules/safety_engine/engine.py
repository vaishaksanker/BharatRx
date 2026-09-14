"""
engine.py
---------
THE MAIN FILE. This is the one your teammates call.

It does not contain any medical logic itself. Its only job is to:
  1. Run all five checkers
  2. Collect their alerts into one list
  3. Sort them so the scariest ones appear first
  4. Ask severity.py for the overall verdict
  5. Return one clean dictionary that Vaishak's React dashboard can render

Keep it this way. When a teammate asks "where is the drug logic?", the
answer should be drug_checker.py - never here.
"""

from . import drug_checker
from . import disease_checker
from . import allergy_checker
from . import duplicate_checker
from . import context_checker
from . import coverage_checker
from . import severity as severity_module


# The order alerts are shown in. Drug-drug and allergy are the ones
# judges recognise instantly, so they sit at the top.
CATEGORY_ORDER = [
    "Allergy",
    "Allergy (Cross-reactivity)",
    "Drug-Drug Interaction",
    "Drug-Disease Interaction",
    "Pregnancy Risk",
    "Duplicate Therapy",
    "Age-related Risk",
    "Coverage Limitation",
]

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def analyse(patient, prescription):
    """
    The single public function of this whole module.

    patient      : dict  - age, gender, pregnant, diseases, allergies,
                           current_medicines   (comes from Namita)
    prescription : list  - medicine names      (comes from Keshav)

    Returns a dict ready to be sent to the frontend as JSON.
    """

    # Defensive defaults. If Namita's module sends a half-filled profile
    # on hackathon day, the engine should still run rather than crash.
    patient = patient or {}
    prescription = prescription or []

    # ---- Run all five checks ----
    alerts = []
    alerts += allergy_checker.check(patient, prescription)
    alerts += drug_checker.check(patient, prescription)
    alerts += disease_checker.check(patient, prescription)
    alerts += context_checker.check(patient, prescription)
    alerts += duplicate_checker.check(patient, prescription)

    # Runs last: reports what we could NOT check, so silence is never
    # mistaken for safety.
    alerts += coverage_checker.check(patient, prescription)
    alerts += coverage_checker.check_current_medicines(patient)

    # ---- Sort: HIGH first, then by category importance ----
    alerts.sort(key=lambda a: (
        SEVERITY_ORDER.get(a.get("severity"), 3),
        CATEGORY_ORDER.index(a["category"]) if a["category"] in CATEGORY_ORDER else 99,
    ))

    # ---- Overall verdict ----
    # Coverage notes are a data limitation, not a clinical risk, so they
    # are excluded from the score and the overall verdict.
    clinical_alerts = [a for a in alerts if a["category"] != "Coverage Limitation"]
    overall_risk, risk_score = severity_module.calculate(clinical_alerts)
    coverage_notes = len(alerts) - len(clinical_alerts)

    # ---- Per-medicine verdict, so the dashboard can colour each row ----
    medicine_summary = build_medicine_summary(prescription, alerts)

    return {
        "overall_risk": overall_risk,
        "risk_score": risk_score,
        "counts": severity_module.summarise(clinical_alerts),
        "unchecked_medicines": coverage_notes,
        "medicines": medicine_summary,
        "alerts": alerts,
    }


def build_medicine_summary(prescription, alerts):
    """
    For each prescribed medicine, work out its worst severity.

    The dashboard shows a table like:
        Ibuprofen    HIGH    2 concerns
        Paracetamol  LOW     No concerns detected
    This function produces exactly that.
    """
    summary = []

    for med in prescription:
        # Find every alert that belongs to this medicine
        own_alerts = [a for a in alerts if a["medicine"] == med]

        if not own_alerts:
            worst = "LOW"
        else:
            # Sort this medicine's alerts and take the most severe one
            worst = sorted(
                own_alerts,
                key=lambda a: SEVERITY_ORDER.get(a["severity"], 3)
            )[0]["severity"]

        summary.append({
            "name": med,
            "severity": worst,
            "concern_count": len(own_alerts),
            "status": "No major concern detected" if not own_alerts
                      else f"{len(own_alerts)} concern(s) detected",
        })

    return summary
