from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CustomerAccountMigrationTests(TransactionTestCase):
    def test_legacy_profiles_remain_unowned_and_unchanged(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        old_targets = [("customers", "0001_initial"), ("accounts", "0001_initial")]
        executor.migrate([("customers", "0001_initial")])
        try:
            apps = executor.loader.project_state(old_targets).apps
            Customer = apps.get_model("customers", "Customer")
            Address = apps.get_model("customers", "CustomerAddress")
            User = apps.get_model("accounts", "User")
            user = User.objects.create(username="legacy-account", email="same@example.com")
            customer = Customer.objects.create(display_name="Legacy Buyer", email="same@example.com", phone="+254724853914")
            address = Address.objects.create(customer=customer, county="Bomet", town_or_area="Sotik", address_line="Existing locality", is_default=True)
            before_customer=Customer.objects.filter(pk=customer.pk).values().get()
            before_address=Address.objects.filter(pk=address.pk).values().get()
            before_user=User.objects.filter(pk=user.pk).values().get()
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(leaves)
        apps=executor.loader.project_state(leaves).apps
        after=apps.get_model("customers","Customer").objects.filter(pk=customer.pk).values().get()
        self.assertIsNone(after.pop("owner_id"))
        self.assertIsNone(after.pop("preferred_picking_location_id"))
        self.assertEqual(after,before_customer)
        self.assertEqual(apps.get_model("customers","CustomerAddress").objects.filter(pk=address.pk).values().get(),before_address)
        self.assertEqual(apps.get_model("accounts","User").objects.filter(pk=user.pk).values().get(),before_user)
