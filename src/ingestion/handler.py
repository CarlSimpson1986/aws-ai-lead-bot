import logging
import json
import os
import uuid
from datetime import datetime, timezone

import boto3


REQUIRED_FIELDS = ["name", "email", "company", "message"]

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def log_event(event_name, **fields):
    payload = {
        "event": event_name,
        **fields
    }
    logger.info(json.dumps(payload))


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

sqs = boto3.client("sqs")
queue_url = os.environ["QUEUE_URL"]


def lambda_handler(event, context):
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

        log_event("validation_passed")

        lead_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        lead = {
            "lead_id": lead_id,
            "name": body["name"],
            "email": body["email"],
            "company": body["company"],
            "message": body["message"],
            "status": "PENDING",
            "created_at": created_at
        }

        table.put_item(Item=lead)
        log_event("lead_persisted", lead_id=lead_id, status="PENDING")

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
                "message": "Lead accepted for processing",
                "lead_id": lead_id,
                "status": "PENDING"
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
