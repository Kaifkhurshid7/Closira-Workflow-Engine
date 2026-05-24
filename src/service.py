"""
Enquiry Service
───────────────
Business logic for enquiry operations.
Keeps route handlers thin — they only deal with HTTP concerns.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import Enquiry, StatusEvent, EnquiryStatus, Channel


async def create_enquiry(
    db: AsyncSession,
    customer_name: str,
    channel: Channel,
    message: str,
) -> Enquiry:
    """Create a new enquiry and its initial 'new' status event."""
    enquiry = Enquiry(
        customer_name=customer_name,
        channel=channel,
        message=message,
        status=EnquiryStatus.new,
    )
    db.add(enquiry)
    await db.flush()  # Get generated ID before creating the event

    event = StatusEvent(
        enquiry_id=enquiry.id,
        status=EnquiryStatus.new,
        note="Enquiry received and queued for processing.",
    )
    db.add(event)
    await db.commit()
    await db.refresh(enquiry)
    return enquiry


async def get_enquiry_with_history(
    db: AsyncSession, enquiry_id: str
) -> Optional[Enquiry]:
    """Fetch enquiry with eager-loaded status timeline (avoids N+1)."""
    result = await db.execute(
        select(Enquiry)
        .options(selectinload(Enquiry.status_events))
        .where(Enquiry.id == enquiry_id)
    )
    return result.scalar_one_or_none()


async def update_enquiry_sop(
    db: AsyncSession,
    enquiry_id: str,
    sop_name: str,
    suggested_response: str,
) -> Optional[Enquiry]:
    """Record SOP match result from background processing."""
    enquiry = await db.get(Enquiry, enquiry_id)
    if not enquiry:
        return None

    enquiry.sop_matched = sop_name
    enquiry.suggested_response = suggested_response
    enquiry.status = EnquiryStatus.sop_matched
    enquiry.updated_at = datetime.now(timezone.utc)

    db.add(StatusEvent(
        enquiry_id=enquiry_id,
        status=EnquiryStatus.sop_matched,
        note=f"SOP matched: {sop_name}",
    ))
    await db.commit()
    await db.refresh(enquiry)
    return enquiry


async def escalate_enquiry(
    db: AsyncSession,
    enquiry_id: str,
    reason: str,
    auto: bool = False,
) -> Optional[Enquiry]:
    """Mark enquiry as escalated (manual or auto when no SOP matches)."""
    enquiry = await db.get(Enquiry, enquiry_id)
    if not enquiry:
        return None

    enquiry.status = EnquiryStatus.escalated
    enquiry.escalation_reason = reason
    enquiry.updated_at = datetime.now(timezone.utc)

    note = f"{'[Auto] ' if auto else ''}Escalated: {reason}"
    db.add(StatusEvent(
        enquiry_id=enquiry_id,
        status=EnquiryStatus.escalated,
        note=note,
    ))
    await db.commit()
    await db.refresh(enquiry)
    return enquiry


async def schedule_follow_up(
    db: AsyncSession,
    enquiry_id: str,
    delay_minutes: int,
    message_template: Optional[str],
) -> Optional[Enquiry]:
    """
    Schedule a follow-up for an enquiry.
    Stores delay + template. Actual sending would need a scheduler in production.
    """
    enquiry = await db.get(Enquiry, enquiry_id)
    if not enquiry:
        return None

    enquiry.status = EnquiryStatus.follow_up_scheduled
    enquiry.follow_up_delay_minutes = str(delay_minutes)
    enquiry.follow_up_template = message_template
    enquiry.updated_at = datetime.now(timezone.utc)

    db.add(StatusEvent(
        enquiry_id=enquiry_id,
        status=EnquiryStatus.follow_up_scheduled,
        note=f"Follow-up scheduled in {delay_minutes} minute(s).",
    ))
    await db.commit()
    await db.refresh(enquiry)
    return enquiry
