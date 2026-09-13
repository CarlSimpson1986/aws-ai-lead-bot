import pytest

from src.processing.handler import validate_qualification


def test_valid_hot_result():
    result = {
        "category": "HOT",
        "summary": "Multi-site business with an approved budget and immediate requirement.",
        "reason": "Clear commercial need, budget and buying intent.",
        "confidence": 92
    }

    assert validate_qualification(result) == result


def test_valid_warm_result():
    result = {
        "category": "WARM",
        "summary": "Business is exploring AI automation but has not confirmed budget.",
        "reason": "Relevant need but buying intent is not yet strong.",
        "confidence": 78
    }

    assert validate_qualification(result) == result


def test_valid_cold_result():
    result = {
        "category": "COLD",
        "summary": "General enquiry with no clear commercial requirement.",
        "reason": "No meaningful buying intent or defined project.",
        "confidence": 88
    }

    assert validate_qualification(result) == result


def test_rejects_invalid_category():
    result = {
        "category": "QUALIFIED",
        "summary": "Example",
        "reason": "Example",
        "confidence": 90
    }

    with pytest.raises(ValueError):
        validate_qualification(result)


def test_rejects_confidence_above_100():
    result = {
        "category": "HOT",
        "summary": "Example",
        "reason": "Example",
        "confidence": 101
    }

    with pytest.raises(ValueError):
        validate_qualification(result)


def test_rejects_missing_summary():
    result = {
        "category": "WARM",
        "summary": "",
        "reason": "Example",
        "confidence": 80
    }

    with pytest.raises(ValueError):
        validate_qualification(result)


def test_rejects_missing_reason():
    result = {
        "category": "COLD",
        "summary": "Example",
        "reason": "",
        "confidence": 80
    }

    with pytest.raises(ValueError):
        validate_qualification(result)
