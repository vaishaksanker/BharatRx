"""
coverage_checker.py
-------------------
SAFETY CHECK 6: Knowledge coverage.

Every other checker answers "is there a problem?" This one answers a
different and more honest question:

    "Do I actually know anything about this medicine at all?"

WHY THIS EXISTS
---------------
A lookup engine can only say "found" or "not found". But "not found"
covers three completely different situations:

    1. No interaction exists          -> genuinely safe
    2. Interaction exists, we never added it  -> DANGEROUS
    3. Drug isn't in our data at all  -> UNKNOWN

Without this checker, all three print the same green "no concern
detected". A doctor reads that as "checked and cleared", which for
cases 2 and 3 is false reassurance.

This is called a false negative, and in clinical software it is worse
than a false alarm. A false alarm annoys. A false negative lets a
harmful prescription through with a reassuring tick.

So: when we don't know a medicine, we say so.
"""

from .utils import to_generics, is_known_drug


def check(patient, prescription):
    """
    Flag any medicine the knowledge base has never seen.

    Severity is LOW - this is not a clinical danger, it is a limitation
    of our data. But it is visible, which is the whole point.
    """
    alerts = []

    for raw_name in prescription:
        generics = to_generics(raw_name)

        # Which components of this medicine are unknown to us?
        unknown = [g for g in generics if not is_known_drug(g)]

        if not unknown:
            continue          # we know every component - nothing to report

        names = ", ".join(unknown)

        alerts.append({
            "medicine": raw_name,
            "generic": unknown[0],
            "severity": "LOW",
            "category": "Coverage Limitation",
            "title": f"{names} not in knowledge base",
            "reason": (
                f"{names} is not present in the BharatRx knowledge base, so no "
                f"automated interaction, allergy or contraindication check could "
                f"be performed for it. The absence of an alert does not mean this "
                f"medicine is safe for this patient."
            ),
            "recommendation": (
                "Verify this medicine manually against a drug reference or with "
                "a pharmacist before dispensing."
            ),
            "triggered_by": "knowledge base coverage",
            "evidence": "coverage",
        })

    return alerts


def check_current_medicines(patient):
    """
    Same idea, but for medicines the patient is ALREADY taking.

    This matters just as much. If the patient is on a drug we don't
    know, then every drug-drug check against it silently found nothing
    - not because it is safe, but because we had nothing to compare.
    """
    alerts = []
    current = patient.get("current_medicines", []) or []

    for raw_name in current:
        unknown = [g for g in to_generics(raw_name) if not is_known_drug(g)]
        if not unknown:
            continue

        names = ", ".join(unknown)
        alerts.append({
            "medicine": raw_name,
            "generic": unknown[0],
            "severity": "LOW",
            "category": "Coverage Limitation",
            "title": f"Existing medicine {names} not recognised",
            "reason": (
                f"The patient's current medicine {names} is not in the knowledge "
                f"base, so the new prescription could not be checked against it "
                f"for interactions."
            ),
            "recommendation": (
                "Review this existing medicine manually against the new prescription."
            ),
            "triggered_by": "knowledge base coverage",
            "evidence": "coverage",
        })

    return alerts
