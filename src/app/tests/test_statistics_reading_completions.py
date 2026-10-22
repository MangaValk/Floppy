import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from app import stats_reading
from app.models import Book, Item, MediaTypes, Sources, Status
from app.statistics_cache import get_statistics_data


class ReadingCompletionsTests(TestCase):
    """Issue #1379: "Books Finished" must count finished books, not reading days."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reader", password="password123"
        )

    def _book(self, media_id, status, start, end, pages=300, progress=None):
        item = Item.objects.create(
            media_id=media_id,
            source=Sources.MANUAL.value,
            media_type=MediaTypes.BOOK.value,
            title=f"Book {media_id}",
            number_of_pages=pages,
        )
        tz = timezone.get_current_timezone()
        return Book.objects.create(
            user=self.user,
            item=item,
            status=status,
            progress=pages if progress is None else progress,
            start_date=datetime.datetime(*start, 12, 0, tzinfo=tz),
            end_date=datetime.datetime(*end, 12, 0, tzinfo=tz),
        )

    def test_finished_counts_books_not_reading_days(self):
        # One book read over 30 days in 2023, one read in a single day in 2024,
        # one still in progress (must not count as finished).
        self._book("b1", Status.COMPLETED.value, (2023, 1, 1), (2023, 1, 30))
        self._book("b2", Status.COMPLETED.value, (2024, 5, 4), (2024, 5, 4))
        self._book("b3", Status.IN_PROGRESS.value, (2024, 6, 1), (2024, 6, 10), progress=100)

        data = get_statistics_data(self.user, start_date=None, end_date=None)
        book = data["book_consumption"]

        by_year = book["completion_charts"]["by_year"]
        self.assertEqual(by_year["labels"], ["2023", "2024"])
        self.assertEqual(by_year["datasets"][0]["data"], [1, 1])
        self.assertEqual(book["completions"]["total"], 2)


class ReadingRangePrefilterTests(TestCase):
    """The SQL prefilter must never drop a row the date predicate keeps."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reading-prefilter", password="password123"
        )
        tz = timezone.get_current_timezone()
        self.start = timezone.make_aware(datetime.datetime(2024, 1, 1), tz)
        self.end = timezone.make_aware(
            datetime.datetime(2024, 1, 31, 23, 59, 59), tz
        )

    def _book(self, media_id, start=None, end=None, created=None):
        tz = timezone.get_current_timezone()

        def dt(value):
            return (
                timezone.make_aware(datetime.datetime(*value, 12, 0), tz)
                if value
                else None
            )

        item = Item.objects.create(
            media_id=media_id,
            source=Sources.MANUAL.value,
            media_type=MediaTypes.BOOK.value,
            title=f"Book {media_id}",
            number_of_pages=300,
        )
        entry = Book.objects.create(
            user=self.user,
            item=item,
            status=Status.COMPLETED.value,
            progress=300,
            start_date=dt(start),
            end_date=dt(end),
        )
        if created:
            Book.objects.filter(pk=entry.pk).update(created_at=dt(created))
            entry.refresh_from_db()
        return entry

    def test_the_prefilter_is_a_superset_of_the_date_predicate(self):
        entries = {
            "inside": self._book("inside", (2024, 1, 5), (2024, 1, 10)),
            "before": self._book("before", (2023, 11, 1), (2023, 11, 2)),
            "after": self._book("after", (2024, 3, 1), (2024, 3, 2)),
            "spans_start": self._book(
                "spans-start", (2023, 12, 20), (2024, 1, 5)
            ),
            "start_only_inside": self._book("start-only-in", (2024, 1, 8), None),
            "end_only_inside": self._book("end-only-in", None, (2024, 1, 9)),
            "start_only_after": self._book("start-only-out", (2024, 4, 1), None),
            "end_only_before": self._book("end-only-out", None, (2023, 6, 1)),
            "undated_inside": self._book("undated-in", created=(2024, 1, 20)),
            "undated_before": self._book("undated-out", created=(2023, 6, 1)),
        }
        kept = {
            name
            for name, entry in entries.items()
            if stats_reading._reading_entry_in_range(entry, self.start, self.end)
        }
        narrowed = set(
            Book.objects.filter(
                stats_reading._reading_entry_range_filter(self.start, self.end)
            ).values_list("pk", flat=True)
        )

        self.assertEqual(
            kept,
            {
                "inside",
                "spans_start",
                "start_only_inside",
                "end_only_inside",
                "undated_inside",
            },
        )
        self.assertTrue(
            {entries[name].pk for name in kept} <= narrowed,
            "the prefilter dropped a row the date predicate keeps",
        )
        self.assertNotIn(entries["before"].pk, narrowed)
        self.assertNotIn(entries["after"].pk, narrowed)
