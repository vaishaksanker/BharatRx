"""
severity.py
-----------
Turns a pile of individual alerts into ONE overall verdict.

The frontend needs a single headline ("OVERALL RISK: HIGH") plus a
number for the progress bar. That is all this file produces.
"""

# How many points each alert contributes
POINTS = {"HIGH": 30, "MEDIUM": 15, "LOW": 5}


def calculate(alerts):
    """
    Input : list of alert dictionaries
    Output: (overall_risk_string, risk_score_number)
    """
    if not alerts:
        return "LOW", 0

    # Add up the points for every alert
    score = 0
    for alert in alerts:
        score += POINTS.get(alert.get("severity", "LOW"), 5)

    # Cap at 100 so the frontend progress bar never overflows
    score = min(score, 100)

    # Rule: even ONE high-severity alert makes the whole prescription HIGH risk.
    # You never want to average away a penicillin allergy.
    if any(a.get("severity") == "HIGH" for a in alerts):
        overall = "HIGH"
    elif score >= 21:
        overall = "MEDIUM"
    else:
        overall = "LOW"

    return overall, score


def summarise(alerts):
    """Count alerts by severity - handy for the dashboard header."""
    return {
        "high": sum(1 for a in alerts if a.get("severity") == "HIGH"),
        "medium": sum(1 for a in alerts if a.get("severity") == "MEDIUM"),
        "low": sum(1 for a in alerts if a.get("severity") == "LOW"),
        "total": len(alerts),
    }
