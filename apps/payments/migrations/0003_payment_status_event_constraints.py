from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0002_paymentverificationattempt_provider_reference_and_more")
    ]

    operations = [
        migrations.AddConstraint(
            model_name="paymentstatusevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(previous_state__isnull=True),
                fields=("payment",),
                name="payment_one_initial_status_event",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentstatusevent",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(previous_state__isnull=True, new_state="PENDING")
                    | models.Q(
                        previous_state="PENDING",
                        new_state="CONFIRMED",
                        actor__isnull=False,
                    )
                ),
                name="payment_status_event_valid_transition",
            ),
        ),
    ]
