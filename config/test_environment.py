from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.environment import (
    allowed_hosts,
    database_config,
    env_bool,
    env_non_negative_int,
    secret_key,
)


class EnvironmentConfigurationTests(SimpleTestCase):
    def test_development_defaults_remain_local_and_sqlite(self):
        self.assertTrue(env_bool("WAYTOP_DEBUG", True, environ={}))
        self.assertTrue(secret_key(debug=True, environ={}).startswith("django-insecure-"))
        database = database_config(base_dir=Path("C:/test"), environ={})["default"]
        self.assertEqual(database["ENGINE"], "django.db.backends.sqlite3")

    def test_production_requires_a_strong_external_secret(self):
        for environment in ({}, {"SECRET_KEY": "short"}, {"SECRET_KEY": "x" * 60}):
            with self.subTest(environment=environment), self.assertRaises(ImproperlyConfigured):
                secret_key(debug=False, environ=environment)
        value = "safe-external-test-value-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        self.assertEqual(secret_key(debug=False, environ={"SECRET_KEY": value}), value)

    def test_production_hosts_are_explicit_normalized_and_non_wildcard(self):
        self.assertEqual(
            allowed_hosts(
                debug=False,
                environ={"ALLOWED_HOSTS": " farm.example,staff.example "},
            ),
            ["farm.example", "staff.example"],
        )
        for environment in ({}, {"ALLOWED_HOSTS": ""}, {"ALLOWED_HOSTS": "*"}):
            with self.subTest(environment=environment), self.assertRaises(
                ImproperlyConfigured
            ):
                allowed_hosts(debug=False, environ=environment)

    def test_postgresql_configuration_is_explicit_and_test_database_is_isolated(self):
        with self.assertRaises(ImproperlyConfigured):
            database_config(
                base_dir=Path("C:/test"),
                environ={"WAYTOP_DATABASE_BACKEND": "postgresql"},
            )
        database = database_config(
            base_dir=Path("C:/test"),
            environ={
                "WAYTOP_DATABASE_BACKEND": "postgresql",
                "POSTGRES_DB": "waytop_runtime",
                "POSTGRES_TEST_DB": "waytop_isolated_test",
                "POSTGRES_USER": "waytop_test",
                "POSTGRES_PASSWORD": "not-a-real-secret",
                "POSTGRES_HOST": "127.0.0.1",
                "POSTGRES_PORT": "5432",
                "POSTGRES_SSLMODE": "require",
            },
        )["default"]
        self.assertEqual(database["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(database["TEST"], {"NAME": "waytop_isolated_test"})
        self.assertEqual(database["OPTIONS"], {"sslmode": "require"})
        self.assertEqual(database["CONN_MAX_AGE"], 0)
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "POSTGRES_TEST_DB must differ from POSTGRES_DB.",
        ):
            database_config(
                base_dir=Path("C:/test"),
                environ={
                    "WAYTOP_DATABASE_BACKEND": "postgresql",
                    "POSTGRES_DB": "waytop_test",
                    "POSTGRES_TEST_DB": "waytop_test",
                    "POSTGRES_USER": "waytop_test",
                    "POSTGRES_PASSWORD": "not-a-real-secret",
                },
            )

    def test_security_environment_values_are_strictly_parsed(self):
        self.assertTrue(env_bool("FLAG", False, environ={"FLAG": "yes"}))
        self.assertFalse(env_bool("FLAG", True, environ={"FLAG": "off"}))
        with self.assertRaises(ImproperlyConfigured):
            env_bool("FLAG", False, environ={"FLAG": "sometimes"})
        self.assertEqual(env_non_negative_int("SECONDS", 0, environ={"SECONDS": "60"}), 60)
        with self.assertRaises(ImproperlyConfigured):
            env_non_negative_int("SECONDS", 0, environ={"SECONDS": "-1"})
