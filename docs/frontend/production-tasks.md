# Production Tasks and Exceptions

## Purpose and displayed data
Tasks organise accountable nursery work; exceptions isolate conditions needing decisions. Queues cover overdue, today, upcoming and completed work such as sowing, grafting, transplanting, watering, fertilising, treatment/spraying, pruning, hardening, quality inspection and release preparation. Exceptions cover mortality, establishment, growth, quality, delay, overdue work, shortages, holds and pending approval.

## Actions, permissions and states
The frontend displays only. Future actions create/assign/reschedule/complete tasks, record evidence and acknowledge/escalate exceptions. Restricted applications require authorised applicators. View, manage-task, record-care, manage-exception and approve-release permissions remain distinct. Shared loading, empty, validation/error, offline, permission and success states apply.

## Backend contract and business rules
`ProductionTask` links optionally to a batch, stage, location and responsible staff/role. It stores type, due window, status, completion evidence and audit history. `ProductionException` stores policy, severity, observations, owner, opened/resolved timestamps and resolution; it is not a stage. Task completion cannot silently create an application, observation, stage transition, hold or release.

## Definition of Done
Fast-scanning responsive queues, exception-only dashboard, keyboard-accessible navigation, explicit ownership/due context, documented contracts and no scheduling, threshold or production calculations in the frontend.
