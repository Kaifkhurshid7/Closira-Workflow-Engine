"""
ORM Models
──────────
Defines the database schema for enquiries and their status timeline.

Design decisions:
- Human-readable IDs (enq_<8hex>) — easy to spot in logs and API responses
- Append-only StatusEvent table — full audit trail, never lose history
- Denormalised status on Enquiry — fast reads without joining events
- UTC timestamps everywhere — no timezone ambiguity
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.orm import relationship

from src.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────


class Channel(str, enum.Enum):
    whatsapp = "whatsapp"
    email = "email"
    call = "call"


class EnquiryStatus(str, enum.Enum):
    """
    Lifecycle:
      new → processing → sop_matched → resolved
                       ↘ escalated
      new → follow_up_scheduled
      any → escalated (manual)
    """
    new = "new"
    processing = "processing"
    sop_matched = "sop_matched"
    escalated = "escalated"
    follow_up_scheduled = "follow_up_scheduled"
    resolved = "resolved"


# ── Models ────────────────────────────────────────────────────────────────────


class Enquiry(Base):
    __tablename__ = "enquiries"

    id = Column(String(20), primary_key=True, default=lambda: f"enq_{uuid.uuid4().hex[:8]}")
    customer_name = Column(String(255), nullable=False)
    channel = Column(SAEnum(Channel), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(SAEnum(EnquiryStatus), nullable=False, default=EnquiryStatus.new)

    # Populated async by background worker
    sop_matched = Column(String(100), nullable=True)
    suggested_response = Column(Text, nullable=True)

    # Escalation
    escalation_reason = Column(Text, nullable=True)

    # Follow-up
    follow_up_delay_minutes = Column(String(20), nullable=True)
    follow_up_template = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    status_events = relationship(
        "StatusEvent", back_populates="enquiry", order_by="StatusEvent.created_at"
    )

    __table_args__ = (
        Index("ix_enquiries_status", "status"),
        Index("ix_enquiries_created_at", "created_at"),
    )


class StatusEvent(Base):
    """Append-only audit log — every status change is a new row."""
    __tablename__ = "status_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    enquiry_id = Column(String(20), ForeignKey("enquiries.id"), nullable=False)
    status = Column(SAEnum(EnquiryStatus), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    enquiry = relationship("Enquiry", back_populates="status_events")

    __table_args__ = (
        Index("ix_status_events_enquiry", "enquiry_id"),
    )
