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

## Bedrock Access Verification

During end-to-end testing, the processing Lambda successfully reached the Amazon Bedrock Converse API using the configured least-privilege IAM role.

The first live Nova Micro invocation returned:

`AccessDeniedException: Your account is currently being verified.`

### Assessment

This was identified as an AWS account-level Bedrock verification restriction rather than an application-code or IAM-policy failure.

The processing Lambda already has:

- `bedrock:InvokeModel`
- access restricted to `amazon.nova-micro-v1:0`

No additional IAM permissions were added because doing so would not resolve an account-verification restriction and would unnecessarily weaken the least-privilege security model.

### Decision

Keep the existing Bedrock IAM policy unchanged and continue building/testing the surrounding workflow while AWS completes account verification.

### Engineering Principle

Infrastructure or provider-level restrictions should be distinguished from application defects before changing code or security permissions.


## Architecture Decision Matrix

| Area | Decision | Why | Trade-off / Alternative |
|---|---|---|---|
| Bedrock verification failure | Do not broaden IAM permissions | The live Converse call reached Bedrock but was blocked by AWS account verification, not by missing role permissions | Wait for account verification instead of weakening least-privilege IAM |

### SQS Visibility Timeout

The processing Lambda has a 30-second execution timeout. The SQS processing queue is configured with a 180-second visibility timeout.

This follows AWS guidance to set the queue visibility timeout to at least six times the Lambda timeout when SQS is used as a Lambda event source.

**Why this matters:**
- Prevents a message becoming visible again while the Lambda may still be processing it.
- Reduces accidental duplicate processing.
- Gives AWS room for throttling and retry behaviour.
- Works alongside the application-level idempotency guard.

**Trade-off:**  
A longer visibility timeout means a genuinely failed message takes longer to become available for another processing attempt. For this asynchronous lead-qualification workload, reliability is more important than retrying within a few seconds.

**Alternative:**  
For latency-sensitive workloads, a shorter Lambda timeout and correspondingly shorter SQS visibility timeout could reduce retry delay.
