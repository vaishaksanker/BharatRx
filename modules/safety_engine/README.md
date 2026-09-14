# Safety Engine — Module 3 (Sidharth)

Rule-based medication safety checker. Deterministic decisions, optional LLM wording.

## Contract for the frontend

**`POST /api/safety-check`**

Request:
```json
{
  "patient": {
    "age": 71, "gender": "Female", "pregnant": false,
    "diseases": ["Diabetes", "Kidney Disease"],
    "allergies": ["Sulfa"],
    "current_medicines": ["Glycomet 500", "Losartan"]
  },
  "prescription": ["Voveran", "Septran DS"],
  "explain_with_ai": true
}
```

Response:
```json
{
  "overall_risk": "HIGH",
  "risk_score": 100,
  "summary": "...",
  "counts": { "high": 3, "medium": 1, "low": 0, "total": 4 },
  "medicines": [
    { "name": "Voveran", "severity": "HIGH", "concern_count": 3, "status": "3 concern(s) detected" }
  ],
  "alerts": [
    {
      "medicine": "Septran DS",
      "generic": "Cotrimoxazole",
      "severity": "HIGH",
      "category": "Allergy",
      "title": "Sulfa allergy alert",
      "reason": "...",
      "recommendation": "...",
      "triggered_by": "Sulfa",
      "patient_friendly": "...",
      "action": "..."
    }
  ]
}
```

`severity` is always one of `HIGH` / `MEDIUM` / `LOW`.
`overall_risk` uses the same three values. **This contract will not change.**

## Colour mapping for the dashboard
| severity | colour |
|---|---|
| HIGH | red |
| MEDIUM | amber |
| LOW | green |

## The five checks
1. **Drug–Drug** — new medicine vs current medicines (46 pairs)
2. **Drug–Disease** — medicine vs patient's conditions
3. **Allergy** — direct family match + cross-reactivity (penicillin → cephalosporin)
4. **Duplicate therapy** — brand→generic normalisation catches Dolo + Combiflam
5. **Patient context** — age thresholds and pregnancy

## Run the tests
From the repo root:
```bash
python -m modules.safety_engine.test_engine
```

## Notes
- Gemini is used **only** to reword alerts the rule engine already produced.
- If `GEMINI_API_KEY` is absent or the call fails, the module falls back to dataset text. The demo cannot break because of the LLM.
- Uses the same shared key as Namita: `GEMINI_API_KEY` in `backend/.env`.
