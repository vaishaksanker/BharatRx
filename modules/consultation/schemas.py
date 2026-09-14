"""
Data contracts and Pydantic schemas for BharatRx Pre-Consultation AI Module.

Defines the standardized request, response, patient profile,
medication, error, and consultation report contracts.

Compatible with:
- engine.py
- conversation_manager.py
- mock_engine.py
- urgency_detector.py
- report_generator.py

Requires Pydantic v2.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


# ==========================================================
# ENUMS
# ==========================================================

class UrgencyLevel(str, Enum):
    """Supported consultation urgency levels."""

    ROUTINE = "routine"
    URGENT = "urgent"


class ErrorCode(str, Enum):
    """Standard BharatRx error codes."""

    INVALID_REQUEST = "INVALID_REQUEST"
    PATIENT_NOT_FOUND = "PATIENT_NOT_FOUND"
    INVALID_MEDICATION = "INVALID_MEDICATION"
    MODULE_ERROR = "MODULE_ERROR"
    AI_SERVICE_ERROR = "AI_SERVICE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ==========================================================
# ERROR SCHEMAS
# ==========================================================

class ErrorDetail(BaseModel):
    """Details about an application error."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Standard API error response."""

    model_config = ConfigDict(extra="forbid")

    success: bool = False
    error: ErrorDetail


# ==========================================================
# CONSULTATION MESSAGE SCHEMAS
# ==========================================================

class ConsultationMessageRequest(BaseModel):
    """
    Patient message submitted during a consultation.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    session_id: str = Field(
        ...,
        min_length=1,
        description="Unique consultation session identifier",
    )

    patient_id: str = Field(
        ...,
        min_length=1,
        description="Unique patient identifier",
    )

    message: str = Field(
        ...,
        min_length=1,
        description="Patient input message or health complaint",
    )


class ConsultationMessageResponse(BaseModel):
    """
    Response returned after processing a patient message.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str

    next_question: str

    conversation_complete: bool = False

    urgency: str = Field(
        default=UrgencyLevel.ROUTINE.value
    )

    @field_validator("urgency")
    @classmethod
    def validate_urgency(
        cls,
        value: str,
    ) -> str:

        normalized = (
            value.lower().strip()
        )

        allowed_values = {
            UrgencyLevel.ROUTINE.value,
            UrgencyLevel.URGENT.value,
        }

        if normalized not in allowed_values:

            raise ValueError(
                "Urgency must be either "
                "'routine' or 'urgent'."
            )

        return normalized


# ==========================================================
# CONSULTATION REPORT REQUEST
# ==========================================================

class ConsultationReportRequest(BaseModel):
    """
    Request for retrieving a completed consultation report.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    session_id: str = Field(
        ...,
        min_length=1,
    )

    patient_id: str = Field(
        ...,
        min_length=1,
    )


# ==========================================================
# MEDICATION
# ==========================================================

class Medication(BaseModel):
    """
    Structured medication information.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str = Field(
        ...,
        min_length=1,
        description="Medication name",
    )

    dose: str = Field(
        default="Not provided",
        description="Medication dosage",
    )

    frequency: str = Field(
        default="Not provided",
        description="Medication frequency",
    )


# ==========================================================
# PATIENT PROFILE
# ==========================================================

class PatientProfile(BaseModel):
    """
    Unified patient representation.

    Used by:
    - Vaishak's backend
    - Sidharth's safety engine
    """

    model_config = ConfigDict(extra="forbid")

    patient_id: str

    name: Optional[str] = "Not provided"

    age: Optional[int] = Field(
        default=None,
        ge=0,
        le=150,
    )

    sex: str = "Not provided"

    conditions: List[str] = Field(
        default_factory=list
    )

    allergies: List[str] = Field(
        default_factory=list
    )

    current_medications: List[Medication] = Field(
        default_factory=list
    )


# ==========================================================
# CONSULTATION REPORT
# ==========================================================

class ConsultationReport(BaseModel):
    """
    Structured doctor consultation report.

    Missing value rules:
    - Missing numbers -> null
    - Missing lists -> []
    - Missing text -> "Not provided"
    """

    model_config = ConfigDict(extra="forbid")

    report_id: str

    patient_id: str


    # ------------------------------------------------------
    # CHIEF COMPLAINT
    # ------------------------------------------------------

    chief_complaint: str = "Not provided"

    duration: str = "Not provided"


    # ------------------------------------------------------
    # CLINICAL VALUES
    # ------------------------------------------------------

    severity: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
    )

    temperature: Optional[float] = Field(
        default=None,
        ge=80.0,
        le=115.0,
        description=(
            "Reported temperature in Fahrenheit "
            "when available"
        ),
    )


    # ------------------------------------------------------
    # SYMPTOMS
    # ------------------------------------------------------

    associated_symptoms: List[str] = Field(
        default_factory=list
    )


    # ------------------------------------------------------
    # MEDICAL HISTORY
    # ------------------------------------------------------

    medical_history: List[str] = Field(
        default_factory=list
    )

    current_medications: List[Medication] = Field(
        default_factory=list
    )

    allergies: List[str] = Field(
        default_factory=list
    )


    # ------------------------------------------------------
    # UPLOADED IMAGE
    # ------------------------------------------------------

    uploaded_image: Optional[str] = "Not provided"


    # ------------------------------------------------------
    # GENERATED CLINICAL TEXT
    # ------------------------------------------------------

    patient_description: str = "Not provided"

    ai_summary: str = "Not provided"


    # ------------------------------------------------------
    # DOCTOR REVIEW QUESTIONS
    # ------------------------------------------------------

    doctor_review_questions: List[str] = Field(
        default_factory=list,
        max_length=3,
    )


    # ------------------------------------------------------
    # TRIAGE
    # ------------------------------------------------------

    urgency: str = Field(
        default=UrgencyLevel.ROUTINE.value
    )


    # ------------------------------------------------------
    # TIMESTAMP
    # ------------------------------------------------------

    created_at: str = Field(
        default_factory=lambda: (
            datetime.now(timezone.utc).isoformat()
        )
    )


    @field_validator("urgency")
    @classmethod
    def validate_urgency(
        cls,
        value: str,
    ) -> str:

        normalized = (
            value.lower().strip()
        )

        allowed_values = {
            UrgencyLevel.ROUTINE.value,
            UrgencyLevel.URGENT.value,
        }

        if normalized not in allowed_values:

            raise ValueError(
                "Urgency must be either "
                "'routine' or 'urgent'."
            )

        return normalized