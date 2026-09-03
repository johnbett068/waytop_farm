from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.utils import timezone

from apps.commitments.models import (
    Commitment,
    CommitmentEvent,
    CommitmentSupplyEvent,
)
from apps.fulfillment.models import FulfillmentCompletion
from apps.inventory.models import (
    InventoryItem,
    InventoryMovement,
    Reservation,
    ReservationEvent,
    SourceAllocationOperation,
    StockPosition,
)
from apps.orders.models import Order, OrderStatusEvent
from apps.payments.models import (
    Payment,
    PaymentStatusEvent,
    PaymentVerificationAttempt,
)


OPERATIONS_PERMISSIONS = {
    "orders": "orders.view",
    "payments": "payments.verify",
    "commitments": "commitments.view",
    "inventory": "inventory.view",
    "fulfillment": "fulfillment.complete",
}
RECENT_ACTIVITY_LIMIT = 12


@dataclass(frozen=True)
class OperationsActivity:
    timestamp: object
    category: str
    title: str
    reference: str
    source: str


def _permissions_for(actor):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.is_staff
    ):
        raise PermissionDenied("Operations requires an authenticated active staff user.")
    permissions = {
        scope: actor.has_perm(permission)
        for scope, permission in OPERATIONS_PERMISSIONS.items()
    }
    return permissions


def _state_counts(model, states, *, field="state"):
    counts = {state: 0 for state in states}
    for row in model.objects.values(field).annotate(total=Count("pk")):
        counts[row[field]] = row["total"]
    return counts


def _metric(label, value, meta):
    return {"label": label, "value": value, "meta": meta, "tone": "neutral"}


def _orders_section():
    states = [value for value, _label in Order.Status.choices]
    counts = _state_counts(Order, states, field="status")
    return {
        "key": "orders",
        "eyebrow": "Order lifecycle",
        "title": "Orders",
        "record_count": sum(counts.values()),
        "metrics": [
            _metric("Pending", counts[Order.Status.PENDING], "Current lifecycle state"),
            _metric("Confirmed", counts[Order.Status.CONFIRMED], "Current lifecycle state"),
            _metric("Processing", counts[Order.Status.PROCESSING], "Current lifecycle state"),
            _metric("Fulfilled", counts[Order.Status.FULFILLED], "Current lifecycle state"),
            _metric("Cancelled", counts[Order.Status.CANCELLED], "Current lifecycle state"),
        ],
    }


def _payments_section():
    states = [value for value, _label in Payment.State.choices]
    counts = _state_counts(Payment, states)
    attempts = PaymentVerificationAttempt.objects.aggregate(
        total=Count("pk"),
        approved=Count(
            "pk",
            filter=Q(outcome=PaymentVerificationAttempt.Outcome.APPROVED),
        ),
        rejected=Count(
            "pk",
            filter=Q(outcome=PaymentVerificationAttempt.Outcome.REJECTED),
        ),
    )
    return {
        "key": "payments",
        "eyebrow": "Payment state",
        "title": "Payments",
        "record_count": sum(counts.values()) + attempts["total"],
        "metrics": [
            _metric("Pending", counts[Payment.State.PENDING], "Current payment state"),
            _metric("Confirmed", counts[Payment.State.CONFIRMED], "Current payment state"),
            _metric("Approved verifications", attempts["approved"], "Verification history"),
            _metric("Rejected verifications", attempts["rejected"], "Verification history"),
        ],
    }


def _commitments_section():
    commitment_states = [value for value, _label in Commitment.State.choices]
    reservation_states = [value for value, _label in Reservation.State.choices]
    commitments = _state_counts(Commitment, commitment_states)
    reservations = _state_counts(Reservation, reservation_states)
    return {
        "key": "commitments",
        "eyebrow": "Committed supply",
        "title": "Commitments and reservations",
        "record_count": sum(commitments.values()) + sum(reservations.values()),
        "metrics": [
            _metric("Active commitments", commitments[Commitment.State.ACTIVE], "Current commitment state"),
            _metric("Satisfied commitments", commitments[Commitment.State.SATISFIED], "Current commitment state"),
            _metric("Cancelled commitments", commitments[Commitment.State.CANCELLED], "Current commitment state"),
            _metric("Active reservations", reservations[Reservation.State.ACTIVE], "Current reservation state"),
            _metric("Consumed reservations", reservations[Reservation.State.CONSUMED], "Current reservation state"),
            _metric("Released reservations", reservations[Reservation.State.RELEASED], "Current reservation state"),
        ],
    }


def _inventory_section():
    item_count = InventoryItem.objects.count()
    positive_positions = StockPosition.objects.filter(
        on_hand_base_quantity__gt=0
    ).count()
    movements = InventoryMovement.objects.aggregate(
        total=Count("pk"),
        issues=Count("pk", filter=Q(movement_type=InventoryMovement.Type.ISSUE)),
    )
    return {
        "key": "inventory",
        "eyebrow": "Physical inventory",
        "title": "Inventory",
        "record_count": item_count + positive_positions + movements["total"],
        "metrics": [
            _metric("Inventory items", item_count, "Persisted item records"),
            _metric("Positions with stock", positive_positions, "On-hand quantity above zero"),
            _metric("Movements", movements["total"], "Immutable ledger records"),
            _metric("Issues", movements["issues"], "ISSUE movements"),
        ],
    }


def _fulfillment_section():
    count = FulfillmentCompletion.objects.count()
    return {
        "key": "fulfillment",
        "eyebrow": "Completion history",
        "title": "Fulfillment",
        "record_count": count,
        "metrics": [
            _metric("Completed fulfillments", count, "Persisted completion records"),
        ],
    }


def _transition(previous, current):
    return f"{previous or 'Created'} → {current}"


def _order_activity(limit):
    return [
        OperationsActivity(
            event.created_at,
            "Order",
            f"Order {_transition(event.previous_status, event.new_status)}",
            event.order.order_number,
            "OrderStatusEvent",
        )
        for event in OrderStatusEvent.objects.select_related("order").order_by(
            "-created_at", "-id"
        )[:limit]
    ]


def _payment_activity(limit):
    activity = [
        OperationsActivity(
            event.created_at,
            "Payment",
            f"Payment {_transition(event.previous_state, event.new_state)}",
            event.payment.order.order_number,
            "PaymentStatusEvent",
        )
        for event in PaymentStatusEvent.objects.select_related(
            "payment__order"
        ).order_by("-created_at", "-id")[:limit]
    ]
    activity.extend(
        OperationsActivity(
            attempt.created_at,
            "Payment",
            f"Payment verification {attempt.get_outcome_display()}",
            attempt.payment.order.order_number,
            "PaymentVerificationAttempt",
        )
        for attempt in PaymentVerificationAttempt.objects.select_related(
            "payment__order"
        ).order_by("-created_at", "-id")[:limit]
    )
    return activity


def _commitment_activity(limit):
    activity = [
        OperationsActivity(
            event.created_at,
            "Commitment",
            f"Commitment {_transition(event.previous_state, event.new_state)}",
            event.commitment.order.order_number,
            "CommitmentEvent",
        )
        for event in CommitmentEvent.objects.select_related(
            "commitment__order"
        ).order_by("-created_at", "-id")[:limit]
    ]
    activity.extend(
        OperationsActivity(
            event.created_at,
            "Supply",
            "Commitment supply recorded",
            event.commitment.order.order_number,
            "CommitmentSupplyEvent",
        )
        for event in CommitmentSupplyEvent.objects.select_related(
            "commitment__order"
        ).order_by("-created_at", "-id")[:limit]
    )
    activity.extend(
        OperationsActivity(
            event.created_at,
            "Reservation",
            f"Reservation {event.get_action_display()}",
            event.reservation.commitment.order.order_number,
            "ReservationEvent",
        )
        for event in ReservationEvent.objects.select_related(
            "reservation__commitment__order"
        ).order_by("-created_at", "-id")[:limit]
    )
    activity.extend(
        OperationsActivity(
            operation.created_at,
            "Allocation",
            operation.get_kind_display(),
            operation.reservation.commitment.order.order_number,
            "SourceAllocationOperation",
        )
        for operation in SourceAllocationOperation.objects.select_related(
            "reservation__commitment__order"
        ).order_by("-created_at", "-id")[:limit]
    )
    return activity


def _inventory_activity(limit):
    return [
        OperationsActivity(
            movement.posted_at,
            "Inventory",
            f"Inventory {movement.get_movement_type_display().lower()} posted",
            "Inventory movement",
            "InventoryMovement",
        )
        for movement in InventoryMovement.objects.order_by("-posted_at", "-id")[:limit]
    ]


def _fulfillment_activity(limit):
    return [
        OperationsActivity(
            completion.completed_at,
            "Fulfillment",
            "Order fulfillment completed",
            completion.order.order_number,
            "FulfillmentCompletion",
        )
        for completion in FulfillmentCompletion.objects.select_related("order").order_by(
            "-completed_at", "-id"
        )[:limit]
    ]


def build_operations_dashboard(*, actor):
    permissions = _permissions_for(actor)
    sections = []
    activity = []

    if permissions["orders"]:
        sections.append(_orders_section())
        activity.extend(_order_activity(RECENT_ACTIVITY_LIMIT))
    if permissions["payments"]:
        sections.append(_payments_section())
        activity.extend(_payment_activity(RECENT_ACTIVITY_LIMIT))
    if permissions["commitments"]:
        sections.append(_commitments_section())
        activity.extend(_commitment_activity(RECENT_ACTIVITY_LIMIT))
    if permissions["inventory"]:
        sections.append(_inventory_section())
        activity.extend(_inventory_activity(RECENT_ACTIVITY_LIMIT))
    if permissions["fulfillment"]:
        sections.append(_fulfillment_section())
        activity.extend(_fulfillment_activity(RECENT_ACTIVITY_LIMIT))

    activity.sort(
        key=lambda item: (
            item.timestamp,
            item.category,
            item.reference,
            item.source,
        ),
        reverse=True,
    )
    return {
        "generated_at": timezone.now(),
        "sections": sections,
        "has_records": any(section["record_count"] for section in sections),
        "activity": activity[:RECENT_ACTIVITY_LIMIT],
        "permissions": permissions,
    }
