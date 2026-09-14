"""
Urgency and clinical red-flag detection for BharatRx Pre-Consultation AI Module.

Provides deterministic, rule-based safety triage without:
- Diagnosing medical conditions
- Prescribing treatment
- Replacing professional medical evaluation

The detector identifies potentially serious symptom patterns and marks
the consultation as "urgent" for prioritized professional review.
"""

import re

from typing import List, Optional, Tuple


class UrgencyDetector:
    """
    Evaluates reported symptoms and available clinical values for
    potential red flags.

    Returns only:
    - routine
    - urgent

    Important:
    This module does not diagnose diseases.
    """

    # ==========================================================
    # RED-FLAG SYMPTOM PATTERNS
    # ==========================================================

    RED_FLAG_PATTERNS = {

        # ------------------------------------------------------
        # NEUROLOGICAL
        # ------------------------------------------------------

        "neurological": [

            "worst headache of my life",

            "worst headache ever",

            "thunderclap headache",

            "sudden severe headache",

            "loss of vision",

            "vision loss",

            "double vision",

            "facial drooping",

            "face drooping",

            "slurred speech",

            "difficulty speaking",

            "unable to speak",

            "numbness on one side",

            "weakness on one side",

            "one-sided weakness",

            "seizure",

            "loss of consciousness",

            "passed out",

            "fainted",

            "suddenly confused",

            "sudden confusion",
        ],

        # ------------------------------------------------------
        # CARDIORESPIRATORY
        # ------------------------------------------------------

        "cardiorespiratory": [

            "crushing chest pain",

            "crushing chest",

            "severe chest pressure",

            "chest pressure",

            "pain radiating to arm",

            "pain radiating to jaw",

            "shortness of breath",

            "difficulty breathing",

            "trouble breathing",

            "can't breathe",

            "cannot breathe",

            "gasping for air",

            "coughing blood",

            "coughing up blood",
        ],

        # ------------------------------------------------------
        # GASTROINTESTINAL
        # ------------------------------------------------------

        "gastrointestinal": [

            "vomiting blood",

            "blood in vomit",

            "throwing up blood",

            "black stool",

            "black stools",

            "tarry stool",

            "tarry stools",

            "blood in stool",

            "bloody stool",

            "rigid abdomen",

            "hard abdomen",

            "unbearable stomach pain",

            "unbearable abdominal pain",

            "severe abdominal pain",
        ],

        # ------------------------------------------------------
        # ALLERGIC / AIRWAY
        # ------------------------------------------------------

        "systemic_allergic": [

            "swelling of lips",

            "swollen lips",

            "swelling of tongue",

            "swollen tongue",

            "throat tightness",

            "tight throat",

            "throat closing",

            "throat feels like closing",

            "anaphylaxis",

            "widespread blistering",

            "blisters all over",
        ],

        # ------------------------------------------------------
        # FEVER / INFECTION
        # ------------------------------------------------------

        "high_fever_and_infection": [

            "stiff neck with fever",

            "fever with confusion",

            "fever and confusion",

            "unresponsive",

            "not responding",
        ],
    }

    # ==========================================================
    # NEGATION PATTERNS
    # ==========================================================

    NEGATION_PREFIXES = [

        "no",

        "not",

        "without",

        "deny",

        "denies",

        "don't have",

        "do not have",

        "didn't have",

        "did not have",

        "never had",

        "haven't had",

        "have not had",
    ]

    # ==========================================================
    # HELPER: NORMALIZE TEXT
    # ==========================================================

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalizes patient text for consistent matching.
        """

        normalized = (text or "").lower().strip()

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return normalized

    # ==========================================================
    # HELPER: CHECK PHRASE
    # ==========================================================

    @staticmethod
    def _contains_phrase(
        text: str,
        phrase: str,
    ) -> bool:
        """
        Checks for a phrase using safe word boundaries.

        Prevents accidental substring matches.
        """

        pattern = (
            r"(?<!\w)"
            + re.escape(phrase)
            + r"(?!\w)"
        )

        return bool(
            re.search(
                pattern,
                text,
            )
        )

    # ==========================================================
    # CHECK NEGATION
    # ==========================================================

    @classmethod
    def _is_negated(
        cls,
        text: str,
        pattern: str,
    ) -> bool:
        """
        Checks whether a symptom pattern appears to be explicitly
        negated.

        Examples:
        - "I have chest pain" -> False
        - "I have no chest pain" -> True
        - "No shortness of breath" -> True

        Uses a small context window before the matched symptom.
        """

        escaped_pattern = re.escape(pattern)

        match_pattern = (
            r"(?<!\w)"
            + escaped_pattern
            + r"(?!\w)"
        )

        matches = list(
            re.finditer(
                match_pattern,
                text,
            )
        )

        for match in matches:

            # Look at a limited amount of text immediately
            # before the matched symptom phrase.
            start_index = max(
                0,
                match.start() - 60,
            )

            context = text[
                start_index:match.start()
            ].strip()

            # Keep only the recent part of the context.
            context_words = context.split()

            recent_context = " ".join(
                context_words[-6:]
            )

            for prefix in cls.NEGATION_PREFIXES:

                negation_pattern = (
                    r"(?<!\w)"
                    + re.escape(prefix)
                    + r"(?!\w)"
                )

                if re.search(
                    negation_pattern,
                    recent_context,
                ):
                    return True

        return False

    # ==========================================================
    # ADD REASON SAFELY
    # ==========================================================

    @classmethod
    def _add_reason(
        cls,
        reasons: List[str],
        reason: str,
    ) -> None:
        """
        Adds a reason only if it is not already present.
        """

        if (
            reason
            and reason not in reasons
        ):

            reasons.append(reason)

    # ==========================================================
    # TEXT RED-FLAG DETECTION
    # ==========================================================

    @classmethod
    def _detect_text_red_flags(
        cls,
        text: str,
        reasons: List[str],
    ) -> None:
        """
        Detects red-flag symptom phrases in patient text.

        Explicitly negated symptom phrases are ignored.
        """

        lower_text = cls._normalize_text(
            text
        )

        if not lower_text:
            return

        for category, patterns in (
            cls.RED_FLAG_PATTERNS.items()
        ):

            category_detected = False

            for pattern in patterns:

                if not cls._contains_phrase(
                    lower_text,
                    pattern,
                ):
                    continue

                # Ignore explicitly negated symptoms.
                if cls._is_negated(
                    lower_text,
                    pattern,
                ):
                    continue

                reason = (
                    "Reported red-flag symptom requiring "
                    f"prompt professional review: {pattern}"
                )

                cls._add_reason(
                    reasons,
                    reason,
                )

                category_detected = True

                # One clear reason per category per message
                # prevents excessive duplicate reasons.
                if category_detected:
                    break

    # ==========================================================
    # NUMERIC SEVERITY DETECTION
    # ==========================================================

    @classmethod
    def _detect_high_severity(
        cls,
        severity: Optional[int],
        reasons: List[str],
    ) -> None:
        """
        Flags very high self-reported severity.

        The score is self-reported and does not represent
        a diagnosis.
        """

        if severity is None:
            return

        try:
            severity_value = int(severity)

        except (
            TypeError,
            ValueError,
        ):
            return

        if severity_value >= 9:

            reason = (
                "Very high self-reported severity score "
                f"({severity_value}/10)"
            )

            cls._add_reason(
                reasons,
                reason,
            )

    # ==========================================================
    # TEMPERATURE DETECTION
    # ==========================================================

    @classmethod
    def _detect_high_temperature(
        cls,
        temperature: Optional[float],
        reasons: List[str],
    ) -> None:
        """
        Flags significantly elevated temperature.

        The BharatRx MockConsultationEngine stores temperature
        values in Fahrenheit.

        Example:
        39.5°C -> 103.1°F
        """

        if temperature is None:
            return

        try:

            temperature_value = float(
                temperature
            )

        except (
            TypeError,
            ValueError,
        ):

            return

        if temperature_value >= 103.0:

            reason = (
                "Significantly elevated temperature reported "
                f"({temperature_value}°F)"
            )

            cls._add_reason(
                reasons,
                reason,
            )

    # ==========================================================
    # MAIN URGENCY EVALUATION
    # ==========================================================

    @classmethod
    def evaluate(
        cls,
        text: str,
        severity: Optional[int] = None,
        temperature: Optional[float] = None,
        existing_reasons: Optional[List[str]] = None,
    ) -> Tuple[
        str,
        List[str],
        Optional[str],
    ]:
        """
        Evaluates the latest patient message and available
        clinical information.

        Parameters:
        ----------
        text:
            Latest patient message.

        severity:
            Self-reported severity score.

        temperature:
            Stored temperature value in Fahrenheit.

        existing_reasons:
            Previously identified urgency reasons.
            These are preserved so an already urgent consultation
            cannot accidentally be downgraded.

        Returns:
        --------
        urgency:
            "routine" or "urgent"

        reasons:
            List of identified urgency reasons.

        escalation_message:
            Safe patient guidance when urgent.
        """

        # ------------------------------------------------------
        # PRESERVE EXISTING REASONS
        # ------------------------------------------------------

        reasons = []

        for reason in existing_reasons or []:

            cls._add_reason(
                reasons,
                reason,
            )

        # ------------------------------------------------------
        # DETECT TEXT RED FLAGS
        # ------------------------------------------------------

        cls._detect_text_red_flags(
            text,
            reasons,
        )

        # ------------------------------------------------------
        # DETECT HIGH SEVERITY
        # ------------------------------------------------------

        cls._detect_high_severity(
            severity,
            reasons,
        )

        # ------------------------------------------------------
        # DETECT HIGH TEMPERATURE
        # ------------------------------------------------------

        cls._detect_high_temperature(
            temperature,
            reasons,
        )

        # ------------------------------------------------------
        # DETERMINE URGENCY
        # ------------------------------------------------------

        urgency = (
            "urgent"
            if reasons
            else "routine"
        )

        # ------------------------------------------------------
        # ESCALATION MESSAGE
        # ------------------------------------------------------

        escalation_message = None

        if urgency == "urgent":

            escalation_message = (
                "Some of the information you shared may require "
                "prompt medical attention. Please seek evaluation "
                "from a qualified healthcare professional or an "
                "appropriate healthcare facility as soon as possible."
            )

        return (
            urgency,
            reasons,
            escalation_message,
        )