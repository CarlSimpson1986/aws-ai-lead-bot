# Deployment Guide

This guide explains how to reproduce and deploy the AWS AI Lead Qualification Bot using the AWS CLI.

## Deployment Approach

This project was deliberately built using the AWS CLI rather than the AWS Management Console.

Infrastructure configuration and IAM policy documents are stored in the `infrastructure/` directory so the architecture and security decisions are visible and version-controlled.

The current repository does not provide a one-command Infrastructure-as-Code deployment. Resources are created and configured sequentially with the AWS CLI so each step and dependency can be understood and verified.

## Prerequisites

- AWS account
- AWS CLI v2 configured locally
- Python 3.13
- Git
- GitHub repository access if using the CI/CD pipeline
- Amazon Bedrock access to `amazon.nova-micro-v1:0` in `eu-west-2`

## Region

The reference deployment uses:

`eu-west-2` — Europe (London)

## Deployment Order

The AWS resources depend on one another, so deployment should follow this order:

1. DynamoDB table
2. SQS dead-letter queue
3. SQS processing queue
4. SNS HOT-lead alert topic
5. SNS operational-alert topic
6. Lambda IAM roles and policies
7. Ingestion Lambda
8. Processing Lambda
9. SQS event source mapping
10. API Gateway HTTP API
11. CloudWatch DLQ alarm
12. GitHub OIDC provider and deployment role
13. GitHub Actions CI/CD validation

Detailed AWS CLI commands will be documented below as the reproduction guide is completed.

## 1. Create the DynamoDB Table

The project stores lead state in DynamoDB using `lead_id` as the partition key.

Configuration:

- Table: `ai-lead-qualification-leads`
- Partition key: `lead_id` (String)
- Provisioned capacity: 1 RCU / 1 WCU

Deploy with:

```bash
aws dynamodb create-table \
  --cli-input-json file://infrastructure/dynamodb-table.json \
  --region eu-west-2
```

Then wait for the table to become active:

```bash
aws dynamodb wait table-exists \
  --table-name ai-lead-qualification-leads \
  --region eu-west-2
```

The deliberately low provisioned capacity keeps the portfolio deployment small and predictable. A higher-volume production system could instead use on-demand capacity or tuned provisioned autoscaling depending on traffic patterns.


## 2. Create the SQS Queues

The architecture uses:

- `ai-lead-qualification-dlq` — isolates repeatedly failing messages
- `ai-lead-qualification-processing` — buffers leads for asynchronous processing

Create the dead-letter queue first:

```powershell
aws sqs create-queue `
  --queue-name ai-lead-qualification-dlq `
  --region eu-west-2
```

Retrieve the DLQ ARN:

```powershell
$dlqUrl = aws sqs get-queue-url `
  --queue-name ai-lead-qualification-dlq `
  --region eu-west-2 `
  --query QueueUrl `
  --output text

$dlqArn = aws sqs get-queue-attributes `
  --queue-url $dlqUrl `
  --attribute-names QueueArn `
  --region eu-west-2 `
  --query Attributes.QueueArn `
  --output text
```

Create a portable redrive-policy file using the ARN from the current AWS account:

```powershell
@{
    RedrivePolicy = (@{
        deadLetterTargetArn = $dlqArn
        maxReceiveCount     = "3"
    } | ConvertTo-Json -Compress)
    VisibilityTimeout = "180"
} | ConvertTo-Json | Set-Content infrastructure\sqs-deployment-attributes.json
```

Then create the processing queue:

```powershell
aws sqs create-queue `
  --queue-name ai-lead-qualification-processing `
  --attributes file://infrastructure/sqs-deployment-attributes.json `
  --region eu-west-2
```

The 180-second visibility timeout is six times the processing Lambda's 30-second timeout. This reduces the risk of a slow invocation causing the same message to become visible and process concurrently.

Messages that fail processing three times are moved to the DLQ.

### Portability Note

The existing `sqs-main-queue-attributes.json` records the configuration used by the reference deployment and therefore contains the original AWS account-specific DLQ ARN.

The reproduction procedure above generates the ARN dynamically so the deployment can be used in a different AWS account without modifying hard-coded account identifiers.


## 3. Create the SNS Topics

Create the HOT-lead notification topic. The deployed AWS resource retains the original name `ai-lead-qualified`:

```powershell
aws sns create-topic `
  --name ai-lead-qualified `
  --region eu-west-2
```

Create the operational-alert topic:

```powershell
aws sns create-topic `
  --name ai-lead-ops-alerts `
  --region eu-west-2
```

The `ai-lead-qualified` topic is used only for leads classified as `HOT`. The resource name is retained from the original implementation.

The operational-alert topic is used by CloudWatch to notify operators when messages reach the dead-letter queue.

Email subscriptions are environment-specific and should be created using the recipient address appropriate to the deployment rather than hard-coding the reference deployment address.



## 4. Lambda Functions and IAM Roles

The deployed application uses three Lambda functions:

- `ai-lead-ingestion`
- `ai-lead-processing`
- `ai-lead-retrieval`

Each function has a separate least-privilege IAM role.

### Ingestion Lambda

Responsibilities:

- Validate the public request
- Accept caller-supplied `lead_id`
- Conditionally store the lead in DynamoDB
- Send only the `lead_id` to SQS

Required permissions:

- `dynamodb:PutItem` on the project table
- `sqs:SendMessage` on the processing queue
- CloudWatch Logs permissions for its own log group

### Processing Lambda

Responsibilities:

- Read the lead from DynamoDB
- Atomically claim the lead using a processing lease
- Invoke Amazon Bedrock Nova Micro
- Validate `category`, `summary`, `reason`, and `confidence`
- Persist `HOT`, `WARM`, or `COLD`
- Publish to SNS only when the lead is `HOT`

Required permissions:

- SQS receive/delete/get attributes on the processing queue
- DynamoDB `GetItem` and `UpdateItem`
- `bedrock:InvokeModel` for Nova Micro
- `sns:Publish` to the HOT-lead topic
- CloudWatch Logs permissions for its own log group

### Retrieval Lambda

Responsibilities:

- Handle `GET /leads/{lead_id}`
- Read the lead from DynamoDB
- Return qualification data without exposing stored email or original message

Required permissions:

- `dynamodb:GetItem` on the project table
- CloudWatch Logs permissions for its own log group

The retrieval role intentionally has no write access to DynamoDB.


## 5. API Gateway Routes

The HTTP API exposes two routes:

```text
POST /leads
GET /leads/{lead_id}
```

`POST /leads` integrates with `ai-lead-ingestion`.

`GET /leads/{lead_id}` integrates with `ai-lead-retrieval`.

The POST route is throttled to:

- 1 request per second steady state
- Burst limit of 2

The API returns `202 Accepted` for valid asynchronous submissions.

A missing required `lead_id` returns HTTP 400.

A retrieval request for an unknown lead returns HTTP 404.


## 6. SQS Event Source Mapping

The processing queue invokes `ai-lead-processing`.

Configuration:

- Batch size: 1
- Maximum concurrency: 2
- Queue visibility timeout: 180 seconds
- Processing Lambda timeout: 30 seconds
- Processing lease: 120 seconds

The queue redrive policy moves repeatedly failing messages to the DLQ after three failed receives.


## 7. CloudWatch Monitoring

Lambda log groups:

```text
/aws/lambda/ai-lead-ingestion
/aws/lambda/ai-lead-processing
/aws/lambda/ai-lead-retrieval
```

The DLQ is monitored using a CloudWatch alarm on:

```text
AWS/SQS
ApproximateNumberOfMessagesVisible
```

Alarm condition:

- Queue: `ai-lead-qualification-dlq`
- Threshold: 1 or more visible messages
- Period: 60 seconds
- Evaluation periods: 1
- Missing data: `notBreaching`

The alarm publishes to the dedicated operations SNS topic.

The failure path was validated live by sending a poison message, observing retries, DLQ redrive, alarm transition to `ALARM`, email notification, and eventual recovery to `OK`.


## 8. CI/CD Deployment

GitHub Actions provides both CI and CD.

### Continuous Integration

On relevant pushes and pull requests:

1. Checkout repository
2. Use Python 3.13
3. Install development dependencies
4. Run `pytest`

Current automated test result:

```text
16 passed
```

### Continuous Deployment

A successful CI run on `main` triggers the deployment workflow.

The deployment workflow:

1. Checks out the exact commit SHA that passed CI
2. Runs the tests again
3. Uses GitHub OIDC to obtain short-lived AWS credentials
4. Assumes a least-privilege deployment role
5. Packages the Lambda source
6. Updates:
   - `ai-lead-ingestion`
   - `ai-lead-processing`
   - `ai-lead-retrieval`
7. Waits for each Lambda update to complete

No long-lived AWS access keys are stored in GitHub.


## 9. Live Acceptance Validation

The deployed system has been validated end-to-end.

Confirmed behaviour:

- HOT lead classified as `HOT`
- WARM lead classified as `WARM`
- COLD lead classified as `COLD`
- Structured output includes category, summary, reason, and confidence
- Only HOT leads trigger the sales SNS notification
- Duplicate lead IDs do not overwrite the existing record
- Duplicate processing is stopped before another Bedrock invocation
- GET retrieval works by `lead_id`
- Retrieval excludes stored email and original message
- Missing required `lead_id` returns HTTP 400
- Unknown retrieval ID returns HTTP 404
- Repeated processing failures reach the DLQ and trigger an operational alert


## 10. Cost and Production Notes

The architecture is intentionally serverless and low-volume.

Cost controls include:

- API Gateway throttling
- SQS-controlled processing concurrency
- Small Lambda memory allocations
- Minimal data sent to Bedrock
- Input length limits
- AWS Budget alerting
- Bedrock invoked only after successful validation and atomic claim

The reference deployment is appropriate for portfolio and low-volume workloads.

For a production client deployment, additional controls could include:

- Authentication or API keys
- AWS WAF or bot protection
- Infrastructure as Code
- Separate environments
- Automated secret rotation where applicable
- Enhanced dashboards and alerting
- Retention policies and formal data lifecycle controls
