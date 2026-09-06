import json
import os
import uuid
from datetime import datetime, timezone

import boto3


REQUIRED_FIELDS = ["name", "email", "company", "message"]

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

sqs = boto3.client("sqs")
queue_url = os.environ["QUEUE_URL"]


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

        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({
                "lead_id": lead_id
            })
        )

        return {
            "statusCode": 202,
            "body": json.dumps({
                "message": "Lead accepted for processing",
                "lead_id": lead_id,
                "status": "PENDING"
            })
        }

    except (json.JSONDecodeError, ValueError):
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Invalid JSON request"
            })
        }
