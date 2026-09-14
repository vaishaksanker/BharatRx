"""
Gemini API integration for BharatRx Pre-Consultation AI Module.

Provides safe conversational intake and doctor-facing summary generation.

Safety boundaries:
- No diagnosis
- No prescription
- No treatment recommendations
- Collects and organizes information only
- Falls back safely when Gemini is unavailable
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


logger = logging.getLogger(__name__)


# ==========================================================
# ENVIRONMENT LOADING
# ==========================================================

def _safe_load_dotenv() -> None:
    """
    Safely loads environment variables from .env if python-dotenv
    is available.

    Never logs or exposes secret values.
    """

    try:
        from dotenv import load_dotenv

        repo_root = Path(__file__).resolve().parent.parent.parent
        root_env = repo_root / ".env"

        if root_env.is_file():

            load_dotenv(
                dotenv_path=root_env,
                override=False,
            )

        else:

            load_dotenv(
                override=False,
            )

    except Exception:

        # Mock/offline mode remains unaffected.
        pass


# ==========================================================
# GEMINI SERVICE
# ==========================================================

class GeminiService:
    """
    Interfaces with Google Gemini for BharatRx pre-consultation
    intake and doctor-facing summary generation.

    Important:
    - Does not diagnose
    - Does not prescribe
    - Does not recommend treatment
    - Returns None on failure so deterministic fallback can be used
    """

    DEFAULT_MODEL = "gemini-1.5-flash"

    BASE_URL = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models"
    )

    REQUEST_TIMEOUT = 8.0


    # ======================================================
    # INITIALIZATION
    # ======================================================

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):

        _safe_load_dotenv()

        self.api_key = (
            api_key
            or os.environ.get(
                "GEMINI_API_KEY",
                "",
            ).strip()
        )

        self.model = (
            model
            or os.environ.get(
                "GEMINI_MODEL",
                self.DEFAULT_MODEL,
            ).strip()
        )


    # ======================================================
    # AVAILABILITY
    # ======================================================

    def is_available(self) -> bool:
        """
        Returns True when a Gemini API key is configured.
        """

        return bool(self.api_key)


    # ======================================================
    # URL BUILDER
    # ======================================================

    def _get_generate_url(self) -> str:
        """
        Builds the Gemini generateContent endpoint.
        """

        return (
            f"{self.BASE_URL}/"
            f"{self.model}:generateContent"
        )


    # ======================================================
    # RESPONSE TEXT EXTRACTION
    # ======================================================

    @staticmethod
    def _extract_response_text(
        data: Dict[str, Any],
    ) -> str:
        """
        Safely extracts generated text from a Gemini API response.
        """

        try:

            candidates = data.get(
                "candidates",
                [],
            )

            if not candidates:

                return ""

            candidate = candidates[0]

            content = candidate.get(
                "content",
                {},
            )

            parts = content.get(
                "parts",
                [],
            )

            if not parts:

                return ""

            text = parts[0].get(
                "text",
                "",
            )

            return (
                text.strip()
                if isinstance(text, str)
                else ""
            )

        except (
            AttributeError,
            IndexError,
            TypeError,
        ):

            return ""


    # ======================================================
    # JSON PARSING
    # ======================================================

    @staticmethod
    def _parse_json_response(
        text: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Safely parses Gemini JSON output.

        Also handles accidental markdown code fences.
        """

        if not text:

            return None


        cleaned = text.strip()


        # Remove accidental markdown fences.

        if cleaned.startswith("```"):

            cleaned = (
                cleaned
                .replace("```json", "")
                .replace("```JSON", "")
                .replace("```", "")
                .strip()
            )


        try:

            parsed = json.loads(
                cleaned
            )

        except (
            json.JSONDecodeError,
            TypeError,
        ):

            return None


        if not isinstance(
            parsed,
            dict,
        ):

            return None


        return parsed


    # ======================================================
    # API REQUEST
    # ======================================================

    def _request_generation(
        self,
        prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Sends a generation request to Gemini.

        Returns parsed JSON dictionary or None on failure.
        """

        if not self.is_available():

            return None


        url = self._get_generate_url()


        body = {

            "contents": [

                {

                    "role": "user",

                    "parts": [

                        {
                            "text": prompt
                        }

                    ],

                }

            ],

            "generationConfig": {

                "temperature": 0.2,

                "responseMimeType":
                    "application/json",

            },

        }


        try:

            with httpx.Client(
                timeout=self.REQUEST_TIMEOUT,
            ) as client:

                response = client.post(

                    url,

                    params={
                        "key": self.api_key
                    },

                    json=body,

                )


                if response.status_code != 200:

                    logger.warning(
                        "Gemini API returned status %s.",
                        response.status_code,
                    )

                    return None


                data = response.json()


                if not isinstance(
                    data,
                    dict,
                ):

                    return None


                text_response = (
                    self._extract_response_text(
                        data
                    )
                )


                if not text_response:

                    return None


                return (
                    self._parse_json_response(
                        text_response
                    )
                )


        except (
            httpx.HTTPError,
            json.JSONDecodeError,
            ValueError,
            TypeError,
        ) as exc:

            logger.warning(
                "Gemini API request failed; "
                "falling back to deterministic engine. "
                "Error: %s",
                exc,
            )

            return None


        except Exception as exc:

            logger.exception(
                "Unexpected Gemini service error: %s",
                exc,
            )

            return None


    # ======================================================
    # GENERATE NEXT TURN
    # ======================================================

    def generate_next_turn(
        self,
        history: List[Dict[str, str]],
        slots: Dict[str, Any],
        turn_count: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Generates the next intake question and optional slot updates.

        Returns None when Gemini is unavailable or fails.
        """

        if not self.is_available():

            return None


        system_instruction = (
            "You are BharatRx AI, a clinical pre-consultation "
            "intake assistant for patients in India.\n\n"

            "YOUR ONLY ROLE:\n"
            "Collect and organize patient information before "
            "the patient sees a qualified healthcare professional.\n\n"

            "CRITICAL SAFETY BOUNDARIES:\n"
            "1. DO NOT diagnose any disease or condition.\n"
            "2. DO NOT prescribe medications.\n"
            "3. DO NOT recommend treatments, remedies, or therapies.\n"
            "4. DO NOT invent patient information.\n"
            "5. Only record information explicitly reported by "
            "the patient.\n"
            "6. Ask only 1 or 2 focused questions at a time.\n\n"

            "INFORMATION TO COLLECT WHEN RELEVANT:\n"
            "- Chief complaint\n"
            "- Location\n"
            "- Character of symptom or pain\n"
            "- Onset\n"
            "- Duration\n"
            "- Severity from 1 to 10\n"
            "- Progression\n"
            "- Associated symptoms\n"
            "- Temperature if known\n"
            "- Chronic medical conditions\n"
            "- Current medications\n"
            "- Known allergies\n\n"

            "CONVERSATION RULES:\n"
            "1. Inspect current_slots and conversation_history.\n"
            "2. Ask only for information that is still missing.\n"
            "3. Never ask again for information already provided.\n"
            "4. Explicit negative answers count as collected.\n"
            "5. If the patient says they have no conditions, "
            "medications, or allergies, record that category "
            "as addressed.\n"
            "6. If the patient answers a different question, "
            "record the useful information and continue naturally.\n"
            "7. Do not repeat questions unnecessarily.\n"
            "8. Do not complete solely because of turn count.\n"
            "9. Prefer the next missing intake field.\n\n"

            "COMPLETION RULES:\n"
            "Only mark conversation_complete true when the "
            "available intake information is reasonably collected.\n"
            "Explicit negative answers count as addressed.\n\n"

            "URGENCY RULE:\n"
            "Return urgency as 'routine'. Do not perform diagnosis. "
            "The deterministic BharatRx safety system handles "
            "red-flag detection separately.\n\n"

            "OUTPUT RULES:\n"
            "Return STRICT JSON only with exactly these keys:\n"
            "{\n"
            '  "next_question": "string",\n'
            '  "conversation_complete": false,\n'
            '  "urgency": "routine",\n'
            '  "extracted_slots": {}\n'
            "}\n\n"

            "SLOT RULES:\n"
            "- severity must be an integer from 1 to 10 or null.\n"
            "- Do not overwrite known information with empty values.\n"
            "- associated_symptoms must contain only explicitly "
            "reported symptoms.\n"
            "- conditions must contain only explicitly reported "
            "medical conditions.\n"
            "- current_medications must contain only explicitly "
            "reported medications.\n"
            "- allergies must contain only explicitly reported "
            "allergies.\n"
        )


        prompt_payload = {

            "turn_count":
                turn_count,

            "current_slots":
                slots,

            "conversation_history":
                history,

        }


        prompt = (
            f"{system_instruction}\n\n"
            "CURRENT INTAKE STATE:\n"
            f"{json.dumps(prompt_payload, indent=2, default=str)}"
        )


        parsed = (
            self._request_generation(
                prompt
            )
        )


        if not parsed:

            return None


        # --------------------------------------------------
        # VALIDATE NEXT QUESTION
        # --------------------------------------------------

        next_question = parsed.get(
            "next_question",
            "",
        )


        if not isinstance(
            next_question,
            str,
        ):

            next_question = ""


        next_question = (
            next_question.strip()
        )


        # --------------------------------------------------
        # VALIDATE COMPLETION
        # --------------------------------------------------

        conversation_complete = bool(
            parsed.get(
                "conversation_complete",
                False,
            )
        )


        # --------------------------------------------------
        # VALIDATE EXTRACTED SLOTS
        # --------------------------------------------------

        extracted_slots = parsed.get(
            "extracted_slots",
            {},
        )


        if not isinstance(
            extracted_slots,
            dict,
        ):

            extracted_slots = {}


        # --------------------------------------------------
        # VALIDATE URGENCY
        # --------------------------------------------------

        urgency = (
            parsed.get(
                "urgency",
                "routine",
            )
        )


        if urgency != "urgent":

            urgency = "routine"


        return {

            "next_question":
                next_question,

            "conversation_complete":
                conversation_complete,

            "urgency":
                urgency,

            "extracted_slots":
                extracted_slots,

        }


    # ======================================================
    # GENERATE SUMMARY
    # ======================================================

    def generate_summary(
        self,
        history: List[Dict[str, str]],
        slots: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Generates a doctor-facing summary.

        Returns None on failure so ReportGenerator can use
        deterministic fallback generation.
        """

        if not self.is_available():

            return None


        system_instruction = (
            "You are a clinical documentation assistant for BharatRx.\n\n"

            "Your purpose is to organize completed patient intake "
            "information for review by a qualified healthcare "
            "professional.\n\n"

            "CRITICAL RULES:\n"
            "1. DO NOT diagnose any disease or condition.\n"
            "2. DO NOT prescribe medication.\n"
            "3. DO NOT recommend treatment.\n"
            "4. DO NOT invent patient information.\n"
            "5. Use only information explicitly present in the "
            "clinical slots or conversation.\n"
            "6. Use neutral, descriptive language.\n\n"

            "Return STRICT JSON only with these keys:\n"
            "{\n"
            '  "patient_description": "string",\n'
            '  "ai_summary": "string",\n'
            '  "doctor_review_questions": [],\n'
            '  "associated_symptoms": []\n'
            "}\n\n"

            "RULES FOR associated_symptoms:\n"
            "- Include only distinct symptoms explicitly reported.\n"
            "- Do not invent symptoms.\n"
            "- Use concise normalized names when possible.\n"
        )


        prompt_payload = {

            "clinical_slots":
                slots,

            "conversation_history":
                history,

        }


        prompt = (
            f"{system_instruction}\n\n"
            "INTAKE INFORMATION:\n"
            f"{json.dumps(prompt_payload, indent=2, default=str)}"
        )


        parsed = (
            self._request_generation(
                prompt
            )
        )


        if not parsed:

            return None


        # --------------------------------------------------
        # VALIDATE STRING FIELDS
        # --------------------------------------------------

        patient_description = parsed.get(
            "patient_description",
            "",
        )


        ai_summary = parsed.get(
            "ai_summary",
            "",
        )


        if not isinstance(
            patient_description,
            str,
        ):

            patient_description = ""


        if not isinstance(
            ai_summary,
            str,
        ):

            ai_summary = ""


        # --------------------------------------------------
        # VALIDATE REVIEW QUESTIONS
        # --------------------------------------------------

        doctor_review_questions = parsed.get(
            "doctor_review_questions",
            [],
        )


        if not isinstance(
            doctor_review_questions,
            list,
        ):

            doctor_review_questions = []


        doctor_review_questions = [

            question.strip()

            for question
            in doctor_review_questions

            if (
                isinstance(question, str)
                and question.strip()
            )

        ]


        # --------------------------------------------------
        # NORMALIZE SYMPTOMS
        # --------------------------------------------------

        existing_symptoms = slots.get(
            "associated_symptoms",
            [],
        )


        generated_symptoms = parsed.get(
            "associated_symptoms",
            [],
        )


        if not isinstance(
            existing_symptoms,
            list,
        ):

            existing_symptoms = []


        if not isinstance(
            generated_symptoms,
            list,
        ):

            generated_symptoms = []


        symptom_mapping = {

            "nauseous":
                "nausea",

            "nauseated":
                "nausea",

            "feeling nauseous":
                "nausea",

            "feeling sick":
                "nausea",

            "photophobia":
                "light sensitivity",

            "bright light":
                "light sensitivity",

            "bright lights":
                "light sensitivity",

            "sensitive to light":
                "light sensitivity",

            "sensitivity to light":
                "light sensitivity",

        }


        normalized_symptoms = []


        # Preserve deterministic extracted symptoms first.

        for symptom in existing_symptoms:

            if not isinstance(
                symptom,
                str,
            ):

                continue


            normalized = (
                symptom.strip().lower()
            )


            if not normalized:

                continue


            normalized = (
                symptom_mapping.get(
                    normalized,
                    normalized,
                )
            )


            if normalized not in normalized_symptoms:

                normalized_symptoms.append(
                    normalized
                )


        # Add Gemini symptoms only if they are valid strings.

        for symptom in generated_symptoms:

            if not isinstance(
                symptom,
                str,
            ):

                continue


            normalized = (
                symptom.strip().lower()
            )


            if not normalized:

                continue


            normalized = (
                symptom_mapping.get(
                    normalized,
                    normalized,
                )
            )


            if normalized not in normalized_symptoms:

                normalized_symptoms.append(
                    normalized
                )


        return {

            "patient_description":
                patient_description.strip(),

            "ai_summary":
                ai_summary.strip(),

            "doctor_review_questions":
                doctor_review_questions,

            "associated_symptoms":
                normalized_symptoms,

        }