"""
In-memory session state management for BharatRx Pre-Consultation AI Module.

Stores:
- Conversation history
- Clinical slot values
- Asked steps
- Session progress
- Urgency information
- Uploaded image references

This manager does not perform diagnosis or clinical reasoning.
It only manages consultation state safely.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ==========================================================
# SESSION STATE
# ==========================================================

@dataclass
class SessionState:

    session_id: str
    patient_id: str

    # ------------------------------------------------------
    # CONSULTATION FLOW
    # ------------------------------------------------------

    flow_category: str = "general"

    # ------------------------------------------------------
    # CONVERSATION HISTORY
    # ------------------------------------------------------

    history: List[Dict[str, str]] = field(
        default_factory=list
    )

    # ------------------------------------------------------
    # CLINICAL INFORMATION
    # ------------------------------------------------------

    slots: Dict[str, Any] = field(
        default_factory=dict
    )

    # ------------------------------------------------------
    # QUESTION TRACKING
    # ------------------------------------------------------

    asked_step_keys: List[str] = field(
        default_factory=list
    )

    asked_questions: List[str] = field(
        default_factory=list
    )

    # ------------------------------------------------------
    # CONVERSATION STATUS
    # ------------------------------------------------------

    turn_count: int = 0

    conversation_complete: bool = False

    # ------------------------------------------------------
    # URGENCY INFORMATION
    # ------------------------------------------------------

    urgency: str = "routine"

    urgency_reasons: List[str] = field(
        default_factory=list
    )

    escalation_message: Optional[str] = None

    # ------------------------------------------------------
    # UPLOADED IMAGE
    # ------------------------------------------------------

    uploaded_image: Optional[str] = None

    # ------------------------------------------------------
    # CREATION TIME
    # ------------------------------------------------------

    created_at: str = field(
        default_factory=lambda: (
            datetime.now(timezone.utc).isoformat()
        )
    )


# ==========================================================
# CONVERSATION MANAGER
# ==========================================================

class ConversationManager:

    """
    Manages BharatRx pre-consultation sessions.

    Responsibilities:
    - Create and retrieve sessions
    - Store conversation history
    - Track consultation questions
    - Update clinical information
    - Track urgency
    - Store uploaded images
    - Mark consultations complete

    This class does not:
    - Diagnose
    - Prescribe treatment
    - Perform clinical reasoning
    """

    def __init__(self):

        self._sessions: Dict[
            str,
            SessionState
        ] = {}

    # ======================================================
    # INTERNAL VALIDATION
    # ======================================================

    @staticmethod
    def _validate_identifier(
        value: str,
        field_name: str,
    ) -> str:

        if not isinstance(value, str):

            raise ValueError(
                f"{field_name} must be a string."
            )

        cleaned_value = value.strip()

        if not cleaned_value:

            raise ValueError(
                f"{field_name} cannot be empty."
            )

        return cleaned_value

    # ======================================================
    # INTERNAL SESSION VALIDATION
    # ======================================================

    def _require_session(
        self,
        session_id: str,
    ) -> SessionState:

        session_id = self._validate_identifier(
            session_id,
            "session_id",
        )

        session = self._sessions.get(
            session_id
        )

        if session is None:

            raise ValueError(
                f"Session '{session_id}' not found."
            )

        return session

    # ======================================================
    # DEFAULT CLINICAL SLOTS
    # ======================================================

    @staticmethod
    def _create_initial_slots(
        patient_id: str,
    ) -> Dict[str, Any]:

        return {

            # --------------------------------------------------
            # PATIENT INFORMATION
            # --------------------------------------------------

            "patient_id": patient_id,

            "name": "Not provided",

            "age": None,

            "sex": "Not provided",

            # --------------------------------------------------
            # MAIN COMPLAINT
            # --------------------------------------------------

            "chief_complaint": "Not provided",

            # --------------------------------------------------
            # SYMPTOM DETAILS
            # --------------------------------------------------

            "location": None,

            "character": None,

            "appearance": None,

            "sensation": None,

            "duration": "Not provided",

            "onset": None,

            "progression": None,

            "severity": None,

            "temperature": None,

            "temperature_unit": None,

            # --------------------------------------------------
            # ASSOCIATED SYMPTOMS
            # --------------------------------------------------

            "associated_symptoms": [],

            # --------------------------------------------------
            # MEDICAL CONTEXT
            # --------------------------------------------------

            "conditions": [],

            "current_medications": [],

            "allergies": [],

            # --------------------------------------------------
            # QUESTION ANSWER FLAGS
            # --------------------------------------------------

            "duration_addressed": False,

            "severity_addressed": False,

            "temperature_addressed": False,

            "associated_symptoms_addressed": False,

            "conditions_addressed": False,

            "medications_addressed": False,

            "allergies_addressed": False,

            # --------------------------------------------------
            # IMAGE INFORMATION
            # --------------------------------------------------

            "uploaded_image": "Not provided",
        }

    # ======================================================
    # SESSION MANAGEMENT
    # ======================================================

    def get_or_create_session(
        self,
        session_id: str,
        patient_id: str,
    ) -> SessionState:

        """
        Retrieves an existing session.

        Creates a new session if one does not exist.

        A session ID must always remain associated with
        the same patient ID.
        """

        session_id = self._validate_identifier(
            session_id,
            "session_id",
        )

        patient_id = self._validate_identifier(
            patient_id,
            "patient_id",
        )

        # --------------------------------------------------
        # CREATE NEW SESSION
        # --------------------------------------------------

        if session_id not in self._sessions:

            initial_slots = (
                self._create_initial_slots(
                    patient_id
                )
            )

            self._sessions[
                session_id
            ] = SessionState(

                session_id=session_id,

                patient_id=patient_id,

                slots=initial_slots,
            )

        # --------------------------------------------------
        # VALIDATE EXISTING SESSION
        # --------------------------------------------------

        session = self._sessions[
            session_id
        ]

        if session.patient_id != patient_id:

            raise ValueError(
                "This session_id is already associated "
                "with a different patient_id."
            )

        return session

    # ======================================================
    # GET SESSION
    # ======================================================

    def get_session(
        self,
        session_id: str,
    ) -> Optional[SessionState]:

        """
        Returns the session if it exists.
        """

        if not isinstance(
            session_id,
            str,
        ):
            return None

        cleaned_session_id = (
            session_id.strip()
        )

        if not cleaned_session_id:
            return None

        return self._sessions.get(
            cleaned_session_id
        )

    # ======================================================
    # PATIENT MESSAGE
    # ======================================================

    def add_patient_message(
        self,
        session_id: str,
        message: str,
    ) -> SessionState:

        """
        Stores a patient message and increments
        the patient turn count.
        """

        session = self._require_session(
            session_id
        )

        if not isinstance(
            message,
            str,
        ):

            raise ValueError(
                "Patient message must be a string."
            )

        cleaned_message = message.strip()

        if not cleaned_message:

            return session

        session.history.append(
            {
                "role": "patient",
                "content": cleaned_message,
            }
        )

        session.turn_count += 1

        return session

    # ======================================================
    # ASSISTANT RESPONSE
    # ======================================================

    def record_assistant_response(
        self,
        session_id: str,
        question: str,
        step_key: Optional[str] = None,
        complete: bool = False,
    ) -> SessionState:

        """
        Stores BharatRx assistant response.

        Also tracks:
        - Asked questions
        - Asked step keys
        - Conversation completion
        """

        session = self._require_session(
            session_id
        )

        if not isinstance(
            question,
            str,
        ):

            raise ValueError(
                "Assistant response must be a string."
            )

        question = question.strip()

        if not question:

            question = (
                "Could you please provide more information?"
            )

        # --------------------------------------------------
        # STORE ASSISTANT MESSAGE
        # --------------------------------------------------

        session.history.append(
            {
                "role": "assistant",
                "content": question,
            }
        )

        # --------------------------------------------------
        # STORE QUESTION
        # --------------------------------------------------

        if (
            not complete
            and question not in session.asked_questions
        ):

            session.asked_questions.append(
                question
            )

        # --------------------------------------------------
        # STORE STEP KEY
        # --------------------------------------------------

        if (
            step_key
            and step_key != "conclusion"
        ):

            if step_key in session.asked_step_keys:

                session.asked_step_keys.remove(
                    step_key
                )

            session.asked_step_keys.append(
                step_key
            )

        # --------------------------------------------------
        # CONVERSATION STATUS
        # --------------------------------------------------

        if complete:

            session.conversation_complete = True

        return session

    # ======================================================
    # SLOT MANAGEMENT
    # ======================================================

    @staticmethod
    def _normalize_string(
        value: Any,
    ) -> str:

        """
        Converts a value into a normalized string
        for duplicate comparison.
        """

        return str(value).strip().lower()

    # ======================================================
    # UPDATE SLOTS
    # ======================================================

    def update_slots(
        self,
        session_id: str,
        new_slots: Dict[str, Any],
    ) -> SessionState:

        """
        Safely merges extracted clinical information.

        Rules:
        - Useful information is preserved.
        - Empty values do not erase useful data.
        - True answer flags are preserved.
        - Lists are merged uniquely.
        - Dictionaries are merged safely.
        - Medication dictionaries are merged by name.
        """

        session = self._require_session(
            session_id
        )

        if not isinstance(
            new_slots,
            dict,
        ):

            raise ValueError(
                "new_slots must be a dictionary."
            )

        for key, value in new_slots.items():

            # ==================================================
            # BOOLEAN VALUES
            # ==================================================

            if isinstance(value, bool):

                current_value = session.slots.get(
                    key
                )

                # Once True, preserve True.
                if value is True:

                    session.slots[key] = True

                elif current_value is None:

                    session.slots[key] = False

                elif current_value is False:

                    session.slots[key] = False

                # Do not overwrite True with False.
                continue

            # ==================================================
            # NONE VALUES
            # ==================================================

            if value is None:

                if key not in session.slots:

                    session.slots[key] = None

                continue

            # ==================================================
            # STRING VALUES
            # ==================================================

            if isinstance(value, str):

                cleaned_value = value.strip()

                if not cleaned_value:

                    continue

                current_value = session.slots.get(
                    key
                )

                # Do not replace useful information
                # with "Not provided".
                if cleaned_value == "Not provided":

                    if (
                        current_value is None
                        or current_value == ""
                    ):

                        session.slots[key] = (
                            cleaned_value
                        )

                    continue

                session.slots[key] = cleaned_value

                continue

            # ==================================================
            # LIST VALUES
            # ==================================================

            if isinstance(value, list):

                existing = session.slots.get(
                    key
                )

                if not isinstance(
                    existing,
                    list,
                ):

                    existing = []

                # Do not erase useful information
                # with an empty list.
                if not value:

                    session.slots[key] = existing

                    continue

                for item in value:

                    # ------------------------------------------
                    # DICTIONARY ITEM
                    # ------------------------------------------

                    if isinstance(
                        item,
                        dict,
                    ):

                        item_copy = dict(item)

                        item_name = (
                            self._normalize_string(
                                item_copy.get(
                                    "name",
                                    "",
                                )
                            )
                        )

                        already_exists = False

                        for (
                            index,
                            existing_item,
                        ) in enumerate(existing):

                            if not isinstance(
                                existing_item,
                                dict,
                            ):
                                continue

                            existing_name = (
                                self._normalize_string(
                                    existing_item.get(
                                        "name",
                                        "",
                                    )
                                )
                            )

                            # Merge dictionaries with
                            # the same name.
                            if (
                                item_name
                                and item_name == existing_name
                            ):

                                merged_item = dict(
                                    existing_item
                                )

                                for (
                                    item_key,
                                    item_value,
                                ) in item_copy.items():

                                    if (
                                        item_value is not None
                                        and item_value != ""
                                        and item_value
                                        != "Not provided"
                                    ):

                                        merged_item[
                                            item_key
                                        ] = item_value

                                existing[index] = (
                                    merged_item
                                )

                                already_exists = True

                                break

                        if not already_exists:

                            existing.append(
                                item_copy
                            )

                    # ------------------------------------------
                    # NORMAL ITEM
                    # ------------------------------------------

                    else:

                        if isinstance(
                            item,
                            str,
                        ):

                            cleaned_item = item.strip()

                            if not cleaned_item:
                                continue

                            normalized_item = (
                                cleaned_item.lower()
                            )

                            existing_normalized = {

                                self._normalize_string(
                                    existing_item
                                )

                                for existing_item in existing

                                if isinstance(
                                    existing_item,
                                    str,
                                )
                            }

                            if (
                                normalized_item
                                not in existing_normalized
                            ):

                                existing.append(
                                    cleaned_item
                                )

                        elif item not in existing:

                            existing.append(
                                item
                            )

                session.slots[key] = existing

                continue

            # ==================================================
            # DICTIONARY VALUES
            # ==================================================

            if isinstance(value, dict):

                existing = session.slots.get(
                    key
                )

                if isinstance(
                    existing,
                    dict,
                ):

                    merged_value = dict(
                        existing
                    )

                    for (
                        item_key,
                        item_value,
                    ) in value.items():

                        if item_value is not None:

                            merged_value[
                                item_key
                            ] = item_value

                    session.slots[key] = (
                        merged_value
                    )

                else:

                    session.slots[key] = dict(
                        value
                    )

                continue

            # ==================================================
            # NUMBERS / OTHER VALUES
            # ==================================================

            session.slots[key] = value

        return session

    # ======================================================
    # FLOW CATEGORY MANAGEMENT
    # ======================================================

    def update_flow_category(
        self,
        session_id: str,
        flow_category: str,
    ) -> SessionState:

        """
        Updates the consultation flow category.
        """

        session = self._require_session(
            session_id
        )

        if not isinstance(
            flow_category,
            str,
        ):

            raise ValueError(
                "flow_category must be a string."
            )

        cleaned_category = (
            flow_category.strip().lower()
        )

        if cleaned_category:

            session.flow_category = (
                cleaned_category
            )

        return session

    # ======================================================
    # IMAGE MANAGEMENT
    # ======================================================

    def attach_image(
        self,
        session_id: str,
        image_reference: str,
    ) -> SessionState:

        """
        Stores uploaded image reference.

        BharatRx does not perform
        image diagnosis here.
        """

        session = self._require_session(
            session_id
        )

        if not isinstance(
            image_reference,
            str,
        ):

            raise ValueError(
                "Image reference must be a string."
            )

        image_reference = (
            image_reference.strip()
        )

        if not image_reference:

            raise ValueError(
                "Image reference cannot be empty."
            )

        session.uploaded_image = (
            image_reference
        )

        session.slots[
            "uploaded_image"
        ] = image_reference

        return session

    # ======================================================
    # URGENCY MANAGEMENT
    # ======================================================

    def update_urgency(
        self,
        session_id: str,
        urgency: str,
        reasons: Optional[List[str]] = None,
        escalation_message: Optional[str] = None,
    ) -> SessionState:

        """
        Updates consultation urgency.

        Valid urgency values:
        - routine
        - urgent

        Important:
        Once marked urgent, a consultation
        cannot automatically be downgraded.
        """

        session = self._require_session(
            session_id
        )

        urgency = (
            urgency or "routine"
        ).strip().lower()

        # --------------------------------------------------
        # VALIDATE URGENCY
        # --------------------------------------------------

        if urgency not in (
            "routine",
            "urgent",
        ):

            urgency = "routine"

        # --------------------------------------------------
        # UPDATE URGENCY
        # --------------------------------------------------

        if urgency == "urgent":

            session.urgency = "urgent"

        elif session.urgency != "urgent":

            session.urgency = "routine"

        # --------------------------------------------------
        # ADD REASONS
        # --------------------------------------------------

        for reason in reasons or []:

            if not isinstance(
                reason,
                str,
            ):
                continue

            cleaned_reason = reason.strip()

            if not cleaned_reason:
                continue

            existing_reasons = {
                existing_reason.strip().lower()
                for existing_reason
                in session.urgency_reasons
                if isinstance(
                    existing_reason,
                    str,
                )
            }

            if (
                cleaned_reason.lower()
                not in existing_reasons
            ):

                session.urgency_reasons.append(
                    cleaned_reason
                )

        # --------------------------------------------------
        # ESCALATION MESSAGE
        # --------------------------------------------------

        if (
            session.urgency == "urgent"
            and isinstance(
                escalation_message,
                str,
            )
        ):

            cleaned_message = (
                escalation_message.strip()
            )

            if cleaned_message:

                session.escalation_message = (
                    cleaned_message
                )

        return session

    # ======================================================
    # COMPLETE CONSULTATION
    # ======================================================

    def mark_conversation_complete(
        self,
        session_id: str,
    ) -> SessionState:

        """
        Marks the consultation as complete.
        """

        session = self._require_session(
            session_id
        )

        session.conversation_complete = True

        return session

    # ======================================================
    # DELETE SESSION
    # ======================================================

    def delete_session(
        self,
        session_id: str,
    ) -> bool:

        """
        Deletes a session.

        Useful for:
        - Testing
        - Cleanup
        """

        if not isinstance(
            session_id,
            str,
        ):

            return False

        session_id = session_id.strip()

        if not session_id:

            return False

        if session_id in self._sessions:

            del self._sessions[
                session_id
            ]

            return True

        return False

    # ======================================================
    # SESSION EXISTS
    # ======================================================

    def session_exists(
        self,
        session_id: str,
    ) -> bool:

        """
        Returns True if the session exists.
        """

        if not isinstance(
            session_id,
            str,
        ):

            return False

        cleaned_session_id = (
            session_id.strip()
        )

        if not cleaned_session_id:

            return False

        return (
            cleaned_session_id
            in self._sessions
        )