from src.ingestion.handler import validate_lead_fields


def test_valid_lead_fields():
    body = {
        "lead_id": "lead-001",
        "name": "Carl Simpson",
        "email": "admin@myfitpod.co.uk",
        "message": "We need an AI lead qualification system."
    }

    assert validate_lead_fields(body) == {}


def test_company_is_optional():
    body = {
        "lead_id": "lead-002",
        "name": "Carl Simpson",
        "email": "admin@myfitpod.co.uk",
        "message": "We need an AI lead qualification system."
    }

    assert validate_lead_fields(body) == {}


def test_rejects_invalid_email():
    body = {
        "lead_id": "lead-003",
        "name": "Carl Simpson",
        "email": "not-an-email",
        "message": "We need an AI lead qualification system."
    }

    errors = validate_lead_fields(body)

    assert errors["email"] == "must be a valid email address"


def test_rejects_non_string_name():
    body = {
        "lead_id": "lead-004",
        "name": 123,
        "email": "admin@myfitpod.co.uk",
        "message": "We need an AI lead qualification system."
    }

    errors = validate_lead_fields(body)

    assert errors["name"] == "must be a string"


def test_rejects_oversized_message():
    body = {
        "lead_id": "lead-005",
        "name": "Carl Simpson",
        "email": "admin@myfitpod.co.uk",
        "message": "A" * 2001
    }

    errors = validate_lead_fields(body)

    assert errors["message"] == "must be 2000 characters or fewer"


def test_rejects_invalid_lead_id_type():
    body = {
        "lead_id": 123,
        "name": "Carl Simpson",
        "email": "admin@myfitpod.co.uk",
        "message": "We need an AI lead qualification system."
    }

    errors = validate_lead_fields(body)

    assert errors["lead_id"] == "must be a string"
