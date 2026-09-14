"""
Clinical report and unified patient profile generator
for BharatRx Pre-Consultation AI Module.

Generates:
1. ConsultationReport
2. PatientProfile

This module:
- Does not diagnose
- Does not prescribe treatment
- Generates structured clinical intake information
- Creates doctor review questions
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

from .conversation_manager import SessionState
from .schemas import (
    ConsultationReport,
    Medication,
    PatientProfile,
    UrgencyLevel,
)


class ReportGenerator:
    """
    Synthesizes consultation session data into:

    1. ConsultationReport
    2. PatientProfile
    """

    # =========================================================
    # DOCTOR REVIEW QUESTIONS
    # =========================================================

    DOCTOR_QUESTIONS_BY_CATEGORY = {

        "headache": [
            (
                "Check for focal neurological deficits, "
                "pupillary reflexes, and cranial nerve signs."
            ),
            (
                "Verify current blood pressure reading."
            ),
            (
                "Inquire about visual aura, stress triggers, "
                "and family history of migraine."
            ),
        ],

        "fever": [
            (
                "Verify temperature pattern, hydration state, "
                "and peripheral perfusion."
            ),
            (
                "Examine for focal signs of infection including "
                "respiratory, ENT, or urinary symptoms."
            ),
            (
                "Review relevant exposure history and consider "
                "appropriate evaluation based on clinical findings."
            ),
        ],

        "stomach_pain": [
            (
                "Perform abdominal examination for tenderness, "
                "guarding, or other significant findings."
            ),
            (
                "Assess relation of symptoms to food intake and "
                "ask about bowel or urinary changes."
            ),
            (
                "Review recent medication use and relevant "
                "gastrointestinal history."
            ),
        ],

        "skin_rash": [
            (
                "Inspect lesion morphology and body distribution."
            ),
            (
                "Evaluate for signs of acute allergic reaction "
                "or medication-related skin changes."
            ),
            (
                "Inquire about recent medication changes, "
                "topical exposures, or environmental triggers."
            ),
        ],

        "general": [
            (
                "Perform targeted physical examination based "
                "on the chief complaint."
            ),
            (
                "Correlate reported symptoms with chronic "
                "conditions and current medications."
            ),
            (
                "Verify relevant vital signs and assess "
                "functional impact."
            ),
        ],
    }

    # =========================================================
    # HELPER: FORMAT LIST NATURALLY
    # =========================================================

    @classmethod
    def _format_list(
        cls,
        items: List[str],
    ) -> str:
        """
        Converts a list into natural language.

        Example:

        ["forehead"]
        -> forehead

        ["forehead", "temples"]
        -> forehead and temples

        ["a", "b", "c"]
        -> a, b, and c
        """

        cleaned_items = []

        for item in items:

            if not item:
                continue

            item = str(item).strip()

            if item and item not in cleaned_items:
                cleaned_items.append(item)

        if not cleaned_items:
            return ""

        if len(cleaned_items) == 1:
            return cleaned_items[0]

        if len(cleaned_items) == 2:
            return (
                f"{cleaned_items[0]} and "
                f"{cleaned_items[1]}"
            )

        return (
            ", ".join(cleaned_items[:-1])
            + ", and "
            + cleaned_items[-1]
        )

    # =========================================================
    # HELPER: GET LOCATION TEXT
    # =========================================================

    @classmethod
    def _format_location(
        cls,
        location: Optional[str],
    ) -> str:
        """
        Cleans comma-separated location information.
        """

        if not location:
            return ""

        location_items = [
            item.strip()
            for item in location.split(",")
            if item.strip()
        ]

        # Remove singular/plural duplicates
        cleaned_locations = []

        for item in location_items:

            normalized = item.lower().rstrip("s")

            duplicate = any(
                existing.lower().rstrip("s")
                == normalized
                for existing in cleaned_locations
            )

            if not duplicate:
                cleaned_locations.append(item)

        return cls._format_list(
            cleaned_locations
        )

    # =========================================================
    # DOCTOR REVIEW QUESTIONS
    # =========================================================

    @classmethod
    def generate_doctor_review_questions(
        cls,
        flow_category: str,
        urgency: str,
        urgency_reasons: List[str],
    ) -> List[str]:
        """
        Generates targeted review questions
        for the attending doctor.
        """

        base_questions = list(
            cls.DOCTOR_QUESTIONS_BY_CATEGORY.get(
                flow_category,
                cls.DOCTOR_QUESTIONS_BY_CATEGORY[
                    "general"
                ],
            )
        )

        if (
            urgency == UrgencyLevel.URGENT.value
            and urgency_reasons
        ):

            urgent_question = (
                "Priority review: Evaluate the reported "
                f"red-flag factor ({urgency_reasons[0]})."
            )

            return (
                [urgent_question]
                + base_questions[:2]
            )

        return base_questions[:3]

    # =========================================================
    # GENERATE NARRATIVE AND SUMMARY
    # =========================================================

    @classmethod
    def generate_narrative_and_summary(
        cls,
        slots: Dict[str, Any],
        urgency: str,
        flow_category: str,
    ) -> Dict[str, str]:
        """
        Generates:

        1. Patient description
        2. Structured AI summary

        This method does NOT diagnose or prescribe.
        """

        # -----------------------------------------------------
        # EXTRACT BASIC INFORMATION
        # -----------------------------------------------------

        chief = slots.get(
            "chief_complaint",
            "Not provided",
        )

        location = slots.get(
            "location"
        )

        character = slots.get(
            "character"
        )

        duration = slots.get(
            "duration",
            "Not provided",
        )

        onset = slots.get(
            "onset"
        )

        severity = slots.get(
            "severity"
        )

        temperature = slots.get(
            "temperature"
        )

        associated_symptoms = list(
            slots.get(
                "associated_symptoms",
                [],
            )
        )

        conditions = list(
            slots.get(
                "conditions",
                [],
            )
        )

        medications = list(
            slots.get(
                "current_medications",
                [],
            )
        )

        allergies = list(
            slots.get(
                "allergies",
                [],
            )
        )

        # -----------------------------------------------------
        # CLEAN LOCATION
        # -----------------------------------------------------

        location_text = cls._format_location(
            location
        )

        # -----------------------------------------------------
        # BUILD PATIENT DESCRIPTION
        # -----------------------------------------------------

        description_parts = []

        # -----------------------------------------------------
        # BUILD PRIMARY SYMPTOM
        # -----------------------------------------------------

        symptom_words = []

        if onset:

            symptom_words.append(
                f"{onset}-onset"
            )

        if character:

            symptom_words.append(
                character
            )

        # Map category to readable symptom

        category_symptom_map = {

            "headache": "headache",

            "fever": "fever",

            "stomach_pain": "stomach pain",

            "skin_rash": "skin rash",

        }

        primary_symptom = (
            category_symptom_map.get(
                flow_category
            )
        )

        # -----------------------------------------------------
        # PRIMARY DESCRIPTION
        # -----------------------------------------------------

        if primary_symptom:

            symptom_words.append(
                primary_symptom
            )

            symptom_phrase = " ".join(
                symptom_words
            )

            first_sentence = (
                f"Patient presents with a "
                f"{symptom_phrase}"
            )

        else:

            first_sentence = (
                f"Patient presents with "
                f"{chief}"
            )

        # -----------------------------------------------------
        # LOCATION
        # -----------------------------------------------------

        if location_text:

            first_sentence += (
                f" localized to the "
                f"{location_text}"
            )

        first_sentence += "."

        description_parts.append(
            first_sentence
        )

        # -----------------------------------------------------
        # DURATION
        # -----------------------------------------------------

        if (
            duration
            and duration != "Not provided"
        ):

            description_parts.append(
                f"Symptoms have been present "
                f"{duration}."
            )

        # -----------------------------------------------------
        # SEVERITY
        # -----------------------------------------------------

        if severity is not None:

            description_parts.append(
                f"Reported severity is "
                f"{severity}/10."
            )

        # -----------------------------------------------------
        # TEMPERATURE
        # -----------------------------------------------------

        if temperature is not None:

            description_parts.append(
                f"Reported temperature is "
                f"{temperature}°F."
            )

        # -----------------------------------------------------
        # ASSOCIATED SYMPTOMS
        # -----------------------------------------------------

        if associated_symptoms:

            symptoms_text = cls._format_list(
                associated_symptoms
            )

            description_parts.append(
                f"Associated symptoms include "
                f"{symptoms_text}."
            )

        # -----------------------------------------------------
        # CONDITIONS
        # -----------------------------------------------------

        if conditions:

            conditions_text = cls._format_list(
                conditions
            )

            description_parts.append(
                f"Relevant chronic conditions include "
                f"{conditions_text}."
            )

        elif slots.get(
            "conditions_addressed"
        ):

            description_parts.append(
                "Patient reports no chronic "
                "medical conditions."
            )

        # -----------------------------------------------------
        # MEDICATIONS
        # -----------------------------------------------------

        medication_names = []

        for medication in medications:

            if isinstance(
                medication,
                dict,
            ):

                name = medication.get(
                    "name"
                )

                if (
                    name
                    and name != "Not provided"
                ):

                    medication_names.append(
                        name
                    )

            elif isinstance(
                medication,
                str,
            ):

                if medication.strip():

                    medication_names.append(
                        medication.strip()
                    )

        if medication_names:

            medications_text = cls._format_list(
                medication_names
            )

            description_parts.append(
                f"Current medications include "
                f"{medications_text}."
            )

        elif slots.get(
            "medications_addressed"
        ):

            description_parts.append(
                "Patient reports no regular medications."
            )

        # -----------------------------------------------------
        # ALLERGIES
        # -----------------------------------------------------

        if allergies:

            allergies_text = cls._format_list(
                allergies
            )

            description_parts.append(
                f"Known allergies include "
                f"{allergies_text}."
            )

        elif slots.get(
            "allergies_addressed"
        ):

            description_parts.append(
                "Patient reports no known allergies."
            )

        # -----------------------------------------------------
        # FINAL PATIENT DESCRIPTION
        # -----------------------------------------------------

        patient_description = " ".join(
            description_parts
        )

        # =====================================================
        # BUILD AI SUMMARY
        # =====================================================

        # -----------------------------------------------------
        # SEVERITY
        # -----------------------------------------------------

        if severity is not None:

            severity_text = (
                f"{severity}/10"
            )

        else:

            severity_text = (
                "Not provided"
            )

        # -----------------------------------------------------
        # TEMPERATURE
        # -----------------------------------------------------

        if temperature is not None:

            temperature_text = (
                f"{temperature}°F"
            )

        else:

            temperature_text = (
                "Not recorded"
            )

        # -----------------------------------------------------
        # CONDITIONS
        # -----------------------------------------------------

        if conditions:

            conditions_summary = cls._format_list(
                conditions
            )

        elif slots.get(
            "conditions_addressed"
        ):

            conditions_summary = (
                "None reported"
            )

        else:

            conditions_summary = (
                "Not provided"
            )

        # -----------------------------------------------------
        # MEDICATIONS
        # -----------------------------------------------------

        if medication_names:

            medications_summary = (
                cls._format_list(
                    medication_names
                )
            )

        elif slots.get(
            "medications_addressed"
        ):

            medications_summary = (
                "None reported"
            )

        else:

            medications_summary = (
                "Not provided"
            )

        # -----------------------------------------------------
        # ALLERGIES
        # -----------------------------------------------------

        if allergies:

            allergies_summary = (
                cls._format_list(
                    allergies
                )
            )

        elif slots.get(
            "allergies_addressed"
        ):

            allergies_summary = (
                "No known drug allergies reported"
            )

        else:

            allergies_summary = (
                "Not provided"
            )

        # -----------------------------------------------------
        # ASSOCIATED SYMPTOMS
        # -----------------------------------------------------

        if associated_symptoms:

            associated_summary = (
                cls._format_list(
                    associated_symptoms
                )
            )

        else:

            associated_summary = (
                "None reported"
            )

        # -----------------------------------------------------
        # LOCATION
        # -----------------------------------------------------

        if location_text:

            location_summary = (
                location_text
            )

        else:

            location_summary = (
                "Not provided"
            )

        # -----------------------------------------------------
        # CHARACTER
        # -----------------------------------------------------

        if character:

            character_summary = (
                character
            )

        else:

            character_summary = (
                "Not provided"
            )

        # -----------------------------------------------------
        # ONSET
        # -----------------------------------------------------

        if onset:

            onset_summary = onset

        else:

            onset_summary = (
                "Not provided"
            )

        # -----------------------------------------------------
        # AI SUMMARY
        # -----------------------------------------------------

        ai_summary = (

            "Pre-Consultation Clinical Intake:\n"

            f"- Chief Complaint: {chief}\n"

            f"- Location: {location_summary}\n"

            f"- Symptom Character: "
            f"{character_summary}\n"

            f"- Onset: {onset_summary}\n"

            f"- Duration: {duration}\n"

            f"- Severity: {severity_text}\n"

            f"- Temperature: "
            f"{temperature_text}\n"

            f"- Associated Symptoms: "
            f"{associated_summary}\n"

            f"- Chronic Conditions: "
            f"{conditions_summary}\n"

            f"- Active Medications: "
            f"{medications_summary}\n"

            f"- Allergies: "
            f"{allergies_summary}\n"

            f"- Triage Urgency: "
            f"{urgency.upper()}"
        )

        return {

            "patient_description":
                patient_description,

            "ai_summary":
                ai_summary,

        }

    # =========================================================
    # GENERATE CONSULTATION REPORT
    # =========================================================

    @classmethod
    def generate_report(
        cls,
        session: SessionState,
        llm_summary: Optional[
            Dict[str, Any]
        ] = None,
    ) -> ConsultationReport:
        """
        Builds the standardized ConsultationReport.
        """

        slots = session.slots

        report_id = (
            f"R_{session.patient_id}_"
            f"{int(time.time())}"
        )

        # -----------------------------------------------------
        # DOCTOR QUESTIONS
        # -----------------------------------------------------

        doctor_questions = (
            cls.generate_doctor_review_questions(
                flow_category=session.flow_category,
                urgency=session.urgency,
                urgency_reasons=session.urgency_reasons,
            )
        )

        # -----------------------------------------------------
        # AI / LLM SUMMARY
        # -----------------------------------------------------

        if (
            llm_summary
            and llm_summary.get("ai_summary")
        ):

            patient_description = (
                llm_summary.get(
                    "patient_description",
                    "Not provided",
                )
            )

            ai_summary = (
                llm_summary.get(
                    "ai_summary",
                    "Not provided",
                )
            )

            if llm_summary.get(
                "doctor_review_questions"
            ):

                doctor_questions = (
                    llm_summary[
                        "doctor_review_questions"
                    ][:3]
                )

        else:

            narratives = (
                cls.generate_narrative_and_summary(
                    slots=slots,
                    urgency=session.urgency,
                    flow_category=session.flow_category,
                )
            )

            patient_description = (
                narratives[
                    "patient_description"
                ]
            )

            ai_summary = (
                narratives[
                    "ai_summary"
                ]
            )

        # -----------------------------------------------------
        # FORMAT MEDICATIONS
        # -----------------------------------------------------

        current_meds = []

        for medication in slots.get(
            "current_medications",
            [],
        ):

            if isinstance(
                medication,
                dict,
            ):

                current_meds.append(
                    {
                        "name":
                            medication.get(
                                "name",
                                "Not provided",
                            ),

                        "dose":
                            medication.get(
                                "dose",
                                "Not provided",
                            ),

                        "frequency":
                            medication.get(
                                "frequency",
                                "Not provided",
                            ),
                    }
                )

            elif isinstance(
                medication,
                str,
            ):

                current_meds.append(
                    {
                        "name": medication,

                        "dose":
                            "Not provided",

                        "frequency":
                            "Not provided",
                    }
                )

        # -----------------------------------------------------
        # BUILD REPORT
        # -----------------------------------------------------

        return ConsultationReport(

            report_id=report_id,

            patient_id=session.patient_id,

            chief_complaint=slots.get(
                "chief_complaint",
                "Not provided",
            ),

            duration=slots.get(
                "duration",
                "Not provided",
            ),

            severity=slots.get(
                "severity"
            ),

            temperature=slots.get(
                "temperature"
            ),

            associated_symptoms=list(
                slots.get(
                    "associated_symptoms",
                    [],
                )
            ),

            medical_history=list(
                slots.get(
                    "conditions",
                    [],
                )
            ),

            current_medications=current_meds,

            allergies=list(
                slots.get(
                    "allergies",
                    [],
                )
            ),

            uploaded_image=(
                session.uploaded_image
                or "Not provided"
            ),

            patient_description=
                patient_description,

            ai_summary=
                ai_summary,

            doctor_review_questions=
                doctor_questions,

            urgency=
                session.urgency,

            created_at=
                datetime.now(
                    timezone.utc
                ).isoformat(),

        )

    # =========================================================
    # GENERATE PATIENT PROFILE
    # =========================================================

    @classmethod
    def generate_patient_profile(
        cls,
        session: SessionState,
    ) -> PatientProfile:
        """
        Builds the unified PatientProfile.

        Used by downstream systems.
        """

        slots = session.slots

        medications = []

        # -----------------------------------------------------
        # FORMAT MEDICATIONS
        # -----------------------------------------------------

        for medication in slots.get(
            "current_medications",
            [],
        ):

            if isinstance(
                medication,
                dict,
            ):

                medications.append(

                    Medication(

                        name=
                            medication.get(
                                "name",
                                "Not provided",
                            ),

                        dose=
                            medication.get(
                                "dose",
                                "Not provided",
                            ),

                        frequency=
                            medication.get(
                                "frequency",
                                "Not provided",
                            ),

                    )

                )

            elif isinstance(
                medication,
                str,
            ):

                medications.append(

                    Medication(

                        name=medication,

                        dose=
                            "Not provided",

                        frequency=
                            "Not provided",

                    )

                )

        # -----------------------------------------------------
        # BUILD PROFILE
        # -----------------------------------------------------

        return PatientProfile(

            patient_id=
                session.patient_id,

            name=
                slots.get(
                    "name",
                    "Not provided",
                ),

            age=
                slots.get(
                    "age"
                ),

            sex=
                slots.get(
                    "sex",
                    "Not provided",
                ),

            conditions=list(
                slots.get(
                    "conditions",
                    [],
                )
            ),

            allergies=list(
                slots.get(
                    "allergies",
                    [],
                )
            ),

            current_medications=
                medications,

        )