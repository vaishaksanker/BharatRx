"""
backend/app/routes/safety.py
----------------------------
Your API endpoint. This is the ONLY file Vaishak needs to know about.

He does not import your Python. He calls:

    POST http://localhost:8000/api/safety-check

Everything else in your module is invisible to him. That is the whole
point of the contract - you can rewrite your checkers all you like and
his React code never changes.
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# PATH BOOTSTRAP - important, do not delete.
#
# This file lives at  BharatRx/backend/app/routes/safety.py
# but it needs to import  BharatRx/modules/safety_engine.
#
# If uvicorn is started from inside backend/ (which is common), Python will
# not know where BharatRx/ is, and the import below fails with
# "ModuleNotFoundError: No module named 'modules'".
#
# These three lines add the BharatRx root folder to Python's search path,
# so the import works no matter which folder the server was started from.
# parents[0]=routes  [1]=app  [2]=backend  [3]=BharatRx
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# ---------------------------------------------------------------------------

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional, Any

from modules.safety_engine import analyse
from modules.safety_engine.explainer import explain

# A router is a group of related endpoints. main.py will plug this in.
router = APIRouter(prefix="/api", tags=["Safety Engine"])


# ---------------------------------------------------------------------------
# REQUEST SHAPE
# Pydantic checks incoming JSON for you. If Vaishak sends age as "sixty",
# FastAPI rejects it with a clear error instead of your engine crashing.
# ---------------------------------------------------------------------------

class Patient(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    pregnant: bool = False
    diseases: List[str] = Field(default_factory=list)
    allergies: List[Any] = Field(default_factory=list)   # str or dict both accepted
    current_medicines: List[str] = Field(default_factory=list)


class SafetyRequest(BaseModel):
    patient: Patient
    prescription: List[str] = Field(default_factory=list)
    explain_with_ai: bool = True      # frontend can turn Gemini off for speed


# ---------------------------------------------------------------------------
# THE ENDPOINT
# ---------------------------------------------------------------------------

@router.post("/safety-check")
def safety_check(request: SafetyRequest):
    """
    Receive patient + prescription, return the full safety report.

    This function is deliberately tiny. All it does is:
      1. convert the validated request back into plain dicts
      2. call your engine
      3. optionally add Gemini wording
      4. return it
    """
    patient = request.patient.model_dump()      # Pydantic object -> plain dict

    report = analyse(patient, request.prescription)

    if request.explain_with_ai:
        report = explain(report, patient)

    return report


@router.get("/safety-check/health")
def health():
    """Quick check that the module loaded. Useful during integration."""
    from modules.safety_engine.utils import (
        DRUG_INTERACTIONS, DISEASE_RULES, BRAND_GENERIC
    )
    return {
        "status": "ok",
        "module": "safety_engine",
        "interaction_pairs": sum(
            len(v) for k, v in DRUG_INTERACTIONS.items() if not k.startswith("_")
        ),
        "disease_rules": len([k for k in DISEASE_RULES if not k.startswith("_")]),
        "brands_mapped": len([k for k in BRAND_GENERIC if not k.startswith("_")]),
    }
