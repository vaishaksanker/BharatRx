"""
BharatRx Pre-Consultation AI Module.
Owned by: Namita
"""

from .api import app, router
from .conversation_manager import ConversationManager, SessionState
from .engine import ConsultationEngine
from .gemini_service import GeminiService
from .mock_data import MOCK_DEMO_SCENARIOS
from .mock_engine import MockConsultationEngine
from .report_generator import ReportGenerator
from .schemas import (
    ConsultationMessageRequest,
    ConsultationMessageResponse,
    ConsultationReport,
    ConsultationReportRequest,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    Medication,
    PatientProfile,
    UrgencyLevel,
)
from .urgency_detector import UrgencyDetector

__all__ = [
    "ConsultationEngine",
    "ConversationManager",
    "SessionState",
    "UrgencyDetector",
    "MockConsultationEngine",
    "GeminiService",
    "ReportGenerator",
    "ConsultationMessageRequest",
    "ConsultationMessageResponse",
    "ConsultationReportRequest",
    "ConsultationReport",
    "Medication",
    "PatientProfile",
    "UrgencyLevel",
    "ErrorCode",
    "ErrorDetail",
    "ErrorResponse",
    "MOCK_DEMO_SCENARIOS",
    "router",
    "app",
]
