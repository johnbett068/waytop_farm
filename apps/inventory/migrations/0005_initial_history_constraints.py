from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0004_alter_sourceallocationoperation_kind")]

    operations = [
        migrations.AddConstraint(
            model_name="reservationevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(action="CREATED"),
                fields=("reservation",),
                name="reservation_one_created_event",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservationevent",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        action="CREATED",
                        previous_state__isnull=True,
                        new_state="ACTIVE",
                    )
                    | models.Q(
                        action="CONSUMED",
                        previous_state="ACTIVE",
                        new_state__in=("ACTIVE", "CONSUMED"),
                    )
                    | models.Q(
                        action="RELEASED",
                        previous_state="ACTIVE",
                        new_state="RELEASED",
                    )
                ),
                name="reservation_event_valid_transition",
            ),
        ),
        migrations.AddConstraint(
            model_name="sourceallocationoperation",
            constraint=models.UniqueConstraint(
                condition=models.Q(kind="INITIAL"),
                fields=("reservation",),
                name="allocation_one_initial_operation",
            ),
        ),
    ]
