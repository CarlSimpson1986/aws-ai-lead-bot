import os
from unittest.mock import MagicMock, patch

from src.retrieval.handler import lambda_handler


def test_returns_400_when_lead_id_missing():
    event = {"pathParameters": None}

    response = lambda_handler(event, None)

    assert response["statusCode"] == 400


@patch.dict(os.environ, {"TABLE_NAME": "ai-lead-qualification-leads"})
@patch("src.retrieval.handler.boto3.resource")
def test_returns_404_when_lead_not_found(mock_resource):
    table = MagicMock()
    table.get_item.return_value = {}
    mock_resource.return_value.Table.return_value = table

    event = {
        "pathParameters": {
            "lead_id": "lead-404"
        }
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 404


@patch.dict(os.environ, {"TABLE_NAME": "ai-lead-qualification-leads"})
@patch("src.retrieval.handler.boto3.resource")
def test_returns_qualification_without_pii(mock_resource):
    table = MagicMock()
    table.get_item.return_value = {
        "Item": {
            "lead_id": "lead-001",
            "name": "Carl Simpson",
            "email": "private@example.com",
            "message": "Sensitive lead message",
            "status": "HOT",
            "qualification_category": "HOT",
            "qualification_summary": "Business has an immediate AI requirement.",
            "qualification_reason": "Strong buying intent.",
            "qualification_confidence": 94
        }
    }
    mock_resource.return_value.Table.return_value = table

    event = {
        "pathParameters": {
            "lead_id": "lead-001"
        }
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 200
    assert '"category": "HOT"' in response["body"]
    assert '"confidence": 94' in response["body"]
    assert "private@example.com" not in response["body"]
    assert "Sensitive lead message" not in response["body"]
