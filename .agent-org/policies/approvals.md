# Approval Policy

Human gates (cannot be bypassed by agents):

| Gate | Workflow point | Approver |
| ---- | -------------- | -------- |
| plan-approval | AWAITING_DECISION -> APPROVED | Product owner / requester |
| release-approval | AWAITING_APPROVAL -> READY_FOR_RELEASE | Release owner |
| budget-extension | any budget exhaustion | Cost owner |
| destructive-action | any destructive tool call | Security owner |

Approvals are recorded with approver identity, timestamp, and reason, and
are visible in the audit timeline.
