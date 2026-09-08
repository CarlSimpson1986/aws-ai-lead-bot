from src.ingestion.handler import validate_lead_fields


def test_valid_lead_fields():
    body = {
        "name": "Carl Simpson",
        "email": "admin@myfitpod.co.uk",
        "company": "My Fit Pod Franchise Ltd",
        "message": "We need an AI lead qualification system."
    }

    assert validate_lead_fields(body) == {}


def test_rejects_invalid_email():
    body = {
        "name": "Carl Simpson",
        "email": "not-an-email",
        "company": "My Fit Pod Franchise Ltd",
        "message": "We need an AI lead qualification system."
    }

    errors = validate_lead_fields(body)

    assert errors["email"] == "must be a valid email address"


def test_rejects_non_string_name():
    body = {
        "name": 123,
        "email": "admin@myfitpod.co.uk",
        "company": "My Fit Pod Franchise Ltd",
        "message": "We need an AI lead qualification system."
    }

    errors = validate_lead_fields(body)

    assert errors["name"] == "must be a string"


def test_rejects_oversized_message():
    body = {
        "name": "Carl Simpson",
        "email": "admin@myfitpod.co.uk",
        "company": "My Fit Pod Franchise Ltd",
        "message": "A" * 2001
    }

    errors = validate_lead_fields(body)

    assert errors["message"] == "must be 2000 characters or fewer"
