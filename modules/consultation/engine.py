"""
Main ConsultationEngine coordinator for BharatRx Pre-Consultation AI Module.

Integrates:
- Session management
- Gemini AI service
- Deterministic mock fallback
- Red-flag urgency detection
- Clinical report generation

Safety principles:
- Does not diagnose
- Does not prescribe treatment
- Uses deterministic urgency detection
- Preserves consultation information
- Avoids unnecessary repeated questions
"""

import logging
import time

from typing import Any, Dict, List, Optional, Tuple

from .conversation_manager import (
    ConversationManager,
    SessionState,
)

from .gemini_service import GeminiService
from .mock_engine import MockConsultationEngine
from .report_generator import ReportGenerator
from .schemas import ConsultationMessageResponse
from .urgency_detector import UrgencyDetector


logger = logging.getLogger(__name__)


class ConsultationEngine:
    """
    Main coordinator for BharatRx AI Pre-Consultation services.

    Exposes:
    - start_consultation
    - process_message
    - attach_image_reference
    - get_consultation_report
    - get_patient_profile
    """

    MAX_SAFETY_TURNS = 8


    GREETING_MESSAGE = (
        "Hi! I'm BharatRx, your AI pre-consultation assistant. "
        "I'll ask you a few questions to help organize your symptoms "
        "and medical information for your doctor. "
        "What health concern or symptom are you experiencing today?"
    )


    COMPLETION_MESSAGE = (
        "Thank you for sharing these details. "
        "I have gathered the available intake information "
        "for your doctor. Your pre-consultation summary "
        "has been prepared for review."
    )


    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        force_mock: bool = False,
    ):

        self.manager = ConversationManager()

        self.mock_engine = MockConsultationEngine()

        self.gemini = (
            None
            if force_mock
            else GeminiService(
                api_key=gemini_api_key
            )
        )

        self.force_mock = force_mock


    # ======================================================
    # INTAKE VALIDATION
    # ======================================================

    def _get_missing_intake_fields(
        self,
        session: SessionState,
    ) -> List[str]:
        """
        Determines which essential intake categories
        have not yet been addressed.
        """

        slots = session.slots

        missing = []


        # --------------------------------------------------
        # DURATION
        # --------------------------------------------------

        has_duration = (
            bool(
                slots.get("duration")
                and slots.get("duration") != "Not provided"
            )
            or bool(
                slots.get("duration_addressed")
            )
        )

        if not has_duration:
            missing.append(
                "duration"
            )


        # --------------------------------------------------
        # SEVERITY
        # --------------------------------------------------

        has_severity = (
            slots.get("severity") is not None
            or bool(
                slots.get("severity_addressed")
            )
        )

        if not has_severity:
            missing.append(
                "severity"
            )


        # --------------------------------------------------
        # CONDITIONS
        # --------------------------------------------------

        has_conditions = (
            bool(
                slots.get("conditions")
            )
            or bool(
                slots.get("conditions_addressed")
            )
        )

        if not has_conditions:
            missing.append(
                "conditions"
            )


        # --------------------------------------------------
        # MEDICATIONS
        # --------------------------------------------------

        has_medications = (
            bool(
                slots.get("current_medications")
            )
            or bool(
                slots.get("medications_addressed")
            )
        )

        if not has_medications:
            missing.append(
                "medications"
            )


        # --------------------------------------------------
        # ALLERGIES
        # --------------------------------------------------

        has_allergies = (
            bool(
                slots.get("allergies")
            )
            or bool(
                slots.get("allergies_addressed")
            )
        )

        if not has_allergies:
            missing.append(
                "allergies"
            )


        return missing


    def _is_intake_sufficient(
        self,
        session: SessionState,
    ) -> bool:
        """
        Returns True when all essential intake
        categories have been addressed.
        """

        return (
            len(
                self._get_missing_intake_fields(
                    session
                )
            )
            == 0
        )


    # ======================================================
    # FOLLOW-UP GENERATION
    # ======================================================

    def _generate_guardrail_followup(
        self,
        missing_fields: List[str],
    ) -> Tuple[str, str]:
        """
        Generates a focused follow-up question and corresponding step_id
        for missing essential intake information.
        """

        symptom_inquiries = []


        if (
            "duration" in missing_fields
            and "severity" in missing_fields
        ):

            symptom_inquiries.append(
                "how long you have had these symptoms "
                "and their severity on a scale of 1 to 10"
            )

        elif "duration" in missing_fields:

            symptom_inquiries.append(
                "how long you have been experiencing "
                "these symptoms"
            )

        elif "severity" in missing_fields:

            symptom_inquiries.append(
                "how severe your discomfort is "
                "on a scale of 1 to 10"
            )


        medical_inquiries = []


        if "conditions" in missing_fields:

            medical_inquiries.append(
                "chronic medical conditions"
            )


        if "medications" in missing_fields:

            medical_inquiries.append(
                "current medications"
            )


        if "allergies" in missing_fields:

            medical_inquiries.append(
                "known allergies"
            )


        parts = []


        if symptom_inquiries:

            parts.append(
                " and ".join(
                    symptom_inquiries
                )
            )


        if medical_inquiries:

            parts.append(
                "whether you have any "
                f"{', '.join(medical_inquiries)} "
                "(you can reply 'none' if not applicable)"
            )


        if parts:

            question = (
                "Before we conclude your pre-consultation, "
                "could you please clarify "
                f"{' as well as '.join(parts)}?"
            )

        else:

            question = (
                "Before we conclude your pre-consultation, "
                "do you have any chronic medical conditions, "
                "current medications, or known allergies? "
                "(You can reply 'none' if not applicable.)"
            )


        if len(missing_fields) == 1:

            step_id = missing_fields[0]

        elif set(missing_fields).issubset(
            {"conditions", "medications", "allergies"}
        ):

            step_id = "medical_context"

        elif set(missing_fields) == {"duration", "severity"}:

            step_id = "duration_and_severity"

        else:

            step_id = missing_fields[0]


        return question, step_id


    # ======================================================
    # MESSAGE HELPERS
    # ======================================================

    def _is_greeting_or_empty_message(
        self,
        message: str,
    ) -> bool:
        """
        Checks whether the message is empty
        or contains only a simple greeting.
        """

        if not message:
            return True


        cleaned = (
            message.strip().lower()
        )


        greetings = {

            "hi",
            "hello",
            "hey",
            "hii",
            "hiii",
            "good morning",
            "good afternoon",
            "good evening",
            "start",

        }


        return cleaned in greetings


    def _is_waiting_for_initial_complaint(
        self,
        session: SessionState,
    ) -> bool:
        """
        Returns True when the patient has not yet
        provided an actual health complaint.
        """

        chief_complaint = (
            session.slots.get(
                "chief_complaint"
            )
        )


        return (
            not chief_complaint
            or chief_complaint == "Not provided"
        )


    def _has_escalation_been_delivered(
        self,
        session: SessionState,
    ) -> bool:
        """
        Checks whether the current escalation
        message has already been sent.
        """

        escalation_message = (
            session.escalation_message
        )


        if not escalation_message:
            return True


        for message in session.history:

            if (
                message.get("role") == "assistant"
                and escalation_message
                in message.get("content", "")
            ):

                return True


        return False


    def _is_duplicate_question(
        self,
        session: SessionState,
        question: Optional[str],
    ) -> bool:
        """
        Returns True if the question has already
        been asked during the consultation.
        """

        if not question:
            return False


        normalized_question = (
            question.strip().lower()
        )


        for asked_question in (
            session.asked_questions
        ):

            if (
                asked_question.strip().lower()
                == normalized_question
            ):

                return True


        return False


    # ======================================================
    # URGENCY EVALUATION
    # ======================================================

    def _evaluate_and_update_urgency(
        self,
        session_id: str,
        text: str,
    ) -> SessionState:
        """
        Runs deterministic urgency detection using
        the latest patient message and stored values.

        This remains the authority for urgency decisions.
        """

        session = (
            self.manager.get_session(
                session_id
            )
        )


        if not session:

            raise ValueError(
                f"Session '{session_id}' not found."
            )


        urgency, reasons, escalation_message = (
            UrgencyDetector.evaluate(
                text=text,
                severity=session.slots.get(
                    "severity"
                ),
                temperature=session.slots.get(
                    "temperature"
                ),
                existing_reasons=session.urgency_reasons,
            )
        )


        return self.manager.update_urgency(
            session_id=session_id,
            urgency=urgency,
            reasons=reasons,
            escalation_message=escalation_message,
        )


    # ======================================================
    # START CONSULTATION
    # ======================================================

    def start_consultation(
        self,
        patient_id: str,
        initial_message: str = "",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Begins a consultation.

        If no medical complaint is provided,
        BharatRx asks for the patient's concern.

        If a complaint is provided directly,
        intake begins immediately.
        """

        if not session_id:

            session_id = (
                f"S_{patient_id}_"
                f"{int(time.time() * 1000)}"
            )


        session = (
            self.manager.get_or_create_session(
                session_id,
                patient_id,
            )
        )


        # --------------------------------------------------
        # START WITH GREETING
        # --------------------------------------------------

        if self._is_greeting_or_empty_message(
            initial_message
        ):

            # Avoid adding duplicate greetings
            # when an existing session is started again.

            if not session.history:

                self.manager.record_assistant_response(
                    session_id=session_id,
                    question=self.GREETING_MESSAGE,
                    step_key="greeting",
                    complete=False,
                )


            response = (
                ConsultationMessageResponse(
                    session_id=session_id,
                    next_question=self.GREETING_MESSAGE,
                    conversation_complete=False,
                    urgency=session.urgency,
                )
            )


            return response.model_dump()


        # --------------------------------------------------
        # DIRECT MEDICAL COMPLAINT
        # --------------------------------------------------

        return self.process_message(
            session_id=session_id,
            patient_message=initial_message,
            patient_id=patient_id,
        )


    # ======================================================
    # PROCESS MESSAGE
    # ======================================================

    def process_message(
        self,
        session_id: str,
        patient_message: str,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processes a patient message and generates
        the next consultation question.
        """

        session = (
            self.manager.get_session(
                session_id
            )
        )


        # --------------------------------------------------
        # SESSION RECOVERY
        # --------------------------------------------------

        if not session:

            if patient_id:

                session = (
                    self.manager.get_or_create_session(
                        session_id,
                        patient_id,
                    )
                )

            else:

                raise ValueError(
                    f"Session '{session_id}' not found and "
                    "patient_id was not provided."
                )


        # --------------------------------------------------
        # ALREADY COMPLETE
        # --------------------------------------------------

        if session.conversation_complete:

            response = (
                ConsultationMessageResponse(
                    session_id=session_id,
                    next_question=self.COMPLETION_MESSAGE,
                    conversation_complete=True,
                    urgency=session.urgency,
                )
            )


            return response.model_dump()


        # --------------------------------------------------
        # HANDLE INITIAL COMPLAINT
        # --------------------------------------------------

        if self._is_waiting_for_initial_complaint(
            session
        ):

            if self._is_greeting_or_empty_message(
                patient_message
            ):

                next_question = (
                    "Hello! Please tell me what health concern "
                    "or symptom you are experiencing today."
                )


                self.manager.add_patient_message(
                    session_id,
                    patient_message,
                )


                if not self._is_duplicate_question(
                    session,
                    next_question,
                ):

                    self.manager.record_assistant_response(
                        session_id=session_id,
                        question=next_question,
                        step_key="waiting_for_complaint",
                        complete=False,
                    )


                response = (
                    ConsultationMessageResponse(
                        session_id=session_id,
                        next_question=next_question,
                        conversation_complete=False,
                        urgency=session.urgency,
                    )
                )


                return response.model_dump()


            # Store first actual complaint

            cleaned_complaint = (
                patient_message.strip()
            )


            session.slots[
                "chief_complaint"
            ] = cleaned_complaint


            session.flow_category = (
                self.mock_engine.detect_flow_category(
                    cleaned_complaint
                )
            )


        # --------------------------------------------------
        # STORE PATIENT MESSAGE
        # --------------------------------------------------

        self.manager.add_patient_message(
            session_id,
            patient_message,
        )


        # --------------------------------------------------
        # EXTRACT CLINICAL SLOTS
        # --------------------------------------------------

        expected_field = (
            session.asked_step_keys[-1]
            if session.asked_step_keys
            else None
        )

        extracted = (
            self.mock_engine.extract_slots_from_text(
                patient_message,
                session.slots,
                expected_field=expected_field,
            )
        )


        self.manager.update_slots(
            session_id,
            extracted,
        )


        # Refresh session after slot update

        session = (
            self.manager.get_session(
                session_id
            )
        )


        # --------------------------------------------------
        # DETERMINISTIC URGENCY EVALUATION
        # --------------------------------------------------

        self._evaluate_and_update_urgency(
            session_id=session_id,
            text=patient_message,
        )


        session = (
            self.manager.get_session(
                session_id
            )
        )


        # --------------------------------------------------
        # DETERMINE NEXT REQUIRED FIELD (DETERMINISTIC)
        # --------------------------------------------------

        (
            mock_question,
            mock_step_id,
            complete,
        ) = self.mock_engine.get_next_question(
            flow_category=session.flow_category,
            asked_step_keys=session.asked_step_keys,
            slots=session.slots,
        )

        next_question = mock_question

        step_id = mock_step_id

        # --------------------------------------------------
        # INTAKE COMPLETION GUARDRAIL
        # --------------------------------------------------

        if complete:

            missing_fields = self._get_missing_intake_fields(
                session
            )

            if (
                missing_fields
                and session.turn_count < self.MAX_SAFETY_TURNS
            ):

                complete = False

                next_question, step_id = (
                    self._generate_guardrail_followup(
                        missing_fields
                    )
                )

        # --------------------------------------------------
        # OPTIONAL GEMINI WORDING ENHANCEMENT
        # --------------------------------------------------

        if (
            not complete
            and self.gemini
            and self.gemini.is_available()
            and not self.force_mock
        ):

            try:

                llm_result = self.gemini.generate_next_turn(
                    history=session.history,
                    slots=session.slots,
                    turn_count=session.turn_count,
                )

                if llm_result:

                    # Update any additional extracted slots
                    if llm_result.get("extracted_slots"):

                        self.manager.update_slots(
                            session_id,
                            llm_result["extracted_slots"],
                        )

                        session = self.manager.get_session(
                            session_id
                        )

                        self._evaluate_and_update_urgency(
                            session_id=session_id,
                            text=patient_message,
                        )

                        session = self.manager.get_session(
                            session_id
                        )

                    # Intercept premature completion
                    if llm_result.get("conversation_complete"):

                        missing_fields = self._get_missing_intake_fields(
                            session
                        )

                        if (
                            missing_fields
                            and session.turn_count < self.MAX_SAFETY_TURNS
                        ):

                            complete = False

                            next_question, step_id = (
                                self._generate_guardrail_followup(
                                    missing_fields
                                )
                            )

                    # Use conversational phrasing if valid and not a duplicate
                    llm_question = llm_result.get(
                        "next_question"
                    )

                    if (
                        llm_question
                        and not self._is_duplicate_question(
                            session,
                            llm_question,
                        )
                        and not complete
                    ):

                        next_question = llm_question

            except Exception as exc:

                logger.exception(
                    "Gemini generation failed. "
                    "Using deterministic fallback. "
                    "Error: %s",
                    exc,
                )


        # --------------------------------------------------
        # MAXIMUM TURN LIMIT & COMPLETION
        # --------------------------------------------------

        if (
            session.turn_count
            >= self.MAX_SAFETY_TURNS
        ):

            complete = True

        if complete:

            next_question = (
                self.COMPLETION_MESSAGE
            )

            step_id = (
                "conclusion"
            )


        # --------------------------------------------------
        # URGENCY ESCALATION DELIVERY
        # --------------------------------------------------

        if (
            session.escalation_message
            and not self._has_escalation_been_delivered(
                session
            )
        ):

            next_question = (
                f"{session.escalation_message}\n\n"
                f"{next_question}"
            )


        # --------------------------------------------------
        # FALLBACK STEP ID
        # --------------------------------------------------

        if step_id is None:

            step_id = (
                f"turn_{session.turn_count}"
            )


        # --------------------------------------------------
        # SAVE ASSISTANT RESPONSE
        # --------------------------------------------------

        self.manager.record_assistant_response(
            session_id=session_id,
            question=next_question,
            step_key=step_id,
            complete=complete,
        )


        # --------------------------------------------------
        # ENSURE COMPLETION IS STORED
        # --------------------------------------------------

        if complete:

            self.manager.mark_conversation_complete(
                session_id
            )


        session = (
            self.manager.get_session(
                session_id
            )
        )


        # --------------------------------------------------
        # RESPONSE
        # --------------------------------------------------

        response = (
            ConsultationMessageResponse(
                session_id=session_id,
                next_question=next_question,
                conversation_complete=session.conversation_complete,
                urgency=session.urgency,
            )
        )


        return response.model_dump()


    # ======================================================
    # IMAGE MANAGEMENT
    # ======================================================

    def attach_image_reference(
        self,
        session_id: str,
        image_reference: str,
    ) -> Dict[str, Any]:
        """
        Associates an uploaded image reference
        with the consultation session.

        Does not diagnose the image.
        """

        session = (
            self.manager.get_session(
                session_id
            )
        )


        if not session:

            raise ValueError(
                f"Session '{session_id}' not found."
            )


        self.manager.attach_image(
            session_id,
            image_reference,
        )


        return {

            "session_id": session_id,

            "uploaded_image": image_reference,

            "success": True,

        }


    # ======================================================
    # CONSULTATION REPORT
    # ======================================================

    def get_consultation_report(
        self,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Generates the structured consultation report.
        """

        session = (
            self.manager.get_session(
                session_id
            )
        )


        if not session:

            raise ValueError(
                f"Session '{session_id}' not found."
            )


        llm_summary = None


        if (
            self.gemini
            and self.gemini.is_available()
            and not self.force_mock
        ):

            try:

                llm_summary = (
                    self.gemini.generate_summary(
                        session.history,
                        session.slots,
                    )
                )

            except Exception as exc:

                logger.exception(
                    "Gemini summary generation failed. "
                    "Using deterministic report generation. "
                    "Error: %s",
                    exc,
                )


        report = (
            ReportGenerator.generate_report(
                session,
                llm_summary=llm_summary,
            )
        )


        return report.model_dump()


    # ======================================================
    # PATIENT PROFILE
    # ======================================================

    def get_patient_profile(
        self,
        session_id: str,
    ) -> Dict[str, Any]:
        """
        Generates the unified PatientProfile.
        """

        session = (
            self.manager.get_session(
                session_id
            )
        )


        if not session:

            raise ValueError(
                f"Session '{session_id}' not found."
            )


        profile = (
            ReportGenerator.generate_patient_profile(
                session
            )
        )


        return profile.model_dump()