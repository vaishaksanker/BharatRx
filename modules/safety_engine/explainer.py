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
import urllib.request
import urllib.error
import time

# Read the key from backend/.env - loaded by the server at startup.
API_KEY = os.getenv("GEMINI_API_KEY")

# gemini-2.5-flash is the current free-tier workhorse. Change here if
# Google renames it; nothing else in the file references the model.
# Models are tried IN ORDER. If one returns 503 (high demand) we move to
# the next rather than giving up. Flash-lite models are less popular and
# therefore less likely to be overloaded, so they sit near the top.
#
# Check what your key can access with:
#   GET https://generativelanguage.googleapis.com/v1beta/models
MODEL_CHAIN = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
]

# Kept for backwards compatibility - some code may still read this.
MODEL_NAME = MODEL_CHAIN[0]

API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

# Per-attempt timeout. Total worst case is roughly
# TIMEOUT_SECONDS x len(MODEL_CHAIN), so keep this modest.
TIMEOUT_SECONDS = 20

# How many times to retry the SAME model on a 503 before moving on.
RETRIES_PER_MODEL = 2


def _post(model, prompt):
    """One HTTP call to one model. Raises on any failure."""
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3},
    }).encode("utf-8")

    request = urllib.request.Request(
        API_URL.format(model=model),
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": API_KEY,
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return payload["candidates"][0]["content"]["parts"][0]["text"]


def _call_gemini(prompt, verbose=False):
    """
    Try each model in MODEL_CHAIN until one answers.

    Why a chain: Google returns 503 "experiencing high demand" on popular
    models at busy times. That is not our bug and not our key - it is
    queueing. Rather than fail, we ask a less busy model the same question.

    Uses urllib from the standard library rather than an SDK, because
    Google deprecated google.generativeai and SDKs keep changing. The
    REST endpoint does not.

    Raises only if EVERY model fails. The caller then falls back to our
    own dataset wording.
    """
    if not API_KEY:
        raise RuntimeError("no api key")

    last_error = None

    for model in MODEL_CHAIN:
        for attempt in range(RETRIES_PER_MODEL):
            try:
                if verbose:
                    print(f"  trying {model} (attempt {attempt + 1})...")
                return _post(model, prompt)

            except urllib.error.HTTPError as err:
                last_error = f"{model}: HTTP {err.code}"
                if verbose:
                    print(f"    -> HTTP {err.code}")
                # 503 = overloaded, worth retrying. Anything else is a
                # real problem with this model, so move on immediately.
                if err.code != 503:
                    break
                time.sleep(1.5 * (attempt + 1))   # brief backoff

            except Exception as err:
                last_error = f"{model}: {type(err).__name__}"
                if verbose:
                    print(f"    -> {type(err).__name__}")
                break      # timeout or network issue - try the next model

    raise RuntimeError(f"all models failed (last: {last_error})")


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

    if not API_KEY:
        return _fallback(report)

    # Send Gemini only the minimum it needs. Never send patient names or IDs.
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
        text = _call_gemini(prompt).strip()

        # Gemini sometimes wraps JSON in ```json fences. Strip them.
        text = text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(text)

        report["summary"] = parsed.get("summary", "")

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
        # Any failure at all - no key, no network, timeout, quota exhausted,
        # malformed JSON - falls through to our own dataset wording.
        # The demo cannot be killed by this file.
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
