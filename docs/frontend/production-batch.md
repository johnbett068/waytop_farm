# Production Batches and Batch Detail

## Purpose and displayed data
The list scans batch number, target product, propagation method, current stage, age, location, responsible staff, health, expected release, estimated and observed current quantities, and notes. Detail presents the lifecycle timeline; linked source lots; input usage; labour; watering; treatments; observations; losses/culls; quality notes/holds; internal location history; photos/attachments; release approval; and cost placeholders.

## User actions and states
Staff may search, filter and open a batch. Future commands record observations, loss/cull, input usage, care activity, location movement, quality hold/release and evidence. Phase 3C controls are inert. Loading, empty, error, offline, permission and success are supported; future validation appears at field and summary level without discarding input.

## Permissions
Viewing, recording production, recording restricted treatments, moving WIP, applying/removing holds, reviewing quality and approving release are separate permissions. The initiator, approver, timestamp, reason and before/after state are audited. Release approval can require separation of duty.

## Future models and relationships
`ProductionBatch` belongs to a product/variant and propagation method. Many source lots join many batches through `BatchMaterialUsage`. Child records include stage events, quantity observations, losses, grades, tasks, labour, inputs, watering, applications, locations/movements, notes, holds, reviews, approvals and attachments. Records are append-oriented; observed quantity does not overwrite planned quantity.

## Business rules and Definition of Done
Stages advance only through authorised, validated commands. Task completion never advances a stage. Percentages and cost are future services, not browser calculations. A release records approved grades and quantities; Inventory later consumes that event through its own movement. Done means responsive detail/list views, complete governed record sections and no backend, cost, quantity or stock logic.
