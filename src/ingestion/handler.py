import json

REQUIRED_FIELDS = ["name", "email", "company", "message"]


def lambda_handler(event, context):
    try:
        body = event.get("body", event)

        if isinstance(body, str):
            body = json.loads(body)

        if not isinstance(body, dict):
            raise ValueError("Request body must be a JSON object")

        missing_fields = [
            field
            for field in REQUIRED_FIELDS
            if not body.get(field)
        ]

        if missing_fields:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Missing required fields",
                    "fields": missing_fields
                })
            }

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Lead payload is valid"
            })
        }

    except (json.JSONDecodeError, ValueError):
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Invalid JSON request"
            })
        }
