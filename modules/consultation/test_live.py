import json

from modules.consultation.engine import ConsultationEngine


# Create consultation engine
engine = ConsultationEngine(force_mock=True)


# --------------------------------------------------
# STEP 1: Start BharatRx consultation with greeting
# --------------------------------------------------

start = engine.start_consultation(
    patient_id="P001",
    initial_message=""
)

session_id = start["session_id"]

print("\n--- CONSULTATION STARTED ---")
print("BharatRx:", start["next_question"])


# --------------------------------------------------
# STEP 2: Patient tells the main problem
# --------------------------------------------------

initial_message = (
    "I have had a throbbing headache since yesterday morning."
)

print("\nPatient:", initial_message)

result = engine.process_message(
    session_id=session_id,
    patient_message=initial_message
)

print("BharatRx:", result["next_question"])


# --------------------------------------------------
# STEP 3: Patient responses
# --------------------------------------------------

responses = [
    "It is mostly in my forehead and temples.",
    "It started yesterday morning and came gradually.",
    "The pain is 6 out of 10.",
    "I feel mildly nauseous and bright lights bother my eyes.",
    "I do not have any medical conditions.",
    "I am not taking any medicines.",
    "I have no known allergies."
]


# --------------------------------------------------
# STEP 4: Process consultation responses
# --------------------------------------------------

for answer in responses:

    result = engine.process_message(
        session_id=session_id,
        patient_message=answer
    )

    print("\nPatient:", answer)
    print("BharatRx:", result["next_question"])

    if result["conversation_complete"]:

        print("\n--- CONSULTATION COMPLETE ---")

        break


# --------------------------------------------------
# STEP 5: Generate doctor consultation report
# --------------------------------------------------

report = engine.get_consultation_report(
    session_id=session_id
)

print("\n--- DOCTOR CONSULTATION REPORT ---")

print(
    json.dumps(
        report,
        indent=2
    )
)