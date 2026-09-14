"""
allergy_checker.py
------------------
SAFETY CHECK 3 of 5: Allergy.

Question: "Does this prescription contain something the patient is allergic to,
or something from the same drug family?"

Two levels:
  DIRECT     - Penicillin allergy + Amoxicillin  -> HIGH (same family)
  CROSS      - Penicillin allergy + Cefixime     -> MEDIUM (related family)
"""

from .utils import ALLERGY_GROUPS, CROSS_REACTIVITY, to_generics, find_key


def check(patient, prescription):
    alerts = []

    allergies = patient.get("allergies", []) or []

    for allergy in allergies:
        # Namita's chatbot may send either a plain string ("Penicillin")
        # or a dict ({"medicine": "Penicillin", "reaction": "rash"}).
        # Handle both so integration day has no surprises.
        if isinstance(allergy, dict):
            allergy_name = allergy.get("medicine") or allergy.get("name", "")
        else:
            allergy_name = allergy

        group_key = find_key(ALLERGY_GROUPS, allergy_name)
        if not group_key:
            continue              # we don't know this allergy family - skip it

        family_members = ALLERGY_GROUPS[group_key]

        for new_med in prescription:
            for generic in to_generics(new_med):

                # --- Level 1: direct match inside the allergy family ---
                if any(generic.lower() == m.lower() for m in family_members):
                    alerts.append({
                        "medicine": new_med,
                        "generic": generic,
                        "severity": "HIGH",
                        "category": "Allergy",
                        "title": f"{group_key} allergy alert",
                        "reason": (
                            f"{generic} belongs to the {group_key} family, "
                            f"which the patient has reported an allergy to. "
                            f"This may cause rash, swelling or in severe cases anaphylaxis."
                        ),
                        "recommendation": (
                            "Do not dispense without clinician review. "
                            "An antibiotic from a different class should be considered."
                        ),
                        "triggered_by": allergy_name,
                    })
                    continue

                # --- Level 2: cross-reactivity with a related family ---
                related = CROSS_REACTIVITY.get(group_key, {})
                for other_family, info in related.items():
                    members = ALLERGY_GROUPS.get(other_family, [])
                    if any(generic.lower() == m.lower() for m in members):
                        alerts.append({
                            "medicine": new_med,
                            "generic": generic,
                            "severity": info["severity"],
                            "category": "Allergy (Cross-reactivity)",
                            "title": f"Possible cross-reaction with {group_key} allergy",
                            "reason": info["reason"],
                            "recommendation": (
                                "Confirm the nature of the previous reaction with the "
                                "patient before dispensing."
                            ),
                            "triggered_by": allergy_name,
                        })

    return alerts
