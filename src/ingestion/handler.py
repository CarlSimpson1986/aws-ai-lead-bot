import logging
import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


REQUIRED_FIELDS = ["lead_id", "name", "email", "message"]

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def log_event(event_name, **fields):
    payload = {
        "event": event_name,
        **fields
    }
    logger.info(json.dumps(payload))


FIELD_LIMITS = {
    "lead_id": 100,
    "name": 100,
    "email": 254,
    "message": 2000
}

OPTIONAL_FIELD_LIMITS = {
    "company": 200
}


def validate_lead_fields(body):
    errors = {}

    for field, max_length in FIELD_LIMITS.items():
        value = body.get(field)

        if not isinstance(value, str):
            errors[field] = "must be a string"
            continue

        value = value.strip()

        if not value:
            errors[field] = "must not be empty"
            continue

        if len(value) > max_length:
            errors[field] = f"must be {max_length} characters or fewer"

    for field, max_length in OPTIONAL_FIELD_LIMITS.items():
        value = body.get(field)

        if value is None:
            continue

        if not isinstance(value, str):
            errors[field] = "must be a string"
            continue

        value = value.strip()

        if len(value) > max_length:
            errors[field] = f"must be {max_length} characters or fewer"

    email = body.get("email")

    if isinstance(email, str) and email.strip():
        email = email.strip()

        if "@" not in email or email.startswith("@") or email.endswith("@"):
            errors["email"] = "must be a valid email address"

    return errors


def lambda_handler(event, context):
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(os.environ["TABLE_NAME"])

    sqs = boto3.client("sqs")
    queue_url = os.environ["QUEUE_URL"]

    try:
        log_event("request_received", request_id=getattr(context, "aws_request_id", None))
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
            log_event("validation_failed", reason="missing_fields", fields=missing_fields)
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Missing required fields",
                    "fields": missing_fields
                })
            }

        validation_errors = validate_lead_fields(body)

        if validation_errors:
            log_event(
                "validation_failed",
                reason="invalid_fields",
                fields=list(validation_errors.keys())
            )
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Invalid fields",
                    "fields": validation_errors
                })
            }

        log_event("validation_passed")

        lead_id = body["lead_id"].strip()
        created_at = datetime.now(timezone.utc).isoformat()

        lead = {
            "lead_id": lead_id,
            "name": body["name"],
            "email": body["email"],
            "message": body["message"],
            "status": "PENDING",
            "created_at": created_at
        }

        if body.get("company"):
            lead["company"] = body["company"].strip()

        duplicate = False

        try:
            table.put_item(
                Item=lead,
                ConditionExpression="attribute_not_exists(lead_id)"
            )
            log_event("lead_persisted", lead_id=lead_id, status="PENDING")

        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

            duplicate = True
            log_event("duplicate_lead_received", lead_id=lead_id)

        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({
                "lead_id": lead_id
            })
        )

        log_event("lead_enqueued", lead_id=lead_id)

        return {
            "statusCode": 202,
            "body": json.dumps({
                "message": (
                    "Existing lead accepted for safe reprocessing"
                    if duplicate
                    else "Lead accepted for processing"
                ),
                "lead_id": lead_id,
                "status": "PENDING",
                "duplicate": duplicate
            })
        }

    except (json.JSONDecodeError, ValueError):
        log_event("validation_failed", reason="invalid_json")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Invalid JSON request"
            })
        }
