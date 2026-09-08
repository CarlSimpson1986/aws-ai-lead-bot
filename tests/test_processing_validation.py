from src.processing.handler import validate_qualification, should_notify


def test_valid_qualified_result():
    result = {
        "score": 85,
        "decision": "QUALIFIED",
        "reason": "Clear commercial AI requirement"
    }

    assert validate_qualification(result) == result
    assert should_notify(result) is True


def test_valid_unqualified_result():
    result = {
        "score": 40,
        "decision": "UNQUALIFIED",
        "reason": "Insufficient commercial intent"
    }

    assert validate_qualification(result) == result
    assert should_notify(result) is False


def test_rejects_score_above_100():
    result = {
        "score": 101,
        "decision": "QUALIFIED",
        "reason": "Invalid score"
    }

    try:
        validate_qualification(result)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "Invalid qualification score"


def test_rejects_qualified_below_threshold():
    result = {
        "score": 60,
        "decision": "QUALIFIED",
        "reason": "Threshold mismatch"
    }

    try:
        validate_qualification(result)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "QUALIFIED decision requires score >= 70"


def test_rejects_unqualified_above_threshold():
    result = {
        "score": 80,
        "decision": "UNQUALIFIED",
        "reason": "Threshold mismatch"
    }

    try:
        validate_qualification(result)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "UNQUALIFIED decision requires score < 70"
