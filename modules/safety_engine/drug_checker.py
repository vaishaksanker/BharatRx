"""
drug_checker.py
---------------
SAFETY CHECK 1 of 5: Drug <-> Drug interaction.

Question this file answers:
"Does any NEW medicine clash with any medicine the patient is ALREADY taking?"
"""

from .utils import DRUG_INTERACTIONS, CLASS_INTERACTIONS, to_generics, find_key, classes_of


def look_up_pair(drug_a, drug_b):
    """
    Ask the dataset: is the pair (drug_a, drug_b) a known interaction?

    The dataset only stores each pair once, e.g. Warfarin -> Ibuprofen.
    But the patient might be on Ibuprofen and get prescribed Warfarin.
    So we check BOTH directions before giving up.
    """
    # Direction 1: drug_a is the outer key
    outer = find_key(DRUG_INTERACTIONS, drug_a)
    if outer:
        inner = find_key(DRUG_INTERACTIONS[outer], drug_b)
        if inner:
            return DRUG_INTERACTIONS[outer][inner]

    # Direction 2: drug_b is the outer key
    outer = find_key(DRUG_INTERACTIONS, drug_b)
    if outer:
        inner = find_key(DRUG_INTERACTIONS[outer], drug_a)
        if inner:
            return DRUG_INTERACTIONS[outer][inner]

    return None    # no known interaction


def look_up_class_pair(drug_a, drug_b):
    """
    TIER 2: no explicit pair found, so ask the CLASS rules instead.

    Example: "Aceclofenac + Acenocoumarol" is not written anywhere in
    drug_interactions.json. But Aceclofenac is an NSAID and Acenocoumarol
    is an Anticoagulant, and we have a rule saying NSAID + Anticoagulant
    is HIGH risk. So the pair is caught anyway.

    50 class rules cover roughly 1,700 drug pairs this way.
    """
    classes_a = classes_of(drug_a)
    classes_b = classes_of(drug_b)

    if not classes_a or not classes_b:
        return None          # at least one drug has no class - nothing to match

    best = None
    for rule in CLASS_INTERACTIONS["rules"]:
        ca, cb = rule["class_a"], rule["class_b"]

        # The rule matches if the drugs sit in the two named classes,
        # in either order.
        forward = ca in classes_a and cb in classes_b
        backward = cb in classes_a and ca in classes_b
        if not (forward or backward):
            continue

        hit = {
            "severity": rule["severity"],
            "reason": rule["reason"],
            "recommendation": rule["recommendation"],
            "rule": f"{ca} + {cb}",
        }
        # If several rules match, keep the most severe one.
        if best is None or _rank(hit["severity"]) < _rank(best["severity"]):
            best = hit

    return best


def _rank(severity):
    return {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(severity, 3)


def check(patient, prescription):
    """
    Compare every new medicine against every current medicine.

    patient      : dict with a "current_medicines" list
    prescription : list of newly prescribed medicine names

    Returns: a list of alert dictionaries (empty list if nothing found).
    """
    alerts = []

    current = patient.get("current_medicines", []) or []

    for new_med in prescription:
        # One prescription item may contain several generics (e.g. Combiflam)
        new_generics = to_generics(new_med)

        for old_med in current:
            old_generics = to_generics(old_med)

            # Compare every generic in the new medicine against every
            # generic in the existing medicine.
            for new_g in new_generics:
                for old_g in old_generics:

                    if new_g.lower() == old_g.lower():
                        continue      # same drug - that's the duplicate checker's job

                    # TIER 1: curated pair. Highest confidence - always wins.
                    hit = look_up_pair(old_g, new_g)
                    source = "curated"

                    # TIER 2: fall back to class-level rules.
                    if not hit:
                        hit = look_up_class_pair(old_g, new_g)
                        source = "class-rule"

                    if hit:
                        alert = {
                            "medicine": new_med,
                            "generic": new_g,
                            "severity": hit["severity"],
                            "category": "Drug-Drug Interaction",
                            "title": f"{new_g} interacts with {old_g}",
                            "reason": hit["reason"],
                            "recommendation": hit["recommendation"],
                            "triggered_by": old_med,
                            "evidence": source,
                        }
                        if source == "class-rule":
                            alert["rule"] = hit.get("rule")
                        alerts.append(alert)

    # --------------------------------------------------------------
    # Also compare the NEW medicines against EACH OTHER.
    #
    # Without this, a doctor prescribing two clashing drugs on the same
    # prescription gets no warning - the loop above only ever compared
    # new medicines against ones the patient was already taking.
    # --------------------------------------------------------------
    for i, med_a in enumerate(prescription):
        for med_b in prescription[i + 1:]:          # each pair once only
            for g_a in to_generics(med_a):
                for g_b in to_generics(med_b):

                    if g_a.lower() == g_b.lower():
                        continue                     # duplicate checker's job

                    hit = look_up_pair(g_a, g_b)
                    source = "curated"
                    if not hit:
                        hit = look_up_class_pair(g_a, g_b)
                        source = "class-rule"

                    if hit:
                        alert = {
                            "medicine": med_b,
                            "generic": g_b,
                            "severity": hit["severity"],
                            "category": "Drug-Drug Interaction",
                            "title": f"{g_b} interacts with {g_a}",
                            "reason": hit["reason"],
                            "recommendation": hit["recommendation"],
                            "triggered_by": med_a,
                            "evidence": source,
                        }
                        if source == "class-rule":
                            alert["rule"] = hit.get("rule")
                        alerts.append(alert)

    return deduplicate(alerts)


def deduplicate(alerts):
    """
    Remove identical alerts.
    Example: patient takes both Ecosprin and Aspirin - we don't want the
    same warfarin warning printed twice.
    """
    seen = set()
    out = []
    for a in alerts:
        # frozenset makes the pair order-independent, so
        # "Diclofenac interacts with Aspirin" and
        # "Aspirin interacts with Diclofenac" count as ONE alert.
        pair = frozenset([
            str(a.get("generic", "")).lower(),
            str(a.get("triggered_by", "")).lower(),
        ])
        key = (a["category"], pair)
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out
