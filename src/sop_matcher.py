"""
SOP Matching Engine
───────────────────
Classifies inbound customer messages into Standard Operating Procedures
using keyword-based matching. No AI required — simple, fast, transparent.

Matching strategy:
  1. Normalise message to lowercase
  2. For each SOP, count how many of its keywords appear in the message
  3. Highest-scoring SOP wins (first-match tiebreaker via catalog order)
  4. If nothing matches → return None → triggers auto-escalation

Why keyword-based?
  - Transparent: every decision is explainable and auditable
  - Fast: sub-millisecond, no external calls
  - Extensible: add a new SOP by appending a dict to the catalog
  - Production path: swap in embeddings or a classifier later
"""

from typing import Optional, Tuple

# ── SOP Catalog ───────────────────────────────────────────────────────────────
# Each SOP defines trigger keywords and a suggested response template.
# In production this would live in a database for runtime updates.

SOP_CATALOG: list[dict] = [
    {
        "name": "booking_enquiry",
        "keywords": [
            "book", "appointment", "schedule", "reserve",
            "slot", "reservation", "availability",
        ],
        "response": (
            "Thank you for reaching out! We'd be happy to assist you with booking. "
            "Could you please share your preferred date and time? "
            "Our team will confirm availability shortly."
        ),
    },
    {
        "name": "pricing_question",
        "keywords": [
            "price", "cost", "fee", "quote", "charge",
            "how much", "rate", "pricing", "plan", "subscription",
        ],
        "response": (
            "Great question! Our pricing depends on the package you choose. "
            "We have options starting from ₹999/month. "
            "Would you like me to send you a detailed pricing breakdown?"
        ),
    },
    {
        "name": "complaint",
        "keywords": [
            "complaint", "unhappy", "disappointed", "refund",
            "angry", "poor", "bad", "worst", "terrible", "awful",
        ],
        "response": (
            "We're truly sorry to hear about your experience. "
            "This is not the standard we hold ourselves to. "
            "A senior team member will reach out to you within 2 hours to resolve this."
        ),
    },
    {
        "name": "after_hours",
        "keywords": [
            "closed", "after hours", "tonight", "weekend",
            "holiday", "open now", "open today", "working hours",
        ],
        "response": (
            "Thanks for reaching out! Our office hours are Mon–Sat, 9 AM to 6 PM. "
            "We've noted your enquiry and will get back to you first thing when we reopen. "
            "For urgent matters, please email support@closira.com."
        ),
    },
    {
        "name": "general_support",
        "keywords": [
            "help", "support", "issue", "problem",
            "not working", "broken", "error", "bug", "fix",
        ],
        "response": (
            "We're here to help! Could you describe the issue in a bit more detail? "
            "Our support team will review and get back to you within 4 business hours."
        ),
    },
]


def match_sop(message: str) -> Optional[Tuple[str, str]]:
    """
    Match a message to the best-fit SOP.

    Returns:
        (sop_name, suggested_response) if matched, else None.

    The highest keyword-hit-count wins. If no keyword matches at all,
    returns None — the caller should escalate.
    """
    lowered = message.lower()
    best_match: Optional[Tuple[str, str]] = None
    best_score = 0

    for sop in SOP_CATALOG:
        score = sum(1 for kw in sop["keywords"] if kw in lowered)
        if score > best_score:
            best_score = score
            best_match = (sop["name"], sop["response"])

    return best_match
