"""
explainer.py
------------
THE LAST STEP. Optional. Build this only after everything else works.

Gemini does NOT decide anything here. Your rule engine has already
decided. Gemini only rewrites the finished alert in warm, plain language
for the patient.

That distinction is your best line in the pitch:
    "The LLM never makes a clinical decision. It writes the explanation
     for a decision our deterministic engine already made and can show
     the source for."

If GEMINI_API_KEY is missing, or Gemini is slow, or the network dies at
the venue, this file falls back to the text already stored in your JSON
datasets. Your demo cannot break because of this file.
"""

import os
import json

# Read the shared key from backend/.env - the SAME key Namita uses.
API_KEY = os.getenv("GEMINI_API_KEY")

MODEL_NAME = "gemini-2.0-flash"

# We only build the client once, not on every request.
_model = None


def _get_model():
    """Create the Gemini client lazily, and only if a key exists."""
    global _model
    if _model is not None:
        return _model
    if not API_KEY:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=API_KEY)
        _model = genai.GenerativeModel(MODEL_NAME)
        return _model
    except Exception:
        # Library not installed, or key rejected. Fall back silently.
        return None


PROMPT = """You are a medication safety communicator for an Indian healthcare app.

A deterministic clinical rules engine has ALREADY verified the safety concerns below.
Do not add, remove, or dispute any concern. Do not introduce new medical claims.
Your only job is to rewrite what is given into plain, calm language.

Patient: {age} year old {gender}
Verified concerns (JSON):
{alerts}

Return ONLY valid JSON, no markdown fences, in this exact shape:
{{
  "summary": "two sentences for the patient about what was found overall",
  "explanations": [
    {{"medicine": "<exact medicine name from input>",
      "title": "<short headline, max 6 words>",
      "patient_friendly": "<2-3 sentences, simple English, no jargon>",
      "action": "<one sentence telling them what to do>"}}
  ]
}}

Rules:
- One entry per concern, in the same order as the input.
- Never tell the patient to stop or start a medicine on their own.
- Always point them back to the prescribing doctor or pharmacist.
- Do not use frightening language. Be factual and reassuring.
"""


def explain(report, patient):
    """
    Add patient-friendly wording to an existing safety report.

    Takes the dict from engine.analyse() and returns the SAME dict with
    two extras: report["summary"] and a "patient_friendly" field on each
    alert. If Gemini is unavailable, the fallback fills these in from
    your dataset text.
    """
    alerts = report.get("alerts", [])

    if not alerts:
        report["summary"] = (
            "No major safety concerns were detected for this prescription "
            "based on the information available."
        )
        return report

    model = _get_model()

    if model is None:
        return _fallback(report)

    # Send Gemini only the minimum it needs. Never send names or IDs.
    slim = [
        {
            "medicine": a["medicine"],
            "severity": a["severity"],
            "category": a["category"],
            "reason": a["reason"],
            "recommendation": a["recommendation"],
        }
        for a in alerts
    ]

    prompt = PROMPT.format(
        age=patient.get("age", "adult"),
        gender=patient.get("gender", "patient"),
        alerts=json.dumps(slim, indent=2),
    )

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Gemini sometimes wraps JSON in ```json fences. Strip them.
        text = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(text)

        report["summary"] = parsed.get("summary", "")

        # Match each explanation back onto its alert, by position
        explanations = parsed.get("explanations", [])
        for i, alert in enumerate(alerts):
            if i < len(explanations):
                e = explanations[i]
                alert["friendly_title"] = e.get("title", alert["title"])
                alert["patient_friendly"] = e.get("patient_friendly", alert["reason"])
                alert["action"] = e.get("action", alert["recommendation"])
            else:
                _fill_from_dataset(alert)

        report["explained_by"] = "gemini"
        return report

    except Exception:
        # Any failure at all - bad JSON, timeout, quota - use the fallback.
        return _fallback(report)


def _fallback(report):
    """No Gemini? Use the text already written in your JSON datasets."""
    for alert in report.get("alerts", []):
        _fill_from_dataset(alert)

    counts = report.get("counts", {})
    report["summary"] = (
        f"{counts.get('total', 0)} safety concern(s) were found in this "
        f"prescription, including {counts.get('high', 0)} that need the "
        f"prescribing doctor's attention before the medicines are taken."
    )
    report["explained_by"] = "rules"
    return report


def _fill_from_dataset(alert):
    alert["friendly_title"] = alert.get("title", "")
    alert["patient_friendly"] = alert.get("reason", "")
    alert["action"] = alert.get("recommendation", "")
