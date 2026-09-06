# LedgerMind v0.26
Adds persistent processing jobs with PENDING/RUNNING/RETRY/SUCCEEDED/DEAD states, attempt counts, idempotent job keys, and accounting exceptions with OPEN/REVIEW/RESOLVED lifecycle.

When a transaction first requires owner information, an OPEN exception is persisted. If later evidence causes the same transaction to become AUTO_FINISH, that exception is automatically RESOLVED with the resolving ingest event recorded.

The sandbox executes queued jobs immediately. Production can move the same job records behind a worker/queue without changing accounting semantics.
