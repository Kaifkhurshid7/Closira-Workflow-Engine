"""
SOP Matcher Unit Tests
──────────────────────
Pure logic tests — no database, no HTTP.
"""

import pytest
from src.sop_matcher import match_sop


def test_matches_pricing_question():
    result = match_sop("Hi, what is the price of your plans?")
    assert result is not None
    assert result[0] == "pricing_question"


def test_matches_booking_enquiry():
    result = match_sop("I'd like to book an appointment please.")
    assert result is not None
    assert result[0] == "booking_enquiry"


def test_matches_complaint():
    result = match_sop("I'm very unhappy with the service I received.")
    assert result is not None
    assert result[0] == "complaint"


def test_matches_after_hours():
    result = match_sop("Are you closed on the weekend?")
    assert result is not None
    assert result[0] == "after_hours"


def test_matches_general_support():
    result = match_sop("I'm having a problem with my account, need help.")
    assert result is not None
    assert result[0] == "general_support"


def test_returns_none_for_no_match():
    result = match_sop("Lalala nothing relevant here xyz123")
    assert result is None


def test_case_insensitive():
    result = match_sop("WHAT IS THE PRICE FOR YOUR SERVICE?")
    assert result is not None
    assert result[0] == "pricing_question"


def test_highest_score_wins():
    """Multiple complaint keywords should beat a single support keyword."""
    result = match_sop("I'm unhappy, disappointed, and angry about this terrible service")
    assert result is not None
    assert result[0] == "complaint"


def test_empty_message():
    assert match_sop("") is None
