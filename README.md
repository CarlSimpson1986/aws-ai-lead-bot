# AWS AI Lead Qualification Bot

Serverless asynchronous lead qualification system built with AWS CLI.

## Architecture

API Gateway -> Ingestion Lambda -> DynamoDB + SQS -> Processing Lambda -> Amazon Bedrock -> DynamoDB + SNS

Failed SQS messages are routed to a Dead-Letter Queue (DLQ).

## Project Goals

- AWS CLI only
- £0 out-of-pocket using AWS Free Tier / free-plan credits
- Least-privilege IAM
- Asynchronous and resilient architecture
- Production-style logging and failure handling
- Document architecture decisions, trade-offs and alternatives
