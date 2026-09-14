"""
disease_checker.py
------------------
SAFETY CHECK 2 of 5: Drug <-> Disease.

Question: "Is this medicine risky because of a condition the patient HAS?"

The medicine itself is fine. It is wrong for THIS patient.
This is the check that makes BharatRx patient-specific rather than a
generic interaction lookup.
"""

from .utils import DISEASE_RULES, to_generics, find_key


def check(patient, prescription):
    alerts = []

    diseases = patient.get("diseases", []) or []

    for new_med in prescription:
        for generic in to_generics(new_med):

            # Does the dataset have any rules for this medicine at all?
            med_key = find_key(DISEASE_RULES, generic)
            if not med_key:
                continue

            rules_for_medicine = DISEASE_RULES[med_key]

            # It does. Now check each of the patient's diseases against it.
            for disease in diseases:
                disease_key = find_key(rules_for_medicine, disease)
                if not disease_key:
                    continue

                rule = rules_for_medicine[disease_key]
                alerts.append({
                    "medicine": new_med,
                    "generic": generic,
                    "severity": rule["severity"],
                    "category": "Drug-Disease Interaction",
                    "title": f"{generic} with {disease_key}",
                    "reason": rule["reason"],
                    "recommendation": rule["recommendation"],
                    "triggered_by": disease,
                })

    return alerts
