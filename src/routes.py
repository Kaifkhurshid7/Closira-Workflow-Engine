"""
API Routes
──────────
All endpoint handlers in one module. Kept thin — they validate input,
delegate to the service layer, and format the HTTP response.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db
from src.logger import logger
from src.schemas import (
    CreateEnquiryRequest,
    EnquiryCreatedResponse,
    EnquiryHistoryResponse,
    EscalateRequest,
    FollowUpRequest,
    HealthResponse,
    StatusEventOut,
)
from src.service import (
    create_enquiry,
    escalate_enquiry,
    get_enquiry_with_history,
    schedule_follow_up,
)
from src.worker import process_enquiry

router = APIRouter()


# ── POST /enquiry ─────────────────────────────────────────────────────────────


@router.post(
    "/enquiry",
    response_model=EnquiryCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Enquiry"],
    summary="Create a new inbound enquiry",
    description=(
        "Accepts a customer enquiry from WhatsApp, email, or a phone call. "
        "Returns a job ID immediately — the enquiry is processed asynchronously "
        "in the background where it is matched to an SOP or auto-escalated."
    ),
)
async def create_enquiry_endpoint(
    payload: CreateEnquiryRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> EnquiryCreatedResponse:
    enquiry = await create_enquiry(
        db,
        customer_name=payload.customer_name,
        channel=payload.channel,
        message=payload.message,
    )

    # Queue async SOP classification — runs after response is sent
    background_tasks.add_task(process_enquiry, enquiry.id, payload.message)

    logger.info(
        "Enquiry created",
        extra={"enquiry_id": enquiry.id, "channel": payload.channel, "event": "enquiry_created"},
    )

    return EnquiryCreatedResponse(
        job_id=enquiry.id,
        status=enquiry.status.value,
        message="Enquiry received and queued for processing.",
    )


# ── POST /enquiry/{id}/followup ───────────────────────────────────────────────


@router.post(
    "/enquiry/{enquiry_id}/followup",
    status_code=status.HTTP_200_OK,
    tags=["Enquiry"],
    summary="Schedule a follow-up for an open enquiry",
    description=(
        "Schedules a follow-up action. Accepts a delay in minutes and an "
        "optional message template. Updates status to follow_up_scheduled."
    ),
)
async def schedule_follow_up_endpoint(
    enquiry_id: str,
    payload: FollowUpRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    enquiry = await schedule_follow_up(
        db,
        enquiry_id=enquiry_id,
        delay_minutes=payload.delay_minutes,
        message_template=payload.message_template,
    )
    if not enquiry:
        raise HTTPException(status_code=404, detail=f"Enquiry '{enquiry_id}' not found.")

    logger.info(
        "Follow-up scheduled",
        extra={"enquiry_id": enquiry_id, "delay_minutes": payload.delay_minutes, "event": "follow_up_scheduled"},
    )

    return {
        "enquiry_id": enquiry_id,
        "status": enquiry.status.value,
        "follow_up_in_minutes": payload.delay_minutes,
        "message": "Follow-up scheduled successfully.",
    }


# ── POST /enquiry/{id}/escalate ───────────────────────────────────────────────


@router.post(
    "/enquiry/{enquiry_id}/escalate",
    status_code=status.HTTP_200_OK,
    tags=["Enquiry"],
    summary="Escalate an enquiry to a human agent",
    description=(
        "Marks an enquiry as escalated. Requires a reason field. "
        "Updates status to 'escalated' and appends to the timeline."
    ),
)
async def escalate_enquiry_endpoint(
    enquiry_id: str,
    payload: EscalateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    enquiry = await escalate_enquiry(db, enquiry_id=enquiry_id, reason=payload.reason)
    if not enquiry:
        raise HTTPException(status_code=404, detail=f"Enquiry '{enquiry_id}' not found.")

    logger.info(
        "Enquiry escalated",
        extra={"enquiry_id": enquiry_id, "reason": payload.reason, "event": "escalation_triggered"},
    )

    return {
        "enquiry_id": enquiry_id,
        "status": enquiry.status.value,
        "reason": payload.reason,
        "message": "Enquiry escalated to a human agent.",
    }


# ── GET /enquiry/{id}/history ─────────────────────────────────────────────────


@router.get(
    "/enquiry/{enquiry_id}/history",
    response_model=EnquiryHistoryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Enquiry"],
    summary="Get full conversation history and status timeline",
    description=(
        "Returns all details for a given enquiry: original message, channel, "
        "SOP match result, suggested response, escalation reason, "
        "and a full chronological status timeline."
    ),
)
async def get_history_endpoint(
    enquiry_id: str,
    db: AsyncSession = Depends(get_db),
) -> EnquiryHistoryResponse:
    enquiry = await get_enquiry_with_history(db, enquiry_id)
    if not enquiry:
        raise HTTPException(status_code=404, detail=f"Enquiry '{enquiry_id}' not found.")

    return EnquiryHistoryResponse(
        id=enquiry.id,
        customer_name=enquiry.customer_name,
        channel=enquiry.channel,
        message=enquiry.message,
        status=enquiry.status,
        sop_matched=enquiry.sop_matched,
        suggested_response=enquiry.suggested_response,
        escalation_reason=enquiry.escalation_reason,
        follow_up_delay_minutes=enquiry.follow_up_delay_minutes,
        follow_up_template=enquiry.follow_up_template,
        created_at=enquiry.created_at,
        updated_at=enquiry.updated_at,
        timeline=[
            StatusEventOut(
                id=e.id, status=e.status, note=e.note, created_at=e.created_at,
            )
            for e in enquiry.status_events
        ],
    )


# ── GET /health ───────────────────────────────────────────────────────────────


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="API health check",
    description="Returns API status and database connectivity.",
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unreachable"

    return HealthResponse(
        status="ok",
        database=db_status,
        environment=settings.APP_ENV,
        timestamp=datetime.now(timezone.utc),
    )
