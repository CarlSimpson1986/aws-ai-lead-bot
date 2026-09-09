# Engineering Log

This log records significant architecture decisions, implementation changes, failures, fixes and lessons from the AWS AI Lead Qualification Bot.

It complements the README and Git history:

- **README** — polished portfolio and architecture story
- **Git history** — exact implementation changes
- **Engineering log** — why decisions were made, what failed and what was learned

---

## 1. Asynchronous Lead Processing

**Decision:** Use API Gateway -> ingestion Lambda -> DynamoDB + SQS -> processing Lambda -> Amazon Bedrock.

**Reason:** The public API should acknowledge a lead quickly without waiting for AI inference. SQS decouples ingestion from processing and allows downstream failures to be retried safely.

**Trade-off:** Adds eventual consistency and additional infrastructure compared with synchronous processing.

**Alternative:** API Gateway -> Lambda -> Bedrock synchronously.

**Why not chosen:** Bedrock latency or failure would directly affect the client request and make the API less resilient.

---

## 2. DynamoDB as the Persistent Source of Truth

**Decision:** Store lead state in DynamoDB while SQS carries only the `lead_id`.

**Reason:** SQS is a transport mechanism, not the long-term system of record. DynamoDB allows status tracking from PENDING through PROCESSING to QUALIFIED or UNQUALIFIED.

**Trade-off:** Requires an additional database service and state-management logic.

**Alternative:** Put the entire lead payload in SQS.

**Why not chosen:** That would duplicate sensitive data in the queue and provide no persistent status record.

---

## 3. Data Minimisation

**Decision:** Minimise sensitive data passed between services.

**Implementation:**
- SQS contains only `lead_id`.
- Bedrock receives company and message, not email.
- Qualified-lead SNS notifications contain lead ID, score and reason rather than the full lead payload.
- Application logs avoid lead PII.

**Reason:** Reduce unnecessary exposure of customer data and limit the impact of logs, queues or notifications being accessed.

**Trade-off:** Processing Lambda must read the lead from DynamoDB before inference.

---

## 4. Duplicate-Safe Processing

**Decision:** Add an atomic DynamoDB processing claim and lease.

**Reason:** SQS Standard provides at-least-once delivery, meaning duplicate delivery is possible.

**Implementation:** A lead is conditionally moved from PENDING to PROCESSING with a temporary processing lease. Competing Lambda invocations cannot both process the same lead.

**Trade-off:** More DynamoDB conditional-update logic and lease recovery behaviour.

**Alternative:** Rely only on checking the current status before processing.

**Why not chosen:** Two concurrent invocations could both read PENDING before either updated it.

---

## 5. SQS Visibility Timeout

**Decision:** Set the processing queue visibility timeout to 180 seconds while the processing Lambda timeout is 30 seconds.

**Reason:** Gives the Lambda sufficient time to complete before a failed message becomes visible for retry.

**Trade-off:** A genuinely failed message may take several minutes to reach the DLQ.

**Alternative:** Use a shorter visibility timeout for quicker retries.

**Why not chosen:** Too short a timeout increases the risk of the same message being processed concurrently during a slow invocation.

---

## 6. Dead-Letter Queue and Operational Alert

**Decision:** Configure an SQS DLQ with `maxReceiveCount = 3` and a CloudWatch alarm when visible DLQ messages reach 1 or more.

**Reason:** Repeatedly failing messages need to be isolated rather than retried indefinitely, and operators need to know when failures require investigation.

**Validation:** A poison-message test was allowed to retry and reach the DLQ. The CloudWatch alarm entered ALARM state and an SNS operational email was received.

**Recovery validation:** The DLQ was purged and fresh zero-value datapoints returned the alarm to OK.

---

## 7. Public API Guardrails

**Decision:** Apply API Gateway throttling and strict ingestion validation.

**Implementation:**
- steady-state rate: 1 request/second
- burst: 2
- required string fields validated
- email basic validation
- field length limits
- malformed requests return HTTP 400

**Reason:** Reduce accidental abuse, uncontrolled queue growth and unnecessary downstream processing.

**Limitation:** Throttling is not authentication or bot protection.

**Production consideration:** A production public lead form could add frontend bot protection or another abuse-control layer depending on threat and cost requirements.

---

## 8. Processing Concurrency Guardrail

**Decision:** Limit SQS-triggered processing Lambda concurrency to 2.

**Reason:** Protect Bedrock usage and costs from sudden queue growth while keeping the portfolio workload deliberately small.

**Trade-off:** Large backlogs process more slowly.

**Production consideration:** Tune concurrency based on traffic, latency, service quotas and cost objectives.

---

## 9. Prompt-Injection Resistance

**Decision:** Treat lead text as untrusted input and explicitly instruct the model not to follow instructions contained inside the lead.

**Reason:** Lead submissions can contain arbitrary text and should never be trusted as system instructions.

**Additional control:** Model output is validated before being written to DynamoDB.

**Limitation:** Prompt wording alone is not a complete security boundary.

---

## 10. Structured Logging Without Lead PII

**Decision:** Use structured operational logs containing IDs, statuses and processing outcomes rather than names, email addresses or full messages.

**Reason:** Logs should support diagnosis without unnecessarily duplicating customer information.

**Note:** AWS Lambda platform logs may contain AWS runtime metadata. The application logging policy is specifically designed not to emit lead PII.

---

## 11. Automated Validation Tests

**Decision:** Add pytest tests for deterministic application logic.

**Coverage includes:**
- valid ingestion fields
- invalid email
- non-string fields
- oversized message
- valid QUALIFIED model output
- valid UNQUALIFIED model output
- score range validation
- qualification threshold consistency

**Current result:** 9 tests passing.

**Reason:** Deterministic validation logic should be tested without requiring live AWS services or Bedrock calls.

---

## 12. GitHub Actions CI

**Decision:** Run automated Python tests on pushes and pull requests targeting `main`.

**Reason:** Prevent known validation regressions from being merged or deployed.

**Security:** CI requires no AWS credentials.

---

## 13. GitHub Actions Deployment with OIDC

**Decision:** Use GitHub Actions OIDC to assume a narrowly scoped AWS IAM deployment role.

**Reason:** Avoid storing long-lived AWS access keys in GitHub.

**Security controls:**
- repository identity restricted using GitHub repository and owner IDs
- trust restricted to `main`
- deployment permissions limited to the two project Lambda functions
- only required Lambda read/update actions are granted

**Alternative:** Store AWS access keys as GitHub secrets.

**Why not chosen:** Long-lived credentials create unnecessary credential-management and compromise risk.

---

## 14. CI/CD Permission Failure

**What happened:** The first deployment workflow updated the ingestion Lambda successfully but failed while waiting for the function update to complete.

**Why:** The deployment role allowed `lambda:UpdateFunctionCode` but did not allow the read operation required by the AWS CLI waiter.

**Diagnosis:** GitHub Actions showed the code update succeeding before the waiter returned AccessDenied.

**Fix:** Add only `lambda:GetFunction` to the deployment role rather than broad Lambda permissions.

**What was learned:** Deployment tooling can require read permissions in addition to the obvious write permission.

**Production lesson:** Start with least privilege, observe the exact failure, then add the minimum additional permission required.

---

## 15. Automatic Deployment After Successful CI

**Decision:** Change CD from manual commissioning mode to automatic deployment after a successful Python CI run on `main`.

**Safety gate:**
- upstream workflow must conclude `success`
- upstream event must be `push`
- upstream branch must be `main`
- manual `workflow_dispatch` remains available

**Reason:** A tested `main` commit should deploy automatically while failed tests or pull-request CI runs must never trigger AWS deployment.

---

## 16. Deploy Exactly What Was Tested

**Decision:** When CD is triggered by `workflow_run`, check out `github.event.workflow_run.head_sha`.

**Reason:** A deployment must use the exact commit that CI tested rather than whatever commit happens to be newest on `main` when CD starts.

**Risk avoided:**

CI tests Commit A -> Commit B arrives -> CD accidentally deploys untested Commit B.

**Validated result:** A real push to `main` triggered Python CI successfully, which then triggered the AWS deployment workflow. OIDC authentication, packaging and deployment of both Lambda functions completed successfully.

---

## Current Portfolio Evidence

The project currently demonstrates:

- public HTTP API
- asynchronous serverless architecture
- DynamoDB state management
- SQS retry and DLQ handling
- duplicate-safe processing
- Amazon Bedrock inference
- prompt-injection consideration
- model-output validation
- SNS notifications
- CloudWatch monitoring and alerting
- least-privilege IAM
- data minimisation
- structured logging
- automated tests
- GitHub Actions CI
- OIDC-based AWS deployment
- automatic gated CD
- real failure diagnosis and recovery

---

## Next Review

Before declaring the project portfolio-ready, review:

1. Architecture diagram
2. README structure and clarity
3. Reproduction/deployment instructions
4. Cost analysis
5. Security summary and known limitations
6. Production gap analysis
7. Screenshots/evidence
8. Interview explanation
9. Real Upwork job match

## 17. Path-Aware CI/CD

**Decision:** Restrict automatic CI runs to application code, tests, development dependencies and GitHub workflow changes.

**Reason:** Documentation-only changes do not affect Lambda behaviour and should not cause unnecessary testing and AWS redeployment.

**Included paths:**
- `src/**`
- `tests/**`
- `requirements-dev.txt`
- `.github/workflows/**`

**Excluded examples:**
- `README.md`
- `docs/**`

**Trade-off:** Changes outside the configured paths will not automatically exercise CI.

**Validation:** The workflow-change commit triggered CI and CD successfully. A documentation-only commit is used to verify that neither workflow runs unnecessarily.

