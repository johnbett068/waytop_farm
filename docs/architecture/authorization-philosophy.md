# Authorization philosophy

WayTop uses capability-based authorization because job titles describe people, not durable business decisions. Capabilities such as `inventory.adjust` remain meaningful when roles change, custom roles emerge or modules grow. Roles are convenient, versioned bundles; domain logic never compares a role name.

Scopes apply least privilege to location and responsibility. A person may be trusted to receive stock in Bomet Main Store without receiving it everywhere. Branch, area, warehouse, register, order and task scopes also prevent list/search/export endpoints from becoming wider than detail actions.

Delegation exists because farms continue operating during leave, illness and emergencies. Explicit capability, scope, reason and time limits are safer and more auditable than credential sharing, permanent promotion or pretending to be another worker.

Audit records are immutable because operational, stock, financial and access decisions must remain attributable. Corrections append compensating or superseding records; they never rewrite history. Audit identity includes the real actor, selected role, delegated authority, approver, reason, time, branch, device and correlation ID.

Separation of duties reduces error, fraud and conflicted approval. A second role held by the same person is not independent review, and delegation cannot manufacture independence.

Hidden UI is not security. Capability-filtered navigation improves clarity and accessibility, but direct URLs, commands, exports and object queries require future server enforcement using the same policy. The frontend may simulate denial in development only.

Least privilege is the default: explicit grants, narrow scopes, active time windows, deny precedence, field-level protection and periodic review. Administrator is not synonymous with every operational capability. Emergency access is constrained, visible and reviewed.

Authorization decisions must be explainable without exposing sensitive existence. Staff receive actionable denial guidance and a correlation reference; policy owners can inspect the full decision and immutable audit event. Policy is versioned so an action can always be evaluated in its historical context.

