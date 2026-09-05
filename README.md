# NEXUS — Infrastructure Engineering Operator Console

NEXUS is a local, deterministic Developer Operations platform designed to demonstrate reliable background work processing, controlled failure handling, release rollback, and operator visibility.

## Overview

NEXUS provides a small working model of an infrastructure operations platform where accepted work must remain durable, failures must be bounded, and operators must be able to understand what happened.

The system includes:

* Durable job acceptance using SQLite
* Background worker processing
* Retry limits and dead-letter state
* Duplicate job protection
* Worker stop/start controls
* Deliberate failure injection
* Release management
* One-action release rollback
* Persistent event history
* Operator dashboard
* Local and offline operation

## Architecture

```text
React + TypeScript + Tailwind
            |
            | HTTP
            v
       FastAPI Backend
            |
            v
          SQLite
            |
            v
      Background Worker
```

All application state is stored locally. No cloud services, external network calls, or AI model calls are required at runtime.

## Start

### Backend

Open a terminal in:

```text
Nexus-Priyanshi/backend
```

Make sure Python 3.11+ is installed.

Activate the backend virtual environment if required:

```powershell
.\venv\Scripts\Activate.ps1
```

Start the API:

```powershell
uvicorn main:app --reload
```

The backend runs at:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### Frontend

Make sure Node.js LTS is installed.

Open another terminal in:

```text
Nexus-Priyanshi/frontend
```

Install dependencies if needed:

```powershell
npm install
```

Start the frontend:

```powershell
npm run dev
```

Open the local frontend URL shown by Vite, normally:

```text
http://localhost:5173
```

## Use

### Create a job

Use the dashboard or the API endpoint:

```text
POST /jobs/
```

Example:

```json
{
  "id": "demo-001",
  "type": "payment-test",
  "body": "Example job"
}
```

A newly accepted job starts in:

```text
QUEUED
```

The worker processes the job and eventually moves it to:

```text
SUCCESS
```

or, after the retry limit:

```text
DEAD
```

### View work state

The dashboard shows:

* Total jobs
* Successful jobs
* Active/pending jobs
* Dead/given-up jobs
* Worker restarts
* Queue size
* Oldest active job
* Individual job attempts
* Event history

### Worker control

The operator can:

* Stop the worker
* Start the worker
* Observe the restart count

Accepted jobs remain stored in SQLite while the worker is stopped.

### Failure injection

Failure mode can be enabled or disabled from the operator console.

When failure mode is enabled, jobs intentionally fail and are retried.

The retry limit is:

```text
3 attempts
```

After the final failed attempt, the job becomes:

```text
DEAD
```

This prevents unlimited retry loops.

### Duplicate protection

Every job has a unique ID.

Submitting the same job ID again results in:

```text
409 Conflict
```

with:

```text
Job ID already exists
```

### Release management

A release can be created through:

```text
POST /releases/
```

The dashboard displays the active release.

A previous release can be restored using:

```text
POST /releases/rollback
```

Rollback is performed as a single operator action.

## Break

The system contains deliberate failure controls for demonstration and testing.

### Failure test

1. Enable **FAIL MODE**.
2. Create a new job.
3. Observe:

   * ACCEPTED
   * RUNNING
   * FAILED
   * retry
   * DEAD after the third attempt

### Persistence test

1. Stop the worker.
2. Create a new job.
3. Confirm that the job remains `QUEUED`.
4. Start the worker.
5. Confirm that the stored job is processed.

### Duplicate test

1. Create a job with a unique ID.
2. Submit the same ID again.
3. Confirm the second request returns `409 Conflict`.

### Rollback test

1. Create release `v1.0`.
2. Create release `v2.0`.
3. Confirm `v2.0` becomes active.
4. Click **Rollback One Release**.
5. Confirm `v1.0` becomes active again.

## Look

The main operator console is designed to make the current state understandable quickly.

The dashboard provides:

### System Overview

Current:

* Worker state
* Total work
* Successful work
* Active/pending work
* Dead work
* Worker restart count

### Queue Health

Current:

* Queued work
* Running work
* Retry waiting work
* Oldest active job
* Backlog size

### Worker Control

Operators can stop and start background processing.

### Failure Injection

Operators can deliberately enable or disable worker failure behaviour.

### Active Release

The currently active release and rollback action are visible.

### Work State

Each accepted job shows:

* Job ID
* Type
* Status
* Attempt count
* Creation time

### Event History

The event history records:

* What happened
* When it happened
* Which job was involved
* Why the event occurred

This allows an operator to reconstruct recent system behaviour.

## Reliability Decisions

NEXUS prioritizes reliability depth over implementing many shallow features.

The main reliability mechanisms are:

1. Accepted work is persisted in SQLite.
2. Jobs have explicit states.
3. Retries have a hard limit.
4. Duplicate job IDs are rejected.
5. Worker state is operator-controlled and visible.
6. Important actions are recorded in the event history.
7. Releases can be rolled back in one action.
8. The complete system operates locally without external dependencies at runtime.

## Technology

* Python
* FastAPI
* SQLite
* React
* TypeScript
* Tailwind CSS
* Vite

## Runtime Constraints

NEXUS is intentionally designed for local demonstration.

It does not require:

* Cloud infrastructure
* User accounts
* External databases
* Network services
* Runtime AI model calls

## Demo Flow

For a short evaluator demonstration:

1. Start the backend and frontend.
2. Open the Operator Console.
3. Show the healthy system state.
4. Create a job.
5. Enable failure mode.
6. Show bounded retries and the `DEAD` state.
7. Show the event history explaining what happened.
8. Stop the worker.
9. Create another job and show that it remains queued.
10. Start the worker and show recovery.
11. Demonstrate duplicate protection.
12. Create a new release and perform one-action rollback.

## Project Structure

```text
Nexus-Priyanshi/

├── backend/
│   ├── api/
│   │   ├── failures.py
│   │   ├── jobs.py
│   │   └── releases.py
│   ├── database/
│   │   └── database.py
│   ├── workers/
│   │   └── worker.py
│   └── main.py
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── App.css
│   │   └── index.css
│   └── vite.config.ts
│
├── README.md
└── ACCOUNT.md
```

## Status

NEXUS is a local working prototype focused on demonstrating infrastructure reliability, bounded failure behaviour, operational visibility, durable work state, and safe release rollback.
