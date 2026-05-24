"""
Pydantic Schemas
────────────────
Request validation and response serialisation.
Strict constraints catch bad data at the API boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from src.models import Channel, EnquiryStatus


# ── Requests ──────────────────────────────────────────────────────────────────


class CreateEnquiryRequest(BaseModel):
    """Payload for creating a new inbound customer enquiry."""

    customer_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name of the customer.",
        examples=["Sarah Mitchell"],
    )
    channel: Channel = Field(
        ...,
        description="Communication channel: whatsapp | email | call",
        examples=["whatsapp"],
    )
    message: str = Field(
        ...,
        min_length=1,
        description="The inbound customer message.",
        examples=["Hi, I wanted to know about your pricing plans."],
    )


class FollowUpRequest(BaseModel):
    """Payload for scheduling a follow-up."""

    delay_minutes: int = Field(
        ...,
        ge=1,
        le=10080,
        description="Delay in minutes before follow-up (max 7 days).",
        examples=[30],
    )
    message_template: Optional[str] = Field(
        None,
        description="Optional message template. Use {customer_name} as placeholder.",
        examples=["Hi {customer_name}, following up on your enquiry!"],
    )


class EscalateRequest(BaseModel):
    """Payload for escalating an enquiry to a human agent."""

    reason: str = Field(
        ...,
        min_length=1,
        description="Reason for escalation.",
        examples=["Customer is unhappy and demanding a manager."],
    )


# ── Responses ─────────────────────────────────────────────────────────────────


class EnquiryCreatedResponse(BaseModel):
    """Returned immediately after enquiry creation (202 Accepted)."""
    job_id: str = Field(..., description="Unique enquiry ID for tracking.")
    status: str
    message: str

    model_config = {"from_attributes": True}


class StatusEventOut(BaseModel):
    id: str
    status: EnquiryStatus
    note: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class EnquiryHistoryResponse(BaseModel):
    """Full enquiry details with status timeline."""
    id: str
    customer_name: str
    channel: Channel
    message: str
    status: EnquiryStatus
    sop_matched: Optional[str]
    suggested_response: Optional[str]
    escalation_reason: Optional[str]
    follow_up_delay_minutes: Optional[str]
    follow_up_template: Optional[str]
    created_at: datetime
    updated_at: datetime
    timeline: List[StatusEventOut]

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    database: str
    environment: str
    timestamp: datetime
