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
4. SNS qualified-lead topic
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

Create the qualified-lead notification topic:

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

The qualified-lead topic is used for successful qualification notifications.

The operational-alert topic is used by CloudWatch to notify operators when messages reach the dead-letter queue.

Email subscriptions are environment-specific and should be created using the recipient address appropriate to the deployment rather than hard-coding the reference deployment address.

