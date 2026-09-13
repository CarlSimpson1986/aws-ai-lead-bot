import json
import logging
import os

import boto3


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    lead_id = (
        event.get("pathParameters", {}) or {}
    ).get("lead_id")

    if not lead_id:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "lead_id is required"
            })
        }

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(os.environ["TABLE_NAME"])

    response = table.get_item(
        Key={"lead_id": lead_id}
    )

    lead = response.get("Item")

    if not lead:
        return {
            "statusCode": 404,
            "body": json.dumps({
                "error": "Lead not found",
                "lead_id": lead_id
            })
        }

    result = {
        "lead_id": lead_id,
        "status": lead.get("status")
    }

    if lead.get("qualification_category"):
        result["category"] = lead["qualification_category"]

    if lead.get("qualification_summary"):
        result["summary"] = lead["qualification_summary"]

    if lead.get("qualification_reason"):
        result["reason"] = lead["qualification_reason"]

    if lead.get("qualification_confidence") is not None:
        result["confidence"] = int(lead["qualification_confidence"])

    return {
        "statusCode": 200,
        "body": json.dumps(result)
    }
