from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from accounts.models import UserLogin, UserProfile
from library.copies import (
    HOLD_STATUSES, assign_copy, available_copies, next_copy_number, with_copy_counts,
)
from library.models import BookCopy, Books, BorrowRecords, ConditionChoices, StatusChoices


class CopyFixtures:
    def make_book(self, call_number, **fields):
        return Books.objects.create(
            call_number=call_number, isbn=fields.pop('isbn', ''), title=f'Title {call_number}',
            author='Author', publisher='Publisher', year_published='2000', pages='100', **fields,
        )

    def make_user(self, id_number):
        user = UserLogin.objects.create_user(f'{id_number}@example.com', 'test-password')
        return UserProfile.objects.create(user=user, id_number=id_number)

    def loan(self, copy, status, user=None):
        return BorrowRecords.objects.create(user=user or self.profile, copy=copy, status=status)


class BookCopyConstraintTests(CopyFixtures, TestCase):
    def setUp(self):
        self.profile = self.make_user('reader')
        self.book = self.make_book('100.A1')
        self.copy = BookCopy.objects.create(book=self.book, copy_number=1)

    def test_duplicate_copy_number_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BookCopy.objects.create(book=self.book, copy_number=1)

    def test_same_copy_number_on_another_title_allowed(self):
        BookCopy.objects.create(book=self.make_book('100.A2'), copy_number=1)

    def test_duplicate_nonblank_accession_rejected(self):
        BookCopy.objects.create(book=self.book, copy_number=2, accession_number='ACC-1')
        with self.assertRaises(IntegrityError), transaction.atomic():
            BookCopy.objects.create(book=self.book, copy_number=3, accession_number='ACC-1')

    def test_several_blank_accessions_allowed(self):
        BookCopy.objects.create(book=self.book, copy_number=2, accession_number='')
        BookCopy.objects.create(book=self.book, copy_number=3, accession_number='')
        self.assertEqual(BookCopy.objects.filter(accession_number='').count(), 3)

    def test_second_hold_loan_on_one_copy_rejected(self):
        other = self.make_user('other')
        for first, second in [(StatusChoices.PENDING, StatusChoices.ACTIVE),
                              (StatusChoices.ACTIVE, StatusChoices.PENDING),
                              (StatusChoices.DUE, StatusChoices.OVERDUE)]:
            with self.subTest(first=first, second=second):
                held = self.loan(self.copy, first)
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.loan(self.copy, second, user=other)
                held.delete()

    def test_new_loan_allowed_after_returned_or_cancelled(self):
        self.loan(self.copy, StatusChoices.RETURNED)
        self.loan(self.copy, StatusChoices.CANCELLED)
        self.loan(self.copy, StatusChoices.PENDING)
        self.assertEqual(self.copy.loans.count(), 3)

    def test_loan_book_property_reads_through_copy(self):
        self.assertEqual(self.loan(self.copy, StatusChoices.PENDING).book, self.book)


class CopyAvailabilityTests(CopyFixtures, TestCase):
    def setUp(self):
        self.profile = self.make_user('reader')
        self.book = self.make_book('200.B1')

    def add_copy(self, book=None, **fields):
        book = book or self.book
        return BookCopy.objects.create(book=book, copy_number=next_copy_number(book), **fields)

    def test_hold_statuses(self):
        self.assertEqual(set(HOLD_STATUSES), {
            StatusChoices.PENDING, StatusChoices.ACTIVE, StatusChoices.DUE, StatusChoices.OVERDUE,
        })

    def test_available_excludes_archived_lost_damaged_and_held_copies(self):
        free = self.add_copy()
        self.add_copy(is_archived=True)
        self.add_copy(condition=ConditionChoices.LOST)
        self.add_copy(condition=ConditionChoices.DAMAGED)
        for status in HOLD_STATUSES:
            self.loan(self.add_copy(), status)
        self.assertEqual(list(available_copies(self.book)), [free])

    def test_returned_or_cancelled_loan_frees_copy(self):
        returned, cancelled = self.add_copy(), self.add_copy()
        self.loan(returned, StatusChoices.RETURNED)
        self.loan(cancelled, StatusChoices.CANCELLED)
        self.assertEqual(list(available_copies(self.book)), [returned, cancelled])

    def test_available_without_book_spans_titles_in_copy_order(self):
        other = self.make_book('200.B2')
        first = self.add_copy()
        self.add_copy(other)
        self.assertEqual(available_copies().count(), 2)
        self.assertNotIn(first, available_copies(other))

    def test_with_copy_counts(self):
        self.add_copy()
        self.add_copy()
        self.add_copy(is_archived=True)
        self.add_copy(condition=ConditionChoices.DAMAGED)
        self.loan(self.add_copy(), StatusChoices.ACTIVE)
        empty = self.make_book('200.B3')
        counts = {b.pk: (b.total_copies, b.available_copies) for b in with_copy_counts(Books.objects.all())}
        self.assertEqual(counts, {self.book.pk: (4, 2), empty.pk: (0, 0)})

    def test_assign_copy_returns_lowest_available(self):
        first, second, third = self.add_copy(), self.add_copy(), self.add_copy()
        self.loan(first, StatusChoices.PENDING)
        with transaction.atomic():
            self.assertEqual(assign_copy(self.book), second)
        self.loan(second, StatusChoices.ACTIVE)
        with transaction.atomic():
            self.assertEqual(assign_copy(self.book), third)

    def test_assign_copy_returns_none_when_no_copy_free(self):
        self.loan(self.add_copy(), StatusChoices.OVERDUE)
        self.add_copy(condition=ConditionChoices.LOST)
        with transaction.atomic():
            self.assertIsNone(assign_copy(self.book))
        with transaction.atomic():
            self.assertIsNone(assign_copy(self.make_book('200.B4')))

    def test_next_copy_number_counts_archived_copies(self):
        self.assertEqual(next_copy_number(self.book), 1)
        BookCopy.objects.create(book=self.book, copy_number=1)
        BookCopy.objects.create(book=self.book, copy_number=4, is_archived=True)
        self.assertEqual(next_copy_number(self.book), 5)


class BookCopyMigrationTests(TransactionTestCase):
    before = [('library', '0013_books_is_archived')]
    after = [('library', '0016_finalize_book_copy')]

    def migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def tearDown(self):
        # Later tests expect the latest schema, whatever happened above.
        call_command('migrate', verbosity=0)
        super().tearDown()

    def test_forward_backfill_and_reverse_restore(self):
        apps = self.migrate(self.before)
        Books = apps.get_model('library', 'Books')
        Loans = apps.get_model('library', 'BorrowRecords')
        User = apps.get_model('accounts', 'UserLogin')
        Profile = apps.get_model('accounts', 'UserProfile')
        profile = Profile.objects.create(user=User.objects.create(email='m@example.com', password='x'), id_number='m')

        def book(call_number, condition, date_acquired):
            return Books.objects.create(
                call_number=call_number, title=call_number, author='A', publisher='P',
                year_published='2000', pages='1', condition=condition, date_acquired=date_acquired,
            )

        books = {
            'good': book('300.G', 'good', '2020-01-15'),
            'lost': book('300.L', 'lost', ''),
            'damaged': book('300.D', 'damaged', 'March 2019'),
        }
        loans = {
            Loans.objects.create(user=profile, book=books['good'], status='Returned').pk: books['good'].pk,
            Loans.objects.create(user=profile, book=books['good'], status='Active').pk: books['good'].pk,
            Loans.objects.create(user=profile, book=books['damaged'], status='Cancelled').pk: books['damaged'].pk,
        }
        expected = {b.pk: (b.condition, b.date_acquired) for b in books.values()}

        apps = self.migrate(self.after)
        Copy = apps.get_model('library', 'BookCopy')
        Loans = apps.get_model('library', 'BorrowRecords')
        copies = list(Copy.objects.all())
        self.assertEqual(len(copies), 3)
        for copy in copies:
            self.assertEqual(copy.copy_number, 1)
            self.assertEqual(copy.accession_number, '')
            self.assertFalse(copy.is_archived)
            self.assertEqual((copy.condition, copy.date_acquired), expected[copy.book_id])
        self.assertEqual({l.pk: l.copy.book_id for l in Loans.objects.select_related('copy')}, loans)

        apps = self.migrate(self.before)
        Books = apps.get_model('library', 'Books')
        Loans = apps.get_model('library', 'BorrowRecords')
        self.assertEqual({b.pk: (b.condition, b.date_acquired) for b in Books.objects.all()}, expected)
        self.assertEqual({l.pk: l.book_id for l in Loans.objects.all()}, loans)
