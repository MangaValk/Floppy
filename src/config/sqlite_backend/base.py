import re

from django.db import OperationalError
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.backends.sqlite3.base import DatabaseWrapper as SQLiteDatabaseWrapper
from django.db.backends.sqlite3.features import (
    DatabaseFeatures as SQLiteDatabaseFeatures,
)
from django.db.backends.sqlite3.schema import (
    DatabaseSchemaEditor as SQLiteDatabaseSchemaEditor,
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


_INDEX_DDL = re.compile(
    r"\s*(CREATE\s+(UNIQUE\s+)?INDEX|DROP\s+INDEX)\b", re.IGNORECASE
)


class DatabaseSchemaEditor(SQLiteDatabaseSchemaEditor):
    """Skip the whole-database foreign-key scan after an index-only migration.

    Django's SQLite editor runs ``foreign_key_check`` over every table when it
    exits, so each index migration on a multi-GB database re-reads all child
    tables and probes their parents (about 50s each on a 4 GB test database,
    far more on spinning storage). Creating or dropping an index changes no
    row and no foreign key, so the scan can find nothing new. It is skipped
    only when every statement the editor ran was CREATE/DROP [UNIQUE] INDEX
    and SQLite reports no row changed (a RunPython in the same migration
    would show up there). Anything else, including table rebuilds, still gets
    Django's full check.
    """

    def __enter__(self):
        """Start tracking whether this migration only touches indexes."""
        self._index_only = True
        editor = super().__enter__()
        self._changes_at_enter = self.connection.connection.total_changes
        return editor

    def execute(self, sql, params=()):
        """Record any statement that is not index DDL."""
        if not _INDEX_DDL.match(str(sql)):
            self._index_only = False
        return super().execute(sql, params)

    def __exit__(self, exc_type, exc_value, traceback):
        """Run Django's foreign-key scan unless the migration was index-only."""
        if (
            exc_type is None
            and self._index_only
            and self.connection.connection.total_changes == self._changes_at_enter
        ):
            BaseDatabaseSchemaEditor.__exit__(self, exc_type, exc_value, traceback)
            self.connection.enable_constraint_checking()
            return
        super().__exit__(exc_type, exc_value, traceback)


class DatabaseWrapper(SQLiteDatabaseWrapper):
    """Use Django's SQLite backend with the corrected JSON probe."""

    features_class = DatabaseFeatures
    SchemaEditorClass = DatabaseSchemaEditor
