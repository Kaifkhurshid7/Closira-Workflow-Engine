"""
API Endpoint Tests
──────────────────
Integration tests covering all 5 endpoints with happy paths and edge cases.
"""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_create_enquiry_returns_202(client):
    response = await client.post(
        "/enquiry",
        json={
            "customer_name": "Sarah Mitchell",
            "channel": "whatsapp",
            "message": "Hi, I wanted to know about your pricing plans.",
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "new"
    assert data["job_id"].startswith("enq_")


@pytest.mark.asyncio
async def test_create_enquiry_invalid_channel(client):
    response = await client.post(
        "/enquiry",
        json={"customer_name": "John", "channel": "telegram", "message": "Hello"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_enquiry_missing_fields(client):
    response = await client.post("/enquiry", json={"customer_name": "John"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_enquiry_empty_message(client):
    response = await client.post(
        "/enquiry",
        json={"customer_name": "John", "channel": "email", "message": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_history(client):
    create_resp = await client.post(
        "/enquiry",
        json={
            "customer_name": "Ravi Kumar",
            "channel": "email",
            "message": "I have a complaint about my recent order.",
        },
    )
    enquiry_id = create_resp.json()["job_id"]

    history_resp = await client.get(f"/enquiry/{enquiry_id}/history")
    assert history_resp.status_code == 200

    data = history_resp.json()
    assert data["id"] == enquiry_id
    assert data["customer_name"] == "Ravi Kumar"
    assert data["channel"] == "email"
    assert len(data["timeline"]) >= 1
    assert data["timeline"][0]["status"] == "new"


@pytest.mark.asyncio
async def test_get_history_not_found(client):
    response = await client.get("/enquiry/enq_doesnotexist/history")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_escalate_enquiry(client):
    create_resp = await client.post(
        "/enquiry",
        json={
            "customer_name": "Priya Sharma",
            "channel": "call",
            "message": "I need urgent help with my account.",
        },
    )
    enquiry_id = create_resp.json()["job_id"]

    escalate_resp = await client.post(
        f"/enquiry/{enquiry_id}/escalate",
        json={"reason": "Customer demands immediate callback."},
    )
    assert escalate_resp.status_code == 200
    data = escalate_resp.json()
    assert data["status"] == "escalated"
    assert data["enquiry_id"] == enquiry_id


@pytest.mark.asyncio
async def test_escalate_not_found(client):
    response = await client.post(
        "/enquiry/enq_missing/escalate", json={"reason": "Some reason"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_schedule_followup(client):
    create_resp = await client.post(
        "/enquiry",
        json={
            "customer_name": "Amit Joshi",
            "channel": "whatsapp",
            "message": "Can you help me book an appointment?",
        },
    )
    enquiry_id = create_resp.json()["job_id"]

    followup_resp = await client.post(
        f"/enquiry/{enquiry_id}/followup",
        json={"delay_minutes": 30, "message_template": "Hi {customer_name}, following up!"},
    )
    assert followup_resp.status_code == 200
    data = followup_resp.json()
    assert data["status"] == "follow_up_scheduled"
    assert data["follow_up_in_minutes"] == 30


@pytest.mark.asyncio
async def test_schedule_followup_not_found(client):
    response = await client.post(
        "/enquiry/enq_missing/followup", json={"delay_minutes": 15}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_escalate_updates_timeline(client):
    create_resp = await client.post(
        "/enquiry",
        json={
            "customer_name": "Neha Verma",
            "channel": "email",
            "message": "I'm very disappointed with your service.",
        },
    )
    enquiry_id = create_resp.json()["job_id"]

    await client.post(
        f"/enquiry/{enquiry_id}/escalate", json={"reason": "Repeated complaint."}
    )

    history = await client.get(f"/enquiry/{enquiry_id}/history")
    data = history.json()
    statuses = [e["status"] for e in data["timeline"]]
    assert "escalated" in statuses


@pytest.mark.asyncio
async def test_followup_invalid_delay_zero(client):
    create_resp = await client.post(
        "/enquiry",
        json={"customer_name": "Test", "channel": "whatsapp", "message": "Hello"},
    )
    enquiry_id = create_resp.json()["job_id"]

    response = await client.post(
        f"/enquiry/{enquiry_id}/followup", json={"delay_minutes": 0}
    )
    assert response.status_code == 422
