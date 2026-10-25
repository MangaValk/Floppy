"""Run DB-independent safety suites with the production image's dependencies."""
import unittest

import django
from django.conf import settings

settings.configure(
    SECRET_KEY='test-only', INSTALLED_APPS=[], DATABASES={}, USE_TZ=True,
    STATIC_URL='/static/',
)
django.setup()
labels = [
    'config.tests.test_sqlite_startup_fast_path',
    'config.tests.test_sqlite_recovery_policy',
    'config.tests.test_sqlite_integrity',
    'config.tests.test_sqlite_data_preserving_recovery',
    'config.tests.test_static_collection',
]
result = unittest.TextTestRunner(verbosity=1).run(
    unittest.defaultTestLoader.loadTestsFromNames(labels),
)
raise SystemExit(not result.wasSuccessful())
