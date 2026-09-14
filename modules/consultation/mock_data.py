"""
Synthetic test patients, conversations, and demo fixtures for BharatRx.
Used for offline evaluation, hackathon demonstrations, and contract verification.
DOES NOT contain any real patient data.
"""

MOCK_DEMO_SCENARIOS = {
    "headache_routine": {
        "scenario_name": "Moderate Tension/Migraine Headache",
        "patient": {
            "patient_id": "P001",
            "name": "Ramesh Kumar",
            "age": 42,
            "sex": "M",
        },
        "initial_message": "I have had a throbbing headache since yesterday morning.",
        "responses": [
            "It is mostly in my forehead and temples, throbbing pain.",
            "Since yesterday, started gradually.",
            "It is about 6 out of 10 in severity.",
            "I feel mildly nauseous and bright lights bother my eyes.",
            "I have mild hypertension and take Telmisartan 40mg OD. No known drug allergies.",
        ],
        "expected_slots": {
            "chief_complaint": "I have had a throbbing headache since yesterday morning.",
            "duration": "1 day",
            "severity": 6,
            "conditions": ["Hypertension"],
            "current_medications": [{"name": "Telmisartan", "dose": "40 mg", "frequency": "OD"}],
            "allergies": [],
            "urgency": "routine",
        },
    },
    "fever_routine": {
        "scenario_name": "Acute Viral Fever with Body Aches",
        "patient": {
            "patient_id": "P002",
            "name": "Ananya Sharma",
            "age": 28,
            "sex": "F",
        },
        "initial_message": "I am having high fever and severe shivering for the past 2 days.",
        "responses": [
            "2 days now, and my temperature was 101.5 F when I checked.",
            "Severity is about 7 on 10, feeling very weak with chills and body ache.",
            "Yes, I have a dry cough and throat irritation.",
            "I took Dolo 650 SOS. No chronic diseases, no known allergies.",
        ],
        "expected_slots": {
            "duration": "2 days",
            "severity": 7,
            "temperature": 101.5,
            "current_medications": [{"name": "Dolo 650", "dose": "650 mg", "frequency": "SOS"}],
            "urgency": "routine",
        },
    },
    "stomach_pain_routine": {
        "scenario_name": "Epigastric Gastric Pain",
        "patient": {
            "patient_id": "P003",
            "name": "Suresh Nair",
            "age": 55,
            "sex": "M",
        },
        "initial_message": "I have a burning stomach pain in the upper abdomen.",
        "responses": [
            "It is in the upper belly, burning type of sensation.",
            "Started 1 day ago, severity is 5 out of 10.",
            "It gets slightly worse after eating spicy food, no vomiting.",
            "I have acid reflux (GERD) and take Pantoprazole 40mg OD. Allergic to Sulfa drugs.",
        ],
        "expected_slots": {
            "duration": "1 day",
            "severity": 5,
            "conditions": ["GERD"],
            "allergies": ["Sulfa drugs"],
            "current_medications": [{"name": "Pantoprazole", "dose": "40 mg", "frequency": "OD"}],
            "urgency": "routine",
        },
    },
    "skin_rash_routine": {
        "scenario_name": "Pruritic Allergic Skin Rash",
        "patient": {
            "patient_id": "P004",
            "name": "Priya Patel",
            "age": 34,
            "sex": "F",
        },
        "initial_message": "I have developed an itchy red rash on both my arms.",
        "responses": [
            "On both forearms, red and bumpy spots.",
            "Appeared yesterday, very itchy.",
            "No fever or face swelling, started a new laundry detergent 3 days ago.",
            "No chronic illnesses. I am allergic to Penicillin.",
        ],
        "expected_slots": {
            "allergies": ["Penicillin"],
            "urgency": "routine",
        },
    },
    "urgent_red_flag_headache": {
        "scenario_name": "Acute Thunderclap Headache with High Pain",
        "patient": {
            "patient_id": "P005",
            "name": "Vikram Singh",
            "age": 60,
            "sex": "M",
        },
        "initial_message": "This is the worst headache of my life, sudden onset chest pressure and blurriness.",
        "responses": [
            "Sudden explosion of pain, 10 out of 10 severity.",
        ],
        "expected_slots": {
            "severity": 10,
            "urgency": "urgent",
        },
    },
}
