"""
FastAPI REST API routes for BharatRx Pre-Consultation AI Module.
Implements POST /api/consultation/message and POST /api/consultation/report
strictly conforming to docs/integration.md contracts and error responses.
"""

from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .engine import ConsultationEngine
from .schemas import (
    ConsultationMessageRequest,
    ConsultationMessageResponse,
    ConsultationReport,
    ConsultationReportRequest,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
)

# Global in-memory engine instance
consultation_engine = ConsultationEngine()

router = APIRouter(prefix="/api/consultation", tags=["Consultation"])


@router.post(
    "/message",
    response_model=ConsultationMessageResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def process_consultation_message(payload: ConsultationMessageRequest):
    """
    Interactive intake endpoint.
    Receives patient message, returns the next adaptive question and urgency status.
    """
    try:
        result = consultation_engine.process_message(
            session_id=payload.session_id,
            patient_message=payload.message,
            patient_id=payload.patient_id,
        )
        return ConsultationMessageResponse(**result)
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": ErrorCode.INVALID_REQUEST.value,
                    "message": str(ve),
                },
            },
        )
    except Exception as ex:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": ErrorCode.MODULE_ERROR.value,
                    "message": f"Error processing consultation turn: {str(ex)}",
                },
            },
        )


@router.post(
    "/report",
    response_model=ConsultationReport,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_consultation_report(payload: ConsultationReportRequest):
    """
    Structured report endpoint.
    Retrieves the clinical intake report and doctor review questions.
    """
    try:
        report_data = consultation_engine.get_consultation_report(session_id=payload.session_id)
        # Verify patient_id matches session
        if report_data.get("patient_id") != payload.patient_id:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "success": False,
                    "error": {
                        "code": ErrorCode.PATIENT_NOT_FOUND.value,
                        "message": f"Patient '{payload.patient_id}' does not match session '{payload.session_id}'.",
                    },
                },
            )
        return ConsultationReport(**report_data)
    except ValueError as ve:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": ErrorCode.PATIENT_NOT_FOUND.value,
                    "message": str(ve),
                },
            },
        )
    except Exception as ex:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": ErrorCode.MODULE_ERROR.value,
                    "message": f"Error generating consultation report: {str(ex)}",
                },
            },
        )


def create_app() -> FastAPI:
    """Factory creating standalone FastAPI application with standard BharatRx error handlers."""
    app = FastAPI(
        title="BharatRx Pre-Consultation AI Module",
        description="Standalone AI Pre-Consultation service for BharatRx clinical platform.",
        version="1.0.0",
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        first_error = exc.errors()[0] if exc.errors() else {}
        loc = " -> ".join([str(l) for l in first_error.get("loc", [])])
        msg = first_error.get("msg", "Validation error")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": ErrorCode.INVALID_REQUEST.value,
                    "message": f"Invalid field '{loc}': {msg}",
                },
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        code = ErrorCode.INVALID_REQUEST.value if exc.status_code == 400 else ErrorCode.MODULE_ERROR.value
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": code,
                    "message": exc.detail,
                },
            },
        )

    app.include_router(router)
    return app


app = create_app()
