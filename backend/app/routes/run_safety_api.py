"""
run_safety_api.py
-----------------
A tiny standalone server so YOU can test your endpoint before Vaishak's
main.py exists. Not part of the final product - it is your test harness.

Run it from the BharatRx root folder:

    python backend/app/routes/run_safety_api.py

Then open http://127.0.0.1:8000/docs in your browser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.routes.safety import router

app = FastAPI(title="BharatRx Safety Engine (standalone test server)")

# CORS lets Vaishak's React app (running on a different port) call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
