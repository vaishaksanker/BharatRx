"""
context_checker.py
------------------
SAFETY CHECK 5 of 5: Patient context.

Question: "Is this medicine risky because of WHO the patient is - their
age or pregnancy status - rather than what else they take?"

Three sub-checks:
  age_above  - elderly warnings  (sleeping pills at 70)
  age_below  - paediatric warnings (aspirin at 10 -> Reye's syndrome)
  pregnancy  - teratogenic drugs
"""

from .utils import CONTEXT_RULES, to_generics, find_key


def check(patient, prescription):
    alerts = []

    age = patient.get("age")
    pregnant = patient.get("pregnant", False)

    for new_med in prescription:
        for generic in to_generics(new_med):

            # ---------- Elderly rules ----------
            if age is not None:
                key = find_key(CONTEXT_RULES["age_above"], generic)
                if key:
                    rule = CONTEXT_RULES["age_above"][key]
                    if age >= rule["age"]:
                        alerts.append(_alert(
                            new_med, generic, rule,
                            "Age-related Risk",
                            f"{generic} in patients over {rule['age']}",
                            f"age {age}",
                        ))

                key = find_key(CONTEXT_RULES["age_below"], generic)
                if key:
                    rule = CONTEXT_RULES["age_below"][key]
                    if age < rule["age"]:
                        alerts.append(_alert(
                            new_med, generic, rule,
                            "Age-related Risk",
                            f"{generic} in patients under {rule['age']}",
                            f"age {age}",
                        ))

            # ---------- Pregnancy rules ----------
            if pregnant:
                key = find_key(CONTEXT_RULES["pregnancy"], generic)
                if key:
                    rule = CONTEXT_RULES["pregnancy"][key]
                    alerts.append(_alert(
                        new_med, generic, rule,
                        "Pregnancy Risk",
                        f"{generic} in pregnancy",
                        "pregnancy",
                    ))

    return alerts


def _alert(medicine, generic, rule, category, title, trigger):
    """Small helper so we don't repeat the same dictionary three times."""
    return {
        "medicine": medicine,
        "generic": generic,
        "severity": rule["severity"],
        "category": category,
        "title": title,
        "reason": rule["reason"],
        "recommendation": rule["recommendation"],
        "triggered_by": trigger,
    }
