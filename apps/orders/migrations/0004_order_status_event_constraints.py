from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0003_alter_order_options")]

    operations = [
        migrations.AddConstraint(
            model_name="orderstatusevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(previous_status__isnull=True),
                fields=("order",),
                name="order_one_initial_status_event",
            ),
        ),
        migrations.AddConstraint(
            model_name="orderstatusevent",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(previous_status__isnull=True, new_status="PENDING")
                    | models.Q(
                        previous_status="PENDING",
                        new_status="CONFIRMED",
                        actor__isnull=False,
                    )
                    | (
                        models.Q(
                            previous_status="CONFIRMED",
                            new_status="PROCESSING",
                            actor__isnull=False,
                        )
                        & ~models.Q(reason="")
                    )
                    | (
                        models.Q(
                            previous_status__in=("CONFIRMED", "PROCESSING"),
                            new_status="CANCELLED",
                            actor__isnull=False,
                        )
                        & ~models.Q(reason="")
                    )
                    | models.Q(
                        previous_status="PROCESSING",
                        new_status="FULFILLED",
                        actor__isnull=False,
                    )
                ),
                name="order_status_event_valid_transition",
            ),
        ),
    ]
