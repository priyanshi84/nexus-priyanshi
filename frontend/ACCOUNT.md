# NEXUS — Engineering Account

## Scope

NEXUS is a local working model of a Developer Operations platform focused on reliable background work, controlled failures, operational visibility, and safe release rollback.

The implementation focuses on the core reliability requirements:

* Durable accepted work
* Explicit work states
* Bounded retries
* Duplicate protection
* Operator-controlled worker state
* Persistent event history
* Release rollback
* Deliberate failure injection
* Clear operator visibility

The system is intentionally designed to run on one machine without cloud infrastructure or external runtime dependencies.

## Decisions

### 1. SQLite for durable state

SQLite was selected because the challenge requires a local, deterministic system. It provides persistent state without requiring an external database server.

Jobs, events, releases, and system state are stored locally.

### 2. Explicit job states

Jobs use explicit states such as:

* `QUEUED`
* `RUNNING`
* `RETRY_WAIT`
* `SUCCESS`
* `DEAD`

This makes the current state of accepted work visible to the operator.

### 3. Bounded retries

Failed jobs are retried up to three attempts.

After the third failed attempt, the job becomes `DEAD`.

This prevents an uncontrolled retry loop and gives the operator a clear terminal state.

### 4. Unique job IDs

Every accepted job has a unique ID.

SQLite primary-key enforcement prevents the same job ID from being accepted twice.

A duplicate submission returns `409 Conflict`.

### 5. Operator-controlled worker state

The worker can be stopped and started through the operator console.

Worker state is stored in SQLite so the API and worker use the same operational state.

### 6. Event history

Important job and operator actions are recorded as events.

The event history provides:

* Event type
* Job ID when applicable
* Timestamp
* Reason

This allows recent system behaviour to be reconstructed.

### 7. One-action rollback

Releases maintain an active/inactive state.

The rollback operation identifies the active release and restores the previous release in one operator action.

### 8. Deliberate failure injection

Failure mode is an explicit operator control.

It allows reviewers to reproduce failure behaviour and observe bounded retries and terminal failure without modifying source code.

## Failure Behaviour

### Worker stopped

When the worker is stopped:

* New jobs can still be accepted.
* Accepted jobs remain stored in SQLite.
* Queued jobs remain visible in the operator console.
* Starting the worker allows queued work to continue processing.

### Processing failure

When failure mode is enabled:

1. The job enters `RUNNING`.
2. The attempt fails.
3. The job enters `RETRY_WAIT`.
4. The worker retries the job.
5. After the third failed attempt, the job becomes `DEAD`.

### Duplicate submission

If an existing job ID is submitted again, the database rejects the duplicate and the API returns:

`409 Conflict — Job ID already exists`

### Release failure

A bad or unwanted active release can be reverted using the single rollback action.

The previous release becomes active again and the rollback is recorded in event history.

## Limits

This implementation is intentionally scoped as a local challenge prototype.

Current limits include:

* Single-machine operation
* Local SQLite persistence
* A small number of worker processes/threads
* No distributed coordination
* No external authentication
* No cloud deployment requirement at runtime
* No external message broker
* No production-grade multi-node failover
* No runtime AI model dependency

The worker simulation uses a simple deterministic processing loop suitable for demonstrating the required reliability behaviour.

## Confidence

The following behaviours have been manually verified during development:

### Durable queued work

A job was accepted while the worker was stopped and remained queued and visible in the dashboard.

### Bounded retry

`demo-001` was processed as:

`ACCEPTED → RUNNING → FAILED → RUNNING → FAILED → RUNNING → DEAD`

The job stopped after three attempts.

### Duplicate protection

Submitting `demo-001` again returned:

`409 Conflict`

with:

`Job ID already exists`

### Release rollback

A release sequence was tested:

`v1.0 → v2.0 → rollback → v1.0`

The rollback was recorded in event history.

### Operator visibility

The dashboard displays worker state, queue health, work state, attempts, active release, failure mode, and event history.

## Next

If this system were developed beyond the challenge prototype, the next reliability improvements would include:

1. Stronger atomic job claiming to prevent concurrent workers from claiming the same job.
2. Recovery handling for jobs interrupted while in `RUNNING`.
3. Persistent retry scheduling with explicit backoff timestamps.
4. More detailed release-to-job linkage.
5. Release health checks and automatic detection of problematic behaviour.
6. More comprehensive workload and throughput controls.
7. Multi-worker coordination and distributed persistence.
8. Additional automated tests for crash and restart scenarios.

## Reviewer Notes

The prototype intentionally prioritizes reliability depth and demonstrability over breadth.

The primary demonstration focuses on:

* Work that persists
* Failures that have limits
* Duplicates that are rejected
* Events that explain system history
* Releases that can be rolled back
* An operator console that exposes current state clearly

The system is deterministic and designed to be understandable through both the operator dashboard and the API documentation.
