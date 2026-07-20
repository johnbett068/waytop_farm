# Separation of duties

## Principle

Possessing a capability is necessary but not always sufficient. Sensitive workflows require an independent person, appropriate scope and an approval decision. Delegation, administrator status and temporary assignment do not waive these controls.

## Mandatory prohibitions

| Initiating action | Independent action | Prohibition |
|---|---|---|
| Draft inventory adjustment/write-off | Approve adjustment/write-off | Creator, beneficiary or recorder cannot approve. |
| Record stock count | Approve count variance | Counter/recorder cannot approve their own variance. |
| Initiate inventory transfer | Approve transfer | Initiator cannot approve; source dispatcher cannot attest destination receipt. |
| Dispatch transfer | Receive transfer | Same actor cannot perform both custody attestations except documented emergency policy followed by review. |
| Create/refund request | Approve refund | Cashier/requester and original sale beneficiary cannot approve. |
| Process POS sale | Approve void of that sale | Original cashier cannot approve their own void. |
| Perform production quality review | Approve/release reviewed batch | Reviewer cannot approve their own review/release. |
| Record production quantity/correction | Approve material correction | Recorder cannot approve their own exception. |
| Propose role/capability change | Approve/publish change | Proposer cannot be sole approver, especially when affected. |
| Create/modify own staff access | Approve access change | Subject cannot approve; privileged grant needs independent administrator/governance approval. |
| Change critical settings | Approve/publish critical settings | Proposer cannot approve; policy version and rollback reference required. |
| Produce controlled report/export request | Approve restricted export | Requester cannot approve when policy classifies data as sensitive. |
| Create purchase request | Approve same request | Requester cannot approve their own demand. |
| Prepare quotation comparison/supplier award | Solely approve award | Preparer or conflicted supplier contact cannot be sole approver. |
| Create or materially amend purchase order | Approve/issue same order | Creator cannot be the only approver; threshold policy may require Operations/Administrator. |
| Record supplier delivery/inspection | Approve related Inventory receipt variance | Inspector cannot conceal rejected/damaged/short quantities through Inventory approval. |

## Enforcement contract

Future commands identify initiator, recorder, subject/beneficiary, proposed approver, prior relevant actors and delegation lineage. Policy evaluates immutable IDs, not display names. Approval commands require fresh authorization, expected record version, reason and evidence. The server rejects conflicts; frontend disabling is explanatory only.

No shared accounts are allowed. A second active role on the same human does not make them a second person. Acting under delegation remains the same performer for separation checks. Services may execute approved effects but cannot act as the independent human approver.

## Exceptions

Baseline prohibited pairs have no routine override. A genuine safety/business-continuity emergency uses a documented break-glass policy outside ordinary delegation: incident reference, shortest duration, explicit governance approval where available, real-time alert, complete audit and mandatory retrospective review. It cannot delete evidence or disguise the actor.
