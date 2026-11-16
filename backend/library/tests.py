import csv
import io
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import EducationLevel, RoleChoices, UserLogin, UserProfile
from .copies import available_copies, next_copy_number
from .models import (
    AcademicTerm, BookCopy, Books, BorrowRecords, ConditionChoices, ItemType, LoanFine, StatusChoices,
)


MANILA = ZoneInfo('Asia/Manila')
NOW = datetime(2026, 10, 7, 12, tzinfo=MANILA)


@override_settings(LIBRARY_TIME_ZONE='Asia/Manila')
class DashboardTestCase(TestCase):
    def setUp(self):
        clock = patch('django.utils.timezone.now', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)
        self.user = UserLogin.objects.create_user('reader@example.com', 'test-password')
        self.profile = UserProfile.objects.create(
            user=self.user, id_number='reader', education_level=EducationLevel.COLLEGE, year_level='1',
        )
        self.other_user = UserLogin.objects.create_user('other@example.com', 'test-password')
        self.other = UserProfile.objects.create(
            user=self.other_user, id_number='other', education_level=EducationLevel.SENIOR_HIGH, year_level='11',
        )
        self.book = self.make_book('600.T932 1991')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def make_book(self, call_number, **fields):
        # Like addBook/, a new title starts with copy 1.
        book = Books.objects.create(
            call_number=call_number, title=f'Book {call_number}', author='Author',
            publisher='Publisher', year_published='2026', pages='100', **fields,
        )
        self.make_copy(book)
        return book

    def make_copy(self, book, **fields):
        return BookCopy.objects.create(book=book, copy_number=next_copy_number(book), **fields)

    def loan(self, **changes):
        # Each open loan needs its own copy, so take a free one or add another to the title.
        book = changes.pop('book', self.book)
        if 'copy' not in changes:
            changes['copy'] = available_copies(book).first() or self.make_copy(book)
        values = dict(user=self.profile, borrow_date=NOW - timedelta(days=2),
                      due_date=date(2026, 10, 10), status=StatusChoices.ACTIVE)
        values.update(changes)
        return BorrowRecords.objects.create(**values)

    def term(self, **changes):
        values = dict(academic_year='2026-2027', semester='1', education_level=EducationLevel.COLLEGE,
                      start_date=date(2026, 9, 1), end_date=date(2027, 1, 31))
        values.update(changes)
        return AcademicTerm.objects.create(**values)

    def analytics(self):
        response = self.client.get(reverse('get_user_analytics'))
        self.assertEqual(response.status_code, 200, response.data)
        return response.data


class UserDashboardAPITests(DashboardTestCase):
    endpoints = ('get_user_analytics', 'get_user_current_loans', 'get_user_borrowing_history')

    def test_endpoints_require_authentication_and_only_allow_get(self):
        for endpoint in self.endpoints:
            with self.subTest(endpoint=endpoint):
                self.client.force_authenticate(None)
                self.assertEqual(self.client.get(reverse(endpoint)).status_code, 401)
                self.client.force_authenticate(self.user)
                self.assertEqual(self.client.post(reverse(endpoint), {}).status_code, 405)

    def test_real_jwt_authentication_scopes_results_to_token_owner(self):
        self.loan()
        self.loan(user=self.other)
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.assertEqual(self.analytics()['statistics']['currently_borrowed'], 1)

    def test_missing_profile_returns_404(self):
        self.profile.delete()
        self.user = UserLogin.objects.get(pk=self.user.pk)
        self.client.force_authenticate(self.user)
        for endpoint in self.endpoints:
            self.assertEqual(self.client.get(reverse(endpoint)).status_code, 404)

    def test_user_identifiers_cannot_select_another_borrower(self):
        own = self.loan()
        other = self.loan(user=self.other)
        LoanFine.objects.create(loan=other, amount_assessed='100.00')
        spoof = {'id': self.other.pk, 'user_id': self.other.pk, 'id_number': self.other.id_number}
        stats = self.client.get(reverse('get_user_analytics'), spoof).data
        self.assertEqual(stats['history_summary']['total_borrowed'], 1)
        self.assertEqual(stats['history_summary']['fine']['outstanding'], '0.00')
        self.assertEqual(stats['most_borrowed_subjects']['total_borrowed'], 1)
        self.assertEqual(sum(row['count'] for row in stats['borrowing_frequency']), 1)
        for endpoint in self.endpoints[1:]:
            response = self.client.get(reverse(endpoint), spoof)
            self.assertEqual([row['loan_id'] for row in response.data['results']], [own.pk])
            self.assertNotIn('email', response.data['results'][0])

    def test_empty_dashboard_has_zero_counts_and_six_empty_months(self):
        self.term()
        data = self.analytics()
        self.assertEqual(data['statistics'], {
            'currently_borrowed': 0, 'due_soon': 0, 'overdue': 0, 'books_this_semester': 0,
        })
        self.assertEqual(data['most_borrowed_subjects'], {'total_borrowed': 0, 'subjects': []})
        self.assertEqual([row['month'] for row in data['borrowing_frequency']],
                         ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'])
        self.assertTrue(all(row['count'] == 0 for row in data['borrowing_frequency']))
        self.assertEqual(data['history_summary']['fine']['outstanding'], '0.00')
        for endpoint in self.endpoints[1:]:
            response = self.client.get(reverse(endpoint))
            self.assertEqual(response.data['results'], [])
            self.assertEqual(response.data['count'], 0)

    def test_counts_use_checkouts_and_due_dates_not_stale_status(self):
        self.term()
        self.loan(due_date=date(2026, 10, 6))  # Stale Active, actually overdue.
        self.loan(due_date=date(2026, 10, 7), status=StatusChoices.OVERDUE)  # Due today.
        self.loan(due_date=date(2026, 10, 10))
        self.loan(due_date=date(2026, 10, 11), status=StatusChoices.DUE)
        self.loan(due_date=None)
        self.loan(status=StatusChoices.RETURNED, return_date=date(2026, 10, 6), due_date=date(2026, 10, 5))
        self.loan(status=StatusChoices.PENDING, borrow_date=None)
        self.loan(status=StatusChoices.CANCELLED, return_date=date(2026, 10, 6))
        self.loan(borrow_date=None)
        self.loan(borrow_date=NOW + timedelta(days=1))
        data = self.analytics()
        self.assertEqual(data['statistics'], {
            'currently_borrowed': 5, 'due_soon': 2, 'overdue': 1, 'books_this_semester': 6,
        })
        self.assertEqual(data['history_summary']['total_borrowed'], 6)
        self.assertEqual(data['history_summary']['late_returned'], 1)
        self.assertEqual(data['due_soon_window'], {'start_date': '2026-10-07', 'end_date': '2026-10-10'})

    def test_due_soon_rolls_over_on_sunday_in_manila(self):
        # Saturday UTC is already Sunday in the library.
        sunday = datetime(2026, 10, 10, 16, 0, tzinfo=datetime_timezone.utc)
        self.loan(due_date=date(2026, 10, 10))
        self.loan(due_date=date(2026, 10, 11))
        self.loan(due_date=date(2026, 10, 17))
        self.loan(due_date=date(2026, 10, 18))
        with patch('django.utils.timezone.now', return_value=sunday):
            data = self.analytics()
        self.assertEqual(data['statistics']['due_soon'], 2)
        self.assertEqual(data['statistics']['overdue'], 1)
        self.assertEqual(data['due_soon_window'], {'start_date': '2026-10-11', 'end_date': '2026-10-17'})

    def test_due_soon_on_saturday_is_today_only(self):
        self.loan(due_date=date(2026, 10, 10))
        self.loan(due_date=date(2026, 10, 11))
        with patch('django.utils.timezone.now', return_value=datetime(2026, 10, 10, 12, tzinfo=MANILA)):
            data = self.analytics()
        self.assertEqual(data['statistics']['due_soon'], 1)
        self.assertEqual(data['due_soon_window']['end_date'], '2026-10-10')

    def test_frequency_uses_local_month_boundaries_and_counts_repeat_checkouts(self):
        before_may = datetime(2026, 4, 30, 15, 59, tzinfo=datetime_timezone.utc)
        start_may = datetime(2026, 4, 30, 16, 0, tzinfo=datetime_timezone.utc)
        start_october = datetime(2026, 9, 30, 16, 0, tzinfo=datetime_timezone.utc)
        self.loan(borrow_date=before_may)
        self.loan(borrow_date=start_may, status=StatusChoices.RETURNED, return_date=date(2026, 5, 3))
        self.loan(borrow_date=start_october)
        self.loan(borrow_date=NOW)
        self.loan(borrow_date=NOW, status=StatusChoices.PENDING)
        self.loan(borrow_date=NOW, status=StatusChoices.CANCELLED)
        data = self.analytics()
        self.assertEqual([row['count'] for row in data['borrowing_frequency']], [1, 0, 0, 0, 0, 2])
        self.assertEqual(data['history_summary']['total_borrowed'], 4)

    def test_frequency_handles_year_transition(self):
        with patch('django.utils.timezone.now', return_value=datetime(2026, 1, 1, tzinfo=MANILA)):
            months = self.analytics()['borrowing_frequency']
        self.assertEqual([row['month'] for row in months],
                         ['2025-08', '2025-09', '2025-10', '2025-11', '2025-12', '2026-01'])

    def test_subjects_group_dewey_classes_and_keep_other_counts(self):
        for number in ('600.A', '600.B', '601.C', '100.A', '199.B', '300.A', '400.A', '500.A', '800.A', 'REF unknown'):
            self.loan(book=self.make_book(number))
        data = self.analytics()['most_borrowed_subjects']
        self.assertEqual(data['total_borrowed'], 10)
        self.assertEqual([row['code'] for row in data['subjects']], ['600', '100', '300', '400', '500', 'other'])
        self.assertEqual(data['subjects'][0]['count'], 3)
        self.assertEqual(data['subjects'][0]['percentage'], 30)
        self.assertEqual(data['subjects'][-1]['count'], 2)
        self.assertEqual(sum(row['count'] for row in data['subjects']), 10)

    def test_general_information_and_unclassified_subjects(self):
        for number in ('000.A', '001.A82 2023', '099.C', '1000.invalid', 'Fiction'):
            self.loan(book=self.make_book(number))
        rows = self.analytics()['most_borrowed_subjects']['subjects']
        self.assertEqual([(row['code'], row['count']) for row in rows], [('001', 3), ('unclassified', 2)])

    def test_current_table_has_pending_and_derived_statuses_with_stable_ids(self):
        pending = self.loan(status=StatusChoices.PENDING, borrow_date=None, due_date=None)
        overdue = self.loan(due_date=date(2026, 10, 6))
        due = self.loan(due_date=date(2026, 10, 7))
        active = self.loan(status=StatusChoices.OVERDUE)
        self.loan(status=StatusChoices.RETURNED, return_date=date(2026, 10, 6))
        self.loan(status=StatusChoices.CANCELLED)
        response = self.client.get(reverse('get_user_current_loans'))
        rows = {row['loan_id']: row for row in response.data['results']}
        self.assertEqual(set(rows), {pending.pk, overdue.pk, due.pk, active.pk})
        self.assertIsNone(rows[pending.pk]['borrow_date'])
        self.assertIsNone(rows[pending.pk]['due_date'])
        self.assertEqual(rows[pending.pk]['status'], 'Pending')
        self.assertEqual(rows[overdue.pk]['status'], 'Overdue')
        self.assertEqual(rows[due.pk]['status'], 'Due')
        self.assertEqual(rows[active.pk]['status'], 'Active')
        self.assertEqual(rows[active.pk]['title'], self.book.title)
        self.assertEqual(rows[active.pk]['book_id'], self.book.pk)

    def test_history_includes_actual_loans_and_paid_amount_not_pending_or_cancelled(self):
        active = self.loan()
        returned = self.loan(status=StatusChoices.RETURNED, return_date=date(2026, 10, 6))
        LoanFine.objects.create(loan=returned, amount_assessed='25.50', amount_paid='10.25')
        self.loan(status=StatusChoices.PENDING, borrow_date=None)
        self.loan(status=StatusChoices.CANCELLED, return_date=date(2026, 10, 6))
        response = self.client.get(reverse('get_user_borrowing_history'))
        rows = {row['loan_id']: row for row in response.data['results']}
        self.assertEqual(set(rows), {active.pk, returned.pk})
        self.assertIsNone(rows[active.pk]['return_date'])
        self.assertEqual(rows[returned.pk]['return_date'], '2026-10-06')
        self.assertEqual(rows[returned.pk]['fine']['amount_paid'], '10.25')
        self.assertEqual(response.data['summary']['fine']['outstanding'], '15.25')

    def test_pagination_has_no_duplicates_and_summary_is_not_page_limited(self):
        expected = [self.loan().pk for _ in range(5)][::-1]
        for endpoint in self.endpoints[1:]:
            seen = []
            for page in (1, 2, 3):
                response = self.client.get(reverse(endpoint), {'page': page, 'page_size': 2})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['count'], 5)
                seen.extend(row['loan_id'] for row in response.data['results'])
                if endpoint == 'get_user_borrowing_history':
                    self.assertEqual(response.data['summary']['total_borrowed'], 5)
            self.assertEqual(seen, expected)
            self.assertIsNone(response.data['next'])
            self.assertIsNotNone(response.data['previous'])

    def test_invalid_pagination_returns_client_errors(self):
        for endpoint in self.endpoints[1:]:
            for params in ({'page': 0}, {'page': 'bad'}, {'page_size': 0}, {'page_size': 101}, {'page_size': 'bad'}):
                with self.subTest(endpoint=endpoint, params=params):
                    self.assertEqual(self.client.get(reverse(endpoint), params).status_code, 400)
            self.assertEqual(self.client.get(reverse(endpoint), {'page': 99}).status_code, 404)

    def test_table_query_count_does_not_grow_per_loan(self):
        for _ in range(10):
            LoanFine.objects.create(loan=self.loan(), amount_assessed='10.00')
        # The already-cached profile needs no query: COUNT plus one joined page query.
        with self.assertNumQueries(2):
            response = self.client.get(reverse('get_user_current_loans'))
            self.assertEqual(len(response.data['results']), 10)

    def test_checkout_and_return_store_library_local_dates(self):
        loan = self.loan(status=StatusChoices.PENDING, borrow_date=None, due_date=None)
        payload = {'loan_id': loan.pk}
        # UTC Oct 6, but the library has already reached Oct 7.
        checkout = datetime(2026, 10, 6, 16, 30, tzinfo=datetime_timezone.utc)
        with patch('django.utils.timezone.now', return_value=checkout):
            response = self.client.put(reverse('accept_borrowed_book'), payload)
        self.assertEqual(response.status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.due_date, date(2026, 10, 14))
        self.assertEqual(loan.borrow_date, checkout)
        LoanFine.objects.create(loan=loan, amount_assessed='25.00')
        returned = datetime(2026, 10, 14, 16, 30, tzinfo=datetime_timezone.utc)
        with patch('django.utils.timezone.now', return_value=returned):
            response = self.client.put(reverse('return_book'), {**payload, 'action': 'return'})
            data = self.analytics()
        self.assertEqual(response.status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.return_date, date(2026, 10, 15))
        self.assertEqual(data['history_summary']['late_returned'], 1)
        self.assertEqual(data['history_summary']['fine']['outstanding'], '25.00')


class AcademicTermTests(DashboardTestCase):
    def test_unknown_profile_and_unconfigured_or_inactive_terms_do_not_fake_zero(self):
        self.assertEqual(self.analytics()['academic_term']['status'], 'not_configured')
        self.assertIsNone(self.analytics()['statistics']['books_this_semester'])
        self.term(start_date=date(2026, 11, 1))
        self.assertEqual(self.analytics()['academic_term']['status'], 'no_active_term')
        self.profile.education_level = ''
        self.profile.save()
        self.assertEqual(self.analytics()['academic_term']['status'], 'profile_incomplete')

    def test_blank_year_level_follows_default_term_not_overrides(self):
        default = self.term()
        self.term(year_level='1', start_date=date(2026, 10, 1))
        self.profile.year_level = ''
        self.profile.save()
        self.assertEqual(self.analytics()['academic_term']['term']['id'], default.pk)

    def test_year_override_takes_precedence_before_date_filtering(self):
        self.term()
        override = self.term(year_level='1', start_date=date(2026, 10, 15))
        self.assertEqual(self.analytics()['academic_term']['status'], 'no_active_term')
        override.start_date = date(2026, 10, 1)
        override.save()
        self.loan(borrow_date=datetime(2026, 9, 15, tzinfo=MANILA))
        self.loan()
        data = self.analytics()
        self.assertEqual(data['academic_term']['term']['id'], override.pk)
        self.assertEqual(data['statistics']['books_this_semester'], 1)

    def test_default_applies_to_other_years_and_different_education_has_own_term(self):
        default = self.term(year_level='')
        self.term(year_level='2', start_date=date(2026, 10, 15))
        high_school = self.term(education_level=EducationLevel.SENIOR_HIGH, start_date=date(2026, 8, 1))
        self.assertEqual(self.analytics()['academic_term']['term']['id'], default.pk)
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.analytics()['academic_term']['term']['id'], high_school.pk)

    def test_old_academic_year_override_does_not_affect_new_year(self):
        self.term(academic_year='2025-2026', year_level='1',
                  start_date=date(2025, 10, 1), end_date=date(2026, 2, 1))
        current = self.term()
        self.assertEqual(self.analytics()['academic_term']['term']['id'], current.pk)

    def test_semester_boundaries_are_inclusive_in_manila(self):
        self.term(start_date=date(2026, 10, 1), end_date=date(2026, 10, 7))
        self.loan(borrow_date=datetime(2026, 9, 30, 15, 59, tzinfo=datetime_timezone.utc))
        self.loan(borrow_date=datetime(2026, 9, 30, 16, 0, tzinfo=datetime_timezone.utc))
        self.loan(borrow_date=datetime(2026, 10, 7, 15, 59, tzinfo=datetime_timezone.utc))
        self.loan(borrow_date=datetime(2026, 10, 7, 16, 0, tzinfo=datetime_timezone.utc))
        with patch('django.utils.timezone.now', return_value=datetime(2026, 10, 7, 23, 59, 59, tzinfo=MANILA)):
            self.assertEqual(self.analytics()['statistics']['books_this_semester'], 2)
        with patch('django.utils.timezone.now', return_value=datetime(2026, 10, 8, tzinfo=MANILA)):
            self.assertEqual(self.analytics()['academic_term']['status'], 'no_active_term')

    def test_overlapping_effective_terms_validate_and_runtime_reports_conflict(self):
        self.term()
        overlap = AcademicTerm(academic_year='2026-2027', semester='2', education_level='college',
                               start_date=date(2026, 10, 1), end_date=date(2027, 2, 1))
        with self.assertRaises(ValidationError):
            overlap.full_clean()
        # Imported legacy data can bypass model validation; never silently pick one.
        overlap.save()
        data = self.analytics()
        self.assertEqual(data['academic_term']['status'], 'conflict')
        self.assertIsNone(data['statistics']['books_this_semester'])

    def test_default_and_override_can_overlap_intentionally(self):
        self.term()
        override = AcademicTerm(academic_year='2026-2027', semester='1', education_level='college', year_level='1',
                                start_date=date(2026, 10, 1), end_date=date(2027, 2, 1))
        override.full_clean()
        override.save()
        self.assertEqual(self.analytics()['academic_term']['term']['id'], override.pk)

    def test_database_rejects_duplicate_null_empty_and_exact_scopes(self):
        self.term()
        for year in (None, ''):
            with self.subTest(year=year), self.assertRaises(IntegrityError), transaction.atomic():
                self.term(year_level=year)
        self.term(year_level='1')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.term(year_level='1')
        self.term(semester='2', year_level='')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.term(semester='2', year_level=None)

    def test_invalid_date_order_is_rejected_but_single_day_term_is_valid(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.term(start_date=date(2026, 10, 8), end_date=date(2026, 10, 7))
        self.term(start_date=date(2026, 10, 7), end_date=date(2026, 10, 7))
        self.assertEqual(self.analytics()['academic_term']['status'], 'active')

    def test_profile_and_term_year_levels_use_numeric_values(self):
        self.profile.year_level = 'Freshman'
        with self.assertRaises(ValidationError):
            self.profile.full_clean()
        invalid = AcademicTerm(academic_year='2026-2027', semester='1', education_level='college', year_level='01',
                               start_date=date(2026, 9, 1), end_date=date(2027, 1, 1))
        with self.assertRaises(ValidationError):
            invalid.full_clean()


class LoanFineTests(DashboardTestCase):
    def test_partial_and_full_payments_and_returned_unpaid_fines(self):
        returned = self.loan(status=StatusChoices.RETURNED, return_date=date(2026, 10, 6))
        first = LoanFine.objects.create(loan=returned, amount_assessed='50.50', amount_paid='10.25')
        LoanFine.objects.create(loan=self.loan(), amount_assessed='25.00', amount_paid='25.00')
        LoanFine.objects.create(loan=self.loan(user=self.other), amount_assessed='999.00')
        fine = self.analytics()['history_summary']['fine']
        self.assertEqual(fine, {'currency': 'PHP', 'amount_assessed': '75.50', 'amount_paid': '35.25', 'outstanding': '40.25'})
        first.amount_paid = Decimal('50.50')
        first.save()
        self.assertEqual(self.analytics()['history_summary']['fine']['outstanding'], '0.00')

    def test_no_automatic_charge_for_overdue_loan(self):
        self.loan(due_date=date(2026, 1, 1))
        self.assertEqual(self.analytics()['history_summary']['fine']['outstanding'], '0.00')

    def test_invalid_amounts_rejected_by_model_and_database(self):
        loan = self.loan()
        for assessed, paid in (('-1.00', '0.00'), ('10.00', '-1.00'), ('10.00', '10.01')):
            with self.subTest(assessed=assessed, paid=paid):
                with self.assertRaises(ValidationError):
                    LoanFine.objects.create(loan=loan, amount_assessed=assessed, amount_paid=paid)
                with self.assertRaises(IntegrityError), transaction.atomic():
                    LoanFine.objects.bulk_create([LoanFine(loan=loan, amount_assessed=assessed, amount_paid=paid)])

    def test_pending_and_cancelled_requests_cannot_receive_fines(self):
        for status in (StatusChoices.PENDING, StatusChoices.CANCELLED):
            with self.subTest(status=status), self.assertRaises(ValidationError):
                LoanFine.objects.create(loan=self.loan(status=status), amount_assessed='25.00')
        with self.assertRaises(ValidationError):
            LoanFine.objects.create(loan=self.loan(borrow_date=None), amount_assessed='25.00')

    def test_one_fine_per_loan_and_loan_is_protected_from_deletion(self):
        loan = self.loan()
        LoanFine.objects.create(loan=loan, amount_assessed='25.00')
        with self.assertRaises(ValidationError):
            LoanFine.objects.create(loan=loan, amount_assessed='10.00')
        with self.assertRaises(ProtectedError):
            loan.delete()


class ItemIdentityTests(DashboardTestCase):
    """Theses usually have no ISBN, so item flows identify an item by its primary key."""

    def thesis_data(self, call_number, **changes):
        values = dict(item_type=ItemType.THESIS, call_number=call_number, isbn='',
                      title=f'Thesis {call_number}', author='Student', publisher='College',
                      year_published='2026', pages='80')
        values.update(changes)
        return values

    def thesis(self, call_number, **changes):
        thesis = Books.objects.create(**self.thesis_data(call_number, **changes))
        self.make_copy(thesis)
        return thesis

    def post(self, endpoint, payload):
        return self.client.post(reverse(endpoint), payload, format='json')

    def put(self, endpoint, payload):
        return self.client.put(reverse(endpoint), payload, format='json')

    def borrow(self, book, profile=None):
        return self.post('borrow_book', {'id_number': (profile or self.profile).id_number, 'book_id': book.pk})

    def test_two_theses_without_isbn_can_be_added(self):
        self.assertEqual(self.post('add_book', self.thesis_data('T 001.A 2026')).status_code, 201)
        omitted = self.thesis_data('T 001.B 2026')
        del omitted['isbn']
        response = self.post('add_book', omitted)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Books.objects.filter(item_type=ItemType.THESIS, isbn='').count(), 2)

    def test_books_still_require_a_unique_isbn(self):
        book = self.thesis_data('500.A 2026', item_type=ItemType.BOOK)
        self.assertEqual(self.post('add_book', book).status_code, 400)
        book['isbn'] = '9780000000001'
        self.assertEqual(self.post('add_book', book).status_code, 201)
        for item_type in (ItemType.BOOK, ItemType.THESIS):
            with self.subTest(item_type=item_type):
                duplicate = {**book, 'call_number': f'500.B 2026 {item_type}', 'item_type': item_type}
                response = self.post('add_book', duplicate)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['message'], 'Book already exists')

    def test_database_enforces_isbn_uniqueness_only_when_present(self):
        self.thesis('T 1')
        self.thesis('T 2')
        self.thesis('T 3', isbn='9780000000001')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.thesis('T 4', isbn='9780000000001')

    def test_listings_expose_the_item_id(self):
        thesis = self.thesis('T 1')
        self.loan(book=thesis)
        books = self.client.get(reverse('get_books')).data['data']
        self.assertIn(thesis.pk, [row['id'] for row in books])
        loans = self.client.get(reverse('get_all_borrowed_books')).data['data']
        self.assertEqual([row['book']['id'] for row in loans], [thesis.pk])

    def test_borrowing_one_thesis_without_isbn_does_not_affect_another(self):
        first, second = self.thesis('T 1'), self.thesis('T 2')
        for thesis in (second, first):
            response = self.borrow(thesis)
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(sorted(BorrowRecords.objects.values_list('copy__book_id', flat=True)),
                         sorted([first.pk, second.pk]))

    def test_editing_one_thesis_without_isbn_leaves_others_unchanged(self):
        first, second = self.thesis('T 1'), self.thesis('T 2')
        response = self.put('edit_book', {'book_id': second.pk, 'title': 'Revised',
                                          'call_number': 'T 2 rev', 'year_published': '2025'})
        self.assertEqual(response.status_code, 200, response.data)
        second.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual((second.title, second.call_number, second.year_published), ('Revised', 'T 2 rev', '2025'))
        self.assertEqual((first.title, first.call_number), ('Thesis T 1', 'T 1'))
        self.assertEqual(self.put('edit_book', {'book_id': second.pk, 'call_number': 'T 1'}).status_code, 400)

    def test_missing_or_unknown_item_id_is_a_client_error(self):
        requests = (('edit_book', self.put, {}), ('borrow_book', self.post, {'id_number': self.profile.id_number}))
        for endpoint, send, base in requests:
            for book_id, expected in ((None, 400), ('abc', 400), (999999, 404)):
                with self.subTest(endpoint=endpoint, book_id=book_id):
                    payload = base if book_id is None else {**base, 'book_id': book_id}
                    self.assertEqual(send(endpoint, payload).status_code, expected)

    def test_circulation_actions_target_the_requested_loan(self):
        first, second = self.thesis('T 1'), self.thesis('T 2')
        first_loan = self.loan(book=first, status=StatusChoices.PENDING, borrow_date=None, due_date=None)
        second_loan = self.loan(book=second, status=StatusChoices.PENDING, borrow_date=None, due_date=None)
        self.assertEqual(self.put('accept_borrowed_book', {'loan_id': second_loan.pk}).status_code, 200)
        self.assertEqual(self.put('cancel_borrowed_book', {'loan_id': first_loan.pk}).status_code, 200)
        self.assertEqual(self.put('return_book', {'loan_id': second_loan.pk}).status_code, 200)
        first_loan.refresh_from_db()
        second_loan.refresh_from_db()
        self.assertEqual(first_loan.status, StatusChoices.CANCELLED)
        self.assertEqual(second_loan.status, StatusChoices.RETURNED)

    def test_accept_rejects_a_cancelled_request(self):
        cancelled = self.loan(status=StatusChoices.CANCELLED, borrow_date=None, due_date=None)
        pending = self.loan(status=StatusChoices.PENDING, borrow_date=None, due_date=None)
        self.assertEqual(self.put('accept_borrowed_book', {'loan_id': cancelled.pk}).status_code, 404)
        self.assertEqual(self.put('accept_borrowed_book', {'loan_id': pending.pk}).status_code, 200)
        pending.refresh_from_db()
        cancelled.refresh_from_db()
        self.assertEqual(pending.status, StatusChoices.ACTIVE)
        self.assertEqual(cancelled.status, StatusChoices.CANCELLED)

    def test_open_loan_on_the_only_copy_blocks_a_new_borrow(self):
        for status in (StatusChoices.ACTIVE, StatusChoices.DUE, StatusChoices.OVERDUE, StatusChoices.PENDING):
            with self.subTest(status=status):
                self.loan(status=status)
                response = self.borrow(self.book, self.other)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['message'], 'All copies are currently borrowed')
                self.assertFalse(BorrowRecords.objects.filter(user=self.other).exists())
                BorrowRecords.objects.all().delete()
        self.loan(status=StatusChoices.RETURNED, return_date=date(2026, 10, 6))
        self.loan(status=StatusChoices.CANCELLED)
        self.assertEqual(self.borrow(self.book, self.other).status_code, 200)


class CopyAPITestCase(DashboardTestCase):
    """Shared helpers for the copy-aware catalog and loan endpoints."""

    def setUp(self):
        super().setUp()
        self.admin_user = UserLogin.objects.create_user('admin@example.com', 'test-password', role=RoleChoices.ADMIN)
        self.admin = APIClient()
        self.admin.force_authenticate(self.admin_user)
        self.third_user = UserLogin.objects.create_user('third@example.com', 'test-password')
        self.third = UserProfile.objects.create(
            user=self.third_user, id_number='third', education_level=EducationLevel.COLLEGE, year_level='2',
        )

    def post(self, endpoint, payload, client=None):
        return (client or self.client).post(reverse(endpoint), payload, format='json')

    def put(self, endpoint, payload, client=None):
        return (client or self.client).put(reverse(endpoint), payload, format='json')

    def borrow(self, book, profile=None):
        return self.post('borrow_book', {'id_number': (profile or self.profile).id_number, 'book_id': book.pk})

    def book_data(self, call_number, **changes):
        values = dict(call_number=call_number, isbn='', item_type=ItemType.THESIS, title=f'Thesis {call_number}',
                      author='Student', publisher='College', year_published='2026', pages='80')
        values.update(changes)
        return values

    def listed(self, book):
        rows = self.client.get(reverse('get_books')).data['data']
        return next(row for row in rows if row['id'] == book.pk)


class CatalogCopyTests(CopyAPITestCase):
    def test_get_books_lists_counts_and_circulating_copies_in_order(self):
        self.make_copy(self.book, condition=ConditionChoices.DAMAGED)       # c.2
        self.make_copy(self.book, accession_number='ACC-3')                 # c.3
        self.make_copy(self.book, is_archived=True)                         # c.4
        self.loan(copy=BookCopy.objects.get(book=self.book, copy_number=1), status=StatusChoices.PENDING)
        archived_title = self.make_book('900.ARCHIVED', is_archived=True)
        rows = self.client.get(reverse('get_books')).data['data']
        self.assertNotIn(archived_title.pk, [row['id'] for row in rows])
        row = self.listed(self.book)
        self.assertNotIn('condition', row)
        self.assertNotIn('date_acquired', row)
        self.assertEqual((row['total_copies'], row['available_copies']), (3, 1))
        self.assertEqual([(c['copy_number'], c['is_available']) for c in row['copies']],
                         [(1, False), (2, False), (3, True)])
        self.assertEqual(set(row['copies'][0]), {
            'id', 'copy_number', 'accession_number', 'condition', 'date_acquired', 'is_available',
        })
        self.assertEqual(row['copies'][2]['accession_number'], 'ACC-3')
        self.assertEqual(row['copies'][1]['condition'], 'damaged')

    def test_get_books_query_count_does_not_grow_with_titles_or_copies(self):
        with CaptureQueriesContext(connection) as small:
            self.client.get(reverse('get_books'))
        for number in range(5):
            book = self.make_book(f'700.{number}')
            for _ in range(3):
                self.make_copy(book)
            self.loan(book=book, status=StatusChoices.PENDING)
        with self.assertNumQueries(len(small.captured_queries)):
            response = self.client.get(reverse('get_books'))
        self.assertEqual(len(response.data['data']), 6)
        self.assertEqual(sum(len(row['copies']) for row in response.data['data']), 21)

    def test_add_book_creates_title_and_copy_one(self):
        response = self.post('add_book', self.book_data('T 10', accession_number='ACC-10',
                                                         date_acquired='2026-01-05', condition='damaged'))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data, {'message': 'Book Successfully Added!'})
        copy = BookCopy.objects.get(book__call_number='T 10')
        self.assertEqual((copy.copy_number, copy.accession_number, copy.date_acquired, copy.condition),
                         (1, 'ACC-10', '2026-01-05', 'damaged'))

    def test_add_book_copy_fields_are_optional(self):
        self.assertEqual(self.post('add_book', self.book_data('T 11', condition=None)).status_code, 201)
        copy = BookCopy.objects.get(book__call_number='T 11')
        self.assertEqual((copy.copy_number, copy.accession_number, copy.date_acquired, copy.condition),
                         (1, '', '', 'good'))

    def test_add_book_rejects_bad_copy_fields_without_creating_a_title(self):
        self.make_copy(self.book, accession_number='ACC-1')
        cases = (({'accession_number': 'ACC-1'}, 'Accession number already exists'),
                 ({'condition': 'shiny'}, 'Invalid condition'),
                 ({'condition': ''}, 'Invalid condition'))
        for fields, message in cases:
            with self.subTest(fields=fields):
                response = self.post('add_book', self.book_data('T 12', **fields))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['message'], message)
                self.assertFalse(Books.objects.filter(call_number='T 12').exists())

    def test_add_book_is_atomic_when_the_copy_cannot_be_saved(self):
        with patch('library.views.CopyFieldsSerializer.save', side_effect=IntegrityError):
            response = self.post('add_book', self.book_data('T 13'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Books.objects.filter(call_number='T 13').exists())

    def test_add_book_keeps_missing_field_and_unarchive_rules(self):
        response = self.post('add_book', {'call_number': 'T 14', 'title': 'No author'})
        self.assertEqual((response.status_code, response.data['message']), (400, 'Missing important fields'))
        archived = self.make_book('T 15', is_archived=True)
        response = self.post('add_book', self.book_data('T 15', isbn=''))
        self.assertEqual((response.status_code, response.data['message']), (200, 'Book Successfully Added!'))
        archived.refresh_from_db()
        self.assertFalse(archived.is_archived)
        self.assertEqual(archived.copies.count(), 1)

    def test_edit_book_ignores_copy_and_count_keys(self):
        copy = self.book.copies.get()
        response = self.put('edit_book', {
            'book_id': self.book.pk, 'title': 'Renamed', 'condition': 'lost', 'date_acquired': '1999',
            'copies': [], 'total_copies': 9, 'available_copies': 9,
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['message'], 'Book Successfully Edited')
        copy.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, 'Renamed')
        self.assertEqual((copy.condition, copy.date_acquired), ('good', ''))
        self.assertEqual(self.book.copies.count(), 1)

    def test_remove_book_still_archives_the_title(self):
        response = self.post('remove_book', {'book_id': self.book.pk})
        self.assertEqual((response.status_code, response.data['message']), (200, 'Book successfully removed'))
        self.book.refresh_from_db()
        self.assertTrue(self.book.is_archived)


class CopyEndpointTests(CopyAPITestCase):
    def test_copy_endpoints_are_admin_only(self):
        copy = self.book.copies.get()
        calls = (('add_copy', self.post, {'book_id': self.book.pk}),
                 ('edit_copy', self.put, {'copy_id': copy.pk, 'condition': 'lost'}),
                 ('remove_copy', self.post, {'copy_id': copy.pk}))
        anonymous = APIClient()
        for endpoint, send, payload in calls:
            with self.subTest(endpoint=endpoint):
                self.assertEqual(send(endpoint, payload).status_code, 403)
                self.assertEqual(send(endpoint, payload, anonymous).status_code, 401)
        self.assertEqual(BookCopy.objects.count(), 1)
        copy.refresh_from_db()
        self.assertEqual((copy.condition, copy.is_archived), ('good', False))

    def test_add_copy_with_only_book_id_takes_the_next_number(self):
        response = self.post('add_copy', {'book_id': self.book.pk}, self.admin)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['message'], 'Copy added')
        new = BookCopy.objects.get(book=self.book, copy_number=2)
        self.assertEqual(response.data['copy'], {
            'id': new.pk, 'copy_number': 2, 'accession_number': '', 'condition': 'good',
            'date_acquired': '', 'is_available': True,
        })

    def test_add_copy_stores_fields_and_never_reuses_an_archived_number(self):
        self.make_copy(self.book, is_archived=True)  # c.2
        response = self.post('add_copy', {'book_id': self.book.pk, 'accession_number': 'ACC-9',
                                          'date_acquired': '2026-02-01', 'condition': 'damaged'}, self.admin)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['copy']['copy_number'], 3)
        self.assertEqual(response.data['copy']['accession_number'], 'ACC-9')
        self.assertEqual(response.data['copy']['date_acquired'], '2026-02-01')
        self.assertFalse(response.data['copy']['is_available'])

    def test_add_copy_errors(self):
        self.make_copy(self.book, accession_number='ACC-1')
        archived = self.make_book('900.ARCHIVED', is_archived=True)
        cases = (({}, 400, 'Missing book_id'),
                 ({'book_id': 'abc'}, 400, 'Missing book_id'),
                 ({'book_id': 999999}, 404, 'Book not found'),
                 ({'book_id': archived.pk}, 400, 'Book is archived'),
                 ({'book_id': self.book.pk, 'accession_number': 'ACC-1'}, 400, 'Accession number already exists'),
                 ({'book_id': self.book.pk, 'condition': 'shiny'}, 400, 'Invalid condition'))
        for payload, code, message in cases:
            with self.subTest(payload=payload):
                response = self.post('add_copy', payload, self.admin)
                self.assertEqual((response.status_code, response.data['message']), (code, message))
        self.assertEqual(BookCopy.objects.filter(book=self.book).count(), 2)

    def test_edit_copy_updates_fields_and_availability(self):
        copy = self.book.copies.get()
        response = self.put('edit_copy', {'copy_id': copy.pk, 'condition': 'lost',
                                          'accession_number': 'ACC-5', 'date_acquired': '2020'}, self.admin)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['message'], 'Copy successfully edited')
        self.assertEqual(response.data['copy'], {
            'id': copy.pk, 'copy_number': 1, 'accession_number': 'ACC-5', 'condition': 'lost',
            'date_acquired': '2020', 'is_available': False,
        })
        # Sending only one field leaves the others alone; a copy may keep its own accession number.
        response = self.put('edit_copy', {'copy_id': copy.pk, 'condition': 'good', 'accession_number': 'ACC-5'},
                            self.admin)
        self.assertEqual(response.status_code, 200, response.data)
        copy.refresh_from_db()
        self.assertEqual((copy.condition, copy.accession_number, copy.date_acquired), ('good', 'ACC-5', '2020'))
        self.assertTrue(response.data['copy']['is_available'])

    def test_edit_copy_errors(self):
        copy = self.book.copies.get()
        self.make_copy(self.book, accession_number='ACC-2')
        cases = (({}, 400, 'Missing copy_id'),
                 ({'copy_id': 'abc'}, 400, 'Missing copy_id'),
                 ({'copy_id': 999999}, 404, 'Copy not found'),
                 ({'copy_id': copy.pk, 'condition': 'shiny'}, 400, 'Invalid condition'),
                 ({'copy_id': copy.pk, 'accession_number': 'ACC-2'}, 400, 'Accession number already exists'))
        for payload, code, message in cases:
            with self.subTest(payload=payload):
                response = self.put('edit_copy', payload, self.admin)
                self.assertEqual((response.status_code, response.data['message']), (code, message))
        copy.refresh_from_db()
        self.assertEqual((copy.condition, copy.accession_number), ('good', ''))

    def test_remove_copy_archives_it_and_drops_it_from_the_catalog(self):
        second = self.make_copy(self.book)
        self.loan(copy=second, status=StatusChoices.RETURNED, return_date=date(2026, 10, 6))
        response = self.post('remove_copy', {'copy_id': second.pk}, self.admin)
        self.assertEqual((response.status_code, response.data), (200, {'message': 'Copy successfully removed'}))
        second.refresh_from_db()
        self.assertTrue(second.is_archived)
        self.assertEqual(second.loans.count(), 1)
        row = self.listed(self.book)
        self.assertEqual((row['total_copies'], [c['copy_number'] for c in row['copies']]), (1, [1]))

    def test_remove_copy_refuses_a_copy_on_loan(self):
        copy = self.book.copies.get()
        for status in (StatusChoices.PENDING, StatusChoices.ACTIVE, StatusChoices.DUE, StatusChoices.OVERDUE):
            with self.subTest(status=status):
                loan = self.loan(copy=copy, status=status)
                response = self.post('remove_copy', {'copy_id': copy.pk}, self.admin)
                self.assertEqual((response.status_code, response.data['message']), (400, 'Copy is on loan'))
                copy.refresh_from_db()
                self.assertFalse(copy.is_archived)
                loan.delete()

    def test_remove_copy_errors(self):
        for payload, code, message in (({}, 400, 'Missing copy_id'), ({'copy_id': 999999}, 404, 'Copy not found')):
            with self.subTest(payload=payload):
                response = self.post('remove_copy', payload, self.admin)
                self.assertEqual((response.status_code, response.data['message']), (code, message))


class BorrowCopyTests(CopyAPITestCase):
    def test_borrow_assigns_the_lowest_numbered_available_copy(self):
        BookCopy.objects.filter(book=self.book, copy_number=1).update(condition=ConditionChoices.DAMAGED)
        self.make_copy(self.book, is_archived=True)                       # c.2
        held = self.make_copy(self.book)                                  # c.3
        self.loan(copy=held, user=self.other, status=StatusChoices.ACTIVE)
        expected = self.make_copy(self.book, accession_number='ACC-4')    # c.4
        self.make_copy(self.book)                                         # c.5
        response = self.borrow(self.book)
        self.assertEqual(response.status_code, 200, response.data)
        loan = BorrowRecords.objects.get(user=self.profile)
        self.assertEqual(response.data, {
            'message': 'Book successfully borrowed', 'loan_id': loan.pk,
            'copy': {'id': expected.pk, 'copy_number': 4, 'accession_number': 'ACC-4'},
        })
        self.assertEqual((loan.copy, loan.status), (expected, StatusChoices.PENDING))

    def test_a_second_student_gets_copy_two(self):
        self.make_copy(self.book)
        first, second = self.borrow(self.book), self.borrow(self.book, self.other)
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual((first.data['copy']['copy_number'], second.data['copy']['copy_number']), (1, 2))
        third = self.borrow(self.book, self.third)
        self.assertEqual((third.status_code, third.data['message']), (400, 'All copies are currently borrowed'))

    def test_one_request_or_loan_per_user_and_title(self):
        self.make_copy(self.book)
        for status in (StatusChoices.PENDING, StatusChoices.ACTIVE, StatusChoices.DUE, StatusChoices.OVERDUE):
            with self.subTest(status=status):
                self.loan(status=status)
                response = self.borrow(self.book)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['message'], 'You already have a request or loan for this book')
                self.assertEqual(BorrowRecords.objects.filter(user=self.profile).count(), 1)
                # The free copy is still there for someone else.
                self.assertEqual(self.borrow(self.book, self.other).status_code, 200)
                BorrowRecords.objects.all().delete()
        # Another title is unaffected, and a finished loan does not count.
        self.loan()
        self.assertEqual(self.borrow(self.make_book('800.OTHER')).status_code, 200)
        BorrowRecords.objects.filter(copy__book=self.book).update(status=StatusChoices.RETURNED,
                                                                   return_date=date(2026, 10, 6))
        self.assertEqual(self.borrow(self.book).status_code, 200)

    def test_no_circulating_copy_means_all_borrowed(self):
        BookCopy.objects.filter(book=self.book).update(condition=ConditionChoices.LOST)
        response = self.borrow(self.book)
        self.assertEqual((response.status_code, response.data['message']), (400, 'All copies are currently borrowed'))
        no_copies = Books.objects.create(call_number='800.EMPTY', title='Empty', author='A', publisher='P',
                                         year_published='2026', pages='1')
        response = self.borrow(no_copies)
        self.assertEqual((response.status_code, response.data['message']), (400, 'All copies are currently borrowed'))
        self.assertFalse(BorrowRecords.objects.exists())

    def test_existing_borrow_checks_are_unchanged(self):
        archived = self.make_book('900.ARCHIVED', is_archived=True)
        cases = (({'id_number': 'nobody', 'book_id': self.book.pk}, 404, 'User not found'),
                 ({'id_number': 'reader'}, 400, 'Missing book_id'),
                 ({'id_number': 'reader', 'book_id': 999999}, 404, 'Book not found'),
                 ({'id_number': 'reader', 'book_id': archived.pk}, 400, 'Book is archived and cannot be borrowed'))
        for payload, code, message in cases:
            with self.subTest(payload=payload):
                response = self.post('borrow_book', payload)
                self.assertEqual((response.status_code, response.data['message']), (code, message))
        self.assertFalse(BorrowRecords.objects.exists())

    def test_returned_or_cancelled_loan_frees_its_copy(self):
        copy = self.book.copies.get()
        loan_id = self.borrow(self.book).data['loan_id']
        self.assertEqual(self.borrow(self.book, self.other).status_code, 400)
        self.assertEqual(self.put('cancel_borrowed_book', {'loan_id': loan_id}).status_code, 200)
        response = self.borrow(self.book, self.other)
        self.assertEqual((response.status_code, response.data['copy']['id']), (200, copy.pk))
        loan_id = response.data['loan_id']
        self.assertEqual(self.put('accept_borrowed_book', {'loan_id': loan_id}).status_code, 200)
        self.assertEqual(self.borrow(self.book, self.third).status_code, 400)
        self.assertEqual(self.put('return_book', {'loan_id': loan_id}).status_code, 200)
        response = self.borrow(self.book, self.third)
        self.assertEqual((response.status_code, response.data['copy']['id']), (200, copy.pk))


class LoanByIdTests(CopyAPITestCase):
    def setUp(self):
        super().setUp()
        self.make_copy(self.book)
        self.mine = BorrowRecords.objects.get(pk=self.borrow(self.book).data['loan_id'])
        self.theirs = BorrowRecords.objects.get(pk=self.borrow(self.book, self.other).data['loan_id'])

    def status_of(self, loan):
        loan.refresh_from_db()
        return loan.status

    def test_two_students_with_copies_of_one_title_are_handled_separately(self):
        self.assertNotEqual(self.mine.copy_id, self.theirs.copy_id)
        response = self.put('accept_borrowed_book', {'loan_id': self.theirs.pk})
        self.assertEqual(response.status_code, 200)
        self.theirs.refresh_from_db()
        self.assertEqual(response.data, {'message': 'Borrower Accepted', 'book': {
            'status': StatusChoices.ACTIVE, 'due_date': self.theirs.due_date.isoformat(),
        }})
        self.assertEqual(self.status_of(self.mine), StatusChoices.PENDING)
        response = self.put('return_book', {'loan_id': self.theirs.pk})
        self.assertEqual((response.status_code, response.data), (200, {'message': 'Book returned successfully'}))
        self.assertEqual(self.status_of(self.mine), StatusChoices.PENDING)
        response = self.put('cancel_borrowed_book', {'loan_id': self.mine.pk})
        self.assertEqual((response.status_code, response.data),
                         (200, {'message': 'Book borrow cancelled successfully'}))
        self.assertEqual((self.status_of(self.mine), self.status_of(self.theirs)),
                         (StatusChoices.CANCELLED, StatusChoices.RETURNED))

    def test_missing_or_non_integer_loan_id(self):
        for endpoint in ('accept_borrowed_book', 'return_book', 'cancel_borrowed_book'):
            for payload in ({}, {'loan_id': 'abc'}, {'book_id': self.book.pk}):
                with self.subTest(endpoint=endpoint, payload=payload):
                    response = self.put(endpoint, payload)
                    self.assertEqual((response.status_code, response.data['message']), (400, 'Missing loan_id'))

    def test_unknown_loan_or_wrong_status_is_not_found(self):
        cases = (('accept_borrowed_book', 999999, 'Book not found'),
                 ('return_book', 999999, 'No active book found'),
                 ('cancel_borrowed_book', 999999, 'No active book found'),
                 # A pending request has not been checked out, so it cannot be returned.
                 ('return_book', self.mine.pk, 'No active book found'))
        for endpoint, loan_id, message in cases:
            with self.subTest(endpoint=endpoint, loan_id=loan_id):
                response = self.put(endpoint, {'loan_id': loan_id})
                self.assertEqual((response.status_code, response.data['message']), (404, message))
        self.put('accept_borrowed_book', {'loan_id': self.mine.pk})
        for endpoint, message in (('accept_borrowed_book', 'Book not found'),
                                  ('cancel_borrowed_book', 'No active book found')):
            with self.subTest(endpoint=endpoint, status='Active'):
                response = self.put(endpoint, {'loan_id': self.mine.pk})
                self.assertEqual((response.status_code, response.data['message']), (404, message))
        self.assertEqual(self.status_of(self.mine), StatusChoices.ACTIVE)


class LoanListingTests(CopyAPITestCase):
    def setUp(self):
        super().setUp()
        self.copy = self.book.copies.get()
        self.copy.accession_number = 'ACC-1'
        self.copy.save()
        self.record = self.loan(copy=self.copy)

    def test_all_borrowed_books_add_loan_id_and_copy_ref(self):
        rows = self.client.get(reverse('get_all_borrowed_books')).data['data']
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['id'], self.record.pk)
        self.assertEqual(row['copy'], {'id': self.copy.pk, 'copy_number': 1, 'accession_number': 'ACC-1'})
        self.assertEqual(row['user']['id_number'], 'reader')
        self.assertEqual(row['book']['id'], self.book.pk)
        for key in ('copies', 'total_copies', 'available_copies', 'condition', 'date_acquired'):
            self.assertNotIn(key, row['book'])

    def test_user_borrowed_books_add_loan_id(self):
        rows = self.post('get_user_borrowed_books', {'id': 'reader'}).data['books']
        self.assertEqual(rows, [{'id': self.record.pk, 'cover_url': None, 'due_date': '2026-10-10',
                                 'status': StatusChoices.ACTIVE}])

    def test_dashboard_loans_add_copy_number_and_accession(self):
        row = self.client.get(reverse('get_user_current_loans')).data['results'][0]
        self.assertEqual((row['loan_id'], row['book_id'], row['copy_number'], row['accession_number']),
                         (self.record.pk, self.book.pk, 1, 'ACC-1'))

    def test_csv_export_appends_copy_columns(self):
        response = self.client.get(reverse('export_borrowed_books_csv'))
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0][-5:], ['Book Title', 'ISBN', 'Call Number', 'Copy Number', 'Accession Number'])
        self.assertEqual(rows[1][-5:], [self.book.title, '', self.book.call_number, '1', 'ACC-1'])
