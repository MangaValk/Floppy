from django.db import OperationalError
from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper
from django.db.backends.sqlite3.features import (
    DatabaseFeatures as SQLiteDatabaseFeatures,
)
from django.utils.functional import cached_property


class DatabaseFeatures(SQLiteDatabaseFeatures):
    """Keep capability detection independent of SQLite's writer lock."""

    @cached_property
    def supports_json_field(self):
        """Probe JSON without taking IMMEDIATE's write lock for a SELECT.

        Django 5.2 wraps this in atomic() and treats every OperationalError,
        including a busy database, as missing JSON support. A standalone
        SQLite SELECT needs no transaction wrapper; operational failures must
        remain visible instead of being cached as a capability result.
        """
        with self.connection.cursor() as cursor:
            try:
                cursor.execute('SELECT JSON(\'{"a": "b"}\')')
                cursor.fetchone()
            except OperationalError as error:
                if str(error).lower() == "no such function: json":
                    return False
                raise
        return True


class DatabaseWrapper(SQLiteDatabaseWrapper):
    """Use Django's SQLite backend with the corrected JSON probe."""

    features_class = DatabaseFeatures
