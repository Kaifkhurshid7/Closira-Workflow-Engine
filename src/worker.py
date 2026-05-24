"""
Background Worker: Enquiry Processor
─────────────────────────────────────
Triggered after a new enquiry is created. Runs inside FastAPI's
BackgroundTasks — same process, no broker needed.

Flow:
  1. Open a fresh DB session (background tasks run after response is sent,
     so the request session is already closed)
  2. Match message to SOP using keyword logic
  3. If matched → update enquiry with SOP name + suggested response
  4. If no match → auto-escalate and log the event
"""

import src.database as _db_module
from src.sop_matcher import match_sop
from src.service import update_enquiry_sop, escalate_enquiry
from src.logger import logger


async def process_enquiry(enquiry_id: str, message: str) -> None:
    """
    Classify an enquiry asynchronously and update its status.
    Designed to be passed to BackgroundTasks.add_task().
    """
    logger.info(
        "Background task started",
        extra={"enquiry_id": enquiry_id, "event": "task_started"},
    )

    # Resolve session factory at call time — allows test patching
    session_factory = _db_module.AsyncSessionLocal

    async with session_factory() as db:
        result = match_sop(message)

        if result:
            sop_name, suggested_response = result
            await update_enquiry_sop(db, enquiry_id, sop_name, suggested_response)
            logger.info(
                "SOP matched",
                extra={"enquiry_id": enquiry_id, "sop": sop_name, "event": "sop_matched"},
            )
        else:
            # No SOP matched — escalate so no enquiry is silently dropped
            await escalate_enquiry(
                db, enquiry_id,
                reason="No SOP matched for inbound message. Requires human review.",
                auto=True,
            )
            logger.warning(
                "No SOP matched — auto-escalated",
                extra={"enquiry_id": enquiry_id, "event": "escalation_triggered"},
            )
