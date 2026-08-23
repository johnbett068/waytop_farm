from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("commitments", "0002_commitmentsupplyevent")]

    operations = [
        migrations.AddConstraint(
            model_name="commitmentevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(previous_state__isnull=True),
                fields=("commitment",),
                name="commitment_one_initial_event",
            ),
        ),
        migrations.AddConstraint(
            model_name="commitmentevent",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(previous_state__isnull=True, new_state="ACTIVE")
                    | models.Q(previous_state="ACTIVE", new_state="CANCELLED")
                ),
                name="commitment_event_valid_transition",
            ),
        ),
    ]
