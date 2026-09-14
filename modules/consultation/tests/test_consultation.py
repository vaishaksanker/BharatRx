"""
Unit and integration tests for BharatRx Pre-Consultation AI Module.
Validates conversation management, mock flows, slot extraction, urgency detection,
report generation, patient profile construction, and API contract compliance.
"""

import pytest
from fastapi.testclient import TestClient

from modules.consultation.api import app
from modules.consultation.engine import ConsultationEngine
from modules.consultation.mock_data import MOCK_DEMO_SCENARIOS
from modules.consultation.mock_engine import MockConsultationEngine
from modules.consultation.schemas import (
    ConsultationMessageRequest,
    ConsultationMessageResponse,
    ConsultationReport,
    PatientProfile,
    UrgencyLevel,
)
from modules.consultation.urgency_detector import UrgencyDetector


@pytest.fixture
def engine():
    """Provides fresh ConsultationEngine instance forced to mock engine."""
    return ConsultationEngine(force_mock=True)


@pytest.fixture
def client():
    """Provides FastAPI test client."""
    return TestClient(app)


def test_session_creation_and_initial_message(engine):
    """Verifies starting a consultation session initializes state properly."""
    res = engine.start_consultation(
        patient_id="P001",
        initial_message="I have had a headache since yesterday.",
        session_id="S_TEST_001",
    )
    assert res["session_id"] == "S_TEST_001"
    assert "next_question" in res
    assert isinstance(res["next_question"], str)
    assert len(res["next_question"]) > 0
    assert res["conversation_complete"] is False
    assert res["urgency"] == "routine"


def test_adaptive_follow_up_headache_flow(engine):
    """Verifies multi-turn adaptive questioning for Headache."""
    session_id = "S_HEADACHE_01"
    # Turn 1: Initial complaint
    t1 = engine.start_consultation(patient_id="P001", initial_message="I have a headache.", session_id=session_id)
    assert "located" in t1["next_question"].lower() or "where" in t1["next_question"].lower()

    # Turn 2: Location answer
    t2 = engine.process_message(session_id=session_id, patient_message="It is in the temples, throbbing pain.")
    assert "how long" in t2["next_question"].lower() or "duration" in t2["next_question"].lower()

    # Turn 3: Duration answer
    t3 = engine.process_message(session_id=session_id, patient_message="Two days.")
    assert "scale of 1 to 10" in t3["next_question"].lower() or "severe" in t3["next_question"].lower()

    # Turn 4: Severity answer
    t4 = engine.process_message(session_id=session_id, patient_message="7 out of 10.")
    assert "other symptoms" in t4["next_question"].lower() or "nausea" in t4["next_question"].lower()


def test_adaptive_flows_for_all_four_conditions():
    """Verifies that all 4 specified conditions are properly categorized and have flow definitions."""
    conditions = [
        ("I have a migraine and severe head pain", "headache"),
        ("I have a high fever with chills", "fever"),
        ("My stomach is aching and burning", "stomach_pain"),
        ("I have an itchy red skin rash on my arms", "skin_rash"),
    ]
    for prompt, expected_category in conditions:
        detected = MockConsultationEngine.detect_flow_category(prompt)
        assert detected == expected_category, f"Failed for {prompt}"
        flow = MockConsultationEngine.FLOW_DEFINITIONS.get(detected)
        assert flow is not None and len(flow) >= 4


def test_red_flag_urgency_detection():
    """Verifies that acute red-flag symptoms are classified as urgent."""
    # Neurological red flag
    urgency, reasons, esc = UrgencyDetector.evaluate("This is the worst headache of my life.")
    assert urgency == "urgent"
    assert len(reasons) > 0
    assert esc is not None

    # Cardiorespiratory red flag
    urgency_cp, reasons_cp, _ = UrgencyDetector.evaluate("I have severe chest pain radiating to arm.")
    assert urgency_cp == "urgent"

    # Extreme pain severity
    urgency_sev, _, _ = UrgencyDetector.evaluate("Pain is very bad", severity=10)
    assert urgency_sev == "urgent"

    # Routine symptom
    urgency_rout, reasons_rout, esc_rout = UrgencyDetector.evaluate("Mild headache since morning", severity=4)
    assert urgency_rout == "routine"
    assert len(reasons_rout) == 0
    assert esc_rout is None


def test_missing_data_formatting_rules(engine):
    """
    Verifies adherence to BharatRx contract missing data rules:
    - Missing numeric values: null
    - Missing lists: []
    - Missing text: 'Not provided'
    """
    session_id = "S_SPARSE_01"
    engine.start_consultation(patient_id="P_SPARSE", initial_message="Cough", session_id=session_id)
    report = engine.get_consultation_report(session_id)

    # Validate against ConsultationReport Pydantic schema
    validated_report = ConsultationReport(**report)
    assert validated_report.temperature is None
    assert validated_report.severity is None
    assert isinstance(validated_report.associated_symptoms, list)
    assert isinstance(validated_report.allergies, list)
    assert isinstance(validated_report.medical_history, list)
    assert validated_report.uploaded_image == "Not provided"


def test_image_reference_attachment(engine):
    """Verifies attaching an uploaded image reference to session and report."""
    session_id = "S_IMAGE_01"
    engine.start_consultation(patient_id="P001", initial_message="Skin rash", session_id=session_id)
    attach_res = engine.attach_image_reference(session_id, "https://storage.bharatrx.in/prescriptions/rx123.png")
    assert attach_res["success"] is True

    report = engine.get_consultation_report(session_id)
    assert report["uploaded_image"] == "https://storage.bharatrx.in/prescriptions/rx123.png"


def test_unified_patient_profile_generation(engine):
    """
    Verifies that the generated patient profile conforms to docs/integration.md Section 3:
    patient_id, name, age, sex, conditions, allergies, current_medications (name, dose, frequency).
    """
    session_id = "S_PROFILE_01"
    engine.start_consultation(patient_id="P001", initial_message="I have fever", session_id=session_id)
    engine.process_message(
        session_id=session_id,
        patient_message="I have CKD and I am taking Warfarin 5mg OD. Also allergic to Penicillin.",
    )
    profile_data = engine.get_patient_profile(session_id)
    profile = PatientProfile(**profile_data)

    assert profile.patient_id == "P001"
    assert "CKD" in profile.conditions
    assert "Penicillin" in profile.allergies
    assert len(profile.current_medications) >= 1
    warfarin_med = profile.current_medications[0]
    assert warfarin_med.name == "Warfarin"
    assert "5" in warfarin_med.dose
    assert warfarin_med.frequency == "OD"


def test_api_message_endpoint(client):
    """Tests POST /api/consultation/message endpoint contract."""
    payload = {
        "session_id": "S_API_01",
        "patient_id": "P_API_01",
        "message": "I have had a headache since yesterday.",
    }
    response = client.post("/api/consultation/message", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "S_API_01"
    assert "next_question" in data
    assert "conversation_complete" in data
    assert data["urgency"] in ["routine", "urgent"]


def test_api_report_endpoint(client):
    """Tests POST /api/consultation/report endpoint contract."""
    session_id = "S_API_REPORT_01"
    patient_id = "P_API_REPORT_01"

    # Create session first
    client.post(
        "/api/consultation/message",
        json={"session_id": session_id, "patient_id": patient_id, "message": "Fever for 2 days"},
    )

    # Request report
    report_payload = {
        "session_id": session_id,
        "patient_id": patient_id,
    }
    response = client.post("/api/consultation/report", json=report_payload)
    assert response.status_code == 200
    report = response.json()
    assert report["patient_id"] == patient_id
    assert "report_id" in report
    assert "chief_complaint" in report
    assert "doctor_review_questions" in report
    assert isinstance(report["doctor_review_questions"], list)
    assert len(report["doctor_review_questions"]) >= 2
    assert report["urgency"] in ["routine", "urgent"]


def test_api_error_response_format(client):
    """Tests that error responses strictly follow the BharatRx error contract."""
    # Missing required field 'message'
    response = client.post(
        "/api/consultation/message",
        json={"session_id": "S001", "patient_id": "P001"},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert "message" in data["error"]

    # Non-existent session report request
    response_not_found = client.post(
        "/api/consultation/report",
        json={"session_id": "NON_EXISTENT_SESSION_999", "patient_id": "P999"},
    )
    assert response_not_found.status_code == 404
    data_nf = response_not_found.json()
    assert data_nf["success"] is False
    assert data_nf["error"]["code"] == "PATIENT_NOT_FOUND"


def test_mock_scenarios_execution(engine):
    """Simulates complete demo flow from mock_data.py."""
    for key, scenario in MOCK_DEMO_SCENARIOS.items():
        sess_id = f"S_SCENARIO_{key}"
        patient_info = scenario["patient"]
        init_res = engine.start_consultation(
            patient_id=patient_info["patient_id"],
            initial_message=scenario["initial_message"],
            session_id=sess_id,
        )
        assert init_res["session_id"] == sess_id

        for user_ans in scenario["responses"]:
            turn_res = engine.process_message(
                session_id=sess_id,
                patient_message=user_ans,
            )
            assert "next_question" in turn_res

        report = engine.get_consultation_report(sess_id)
        assert report["patient_id"] == patient_info["patient_id"]
        assert report["urgency"] == scenario["expected_slots"]["urgency"]


def test_severity_validation_in_report():
    """Verifies that severity score must be between 1 and 10 or None."""
    # Valid report
    valid_report = ConsultationReport(
        report_id="R1",
        patient_id="P1",
        chief_complaint="Headache",
        duration="1 day",
        severity=7,
        urgency="routine",
    )
    assert valid_report.severity == 7

    # Invalid severity > 10 should raise ValidationError
    with pytest.raises(Exception):
        ConsultationReport(
            report_id="R2",
            patient_id="P2",
            chief_complaint="Headache",
            duration="1 day",
            severity=15,
            urgency="routine",
        )


def test_gemini_fallback_on_invalid_key():
    """Verifies that if an invalid Gemini key is provided, the engine safely falls back without crashing."""
    engine_with_bad_key = ConsultationEngine(gemini_api_key="INVALID_MOCK_KEY_12345")
    # Turn 1 should catch error and fall back to mock engine question
    res = engine_with_bad_key.start_consultation(
        patient_id="P_FALLBACK_01",
        initial_message="I have a headache",
        session_id="S_FALLBACK_01",
    )
    assert "session_id" in res
    assert "next_question" in res
    assert len(res["next_question"]) > 0


def test_complete_conversation_flow_termination(engine):
    """Verifies that a multi-turn conversation eventually sets conversation_complete to True."""
    sess_id = "S_COMPLETE_01"
    engine.start_consultation(patient_id="P100", initial_message="Stomach pain", session_id=sess_id)
    answers = [
        "Upper belly",
        "2 days, pain is 5 out of 10",
        "No vomiting",
        "No other medicines",
        "Nothing else",
    ]
    last_res = None
    for a in answers:
        last_res = engine.process_message(session_id=sess_id, patient_message=a)

    assert last_res["conversation_complete"] is True
    assert "prepared" in last_res["next_question"].lower() or "thank you" in last_res["next_question"].lower()


def test_safe_dotenv_loading_and_availability(tmp_path, monkeypatch):
    """Verifies that .env loading works safely without exposing secrets and respects availability toggle."""
    import os
    import dotenv
    from modules.consultation.gemini_service import GeminiService

    # Clear any pre-existing GEMINI_API_KEY from the test process environment
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    fake_env = tmp_path / ".env"

    # Intercept load_dotenv to isolate from the project's real root .env
    def fake_load_dotenv(dotenv_path=None, override=False):
        if fake_env.is_file():
            for line in fake_env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if override or k not in os.environ:
                        os.environ[k.strip()] = v.strip()

    monkeypatch.setattr(dotenv, "load_dotenv", fake_load_dotenv)

    # 1. No key loaded yet (fake_env does not exist yet) -> is_available should be False
    service_no_key = GeminiService()
    assert service_no_key.is_available() is False

    # Explicit empty key -> is_available should be False
    service_explicit_empty = GeminiService(api_key="")
    assert service_explicit_empty.is_available() is False

    # 2. Create isolated fake .env file
    fake_env.write_text("GEMINI_API_KEY=test_mock_secret_key_123\n", encoding="utf-8")

    # Initializing GeminiService now triggers _safe_load_dotenv which calls fake_load_dotenv
    service_with_key = GeminiService()
    assert service_with_key.is_available() is True
    assert service_with_key.api_key == "test_mock_secret_key_123"


def test_associated_symptoms_extraction_and_report_population(engine):
    """
    Verifies that:
    1. 'I feel mildly nauseous' extracts 'nausea'
    2. 'Bright lights bother my eyes' extracts 'light sensitivity'
    3. The final consultation report contains these values in associated_symptoms
    """
    from modules.consultation.mock_engine import MockConsultationEngine

    # 1. Direct slot extraction verification
    slots_1 = MockConsultationEngine.extract_slots_from_text("I feel mildly nauseous", {})
    assert "nausea" in slots_1["associated_symptoms"]

    slots_2 = MockConsultationEngine.extract_slots_from_text("Bright lights bother my eyes", {})
    assert "light sensitivity" in slots_2["associated_symptoms"]

    # 2. End-to-end engine and report verification
    session_id = "S_ASSOC_TEST_01"
    engine.start_consultation(
        patient_id="P001",
        initial_message="I have had a throbbing headache since yesterday morning.",
        session_id=session_id,
    )
    engine.process_message(
        session_id=session_id,
        patient_message="I feel mildly nauseous and bright lights bother my eyes.",
    )

    report = engine.get_consultation_report(session_id=session_id)
    assert "nausea" in report["associated_symptoms"]
    assert "light sensitivity" in report["associated_symptoms"]


def test_completion_prevented_when_medical_context_unaddressed(engine):
    """
    Verifies that conversation_complete does NOT become True at turn 5 (or any turn)
    if medical history, medications, or allergies are unaddressed.
    """
    session_id = "S_GUARD_01"
    # Turn 1
    engine.start_consultation(patient_id="P001", initial_message="I have a throbbing headache.", session_id=session_id)
    # Turn 2: Location
    engine.process_message(session_id=session_id, patient_message="Forehead and temples.")
    # Turn 3: Duration
    engine.process_message(session_id=session_id, patient_message="Started 2 days ago.")
    # Turn 4: Severity
    engine.process_message(session_id=session_id, patient_message="Pain is 6 out of 10.")
    # Turn 5: Associated symptoms
    engine.process_message(session_id=session_id, patient_message="Mild nausea.")
    # Turn 6: Off-topic / unaddressed answer when asked about medical context
    t6 = engine.process_message(session_id=session_id, patient_message="It also hurts when I bend down.")

    # Even though all 5 mock steps were asked, intake is missing conditions/meds/allergies
    assert t6["conversation_complete"] is False
    assert any(
        k in t6["next_question"].lower()
        for k in ["conditions", "medications", "allergies"]
    )


def test_explicit_negative_answers_allow_completion(engine):
    """
    Verifies that explicit negative answers ('no conditions', 'no medications', 'no allergies')
    count as collected information and allow clean completion with appropriate reporting.
    """
    session_id = "S_NEG_01"
    # Turn 1
    engine.start_consultation(patient_id="P002", initial_message="I have a migraine.", session_id=session_id)
    # Turn 2
    engine.process_message(session_id=session_id, patient_message="On the left temple, throbbing.")
    # Turn 3
    engine.process_message(session_id=session_id, patient_message="Since yesterday.")
    # Turn 4
    engine.process_message(session_id=session_id, patient_message="Severity is 7 on 10.")
    # Turn 5
    engine.process_message(session_id=session_id, patient_message="Light sensitivity.")
    # Turn 6: Explicit negative response to medical history/meds/allergies
    t6 = engine.process_message(
        session_id=session_id,
        patient_message="No medical conditions, no medications, and no known allergies.",
    )

    assert t6["conversation_complete"] is True
    assert "prepared" in t6["next_question"].lower() or "thank you" in t6["next_question"].lower()

    report = engine.get_consultation_report(session_id=session_id)
    assert report["medical_history"] == []
    assert report["current_medications"] == []
    assert report["allergies"] == []
    assert "None reported" in report["ai_summary"]
    assert "No known drug allergies reported" in report["ai_summary"]


def test_guardrail_intercepts_premature_llm_completion(monkeypatch):
    """
    Verifies that engine.py intercepts Gemini when it prematurely sets conversation_complete=True
    before essential intake fields (conditions, meds, allergies) are addressed.
    """
    from modules.consultation.gemini_service import GeminiService

    # Create an engine with a mock GeminiService returning premature completion
    engine_with_gemini = ConsultationEngine(gemini_api_key="mock_key_test")

    def mock_premature_turn(history, slots, turn_count):
        return {
            "next_question": "Thank you, I have everything I need. Goodbye!",
            "conversation_complete": True,  # Premature completion attempted by LLM
            "urgency": "routine",
            "extracted_slots": {"severity": 5, "duration": "1 day"},
        }

    monkeypatch.setattr(engine_with_gemini.gemini, "generate_next_turn", mock_premature_turn)

    session_id = "S_LLM_GUARD_01"
    # Turn 1
    engine_with_gemini.start_consultation(
        patient_id="P003", initial_message="I have had a headache for 1 day.", session_id=session_id
    )
    # Turn 2: Patient gives severity, LLM tries to complete immediately
    t2 = engine_with_gemini.process_message(
        session_id=session_id, patient_message="Pain is 5 out of 10."
    )

    # Deterministic guardrail MUST intercept and keep conversation_complete False
    assert t2["conversation_complete"] is False
    assert any(
        k in t2["next_question"].lower()
        for k in ["conditions", "medications", "allergies"]
    )


def test_safety_limit_terminates_conversation_if_uncooperative(engine):
    """
    Verifies that:
    1. Maximum safety limit (8 turns) terminates an uncooperative conversation.
    2. Missing data adheres to standard defaults (null, [], 'Not provided').
    3. Narrative does not falsely claim the patient denied conditions/allergies.
    """
    session_id = "S_SAFETY_01"
    engine.start_consultation(
        patient_id="P_UNCOOP",
        initial_message="Something hurts.",
        session_id=session_id,
    )

    last_res = None
    # Provide evasive / unhelpful answers for 7 more turns (reaching 8 turns total)
    for i in range(2, 9):
        last_res = engine.process_message(
            session_id=session_id,
            patient_message="I don't want to answer that.",
        )

    # Turn 8 must force conversation_complete to True
    assert last_res is not None
    assert last_res["conversation_complete"] is True

    report = engine.get_consultation_report(session_id=session_id)
    # Validate missing data contract
    assert report["severity"] is None
    assert report["temperature"] is None
    assert report["duration"] == "Not provided"
    assert report["medical_history"] == []
    assert report["current_medications"] == []
    assert report["allergies"] == []
    # Verify narrative does NOT claim "None reported" when patient never answered
    assert "Chronic Conditions: Not provided" in report["ai_summary"]
    assert "Active Medications: Not provided" in report["ai_summary"]
    assert "Allergies: Not provided" in report["ai_summary"]


