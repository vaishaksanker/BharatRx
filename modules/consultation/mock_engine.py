"""
Mock Consultation Engine for BharatRx AI Pre-Consultation System.

Provides deterministic clinical question flows and rule-based entity/slot
extraction when Gemini is unavailable, offline, or force-disabled.

Clinical Flow Rules:
- Supports 4 complaint categories: Headache, Fever, Stomach Pain, Skin Rash, plus General.
- Flow progressions are 4 to 5 steps, asking location/character, duration/onset, severity,
  associated symptoms, and medical background.
- Deterministic extraction captures symptoms, durations, severities, temperatures,
  conditions, medications (with dosages), and allergies.
- Supports explicit negative answers ("none", "no", "nothing else", "NKDA") without inventing data.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


class MockConsultationEngine:
    """Deterministic, rule-based clinical consultation intake engine."""

    # -------------------------------------------------------------------------
    # Clinical Question Flow Definitions (Grouped by clinical concern)
    # -------------------------------------------------------------------------
    FLOW_DEFINITIONS: Dict[str, List[Dict[str, Any]]] = {
        "headache": [
            {
                "step": "location_and_character",
                "question": "Where exactly is the headache located (e.g., forehead, temples, one side), and how does it feel (throbbing, dull, or sharp)?",
                "keys": ["location", "character"],
            },
            {
                "step": "duration_and_onset",
                "question": "How long have you had this headache, and did it start suddenly or gradually?",
                "keys": ["duration", "onset"],
            },
            {
                "step": "severity_and_progression",
                "question": "On a scale of 1 to 10, how severe is the pain, and has it been getting worse?",
                "keys": ["severity", "severity_addressed"],
            },
            {
                "step": "associated_symptoms",
                "question": "Are you experiencing any other symptoms such as nausea, sensitivity to light, or neck stiffness?",
                "keys": ["associated_symptoms", "associated_symptoms_addressed"],
            },
            {
                "step": "medical_context",
                "question": "Do you have any existing medical conditions (like high blood pressure), known allergies, or active medications you are taking?",
                "keys": ["conditions_addressed", "medications_addressed", "allergies_addressed"],
            },
        ],
        "fever": [
            {
                "step": "duration_and_temp",
                "question": "How many days have you had the fever, and have you measured your temperature?",
                "keys": ["duration", "temperature", "duration_addressed"],
            },
            {
                "step": "pattern_and_severity",
                "question": "Does the fever come and go, and are you having chills, shivering, or body aches?",
                "keys": ["character", "severity", "severity_addressed"],
            },
            {
                "step": "associated_symptoms",
                "question": "Do you have any cough, sore throat, vomiting, loose motions, or pain while passing urine?",
                "keys": ["associated_symptoms", "associated_symptoms_addressed"],
            },
            {
                "step": "medical_context",
                "question": "Do you have any medical conditions, current medications (like paracetamol), or known allergies?",
                "keys": ["conditions_addressed", "medications_addressed", "allergies_addressed"],
            },
        ],
        "stomach_pain": [
            {
                "step": "location_and_character",
                "question": "Where in your abdomen is the pain located (e.g., upper belly, lower abdomen, around the navel), and is it cramping, dull, or sharp?",
                "keys": ["location", "character"],
            },
            {
                "step": "duration_and_severity",
                "question": "How long have you had this pain, and how severe is it on a scale from 1 to 10?",
                "keys": ["duration", "severity", "severity_addressed"],
            },
            {
                "step": "associated_symptoms",
                "question": "Have you experienced nausea, vomiting, fever, loose motions, or acidity/bloating?",
                "keys": ["associated_symptoms", "associated_symptoms_addressed"],
            },
            {
                "step": "medical_context",
                "question": "Do you have any history of ulcers or acidity, and are you taking any regular medications or have drug allergies?",
                "keys": ["conditions_addressed", "medications_addressed", "allergies_addressed"],
            },
        ],
        "skin_rash": [
            {
                "step": "location_and_appearance",
                "question": "Where on your body did the rash appear, and what does it look like (e.g., red spots, raised bumps, flat patches)?",
                "keys": ["location", "appearance"],
            },
            {
                "step": "duration_and_sensation",
                "question": "How many days has the rash been present, and is it itchy, painful, or warm to touch?",
                "keys": ["duration", "sensation", "duration_addressed"],
            },
            {
                "step": "associated_symptoms",
                "question": "Do you have any accompanying fever, joint pain, or swelling of the face/lips?",
                "keys": ["associated_symptoms", "associated_symptoms_addressed"],
            },
            {
                "step": "medical_context",
                "question": "Have you recently started any new medications or foods, and do you have any known allergies or skin conditions?",
                "keys": ["conditions_addressed", "medications_addressed", "allergies_addressed"],
            },
        ],
        "general": [
            {
                "step": "duration_and_onset",
                "question": "How long have you been experiencing these symptoms, and did they start suddenly or gradually?",
                "keys": ["duration", "onset", "duration_addressed"],
            },
            {
                "step": "severity_and_progression",
                "question": "On a scale from 1 to 10, how severe is your discomfort, and has it been getting worse or better?",
                "keys": ["severity", "severity_addressed"],
            },
            {
                "step": "associated_symptoms",
                "question": "Are you having any other symptoms, such as fever, nausea, fatigue, or body aches?",
                "keys": ["associated_symptoms", "associated_symptoms_addressed"],
            },
            {
                "step": "medical_context",
                "question": "Do you have any chronic medical conditions, regular medications, or known drug allergies?",
                "keys": ["conditions_addressed", "medications_addressed", "allergies_addressed"],
            },
        ],
    }

    # -------------------------------------------------------------------------
    # Classification Helper
    # -------------------------------------------------------------------------
    @classmethod
    def detect_flow_category(cls, text: str) -> str:
        """Classifies the patient's concern into one of the 4 clinical categories or general."""
        lower = (text or "").lower()

        # Headache
        if any(w in lower for w in ["headache", "head ache", "head pain", "migraine", "head throbbing", "temple pain", "front head"]):
            return "headache"

        # Fever
        if any(w in lower for w in ["fever", "temperature", "chills", "feverish", "high temp", "hot body", "pyrexia"]):
            return "fever"

        # Stomach pain
        if any(w in lower for w in [
            "stomach", "abdomen", "abdominal", "belly", "tummy", "cramp", "gastric",
            "loose motion", "diarrhea", "vomiting", "nausea", "acidity", "gut",
        ]):
            return "stomach_pain"

        # Skin rash
        if any(w in lower for w in [
            "rash", "skin", "itching", "itch", "bumps", "spots", "hives", "redness",
            "blister", "scaly", "eruption", "boil",
        ]):
            return "skin_rash"

        return "general"

    # -------------------------------------------------------------------------
    # Question Flow Engine
    # -------------------------------------------------------------------------
    @classmethod
    def get_next_question(
        cls,
        flow_category: str,
        asked_step_keys: List[str],
        slots: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Retrieves the next appropriate clinical question.

        Returns:
            (next_question, step_id, is_complete)
        """
        slots = slots or {}
        category = flow_category if flow_category in cls.FLOW_DEFINITIONS else "general"
        steps = cls.FLOW_DEFINITIONS[category]

        for step_def in steps:
            step_id = step_def["step"]
            if step_id in asked_step_keys:
                continue

            # Check if all keys for this step are already addressed
            keys = step_def.get("keys", [])
            all_keys_present = True
            for k in keys:
                if not cls._is_field_addressed(k, slots):
                    all_keys_present = False
                    break

            if all_keys_present and keys:
                continue

            return step_def["question"], step_id, False

        # If all steps asked or addressed, intake flow is complete
        return None, "completed", True

    @staticmethod
    def _is_field_addressed(field_name: str, slots: Dict[str, Any]) -> bool:
        """Checks whether a slot or addressed flag has been satisfied."""
        if field_name == "location":
            return bool(slots.get("location"))
        if field_name == "character":
            return bool(slots.get("character"))
        if field_name == "duration":
            return bool(slots.get("duration") and slots.get("duration") != "Not provided")
        if field_name == "duration_addressed":
            return bool(slots.get("duration_addressed") or (slots.get("duration") and slots.get("duration") != "Not provided"))
        if field_name == "onset":
            return bool(slots.get("onset"))
        if field_name == "severity":
            return bool(slots.get("severity") is not None or slots.get("severity_addressed"))
        if field_name == "temperature":
            return bool(slots.get("temperature") is not None or slots.get("temperature_addressed"))
        if field_name == "associated_symptoms":
            return bool(slots.get("associated_symptoms") or slots.get("associated_symptoms_addressed"))
        if field_name in ("conditions", "medical_history"):
            return bool(slots.get("conditions") or slots.get("conditions_addressed"))
        if field_name in ("medications", "current_medications"):
            return bool(slots.get("current_medications") or slots.get("medications_addressed"))
        if field_name == "allergies":
            return bool(slots.get("allergies") or slots.get("allergies_addressed"))
        if field_name == "appearance":
            return bool(slots.get("appearance"))
        if field_name == "sensation":
            return bool(slots.get("sensation"))
        if field_name == "progression":
            return bool(slots.get("progression"))
        if field_name == "chills":
            return bool(slots.get("chills"))
        if field_name == "triggers":
            return bool(slots.get("triggers"))
        return False

    @classmethod
    def extract_slots_from_text(
        cls,
        text: str,
        existing_slots: Dict[str, Any],
        expected_field: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Heuristically extracts key clinical slots from patient answers.
        Preserves existing data, recognizes explicit negative answers, and uses
        expected_field context when available.
        """
        slots = dict(existing_slots)
        lower = (text or "").lower().strip()
        if not lower:
            return slots

        # ------------------------------------------------------
        # 1. Chief complaint
        # ------------------------------------------------------
        if not slots.get("chief_complaint") or slots.get("chief_complaint") == "Not provided":
            cat = cls.detect_flow_category(lower)
            mapping = {
                "headache": "Headache",
                "fever": "Fever",
                "stomach_pain": "Stomach pain",
                "skin_rash": "Skin rash",
            }
            if cat in mapping:
                slots["chief_complaint"] = mapping[cat]

        # ------------------------------------------------------
        # 2. Location
        # ------------------------------------------------------
        if not slots.get("location"):
            location_groups = [
                ("forehead", ["forehead"]),
                ("temples", ["temples", "temple"]),
                ("back of head", ["back of head"]),
                ("top of head", ["top of head"]),
                ("one side", ["left side", "right side", "one side"]),
                ("upper belly", ["upper belly", "upper stomach", "upper abdomen"]),
                ("lower abdomen", ["lower belly", "lower stomach", "lower abdomen", "lower right", "lower left"]),
                ("around navel", ["around the navel", "navel"]),
                ("chest", ["chest"]),
                ("back", ["back"]),
                ("arms", ["arm", "arms", "forearm", "forearms"]),
                ("legs", ["leg", "legs"]),
                ("neck", ["neck"]),
                ("throat", ["throat"]),
            ]
            found_locs = []
            for formal, triggers in location_groups:
                if any(t in lower for t in triggers) and formal not in found_locs:
                    found_locs.append(formal)
            if found_locs:
                slots["location"] = ", ".join(found_locs)

        # ------------------------------------------------------
        # 3. Pain Character / Onset / Appearance / Sensation
        # ------------------------------------------------------
        if not slots.get("character"):
            chars = ["throbbing", "dull", "sharp", "burning", "cramping", "constant", "intermittent", "pulsating", "aching"]
            for c in chars:
                if re.search(rf"\b{re.escape(c)}\b", lower):
                    slots["character"] = c
                    break

        if not slots.get("onset"):
            if any(p in lower for p in ["sudden", "suddenly", "all of a sudden"]):
                slots["onset"] = "sudden"
            elif any(p in lower for p in ["gradual", "gradually", "slowly", "over time"]):
                slots["onset"] = "gradual"

        if not slots.get("appearance"):
            app_terms = ["red", "bumpy", "flat", "blistering", "scaly", "swollen", "spots", "bumps", "hives"]
            found_app = [t for t in app_terms if re.search(rf"\b{re.escape(t)}\b", lower)]
            if found_app:
                slots["appearance"] = ", ".join(found_app)

        if not slots.get("sensation"):
            sens_terms = ["itchy", "itching", "painful", "warm", "burning", "stinging"]
            found_sens = [t for t in sens_terms if re.search(rf"\b{re.escape(t)}\b", lower)]
            if found_sens:
                slots["sensation"] = ", ".join(found_sens)

        # ------------------------------------------------------
        # 4. Severity (1 to 10)
        # ------------------------------------------------------
        if slots.get("severity") is None:
            sev_match = re.search(r"\b(10|[1-9])\s*(?:out of 10|\/10|\/ten|on 10|on a scale of 10)\b", lower)
            if not sev_match:
                sev_match = re.search(r"(?:severity|pain|scale|level|rate)\s*(?:is|of|at|around)?\s*(10|[1-9])\b", lower)
            if not sev_match and expected_field in ("severity", "severity_and_progression", "pattern_and_severity", "duration_and_severity", "severity_score"):
                sev_match = re.fullmatch(r"\s*(?:it is|it's|its|about|around|approx|maybe)?\s*(10|[1-9])[\.\!]?\s*", lower)

            if sev_match:
                try:
                    slots["severity"] = int(sev_match.group(1))
                    slots["severity_addressed"] = True
                except (ValueError, IndexError):
                    pass

        if slots.get("severity") is not None:
            slots["severity_addressed"] = True
        elif re.search(r"\b(?:don't know|not sure|unknown|can't rate|cannot rate)\s+(?:severity|scale|level)\b", lower):
            slots["severity_addressed"] = True

        # ------------------------------------------------------
        # 5. Duration
        # ------------------------------------------------------
        if not slots.get("duration") or slots["duration"] == "Not provided":
            dur_match = re.search(
                r"\b((?:since\s+\w+|\d+\s*(?:day|days|hour|hours|week|weeks|month|months|year|years)))\b",
                lower,
            )
            if not dur_match:
                dur_match = re.search(
                    r"\b((?:one|two|three|four|five|six|seven|eight|nine|ten|a few|couple of)\s*(?:day|days|hour|hours|week|weeks|month|months|year|years))\b",
                    lower,
                )
            if dur_match:
                slots["duration"] = dur_match.group(1).strip()
                slots["duration_addressed"] = True
            elif "yesterday" in lower:
                slots["duration"] = "1 day"
                slots["duration_addressed"] = True
            elif "today" in lower:
                slots["duration"] = "today"
                slots["duration_addressed"] = True
            elif expected_field in ("duration", "duration_and_onset", "duration_and_temp", "duration_and_severity", "duration_and_sensation"):
                if re.search(r"\b(?:don't know|not sure|unknown|can't tell)\s+(?:how long|duration|since when)\b", lower):
                    slots["duration_addressed"] = True
                elif len(lower.split()) <= 4 and any(w in lower for w in ["day", "days", "hour", "hours", "week", "weeks", "since", "ago"]):
                    slots["duration"] = text.strip()
                    slots["duration_addressed"] = True

        if slots.get("duration") and slots["duration"] != "Not provided":
            slots["duration_addressed"] = True

        # ------------------------------------------------------
        # 6. Temperature
        # ------------------------------------------------------
        if slots.get("temperature") is None:
            temp_match = re.search(r"\b(9[5-9](?:\.\d+)?|10[0-6](?:\.\d+)?)\s*(?:°?\s*f|degrees|f|fahrenheit)?\b", lower)
            celsius_match = re.search(r"\b(3[5-9](?:\.\d+)?|4[0-3](?:\.\d+)?)\s*(?:°?\s*c|celsius)\b", lower)

            if temp_match and ("f" in lower or "deg" in lower or "." in temp_match.group(1) or float(temp_match.group(1)) >= 97.0):
                try:
                    slots["temperature"] = float(temp_match.group(1))
                    slots["temperature_unit"] = "F"
                    slots["temperature_addressed"] = True
                except (ValueError, IndexError):
                    pass
            elif celsius_match:
                try:
                    c_val = float(celsius_match.group(1))
                    slots["temperature"] = round(c_val * 9 / 5 + 32, 1)
                    slots["temperature_unit"] = "F"
                    slots["temperature_addressed"] = True
                except (ValueError, IndexError):
                    pass

        if expected_field in ("temperature", "duration_and_temp"):
            if re.search(r"\b(?:haven't checked|have not checked|didn't check|not checked|no thermometer|don't know|not measured|haven't measured)\b", lower):
                slots["temperature_addressed"] = True

        # ------------------------------------------------------
        # 7. Chronic Conditions
        # ------------------------------------------------------
        known_conditions = [
            ("ckd", "CKD"),
            ("chronic kidney disease", "CKD"),
            ("hypertension", "Hypertension"),
            ("high blood pressure", "Hypertension"),
            ("high bp", "Hypertension"),
            ("bp", "Hypertension"),
            ("diabetes", "Diabetes Mellitus"),
            ("sugar", "Diabetes Mellitus"),
            ("asthma", "Asthma"),
            ("copd", "COPD"),
            ("heart disease", "Coronary Artery Disease"),
            ("cad", "Coronary Artery Disease"),
            ("thyroid", "Thyroid Disorder"),
            ("gerd", "GERD"),
            ("acid reflux", "GERD"),
            ("ulcer", "Peptic Ulcer Disease"),
            ("epilepsy", "Epilepsy"),
            ("arthritis", "Arthritis"),
        ]
        cond_list = list(slots.get("conditions", []))
        for key, formal_name in known_conditions:
            if re.search(rf"\b{re.escape(key)}\b", lower) and formal_name not in cond_list:
                neg_match = re.search(rf"(?:no|don't have|never had|without|deny|denies)\s+(?:\w+\s+)?{re.escape(key)}", lower)
                if not neg_match:
                    cond_list.append(formal_name)
                    slots["conditions_addressed"] = True
        slots["conditions"] = cond_list

        # ------------------------------------------------------
        # 8. Known Allergies
        # ------------------------------------------------------
        known_allergens = [
            ("penicillin", "Penicillin"),
            ("amoxicillin", "Penicillin"),
            ("sulfa", "Sulfa drugs"),
            ("sulfonamide", "Sulfa drugs"),
            ("aspirin", "Aspirin"),
            ("nsaids", "NSAIDs"),
            ("nsaid", "NSAIDs"),
            ("ibuprofen", "NSAIDs"),
            ("paracetamol", "Paracetamol"),
            ("peanuts", "Peanuts"),
            ("peanut", "Peanuts"),
            ("eggs", "Eggs"),
            ("egg", "Eggs"),
        ]
        allergy_list = list(slots.get("allergies", []))
        for key, formal_name in known_allergens:
            if re.search(rf"\b{re.escape(key)}\b", lower) and formal_name not in allergy_list:
                neg_match = re.search(rf"(?:no|not|deny|denies)\s+(?:known\s+)?allerg(?:y|ies)\s+(?:to\s+)?{re.escape(key)}", lower)
                if not neg_match:
                    is_allergy_context = bool(
                        expected_field in ("allergies", "known_allergies", "drug_allergies")
                        or re.search(rf"(?:allerg(?:y|ies|ic)|reaction|sensitive|intoleran)\s+(?:to\s+)?(?:\w+\s+){{0,3}}{re.escape(key)}", lower)
                        or re.search(rf"{re.escape(key)}\s+(?:allerg(?:y|ies|ic)|reaction)", lower)
                        or key in ("peanuts", "peanut", "eggs", "egg", "sulfa", "sulfonamide")
                    )
                    med_taking_context = bool(
                        re.search(rf"(?:taking|take|took|on|prescribed)\s+(?:\w+\s+){{0,2}}{re.escape(key)}", lower)
                        or re.search(rf"{re.escape(key)}\s*(?:\d+\s*(?:mg|g)|od|bd|tds|sos)", lower)
                    )
                    if is_allergy_context and not (med_taking_context and not re.search(r"allerg", lower)):
                        allergy_list.append(formal_name)
                        slots["allergies_addressed"] = True
        slots["allergies"] = allergy_list

        # ------------------------------------------------------
        # 9. Current Medications & Dosages
        # ------------------------------------------------------
        known_meds = [
            ("warfarin", "Warfarin", "5 mg", "OD"),
            ("metformin", "Metformin", "500 mg", "BD"),
            ("atorvastatin", "Atorvastatin", "20 mg", "OD"),
            ("amlodipine", "Amlodipine", "5 mg", "OD"),
            ("telmisartan", "Telmisartan", "40 mg", "OD"),
            ("losartan", "Losartan", "50 mg", "OD"),
            ("aspirin", "Aspirin", "75 mg", "OD"),
            ("paracetamol", "Paracetamol", "650 mg", "SOS"),
            ("dolo", "Dolo 650", "650 mg", "SOS"),
            ("ibuprofen", "Ibuprofen", "400 mg", "BD"),
            ("pantoprazole", "Pantoprazole", "40 mg", "OD"),
            ("omeprazole", "Omeprazole", "20 mg", "OD"),
        ]
        med_list = list(slots.get("current_medications", []))
        existing_med_names = [m.get("name", "").lower() if isinstance(m, dict) else str(m).lower() for m in med_list]
        for key, formal_name, default_dose, default_freq in known_meds:
            if re.search(rf"\b{re.escape(key)}\b", lower) and formal_name.lower() not in existing_med_names:
                # Avoid capturing if user says "allergic to penicillin and aspirin"
                allergy_ctx = bool(
                    re.search(rf"allerg(?:y|ic)\s+(?:to\s+)?(?:\w+\s+)*{re.escape(key)}", lower)
                    or re.search(rf"{re.escape(key)}\s+(?:allerg(?:y|ies|ic)|reaction)", lower)
                )
                if allergy_ctx:
                    continue
                if expected_field in ("allergies", "known_allergies", "drug_allergies") and not any(w in lower for w in ["taking", "take", "prescribed", "regularly", "medication", "medicine"]):
                    continue

                custom_dose = default_dose
                custom_freq = default_freq
                dose_match = re.search(rf"{re.escape(key)}\s*(\d+\s*(?:mg|mcg|g))", lower)
                if dose_match:
                    custom_dose = dose_match.group(1).strip()
                if "once a day" in lower or re.search(r"\bod\b", lower):
                    custom_freq = "OD"
                elif "twice a day" in lower or re.search(r"\bbd\b", lower):
                    custom_freq = "BD"
                elif "thrice a day" in lower or re.search(r"\btds\b", lower):
                    custom_freq = "TDS"
                elif "sos" in lower:
                    custom_freq = "SOS"

                med_list.append({
                    "name": formal_name,
                    "dose": custom_dose,
                    "frequency": custom_freq,
                })
                slots["medications_addressed"] = True
        slots["current_medications"] = med_list

        # ------------------------------------------------------
        # 10. Associated Symptoms
        # ------------------------------------------------------
        symptom_mappings = [
            (["nausea", "nauseous", "nauseated", "feeling sick", "feel sick"], "nausea"),
            (
                [
                    "light sensitivity",
                    "photophobia",
                    "bright light",
                    "bright lights",
                    "bright lights bother",
                    "lights bother",
                    "light bothers",
                    "sensitive to light",
                ],
                "light sensitivity",
            ),
            (["sound sensitivity", "phonophobia", "sensitive to sound", "loud sound", "sounds bother"], "sound sensitivity"),
            (["vomiting", "throwing up", "threw up"], "vomiting"),
            (["dizziness", "dizzy", "lightheaded"], "dizziness"),
            (["neck stiffness", "stiff neck"], "neck stiffness"),
            (["chills", "shivering"], "chills"),
            (["cough", "coughing"], "cough"),
            (["sore throat", "throat pain", "throat irritation"], "sore throat"),
            (["diarrhea", "loose motions", "watery stools"], "diarrhea"),
            (["bloating", "bloated"], "bloating"),
            (["fatigue", "tiredness", "exhausted", "tired"], "fatigue"),
            (["body ache", "body aches", "muscle ache", "muscle pain"], "body ache"),
            (["weakness", "feeling weak", "weak"], "weakness"),
            (["sweating", "night sweats"], "sweating"),
            (["loss of appetite", "no appetite", "not feeling hungry"], "loss of appetite"),
            (["itching", "itchy"], "itching"),
            (["burning", "burning sensation"], "burning"),
        ]
        assoc_list = list(slots.get("associated_symptoms", []))
        for triggers, formal_symptom in symptom_mappings:
            if formal_symptom in assoc_list:
                continue
            for trigger in triggers:
                if trigger in lower:
                    neg_pattern = rf"\b(?:no|without|denies|deny|not|don't have|do not have|haven't had|never had|zero)\s+(?:\w+\s+){{0,3}}{re.escape(trigger)}\b"
                    if not re.search(neg_pattern, lower):
                        assoc_list.append(formal_symptom)
                        slots["associated_symptoms_addressed"] = True
                        break
                    else:
                        slots["associated_symptoms_addressed"] = True
        slots["associated_symptoms"] = assoc_list

        # ------------------------------------------------------
        # 11. Explicit Negative Answer Recognition
        # ------------------------------------------------------
        # Conditions negated
        if slots.get("conditions"):
            slots["conditions_addressed"] = True
        elif (
            re.search(
                r"\b(?:no|none|never had|don't have|do not have|without|zero|not any|denies|deny)\s+(?:any\s+)?(?:known\s+)?(?:chronic\s+)?(?:past\s+)?(?:medical\s+)?(?:conditions?|history|diseases?|illnesses?|health problems?)\b",
                lower,
            )
            or re.search(r"\bno\s+(?:past\s+)?medical\s+history\b", lower)
            or re.search(r"\bno\s+(?:chronic\s+)?conditions\b", lower)
            or re.search(r"\bno\s+health\s+problems\b", lower)
            or re.search(r"\bno\s+chronic\s+illnesses\b", lower)
        ):
            slots["conditions_addressed"] = True

        # Medications negated
        if slots.get("current_medications"):
            slots["medications_addressed"] = True
        elif (
            re.search(
                r"\b(?:no|none|not taking|don't take|do not take|without|zero|not on|denies|deny)\s+(?:any\s+)?(?:regular\s+|active\s+|current\s+|other\s+)?(?:medications?|medicines?|meds|drugs|prescriptions?)\b",
                lower,
            )
            or re.search(r"\bnot\s+on\s+(?:any\s+)?(?:medications?|medicines?|meds)\b", lower)
            or re.search(r"\bno\s+(?:other\s+|regular\s+)?(?:medications?|medicines?|meds)\b", lower)
        ):
            slots["medications_addressed"] = True

        # Allergies negated
        if slots.get("allergies"):
            slots["allergies_addressed"] = True
        elif (
            re.search(
                r"\b(?:no|none|never had|don't have|do not have|without|zero|not|not any|denies|deny)\s+(?:any\s+)?(?:known\s+)?(?:drug\s+|food\s+)?(?:allergies|allergy|allergic)\b",
                lower,
            )
            or re.search(r"\bno\s+known\s+allergies\b", lower)
            or re.search(r"\bnkda\b", lower)
            or re.search(r"\bno\s+allergies\b", lower)
        ):
            slots["allergies_addressed"] = True

        # Associated symptoms negated
        if re.search(r"\b(?:no\s+other\s+symptoms?|no\s+associated\s+symptoms?|no\s+additional\s+symptoms?)\b", lower):
            slots["associated_symptoms_addressed"] = True

        # Compound negatives covering multiple categories
        compound_neg = any(
            p in lower
            for p in [
                "no conditions, no medications, no allergies",
                "no conditions, no medications, and no known allergies",
                "no medical conditions, no medications, and no known allergies",
                "no medical conditions, no medications, and no allergies",
                "no medical conditions, no medications, no allergies",
                "no medical conditions, no meds, no allergies",
                "no conditions, no meds, no allergies",
                "no diseases, no medicines, no allergies",
                "no conditions, medications, or allergies",
                "no conditions, medicines, or allergies",
                "no medical conditions, medications, or allergies",
                "no medical conditions, medicines, or allergies",
                "no conditions or medications or allergies",
            ]
        )
        if compound_neg:
            slots["conditions_addressed"] = True
            slots["medications_addressed"] = True
            slots["allergies_addressed"] = True

        # Concise standalone negative answers (e.g. "none", "no", "nothing", "nothing else")
        is_concise_none = bool(
            re.fullmatch(
                r"\s*(?:none|nothing|nothing else|none of them|none of these|none of the above|no to all|neither|no|nil|n\/a|na|nope|not applicable)[\.\!]?\s*",
                lower,
            )
        )
        if is_concise_none:
            # Context-sensitive assignment based on expected_field
            if expected_field in ("medical_context", "meds_and_history", "medical_history", "meds_and_allergies"):
                slots["conditions_addressed"] = True
                slots["medications_addressed"] = True
                slots["allergies_addressed"] = True
            elif expected_field in ("conditions", "medical_conditions", "chronic_conditions"):
                slots["conditions_addressed"] = True
            elif expected_field in ("medications", "current_medications", "active_medications"):
                slots["medications_addressed"] = True
            elif expected_field in ("allergies", "known_allergies", "drug_allergies"):
                slots["allergies_addressed"] = True
            elif expected_field in ("associated_symptoms", "symptoms"):
                slots["associated_symptoms_addressed"] = True
            elif expected_field in ("temperature", "duration_and_temp"):
                slots["temperature_addressed"] = True
            elif expected_field in ("duration",):
                slots["duration_addressed"] = True
            elif expected_field in ("severity",):
                slots["severity_addressed"] = True
            else:
                slots["conditions_addressed"] = True
                slots["medications_addressed"] = True
                slots["allergies_addressed"] = True
                slots["associated_symptoms_addressed"] = True

        return slots


    @classmethod
    def get_next_question(
        cls,
        flow_category: str,
        asked_step_keys: List[str],
        slots: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Retrieves the next appropriate clinical question.

        Returns:
            (next_question, step_id, is_complete)
        """
        slots = slots or {}
        category = flow_category if flow_category in cls.FLOW_DEFINITIONS else "general"
        steps = cls.FLOW_DEFINITIONS[category]

        for step_def in steps:
            step_id = step_def["step"]
            if step_id in asked_step_keys:
                continue

            # Check if all keys for this step are already addressed
            keys = step_def.get("keys", [])
            all_keys_present = True
            for k in keys:
                if not cls._is_field_addressed(k, slots):
                    all_keys_present = False
                    break

            if all_keys_present and keys:
                continue

            return step_def["question"], step_id, False

        # If all steps asked or addressed, intake flow is complete
        return None, "completed", True